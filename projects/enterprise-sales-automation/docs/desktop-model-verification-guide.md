# 自动化 PBIP 与 Desktop 会话生命周期

本项目的模型、DAX、关系和报告资产走可追溯的 PBIP/PBIR/TMDL 文件自动化。初始 PBIP 壳已经由 Power BI Desktop 创建；后续 Desktop 阶段由工作流按变更范围选择，不再把刷新、指标、RLS和截图强制捆绑运行。

## 默认运行

```powershell
.\scripts\Invoke-BIWorkflow.ps1 -Stage Resume -ProjectPath .\projects\enterprise-sales-automation
```

当计划包含任一 Desktop 阶段时，先运行 `DesktopPreflight`；默认 `Fresh` 策略执行：

1. 枚举所有`PBIDesktop.exe` PID，分别读取 Desktop Bridge 状态，再按目标 PBIP 的规范化绝对路径匹配实例；
2. 目标存在且无未保存修改时优雅关闭，目标不存在时跳过关闭；
3. 从环境变量、现有进程、PATH或开始菜单快捷方式发现 Desktop 可执行文件，再调用`powerbi-desktop open`；
4. 按 Desktop PID轮询 Bridge，直到`currentFilePath`与目标 PBIP一致，而不是接受任意空白 Bridge；
5. 获取目标进程的本地 Analysis Services 工作区；
6. 只执行计划选择的 `DesktopRefresh`、`DesktopMetrics`、`DesktopRls` 或 `CaptureDesktopScreenshots`；
7. 分阶段写入`desktop-session.json`及对应质量门证据。

## 显式策略

- `Fresh`：默认；只关闭没有未保存修改的目标实例，然后重新打开。
- `Auto`：显式快速路径；复用或自动打开。
- `Reuse`：必须已有目标实例。
- `Reload`：旧路径的显式兼容策略。

`Fresh`使用`CloseMainWindow()`并等待最多30秒；关闭未被接受或超时时立即阻断，不调用`Stop-Process`。任何策略发现未保存修改都立即阻断。

如果同一目标 PBIP同时存在多个 Desktop 实例，`Auto/Reuse/Reload`及PBIR写回会阻断；`Fresh`仅在所有目标实例都没有未保存修改时逐个优雅关闭，再启动唯一目标实例。

逐 PID Bridge查询若有任何一个失败，工作流把发现结果视为不完整并阻断，不会基于部分状态自动打开或切换实例。目标打开后优先探测新 PID，仅在未命中时回退检查既有 PID。

## 人工边界

工作流不自动确认主观视觉质量，不执行屏幕阅读器/键盘/实际筛选/Performance Analyzer 人工验收，也不执行最终 PBIX 保存。刷新后出现未保存模型状态时，由项目所有者决定保存或放弃；自动化不会覆盖该决定。
