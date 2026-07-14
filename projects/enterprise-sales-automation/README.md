# Enterprise Sales Automation MVP

## 当前状态

本目录是企业级 Power BI Desktop 自动化的当前交付入口。数据、十项指标、星型模型、模拟动态 RLS、三页 PBIP/PBIR、共享 UI 契约、本地交互原型、PBIR 原子生成和可续跑工作流均已有验证证据。

Desktop Import 刷新、DAX、模拟 RLS、实际筛选、Performance Analyzer、键盘、屏幕阅读器、最终视觉验收和轻量 Release 均已通过，最终 PBIX 已由项目所有者保存。项目当前达到仓库定义的 L1 Desktop 可交付状态；30 分钟端到端效率目标没有本轮计时证据，不对外声明已经达到。Service、Fabric、网关、真实共享和真实客户验收继续保持未验证。

旧的15行零售PBIR看板位于 **../bi-report-automation-lab/**，已冻结为L0技术样板，不在本项目中继续扩展。

## 目标

从已加载至本地MySQL的UCI Online Retail II交易数据开始，经一次人工字段映射确认，自动生成并验证三页Power BI Desktop报表：

1. **Executive Overview**
2. **Product & Trend Analysis**
3. **Customer & Country Analysis**

数据模型使用Import模式，DuckDB负责独立指标基线，模拟用户—国家映射用于动态RLS测试。

## 开始前阅读

1. [企业级Power BI自动化能力标准](../../docs/ENTERPRISE_POWERBI_AUTOMATION_STANDARD.md)
2. [MVP开发规范](../../docs/ENTERPRISE_SALES_AUTOMATION_MVP.md)
3. [报表设计参考标准](../../docs/REPORT_DESIGN_REFERENCE_STANDARD.md)
4. [项目范围](docs/scope.md)
5. [验收标准](docs/acceptance-criteria.md)
6. [数据合同](docs/data-contract.md)
7. [指标字典](docs/metric-dictionary.md)
8. [报表设计规格](docs/report-design-spec.md)
9. [Light Executive UI设计系统](docs/ui-design-system.md)
10. [开源自动化组件采用策略](docs/open-source-automation-adoption.md)
11. [动态RLS说明](docs/security-rls.md)
12. [十天 Agentic 交付计划](docs/10-day-agentic-delivery-plan.md)
13. [Agent运行稳定性与开发流程](docs/agent-runtime-operations.md)
14. [共享 UI 契约](report/ui-contract.json)
15. [本地交互原型](ui-prototype/README.md)
16. [自动化 PBIP 启动与 Desktop 安全边界](docs/desktop-model-verification-guide.md)

## 固定边界

- 操作者：项目所有者，通过VS Code和Codex运行。
- 起点：UCI数据已加载至本地MySQL；凭据不进入Git。
- 终点：生成和验证PBIP/PBIR、核对DAX、测试RLS并打开Desktop。
- 性能目标：106万行Import刷新不超过5分钟；常用交互通常不超过3秒。
- 自动化目标：字段映射确认后30分钟内完成。
- 人工责任：需求、映射、口径、视觉、PBIX保存和最终交付。
- 未验证：Service、Fabric、网关、真实多用户共享和真实客户验收。

## Desktop 会话生命周期

日常恢复使用按输入指纹选择阶段的工作流：

```powershell
.\scripts\Invoke-BIWorkflow.ps1 -Stage Resume -ProjectPath .\projects\enterprise-sales-automation
```

- `Fresh`（默认）：目标已保存时优雅关闭并重新打开；存在未保存修改、关闭失败或超时时阻断，不强杀进程。
- `Auto`：显式快速路径；复用已连接且已保存的目标 PBIP，没有目标实例时自动打开。
- `Reuse`：只允许复用现有目标实例，目标不存在时阻断。
- `Reload`：仅用于明确需要验证旧 reload 路径时；不是默认策略。

原 `DesktopQA` 已拆为 `DesktopPreflight`、`DesktopRefresh`、`DesktopMetrics`、`DesktopRls` 和 `CaptureDesktopScreenshots`；只有对应输入变化时才运行。证据写入 `evidence/runs/<run-id>/`。

## 计划交付包

- PBIP源码与人工验收后另存的PBIX；
- MySQL SQL、字段映射配置和DuckDB核对查询；
- 数据字典、指标字典、RLS说明和验证证据；
- 中文内部维护文档与英文客户/作品集说明。
- [L1 Desktop 交付清单](docs/delivery-checklist.md)与[证据索引](evidence/README.md)。

实际状态以 **project.yaml**、`NEXT_CONTEXT.md` 和最近一次 `evidence/runs/<run-id>/summary.json` 为准。

## 报表 UI 与开源组件

当前报表采用可版本化的 `Light Executive` 设计令牌。`report/ui-contract.json` 是页面、筛选、指标绑定和交互语义的唯一共享源：本地 Web 原型负责快速交互与可访问性验收，PBIR 生成器负责映射到最终 Power BI 报表。Web 原型不是客户运行时，Desktop 原生可访问性与视觉性能仍需单独验收。

通用自动化优先复用开源组件，而不是重建平台能力。采用边界和后续评估顺序见[开源自动化组件采用策略](docs/open-source-automation-adoption.md)。
