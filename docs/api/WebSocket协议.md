# WebSocket 协议说明

## 概述

AlphaTerminal 提供 WebSocket 实时数据推送服务，支持行情订阅、心跳检测、消息批量发送等功能。本文档说明 WebSocket 端点、消息类型、心跳机制以及连接生命周期。

---

## WebSocket 端点

### 连接地址

```
ws://localhost:60100/ws
```

**生产环境**：
```
wss://your-domain.com/ws
```

### 连接示例

```javascript
// JavaScript
const ws = new WebSocket('ws://localhost:60100/ws')

ws.onopen = () => {
  console.log('WebSocket connected')
  // 订阅行情
  ws.send(JSON.stringify({
    action: 'subscribe',
    symbols: ['sh600519', 'sz000001']
  }))
}

ws.onmessage = (event) => {
  const data = JSON.parse(event.data)
  console.log('Received:', data)
}

ws.onerror = (error) => {
  console.error('WebSocket error:', error)
}

ws.onclose = () => {
  console.log('WebSocket disconnected')
}
```

```python
# Python (websockets)
import asyncio
import websockets
import json

async def connect():
    async with websockets.connect('ws://localhost:60100/ws') as ws:
        # 订阅行情
        await ws.send(json.dumps({
            'action': 'subscribe',
            'symbols': ['sh600519', 'sz000001']
        }))
        
        # 接收消息
        while True:
            message = await ws.recv()
            data = json.loads(message)
            print('Received:', data)

asyncio.run(connect())
```

---

## 消息类型

### 客户端 → 服务器

#### 1. 订阅行情 (subscribe)

```json
{
  "action": "subscribe",
  "symbols": ["sh600519", "sz000001", "sh000001"]
}
```

**响应**：
```json
{
  "type": "subscribe_result",
  "success": true,
  "symbols": ["sh600519", "sz000001", "sh000001"],
  "message": ""
}
```

#### 2. 取消订阅 (unsubscribe)

```json
{
  "action": "unsubscribe",
  "symbols": ["sh600519"]
}
```

**响应**：
```json
{
  "type": "unsubscribe_result",
  "success": true,
  "symbols": ["sh600519"]
}
```

#### 3. 心跳响应 (pong)

```json
{
  "action": "pong"
}
```

**说明**：客户端收到 `ping` 消息后，应立即回复 `pong`。

### 服务器 → 客户端

#### 1. 行情推送 (quote)

