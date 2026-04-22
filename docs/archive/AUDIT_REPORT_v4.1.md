# AlphaTerminal 代码审计报告 v4.1（第二轮）
**日期**: 2026-04-09
**版本**: v0.4.108
**审计人**: AI Assistant

---

## 执行摘要

本次审计在第一轮基础上深入发现了 3 个 P0 级 bug（其中 1 个为**导致黑屏的直接根因**），并完成全链路数据流修复。

---

## 1. 黑屏问题深度分析

### 🔴 P0-A: Decorator 放错位置（黑屏直接根因）

**文件**: `backend/app/routers/market.py`
**问题**: 在编辑 `market_overview` 相关代码时，`@router.get("/market/overview")` 装饰器被意外放置在了 `_get_cached_wind()` 函数定义之前，而非 `async def market_overview()` 之前。

**影响**: FastAPI 路由将 `/market/overview` 映射到了 `_get_cached_wind`，该函数直接返回 `{wind: {...}}`（无统一响应包装），导致前端 `results.overview?.wind` 取不到数据，DashboardGrid 不渲染，**全屏黑屏**。

**调试方法**:
```python
# 检查 FastAPI 路由映射
python3 -c "from app.routers import market; 
[print(r.path, '->', r.endpoint.__name__) for r in market.router.routes if 'overview' in r.path]"
# 修复前: /market/overview -> _get_cached_wind  ❌
# 修复后: /market/overview -> market_overview    ✅
```

**修复**: 将装饰器移至 `async def market_overview()` 之前。

---

## 2. 数据流断裂问题

### 🔴 P0-B: 前端数据提取路径与后端响应格式不匹配

**文件**: `App.vue`, `DashboardGrid.vue`, `SentimentGauge.vue`

**问题**: `market_overview` API 修复后直接返回 Sina 实时数据（`{wind: {...}, meta: {...}}`），但前端多处代码使用旧格式提取：
- `App.vue`: `results.overview?.wind` — 需要 `results.overview.data.wind`
- `DashboardGrid.vue`: `props.marketData?.wind` — `marketData` 已是 wind 对象
- `DashboardGrid.vue`: `item.index` — Sina 数据用 `item.price`
- `SentimentGauge.vue`: `props.marketData?.wind` + 缺少 `macroData` prop

**修复**:
1. `App.vue`: `marketOverview.value = results.overview?.wind || results.overview || null`
2. `DashboardGrid.vue`: `props.marketData || {}` + `item.price ?? item.index ?? 0`
3. `SentimentGauge.vue`: `props.marketData || {}` + 添加 `macroData` prop

---

## 3. 实时性问题

### 🔴 P0-C: `quote_detail` 从 DB 读最大 70 秒延迟

**文件**: `backend/app/routers/market.py`, `backend/app/services/scheduler.py`

**问题**: 
- `fetch_all_and_buffer()` 每 60 秒写入 `write_buffer`
- `flush_write_buffer()` 每 10 秒刷入 `market_data_realtime`
- `quote_detail` 从 `market_data_realtime` 读 → 最大延迟 70 秒

**修复**:
1. `market_overview`: 直接调 `fetch_china_indices()` + `fetch_global_indices()`（Sina，~0延迟）+ 10秒缓存
2. `market_china_all`: 直接调 `fetch_china_all_indices()`（Sina）+ 10秒缓存
3. 调度器优化：fetch 60s→30s，flush 10s→5s
4. 前端轮询：30s→15s

**架构变更**:
```
旧: AkShare → scheduler(60s) → write_buffer → flush(10s) → DB → quote_detail
新: market_overview/china_all → Sina (直接) → ~0延迟
```

---

## 4. 发现但暂未修复的问题

### 🟠 P1: `quote_detail` 仍从 DB 读（最大 30 秒延迟）

**当前**: `quote_detail` 从 `market_data_realtime` 读，调度器每 30 秒刷新
**优化方案**: 直接读 `SpotCache`（由 `trigger_spot_fetch()` 每 30 秒更新）或直接调 Sina

### 🟠 P1: `npm run preview` 无 proxy（陷阱）

**当前**: `vite.config.js` 的 `server.proxy` 只在 dev 模式生效，preview 模式无 proxy
**问题**: 开发者可能习惯用 `npm run preview` 但因此遇到 404
**建议**: 在 `vite.config.js` 中添加 `preview.proxy` 配置

### 🟡 P2: `market_mock.py` 废弃文件

**文件**: `backend/app/routers/market_mock.py`
**问题**: Phase 2 的 mock 文件仍存在，且使用不同的数据格式（`index` vs `price`）
**建议**: 删除或标记为 deprecated

---

## 5. API 响应格式现状

| 端点 | 格式 | 延迟 | 状态 |
|------|------|------|------|
| `GET /market/overview` | `{code, data: {wind, meta}}` | ~0s (Sina) | ✅ |
| `GET /market/china_all` | `{code, data: {china_all}}` | ~0s (Sina) | ✅ |
| `GET /market/quote_detail` | `{code, data: {...}}` | ~30s (DB) | ⚠️ |
| `GET /market/history` | `{code, data: {...}}` | DB | ✅ |
| `GET /news/flash` | `{code, data: {news}}` | 实时 | ✅ |

---

## 6. 版本历史

| 版本 | 主要修复 |
|------|---------|
| v0.4.106 | API 统一格式、ECharts 内存泄漏、键盘快捷键 |
| v0.4.107 | 黑屏修复、实时性修复、数据流断裂修复 |
| v0.4.108 | Decorator bug 修复 |
