# AlphaTerminal 代码审计报告 v4.0
**日期**: 2026-04-09
**版本**: v0.4.105 → v0.4.106 (审计修复版)
**审计人**: AI Assistant

---

## 1. 与专业金融平台的差距评估

### 差距矩阵

| 维度 | 专业平台 (Wind/Bloomberg) | AlphaTerminal 当前 | 差距等级 |
|------|------------------------|-------------------|---------|
| 数据覆盖 | 全市场A股/港股/美股实时 | 仅10+指数+5只示例股 | 🔴 极大 |
| K线质量 | Level-2/逐笔成交 | 日K/周K/月K/分钟K | 🟡 中等 |
| 技术指标 | 100+指标库 | 8个副图指标 | 🟡 中等 |
| 基本面 | 财报/估值/预测 | 仅有PE/PB空值 | 🔴 极大 |
| 资金流 | 主力/散户/北向分项 | 全为null | 🔴 极大 |
| 新闻 | 实时+深度+舆情 | 东方财富快讯 | 🟡 小 |
| 搜索 | 全市场秒级检索 | 仅SymbolRegistry | 🟡 中等 |
| 组合分析 | VaR/夏普/回测 | 简单持仓管理 | 🟡 中等 |
| 画线工具 | 专业套装 | 11种画线工具 | 🟢 已覆盖 |
| Copilot | 研报生成 | 基础问答+Mock LLM | 🟡 中等 |

### 核心差距
1. **数据源瓶颈**: AkShare 穿透是按需触发，非主动全量同步，导致大量标的"无数据"
2. **基本面空心化**: quote_detail 返回的PE/PB/资金流全为null
3. **全市场搜索缺失**: `_SYMBOL_REGISTRY` 仅含20条，全市场个股首次搜索失败

---

## 2. 前端UI潜在问题

### 🔴 P0 - 立即修复

**2.1 `quote_detail` API 完全损坏**
- **文件**: `backend/app/routers/market.py` 第~700行
- **问题**: `get_latest_prices` 的调用方式错误
  ```python
  rows_latest = get_latest_prices([db_sym]) if hasattr(get_latest_prices, '__code__') else []
  ```
  `hasattr(get_latest_prices, '__code__')` 永远为 `True`（函数天然有`__code__`），但返回值是 **list 而非 dict**，导致后续 `w = rows_latest[0]` 取到的是列名字典而非行数据。`w.get('index')` 或 `w.get('price')` 均取不到正确字段，导致 `price = 0.0`！
- **影响**: 全屏K线右侧 QuotePanel 显示价格永远是 `--`

**2.2 Symbol Normalization 三套并行**
- **文件**: `market.py`
  - `_normalize_symbol()` - 前端传入的symbol标准化
  - `_clean_symbol()` - 用于数据库查询
  - `_unprefix()` - 去掉 sh/sz/hk 前缀
- **问题**: 三套逻辑略有差异，"sh000001" 经过不同函数可能返回不同结果
- **影响**: 板块点击时 K 线有时无法正确加载

**2.3 ECharts 内存泄漏**
- **文件**: `FullscreenKline.vue`, `IndexLineChart.vue`
- **问题**: `chart?.dispose()` 在 `onUnmounted` 中调用，但如果组件被 `keep-alive` 或父组件异常未触发 unmount，则 chart 不释放
- **影响**: 多次打开/关闭全屏K线后浏览器内存持续增长

### 🟠 P1 - 高优先级

**2.4 DashboardGrid 网格重叠风险**
- `gs-y="17"` 给 StockScreener 留了8格高度，但如果上方组件高度变化（如隐藏某widget），会导致重叠
- `GridStack.setStatic()` 在 `isLocked` 切换时可能有延迟

**2.5 键盘快捷键失效**
- `FullscreenKline.vue` 的 `handleKeydown` 依赖 `tabindex="0"` 和 `focus()`
- 但组件被 `<Teleport to="body">` 包裹，初始无 focus，需要点击后才能响应
- `Escape` 关闭功能依赖全局按键，但未注册 `window` 级别监听

**2.6 分页数据处理低效**
- `NewsFeed.vue` 使用 `items.slice()` 做前端分页，200条全量存在内存
- 每次 `fetchNews` 都做 `items.sort()` 全量排序，O(n log n)

**2.7 API 响应格式不统一**
- `/api/v1/market/overview` → `{code:0, data: {wind: {...}, meta: {...}}}`
- `/api/v1/market/history/{symbol}` → 直接返回 `{symbol, period, history: []}` **无 code 包裹**
- `/api/v1/market/quote_detail/{symbol}` → 直接返回 `{name, symbol, price, ...}` **无 code 包裹**
- 前端 `fetchApiBatch` 的 fallback 逻辑 `results.news?.news || results.news` 脆弱