```json
{
  "type": "quote",
  "data": {
    "symbol": "sh600519",
    "name": "贵州茅台",
    "price": 1800.50,
    "change": 25.30,
    "change_pct": 1.42,
    "volume": 12345678,
    "amount": 2222222222.22,
    "high": 1810.00,
    "low": 1780.00,
    "open": 1790.00,
    "prev_close": 1775.20,
    "time": "2026-05-31T10:30:00",
    "seq": 12345
  },
  "timestamp": "2026-05-31T10:30:00.123456"
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `symbol` | string | 股票代码（带前缀） |
| `name` | string | 股票名称 |
| `price` | float | 当前价格 |
| `change` | float | 涨跌额 |
| `change_pct` | float | 涨跌幅（%） |
| `volume` | int | 成交量（手） |
| `amount` | float | 成交额（元） |
| `high` | float | 最高价 |
| `low` | float | 最低价 |
| `open` | float | 开盘价 |
| `prev_close` | float | 昨收价 |
| `time` | string | 行情时间 |
| `seq` | int | 序列号（用于去重） |

#### 2. 性能指标推送 (performance_metrics)

```json
{
  "type": "performance_metrics",
  "data": {
    "stats": {
      "total_requests": 15420,
      "avg_latency_ms": 45.2,
      "p95_latency_ms": 120.5,
      "p99_latency_ms": 350.8,
      "success_rate": 98.5,
      "error_rate": 1.5,
      "cache_hit_rate": 45.2
    },
    "top_endpoints": [
      {
        "endpoint": "/api/v1/market/quote",
        "request_count": 5420,
        "avg_ms": 35.2,
        "error_rate": 0.5
      }
    ]
  },
  "timestamp": "2026-05-31T10:30:00"
}
```

**说明**：每 5 秒广播一次，无需订阅，所有连接都会收到。

#### 3. 心跳请求 (ping)

```json
{
  "type": "ping"
}
```

**说明**：服务器每 25 秒发送一次 `ping`，客户端应在 10 秒内回复 `pong`。

#### 4. 订阅结果 (subscribe_result)

```json
{
  "type": "subscribe_result",
  "success": true,
  "symbols": ["sh600519", "sz000001"],
  "message": ""
}
```

#### 5. 错误消息 (error)

```json
{
  "type": "error",
  "code": 120,
  "message": "订阅数量超过限制（最大 50 个）"
}
```

---

## 心跳机制

### 配置参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `PING_INTERVAL` | 25s | 服务器发送 ping 间隔 |
| `PONG_TIMEOUT` | 10s | 等待 pong 响应超时 |
| `CLEANUP_INTERVAL` | 30s | 死连接清理间隔 |

### 心跳流程

```
服务器                              客户端
  │                                   │
  ├── 每 25s 发送 ping ──────────────►│
  │                                   │
  │◄──────── 立即回复 pong ───────────┤
  │                                   │
  ├── 更新 last_pong 时间             │
  │                                   │
  ├── 如果 10s 内未收到 pong ────────►│ 标记为死连接
  │                                   │
  ├── 每 30s 清理死连接 ─────────────►│ 断开连接
```

### 客户端实现

```javascript
// 正确的心跳处理
ws.onmessage = (event) => {
  const data = JSON.parse(event.data)
  
  if (data.type === 'ping') {
    // 立即回复 pong
    ws.send(JSON.stringify({ action: 'pong' }))
    return
  }
  
  // 处理其他消息
  handleMessage(data)
}
```

### 延迟检测

服务器记录每次 pong 响应的延迟：

```json
{
  "type": "latency_update",
  "latency_ms": 15.5
}
```

---

## 连接生命周期

### 生命周期图

```
创建连接 → 认证通过 → 订阅行情 → 接收推送 → 心跳维持 → 断开连接
    │          │          │          │          │          │
    │          │          │          │          │          └── 清理订阅
    │          │          │          │          └── 超时/主动断开
    │          │          │          └── 批量发送（50ms）
    │          │          └── 最多 50 个订阅
    │          └── 连接限制（100 个）
    └── ws://localhost:60100/ws
```

### 连接限制

| 限制项 | 值 | 说明 |
|--------|-----|------|
| **最大连接数** | 100 | 服务器最大并发连接 |
| **最大订阅数** | 50 | 每个连接最多订阅 50 个股票 |
| **消息速率** | 100 msg/s | 每秒最多 100 条消息 |

### 连接拒绝

当超过限制时，服务器返回 WebSocket Close Code：

```javascript
// 连接数超过限制
ws.onclose = (event) => {
  if (event.code === 1013) {
    console.error('Connection limit exceeded')
  }
}
```

---

## 消息批量发送

### 批量机制

服务器使用批量发送优化性能：

| 参数 | 值 | 说明 |
|------|-----|------|
| `BATCH_INTERVAL` | 50ms | 批量发送间隔 |
| `MAX_MSG_PER_SECOND` | 100 | 每秒最大消息数 |

### 批量流程

```
Tick 到达 → 加入批量队列 → 等待 50ms → 批量发送给订阅者
     │            │              │              │
     │            │              │              └── 一次发送多条消息
     │            │              └── 减少网络往返
     │            └── 按股票分组
     └── 实时行情更新
```

### 客户端处理

```javascript
// 批量消息处理
const tickBuffer = []

