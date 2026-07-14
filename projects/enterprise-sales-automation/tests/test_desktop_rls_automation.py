"""Contract tests for zero-popup dynamic RLS validation."""

from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RLS_SCRIPT = PROJECT_ROOT / "src" / "automation" / "Validate-DesktopRls.ps1"


class DesktopRlsAutomationTests(unittest.TestCase):
    def test_rls_runner_uses_runtime_identity_and_restores_memory_partition(self) -> None:
        self.assertTrue(RLS_SCRIPT.is_file(), "Desktop RLS runner does not exist")
        script = RLS_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("USERPRINCIPALNAME()", script)
        self.assertIn("TMSCHEMA_PARTITIONS", script)
        self.assertIn("QueryDefinition", script)
        self.assertIn("Microsoft.AnalysisServices.Tabular.Server", script)
        self.assertIn("SaveChanges", script)
        self.assertIn("temporaryMappingApplied", script)
        self.assertIn("VisibleCountryCount -eq 0 -or $null -eq $visible.VisibleCountryCount", script)
        self.assertIn("$validationStatus", script)
        self.assertIn("UTF8Encoding($false)", script)
        self.assertIn("CountryManager", script)
        self.assertIn("finally", script)
        self.assertIn("originalPartitionExpression", script)
        self.assertIn("desktop-rls-validation.json", script)
        self.assertNotIn("MYSQL_PASSWORD", script)
        self.assertNotIn("RuntimeIdentity = $runtimeIdentity", script)

    def test_rls_runner_declares_uk_france_and_unmapped_scenarios(self) -> None:
        script = RLS_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("United Kingdom", script)
        self.assertIn("France", script)
        self.assertIn("unmapped", script)
        self.assertIn("Roles=CountryManager", script)
        self.assertIn("approved_duckdb_baseline", script)


if __name__ == "__main__":
    unittest.main()
