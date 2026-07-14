#!/usr/bin/env python3
"""Validate report QA readiness for a file-based BI project."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


REPORT_DEFINITION_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json"


def issue(code: str, scope: str, message: str) -> dict[str, str]:
    return {"code": code, "scope": scope, "message": message}


def has_content(path: Path) -> bool:
    try:
        return path.is_file() and bool(path.read_text(encoding="utf-8-sig").strip())
    except OSError:
        return False


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except OSError:
        return ""


def find_report_dirs(project_path: Path) -> list[Path]:
    return sorted(
        path
        for path in project_path.glob("*.Report")
        if path.is_dir() and (path / "definition.pbir").is_file()
    )


def extract_gate_result(markdown: str, gate_name: str) -> str | None:
    pattern = re.compile(
        rf"^\|\s*{re.escape(gate_name)}\s*\|(?P<cells>.+)\|$",
        re.IGNORECASE | re.MULTILINE,
    )
    match = pattern.search(markdown)
    if not match:
        return None
    cells = [cell.strip() for cell in match.group("cells").split("|")]
    if len(cells) < 2:
        return None
    return cells[1]


def extract_status_line(markdown: str, heading: str) -> str | None:
    heading_pattern = re.compile(rf"^##\s+{re.escape(heading)}\s*$", re.IGNORECASE | re.MULTILINE)
    match = heading_pattern.search(markdown)
    if not match:
        return None
    section = markdown[match.end():]
    next_heading = re.search(r"^##\s+", section, re.MULTILINE)
    if next_heading:
        section = section[: next_heading.start()]
    status_match = re.search(r"^\s*-\s*Status:\s*(?P<status>.+?)\s*$", section, re.IGNORECASE | re.MULTILINE)
    if not status_match:
        return None
    return status_match.group("status").strip()


def validate(project_path: Path) -> tuple[str, dict[str, Any], list[dict[str, str]]]:
    issues: list[dict[str, str]] = []
    summary: dict[str, Any] = {
        "report_count": 0,
        "page_count": 0,
        "visual_count": 0,
        "report_gate_result": None,
        "release_gate_result": None,
        "desktop_render_status": None,
    }

    blueprint_path = project_path / "docs" / "dashboard-blueprint.md"
    qa_report_path = project_path / "docs" / "qa-report.md"
    if not has_content(blueprint_path):
        issues.append(issue("dashboard_blueprint_missing", "docs/dashboard-blueprint.md", "Dashboard blueprint is missing or empty."))
    if not has_content(qa_report_path):
        issues.append(issue("qa_report_missing", "docs/qa-report.md", "QA report is missing or empty."))

    qa_text = read_text(qa_report_path)
    report_gate_result = extract_gate_result(qa_text, "Report")
    release_gate_result = extract_gate_result(qa_text, "Release")
    desktop_render_status = extract_status_line(qa_text, "Desktop render evidence")
    summary["report_gate_result"] = report_gate_result
    summary["release_gate_result"] = release_gate_result
    summary["desktop_render_status"] = desktop_render_status

    if not report_gate_result:
        issues.append(issue("report_gate_missing", "docs/qa-report.md", "QA report must contain a Report gate row."))
    elif any(value in report_gate_result.lower() for value in ("failed", "blocked")):
        issues.append(issue("report_gate_failed", "docs/qa-report.md", f"Report gate is explicitly failed or blocked: {report_gate_result}"))

    if not desktop_render_status:
        issues.append(issue("desktop_render_status_missing", "docs/qa-report.md", "QA report must record Desktop render evidence as Passed, Pending, Failed, or Blocked."))
    elif any(value in desktop_render_status.lower() for value in ("failed", "blocked")):
        issues.append(issue("desktop_render_failed", "docs/qa-report.md", f"Desktop render evidence is explicitly failed or blocked: {desktop_render_status}"))

    qa_lower = qa_text.lower()
    for keyword in ("refresh", "visual", "performance", "release"):
        if keyword not in qa_lower:
            issues.append(issue("manual_report_check_missing", "docs/qa-report.md", f"QA report must mention manual check area: {keyword}"))

    report_dirs = find_report_dirs(project_path)
    summary["report_count"] = len(report_dirs)
    if not report_dirs:
        issues.append(issue("report_project_missing", "*.Report", "No PBIR report project directory was found."))

    page_files: list[Path] = []
    visual_files: list[Path] = []
    for report_dir in report_dirs:
        pbir_path = report_dir / "definition.pbir"
        pbir_scope = str(pbir_path.relative_to(project_path)).replace("\\", "/")
        try:
            pbir = json.loads(pbir_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            issues.append(issue("report_definition_invalid", pbir_scope, f"definition.pbir is not valid JSON: {exc}"))
            pbir = None
        if isinstance(pbir, dict) and pbir.get("$schema") != REPORT_DEFINITION_SCHEMA:
            issues.append(
                issue(
                    "report_definition_schema_missing",
                    pbir_scope,
                    "definition.pbir must declare the enhanced PBIR definitionProperties 2.0.0 schema.",
                )
            )
        definition_path = report_dir / "definition"
        pages_metadata = definition_path / "pages" / "pages.json"
        if not pages_metadata.is_file():
            issues.append(issue("report_pages_metadata_missing", str(pages_metadata.relative_to(project_path)).replace("\\", "/"), "PBIR pages metadata is missing."))
        page_files.extend(definition_path.glob("pages/*/page.json"))
        visual_files.extend(definition_path.glob("pages/*/visuals/*/visual.json"))

    summary["page_count"] = len(page_files)
    summary["visual_count"] = len(visual_files)
    if not page_files:
        issues.append(issue("report_pages_missing", "PBIR pages", "No PBIR page definition files were found."))
    if not visual_files:
        issues.append(issue("report_visuals_missing", "PBIR visuals", "No PBIR visual definition files were found."))

    status = "passed" if not issues else "blocked"
    return status, summary, issues


def write_report(project_path: Path, status: str, summary: dict[str, Any], issues: list[dict[str, str]]) -> None:
    output_path = project_path / "evidence" / "report"
    output_path.mkdir(parents=True, exist_ok=True)

    report = {
        "name": "BI Report QA Validation",
        "status": status,
        "generated_at": datetime.now().astimezone().isoformat(),
        "project_path": ".",
        "summary": {**summary, "issue_count": len(issues)},
        "issues": issues,
        "manual_or_external_checks": [
            "Power BI Desktop refresh",
            "Human visual and interaction review",
            "Performance Analyzer or equivalent performance check",
            "Power BI Service/Fabric publish, permissions, and sign-off",
        ],
    }
    (output_path / "report-qa.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        "# BI Report QA Validation",
        "",
        f"- Status: **{status}**",
        f"- Reports: {summary.get('report_count', 0)}",
        f"- Pages: {summary.get('page_count', 0)}",
        f"- Visuals: {summary.get('visual_count', 0)}",
        f"- Issues: {len(issues)}",
        "",
        "| Code | Scope | Message |",
        "|---|---|---|",
    ]
    if issues:
        for item in issues:
            lines.append(f"| {item['code']} | {item['scope']} | {item['message'].replace('|', '\\|')} |")
    else:
        lines.append("| none | - | Report QA checks passed. |")
    lines.extend(
        [
            "",
            "## Manual or external checks",
            "",
            "- Power BI Desktop refresh.",
            "- Human visual and interaction review.",
            "- Performance Analyzer or equivalent performance check.",
            "- Power BI Service/Fabric publish, permissions, and sign-off.",
        ]
    )
    (output_path / "report-qa.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(project_path: Path) -> int:
    status, summary, issues = validate(project_path)
    write_report(project_path, status, summary, issues)
    for item in issues:
        print(f"{item['code']}: {item['scope']}: {item['message']}")
    print("report_qa_passed" if status == "passed" else "report_qa_failed")
    return 0 if status == "passed" else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-path", required=True, type=Path)
    arguments = parser.parse_args()
    if not arguments.project_path.is_dir():
        print(f"project_not_found: {arguments.project_path}")
        return 3
    try:
        return run(arguments.project_path.resolve())
    except Exception as exc:
        print(f"unexpected_error: {type(exc).__name__}: {exc}")
        return 3


if __name__ == "__main__":
    sys.exit(main())
