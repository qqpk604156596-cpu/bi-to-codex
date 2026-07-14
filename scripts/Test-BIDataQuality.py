#!/usr/bin/env python3
"""Validate a BI CSV data contract and test a dataset without external packages."""

from __future__ import annotations

import argparse
import ast
import csv
import json
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


SUPPORTED_TYPES = {"string", "integer", "number", "boolean", "date", "datetime"}
BOOLEAN_VALUES = {"true", "false", "1", "0", "yes", "no"}
ALLOWED_BINARY_OPERATORS = (ast.Add, ast.Sub, ast.Mult, ast.Div)
ALLOWED_UNARY_OPERATORS = (ast.UAdd, ast.USub)


def issue(code: str, scope: str, message: str, row: int | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"code": code, "scope": scope, "message": message}
    if row is not None:
        result["row"] = row
    return result


def parse_formula(expression: str) -> tuple[ast.Expression | None, set[str], str | None]:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        return None, set(), "Formula is not valid arithmetic syntax."

    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.BinOp):
            if not isinstance(node.op, ALLOWED_BINARY_OPERATORS):
                return None, names, "Formula uses an unsupported binary operator."
        elif isinstance(node, ast.UnaryOp):
            if not isinstance(node.op, ALLOWED_UNARY_OPERATORS):
                return None, names, "Formula uses an unsupported unary operator."
        elif isinstance(
            node,
            (
                ast.Expression,
                ast.Load,
                ast.Constant,
                ast.Add,
                ast.Sub,
                ast.Mult,
                ast.Div,
                ast.UAdd,
                ast.USub,
            ),
        ):
            if isinstance(node, ast.Constant) and (
                isinstance(node.value, bool) or not isinstance(node.value, (int, float))
            ):
                return None, names, "Formula constants must be numeric."
        else:
            return None, names, f"Formula contains unsupported syntax: {type(node).__name__}."
    return tree, names, None


def evaluate_formula(node: ast.AST, values: dict[str, Decimal]) -> Decimal:
    if isinstance(node, ast.Expression):
        return evaluate_formula(node.body, values)
    if isinstance(node, ast.Name):
        return values[node.id]
    if isinstance(node, ast.Constant):
        return Decimal(str(node.value))
    if isinstance(node, ast.UnaryOp):
        operand = evaluate_formula(node.operand, values)
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.UAdd):
            return operand
    if isinstance(node, ast.BinOp):
        left = evaluate_formula(node.left, values)
        right = evaluate_formula(node.right, values)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
    raise ValueError(f"Unsupported formula node: {type(node).__name__}")


def read_contract(contract_path: Path) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if not contract_path.is_file():
        return None, [issue("contract_not_found", "contract", "Contract not found: config/data-contract.json")]
    try:
        with contract_path.open("r", encoding="utf-8-sig") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        return None, [issue("invalid_contract_json", "contract", str(exc))]
    if not isinstance(value, dict):
        return None, [issue("invalid_contract_root", "contract", "Contract root must be an object.")]
    return value, []


