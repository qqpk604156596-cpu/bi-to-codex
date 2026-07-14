# QA 报告

本文件记录人工与自动质量门的职责边界。状态只能由新鲜证据更新；Web 原型通过不等于 Desktop 最终验收通过。

## 质量门摘要

| Gate | Required evidence | Result | Owner |
|---|---|---|---|
| Scope | 人工批准范围、排除项和公开数据练习分类 | Passed | Portfolio project owner |
| Authorization | UCI 来源、CC BY 4.0 与本地凭据边界 | Passed | Portfolio project owner |
| Data contract | 字段映射批准、粒度与异常规则 | Passed | Portfolio project owner |
| Data quality | MySQL 标准化抽取与全量质量证据 | Passed | Portfolio project owner |
| Metrics | 十项指标的 DuckDB/MySQL 独立对账 | Passed | Portfolio project owner |
| Model | 星型模型、关系、日期表和十项 DAX | Passed | Portfolio project owner |
| RLS | UK、France 与未映射本地模拟场景 | Passed | Portfolio project owner |
| Report | PBIR 结构、绑定、Desktop 渲染、交互与可访问性 | Passed | Portfolio project owner |
| Performance | Import refresh、DAX 代理与 Performance Analyzer | Passed | Portfolio project owner |
| Delivery | PBIP、人工批准 PBIX、清单与交接 | Passed | Portfolio project owner |
| Portfolio | 公开版叙事、限制和证据索引 | Passed | Portfolio project owner |
| Release | 完整 Release 运行与人工签字 | Passed | Portfolio project owner |

## 当前自动化证据

- Data / Metrics：数据合同、全量质量、DuckDB/MySQL 十项指标对账已通过。
- Model / RLS：文件化模型、Desktop 本地模型、UK、France 与未映射模拟 RLS 已有证据；Service 身份未验证。
- UI contract：三个固定页面、Dropdown、字段与度量绑定、MoM/YoY 空值策略和可访问性语义已锁定。
- Prototype：5 项 Playwright 测试、axe Critical/Serious 检查、1% 截图回归和 `next build --webpack` 已通过。
- PBIR：共享 UI 契约已生成 3 页、33 个视觉对象；原子生成负向测试证明失败不覆盖最后健康定义。

## Desktop render evidence

- Status: Passed
- 证据：[`../evidence/runs/20260714T063334594Z/`](../evidence/runs/20260714T063334594Z/) 包含同一次 DesktopQA 的 Import refresh、DAX、RLS 和三页截图。

## 人工 Desktop QA

- Refresh：Passed；完整 Import 刷新为 `68.58653 s`。
- Visual：Passed；项目所有者确认三页层级、裁切、格式、真实筛选和跨页一致性。
- Accessibility：Passed；项目所有者确认键盘顺序、焦点和屏幕阅读器检查通过。
- Performance：Passed；Performance Analyzer 代表性场景最大单视觉耗时为 `455 ms`。
- Release：Passed；运行`20260714T104208402Z`返回0 issues，复用兼容的Desktop刷新、指标、RLS和三页截图证据。

## 已知边界

- 本案例是 UCI 公开数据练习，不是付费客户经历。
- MySQL 使用原生 Import；不包含 DirectQuery。
- 没有成本字段，不展示利润、毛利或毛利率。
- Service、Fabric、网关、真实共享、真实身份和客户签收均未验证。
- 单一销售模板不能描述为任意行业或任意 schema 的一键生成器。

## 当前阻断

| ID | Severity | Description | Status |
|---|---|---|---|
| QA-001 | Blocker | 需要连接目标 PBIP 执行新鲜 DesktopQA | Closed |
| QA-002 | Blocker | 首次 Desktop 可访问性、Performance Analyzer 与最终视觉验收未完成 | Closed |
| QA-003 | Blocker | Release、交付清单和作品集最终证据未完成 | Closed |
