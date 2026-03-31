# AlphaTerminal 开发日志 (dev_log)

## 2026-03-31

### 后端端口配置

- **后端端口**：8002（8002 原空闲，直接启用，未触发动态迁移）
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
- `GET /api/v1/market/history/{symbol}` → K线数据
- `GET /api/v1/market/china_all` → A股全表

### 网络策略（紧急修订）

> ⚠️ **安全指令**：严禁随意 `kill` 未知进程，以防影响服务器其他服务。
> 如端口冲突，优先动态迁移至 60101+ 空闲端口，而非击杀进程。

### Git Remote

- 已更新 origin 使用 Token 认证
- 代理：`http://192.168.1.50:7897`