def validate_contract(contract: dict[str, Any], project_path: Path) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if contract.get("schema_version") != 1:
        issues.append(issue("unsupported_schema_version", "schema_version", "schema_version must equal 1."))

    dataset = contract.get("dataset")
    if not isinstance(dataset, dict):
        return issues + [issue("missing_dataset", "dataset", "dataset must be an object.")]

    for field in ("name", "grain"):
        if not isinstance(dataset.get(field), str) or not dataset[field].strip():
            issues.append(issue("missing_dataset_field", f"dataset.{field}", f"{field} must be a non-empty string."))

    source = dataset.get("source")
    if not isinstance(source, dict):
        issues.append(issue("missing_source", "dataset.source", "source must be an object."))
    else:
        if source.get("type") != "csv":
            issues.append(issue("unsupported_source_type", "dataset.source.type", "Only csv is supported."))
        source_path = source.get("path")
        if not isinstance(source_path, str) or not source_path.strip():
            issues.append(issue("missing_source_path", "dataset.source.path", "CSV path must be a non-empty string."))
        else:
            path_value = Path(source_path)
            if path_value.is_absolute():
                issues.append(issue("absolute_source_path", "dataset.source.path", "CSV path must be project-relative."))
            else:
                resolved = (project_path / path_value).resolve()
                try:
                    resolved.relative_to(project_path.resolve())
                except ValueError:
                    issues.append(issue("source_path_outside_project", "dataset.source.path", "CSV path must stay inside the project."))
        delimiter = source.get("delimiter", ",")
        if not isinstance(delimiter, str) or len(delimiter) != 1:
            issues.append(issue("invalid_delimiter", "dataset.source.delimiter", "delimiter must be one character."))

    columns = contract.get("columns")
    if not isinstance(columns, list) or not columns:
        return issues + [issue("missing_columns", "columns", "columns must be a non-empty array.")]

    column_names: list[str] = []
    for index, column in enumerate(columns):
        scope = f"columns[{index}]"
        if not isinstance(column, dict):
            issues.append(issue("invalid_column", scope, "Column definition must be an object."))
            continue
        name = column.get("name")
        if not isinstance(name, str) or not name.strip():
            issues.append(issue("missing_column_name", scope, "Column name must be a non-empty string."))
            continue
        column_names.append(name)
        data_type = column.get("type")
        if data_type not in SUPPORTED_TYPES:
            issues.append(issue("unsupported_type", f"{scope}.type", f"Unsupported type for column {name}."))
        for flag in ("required", "nullable", "unique"):
            if flag in column and not isinstance(column[flag], bool):
                issues.append(issue("invalid_boolean_option", f"{scope}.{flag}", f"{flag} must be boolean."))
        allowed_values = column.get("allowed_values")
        if allowed_values is not None and not isinstance(allowed_values, list):
            issues.append(issue("invalid_allowed_values", f"{scope}.allowed_values", "allowed_values must be an array."))
        for boundary in ("min", "max"):
            if boundary in column and not isinstance(column[boundary], (int, float)):
                issues.append(issue("invalid_boundary", f"{scope}.{boundary}", f"{boundary} must be numeric."))
            if boundary in column and data_type not in {"integer", "number"}:
                issues.append(issue("boundary_on_non_numeric", f"{scope}.{boundary}", "Numeric boundaries require integer or number type."))
        if "min" in column and "max" in column and column["min"] > column["max"]:
            issues.append(issue("invalid_range", scope, "min cannot exceed max."))

    duplicates = sorted({name for name in column_names if column_names.count(name) > 1})
    for name in duplicates:
        issues.append(issue("duplicate_column_definition", "columns", f"Column defined more than once: {name}"))

    primary_key = dataset.get("primary_key")
    if not isinstance(primary_key, list) or not primary_key or not all(isinstance(value, str) and value for value in primary_key):
        issues.append(issue("invalid_primary_key", "dataset.primary_key", "primary_key must be a non-empty string array."))
    else:
        for key in primary_key:
            if key not in column_names:
                issues.append(issue("unknown_primary_key_column", "dataset.primary_key", f"Primary-key column is not defined: {key}"))

    row_rules = contract.get("row_rules", [])
    if not isinstance(row_rules, list):
        issues.append(issue("invalid_row_rules", "row_rules", "row_rules must be an array."))
    else:
        rule_names: set[str] = set()
        for index, rule in enumerate(row_rules):
            scope = f"row_rules[{index}]"
            if not isinstance(rule, dict):
                issues.append(issue("invalid_row_rule", scope, "Row rule must be an object."))
                continue
            for field in ("name", "type", "target", "expression"):
                if not isinstance(rule.get(field), str) or not rule[field].strip():
                    issues.append(issue("missing_row_rule_field", f"{scope}.{field}", f"{field} must be a non-empty string."))
            name = rule.get("name")
            if isinstance(name, str):
                if name in rule_names:
                    issues.append(issue("duplicate_row_rule", scope, f"Row rule is duplicated: {name}"))
                rule_names.add(name)
            if rule.get("type") != "formula":
                issues.append(issue("unsupported_row_rule_type", f"{scope}.type", "Only formula row rules are supported."))
            target = rule.get("target")
            if isinstance(target, str) and target not in column_names:
                issues.append(issue("unknown_formula_target", f"{scope}.target", f"Formula target is not a defined column: {target}"))
            tolerance = rule.get("tolerance", 0)
            if not isinstance(tolerance, (int, float)) or isinstance(tolerance, bool) or tolerance < 0:
                issues.append(issue("invalid_formula_tolerance", f"{scope}.tolerance", "Formula tolerance must be a non-negative number."))
            expression = rule.get("expression")
            if isinstance(expression, str):
                _, names, formula_error = parse_formula(expression)
                if formula_error:
                    issues.append(issue("unsupported_formula_expression", f"{scope}.expression", formula_error))
                for referenced_name in sorted(names - set(column_names)):
                    issues.append(issue("unknown_formula_column", f"{scope}.expression", f"Formula references an unknown column: {referenced_name}"))

    expectations = contract.get("expectations", {})
    if not isinstance(expectations, dict):
        issues.append(issue("invalid_expectations", "expectations", "expectations must be an object."))
    else:
        for name in ("min_rows", "max_rows"):
            if name in expectations and (not isinstance(expectations[name], int) or expectations[name] < 0):
                issues.append(issue("invalid_row_expectation", f"expectations.{name}", f"{name} must be a non-negative integer."))
        if (
            isinstance(expectations.get("min_rows"), int)
            and isinstance(expectations.get("max_rows"), int)
            and expectations["min_rows"] > expectations["max_rows"]
        ):
            issues.append(issue("invalid_row_range", "expectations", "min_rows cannot exceed max_rows."))

    return issues


