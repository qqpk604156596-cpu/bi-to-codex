# Agent 运行稳定性与开发流程

本文规定本项目后续 Agent 开发、验证和恢复方式。目标是让长任务可观察、可终止、可续跑，并减少无效重复运行和上下文消耗。

## 工作包大小

- 一个工作包只包含一个可独立验收的目标，例如“工作流心跳”或“Desktop RLS 采证”。
- 预计专注时间控制在 30–60 分钟；超过 60 分钟的目标必须拆成多个质量门。
- 每个工作包开始时写明输入、修改范围、验收命令和停止条件。
- 测试失败时只修复当前目标直接造成的问题；发现新的架构问题时停止扩张并重新规划。
- 功能开发、依赖安装、完整回归和 Desktop 人工验收不得合并成一个不可见的长步骤。

## 模型与推理配置

| 工作类型 | 建议配置 |
|---|---|
| 代码修改、故障诊断、架构边界 | `5.6 Sol`、高推理、标准速度 |
| 已有测试重跑、文档同步、状态检查 | `5.6 Sol`、中推理、标准或快速速度 |
| 短时间重大架构审查 | `5.6 Sol`、极高推理；不得用于持续开发全程 |

模型速度不影响 npm 下载、Playwright、MySQL、Power BI 刷新或 Desktop Bridge。外部工具耗时必须由阶段日志和心跳判断。

## 唯一运行入口

日常恢复：

```powershell
./scripts/Invoke-BIWorkflow.ps1 `
  -Stage Resume `
  -ProjectPath ./projects/enterprise-sales-automation `
  -HeartbeatSeconds 15
```

最终交付检查：

```powershell
./scripts/Invoke-BIWorkflow.ps1 `
  -Stage Release `
  -ProjectPath ./projects/enterprise-sales-automation `
  -HeartbeatSeconds 15
```

`Resume`只执行输入指纹已失效或上次被阻断的质量门，不再固定执行完整 Desktop QA。`Release`始终执行轻量 `Preflight`、`ValidateStructure` 和 `ValidateRelease`，其余阶段只有在指纹缓存缺失或输入已经变化时才执行。

原 `DesktopQA` 已拆分为：

1. `DesktopPreflight`：以安全的 Fresh 生命周期检查未保存状态、唯一目标实例和本地模型工作区；
2. `DesktopRefresh`：仅执行完整 Import 刷新和 300 秒门；
3. `DesktopMetrics`：仅执行 Desktop DAX 指标对账；
4. `DesktopRls`：仅执行本地 RLS 验证；
5. `CaptureDesktopScreenshots`：仅采集三页截图。

`DesktopQA` 仅作为向后兼容的显式组合入口保留，不属于默认 `Resume` 或 `Release` 阶段图。

## 变更触发矩阵

| 输入变化 | 默认阶段 | 明确跳过 |
|---|---|---|
| 文档 | `ValidateDocumentation` | Desktop、数据、Prototype |
| 数据合同、原始/中间数据、ETL | Data Contract、Data Quality、Metrics、Model、Desktop Refresh/Metrics/RLS | Prototype、截图 |
| 指标/DAX | Metrics、Model、Desktop Metrics | Data Quality、Refresh、Prototype、截图 |
| 模型、Power Query、分区 | Model、Power BI Project、Desktop Refresh/Metrics/RLS | Prototype、截图 |
| UI契约或Prototype | UI Contract、Prototype、PBIR生成、Report QA、Desktop截图 | Data Quality、Refresh、RLS |
| PBIR清单或报表定义 | PBIR生成、Report QA、Desktop截图 | Data Quality、Refresh、Metrics、RLS、Prototype |

阶段成功后，`project.yaml.workflow.stage_cache_json` 保存该阶段的输入指纹和证据运行。Release 可复用指纹仍匹配的刷新、指标、RLS和截图证据，不要求为了“同一次运行”重新制造相同证据。

从 schema v1 升级时，可用现有已通过质量门和本地证据初始化一次缓存；证据缺失的阶段会保持未缓存：

