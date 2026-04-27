# KNOWN ISSUES & ROADMAP — Beta v0.5.169

> 研发进度表与技术债记录。更新于 2026-04-27。
> 涵盖 v0.5.4 → v0.5.169 共 **完整审计** 的完整 Epic 记录。

---

## ✅ Beta v0.5.x — Release 记录

| 版本 | 日期 | 核心成果 |
|:---|:---:|:---|
| v0.5.169 | 04-27 | 第二轮全面审计修复：SQL注入防护、API密钥掩码、连接泄漏修复、Sharpe比率正确计算、符号规范化、前端logger统一 |
| v0.5.168 | 04-27 | 全面代码审计 + 修复 startQuotePolling 函数定义 + 版本号统一 + console 清理 |
| v0.5.167 | 04-19 | 验证48个问题全部修复/无需修复 |
| v0.5.113 | 04-18 | 回测看板可见性增强 + 图表-表格联动 |
| v0.5.109 | 04-18 | 回测看板重新设计 + 组合联动 |
| v0.5.97 | 04-15 | Admin 状态持久化（SQLite admin_config 表）|
| v0.5.91 | 04-14 | FundFlowPanel 硬核重写 + StockScreener 深度 watch + 价格/市值过滤 |
| v0.5.81 | 04-13 | BaseKLineChart 双 Y 轴 + buildOverlaySeries() 统一数据中枢 |
| v0.5.72 | 04-12 | StockScreener 服务端搜索 API + useDebounceFn |
| v0.5.71 | 04-12 | `/market/stocks/search` 后端 API（支持过滤/排序/分页）|
| v0.5.67 | 04-11 | Admin Dashboard WebSocket 实时日志流 + 等级过滤 |
| v0.5.57 | 04-10 | AI Copilot 真实 LLM 集成 + 上下文感知 Prompt |
| v0.5.55 | 04-10 | Task 9：组合归因 + 风险分析引擎（VaR / 波动率 / 夏普）|
| v0.5.54 | 04-10 | Task 8：回测引擎 + 信号可视化 |
| v0.5.53 | 04-09 | Task 7：股债双轴叠加对比 |
| v0.5.52 | 04-09 | 数据源抽象层 Phase 2 + Circuit Breaker 熔断器 |
| v0.5.46 | 04-08 | Phase 9 债券深度分析（隐含税率 + 历史分位弹窗 + 10Y-2Y 利差图）|
| v0.5.42 | 04-08 | K线引擎重构 + ΔOI 量价仓联动 + 债券历史曲线 + 期限结构 |
| v0.5.33 | 04-07 | logger 工具统一替换 + Pinia 迁移 + FOUC 修复 |
| v0.5.22 | 04-07 | WebSocket 前端集成（AdvancedKlinePanel + FullscreenKline）|
| v0.5.4 | 04-06 | 后端 WebSocket 行情推送链路打通 |

---

## 🔴 P0 — 已完成（Critical Bug Fixes）

### Issue #NEW1：SQL注入防护缺陷
**严重程度**：🔴 极高
**状态**：✅ 已关闭（v0.5.169）

**根因**：`admin.py` 中数据库统计查询使用字符串格式化拼接表名。
**修复**：添加表名白名单校验 `_ALLOWED_TABLES`，仅允许访问授权表。

---

### Issue #NEW2：API密钥日志泄露
**严重程度**：🔴 极高
**状态**：✅ 已关闭（v0.5.169）

**根因**：`copilot.py` 中 DeepSeek API 调用日志输出密钥前10字符。
**修复**：使用 `_mask_key()` 函数掩码处理，仅显示前后各若干字符。

---

### Issue #NEW3：Portfolio连接泄漏
**严重程度**：🔴 高
**状态**：✅ 已关闭（v0.5.169）

**根因**：`portfolio.py` 中 `portfolio_pnl` 函数在 `finally` 关闭 `conn` 后，又使用该连接执行查询。
**修复**：使用新的独立连接 `_conn_txn` 执行当日盈亏查询。

