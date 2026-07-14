"""Contract tests for the generated three-page PBIR report."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "report" / "visual-manifest.json"
DESIGN_TOKENS_PATH = PROJECT_ROOT / "report" / "design-tokens.json"
METRICS_PATH = PROJECT_ROOT / "config" / "metrics.json"
GENERATOR_PATH = PROJECT_ROOT / "src" / "automation" / "apply_pbir_report.py"
REPORT_DEFINITION_PATH = PROJECT_ROOT / "EnterpriseSalesAutomation.Report" / "definition.pbir"
EXPECTED_PAGES = [
    "Executive Overview",
    "Product & Trend Analysis",
    "Customer & Country Analysis",
]


def load_generator():
    specification = importlib.util.spec_from_file_location("apply_pbir_report", GENERATOR_PATH)
    if specification is None or specification.loader is None:
        raise AssertionError("apply_pbir_report.py cannot be imported")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class VisualManifestTests(unittest.TestCase):
    def test_generator_restores_enhanced_schema_on_desktop_definition(self) -> None:
        generator = load_generator()
        with tempfile.TemporaryDirectory() as temporary_directory:
            report_directory = Path(temporary_directory) / "Test.Report"
            report_directory.mkdir()
            pbir_path = report_directory / "definition.pbir"
            pbir_path.write_text(
                '{"version":"4.0","datasetReference":{"byPath":{"path":"../Test.SemanticModel"}}}',
                encoding="utf-8",
            )

            generator.ensure_report_definition_schema(report_directory)

            definition = json.loads(pbir_path.read_text(encoding="utf-8"))
            self.assertEqual(
                definition["$schema"],
                "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
            )
            self.assertEqual(definition["datasetReference"]["byPath"]["path"], "../Test.SemanticModel")

    def test_atomic_generation_preserves_last_healthy_definition_on_failure(self) -> None:
        generator = load_generator()
        manifest = generator.load_manifest(MANIFEST_PATH)
        tokens = generator.load_design_tokens(DESIGN_TOKENS_PATH)
        with tempfile.TemporaryDirectory() as temporary_directory:
            report_directory = Path(temporary_directory) / "Test.Report"
            definition_directory = report_directory / "definition"
            definition_directory.mkdir(parents=True)
            marker = definition_directory / "healthy-marker.txt"
            marker.write_text("last-healthy", encoding="utf-8")

            with mock.patch.object(generator, "write_report_pages", side_effect=RuntimeError("generation failed")):
                with self.assertRaisesRegex(RuntimeError, "generation failed"):
                    generator.replace_report_definition_atomically(report_directory, manifest, tokens)

            self.assertEqual(marker.read_text(encoding="utf-8"), "last-healthy")
            self.assertFalse(list(report_directory.glob(".definition.staging-*")))

    def test_atomic_generation_validates_then_replaces_definition(self) -> None:
        generator = load_generator()
        manifest = generator.load_manifest(MANIFEST_PATH)
        tokens = generator.load_design_tokens(DESIGN_TOKENS_PATH)
        with tempfile.TemporaryDirectory() as temporary_directory:
            report_directory = Path(temporary_directory) / "Test.Report"
            definition_directory = report_directory / "definition"
            (definition_directory / "pages").mkdir(parents=True)
            (definition_directory / "definition.json").write_text("{}", encoding="utf-8")

            generator.replace_report_definition_atomically(report_directory, manifest, tokens)

            pages = json.loads((definition_directory / "pages" / "pages.json").read_text(encoding="utf-8"))
            self.assertEqual(pages["pageOrder"], [page["id"] for page in manifest["pages"]])
            self.assertTrue((definition_directory / "definition.json").is_file())
            self.assertFalse(list(report_directory.glob(".definition.backup-*")))

    def test_desktop_saved_report_definition_is_valid_pbir_v4(self) -> None:
        definition = json.loads(REPORT_DEFINITION_PATH.read_text(encoding="utf-8-sig"))
        self.assertEqual(definition["version"], "4.0")
        self.assertEqual(
            definition["datasetReference"]["byPath"]["path"],
            "../EnterpriseSalesAutomation.SemanticModel",
        )
        if "$schema" in definition:
            self.assertEqual(
                definition["$schema"],
                "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
            )

    def test_light_executive_tokens_define_required_palette(self) -> None:
        self.assertTrue(DESIGN_TOKENS_PATH.is_file(), "design-tokens.json does not exist")
        tokens = json.loads(DESIGN_TOKENS_PATH.read_text(encoding="utf-8"))
        self.assertEqual(tokens["theme"]["name"], "Light Executive")
        self.assertTrue({"canvas", "primary", "accent", "text_primary"}.issubset(tokens["colors"]))

    def test_manifest_covers_three_pages_with_only_approved_metrics(self) -> None:
        self.assertTrue(MANIFEST_PATH.is_file(), "visual-manifest.json does not exist")
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        approved_metric_ids = {metric["id"] for metric in json.loads(METRICS_PATH.read_text(encoding="utf-8"))["metrics"]}

        self.assertEqual([page["name"] for page in manifest["pages"]], EXPECTED_PAGES)
        self.assertEqual(manifest["global_slicers"], ["DimDate.YearMonth", "DimCountry.Country"])
        for page in manifest["pages"]:
            self.assertTrue(page["primary_visual_id"])
            self.assertTrue(page["visuals"])
            for visual in page["visuals"]:
                self.assertNotIn(visual["metric_id"], {"profit", "margin", "cost"})
                if visual["metric_id"]:
                    self.assertIn(visual["metric_id"], approved_metric_ids)
                if visual["id"].endswith("title"):
                    self.assertGreaterEqual(visual["position"][3], 57)
                if visual["visual_type"] == "cardVisual":
                    self.assertGreaterEqual(visual["position"][2], 270)
                if visual["visual_type"] == "slicer":
                    self.assertGreaterEqual(visual["position"][3], 76)

    def test_generator_writes_visuals_for_every_manifest_page(self) -> None:
        self.assertTrue(GENERATOR_PATH.is_file(), "PBIR report generator does not exist")
        generator = load_generator()
        manifest = generator.load_manifest(MANIFEST_PATH)

        with tempfile.TemporaryDirectory() as temporary_directory:
            definition_directory = Path(temporary_directory) / "definition"
            (definition_directory / "pages").mkdir(parents=True)
            stale_page = definition_directory / "pages" / "staleblankpage00000000"
            stale_page.mkdir()
            (stale_page / "page.json").write_text('{"displayName":"Page 1"}', encoding="utf-8")
            generator.write_report_pages(definition_directory, manifest)

            pages = json.loads((definition_directory / "pages" / "pages.json").read_text(encoding="utf-8"))
            self.assertEqual(len(pages["pageOrder"]), 3)
            self.assertFalse(stale_page.exists())
            for page in manifest["pages"]:
                page_directory = definition_directory / "pages" / page["id"]
                page_json = json.loads((page_directory / "page.json").read_text(encoding="utf-8"))
                self.assertEqual(page_json["displayName"], page["name"])
                self.assertEqual(
                    page_json["objects"]["background"][0]["properties"]["color"]["expr"]["Literal"]["Value"],
                    "'#F7F9FC'",
                )
                visual_paths = list((page_directory / "visuals").glob("*/visual.json"))
                self.assertGreaterEqual(len(visual_paths), len(page["visuals"]))
                visuals = [json.loads(path.read_text(encoding="utf-8")) for path in visual_paths]
                slicers = [visual for visual in visuals if visual["visual"]["visualType"] == "slicer"]
                for slicer in slicers:
                    self.assertEqual(
                        slicer["visual"]["objects"]["data"][0]["properties"]["mode"]["expr"]["Literal"]["Value"],
                        "'Dropdown'",
                    )
                for visual in visuals:
                    if visual["visual"]["visualType"] == "lineChart":
                        self.assertNotIn("sortDefinition", visual["visual"]["query"])
                    if visual["visual"]["visualType"] == "barChart":
                        self.assertIn("sortDefinition", visual["visual"]["query"])

    def test_generator_applies_light_executive_style_to_native_visuals(self) -> None:
        generator = load_generator()
        tokens = generator.load_design_tokens(DESIGN_TOKENS_PATH)
        manifest = generator.load_manifest(MANIFEST_PATH)

        with tempfile.TemporaryDirectory() as temporary_directory:
            definition_directory = Path(temporary_directory) / "definition"
            (definition_directory / "pages").mkdir(parents=True)
            generator.write_report_pages(definition_directory, manifest, tokens)

            visuals = [
                json.loads(path.read_text(encoding="utf-8"))
                for path in (definition_directory / "pages").glob("*/visuals/*/visual.json")
            ]
            title_box = next(visual for visual in visuals if visual["name"] == generator.visual_name("e10a5c4d8b7f612934ab", "exec_title"))
            self.assertEqual(
                title_box["visual"]["objects"]["general"][0]["properties"]["paragraphs"][0]["textRuns"][0]["textStyle"]["color"],
                tokens["colors"]["text_primary"],
            )
            cards = [visual for visual in visuals if visual["visual"]["visualType"] == "cardVisual"]
            self.assertTrue(cards)
            for card in cards:
                self.assertEqual(card["visual"]["visualContainerObjects"]["title"][0]["properties"]["fontColor"]["expr"]["Literal"]["Value"], f"'{tokens['colors']['primary']}'")
            charts = [visual for visual in visuals if visual["visual"]["visualType"] in {"lineChart", "barChart"}]
            self.assertTrue(charts)
            for chart in charts:
                self.assertEqual(chart["visual"]["visualContainerObjects"]["title"][0]["properties"]["fontColor"]["expr"]["Literal"]["Value"], f"'{tokens['colors']['primary']}'")

    def test_generator_disables_locale_dependent_display_units_and_duplicate_card_labels(self) -> None:
        generator = load_generator()
        manifest = generator.load_manifest(MANIFEST_PATH)
        tokens = generator.load_design_tokens(DESIGN_TOKENS_PATH)

        with tempfile.TemporaryDirectory() as temporary_directory:
            definition_directory = Path(temporary_directory) / "definition"
            (definition_directory / "pages").mkdir(parents=True)
            generator.write_report_pages(definition_directory, manifest, tokens)

            visuals = [
                json.loads(path.read_text(encoding="utf-8"))
                for path in (definition_directory / "pages").glob("*/visuals/*/visual.json")
            ]
            cards = [visual for visual in visuals if visual["visual"]["visualType"] == "cardVisual"]
            charts = [visual for visual in visuals if visual["visual"]["visualType"] in {"lineChart", "barChart"}]
            for card in cards:
                self.assertEqual(
                    card["visual"]["objects"]["value"][0]["properties"]["displayUnits"]["expr"]["Literal"]["Value"],
                    "1D",
                )
                self.assertEqual(
                    card["visual"]["objects"]["label"][0]["properties"]["show"]["expr"]["Literal"]["Value"],
                    "false",
                )
                self.assertEqual(
                    card["visual"]["objects"]["value"][0]["selector"],
                    {"data": [{"dataViewWildcard": {"matchingOption": 1}}]},
                )
                self.assertEqual(
                    card["visual"]["objects"]["label"][0]["selector"],
                    {"data": [{"dataViewWildcard": {"matchingOption": 1}}]},
                )
            for chart in charts:
                self.assertEqual(
                    chart["visual"]["objects"]["valueAxis"][0]["properties"]["labelDisplayUnits"]["expr"]["Literal"]["Value"],
                    "1D",
                )


if __name__ == "__main__":
    unittest.main()
