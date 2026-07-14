"""Regression contract for datetime support in the CSV quality gate."""

from __future__ import annotations

import importlib.util
import unittest
from datetime import datetime
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "Test-BIDataQuality.py"


def load_quality_module():
    specification = importlib.util.spec_from_file_location("bi_data_quality", SCRIPT_PATH)
    if specification is None or specification.loader is None:
        raise AssertionError("Test-BIDataQuality.py cannot be imported")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class DataQualityDateTimeTests(unittest.TestCase):
    def test_datetime_value_is_accepted_with_explicit_format(self) -> None:
        valid, value = load_quality_module().parse_value(
            "2009-12-01T08:26:00",
            {"type": "datetime", "format": "%Y-%m-%dT%H:%M:%S"},
        )

        self.assertTrue(valid)
        self.assertEqual(value, datetime(2009, 12, 1, 8, 26))


if __name__ == "__main__":
    unittest.main()
