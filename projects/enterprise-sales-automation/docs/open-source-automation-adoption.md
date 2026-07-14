# 开源 Power BI 自动化组件采用策略

## 结论

本项目不从零开发完整的 Power BI 平台，也不把单一工具包装成“任意数据一键生成看板”。采用成熟开源组件处理通用能力，本项目保留业务映射、指标口径、验证证据、质量门和交付说明的编排责任。

## 已评估组件

| 组件 | 可复用能力 | 本项目采用状态 | 边界 |
|---|---|---|---|
| pbi-tools | PBIX/PBIP 源码化、提取、构建与 DevOps 工作流 | 研究候选 | 当前已有 PBIP；不得替换已验证的 PBIR 生成与 Desktop 验证链路。 |
| Tabular Editor 2 | 模型、DAX、角色、显示文件夹和批处理脚本 | 后续候选 | 只在独立验证后用于模型质量检查；不以第三方写入代替 DAX 对账。 |
| PBI Inspector / Fab Inspector | PBIP/PBIR 布局和元数据规则检查，可产出 JSON、HTML、PNG | 下一优先级 | 用于补齐报表 QA，不替代 Desktop 渲染、可访问性或业务验收。 |
| Semantic Link Labs | Fabric/Service 中的语义模型、报告、BPA、XMLA/TMSL 辅助自动化 | Fabric 阶段候选 | 当前 Desktop MVP 不安装、不调用，也不因此宣称 Service/Fabric 能力。 |

## 当前架构责任

```text
公开数据 / MySQL
  -> 本项目的数据合同、SQL、DuckDB 基线
  -> TMDL / DAX / PBIR 生成器
  -> 开源校验组件（按需接入）
  -> Power BI Desktop 实际刷新与渲染证据
  -> 质量门、交付说明与作品集限制
```

## 采用规则

- 先在独立分支或独立案例验证组件，再写入主流程。
- 工具输出必须能回链至版本化资产、命令和证据；不能只保留截图或聊天结论。
- 不保存凭据、真实客户数据或真实身份到开源工具配置、日志或 Git。
- Service、Fabric、网关、真实共享和真实客户权限仍为未验证状态，除非有独立实测证据。

## 近期顺序

1. 完成本项目 RLS 正向验证、性能、可访问性和交付门。
2. 以 PBI Inspector/Fab Inspector 建立 PBIR 规则化 QA 试点。
3. 评估 Tabular Editor 2 的模型/DAX 批量检查价值。
4. 仅在新案例中评估 Service 或 Fabric 自动化。
