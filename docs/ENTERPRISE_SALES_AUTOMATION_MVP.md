# Enterprise Sales Automation MVP 开发规范

## 1. 目标

在一周、项目所有者投入20–30小时的边界内，建立一个可由VS Code与Codex操作的纵向MVP：从已经加载到本地MySQL的公开零售交易数据开始，经一次人工字段映射确认，在30分钟内生成、验证并打开三页Power BI Desktop报表。

本MVP用于证明企业Desktop报表交付能力和受控自动化方法，不证明Power BI Service、Fabric、网关或任意数据自动理解能力。

## 2. 用户与使用场景

- **操作者**：项目所有者，在VS Code中使用Codex和仓库脚本。
- **模拟客户**：需要销售运营分析的中小企业部门负责人。
- **报表用户**：销售经理、运营经理和国家/区域负责人。
- **首要外部读者**：Upwork客户。

完成后可以广泛筛选Power BI项目，但只承接数据源、业务口径和交付边界能被当前证据覆盖的工作。

## 3. 数据基线与许可

- 数据集：[UCI Online Retail II](https://archive.ics.uci.edu/dataset/502/online%2Bretail%2Bii)。
- DOI：[10.24432/C5CG6D](https://doi.org/10.24432/C5CG6D)。
- 许可：CC BY 4.0；公开成果必须署名数据集作者与UCI Machine Learning Repository。
- 规模：UCI记录为1,067,371条交易明细。
- 业务背景：英国非门店零售商2009-12-01至2011-12-09的交易。
- 已知问题：取消单、负数量、缺失客户、描述缺失和可能的价格异常。

原始文件不进入Git。凭据不写入配置、日志、截图或提交历史。

## 4. 固定接口

### 起点

1. MySQL 8.0正在运行。
2. UCI数据已经加载到获准使用的数据库与表。
3. Power BI Desktop、MySQL Connector/NET、Power BI Modeling MCP、**powerbi-report-author**和**powerbi-desktop**可用。
4. 操作者提供不进入Git的连接信息。

### 受控交互

1. 工具读取MySQL schema和样本统计。
2. AI提出源字段到标准字段的映射、粒度和缺失能力。
3. 操作者确认或修正映射与业务口径。
4. 只有确认后才允许生成模型和报表。

### 终点

- 生成并通过结构校验的PBIP/PBIR；
- MySQL Import模型刷新成功；
- DAX结果与DuckDB/SQL独立基线一致；
- 动态国家RLS测试通过；
- 三页报表通过PBIR校验和人工视觉审查；
- Power BI Desktop打开已验证报表；
- 最终人工验收后另存PBIX并组装交付包。

## 5. 数据流

    已加载MySQL
      -> schema与数据合同检查
      -> AI字段映射建议
      -> 人工确认
      -> MySQL源端视图/查询
      -> Import星型模型与动态RLS
      -> 已验证PBIR模板实例化
      -> DuckDB/SQL基线与DAX核对
      -> PBIR结构校验
      -> Desktop打开、性能与视觉验收

MySQL是正式Power BI数据源。DuckDB只承担可复现的基线计算、异常核对和测试辅助，不进入客户生产架构。

## 6. 标准模型

- 事实粒度：一行订单商品明细。
- 事实表：**FactSalesLine**。
- 维度表：**DimDate**、**DimProduct**、**DimCustomer**、**DimCountry**。
- 安全表：**SecurityUserCountry**，使用明确标注为模拟的用户—国家映射。
- 存储模式：MySQL原生连接器的Import模式。

源列名称允许不同，但必须映射到标准字段；AI不得自行改变事实粒度。

## 7. 指标范围

首版指标包括：

- **Net Sales**
- **Gross Sales**
- **Cancelled Sales**
- **Order Count**
- **Units Sold**
- **Active Customers**
- **Average Order Value**
- **Cancellation Rate**
- **Sales MoM %**
- **Sales YoY %**

数据没有成本字段，因此利润、毛利和毛利率模块必须显示为不可用并从首版页面移除。禁止通过行业比例或AI推测成本。

## 8. 三页管理决策链

1. **Executive Overview**：回答整体表现、变化方向和主要国家/产品贡献。
2. **Product & Trend Analysis**：解释销售变化由哪些产品和时间段驱动。
3. **Customer & Country Analysis**：定位客户和国家表现，并作为动态RLS的主要验收页。

页面职责、筛选、交互和视觉规范见案例内的 **docs/report-design-spec.md**。

## 9. 自动化与人工边界

### 自动化范围

- schema、合同、数据质量和字段映射建议；
- MySQL查询、星型模型、度量值、RLS和PBIR模板实例化；
- DuckDB/SQL基线、DAX、PBIR与性能证据；
- 交付清单、数据字典和限制说明。

### 人工范围

- 需求、数据授权和业务口径；
- 字段映射和模块降级确认；
- 视觉、交互、洞察和数字验收；
- PBIX保存、外部发送、Service发布和客户签收。

## 10. 失败模式

以下任一情况必须停止，并保护最后一个健康报表：

- 必需字段无法映射或事实粒度不明确；
- 数据合同或质量门失败且没有业务负责人接受记录；
- DuckDB/SQL与DAX超出容差；
- RLS出现越权或零数据异常；
- PBIR存在error或warning；
- Import刷新超过5分钟或常用交互通常超过3秒；
- 生成流程在字段映射确认后超过30分钟；
- Desktop打开后页面空白、视觉损坏或筛选传播错误。

失败输出必须指出质量门、错误代码、证据路径和恢复动作，不得仅输出“生成失败”。

## 11. 性能与验收环境

- 目标数据量：1,067,371条源交易明细。
- 当前基准机器：Intel Core i5-1135G7、16GB RAM、Windows。
- 完整Import刷新：不超过5分钟。
- 常用页面加载与筛选交互：通常不超过3秒。
- 字段映射确认后完整自动化：不超过30分钟。

性能结论必须记录Power BI版本、时间、行数、模型大小和测量方法。

## 12. 一周里程碑

| 日程 | 可验收结果 |
|---|---|
| 第1天 | 数据来源、MySQL schema、数据合同、许可与质量问题被记录 |
| 第2天 | 标准星型模型、指标基线和DuckDB核对设计通过 |
| 第3天 | 动态RLS与三页PBIR模板能够加载和校验 |
| 第4天 | 受控一键流程、失败阻断和性能证据可重复运行 |
| 第5天 | 视觉审查、完整交付包和Upwork案例说明完成 |

未通过前一日对应质量门时，不通过压缩验证来追赶进度。

## 13. 后续阶段

以下项目不属于本MVP：

- 六页完整套件；
- 三套不同schema的复用验收；
- SQL Server或PostgreSQL DirectQuery案例；
- Power BI Service、标准模式网关、真实共享与真实用户RLS；
- Fabric、Git集成、开发/测试/生产部署与容量治理；
- 面向非技术客户的GUI或任意数据自动理解。
