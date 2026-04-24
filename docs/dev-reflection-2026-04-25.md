# 2026-04-25 开发反思与经验总结

## 本次修复内容

### 1. 投资组合持仓显示问题
**问题**: 组合页面始终显示"暂无持仓"
**根因**: `/positions` API 查询的是空的 `positions` 表，而非实际存储数据的 `position_summary` 表
**修复**: 
- 修改 `portfolio.py` 的 `list_positions` 和 `portfolio_pnl` 函数，从 `position_summary` 读取
- 添加字段映射（`marketValue`, `cost`, `unrealized_pnl`）对齐前端期望

### 2. 回测结果不持久化
**问题**: 跑完回测刷新页面，历史记录消失
**根因**: `/backtest/run` 只返回 JSON，未写入 `backtest_results` 表
**修复**: 在 `backtest.py` 的 `run_backtest` 函数中添加 INSERT 逻辑，保存结果到数据库

### 3. 进程保活 Watchdog
**新增功能**:
- 后端 `watchdog.py`: 每30秒健康检查，崩溃时自动重启
- Admin API: `/watchdog/status`, `/watchdog/toggle`, `/watchdog/restart`
- Admin 面板: 开关控制、状态显示、手动重启
**前端修复**: 处理 `apiFetch` 自动提取 `data` 字段的问题

### 4. 行情数据同步阻塞
**问题**: `quote_source.py` 使用同步 `httpx.get`，阻塞 FastAPI 事件循环
**修复**: 
- 改为 `httpx.Client` 上下文管理器
- 新增 `get_quote_with_fallback_async()` 使用 `asyncio.to_thread()` 隔离阻塞

### 5. Mock 数据字段缺失
**问题**: `_mock_fund_info` 缺少 `accumulated_nav`, `rating` 等字段，导致前端解构报错
**修复**: 补全 Mock 数据至14个字段

### 6. Vue 组件错误
**问题**: `BondHistoryModal.vue` 使用 `onUnmounted` 但未从 Vue 导入
**修复**: 添加 `onUnmounted` 到 import 语句

---

## 关键教训

### 教训 1: 数据表与 API 不匹配
**现象**: 数据库有数据，API 返回空
**原因**: `position_lots`/`position_summary` 是新 lot-based 系统，但 `positions` 表是旧表
**经验**: 修改数据模型时，必须同步更新所有查询该表的 API

### 教训 2: apiFetch 自动提取 data 字段
**现象**: 后端返回 `{code: 0, data: {...}}`，前端收到 `{...}`
**原因**: `apiFetch` 内部调用 `extractData()` 自动提取 `data` 字段
**经验**: 前端处理 API 响应时，要了解中间层的转换逻辑

### 教训 3: 进程死亡 vs 代码 Bug
**现象**: 全站 500 错误，怀疑代码问题
**实际**: 后端进程已死亡，端口无监听
**经验**: 遇到 500 错误时，先检查进程状态，再检查代码

### 教训 4: 乐观更新与错误处理
**问题**: Watchdog 开关切换后 UI 不更新
**改进**: 添加乐观更新（立即改 UI）、错误回滚、加载状态、详细日志

---

## 技术决策记录

### 决策 1: 保持同步 HTTP 客户端，用 to_thread 隔离
**选择**: 不改为 `httpx.AsyncClient`，而是 `asyncio.to_thread()` 包装同步调用
**理由**: 
- 避免 AsyncClient 连接池泄漏问题
- 同步代码更易调试和测试
- 网络阻塞在独立线程，不卡主事件循环

### 决策 2: Watchdog 自包含设计
**选择**: Watchdog 作为独立线程运行，不依赖 systemd/pm2
**理由**:
- 环境约束（无 sudo，无 Docker 权限）
- 自包含，可移植
- 通过 Admin API 可控

---

## 版本信息

- **版本**: v0.5.167
- **提交**: cb0a0a8
- **推送**: 成功同步至 GitHub

---

## 待办事项

- [ ] 图表渲染延迟问题（CDN 加载时序）
- [ ] Admin 数据源 Matrix 面板
- [ ] 回测-组合联动（strategy_id/portfolio_id 关联）
- [ ] 宏观数据面板（GDP/CPI/PMI）
