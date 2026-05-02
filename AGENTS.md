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

## Debug工作流（管理面板联动）

### 目录结构
```
scripts/debug/                    # Debug工具集合
├── debug.sh                      # 统一入口
├── quick_check.sh                # 快速健康检查
├── api_debug.sh                  # API接口测试
├── database_debug.sh             # 数据库诊断
├── security_audit.sh             # 安全审计
├── performance_profile.sh        # 性能分析
├── websocket_debug.py            # WebSocket测试
├── log_analyzer.py               # 日志分析
├── frontend_debug.sh             # 前端调试
├── README.md                     # 使用文档
└── WORKFLOW.md                   # 完整工作流设计
```

### 使用方法

#### 命令行方式
```bash
# 快速健康检查
./scripts/debug/debug.sh quick

# 完整诊断（所有检查）
./scripts/debug/debug.sh full

# 指定模式
./scripts/debug/debug.sh api        # API测试
./scripts/debug/debug.sh database   # 数据库检查
./scripts/debug/debug.sh security   # 安全审计
./scripts/debug/debug.sh performance # 性能分析
./scripts/debug/debug.sh websocket  # WebSocket测试
./scripts/debug/debug.sh logs       # 日志分析

# JSON输出（用于CI/CD）
./scripts/debug/debug.sh quick --json
./scripts/debug/debug.sh full --json --output-dir ./reports
```

#### API方式（管理面板联动）
```bash
# 获取可用工具列表
curl http://localhost:8002/api/v1/debug/tools

# 执行Debug工具
curl -X POST http://localhost:8002/api/v1/debug/execute \
  -H "Content-Type: application/json" \
  -d '{"tool_id": "quick_check", "options": {}}'

# 获取聚合健康状态
curl http://localhost:8002/api/v1/debug/health/aggregate

# 获取执行历史
curl http://localhost:8002/api/v1/debug/executions?limit=10

# 获取报告列表
curl http://localhost:8002/api/v1/debug/reports

# 获取系统信息
curl http://localhost:8002/api/v1/debug/system/info
```

#### WebSocket实时通信
```javascript
// 前端连接WebSocket
const ws = new WebSocket('ws://localhost:8002/api/v1/debug/ws');

// 执行工具
ws.send(JSON.stringify({
  action: 'execute',
  tool_id: 'quick_check',
  options: {}
}));

// 获取健康状态
ws.send(JSON.stringify({action: 'health'}));

// 接收结果
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data.type, data);  // started | completed | health | error
};
```

### 管理面板集成

前端管理面板路径: `/admin/debug`

功能模块:
- **健康仪表盘**: 实时显示服务状态、问题数量
- **Debug控制台**: 一键执行诊断工具、实时查看输出
- **报告中心**: 历史报告查看、对比、导出
- **系统监控**: CPU/内存/磁盘使用率、服务运行时间

### 自动化场景

#### CI/CD集成
```yaml
# .github/workflows/debug-audit.yml
- name: Run Debug Checks
  run: |
    ./scripts/debug/debug.sh full --json > debug_report.json
    
- name: Upload Reports
  uses: actions/upload-artifact@v4
  with:
    name: debug-reports
    path: debug_report.json
```

#### 定时巡检
```bash
# crontab -e
# 每天凌晨3点自动巡检
0 3 * * * cd /path/to/AlphaTerminal && ./scripts/debug/debug.sh full --json > /tmp/daily_check.json 2>&1
```

### 扩展Debug工具

1. 创建脚本 `scripts/debug/my_tool.sh`
2. 在 `backend/app/routers/debug.py` 的 `DEBUG_TOOLS` 列表中添加定义
3. 前端管理面板自动显示新工具

## 网络访问

服务绑定到 `0.0.0.0`，支持：
- 本地访问: `http://localhost:60100`
- 局域网访问: `http://192.168.1.50:60100`
- 其他IP: 任何能访问该机器的网络地址
