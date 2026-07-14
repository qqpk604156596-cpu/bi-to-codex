# 报表设计规格

## 1. 决策路径

报表采用“发生了什么 → 为什么 → 应关注谁或哪里”的管理决策链：

1. **Executive Overview**：快速判断整体表现和主要变化。
2. **Product & Trend Analysis**：解释变化由哪些产品和时间段驱动。
3. **Customer & Country Analysis**：定位客户与国家贡献，并验证RLS后的可见范围。

## 2. 共同布局

- 画布：16:9，最低检查窗口1366×768。
- 视觉方向：`Light Executive` 浅色企业风格；机器可读令牌见 [`../report/design-tokens.json`](../report/design-tokens.json)，详细组件规则见 [UI设计系统](ui-design-system.md)。
- Header：左侧页面标题，中间页面导航，右侧数据更新时间和RLS状态说明。
- Global filters：Date、Country；三页位置和交互一致。
- KPI row：4–6张卡片，统一数值格式和比较逻辑。
- 主分析区：一个主视觉加1–3个辅助视觉。
- Footer：UCI来源、public-data practice标识和限制入口。
- 视觉对象：首版优先Power BI原生视觉对象。
- 视觉容器：卡片、筛选器和图表使用白色表面；页面使用浅灰蓝画布；标题和主趋势使用深蓝，强调与风险须同时以文字或图例说明。
- 共享接口：[`../report/ui-contract.json`](../report/ui-contract.json)定义组件、字段、度量、Dropdown、交互和可访问性语义；Web 原型与 PBIR 生成器不得各自维护第二份页面契约。

## 3. 页面规格

### Executive Overview

**业务问题**：整体销售表现如何，变化主要来自哪里？

- KPI：Net Sales、Order Count、Units Sold、Active Customers、Average Order Value、Cancellation Rate。
- 主视觉：Monthly Net Sales与同比/环比趋势。
- 辅助视觉：Top Countries、Top Products、取消金额摘要。
- 筛选：Date、Country。
- 交互：选择国家或月份同步筛选产品和取消摘要；提供到第二、三页的导航。

### Product & Trend Analysis

**业务问题**：哪些产品和时间段推动增长或下降？

- KPI：Net Sales、Units Sold、Cancelled Sales、Sales MoM %、Sales YoY %。首版只使用已经进入指标字典和自动对账的指标，不为填满卡片临时增加未验证的 Product Count。
- 主视觉：按月销售趋势，提供当前期与可比期。
- 辅助视觉：Top/Bottom Products、产品销售与取消矩阵、产品明细表。
- 筛选：Date、Country、StockCode或Description。
- 交互：产品选择同步趋势和明细；不使用利润或成本推断。

### Customer & Country Analysis

**业务问题**：哪些客户和国家贡献最大，当前用户获准查看什么？

- KPI：Net Sales、Order Count、Active Customers、Average Order Value、Cancelled Sales、Cancellation Rate。首版只使用已经进入指标字典和自动对账的指标；Country Count 与 Unknown Customer Sales 留作后续独立指标扩展，不作为本轮视觉整改的隐式模型变更。
- 主视觉：Country排名和时间变化。
- 辅助视觉：Top Customers、客户订单与金额分布、明细表。
- 筛选：Date、Country、CustomerID。
- 交互：动态RLS先限制Country，再应用页面筛选；明细最小化显示CustomerID。

## 4. 导航与状态

- 三页使用同一顶栏导航，当前页具有文本和颜色双重状态。
- 所有筛选器提供清除状态；默认范围和当前范围可见。
- 无数据时显示“当前筛选范围无数据”，不保留误导性的0值趋势。
- RLS页必须显示“模拟权限测试”说明，避免被理解为真实客户权限。
- Tooltip只补充定义和上下文，不承载理解主结论所必需的信息。
- “所有”、多月或缺少可比期间时，`Sales MoM %` 与 `Sales YoY %` 显示 `--`；仅选择一个且存在可比期间的月份时显示百分比。
- Web 原型必须提供加载和空状态；PBIR 以无数据说明和 DAX 空值策略表达相同语义。

## 5. 可访问性

- 正文和背景对比度目标至少4.5:1。
- 红绿不作为唯一好坏编码；同时使用文本或符号标签。
- 非装饰视觉对象包含替代文本。
- Tab顺序遵循标题、筛选、KPI、主视觉、辅助视觉、导航。
- 页面标题、视觉标题和筛选标签使用清楚的英文业务语言。
- 可访问性截图审查不能替代键盘、屏幕阅读器和高对比度实际测试。

## 6. 参考来源登记

| 来源 | 作者/组织 | 访问日期 | 借鉴点 | 不复制项 | 状态 |
|---|---|---|---|---|---|
| [Sales and Returns sample](https://learn.microsoft.com/en-us/power-bi/create-reports/sample-sales-returns) | Microsoft | 2026-07-11 | 页面职责、导航、数据叙事、交互提示 | 品牌、业务内容、自定义视觉资产 | Approved reference |
| [Retail Analysis sample](https://learn.microsoft.com/en-us/power-bi/create-reports/sample-retail-analysis) | Microsoft/obviEnce | 2026-07-11 | 零售KPI层级、地区分析、管理阅读路径 | 原数据、结论、布局坐标 | Approved reference |
| [Dashboard de Vendas](https://community.fabric.microsoft.com/t5/Data-Stories-Gallery/Dashboard-de-Vendas-Receita-Metas-e-Funil-de-Convers%C3%A3o-Design-by/td-p/5194077) | Fabric Community作者 | 2026-07-11 | Figma到Power BI流程、留白和节奏 | 品牌、图形资产、具体页面复制 | Visual inspiration only |
| [Figma Community](https://www.figma.com/community) | 各作品作者 | 2026-07-11 | 发现栅格、间距和组件做法 | 未登记具体作品前不采用资产 | Discovery only |
| [Behance](https://www.behance.net/) | 各作品作者 | 2026-07-11 | 发现案例呈现和视觉语言 | 未登记具体作品前不采用资产 | Discovery only |

当前没有采用具体Figma或Behance作品资产。后续采用时必须新增单独来源记录。

## 7. 设计质量门

- 三页PBIR结构存在且页面名称完全一致；
- 每页所有视觉对象都能追溯到业务问题和指标；
- PBIR校验0 errors、0 warnings；
- 默认状态、国家筛选和至少一个模拟RLS用户均有截图；
- 页面在目标窗口无裁切、空白或重叠；
- 人工审查确认层级、对齐、格式、交互和英文文案；
- 设计参考登记完整，未使用许可不明资产。
- 设计令牌、PBIR生成器和视觉清单的回归测试通过；视觉优化不能替代可访问性、性能或人工视觉验收。
- Playwright 三页导航、Dropdown、清除筛选、图表点击、axe 与截图回归通过；截图差异阈值不超过 1%。
- UI 契约中的每个组件有且只有一个 PBIR 映射，未知度量或孤立组件阻断生成。

## 8. 开源组件边界

本项目采用“成熟组件 + 自定义业务编排”的路线。pbi-tools、Tabular Editor 2、PBI/Fab Inspector 与 Semantic Link Labs 的采用顺序、验证边界和不适用范围见[开源自动化组件采用策略](open-source-automation-adoption.md)。
