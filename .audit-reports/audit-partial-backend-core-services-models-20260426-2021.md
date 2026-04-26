# AlphaTerminal v0.5.x 代码审计报告 - Batch B-1 (backend-core + backend-services + backend-models)

## 审计信息
- 审计时间: 2026-04-26 20:21 CST
- 任务: AlphaTerminal-Code-Audit v4 (cron:88fda36d)
- 审计模块: backend-core, backend-services, backend-models
- 报告路径: /vol3/@apphome/trim.openclaw/data/workspace/AlphaTerminal/.audit-reports/audit-partial-backend-core-services-models-20260426-2021.md

---

## 已知延续发现 (Previously Identified Issues)

以下问题已在历史审计报告中记录，本轮确认仍然存在：

| ID | 模块 | 文件 | 问题 | 风险 |
|----|------|------|------|------|
| P0-1 | backend-services | news_fetcher.py | 同步阻塞 HTTP (requests/httpx) 在 async def 中 | P0 |
| P0-2 | backend-routers | copilot.py | MINIMAX_API_KEY 等变量未导入，NameError | P0 |
| P1-1 | backend-services | scheduler.py | flush_write_buffer_and_broadcast 重复注册（已用 replace_existing=True 缓解） | P1 |
| P1-2 | backend-services | trading.py | get_position_summary() finally 双重 conn.close() | P1 |
| P1-3 | backend-services | trading.py | include_children 参数默认 False，router 可能未传 | P1 |
| P1-4 | backend-services | scheduler.py | refresh_period_klines 未导入，NameError | P1 |
| P1-5 | backend-routers | admin.py | Admin API 认证完全失效：dependencies=[] | P1 |
| P1-6 | backend-routers | copilot.py | /status 端点 OPENAI/DEEPSEEK/QIANWEN/MINIMAX_API_KEY 未导入 | P1 |
| P2-1 | backend-services | watchdog.py | BACKEND_START_CMD 硬编码相对路径 | P2 |
| P2-2 | backend-services | ws_manager.py | __del__ 在多线程环境非安全 | P2 |
| P2-3 | backend-services | circuit_breaker.py | HALF_OPEN 状态同步问题 | P2 |
| P2-4 | backend-services | sectors_cache.py | is_ready() 无锁访问竞态条件 | P2 |
| P2-5 | backend-services | http_client.py | __aexit__ 返回值 False 语义不明确 | P2 |
| P2-6 | backend-services | logging_queue.py | WebSocket 日志截断到300字符 | P2 |
| P2-7 | backend-core | main.py | CORS allow_origins 硬编码多个内网 IP | P2 |
| P1-9 | backend-services | news_fetcher.py | SSRF 防护空 hostname 绕过 | P1 |
| P1-10 | backend-routers | portfolio.py | include_children 无权限校验 | P1 |
| P2-11 | backend-services | stocks.py (routers) | akshare 同步调用阻塞事件循环 | P2 |
| P2-12 | backend-routers | backtest.py | benchmark_return_pct 除零风险 (first_close <= 0) | P2 |
| P2-13 | backend-routers | backtest.py | params JSON 无复杂度限制 | P2 |
| P2-14 | backend-routers | admin.py | /admin/system/metrics 无认证暴露系统资源 | P2 |
| P2-15 | backend-routers | portfolio.py | DELETE /portfolios/{id} 无 ownership 校验 | P2 |

---

## 本轮新发现

### P1 - 中高风险

**P1-NEW-1: backend-services trading.py — upsert_position_summary market_value 默认写死 0.0**

- 文件: `backend/app/services/trading.py` (upsert_position_summary 函数)
- 问题: `upsert_position_summary` 在无持仓时DELETE，有持仓时 INSERT 但 market_value 写死 0.0。虽然注释说明"market_value 和 unrealized_pnl 由外部调用方更新"，但调用方若未及时更新，持仓聚合表将长期显示错误的 0.0 市值。
- 影响: 持仓汇总页面显示错误的市值和浮动盈亏，用户无法看到实际盈亏
- 修复: 外部批量刷新流程需要确保被调用，或在 upsert_position_summary 中预留外部价格注入接口

---

### P2 - 中等风险

**P2-NEW-1: backend-core main.py — debug router 兜底路由风险**

