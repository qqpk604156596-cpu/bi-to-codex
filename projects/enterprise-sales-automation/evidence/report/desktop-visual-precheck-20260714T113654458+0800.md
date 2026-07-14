# Desktop 视觉预审（Agent 辅助，非人工签字）

- 状态：**Blocked**
- 检查时间：2026-07-14 11:36:54 +08:00
- 截图来源：[`../runs/20260714T030603356Z/desktop-screenshots/`](../runs/20260714T030603356Z/desktop-screenshots/)
- 关联自动证据：同一运行的刷新、指标和 RLS 均为 `passed`
- 边界：本记录不替代项目所有者的真实筛选、键盘、屏幕阅读器、Performance Analyzer 和最终视觉签字。

## 事实

1. 三页均已渲染实际数据，没有空白页；截图中的 Net Sales、Order Count、Units Sold、Active Customers、Average Order Value 与 Cancellation Rate 与同一运行的 DAX 证据一致。
2. 三页 KPI 卡片的底部度量标签均被卡片边界裁切。PBIR 使用新 `cardVisual`，高度为 120；生成器同时启用了外部标题，而卡片内部标签仍保持默认显示。
3. 三张证据截图均包含展开的 Power BI 筛选器窗格，不适合作为最终作品集或交付截图。
4. 英文页面标题与视觉标题同中文自动显示单位（例如“百万”“千”）及中文未筛选状态“所有”混用。该现象来自当前中文 Desktop 渲染环境，但当前截图仍不满足统一英文成品的展示要求。
5. 共享 UI 契约与 [`report-design-spec.md`](../../docs/report-design-spec.md) 存在内容漂移：
   - Product 页契约有 5 张 KPI 卡；规格要求 6 张，并额外要求 `Product Count`。
   - Customer 页契约有 4 张 KPI 卡（包含 `Cancellation Rate`）；规格要求 `Country Count` 和 `Unknown Customer Sales`，且没有列出 `Cancellation Rate`。
   - 规格要求共同 Header、更新时间、导航和 Footer；当前 UI 契约只声明使用 Desktop page tabs 导航，三页没有完整的共同 Header/Footer 组件。
6. 当前目标 Desktop 实例 PID `25740` 仍报告 `hasUnsavedChanges: true`。在项目所有者决定保存或放弃前，不应写回 PBIR 或重新加载会话。

## 推断

- 卡片裁切的直接根因是“外部视觉标题 + 新 Card 内部默认标签 + 120 高度”的组合，而不是数据或度量错误。
- KPI 组合差异属于规格与契约漂移；直接新增度量或直接删改规格都会改变人工批准的报表范围，必须由项目所有者选择目标。

## 未知

- 真实 Dropdown 筛选、跨视觉传播、键盘 Tab 顺序、屏幕阅读器朗读和 Performance Analyzer 时长尚未执行。
- Windows 受控截图接口本轮返回 `0x80004002（不支持此接口）`，因此没有使用当前窗口状态覆盖同一次 Fresh 运行的证据截图。

## 继续条件

1. 项目所有者先保存或明确放弃 PID `25740` 的未保存 PBIP 状态。
2. 项目所有者确认 KPI 漂移处理方向：以当前 10 项批准指标的 UI 契约为准并同步规格，或扩展模型与契约以满足现有规格。
3. Agent 测试先行修复卡片裁切和可复现的截图格式问题，重新运行 Report QA 与 DesktopQA。
4. 项目所有者完成真实筛选、键盘、屏幕阅读器、Performance Analyzer 和最终视觉签字后，才能把 `report` / `performance` 人工门关闭并进入 PBIX 最终保存。
