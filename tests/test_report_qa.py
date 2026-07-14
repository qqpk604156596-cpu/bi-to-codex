"""Behavioral tests for pre-Desktop PBIR report QA."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "Test-BIReportQA.py"


def load_module():
    specification = importlib.util.spec_from_file_location("test_bi_report_qa", SCRIPT_PATH)
    if specification is None or specification.loader is None:
        raise AssertionError("Test-BIReportQA.py cannot be imported")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def create_report_shell(project: Path, report_result: str, desktop_status: str) -> None:
    docs = project / "docs"
    docs.mkdir(parents=True)
    (docs / "dashboard-blueprint.md").write_text("# Blueprint\n", encoding="utf-8")
    (docs / "qa-report.md").write_text(
        f"""# QA Report

| Gate | Evidence | Result | Owner |
|---|---|---|---|
| Report | PBIR structure and bindings | {report_result} | Owner |
| Release | Desktop and delivery | Pending | Owner |

## Desktop render evidence

- Status: {desktop_status}

Manual areas: refresh, visual, performance, release.
""",
        encoding="utf-8",
    )
    report = project / "Test.Report"
    report.mkdir()
    definition = report / "definition"
    (report / "definition.pbir").write_text(
        json.dumps(
            {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
                "version": "4.0",
                "datasetReference": {"byPath": {"path": "../Test.SemanticModel"}},
            }
        ),
        encoding="utf-8",
    )
    page = definition / "pages" / "page-1"
    visual = page / "visuals" / "visual-1"
    visual.mkdir(parents=True)
    (definition / "pages" / "pages.json").write_text("{}", encoding="utf-8")
    (page / "page.json").write_text("{}", encoding="utf-8")
    (visual / "visual.json").write_text("{}", encoding="utf-8")


class ReportQATests(unittest.TestCase):
    def test_pending_human_desktop_checks_do_not_block_pre_desktop_structure_gate(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            create_report_shell(project, report_result="Pending", desktop_status="Pending")
            status, summary, issues = module.validate(project)
            self.assertEqual(status, "passed")
            self.assertEqual(issues, [])
            self.assertEqual(summary["report_gate_result"], "Pending")
            self.assertEqual(summary["desktop_render_status"], "Pending")

    def test_explicit_failed_report_gate_blocks_structure_gate(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            create_report_shell(project, report_result="Failed", desktop_status="Pending")
            status, _summary, issues = module.validate(project)
            self.assertEqual(status, "blocked")
            self.assertTrue(any(item["code"] == "report_gate_failed" for item in issues))

    def test_missing_enhanced_pbir_schema_blocks_structure_gate(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            create_report_shell(project, report_result="Pending", desktop_status="Pending")
            pbir_path = project / "Test.Report" / "definition.pbir"
            pbir_path.write_text('{"version":"4.0"}', encoding="utf-8")

            status, _summary, issues = module.validate(project)

            self.assertEqual(status, "blocked")
            self.assertTrue(any(item["code"] == "report_definition_schema_missing" for item in issues))


if __name__ == "__main__":
    unittest.main()