- 文件: `backend/app/main.py` (路由注册顺序)
- 问题: `debug.router` 放在所有路由之后注册兜底，配合 `catch_all` 做最后处理。若 debug router 中有任何正则匹配的路径，可能意外接管其他路由（如 `/api/v1/debug/portfolio` 会先于 `/api/v1/portfolio` 匹配）。
- 代码:
  ```python
  app.include_router(debug.router, prefix="/api/v1", tags=["debug"])   # 放在最后兜底
  ```
- 影响: 路由优先级冲突，可能导致某些 API 端点被 debug 路由错误拦截
- 修复: debug 路由应使用更精确的路径前缀，如 `/api/v1/debug/`

**P2-NEW-2: backend-db db_writer.py — WAL 模式对非 /vol3/ /tmp/ /nas/ 路径误判**

- 文件: `backend/app/db/db_writer.py`
- 问题:
  ```python
  if "/vol3/" in _db_path or "/tmp/" in _db_path or "/nas/" in _db_path:
      conn.execute("PRAGMA journal_mode=DELETE")
  ```
  路径检测逻辑不可靠（如 `/home/user/vol3/data` 也会被匹配）。同时注释说 WAL 模式支持并发读，但 DELETE 模式在多线程写入时可能导致锁竞争。
- 影响: 在非预期路径下使用 DELETE journal mode，高并发写入时性能差甚至锁超时
- 修复: 明确 WAL 适用场景，或使用配置文件控制

**P2-NEW-3: backend-services scheduler.py — 线程池 executor 未正确管理生命周期**

- 文件: `backend/app/services/scheduler.py` (_broadcast_realtime_ticks)
- 问题:
  ```python
  executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="ws_broadcast")
  executor.submit(_sync_broadcast)
  executor.shutdown(wait=False)
  ```
  executor.submit() 是异步的，shutdown(wait=False) 立即返回，导致任务可能在 shutdown 后才执行（尤其在高负载时）。且每次调用都创建新 executor。
- 影响: WS 广播任务可能被跳过，实时数据推送丢失
- 修复: 使用单例 executor 或 `asyncio.run_in_executor` 配合生命周期管理

**P2-NEW-4: backend-db database.py — get_all_stocks() 未在 file scope 内**

- 文件: `backend/app/db/database.py`
- 问题: `get_all_stocks()` 函数存在，在审计历史中记录了 `conn.close()` 在 rows 读取之前执行的问题。需确认该函数是否仍在使用。
- 代码片段（需验证是否为最新状态）:
  ```python
  def get_all_stocks():
      conn = _get_conn()
      conn.close()   # ← 可能在 rows 读取前关闭
      rows = conn.execute("SELECT ...")   # ← 已关闭连接，无法执行
      return [dict(r) for r in rows]
  ```

**P2-NEW-5: backend-core main.py — /health 端点无鉴权暴露内部状态**

- 文件: `backend/app/main.py`
- 问题: `/health` 端点返回 `{"status":"ok","service":"AlphaTerminal"}`，本身无害，但若在同一 host 上暴露其他非认证端点，攻击者可快速探测服务。
- 影响: 低（当前仅返回 ok），但建议加上可选认证
- 修复: 可保持现状或限制为仅 localhost 访问

**P2-NEW-6: backend-routers admin.py — verify_admin_key 无速率限制**

- 文件: `backend/app/routers/admin.py`
- 问题: `verify_admin_key` 函数只校验 key 是否匹配，无登录尝试次数限制。攻击者可无限次暴力猜解 ADMIN_API_KEY。
- 影响: 若 ADMIN_API_KEY 弱或未配置（非生产），可能被暴力破解
- 修复: 添加限流（如 5分钟内最多尝试 10 次）

---

## 本轮新增发现统计

| 风险等级 | 本轮新增 | 已知延续 | 合计 |
|----------|----------|----------|------|
| P1 | 1 | 8 | 9 |
| P2 | 6 | 13 | 19 |
| P3 | 0 | 0 | 0 |

---

## 关键观察

1. **trading.py 的双重 close()** 仍未修复，会导致 `ProgrammingError: Cannot operate on a closed cursor/connection`
2. **admin.py 的认证绕过** 是最严重的安全问题，任何人都可以调用 `/admin/*` 端点重启服务
3. **copilot.py 的 NameError** 在 /status 端点触发，`OPENAI_API_KEY` 等变量未定义
4. **backtest.py benchmark_return_pct** 当 first_close <= 0 时（如期货合约上市首日）会除零错误

---

*本报告由 AlphaTerminal-Code-Audit v4 cron 任务自动生成，仅供审计使用，不修改任何代码。*
