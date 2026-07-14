# 刷新性能整改证据

- 状态：**passed**
- 刷新质量门：完整 Desktop Import 模型刷新不超过 300 秒
- 基线证据：`evidence/runs/20260713T133031846Z/desktop-model/desktop-model-refresh.json`
- 优化后证据：`evidence/performance/20260713T151201855Z/desktop-model-refresh.json`
- 最终代码复测：`evidence/performance/20260713T155828935Z/desktop-model-refresh.json`
- MySQL 索引诊断：`evidence/performance/mysql-index-diagnostics.json`

## 事实

| 检查 | 整改前 | 整改后 |
|---|---:|---:|
| 完整模型刷新 | 376,096.43 ms | 86,864.85 ms |
| 300 秒质量门 | failed | passed |
| `vw_dim_product` 产品聚合 | 忽略覆盖索引后 30,043.37 ms 由服务器中止 | 807.12 ms |

- 完整模型刷新耗时下降 76.90%。
- 最终代码复测耗时为 20,909.62 ms；两次优化后完整刷新均通过 300 秒门。刷新时间受本地缓存和机器负载影响，因此整改比例仍使用首次优化后运行的保守结果。
- 忽略覆盖索引的对照执行计划估算扫描 1,058,252 行，使用 `ix_stock_code`，没有索引分组优化。
- 整改后执行计划使用 `ix_product_cover`，估算扫描 9,753 行，并显示 `Using index for group-by`。
- 当前数据共有 1,067,366 行，`DescriptionText` 最大长度为 35 个字符；本地 MySQL 列为 `VARCHAR(512)`。
- Power BI 刷新证据明确记录 `duration_ms`、`refresh_threshold_seconds` 和 `performance_gate_passed`，不写入 MySQL 凭据。

## 根因

`vw_dim_product` 使用 `GROUP BY StockCode` 与 `MAX(DescriptionText)`。原始 `DescriptionText` 为 `TEXT`，现有单列产品索引不能覆盖该聚合，MySQL 需要对约 106 万行执行昂贵的表访问和分组；数据库级 full refresh 默认并行时，该分区成为关键路径。

整改将描述列约束为适合本数据合同的 `VARCHAR(512)`，并增加 `(StockCode, DescriptionText)` 覆盖索引，在保持 `MAX(Description)` 结果语义的前提下启用索引分组。

会话中还观察到 `DimProduct` Desktop 单表刷新从 180 秒未完成降至 2.243 秒；该单表命令的原始输出未单独保存，因此不作为正式质量门数字。正式性能判定只使用上方两份完整刷新 JSON。

## 边界

- 这是同一台本地开发机、同一公开数据集上的 Desktop Import 刷新证据，不代表 Service、Fabric、网关或客户环境性能。
- 300 秒门只覆盖 TMSL 完整模型刷新；报告交互继续使用现有 3 秒本地 DAX 代理门，二者不混用。
- MySQL 现有表的一次性列迁移和索引构建成本不计入日常刷新时间。
