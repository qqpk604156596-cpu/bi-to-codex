"""Contract tests for the generated Enterprise Sales semantic-model assets."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUTOMATION_PATH = PROJECT_ROOT / "src" / "automation" / "apply_pbip_model.py"
STANDARDIZED_VIEWS_SQL_PATH = PROJECT_ROOT / "src" / "sql" / "010_create_standardized_views.sql"
SCHEMA_SQL_PATH = PROJECT_ROOT / "src" / "sql" / "001_create_schema.sql"
LOADER_PATH = PROJECT_ROOT / "src" / "extract" / "load_online_retail_ii.py"


def load_generator():
    specification = importlib.util.spec_from_file_location("apply_pbip_model", AUTOMATION_PATH)
    if specification is None or specification.loader is None:
        raise AssertionError("apply_pbip_model.py cannot be imported")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class PbipModelAssetTests(unittest.TestCase):
    def test_generator_defines_portable_mysql_import_model_assets(self) -> None:
        self.assertTrue(AUTOMATION_PATH.is_file(), "PBIP model generator does not exist")
        assets = load_generator().build_asset_map()

        expected_paths = {
            "model.tmdl",
            "expressions.tmdl",
            "relationships.tmdl",
            "tables/FactSalesLine.tmdl",
            "tables/DimDate.tmdl",
            "tables/DimProduct.tmdl",
            "tables/DimCustomer.tmdl",
            "tables/DimCountry.tmdl",
            "tables/SecurityUserCountry.tmdl",
            "roles/CountryManager.tmdl",
        }
        self.assertTrue(expected_paths.issubset(assets))

        model_text = assets["model.tmdl"]
        expressions_text = assets["expressions.tmdl"]
        role_text = assets["roles/CountryManager.tmdl"]
        fact_text = assets["tables/FactSalesLine.tmdl"]
        relationships_text = assets["relationships.tmdl"]

        self.assertIn("ref table FactSalesLine", model_text)
        self.assertIn("ref role CountryManager", model_text)
        self.assertIn("expression MySqlServer", expressions_text)
        self.assertIn("expression MySqlDatabase", expressions_text)
        self.assertIn("MySQL.Database(MySqlServer, MySqlDatabase", fact_text)
        self.assertIn("USERPRINCIPALNAME()", role_text)
        self.assertIn("securityFilteringBehavior: bothDirections", relationships_text)
        self.assertIn("measure 'Gross Sales' = ```", fact_text)
        self.assertIn("measure 'Sales MoM %' = ```", fact_text)
        self.assertIn("\n\t\t```\n\t\tformatString", fact_text)
        self.assertIn("HASONEVALUE ( DimDate[YearMonth] )", fact_text)

        generated_text = "\n".join(assets.values())
        self.assertNotIn("C:\\Users\\", generated_text)
        self.assertNotIn("password", generated_text.lower())
        self.assertNotIn("[Query =", generated_text)
        self.assertIn("MySQL.Database(MySqlServer, MySqlDatabase, [ReturnSingleDatabase = true])", fact_text)
        self.assertIn("Navigation = Source{[Schema=MySqlDatabase, Item=\"vw_fact_sales_line\"]}[Data]", fact_text)
        self.assertNotIn("Table.SelectColumns(Navigation, {{", generated_text)
        self.assertNotIn("Table.Distinct(Renamed, {{", generated_text)
        self.assertNotIn("Table.Group(Selected, {{", generated_text)
        self.assertIn("Navigation = Source{[Schema=MySqlDatabase, Item=\"vw_dim_product\"]}[Data]", generated_text)
        self.assertNotIn("Table.Group(Selected", generated_text)

    def test_dimension_views_enforce_star_schema_keys_in_mysql(self) -> None:
        sql = STANDARDIZED_VIEWS_SQL_PATH.read_text(encoding="utf-8")

        self.assertIn("CREATE OR REPLACE VIEW `vw_dim_product`", sql)
        self.assertIn("GROUP BY `StockCode`", sql)
        self.assertIn("CREATE OR REPLACE VIEW `vw_dim_customer`", sql)
        self.assertIn("CREATE OR REPLACE VIEW `vw_dim_country`", sql)

    def test_product_dimension_aggregate_has_a_bounded_covering_index(self) -> None:
        schema_sql = SCHEMA_SQL_PATH.read_text(encoding="utf-8")
        loader = LOADER_PATH.read_text(encoding="utf-8")

        for definition in (schema_sql, loader):
            self.assertIn("DescriptionText VARCHAR(512) NULL", definition)
            self.assertIn("(StockCode, DescriptionText)", definition)

    def test_generator_writes_only_to_a_desktop_created_empty_shell(self) -> None:
        self.assertTrue(AUTOMATION_PATH.is_file(), "PBIP model generator does not exist")
        generator = load_generator()
        self.assertTrue(hasattr(generator, "apply_assets"), "PBIP model generator cannot write assets")
        with tempfile.TemporaryDirectory() as temporary_directory:
            semantic_model_path = Path(temporary_directory) / "EnterpriseSalesAutomation.SemanticModel"
            definition_path = semantic_model_path / "definition"
            definition_path.mkdir(parents=True)
            (semantic_model_path / "definition.pbism").write_text("{}", encoding="utf-8")

            written = generator.apply_assets(semantic_model_path)

            self.assertGreaterEqual(len(written), 10)
            self.assertTrue((definition_path / "tables" / "FactSalesLine.tmdl").is_file())
            self.assertTrue((definition_path / "roles" / "CountryManager.tmdl").is_file())

    def test_generator_adds_schema_to_desktop_created_pbir(self) -> None:
        generator = load_generator()
        self.assertTrue(hasattr(generator, "ensure_report_schema"), "PBIP generator cannot normalize PBIR schema")
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_path = Path(temporary_directory)
            report_path = project_path / "EnterpriseSalesAutomation.Report"
            report_path.mkdir()
            pbir_path = report_path / "definition.pbir"
            pbir_path.write_text('{"version":"4.0"}', encoding="utf-8")

            generator.ensure_report_schema(project_path)

            definition = json.loads(pbir_path.read_text(encoding="utf-8"))
            self.assertEqual(
                definition["$schema"],
                "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
            )


if __name__ == "__main__":
    unittest.main()
