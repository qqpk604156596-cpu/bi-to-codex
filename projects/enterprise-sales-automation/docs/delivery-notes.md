# 交付说明

## 当前状态

本文件定义计划交付包。公开数据、指标、模型、模拟 RLS、三页 PBIP/PBIR、共享 UI 契约、本地交互原型、集中 Desktop 人工验收、最终 PBIX 保存、交付清单、作品集证据和最终轻量 Release 均已完成。

## 计划交付资产

- 经过验证的PBIP源码；
- 人工视觉与数字验收后另存的PBIX；
- MySQL源端SQL和DuckDB基线查询；
- 不含凭据的字段映射与生成配置；
- 数据合同、指标字典、模型与RLS说明；
- JSON与Markdown验证证据；
- 默认状态与RLS状态截图；
- 中文维护说明和英文客户说明；
- UCI来源、DOI与CC BY 4.0署名。
- 共享 UI 契约、Web 原型源码、Playwright/axe 与截图回归证据。
- [L1 Desktop交付清单](delivery-checklist.md)和[统一证据索引](../evidence/README.md)。

## 运行与刷新

- Power BI使用MySQL原生Import模式。
- 客户或操作者负责提供连接终点、数据库和凭据。
- 凭据不进入Git、交付截图或公开证据。
- 完整刷新目标不超过5分钟，但只有实际测量后才能声明通过。
- 自动 DAX 查询性能代理阈值为3秒；它不替代首次 Performance Analyzer 视觉性能记录。
- Service计划刷新和网关配置未验证；交付手册不能替代实测。

## 客户或操作者必须完成

- 确认数据授权、schema映射和业务口径；
- 确认取消、缺失客户和异常价格处理；
- 审核动态RLS映射；
- 仅在自动生成的 PBIP 打开后检查三页视觉和交互；
- 保存最终PBIX；
- 决定是否外部发送、发布或公开。

## 已知限制

- 只验证UCI Online Retail II和固定销售运营模板；
- 数据没有成本，首版不提供利润或毛利；
- RLS使用模拟用户—国家映射；
- 没有Service、Fabric、网关、真实共享或真实客户验收；
- 一套数据不能证明任意schema自动理解。

## 验收记录

| 项目 | 结果 |
|---|---|
| 当前阶段 | L1 Desktop可交付；最终轻量Release Passed（`20260714T104208402Z`） |
| 数据质量 | Passed |
| 指标基线 | Passed |
| 文件级模型规格 | Passed |
| 实际模型 | Passed（既有 Desktop 证据） |
| RLS | Passed（本地模拟 UK、France、未映射；Service 身份未验证） |
| Web 原型 | Passed（5项 Playwright、axe、截图回归与生产构建） |
| 报表与性能 | Passed（DesktopQA、Performance Analyzer 与项目所有者人工签字） |
| PBIX保存 | Passed（`EnterpriseSalesAutomation.pbix`，21,185,646 bytes） |
| 交付清单 | Passed（见`delivery-checklist.md`） |
| 作品集说明 | Passed（公开数据分类、来源、限制和个人贡献边界已记录） |
| Release | Passed（0 issues；复用兼容的刷新、DAX、RLS和截图证据） |
| 客户签收 | Not applicable — public-data practice |

质量门通过后，验收记录必须链接到新鲜证据，而不是只修改状态文字。
