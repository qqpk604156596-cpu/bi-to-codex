# Enterprise Sales Automation 证据索引

本目录保存本项目的数据、指标、模型、模拟 RLS、报表、性能和工作流证据。证据仅支持公开数据练习范围内的 Power BI Desktop L1 交付声明。

## 范围与授权

- [范围批准记录](workflow/scope-approval-20260714.md)
- [项目范围](../docs/scope.md)
- [数据合同](../docs/data-contract.md)
- 数据源：UCI Online Retail II，CC BY 4.0，公开数据练习。

## 数据与指标

- [MySQL 原始加载](data-quality/mysql-load.md)
- [数据合同验证](data-quality/contract-validation.md)
- [行级数据质量](data-quality/data-quality.md)
- [MySQL 异常摘要](data-quality/mysql-anomaly-summary.md)
- [DuckDB/MySQL 指标对账](metrics/reconciliation.md)
- [指标验证](metrics/metrics-validation.md)

## 模型与 RLS

- [模型规格验证](model/model-spec-validation.md)
- [Power BI Project 验证](model/powerbi-project-validation.md)
- [Desktop 模型刷新](runs/20260714T063334594Z/desktop-model/desktop-model-refresh.json)
- [Desktop DAX 指标](runs/20260714T063334594Z/desktop-metrics/desktop-metric-validation.json)
- [Desktop 模拟 RLS](runs/20260714T063334594Z/desktop-rls/desktop-rls-validation.json)

RLS 证据只覆盖 Desktop 本地模拟场景。Power BI Service、Entra、真实用户与真实共享权限未验证。

## 报表、人工验收与性能

- [PBIR 校验](report/pbir-validation.json)
- [报表 QA](report/report-qa.md)
- [Desktop 人工验收](report/human-desktop-acceptance-20260714T1500+0800.md)
- [三页保存状态截图](runs/20260714T064441297Z/saved-desktop-screenshots/)
- [Performance Analyzer](performance/performance-analyzer-20260714T1517+0800.md)
- [刷新性能整改说明](performance/refresh-performance-remediation.md)

## 交付封板

- [L1 Desktop 交付清单](../docs/delivery-checklist.md)
- [L1 交付封板证据](workflow/l1-delivery-closure-20260714.md)
- [最终 Release 检查](runs/20260714T104208402Z/release-check.md)与[机器结果](runs/20260714T104208402Z/release-check.json)

## 未验证边界

- 字段映射批准到打开 Desktop 的完整端到端 30 分钟计时没有本轮证据；它保持为未验证效率目标。
- Power BI Service、Fabric、网关、计划刷新、真实多用户共享、真实用户 RLS 和真实客户验收均未验证。
- 本项目不得描述为真实客户项目、生产部署或任意 schema 一键生成器。
