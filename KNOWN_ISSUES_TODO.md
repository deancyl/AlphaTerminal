# KNOWN ISSUES & ROADMAP — Beta 0.4.34

> 研发进度表与技术债记录。更新于 2026-04-07。

---

## ✅ Beta 0.4.x — 发布记录

| 版本 | 日期 | 核心修复 |
|------|------|---------|
| v0.4.34 | 04-07 07:40 | `_normalize_symbol` 上证指数归类/sh000858→sz000858/_clean_symbol removeprefix |
| v0.4.33 | 04-07 00:30 | 新浪财经板块API替代AkShare Eastmoney（84行业+175概念，httpx直连CDN）|
| v0.4.32 | 04-06 | quote_detail接入SpotCache涨跌家数（advance/decline/unchanged）|
| v0.4.31 | 04-06 | market.py清理死代码（usdcnh/fetched/重复fallback）|
| v0.4.30 | 04-06 23:58 | DrawingCanvas locked/键盘快捷键/线段命中/ResizeObserver；FullscreenKline 键盘全支持 |
| v0.4.29 | 04-06 23:47 | Dashboard 布局+快讯时间层级+柱状图颜色 |
| v0.4.28 | 04-06 23:30 | 52w高低计算DESC排序修复；hover时indexStats保留 |
| v0.4.27 | 04-06 23:06 | IndexLineChart ChartToolbar错误依赖修复 |
| v0.4.26 | 04-06 23:02 | App.vue重复Teleport移除+调试日志清理 |
| v0.4.25 | 04-06 22:40 | FullscreenKline重写（405行），isFull ReferenceError |
| v0.4.24 | 04-06 22:00 | QuotePanel `isMock` ReferenceError（黑屏）|

---

## ✅ P0 — 已完成

### Issue #1：Force Refresh 无差异化错误提示

**状态**：✅ 已修复（v0.4.34之前）

**实现**：
- 后端 `POST /news/force_refresh` 失败时返回 **HTTP 500**（非200）
- 响应体包含 `{"error": "...", "items_stale": true, "stale_count": N}`
- 前端检测 `error` 字段显示红色警告

**涉及文件**：`backend/app/routers/news.py` 第67-78行

---

### Issue #2：全市场个股名称未同步

**状态**：✅ 已修复（v0.4.30+）

**修复方案**：`/api/v1/market/symbols` 懒加载全市场A股（akshare `stock_info_a_code_name`），结果缓存于内存，API直接返回。

**涉及文件**：
- 后端：`backend/app/routers/market.py`（`_load_all_stock_names()` + `/market/symbols` 路由）
- 前端：`frontend/src/composables/useMarketStore.js`（`symbolRegistry`）

---

### Issue #3：涨跌家数空白

**状态**：✅ 已修复（v0.4.32）

**修复方案**：从 `SpotCache.get_histogram()`（Sina HQ 全市场实时股票池，每3分钟刷新）读取 `advance/decline/unchanged`，接入 `quote_detail` 接口返回给前端 QuotePanel，展示横向红绿比例条。

---

## 🟡 P1 — 进行中 / 待处理

### Issue #4：成交额/换手率/振幅 字段为空

**状态**：⚠️ 部分完成

**根因**：
- `market_data_daily` 表无 `amount` 列（AkShare 日K返回数据不含此字段）
- symbol 前缀匹配逻辑（`_unprefix` 已修复）

**修复方向**：
- [ ] 扩展 `buffer_insert_daily` 加入 `amount` / `turnover_rate` / `amplitude` 字段
- [ ] 日K历史数据回填时补充上述字段

---

### Issue #5：条件选股

**状态**：⚠️ 待开发

**方向**：增加价格/换手率/涨跌幅/市值区间过滤。

---

### Issue #6：画线工具完善

**状态**：⚠️ 进行中

**已完成**：locked 状态、键盘快捷键、线段命中高亮、ResizeObserver、range-select

**待完成**：
- [ ] 右键菜单替代 `confirm()` 对话框
- [ ] 选择/移动模式（切换工具而非每次绘制）
- [ ] 文本标注改内联输入框

---

### Issue #7：模拟组合

**状态**：⚠️ 待开发

**方向**：localStorage 存储虚拟持仓，计算浮动盈亏。

---

## 🟢 P2 — 长期功能

### Issue #8：全球市场数据
- 港股期货主力合约
- 欧股/日股指数实时行情

### Issue #9：技术指标扩展
- RSI、DMI、OBV、SAR 等新指标
- 多周期 K 线同时展示（日+周+月）
- 指标参数自定义

### Issue #10：回测框架
- 接入 akshare 历史数据
- 均线策略回测（买入/卖出信号）
- 绩效统计（收益率、夏普比率、最大回撤）

---

## 📝 技术债

| # | 债项 | 位置 | 清理状态 |
|---|------|------|---------|
| 1 | market.py `fetched` 死变量 | `_get_macro_data()` | ✅ 已删除（v0.4.31）|
| 2 | market.py `usdcnh_price` 未使用 | `_get_macro_data()` | ✅ 已删除（v0.4.31）|
| 3 | market.py 静态 fallbacks 被立即覆盖 | `_get_macro_data()` | ✅ 已合并（v0.4.31）|
| 4 | `_SYMBOL_REGISTRY` sh000858/sh002594 前缀错误 | market.py | ✅ 已修复（v0.4.34）|
| 5 | `_normalize_symbol` 上证指数错误归为sz | market.py | ✅ 已修复（v0.4.34）|
| 6 | `_clean_symbol` replace误删中间子串 | market.py | ✅ 已修复（v0.4.34）|
| 7 | KNOWN_ISSUES_TODO.md 文档滞后 | 根目录 | ✅ 更新至 v0.4.34（本次）|
| 8 | 全局无单元测试 | backend/ | ⚠️ 待建立 |
| 9 | 后端无统一错误码/日志规范 | backend/app/ | ⚠️ 待建立 |
