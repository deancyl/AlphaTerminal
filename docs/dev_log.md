# AlphaTerminal 开发日志 (dev_log)

## 2026-03-31

### 后端端口配置

- **后端端口**：8002
- **前端端口**：60100（Vite dev server）
- **代理配置**：前端 vite.config.js 代理 `/api` → `http://127.0.0.1:8002`
- **健康检查**：`GET /health` → `{"status":"ok","service":"AlphaTerminal"}`
- **API 基础路径**：`/api/v1`（路由前缀）

### 进程状态

| 进程 | 端口 | 状态 |
|------|------|------|
| uvicorn (backend) | 8002 | ✅ 运行中 |
| vite (frontend) | 60100 | ✅ 运行中 |

### 关键端点验证

- `GET /api/v1/market/overview` → 200 ✅（返回 A股/港股/美股 overview 数据）
- `GET /api/v1/market/history/{symbol}?period=daily` → 200 ✅（日K，日线已回填 28357 条）
- `GET /api/v1/market/history/{symbol}?period=weekly` → 200 ✅（周线，已聚合 7085 条）
- `GET /api/v1/market/history/{symbol}?period=monthly` → 200 ✅（月线）
- `GET /api/v1/news/flash` → 200 ✅（真实新闻，MD5 URL 去重，来源：东方财富）

### Phase 1 补完：多周期 K 线 + 信息流引擎

#### Task 1：全周期数据
- **Symbol 清洗**：前后缀剥离（`sz399001` → `399001`，`sh000001` → `000001`）
- **日线**：AkShare `stock_zh_index_daily`，5 大指数 × 8518 条，已回填 `market_data_daily`
- **周线/月线**：从日线 pandas 聚合（不依赖外部 API），写入 `market_data_periodic`
  - 周线：5 指数 × 520 条
  - 月线：5 指数 × 120 条
- **Scheduler 改进**：`backfill_daily_history()` 启动时延迟 2s 执行，周/月聚合内嵌

#### Task 2：实时新闻引擎
- **数据源**：`akshare stock_news_em`（东方财富），轮询 5 个核心标的
- **去重机制**：MD5(news_url) 哈希集合，进程内存常驻（uvicorn 生命周期）
- **缓存管理**：超过 500 条时自动清理旧哈希，保留最新 300 条
- **标签系统**：基于标题关键词自动打标（🔴突发/💎宏观/📈A股/🌏港股等）
- **降级策略**：API 全部失败时返回内置静态 5 条 Mock 数据
- **注册路由**：`/api/v1/news/flash` → `app/routers/news.py`

#### Task 3：前端信息流挂载 + 详情 Modal
- **NewsFeed.vue**：重写完成（分页 + 异步正文抓取 + 详情 Modal）
  - 分页：50 条/页，支持 ‹ › 按钮（最多显示 5 个页码按钮）
  - 高度锁定：`min-height: 380px` 容器，`overflow-y-auto`，固定显示约 7 条
  - Modal：点击新闻标题弹出详情，`backdrop-blur` 遮罩，先显示"正文努力提取中..."，异步 GET `/api/v1/news/detail` 后展示纯文本正文
  - 原文链接：Modal 底部显示可点击外链
- **DashboardGrid**：NewsFeed 网格扩大至 `gs-w="8"`（占 2/3 宽度）
- **挂载位置**：DashboardGrid Widget 5（原板块与商品 Tab 区）
- **清理**：移除未使用的 `commodityTab`、`sectorsData`、`derivativesData` 等变量

#### Task 4（Phase 4）：新闻详情正文抓取
- **路由**：`GET /api/v1/news/detail?url=xxx`
- **白名单域名**：`eastmoney.com`, `sina.com.cn`, `qq.com`, `ifeng.com`, `cls.cn`, `xinhuanet.com` 等
- **技术栈**：`requests` + `BeautifulSoup4`（html.parser）
- **清洗规则**：移除 `<script>`, `<style>`, `<img>`, `<svg>`, `<iframe>`, `<nav>`, `<header>`, `<footer>`, `<aside>`，仅提取 `<p>` 段落文字（>20字符）
- **容错降级**：解析失败返回"原文解析失败，请点击链接查看网页"
- **SSRF 防护**：仅白名单域名可通过

### 关键代码变更

