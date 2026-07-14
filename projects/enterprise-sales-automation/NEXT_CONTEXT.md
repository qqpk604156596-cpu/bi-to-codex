# 当前上下文

> 本文件由 `scripts/bi_workflow_runtime.py` 根据 `project.yaml` 与最近工作流证据生成，请勿手工维护状态。

- 项目：Enterprise Sales Automation MVP
- 项目状态：l1-desktop-deliverable
- 最近工作流：20260714T104208402Z（passed）
- 最近模式：release
- 最近成功阶段：ValidateRelease
- 待续跑阶段：无
- 下一动作：No automated stage is pending; continue with the documented human quality gates.

## 质量门

- scope: passed
- authorization: passed
- data_contract: passed
- data_quality: passed
- metrics: passed
- model_spec: passed
- model: passed
- rls: passed
- powerbi_project: passed
- report: passed
- performance: passed
- delivery: passed
- release: passed
- portfolio: passed

## 外部能力边界

- power_bi_service: not-validated
- fabric: not-validated
- gateway: not-validated
- real_multi_user_sharing: not-validated
- real_client_acceptance: not-validated

## 恢复入口

`./scripts/Invoke-BIWorkflow.ps1 -Stage Resume -ProjectPath ./projects/enterprise-sales-automation`

原始日志和阶段结果位于：
`projects/enterprise-sales-automation/evidence/runs/20260714T104208402Z/`
