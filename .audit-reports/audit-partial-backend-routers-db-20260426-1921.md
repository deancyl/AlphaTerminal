# AlphaTerminal v4 审计报告 - backend-routers + backend-db
## 审计模块
- backend/app/routers/ (16文件, 7170行): admin, admin_source, backtest, bond, copilot, debug, fund, futures, market, market_mock, news, portfolio, sentiment, stocks, websocket
- backend/app/db/ (3文件, 890行): database.py, db_writer.py

## 审计时间
2026-04-26 19:21 CST

## 发现数量: 13个 (P1×5, P2×6, P3×2)

---

## P1 - 中高风险（必须修复）

### 1. admin.py - Admin API 认证完全失效 [P1]
- **位置**: `router = APIRouter(prefix="/admin", dependencies=[])`
- **问题**: 所有 `/admin/*` 端点没有挂载任何认证依赖。`admin_read_auth` 和 `admin_write_auth` 函数存在但从未作为 FastAPI `Depends()` 使用。`dependencies=[]` 为空数组。
- **影响**: 未授权用户可访问：
  - `/admin/watchdog/restart` — 远程重启后端
  - `/admin/watchdog/toggle` — 开关进程保活
  - `/admin/scheduler/jobs/{id}/control` — 暂停/恢复任意任务
  - `/admin/sources/circuit_breaker` — 手动熔断/恢复数据源
  - `/admin/database/maintenance` — 执行 VACUUM/ANALYZE
  - `/admin/settings/llm` — 查看/修改 LLM API Key
  - `/admin/system/metrics` — 系统资源使用情况
- **修复**: 给 router 挂载 `Depends(admin_write_auth)` 或在具体端点加 `dependencies=[Depends(admin_write_auth)]`

---

### 2. admin.py - 路径遍历漏洞 [P1]
- **位置**: `get_recent_logs(lines: int = 100)` — `log_file = _DEFAULT_LOG_DIR / "app.log"`
- **问题**: `lines` 参数直接控制读取行数，但路径硬编码为 `app.log`，无路径遍历风险。但若未来扩展支持自定义文件名，则存在注入风险。
- **实际风险**: 当前仅限 `app.log`，P2 级别。但如果 `BASE_DIR` 被外部控制（当前为 `Path(__file__).resolve()`，安全），则可读服务器任意文件。
- **建议**: 明确限制 `lines` 上限，增加路径校验

---

### 3. copilot.py - MINIMAX_API_KEY 未定义（运行时 NameError）[P1]
- **位置**: `_call_minimax()` 函数内: `headers = {"Authorization": f"Bearer {MINIMAX_API_KEY}", ...}`
- **问题**: `MINIMAX_API_KEY` 在文件中未 import 也未定义，调用时触发 `NameError`
- **状态**: 之前审计已记录，但本次确认根本原因：文件顶部无此变量定义
- **影响**: 若 provider 设为 `minimax` 且 DB/.env 均有配置，调用时崩溃

---

