# AlphaTerminal API 文档

## 概述

AlphaTerminal 后端基于 FastAPI，自动生成 OpenAPI/Swagger 文档。

- **Swagger UI**: `http://localhost:8002/docs`
- **ReDoc**: `http://localhost:8002/redoc`
- **OpenAPI JSON**: `http://localhost:8002/openapi.json`

## 响应格式

所有 API 响应使用统一的格式：

```json
{
  "code": 0,
  "message": "success",
  "data": {},
  "trace_id": "a1b2c3d4",
  "timestamp": 1714291200000
}
```

### 错误码

| 码段 | 含义 |
|------|------|
| 0 | 成功 |
| 1xx | 客户端错误 |
| 2xx | 服务端错误 |
| 3xx | 第三方错误 |
| 4xx | 业务逻辑错误 |

## 主要路由

### 市场数据

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/market/overview` | GET | 市场概览 |
| `/api/v1/market/indices` | GET | A股指数列表 |
| `/api/v1/market/china_all` | GET | 国内10+核心指数 |
| `/api/v1/market/macro` | GET | 宏观核心数据 |
| `/api/v1/market/symbols` | GET | 符号注册表 |
| `/api/v1/market/lookup/{symbol}` | GET | 符号查询 |
| `/api/v1/market/quote/{symbol}` | GET | 实时行情 |
| `/api/v1/market/history/{symbol}` | GET | 历史K线 |
| `/api/v1/market/all_stocks` | GET | 全市场A股列表 |
| `/api/v1/market/stocks/search` | GET | 个股搜索 |
| `/api/v1/market/fund_flow` | GET | 资金流向 |

### 回测引擎

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/backtest/strategies` | GET | 获取策略列表 |
| `/api/v1/backtest/strategies` | POST | 创建策略 |
| `/api/v1/backtest/run` | POST | 执行回测 |
| `/api/v1/backtest/results` | GET | 获取回测结果 |

### 投资组合

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/portfolio/` | GET | 组合列表 |
| `/api/v1/portfolio/` | POST | 创建组合 |
| `/api/v1/portfolio/{id}` | PUT | 更新组合 |
| `/api/v1/portfolio/{id}` | DELETE | 删除组合 |
| `/api/v1/portfolio/{id}/pnl` | GET | 组合盈亏 |

## 启动服务

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```
