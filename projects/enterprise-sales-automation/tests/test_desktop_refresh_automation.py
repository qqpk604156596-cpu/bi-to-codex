"""Contract tests for the long-running zero-popup Desktop refresh runner."""

from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REFRESH_SCRIPT = PROJECT_ROOT / "src" / "automation" / "Refresh-DesktopModel.ps1"
METRIC_VALIDATION_SCRIPT = PROJECT_ROOT / "src" / "automation" / "Validate-DesktopMetrics.ps1"


class DesktopRefreshAutomationTests(unittest.TestCase):
    def test_refresh_runner_uses_local_desktop_port_and_writes_evidence(self) -> None:
        self.assertTrue(REFRESH_SCRIPT.is_file(), "Desktop refresh runner does not exist")
        script = REFRESH_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("msmdsrv.port.txt", script)
        self.assertIn("Microsoft.PowerBI.AdomdClient.dll", script)
        self.assertIn("ExecuteNonQuery", script)
        self.assertIn("desktop-model-refresh.json", script)
        self.assertNotIn("MYSQL_PASSWORD", script)

    def test_refresh_runner_records_duration_and_enforces_five_minute_gate(self) -> None:
        script = REFRESH_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("RefreshThresholdSeconds = 300", script)
        self.assertIn("duration_ms", script)
        self.assertIn("refresh_threshold_seconds", script)
        self.assertIn("performance_gate_passed", script)
        self.assertIn("desktop_refresh_performance_gate_failed", script)
        self.assertIn("$refreshCompleted = $false", script)
        self.assertIn("$refreshCompleted = $true", script)
        self.assertIn("if (-not $refreshCompleted) { $null }", script)

    def test_metric_validation_runner_queries_desktop_and_writes_slice_evidence(self) -> None:
        self.assertTrue(METRIC_VALIDATION_SCRIPT.is_file(), "Desktop metric validation runner does not exist")
        script = METRIC_VALIDATION_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("Microsoft.PowerBI.AdomdClient.dll", script)
        self.assertIn("DimCountry[Country]", script)
        self.assertIn("DimDate[YearMonth]", script)
        self.assertIn("desktop-metric-validation.json", script)
        self.assertIn("PerformanceThresholdMilliseconds = 3000", script)
        self.assertIn("duration_ms", script)
        self.assertIn("performance_proxy_passed", script)
        self.assertIn("Trim([char[]]'[]')", script)
        self.assertNotIn('\\"', script)
        self.assertNotIn("MYSQL_PASSWORD", script)


if __name__ == "__main__":
    unittest.main()
