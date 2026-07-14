"""Shared UI contract tests for the prototype and PBIR generator."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
UI_CONTRACT_PATH = PROJECT_ROOT / "report" / "ui-contract.json"
MANIFEST_PATH = PROJECT_ROOT / "report" / "visual-manifest.json"
GENERATOR_PATH = PROJECT_ROOT / "src" / "automation" / "apply_pbir_report.py"


def load_generator():
    specification = importlib.util.spec_from_file_location("apply_pbir_report", GENERATOR_PATH)
    if specification is None or specification.loader is None:
        raise AssertionError("apply_pbir_report.py cannot be imported")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class UIContractTests(unittest.TestCase):
    def test_contract_defines_three_pages_filters_states_and_accessibility(self) -> None:
        contract = json.loads(UI_CONTRACT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(contract["schema_version"], 1)
        self.assertEqual(
            [page["name"] for page in contract["pages"]],
            ["Executive Overview", "Product & Trend Analysis", "Customer & Country Analysis"],
        )
        self.assertEqual(contract["comparison_policy"]["multi_period_value"], "--")
        self.assertEqual(contract["comparison_policy"]["no_comparable_period_value"], "--")
        self.assertGreaterEqual(contract["accessibility"]["minimum_contrast_ratio"], 4.5)

        filter_fields = {
            tuple(filter_definition["field"])
            for page in contract["pages"]
            for filter_definition in page["filters"]
        }
        self.assertTrue(
            {
                ("DimDate", "YearMonth"),
                ("DimCountry", "Country"),
                ("DimProduct", "StockCode"),
                ("DimCustomer", "CustomerID"),
            }.issubset(filter_fields)
        )

    def test_every_contract_component_maps_to_the_pbir_manifest(self) -> None:
        contract = json.loads(UI_CONTRACT_PATH.read_text(encoding="utf-8"))
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        manifest_ids = {visual["id"] for page in manifest["pages"] for visual in page["visuals"]}
        contract_ids = {component["pbir_visual_id"] for page in contract["pages"] for component in page["components"]}
        self.assertEqual(contract_ids, manifest_ids)

    def test_generator_loads_the_shared_ui_contract_as_the_manifest_source(self) -> None:
        generator = load_generator()
        contract = generator.load_ui_contract(UI_CONTRACT_PATH)
        manifest = generator.manifest_from_ui_contract(contract)
        self.assertEqual(manifest["pages"][0]["name"], "Executive Overview")
        self.assertEqual(manifest["pages"][1]["visuals"][1]["visual_type"], "slicer")

    def test_kpi_cards_use_the_shared_three_column_grid(self) -> None:
        contract = json.loads(UI_CONTRACT_PATH.read_text(encoding="utf-8"))
        approved_x_positions = {32, 432, 832}
        approved_y_positions = {104, 252}

        for page in contract["pages"]:
            cards = [component for component in page["components"] if component["role"] == "cardVisual"]
            self.assertTrue(cards, page["name"])
            for card in cards:
                x, y, width, height = card["pbir"]["position"]
                self.assertIn(x, approved_x_positions, card["id"])
                self.assertIn(y, approved_y_positions, card["id"])
                self.assertEqual(width, 380, card["id"])
                self.assertEqual(height, 132, card["id"])

    def test_customer_page_uses_six_existing_approved_metrics(self) -> None:
        contract = json.loads(UI_CONTRACT_PATH.read_text(encoding="utf-8"))
        customer_page = next(page for page in contract["pages"] if page["name"] == "Customer & Country Analysis")
        customer_metrics = [
            component["pbir"]["metric_id"]
            for component in customer_page["components"]
            if component["role"] == "cardVisual"
        ]
        self.assertEqual(
            customer_metrics,
            [
                "net_sales",
                "order_count",
                "active_customers",
                "average_order_value",
                "cancelled_sales",
                "cancellation_rate",
            ],
        )


if __name__ == "__main__":
    unittest.main()
