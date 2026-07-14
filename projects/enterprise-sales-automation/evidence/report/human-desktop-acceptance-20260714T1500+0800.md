# Power BI Desktop 集中人工验收记录

- 创建时间：2026-07-14 15:00 +08:00
- 当前实例：PID `13448`，`EnterpriseSalesAutomation.pbip`
- 当前保存状态：`hasUnsavedChanges: false`
- 自动证据：[`../runs/20260714T063334594Z/`](../runs/20260714T063334594Z/)
- 保存状态截图：[`../runs/20260714T064441297Z/saved-desktop-screenshots/`](../runs/20260714T064441297Z/saved-desktop-screenshots/)
- 当前状态：**Passed**

## 已收到的项目所有者证据

- `Country = United Kingdom` 筛选与数字核对：Passed。
- `YearMonth = 2010-11` 筛选与数字核对：Passed。
- Performance Analyzer 代表性交互：Passed；最大单视觉耗时 `455 ms`，见 [`../../performance/performance-analyzer-20260714T1517+0800.md`](../../performance/performance-analyzer-20260714T1517+0800.md)。
- 跨视觉单击响应、键盘焦点顺序、屏幕阅读器和最终视觉签字：Passed（项目所有者于 2026-07-14 明确确认）。

## Agent 已完成

- 三页结构、绑定、刷新、DAX、RLS 和保存状态检查通过。
- 完整 Import 刷新为 `68.58653 s`，通过 `≤300 s` 门限。
- 默认状态截图已确认三页无裁切、Customer 页布局一致、英文 `M/K` 单位生效。
- Windows 受控窗口读取返回 `0x80004002（不支持此接口）`；为避免盲目点击，Agent 未代替项目所有者执行以下人工操作。

## 项目所有者一次性验收步骤

1. 收起 `Filters`、`Visualizations` 和 `Data` 三个作者窗格；逐页确认标题、卡片、图表和页签没有裁切、重叠或异常滚动。
2. 在 `Executive Overview` 将 `Country` 设为 `United Kingdom`：`Net Sales` 应约为 `£16.54M`，`Order Count` 应为 `36,535`；清除筛选后应恢复约 `£19.45M` 和 `40K`。
3. 在 `Product & Trend Analysis` 将 `YearMonth` 设为 `2010-11`：`Net Sales` 应约为 `£1.42M`，`Sales MoM %` 应约为 `31.23%`，`Sales YoY %` 应保持空值；清除筛选。
4. 在任一国家或产品条形图单击一个条目，确认同页其他视觉发生交叉筛选或突出显示；再次单击空白处恢复默认状态。
5. 使用 `Tab` / `Shift+Tab` 遍历切片器和视觉对象，确认焦点可见、顺序符合从上到下和从左到右；用现有屏幕阅读器确认页面标题、切片器名称和主要视觉标题可识别。
6. ~~打开 Performance Analyzer，开始记录后执行一次国家筛选与清除；确认常用交互通常不超过 `3 s`，保存或截图该记录。~~ **Passed**
7. 最终确认三页视觉风格和数字满足作品集交付要求。

## 项目所有者结论

- 键盘检查：Passed。
- 屏幕阅读器检查：Passed。
- 最终视觉检查：Passed。
- 签字结论：`人工验收通过，可以关闭 report 门并进入最终 PBIX 保存。`
- PBIX 保存：Passed；项目所有者已保存 [`EnterpriseSalesAutomation.pbix`](../../EnterpriseSalesAutomation.pbix)。本地核对大小为 `21,185,646` bytes，修改时间为 `2026-07-14 16:23:09 +08:00`。
