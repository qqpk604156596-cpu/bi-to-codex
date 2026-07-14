"""Behavioral contracts for the approved enterprise-sales metric baseline."""

from __future__ import annotations

import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = PROJECT_ROOT / "src" / "transform" / "compute_duckdb_baseline.py"
MYSQL_SQL_PATH = PROJECT_ROOT / "src" / "sql" / "020_metric_baseline.sql"
HEADERS = (
    "SourceRowId", "InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate",
    "UnitPrice", "CustomerID", "Country", "IsCancellation", "UnknownCustomer", "ZeroPrice", "LineAmount",
)


def load_baseline_module():
    if not BASELINE_PATH.is_file():
        raise AssertionError("compute_duckdb_baseline.py does not exist")
    specification = importlib.util.spec_from_file_location("enterprise_metric_baseline", BASELINE_PATH)
    if specification is None or specification.loader is None:
        raise AssertionError("metric baseline module cannot be imported")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def row(**changes: str) -> dict[str, str]:
    values = {
        "SourceRowId": "1", "InvoiceNo": "A-001", "StockCode": "P-001", "Description": "Product",
        "Quantity": "2", "InvoiceDate": "2010-11-15T09:00:00", "UnitPrice": "5.00",
        "CustomerID": "C-001", "Country": "United Kingdom", "IsCancellation": "false",
        "UnknownCustomer": "false", "ZeroPrice": "false", "LineAmount": "10.00",
    }
    values.update(changes)
    return values


class MetricBaselineTests(unittest.TestCase):
    def test_cancellation_is_excluded_from_completed_metrics_and_retained_in_net_sales(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "sales.csv"
            write_csv(
                csv_path,
                [
                    row(),
                    row(SourceRowId="2", InvoiceNo="C-001", Quantity="-2", IsCancellation="true", LineAmount="-10.00"),
                ],
            )
            result = load_baseline_module().calculate_duckdb_metrics(csv_path, {"id": "all"})

        self.assertEqual(result["gross_sales"], "10.00")
        self.assertEqual(result["cancelled_sales"], "10.00")
        self.assertEqual(result["net_sales"], "0.00")
        self.assertEqual(result["order_count"], 1)
        self.assertEqual(result["units_sold"], 2)

    def test_blank_customer_is_excluded_and_zero_prior_month_returns_null_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "sales.csv"
            write_csv(
                csv_path,
                [
                    row(SourceRowId="1", CustomerID="", UnknownCustomer="true", InvoiceDate="2010-11-14T09:00:00"),
                    row(SourceRowId="2", InvoiceNo="A-002", CustomerID="C-002", InvoiceDate="2010-11-15T09:00:00"),
                ],
            )
            result = load_baseline_module().calculate_duckdb_metrics(
                csv_path,
                {"id": "month", "month": "2010-11"},
            )

        self.assertEqual(result["active_customers"], 1)
        self.assertIsNone(result["sales_mom_pct"])
        self.assertIsNone(result["sales_yoy_pct"])

    def test_reconciliation_respects_amount_and_ratio_tolerances(self) -> None:
        module = load_baseline_module()
        result = module.reconcile_metric_values(
            {"gross_sales": "10.00", "cancellation_rate": "0.10000", "sales_mom_pct": None},
            {"gross_sales": "10.005", "cancellation_rate": "0.10005", "sales_mom_pct": None},
        )

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["metrics"]["gross_sales"]["tolerance"], "0.01")
        self.assertEqual(result["metrics"]["sales_mom_pct"]["status"], "both-null")

    def test_mysql_baseline_sql_targets_the_standardized_view(self) -> None:
        self.assertTrue(MYSQL_SQL_PATH.is_file(), "020_metric_baseline.sql does not exist")
        self.assertIn("vw_fact_sales_line", MYSQL_SQL_PATH.read_text(encoding="utf-8"))

    def test_reconciliation_evidence_writes_its_nested_metric_results(self) -> None:
        module = load_baseline_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir)
            module.write_json_and_markdown(
                output_path,
                "reconciliation",
                "Reconciliation",
                {
                    "name": "Reconciliation",
                    "status": "passed",
                    "generated_at": "2026-07-12T00:00:00+00:00",
                    "slices": [
                        {
                            "id": "all",
                            "reconciliation": {
                                "status": "passed",
                                "metrics": {
                                    "gross_sales": {"difference": "0.00", "status": "passed"}
                                },
                            },
                        }
                    ],
                },
            )
            markdown = (output_path / "reconciliation.md").read_text(encoding="utf-8")

        self.assertIn("gross_sales", markdown)
        self.assertIn("passed", markdown)


if __name__ == "__main__":
    unittest.main()
