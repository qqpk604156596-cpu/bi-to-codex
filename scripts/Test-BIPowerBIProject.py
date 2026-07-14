#!/usr/bin/env python3
"""Validate file-based Power BI Project wrappers and local model references."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

LOCAL_PATH_PATTERNS = (
    "C:/Users/",
    "C:\\Users\\",
    "/Users/",
)


def issue(code: str, scope: str, message: str) -> dict[str, str]:
    return {"code": code, "scope": scope, "message": message}


def read_json(path: Path, missing_code: str) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    if not path.is_file():
        return None, [issue(missing_code, str(path), f"Required file is missing: {path.name}")]
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, [issue("invalid_json", str(path), str(exc))]
    if not isinstance(value, dict):
        return None, [issue("invalid_json_root", str(path), "JSON root must be an object.")]
    return value, []


def safe_relative(path: Path, project_path: Path) -> str:
    try:
        return str(path.relative_to(project_path)).replace("\\", "/")
    except ValueError:
        return str(path)


def resolve_relative(base_file: Path, relative_path: str) -> Path:
    return (base_file.parent / relative_path.replace("/", "\\")).resolve()


def validate_report_definition(report_folder: Path, project_path: Path) -> tuple[list[dict[str, str]], dict[str, bool]]:
    issues: list[dict[str, str]] = []
    checks = {
        "report_json": False,
        "pages_json": False,
        "version_json": False,
    }
    required_json_files = [
        ("report_definition_report_missing", report_folder / "definition" / "report.json", "report_json"),
        ("report_definition_pages_missing", report_folder / "definition" / "pages" / "pages.json", "pages_json"),
        ("report_definition_version_missing", report_folder / "definition" / "version.json", "version_json"),
    ]
    for missing_code, path, check_name in required_json_files:
        value, read_issues = read_json(path, missing_code)
        issues.extend(read_issues)
        checks[check_name] = value is not None
    return issues, checks


def validate_semantic_model(semantic_model_folder: Path, project_path: Path) -> tuple[list[dict[str, str]], dict[str, int | bool]]:
    issues: list[dict[str, str]] = []
    checks: dict[str, int | bool] = {
        "definition_pbism": False,
        "database_tmdl": False,
        "model_tmdl": False,
        "relationships_tmdl": False,
        "table_tmdl_count": 0,
        "source_parameter": False,
        "portable_source_paths": True,
    }

    pbism, pbism_issues = read_json(
        semantic_model_folder / "definition.pbism", "semantic_model_definition_missing"
    )
    issues.extend(pbism_issues)
    checks["definition_pbism"] = pbism is not None

    tmdl_definition = semantic_model_folder / "definition"
    required_tmdl_files = [
        ("semantic_model_database_missing", tmdl_definition / "database.tmdl", "database_tmdl"),
        ("semantic_model_model_missing", tmdl_definition / "model.tmdl", "model_tmdl"),
        ("semantic_model_relationships_missing", tmdl_definition / "relationships.tmdl", "relationships_tmdl"),
    ]
    for missing_code, path, check_name in required_tmdl_files:
        exists = path.is_file()
        checks[check_name] = exists
        if not exists:
            issues.append(
                issue(missing_code, safe_relative(path, project_path), f"Required TMDL file is missing: {path.name}")
            )

    table_tmdl_files = sorted((tmdl_definition / "tables").glob("*.tmdl"))
    checks["table_tmdl_count"] = len(table_tmdl_files)
    if not table_tmdl_files:
        issues.append(
            issue(
                "semantic_model_tables_missing",
                safe_relative(tmdl_definition / "tables", project_path),
                "At least one table TMDL file is required.",
            )
        )

    expressions_path = tmdl_definition / "expressions.tmdl"
    expressions_text = ""
    if expressions_path.is_file():
        try:
            expressions_text = expressions_path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            issues.append(issue("tmdl_read_error", safe_relative(expressions_path, project_path), str(exc)))
    has_csv_parameter = (
        "expression SourceCsvPath" in expressions_text
        and "IsParameterQuery=true" in expressions_text
    )
    has_mysql_parameters = (
        "expression MySqlServer" in expressions_text
        and "expression MySqlDatabase" in expressions_text
        and expressions_text.count("IsParameterQuery=true") >= 2
    )
    checks["source_parameter"] = has_csv_parameter or has_mysql_parameters
    if not checks["source_parameter"]:
        issues.append(
            issue(
                "missing_tmdl_source_parameter",
                safe_relative(expressions_path, project_path),
                "Semantic model must define either SourceCsvPath or MySqlServer and MySqlDatabase Power Query parameters.",
            )
        )

    for tmdl_path in sorted(tmdl_definition.rglob("*.tmdl")):
        try:
            text = tmdl_path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            issues.append(issue("tmdl_read_error", safe_relative(tmdl_path, project_path), str(exc)))
            continue
        normalized_text = text.replace("\\\\", "\\")
        if str(project_path).replace("\\", "/") in normalized_text.replace("\\", "/"):
            checks["portable_source_paths"] = False
            issues.append(
                issue(
                    "absolute_tmdl_source_path",
                    safe_relative(tmdl_path, project_path),
                    "TMDL must not contain the project absolute path.",
                )
            )
        for pattern in LOCAL_PATH_PATTERNS:
            if pattern in normalized_text:
                checks["portable_source_paths"] = False
                issues.append(
                    issue(
                        "absolute_tmdl_source_path",
                        safe_relative(tmdl_path, project_path),
                        f"TMDL must not contain local absolute path pattern: {pattern}",
                    )
                )
                break
        if "File.Contents(" in text and "File.Contents(SourceCsvPath)" not in text:
            checks["portable_source_paths"] = False
            issues.append(
                issue(
                    "unparameterized_tmdl_file_contents",
                    safe_relative(tmdl_path, project_path),
                    "File.Contents calls must use SourceCsvPath.",
                )
            )

    return issues, checks


def validate_powerbi_project(project_path: Path) -> tuple[list[dict[str, str]], dict[str, Any]]:
    issues: list[dict[str, str]] = []
    summary: dict[str, Any] = {
        "pbip_count": 0,
        "report_count": 0,
        "semantic_model_count": 0,
        "report_checks": [],
        "semantic_model_checks": [],
    }

    pbip_files = sorted(project_path.glob("*.pbip"))
    summary["pbip_count"] = len(pbip_files)
    if not pbip_files:
        issues.append(issue("pbip_not_found", ".", "At least one .pbip project shortcut is required."))
        return issues, summary

    seen_semantic_models: set[Path] = set()
    for pbip_path in pbip_files:
        pbip, pbip_issues = read_json(pbip_path, "pbip_not_found")
        issues.extend(pbip_issues)
        if pbip is None:
            continue

        artifacts = pbip.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            issues.append(issue("pbip_artifacts_missing", safe_relative(pbip_path, project_path), "PBIP artifacts must be a non-empty array."))
            continue

        for index, artifact in enumerate(artifacts):
            scope = f"{safe_relative(pbip_path, project_path)}.artifacts[{index}]"
            if not isinstance(artifact, dict):
                issues.append(issue("pbip_artifact_invalid", scope, "PBIP artifact must be an object."))
                continue
            report = artifact.get("report")
            if not isinstance(report, dict) or not isinstance(report.get("path"), str) or not report["path"].strip():
                issues.append(issue("report_path_missing", scope, "PBIP artifact must include report.path."))
                continue

            report_folder = resolve_relative(pbip_path, report["path"])
            summary["report_count"] += 1
            if not report_folder.is_dir():
                issues.append(
                    issue(
                        "report_folder_missing",
                        safe_relative(report_folder, project_path),
                        "PBIP report.path does not point to an existing report folder.",
                    )
                )
                continue

            report_issues, report_checks = validate_report_definition(report_folder, project_path)
            issues.extend(report_issues)
            summary["report_checks"].append(
                {
                    "path": safe_relative(report_folder, project_path),
                    **report_checks,
                }
            )

            pbir_path = report_folder / "definition.pbir"
            pbir, pbir_issues = read_json(pbir_path, "pbir_missing")
            issues.extend(pbir_issues)
            if pbir is None:
                continue

            dataset_reference = pbir.get("datasetReference")
            if not isinstance(dataset_reference, dict):
                issues.append(issue("pbir_dataset_reference_missing", safe_relative(pbir_path, project_path), "definition.pbir must include datasetReference."))
                continue
            by_path = dataset_reference.get("byPath")
            by_connection = dataset_reference.get("byConnection")
            if by_connection is not None:
                issues.append(issue("pbir_by_connection_unsupported", safe_relative(pbir_path, project_path), "This workflow gate only supports local byPath semantic-model references."))
            if not isinstance(by_path, dict) or not isinstance(by_path.get("path"), str) or not by_path["path"].strip():
                issues.append(issue("pbir_by_path_missing", safe_relative(pbir_path, project_path), "definition.pbir must include datasetReference.byPath.path."))
                continue

            semantic_model_folder = resolve_relative(pbir_path, by_path["path"])
            if not semantic_model_folder.is_dir():
                issues.append(
                    issue(
                        "semantic_model_path_missing",
                        safe_relative(semantic_model_folder, project_path),
                        "definition.pbir byPath does not point to an existing semantic model folder.",
                    )
                )
                continue
            seen_semantic_models.add(semantic_model_folder)

    for semantic_model_folder in sorted(seen_semantic_models):
        semantic_issues, semantic_checks = validate_semantic_model(semantic_model_folder, project_path)
        issues.extend(semantic_issues)
        summary["semantic_model_checks"].append(
            {
                "path": safe_relative(semantic_model_folder, project_path),
                **semantic_checks,
            }
        )
    summary["semantic_model_count"] = len(seen_semantic_models)
    return issues, summary


def write_report(project_path: Path, issues: list[dict[str, str]], summary: dict[str, Any]) -> None:
    output_path = project_path / "evidence" / "model"
    output_path.mkdir(parents=True, exist_ok=True)
    status = "passed" if not issues else "failed"
    report = {
        "name": "Power BI Project Structure Validation",
        "status": status,
        "scope": "pbip_pbir_pbism_tmdl_structure",
        "desktop_cold_start_executed": False,
        "generated_at": datetime.now().astimezone().isoformat(),
        "project_path": ".",
        "summary": {**summary, "issue_count": len(issues)},
        "issues": issues,
    }
    (output_path / "powerbi-project-validation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        "# Power BI Project Structure Validation",
        "",
        f"- Status: **{status}**",
        "- Scope: PBIP/PBIR/PBISM/TMDL file structure",
        "- Desktop cold-start executed: **No**",
        f"- PBIP files: {summary.get('pbip_count', 0)}",
        f"- Reports: {summary.get('report_count', 0)}",
        f"- Semantic models: {summary.get('semantic_model_count', 0)}",
        f"- Issues: {len(issues)}",
        "",
        "| Code | Scope | Message |",
        "|---|---|---|",
    ]
    if issues:
        for item in issues:
            lines.append(f"| {item['code']} | {item['scope']} | {item['message'].replace('|', '\\|')} |")
    else:
        lines.append("| none | - | Power BI project structure checks passed. |")
    (output_path / "powerbi-project-validation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(project_path: Path) -> int:
    issues, summary = validate_powerbi_project(project_path)
    write_report(project_path, issues, summary)
    for item in issues:
        print(f"{item['code']}: {item['scope']}: {item['message']}")
    print("powerbi_project_validation_passed" if not issues else "powerbi_project_validation_failed")
    return 0 if not issues else 2


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
