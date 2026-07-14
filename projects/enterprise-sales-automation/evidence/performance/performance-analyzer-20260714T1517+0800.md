# Performance Analyzer 交互性能证据

- 证据时间：2026-07-14 15:12–15:17 +08:00
- 执行人：Portfolio project owner
- 页面：`Customer & Country Analysis`
- 目标：常用页面刷新与筛选交互通常不超过 `3,000 ms`
- 状态：**Passed**

## 结果

| 场景 | 最大单视觉耗时 | 阈值 | 结果 | 截图 |
|---|---:|---:|---|---|
| 默认状态 `Refresh visuals` | 404 ms | 3,000 ms | Passed | [`default-refresh.png`](../report/performance-analyzer-20260714/default-refresh.png) |
| `Country = United Kingdom` | 453 ms | 3,000 ms | Passed | [`country-united-kingdom.png`](../report/performance-analyzer-20260714/country-united-kingdom.png) |
| `YearMonth = 2010-11` | 455 ms | 3,000 ms | Passed | [`month-2010-11.png`](../report/performance-analyzer-20260714/month-2010-11.png) |

## 数字核对

- United Kingdom 截图显示 `Net Sales £16.54M`、`Order Count 37K`、`Average Order Value £489.15` 和 `Cancellation Rate 14.90%`，与最终 Desktop DAX 证据的显示精度一致。
- 2010-11 截图显示 `Net Sales £1.42M`、`Order Count 3K`、`Average Order Value £535.23`、`Cancelled Sales £47.62K` 和 `Cancellation Rate 15.70%`，与最终 Desktop DAX 证据的显示精度一致。

## 边界

- 本证据来自 Power BI Desktop Performance Analyzer 截图，不包含导出的 JSON；截图已经显示各视觉对象的 `Duration (ms)`，足以支持本项目的 `≤3 s` 交互门。
- 测试覆盖当前报表中视觉对象数量最多的 Customer 页面及两个批准的代表性筛选场景；自动 DAX 性能代理和完整 Import 刷新另有机器证据。
- 本证据不替代键盘、屏幕阅读器、跨视觉交互和最终主观视觉签字。
