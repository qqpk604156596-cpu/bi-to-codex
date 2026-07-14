#!/usr/bin/env python3
"""Generate portable TMDL assets into the Desktop-created Enterprise Sales PBIP shell."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEMANTIC_MODEL_NAME = "EnterpriseSalesAutomation.SemanticModel"


def build_asset_map() -> dict[str, str]:
    """Return the generated TMDL files, relative to a semantic-model definition folder."""
    return {
        "model.tmdl": """model Model
\tculture: zh-CN
\tdefaultPowerBIDataSourceVersion: powerBI_V3
\tsourceQueryCulture: zh-CN

annotation __PBI_TimeIntelligenceEnabled = 1

annotation PBI_ProTooling = [\"DevMode\"]

ref table FactSalesLine
ref table DimDate
ref table DimProduct
ref table DimCustomer
ref table DimCountry
ref table SecurityUserCountry
ref role CountryManager
ref cultureInfo zh-CN
""",
        "expressions.tmdl": """/// Local MySQL host. Configure credentials only through Power BI Desktop; no credentials are stored in this project.
expression MySqlServer = \"127.0.0.1\" meta [IsParameterQuery=true, Type=\"Text\", IsParameterQueryRequired=true]

/// Local MySQL database containing vw_fact_sales_line.
expression MySqlDatabase = \"enterprise_sales\" meta [IsParameterQuery=true, Type=\"Text\", IsParameterQueryRequired=true]
""",
        "relationships.tmdl": """relationship FactSalesLine_InvoiceDateDate_DimDate
\tfromColumn: FactSalesLine.InvoiceDateDate
\ttoColumn: DimDate.Date

relationship FactSalesLine_StockCode_DimProduct
\tfromColumn: FactSalesLine.StockCode
\ttoColumn: DimProduct.StockCode

relationship FactSalesLine_CustomerKey_DimCustomer
\tfromColumn: FactSalesLine.CustomerKey
\ttoColumn: DimCustomer.CustomerKey

relationship FactSalesLine_Country_DimCountry
\tfromColumn: FactSalesLine.Country
\ttoColumn: DimCountry.Country

relationship SecurityUserCountry_Country_DimCountry
\tcrossFilteringBehavior: bothDirections
\tsecurityFilteringBehavior: bothDirections
\tfromColumn: SecurityUserCountry.Country
\ttoColumn: DimCountry.Country
""",
        "tables/FactSalesLine.tmdl": """table FactSalesLine
\tcolumn SourceRowId
\t\tdataType: string
\t\tisHidden: true
\t\tsourceColumn: SourceRowId

\tcolumn InvoiceNo
\t\tdataType: string
\t\tsourceColumn: InvoiceNo

\tcolumn StockCode
\t\tdataType: string
\t\tisHidden: true
\t\tsourceColumn: StockCode

\tcolumn Description
\t\tdataType: string
\t\tsourceColumn: Description

\tcolumn Quantity
\t\tdataType: int64
\t\tsourceColumn: Quantity

\tcolumn InvoiceDate
\t\tdataType: dateTime
\t\tsourceColumn: InvoiceDate

\tcolumn InvoiceDateDate
\t\tdataType: dateTime
\t\tisHidden: true
\t\tsourceColumn: InvoiceDateDate

\tcolumn UnitPrice
\t\tdataType: decimal
\t\tsourceColumn: UnitPrice

\tcolumn CustomerID
\t\tdataType: string
\t\tisHidden: true
\t\tsourceColumn: CustomerID

\tcolumn CustomerKey
\t\tdataType: string
\t\tisHidden: true
\t\tsourceColumn: CustomerKey

\tcolumn Country
\t\tdataType: string
\t\tisHidden: true
\t\tsourceColumn: Country

\tcolumn IsCancellation
\t\tdataType: boolean
\t\tisHidden: true
\t\tsourceColumn: IsCancellation

\tcolumn UnknownCustomer
\t\tdataType: boolean
\t\tisHidden: true
\t\tsourceColumn: UnknownCustomer

\tcolumn ZeroPrice
\t\tdataType: boolean
\t\tisHidden: true
\t\tsourceColumn: ZeroPrice

\tcolumn LineAmount
\t\tdataType: decimal
\t\tsourceColumn: LineAmount

\tmeasure 'Gross Sales' = ```
\t\tCALCULATE ( SUM ( FactSalesLine[LineAmount] ), FactSalesLine[IsCancellation] = FALSE (), FactSalesLine[Quantity] > 0, FactSalesLine[UnitPrice] > 0 )
\t\t```
\t\tformatString: \"£#,0.00\"

\tmeasure 'Cancelled Sales' = ```
\t\tCALCULATE ( SUMX ( FactSalesLine, ABS ( FactSalesLine[LineAmount] ) ), FactSalesLine[IsCancellation] = TRUE () )
\t\t```
\t\tformatString: \"£#,0.00\"

\tmeasure 'Net Sales' = SUM ( FactSalesLine[LineAmount] )
\t\tformatString: \"£#,0.00\"

\tmeasure 'Order Count' = ```
\t\tCALCULATE ( DISTINCTCOUNT ( FactSalesLine[InvoiceNo] ), FactSalesLine[IsCancellation] = FALSE (), FactSalesLine[Quantity] > 0, FactSalesLine[UnitPrice] > 0 )
\t\t```
\t\tformatString: \"0\"

\tmeasure 'Units Sold' = ```
\t\tCALCULATE ( SUM ( FactSalesLine[Quantity] ), FactSalesLine[IsCancellation] = FALSE (), FactSalesLine[Quantity] > 0, FactSalesLine[UnitPrice] > 0 )
\t\t```
\t\tformatString: \"0\"

\tmeasure 'Active Customers' = ```
\t\tCALCULATE ( DISTINCTCOUNT ( FactSalesLine[CustomerID] ), FactSalesLine[IsCancellation] = FALSE (), FactSalesLine[Quantity] > 0, FactSalesLine[UnitPrice] > 0, NOT ISBLANK ( FactSalesLine[CustomerID] ) )
\t\t```
\t\tformatString: \"0\"

\tmeasure 'Average Order Value' = DIVIDE ( [Gross Sales], [Order Count] )
\t\tformatString: \"£#,0.00\"

\tmeasure 'Cancelled Invoice Count' = CALCULATE ( DISTINCTCOUNT ( FactSalesLine[InvoiceNo] ), FactSalesLine[IsCancellation] = TRUE () )
\t\tisHidden: true

\tmeasure 'All Invoice Count' = DISTINCTCOUNT ( FactSalesLine[InvoiceNo] )
\t\tisHidden: true

\tmeasure 'Cancellation Rate' = DIVIDE ( [Cancelled Invoice Count], [All Invoice Count] )
\t\tformatString: \"0.00%\"

\tmeasure 'Sales MoM %' = ```
\t\tVAR IsSingleMonth = HASONEVALUE ( DimDate[YearMonth] )
\t\tVAR PreviousSales = CALCULATE ( [Net Sales], DATEADD ( DimDate[Date], -1, MONTH ) )
\t\tRETURN IF ( NOT IsSingleMonth || ISBLANK ( PreviousSales ) || PreviousSales = 0, BLANK (), DIVIDE ( [Net Sales] - PreviousSales, PreviousSales ) )
\t\t```
\t\tformatString: \"0.00%\"

\tmeasure 'Sales YoY %' = ```
\t\tVAR IsSingleMonth = HASONEVALUE ( DimDate[YearMonth] )
\t\tVAR PriorYearSales = CALCULATE ( [Net Sales], DATEADD ( DimDate[Date], -1, YEAR ) )
\t\tRETURN IF ( NOT IsSingleMonth || ISBLANK ( PriorYearSales ) || PriorYearSales = 0, BLANK (), DIVIDE ( [Net Sales] - PriorYearSales, PriorYearSales ) )
\t\t```
\t\tformatString: \"0.00%\"

\tpartition FactSalesLine = m
\t\tmode: import
\t\tsource =
\t\t\t\tlet
\t\t\t\t\tSource = MySQL.Database(MySqlServer, MySqlDatabase, [ReturnSingleDatabase = true]),
\t\t\t\t\tNavigation = Source{[Schema=MySqlDatabase, Item=\"vw_fact_sales_line\"]}[Data],
\t\t\t\t\tTyped = Table.TransformColumnTypes(Navigation, {{\"SourceRowId\", type text}, {\"InvoiceNo\", type text}, {\"StockCode\", type text}, {\"Description\", type text}, {\"Quantity\", Int64.Type}, {\"InvoiceDate\", type datetime}, {\"UnitPrice\", type number}, {\"CustomerID\", type text}, {\"Country\", type text}, {\"IsCancellation\", type logical}, {\"UnknownCustomer\", type logical}, {\"ZeroPrice\", type logical}, {\"LineAmount\", type number}}),
\t\t\t\t\tWithDate = Table.AddColumn(Typed, \"InvoiceDateDate\", each DateTime.Date([InvoiceDate]), type date),
\t\t\t\t\tWithCustomerKey = Table.AddColumn(WithDate, \"CustomerKey\", each if [CustomerID] = null then \"UNKNOWN\" else [CustomerID], type text)
\t\t\t\tin
\t\t\t\t\tWithCustomerKey
""",
        "tables/DimDate.tmdl": """table DimDate
\tcolumn Date
\t\tdataType: dateTime
\t\tsourceColumn: Date

\tcolumn Year
\t\tdataType: int64
\t\tsourceColumn: Year

\tcolumn MonthNumber
\t\tdataType: int64
\t\tsourceColumn: MonthNumber

\tcolumn MonthName
\t\tdataType: string
\t\tsortByColumn: MonthNumber
\t\tsourceColumn: MonthName

\tcolumn YearMonth
\t\tdataType: string
\t\tsourceColumn: YearMonth

\tpartition DimDate = m
\t\tmode: import
\t\tsource =
\t\t\t\tlet
\t\t\t\t\tSource = MySQL.Database(MySqlServer, MySqlDatabase, [ReturnSingleDatabase = true]),
\t\t\t\t\tNavigation = Source{[Schema=MySqlDatabase, Item=\"vw_dim_date\"]}[Data],
\t\t\t\t\tTyped = Table.TransformColumnTypes(Navigation, {{\"Date\", type date}}),
\t\t\t\t\tWithYear = Table.AddColumn(Typed, \"Year\", each Date.Year([Date]), Int64.Type),
\t\t\t\t\tWithMonthNumber = Table.AddColumn(WithYear, \"MonthNumber\", each Date.Month([Date]), Int64.Type),
\t\t\t\t\tWithMonthName = Table.AddColumn(WithMonthNumber, \"MonthName\", each Date.MonthName([Date]), type text),
\t\t\t\t\tWithYearMonth = Table.AddColumn(WithMonthName, \"YearMonth\", each Date.ToText([Date], \"yyyy-MM\"), type text)
\t\t\t\tin
\t\t\t\t\tWithYearMonth
""",
        "tables/DimProduct.tmdl": """table DimProduct
\tcolumn StockCode
\t\tdataType: string
\t\tsourceColumn: StockCode

\tcolumn Description
\t\tdataType: string
\t\tsourceColumn: Description

\tpartition DimProduct = m
\t\tmode: import
\t\tsource =
\t\t\t\tlet
\t\t\t\t\tSource = MySQL.Database(MySqlServer, MySqlDatabase, [ReturnSingleDatabase = true]),
\t\t\t\t\tNavigation = Source{[Schema=MySqlDatabase, Item=\"vw_dim_product\"]}[Data]
\t\t\t\tin
\t\t\t\t\tNavigation
""",
        "tables/DimCustomer.tmdl": """table DimCustomer
\tcolumn CustomerKey
\t\tdataType: string
\t\tsourceColumn: CustomerKey

\tcolumn CustomerID
\t\tdataType: string
\t\tisHidden: true
\t\tsourceColumn: CustomerID

\tcolumn IsUnknownCustomer
\t\tdataType: boolean
\t\tsourceColumn: IsUnknownCustomer

\tpartition DimCustomer = m
\t\tmode: import
\t\tsource =
\t\t\t\tlet
\t\t\t\t\tSource = MySQL.Database(MySqlServer, MySqlDatabase, [ReturnSingleDatabase = true]),
\t\t\t\t\tNavigation = Source{[Schema=MySqlDatabase, Item=\"vw_dim_customer\"]}[Data],
\t\t\t\t\tTyped = Table.TransformColumnTypes(Navigation, {{\"CustomerKey\", type text}, {\"CustomerID\", type text}, {\"IsUnknownCustomer\", type logical}})
\t\t\t\tin
\t\t\t\t\tTyped
""",
        "tables/DimCountry.tmdl": """table DimCountry
\tcolumn Country
\t\tdataType: string
\t\tsourceColumn: Country

\tpartition DimCountry = m
\t\tmode: import
\t\tsource =
\t\t\t\tlet
\t\t\t\t\tSource = MySQL.Database(MySqlServer, MySqlDatabase, [ReturnSingleDatabase = true]),
\t\t\t\t\tNavigation = Source{[Schema=MySqlDatabase, Item=\"vw_dim_country\"]}[Data]
\t\t\t\tin
\t\t\t\t\tNavigation
""",
        "tables/SecurityUserCountry.tmdl": """table SecurityUserCountry
\tcolumn UserPrincipalName
\t\tdataType: string
\t\tsourceColumn: UserPrincipalName

\tcolumn Country
\t\tdataType: string
\t\tsourceColumn: Country

\tcolumn IsActive
\t\tdataType: boolean
\t\tsourceColumn: IsActive

\tpartition SecurityUserCountry = m
\t\tmode: import
\t\tsource =
\t\t\t\t#table(type table [UserPrincipalName = text, Country = text, IsActive = logical], {{\"manager.uk@example.invalid\", \"United Kingdom\", true}, {\"manager.fr@example.invalid\", \"France\", true}})
""",
        "roles/CountryManager.tmdl": """/// Simulated RLS only. It does not represent a real customer identity or authorization system.
role CountryManager
\tmodelPermission: read

\ttablePermission SecurityUserCountry = [IsActive] = TRUE() && [UserPrincipalName] = USERPRINCIPALNAME()
""",
    }


def apply_assets(semantic_model_folder: Path, *, replace_generated: bool = False) -> list[Path]:
    """Write generated assets only into a Desktop-created, currently empty semantic-model shell."""
    definition_folder = semantic_model_folder / "definition"
    if not (semantic_model_folder / "definition.pbism").is_file() or not definition_folder.is_dir():
        raise FileNotFoundError("A Desktop-created semantic-model folder with definition.pbism is required.")
    tables_folder = definition_folder / "tables"
    existing_tables = list(tables_folder.glob("*.tmdl")) if tables_folder.is_dir() else []
    if existing_tables and not replace_generated:
        raise FileExistsError("Refusing to overwrite an existing semantic model. Use --replace-generated only for this generated model.")

    written: list[Path] = []
    for relative_path, content in build_asset_map().items():
        output_path = definition_folder / relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content.rstrip() + "\n", encoding="utf-8")
        written.append(output_path)
    return written


def ensure_report_schema(project_path: Path) -> list[Path]:
    """Add the standard schema URL to Desktop-created PBIR definition files when absent."""
    schema_url = "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json"
    updated: list[Path] = []
    for pbir_path in sorted(project_path.glob("*.Report/definition.pbir")):
        definition = json.loads(pbir_path.read_text(encoding="utf-8-sig"))
        if definition.get("$schema") != schema_url:
            definition = {"$schema": schema_url, **definition}
            pbir_path.write_text(json.dumps(definition, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            updated.append(pbir_path)
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--semantic-model-path", type=Path, default=PROJECT_ROOT / SEMANTIC_MODEL_NAME)
    parser.add_argument("--replace-generated", action="store_true")
    arguments = parser.parse_args()
    ensure_report_schema(PROJECT_ROOT)
    written = apply_assets(arguments.semantic_model_path.resolve(), replace_generated=arguments.replace_generated)
    print(f"pbip_model_assets_written={len(written)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
