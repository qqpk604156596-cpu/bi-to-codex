# 指标字典

## 1. 通用规则

- 货币：GBP。
- 日期口径：使用InvoiceDate和标准日期表。
- 完成交易：IsCancellation为false且Quantity大于0。
- 取消交易：IsCancellation为true或经批准规则识别为取消。
- CustomerID缺失记录参与销售金额，但不参与Active Customers。
- 所有时间比较必须明确当前筛选上下文；没有可比期间时返回空值，不返回0。
- 利润、毛利和毛利率不在首版范围，因为数据没有成本字段。

## 2. 核心指标

| 指标 | 业务定义 | 公式/口径 | 单位 | 主要排除项 | 状态 |
|---|---|---|---|---|---|
| Gross Sales | 完成交易的正销售额 | SUMX(完成交易, Quantity × UnitPrice) | GBP | 取消、非正数量 | Verified: DuckDB/MySQL |
| Cancelled Sales | 取消交易对应金额的绝对值 | SUMX(取消交易, ABS(Quantity × UnitPrice)) | GBP | 非取消交易 | Verified: DuckDB/MySQL |
| Net Sales | 全部有效明细的净影响 | SUM(LineAmount) | GBP | 质量门拒绝的行 | Verified: DuckDB/MySQL |
| Order Count | 完成发票数量 | DISTINCTCOUNT(完成交易InvoiceNo) | orders | 取消发票 | Verified: DuckDB/MySQL |
| Units Sold | 完成交易销售件数 | SUM(完成交易Quantity) | units | 取消和非正数量 | Verified: DuckDB/MySQL |
| Active Customers | 有完成交易且ID非空的客户数 | DISTINCTCOUNT(CustomerID) | customers | 空CustomerID、取消 | Verified: DuckDB/MySQL |
| Average Order Value | 每个完成订单的完成销售额 | Gross Sales ÷ Order Count | GBP/order | 除数为0时返回空 | Verified: DuckDB/MySQL |
| Cancellation Rate | 取消发票占全部发票的比例 | Cancelled Invoice Count ÷ All Invoice Count | % | 空InvoiceNo | Verified: DuckDB/MySQL |
| Sales MoM % | 完整月净销售额相对上月变化 | (本期Net Sales − 上月Net Sales) ÷ 上月Net Sales | % | 无上月或上月为0时返回空 | Verified: DuckDB/MySQL |
| Sales YoY % | 净销售额相对上年同期变化 | (本期Net Sales − 上年同期Net Sales) ÷ 上年同期Net Sales | % | 无上年同期或同期为0时返回空 | Verified: DuckDB/MySQL |

## 3. 辅助指标

- **All Invoice Count**：所有有效InvoiceNo的去重数量。
- **Cancelled Invoice Count**：取消InvoiceNo的去重数量。
- **Unknown Customer Sales**：CustomerID缺失明细的Net Sales。
- **Product Count**：筛选上下文中的StockCode去重数量。
- **Country Count**：筛选上下文中的Country去重数量。

辅助指标可以支持页面和质量说明，但不取代10项核心指标验收。

## 4. 独立验证

每个核心指标必须同时具有：

1. DuckDB或MySQL基线SQL；
2. Power BI DAX度量值；
3. 无筛选总计测试；
4. 至少一个国家筛选测试；
5. 至少一个月份筛选测试；
6. 对取消与CustomerID缺失边界的测试。

金额绝对误差不超过0.01英镑；比例误差不超过0.0001。容差外差异将指标质量门置为failed。

当前已完成 DuckDB/MySQL 的总计、United Kingdom 和 2010-11 完整月份对账，见 [`reconciliation.json`](../evidence/metrics/reconciliation.json)。全量与国家切片没有单一月份上下文，因此 Sales MoM % 和 Sales YoY % 为 `null`；2010-11 的 YoY 因 2009-11 没有可比数据也为 `null`。这不是 DAX 或 Desktop 验证证据。

## 5. 模块化降级

如果未来客户数据缺少某个指标所需字段：

- 工具必须列出缺失字段、受影响指标和页面；
- 人工确认后可以关闭对应模块；
- 关闭模块不得用估算数据填充；
- 对外交付说明必须记录未提供的能力。
