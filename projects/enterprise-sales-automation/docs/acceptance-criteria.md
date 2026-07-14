# 验收标准

只有运行对应验证并保存新鲜证据后才能改为 **Passed**；未验证项目保持 **Pending**。

| ID | 可观察结果 | 验证方法 | 负责人 | 状态 |
|---|---|---|---|---|
| AC-01 | 数据来源、DOI、CC BY 4.0许可和公开限制已记录 | 文档与来源链接检查 | 项目所有者 | Passed |
| AC-02 | MySQL事实粒度和标准字段映射获得人工确认 | 映射审批记录 | 项目所有者 | Passed |
| AC-03 | 1,067,371条源记录被加载，或差异有可解释对账 | MySQL行数与UCI来源核对 | 项目所有者 | Passed |
| AC-04 | 取消单、负数量、缺失客户、重复和异常价格规则可重复执行 | 数据质量命令返回0并保存证据 | 项目所有者 | Passed |
| AC-05 | 10项指标的DuckDB/MySQL基线在批准容差内一致；DAX留待模型阶段验证 | 自动指标核对 | 项目所有者 | Passed |
| AC-06 | 星型模型的关系、方向、键和日期表通过设计与实际模型验证 | 模型规范、Desktop结构证据和DAX查询 | 项目所有者 | Passed |
| AC-07 | 模拟用户只能查看获准国家且无越权 | Desktop本地运行时身份的UK、France、未映射自动查询；与DuckDB国家基线对账 | 项目所有者 | Passed |
| AC-08 | 三个规定页面存在并支持批准的管理决策链 | PBIR结构检查与人工视觉QA | 项目所有者 | Passed |
| AC-09 | PBIR校验为0 errors、0 warnings | powerbi-report-author validate | 项目所有者 | Passed |
| AC-10 | 106万行完整Import刷新不超过5分钟 | Desktop刷新计时证据 | 项目所有者 | Passed |
| AC-11 | 常用页面加载与筛选交互通常不超过3秒 | Performance Analyzer或等价记录 | 项目所有者 | Passed |
| AC-12 | 字段映射确认后30分钟内完成生成、验证并打开Desktop | 端到端时间记录；当前没有完整计时，不作为L1通过声明 | 项目所有者 | Pending |
| AC-13 | 失败质量门返回明确状态且不覆盖健康报表 | PBIR临时生成/回滚与Blocked续跑回归测试 | 项目所有者 | Passed |
| AC-14 | PBIP、PBIX、SQL、配置、字典、证据和说明组成完整交付包 | [交付清单审查](delivery-checklist.md) | 项目所有者 | Passed |
| AC-15 | Service、Fabric、网关和真实客户验收被明确标为未验证 | 文档措辞扫描与[证据索引](../evidence/README.md) | 项目所有者 | Passed |

支持环境基线：Windows、Power BI Desktop、MySQL 8.0、MySQL Connector/NET、DuckDB、PowerShell、Node.js、Playwright、VS Code和Codex。

数据与指标证据见[MySQL原始加载](../evidence/data-quality/mysql-load.md)、[数据合同验证](../evidence/data-quality/contract-validation.md)、[行级质量验证](../evidence/data-quality/data-quality.md)和[指标对账结果](../evidence/metrics/reconciliation.md)。模型与 RLS 证据见 [`../evidence/model/`](../evidence/model/) 与 [`../evidence/rls/`](../evidence/rls/)。AC-12 仍为未验证效率目标；它不会被写成已通过，也不阻断本轮已具备完整L1证据的Desktop交付。AC-08 与 AC-09 的证据见 [`../evidence/report/human-desktop-acceptance-20260714T1500+0800.md`](../evidence/report/human-desktop-acceptance-20260714T1500+0800.md) 和 [`../evidence/report/pbir-validation.json`](../evidence/report/pbir-validation.json)；AC-10 与 AC-11 的证据分别见 [`../evidence/runs/20260714T063334594Z/desktop-model/desktop-model-refresh.json`](../evidence/runs/20260714T063334594Z/desktop-model/desktop-model-refresh.json) 和 [`../evidence/performance/performance-analyzer-20260714T1517+0800.md`](../evidence/performance/performance-analyzer-20260714T1517+0800.md)。AC-14与AC-15见[交付清单](delivery-checklist.md)和[证据索引](../evidence/README.md)。

最终轻量Release见[`../evidence/runs/20260714T104208402Z/release-check.md`](../evidence/runs/20260714T104208402Z/release-check.md)，结果为Passed、0 issues。
