# KNOWN ISSUES & ROADMAP — Beta 0.4.30

> 研发进度表与技术债记录。更新于 2026-04-06。

---

## ✅ Beta 0.4.x — 发布记录（2026-04-06 当天）

| 版本 | 日期 | 核心修复 |
|------|------|---------|
| v0.4.24 | 04-06 22:00 | QuotePanel `isMock: mock` ReferenceError（黑屏）|
| v0.4.25 | 04-06 22:40 | FullscreenKline `isFull is not defined` 重写（405行）|
| v0.4.26 | 04-06 23:02 | App.vue 重复Teleport移除+调试日志清理；IndexLineChart 恢复干净版 |
| v0.4.27 | 04-06 23:06 | IndexLineChart ChartToolbar 错误依赖修复（恢复 d8b9ce46）|
| v0.4.28 | 04-06 23:30 | 52w高低计算错误（hist DESC 排序取错252条）；hover 时 indexStats 保留 |
| v0.4.29 | 04-06 23:47 | Dashboard 布局滚动条+数字右对齐+快讯时间层级+柱状图颜色纠正 |
| v0.4.30 | 04-06 23:58 | DrawingCanvas locked/键盘快捷键/线段命中/ResizeObserver；FullscreenKline 键盘全支持 |

---

## 🔴 P0 — 未完成

### Issue #1：Force Refresh 无差异化错误提示

**状态**：⚠️ 未完成

**描述**：`POST /news/force_refresh` 在抓取失败时仍返回 HTTP 200 + 旧缓存，前端显示"✅ 刚刚更新"但数据实为过期。

**修复方向**：
- [ ] 后端返回 `{"error": "...", "items_stale": true, "total": N}`（N=旧缓存条数）
- [ ] 前端检测 `error` 字段，显示红色「⚠️ 抓取失败，显示 {N} 条旧数据」
- [ ] 前端设置 5s 请求超时

---

### Issue #2：全市场个股名称未同步（已有数据源）

**状态**：✅ 已修复（后端使用 akshare stock_info_a_code_name，/api/v1/market/symbols 返回全量A股名称）

**涉及文件**：
- 后端：`backend/app/routers/market.py`（`/api/v1/market/symbols` 路由）
- 前端：`frontend/src/composables/useMarketStore.js`（`symbolRegistry`）

---

### Issue #3：涨跌家数空白（数据源缺失）

**状态**：⚠️ 数据源待接入

**描述**：后端 `quote_detail` 返回 `advance_count: null`，前端"涨跌统计"卡片空白。

**根因**：沪深交易所不直接开放涨跌家数实时接口，需通过东方财富等第三方。

**修复方向**：
- [ ] 接入东方财富 A 股涨跌统计接口（`push_stock_stat_sina` 或同效接口）
- [ ] 后端计算并缓存：`{ advance_count, decline_count, unchanged_count, advance_rate }`
- [ ] 前端 QuotePanel 展示横向红绿比例条

---

### Issue #4：成交额/换手率/振幅 字段为空

**状态**：⚠️ 部分完成

**根因**：
- `market_data_daily` 表无 `amount` 列（AkShare 日K返回数据不含此字段）
- `get_price_history` 查询 symbol 前缀不匹配（`sh000001` vs `000001`）

**修复方向**：
- [ ] 扩展 `buffer_insert_daily` 加入 `amount`/`turnover_rate`/`amplitude` 字段
- [ ] 修复 symbol 前缀匹配逻辑

---

## 🟡 P1 — 中期功能

### Issue #5：条件选股

**描述**：现有 StockScreener 只有展示功能，无筛选能力。

**方向**：增加价格/换手率/涨跌幅/市值区间过滤。

---

### Issue #6：画线工具完善

**状态**：⚠️ 进行中

**已完成**：locked 状态、键盘快捷键、线段命中高亮、ResizeObserver

**待完成**：
- [ ] 右键菜单替代 `confirm()` 对话框
- [ ] 选择/移动模式（切换工具而非每次绘制）
- [ ] 文本标注改内联输入框

---

### Issue #7：模拟组合

**描述**：无持仓管理、盈亏计算功能。

**方向**：localStorage 存储虚拟持仓，计算浮动盈亏。

---

## 🟢 P2 — 长期功能

### Issue #8：全球市场数据

- 美股指数（纳斯达克、标普500）实时行情
- 恒指期货主力合约
- 欧股/日股指数

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
| 4 | KNOWN_ISSUES_TODO.md 文档滞后 | 根目录 | ✅ 更新至 v0.4.30（v0.4.31）|
| 5 | 全局无单元测试 | backend/ | ⚠️ 待建立 |
| 6 | 后端无统一错误码/日志规范 | backend/app/ | ⚠️ 待建立 |
