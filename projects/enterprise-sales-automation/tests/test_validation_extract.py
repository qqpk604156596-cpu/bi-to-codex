"""Behavioral contract for the MySQL validation extract exporter."""

from __future__ import annotations

import importlib.util
import unittest
from datetime import datetime
from decimal import Decimal
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPORTER_PATH = PROJECT_ROOT / "src" / "transform" / "export_validation_extract.py"


def load_exporter_module():
    if not EXPORTER_PATH.is_file():
        raise AssertionError("export_validation_extract.py does not exist")
    specification = importlib.util.spec_from_file_location("enterprise_sales_validation_export", EXPORTER_PATH)
    if specification is None or specification.loader is None:
        raise AssertionError("validation extract exporter cannot be imported")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class ValidationExtractTests(unittest.TestCase):
    def test_format_export_row_preserves_datetime_and_flags(self) -> None:
        exporter = load_exporter_module()
        formatted = exporter.format_export_row(
            {
                "SourceRowId": "2009-2010:2",
                "InvoiceNo": "536365",
                "StockCode": "85123A",
                "Description": "WHITE HANGING HEART T-LIGHT HOLDER",
                "Quantity": 6,
                "InvoiceDate": datetime(2009, 12, 1, 8, 26),
                "UnitPrice": Decimal("2.55"),
                "CustomerID": "17850",
                "Country": "United Kingdom",
                "IsCancellation": 0,
                "UnknownCustomer": 0,
                "ZeroPrice": 0,
                "LineAmount": Decimal("15.30"),
            }
        )

        self.assertEqual(formatted["InvoiceDate"], "2009-12-01T08:26:00")
        self.assertEqual(formatted["UnitPrice"], "2.55")
        self.assertEqual(formatted["LineAmount"], "15.30")
        self.assertEqual(formatted["IsCancellation"], "false")
        self.assertEqual(formatted["UnknownCustomer"], "false")
        self.assertEqual(formatted["ZeroPrice"], "false")


if __name__ == "__main__":
    unittest.main()
