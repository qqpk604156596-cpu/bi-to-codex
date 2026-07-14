# 风险登记表

| ID | 风险 | 类型 | 可能性 | 影响 | 缓解措施 | 状态 |
|---|---|---|---|---|---|---|
| R-01 | MySQL字段与标准字段不一致 | Data | High | High | AI只提出映射建议，人工确认后才继续 | Open |
| R-02 | 取消单和负数规则导致指标口径偏差 | Metric | Medium | High | MySQL、DuckDB与DAX使用同一批准口径并交叉核对 | Open |
| R-03 | 缺失CustomerID导致客户指标失真 | Data | High | Medium | 保留Unknown销售，客户去重指标排除空ID | Open |
| R-04 | 动态RLS误授权或无映射用户看到数据 | Security | Medium | High | 默认拒绝，使用虚构用户逐角色测试并留证 | Open |
| R-05 | 百万行刷新或常用交互超过阈值 | Performance | Medium | Medium | 在目标设备记录刷新和Performance Analyzer证据 | Open |
| R-06 | 文档完成被误述为企业交付完成 | Claim | Medium | High | 所有质量门保持Pending，Service/Fabric标记未验证 | Mitigated |

风险的关闭必须引用实际证据；计划、说明或截图占位不能作为关闭依据。
