# Power BI 报表设计参考标准

## 1. 目的

本标准规定企业销售MVP如何使用公开设计来源。参考的作用是提高业务真实性、可用性和视觉一致性，不是复制他人的品牌、布局成品或受版权保护资产。

## 2. 三层参考体系

### Microsoft官方：结构与交互基线

| 来源 | 使用范围 | 不直接复制 |
|---|---|---|
| [Sales and Returns sample](https://learn.microsoft.com/en-us/power-bi/create-reports/sample-sales-returns) | 页面职责、导航、数据叙事、Tooltip、交互提示和跨设备考虑 | Microsoft品牌、滑板业务内容、非必要自定义视觉对象 |
| [Retail Analysis sample](https://learn.microsoft.com/en-us/power-bi/create-reports/sample-retail-analysis) | 零售KPI层级、年度比较、地区与门店分析、管理者阅读路径 | 原报告数据、颜色、布局坐标和业务结论 |
| [Power BI可访问性指导](https://learn.microsoft.com/en-us/power-bi/create-reports/desktop-accessibility-creating-reports) | 对比度、替代文本、键盘顺序、颜色冗余和一致筛选器 | 不把截图检查写成完整WCAG合规 |

### Fabric Community：近期Power BI实践

社区案例只作为可实现性和现代Power BI版式参考，不代表Microsoft生产认证。当前候选参考：

- [Dashboard de Vendas — Receita, Metas e Funil de Conversão](https://community.fabric.microsoft.com/t5/Data-Stories-Gallery/Dashboard-de-Vendas-Receita-Metas-e-Funil-de-Convers%C3%A3o-Design-by/td-p/5194077)：参考Figma到Power BI的工作方式、留白和页面节奏。
- [Data Stories Gallery](https://community.fabric.microsoft.com/t5/Data-Stories-Gallery/bd-p/DataStoriesGallery)：只从明确披露业务目标和交互的案例中选择补充参考。

社区素材不得作为性能、安全、模型质量或客户验收证据。

### 设计网站：视觉语言补充

- [Figma Community](https://www.figma.com/community)：用于检索dashboard、analytics和enterprise data产品的栅格、组件和间距做法。
- [Behance](https://www.behance.net/)：用于观察信息密度、色彩和案例呈现方式。

设计网站是发现入口。采用任何具体作品前，必须在案例内登记作者、URL、访问日期、许可或可引用边界。许可不明确时只能总结设计原则，不下载、嵌入或重分发资产。

## 3. 参考登记格式

每个实际采用的参考在 **projects/enterprise-sales-automation/docs/report-design-spec.md** 记录：

| 字段 | 要求 |
|---|---|
| 来源 | 可直接访问的原页面URL |
| 作者/组织 | Microsoft、社区作者或设计作者 |
| 访问日期 | YYYY-MM-DD |
| 借鉴点 | 页面职责、导航、间距、色彩、交互或可访问性 |
| 不复制项 | 品牌、业务文案、数据、图片、图标或坐标 |
| 许可状态 | 官方样例、明确许可、仅观察或未知 |

没有登记的外部资产不得进入主题、PBIR或作品集。

## 4. 默认企业视觉方向

- 浅色背景、深色文字和单一蓝色主强调色；
- 16:9画布，使用一致栅格、留白和对齐；
- 顶部保留页面标题、数据更新时间与全局筛选区；
- KPI按重要性从左到右排列，数值高于装饰；
- 三页保持一致导航、筛选位置、字体层级和交互反馈；
- 优先使用Power BI原生视觉对象，减少模板环境依赖；
- 颜色不作为唯一信息载体；正文与背景对比度目标至少4.5:1；
- 所有非装饰视觉对象提供替代文本，设置合理Tab顺序；
- 不使用无法解释的渐变、背景图片、大面积阴影或装饰图标。

## 5. 三页共同结构

| 区域 | 规则 |
|---|---|
| Header | 页面标题、导航、数据更新时间 |
| Global filters | Date、Country；页内筛选不得改变位置语义 |
| KPI row | 4–6个当前页最重要指标 |
| Primary analysis | 一个回答主要业务问题的核心视觉 |
| Supporting analysis | 1–3个解释原因或定位对象的辅助视觉 |
| Detail/tooltip | 只在支持决策时提供，不堆叠字段 |
| Footer | 数据来源、公开数据练习标识与限制入口 |

## 6. 设计质量门

- 每页能用一句话说明其业务问题；
- 阅读顺序与管理决策链一致；
- 默认状态不依赖悬停才能理解；
- 筛选、跨页导航和RLS状态可见且一致；
- 1366×768及以上常见桌面窗口不出现裁切；
- 视觉截图经过人工审查，记录空白、加载、交互和可访问性限制；
- 参考来源和不复制项已登记；
- 设计通过不代表数据、性能、安全或发布质量门通过。
