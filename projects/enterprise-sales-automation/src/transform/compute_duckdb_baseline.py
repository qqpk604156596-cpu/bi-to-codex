#!/usr/bin/env python3
"""Calculate the approved enterprise-sales metric baseline from the validation CSV."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
METRIC_IDS = (
    "gross_sales", "cancelled_sales", "net_sales", "order_count", "units_sold",
    "active_customers", "average_order_value", "cancellation_rate", "sales_mom_pct", "sales_yoy_pct",
)
RATIO_METRICS = {"cancellation_rate", "sales_mom_pct", "sales_yoy_pct"}
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def decimal_string(value: Any) -> str:
    decimal_value = Decimal(str(value or 0))
    raw = format(decimal_value, "f")
    if "." not in raw:
        return f"{raw}.00"
    whole, fraction = raw.split(".", 1)
    fraction = fraction.rstrip("0")
    if len(fraction) < 2:
        fraction = fraction.ljust(2, "0")
    return f"{whole}.{fraction}"


def month_offsets(month: str) -> tuple[str, str]:
    current = datetime.strptime(month, "%Y-%m")
    previous_year = current.year - 1 if current.month == 1 else current.year
    previous_month = 12 if current.month == 1 else current.month - 1
    return f"{previous_year:04d}-{previous_month:02d}", f"{current.year - 1:04d}-{current.month:02d}"


def create_duckdb_fact(connection: Any, csv_path: Path) -> None:
    escaped_path = str(csv_path).replace("'", "''")
    connection.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW fact_sales_line AS
        SELECT
            SourceRowId,
            InvoiceNo,
            StockCode,
            Description,
            CAST(Quantity AS BIGINT) AS Quantity,
            CAST(InvoiceDate AS TIMESTAMP) AS InvoiceDate,
            CAST(UnitPrice AS DECIMAL(20, 4)) AS UnitPrice,
            CustomerID,
            Country,
            lower(IsCancellation) IN ('true', '1', 'yes') AS IsCancellation,
            lower(UnknownCustomer) IN ('true', '1', 'yes') AS UnknownCustomer,
            lower(ZeroPrice) IN ('true', '1', 'yes') AS ZeroPrice,
            CAST(LineAmount AS DECIMAL(20, 4)) AS LineAmount
        FROM read_csv('{escaped_path}', header = true, all_varchar = true)
        """
    )


def slice_where(slice_definition: dict[str, str], *, include_month: bool = True) -> tuple[str, list[str]]:
    slice_id = slice_definition.get("id")
    if slice_id == "all":
        return "", []
    if slice_id == "country":
        return "WHERE Country = ?", [slice_definition["country"]]
    if slice_id == "month" and include_month:
        return "WHERE strftime(InvoiceDate, '%Y-%m') = ?", [slice_definition["month"]]
    if slice_id == "month":
        return "", []
    raise ValueError("unsupported_metric_slice")


def calculate_base_metrics(connection: Any, where_clause: str, parameters: list[str]) -> dict[str, Any]:
    row = connection.execute(
        f"""
        SELECT
            COALESCE(SUM(CASE WHEN NOT IsCancellation AND Quantity > 0 AND UnitPrice > 0 THEN LineAmount ELSE 0 END), 0) AS gross_sales,
            COALESCE(SUM(CASE WHEN IsCancellation THEN ABS(LineAmount) ELSE 0 END), 0) AS cancelled_sales,
            COALESCE(SUM(LineAmount), 0) AS net_sales,
            COUNT(DISTINCT CASE WHEN NOT IsCancellation AND Quantity > 0 AND UnitPrice > 0 THEN InvoiceNo END) AS order_count,
            COALESCE(SUM(CASE WHEN NOT IsCancellation AND Quantity > 0 AND UnitPrice > 0 THEN Quantity ELSE 0 END), 0) AS units_sold,
            COUNT(DISTINCT CASE WHEN NOT IsCancellation AND Quantity > 0 AND UnitPrice > 0 AND NULLIF(trim(CustomerID), '') IS NOT NULL THEN CustomerID END) AS active_customers,
            COUNT(DISTINCT CASE WHEN IsCancellation THEN InvoiceNo END) AS cancelled_invoice_count,
            COUNT(DISTINCT NULLIF(trim(InvoiceNo), '')) AS all_invoice_count
        FROM fact_sales_line
        {where_clause}
        """,
        parameters,
    ).fetchone()
    names = (
        "gross_sales", "cancelled_sales", "net_sales", "order_count", "units_sold",
        "active_customers", "cancelled_invoice_count", "all_invoice_count",
    )
    return dict(zip(names, row, strict=True))


