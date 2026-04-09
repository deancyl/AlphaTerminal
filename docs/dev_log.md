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

| 端点 | 状态 | 说明 |
|------|------|------|
| `/api/v1/market/overview` | ✅ | 风向标数据 |
| `/api/v1/market/china_all` | ✅ | 国内10+指数 |
| `/api/v1/news/flash` | ✅ | 快讯 |
| `/api/v1/chat` | ✅ | Copilot对话 |

---

## 2026-04-09 v0.4.106 - 代码审计与P0修复

### 代码审计 (AUDIT_REPORT_v4.md)

完成全面项目审计，评估：
1. 与专业金融平台（Wind/Bloomberg）的差距
2. 前端 UI 潜在问题（P0~P2 分级）
3. 前后端代码协同问题
4. 整体代码质量

### P0 修复 (v0.4.106)

#### F1: `quote_detail` API 完全损坏
- **根因**: `w.get('index')` 取不到数据（字段是 `price`）
- **修复**: 改为 `w.get('price')`，统一用 `db_sym` 查 `market_data_daily`
- **额外**: amplitude 计算改为 `(high-low)/prev_close * 100`
- **文件**: `backend/app/routers/market.py`

#### F2: Symbol Normalization 三套并行
- **修复**: `_unprefix(norm)` 在所有 DB 查询处统一使用
- **文件**: `backend/app/routers/market.py`

#### F3: ECharts 内存泄漏
- **修复**: 添加 `onBeforeUnmount` 立即 dispose，保留 `onUnmounted` 双重保险
- **文件**: `frontend/src/components/FullscreenKline.vue`

#### F4: API 响应格式不统一
- **修复**: `market_history` 和 `quote_detail` 统一使用 `success_response()` 包装
- **新增**: `frontend/src/utils/apiCompat.js` - 统一数据提取器，兼容新旧格式
- **更新组件**: `FullscreenKline.vue`, `IndexLineChart.vue`, `AdvancedKlinePanel.vue`

#### F5: 键盘快捷键失效
- **修复**: 注册 window 级别 `keydown` 监听器，`Escape` 正确触发关闭
- **文件**: `frontend/src/components/FullscreenKline.vue`

#### F6: callable() 替代 hasattr 检查
- **修复**: `hasattr(..., '__code__')` → `callable(...)` 规范
- **文件**: `backend/app/routers/market.py`

### API 变更
- `GET /market/quote_detail/{symbol}` → `{code:0, data: {...}}`
- `GET /market/history/{symbol}` → `{code:0, data: {...}}`

---

## 2026-04-09 v0.4.107 - P0问题修复

### 用户反馈的5个问题
1. K线数据非实时
2. WebLLM加载两个模型导致移动端崩溃
3. 投资组合功能待完善
4. 国内指数数据缺失
5. 全市场个股名称宽度过宽

### P0修复 (v0.4.107)

#### F1: K线自动刷新
- **文件**: `frontend/src/components/FullscreenKline.vue`
- **修复**: 添加 `setInterval` 每30秒自动刷新K线数据
- **代码**: `refreshTimer = setInterval(() => { fetchData(); fetchQuote() }, 30000)`

#### F2: WebLLM仅加载1个模型
- **文件**: `frontend/src/components/CopilotSidebar.vue`
- **修复**: 模型列表从3个减少到1个 (SmolLM2-360M, ~200MB)
- **避免**: 顺序尝试多个模型导致的内存溢出

#### F3: 移动端禁用WebLLM
- **文件**: `frontend/src/components/CopilotSidebar.vue`
- **修复**: 检测移动设备 (`/Android|iPhone/i`) 和低内存 (`navigator.deviceMemory < 4`)
- **行为**: 自动禁用WebLLM，提示用户使用云端模式

#### F4: 股票名称宽度限制
- **文件**: `frontend/src/components/StockScreener.vue`
- **修复**: 添加 `max-w-[80px] truncate` 和 `title` 提示
- **避免**: 长名称撑破表格布局

### 审计报告
- `docs/AUDIT_REPORT_v5.md` - 全面审计报告，包含差距分析、问题分级、修复计划

### 待解决问题 (P1)
- 投资组合高级功能 (风险指标、归因分析)
- 全市场个股数据接入 (目前仅50只)
- 骨架屏加载状态
- WebSocket实时数据流架构
