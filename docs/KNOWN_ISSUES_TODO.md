# KNOWN_ISSUES_TODO.md

> Last updated: 2026-04-16 v0.5.46
> 维护者：架构评审 + openclaw

---

## 🔴 P0 — 紧急修复与内存治理

### Issue #11：WebSocket 内存泄漏（`useMarketStream.js` 缺少 `unsubscribe`）
**严重程度**：🔴 高 — 浏览器长时间运行内存持续增长，最终卡顿崩溃
**影响范围**：`frontend/src/composables/useMarketStream.js` + `backend/app/routers/ws.py`

**根因分析**：
- `connect(sym)` 每次调用都往 `subscribedSyms.add(s)` 追加，但**没有任何机制移除**已不再需要的 symbol
- 用户浏览股票 A → 切换到 B → B → C，`subscribedSyms` 集合只增不减
- `globalTicks[sym]` 和 `tickHistory[sym]` 永远不清理
- `disconnect()` 只在 `_connectedCount <= 0` 时才清空全部数据，但单个股票切换不会触发

**修复方案**：
1. 新增 `unsubscribe(symbols)` 函数（支持单 symbol 或数组）
2. `unsubscribe` 时从 `subscribedSyms` delete 该 symbol
3. `unsubscribe` 时从 `globalTicks` delete 该 symbol（`delete globalTicks.value[sym]`）
4. `unsubscribe` 时清理 `tickHistory[sym]`
5. `unsubscribe` 时向后端发送 `{"action": "unsubscribe", "symbols": [...]}`（需后端 ws.py 配合）
6. 后端 `ws_manager.py` 维护每个连接已订阅 symbol 列表，收到 unsubscribe 时停止推送
7. 组件内 `connect` 替换前自动调用旧 symbol 的 `unsubscribe`（或提供 `switchSymbol(newSym)` 封装）

**Ticket 验收标准**：
- [ ] 切换 10 只不同股票后，`subscribedSyms.size === 1`，`Object.keys(globalTicks).length === 1`
- [ ] 内存 profile 确认无持续增长
- [ ] 后端 ws.py 正确响应 unsubscribe 指令

**状态**：✅ 已完成（v0.5.44，commit a964471）
- `subscribedSyms Set` → `subscribedSymRefCount Map`（引用计数）
- 新增 `unsubscribe(symOrList)`：refcount 归零时精准清理 globalTicks + tickHistory + 后端通知
- `watch(localSymbol)` 自动 unsubscribe 切换前的旧股票
- `onUnmounted` 同时触发 unsubscribe(本地symbol) + disconnect(refcount -1)
- 后端 ws_manager.py 已有 unsubscribe 逻辑，无需修改

---

### Issue #13：收口数据源代理硬编码
**状态**：✅ 已完成（v0.5.45，commit e3b5fd3）
- 新增 `backend/app/services/proxy_config.py`：统一配置层
  - `get_proxy_url()` — 读环境变量 `HTTP_PROXY/http_proxy`，无硬编码
  - `build_httpx_proxies()` — 构造 httpx proxies dict，为空返回 None（直连）
  - `setup_environ()` — 同步代理到 os.environ（供 akshare 等库）
- `data_fetcher.py:701` — 硬编码 proxies → `get_proxies()`
- `news_fetcher.py:13` — `PROXY_YOUTUBE` → `get_proxy_url()`
- `quote_source.py` — `proxy_url` 置 null，`_get_proxy()` 走 `build_httpx_proxies()`
- Debug 测试：带代理 / 无代理 两种 Case 均通过

---

### Issue #12：全局版本号统一（Single Source of Truth）
**严重程度**：🟡 中 — 版本信息碎片化，Debug 时无法对齐基线
**影响范围**：`package.json`, `vite.config.js`, 各 `.vue` 组件, `README.md`, `KNOWN_ISSUES_TODO.md`

**根因**：版本号散落在 5+ 个文件中，无统一入口

