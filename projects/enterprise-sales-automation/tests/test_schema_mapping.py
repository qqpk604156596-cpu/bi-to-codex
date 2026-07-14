"""Contract tests for the enterprise MySQL schema and mapping gate."""

from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "src" / "transform" / "inspect_mysql_schema.py"


def load_schema_module():
    specification = importlib.util.spec_from_file_location("enterprise_schema_inspector", SCRIPT_PATH)
    if specification is None or specification.loader is None:
        raise AssertionError("schema inspector module cannot be imported")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def write_mapping(path: Path, *, status: str) -> None:
    path.write_text(
        json.dumps(
            {
                "status": status,
                "source_table_env": "MYSQL_SOURCE_TABLE",
                "mapping": {
                    "InvoiceNo": "Invoice",
                    "StockCode": "StockCode",
                    "Description": "Description",
                    "Quantity": "Quantity",
                    "InvoiceDate": "InvoiceDate",
                    "UnitPrice": "Price",
                    "CustomerID": "Customer ID",
                    "Country": "Country",
                },
                "cancellation_rule": {"type": "invoice_prefix", "prefix": "C"},
                "approved_by": None,
                "approved_at": None,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


class SchemaMappingGateTests(unittest.TestCase):
    def run_gate(
        self, *arguments: str, cwd: Path = PROJECT_ROOT
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT_PATH), *arguments],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_unapproved_mapping_blocks_before_database_access(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            mapping_path = Path(temp_dir) / "mapping.json"
            write_mapping(mapping_path, status="pending-owner-approval")

            result = self.run_gate(
                "--mapping-file",
                str(mapping_path),
                "--require-approved-mapping",
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("mapping_not_approved", result.stdout)

    def test_missing_environment_blocks_schema_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            mapping_path = temp_path / "mapping.json"
            missing_env_path = temp_path / "missing.env"
            write_mapping(mapping_path, status="pending-owner-approval")

            result = self.run_gate(
                "--mapping-file",
                str(mapping_path),
                "--env-file",
                str(missing_env_path),
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("mysql_environment_missing", result.stdout)

    @unittest.skipUnless((PROJECT_ROOT / ".env").is_file(), "requires local MySQL .env")
    def test_default_mapping_path_is_project_relative_and_uses_approved_mapping(self) -> None:
        result = self.run_gate("--require-approved-mapping", cwd=PROJECT_ROOT.parents[1])

        self.assertEqual(result.returncode, 0)
        self.assertIn("mysql_schema_profile_written", result.stdout)

    def test_description_text_is_suggested_for_canonical_raw_table(self) -> None:
        suggestion = load_schema_module().propose_mapping(
            [
                "SourceRowId",
                "InvoiceNo",
                "StockCode",
                "DescriptionText",
                "Quantity",
                "InvoiceDate",
                "UnitPrice",
                "CustomerID",
                "Country",
            ]
        )

        self.assertEqual(suggestion["Description"], "DescriptionText")


if __name__ == "__main__":
    unittest.main()
