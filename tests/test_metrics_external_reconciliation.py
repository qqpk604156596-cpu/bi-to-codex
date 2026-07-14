"""Regression contract for metric validation backed by project reconciliation evidence."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "Test-BIMetrics.py"


def load_metrics_module():
    specification = importlib.util.spec_from_file_location("bi_metrics", SCRIPT_PATH)
    if specification is None or specification.loader is None:
        raise AssertionError("Test-BIMetrics.py cannot be imported")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class ExternalReconciliationTests(unittest.TestCase):
    def test_passed_reconciliation_evidence_is_accepted_for_external_metric_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            evidence_path = project_path / "evidence" / "metrics"
            evidence_path.mkdir(parents=True)
            (evidence_path / "reconciliation.json").write_text(
                json.dumps(
                    {
                        "status": "passed",
                        "slices": [
                            {
                                "id": "all",
                                "reconciliation": {
                                    "status": "passed",
                                    "metrics": {
                                        "gross_sales": {"status": "passed", "tolerance": "0.01"},
                                        "sales_mom_pct": {"status": "both-null", "tolerance": "0.0001"},
                                    },
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            issues = load_metrics_module().validate_external_reconciliation(
                project_path,
                {
                    "baseline_evidence": "evidence/metrics/reconciliation.json",
                    "metrics": [{"id": "gross_sales"}, {"id": "sales_mom_pct"}],
                },
            )

        self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()
