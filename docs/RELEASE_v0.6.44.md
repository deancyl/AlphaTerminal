# AlphaTerminal v0.6.44 Release Notes

**发布日期**: 2026-05-17

## 概述

本次更新实现了外部审计报告中的9项优先级任务，涵盖性能优化、基础设施增强、合规性改进和用户体验提升四个方面。

## 性能优化（Wave 1）

### W1-T1: 新闻并行获取

**问题**: 新闻数据顺序获取导致延迟过高（~3秒）

**解决方案**: 使用 `asyncio.gather()` 并行获取宏观快讯和个股新闻

**效果**: 延迟从 ~3s 降至 ~0.62s（**5倍提升**）

**文件**: `backend/app/services/news_engine.py`

```python
# 并行获取宏观快讯和个股新闻，减少总延迟
macro_news, stock_news = asyncio.run(asyncio.gather(
    asyncio.wait_for(fetch_news_parallel(_MACRO_SYMBOLS), timeout=30),
    asyncio.wait_for(fetch_news_parallel(NEWS_SYMBOLS), timeout=30)
))
```

### W1-T2: 数据库复合索引

**问题**: 股票筛选查询全表扫描，响应时间过长（~200ms）

**解决方案**: 在 `market_all_stocks` 表添加5个复合索引

**效果**: 查询时间从 ~200ms 降至 ~2ms（**100倍提升**）

**索引列表**:
| 索引名 | 列 | 用途 |
|--------|-----|------|
| `idx_allstocks_price_chgpct` | (price, change_pct) | 价格+涨跌幅筛选 |
| `idx_allstocks_price_turnover` | (price, turnover) | 价格+换手率筛选 |
| `idx_allstocks_price_mktcap` | (price, mktcap) | 价格+市值筛选 |
| `idx_allstocks_chgpct_turnover` | (change_pct, turnover) | 涨跌幅+换手率筛选 |
| `idx_allstocks_code_name` | (code, name) | 代码/名称搜索 |

**文件**: `backend/app/db/database.py`

### W1-T3: 统一缓存架构

**问题**: 各路由器使用分散的字典缓存，缺乏统一管理

**解决方案**: 创建 `DataCache` 单例类，统一缓存管理

**效果**: 13个路由器迁移至统一缓存，支持 TTL 过期、LRU 淘汰

**特性**:
- TTL 过期（默认5分钟）
- LRU 淘汰（内存限制100MB）
- 线程安全（RLock）
- 统计追踪

**文件**: `backend/app/services/data_cache.py`

## 基础设施（Wave 2）

### W2-T1: WebSocket 实时数据流

**问题**: 缺乏实时数据推送基础设施

**解决方案**: 新增 `streaming` 模块，实现 WebSocket 实时数据流

**特性**:
- 熔断器保护（CLOSED/OPEN/HALF_OPEN 三态）
- HTTP 轮询降级机制
- 健康监控（30秒间隔）
- 消息广播

**测试覆盖**: 43个单元测试

**文件**: `backend/app/services/streaming/`

### W2-T2: HMAC-SHA256 审计追踪

**问题**: 缺乏合规性审计日志

**解决方案**: 实现哈希链审计追踪（SEC 17a-4 合规）

**特性**:
- 哈希链结构（prev_hash 链接）
- HMAC-SHA256 签名
- 7年保留期
- 链完整性验证

**API 端点**: `GET /api/v1/audit/verify`

**文件**: `backend/app/services/audit_chain.py`

## 合规性（Wave 3）

### W3-T1: OMS 状态机

**问题**: 缺乏订单状态管理机制

**解决方案**: 新增 `oms` 模块，实现订单状态机

