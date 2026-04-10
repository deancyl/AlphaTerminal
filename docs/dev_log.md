# AlphaTerminal 开发日志 (dev_log)

## 2026-04-09 v0.4.109 - 今日K线数据实时入库修复

### 问题描述
指标图表模块中K线显示"上一日及之前的数据"，今日数据缺失。

### 根因分析
1. `market_data_daily` 仅在后端启动时通过 `initial_backfill` 回填
2. `initial_backfill` 没有日志跟踪，执行状态不明
3. `market_data_daily` 没有定时刷新任务
4. AkShare 数据本身可用（今日4/9数据可正常获取）

### 修复内容 (scheduler.py)
1. `initial_backfill` 添加 try/except 日志
2. 新增 `today_daily_refresh` 任务，每5分钟刷新主要指数日K线
3. 确保今日数据在交易时段内定期入库

### 验证结果
```
K线API: 2026-04-09 close=3966.171 ✅
风向标: 上证指数 3966.1712 (-0.72%) ✅
```

---

## 2026-04-09 v0.4.108 - 国内指数/新闻数据展示修复

### 关键Bug修复
App.vue 数据提取逻辑中三元运算符优先级问题
```javascript
// 错误: a || b || Array.isArray(c) ? c : []
// 正确: a || b || (Array.isArray(c) ? c : [])
```
导致 chinaAllData/newsData 被错误赋值为整个对象而非数组。

---

## 2026-04-09 v0.4.107 - P0问题修复

### 用户反馈5个问题
1. ✅ K线数据非实时 - 添加30秒自动刷新
2. ❌ WebLLM加载失败 - VK_ERROR_UNKNOWN 显卡硬件限制
3. ⚠️ 投资组合功能待完善 - 需后续开发
4. ✅ 国内指数数据缺失 - 运算符优先级Bug修复
5. ✅ 股票名称宽度过宽 - 添加max-w-[80px] truncate

### WebLLM说明
`VK_ERROR_UNKNOWN` 表示显卡不支持 WebGPU Compute Shaders，无法通过代码修复。
建议使用云端模式（已自动检测并禁用WebLLM）。

---

## 2026-03-31 初始化

### 后端端口配置
- 后端端口：8002
- 前端端口：60100（Vite dev server）
- API 基础路径：`/api/v1`

### 进程状态
| 进程 | 端口 | 状态 |
|------|------|------|
| uvicorn (backend) | 8002 | ✅ 运行中 |
| vite (frontend) | 60100 | ✅ 运行中 |

## v0.4.116 — 2026-04-10

### 修复
- `usePortfolioStore.js` + `PortfolioDashboard.vue`: 修复 `snapshots.map is not a function`（ref 未 .value）
- `StockScreener.vue`: 修复全市场个股 price/chg_pct/turnover 为0（字段兼容）
- `StockScreener.vue`: 扩大加载至30页(6000条)覆盖全市场5494只
- `StockScreener.vue`: 股票名称列宽收紧至72px

### 发布
- GitHub Release: https://github.com/deancyl/AlphaTerminal/releases/tag/v0.4.116
- Git Tag: v0.4.116

## v0.4.117 — 2026-04-10

### 修复
- **API响应格式统一**: 消除 `{error:xxx}` 直接返回
- `market.py`: 统一使用 success_response/error_response
- `futures.py`: 统一响应格式
- `news.py`: 修复语法错误

### 发布
- GitHub Release: https://github.com/deancyl/AlphaTerminal/releases/tag/v0.4.117
- Git Tag: v0.4.117 (创建中)

### 状态
- 后端: 运行中
- 前端: 运行中

## v0.4.120 — 2026-04-10

### 修复
- API字段标准化层 - 统一price/turnover等字段兼容
- 添加 FIELD_MAP 字段映射表
- 添加 normalizeFields()

### 发布
- GitHub Release: https://github.com/deancyl/AlphaTerminal/releases/tag/v0.4.120
- Git Tag: v0.4.120

### 验证
- 日线/周线/月线/分时: 正常

## v0.4.124 — 2026-04-10

### 修复
- 全市场个股 `change` 字段自动计算
- 快讯轮询从 5 分钟缩短到 2 分钟
- 每 6 分钟执行一次 force_refresh 穿透刷新

### 发布
- GitHub Release: https://github.com/deancyl/AlphaTerminal/releases/tag/v0.4.124
- Git Tag: v0.4.124

## v0.4.126 — 2026-04-10

### 修复
- 市场情绪涨跌家数改为全市场真实统计（5497只）
- SpotCache 失败后自动 fallback 到 market_all_stocks

### 发布
- GitHub Release: https://github.com/deancyl/AlphaTerminal/releases/tag/v0.4.126
- Git Tag: v0.4.126
