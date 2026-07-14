"""Contract tests for the resumable BI workflow runtime."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PATH = REPO_ROOT / "scripts" / "bi_workflow_runtime.py"


def load_runtime():
    specification = importlib.util.spec_from_file_location("bi_workflow_runtime", RUNTIME_PATH)
    if specification is None or specification.loader is None:
        raise AssertionError("bi_workflow_runtime.py cannot be imported")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class BIWorkflowRuntimeTests(unittest.TestCase):
    def test_resume_uses_monitored_child_process_instead_of_buffering_stage_output(self) -> None:
        script = (REPO_ROOT / "scripts" / "Invoke-BIWorkflow.ps1").read_text(encoding="utf-8-sig")
        resumable = script.split("function Invoke-ResumableStage", 1)[1].split("try {", 1)[0]
        self.assertNotIn("$captured = @(& { Invoke-WorkflowStageByName", resumable)
        self.assertIn("run_with_heartbeat.py", resumable)
        self.assertIn("--heartbeat-seconds", resumable)
        self.assertIn("--timeout-seconds", resumable)
        self.assertIn("duration_ms", resumable)
        self.assertIn("timed_out", resumable)

    def test_workflow_exposes_bounded_heartbeat_and_stage_timeout_controls(self) -> None:
        script = (REPO_ROOT / "scripts" / "Invoke-BIWorkflow.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("[ValidateRange(5, 60)]", script)
        self.assertIn("[int]$HeartbeatSeconds = 15", script)
        self.assertIn("[ValidateRange(0, 3600)]", script)
        self.assertIn("[int]$StageTimeoutSeconds = 0", script)
        self.assertIn("function Get-StageTimeoutSeconds", script)

    def test_fingerprint_collection_prunes_ignored_directories_without_rglob(self) -> None:
        runtime = load_runtime()
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            (project / "docs").mkdir()
            (project / "docs" / "scope.md").write_text("scope", encoding="utf-8")
            (project / "ui-prototype" / "node_modules").mkdir(parents=True)
            (project / "ui-prototype" / "node_modules" / "ignored.js").write_text("ignored", encoding="utf-8")
            with mock.patch.object(Path, "rglob", side_effect=AssertionError("rglob must not enumerate dependency trees")):
                fingerprints = runtime.collect_fingerprints(project)
            self.assertEqual(set(fingerprints), set(runtime.GROUP_PATTERNS))

    def test_fingerprint_collection_ignores_local_pbix_delivery_files(self) -> None:
        runtime = load_runtime()
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            (project / "docs").mkdir()
            (project / "docs" / "scope.md").write_text("scope", encoding="utf-8")
            before = runtime.collect_fingerprints(project)
            (project / "EnterpriseSalesAutomation.pbix").write_bytes(b"local-pbix")
            self.assertEqual(runtime.collect_fingerprints(project), before)

    def test_powershell_prototype_stage_uses_native_playwright_cli(self) -> None:
        script = (REPO_ROOT / "scripts" / "Invoke-BIWorkflow.ps1").read_text(encoding="utf-8-sig")
        self.assertNotIn("--runInBand", script)

    def test_generate_report_blocks_before_writing_when_desktop_has_unsaved_changes(self) -> None:
        script = (REPO_ROOT / "scripts" / "Invoke-BIWorkflow.ps1").read_text(encoding="utf-8-sig")
        stage = script.split("function Invoke-GenerateReportStage", 1)[1].split("function Invoke-DesktopQAStage", 1)[0]
        self.assertIn("desktop_unsaved_changes_blocked", stage)
        self.assertLess(stage.index("desktop_unsaved_changes_blocked"), stage.index("$pythonCommand $generatorPath"))

    def test_desktop_target_lookup_skips_connected_blank_instances(self) -> None:
        script = (REPO_ROOT / "scripts" / "Invoke-BIWorkflow.ps1").read_text(encoding="utf-8-sig")
        lookup = script.split("function Get-DesktopTargetInstance", 1)[1].split(
            "function New-DesktopSessionResult", 1
        )[0]

        self.assertIn("-not [string]::IsNullOrWhiteSpace([string]$_.currentFilePath)", lookup)
        self.assertGreaterEqual(script.count("Get-DesktopTargetInstance"), 4)

    def test_desktop_qa_is_a_legacy_composite_over_split_desktop_stages(self) -> None:
        script = (REPO_ROOT / "scripts" / "Invoke-BIWorkflow.ps1").read_text(encoding="utf-8-sig")
        stage = script.split("function Invoke-DesktopQAStage", 1)[1].split("function Invoke-WorkflowStageByName", 1)[0]
        expected = [
            "Invoke-DesktopPreflightStage",
            "Invoke-DesktopRefreshStage",
            "Invoke-DesktopMetricsStage",
            "Invoke-DesktopRlsStage",
            "Invoke-CaptureDesktopScreenshotsStage",
        ]
        positions = [stage.index(value) for value in expected]
        self.assertEqual(positions, sorted(positions))

    def test_split_desktop_stages_keep_refresh_metrics_rls_and_screenshot_evidence(self) -> None:
        script = (REPO_ROOT / "scripts" / "Invoke-BIWorkflow.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("function Invoke-DesktopPreflightStage", script)
        self.assertIn("function Invoke-DesktopRefreshStage", script)
        self.assertIn("function Invoke-DesktopMetricsStage", script)
        self.assertIn("function Invoke-DesktopRlsStage", script)
        self.assertIn("function Invoke-CaptureDesktopScreenshotsStage", script)
        self.assertIn("Refresh-DesktopModel.ps1", script)
        self.assertIn("Validate-DesktopMetrics.ps1", script)
        self.assertIn("Validate-DesktopRls.ps1", script)
        self.assertIn("screenshot-all", script)
        screenshot_stage = script.split("function Invoke-CaptureDesktopScreenshotsStage", 1)[1].split(
            "function Invoke-DesktopQAStage", 1
        )[0]
        self.assertIn("desktop_screenshot_count_blocked", screenshot_stage)
        self.assertIn("$screenshotCount -lt 3", screenshot_stage)

    def test_desktop_qa_defaults_to_fresh_session_lifecycle_and_keeps_legacy_switch(self) -> None:
        script = (REPO_ROOT / "scripts" / "Invoke-BIWorkflow.ps1").read_text(encoding="utf-8-sig")
        resumable = script.split("function Invoke-ResumableStage", 1)[1].split("try {", 1)[0]

        self.assertIn("[ValidateSet('Auto', 'Reuse', 'Fresh', 'Reload')]", script)
        self.assertIn("[string]$DesktopSessionPolicy = 'Fresh'", script)
        self.assertIn("[switch]$SkipDesktopReload", script)
        self.assertIn("function Resolve-DesktopSessionPolicy", script)
        self.assertIn("desktop_session_legacy_skip_reload_mapped_to_reuse", script)
        self.assertIn("'-DesktopSessionPolicy', $DesktopSessionPolicy", resumable)
        self.assertIn("$childArguments += '-SkipDesktopReload'", resumable)

    def test_desktop_session_auto_reuses_target_or_opens_it_without_reload(self) -> None:
        script = (REPO_ROOT / "scripts" / "Invoke-BIWorkflow.ps1").read_text(encoding="utf-8-sig")
        lifecycle = script.split("function Acquire-DesktopSession", 1)[1].split(
            "function Write-DesktopSessionEvidence", 1
        )[0]
        auto_branch = lifecycle.split("'Auto' {", 1)[1].split("'Reuse' {", 1)[0]

        self.assertIn("desktop_session_auto_reused", auto_branch)
        self.assertIn("Open-DesktopTarget", auto_branch)
        self.assertNotIn("'reload'", auto_branch)

    def test_desktop_session_fresh_blocks_unsaved_and_restarts_clean_target_gracefully(self) -> None:
        script = (REPO_ROOT / "scripts" / "Invoke-BIWorkflow.ps1").read_text(encoding="utf-8-sig")
        lifecycle = script.split("function Acquire-DesktopSession", 1)[1].split(
            "function Write-DesktopSessionEvidence", 1
        )[0]
        fresh_branch = lifecycle.split("'Fresh' {", 1)[1].split("'Reload' {", 1)[0]

        self.assertIn("desktop_unsaved_changes_blocked", lifecycle)
        self.assertIn("Close-DesktopTargetGracefully", fresh_branch)
        self.assertIn("Open-DesktopTarget", fresh_branch)
        self.assertIn("desktop_fresh_session_started", fresh_branch)
        self.assertIn("CloseMainWindow", script)
        self.assertIn("desktop_fresh_close_timeout", script)

    def test_desktop_reload_is_an_explicit_legacy_policy(self) -> None:
        script = (REPO_ROOT / "scripts" / "Invoke-BIWorkflow.ps1").read_text(encoding="utf-8-sig")
        lifecycle = script.split("function Acquire-DesktopSession", 1)[1].split(
            "function Write-DesktopSessionEvidence", 1
        )[0]
        reload_branch = lifecycle.split("'Reload' {", 1)[1]

        self.assertIn("'reload', '--pid'", reload_branch)
        self.assertIn("desktop_session_reload_completed", reload_branch)

    def test_desktop_qa_records_session_lifecycle_evidence(self) -> None:
        script = (REPO_ROOT / "scripts" / "Invoke-BIWorkflow.ps1").read_text(encoding="utf-8-sig")
        stage = script.split("function Invoke-DesktopPreflightStage", 1)[1].split(
            "function Invoke-DesktopRefreshStage", 1
        )[0]

        self.assertIn("Write-DesktopSessionEvidence", stage)
        self.assertIn("desktop-session.json", script)
        self.assertIn("created_by_workflow", script)
        self.assertIn("acquisition_duration_ms", script)

    def test_desktop_session_evidence_distinguishes_blocked_from_failed(self) -> None:
        script = (REPO_ROOT / "scripts" / "Invoke-BIWorkflow.ps1").read_text(encoding="utf-8-sig")
        evidence = script.split("function Write-DesktopSessionEvidence", 1)[1].split(
            "function Invoke-GenerateReportStage", 1
        )[0]

        self.assertIn("elseif ($SessionResult.exit_code -eq 4) { 'blocked' }", evidence)
        self.assertIn("else { 'failed' }", evidence)

    def test_desktop_open_discovers_custom_install_path_without_persisting_environment(self) -> None:
        script = (REPO_ROOT / "scripts" / "Invoke-BIWorkflow.ps1").read_text(encoding="utf-8-sig")
        resolver = script.split("function Resolve-PowerBIDesktopExecutable", 1)[1].split(
            "function Open-DesktopTarget", 1
        )[0]
        opener = script.split("function Open-DesktopTarget", 1)[1].split(
            "function Close-DesktopTargetGracefully", 1
        )[0]

        self.assertIn("$env:PBI_DESKTOP_PATH", resolver)
        self.assertIn("Get-Process -Id", resolver)
        self.assertIn("WScript.Shell", resolver)
        self.assertIn("*.lnk", resolver)
        self.assertIn("$previousDesktopPath = $env:PBI_DESKTOP_PATH", opener)
        self.assertIn("$env:PBI_DESKTOP_PATH = $resolvedDesktopPath", opener)
        self.assertIn("finally", opener)
        self.assertIn("$env:PBI_DESKTOP_PATH = $previousDesktopPath", opener)

    def test_desktop_open_waits_for_the_target_path_on_a_specific_bridge_process(self) -> None:
        script = (REPO_ROOT / "scripts" / "Invoke-BIWorkflow.ps1").read_text(encoding="utf-8-sig")
        waiter = script.split("function Wait-DesktopTargetInstance", 1)[1].split(
            "function Open-DesktopTarget", 1
        )[0]
        opener = script.split("function Open-DesktopTarget", 1)[1].split(
            "function Close-DesktopTargetGracefully", 1
        )[0]

        self.assertIn("Get-Process PBIDesktop", waiter)
        self.assertIn("-ProcessId $candidateProcess.Id", waiter)
        self.assertIn("Get-DesktopTargetInstance", waiter)
        self.assertIn("Start-Sleep -Milliseconds 500", waiter)
        self.assertIn("Wait-DesktopTargetInstance", opener)
        self.assertIn("desktop_target_open_timeout", opener)

    def test_desktop_lifecycle_and_report_guard_enumerate_every_bridge_process_by_pid(self) -> None:
        script = (REPO_ROOT / "scripts" / "Invoke-BIWorkflow.ps1").read_text(encoding="utf-8-sig")
        enumerator = script.split("function Get-AllDesktopBridgeInstances", 1)[1].split(
            "function Get-DesktopTargetInstance", 1
        )[0]
        lifecycle = script.split("function Acquire-DesktopSession", 1)[1].split(
            "function Write-DesktopSessionEvidence", 1
        )[0]
        report = script.split("function Invoke-GenerateReportStage", 1)[1].split(
            "function Invoke-DesktopQAStage", 1
        )[0]

        self.assertIn("Get-Process PBIDesktop", enumerator)
        self.assertIn("-ProcessId $desktopProcess.Id", enumerator)
        self.assertIn("instances = $instances.ToArray()", enumerator)
        self.assertIn("Get-AllDesktopBridgeInstances", lifecycle)
        self.assertIn("Get-AllDesktopBridgeInstances", report)

    def test_desktop_lifecycle_handles_multiple_target_instances_fail_safe(self) -> None:
        script = (REPO_ROOT / "scripts" / "Invoke-BIWorkflow.ps1").read_text(encoding="utf-8-sig")
        lifecycle = script.split("function Acquire-DesktopSession", 1)[1].split(
            "function Write-DesktopSessionEvidence", 1
        )[0]
        report = script.split("function Invoke-GenerateReportStage", 1)[1].split(
            "function Invoke-DesktopQAStage", 1
        )[0]

        self.assertIn("desktop_multiple_target_instances_blocked", lifecycle)
        self.assertIn("foreach ($freshInstance in $targetInstances)", lifecycle)
        self.assertIn("Where-Object { $_.hasUnsavedChanges }", lifecycle)
        self.assertIn("Where-Object { $_.hasUnsavedChanges }", report)

    def test_ui_contract_stage_uses_exit_code_instead_of_unittest_stderr(self) -> None:
        script = (REPO_ROOT / "scripts" / "Invoke-BIWorkflow.ps1").read_text(encoding="utf-8-sig")
        stage = script.split("function Invoke-UIContractStage", 1)[1].split("function Invoke-PrototypeStage", 1)[0]
        self.assertIn("Invoke-NativeCommandCaptured", stage)

    def test_native_stage_helper_merges_stderr_and_returns_only_exit_code(self) -> None:
        script = (REPO_ROOT / "scripts" / "Invoke-BIWorkflow.ps1").read_text(encoding="utf-8-sig")
        helper = script.split("function Invoke-NativeCommandCaptured", 1)[1].split("function Invoke-UIContractStage", 1)[0]
        self.assertIn("2>&1", helper)
        self.assertIn("$nativeExitCode = $LASTEXITCODE", helper)
        self.assertIn("return $nativeExitCode", helper)

    def test_prototype_stage_uses_native_exit_code_helper(self) -> None:
        script = (REPO_ROOT / "scripts" / "Invoke-BIWorkflow.ps1").read_text(encoding="utf-8-sig")
        stage = script.split("function Invoke-PrototypeStage", 1)[1].split("function Invoke-GenerateReportStage", 1)[0]
        self.assertIn("Invoke-NativeCommandCaptured", stage)

    def test_document_validation_reports_missing_relative_markdown_links(self) -> None:
        runtime = load_runtime()
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            (project / "docs").mkdir()
            (project / "project.yaml").write_text("project:\n  name: \"Docs\"\n", encoding="utf-8")
            (project / "README.md").write_text("[missing](docs/missing.md)\n", encoding="utf-8")
            report = runtime.validate_documentation(project)
            self.assertEqual(report["status"], "failed")
            self.assertIn("docs/missing.md", report["missing_links"])

    def test_document_only_change_selects_only_document_validation(self) -> None:
        runtime = load_runtime()
        selection = runtime.select_stages(["docs/scope.md"], force_full=False, release=False)
        self.assertEqual(selection, ["ValidateDocumentation"])

    def test_metric_change_selects_metric_and_desktop_metric_gates_only(self) -> None:
        runtime = load_runtime()
        selection = runtime.select_stages(["config/metrics.json"], force_full=False, release=False)
        self.assertEqual(
            selection,
            [
                "ValidateMetrics",
                "ValidateModelSpec",
                "ValidatePowerBIProject",
                "DesktopPreflight",
                "DesktopMetrics",
            ],
        )

    def test_ui_contract_change_selects_prototype_and_report_stages(self) -> None:
        runtime = load_runtime()
        selection = runtime.select_stages(["report/ui-contract.json"], force_full=False, release=False)
        self.assertEqual(
            selection,
            [
                "ValidateUIContract",
                "ValidatePrototype",
                "GenerateReport",
                "ValidateReportQA",
                "DesktopPreflight",
                "CaptureDesktopScreenshots",
            ],
        )

    def test_report_change_does_not_refresh_metrics_or_rls(self) -> None:
        runtime = load_runtime()
        selection = runtime.select_stages(
            ["report/visual-manifest.json"], force_full=False, release=False
        )
        self.assertEqual(
            selection,
            ["GenerateReport", "ValidateReportQA", "DesktopPreflight", "CaptureDesktopScreenshots"],
        )
        self.assertNotIn("DesktopRefresh", selection)
        self.assertNotIn("DesktopMetrics", selection)
        self.assertNotIn("DesktopRls", selection)

    def test_mixed_document_and_report_changes_union_their_targeted_stages(self) -> None:
        runtime = load_runtime()
        selection = runtime.select_stages(
            ["docs/qa-report.md", "report/visual-manifest.json"],
            force_full=False,
            release=False,
        )
        self.assertEqual(
            selection,
            [
                "ValidateDocumentation",
                "GenerateReport",
                "ValidateReportQA",
                "DesktopPreflight",
                "CaptureDesktopScreenshots",
            ],
        )

    def test_data_change_runs_expensive_data_and_desktop_gates_without_visual_tests(self) -> None:
        runtime = load_runtime()
        selection = runtime.select_stages(
            ["data/interim/fact_sales_line.csv"], force_full=False, release=False
        )
        self.assertIn("TestDataQuality", selection)
        self.assertIn("DesktopRefresh", selection)
        self.assertIn("DesktopMetrics", selection)
        self.assertIn("DesktopRls", selection)
        self.assertNotIn("ValidatePrototype", selection)
        self.assertNotIn("CaptureDesktopScreenshots", selection)

    def test_force_full_resume_stops_before_final_release_gate(self) -> None:
        runtime = load_runtime()
        selection = runtime.select_stages([], force_full=True, release=False)
        self.assertNotIn("ValidateRelease", selection)
        self.assertEqual(selection[-1], "CaptureDesktopScreenshots")
        self.assertNotIn("DesktopQA", selection)

    def test_release_mode_ends_with_delivery_release_gate(self) -> None:
        runtime = load_runtime()
        selection = runtime.select_stages([], force_full=False, release=True)
        self.assertEqual(selection, ["ValidateRelease"])

    def test_release_plan_reuses_valid_stage_cache_and_only_runs_invalidated_gates(self) -> None:
        runtime = load_runtime()
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            (project / "docs").mkdir()
            (project / "docs" / "scope.md").write_text("scope", encoding="utf-8")
            (project / "project.yaml").write_text(
                "project:\n  name: \"Cached BI\"\nworkflow:\n  input_fingerprints_json: \"{}\"\n"
                "  stage_cache_json: \"{}\"\n  pending_stages_json: \"[]\"\n",
                encoding="utf-8",
            )
            fingerprints = runtime.collect_fingerprints(project)
            cache = {
                stage: {
                    "fingerprint": runtime.stage_fingerprint(stage, fingerprints),
                    "run_id": "run-cached",
                    "completed_at": "2026-07-14T00:00:00+00:00",
                }
                for stage in runtime.RELEASE_REQUIRED_STAGES
            }
            text = (project / "project.yaml").read_text(encoding="utf-8")
            text = runtime.replace_yaml_section(
                text,
                "workflow",
                {
                    "schema_version": 2,
                    "input_fingerprints_json": json.dumps(fingerprints, separators=(",", ":")),
                    "stage_cache_json": json.dumps(cache, separators=(",", ":")),
                    "pending_stages_json": "[]",
                },
            )
            (project / "project.yaml").write_text(text, encoding="utf-8")

            plan = runtime.build_run_plan(project, force_full=False, release=True)

            self.assertEqual(
                plan["selected_stages"], ["Preflight", "ValidateStructure", "ValidateRelease"]
            )

    def test_bootstrap_cache_uses_passed_gates_and_latest_compatible_evidence(self) -> None:
        runtime = load_runtime()
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            run_directory = project / "evidence" / "runs" / "run-existing"
            for relative in ("desktop-model", "desktop-metrics", "desktop-rls", "saved-desktop-screenshots"):
                (run_directory / relative).mkdir(parents=True, exist_ok=True)
            (project / "docs").mkdir()
            for name in ("scope.md", "delivery-notes.md", "portfolio-case-study.md", "qa-report.md"):
                (project / "docs" / name).write_text("ready", encoding="utf-8")
            (project / "project.yaml").write_text(
                "automation:\n  target_refresh_minutes: 5\n  prototype_status: \"passed\"\n"
                "quality_gates:\n  data_contract: \"passed\"\n  data_quality: \"passed\"\n"
                "  metrics: \"passed\"\n  model_spec: \"passed\"\n  powerbi_project: \"passed\"\n"
                "  model: \"passed\"\n  rls: \"passed\"\n  report: \"passed\"\n"
                "  performance: \"passed\"\nworkflow:\n  last_run_id: \"run-existing\"\n"
                "  input_fingerprints_json: \"{}\"\n  pending_stages_json: \"[]\"\n",
                encoding="utf-8",
            )
            (run_directory / "desktop-model" / "desktop-model-refresh.json").write_text(
                json.dumps(
                    {
                        "status": "passed",
                        "duration_ms": 90000,
                        "refresh_threshold_seconds": 300,
                        "performance_gate_passed": True,
                    }
                ),
                encoding="utf-8",
            )
            for relative in (
                "desktop-metrics/desktop-metric-validation.json",
                "desktop-rls/desktop-rls-validation.json",
            ):
                (run_directory / relative).write_text('{"status":"passed"}', encoding="utf-8")
            for index in range(3):
                (run_directory / "saved-desktop-screenshots" / f"page-{index}.png").write_bytes(b"png")

            result = runtime.bootstrap_stage_cache(project)
            cache = runtime._read_stage_cache(project)
            plan = runtime.build_run_plan(project, force_full=False, release=True)
            resume_plan = runtime.build_run_plan(project, force_full=False, release=False)

            self.assertEqual(result["skipped_stages"], [])
            self.assertEqual(
                cache["CaptureDesktopScreenshots"]["evidence_relative"], "saved-desktop-screenshots"
            )
            self.assertEqual(plan["selected_stages"], ["Preflight", "ValidateStructure", "ValidateRelease"])
            self.assertEqual(resume_plan["selected_stages"], [])

    def test_release_gate_blocks_without_human_pbix_and_fresh_desktop_evidence(self) -> None:
        runtime = load_runtime()
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            run_directory = project / "evidence" / "runs" / "run-release"
            run_directory.mkdir(parents=True)
            (project / "project.yaml").write_text(
                "quality_gates:\n  scope: \"pending\"\n  report: \"pending\"\n  performance: \"pending\"\n  portfolio: \"pending\"\n",
                encoding="utf-8",
            )
            result = runtime.validate_release(project, run_directory)
            self.assertEqual(result["status"], "blocked")
            self.assertIn("pbix_missing", {item["code"] for item in result["issues"]})

    def test_release_gate_passes_with_manual_gates_and_same_run_desktop_evidence(self) -> None:
        runtime = load_runtime()
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            run_directory = project / "evidence" / "runs" / "run-release"
            for relative in ("desktop-model", "desktop-metrics", "desktop-rls", "desktop-screenshots"):
                (run_directory / relative).mkdir(parents=True)
            (project / "project.yaml").write_text(
                "quality_gates:\n  scope: \"passed\"\n  report: \"passed\"\n  performance: \"passed\"\n  portfolio: \"passed\"\n",
                encoding="utf-8",
            )
            (project / "EnterpriseSalesAutomation.pbip").write_text("{}", encoding="utf-8")
            (project / "EnterpriseSalesAutomation.pbix").write_bytes(b"pbix")
            (project / "docs").mkdir()
            for name in ("delivery-notes.md", "portfolio-case-study.md", "qa-report.md"):
                (project / "docs" / name).write_text("ready", encoding="utf-8")
            for relative in (
                "desktop-model/desktop-model-refresh.json",
                "desktop-metrics/desktop-metric-validation.json",
                "desktop-rls/desktop-rls-validation.json",
            ):
                payload = {"status": "passed"}
                if relative.startswith("desktop-model/"):
                    payload.update(
                        {
                            "duration_ms": 120000,
                            "refresh_threshold_seconds": 300,
                            "performance_gate_passed": True,
                        }
                    )
                (run_directory / relative).write_text(json.dumps(payload), encoding="utf-8")
            for index in range(3):
                (run_directory / "desktop-screenshots" / f"page-{index}.png").write_bytes(b"png")
            result = runtime.validate_release(project, run_directory)
            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["issues"], [])

    def test_release_gate_reuses_fingerprint_compatible_desktop_evidence(self) -> None:
        runtime = load_runtime()
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            cached_run = project / "evidence" / "runs" / "run-cached"
            current_run = project / "evidence" / "runs" / "run-release"
            for relative in ("desktop-model", "desktop-metrics", "desktop-rls", "desktop-screenshots"):
                (cached_run / relative).mkdir(parents=True, exist_ok=True)
            current_run.mkdir(parents=True)
            (project / "EnterpriseSalesAutomation.pbip").write_text("{}", encoding="utf-8")
            (project / "EnterpriseSalesAutomation.pbix").write_bytes(b"pbix")
            (project / "docs").mkdir()
            for name in ("delivery-notes.md", "portfolio-case-study.md", "qa-report.md"):
                (project / "docs" / name).write_text("ready", encoding="utf-8")
            for relative in (
                "desktop-model/desktop-model-refresh.json",
                "desktop-metrics/desktop-metric-validation.json",
                "desktop-rls/desktop-rls-validation.json",
            ):
                payload = {"status": "passed"}
                if relative.startswith("desktop-model/"):
                    payload.update(
                        {
                            "duration_ms": 120000,
                            "refresh_threshold_seconds": 300,
                            "performance_gate_passed": True,
                        }
                    )
                (cached_run / relative).write_text(json.dumps(payload), encoding="utf-8")
            for index in range(3):
                (cached_run / "desktop-screenshots" / f"page-{index}.png").write_bytes(b"png")
            (project / "project.yaml").write_text(
                "automation:\n  target_refresh_minutes: 5\nquality_gates:\n"
                "  scope: \"passed\"\n  report: \"passed\"\n  performance: \"passed\"\n"
                "  portfolio: \"passed\"\nworkflow:\n  stage_cache_json: \"{}\"\n",
                encoding="utf-8",
            )
            fingerprints = runtime.collect_fingerprints(project)
            cache = {
                stage: {
                    "fingerprint": runtime.stage_fingerprint(stage, fingerprints),
                    "run_id": "run-cached",
                }
                for stage in (
                    "DesktopRefresh",
                    "DesktopMetrics",
                    "DesktopRls",
                    "CaptureDesktopScreenshots",
                )
            }
            text = (project / "project.yaml").read_text(encoding="utf-8")
            (project / "project.yaml").write_text(
                runtime.replace_yaml_section(
                    text, "workflow", {"stage_cache_json": json.dumps(cache, separators=(",", ":"))}
                ),
                encoding="utf-8",
            )

            result = runtime.validate_release(project, current_run)

            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["evidence_sources"]["DesktopRefresh"], "run-cached")

    def test_release_gate_rejects_refresh_evidence_without_the_duration_gate(self) -> None:
        runtime = load_runtime()
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            run_directory = project / "evidence" / "runs" / "run-release" / "desktop-model"
            run_directory.mkdir(parents=True)
            (project / "project.yaml").write_text(
                "automation:\n  target_refresh_minutes: 5\nquality_gates:\n"
                "  scope: \"passed\"\n  report: \"passed\"\n  performance: \"passed\"\n  portfolio: \"passed\"\n",
                encoding="utf-8",
            )
            (run_directory / "desktop-model-refresh.json").write_text(
                '{"status":"passed"}', encoding="utf-8"
            )

            result = runtime.validate_release(project, run_directory.parent)

            self.assertIn("refresh_performance_evidence_invalid", {item["code"] for item in result["issues"]})

    def test_refresh_performance_gate_accepts_exactly_300_seconds_and_rejects_overage(self) -> None:
        runtime = load_runtime()
        base = {"refresh_threshold_seconds": 300, "performance_gate_passed": True}

        self.assertIsNone(runtime.refresh_performance_evidence_issue({**base, "duration_ms": 299999}, 300))
        self.assertIsNone(runtime.refresh_performance_evidence_issue({**base, "duration_ms": 300000}, 300))
        self.assertIsNotNone(runtime.refresh_performance_evidence_issue({**base, "duration_ms": 300001}, 300))
        self.assertIsNotNone(
            runtime.refresh_performance_evidence_issue(
                {"duration_ms": 1, "refresh_threshold_seconds": 301, "performance_gate_passed": True}, 300
            )
        )
        self.assertIsNotNone(
            runtime.refresh_performance_evidence_issue({**base, "duration_ms": 1, "performance_gate_passed": False}, 300)
        )

    def test_unchanged_resume_skips_all_stages(self) -> None:
        runtime = load_runtime()
        self.assertEqual(runtime.select_stages([], force_full=False, release=False), [])

    def test_run_summary_and_next_context_are_generated_from_state(self) -> None:
        runtime = load_runtime()
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            (project / "evidence" / "runs").mkdir(parents=True)
            (project / "project.yaml").write_text(
                """project:\n  name: \"Test BI\"\n  status: \"active\"\nquality_gates:\n  data_quality: \"passed\"\n  report: \"pending\"\nexternal_validation:\n  power_bi_service: \"not-validated\"\n""",
                encoding="utf-8",
            )
            report = runtime.write_run_artifacts(
                project,
                run_id="run-001",
                mode="resume",
                selected_stages=["ValidateDocumentation"],
                stage_results=[{"stage": "ValidateDocumentation", "status": "passed", "exit_code": 0}],
                fingerprints={"documentation": "abc"},
            )

            self.assertEqual(report["status"], "passed")
            self.assertTrue((project / "evidence" / "runs" / "run-001" / "summary.json").is_file())
            summary = json.loads(
                (project / "evidence" / "runs" / "run-001" / "summary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(summary["selected_stages"], ["ValidateDocumentation"])
            context = (project / "NEXT_CONTEXT.md").read_text(encoding="utf-8")
            self.assertIn("Test BI", context)
            self.assertIn("data_quality: passed", context)
            self.assertIn("report: pending", context)
            self.assertLessEqual(len(context.splitlines()), 120)

    def test_failed_run_summary_records_runtime_timeout_and_recovery_action(self) -> None:
        runtime = load_runtime()
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            (project / "evidence" / "runs").mkdir(parents=True)
            (project / "project.yaml").write_text(
                "project:\n  name: \"Timed BI\"\nquality_gates:\n  report: \"pending\"\n",
                encoding="utf-8",
            )
            report = runtime.write_run_artifacts(
                project,
                run_id="run-timeout",
                mode="resume",
                selected_stages=["ValidatePrototype", "GenerateReport"],
                stage_results=[
                    {
                        "stage": "ValidatePrototype",
                        "status": "failed",
                        "exit_code": 124,
                        "duration_ms": 180123,
                        "timed_out": True,
                        "timeout_seconds": 180,
                        "log_file": "evidence/runs/run-timeout/ValidatePrototype.log",
                    }
                ],
                fingerprints={},
            )

            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["stage_results"][0]["duration_ms"], 180123)
            self.assertTrue(report["stage_results"][0]["timed_out"])
            self.assertEqual(
                report["next_action"],
                "Inspect evidence/runs/run-timeout/ValidatePrototype.log, fix the cause, then run Resume.",
            )
            markdown = (project / "evidence" / "runs" / "run-timeout" / "summary.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("Duration (s)", markdown)
            self.assertIn("Timed out", markdown)
            self.assertIn("180.1", markdown)

    def test_repo_next_context_is_generated_for_project_under_projects_directory(self) -> None:
        runtime = load_runtime()
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "AGENTS.md").write_text("# rules\n", encoding="utf-8")
            project = root / "projects" / "test-bi"
            (project / "evidence" / "runs").mkdir(parents=True)
            (project / "project.yaml").write_text(
                "project:\n  name: \"Test BI\"\nquality_gates:\n  report: \"pending\"\n",
                encoding="utf-8",
            )
            runtime.write_run_artifacts(
                project,
                run_id="run-002",
                mode="resume",
                selected_stages=[],
                stage_results=[],
                fingerprints={},
            )
            self.assertTrue((project / "NEXT_CONTEXT.md").is_file())
            self.assertIn("run-002", (root / "NEXT_CONTEXT.md").read_text(encoding="utf-8"))

    def test_sync_context_uses_current_project_status_with_latest_workflow_summary(self) -> None:
        runtime = load_runtime()
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "AGENTS.md").write_text("# rules\n", encoding="utf-8")
            project = root / "projects" / "test-bi"
            run_directory = project / "evidence" / "runs" / "run-old"
            run_directory.mkdir(parents=True)
            (project / "project.yaml").write_text(
                "project:\n  name: \"Test BI\"\n  status: \"desktop-pbix-saved\"\n"
                "quality_gates:\n  report: \"passed\"\nworkflow:\n  last_run_id: \"run-old\"\n",
                encoding="utf-8",
            )
            (run_directory / "summary.json").write_text(
                json.dumps(
                    {
                        "run_id": "run-old",
                        "mode": "resume",
                        "status": "passed",
                        "generated_at": "2026-07-14T00:00:00+00:00",
                        "last_successful_stage": "DesktopMetrics",
                        "pending_stages": [],
                        "next_action": "No automated stage is pending.",
                    }
                ),
                encoding="utf-8",
            )

            runtime.sync_next_context(project)

            context = (project / "NEXT_CONTEXT.md").read_text(encoding="utf-8")
            self.assertIn("项目状态：desktop-pbix-saved", context)
            self.assertIn("最近工作流：run-old", context)
            self.assertEqual(context, (root / "NEXT_CONTEXT.md").read_text(encoding="utf-8"))

    def test_blocked_run_resumes_from_blocked_stage_when_inputs_are_unchanged(self) -> None:
        runtime = load_runtime()
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            (project / "evidence" / "runs").mkdir(parents=True)
            (project / "report").mkdir()
            (project / "report" / "ui-contract.json").write_text("{}", encoding="utf-8")
            (project / "project.yaml").write_text(
                "project:\n  name: \"Test BI\"\nquality_gates:\n  report: \"pending\"\n",
                encoding="utf-8",
            )
            stages = [
                "ValidateUIContract",
                "GenerateReport",
                "ValidateReportQA",
                "DesktopPreflight",
                "CaptureDesktopScreenshots",
            ]
            report = runtime.write_run_artifacts(
                project,
                run_id="run-blocked",
                mode="resume",
                selected_stages=stages,
                stage_results=[
                    {"stage": "ValidateUIContract", "status": "passed", "exit_code": 0},
                    {"stage": "GenerateReport", "status": "blocked", "exit_code": 4},
                ],
                fingerprints=runtime.collect_fingerprints(project),
            )
            self.assertEqual(report["status"], "blocked")
            plan = runtime.build_run_plan(project, force_full=False, release=False)
            self.assertEqual(plan["changed_groups"], [])
            self.assertEqual(
                plan["selected_stages"],
                [
                    "GenerateReport",
                    "ValidateReportQA",
                    "DesktopPreflight",
                    "CaptureDesktopScreenshots",
                ],
            )

    def test_blocked_run_persists_reason_timestamp_and_retry_count(self) -> None:
        runtime = load_runtime()
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            (project / "evidence" / "runs").mkdir(parents=True)
            (project / "project.yaml").write_text(
                "project:\n  name: \"Blocked BI\"\nworkflow:\n  pending_stages_json: \"[]\"\n",
                encoding="utf-8",
            )
            report = runtime.write_run_artifacts(
                project,
                run_id="run-blocked-telemetry",
                mode="resume",
                selected_stages=["DesktopPreflight"],
                stage_results=[
                    {
                        "stage": "DesktopPreflight",
                        "status": "blocked",
                        "exit_code": 4,
                        "blocked_at": "2026-07-14T01:00:00+00:00",
                        "blocked_reason": "desktop_unsaved_changes_blocked",
                    }
                ],
                fingerprints=runtime.collect_fingerprints(project),
            )
            config = runtime.parse_simple_yaml((project / "project.yaml").read_text(encoding="utf-8"))
            workflow = config["workflow"]
            self.assertEqual(report["blocked_reason"], "desktop_unsaved_changes_blocked")
            self.assertEqual(workflow["blocked_stage"], "DesktopPreflight")
            self.assertEqual(workflow["blocked_reason"], "desktop_unsaved_changes_blocked")
            self.assertEqual(workflow["blocked_retry_count"], 1)


if __name__ == "__main__":
    unittest.main()
