# Desktop 模型验证记录（待人工填写）

- 状态：**Pending**
- 适用范围：公开 UCI 练习数据；不代表 Service 或真实客户权限。
- PBIP 路径：
- Desktop 版本：
- MySQL Import 刷新结果：
- 验证日期：

| 场景 | 预期 | 实际行数 | 实际 Net Sales | 截图/查询证据 | 结果 |
|---|---|---:|---:|---|---|
| 无 RLS | 全部国家；与 DuckDB/MySQL 基线一致 |  |  |  | Pending |
| UK 用户 | 仅 United Kingdom |  |  |  | Pending |
| France 用户 | 仅 France |  |  |  | Pending |
| 未映射用户 | 0 行或明确无数据状态 |  |  |  | Pending |

只有实际 Desktop 模型、DAX 与 RLS 结果均通过后，才能替换本模板并更新质量门。
