# 十天 Agentic 交付计划

本文件是 `Enterprise Sales Automation MVP` 唯一活动实施计划。旧的一周计划已被本计划取代；数据、指标、模型、RLS 与现有 PBIP/PBIR 证据作为起点，不返工。

## 目标与边界

- 目标：把组件级自动化升级为可续跑、有证据、受质量门约束的 Power BI Desktop 交付流水线。
- 最终产品：Power BI PBIP/PBIR；Web 原型只承担 UI 设计与交互契约。
- 数据模式：本地 MySQL 8.0 原生 `Import`，DuckDB 独立核对。
- 当前不覆盖：Power BI Service、Fabric、Embedded、网关、真实身份与多用户共享。
- 自动化边界：客观检查自动化；首次 Desktop 视觉、键盘体验、屏幕阅读器和 Performance Analyzer 仍需项目所有者集中验收一次。

## 机器接口

唯一状态源是 [`../project.yaml`](../project.yaml)，恢复入口是：

```powershell
./scripts/Invoke-BIWorkflow.ps1 `
  -Stage Resume `
  -ProjectPath ./projects/enterprise-sales-automation
```

完整发布检查使用：

```powershell
./scripts/Invoke-BIWorkflow.ps1 `
  -Stage Release `
  -ProjectPath ./projects/enterprise-sales-automation
```

`-ForceFull` 忽略缓存并重跑全部本地质量门。每次运行生成 `evidence/runs/<run-id>/`，并自动更新项目与仓库根的 `NEXT_CONTEXT.md`。

运行心跳、阶段预算、超时清理和小工作包规则见[Agent运行稳定性与开发流程](agent-runtime-operations.md)。本文件中的“Day”是范围排期，不代表Agent连续运行时长；当前剩余工期必须根据未完成质量门重新估算。

## 阶段依赖

| 输入变化 | 自动重跑范围 |
|---|---|
| 仅文档 | 链接、YAML 与状态一致性 |
| UI 契约或视觉 | UI 契约 → Prototype → PBIR → Report QA → Desktop QA |
| 指标 | 指标 → 模型 → PBIR → Report QA → Desktop QA |
| 模型或 RLS | 模型 → PBIR → Report QA → Desktop QA |
| 数据合同或原始输入 | 数据合同 → 数据质量 → 全部下游门 |
| 无变化且无待续跑阶段 | 跳过摘要 |

失败或阻断时不覆盖最后健康 PBIR；`project.yaml.workflow.pending_stages_json` 保存失败阶段及其下游，下一次 `Resume` 从该处继续。目标 PBIP 有未保存修改时，`GenerateReport` 与 `DesktopQA` 均标记为 `Blocked`，不弹窗、不强制重载。

## Day 1–3：工作流压缩

- [x] U1：`AGENTS.md` 与结构化提示协议按 Tier 0/1/2 分级。
- [x] U2：实现 `Resume`、`Release`、输入指纹、依赖图和失败续跑。
- [x] U3：统一运行摘要、原始日志、`project.yaml` 与 `NEXT_CONTEXT.md`。

验收：常规工作包最多一次 Tier 1 确认；指纹扫描剪枝依赖与缓存目录；无变化计划计算远低于 60 秒。

## 运行稳定性整改

- [x] 每个续跑阶段使用独立受监控子进程，原始输出实时写入阶段日志。
- [x] 静默阶段默认每15秒产生心跳，并记录阶段耗时、预算与超时状态。
- [x] 超时使用固定退出码 `124`，同时终止整个子进程树。
- [x] 失败摘要给出证据路径、待续跑阶段和下一动作。
- [x] 普通 `Resume` 终止于 `DesktopQA`；人工交付门仅由 `Release`执行。
- [x] 工作包按单一目标和30–60分钟预算拆分，避免一次执行整份十天范围。

## Day 4–6：共享 UI 契约与原型

- [x] U4：建立 [`../report/ui-contract.json`](../report/ui-contract.json)，固定三页、Dropdown、字段绑定、交互、空值策略、设计令牌和可访问性语义。
- [x] U4：建立 `ui-prototype/` 的 Next.js、TypeScript、本地 shadcn 风格组件与 Recharts 原型。
- [x] U5：Playwright 覆盖导航、单月与多月、图表点击、清除筛选、axe 与截图回归。
- [x] U5：`next build --webpack` 生产构建通过；本机原生 SWC 不可用时使用官方提示的 WASM + Webpack 回退。

原型只使用公开数据的聚合 Fixture，不连接 MySQL，不包含凭据或完整明细。v0 在线服务不是持续交付依赖；当前会话没有可调用的 v0 连接，因此版本化事实来源是本地代码、测试与 [`../report/ui-contract.json`](../report/ui-contract.json)。

## Day 7–9：PBIR 与 Desktop QA

- [x] U6：PBIR 生成器读取共享 UI 契约，不再维护第二份页面布局源。
- [x] U6：在同卷临时目录生成与校验，成功后替换，失败保留最后健康定义。
- [x] U7：Desktop 阶段按 `Refresh → DAX/性能代理 → RLS → 三页截图` 执行。
- [x] U7：本地 DAX 查询记录 `duration_ms`，阈值为 3000ms；它是 Performance Analyzer 的自动代理，不冒充原生视觉性能证据。
- [ ] U7：目标 PBIP 清除未保存修改后，执行一次新鲜 `Resume` Desktop 证据运行。
- [ ] U7：项目所有者完成首次键盘、屏幕阅读器、实际筛选与 Performance Analyzer 集中验收。

## Day 10：发布与作品集

- [ ] U8：人工批准后保存 PBIX；PBIP/PBIR 继续作为主要版本化资产。
- [ ] U8：完成交付清单、QA 报告、风险、作品集公开说明和证据索引。
- [ ] U8：执行 `Release`，确认全部本地质量门与状态文件一致。

## 验收合同

- 三页固定为 `Executive Overview`、`Product & Trend Analysis`、`Customer & Country Analysis`。
- Dropdown 固定覆盖 `YearMonth`、`Country`、`StockCode`、`CustomerID`。
- “所有”、多月或无可比期间的 MoM/YoY 显示 `--`；仅单月且存在可比期间时显示百分比。
- UI 契约每个组件必须有且只有一个 PBIR 映射；未知度量值或孤立组件阻断生成。
- Prototype axe 不得有 Critical/Serious 问题，正文对比度至少 4.5:1，截图差异阈值 1%。
- PBIR 校验新增 error 必须阻断；外部 JSON Schema 网络警告单独记录。
- MySQL Import 刷新目标不超过 5 分钟；DAX 性能代理和人工常用筛选目标不超过 3 秒。
- 动态 RLS 必须覆盖 UK、France 与未映射用户；Service 身份仍标记“未验证”。
- 未完成的人工门、外部门不得因自动测试通过而改写为 `passed`。