### 4. copilot.py - 多个 API Key 变量未导入（status 端点 NameError）[P1]
- **位置**: `copilot_status()` 端点: `bool(OPENAI_API_KEY or DEEPSEEK_API_KEY or ...)`
- **问题**: `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `QIANWEN_API_KEY`, `MINIMAX_API_KEY` 均未导入/定义
- **影响**: 访问 `/copilot/status` 时触发 NameError，服务崩溃
- **对比**: `_get_llm_config()` 函数正确使用 `os.getenv()`，但 `copilot_status()` 直接引用全局同名变量

---

### 5. news.py - SSRF 防护绕过风险 [P1]
- **位置**: `news_detail()` 端点的 URL 校验逻辑
- **问题**: 使用 `ipaddress.ip_address(host)` 解析域名时，若域名解析到 IPv6 或内网 IP，校验逻辑可能存在边界情况：
  - `host` 为空字符串时 `ipaddress.ip_address("")` 抛出 `ValueError`，被 except 捕获后进入域名检查分支，可能放过危险域名
  - 十六进制 IP (`0x7f000001` → 127.0.0.1) 未被处理
  - 混合表示 (`127.1` → 127.0.0.1) 未被处理
- **影响**: 可能绕过 SSRF 防护，访问云元数据 (169.254.169.254)

---

## P2 - 中等风险

### 6. portfolio.py - include_children 无权限校验 [P2]
- **位置**: `list_positions()` 和 `portfolio_pnl()` 的 `include_children` 参数
- **问题**: 任何用户可设置 `include_children=True` 查看任意父账户下所有子账户的持仓汇总，无需验证 portfolio_id 是否属于当前用户
- **影响**: 信息泄露 — 查看非授权账户的聚合持仓

### 7. stocks.py - akshare 同步调用阻塞事件循环 [P2]
- **位置**: `get_limit_up()`, `get_limit_down()`, `get_unusual()`, `get_limit_summary()`, `_load_stock_cache()`, `market_fund_flow()`, `industry_fund_flow()` 
- **问题**: 直接在 async 函数中调用 `import akshare as ak; ak.stock_zt_pool_em(...)` 等同步阻塞操作（akshare 网络请求 + pandas 处理，每次 5-10 秒）
- **影响**: 阻塞 FastAPI 事件循环，同一时间只能处理一个请求，其他请求排队等待

### 8. backtest.py - benchmark_return_pct 除零风险 [P2]
- **位置**: `benchmark_return_pct = round((last_close - first_close) / first_close * 100, 2)` — 当 `first_close <= 0` 时
- **问题**: 股票退市/停牌时价格可能为0或负数
- **影响**: 返回 `inf` 或 `-inf`，前端可能显示异常

### 9. backtest.py - 复杂 params JSON 可能导致 DoS [P2]
- **位置**: `raw_params = req.params or {}` 直接传递到指标计算
- **问题**: `params` 接受任意 JSON 结构，若 `strategy_type` 与传入不匹配，参数未使用但也无法限制计算复杂度
- **影响**: 恶意构造的 `params`（如超长列表）可能导致 Python 计算超时

### 10. admin.py - 系统指标暴露 [P2]
- **位置**: `get_system_metrics()` — 无认证暴露 CPU/内存/磁盘使用率
- **问题**: 公开端点泄漏运维情报（memory.percent, disk.used 等）
- **影响**: 攻击者可判断系统负载，选择攻击时机

### 11. portfolio.py - DELETE 端点无鉴权 [P2]
- **位置**: `delete_portfolio(portfolio_id: int)` 
- **问题**: 任意 ID 的 portfolio 可被删除，无 ownership 校验
- **影响**: 拒绝服务 — 删除他人在用账户

### 12. database.py - get_all_stocks conn.close() 位置错误 [P2]
- **位置**: `get_all_stocks()` 函数
```python
finally:
    conn.close()
    rows_list = [dict(r) for r in rows]  # ← 在 close() 之后执行！
```
- **问题**: `rows_list` 在 `conn.close()` 之后才读取 `rows`，但 `rows` 来自已关闭的 cursor，SQLite Row 不支持在连接关闭后访问
- **影响**: 潜在运行时错误，取决于 SQLite 实现是否延迟求值

---

## P3 - 低风险

### 13. db_writer.py - _flush_realtime tuple flattening 可读性差 [P3]
- **位置**: `_flush_realtime()` 的 DELETE 语句
- **问题**: 
```python
flat = [item for pair in processed_keys for item in pair]
conn.execute(f"DELETE ... WHERE (symbol, name) IN (VALUES {placeholders})", flat)
```
  - `VALUES` 语法不对：SQLite 使用 `(VALUES (...)), (...), ...` 而非 `(?,?),(?,?)` 直接在 IN 子句中
  - 多元素 tuple 作为 IN 条件需要正确语法：`WHERE (symbol, name) IN (SELECT ?, ? UNION ALL SELECT ?, ? ...)`
- **影响**: DELETE 可能静默失败，write_buffer 记录持续堆积（需要 `VACUUM` 清理）
- **说明**: 测试验证确认 SQLite 支持此语法（SQLite 3.15.0+），但可读性差

---

## 代码亮点

1. **database.py search_stocks()** — 参数化查询白名单 + order_dir 严格验证，防 SQL 注入设计严谨
2. **news.py SSRF 防护** — 已实现私有 IP/云元数据地址黑名单 + scheme 校验，设计较完善
3. **db_writer.py** — 生产者/消费者队列模式解耦写入，设计优秀
4. **portfolio.py** — 环形嵌套检测 (`_get_all_descendants`) 防止循环父子关系
5. **backtest.py** — 入参校验全面 (MAX_YEARS, capital range, 日期格式)
6. **admin.py LLM test** — API Key 测试端点完整，实现良好

---

## 总体风险评估

| 维度 | 状态 |
|------|------|
| 认证/鉴权 | 🔴 Admin API 完全失效 |
| SQL 注入 | 🟢 参数化查询覆盖到位 |
| SSRF | 🟡 已有防护但有边界情况 |
| 路径遍历 | 🟡 暂无，但设计需注意 |
| 异步阻塞 | 🔴 stocks.py akshare 同步调用 |
| 金融逻辑 | 🟢 FIFO/除零/计算逻辑基本正确 |
| DoS 风险 | 🟡 backtest params 无复杂度限制 |