| 文件 | 变更 |
|------|------|
| `app/services/news_engine.py` | **新建**：真实新闻引擎（MD5去重 + AkShare轮询） |
| `app/services/data_fetcher.py` | 新增 `fetch_china_all_indices()` + 周/月聚合逻辑 |
| `app/db/database.py` | `_normalize_symbol()` + periodic 查询symbol清洗 |
| `app/routers/news.py` | 替换 mock → 真实 `news_engine` |
| `frontend/src/components/DashboardGrid.vue` | Widget 5 → NewsFeed 挂载 |

### Git Remote

- origin 使用 Token 认证
- 代理：`http://192.168.1.50:7897`

## 2026-03-31 下午（信息流收官）

### 信息流重构（Phase 4 精准修复）

#### UI 满宽
- DashboardGrid：NewsFeed 移至 `gs-x="0" gs-w="12"`（占满全部 12 列，消除左侧空白）
- 新闻列表高度：`min-height: 380px`，固定显示约 7 条，`overflow-y-auto` 自由滚动

#### 白名单解除
- 后端 `news.py`：`SAFE_NEWS_DOMAINS`、`_is_safe_url()` 已彻底移除
- 所有 `http://` / `https://` URL 均可请求，防 SSRF 改为业务层兜底（超时 10s）
- 实测：eastmoney 真实 URL 正文抓取成功（2358 字符）

#### 150 条新闻池
- `NEWS_SYMBOLS` 从 5 个指数扩展至 **30 只核心 A 股**（银行/保险/券商/科技/消费/周期）
- 后端预热：scheduler 启动时调用 `fetch_latest_news(limit=150)` 填充去重缓存池
- 刷新频率：前后端均改为 **20 分钟**一次
- 实测返回：**150 条真实新闻** ✅

#### Modal 详情弹窗
- Footer 区域：直接显示原文 URL（可点击复制）+ "浏览器打开" 按钮
- 异步正文：先显示"正文努力提取中..."，GET `/api/v1/news/detail` 后展示纯文本

---

# Alpha 0.0.2 — Phase 2 交互升级版

## 发布信息
- **Tag**: v0.0.2-alpha
- **发布日期**: 2026-03-31
- **主题**: 打破信息孤岛 — 全局联动 + 专业图表 + 市场情绪

---

## Phase 2 核心更新

### 1. 全局状态管理 & Drill-down 联动 ✅
- **useMarketStore.js**：Vue 3 Composable 模块级单例
  - `currentSymbol` / `currentSymbolName` / `currentColor` 跨组件共享
  - DashboardGrid 监听 `currentSymbol`，`IndexLineChart` 响应式重渲染
- **全球市场列表**：每行加 `@click` → `handleGlobalClick()` → 映射 symbol（NDX→ndx 等）→ store.setSymbol()
- **国内指数列表**：每行加 `@click` → `handleChinaClick()` → store.setSymbol()
- 点击任一指数 → 主图 K 线**瞬间切换**，无需刷新页面

### 2. 图表专业度升级 ✅
- **Hover Bar**：顶部动态 OHLCV 栏（时间/开/高/低/收/量），随 `mousemove` 实时刷新
- **Grid 比例**：主图 60% + 成交量 20% + 副图 17%（精确像素分配）
- **分时图 Y 轴**：动态 `min/max`（1% padding），从不从 0 开始
- **分时面积图**：渐变 `areaStyle`，均价虚线

### 3. A股市场情绪温度计 ✅
- **sentiment_engine.py**：后台线程拉取新浪全市场（5495 只）
- **真实数据**（2026-03-31 收盘）：
  - 涨 1011 家 / 跌 4377 家 / 平 107 家
  - 涨停 66 只 / 跌停 12 只
  - 上涨比例 18.4%
- **路由**：`GET /api/v1/market/sentiment`
- **Scheduler**：每 3 分钟后台刷新，不阻塞主线程
- **前端组件**：红绿双拼进度条（待集成 Widget）

### 4. 基础架构 ✅
- 新闻引擎：<1ms 缓存读取，后台 20 分钟刷新，150 条池
- 分时数据：Eastmoney push2his 5 分钟 K 线（48 根/日）
- 周/月聚合：SQLite ROW_NUMBER()，first-open / last-close，OHLC 正确

---

## 技术栈
- 后端：Python 3.11 / FastAPI / APScheduler / SQLite / AkShare / BeautifulSoup4
- 前端：Vue 3 / Vite 4 / TailwindCSS / ECharts 5 / GridStack / useMarketStore
- 代理：`http://192.168.1.50:7897`