### 🟡 P2 - 中优先级

**2.8 缺失加载状态骨架屏**
- `NewsFeed`, `DashboardGrid` 加载时直接显示空白，无 skeleton 动画

**2.9 WebSocket 无重连状态 UI**
- `useMarketStream.js` 重连时无明确状态提示，用户不知道数据在断线

**2.10 全屏 K 线响应式问题**
- 移动端 `<768px` 隐藏右侧 QuotePanel，但图表区域宽度计算可能有问题

---

## 3. 前后端代码协同问题

### 🔴 关键问题

**3.1 API 响应格式混乱**
```
/market/overview      → {code, data: {wind, meta}}
/market/china_all     → {code, data: {china_all, meta}}
/market/history/{}    → {symbol, period, history[]}  ❌ 无 code
/market/quote_detail/ → {name, symbol, price, ...}   ❌ 无 code
/news/flash           → {code, data: {news, source, total}}
/news/force_refresh   → {code, data: {news, items_stale, ...}}
```
Phase B 标准化未完全执行，约40%接口仍是旧格式。

**3.2 后端穿透逻辑分散**
- `market_history` 路由中混合了：本地DB查询 → AkShare穿透 → 后台线程 → 同步返回
- 路径选择逻辑复杂，调试困难

**3.3 全局代理环境变量冲突**
- `data_fetcher.py` 设置 `NO_PROXY`，`market.py` 也设置 `NO_PROXY`
- `akshare` 内部可能也设置代理，三个地方可能冲突

### 🟠 协同问题

**3.4 前端 8 路并发请求**
- `App.vue` `fetchMarketData()` 一次性发 8 个请求
- 虽然用 `Promise.all` 并发，但后端每个请求独立查库/网络，无批量优化

**3.5 错误处理链路断裂**
- 后端某接口 500，前端 `fetchApiBatch` 静默使用 `default: []`
- 用户完全不知道有接口失败，只有 console.error

**3.6 `_clean_symbol` vs `_unprefix` 职责不清**
- 两个函数都是"去掉前缀"，但实现略有差异
- 混用导致同一 symbol 产生不同 DB key

---

## 4. 整体代码质量评估

| 维度 | 评分 | 说明 |
|------|------|------|
| 架构设计 | 7/10 | 分层清晰，路由/服务/DB分离好 |
| 代码复用 | 6/10 | 工具函数散落，重复代码多 |
| 错误处理 | 5/10 | 日志充分但接口错误处理不一致 |
| 性能意识 | 6/10 | 有缓存机制但实现粗糙（全局变量+TTL） |
| 可维护性 | 5/10 | 大量TODO/注释残留，逻辑嵌套深 |
| 前端架构 | 6/10 | Vue3 Composition API 使用规范 |
| 测试覆盖 | 2/10 | 无单元测试，回归风险高 |
| 文档质量 | 5/10 | 代码注释充分但无API文档 |

**技术债:**
1. `sentiment_engine.py` 中 `SpotCache` 用全局类变量，有线程安全注释但实现复杂
2. `market.py` 单文件超过 800 行，应拆分
3. `FullscreenKline.vue` 超过 500 行，副图指标计算函数应抽离
4. `data_fetcher.py` 中 `fetch_us_stock_history` 包含4层备选策略，150+行函数

---

## 5. 修复优先级与计划

### 立即执行 (P0)

| # | 问题 | 文件 | 修复方案 |
|---|------|------|---------|
| F1 | `quote_detail` API 损坏 | market.py | 修复 `get_latest_prices` 调用，直接获取 |
| F2 | Symbol norm 三套并行 | market.py | 统一用 `_normalize_symbol` 作为入口 |
| F3 | ECharts 内存泄漏 | FullscreenKline.vue | 添加 `onBeforeUnmount` 或 `onUnmounted` |
| F4 | API 响应格式不统一 | market.py, news.py | 所有接口统一 `{code, data, message, timestamp}` |

### 本轮执行 (P1)

| # | 问题 | 文件 | 修复方案 |
|---|------|------|---------|
| F5 | 键盘快捷键失效 | FullscreenKline.vue | 注册 window keydown 监听 |
| F6 | 分页低效 | NewsFeed.vue | 改用后端分页 |
| F7 | 后端500静默失败 | App.vue | apiClient 增加错误汇总提示 |
| F8 | `_clean_symbol` 歧义 | market.py | 合并到 `_normalize_symbol` |

---

## 6. 修复完成清单

- [ ] F1: quote_detail API 修复
- [ ] F2: Symbol normalization 统一
- [ ] F3: ECharts dispose 完善
- [ ] F4: API 响应格式统一
- [ ] F5: 键盘快捷键 window 级别
- [ ] F6: NewsFeed 后端分页
- [ ] F7: API 错误汇总提示
- [ ] F8: clean_symbol 合并
