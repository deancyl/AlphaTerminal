# KNOWN ISSUES & ROADMAP — Beta 0.4.57

> 研发进度表与技术债记录。更新于 2026-04-08。

---

## ✅ Beta 0.4.x — 发布记录

| 版本 | 日期 | 核心修复 |
|------|------|---------|
| v0.4.57 | 04-08 08:38 | Phase 8完成：K线引擎重构+ΔOI+债券历史曲线+期限结构 |
| v0.4.56 | 04-08 07:17 | 债券接入/bond/curve真实AAA利差，替换口行为商A-AAA |
| v0.4.55 | 04-08 00:xx | FuturesPanel全屏面板+BaseKLineChart复用+持仓量OI曲线 |
| v0.4.54 | 04-07 22:xx | 期货热力图按板块分组+债券真实信用利差 |
| v0.4.53 | 04-07 20:xx | Bond history period参数生效——动态回溯窗口 |
| v0.4.52 | 04-07 19:xx | 移除deep监听性能炸弹+期货K线持仓量OI曲线 |
| v0.4.51 | 04-07 18:xx | WebSocket gap修复+BaseKLineChart基础设施 |
| v0.4.50 | 04-07 16:xx | 多账户模拟组合——数据库Schema+路由CRUD |
| v0.4.49 | 04-07 15:xx | DrawingCanvas键盘快捷键/线段命中检测/range-select |
| v0.4.48 | 04-07 14:xx | StockScreener page_size 5000→100修复FastAPI 422 |
| v0.4.47 | 04-07 13:xx | PortfolioDashboard+usePortfolioStore |
| v0.4.46 | 04-07 12:xx | scheduler每日15:30收盘快照 |
| v0.4.45 | 04-07 11:xx | 多账户组合Schema+CRUD+PnL+快照 |
| v0.4.44 | 04-07 10:xx | DrawingCanvas右键菜单替代confirm() |
| v0.4.43 | 04-07 09:xx | 全局异常处理器+文档同步至v0.4.42 |
| v0.4.42 | 04-07 08:29 | PortfolioDashboard+净值曲线+调仓弹窗 |
| v0.4.41 | 04-07 07:00 | scheduler每日15:30收盘快照；_save_snapshot_impl同步核心 |
| v0.4.40 | 04-07 06:10 | P3多账户组合Schema+CRUD+PnL+快照 |
| v0.4.39 | 04-07 05:58 | DrawingCanvas右键菜单替代confirm() |
| v0.4.38 | 04-07 05:40 | 前端纯计算过滤StockScreener |
| v0.4.37 | 04-07 05:20 | P1 amount/turnover_rate/amplitude字段补全+回填 |
| v0.4.36 | 04-07 04:22 | init_env.sh+README同步 |
| v0.4.35 | 04-07 04:16 | docs:更新KNOWN_ISSUES_TODO.md至v0.4.34 |
| v0.4.34 | 04-07 03:40 | `_normalize_symbol`上證指数/sh000858→sz000858 |
| v0.4.33 | 04-07 00:30 | 新浪财经板块API替代AkShare Eastmoney（84行业+175概念）|

---

## ✅ P0 — 已完成

### Issue #1：Force Refresh 无差异化错误提示
**状态**：✅ 已修复（v0.4.34之前）  
后端失败返回HTTP 500 + `{"error":"...","items_stale":true}`，前端检测`error`字段显示红色警告。

### Issue #2：全市场个股名称未同步
**状态**：✅ 已修复（v0.4.30+）  
`/api/v1/market/symbols`懒加载全市场A股，`symbolRegistry`缓存于内存。

### Issue #3：涨跌家数空白
**状态**：✅ 已修复（v0.4.32）  
`SpotCache.get_histogram()`接入`quote_detail`，展示横向红绿比例条。

---

## 🟡 P1 — 已完成

### Issue #4：成交额/换手率/振幅 字段为空
**状态**：✅ 已完成（v0.4.37-beta）  
`market_data_daily`表新增`amount`/`turnover_rate`/`amplitude`；回填脚本覆盖32只核心A股。