def calculate_period_net_sales(connection: Any, month: str, country: str | None = None) -> Decimal:
    clauses = ["strftime(InvoiceDate, '%Y-%m') = ?"]
    parameters: list[str] = [month]
    if country is not None:
        clauses.append("Country = ?")
        parameters.append(country)
    result = connection.execute(
        "SELECT COALESCE(SUM(LineAmount), 0) FROM fact_sales_line WHERE " + " AND ".join(clauses),
        parameters,
    ).fetchone()[0]
    return Decimal(str(result or 0))


def calculate_duckdb_metrics(csv_path: Path, slice_definition: dict[str, str]) -> dict[str, str | int | None]:
    try:
        import duckdb
    except ModuleNotFoundError as error:
        raise RuntimeError("duckdb_dependency_missing") from error
    connection = duckdb.connect()
    try:
        create_duckdb_fact(connection, csv_path)
        where_clause, parameters = slice_where(slice_definition)
        base = calculate_base_metrics(connection, where_clause, parameters)
        gross_sales = Decimal(str(base["gross_sales"]))
        order_count = int(base["order_count"])
        cancelled_invoice_count = int(base["cancelled_invoice_count"])
        all_invoice_count = int(base["all_invoice_count"])
        metrics: dict[str, str | int | None] = {
            "gross_sales": decimal_string(gross_sales),
            "cancelled_sales": decimal_string(base["cancelled_sales"]),
            "net_sales": decimal_string(base["net_sales"]),
            "order_count": order_count,
            "units_sold": int(base["units_sold"]),
            "active_customers": int(base["active_customers"]),
            "average_order_value": decimal_string(gross_sales / order_count) if order_count else None,
            "cancellation_rate": decimal_string(Decimal(cancelled_invoice_count) / all_invoice_count) if all_invoice_count else None,
            "sales_mom_pct": None,
            "sales_yoy_pct": None,
        }
        if slice_definition.get("id") == "month":
            previous_month, prior_year_month = month_offsets(slice_definition["month"])
            current_net_sales = Decimal(str(base["net_sales"]))
            previous_net_sales = calculate_period_net_sales(connection, previous_month)
            prior_year_net_sales = calculate_period_net_sales(connection, prior_year_month)
            metrics["sales_mom_pct"] = (
                decimal_string((current_net_sales - previous_net_sales) / previous_net_sales)
                if previous_net_sales else None
            )
            metrics["sales_yoy_pct"] = (
                decimal_string((current_net_sales - prior_year_net_sales) / prior_year_net_sales)
                if prior_year_net_sales else None
            )
        return metrics
    finally:
        connection.close()


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
    names = ("MYSQL_HOST", "MYSQL_PORT", "MYSQL_DATABASE", "MYSQL_USER", "MYSQL_PASSWORD")
    return {name: dotenv.get(name, os.environ.get(name, "")) for name in names}


def mysql_slice_where(slice_definition: dict[str, str], *, include_month: bool = True) -> tuple[str, list[str]]:
    slice_id = slice_definition.get("id")
    if slice_id == "all":
        return "", []
    if slice_id == "country":
        return "WHERE `Country` = %s", [slice_definition["country"]]
    if slice_id == "month" and include_month:
        return "WHERE DATE_FORMAT(`InvoiceDate`, '%Y-%m') = %s", [slice_definition["month"]]
    if slice_id == "month":
        return "", []
    raise ValueError("unsupported_metric_slice")


