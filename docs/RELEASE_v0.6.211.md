# v0.6.211 Release Notes

## 外汇模块深度审计修复

**发布日期**: 2026-05-29

本次发布针对外汇模块进行了全面的深度审计，修复了12个关键问题（7个P0 + 5个P1），显著提升了系统的稳定性、安全性和用户体验。

---

## Wave 1 - P0 Critical Fixes (7个)

### 1. ForexDashboard KeepAlive 生命周期修复

**问题**: 组件通过KeepAlive缓存后，重新激活时不刷新数据。

**修复**: 添加`onActivated` hook，实现：
- 检查并刷新空数据
- 重启时间更新定时器
- 重启自动轮询

**文件**: `frontend/src/components/ForexDashboard.vue`

---

### 2. httpx Import 缺失修复

**问题**: 代码引用`httpx.HTTPError`但未导入httpx模块，导致异常处理失败。

**修复**: 添加`import httpx`导入。

**文件**: `backend/app/routers/forex.py:22`

---

### 3. 错误消息敏感信息泄露修复 (CWE-209)

**问题**: 使用`str(e)`直接暴露内部错误详情（路径、API密钥、堆栈跟踪）。

**修复**: 替换为`sanitize_error(e)`，清洗敏感信息。

**文件**: `backend/app/routers/forex.py` (5处替换)

---

### 4. 熔断器回退后永不恢复修复

**问题**: fallback成功获取数据后未调用`record_success()`，熔断器保持OPEN状态。

**修复**: 在3个fallback路径添加`self.cb.record_success()`调用。

**文件**: `backend/app/services/fetchers/forex_fetcher.py:239,252,267`

---

### 5. WebSocket恢复序列号验证

**问题**: 恢复期间旧数据可能覆盖新数据，导致数据损坏。

**修复**: 添加序列号验证逻辑，跳过`seq <= lastSeq`的旧数据。

**文件**: `frontend/src/composables/useMarketStream.js:443-448`

---

### 6. CFETS端点超时保护

**问题**: `/cfets`、`/cfets/cross`、`/official`端点无超时保护，可能无限等待。

**修复**: 添加30秒`asyncio.wait_for()`超时保护。

**文件**: `backend/app/routers/forex.py:513,550,592`

---

### 7. AbortController清理

**问题**: `onDeactivated`未取消待处理的AbortController，可能导致请求冲突。

**修复**: 添加`completeAbort()`调用清理所有待处理请求。

**文件**: `frontend/src/components/ForexDashboard.vue:410`

---

## Wave 2 - P1 High Priority Fixes (3个)

### 8. BaseKLineChart主题重新订阅

**问题**: `onDeactivated`取消主题订阅后，`onActivated`未重新订阅，主题变化不生效。

**修复**: 在`onActivated`中检查并重新订阅主题变化。

**文件**: `frontend/src/components/BaseKLineChart.vue:607`

---

### 9. Symbol参数验证

**问题**: `symbol`路径参数无验证，存在注入攻击风险。

**修复**: 添加`validate_forex_symbol()`函数，验证格式并防止注入。

**文件**: `backend/app/routers/forex.py:52-70`

---

### 10. Thundering Herd防护

**问题**: 多客户端同时请求stale数据触发多个并发API调用（惊群效应）。

**修复**: 添加`_forex_spot_fetch_lock`单飞锁，确保只有一个后台刷新任务。

**文件**: `backend/app/routers/forex.py:47-48,346-352,439-440`

---

## 修改文件清单

| 文件 | 修改类型 | 行数变化 |
|------|---------|---------|
| `frontend/src/components/ForexDashboard.vue` | 修改 | +20 |
| `frontend/src/composables/useMarketStream.js` | 修改 | +7 |
| `frontend/src/components/BaseKLineChart.vue` | 修改 | +6 |
| `backend/app/routers/forex.py` | 修改 | +60 |
| `backend/app/services/fetchers/forex_fetcher.py` | 修改 | +3 |
| `docs/FOREX_AUDIT_REPORT_v0.6.210.md` | 新增 | +580 |

**总计**: 6个文件，+676/-18行

---

## 验证结果

```
✅ Frontend build: Success
✅ Backend compile: Success
✅ All P0 fixes verified: 7/7
✅ All P1 fixes verified: 3/3
✅ Git push: Success
✅ Tag v0.6.211: Created and pushed
```

---

## 升级指南

```bash
# 拉取最新代码
git pull origin master

# 重新构建前端
cd frontend && npm run build

# 重启服务
./start-services.sh restart
```

---

## 后续计划

- v0.6.212: 组合模块深度审计
- v0.6.213: 回测模块深度审计
- v0.7.0: 架构重构版本

---

**审计报告**: `docs/FOREX_AUDIT_REPORT_v0.6.210.md`
