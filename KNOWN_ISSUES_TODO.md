# KNOWN ISSUES & ROADMAP — Beta 0.4.42

> 研发进度表与技术债记录。更新于 2026-04-07。

---

## ✅ Beta 0.4.x — 发布记录

| 版本 | 日期 | 核心修复 |
|------|------|---------|
| v0.4.42 | 04-07 20:29 | P3前端PortfolioDashboard+净值曲线+调仓弹窗；list_portfolios死代码清理 |
| v0.4.41 | 04-07 19:00 | scheduler每日15:30收盘快照；_save_snapshot_impl同步核心 |
| v0.4.40 | 04-07 18:10 | P3多账户组合Schema+CRUD+PnL+快照（portfolios/positions/portfolio_snapshots）|
| v0.4.39 | 04-07 15:58 | DrawingCanvas右键菜单替代confirm()（P2完成）|
| v0.4.38 | 04-07 15:40 | 前端纯计算过滤StockScreener；SpotCache.query补amount字段 |
| v0.4.37 | 04-07 15:20 | P1 amount/turnover_rate/amplitude字段补全+回填脚本 |
| v0.4.36 | 04-07 14:22 | init_env.sh+README同步（GitHub仓库清理完毕）|
| v0.4.35 | 04-07 14:16 | docs:更新KNOWN_ISSUES_TODO.md至v0.4.34 |
| v0.4.34 | 04-07 07:40 | `_normalize_symbol`上證指数/sh000858→sz000858/_clean_symbol removeprefix |
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

## 🟢 P4 — 长期功能

### Issue #8：全球市场数据
- 港股期货主力合约
- 欧股/日股指数实时行情

### Issue #9：技术指标扩展
- RSI、DMI、OBV、SAR等新指标
- 多周期K线同时展示（日+周+月）
- 指标参数自定义

### Issue #10：回测框架
- 均线策略回测，买卖信号可视化
- 绩效统计（收益率、夏普比率、最大回撤）

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