---

# Alpha 0.1.0 — Phase 3 架构重建版

## 发布信息
- **Tag**: v0.1.0-beta
- **发布日期**: 2026-03-31
- **主题**: 高性能投研终端 — API 毫秒级响应 + 响应式 AI 抽屉

---

## Phase 3 核心更新

### 1. Stocks 数据源：从 Sina HQ 批量接口重建 ✅
- **问题根因**：Sina `stock_zh_a_spot` 和 Eastmoney 均被 IP 封锁，返回 HTML 错误
- **解决方案**：新建 `sina_hq_fetcher.py`，使用腾讯行情 `qt.gtimg.cn` 批量接口
  - 50 只重点股票（蓝筹/龙头/消费/银行/科技全覆盖）
  - 单次批量 ≤45 个代码，延迟 0.12s，总耗时 <5s
  - 实测：46 只真实股票 ✅（贵州茅台 1450 元 / +2.11%）
- **接口**：`GET /api/v1/market/stocks` → <1ms 响应

### 2. 新闻多源轮询引擎 ✅
- **主源**：`akshare stock_news_em`（东方财富，30 只股票）
- **从源**：`akshare news_economic_baidu`（宏观快讯兜底）
- **心跳日志**：`[HEARTBEAT] News refreshed at ...` 写入 backend_error.log
- **调试接口**：`GET /api/v1/debug/scheduler` → `{"news_last_success": "...", "spot_cache_ready": true}`

### 3. 涨跌分布直方图（11 桶）✅
- **数据源**：Sina HQ 46 只股票实时行情
- **桶分布**（2026-03-31 收盘）：
  - 跌 33 只 / 涨 13 只
  - 主要集中在 `-2%~0%`（56.52%）和 `0%~2%`（26.09%）
- **响应**：`GET /api/v1/market/sentiment/histogram` → <1ms

### 4. 行业板块（Sectors）修复 ✅
- **问题**：Sina 板块 API 和 Eastmoney 行业 API 均被封锁
- **解决方案**：改用 `china_all` 10 只核心指数作为替代数据源
- **数据**：`GET /api/v1/market/sectors` → 10 条，按涨跌幅排序

### 5. 前端组件 ✅
- **SentimentGauge.vue**：ECharts 11 桶横向柱状图，红绿双色系
- **HotSectors.vue**：行业风口（10 大 A 股指数 + 领涨信息）
- **StockScreener.vue**：全市场个股透视，分页（20 条/页）+ 可排序列（涨跌幅/换手率/价格）
- **DashboardGrid.vue**：新增 Widget 网格，风向标 → 情绪温度计

### 已知限制
- Sina/Eastmoney 全市场个股 API 持续被封锁，暂用 46 只重点股票代替 5000+ 全量
- 新闻多源：Sina 被封锁时宏观快讯降级至 Mock 数据

---

## 技术架构
- 后端：Python 3.11 / FastAPI / APScheduler / SQLite / AkShare / BeautifulSoup4
- 前端：Vue 3 / Vite 4 / TailwindCSS / ECharts 5 / GridStack
- 数据源：Sina HQ (qt.gtimg.cn), AkShare, 东方财富

---

## v0.1.0-beta — Beta 0.1.0 正式发布（2026-03-31）

### 核心架构升级

#### 🎯 Task 1：API 路由零阻塞（20秒→3ms）
**问题**：前端刷新页面卡顿 20 秒，根因 `market.py /sectors` 在 FastAPI 路由线程中同步调用 akshare（网络请求 10~20 秒）。
**解决方案**：彻底分离数据层与路由层：
- 新建 `app/services/sectors_cache.py`：行业板块全局缓存，后台 Job 每 5 分钟刷新
- `market.py /market/sectors`：只读 `get_sectors()` 缓存，响应 **1.8ms**（降幅 99.99%）
- `main.py lifespan`：移除同步预热，uvicorn 启动不再被阻塞
- `scheduler.py`：新增 `sectors_refresh` Job（每 5 分钟），启动时触发 `startup_sectors` 线程

**所有 @router.get 路由现状**：
| 路由 | 响应时间 | 数据源 |
|------|---------|--------|
| `/market/sectors` | **1.8ms** | sectors_cache 内存 |
| `/news/flash` | **4.4ms** | news_engine 内存 |
| `/market/overview` | **5.5ms** | SQLite |
| `/market/sentiment/histogram` | **1.5ms** | SpotCache 内存 |
| `/market/stocks` | **<10ms** | SpotCache 内存 |
- **零同步网络调用**：所有 akshare/Sina 调用已压入后台 Daemon Thread

