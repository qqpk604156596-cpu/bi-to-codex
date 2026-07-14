#!/usr/bin/env python3
"""Inspect a local MySQL source table and enforce the mapping approval gate."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUIRED_ENVIRONMENT = (
    "MYSQL_HOST",
    "MYSQL_PORT",
    "MYSQL_DATABASE",
    "MYSQL_USER",
    "MYSQL_PASSWORD",
    "MYSQL_SOURCE_TABLE",
)
REQUIRED_STANDARD_FIELDS = (
    "InvoiceNo",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "UnitPrice",
    "CustomerID",
    "Country",
)
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def read_mapping(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def mapping_approval_issue(mapping: dict[str, Any] | None) -> str | None:
    if mapping is None:
        return "mapping_file_invalid"
    if mapping.get("status") != "approved":
        return "mapping_not_approved"
    if not isinstance(mapping.get("approved_by"), str) or not mapping["approved_by"].strip():
        return "mapping_approval_owner_missing"
    if not isinstance(mapping.get("approved_at"), str) or not mapping["approved_at"].strip():
        return "mapping_approval_time_missing"
    fields = mapping.get("mapping")
    if not isinstance(fields, dict) or any(not fields.get(name) for name in REQUIRED_STANDARD_FIELDS):
        return "mapping_columns_missing"
    return None


def environment_values(env_file: Path) -> dict[str, str]:
    values = load_dotenv(env_file)
    return {name: values.get(name, os.environ.get(name, "")) for name in REQUIRED_ENVIRONMENT}


def safe_identifier(name: str, error_code: str) -> str:
    if not IDENTIFIER.fullmatch(name):
        raise ValueError(error_code)
    return name


def propose_mapping(columns: list[str]) -> dict[str, str | None]:
    normalized = {column.casefold().replace(" ", ""): column for column in columns}
    synonyms = {
        "InvoiceNo": ("invoice", "invoiceno"),
        "StockCode": ("stockcode",),
        "Description": ("description", "descriptiontext"),
        "Quantity": ("quantity",),
        "InvoiceDate": ("invoicedate",),
        "UnitPrice": ("price", "unitprice"),
        "CustomerID": ("customerid",),
        "Country": ("country",),
    }
    return {
        standard: next((normalized[candidate] for candidate in candidates if candidate in normalized), None)
        for standard, candidates in synonyms.items()
    }


def write_evidence(directory: Path, profile: dict[str, Any], suggested_mapping: dict[str, str | None]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat()
    profile_payload = {"status": "observed", "generated_at": generated_at, **profile}
    suggested_payload = {
        "status": "requires-owner-approval",
        "generated_at": generated_at,
        "mapping": suggested_mapping,
        "missing_standard_fields": [name for name, source in suggested_mapping.items() if source is None],
    }
    (directory / "schema-profile.json").write_text(
        json.dumps(profile_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (directory / "suggested-mapping.json").write_text(
        json.dumps(suggested_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown = [
        "# MySQL schema profile",
        "",
        "- Status: **observed**",
        f"- Generated at: {generated_at}",
        f"- Source table: `{profile['schema']}.{profile['table']}`",
        "",
        "| Column | Type | Nullable |",
        "|---|---|---|",
    ]
    markdown.extend(
        f"| {column['name']} | {column['type']} | {column['nullable']} |" for column in profile["columns"]
    )
    (directory / "schema-profile.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")


def inspect_mysql(values: dict[str, str], evidence_dir: Path) -> int:
    missing = [name for name, value in values.items() if not value]
    if missing:
        print("mysql_environment_missing: " + ", ".join(missing))
        return 2
    try:
        schema = safe_identifier(values["MYSQL_DATABASE"], "mysql_database_identifier_invalid")
        table = safe_identifier(values["MYSQL_SOURCE_TABLE"], "mysql_source_identifier_invalid")
    except ValueError as error:
        print(str(error))
        return 2
    try:
        import mysql.connector  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        print("mysql_connector_missing: install requirements.txt before live schema inspection")
        return 2
    try:
        connection = mysql.connector.connect(
            host=values["MYSQL_HOST"],
            port=int(values["MYSQL_PORT"]),
            database=schema,
            user=values["MYSQL_USER"],
            password=values["MYSQL_PASSWORD"],
            connection_timeout=10,
        )
    except Exception as error:  # Connector exceptions are optional before installation.
        print(f"mysql_connection_failed: {type(error).__name__}")
        return 2
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT COLUMN_NAME AS name, COLUMN_TYPE AS type, IS_NULLABLE AS nullable
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
            """,
            (schema, table),
        )
        columns = list(cursor.fetchall())
        if not columns:
            print("mysql_source_missing: table not found or contains no columns")
            return 2
        cursor.execute(f"SELECT * FROM `{schema}`.`{table}` LIMIT 100")
        sample_count = len(cursor.fetchall())
    except Exception as error:
        print(f"mysql_schema_query_failed: {type(error).__name__}")
        return 2
    finally:
        connection.close()
    profile = {"schema": schema, "table": table, "sample_row_count": sample_count, "columns": columns}
    write_evidence(evidence_dir, profile, propose_mapping([str(column["name"]) for column in columns]))
    print("mysql_schema_profile_written")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=PROJECT_ROOT / ".env")
    parser.add_argument(
        "--mapping-file", type=Path, default=PROJECT_ROOT / "config" / "source-mapping.approved.json"
    )
    parser.add_argument("--evidence-dir", type=Path, default=PROJECT_ROOT / "evidence" / "mapping")
    parser.add_argument("--require-approved-mapping", action="store_true")
    arguments = parser.parse_args()

    mapping = read_mapping(arguments.mapping_file)
    if arguments.require_approved_mapping:
        approval_issue = mapping_approval_issue(mapping)
        if approval_issue:
            print(approval_issue)
            return 2
    return inspect_mysql(environment_values(arguments.env_file), arguments.evidence_dir)


if __name__ == "__main__":
    sys.exit(main())