def calculate_mysql_metrics(values: dict[str, str], slice_definition: dict[str, str]) -> dict[str, str | int | None]:
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise RuntimeError("mysql_environment_missing")
    database = values["MYSQL_DATABASE"]
    if not IDENTIFIER.fullmatch(database):
        raise RuntimeError("mysql_database_identifier_invalid")
    try:
        import mysql.connector
    except ModuleNotFoundError as error:
        raise RuntimeError("mysql_connector_missing") from error
    connection = mysql.connector.connect(
        host=values["MYSQL_HOST"], port=int(values["MYSQL_PORT"]), database=database,
        user=values["MYSQL_USER"], password=values["MYSQL_PASSWORD"], connection_timeout=10,
    )
    try:
        where_clause, parameters = mysql_slice_where(slice_definition)
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            f"""
            SELECT
                COALESCE(SUM(CASE WHEN `IsCancellation` = 0 AND `Quantity` > 0 AND `UnitPrice` > 0 THEN `LineAmount` ELSE 0 END), 0) AS gross_sales,
                COALESCE(SUM(CASE WHEN `IsCancellation` = 1 THEN ABS(`LineAmount`) ELSE 0 END), 0) AS cancelled_sales,
                COALESCE(SUM(`LineAmount`), 0) AS net_sales,
                COUNT(DISTINCT CASE WHEN `IsCancellation` = 0 AND `Quantity` > 0 AND `UnitPrice` > 0 THEN `InvoiceNo` END) AS order_count,
                COALESCE(SUM(CASE WHEN `IsCancellation` = 0 AND `Quantity` > 0 AND `UnitPrice` > 0 THEN `Quantity` ELSE 0 END), 0) AS units_sold,
                COUNT(DISTINCT CASE WHEN `IsCancellation` = 0 AND `Quantity` > 0 AND `UnitPrice` > 0 AND NULLIF(TRIM(`CustomerID`), '') IS NOT NULL THEN `CustomerID` END) AS active_customers,
                COUNT(DISTINCT CASE WHEN `IsCancellation` = 1 THEN `InvoiceNo` END) AS cancelled_invoice_count,
                COUNT(DISTINCT NULLIF(TRIM(`InvoiceNo`), '')) AS all_invoice_count
            FROM `vw_fact_sales_line`
            {where_clause}
            """,
            parameters,
        )
        base = cursor.fetchone()
        gross_sales = Decimal(str(base["gross_sales"] or 0))
        order_count = int(base["order_count"])
        cancelled_invoice_count = int(base["cancelled_invoice_count"])
        all_invoice_count = int(base["all_invoice_count"])
        metrics: dict[str, str | int | None] = {
            "gross_sales": decimal_string(gross_sales),
            "cancelled_sales": decimal_string(base["cancelled_sales"]),
            "net_sales": decimal_string(base["net_sales"]),
            "order_count": order_count,
            "units_sold": int(base["units_sold"]),
            "active_customers": int(base["active_customers"]),
            "average_order_value": decimal_string(gross_sales / order_count) if order_count else None,
            "cancellation_rate": decimal_string(Decimal(cancelled_invoice_count) / all_invoice_count) if all_invoice_count else None,
            "sales_mom_pct": None,
            "sales_yoy_pct": None,
        }
        if slice_definition.get("id") == "month":
            previous_month, prior_year_month = month_offsets(slice_definition["month"])
            def period_net_sales(month: str) -> Decimal:
                cursor.execute(
                    "SELECT COALESCE(SUM(`LineAmount`), 0) AS net_sales FROM `vw_fact_sales_line` WHERE DATE_FORMAT(`InvoiceDate`, '%Y-%m') = %s",
                    [month],
                )
                return Decimal(str(cursor.fetchone()["net_sales"] or 0))
            current_net_sales = Decimal(str(base["net_sales"] or 0))
            previous_net_sales = period_net_sales(previous_month)
            prior_year_net_sales = period_net_sales(prior_year_month)
            metrics["sales_mom_pct"] = decimal_string((current_net_sales - previous_net_sales) / previous_net_sales) if previous_net_sales else None
            metrics["sales_yoy_pct"] = decimal_string((current_net_sales - prior_year_net_sales) / prior_year_net_sales) if prior_year_net_sales else None
        return metrics
    finally:
        connection.close()


