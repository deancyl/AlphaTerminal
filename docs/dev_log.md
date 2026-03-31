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