```powershell
python ./scripts/bi_workflow_runtime.py bootstrap-cache `
  --project-path ./projects/enterprise-sales-automation
```

诊断时可临时覆盖单阶段超时：

```powershell
./scripts/Invoke-BIWorkflow.ps1 `
  -Stage Resume `
  -ProjectPath ./projects/enterprise-sales-automation `
  -StageTimeoutSeconds 300
```

该覆盖作用于本次运行的所有选中阶段，不应作为放任无限等待的手段。

## 默认运行预算

| 阶段 | 超时 |
|---|---:|
| Preflight、Structure、Documentation、Report QA | 60秒 |
| Data Contract、Metrics、Model、Power BI Project、UI Contract、PBIR生成 | 120秒 |
| Prototype | 180秒 |
| Data Quality | 300秒 |
| Desktop Preflight、Metrics、RLS | 120秒 |
| Desktop Refresh | 360秒 |
| Desktop Screenshots | 90秒 |
| 兼容入口 Desktop QA | 600秒 |
| Release | 120秒 |

超时退出码固定为 `124`。运行器必须终止该阶段的整个进程树，避免遗留 npm、Node、Python 或 PowerShell 子进程。

## 可观察输出

每个阶段至少产生以下事件：

```text
stage_start stage=<name> timeout_s=<seconds> log=<path>
heartbeat stage=<name> elapsed_s=<seconds> pid=<pid>
stage_complete stage=<name> status=<status> exit_code=<code> duration_ms=<ms> timed_out=<bool>
```

子进程原始输出实时写入 `evidence/runs/<run-id>/<stage>.log`。进程结果写入 `<stage>.process.json`，运行摘要记录：

- 阶段状态与退出码；
- 实际耗时和超时预算；
- 是否超时；
- 待续跑阶段；
- 证据路径和下一动作；
- 阻断阶段、阻断原因、首次阻断时间和同原因重试次数。

## 停滞判定与恢复

1. 有心跳：任务仍在运行，不得仅凭界面“思考中”中断。
2. 60秒无心跳：检查阶段进程、日志更新时间和 `process.json`，不猜测模型故障。
3. 命中预算：运行器终止整个进程树，以退出码 `124` 标记失败。
4. `Blocked`：解决未保存Desktop修改、缺少实例或人工门，不重复跑健康上游阶段。
5. `Failed`：先读取摘要给出的日志，再修复单一根因并执行 `Resume`。
6. 失败不得覆盖最后健康PBIR，也不得把未执行的下游门标记为通过。
7. `DesktopPreflight` 在任何刷新、指标、RLS或截图阶段之前执行；发现未保存状态后立即停止，不进入昂贵阶段。
8. 同一阻断重复出现时递增 `blocked_retry_count`；恢复后摘要保留 `resolved_block`，不把等待时间伪装成测试耗时。

## 上下文同步

每次 `Resume` 或 `Release` 生成计划前会根据当前 `project.yaml` 和最新工作流摘要重建根目录及项目目录的 `NEXT_CONTEXT.md`。只需同步状态而不运行质量门时使用：

```powershell
python ./scripts/bi_workflow_runtime.py sync-context `
  --project-path ./projects/enterprise-sales-automation
```

## Agent用户更新规则

- 启动工具前说明当前阶段和预计等待范围。
- 运行期间不超过60秒提供一次简短更新。
- 更新只包含当前阶段、已等待时间、最新证据和是否仍有活动进程。
- 不把“命令仍运行”“模型推理中”和“真实卡死”混为一类。
- 完成声明必须引用本轮新鲜测试和运行证据。

## 验收

- 静默命令按配置周期产生心跳。
- 输出在命令完成前写入日志，而不是阶段结束后一次性落盘。
- 超时命令及其后代进程均被终止。
- 运行摘要包含耗时、超时标志、证据路径和下一动作。
- 普通 `Resume` 不触发人工 `Release` 门。
- 无变化的 `Resume` 直接返回跳过摘要。
- 报表样式变化不触发刷新、指标或RLS；数据变化不触发Prototype或截图。
- 指纹仍有效的Release不重复执行Data Quality、Prototype或Desktop完整刷新。