def reconcile_metric_values(
    duckdb_metrics: dict[str, str | int | None], mysql_metrics: dict[str, str | int | None]
) -> dict[str, Any]:
    results: dict[str, dict[str, Any]] = {}
    has_failure = False
    for metric_id in METRIC_IDS:
        duckdb_value = duckdb_metrics.get(metric_id)
        mysql_value = mysql_metrics.get(metric_id)
        tolerance = Decimal("0.0001") if metric_id in RATIO_METRICS else Decimal("0.01")
        if duckdb_value is None and mysql_value is None:
            results[metric_id] = {"duckdb": None, "mysql": None, "difference": None, "tolerance": str(tolerance), "status": "both-null"}
            continue
        if duckdb_value is None or mysql_value is None:
            results[metric_id] = {"duckdb": duckdb_value, "mysql": mysql_value, "difference": None, "tolerance": str(tolerance), "status": "null-mismatch"}
            has_failure = True
            continue
        difference = abs(Decimal(str(duckdb_value)) - Decimal(str(mysql_value)))
        status = "passed" if difference <= tolerance else "failed"
        results[metric_id] = {"duckdb": duckdb_value, "mysql": mysql_value, "difference": decimal_string(difference), "tolerance": str(tolerance), "status": status}
        has_failure = has_failure or status == "failed"
    return {"status": "failed" if has_failure else "passed", "metrics": results}


def write_json_and_markdown(path: Path, filename: str, title: str, payload: dict[str, Any]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / f"{filename}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [f"# {title}", "", f"- Status: **{payload['status']}**", f"- Generated at: {payload['generated_at']}", ""]
    if payload["slices"] and "reconciliation" in payload["slices"][0]:
        lines.extend(["| Slice | Metric | Difference | Status |", "|---|---|---:|---|"])
        for item in payload["slices"]:
            for metric_id, value in item["reconciliation"]["metrics"].items():
                lines.append(f"| {item['id']} | {metric_id} | {value['difference'] if value['difference'] is not None else 'null'} | {value['status']} |")
    else:
        lines.extend(["| Slice | Metric | Value |", "|---|---|---:|"])
        for item in payload["slices"]:
            for metric_id, value in item["metrics"].items():
                lines.append(f"| {item['id']} | {metric_id} | {value if value is not None else 'null'} |")
    (path / f"{filename}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_all_baselines(csv_path: Path, values: dict[str, str]) -> int:
    slices = [
        {"id": "all"},
        {"id": "country", "country": "United Kingdom"},
        {"id": "month", "month": "2010-11"},
    ]
    duckdb_slices = [{**item, "metrics": calculate_duckdb_metrics(csv_path, item)} for item in slices]
    mysql_slices = [{**item, "metrics": calculate_mysql_metrics(values, item)} for item in slices]
    reconciliation_slices = [
        {"id": definition["id"], "reconciliation": reconcile_metric_values(duckdb_item["metrics"], mysql_item["metrics"])}
        for definition, duckdb_item, mysql_item in zip(slices, duckdb_slices, mysql_slices, strict=True)
    ]
    generated_at = datetime.now(timezone.utc).isoformat()
    evidence_path = PROJECT_ROOT / "evidence" / "metrics"
    common = {"generated_at": generated_at, "dataset": "data/interim/fact_sales_line.csv", "metric_ids": list(METRIC_IDS)}
    write_json_and_markdown(evidence_path, "duckdb-baseline", "DuckDB metric baseline", {"name": "DuckDB metric baseline", "status": "passed", **common, "slices": duckdb_slices})
    write_json_and_markdown(evidence_path, "mysql-baseline", "MySQL metric baseline", {"name": "MySQL metric baseline", "status": "passed", **common, "slices": mysql_slices})
    status = "passed" if all(item["reconciliation"]["status"] == "passed" for item in reconciliation_slices) else "failed"
    write_json_and_markdown(evidence_path, "reconciliation", "DuckDB and MySQL metric reconciliation", {"name": "DuckDB and MySQL metric reconciliation", "status": status, **common, "slices": reconciliation_slices})
    print("metric_reconciliation_passed" if status == "passed" else "metric_reconciliation_failed")
    return 0 if status == "passed" else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-path", type=Path, default=PROJECT_ROOT / "data" / "interim" / "fact_sales_line.csv")
    parser.add_argument("--slice", choices=("all", "country", "month"))
    parser.add_argument("--country", default="United Kingdom")
    parser.add_argument("--month", default="2010-11")
    parser.add_argument("--env-file", type=Path, default=PROJECT_ROOT / ".env")
    arguments = parser.parse_args()
    if arguments.slice is None:
        return run_all_baselines(arguments.csv_path, mysql_environment(arguments.env_file))
    definition: dict[str, str] = {"id": arguments.slice}
    if arguments.slice == "country":
        definition["country"] = arguments.country
    if arguments.slice == "month":
        definition["month"] = arguments.month
    print(json.dumps(calculate_duckdb_metrics(arguments.csv_path, definition), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
