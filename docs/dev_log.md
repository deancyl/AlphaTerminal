# AlphaTerminal 开发日志 (dev_log)

## 2026-04-09 v0.4.109 - 今日K线数据实时入库修复

### 问题描述
指标图表模块中K线显示"上一日及之前的数据"，今日数据缺失。

### 根因分析
1. `market_data_daily` 仅在后端启动时通过 `initial_backfill` 回填
2. `initial_backfill` 没有日志跟踪，执行状态不明
3. `market_data_daily` 没有定时刷新任务
4. AkShare 数据本身可用（今日4/9数据可正常获取）

### 修复内容 (scheduler.py)
1. `initial_backfill` 添加 try/except 日志
2. 新增 `today_daily_refresh` 任务，每5分钟刷新主要指数日K线
3. 确保今日数据在交易时段内定期入库

### 验证结果
```
K线API: 2026-04-09 close=3966.171 ✅
风向标: 上证指数 3966.1712 (-0.72%) ✅
```

---

## 2026-04-09 v0.4.108 - 国内指数/新闻数据展示修复

### 关键Bug修复
App.vue 数据提取逻辑中三元运算符优先级问题
```javascript
// 错误: a || b || Array.isArray(c) ? c : []
// 正确: a || b || (Array.isArray(c) ? c : [])
```
导致 chinaAllData/newsData 被错误赋值为整个对象而非数组。

---

## 2026-04-09 v0.4.107 - P0问题修复

### 用户反馈5个问题
1. ✅ K线数据非实时 - 添加30秒自动刷新
2. ❌ WebLLM加载失败 - VK_ERROR_UNKNOWN 显卡硬件限制
3. ⚠️ 投资组合功能待完善 - 需后续开发
4. ✅ 国内指数数据缺失 - 运算符优先级Bug修复
5. ✅ 股票名称宽度过宽 - 添加max-w-[80px] truncate

### WebLLM说明
`VK_ERROR_UNKNOWN` 表示显卡不支持 WebGPU Compute Shaders，无法通过代码修复。
建议使用云端模式（已自动检测并禁用WebLLM）。

---

## 2026-03-31 初始化

### 后端端口配置
- 后端端口：8002
- 前端端口：60100（Vite dev server）
- API 基础路径：`/api/v1`

### 进程状态
| 进程 | 端口 | 状态 |
|------|------|------|
| uvicorn (backend) | 8002 | ✅ 运行中 |
| vite (frontend) | 60100 | ✅ 运行中 |

## v0.4.116 — 2026-04-10

### 修复
- `usePortfolioStore.js` + `PortfolioDashboard.vue`: 修复 `snapshots.map is not a function`（ref 未 .value）
- `StockScreener.vue`: 修复全市场个股 price/chg_pct/turnover 为0（字段兼容）
- `StockScreener.vue`: 扩大加载至30页(6000条)覆盖全市场5494只
- `StockScreener.vue`: 股票名称列宽收紧至72px

### 发布
- GitHub Release: https://github.com/deancyl/AlphaTerminal/releases/tag/v0.4.116
- Git Tag: v0.4.116

## v0.4.117 — 2026-04-10

### 修复
- **API响应格式统一**: 消除 `{error:xxx}` 直接返回
- `market.py`: 统一使用 success_response/error_response
- `futures.py`: 统一响应格式
- `news.py`: 修复语法错误

### 发布
- GitHub Release: https://github.com/deancyl/AlphaTerminal/releases/tag/v0.4.117
- Git Tag: v0.4.117 (创建中)

### 状态
- 后端: 运行中
- 前端: 运行中

## v0.4.120 — 2026-04-10

### 修复
- API字段标准化层 - 统一price/turnover等字段兼容
- 添加 FIELD_MAP 字段映射表
- 添加 normalizeFields()

### 发布
- GitHub Release: https://github.com/deancyl/AlphaTerminal/releases/tag/v0.4.120
- Git Tag: v0.4.120

### 验证
- 日线/周线/月线/分时: 正常

## v0.4.124 — 2026-04-10

### 修复
- 全市场个股 `change` 字段自动计算
- 快讯轮询从 5 分钟缩短到 2 分钟
- 每 6 分钟执行一次 force_refresh 穿透刷新

### 发布
- GitHub Release: https://github.com/deancyl/AlphaTerminal/releases/tag/v0.4.124
- Git Tag: v0.4.124

## v0.4.126 — 2026-04-10

### 修复
- 市场情绪涨跌家数改为全市场真实统计（5497只）
- SpotCache 失败后自动 fallback 到 market_all_stocks

### 发布
- GitHub Release: https://github.com/deancyl/AlphaTerminal/releases/tag/v0.4.126
- Git Tag: v0.4.126

---

## v0.5.117 — 2026-04-19

