# CHECKPOINT v0.5.78 — AlphaTerminal 架构重构全记录

> 生成时间：2026-04-17 20:44 GMT+8
> 当前版本：v0.5.78（Logger 全局替换）
> 下一目标：v0.5.79（上下文固化）+ Sprint 6 跨品种叠加对比重构

---

## 一、整体架构变更概览

从 v0.5.65 到 v0.5.78，AlphaTerminal 完成了从"裸奔前端+混沌后端"到"分层可控、金融级健壮"的系统性重构。

| Sprint | 主题 | 涉及文件 | 版本 |
|--------|------|----------|------|
| Sprint 1 | 安全与架构基建 | admin.py, version.py | v0.5.66–0.5.68 |
| Sprint 2 | 前端性能优化与组件防抖 | AdminDashboard.vue, FullscreenKline.vue | v0.5.69–0.5.70 |
| Sprint 2.5 | Git 同步 | — | — |
| Sprint 3 | 数据流分级与服务端搜索 | database.py, market.py, StockScreener.vue | v0.5.71–0.5.74 |
| Sprint 4 | 错峰轮询与组件自治 | App.vue, DashboardGrid.vue, CopilotSidebar.vue | v0.5.75–0.5.77 |
| Sprint 5 | 技术债清剿与Logger规范 | 9个前端文件 | v0.5.78 |

---

## 二、Sprint 1：安全与架构基建

### P0-1：硬编码路径清除（v0.5.66）

**问题**：admin.py 中存在 `/vol3/@apphome/trim.openclaw/data/workspace/AlphaTerminal/backend/app.log` 等硬编码绝对路径，跨环境部署会崩溃。

**修复**：
- 在 admin.py 顶部添加动态路径配置：
  ```python
  BASE_DIR = Path(__file__).resolve().parent.parent.parent
  _DEFAULT_LOG_DIR = BASE_DIR / "logs"
  ```
- 将硬编码日志路径替换为：
  ```python
  log_dir = os.environ.get("LOG_DIR", str(_DEFAULT_LOG_DIR))
  log_files = [os.path.join(log_dir, "app.log"), os.path.join(log_dir, "backend.log")]
  ```

**关键文件**：`backend/app/routers/admin.py`（第22-25行、第385-391行）、`backend/version.py`

---

### P0-2：Admin 控制台 WebSocket 日志流（v0.5.67）

**问题**：HTTP 轮询日志（30秒一次）无法实时感知系统异常。