---

### Issue #NEW4：符号规范化使用replace而非removeprefix
**严重程度**：🔴 高
**状态**：✅ 已关闭（v0.5.169）

**根因**：`_normalize_symbol` 使用 `replace()` 去除市场前缀，会误删符号中部的 'sh'/'sz' 等子串。
**修复**：改用 `startswith()` + `removeprefix` 模式仅去除头部前缀。

---

### Issue #NEW5：Sharpe比率计算错误
**严重程度**：🔴 高
**状态**：✅ 已关闭（v0.5.169）

**根因**：`backtest.py` 中 Sharpe = 年化收益率 / 最大回撤，这是数学错误（应除以波动率）。
**修复**：基于收益率序列计算标准差，正确计算年化波动率后求 Sharpe。

---

### Issue #11：`useMarketStream` 内存泄漏
**严重程度**：🔴 高  
**状态**：✅ 已关闭（v0.5.92）

**根因**：`connect(sym)` 只增不减，`unsubscribe` 缺失，`globalTicks` / `tickHistory` 永不清理。  
**修复**：引入引用计数 + `unsubscribe()` 函数，切换标的时自动清理旧 symbol。

---

### Issue #12：版本号单一事实来源
**严重程度**：🔴 高  
**状态**：✅ 已关闭（v0.5.92）

**根因**：前端 `package.json` 和后端 `version.py` 两处维护，不同步导致混淆。  
**修复**：`backend/version.py` 作为唯一 Source of Truth，前端通过 `GET /api/v1/status` 运行时获取。

---

### Issue #13：代理 IP 硬编码
**严重程度**：🔴 高  
**状态**：✅ 已关闭（v0.5.92）

**根因**：`proxy_config.py` 及其他文件存在 `192.168.1.50` 硬编码 IP。  
**修复**：所有代理配置统一走 `HTTP_PROXY` / `HTTPS_PROXY` 环境变量，代码无硬编码。

---

## 🟡 P1 — 已完成（Core Features）

### Issue #14：StockScreener 虚拟滚动性能
**状态**：✅ 已关闭（v0.5.92）

**实现**：
- 后端 `GET /api/v1/market/stocks/search`（过滤/排序/分页）
- 前端 `StockScreener.vue` 接入 `useDebounceFn` 防抖
- 支持市值、涨跌幅、换手率、PE 等多维过滤

---

### Issue #15：ECharts ResizeObserver + dispose
**状态**：✅ 已关闭（v0.5.92）

**根因**：组件卸载时 ECharts 实例未 `dispose()`，ResizeObserver 未清理。  
**修复**：`onUnmounted` 中调用 `echartsInstance.dispose()`，`useResizeObserver` 统一生命周期管理。

---

## 🟢 P2 — 已完成（Enhanced Features）

### Issue #17：DrawingCanvas 状态机 + 内联文本编辑
**状态**：✅ 已关闭（v0.5.92）

**实现**：
- 画线工具状态机（绘制 / 选择 / 移动模式切换）
- 内联文本标注（点击文本工具后在 K 线图上直接输入）
- 键盘快捷键（Delete 删除选中 / Esc 取消）
- 右键菜单替代 `window.confirm()` 弹窗

---

### Issue #18：DB 写入队列 — 生产者/消费者模式
**状态**：✅ 已关闭（v0.5.92）

**实现**：`DBWriterThread` 后台线程队列，所有 DB 写操作异步化，不阻塞主请求线程。

---

### P2 Feature：统一 API 拦截器 + 熔断器 UI
**状态**：✅ 已完成（v0.5.52）

**实现**：
- `api.js` 全局拦截器，HTTP 失败时 exponential backoff 重试
- `useCircuitBreaker` composable，后端 API 级熔断状态可视化
- 单数据源失败不影响全页面，其他源自动接管

---

## 🎯 Epic 记录（v0.5.4 → v0.5.117）