ws.onmessage = (event) => {
  const data = JSON.parse(event.data)
  
  if (data.type === 'quote') {
    tickBuffer.push(data.data)
    
    // 批量处理（例如每 100ms 更新一次 UI）
    requestAnimationFrame(() => {
      updateUI(tickBuffer)
      tickBuffer.length = 0
    })
  }
}
```

---

## 订阅管理

### 订阅限制

```javascript
// 错误：订阅超过限制
ws.send(JSON.stringify({
  action: 'subscribe',
  symbols: [/* 51 个股票代码 */]
}))

// 响应
{
  "type": "error",
  "code": 120,
  "message": "订阅数量超过限制（最大 50 个）"
}
```

### 动态订阅

```javascript
// 动态添加订阅
function addSubscription(symbol) {
  ws.send(JSON.stringify({
    action: 'subscribe',
    symbols: [symbol]
  }))
}

// 动态移除订阅
function removeSubscription(symbol) {
  ws.send(JSON.stringify({
    action: 'unsubscribe',
    symbols: [symbol]
  }))
}
```

### 查询订阅列表

```javascript
// 客户端维护订阅列表
const subscriptions = new Set()

ws.onmessage = (event) => {
  const data = JSON.parse(event.data)
  
  if (data.type === 'subscribe_result' && data.success) {
    data.symbols.forEach(s => subscriptions.add(s))
  }
  
  if (data.type === 'unsubscribe_result' && data.success) {
    data.symbols.forEach(s => subscriptions.delete(s))
  }
}
```

---

## 序列号与去重

### 序列号机制

每条行情消息包含 `seq` 字段：

```json
{
  "type": "quote",
  "data": {
    "symbol": "sh600519",
    "seq": 12345,
    ...
  }
}
```

### 客户端去重

```javascript
const lastSeq = {}

ws.onmessage = (event) => {
  const data = JSON.parse(event.data)
  
  if (data.type === 'quote') {
    const symbol = data.data.symbol
    const seq = data.data.seq
    
    // 跳过旧消息
    if (lastSeq[symbol] && seq <= lastSeq[symbol]) {
      return
    }
    
    lastSeq[symbol] = seq
    processQuote(data.data)
  }
}
```

---

## 断线重连

### 重连策略

```javascript
class WebSocketManager {
  constructor(url) {
    this.url = url
    this.ws = null
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 10
    this.reconnectDelay = 1000
    this.subscriptions = new Set()
  }
  
  connect() {
    this.ws = new WebSocket(this.url)
    
    this.ws.onopen = () => {
      console.log('Connected')
      this.reconnectAttempts = 0
      
      // 重新订阅
      if (this.subscriptions.size > 0) {
        this.ws.send(JSON.stringify({
          action: 'subscribe',
          symbols: Array.from(this.subscriptions)
        }))
      }
    }
    
    this.ws.onclose = () => {
      this.scheduleReconnect()
    }
    
    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }
  }
  
  scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnect attempts exceeded')
      return
    }
    
    // 指数退避 + 随机抖动
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts)
    const jitter = Math.random() * 1000
    
    setTimeout(() => {
      this.reconnectAttempts++
      this.connect()
    }, delay + jitter)
  }
  
  subscribe(symbols) {
    symbols.forEach(s => this.subscriptions.add(s))
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        action: 'subscribe',
        symbols
      }))
    }
  }
}
```

---

## 性能指标

### 连接指标

```bash
# 查询 WebSocket 指标
curl http://localhost:60100/api/v1/admin/websocket/metrics

# 响应
{
  "code": 0,
  "data": {
    "active_connections": 45,
    "max_connections": 100,
    "latency_avg": 15.5,
    "latency_min": 5.2,
    "latency_max": 45.8,
    "subscribed_symbols": 120,
    "batch_queue_size": 25,
    "max_subscriptions": 50,
    "max_msg_per_second": 100
  }
}
```

### Prometheus Metrics

```bash
# 查询 Prometheus 指标
curl http://localhost:8002/api/v1/metrics | grep websocket

