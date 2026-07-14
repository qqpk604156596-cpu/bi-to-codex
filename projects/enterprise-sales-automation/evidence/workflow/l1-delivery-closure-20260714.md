# L1 Desktop 交付封板证据

- 日期：2026-07-14
- 状态：Passed。
- 分类：Public-data practice project。

## 已核对事实

- `EnterpriseSalesAutomation.pbip` 存在，SHA-256 为 `171BE908B1EF98302BDDA484267D444627ED602F84A6989C31B6B5B3F367D4C1`。
- `EnterpriseSalesAutomation.pbix` 存在，大小为 21,185,646 bytes，SHA-256 为 `49C8ADE1018288F689D9074246471E463F14C5AA9E980B514F9A4FBBF552CE23`。
- MySQL SQL、数据合同、指标配置、批准映射、指标字典、RLS说明、QA报告、交付说明和作品集说明均存在。
- Desktop Import 刷新为 68.58653 秒，通过不超过 300 秒门。
- Performance Analyzer 代表性场景最大单视觉耗时为 455 毫秒，通过不超过 3 秒门。
- 项目所有者已确认实际筛选、跨视觉交互、键盘、屏幕阅读器和最终视觉检查通过，并保存最终 PBIX。

## 声明边界检查

- 公开数据练习分类：已明确。
- 真实付费客户声明：未使用。
- 任意行业、任意 schema 一键生成声明：未使用。
- Service、Fabric、网关、真实共享和真实客户验收：保持未验证。
- 30 分钟端到端效率目标：没有证据，保持未验证且不对外宣称通过。

## Release 结果

- 运行 ID：`20260714T104208402Z`
- 状态：Passed
- 执行阶段：`Preflight`、`ValidateStructure`、`ValidateReportQA`、`ValidateRelease`
- Release问题数：0
- [人类可读结果](../runs/20260714T104208402Z/release-check.md)
- [机器结果](../runs/20260714T104208402Z/release-check.json)
- 复用证据：Desktop Refresh/Metrics/RLS 来自 `20260714T063334594Z`；三页保存状态截图来自 `20260714T064441297Z`。
- 未执行：Desktop启动、Import刷新、DAX、RLS、截图和人工验收重跑。