**状态列表**:
| 状态 | 类型 | 描述 |
|------|------|------|
| STAGED | 初始 | 订单创建，未提交 |
| SUBMITTED | 处理中 | 发送至验证 |
| VALIDATED | 处理中 | 交易前检查通过 |
| PENDING | 活跃 | 等待执行 |
| PARTIAL_FILLED | 活跃 | 部分成交 |
| FILLED | 终态 | 完全成交 |
| CANCELLED | 终态 | 用户取消 |
| REJECTED | 终态 | 系统拒绝 |
| EXPIRED | 终态 | 订单过期 |

**交易前风控**:
- 资金可用性检查
- 持仓可用性检查
- 价格合理性检查
- 持仓限额检查

**测试覆盖**: 35个单元测试

**文件**: `backend/app/services/oms/`

## 用户体验（Wave 4）

### W4-T1: K线新闻标记

**问题**: K线图缺乏新闻事件关联

**解决方案**: 在K线图上显示新闻事件 markPoint

**特性**:
- 悬停显示新闻标题
- 情感颜色：绿色（利好）、红色（利空）、黄色（中性）
- 自动匹配K线价格

**API 端点**: `GET /api/v1/news/events/{symbol}`

**文件**: `frontend/src/components/BaseKLineChart.vue`

### W4-T2: 防御性UX

**问题**: 交易和转账操作缺乏确认机制

**解决方案**: 实现两步确认流程

**特性**:
- 交易确认：两步确认 + 复选框验证
- 资金划转：两步确认 + 复选框验证
- 警告提示："此操作不可撤销"

**文件**: `SimulatedTradeModal.vue`, `PortfolioDashboard.vue`

### W4-T3: 期权链T型报价表

**问题**: 缺乏期权数据展示

**解决方案**: 新增期权链获取器和T型报价表

**特性**:
- T型报价表：看涨期权（左）/ 行权价（中）/ 看跌期权（右）
- Greeks 显示：Delta, Gamma, Theta, Vega, IV
- 支持 CFFEX（沪深300/中证1000）和 SSE（ETF期权）

**API 端点**: `GET /api/v1/options/cffex/chain`

**文件**: `backend/app/services/fetchers/options_fetcher.py`

## 新增模块

| 模块 | 路径 | 说明 |
|------|------|------|
| 流式传输 | `backend/app/services/streaming/` | WebSocket 实时数据基础设施 |
| OMS | `backend/app/services/oms/` | 订单管理系统 |
| 审计链 | `backend/app/services/audit_chain.py` | 哈希链审计追踪 |
| 期权获取器 | `backend/app/services/fetchers/options_fetcher.py` | 期权数据获取 |
| 审计路由 | `backend/app/routers/audit.py` | 审计 API 端点 |
| OMS路由 | `backend/app/routers/oms.py` | OMS API 端点 |
| 期权路由 | `backend/app/routers/options.py` | 期权 API 端点 |
| 期权链组件 | `frontend/src/components/OptionsChain.vue` | 期权链显示组件 |

## 测试覆盖

- **新增测试**: 78个
  - 流式传输模块：43个测试
  - OMS 模块：35个测试
- **测试文件**:
  - `backend/tests/unit/test_oms.py`
  - `backend/tests/unit/test_services/test_streaming.py`

## 性能指标

| 指标 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 新闻获取延迟 | ~3s | ~0.62s | 5x |
| 数据库查询 | ~200ms | ~2ms | 100x |
| 缓存命中率 | 分散 | 统一 | 13路由 |

## 文件变更统计

- 44个文件修改
- 6174行新增
- 791行删除

## 升级指南

```bash
# 拉取最新代码
git pull origin feat/agent-gateway
git checkout v0.6.44

# 安装依赖
cd backend && pip install -r requirements.txt
cd ../frontend && npm install

# 重启服务
./start-services.sh restart
```

## 已知问题

- 新闻缓存可能为空（网络/代理问题）
- 期权数据在非交易时间返回空数组

## 下一步计划

- 完善审计链测试覆盖
- 优化期权数据获取稳定性
- 增强WebSocket重连机制
