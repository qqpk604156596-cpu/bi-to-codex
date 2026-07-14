# Enterprise Sales UI Prototype

这是 Power BI 三页报表的本地交互原型，不是生产运行时。它由共享 [`../report/ui-contract.json`](../report/ui-contract.json) 驱动验收语义，并只使用 [`lib/fixture.ts`](lib/fixture.ts) 中的公开聚合 Fixture。

## 运行

```powershell
npm install
npm run dev
```

访问 `http://127.0.0.1:3000`。

## 验证

```powershell
npm test
npm run build
```

- Playwright：三页导航、Dropdown、多月、图表点击与清除筛选。
- axe：无 Critical/Serious 自动可访问性问题。
- 截图：`tests/dashboard.spec.ts-snapshots/`，允许差异不超过 1%。
- Build：本机 Next.js 原生 SWC 绑定不可用时使用 `--webpack` 的 WASM 回退。

## 边界

- 不连接 MySQL，不读取 `.env`，不包含原始交易明细。
- v0 可用于初始设计加速，但在线服务不是持续交付依赖。
- 当前原型由本地代码实现；未调用 v0 在线服务，因此不能声称由 v0 自动生成。
- Power BI Desktop/PBIR 才是最终客户交付物。