### Issue #5：条件选股（Stock Screener）
**状态**：✅ 已完成（v0.4.38-beta）

**实现**：  
- 后端：`/api/v1/market/stocks`（SpotCache实时数据，支持排序）  
- 前端：`StockScreener.vue`纯前端computed过滤  
  - 过滤维度：涨跌幅、换手率（%）、成交额（亿）、最新价  
  - 多维排序（代码/盈亏率/市值/股数）  
  - 分页展示（每页50条）  
  - `page_size=5000`→`100`，修复FastAPI 422验证错误（v0.4.42）

---

## 🟡 P1/P2 — 进行中

### Issue #6：画线工具完善
**状态**：🔄 进行中

**已完成**：locked状态、键盘快捷键、线段命中高亮、ResizeObserver、range-select  
**已修复**：右键菜单替代`confirm()`（v0.4.39-beta）✅

**待完成**：
- [ ] 选择/移动模式（切换工具而非每次绘制）
- [ ] 文本标注改内联输入框

---

## ✅ P3 — 已完成（v0.4.42-beta）

### Issue #7：多账户模拟组合
**状态**：✅ 已完成（v0.4.42-beta）

**数据库层**：  
- `portfolios`（id, name, type, created_at, total_cost）  
- `positions`（portfolio_id, symbol, shares, avg_cost, updated_at）  
- `portfolio_snapshots`（portfolio_id, date, total_asset, total_cost）

**后端路由**（`portfolio.py`）：  
- `GET  /api/v1/portfolio/` — 账户列表  
- `POST /api/v1/portfolio/` — 新建账户  
- `DELETE /{id}` — 删除账户  
- `GET  /{id}/positions` — 持仓列表  
- `POST /positions` — 建仓/调仓（upsert）  
- `DELETE /{id}/positions/{symbol}` — 清仓  
- `GET  /{id}/pnl` — 实时浮动盈亏（SpotCache）  
- `GET  /{id}/snapshots` — 净值历史  
- `POST /{id}/snapshots` — 保存当日快照  

**定时任务**：scheduler每日15:30收盘快照，启动时同步触发一次。

**前端**（v0.4.42）：  
- `PortfolioDashboard.vue`：左右分栏+净值曲线+持仓表+调仓弹窗  
- `usePortfolioStore.js`：20秒轮询PnL+CRUD封装  
- Sidebar新增💰投资组合入口  

**初始化**：`python scripts/init_portfolios.py`（主账户id=1，子账户id=2）

---

## ✅ Phase 8 — 专业机构级行情分析（v0.4.57-beta）

**完成时间**：2026-04-08  
**核心架构**：数据层与渲染层完全解耦——`chartDataBuilder.js` 作为唯一数据中枢，`BaseKLineChart.vue` 成为纯渲染哑组件。

### 战役 1：ΔOI 量价仓联动 ✅
**文件**：`chartDataBuilder.js`、`BaseKLineChart.vue`、`FuturesPanel.vue`

- `volumes[]` 新增 `deltaOI`（持仓变化）和 `priceUp`（涨跌方向）字段
- 新增 `D_OI` 副图类型，着色逻辑：
  - 🔴 涨 + 增仓 → 多头主动进攻
  - 🟢 跌 + 增仓 → 空头主动建仓
  - ⚪ 减仓 → 双边离场
- FuturesPanel 副图三档切换：VOL / ΔOI / MACD，默认 ΔOI

### 战役 2：债券收益率历史曲线对比 ✅
**文件**：`bond.py`、`BondDashboard.vue`、`YieldCurveChart.vue`

- 后端：`akshare bond_china_yield()` 全量历史 DataFrame，按日期排序取 -22（≈1M前）和 -252（≈1Y前）行国债截面
- 缓存结构新增 `yield_curve_1m` 和 `yield_curve_1y`
- 前端渲染：今日实线 + 1个月前虚线（dashed，#fbbf24）+ 1年前点线（dotted，#9ca3af）
- 有历史曲线时自动显示图例；Tooltip 多行显示所有曲线同期限数据

