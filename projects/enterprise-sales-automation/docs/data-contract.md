# 数据合同

## 1. 来源与授权

| 来源 | 所有者 | 访问方式 | 项目用途 | 公开使用 |
|---|---|---|---|---|
| [UCI Online Retail II](https://archive.ics.uci.edu/dataset/502/online%2Bretail%2Bii) | 数据集作者/UCI | CC BY 4.0公开下载；后续加载到本地MySQL | 公开数据练习、自动化与作品集 | 允许，但必须署名 |
| 本地MySQL副本 | 项目所有者 | 本机数据库凭据 | Power BI正式数据源 | 不提交数据库或凭据 |
| DuckDB核对库 | 项目所有者 | 本地临时文件 | 独立SQL基线与质量检查 | 只公开脚本和脱敏结果 |

本项目不含客户数据或真实个人权限。CustomerID属于公开数据集字段，公开截图和明细导出仍应最小化展示。

## 2. 粒度与键

- 标准事实粒度：一行发票中的一个商品明细。
- 标准业务键：InvoiceNo + StockCode + InvoiceDate + source row identity。
- 不假设前三个业务字段组合在原始数据中绝对唯一；导入时必须保留可追溯源行标识。
- 时间：原始交易时间按数据集记录解释；报告时区不自行转换。
- 报告期间：2009-12-01至2011-12-09，以实际对账结果为准。
- UCI报告实例数：1,067,371；加载差异必须形成对账说明。

## 3. 标准字段映射

| 标准字段 | 类型 | 必需 | 定义 | 规则 |
|---|---|---:|---|---|
| SourceRowId | whole number/text | 是 | 导入过程生成或保留的源行标识 | 不为空、项目内唯一 |
| InvoiceNo | text | 是 | 发票/订单编号 | 保留前导字符；C前缀用于取消识别 |
| StockCode | text | 是 | 商品代码 | 不为空 |
| Description | text | 否 | 商品描述 | 缺失不得替换为虚构名称 |
| Quantity | whole number | 是 | 该行商品数量 | 允许负数；负数必须分类 |
| InvoiceDate | datetime | 是 | 发票生成时间 | 能解析且位于批准期间 |
| UnitPrice | decimal | 是 | 商品单位价格，英镑 | 负值阻断；零值单独审计 |
| CustomerID | text | 否 | 客户标识 | 缺失保留Unknown分组，不生成虚构客户 |
| Country | text | 是 | 客户所在国家 | 去除首尾空格；空值阻断RLS |
| IsCancellation | boolean | 是 | 是否为取消/退回记录 | 由已批准的InvoiceNo前缀和业务规则生成 |
| LineAmount | decimal | 是 | Quantity × UnitPrice | 精度与容差在机器合同中固定 |

实际 MySQL 原始表映射已由项目所有者于 2026-07-12 批准，机器可读记录见 [`config/source-mapping.approved.json`](../config/source-mapping.approved.json)：`InvoiceNo → InvoiceNo`、`StockCode → StockCode`、`Description → DescriptionText`、`Quantity → Quantity`、`InvoiceDate → InvoiceDate`、`UnitPrice → UnitPrice`、`CustomerID → CustomerID`、`Country → Country`。AI 只提出映射建议；人工确认记录是继续建模的前置条件。

## 4. 质量规则

| 规则 | 处理 |
|---|---|
| InvoiceNo、StockCode、Quantity、InvoiceDate、UnitPrice或Country缺失 | 阻断 |
| CustomerID缺失 | 保留并标记Unknown；客户指标排除空ID，明细量单独报告 |
| Description缺失 | 允许，显示Unknown Product Description |
| Quantity为负 | 不直接删除；必须与取消规则核对 |
| UnitPrice为负 | 阻断并记录源行 |
| UnitPrice为零 | 保留在数据质量异常集中，不计入正销售额 |
| InvoiceNo以C开头 | 分类为取消记录；不得计入完成订单 |
| 重复源行 | 阻断，除非有书面业务依据 |
| 交易日期超出数据集范围 | 阻断或记录来源差异 |

## 5. 对账控制

- MySQL源行数与UCI报告实例数核对。
- MySQL和DuckDB分别计算总行数、发票数、取消发票数、正数量合计、净额和国家数。
- Power BI DAX与DuckDB/SQL使用同一批准过滤定义。
- 金额容差：绝对误差不超过0.01英镑；比例容差不超过0.0001。
- 对账失败时不得继续报表交付。

## 6. 安全与Git边界

- 原始XLSX、MySQL数据目录、DuckDB数据文件、PBIX和凭据不进入Git。
- 连接配置使用参数、环境变量或本地忽略文件。
- 公开证据优先使用聚合结果；明细截图不得暴露不必要的CustomerID。
- UCI署名保存在README、交付说明和作品集案例中。