**修复方案**：
1. `package.json` 的 `version` 字段作为唯一事实来源（当前值：`0.5.43`）
2. `vite.config.js` 中通过 `define` 注入：
   ```js
   define: {
     __APP_VERSION__: JSON.stringify(process.env.npm_package_version),
   }
   ```
3. 前端 UI（Navbar/Footer）统一使用 `{{ __APP_VERSION__ }}` 渲染，删除所有硬编码 "Beta v0.x.x"
4. CI/CD 或发布脚本每次打标签前自动更新 `package.json` version
5. `KNOWN_ISSUES_TODO.md` 顶部引用 `package.json` version，保持同步

**Ticket 验收标准**：
- [ ] `grep -r "v0\.5" frontend/src` 无匹配（硬编码清除）
- [ ] Navbar 显示版本号与 `package.json` 完全一致
- [ ] `README.md` 不含手动版本号（统一引用标签）

**状态**：✅ 已完成（v0.5.46，commit a0627f4）
- `vite.config.js`：Node.js `fs.readFileSync` 读 `package.json`，通过 `define` 注入 `__APP_VERSION__`
- `AdminDashboard.vue`：硬编码 `'0.4.138'` → `__APP_VERSION__`
- `package.json`：版本更新至 `0.5.45`
- `README.md`：Badge v0.4.133 → v0.5.45
- 构建验证：`grep` 确认 `__APP_VERSION__` 在 bundle 中被替换为 `'0.5.45'`

---

### Issue #13：收口数据源代理硬编码
**严重程度**：🔴 高 — 开源代码无法开箱运行，`192.168.1.50` 仅限局域网
**影响范围**：`backend/app/services/data_fetcher.py`, `backend/app/services/fetchers/*.py`

**根因**：代理 IP 散落在多处，未统一从环境变量读取

**修复方案**：
1. 建立统一配置层 `backend/app/config.py`，从 `.env` 或 `os.environ` 读取 `HTTP_PROXY` / `HTTPS_PROXY`
2. 所有 Fetcher 类（Sina/Tencent/Eastmoney）在实例化时从 `FetcherFactory` 注入代理配置，**不再各自单独写死**
3. `data_fetcher.py` 中的 `proxies = {"http://": "http://192.168.1.50:7897"}` 全部替换为 `os.environ.get("HTTP_PROXY")`
4. `.env.example` 模板文件中写入代理配置说明
5. GitHub README 添加代理配置说明段落

**Ticket 验收标准**：
- [ ] `grep -r "192.168.1.50" backend/` 无匹配
- [ ] `grep -r "7897" backend/` 无匹配（无硬编码端口）
- [ ] 在无代理环境下 `HTTP_PROXY="" python start_backend.py` 正常运行

---

## 🟡 P1 — 渲染性能与体验重构

### Issue #14：大数据列表接入虚拟滚动
**状态**：✅ 已完成（v0.5.48，commit f449a0a）
- `StockScreener.vue`：`useVirtualList` 替代 v-for + 分页
  - `ROW_HEIGHT=32px`，可视区 `400px` → 约 12-14 行同时渲染
  - `filteredStocks`：纯过滤（消除副作用seq赋值）
  - `filteredWithSeq`：隔离的排序+seq computed，不污染原始数据
  - 排序/过滤变化时自动滚动到顶部
  - 删除全部分页逻辑（goPage/prevPage/nextPage/visiblePages）
- `@vueuse/core` 已有 v12.4.0，无新依赖引入
- 构建验证：vendor-vue +4KB，7.10s

---

### Issue #15：ECharts 实例管理与 Resize 优化
**严重程度**：🟡 中 — 多 Grid 拖拽时 CPU 峰值高，存在内存泄漏隐患
**影响范围**：所有包含 ECharts 的 Vue 组件

**修复方案**：
1. 所有 `onUnmounted` 生命周期中显式调用 `chartInstance.dispose()`
2. 废弃 `window.addEventListener('resize')` 全量重绘
3. 引入 `ResizeObserver` API，仅对具体 Grid DOM 容器调用 `chartInstance.resize()`
4. 排查所有 `BaseKLineChart.vue` 及子组件，确保每图只有一个 ResizeObserver 实例

