# AlphaTerminal 开发指南

## 服务架构

```
用户浏览器 → 前端服务器(60100) → [API代理] → 后端服务器(8002)
            → [静态文件] → dist/
```

- **前端**: Vite Preview 模式（端口 60100）
  - 提供静态文件（Vue 3 构建产物）
  - 代理 `/api/*` 请求到后端 8002 端口
  - 代理 `/health/*` 请求到后端 8002 端口
  - 代理 `/ws/*` WebSocket 到后端 8002 端口

- **后端**: FastAPI + Uvicorn（端口 8002）
  - 所有业务API
  - WebSocket 实时数据推送
  - 宏观经济数据（akshare）
  - CORS 允许所有来源

## 一键启动脚本

**文件位置**: `./start-services.sh`

### 使用方法

```bash
# 启动所有服务（推荐）
./start-services.sh all

# 重启所有服务（开发调试）
./start-services.sh restart

# 查看服务状态
./start-services.sh status

# 停止所有服务
./start-services.sh stop

# 只启动后端
./start-services.sh backend

# 只启动前端
./start-services.sh frontend
```

### 脚本特性

- ✅ 使用 `setsid` 创建新会话，完全脱离 shell
- ✅ 使用 `disown` 脱离作业控制，Bash 超时不影响
- ✅ 自动检测并释放被占用的端口
- ✅ 自动检测前端是否需要重新构建
- ✅ 健康检查（等待服务就绪）
- ✅ 彩色输出和清晰的错误提示
- ✅ 完整的日志记录到 `/tmp/backend.log` 和 `/tmp/frontend.log`

## 为什么使用 Vite Preview 而不是 Python HTTP 服务器？

### 问题
使用 `python3 -m http.server` 提供静态文件时：
- 前端 API 请求发到 60100 端口（前端服务器）
- Python HTTP 服务器无法代理 `/api/*` 请求
- 导致所有 API 返回 404

### 解决方案
使用 `vite preview` 启动前端：
- 自动应用 `vite.config.js` 中的 proxy 配置
- `/api/*` 请求自动转发到后端 8002 端口
- `/health/*` 请求自动转发到后端 8002 端口
- `/ws/*` WebSocket 自动转发到后端 8002 端口

## 开发检查清单

修改代码后：

1. **前端修改**
   ```bash
   # 修改代码后需要重新构建
   cd frontend
   npm run build
   
   # 然后重启服务（脚本会自动检测并重建）
   ./start-services.sh restart
   ```

2. **后端修改**
   ```bash
   # 使用 --reload 参数，修改后自动重启
   # 无需手动操作
   ```

3. **测试 API**
   ```bash
   # 通过前端代理测试
   curl http://localhost:60100/api/v1/macro/overview
   
   # 直接访问后端
   curl http://localhost:8002/api/v1/macro/overview
   ```

4. **查看日志**
   ```bash
   # 后端日志
   tail -f /tmp/backend.log
   
   # 前端日志
   tail -f /tmp/frontend.log
   ```

## 常见问题

### 1. 数据源异常 - API 连续 N 次失败

**原因**: 前端无法访问后端API
**检查**:
```bash
# 检查后端是否运行
./start-services.sh status

# 直接测试后端
curl http://localhost:8002/api/v1/macro/overview

# 通过前端代理测试
curl http://localhost:60100/api/v1/macro/overview
```

**解决**: 使用 `./start-services.sh restart` 重启服务

### 2. 后端启动后停止

**原因**: Bash 工具超时后会 kill 所有子进程
**解决**: 始终使用 `./start-services.sh` 脚本启动（使用 setsid + disown）

### 3. 前端修改后不生效

**原因**: 需要重新构建 dist 目录
**解决**: 使用 `./start-services.sh restart`，脚本会自动检测并重建

### 4. 宏观数据接口超时

**原因**: akshare 需要从网络抓取数据，第一次加载慢
**解决**:
- 前端超时已增加到 30 秒
- 后端已添加 5 分钟缓存机制
- 第一次加载慢（~10秒），后续很快（~100ms）

### 5. CORS 错误