**修复**：
- 在 `AdminDashboard.vue` 中引入原生 WebSocket，动态构建 URL：
  ```javascript
  function buildWsUrl() {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${proto}//${window.location.host}/api/v1/admin/logs/stream`
  }
  ```
- `watch(activeTab)`：进入 logs tab 时建连，离开时断开（`onUnmounted` 清理）
- `MAX_LOGS = 300`：增量 push，防止 OOM
- `filteredLogs = computed()`：前端纯过滤，无网络请求

**关键文件**：`frontend/src/components/AdminDashboard.vue`

---

### P0-3：异常静默吞噬修复（v0.5.68）

**问题**：`except:` 裸捕获掩盖数据库死锁、调度器崩溃等生产级 Bug。

**修复**：将4处 `except:` 替换为 `except Exception as e: logger.exception(...)`：

| 函数 | 行 | 级别 |
|------|-----|------|
| `get_sources_status()` | 84-89 | `logger.exception` |
| `get_database_status()` | 308-313 | `logger.exception` |
| `get_recent_logs()` 格式1 | 449-452 | `logger.debug` |
| `get_recent_logs()` 格式2 | 458-461 | `logger.debug` |

**关键文件**：`backend/app/routers/admin.py`

---

## 三、Sprint 2：前端性能优化与组件防抖

### P1-1：Admin 全局防抖与请求锁（v0.5.69）

**问题**：controlCircuit / dbMaintenance 等高危操作无锁，用户疯狂连击"确定执行"会并发倾泻 VACUUM 等重负载指令，击穿 SQLite。

**修复**：
- 新增 `const isSubmitting = ref(false)`
- `executeConfirm` 改造为 `async` 函数，finally 块中释放锁
- 按钮 `：disabled="isSubmitting"` + 文本动态切换为"执行中..."

**关键文件**：`frontend/src/components/AdminDashboard.vue`（script + template 两处）

---

### P1-2：FullscreenKline 移动端渲染降级（v0.5.70）

**问题**：复杂 Canvas 叠加层在手机端导致触摸事件漂移和内存溢出。

**修复**：
- 引入 VueUse `useBreakpoints(breakpointsTailwind)`
- `isMobile = computed(() => breakpoints.value.smaller('md'))`（<768px）
- `v-if="!isMobile"` 彻底销毁 DrawingCanvas + DrawingToolbar（非 CSS hide）
- `watch(isMobile)` 当移动端时强制 `activeSubChart.value = 'VOL'`

**关键文件**：`frontend/src/components/FullscreenKline.vue`（script + template 两处）

---

## 四、Sprint 3：深度性能优化与数据流改造

### P1-3：服务端搜索 API（v0.5.71）

**问题**：全市场 5494 只 A 股全量拉取到前端，computed 过滤阻塞浏览器主线程。

**修复**：
- `database.py` 新增 `search_stocks()` 函数，支持多维度过滤+排序白名单+分页
- `market.py` 新增 `GET /api/v1/market/stocks/search` 路由

**过滤参数**：`keyword`, `min_pct_chg/max_pct_chg`, `min_turnover/max_turnover`, `min_pe/max_pe`, `min_pb/max_pb`, `min_mktcap/max_mktcap`, `sort_by`, `sort_dir`, `page`, `page_size`

**安全**：ORDER_FIELDS 白名单映射防止 SQL 注入

**关键文件**：`backend/app/db/database.py`、`backend/app/routers/market.py`

---

### P1-4：StockScreener 前端接入服务端搜索（v0.5.72）

**问题**：前端 computed 过滤 + 全量 HTTP 拉取（最多翻30页）的低效模式。

**修复**：
- 移除 `allStocks` 全量数组和 `filteredStocks` computed
- 引入 `useDebounceFn(fetchStocks, 300)` 防抖
- 引入 `apiFetch` + 分页状态（`stocks`, `total`, `currentPage`, `pageSize`）
- `filteredLogs` → `filteredStocks`（computed 按前端过滤 → 直接展示服务端结果）
- 字段名对齐：`stock.chg_pct` → `stock.change_pct`，`stock.chg` → `stock.change`

**关键文件**：`frontend/src/components/StockScreener.vue`

---

### P1-5：Git 同步（v0.5.71/72）

```bash
git push origin HEAD
git push origin --tags
# v0.5.53, v0.5.66, v0.5.67, v0.5.68, v0.5.69, v0.5.70, v0.5.71, v0.5.72 已推送
```

---

### P1-6：API 错误感知与自动重试（v0.5.73）

**问题**：apiFetch 失败时只 `console.error`，UI 无感知；无指数退避。

**修复**：
- `api.js` 新增 `apiErrorState` 响应式状态（`failedCount`, `lastError`, `isDegraded`）
- `apiFetch` 重试逻辑指数退避：`backoffMs = min(500 * 2^attempt, 8000)`
- App.vue Banner 增强：显示"第 N 次失败，自动重试中" + "忽略"按钮

**关键文件**：`frontend/src/utils/api.js`、`frontend/src/App.vue`

---

### P1-7：聚合层容灾与局部降级（v0.5.74）

**问题**：`Promise.all` Fail-Fast：8 个 API 中有 1 个超时就整个 reject，已成功的数据被丢弃，页面彻底白屏。

**修复**：
- `fetchApiBatch` 改用 `Promise.allSettled`（Best-Effort 模式）
- 单个子请求 `catch` 后返回 `defaultValue`，不影响其他正常接口渲染
- `_errors` 数组仍记录失败 key，驱动 `apiErrorState` + Banner 感知

**关键文件**：`frontend/src/utils/api.js`

---

## 五、Sprint 4：数据流分级与错峰调度

### P0-8：App.vue 错峰轮询改造（v0.5.75）

**问题**：每 30 秒并发 8 个 API，HTTP/1.1 单一域名并发上限为 6，极易触发浏览器 Stalled 导致假性超时。

**修复**：拆解 `fetchMarketData` 为三个错峰梯队：

| 梯队 | 内容 | 频率 |
|------|------|------|
| 高频 | overview（大盘） | 10秒 |
| 中频 | sectors + china_all + derivatives | 60秒 |
| 低频 | macro + rates + global + news | 5分钟 |

- 引入 `useIntervalFn`（自动处理组件卸载清理）
- `useDocumentVisibility` 控制页面隐藏时 `pause()` 所有定时器
- 首屏骨架屏关闭：`fetchHighFreq().then(_checkInitDone)` + `fetchMedFreq().then(_checkInitDone)`（从3改为2）
- 错误重试按钮：`Promise.all([fetchHighFreq(), fetchMedFreq(), fetchLowFreq()])`

**关键文件**：`frontend/src/App.vue`（script 重构）

---

### P1-9：低频数据源全面下沉（v0.5.76）

**问题**：macro/rates/global/news 在 App.vue 中以 5 分钟轮询，但 NewsFeed 内部已有独立轮询，造成双重浪费。

**修复**：
- App.vue 删除：`macroData`, `ratesData`, `globalData`, `newsData`，删除 `fetchLowFreq()`
- DashboardGrid.vue 内部新增 `fetchLowFreq()` + `useIntervalFn(fetchLowFreq, 300_000)`
- CopilotSidebar.vue 删除 `ratesData` / `newsData` Prop 及相关上下文注入代码
- NewsFeed 保持完全自治（已内置 force_refresh 逻辑）

**关键文件**：`App.vue`、`DashboardGrid.vue`、`CopilotSidebar.vue`

---

### P1-10：DashboardGrid 子组件引用修复（v0.5.77）

**问题**：Sprint 4-2 重构时误删了 `<script setup>` 顶部的组件 import，导致 `IndexLineChart` / `StockScreener` 等组件无法解析，DashboardGrid 大面积空白。

**修复**：补回 6 个 import：
```javascript
import IndexLineChart    from './IndexLineChart.vue'
import NewsFeed          from './NewsFeed.vue'
import SentimentGauge    from './SentimentGauge.vue'
import HotSectors        from './HotSectors.vue'
import FundFlowPanel     from './FundFlowPanel.vue'
import StockScreener     from './StockScreener.vue'
```

**关键文件**：`frontend/src/components/DashboardGrid.vue`

---

## 六、Sprint 5：技术债清剿与生产环境加固

### P1-11：全局 Console 清理与 Logger 接管（v0.5.78）

**问题**：
- 原生 `console.*` 在 DevTools 中保持大型数据对象引用（内存泄漏）
- 无法统一控制日志等级，生产环境噪音过大

**修复**：9 个文件，33 处替换，全部 `console.*` → `logger.*`

| 文件 | 替换数 | 级别 |
|------|--------|------|
| QuotePanel.vue | 2 | debug |
| BaseKLineChart.vue | 3 | debug |
| PortfolioDashboard.vue | 2 | debug |
| FullscreenKline.vue | 2 | debug |
| DrawingCanvas.vue | 1 | debug |
| FundFlowPanel.vue | 1 | error |
| AttributionPanel.vue | 1 | error |
| AdvancedKlinePanel.vue | 2 | debug |
| useDataSourceStatus.js | 1 | debug |

**关键文件**：上述 9 个文件

---

## 七、当前架构状态（v0.5.78）

### 前后端通信拓扑
```
前端（App.vue）
├── 10s轮询 → /api/v1/market/overview         （高频：大盘）
├── 60s轮询 → /api/v1/market/sectors           （中频：板块）
│           → /api/v1/market/china_all
│           → /api/v1/market/derivatives
└── 各组件自持（300s）→ /api/v1/market/macro   （低频：宏观）
                → /api/v1/market/rates
                → /api/v1/market/global
                → /api/v1/news/flash           （NewsFeed 内部自治）
