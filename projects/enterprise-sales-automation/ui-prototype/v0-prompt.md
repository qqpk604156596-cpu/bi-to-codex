# v0 可选设计提示词

> 仅包含公开数据背景与脱敏设计规格。使用 v0 在线服务属于外部操作，执行前按 Tier 2 单独确认。

Create a production-quality, light enterprise sales intelligence dashboard prototype using Next.js, TypeScript, Tailwind-compatible component structure, shadcn/ui patterns, and Recharts.

Requirements:

- Three tabbed pages: Executive Overview, Product & Trend Analysis, Customer & Country Analysis.
- Dropdown filters for YearMonth, Country, StockCode, and CustomerID where applicable.
- KPI hierarchy, monthly sales trend, ranked horizontal bars, clear-filter action, chart cross-filtering, loading and empty states.
- MoM and YoY show `--` for all periods, multiple periods, or missing comparison periods.
- Use navy, teal, white, light grey, and amber focus accents; minimum text contrast 4.5:1.
- Use only synthetic or public aggregate fixture data. Do not connect to a database and do not request credentials.
- Keep component identifiers compatible with `report/ui-contract.json`; Power BI is the final delivery runtime.
