# AlphaTerminal - 金融投研平台

> **Phase 1-5 完整交付** | Python 3.11 + FastAPI | Vue 3 + Vite + TailwindCSS | SQLite WAL

---

## 🗂️ 目录结构

```
AlphaTerminal_Workspace/
├── backend/
│   ├── .venv/                    # Python 虚拟环境（已安装全部依赖）
│   ├── app/
│   │   ├── main.py               # FastAPI 入口 + CORS
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   └── database.py      # SQLite WAL 管理（buffer_insert / flush / 查询）
│   │   ├── routers/
│   │   │   ├── market.py        # /api/v1/market/* (读 SQLite)
│   │   │   ├── copilot.py        # /api/v1/chat (SSE 流式对话)
│   │   │   └── news.py           # /api/v1/news/* (快讯/字幕降级)
│   │   └── services/
│   │       ├── scheduler.py      # APScheduler（每3min拉数据 + 每10s flush）
│   │       ├── data_fetcher.py   # Sina HQ 实时指数 + akshare SHIBOR/LPR
│   │       └── news_fetcher.py   # YouTube字幕抓取（降级策略）
│   ├── cache/
│   │   └── alphaterminal.db     # SQLite WAL 数据库
│   ├── requirements.txt
│   └── start_backend.py          # 后端启动脚本（SIGTERM_IGN 保护）
├── frontend/
│   ├── src/
│   │   ├── App.vue               # 侧边栏 Copilot + 主体布局
│   │   └── components/
│   │       ├── CopilotSidebar.vue # ChatGPT 风格对话（SSE + 打字机）
│   │       ├── DashboardGrid.vue  # 5 个 gridstack 拖拽 Widget
│   │       ├── IndexLineChart.vue # ECharts 折线图（自适应 resize）
│   │       └── NewsFeed.vue       # 快讯瀑布流
│   ├── vite.config.js            # 端口 60100，proxy /api → localhost:8002
│   └── index.html                # ECharts CDN + gridstack CDN
├── scripts/
│   └── init_alphaterminal.sh    # Phase 1 一键初始化脚本
└── README.md
```

---

## 🚀 启动命令

```bash
# ── 后端（端口 8002）──────────────────────────────────────────────
cd ~/AlphaTerminal_Workspace/backend
nohup .venv/bin/python3 start_backend.py > /tmp/alphaterminal_backend.log 2>&1 &
curl http://localhost:8002/health   # 验证后端存活

# ── 前端（端口 60100，局域网可访问）────────────────────────────────
cd ~/AlphaTerminal_Workspace/frontend
npx vite --host 0.0.0.0 --port 60100

# 局域网访问：http://<宿主机IP>:60100
```

---

## 📊 数据链路

| 数据源 | 接口 | 说明 |
|---|---|---|
| Sina HQ | `hq.sinajs.cn` | A股实时指数（上证/沪深300/深证/创业板） |
| AkShare | `macro_china_shibor_all` | SHIBOR / LPR 利率 |
| YouTube | `youtube-transcript-api` | 视频字幕（降级 Mock 研报） |
| Mock | `get_mock_news()` | 快讯瀑布流（Phase 4-5） |

**数据流**：Sina/AkShare → `write_buffer`（内存） → 每10s flush → `market_data_realtime`（WAL SQLite） → API 查询

---

## 🔌 API 路由一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 健康检查 |
| GET | `/api/v1/market/overview` | 市场总览（指数+利率） |
| GET | `/api/v1/market/indices` | A股指数列表 |
| GET | `/api/v1/market/rates` | 利率数据 |
| GET | `/api/v1/market/history/{symbol}` | 历史行情（K线） |
| POST | `/api/v1/chat` | SSE 流式对话（支持 context） |
| GET | `/api/v1/news/flash` | 快讯瀑布流 |
| GET | `/api/v1/news/transcript/{video_id}` | YouTube 字幕（降级） |

---

## ⚠️ 已知限制

1. **YouTube 字幕**：宿主机代理 `192.168.1.50:7897` 对字幕 API 端点被封锁，
   已实现优雅降级（返回内置研报文本），替换住宅代理后可恢复正常。
2. **Vite 进程持久化**：开发服务器在长时间空闲后可能被容器回收，
   使用 `nohup` 或 systemd 服务可解决，Phase 6 建议做 Docker 化部署。
3. **数据积累**：历史 K 线需要等待每日定时任务运行数天后才有完整走势。

---

## 🛠️ 依赖版本（关键）

```
Python 3.11
├── fastapi==0.115.0
├── uvicorn[standard]==0.30.6
├── akshare==1.18.49          # SHIBOR / LPR
├── yfinance==0.2.40           # 港美股（备用）
├── youtube-transcript-api==1.2.4  # 字幕（需住宅代理）
└── apscheduler==3.10.4        # 定时任务

Node 22 / Vite 6
├── vue@3.5
├── echarts@5.5.1              # CDN
├── gridstack@10.3.1           # CDN
└── tailwindcss@3
```

---

*最后更新：2026-03-31 Phase 5 终局交付 | commit: $(git rev-parse --short HEAD)*
