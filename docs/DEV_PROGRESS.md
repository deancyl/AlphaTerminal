# 开发进度记录

> 更新于 2026-04-19 · v0.5.117

---

## 当前版本

- **本地**：v0.5.117
- **GitHub**：v0.5.117 ✅ 已同步

---

## 开发阶段（v0.5.x）

### Phase 0 — 核心行情 & WebSocket（v0.5.4 ~ v0.5.22）
| 日期 | 版本 | 内容 |
|:---|:---:|:---|
| 04-06 | v0.5.4 | 后端 WebSocket 行情推送链路打通 |
| 04-07 | v0.5.22 | AdvancedKlinePanel + FullscreenKline WebSocket 集成 |

**完成**：WebSocket 实时行情 → GridStack 实时 K 线渲染

---

### Phase 1 — 数据源抽象层（v0.5.36 ~ v0.5.52）
| 日期 | 版本 | 内容 |
|:---|:---:|:---|
| 04-08 | v0.5.36 | FetcherFactory Phase 1 — 接口定义 |
| 04-08 | v0.5.37 | 数据源管理 API Phase 2 |
| 04-08 | v0.5.38 | quote_v2 + FetcherFactory |
| 04-09 | v0.5.39 | TencentFetcher 实现 |
| 04-09 | v0.5.40 | Circuit Breaker 熔断器模式 |
| 04-09 | v0.5.41 | 熔断器统计 API |
| 04-09 | v0.5.52 | Phase 3 完成，三家 Fetcher 自动降级 |

**完成**：数据源抽象层 + 自动熔断，单源故障不影响全页面

---

### Phase 2 — 投资组合 & 回测引擎（v0.5.53 ~ v0.5.68）
| 日期 | 版本 | 内容 |
|:---|:---:|:---|
| 04-09 | v0.5.53 | 股债双轴叠加对比（Epic 4）|
| 04-10 | v0.5.54 | 回测引擎 + 信号可视化 |
| 04-10 | v0.5.55 | 组合归因 + 风险分析（VaR/波动率/夏普）|
| 04-11 | v0.5.57 | AI Copilot 真实 LLM 集成 |
| 04-11 | v0.5.67 | Admin Dashboard WebSocket 实时日志流 |

**完成**：回测引擎 + 组合风险分析 + Copilot

---

### Phase 3 — Sprint 7–9 UI 重构（v0.5.69 ~ v0.5.94）
| 日期 | 版本 | 内容 |
|:---|:---:|:---|
| 04-11 | v0.5.69 | Admin 全局提交锁防重复提交 |
| 04-11 | v0.5.70 | FullscreenKline 移动端自适应 |
| 04-12 | v0.5.71 | `/market/stocks/search` 后端 API |
| 04-12 | v0.5.72 | StockScreener 服务端搜索 + useDebounceFn |
| 04-12 | v0.5.73 | 全局 API 错误暴露 + 指数退避重试 |
| 04-12 | v0.5.74 | fetchApiBatch Best-Effort 模式（`Promise.allSettled`）|
| 04-12 | v0.5.75 | App.vue 数据分级轮询（10s/60s/300s 三层）|
| 04-12 | v0.5.76 | 低频数据组件自管理，每 5 分钟刷新 |
| 04-12 | v0.5.78 | 全局 `console.*` → `logger` 统一替换（9 文件 33 处）|
| 04-13 | v0.5.80 | buildOverlaySeries() — dual Y-axis 数据构建器 |
| 04-13 | v0.5.81 | BaseKLineChart 双 Y 轴接入 |
| 04-13 | v0.5.82 | StockScreener 无限滚动修复（追加模式）|
| 04-13 | v0.5.83 | FundFlowPanel ResizeObserver + 显式分页 |
| 04-14 | v0.5.91 | FundFlowPanel 硬核重写 + StockScreener 深度 watch |
| 04-13 | v0.5.92 | 综合审计修复（评分 7.5/10）|

**完成**：StockScreener、FundFlowPanel、BaseKLineChart 双 Y 轴全面重构

---

### Phase 4 — 回测看板重构（v0.5.109 ~ v0.5.117）
| 日期 | 版本 | 内容 |
|:---|:---:|:---|
| 04-18 | v0.5.109 | 回测看板重新设计 + 组合联动 |
| 04-18 | v0.5.111 | 回测 UI 策略提示 + 输入反馈 + 空状态 |
| 04-18 | v0.5.112 | 多策略支持 + 基准对比评估 |
| 04-18 | v0.5.113 | 回测看板可见性增强 + 图表-表格联动 |
| 04-19 | v0.5.114 | PortfolioDashboard `.value` 滥用修复 |
| 04-19 | v0.5.115 | `fetchPortfolios` async/await + 响应式追踪修复 |
| 04-19 | v0.5.117 | **股票/组合双模式 + symbol 自动前缀补全** |

**完成**：PortfolioStore reactive 链路全面修复，回测看板可正式使用

---

## Issue 关闭状态

| Issue | 关闭版本 | 内容 |
|:---:|:---:|:---|
| #11 | v0.5.44 | useMarketStream 引用计数 unsubscribe |
| #12 | v0.5.46 | 版本号单一事实来源 |
| #13 | v0.5.45 | 收口 192.168.1.50 代理硬编码 |
| #14 | v0.5.48 | StockScreener 虚拟滚动 |
| #15 | v0.5.47 | ECharts ResizeObserver + dispose |
| #17 | v0.5.51 | DrawingCanvas 状态机 + 内联文本编辑 |
| #18 | v0.5.50 | DB 写入队列（DBWriterThread）|

---

## 技术债清理进度

- [x] api.js console 替换 → logger
- [x] App.vue console 替换 → logger
- [x] 其他组件 console 替换 → logger（9 文件 33 处）
- [x] 买卖盘口重构（简化保留基础功能）
- [x] 数据源自动熔断机制（Circuit Breaker）
- [ ] 单元测试框架搭建（待建立）
- [ ] SQLite 网络盘警告（已在文档注明）
- [ ] AkShare 债券数据源切换（待替换数据源）

---

## 下一步计划

| 优先级 | 功能 | 说明 |
|:---:|:---|:---|
| P1 | 回测支持港股/美股 symbol | 后端 backtest.py 扩展 |
| P1 | 子账户持仓合并展示 | 组合选择后聚合所有子账户持仓 |
| P2 | 宏观数据面板 | GDP/CPI/PMI 定时数据 |
| P2 | 新闻情感打分 | 情感与股价相关性分析 |
| P3 | 量化策略参数优化 | Grid Search |
| P3 | 回测历史记录持久化 | 写入 SQLite |