### Epic 1 — 核心行情 & WebSocket 实时推送（v0.5.4 ~ v0.5.22）
| 提交 | 成果 |
|:---|:---|
| `d193693` | 后端 WebSocket 行情推送链路打通 |
| `ee3d8db` | 前端 WebSocket 集成 — `shallowRef` + HTTP 降级熔断 |
| `cc053d8` | AdvancedKlinePanel WebSocket 实时报价接入 |
| `7c11209` | FullscreenKline WebSocket 集成 |

### Epic 2 — 技术分析指标 & 画线工具（v0.5.23 ~ v0.5.40）
| 提交 | 成果 |
|:---|:---|
| `364604a` | DMI / OBV 技术指标 |
| `968d100` | 跨品种叠加对比功能 |
| `4e06629` | 画线工具选择 / 移动模式 |
| `8313080` | Level 2 十档买卖盘口 API |
| `193fac5` | 资金流向数据 API |

### Epic 3 — 数据源抽象层（v0.5.36 ~ v0.5.52）
| 提交 | 成果 |
|:---|:---|
| `9110688` | 数据源抽象层 Phase 1 — FetcherFactory 接口 |
| `94028ac` | 数据源管理 API Phase 2 |
| `1342735` | `quote_v2` 端点 + FetcherFactory |
| `e2da24a` | EastmoneyFetcher 实现 |
| `f068a2f` | TencentFetcher 实现 |
| `f2a72e6` | Circuit Breaker 熔断器模式 |

### Epic 4 — 投资组合 & 回测引擎（v0.5.53 ~ v0.5.68）
| 提交 | 成果 |
|:---|:---|
| `bef7d9b` | 股债双轴叠加对比 |
| `ef9db58` | 回测引擎 + 信号可视化 |
| `e1c1616` | 组合归因 + 风险分析（VaR / 波动率 / 夏普比率）|
| `7e49be6` | AI Copilot 真实 LLM 集成 + 上下文感知 Prompt |
| `b9642cd` | Admin Dashboard WebSocket 实时日志流 |

### Epic 5 — UI/UX 深化 & Sprint 7–9 重构（v0.5.69 ~ v0.5.94）
| 提交 | 成果 |
|:---|:---|
| `e54f046` | StockScreener 服务端搜索 API + useDebounceFn |
| `777da6a` | 全局 `console.*` → `logger` 统一替换（9 文件 33 处）|
| `30cdac8` | BaseKLineChart 双 Y 轴 + buildOverlaySeries() |
| `21709f6` | FundFlowPanel 硬核重写 + StockScreener 深度 watch |
| `c6ef214` | 指数 amplitude 计算修复 + BondDashboard Mock 警告 |
| `4144aff` | FundFlowPanel chart collapse + ResizeObserver |

### Epic 6 — 回测看板重构 & PortfolioStore 修复（v0.5.109 ~ v0.5.117）
| 提交 | 成果 |
|:---|:---|
| `21b5f84` | 回测看板重新设计 + 组合联动 |
| `1659629` | `portfolioStore.portfolios` computed `.value` 移除 |
| `7e5ab9f` | PortfolioDashboard 所有 store 属性 `.value` 滥用修复 |
| `dc81aaf` | `fetchPortfolios` async/await + 显式响应式追踪 |
| `88f0cd4` | 股票/组合双模式 + symbol 自动前缀补全（normalizeSymbol）|

---

## 🟢 P3 — 已完成（Advanced Features）

### Task 7：股债双轴叠加对比
**状态**：✅ 已完成（v0.5.53）

将 A 股指数与债券收益率叠加在同一坐标系，ECharts dual-y-axis 归一化。

### Task 8：回测引擎
**状态**：✅ 已完成（v0.5.54）

均线交叉 / RSI 超卖 / 布林带三大策略，支持窗口期选择、初始资金配置、基准对比。

### Task 9：组合归因 & 风险分析
**状态**：✅ 已完成（v0.5.55）

