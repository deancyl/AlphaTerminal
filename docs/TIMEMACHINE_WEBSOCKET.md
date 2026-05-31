# TimeMachine WebSocket Event System

## 概述

TimeMachine WebSocket事件系统支持实时推送回放进度更新，允许客户端订阅特定session的回放事件。

## 架构

```
┌─────────────────┐
│  PlaybackEngine │ ──broadcast_timemachine_event()──┐
└─────────────────┘                                    │
                                                       ▼
┌──────────────────────────────────────────────────────────┐
│                   ConnectionManager                        │
│  _subscriptions: {                                        │
│    "timemachine:session123": {conn1, conn2},             │
│    "timemachine:session456": {conn3}                      │
│  }                                                        │
└──────────────────────────────────────────────────────────┘
                      │
                      ▼ broadcast to subscribers
        ┌─────────────────────────────┐
        │     WebSocket Clients       │
        │  (subscribed to session)    │
        └─────────────────────────────┘
```

## API

### 后端方法

#### `broadcast_timemachine_event(session_id: str, event_data: dict)`

广播回放事件给订阅了指定session的所有客户端。

**参数**:
- `session_id`: 回放会话ID
- `event_data`: 事件数据，包含：
  - `bar_index`: 当前K线索引
  - `timestamp`: K线时间戳
  - `bar`: K线数据 (open, high, low, close, volume)

**示例**:
```python
from app.services.ws_manager import ws_manager

await ws_manager.broadcast_timemachine_event("abc123", {
    "bar_index": 42,
    "timestamp": "2024-01-15T10:30:00",
    "bar": {
        "open": 1800,
        "high": 1810,
        "low": 1795,
        "close": 1805,
        "volume": 1000000
    }
})
```

### WebSocket协议

#### 订阅session

```json
// 客户端发送
{"action": "subscribe", "channel": "timemachine:abc123"}

// 服务端响应
{"type": "subscribed", "channel": "timemachine:abc123"}
```

#### 取消订阅

```json
// 客户端发送
{"action": "unsubscribe", "channel": "timemachine:abc123"}

// 服务端响应
{"type": "unsubscribed", "channel": "timemachine:abc123"}
```

#### 接收事件

```json
// 服务端推送
{
    "type": "timemachine_event",
    "session_id": "abc123",
    "data": {
        "bar_index": 42,
        "timestamp": "2024-01-15T10:30:00",
        "bar": {
            "open": 1800,
            "high": 1810,
            "low": 1795,
            "close": 1805,
            "volume": 1000000
        }
    },
    "timestamp": "2024-01-15T10:30:00.123456"
}
```

## 使用示例

### 前端客户端

```javascript
// 建立WebSocket连接
const ws = new WebSocket('ws://localhost:60100/ws/market');

// 订阅session
ws.send(JSON.stringify({
    action: 'subscribe',
    channel: 'timemachine:abc123'
}));

// 监听事件
ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    
    if (message.type === 'timemachine_event') {
        console.log('Bar index:', message.data.bar_index);
        console.log('Bar data:', message.data.bar);
        updateChart(message.data);
    }
};

// 取消订阅
ws.send(JSON.stringify({
    action: 'unsubscribe',
    channel: 'timemachine:abc123'
}));
```

### 后端集成

```python
# backend/app/routers/timemachine.py

from app.services.ws_manager import ws_manager

async def play_next_bar(session_id: str):
    """播放下一根K线"""
    # ... 获取下一根K线数据 ...
    
    # 广播事件给订阅者
    await ws_manager.broadcast_timemachine_event(session_id, {
        "bar_index": current_index,
        "timestamp": bar.timestamp,
        "bar": {
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume
        }
    })
```

## 测试

```bash
# 运行TimeMachine事件测试
cd backend
pytest tests/unit/test_services/test_timemachine_event.py -v

# 运行所有WebSocket测试
pytest tests/unit/test_services/test_ws_heartbeat.py -v
```

## 线程安全

- `_subscriptions`字典通过`_conn_lock`保护
- 所有订阅操作都是原子的
- 连接错误被静默处理，不会影响其他订阅者

## 性能考虑

- 广播使用`send_json()`异步方法
- 错误连接在心跳检测中自动清理
- 每个session的订阅者数量无限制（受MAX_CONNECTIONS限制）

## 后续增强

- [ ] 添加认证逻辑（验证session_id有效性）
- [ ] 添加速率限制（防止高频广播）
- [ ] 添加历史事件缓存（支持断线重连）
