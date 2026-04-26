# AlphaTerminal v0.5.176 代码审计报告 v12 (Audit-Maintenance v5: 修复提交)

## 版本信息
- 审计时间: 2026-04-26 20:21 CST
- 任务: AlphaTerminal-Code-Audit v4 (cron:88fda36d)
- 本次审计: backend-core, backend-services, backend-models (Batch B-1，第4批)
- 累计审计: 全部 12 个模块（6 个批次全部完成）
- 总体进度: ✅ 全部 12 模块审计完成（6 个批次，100%）

---

## 全部审计模块汇总

| # | 模块 | 路径 | 状态 | 说明 |
|---|------|------|------|------|
| 1 | backend-core | backend/app/main.py, __init__.py | ✅ | 审计完成 |
| 2 | backend-services | backend/app/services/ | ✅ | 审计完成 |
| 3 | backend-models | backend/app/models/ | ✅ | 空模块，schemas 在 routers 中 |
| 4 | backend-utils | backend/app/utils/ | ✅ | 审计完成 |
| 5 | backend-routers | backend/app/routers/ | ✅ | 16 文件审计完成 |
| 6 | backend-db | backend/db/ | ✅ | 审计完成 |
| 7 | frontend-composables | frontend/src/composables/ | ✅ | 8 文件审计完成 |
| 8 | frontend-services | frontend/src/services/ | ✅ | 3 文件审计完成 |
| 9 | frontend-utils | frontend/src/utils/ | ✅ | 6 文件审计完成 |
| 10 | frontend-components | frontend/src/components/ | ✅ | 47 Vue 抽检审计完成 |
| 11 | frontend-stores | frontend/src/stores/ | ✅ | 2 文件审计完成 |
| 12 | frontend-views | frontend/src/views/ | ✅ | 目录不存在，组件归入 frontend-components |

---

## 累计发现汇总

### P0 - 严重（必须修复）

| # | 文件 | 问题 | 状态 |
|---|------|------|------|
| P0-1 | news.py, data_fetcher.py | 同步阻塞 HTTP：requests.get() 在 async def 中，阻塞事件循环 | 已知，待修复 |
| P0-2 | copilot.py | MINIMAX_API_KEY 未定义，调用时 NameError | ✅ 已修复 (fix-003, f68d8b2) |

### P1 - 中高风险