# 输出
websocket_connections_active 45
websocket_connections_max 100
websocket_messages_sent_total 15420
websocket_messages_received_total 12345
websocket_latency_avg_ms 15.5
```

---

## 前端集成

### useMarketStream Composable

```javascript
// frontend/src/composables/useMarketStream.js
import { ref, onMounted, onUnmounted } from 'vue'

export function useMarketStream(initialSymbol = null) {
  const wsStatus = ref('disconnected')
  const quoteData = ref({})
  const performanceMetrics = ref(null)
  
  let ws = null
  let reconnectTimer = null
  
  function connect() {
    ws = new WebSocket('ws://localhost:60100/ws')
    
    ws.onopen = () => {
      wsStatus.value = 'connected'
      if (initialSymbol) {
        subscribe([initialSymbol])
      }
    }
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      
      if (data.type === 'ping') {
        ws.send(JSON.stringify({ action: 'pong' }))
        return
      }
      
      if (data.type === 'quote') {
        quoteData.value[data.data.symbol] = data.data
      }
      
      if (data.type === 'performance_metrics') {
        performanceMetrics.value = data.data
      }
    }
    
    ws.onclose = () => {
      wsStatus.value = 'disconnected'
      scheduleReconnect()
    }
  }
  
  function subscribe(symbols) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        action: 'subscribe',
        symbols
      }))
    }
  }
  
  function scheduleReconnect() {
    reconnectTimer = setTimeout(() => {
      connect()
    }, 3000)
  }
  
  onMounted(() => {
    connect()
  })
  
  onUnmounted(() => {
    if (reconnectTimer) clearTimeout(reconnectTimer)
    if (ws) ws.close()
  })
  
  return {
    wsStatus,
    quoteData,
    performanceMetrics,
    subscribe
  }
}
```

### 使用示例

```vue
<template>
  <div>
    <p>WebSocket: {{ wsStatus }}</p>
    <p>茅台价格: {{ quoteData['sh600519']?.price }}</p>
  </div>
</template>

<script setup>
import { useMarketStream } from '@/composables/useMarketStream'

const { wsStatus, quoteData, subscribe } = useMarketStream('sh600519')

// 动态订阅
function addStock(symbol) {
  subscribe([symbol])
}
</script>
```

---

## 测试验证

### 单元测试

```bash
# 运行 WebSocket 测试
cd backend
pytest tests/unit/test_services/test_ws_manager.py -v

# 测试用例：
# - test_connect
# - test_subscribe
# - test_unsubscribe
# - test_heartbeat
# - test_batch_send
# - test_rate_limit
```

### 手动测试

```javascript
// 浏览器控制台测试
const ws = new WebSocket('ws://localhost:60100/ws')

ws.onopen = () => {
  console.log('Connected')
  ws.send(JSON.stringify({
    action: 'subscribe',
    symbols: ['sh600519', 'sz000001']
  }))
}

ws.onmessage = (event) => {
  const data = JSON.parse(event.data)
  console.log('Received:', data)
}
```

---

## 常见问题

### Q1: 为什么连接会自动断开？

**A**: 
1. **心跳超时**：未在 10 秒内回复 pong
2. **连接限制**：超过 100 个并发连接
3. **网络问题**：客户端网络断开

### Q2: 如何处理断线重连？

**A**: 使用指数退避 + 随机抖动策略，避免重连风暴。

### Q3: 为什么使用批量发送？

**A**: 
- 减少网络往返次数
- 降低 CPU 使用率
- 提高吞吐量

### Q4: 如何调试 WebSocket？

**A**: 
1. 浏览器开发者工具 → Network → WS
2. 查看消息内容和时间戳
3. 检查心跳是否正常

---

## 相关文档

- [认证说明](./认证说明.md)
- [速率限制](./速率限制.md)
- [错误码说明](./错误码说明.md)

---

**文档版本**: v0.6.220  
**最后更新**: 2026-05-31