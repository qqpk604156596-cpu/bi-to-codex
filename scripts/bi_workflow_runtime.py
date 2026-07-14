"""State and evidence helpers for the resumable Power BI workflow.

The module intentionally uses only the Python standard library so the root
workflow can run before a project virtual environment is activated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


FULL_STAGES = [
    "Preflight",
    "ValidateStructure",
    "ValidateDataContract",
    "TestDataQuality",
    "ValidateMetrics",
    "ValidateModelSpec",
    "ValidatePowerBIProject",
    "ValidateDocumentation",
    "ValidateUIContract",
    "ValidatePrototype",
    "GenerateReport",
    "ValidateReportQA",
    "DesktopPreflight",
    "DesktopRefresh",
    "DesktopMetrics",
    "DesktopRls",
    "CaptureDesktopScreenshots",
    "ValidateRelease",
]
RESUMABLE_STAGES = FULL_STAGES[:-1]

DESKTOP_STAGES = (
    "DesktopRefresh",
    "DesktopMetrics",
    "DesktopRls",
    "CaptureDesktopScreenshots",
)

STAGE_GROUPS: dict[str, tuple[str, ...]] = {
    "ValidateDocumentation": ("documentation",),
    "ValidateDataContract": ("data_contract",),
    "TestDataQuality": ("data_contract",),
    "ValidateMetrics": ("data_contract", "metrics"),
    "ValidateModelSpec": ("data_contract", "metrics", "model"),
    "ValidatePowerBIProject": ("model",),
    "ValidateUIContract": ("ui", "report"),
    "ValidatePrototype": ("ui",),
    "GenerateReport": ("ui", "report"),
    "ValidateReportQA": ("documentation", "report"),
    "DesktopRefresh": ("data_contract", "model"),
    "DesktopMetrics": ("data_contract", "metrics", "model"),
    "DesktopRls": ("data_contract", "model"),
    "CaptureDesktopScreenshots": ("ui", "report"),
}

RELEASE_REQUIRED_STAGES = tuple(STAGE_GROUPS)

GROUP_STAGES: dict[str, tuple[str, ...]] = {
    "documentation": ("ValidateDocumentation",),
    "data_contract": (
        "ValidateDataContract",
        "TestDataQuality",
        "ValidateMetrics",
        "ValidateModelSpec",
        "ValidatePowerBIProject",
        "DesktopPreflight",
        "DesktopRefresh",
        "DesktopMetrics",
        "DesktopRls",
    ),
    "metrics": (
        "ValidateMetrics",
        "ValidateModelSpec",
        "ValidatePowerBIProject",
        "DesktopPreflight",
        "DesktopMetrics",
    ),
    "model": (
        "ValidateModelSpec",
        "ValidatePowerBIProject",
        "DesktopPreflight",
        "DesktopRefresh",
        "DesktopMetrics",
        "DesktopRls",
    ),
    "ui": (
        "ValidateUIContract",
        "ValidatePrototype",
        "GenerateReport",
        "ValidateReportQA",
        "DesktopPreflight",
        "CaptureDesktopScreenshots",
    ),
    "report": (
        "GenerateReport",
        "ValidateReportQA",
        "DesktopPreflight",
        "CaptureDesktopScreenshots",
    ),
}

GROUP_PATTERNS: dict[str, tuple[str, ...]] = {
    "documentation": ("docs/", "README.md", "AGENTS.md"),
    "data_contract": ("config/data-contract.json", "config/source-mapping", "data/raw/", "data/interim/", "src/extract/", "src/transform/", "src/sql/001_", "src/sql/010_", "src/sql/011_"),
    "metrics": ("config/metrics.json", "src/sql/020_", "src/dax/", "compute_duckdb_baseline.py"),
    "model": ("model/", "EnterpriseSalesAutomation.SemanticModel/", "apply_pbip_model.py", "Validate-Desktop", "Refresh-DesktopModel"),
    "ui": ("report/ui-contract.json", "report/design-tokens.json", "ui-prototype/"),
    "report": ("report/visual-manifest.json", "apply_pbir_report.py", "EnterpriseSalesAutomation.Report/"),
}

IGNORED_PARTS = {".git", ".venv", "node_modules", ".next", "test-results", "playwright-report", "evidence"}
IGNORED_FILE_SUFFIXES = {".pbix", ".pbit"}
STATE_FILES = {"project.yaml", "NEXT_CONTEXT.md"}


def _normalize(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def classify_path(path: str) -> str:
    normalized = _normalize(path)
    for group, patterns in GROUP_PATTERNS.items():
        if any(normalized == pattern or normalized.startswith(pattern) or pattern in normalized for pattern in patterns):
            return group
    return "documentation"


def select_stages(changed_paths: Iterable[str], *, force_full: bool, release: bool) -> list[str]:
    paths = list(changed_paths)
    if release:
        return ["ValidateRelease"]
    if force_full:
        return list(RESUMABLE_STAGES)
    if not paths:
        return []
    groups = {classify_path(path) for path in paths}
    selected = {stage for group in groups for stage in GROUP_STAGES[group]}
    return [stage for stage in FULL_STAGES if stage in selected]


def stage_fingerprint(stage: str, fingerprints: dict[str, str]) -> str:
    """Return the stable input token that makes a passed stage reusable."""
    groups = STAGE_GROUPS.get(stage, ())
    digest = hashlib.sha256()
    for group in groups:
        digest.update(group.encode("utf-8"))
        digest.update(fingerprints.get(group, "missing").encode("utf-8"))
    return digest.hexdigest()


def collect_fingerprints(project: Path) -> dict[str, str]:
    digests = {group: hashlib.sha256() for group in GROUP_PATTERNS}
    matched = {group: 0 for group in GROUP_PATTERNS}
    for directory, child_directories, file_names in os.walk(project):
        child_directories[:] = sorted(name for name in child_directories if name not in IGNORED_PARTS)
        directory_path = Path(directory)
        for file_name in sorted(file_names):
            path = directory_path / file_name
            relative = path.relative_to(project).as_posix()
            if (
                relative in STATE_FILES
                or path.suffix.lower() in IGNORED_FILE_SUFFIXES
                or any(part in IGNORED_PARTS for part in path.relative_to(project).parts)
            ):
                continue
            group = classify_path(relative)
            digests[group].update(relative.encode("utf-8"))
            digests[group].update(path.read_bytes())
            matched[group] += 1
    for group in GROUP_PATTERNS:
        digests[group].update(str(matched[group]).encode("ascii"))
    return {group: digests[group].hexdigest() for group in GROUP_PATTERNS}


def validate_documentation(project: Path) -> dict[str, Any]:
    missing_links: list[str] = []
    checked_files = 0
    link_pattern = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
    for markdown_path in sorted(project.rglob("*.md")):
        if any(part in IGNORED_PARTS for part in markdown_path.relative_to(project).parts):
            continue
        checked_files += 1
        text = markdown_path.read_text(encoding="utf-8-sig")
        for raw_target in link_pattern.findall(text):
            target = raw_target.strip().strip("<>").split("#", 1)[0].strip()
            if not target or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue
            resolved = (markdown_path.parent / target).resolve()
            if not resolved.exists():
                missing_links.append(target.replace("\\", "/"))
    return {
        "status": "passed" if not missing_links else "failed",
        "checked_files": checked_files,
        "missing_links": sorted(set(missing_links)),
    }


def parse_simple_yaml(text: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    section: str | None = None
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if not raw_line.startswith(" ") and raw_line.rstrip().endswith(":"):
            section = raw_line.rstrip()[:-1]
            result.setdefault(section, {})
            continue
        match = re.match(r"^\s{2}([A-Za-z0-9_]+):\s*(.*)$", raw_line)
        if not match or section is None:
            continue
        key, raw_value = match.groups()
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        elif value.lower() in {"true", "false"}:
            value = value.lower() == "true"
        elif value.isdigit():
            value = int(value)
        result[section][key] = value
    return result


def refresh_performance_evidence_issue(payload: dict[str, Any], target_seconds: float) -> str | None:
    """Return an issue when completed-refresh evidence does not prove the approved duration gate."""
    duration_ms = payload.get("duration_ms")
    threshold_seconds = payload.get("refresh_threshold_seconds")
    if (
        isinstance(duration_ms, bool)
        or not isinstance(duration_ms, (int, float))
        or duration_ms < 0
        or isinstance(threshold_seconds, bool)
        or not isinstance(threshold_seconds, (int, float))
        or threshold_seconds <= 0
    ):
        return "Refresh duration or threshold is missing or invalid"
    if threshold_seconds > target_seconds:
        return f"Refresh threshold {threshold_seconds:g}s exceeds the approved target {target_seconds:g}s"
    if payload.get("performance_gate_passed") is not True:
        return "Refresh performance gate did not pass"
    if duration_ms > threshold_seconds * 1000:
        return f"Refresh duration {duration_ms:g}ms exceeds its recorded threshold"
    return None


def validate_release(project: Path, run_directory: Path) -> dict[str, Any]:
    """Validate human-approved assets plus current-run or fingerprint-compatible cached evidence."""
    issues: list[dict[str, str]] = []
    evidence_sources: dict[str, str] = {}

    def add_issue(code: str, path: str, message: str) -> None:
        issues.append({"code": code, "path": path, "message": message})

    config_path = project / "project.yaml"
    config = parse_simple_yaml(config_path.read_text(encoding="utf-8-sig")) if config_path.is_file() else {}
    quality_gates = config.get("quality_gates", {})
    automation = config.get("automation", {})
    try:
        target_refresh_seconds = float(automation.get("target_refresh_minutes", 5)) * 60
    except (TypeError, ValueError):
        target_refresh_seconds = 300
    current_fingerprints = collect_fingerprints(project)
    stage_cache = _read_stage_cache(project)

    def resolve_evidence(stage: str, relative: str) -> Path:
        same_run = run_directory / relative
        if same_run.exists():
            evidence_sources[stage] = run_directory.name
            return same_run
        if stage_cache_is_valid(stage, current_fingerprints, stage_cache):
            cached_run = str(stage_cache[stage].get("run_id", ""))
            cached_relative = str(stage_cache[stage].get("evidence_relative", relative))
            cached_path = project / "evidence" / "runs" / cached_run / cached_relative
            if cached_run and cached_path.exists():
                evidence_sources[stage] = cached_run
                return cached_path
        return same_run
    for gate in ("scope", "report", "performance", "portfolio"):
        if str(quality_gates.get(gate, "missing")).lower() != "passed":
            add_issue("manual_gate_not_passed", "project.yaml", f"quality_gates.{gate} must be passed before release")

    if not (project / "EnterpriseSalesAutomation.pbip").is_file():
        add_issue("pbip_missing", "EnterpriseSalesAutomation.pbip", "Versioned PBIP entry file is missing")
    if not any(path.is_file() for path in project.glob("*.pbix")):
        add_issue("pbix_missing", "*.pbix", "A manually approved PBIX is required for release")

    for name in ("delivery-notes.md", "portfolio-case-study.md", "qa-report.md"):
        path = project / "docs" / name
        if not path.is_file() or not path.read_text(encoding="utf-8-sig").strip():
            add_issue("delivery_document_missing", f"docs/{name}", "Required delivery document is missing or empty")

    evidence_contract = (
        ("DesktopRefresh", "desktop-model/desktop-model-refresh.json"),
        ("DesktopMetrics", "desktop-metrics/desktop-metric-validation.json"),
        ("DesktopRls", "desktop-rls/desktop-rls-validation.json"),
    )
    for stage, relative in evidence_contract:
        path = resolve_evidence(stage, relative)
        if not path.is_file():
            add_issue(
                "compatible_evidence_missing",
                relative,
                "Current-run or fingerprint-compatible cached Desktop evidence is required",
            )
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            status = str(payload.get("status", "missing")).lower()
        except (OSError, json.JSONDecodeError):
            payload = {}
            status = "invalid"
        if status != "passed":
            add_issue("compatible_evidence_not_passed", relative, f"Desktop evidence status is {status}")
        elif relative == "desktop-model/desktop-model-refresh.json":
            performance_issue = refresh_performance_evidence_issue(payload, target_refresh_seconds)
            if performance_issue:
                add_issue("refresh_performance_evidence_invalid", relative, performance_issue)

    screenshot_directory = resolve_evidence("CaptureDesktopScreenshots", "desktop-screenshots")
    screenshots = sorted(screenshot_directory.glob("*.png"))
    if len(screenshots) < 3:
        add_issue(
            "desktop_screenshots_missing",
            "desktop-screenshots",
            "Three current-run or fingerprint-compatible Desktop page screenshots are required",
        )

    result = {
        "name": "Enterprise Sales Release Gate",
        "status": "passed" if not issues else "blocked",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_id": run_directory.name,
        "issues": issues,
        "evidence_sources": evidence_sources,
        "external_validation": config.get("external_validation", {}),
    }
    run_directory.mkdir(parents=True, exist_ok=True)
    (run_directory / "release-check.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown = [
        "# Enterprise Sales Release Gate",
        "",
        f"- Status: **{result['status']}**",
        f"- Run: `{run_directory.name}`",
        "",
        "| Code | Path | Message |",
        "|---|---|---|",
    ]
    if issues:
        markdown.extend(f"| {item['code']} | {item['path']} | {item['message']} |" for item in issues)
    else:
        markdown.append("| none | - | Release checks passed. |")
    (run_directory / "release-check.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    return result


def _yaml_quote(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def replace_yaml_section(text: str, section: str, values: dict[str, Any]) -> str:
    block = section + ":\n" + "\n".join(f"  {key}: {_yaml_quote(value)}" for key, value in values.items()) + "\n"
    pattern = re.compile(rf"(?ms)^{re.escape(section)}:\s*\n(?:^  .*\n?)*")
    if pattern.search(text):
        return pattern.sub(block, text)
    return text.rstrip() + "\n\n" + block


def _read_previous_fingerprints(project: Path) -> dict[str, str]:
    config = parse_simple_yaml((project / "project.yaml").read_text(encoding="utf-8-sig"))
    raw = config.get("workflow", {}).get("input_fingerprints_json", "{}")
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return {str(key): str(value) for key, value in parsed.items()}


def _read_stage_cache(project: Path) -> dict[str, dict[str, Any]]:
    config = parse_simple_yaml((project / "project.yaml").read_text(encoding="utf-8-sig"))
    raw = config.get("workflow", {}).get("stage_cache_json", "{}")
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {
        str(stage): value
        for stage, value in parsed.items()
        if isinstance(value, dict)
    }


def stage_cache_is_valid(
    stage: str,
    fingerprints: dict[str, str],
    cache: dict[str, dict[str, Any]],
) -> bool:
    entry = cache.get(stage, {})
    return entry.get("fingerprint") == stage_fingerprint(stage, fingerprints)


def bootstrap_stage_cache(project: Path) -> dict[str, Any]:
    """Seed schema-v2 cache from passed project gates and existing local evidence."""
    project_yaml = project / "project.yaml"
    text = project_yaml.read_text(encoding="utf-8-sig")
    config = parse_simple_yaml(text)
    workflow = dict(config.get("workflow", {}))
    quality = config.get("quality_gates", {})
    automation = config.get("automation", {})
    fingerprints = collect_fingerprints(project)
    cache = _read_stage_cache(project)
    generated_at = datetime.now(timezone.utc).isoformat()
    default_run_id = str(workflow.get("last_run_id", "bootstrap"))

    gate_by_stage = {
        "ValidateDataContract": "data_contract",
        "TestDataQuality": "data_quality",
        "ValidateMetrics": "metrics",
        "ValidateModelSpec": "model_spec",
        "ValidatePowerBIProject": "powerbi_project",
        "ValidateUIContract": "report",
        "GenerateReport": "report",
        "ValidateReportQA": "report",
    }
    cached: list[str] = []
    skipped: list[str] = []

    def add_cache(stage: str, run_id: str = default_run_id, evidence_relative: str | None = None) -> None:
        entry: dict[str, Any] = {
            "fingerprint": stage_fingerprint(stage, fingerprints),
            "run_id": run_id,
            "completed_at": generated_at,
            "source": "bootstrap-existing-evidence",
        }
        if evidence_relative:
            entry["evidence_relative"] = evidence_relative
        cache[stage] = entry
        cached.append(stage)

    if validate_documentation(project)["status"] == "passed":
        add_cache("ValidateDocumentation")
    else:
        skipped.append("ValidateDocumentation")
    for stage, gate in gate_by_stage.items():
        if str(quality.get(gate, "pending")).lower() == "passed":
            add_cache(stage)
        else:
            skipped.append(stage)
    if str(automation.get("prototype_status", "pending")).lower() == "passed":
        add_cache("ValidatePrototype")
    else:
        skipped.append("ValidatePrototype")

    runs_directory = project / "evidence" / "runs"
    run_directories = sorted(
        (path for path in runs_directory.iterdir() if path.is_dir()),
        key=lambda path: path.name,
        reverse=True,
    ) if runs_directory.is_dir() else []

    try:
        refresh_target_seconds = float(automation.get("target_refresh_minutes", 5)) * 60
    except (TypeError, ValueError):
        refresh_target_seconds = 300
    desktop_contract = {
        "DesktopRefresh": ("performance", ("desktop-model/desktop-model-refresh.json",)),
        "DesktopMetrics": ("metrics", ("desktop-metrics/desktop-metric-validation.json",)),
        "DesktopRls": ("rls", ("desktop-rls/desktop-rls-validation.json",)),
    }
    for stage, (gate, relatives) in desktop_contract.items():
        found: tuple[str, str] | None = None
        if str(quality.get(gate, "pending")).lower() == "passed":
            for run_directory in run_directories:
                for relative in relatives:
                    evidence_path = run_directory / relative
                    if not evidence_path.is_file():
                        continue
                    try:
                        payload = json.loads(evidence_path.read_text(encoding="utf-8-sig"))
                    except (OSError, json.JSONDecodeError):
                        continue
                    if str(payload.get("status", "missing")).lower() != "passed":
                        continue
                    if stage == "DesktopRefresh" and refresh_performance_evidence_issue(
                        payload, refresh_target_seconds
                    ):
                        continue
                    found = (run_directory.name, relative)
                    break
                if found:
                    break
        if found:
            add_cache(stage, found[0], found[1])
        else:
            skipped.append(stage)

    screenshot_found: tuple[str, str] | None = None
    if str(quality.get("report", "pending")).lower() == "passed":
        for run_directory in run_directories:
            for relative in ("saved-desktop-screenshots", "desktop-screenshots"):
                screenshot_directory = run_directory / relative
                if len(list(screenshot_directory.glob("*.png"))) >= 3:
                    screenshot_found = (run_directory.name, relative)
                    break
            if screenshot_found:
                break
    if screenshot_found:
        add_cache("CaptureDesktopScreenshots", screenshot_found[0], screenshot_found[1])
    else:
        skipped.append("CaptureDesktopScreenshots")

    workflow["schema_version"] = 2
    workflow["input_fingerprints_json"] = json.dumps(fingerprints, separators=(",", ":"))
    workflow["stage_cache_json"] = json.dumps(cache, separators=(",", ":"))
    project_yaml.write_text(replace_yaml_section(text, "workflow", workflow), encoding="utf-8")
    return {"status": "passed", "cached_stages": cached, "skipped_stages": skipped}


def _read_pending_stages(project: Path) -> list[str]:
    config = parse_simple_yaml((project / "project.yaml").read_text(encoding="utf-8-sig"))
    raw = config.get("workflow", {}).get("pending_stages_json", "[]")
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(parsed, list):
        return []
    stages: list[str] = []
    for raw_stage in parsed:
        stage = str(raw_stage)
        if stage == "DesktopQA":
            stages.extend(("DesktopPreflight", *DESKTOP_STAGES))
        elif stage != "ValidateRelease" and stage in RESUMABLE_STAGES:
            stages.append(stage)
    return list(dict.fromkeys(stages))


def _merge_stage_sequences(selected: list[str], pending: list[str]) -> list[str]:
    stages = set(selected) | set(pending)
    return [stage for stage in FULL_STAGES if stage in stages]


def build_run_plan(project: Path, *, force_full: bool, release: bool) -> dict[str, Any]:
    current = collect_fingerprints(project)
    previous = _read_previous_fingerprints(project)
    changed_groups = sorted(group for group, value in current.items() if previous.get(group) != value)
    synthetic_paths = [next(iter(GROUP_PATTERNS[group])) for group in changed_groups]
    if release:
        cache = _read_stage_cache(project)
        invalidated = [
            stage
            for stage in RELEASE_REQUIRED_STAGES
            if not stage_cache_is_valid(stage, current, cache)
        ]
        selected_stages = _merge_stage_sequences(
            ["Preflight", "ValidateStructure", *invalidated, "ValidateRelease"],
            _read_pending_stages(project),
        )
        if any(stage in selected_stages for stage in DESKTOP_STAGES) and "DesktopPreflight" not in selected_stages:
            selected_stages = _merge_stage_sequences(selected_stages, ["DesktopPreflight"])
    else:
        selected_stages = select_stages(synthetic_paths, force_full=force_full, release=False)
        if not force_full:
            selected_stages = _merge_stage_sequences(selected_stages, _read_pending_stages(project))
    return {
        "mode": "release" if release else "resume",
        "changed_groups": changed_groups,
        "selected_stages": selected_stages,
        "fingerprints": current,
    }


def _render_next_context(project: Path, report: dict[str, Any]) -> str:
    config = parse_simple_yaml((project / "project.yaml").read_text(encoding="utf-8-sig"))
    project_values = config.get("project", {})
    quality_gates = config.get("quality_gates", {})
    external = config.get("external_validation", {})
    lines = [
        "# 当前上下文",
        "",
        "> 本文件由 `scripts/bi_workflow_runtime.py` 根据 `project.yaml` 与最近工作流证据生成，请勿手工维护状态。",
        "",
        f"- 项目：{project_values.get('name', project.name)}",
        f"- 项目状态：{project_values.get('status', 'unknown')}",
        f"- 最近工作流：{report['run_id']}（{report['status']}）",
        f"- 最近模式：{report['mode']}",
        f"- 最近成功阶段：{report.get('last_successful_stage') or '无'}",
        f"- 待续跑阶段：{', '.join(report.get('pending_stages', [])) or '无'}",
        f"- 下一动作：{report.get('next_action', '查看最近运行摘要。')}",
        "",
        "## 质量门",
        "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in quality_gates.items())
    lines.extend(["", "## 外部能力边界", ""])
    lines.extend(f"- {key}: {value}" for key, value in external.items())
    lines.extend(
        [
            "",
            "## 恢复入口",
            "",
            "`./scripts/Invoke-BIWorkflow.ps1 -Stage Resume -ProjectPath ./projects/enterprise-sales-automation`",
            "",
            "原始日志和阶段结果位于：",
            f"`projects/enterprise-sales-automation/evidence/runs/{report['run_id']}/`",
        ]
    )
    return "\n".join(lines) + "\n"


def sync_next_context(project: Path) -> Path:
    """Regenerate NEXT_CONTEXT from current state and the latest workflow summary."""
    config = parse_simple_yaml((project / "project.yaml").read_text(encoding="utf-8-sig"))
    workflow = config.get("workflow", {})
    candidates: list[tuple[str, dict[str, Any]]] = []
    runs_directory = project / "evidence" / "runs"
    if runs_directory.is_dir():
        for summary_path in runs_directory.glob("*/summary.json"):
            try:
                payload = json.loads(summary_path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError):
                continue
            candidates.append((str(payload.get("generated_at", summary_path.parent.name)), payload))
    if candidates:
        report = max(candidates, key=lambda item: item[0])[1]
    else:
        report = {
            "run_id": str(workflow.get("last_run_id", "none")),
            "mode": str(workflow.get("last_mode", "resume")),
            "status": str(workflow.get("last_status", "unknown")),
            "last_successful_stage": workflow.get("last_successful_stage", ""),
            "pending_stages": _read_pending_stages(project),
            "next_action": "Run Resume to evaluate invalidated automated gates.",
        }
    next_context = _render_next_context(project, report)
    project_context = project / "NEXT_CONTEXT.md"
    project_context.write_text(next_context, encoding="utf-8")
    repository_root = project.parent.parent
    if project.parent.name == "projects" and (repository_root / "AGENTS.md").is_file():
        (repository_root / "NEXT_CONTEXT.md").write_text(next_context, encoding="utf-8")
    return project_context


def write_run_artifacts(
    project: Path,
    *,
    run_id: str,
    mode: str,
    selected_stages: list[str],
    stage_results: list[dict[str, Any]],
    fingerprints: dict[str, str],
) -> dict[str, Any]:
    project_yaml = project / "project.yaml"
    existing_text = project_yaml.read_text(encoding="utf-8-sig")
    existing_config = parse_simple_yaml(existing_text)
    existing_workflow = existing_config.get("workflow", {})
    failed = [result for result in stage_results if result.get("status") == "failed"]
    blocked = [result for result in stage_results if result.get("status") == "blocked"]
    completed_stages = {
        result["stage"] for result in stage_results if result.get("status") in {"passed", "skipped"}
    }
    pending_stages: list[str] = []
    for index, stage in enumerate(selected_stages):
        if stage not in completed_stages:
            pending_stages = selected_stages[index:]
            break
    if failed:
        status = "failed"
    elif blocked:
        status = "blocked"
    elif pending_stages:
        status = "failed"
    else:
        status = "passed"
    successful = [result["stage"] for result in stage_results if result.get("status") == "passed"]
    unresolved_result = next(
        (result for result in stage_results if result.get("status") in {"failed", "blocked"}),
        None,
    )
    if unresolved_result is not None:
        unresolved_log = unresolved_result.get(
            "log_file",
            f"evidence/runs/{run_id}/{unresolved_result['stage']}.log",
        )
        if unresolved_result.get("status") == "blocked":
            next_action = f"Resolve the blocker recorded in {unresolved_log}, then run Resume."
        else:
            next_action = f"Inspect {unresolved_log}, fix the cause, then run Resume."
    elif pending_stages:
        next_action = f"Run Resume to continue from {pending_stages[0]}."
    else:
        next_action = "No automated stage is pending; continue with the documented human quality gates."
    total_duration_ms = sum(int(result.get("duration_ms", 0) or 0) for result in stage_results)
    final_fingerprints = collect_fingerprints(project)
    generated_at = datetime.now(timezone.utc).isoformat()
    blocked_result = blocked[0] if blocked else None
    blocked_stage = str(blocked_result.get("stage", "")) if blocked_result else ""
    blocked_reason = str(blocked_result.get("blocked_reason", "unknown")) if blocked_result else ""
    blocked_at = str(blocked_result.get("blocked_at", generated_at)) if blocked_result else ""
    previous_block_matches = (
        bool(blocked_result)
        and existing_workflow.get("blocked_stage") == blocked_stage
        and existing_workflow.get("blocked_reason") == blocked_reason
    )
    blocked_since = (
        str(existing_workflow.get("blocked_since"))
        if previous_block_matches and existing_workflow.get("blocked_since")
        else blocked_at
    )
    previous_retry_count = existing_workflow.get("blocked_retry_count", 0)
    if not isinstance(previous_retry_count, int):
        previous_retry_count = 0
    blocked_retry_count = previous_retry_count + 1 if previous_block_matches else (1 if blocked_result else 0)

    report = {
        "run_id": run_id,
        "mode": mode,
        "status": status,
        "generated_at": generated_at,
        "selected_stages": selected_stages,
        "last_successful_stage": successful[-1] if successful else None,
        "pending_stages": pending_stages,
        "next_action": next_action,
        "total_duration_ms": total_duration_ms,
        "stage_results": stage_results,
        "input_fingerprints": final_fingerprints,
    }
    if blocked_result:
        report.update(
            {
                "blocked_stage": blocked_stage,
                "blocked_reason": blocked_reason,
                "blocked_at": blocked_at,
                "blocked_since": blocked_since,
                "blocked_retry_count": blocked_retry_count,
            }
        )
    elif existing_workflow.get("blocked_since"):
        report["resolved_block"] = {
            "stage": existing_workflow.get("blocked_stage", ""),
            "reason": existing_workflow.get("blocked_reason", ""),
            "blocked_since": existing_workflow.get("blocked_since", ""),
            "resolved_at": generated_at,
            "retry_count": previous_retry_count,
        }
    run_directory = project / "evidence" / "runs" / run_id
    run_directory.mkdir(parents=True, exist_ok=True)
    (run_directory / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown = [
        "# BI Workflow Run",
        "",
        f"- Run: `{run_id}`",
        f"- Mode: `{mode}`",
        f"- Status: **{status}**",
        f"- Total duration: {total_duration_ms / 1000:.1f}s",
        f"- Next action: {next_action}",
        "",
        "| Stage | Status | Exit code | Duration (s) | Timed out |",
        "|---|---|---:|---:|---|",
    ]
    for result in stage_results:
        duration_seconds = int(result.get("duration_ms", 0) or 0) / 1000
        timed_out = "yes" if result.get("timed_out") else "no"
        markdown.append(
            f"| {result['stage']} | {result['status']} | {result.get('exit_code', '-')} | "
            f"{duration_seconds:.1f} | {timed_out} |"
        )
    if blocked_result:
        markdown.extend(
            [
                "",
                "## Blocked telemetry",
                "",
                f"- Stage: `{blocked_stage}`",
                f"- Reason: `{blocked_reason}`",
                f"- Blocked since: `{blocked_since}`",
                f"- Retry count: {blocked_retry_count}",
            ]
        )
    (run_directory / "summary.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")

    stage_cache = _read_stage_cache(project)
    for result in stage_results:
        stage = str(result.get("stage", ""))
        if result.get("status") == "passed" and stage in STAGE_GROUPS:
            stage_cache[stage] = {
                "fingerprint": stage_fingerprint(stage, final_fingerprints),
                "run_id": run_id,
                "completed_at": generated_at,
            }
    workflow = {
        "schema_version": 2,
        "last_run_id": run_id,
        "last_status": status,
        "last_mode": mode,
        "last_successful_stage": report["last_successful_stage"] or "",
        "last_run_duration_ms": total_duration_ms,
        "input_fingerprints_json": json.dumps(final_fingerprints, separators=(",", ":")),
        "stage_cache_json": json.dumps(stage_cache, separators=(",", ":")),
        "pending_stages_json": json.dumps(pending_stages, separators=(",", ":")),
        "blocked_stage": blocked_stage,
        "blocked_reason": blocked_reason,
        "blocked_since": blocked_since if blocked_result else "",
        "blocked_retry_count": blocked_retry_count,
    }
    project_yaml.write_text(replace_yaml_section(existing_text, "workflow", workflow), encoding="utf-8")
    next_context = _render_next_context(project, report)
    (project / "NEXT_CONTEXT.md").write_text(next_context, encoding="utf-8")
    repository_root = project.parent.parent
    if project.parent.name == "projects" and (repository_root / "AGENTS.md").is_file():
        (repository_root / "NEXT_CONTEXT.md").write_text(next_context, encoding="utf-8")
    return report


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("--project-path", type=Path, required=True)
    plan_parser.add_argument("--force-full", action="store_true")
    plan_parser.add_argument("--release", action="store_true")
    docs_parser = subparsers.add_parser("validate-docs")
    docs_parser.add_argument("--project-path", type=Path, required=True)
    context_parser = subparsers.add_parser("sync-context")
    context_parser.add_argument("--project-path", type=Path, required=True)
    cache_parser = subparsers.add_parser("bootstrap-cache")
    cache_parser.add_argument("--project-path", type=Path, required=True)
    release_parser = subparsers.add_parser("validate-release")
    release_parser.add_argument("--project-path", type=Path, required=True)
    release_parser.add_argument("--run-directory", type=Path, required=True)
    finalize_parser = subparsers.add_parser("finalize")
    finalize_parser.add_argument("--project-path", type=Path, required=True)
    finalize_parser.add_argument("--run-id", required=True)
    finalize_parser.add_argument("--mode", choices=("resume", "release"), required=True)
    finalize_parser.add_argument("--plan-file", type=Path, required=True)
    finalize_parser.add_argument("--results-file", type=Path, required=True)
    arguments = parser.parse_args()

    if arguments.command == "plan":
        project = arguments.project_path.resolve()
        sync_next_context(project)
        print(json.dumps(build_run_plan(project, force_full=arguments.force_full, release=arguments.release)))
        return 0
    if arguments.command == "validate-docs":
        report = validate_documentation(arguments.project_path.resolve())
        print(json.dumps(report, ensure_ascii=False))
        return 0 if report["status"] == "passed" else 2
    if arguments.command == "validate-release":
        report = validate_release(arguments.project_path.resolve(), arguments.run_directory.resolve())
        print(json.dumps(report, ensure_ascii=False))
        return 0 if report["status"] == "passed" else 4
    if arguments.command == "sync-context":
        print(sync_next_context(arguments.project_path.resolve()))
        return 0
    if arguments.command == "bootstrap-cache":
        print(json.dumps(bootstrap_stage_cache(arguments.project_path.resolve()), ensure_ascii=False))
        return 0
    plan = json.loads(arguments.plan_file.read_text(encoding="utf-8-sig"))
    results = json.loads(arguments.results_file.read_text(encoding="utf-8-sig"))
    if isinstance(results, dict):
        results = [results]
    report = write_run_artifacts(
        arguments.project_path.resolve(),
        run_id=arguments.run_id,
        mode=arguments.mode,
        selected_stages=plan["selected_stages"],
        stage_results=results,
        fingerprints=plan["fingerprints"],
    )
    print(json.dumps({"status": report["status"], "run_id": report["run_id"]}))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(_main())