**原因**: 后端 CORS 配置不允许当前域名
**解决**: 后端已配置 `allow_origins=["*"]`，允许所有来源

## 端口占用处理

如果端口被占用：
```bash
# 查看端口占用
lsof -i :8002
lsof -i :60100

# 使用脚本自动处理（会自动 kill 占用进程）
./start-services.sh restart
```

## 技术栈

- **后端**: Python 3.11, FastAPI, Uvicorn, akshare
- **前端**: Vue 3, Vite, ECharts, Tailwind CSS
- **构建**: npm run build (生成 dist/ 目录)
- **代理**: Vite Preview (内置 proxy)

## 服务信息

- **前端**: http://localhost:60100 (Vite Preview + Proxy)
- **后端**: http://localhost:8002 (FastAPI + Uvicorn)
- **工作目录**: `/vol3/1000/docker/opencode/workspace/AlphaTerminal`
- **构建产物**: `frontend/dist/`

## 网络访问

服务绑定到 `0.0.0.0`，支持：
- 本地访问: `http://localhost:60100`
- 局域网访问: `http://192.168.1.50:60100`
- 其他IP: 任何能访问该机器的网络地址

---

## F9 深度资料功能

### 功能概述

F9 深度资料是一个专业的股票深度分析面板，提供 8 个维度的股票信息：

| Tab | 功能 | 数据源 |
|-----|------|--------|
| 公司概况 | 基本信息、主营业务 | `/api/v1/stocks/quote` |
| 财务摘要 | 25+ 财务指标、8 季度趋势 | `stock_financial_analysis_indicator` |
| 机构持股 | 机构持仓、8 季度趋势 | `stock_institute_hold_detail` |
| 盈利预测 | EPS 预测、机构评级 | `stock_profit_forecast_ths` |
| 股东研究 | Top10 股东、股本变动 | `stock_circulate_stock_holder` |
| 公司公告 | 公司公告列表（分页） | `stock_notice_report` |
| 同业比较 | 行业对比、雷达图 | `stock_individual_info_em` |
| 融资融券 | 融资融券余额、30 日趋势 | `stock_margin_detail_sse/szse` |

### 使用方式

1. **键盘快捷键**: 按 `F9` 键打开深度资料
2. **命令面板**: 按 `Ctrl+K`，输入 `:F9`
3. **右键菜单**: 在股票列表中右键选择 "F9 深度资料"

### API 端点

```bash
# 健康检查
GET /api/v1/f9/health

# 财务摘要
GET /api/v1/f9/{symbol}/financial

# 机构持股
GET /api/v1/f9/{symbol}/institution

# 盈利预测
GET /api/v1/f9/{symbol}/forecast

# 股东研究
GET /api/v1/f9/{symbol}/shareholder

# 公司公告（支持分页）
GET /api/v1/f9/{symbol}/announcements?page=1&page_size=20

# 同业比较
GET /api/v1/f9/{symbol}/peers

# 融资融券
GET /api/v1/f9/{symbol}/margin
```

### 缓存策略

- **缓存时间**: 5 分钟（300 秒）
- **缓存位置**: 后端内存缓存
- **缓存键**: `{endpoint}_{symbol}`

### 测试命令

```bash
# 测试所有 F9 端点
curl http://localhost:60100/api/v1/f9/600519/financial
curl http://localhost:60100/api/v1/f9/600519/institution
curl http://localhost:60100/api/v1/f9/600519/margin
curl http://localhost:60100/api/v1/f9/600519/forecast
curl http://localhost:60100/api/v1/f9/600519/shareholder
curl http://localhost:60100/api/v1/f9/600519/announcements
curl http://localhost:60100/api/v1/f9/600519/peers
```

### 文件位置

- **后端路由**: `/backend/app/routers/f9_deep.py`
- **前端组件**: `/frontend/src/components/StockDetail.vue`
- **共享组件**: `/frontend/src/components/f9/`
  - `DataTable.vue` - 可排序、分页的数据表格
  - `InfoCard.vue` - 关键指标卡片
  - `LoadingSpinner.vue` - 加载指示器
  - `ErrorDisplay.vue` - 错误显示组件
  - `TrendChart.vue` - ECharts 趋势图封装