| # | 文件 | 问题 |
|---|------|------|
| P1-1 | scheduler.py | 双重 flush_write_buffer_and_broadcast 注册导致任务重复执行 |
| P1-2 | trading.py | get_position_summary() finally 块双重 conn.close() | ✅ 已修复 (fix-001, f68d8b2) |
| P1-3 | trading.py | include_children 参数默认 False，router 可能未传，子账户汇总丢失 | 已知，待修复 |
| P1-4 | scheduler.py | refresh_period_klines 未导入，NameError 导致周/月线刷新静默失败 | 已知，待修复 |
| P1-5 | admin.py | Admin API 认证完全失效：所有 /admin/* 端点无认证依赖 | ✅ 已修复 (fix-002, f68d8b2) |
| P1-6 | copilot.py | /status 端点 OPENAI/DEEPSEEK/QIANWEN/MINIMAX_API_KEY 未导入 | ✅ 已修复 (fix-003, f68d8b2) |
| P1-7 | CopilotSidebar.vue | XSS：MarkdownIt(html:true) + v-html 直接渲染 LLM 输出 |
| P1-8 | BacktestDashboard.vue | apiFetch POST body 未显式 JSON.stringify |
| P1-9 | news.py | SSRF 防护存在边界情况：空 hostname 抛出异常后绕过检查 | ✅ 已修复 (fix-004, f1b6c81) |
| P1-10 | portfolio.py | include_children 无权限校验，可查看他账户子账户汇总 |
| P1-11 | copilotData.js | searchStock URL 构造 XSS 风险：encodeURIComponent 无法阻止 `<>` 注入 |
| P1-12 | usePortfolioStore.js | upsertPosition 错误消息误报：变量遮蔽导致账户名称错误提示 |

### P2 - 中等风险

| # | 文件 | 问题 |
|---|------|------|
| P2-1 | watchdog.py | BACKEND_START_CMD 硬编码相对路径，重启可靠性差 |
| P2-2 | ws_manager.py | __del__ 在多线程环境非安全 |
| P2-3 | circuit_breaker.py | HALF_OPEN 状态：half_open_max_calls 与 success_threshold 可能不同步 |
| P2-4 | sectors_cache.py | is_ready() 无锁访问，存在竞态条件 |
| P2-5 | http_client.py | __aexit__ 返回值 False 语义不明确 |
| P2-6 | logging_queue.py | WebSocket 日志消息截断到300字符，完整堆栈丢失 |
| P2-7 | main.py | CORS allow_origins 硬编码多个内网 IP |
| P2-8 | DrawingCanvas.vue | convertFromPixel 异常被 catch 吞没，图形绘制静默失败 |
| P2-9 | CopilotSidebar.vue | SSE 流式响应 JSON.parse 容错过宽，后端500错误静默 |
| P2-10 | ConservationAuditCard.vue | setInterval 未包装 try/catch，定时器泄漏风险 |
| P2-11 | stocks.py | akshare 同步调用阻塞事件循环（5-10秒） |
| P2-12 | backtest.py | benchmark_return_pct 除零风险 (first_close <= 0) |
| P2-13 | backtest.py | params JSON 无复杂度限制，可能导致 DoS |
| P2-14 | admin.py | /admin/system/metrics 无认证暴露系统资源 |
| P2-15 | portfolio.py | DELETE /portfolios/{id} 无 ownership 校验 |
| P2-16 | database.py | get_all_stocks() 中 conn.close() 在 rows 读取之前执行 |
| P2-17 | api.js | 模块级 _consecutiveFailures 无并发保护 |
| P2-18 | useDataSourceStatus.js | _listeners Set 无并发保护 |
| P2-19 | useEventBus.js | emit 缺少错误收集机制，listener 失败静默 |
| P2-20 | useMarketStream.js | tickHistory 内存管理需确认 unsubscribe 调用路径 |
| P2-21 | copilotData.js | getCached 返回过期数据无 stale 标记 |

### P3 - 低风险

| # | 文件 | 问题 |
|---|------|------|
| P3-1 | PortfolioDashboard.vue | isAggregated.computed 每次重新计算 childMap，列表较长时性能浪费 |
| P3-2 | useMarketStore.js | computed 未使用但被导入 |
| P3-3 | useTheme.js | onThemeChange 回调无去重，可能多次执行 |
| P3-4 | useUiStore.js | 导出解构不完整，新增状态易遗漏 |
| P3-5 | indicators.js | calcKDJ 中 Math.max(...Array) 大量分配，高频调用有性能问题 |

---

### P1-NEW (Batch B-1: backend-core/services/models)

| # | 文件 | 问题 |
|---|------|------|
| P1-NEW-1 | trading.py | upsert_position_summary market_value 默认写死 0.0，需外部价格注入 |

### P2-NEW (Batch B-1: backend-core/services/models)

| # | 文件 | 问题 |
|---|------|------|
| P2-NEW-1 | main.py | debug router 路由顺序风险，兜底路由可能拦截其他 API |
| P2-NEW-2 | db_writer.py | WAL 模式路径检测不可靠，DELETE mode 误判 |
| P2-NEW-3 | scheduler.py | _broadcast_realtime_ticks 中 ThreadPoolExecutor 生命周期管理错误 | ✅ 已修复 (fix-005, f1b6c81) |
| P2-NEW-4 | database.py | get_all_stocks() conn.close() 提前执行风险（需确认是否仍存在） |
| P2-NEW-5 | main.py | /health 端点无鉴权，内部状态探测 |
| P2-NEW-6 | admin.py | verify_admin_key 无速率限制，可暴力猜解 ADMIN_API_KEY |

## 累计发现统计

| 风险等级 | 数量 | 状态 |
|----------|------|------|
| P0 - 严重 | 2 | 已知，待修复 |
| P1 - 中高风险 | 13 | 已知，待修复 |
| P2 - 中等风险 | 27 | 建议修复 |
| P3 - 低风险 | 5 | 可选修复 |
| **合计** | **47** | |

---

## 报告记录

| 批次 | 时间 | 模块 |
|------|------|------|
| partial-frontend-20260426-1850 | 2026-04-26 18:50 | frontend-components, frontend-stores, frontend-utils |
| partial-backend-core-services-20260426-1904 | 2026-04-26 19:04 | backend-core, backend-services, backend-models, backend-utils |
| partial-backend-routers-db-20260426-1921 | 2026-04-26 19:21 | backend-routers (16文件), backend-db (3文件) |
| partial-frontend-composables-services-utils-20260426-1934 | 2026-04-26 19:34 | frontend-composables (8), frontend-services (3), frontend-utils (6) |
| partial-frontend-components-stores-20260426-1951 | 2026-04-26 19:51 | frontend-components (47 Vue, 抽检7), frontend-stores (2) |
| partial-frontend-views-20260426-2005 | 2026-04-26 20:05 | frontend-views (目录不存在，归入 components) |
| partial-backend-core-services-models-20260426-2021 | 2026-04-26 20:21 | backend-core, backend-services, backend-models (新批次1/4) |
| **v7-快扫-20260426-2049** | **2026-04-26 20:49** | **无待验证修复; 5个新提交仅文档/样式/DashboardGrid修复，不引入新风险点** |
| **v8-re-run-20260426-2104** | **2026-04-26 21:04** | **Re-run检查: allComplete=true, f68d8b2后0新提交, 代码库未变更, 审计状态保持** |

---

## 修复记录

| 时间 | 修复ID | 问题 | 文件 | Commit |
|------|--------|------|------|--------|
| 2026-04-26 20:52 | fix-001 | P1-2: trading.py 双重 conn.close() | backend/app/services/trading.py | f68d8b2 |
| 2026-04-26 20:52 | fix-002 | P1-5: admin.py 认证失效 (dependencies=[]) | backend/app/routers/admin.py | f68d8b2 |
| 2026-04-26 20:52 | fix-003 | P0-2+P1-6: copilot.py API Key 变量 NameError | backend/app/routers/copilot.py | f68d8b2 |
| 2026-04-26 21:38 | fix-004 | P1-9: news.py SSRF空hostname绕过 | backend/app/routers/news.py | f1b6c81 |
| 2026-04-26 21:38 | fix-005 | P2-NEW-3: scheduler.py ThreadPoolExecutor生命周期错误 | backend/app/services/scheduler.py | f1b6c81 |

**累计修复: 5 个问题 (P0×1, P1×3, P2×1) | 剩余待修复: 42 个 (P0×0, P1×9, P2×27, P3×5)**

---

## 总体结论

**✅ AlphaTerminal v4 代码审计全部完成。**

- 累计审计 **12 个模块**（9 个有效代码模块 + 3 个非存在/空模块）
- 发现 **47 个问题**（P0×2, P1×13, P2×27, P3×5）
- 本次修复 **3 个问题**（P0×1, P1×2），剩余 **44 个待修复**
- 建议优先修复 **P0 和 P1** 共计 15 个问题
- 高风险集中在：admin 认证失效、copilot.py API Key 问题、scheduler 任务注册重复

**下次审计**：建议在代码变更后重新扫描 admin.py、scheduler.py、copilot.py、CopilotSidebar.vue 等高风险文件