**Ticket 验收标准**：
- [ ] `onUnmounted` 中 `dispose()` 调用覆盖率 100%
- [ ] GridStack 拖拽时 CPU 占用下降 >= 40%
- [ ] 打开/关闭 K 线面板 10 次后，内存无累积增长

**状态**：✅ 已完成（v0.5.47，commit f4988fc）
- `BaseKLineChart.vue`：ResizeObserver 已存在，添加 debug logs
- `FullscreenKline.vue`：`window.addEventListener('resize')` → ResizeObserver on `chartEl.value`
- `QuotePanel.vue`：新增 ResizeObserver + dispose debug log
- `AdvancedKlinePanel.vue`：新增 dispose debug log
- `BaseKLineChart` 子组件自带 ResizeObserver，无需额外修改
- 构建验证：✓ 81 modules, 6.65s

---

## 🟠 P2 — 中长期架构演进

### Issue #16：前后端 API 错误拦截与熔断 UI
**状态**：✅ 已完成（v0.5.49，commit d64ec38）
- `useDataSourceStatus.js`：单例事件总线，`ok / degraded / down` 三态广播
  - 连续失败 3-5 次 → `degraded`（备用降级）
  - 连续失败 ≥6 次 → `down`（全线熔断）
  - API 成功 → `ok`（自动恢复）
- `apiFetch`：502/503/429/超时/网络错误均触发 `_onFailure()` 广播
- `CommandCenter.vue`：底部状态栏 🟢/🟡/🔴 指示灯 + 4s Toast 提示
- Debug 验证：状态机流转正常，广播事件正确触发

---

### Issue #17：画线工具状态机重构
**严重程度**：🟠 低 — 工具栏无状态隔离，事件监听器互相污染
**涉及文件**：`frontend/src/components/DrawingCanvas.vue`

**修复方案**：
1. 建立 `IDLE / DRAWING / EDITING` 三状态机
2. 右键菜单改为状态转换触发器
3. 文字标注支持内联输入（contenteditable 或 popup input）

---

### Issue #18：数据库写入队列化（消除全局锁瓶颈）
**状态**：✅ 已完成（v0.5.50，commit 88a56a2）
- 新建 `backend/app/db/db_writer.py`：
  - `DBWriterThread` 常驻守护线程，死循环消费队列
  - `enqueue(task)` 生产者接口，< 1ms 返回
  - 任务类型：`T_DAILY / T_PERIODIC / T_REALTIME / T_ALLSTOCKS / T_BUFFER`
  - `start_writer()` / `stop_writer()` 生命周期钩子
- `database.py` 重构：5 个写入函数 → 纯生产者（立即 enqueue 返回）
- `main.py`：`start_writer()` 启动，`stop_writer()` 关闭（最多30s队列排空）
- Debug 验证：3条入队→队列3 → writer 3s内消费完→队列0 → graceful stop ✅

---

## ✅ 已关闭 Ticket

| Ticket | 关闭版本 | 说明 |
|--------|---------|------|
| #1-#10 | v0.5.33-v0.5.43 | 详见各版本 commit log |
| 熔断器实现 | v0.5.40/0.5.41 | CircuitBreaker + FetcherFactory 已落地 |
| #11 WebSocket内存泄漏 | v0.5.44 | useMarketStream 引用计数 Map |
| #12 版本号统一 | v0.5.46 | vite.config.js define 注入 |
| #13 代理硬编码 | v0.5.45 | proxy_config.py 统一代理层 |
| #14 虚拟滚动 | v0.5.48 | StockScreener useVirtualList |
| #15 ECharts ResizeObserver | v0.5.47 | ResizeObserver + dispose |
| #16 熔断 UI | v0.5.49 | useDataSourceStatus + Toast |
| #18 DB写入队列化 | v0.5.50 | DBWriterThread |
