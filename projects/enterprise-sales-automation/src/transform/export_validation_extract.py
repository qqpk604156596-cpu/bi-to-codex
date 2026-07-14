#!/usr/bin/env python3
"""Export the standardized MySQL sales view to the ignored CSV quality-check input."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
EXPORT_COLUMNS = (
    "SourceRowId",
    "InvoiceNo",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "UnitPrice",
    "CustomerID",
    "Country",
    "IsCancellation",
    "UnknownCustomer",
    "ZeroPrice",
    "LineAmount",
)
REQUIRED_ENVIRONMENT = ("MYSQL_HOST", "MYSQL_PORT", "MYSQL_DATABASE", "MYSQL_USER", "MYSQL_PASSWORD")


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


def mysql_environment(env_file: Path) -> dict[str, str]:
    dotenv = load_dotenv(env_file)
    return {name: dotenv.get(name, os.environ.get(name, "")) for name in REQUIRED_ENVIRONMENT}


def safe_identifier(value: str, error_code: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(error_code)
    return value


def format_decimal(value: Any) -> str:
    decimal_value = Decimal(str(value))
    raw = format(decimal_value, "f")
    if "." not in raw:
        return f"{raw}.00"
    whole, fraction = raw.split(".", 1)
    fraction = fraction.rstrip("0")
    if len(fraction) < 2:
        fraction = fraction.ljust(2, "0")
    return f"{whole}.{fraction}"


def format_export_row(row: dict[str, Any]) -> dict[str, str]:
    invoice_date = row["InvoiceDate"]
    if not isinstance(invoice_date, datetime):
        raise ValueError("invoice_date_not_datetime")
    return {
        "SourceRowId": str(row["SourceRowId"]),
        "InvoiceNo": str(row["InvoiceNo"]),
        "StockCode": str(row["StockCode"]),
        "Description": "" if row["Description"] is None else str(row["Description"]),
        "Quantity": str(row["Quantity"]),
        "InvoiceDate": invoice_date.strftime("%Y-%m-%dT%H:%M:%S"),
        "UnitPrice": format_decimal(row["UnitPrice"]),
        "CustomerID": "" if row["CustomerID"] is None else str(row["CustomerID"]),
        "Country": str(row["Country"]),
        "IsCancellation": str(bool(row["IsCancellation"])).lower(),
        "UnknownCustomer": str(bool(row["UnknownCustomer"])).lower(),
        "ZeroPrice": str(bool(row["ZeroPrice"])).lower(),
        "LineAmount": format_decimal(row["LineAmount"]),
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_evidence(evidence_dir: Path, output_path: Path, row_count: int) -> None:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "name": "MySQL validation extract",
        "status": "passed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "MySQL vw_fact_sales_line",
        "output_path": output_path.relative_to(PROJECT_ROOT).as_posix(),
        "row_count": row_count,
        "column_count": len(EXPORT_COLUMNS),
        "sha256": sha256(output_path),
    }
    (evidence_dir / "validation-extract.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown = [
        "# MySQL validation extract",
        "",
        "- Status: **passed**",
        "- Source: `MySQL vw_fact_sales_line`",
        f"- Output: `{report['output_path']}`",
        f"- Rows: {row_count}",
        f"- Columns: {len(EXPORT_COLUMNS)}",
        f"- SHA-256: `{report['sha256']}`",
    ]
    (evidence_dir / "validation-extract.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")


def export_validation_extract(values: dict[str, str], output_path: Path) -> int:
    missing = [name for name, value in values.items() if not value]
    if missing:
        print("mysql_environment_missing: " + ", ".join(missing))
        return 2
    try:
        schema = safe_identifier(values["MYSQL_DATABASE"], "mysql_database_identifier_invalid")
    except ValueError as error:
        print(str(error))
        return 2
    try:
        import mysql.connector  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        print("mysql_connector_missing: install requirements.txt before exporting")
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
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT " + ", ".join(f"`{column}`" for column in EXPORT_COLUMNS) +
            " FROM `vw_fact_sales_line` ORDER BY `SourceRowId`"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        row_count = 0
        with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=EXPORT_COLUMNS)
            writer.writeheader()
            for row in cursor:
                writer.writerow(format_export_row(row))
                row_count += 1
    except Exception as error:
        print(f"validation_extract_failed: {type(error).__name__}")
        return 2
    finally:
        if "connection" in locals() and connection.is_connected():
            connection.close()
    write_evidence(PROJECT_ROOT / "evidence" / "data-quality", output_path, row_count)
    print(f"validation_extract_written: {row_count}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=PROJECT_ROOT / ".env")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "data" / "interim" / "fact_sales_line.csv")
    arguments = parser.parse_args()
    return export_validation_extract(mysql_environment(arguments.env_file), arguments.output)


if __name__ == "__main__":
    sys.exit(main())
