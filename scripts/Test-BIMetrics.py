#!/usr/bin/env python3
"""Validate and reproduce BI metric contracts from a project CSV."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


SUPPORTED_AGGREGATIONS = {"distinct_count", "sum", "average", "ratio"}


def issue(code: str, scope: str, message: str) -> dict[str, str]:
    return {"code": code, "scope": scope, "message": message}


def read_json(path: Path, missing_code: str) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    if not path.is_file():
        return None, [issue(missing_code, str(path.name), f"Required file is missing: {path.name}")]
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, [issue("invalid_json", str(path.name), str(exc))]
    if not isinstance(value, dict):
        return None, [issue("invalid_json_root", str(path.name), "JSON root must be an object.")]
    return value, []


def validate_external_reconciliation(project_path: Path, metrics_contract: dict[str, Any]) -> list[dict[str, str]]:
    evidence_value = metrics_contract.get("baseline_evidence")
    if not isinstance(evidence_value, str) or not evidence_value.strip():
        return [issue("missing_baseline_evidence", "baseline_evidence", "External metric mode requires baseline_evidence.")]
    evidence_path = Path(evidence_value)
    if evidence_path.is_absolute() or ".." in evidence_path.parts:
        return [issue("invalid_baseline_evidence_path", "baseline_evidence", "Evidence path must be project-relative.")]
    evidence, evidence_issues = read_json(project_path / evidence_path, "baseline_evidence_not_found")
    if evidence_issues or evidence is None:
        return evidence_issues
    issues: list[dict[str, str]] = []
    if evidence.get("status") != "passed":
        issues.append(issue("baseline_reconciliation_failed", "baseline_evidence", "Reconciliation evidence status must be passed."))
    expected_ids = {metric.get("id") for metric in metrics_contract.get("metrics", []) if isinstance(metric, dict)}
    slices = evidence.get("slices")
    if not isinstance(slices, list) or not slices:
        return issues + [issue("baseline_slices_missing", "baseline_evidence", "Reconciliation evidence requires slices.")]
    for slice_item in slices:
        if not isinstance(slice_item, dict) or not isinstance(slice_item.get("reconciliation"), dict):
            issues.append(issue("baseline_slice_invalid", "baseline_evidence", "Each reconciliation slice must be an object."))
            continue
        reconciliation = slice_item["reconciliation"]
        if reconciliation.get("status") != "passed":
            issues.append(issue("baseline_slice_failed", str(slice_item.get("id", "unknown")), "Reconciliation slice must be passed."))
        results = reconciliation.get("metrics")
        if not isinstance(results, dict):
            issues.append(issue("baseline_metrics_missing", str(slice_item.get("id", "unknown")), "Reconciliation metrics are required."))
            continue
        for metric_id in expected_ids:
            result = results.get(metric_id)
            if not isinstance(result, dict) or result.get("status") not in {"passed", "both-null"}:
                issues.append(issue("baseline_metric_failed", metric_id, "Metric is missing or failed in reconciliation evidence."))
    return issues


def validate_metric_contract(
    metrics_contract: dict[str, Any], data_contract: dict[str, Any]
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if metrics_contract.get("schema_version") != 1:
        issues.append(issue("unsupported_metrics_schema", "schema_version", "schema_version must equal 1."))
    metrics = metrics_contract.get("metrics")
    if not isinstance(metrics, list) or not metrics:
        return issues + [issue("missing_metrics", "metrics", "metrics must be a non-empty array.")]

    data_columns = {
        column.get("name")
        for column in data_contract.get("columns", [])
        if isinstance(column, dict)
    }
    metric_ids: list[str] = []
    for index, metric in enumerate(metrics):
        scope = f"metrics[{index}]"
        if not isinstance(metric, dict):
            issues.append(issue("invalid_metric", scope, "Metric definition must be an object."))
            continue
        for field in ("id", "name", "aggregation", "expected", "tolerance", "format_string"):
            if field not in metric or metric[field] in (None, ""):
                issues.append(issue("missing_metric_field", f"{scope}.{field}", f"Metric field is required: {field}"))
        metric_id = metric.get("id")
        if isinstance(metric_id, str):
            metric_ids.append(metric_id)
        aggregation = metric.get("aggregation")
        if aggregation not in SUPPORTED_AGGREGATIONS:
            issues.append(issue("unsupported_aggregation", f"{scope}.aggregation", f"Unsupported aggregation: {aggregation}"))
        if aggregation in {"distinct_count", "sum", "average"}:
            column = metric.get("column")
            if not isinstance(column, str) or not column:
                issues.append(issue("missing_metric_column", f"{scope}.column", "Aggregation requires a column."))
            elif column not in data_columns:
                issues.append(issue("unknown_metric_column", f"{scope}.column", f"Column is not defined in the data contract: {column}"))
        if aggregation == "ratio":
            for field in ("numerator_metric", "denominator_metric"):
                if not isinstance(metric.get(field), str) or not metric[field]:
                    issues.append(issue("missing_ratio_metric", f"{scope}.{field}", f"Ratio requires {field}."))
        for field in ("expected", "tolerance"):
            value = metric.get(field)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                issues.append(issue("invalid_metric_number", f"{scope}.{field}", f"{field} must be numeric."))
        if isinstance(metric.get("tolerance"), (int, float)) and metric["tolerance"] < 0:
            issues.append(issue("invalid_metric_tolerance", f"{scope}.tolerance", "tolerance cannot be negative."))

    duplicate_ids = sorted({value for value in metric_ids if metric_ids.count(value) > 1})
    for metric_id in duplicate_ids:
        issues.append(issue("duplicate_metric_id", "metrics", f"Metric id is duplicated: {metric_id}"))

    known_ids = set(metric_ids)
    for index, metric in enumerate(metrics):
        if isinstance(metric, dict) and metric.get("aggregation") == "ratio":
            for field in ("numerator_metric", "denominator_metric"):
                dependency = metric.get(field)
                if isinstance(dependency, str) and dependency not in known_ids:
                    issues.append(issue("unknown_metric_dependency", f"metrics[{index}].{field}", f"Unknown metric dependency: {dependency}"))
                if dependency == metric.get("id"):
                    issues.append(issue("self_metric_dependency", f"metrics[{index}].{field}", "Metric cannot depend on itself."))
    return issues


def decimal_value(raw: str) -> Decimal:
    return Decimal(raw.strip())


def calculate_metrics(
    metrics_contract: dict[str, Any], data_contract: dict[str, Any], project_path: Path
) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]], int]:
    source = data_contract["dataset"]["source"]
    data_path = (project_path / source["path"]).resolve()
    if not data_path.is_file():
        return {}, [issue("data_file_not_found", "dataset.source.path", f"CSV file not found: {source['path']}")], 0
    try:
        with data_path.open(
            "r",
            encoding=source.get("encoding", "utf-8-sig"),
            newline="",
        ) as handle:
            rows = list(csv.DictReader(handle, delimiter=source.get("delimiter", ",")))
    except (OSError, UnicodeError, csv.Error) as exc:
        return {}, [issue("csv_read_error", "dataset.source.path", str(exc))], 0

    issues: list[dict[str, str]] = []
    actual_values: dict[str, Decimal] = {}
    metric_by_id = {metric["id"]: metric for metric in metrics_contract["metrics"]}

    for metric in metrics_contract["metrics"]:
        aggregation = metric["aggregation"]
        if aggregation == "ratio":
            continue
        raw_values = [
            row.get(metric["column"], "").strip()
            for row in rows
            if row.get(metric["column"], "").strip()
        ]
        try:
            if aggregation == "distinct_count":
                actual_values[metric["id"]] = Decimal(len(set(raw_values)))
            elif aggregation == "sum":
                actual_values[metric["id"]] = sum((decimal_value(value) for value in raw_values), Decimal(0))
            elif aggregation == "average":
                if not raw_values:
                    issues.append(issue("empty_metric_input", metric["id"], "Average has no nonblank input values."))
                else:
                    actual_values[metric["id"]] = sum(
                        (decimal_value(value) for value in raw_values), Decimal(0)
                    ) / Decimal(len(raw_values))
        except InvalidOperation:
            issues.append(issue("invalid_metric_input", metric["id"], "Metric input contains a non-numeric value."))

    unresolved = {
        metric["id"]
        for metric in metrics_contract["metrics"]
        if metric["aggregation"] == "ratio"
    }
    for _ in range(len(unresolved) + 1):
        progressed = False
        for metric_id in list(unresolved):
            metric = metric_by_id[metric_id]
            numerator = actual_values.get(metric["numerator_metric"])
            denominator = actual_values.get(metric["denominator_metric"])
            if numerator is None or denominator is None:
                continue
            if denominator == 0:
                issues.append(issue("zero_metric_denominator", metric_id, "Ratio denominator is zero."))
            else:
                actual_values[metric_id] = numerator / denominator
            unresolved.remove(metric_id)
            progressed = True
        if not progressed:
            break
    for metric_id in sorted(unresolved):
        issues.append(issue("unresolved_metric_dependency", metric_id, "Metric dependencies could not be resolved."))

    results: dict[str, dict[str, Any]] = {}
    for metric in metrics_contract["metrics"]:
        metric_id = metric["id"]
        if metric_id not in actual_values:
            continue
        actual = actual_values[metric_id]
        expected = Decimal(str(metric["expected"]))
        tolerance = Decimal(str(metric["tolerance"]))
        difference = abs(actual - expected)
        status = "passed" if difference <= tolerance else "failed"
        if status == "failed":
            issues.append(issue("metric_mismatch", metric_id, "Actual metric differs from expected value beyond tolerance."))
        results[metric_id] = {
            "name": metric["name"],
            "actual": int(actual) if actual == actual.to_integral_value() else float(actual),
            "expected": metric["expected"],
            "difference": int(difference) if difference == difference.to_integral_value() else float(difference),
            "tolerance": metric["tolerance"],
            "status": status,
            "format_string": metric["format_string"],
        }
    return results, issues, len(rows)


def write_report(
    project_path: Path,
    results: dict[str, dict[str, Any]],
    issues: list[dict[str, str]],
    row_count: int,
) -> None:
    output_path = project_path / "evidence" / "metrics"
    output_path.mkdir(parents=True, exist_ok=True)
    status = "passed" if not issues else "failed"
    report = {
        "name": "BI Metric Validation",
        "status": status,
        "generated_at": datetime.now().astimezone().isoformat(),
        "project_path": ".",
        "summary": {
            "row_count": row_count,
            "metric_count": len(results),
            "issue_count": len(issues),
        },
        "results": results,
        "issues": issues,
    }
    (output_path / "metrics-validation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# BI Metric Validation",
        "",
        f"- Status: **{status}**",
        f"- Rows: {row_count}",
        f"- Metrics: {len(results)}",
        f"- Issues: {len(issues)}",
        "",
        "| Metric | Actual | Expected | Difference | Result |",
        "|---|---:|---:|---:|---|",
    ]
    for metric_id, result in results.items():
        lines.append(
            f"| {metric_id} | {result['actual']} | {result['expected']} | {result['difference']} | {result['status']} |"
        )
    if issues:
        lines.extend(["", "## Issues", "", "| Code | Scope | Message |", "|---|---|---|"])
        for item in issues:
            lines.append(f"| {item['code']} | {item['scope']} | {item['message'].replace('|', '\\|')} |")
    (output_path / "metrics-validation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(project_path: Path) -> int:
    metrics_contract, metric_read_issues = read_json(
        project_path / "config" / "metrics.json", "metrics_contract_not_found"
    )
    data_contract, data_read_issues = read_json(
        project_path / "config" / "data-contract.json", "data_contract_not_found"
    )
    issues = metric_read_issues + data_read_issues
    results: dict[str, dict[str, Any]] = {}
    row_count = 0
    if metrics_contract is not None and data_contract is not None:
        if metrics_contract.get("validation_mode") == "external-reconciliation":
            issues.extend(validate_external_reconciliation(project_path, metrics_contract))
            if not issues:
                results = {
                    metric["id"]: {
                        "name": metric["name"],
                        "actual": "reconciliation.json",
                        "expected": "passed",
                        "difference": "n/a",
                        "tolerance": "see reconciliation.json",
                        "status": "passed",
                        "format_string": metric.get("format_string", ""),
                    }
                    for metric in metrics_contract.get("metrics", [])
                    if isinstance(metric, dict) and isinstance(metric.get("id"), str) and isinstance(metric.get("name"), str)
                }
        else:
            issues.extend(validate_metric_contract(metrics_contract, data_contract))
            if not issues:
                results, calculation_issues, row_count = calculate_metrics(
                    metrics_contract, data_contract, project_path
                )
                issues.extend(calculation_issues)
    write_report(project_path, results, issues, row_count)
    for item in issues:
        print(f"{item['code']}: {item['scope']}: {item['message']}")
    print("metrics_validation_passed" if not issues else "metrics_validation_failed")
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
