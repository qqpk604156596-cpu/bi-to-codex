"""Generate the three-page PBIR report from the shared UI contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = PROJECT_ROOT / "report" / "visual-manifest.json"
UI_CONTRACT_PATH = PROJECT_ROOT / "report" / "ui-contract.json"
DESIGN_TOKENS_PATH = PROJECT_ROOT / "report" / "design-tokens.json"
REPORT_DEFINITION_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json"
PAGE_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
PAGES_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json"
VISUAL_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.9.0/schema.json"
MEASURE_NAMES = {
    "gross_sales": "Gross Sales",
    "cancelled_sales": "Cancelled Sales",
    "net_sales": "Net Sales",
    "order_count": "Order Count",
    "units_sold": "Units Sold",
    "active_customers": "Active Customers",
    "average_order_value": "Average Order Value",
    "cancellation_rate": "Cancellation Rate",
    "sales_mom_pct": "Sales MoM %",
    "sales_yoy_pct": "Sales YoY %",
}


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_ui_contract(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def ui_contract_from_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    pages: list[dict[str, Any]] = []
    for page in manifest["pages"]:
        filters = []
        components = []
        for visual in page["visuals"]:
            if visual["visual_type"] == "slicer":
                filters.append(
                    {
                        "id": visual["id"],
                        "label": visual["field"][1],
                        "field": visual["field"],
                        "mode": "Dropdown",
                    }
                )
            components.append(
                {
                    "id": visual["id"],
                    "pbir_visual_id": visual["id"],
                    "role": visual["visual_type"],
                    "pbir": {key: value for key, value in visual.items() if key != "id"},
                }
            )
        pages.append(
            {
                "id": page["id"],
                "name": page["name"],
                "primary_component_id": page["primary_visual_id"],
                "filters": filters,
                "components": components,
            }
        )
    return {
        "schema_version": 1,
        "design_system": "Light Executive",
        "surface": {"canonical_width": 1280, "canonical_height": 720},
        "comparison_policy": {
            "single_period_only": True,
            "multi_period_value": "--",
            "no_comparable_period_value": "--",
        },
        "interactions": {
            "navigation": "page-tabs",
            "filter_mode": "dropdown",
            "chart_selection": "cross-filter-page",
            "clear_filters": True,
        },
        "accessibility": {
            "minimum_contrast_ratio": 4.5,
            "color_is_not_only_status_signal": True,
            "alt_text_required": True,
        },
        "pages": pages,
    }


def manifest_from_ui_contract(contract: dict[str, Any]) -> dict[str, Any]:
    pages = []
    for page in contract["pages"]:
        visuals = []
        for component in page["components"]:
            visual = {"id": component["pbir_visual_id"], **component["pbir"]}
            visuals.append(visual)
        pages.append(
            {
                "id": page["id"],
                "name": page["name"],
                "primary_visual_id": page["primary_component_id"],
                "visuals": visuals,
            }
        )
    return {
        "version": 1,
        "global_slicers": ["DimDate.YearMonth", "DimCountry.Country"],
        "pages": pages,
    }


def load_design_tokens(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ensure_report_definition_schema(report_directory: Path) -> None:
    """Restore the enhanced PBIR schema that Desktop may omit when rewriting the shell."""
    pbir_path = report_directory / "definition.pbir"
    definition = json.loads(pbir_path.read_text(encoding="utf-8-sig"))
    if definition.get("$schema") != REPORT_DEFINITION_SCHEMA:
        write_json(pbir_path, {"$schema": REPORT_DEFINITION_SCHEMA, **definition})


def visual_name(page_id: str, visual_id: str) -> str:
    return hashlib.sha256(f"{page_id}:{visual_id}".encode("utf-8")).hexdigest()[:20]


def literal(value: str) -> dict[str, Any]:
    return {"expr": {"Literal": {"Value": value}}}


def color_literal(color: str) -> dict[str, Any]:
    return literal(f"'{color}'")


def data_value_selector() -> dict[str, Any]:
    """Target per-value formatting for visuals whose format objects are data scoped."""
    return {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}


def measure_projection(metric_id: str) -> dict[str, Any]:
    measure_name = MEASURE_NAMES[metric_id]
    return {
        "field": {
            "Measure": {
                "Expression": {"SourceRef": {"Entity": "FactSalesLine"}},
                "Property": measure_name,
            }
        },
        "queryRef": f"FactSalesLine.{measure_name}",
        "nativeQueryRef": measure_name,
    }


def column_projection(field: list[str]) -> dict[str, Any]:
    table, column = field
    return {
        "field": {
            "Column": {
                "Expression": {"SourceRef": {"Entity": table}},
                "Property": column,
            }
        },
        "queryRef": f"{table}.{column}",
        "nativeQueryRef": column,
        "active": True,
    }


def visual_title(title: str, tokens: dict[str, Any]) -> dict[str, Any]:
    colors = tokens["colors"]
    typography = tokens["typography"]
    return {
        "title": [
            {
                "properties": {
                    "show": literal("true"),
                    "text": literal(f"'{title}'"),
                    "bold": literal("true"),
                    "fontColor": color_literal(colors["primary"]),
                    "fontSize": literal(f"{typography['section_title_size']}D"),
                    "fontFamily": literal(f"'{typography['font_family']}'"),
                }
            }
        ]
    }


def visual_background(color: str) -> dict[str, Any]:
    return {
        "background": [
            {
                "properties": {
                    "show": literal("true"),
                    "color": color_literal(color),
                    "transparency": literal("0L"),
                }
            }
        ]
    }


def build_visual(page_id: str, visual: dict[str, Any], z_order: int, tokens: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    x, y, width, height = visual["position"]
    colors = tokens["colors"]
    typography = tokens["typography"]
    generated_name = visual_name(page_id, visual["id"])
    result: dict[str, Any] = {
        "$schema": VISUAL_SCHEMA,
        "name": generated_name,
        "position": {"x": x, "y": y, "z": z_order, "height": height, "width": width, "tabOrder": z_order},
        "visual": {"visualType": visual["visual_type"]},
    }
    visual_type = visual["visual_type"]
    if visual_type == "textbox":
        result["visual"]["objects"] = {
            "general": [
                {
                    "properties": {
                        "paragraphs": [
                            {
                                "textRuns": [
                                    {
                                        "value": visual["text"],
                                        "textStyle": {
                                            "fontFamily": f"{typography['font_family']} Semibold",
                                            "fontSize": f"{typography['page_title_size']}px" if "title" in visual["id"] else "12px",
                                            "color": colors["text_primary"],
                                        },
                                    }
                                ],
                                "horizontalTextAlignment": "left",
                            }
                        ]
                    }
                }
            ]
        }
    elif visual_type == "slicer":
        result["visual"]["query"] = {"queryState": {"Values": {"projections": [column_projection(visual["field"])]}}}
        result["visual"]["objects"] = {"data": [{"properties": {"mode": literal("'Dropdown'")}}]}
        result["visual"]["visualContainerObjects"] = visual_background(colors["surface"])
    elif visual_type == "cardVisual":
        result["visual"]["query"] = {"queryState": {"Data": {"projections": [measure_projection(visual["metric_id"])]}}}
        result["visual"]["objects"] = {
            "value": [
                {
                    "properties": {"displayUnits": literal("1D")},
                    "selector": data_value_selector(),
                }
            ],
            "label": [
                {
                    "properties": {"show": literal("false")},
                    "selector": data_value_selector(),
                }
            ],
        }
        result["visual"]["visualContainerObjects"] = visual_title(MEASURE_NAMES[visual["metric_id"]], tokens)
        result["visual"]["visualContainerObjects"].update(visual_background(colors["surface"]))
    elif visual_type in {"lineChart", "barChart"}:
        measure = measure_projection(visual["metric_id"])
        result["visual"]["query"] = {
            "queryState": {
                "Category": {"projections": [column_projection(visual["category"])]},
                "Y": {"projections": [measure]},
            }
        }
        if visual_type == "barChart":
            result["visual"]["query"]["sortDefinition"] = {
                "sort": [{"field": measure["field"], "direction": "Descending"}],
                "isDefaultSort": True,
            }
        result["visual"]["objects"] = {
            "valueAxis": [{"properties": {"labelDisplayUnits": literal("1D")}}]
        }
        result["visual"]["visualContainerObjects"] = visual_title(visual["title"], tokens)
        result["visual"]["visualContainerObjects"].update(visual_background(colors["surface"]))
    else:
        raise ValueError(f"Unsupported visual type: {visual_type}")
    return generated_name, result


def write_report_pages(
    definition_directory: Path,
    manifest: dict[str, Any],
    tokens: dict[str, Any] | None = None,
) -> None:
    tokens = tokens or load_design_tokens(DESIGN_TOKENS_PATH)
    pages_directory = definition_directory / "pages"
    pages_directory.mkdir(parents=True, exist_ok=True)
    managed_page_ids = {page["id"] for page in manifest["pages"]}
    for page_directory in pages_directory.iterdir():
        if page_directory.is_dir() and page_directory.name not in managed_page_ids:
            if not list(page_directory.glob("visuals/*/visual.json")):
                shutil.rmtree(page_directory)
    page_order: list[str] = []
    for page in manifest["pages"]:
        page_id = page["id"]
        page_order.append(page_id)
        page_directory = pages_directory / page_id
        if page_directory.exists():
            shutil.rmtree(page_directory)
        visuals_directory = page_directory / "visuals"
        visuals_directory.mkdir(parents=True)
        write_json(
            page_directory / "page.json",
            {
                "$schema": PAGE_SCHEMA,
                "name": page_id,
                "displayName": page["name"],
                "displayOption": "FitToPage",
                "height": 720,
                "width": 1280,
                "objects": {
                    "background": [
                        {
                            "properties": {
                                "color": color_literal(tokens["colors"]["canvas"]),
                                "transparency": literal("0L"),
                            }
                        }
                    ]
                },
            },
        )
        for z_order, visual in enumerate(page["visuals"], start=1):
            generated_name, visual_json = build_visual(page_id, visual, z_order, tokens)
            write_json(visuals_directory / generated_name / "visual.json", visual_json)
    write_json(
        pages_directory / "pages.json",
        {"$schema": PAGES_SCHEMA, "pageOrder": page_order, "activePageName": page_order[0]},
    )


def validate_generated_definition(definition_directory: Path, manifest: dict[str, Any]) -> None:
    """Block replacement unless every managed PBIR page and visual is valid JSON."""
    pages_path = definition_directory / "pages" / "pages.json"
    pages = json.loads(pages_path.read_text(encoding="utf-8"))
    expected_page_order = [page["id"] for page in manifest["pages"]]
    if pages.get("pageOrder") != expected_page_order:
        raise ValueError("generated_page_order_mismatch")
    for page in manifest["pages"]:
        page_directory = definition_directory / "pages" / page["id"]
        page_json = json.loads((page_directory / "page.json").read_text(encoding="utf-8"))
        if page_json.get("displayName") != page["name"]:
            raise ValueError(f"generated_page_name_mismatch:{page['id']}")
        visual_paths = sorted((page_directory / "visuals").glob("*/visual.json"))
        if len(visual_paths) != len(page["visuals"]):
            raise ValueError(f"generated_visual_count_mismatch:{page['id']}")
        for visual_path in visual_paths:
            visual = json.loads(visual_path.read_text(encoding="utf-8"))
            if not visual.get("name") or not visual.get("visual", {}).get("visualType"):
                raise ValueError(f"generated_visual_invalid:{visual_path.parent.name}")


def replace_report_definition_atomically(
    report_directory: Path,
    manifest: dict[str, Any],
    tokens: dict[str, Any],
) -> None:
    """Generate and validate in a sibling directory before replacing the healthy PBIR."""
    definition_directory = report_directory / "definition"
    if not definition_directory.is_dir():
        raise FileNotFoundError("desktop_report_shell_not_found")
    run_suffix = uuid4().hex
    staging_directory = report_directory / f".definition.staging-{run_suffix}"
    backup_directory = report_directory / f".definition.backup-{run_suffix}"
    shutil.copytree(definition_directory, staging_directory)
    try:
        write_report_pages(staging_directory, manifest, tokens)
        validate_generated_definition(staging_directory, manifest)
        definition_directory.replace(backup_directory)
        try:
            staging_directory.replace(definition_directory)
        except Exception:
            backup_directory.replace(definition_directory)
            raise
        shutil.rmtree(backup_directory)
    finally:
        if staging_directory.exists():
            shutil.rmtree(staging_directory)
        if backup_directory.exists():
            if not definition_directory.exists():
                backup_directory.replace(definition_directory)
            else:
                shutil.rmtree(backup_directory)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-path", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--replace-generated", action="store_true", help="Required acknowledgement before writing the three generated pages.")
    parser.add_argument("--bootstrap-ui-contract", action="store_true", help="Create the first shared UI contract from the reviewed manifest.")
    arguments = parser.parse_args()
    if arguments.bootstrap_ui_contract:
        manifest = load_manifest(arguments.project_path / "report" / "visual-manifest.json")
        write_json(arguments.project_path / "report" / "ui-contract.json", ui_contract_from_manifest(manifest))
        print("ui_contract_bootstrapped=1")
        return
    if not arguments.replace_generated:
        parser.error("--replace-generated is required")
    contract = load_ui_contract(arguments.project_path / "report" / "ui-contract.json")
    manifest = manifest_from_ui_contract(contract)
    tokens = load_design_tokens(arguments.project_path / "report" / "design-tokens.json")
    report_directory = arguments.project_path / "EnterpriseSalesAutomation.Report"
    if not (report_directory / "definition").is_dir():
        raise SystemExit("desktop_report_shell_not_found")
    replace_report_definition_atomically(report_directory, manifest, tokens)
    ensure_report_definition_schema(report_directory)
    write_json(arguments.project_path / "report" / "visual-manifest.json", manifest)
    print(f"pbir_pages_written={len(manifest['pages'])}")


if __name__ == "__main__":
    main()
