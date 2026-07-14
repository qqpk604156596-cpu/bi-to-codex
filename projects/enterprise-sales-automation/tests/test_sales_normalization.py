"""Behavioral contract for UCI Online Retail row normalization."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOADER_PATH = PROJECT_ROOT / "src" / "extract" / "load_online_retail_ii.py"


def load_loader_module():
    if not LOADER_PATH.is_file():
        raise AssertionError("load_online_retail_ii.py does not exist")
    specification = importlib.util.spec_from_file_location("enterprise_sales_loader", LOADER_PATH)
    if specification is None or specification.loader is None:
        raise AssertionError("loader module cannot be imported")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class SalesNormalizationTests(unittest.TestCase):
    def test_existing_text_schema_is_migrated_without_changing_row_count(self) -> None:
        module = load_loader_module()

        class Cursor:
            def __init__(self) -> None:
                self.statements: list[str] = []
                self.result = None

            def execute(self, statement: str, _parameters=None) -> None:
                self.statements.append(statement)
                if "INFORMATION_SCHEMA.COLUMNS" in statement:
                    self.result = ("text", 65535)
                elif "COUNT(*), MAX(CHAR_LENGTH" in statement:
                    self.result = (1067366, 35)
                elif "SELECT COUNT(*)" in statement:
                    self.result = (1067366,)
                elif "INFORMATION_SCHEMA.STATISTICS" in statement:
                    self.result = []

            def fetchone(self):
                return self.result

            def fetchall(self):
                return self.result

        cursor = Cursor()
        module.ensure_product_refresh_schema(cursor, "enterprise_sales", "online_retail_raw")

        statements = "\n".join(cursor.statements)
        self.assertIn("MODIFY COLUMN `DescriptionText` VARCHAR(512) NULL", statements)
        self.assertIn("ADD INDEX `ix_product_cover` (`StockCode`, `DescriptionText`)", statements)

    def test_existing_schema_migration_rejects_descriptions_over_512_characters(self) -> None:
        module = load_loader_module()

        class Cursor:
            def execute(self, statement: str, _parameters=None) -> None:
                self.statement = statement
                self.result = ("text", 65535) if "INFORMATION_SCHEMA.COLUMNS" in statement else (1, 513)

            def fetchone(self):
                return self.result

        with self.assertRaisesRegex(ValueError, "description_text_exceeds_512"):
            module.ensure_product_refresh_schema(Cursor(), "enterprise_sales", "online_retail_raw")

    def test_cancellation_invoice_is_retained_and_flagged(self) -> None:
        normalized = load_loader_module().classify_row(
            {
                "Invoice": "C536379",
                "StockCode": "D",
                "Description": "Discount",
                "Quantity": "-1",
                "InvoiceDate": "2009-12-01 09:41:00",
                "Price": "27.50",
                "Customer ID": "14527",
                "Country": "United Kingdom",
            }
        )

        self.assertTrue(normalized["IsCancellation"])
        self.assertEqual(normalized["Quantity"], -1)

    def test_missing_customer_is_preserved_as_unknown(self) -> None:
        normalized = load_loader_module().classify_row(
            {
                "Invoice": "536365",
                "StockCode": "85123A",
                "Description": "WHITE HANGING HEART T-LIGHT HOLDER",
                "Quantity": "6",
                "InvoiceDate": "2009-12-01 08:26:00",
                "Price": "2.55",
                "Customer ID": "",
                "Country": "United Kingdom",
            }
        )

        self.assertIsNone(normalized["CustomerID"])
        self.assertTrue(normalized["UnknownCustomer"])

    def test_numeric_customer_id_does_not_keep_excel_decimal_suffix(self) -> None:
        normalized = load_loader_module().classify_row(
            {
                "Invoice": "536365",
                "StockCode": "85123A",
                "Description": "test",
                "Quantity": "1",
                "InvoiceDate": "2009-12-01 08:26:00",
                "Price": "2.55",
                "Customer ID": 14527.0,
                "Country": "United Kingdom",
            }
        )

        self.assertEqual(normalized["CustomerID"], "14527")

    def test_negative_unit_price_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unit_price_negative"):
            load_loader_module().classify_row(
                {
                    "Invoice": "536365",
                    "StockCode": "85123A",
                    "Description": "test",
                    "Quantity": "1",
                    "InvoiceDate": "2009-12-01 08:26:00",
                    "Price": "-1",
                    "Customer ID": "14527",
                    "Country": "United Kingdom",
                }
            )

    def test_zero_unit_price_is_preserved_and_flagged(self) -> None:
        normalized = load_loader_module().classify_row(
            {
                "Invoice": "536366",
                "StockCode": "85123A",
                "Description": "test",
                "Quantity": "1",
                "InvoiceDate": "2009-12-01 08:28:00",
                "Price": "0",
                "Customer ID": "14527",
                "Country": "United Kingdom",
            }
        )

        self.assertEqual(normalized["UnitPrice"], "0.00")
        self.assertTrue(normalized["ZeroPrice"])

    def test_workbook_outside_project_is_rejected(self) -> None:
        outside_workbook = Path("C:/Temp/online_retail_II.xlsx")
        module = load_loader_module()
        self.assertTrue(
            hasattr(module, "validate_workbook_path"),
            "validate_workbook_path is required before any workbook is loaded",
        )

        with self.assertRaisesRegex(ValueError, "workbook_path_outside_project"):
            module.validate_workbook_path(outside_workbook, PROJECT_ROOT)


if __name__ == "__main__":
    unittest.main()
