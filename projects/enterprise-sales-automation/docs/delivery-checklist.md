# L1 Desktop 交付清单

本清单用于确认 `Enterprise Sales Automation MVP` 已形成符合仓库 L1 标准的 Power BI Desktop 交付包。本项目是公开数据作品集练习，不是付费客户项目。

## 交付结论

- 交付等级：L1 Desktop 可交付。
- 主要运行时：Power BI Desktop，MySQL 8.0 原生 Import。
- 最终文件：`EnterpriseSalesAutomation.pbip` 与项目所有者人工保存的 `EnterpriseSalesAutomation.pbix`。
- AC-12 的“字段映射确认后 30 分钟内完成”没有端到端计时证据，保留为未验证效率目标，不作为本轮 L1 通过声明。
- Power BI Service、Fabric、网关、真实共享、真实用户 RLS 和真实客户验收不属于已验证范围。
- 最终轻量 Release：Passed，运行 `20260714T104208402Z`。

## 资产核对

| 类别 | 资产 | 结果 |
|---|---|---|
| Power BI | `../EnterpriseSalesAutomation.pbip` | Passed |
| Power BI | `../EnterpriseSalesAutomation.pbix` | Passed；21,185,646 bytes |
| SQL | `../src/sql/001_create_schema.sql`、`010_create_standardized_views.sql`、`011_data_quality_anomaly_queries.sql`、`020_metric_baseline.sql`、`030_security_user_country.sql` | Passed |
| 配置 | `../config/data-contract.json`、`metrics.json`、`source-mapping.approved.json` | Passed |
| 数据与指标说明 | `data-contract.md`、`metric-dictionary.md` | Passed |
| 模型与安全说明 | `security-rls.md` 和版本化语义模型资产 | Passed |
| 报表说明 | `report-design-spec.md`、`ui-design-system.md` | Passed |
| 运行与交接 | `agent-runtime-operations.md`、`desktop-model-verification-guide.md`、`delivery-notes.md` | Passed |
| QA | `qa-report.md` 与人工 Desktop 验收证据 | Passed |
| 作品集 | `portfolio-case-study.md` | Passed；公开数据练习与限制已披露 |
| 证据索引 | [`../evidence/README.md`](../evidence/README.md) | Passed |

## 文件完整性

| 文件 | SHA-256 |
|---|---|
| `EnterpriseSalesAutomation.pbip` | `171BE908B1EF98302BDDA484267D444627ED602F84A6989C31B6B5B3F367D4C1` |
| `EnterpriseSalesAutomation.pbix` | `49C8ADE1018288F689D9074246471E463F14C5AA9E980B514F9A4FBBF552CE23` |

哈希用于记录本次本地交付物，不表示 PBIX 应进入 Git。PBIX、凭据、本地缓存和未脱敏证据继续按 `.gitignore` 管理。

## 交付边界

- 可以声明：公开数据作品集项目；受质量门约束的模板化 Power BI Desktop 交付流程；数据、指标、模型、模拟 RLS、报表、刷新与交互性能已在本地证据范围内验证。
- 不可声明：真实付费客户项目、任意行业或任意 schema 一键生成、生产环境已经部署、Service/Fabric/网关已经验证、真实客户已签收。
- 外部发送、公开发布、Git commit/push、Service 部署与权限修改仍需单独授权。

## 项目所有者确认

- 范围与公开数据练习分类：2026-07-14 已确认。
- Desktop 人工验收与 PBIX 保存：Passed。
- 交付资产和限制说明：Passed。
- AC-12 效率目标：Pending；本轮不对外声明已达到。
- 最终 Release：Passed；见 [`../evidence/runs/20260714T104208402Z/release-check.md`](../evidence/runs/20260714T104208402Z/release-check.md)。