底层资产归因（A股/债券/商品/港股分类），VaR(95%)、年化波动率、夏普比率。

### Task 10：Level 2 盘口
**状态**：✅ 已完成（v0.5.40）

十档买卖盘口实时数据，前端降级为五档展示。

### Task 11：AI Copilot
**状态**：✅ 已完成（v0.5.57）

接入真实 LLM API，支持市场分析、新闻摘要、标的选择建议。

---

## 🔴 战役 4：跨品种叠加对比（Cross-Asset Overlay）
**状态**：✅ 已完成（v0.5.53）→ 融入 Epic 4

股债跷跷板研究：沪深300 + 10年期国债收益率叠加，ECharts dual-y-axis 归一化。

---

## ⚠️ 已知限制（AkShare 数据源）

| 限制项 | 影响范围 | 应对 |
|:---|:---|:---|
| 债券曲线停更至 2021-01-22 | BondDashboard | 使用 Mock 静态数据，⚠️ 标签提示 |
| IF/IC/IM 期货期限结构 | FuturesPanel | 仅支持商品期货（AU/AG 等）|
| 指数 realtime volume | 指数 K 线 | Sina 不提供指数成交量，volume=0 |
| Copilot 无 API Key | AI Copilot | Mock 模式运行，待用户配置 |

---

## 📝 技术债

| # | 债项 | 位置 | 状态 |
|:---:|:---|:---|:---:|
| 1 | SQLite 禁止放 SSHFS/FUSE 网络盘 | database.py | ✅ 已在文档注明 |
| 2 | 全局无单元测试 | backend/ | ⚠️ 待建立 |
| 3 | 后端无统一错误码规范 | backend/app/ | ⚠️ 待建立 |
| 4 | AkShare 债券数据停更 | bond.py | ✅ 已优雅降级（akshare → Mock fallback） |
| 5 | 子账户（parent_id）支持完整联动 | portfolio.py | ⚠️ 进行中 |
| 6 | 回测支持港股/美股 symbol | backtest.py | ⚠️ 待扩展 |
| 7 | 前端无 E2E 测试 | frontend/ | ⚠️ 待建立 |

---

## 📊 API 健康状态（v0.5.117）

| 端点 | 状态 | 备注 |
|:---|:---:|:---|
| `/api/v1/market/overview` | ✅ | |
| `/api/v1/market/history/{symbol}` | ✅ | amplitude 计算已修复 |
| `/api/v1/market/sectors` | ✅ | 84 行业 + 175 概念 |
| `/api/v1/market/futures/term_structure` | ✅ | 仅商品期货 |
| `/api/v1/portfolio/` | ✅ | 主账户 + 子账户完整支持 |
| `/api/v1/portfolio/{id}/positions` | ✅ | 含 sh/sz 前缀自动推断 |
| `/api/v1/portfolio/{id}/pnl` | ✅ | SpotCache + DB兜底 |
| `/api/v1/backtest/run` | ✅ | |
| `/api/v1/bond/curve` | ⚠️ | AkShare 停更，使用 Mock |
| `/api/v1/copilot/status` | ✅ | Mock 模式运行 |
| `/api/v1/status` | ✅ | 版本信息单一来源 |

---

## 🚀 Roadmap — 待完成

| 优先级 | 功能 | 状态 |
|:---:|:---|:---:|
| P1 | 回测支持港股/美股 symbol | 待开始 |
| P1 | 子账户持仓联动（组合选择后自动合并子账户 PnL）| 进行中 |
| P2 | 宏观数据面板（GDP/CPI/PMI）| 待开始 |
| P2 | 新闻情感打分与股价相关性分析 | 待开始 |
| P3 | 量化策略参数优化（Grid Search）| 待开始 |
| P3 | 回测结果历史记录持久化 | 待开始 |
| long-term | 夜盘期货连续合约处理 | 待研究 |
| long-term | 美股 Options 链条 | 待研究 |
