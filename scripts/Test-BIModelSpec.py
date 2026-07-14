#!/usr/bin/env python3
"""Validate a file-based semantic model design specification."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def issue(code: str, scope: str, message: str) -> dict[str, str]:
    return {"code": code, "scope": scope, "message": message}


def read_json(path: Path, missing_code: str) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    if not path.is_file():
        return None, [issue(missing_code, path.name, f"Required file is missing: {path.name}")]
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, [issue("invalid_json", path.name, str(exc))]
    if not isinstance(value, dict):
        return None, [issue("invalid_json_root", path.name, "JSON root must be an object.")]
    return value, []


def validate_model_spec(
    model_spec: dict[str, Any], metrics_contract: dict[str, Any]
) -> tuple[list[dict[str, str]], dict[str, int]]:
    issues: list[dict[str, str]] = []
    if model_spec.get("schema_version") != 1:
        issues.append(issue("unsupported_model_schema", "schema_version", "schema_version must equal 1."))

    model = model_spec.get("model")
    if not isinstance(model, dict):
        return issues + [issue("missing_model", "model", "model must be an object.")], {}
    for field in ("name", "fact_table", "date_table"):
        if not isinstance(model.get(field), str) or not model[field]:
            issues.append(issue("missing_model_field", f"model.{field}", f"Model field is required: {field}"))

    tables = model_spec.get("tables")
    if not isinstance(tables, list) or not tables:
        return issues + [issue("missing_tables", "tables", "tables must be a non-empty array.")], {}
    table_map: dict[str, dict[str, Any]] = {}
    for index, table in enumerate(tables):
        scope = f"tables[{index}]"
        if not isinstance(table, dict):
            issues.append(issue("invalid_table", scope, "Table definition must be an object."))
            continue
        for field in ("name", "kind", "columns"):
            if field not in table or table[field] in (None, "", []):
                issues.append(issue("missing_table_field", f"{scope}.{field}", f"Table field is required: {field}"))
        name = table.get("name")
        if isinstance(name, str):
            if name in table_map:
                issues.append(issue("duplicate_table", scope, f"Table is duplicated: {name}"))
            table_map[name] = table
        if table.get("kind") not in {"fact", "date", "dimension", "security-bridge"}:
            issues.append(issue("unsupported_table_kind", f"{scope}.kind", "kind must be fact, date, dimension, or security-bridge."))
        columns = table.get("columns")
        if isinstance(columns, list) and len(columns) != len(set(columns)):
            issues.append(issue("duplicate_model_column", f"{scope}.columns", "Table columns must be unique."))
        if table.get("kind") == "fact":
            for field in ("grain", "source"):
                if not isinstance(table.get(field), str) or not table[field].strip():
                    issues.append(issue("missing_fact_field", f"{scope}.{field}", f"Fact-table field is required: {field}"))
        if table.get("kind") in {"date", "dimension"}:
            primary_key = table.get("primary_key")
            if not isinstance(primary_key, str) or primary_key not in (columns or []):
                issues.append(issue("invalid_dimension_key", f"{scope}.primary_key", "Dimension primary key must be a defined column."))
        if table.get("kind") == "security-bridge":
            if not isinstance(table.get("grain"), str) or not table["grain"].strip():
                issues.append(issue("missing_security_bridge_grain", f"{scope}.grain", "Security bridge requires a grain."))

    fact_table_name = model.get("fact_table")
    if fact_table_name not in table_map or table_map.get(fact_table_name, {}).get("kind") != "fact":
        issues.append(issue("missing_fact_table", "model.fact_table", "Configured fact table is missing or not kind fact."))
    date_table_name = model.get("date_table")
    if date_table_name not in table_map or table_map.get(date_table_name, {}).get("kind") != "date":
        issues.append(issue("missing_date_table", "model.date_table", "Configured date table is missing or not kind date."))

    relationships = model_spec.get("relationships")
    if not isinstance(relationships, list):
        issues.append(issue("invalid_relationships", "relationships", "relationships must be an array."))
        relationships = []
    related_dimensions: set[str] = set()
    for index, relationship in enumerate(relationships):
        scope = f"relationships[{index}]"
        if not isinstance(relationship, dict):
            issues.append(issue("invalid_relationship", scope, "Relationship must be an object."))
            continue
        for field in ("from_table", "from_column", "to_table", "to_column", "cardinality", "active"):
            if field not in relationship:
                issues.append(issue("missing_relationship_field", f"{scope}.{field}", f"Relationship field is required: {field}"))
        from_table = relationship.get("from_table")
        to_table = relationship.get("to_table")
        if from_table not in table_map or to_table not in table_map:
            issues.append(issue("unknown_relationship_table", scope, "Relationship references an unknown table."))
            continue
        if relationship.get("from_column") not in table_map[from_table].get("columns", []):
            issues.append(issue("unknown_relationship_column", f"{scope}.from_column", "from_column is not defined on from_table."))
        if relationship.get("to_column") not in table_map[to_table].get("columns", []):
            issues.append(issue("unknown_relationship_column", f"{scope}.to_column", "to_column is not defined on to_table."))
        if relationship.get("cardinality") != "many-to-one":
            issues.append(issue("unsupported_cardinality", f"{scope}.cardinality", "Only many-to-one is allowed in this model specification."))
        if not isinstance(relationship.get("active"), bool):
            issues.append(issue("invalid_relationship_active", f"{scope}.active", "active must be boolean."))
        if table_map[from_table].get("kind") == "security-bridge" and to_table == fact_table_name:
            issues.append(issue("security_bridge_direct_fact", scope, "Security bridge must filter a dimension, not the fact table directly."))
        if from_table == fact_table_name and table_map[to_table].get("kind") in {"date", "dimension"}:
            related_dimensions.add(to_table)

    for table_name, table in table_map.items():
        if table.get("kind") in {"date", "dimension"} and table_name not in related_dimensions:
            issues.append(issue("unrelated_dimension", table_name, "Dimension has no relationship from the fact table."))

    metric_ids = {
        metric.get("id")
        for metric in metrics_contract.get("metrics", [])
        if isinstance(metric, dict) and isinstance(metric.get("id"), str)
    }
    measures = model_spec.get("measures")
    if not isinstance(measures, list):
        issues.append(issue("invalid_measures", "measures", "measures must be an array."))
        measures = []
    mapped_metrics: list[str] = []
    for index, measure in enumerate(measures):
        scope = f"measures[{index}]"
        if not isinstance(measure, dict):
            issues.append(issue("invalid_measure", scope, "Measure must be an object."))
            continue
        for field in ("name", "metric_id", "table", "expression", "format_string"):
            if not isinstance(measure.get(field), str) or not measure[field].strip():
                issues.append(issue("missing_measure_field", f"{scope}.{field}", f"Measure field is required: {field}"))
        metric_id = measure.get("metric_id")
        if isinstance(metric_id, str):
            mapped_metrics.append(metric_id)
            if metric_id not in metric_ids:
                issues.append(issue("unknown_measure_metric", f"{scope}.metric_id", f"Measure maps to unknown metric: {metric_id}"))
        if measure.get("table") not in table_map:
            issues.append(issue("unknown_measure_table", f"{scope}.table", "Measure table is not defined."))
    for metric_id in sorted(metric_ids - set(mapped_metrics)):
        issues.append(issue("unmapped_metric", metric_id, "Metric has no semantic-model measure mapping."))
    for metric_id in sorted({value for value in mapped_metrics if mapped_metrics.count(value) > 1}):
        issues.append(issue("duplicate_metric_mapping", metric_id, "Metric is mapped by more than one measure."))

    summary = {
        "table_count": len(table_map),
        "relationship_count": len(relationships),
        "measure_count": len(measures),
        "metric_count": len(metric_ids),
    }
    return issues, summary


def write_report(
    project_path: Path, issues: list[dict[str, str]], summary: dict[str, int]
) -> None:
    output_path = project_path / "evidence" / "model"
    output_path.mkdir(parents=True, exist_ok=True)
    status = "passed" if not issues else "failed"
    report = {
        "name": "BI Semantic Model Specification Validation",
        "status": status,
        "scope": "design_specification_only",
        "actual_power_bi_model_validated": False,
        "generated_at": datetime.now().astimezone().isoformat(),
        "project_path": ".",
        "summary": {**summary, "issue_count": len(issues)},
        "issues": issues,
    }
    (output_path / "model-spec-validation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# BI Semantic Model Specification Validation",
        "",
        f"- Status: **{status}**",
        "- Scope: design specification only",
        "- Actual Power BI model validated: **No**",
        f"- Issues: {len(issues)}",
        "",
        "| Code | Scope | Message |",
        "|---|---|---|",
    ]
    if issues:
        for item in issues:
            lines.append(f"| {item['code']} | {item['scope']} | {item['message'].replace('|', '\\|')} |")
    else:
        lines.append("| none | - | Model design checks passed. |")
    (output_path / "model-spec-validation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(project_path: Path) -> int:
    model_spec, model_issues = read_json(
        project_path / "model" / "model-spec.json", "model_spec_not_found"
    )
    metrics_contract, metric_issues = read_json(
        project_path / "config" / "metrics.json", "metrics_contract_not_found"
    )
    issues = model_issues + metric_issues
    summary: dict[str, int] = {}
    if model_spec is not None and metrics_contract is not None:
        validation_issues, summary = validate_model_spec(model_spec, metrics_contract)
        issues.extend(validation_issues)
    write_report(project_path, issues, summary)
    for item in issues:
        print(f"{item['code']}: {item['scope']}: {item['message']}")
    print("model_spec_validation_passed" if not issues else "model_spec_validation_failed")
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
