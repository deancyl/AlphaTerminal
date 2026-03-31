# AlphaTerminal 核心模块技术维基

> 本文档面向后续接手的开发者，记录 AlphaTerminal 核心模块的设计决策与实现细节。

---

## 1. 快讯引擎多线程缓存刷新机制

### 1.1 整体架构

```
APScheduler (scheduler.py)
    │
    └── NewsRefresh (interval: 20min)
           │
           └── trigger_news_fetch()          [sentiment_engine.py]
                  │
                  └── threading.Thread (_do_news_fetch)
                         │
                         ├── akshare stock_news_em (13只宏观标的)
                         │      └── 提取: 新闻标题 / 发布时间 / 文章来源 / 链接
                         │
                         ├── akshare stock_news_em (20只个股标的)
                         │      └── 同上
                         │
                         ├── MD5 URL 去重
                         ├── sort(reverse=True)  ← 按时间倒序
                         │
                         └── _NEWS_CACHE.clear()
                             _NEWS_CACHE.extend(final)  ← 原地修改
                             _NEWS_CACHE_READY = True
```

### 1.2 进程内全局缓存

```python
# news_engine.py
_NEWS_CACHE: list[dict] = []        # 进程全局，非线程局部
_NEWS_CACHE_READY: bool = False
_CACHE_LOCK = threading.Lock()      # 写入锁
```

**为什么用进程内存而不是 Redis？**
- AlphaTerminal 定位是完全本地零依赖，Redis 增加部署复杂度
- 数据量小（≤200条），进程内存完全够用
- 写入频率低（20分钟一次），无需高并发

### 1.3 竞态消除：单一写入源原则

**Beta 0.2.2 之前的 BUG**：
- `scheduler.py` 的 `initial_backfill()` 调用 `trigger_news_fetch()`
- `main.py` 的 `lifespan` 启动时也调用 `refresh_news_cache()`
- 两个线程同时写 `_NEWS_CACHE`，互相覆盖

**修复方案**：
```python
# scheduler.py - initial_backfill() 中移除了 trigger_news_fetch()
def initial_backfill():
    from app.services.sentiment_engine import trigger_spot_fetch
    trigger_spot_fetch()   # ← 不再触发新闻
    # trigger_news_fetch() ← 已删除，由 NewsRefresh 唯一调度

# main.py - lifespan 不再触发新闻预热
# 新闻完全由 scheduler NewsRefresh(20min) 统一管理
```

### 1.4 `_NEWS_CACHE` 引用失效问题

**根因**：
```python
# 错误写法：rebind 导致旧进程中的引用指向旧列表
_NEWS_CACHE = final   # ❌
# 其他模块 import 时拿到的是旧列表对象
```

**正确写法：in-place 原地修改**
```python
with _CACHE_LOCK:
    _NEWS_CACHE.clear()       # ✅ 保持同一引用
    _NEWS_CACHE.extend(final) # ✅ 其他模块立即看到新数据
    _NEWS_CACHE_READY = True
```

### 1.5 数据源对比

| 数据源 | 时间戳字段 | 稳定性 | 代理要求 | Beta 版本 |
|--------|-----------|--------|---------|-----------|
| `news_economic_baidu` | ✅ 有 | ❌ SSL 失败 | 强依赖 | 已废弃 |
| `stock_news_main_cx` | ❌ 无 | ✅ 好 | 依赖 | 已废弃 |
| `stock_news_em` | ✅ 有（`发布时间`） | ✅ 好 | 依赖 | Beta 0.2.2 |

---

## 2. 前端穿透式请求逻辑

### 2.1 三种请求路径

```javascript
// 路径1: GET /news/flash（自动刷新，定时任务，每20分钟一次）
//   quiet=true → 不弹 loading → 只读缓存 → <1ms

// 路径2: GET /news/flash?_t=...（Vite HMR / 浏览器刷新）
//   quiet=true → 不弹 loading → 带时间戳绕过缓存 → <1ms

// 路径3: POST /news/force_refresh（手动用户点击）
//   quiet=false → 弹 loading → 穿透后端外网真实抓取 → 3-5s
```

### 2.2 状态机

```
NewsFeed.vue 状态:
  isRefreshing = false  ←→  isRefreshing = true
        ↑                      ↓
  [初始/成功]              [手动刷新中...]
                                 ↓
                    [成功] → showRefreshed = true (3s)
                    [失败] → console.warn
```

### 2.3 去重合并逻辑

```javascript
// 现有 items.id 集合
const existingIds = new Set(items.value.map(it => it.id || it.title))

// incoming 是 API 返回的最新数据
const newItems = incoming.filter(it => {
    const id = it.id || it.title
    return !existingIds.has(id)  // 只保留全新条目
})

// 合并：新数据在前，旧数据在后（保持 reverse 时间序）
items.value = [...newItems, ...items.value].slice(0, 200)
```

**为什么不用 replace 全量更新？**
- 用户在列表中滚动时全量替换会丢失浏览位置
- 增量合并用户体验更平滑

---

## 3. FastAPI 生命周期与后台任务

### 3.1 Lifespan 职责划分

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()                # APScheduler 启动（注册所有 Job）
    yield
    stop_scheduler()                 # uvicorn 关闭时清理

# 注意：lifespan 中不触发新闻预热
# 新闻完全由 NewsRefresh(20min) + force_refresh 两条路径管理
```

### 3.2 CORS 配置

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:60100",
        "http://127.0.0.1:60100",
        "http://0.0.0.0:60100",
        "http://192.168.2.186:60100",   # 容器内网地址
        "http://192.168.1.50:60100",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 3.3 端口分配

| 端口 | 服务 | 说明 |
|------|------|------|
| 8002 | FastAPI (uvicorn) | 仅 API，不 serve 前端静态文件 |
| 60100 | Vite Dev Server | 前端 HMR 开发模式 |

---

## 4. GitHub 发版脚本（REST API bypass TLS）

```python
#!/usr/bin/env python3
"""
GitHub REST API push (bypass TLS)
用法: python scripts/github_push.py
"""
import os, base64, requests

TOKEN   = os.environ.get("GITHUB_TOKEN", "ghp_XXXXXXXXXXXXX")
REPO    = "deancyl/AlphaTerminal"
BASE    = f"https://api.github.com/repos/{REPO}"
HEADERS = {"Authorization": f"token {TOKEN}", "Content-Type": "application/json"}

def push_file(local_path, github_path, message):
    sha = requests.get(f"{BASE}/contents/{github_path}", headers=HEADERS).json().get("sha", "")
    content = base64.b64encode(open(local_path,"rb").read()).decode()
    r = requests.put(
        f"{BASE}/contents/{github_path}",
        headers=HEADERS,
        json={"message": message, "sha": sha, "content": content}
    )
    print(f"{github_path}: {r.json().get('commit',{}).get('message','?')}")

push_file("README.md",              "README.md",              "docs: update README for Beta 0.2.2")
push_file("KNOWN_ISSUES_TODO.md",  "KNOWN_ISSUES_TODO.md",  "docs: update known issues")
push_file("docs/WIKI_ARCHITECTURE.md", "docs/WIKI_ARCHITECTURE.md", "docs: add architecture wiki")
```

---

_Last Updated: 2026-03-31 by OpenClaw Agent_