def parse_value(raw: str, column: dict[str, Any]) -> tuple[bool, Any]:
    data_type = column["type"]
    try:
        if data_type == "string":
            return True, raw
        if data_type == "integer":
            if raw.strip() != str(int(raw.strip())):
                return False, None
            return True, int(raw.strip())
        if data_type == "number":
            return True, Decimal(raw.strip())
        if data_type == "boolean":
            normalized = raw.strip().lower()
            if normalized not in BOOLEAN_VALUES:
                return False, None
            return True, normalized in {"true", "1", "yes"}
        if data_type == "date":
            return True, datetime.strptime(raw.strip(), column.get("format", "%Y-%m-%d")).date()
        if data_type == "datetime":
            return True, datetime.strptime(raw.strip(), column.get("format", "%Y-%m-%dT%H:%M:%S"))
    except (ValueError, InvalidOperation):
        return False, None
    return False, None


def test_csv(
    contract: dict[str, Any], project_path: Path
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    dataset = contract["dataset"]
    source = dataset["source"]
    data_path = (project_path / source["path"]).resolve()
    summary: dict[str, Any] = {
        "data_path": source["path"],
        "row_count": 0,
        "column_count": 0,
    }
    if not data_path.is_file():
        return [issue("data_file_not_found", "dataset.source.path", f"CSV file not found: {source['path']}")], summary

    encoding = source.get("encoding", "utf-8-sig")
    delimiter = source.get("delimiter", ",")
    try:
        with data_path.open("r", encoding=encoding, newline="") as handle:
            reader = csv.DictReader(handle, delimiter=delimiter)
            headers = reader.fieldnames or []
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        return [issue("csv_read_error", "dataset.source.path", str(exc))], summary

    summary["row_count"] = len(rows)
    summary["column_count"] = len(headers)
    issues: list[dict[str, Any]] = []
    columns = contract["columns"]
    column_by_name = {column["name"]: column for column in columns}

    for column in columns:
        if column.get("required", False) and column["name"] not in headers:
            issues.append(issue("missing_required_column", column["name"], f"Required column is missing: {column['name']}"))

    expectations = contract.get("expectations", {})
    minimum_rows = expectations.get("min_rows")
    maximum_rows = expectations.get("max_rows")
    if minimum_rows is not None and len(rows) < minimum_rows:
        issues.append(issue("below_minimum_rows", "expectations.min_rows", "Dataset has fewer rows than required."))
    if maximum_rows is not None and len(rows) > maximum_rows:
        issues.append(issue("above_maximum_rows", "expectations.max_rows", "Dataset has more rows than allowed."))

    unique_values: dict[str, set[str]] = {
        column["name"]: set() for column in columns if column.get("unique", False)
    }
    primary_key_columns = dataset["primary_key"]
    primary_keys: set[tuple[str, ...]] = set()

    for row_number, row in enumerate(rows, start=2):
        primary_key = tuple((row.get(name) or "").strip() for name in primary_key_columns)
        if all(primary_key):
            if primary_key in primary_keys:
                issues.append(issue("duplicate_primary_key", ",".join(primary_key_columns), "Primary key is duplicated.", row_number))
            primary_keys.add(primary_key)

        parsed_values: dict[str, Any] = {}
        invalid_columns: set[str] = set()
        for name, column in column_by_name.items():
            if name not in headers:
                invalid_columns.add(name)
                continue
            raw = row.get(name) or ""
            if not raw.strip():
                if not column.get("nullable", True):
                    issues.append(issue("null_not_allowed", name, "Blank value is not allowed.", row_number))
                invalid_columns.add(name)
                continue

            parsed, value = parse_value(raw, column)
            if not parsed:
                issues.append(issue("invalid_type", name, f"Value does not match type {column['type']}.", row_number))
                invalid_columns.add(name)
                continue
            parsed_values[name] = value

            if column.get("allowed_values") is not None and raw not in {str(item) for item in column["allowed_values"]}:
                issues.append(issue("not_allowed", name, "Value is outside allowed_values.", row_number))
            if column["type"] in {"integer", "number"}:
                if "min" in column and value < Decimal(str(column["min"])):
                    issues.append(issue("below_minimum", name, "Value is below the configured minimum.", row_number))
                if "max" in column and value > Decimal(str(column["max"])):
                    issues.append(issue("above_maximum", name, "Value is above the configured maximum.", row_number))
            if column.get("unique", False):
                if raw in unique_values[name]:
                    issues.append(issue("duplicate_unique_value", name, "Unique value is duplicated.", row_number))
                unique_values[name].add(raw)

        for rule in contract.get("row_rules", []):
            tree, referenced_names, formula_error = parse_formula(rule["expression"])
            target = rule["target"]
            required_names = referenced_names | {target}
            if formula_error or tree is None or required_names & invalid_columns:
                continue
            try:
                decimal_values = {
                    name: Decimal(str(parsed_values[name])) for name in referenced_names
                }
                expected = evaluate_formula(tree, decimal_values)
                actual = Decimal(str(parsed_values[target]))
                tolerance = Decimal(str(rule.get("tolerance", 0)))
                if abs(actual - expected) > tolerance:
                    issues.append(
                        issue(
                            "formula_mismatch",
                            rule["name"],
                            "Target value does not match the configured formula within tolerance.",
                            row_number,
                        )
                    )
            except (ArithmeticError, InvalidOperation, KeyError, ValueError):
                issues.append(
                    issue(
                        "formula_evaluation_error",
                        rule["name"],
                        "Formula could not be evaluated for this row.",
                        row_number,
                    )
                )

    return issues, summary


def write_report(
    project_path: Path,
    filename: str,
    title: str,
    issues: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    output_path = project_path / "evidence" / "data-quality"
    output_path.mkdir(parents=True, exist_ok=True)
    status = "passed" if not issues else "failed"
    report = {
        "name": title,
        "status": status,
        "generated_at": datetime.now().astimezone().isoformat(),
        "project_path": ".",
        "summary": {**summary, "issue_count": len(issues)},
        "issues": issues,
    }
    (output_path / f"{filename}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        f"# {title}",
        "",
        f"- Status: **{status}**",
        f"- Issues: {len(issues)}",
    ]
    for key, value in summary.items():
        lines.append(f"- {key.replace('_', ' ').title()}: {value}")
    lines.extend(["", "| Code | Scope | Row | Message |", "|---|---|---:|---|"])
    if issues:
        for item in issues:
            message = str(item["message"]).replace("|", "\\|")
            lines.append(
                f"| {item['code']} | {item['scope']} | {item.get('row', '')} | {message} |"
            )
    else:
        lines.append("| none | - |  | All configured checks passed. |")
    (output_path / f"{filename}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(mode: str, project_path: Path) -> int:
    project_path = project_path.resolve()
    contract_path = project_path / "config" / "data-contract.json"
    contract, read_issues = read_contract(contract_path)
    contract_issues = read_issues
    if contract is not None:
        contract_issues.extend(validate_contract(contract, project_path))

    if mode == "validate-contract":
        write_report(
            project_path,
            "contract-validation",
            "BI Data Contract Validation",
            contract_issues,
            {"contract_path": "config/data-contract.json"},
        )
        for item in contract_issues:
            print(f"{item['code']}: {item['scope']}: {item['message']}")
        print("contract_validation_passed" if not contract_issues else "contract_validation_failed")
        return 0 if not contract_issues else 2

    if contract is None or contract_issues:
        write_report(
            project_path,
            "data-quality",
            "BI Data Quality",
            contract_issues,
            {"contract_path": "config/data-contract.json", "row_count": 0, "column_count": 0},
        )
        for item in contract_issues:
            print(f"{item['code']}: {item['scope']}: {item['message']}")
        print("data_quality_failed")
        return 2

    data_issues, summary = test_csv(contract, project_path)
    write_report(project_path, "data-quality", "BI Data Quality", data_issues, summary)
    for item in data_issues:
        row = f" row={item['row']}" if "row" in item else ""
        print(f"{item['code']}: {item['scope']}:{row} {item['message']}")
    print("data_quality_passed" if not data_issues else "data_quality_failed")
    return 0 if not data_issues else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=("validate-contract", "test-data"))
    parser.add_argument("--project-path", required=True, type=Path)
    arguments = parser.parse_args()
    if not arguments.project_path.is_dir():
        print(f"project_not_found: {arguments.project_path}")
        return 3
    try:
        return run(arguments.mode, arguments.project_path)
    except Exception as exc:  # Defensive CLI boundary; details remain visible.
        print(f"unexpected_error: {type(exc).__name__}: {exc}")
        return 3


if __name__ == "__main__":
    sys.exit(main())