### 修复：回测看板 Portfolio 联动链路断裂
- 子账户无法出现在下拉框（`!p.parent_id` 过滤移除）
- 持仓标签 symbol 格式断裂（`normalizeSymbol()` 自动推断 A 股前缀）
- `store.positions.value` / `store.activePid.value` 多加 `.value`（reactive 已自动解包）
- `fetchPortfolios` 未 await，导致首次渲染数据未就位

### 新增：股票 / 组合双模式切换
- 左侧面板「**股票 | 组合**」切换标签
- 组合模式支持主账户 + 所有子账户下拉
- 持仓标签点击自动补全市场前缀并执行回测

### 发布
- GitHub Release: https://github.com/deancyl/AlphaTerminal/releases/tag/v0.5.117
- Git Tag: v0.5.117

---

## v0.5.113 — 2026-04-18

### 回测看板可见性增强 + 图表-表格联动
- 回测结果区域新增核心指标行（收益率/年化/最大回撤/胜率/夏普/盈亏比）
- 策略体检报告（评级 + 策略 vs 基准对比）
- 点击交易记录行，K 线图自动定位到对应日期

---

## v0.5.109 — 2026-04-18

### 回测看板重新设计 + 组合联动
- 重新设计回测看板左侧参数面板
- 策略规则提示根据所选策略动态切换
- 从投资组合导入持仓，一键回测

---

## v0.5.97 — 2026-04-15

### Admin 状态持久化
- 新增 `admin_config` SQLite 表，熔断器/调度器状态持久化
- 熔断状态重启后不丢失

---

## v0.5.92 — 2026-04-13

### 综合审计修复（评分 7.5/10）
- Issue #11：`useMarketStream` 引用计数 unsubscribe 修复
- Issue #12：版本号单一事实来源（`backend/version.py`）
- Issue #13：收口所有 192.168.1.50 代理硬编码
- Issue #14：StockScreener 虚拟滚动（`useVirtualList`）
- Issue #15：ECharts ResizeObserver + dispose
- Issue #17：DrawingCanvas 状态机 + 内联文本编辑
- Issue #18：DB 写入队列（`DBWriterThread`）
- P2 feat：API 拦截器 + 熔断器 UI

---

## v0.5.91 — 2026-04-14

### Sprint 9：FundFlowPanel 硬核重写 + StockScreener 深度 watch
- FundFlowPanel 数据驱动渲染，24h 资金流向支持
- StockScreener 价格/市值过滤器深度 watch 优化
- 后端 SQL 补充市值字段

---

## v0.5.81 — 2026-04-13

### BaseKLineChart 双 Y 轴 + buildOverlaySeries()
- `chartDataBuilder.js` 新增 `buildOverlaySeries()`，支持双 Y 轴叠加
- BaseKLineChart 接入 dual Y-axis + 混合 Tooltip formatter

---

## v0.5.72 — 2026-04-12

### StockScreener 服务端搜索
- 后端 `GET /api/v1/market/stocks/search`（支持多维过滤/排序/分页）
- 前端接入 `useDebounceFn` 防抖，500ms 延迟触发搜索

---

## v0.5.57 — 2026-04-10

### AI Copilot 真实 LLM 集成
- 接入真实 LLM API（需配置 API Key）
- 上下文感知 Prompt 注入（市场数据 + 新闻 + 持仓）
- Mock 模式支持无 Key 运行

---

## v0.5.55 — 2026-04-10

### Task 9：组合归因 + 风险分析引擎
- 底层资产归因（A股/债券/商品/港股）
- VaR(95%)、年化波动率、夏普比率
- `GET /api/v1/portfolio/{id}/attribution`

---

## v0.5.54 — 2026-04-10

### Task 8：回测引擎 + 信号可视化
- 双均线 / RSI 超卖 / 布林带三大策略
- 支持自定义参数（快线/慢线周期、RSI 阈值等）
- 回测结果含交易记录、绩效统计

---

## v0.5.53 — 2026-04-09

### Task 7：股债双轴叠加对比
- ECharts dual-y-axis 归一化，沪深300 + 10年期国债叠加
- 股债跷跷板效应可视化

---

## v0.5.52 — 2026-04-09

### 数据源抽象层 Phase 2 + Circuit Breaker
- 三家 Fetcher（Eastmoney/Tencent/Sina）自动降级
- 熔断器连续失败自动切断，故障恢复自动重启
- 熔断统计 API（`/admin/circuit_status`）

---

## v0.5.4 — 2026-04-06

### 后端 WebSocket 行情推送链路打通
- SpotCache 每 3 分钟刷新全市场行情
- WebSocket 实时推送至前端 `useMarketStream.js`
- `shallowRef` 优化高频 Tick 更新性能

---

## v0.5.22 — 2026-04-07

### WebSocket 前端全面集成
- AdvancedKlinePanel WebSocket 实时报价
- FullscreenKline WebSocket 实时报价

---

*v0.5.4 → v0.5.117 共 141 次提交，详见 https://github.com/deancyl/AlphaTerminal/commits/master*
