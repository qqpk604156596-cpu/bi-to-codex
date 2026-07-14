# Desktop 视觉整改复核（已保存实例，非最终人工签字）

- 状态：**自动视觉预检通过；人工验收仍待完成**
- 检查时间：2026-07-14 14:44 +08:00
- 当前实例：Power BI Desktop PID `13448`
- 当前项目：`EnterpriseSalesAutomation.pbip`
- 已保存状态：Desktop Bridge 报告 `hasUnsavedChanges: false`
- 持久化截图：[`../runs/20260714T064441297Z/saved-desktop-screenshots/`](../runs/20260714T064441297Z/saved-desktop-screenshots/)
- 自动验证：[`../runs/20260714T063334594Z/`](../runs/20260714T063334594Z/)
- 边界：本记录不替代真实筛选交互、键盘顺序、屏幕阅读器、Performance Analyzer 或项目所有者最终视觉签字。

## 事实

1. 三页均已渲染实际数据，KPI 卡片没有文字裁切或重叠；卡片采用共享三列网格。
2. `Customer & Country Analysis` 已调整为与前两页一致的标题、切片器、六张 KPI 卡和双图表视觉层级。
3. 当前已保存实例显示英文自动单位和英文未筛选状态，包括 `£19.45M`、`40K`、`11M`、`6K`、`£1.53M` 和 `All`。
4. 内容漂移按当前已批准指标处理：Product 页保留五项已有指标；Customer 页使用 `Net Sales`、`Order Count`、`Active Customers`、`Average Order Value`、`Cancelled Sales` 和 `Cancellation Rate`。规格已同步，不新增尚未进入批准指标体系的 `Product Count`、`Country Count` 或 `Unknown Customer Sales`。
5. 最终自动 DesktopQA 运行 `20260714T063334594Z` 通过：完整刷新 `68,586.53 ms`，低于 `300 s` 门限；全部、国家和月份切片的 DAX 比对均无差异；UK、France 和未映射拒绝场景的本地动态 RLS 均通过。
6. 本轮用户提供的 Desktop 全窗口截图中，`Filters` 为收起状态，`Visualizations` 和 `Data` 为展开状态。持久化画布截图只显示收起的 `Filters` 条；这些窗格属于 Desktop 作者界面状态，不是 PBIR 报表内容契约。
7. Desktop 保存会省略 `definition.pbir` 的可选 `$schema`；自动生成生命周期随后恢复该字段。再生成后 `ValidatePowerBIProject`、`ValidateUIContract`、`ValidateReportQA` 和 14 项相关单元测试全部通过，PID `13448` 仍为 `hasUnsavedChanges: false`。

## 推断

- 旧预审中的卡片裁切、中文自动单位和 Customer 页样式不一致问题，已由当前已保存实例和持久化截图消除。
- Product 页 `Sales MoM %` 与 `Sales YoY %` 在未选择单月时显示空值，与同一运行的 DAX 验证结果一致，不属于视觉生成失败。

## 未完成或未验证

- 尚未完成项目所有者的真实切片器交互、跨视觉传播、键盘 Tab 顺序、屏幕阅读器和最终视觉签字，因此 `quality_gates.report` 应继续保持 `pending`。
- Power BI Service、Fabric、网关、真实多用户共享和真实客户验收仍未验证。
- 本轮未由 Agent 执行最终 PBIX 保存，也未关闭当前已保存的 PBIP 实例。