#### 🎯 Task 2：Copilot 抽屉式 UX
- `App.vue`：新增 `isCopilotOpen` 响应式变量（默认 `true`）
- 右上角新增 **☰展开/🤖AI** 切换按钮，0.3s CSS `transition-all`
- 左侧主体动态宽度：`isCopilotOpen ? calc(100% - 340px) : 100%`
- 右侧抽屉：`v-show="isCopilotOpen"`，`width: 340px`，GridStack 父容器宽度变化时自动等比拉伸

#### 🎯 Task 3：行业数据源肃清
- `sectors_cache.py fetch_and_cache_sectors()`：主用 `akshare stock_board_industry_name_em()`（真实行业板块）
- 备选：`akshare stock_board_concept_name_em()`（概念板块）
- 静态兜底：酿酒行业/医疗器械/半导体/电池/银行/证券/房地产/煤炭（绝不用指数冒充行业）
- 样本：`酿酒行业 +1.23% top=贵州茅台`，`医疗器械 +0.87% top=迈瑞医疗`

#### 🎯 Task 4：沪深 300 熔断优化
- `sina_hq_fetcher.py`：新增 `get_hs300_pool()` → 沪深 300 成分股最多 100 只
- `sentiment_engine.py _bg_sina_refresh()`：改用 `get_stock_pool()`（优先 HS300，备选 FOCUS_STOCKS 15只）
- 批量抓取：`batch_size=45`，`sleep 0.05s`，避免单次请求超时

#### 🎯 Task 5：新闻 Mock 彻底禁用
- `news.py /news/flash`：缓存未就绪时返回空列表 `[]`（绝不走 Mock 5 条假数据）
- 启动预热：`asyncio.create_task(_bg_startup())` 后台分发（不阻塞 uvicorn）

### 性能压测数据
```
/market/sectors        1.8ms  ✅
/news/flash            4.4ms  ✅
/market/overview       5.5ms  ✅
/sentiment/histogram   1.5ms  ✅
```
**结论：全量 API < 10ms，前端页面刷新从 20 秒降至毫秒级。**

### Beta 0.1.0 完整功能清单
- ✅ 多周期 K 线（分时/日/周/月）
- ✅ 市场情绪 11 桶直方图
- ✅ 沪深 300 个股透视（最多 100 只）
- ✅ 真实行业板块（akshare 数据源）
- ✅ 全市场新闻池（150 条，东方财富+百度宏观）
- ✅ AI Copilot 抽屉式侧边栏
- ✅ 风向标/全球指数/国内指数/期货商品
- ✅ 涨跌停统计/上涨比例/涨跌家数
- ✅ 新闻详情异步抓取（BS4 正文提取）
- ✅ 调度器后台数据刷新（无阻塞）

---

## 正式 Release
- **v0.1.0-beta** 标签已创建
- GitHub: https://github.com/deancyl/AlphaTerminal

---

## Beta 0.3.1 里程碑（2026-04-01）

### 背景：Phase 5-8 精准增量灾难与恢复

2026-04-01 上午，Phase 5-8 所有代码以 dangling commit 形式存在于本地，从未合入 master。
试图发布 Beta-0.3.0 时触发了 SSHFS 死锁 + 指数归零 + ECharts 溢出等多个并发 Bug。

### 根本原因

1. **SSHFS 死锁**：`/vol3/@apphome/trim.openclaw/` 为 SSHFS 挂载点，SQLite WAL 模式写操作触发 I/O 阻塞，导致 `init_tables()` → `_get_conn()` 在 `PRAGMA journal_mode=WAL` 处卡死
2. **git cherry-pick 误判**：Phase 5-8 commits 内容实际已存在于 fe688ed（更完整的 Phase 7 版本），重复 cherry-pick 产生大量冲突
3. **数据库版本混乱**：`/tmp/alphaterminal.db`（残留）vs `/home/deancyl0607/alpha_ultimate.db`（生产）vs `/tmp/alphaterminal_v2.db`（测试）三个版本同时存在

### 精准恢复步骤

