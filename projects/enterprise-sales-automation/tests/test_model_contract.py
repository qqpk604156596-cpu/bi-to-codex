"""File-level contract for the enterprise semantic-model and simulated RLS design."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "model" / "model-spec.json"
METRICS_PATH = PROJECT_ROOT / "config" / "metrics.json"
DAX_PATH = PROJECT_ROOT / "src" / "dax" / "enterprise-sales-measures.dax"
RLS_SQL_PATH = PROJECT_ROOT / "src" / "sql" / "030_security_user_country.sql"
MODEL_VALIDATOR_PATH = PROJECT_ROOT.parents[1] / "scripts" / "Test-BIModelSpec.py"


def load_model_validator():
    specification = importlib.util.spec_from_file_location("bi_model_spec", MODEL_VALIDATOR_PATH)
    if specification is None or specification.loader is None:
        raise AssertionError("Test-BIModelSpec.py cannot be imported")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class ModelContractTests(unittest.TestCase):
    def test_model_spec_passes_file_level_validation(self) -> None:
        model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
        metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))

        issues, summary = load_model_validator().validate_model_spec(model, metrics)

        self.assertEqual(issues, [])
        self.assertEqual(summary["relationship_count"], 5)
        self.assertEqual(summary["measure_count"], 10)

    def test_security_bridge_filters_country_without_a_direct_fact_relationship(self) -> None:
        model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
        security_table = next(table for table in model["tables"] if table["name"] == "SecurityUserCountry")

        self.assertEqual(security_table["kind"], "security-bridge")
        self.assertEqual(security_table["columns"], ["UserPrincipalName", "Country", "IsActive"])
        self.assertTrue(all(
            not (relationship["from_table"] == "SecurityUserCountry" and relationship["to_table"] == "FactSalesLine")
            for relationship in model["relationships"]
        ))
        self.assertTrue(any(
            relationship["from_table"] == "SecurityUserCountry" and relationship["to_table"] == "DimCountry"
            for relationship in model["relationships"]
        ))

    def test_dax_contains_all_approved_metrics_without_profit_or_margin(self) -> None:
        self.assertTrue(DAX_PATH.is_file(), "enterprise-sales-measures.dax does not exist")
        dax = DAX_PATH.read_text(encoding="utf-8")
        metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))["metrics"]

        for metric in metrics:
            self.assertIn(metric["name"] + " =", dax)
        self.assertIn("HASONEVALUE ( DimDate[YearMonth] )", dax)
        self.assertNotIn("Profit", dax)
        self.assertNotIn("Margin", dax)

    def test_rls_script_uses_only_simulated_users_and_has_an_unmapped_user(self) -> None:
        self.assertTrue(RLS_SQL_PATH.is_file(), "030_security_user_country.sql does not exist")
        sql = RLS_SQL_PATH.read_text(encoding="utf-8")

        self.assertIn("manager.uk@example.invalid", sql)
        self.assertIn("manager.fr@example.invalid", sql)
        self.assertIn("unmapped.manager@example.invalid", sql)
        self.assertNotIn("@example.com", sql)


if __name__ == "__main__":
    unittest.main()