### 战役 3：期货期限结构图（Forward Curve）✅
**文件**：`futures.py`、`TermStructureChart.vue`（新）、`FuturesPanel.vue`

- 后端新增 `GET /api/v1/futures/term_structure?symbol=RB`
  - 从 `WATCHED_COMMODITIES` 反查中文名，调用 `akshare futures_zh_realtime()`
  - 过滤僵尸合约，按交割月升序返回
- 新增 `TermStructureChart.vue`：双 Grid（价格折线 + OI 柱状图）
- Contango↑ 绿色标注 / Backwardation↓ 红色标注
- FuturesPanel 顶部新增 `[K线图] | [期限结构]` 切换 Tab

### 架构重构（K线引擎三部曲）✅

**Step 1** — `chartDataBuilder.js`（新建）：MA/BOLL/MACD/KDJ/RSI 全部迁入独立工具函数。

**Step 2** — `BaseKLineChart.vue` 改为哑组件：
- Props：`chartData`（结构化对象）+ `subCharts`（布局控制数组）
- 删除全部 `calc*` / `buildOption` / `echarts.init`
- `datazoom` 事件向上传递（支持懒加载）

**Step 3** — `AdvancedKlinePanel.vue` / `FuturesPanel.vue` / `FullscreenKline.vue` 全面接入：
- 引入 `shallowRef + triggerRef` 优化高频 Tick 更新
- `DrawingCanvas` 改为 `baseChartRef.getChartInstance()` 获取 ECharts 实例
- 净减少臃肿代码 **400+ 行**

### 内存泄漏修复 ✅
- BondDashboard / FuturesDashboard：`setInterval` 配对 `onUnmounted clearInterval`
- 删除废弃 `useMultiStream.js`

---

## 🟢 P4 — 长期功能

### Issue #8：全球市场数据
- 港股期货主力合约
- 欧股/日股指数实时行情

### Issue #9：技术指标扩展
- ~~RSI~~ ✅（v0.4.57）、KDJ ✅、BOLL ✅ 已内置于 `chartDataBuilder.js`
- DMI、OBV、SAR 等新指标
- 多周期K线同时展示（日+周+月）
- 指标参数自定义（已在 AdvancedKlinePanel 预留 UI）

### Issue #10：回测框架
- 均线策略回测，买卖信号可视化
- 绩效统计（收益率、夏普比率、最大回撤）

---

## 🔴 战役 4：跨品种叠加对比（Cross-Asset Overlay）
**状态**：⚙️ 待启动

**价值**：宏观对冲研究——将"沪深300"+"10年期国债收益率"叠放在同一张图上，观察股债跷跷板效应。

**技术路径**：
- AdvancedKlinePanel 新增"叠加品种"搜索框
- `chartDataBuilder.js` 支持注入第二条价格线并归一化（ECharts dual-y-axis）
- `BaseKLineChart` 已有 `overlaySeriesData` 字段，前端无需修改

---

## 📝 技术债

| # | 债项 | 位置 | 清理状态 |
|---|------|------|---------|
| 1 | market.py死代码（usdcnh/fetched） | `_get_macro_data()` | ✅ 已删除（v0.4.31）|
| 2 | `_SYMBOL_REGISTRY`前缀错误 | market.py | ✅ 已修复（v0.4.34）|
| 3 | `_normalize_symbol`上證指数归类 | market.py | ✅ 已修复（v0.4.34）|
| 4 | `_clean_symbol` replace误删 | market.py | ✅ 已修复（v0.4.34）|
| 5 | 板块AkShare断连 | sectors_cache.py | ✅ 已修复（v0.4.33）|
| 6 | GitHub仓库>100MB | .git | ✅ GC后~2-5MB（v0.4.36）|
| 7 | list_portfolios死代码拼接 | portfolio.py | ✅ 已修复（v0.4.42）|
| 8 | 全局无单元测试 | backend/ | ⚠️ 待建立 |
| 9 | 后端无统一错误码规范 | backend/app/ | ⚠️ 下一步处理 |
| 10 | page_size 5000触发422 | market.py | ✅ 已修复（v0.4.42）|