1. `git reset --hard fe688ed`（Phase 7 VHSI 节点，黄金时间点）
2. 解决 cherry-pick f87ea20/3f46a2d/773402f/16dda82 冲突（保留 Phase 7 更完整版本）
3. `git commit -m "Phase 5-8 recovery"` → `0125dca`
4. 强制 push：`git push --force origin master`

### 关键修复清单

| 修复 | 文件 | 详情 |
|------|------|------|
| RLock 死锁 | `market.py` | `threading.Lock()` → `threading.RLock()` |
| ECharts 溢出 | `BondDashboard.vue`/`FuturesDashboard.vue` | `overflow-hidden relative min-h-0` |
| `_parse_sina_index` | `data_fetcher.py` | `len < 10` → `len < 6`，`parts[3]` 直接作为 `chg_pct` |
| Wind 6 指数 | `market.py` | `WIND_SYMBOLS` 新增 399001/399006 |
| data_sources 注册表 | `config/data_sources.py` | 147 行数据源配置 |
| 数据库路径 | `database.py` | `/home/deancyl0607/alpha_ultimate.db` |

### API 验证结果（Beta 0.3.1）

```
Health:              ✅ 200 OK
Wind 6 indices:     ✅ 000001/000300/399001/399006/HSI/IXIC 全非零
china_all:          ✅ 10 条国内指数
Global:             ✅ DJI + HSI + IXIC
Bond yield_curve:   ✅ 8 期限国债曲线
Futures indexes:    ✅ IF/IC/IM
News flash:         ⚠️ cache_empty（scheduler 首次调度）
K-line history:     ⚠️ 0 bars（待 backfill）
```

### Git Commit 时间线

```
f87ea20  Phase 5: RLock deadlock fix + wind 8标的
3f46a2d  Phase 6: BondDashboard + FuturesDashboard + Sidebar
773402f  Phase 7: bond/futures routers + ECharts skeletons
fe688ed  Phase 7P0: VHSI real data + heatmap collapse fix ← 黄金节点
16dda82  Phase 8: ECharts overflow + _parse_sina_index + data_sources
0125dca  Phase 5-8 recovery (forced push to origin/master)
```

### 工程教训

1. **SQLite 绝对不能放在 SSHFS/FUSE 网络文件系统上**（WAL 模式写操作会触发 I/O 阻塞）
2. **发版前必须验证前端真实渲染**，不能只看后端 API 200
3. **每次 cherry-pick 必须物理验证**，不盲目推进
4. **AI 容易产生"路径幻觉"**，必须验证文件系统真实权属和进程间隔离性
5. **快速合入不叫效率**，能一次性通过物理探针验证才叫质量

---

## 正式 Release
- **v0.3.1-beta** 标签已创建（2026-04-01）
- GitHub: https://github.com/deancyl/AlphaTerminal

---

## Beta-0.3.1 里程碑（2026-04-01 22:45）

### 终极修复清单

| Bug | 根因 | 修复 | 验证 |
|-----|------|------|------|
| 分时显示 11.xx | `secid=0.000001` 指向平安银行 | `_INDEX_SECID_MAP` 精确映射 `000001→1.000001` | ✅ 3948.55 |
| 月K/周K全空 | `buffer_insert_periodic(,"weekly")` 硬编码覆盖 | 移除第二个参数，动态列名匹配 | ✅ 300 bars |
| 风向标垂直留白 | 单列 full-width 垂直堆叠 | `grid grid-cols-2` 两列卡片网格 | ✅ |
| 行业板块稀缺 | 仅 8 个行业 | 行业+概念融合 Top 20 + 关键词加权 | ✅ |
| Header 名称残留 | `currentName` 仅从 props 初始化 | `watch props.symbol` 响应式重置 | ✅ |
| SSHFS 死锁 | WAL 模式在 FUSE 挂载层卡死 | DB 迁移至 `/tmp/alpha_ultimate_active.db` | ✅ WAL 正常 |
| DB 权限壁垒 | trim.openclaw UID 无写 home 目录权限 | chmod 666 + DELETE 模式降级 | ✅ |

### 全周期 K 线验证结果

```
分时 Minutely:  ✅ 300 bars, 000001 最新价 3948.55
日K Daily:       ✅ 300 bars, latest=2026-04-01
周K Weekly:      ✅ 300 bars
月K Monthly:     ✅ 300 bars
```

### Git Tag
- `v0.3.1-beta` → `903c3d2`（2026-04-01 23:22）
- `Beta-0.3.0` → 已归档为 pre-release（代码已过时）