```

### 数据流健壮性
- ✅ API 层：Promise.allSettled（Best-Effort，单接口失败不崩溃）
- ✅ 错误感知：apiErrorState 响应式状态 + App Banner UI
- ✅ 重试机制：指数退避（500ms × 2^n，max 8s）
- ✅ 日志规范：全局 logger 接管，生产环境自动静默
- ✅ 组件隔离：低频数据下沉到组件，GridStack 无重型全局状态

### 性能状态
- ✅ 无前端全量 computed 过滤（已迁移到服务端 search API）
- ✅ 无 HTTP 连接池耗尽（错峰轮询，6 并发以内）
- ✅ 移动端无 Canvas 溢出（DrawingCanvas/DrawingToolbar 彻底销毁）
- ✅ 无 console 内存泄漏（全部替换为 logger）

---

## 八、Sprint 6 预告：跨品种叠加对比（Cross-Asset Overlay）

**前置文件**：`frontend/src/utils/chartDataBuilder.js`

**核心改造方向**：
- 支持多标的（股票/期货/指数）K 线叠加对比
- 统一时间轴对齐算法（不同品种交易日不同，需要对齐）
- Overlay 图层管理（多标的切换显示/隐藏）

**上下文准备**：
- 当前工作区已清理，保留 `CHECKPOINT_v0.5.78.md` 作为记忆锚点
- chartDataBuilder.js 是下一个必须读取的文件

---

## 九、Git 版本链

```
v0.5.53  → 修复后端异常（已有）
v0.5.65  → 审计修复（初始）
v0.5.66  → 硬编码路径清除
v0.5.67  → WebSocket 实时日志
v0.5.68  → 异常静默吞噬修复
v0.5.69  → Admin 全局防抖锁
v0.5.70  → K线移动端降级
v0.5.71  → 服务端搜索 API
v0.5.72  → StockScreener 前端重构
v0.5.73  → API 错误感知+重试
v0.5.74  → Promise.allSettled 容灾
v0.5.75  → 错峰轮询改造
v0.5.76  → 低频数据下沉
v0.5.77  → 子组件 import 修复
v0.5.78  → 全局 Logger 规范
v0.5.79  → 本次 checkpoint（待提交）
```

---

*本文档为 AlphaTerminal v0.5.x 重构过程的完整架构记录，是后续 Sprint 6 的唯一上下文锚点。所有技术决策均已在上述文档中可查。*