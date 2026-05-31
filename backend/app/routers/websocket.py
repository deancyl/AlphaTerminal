"""
WebSocket 路由 — 统一端点 /ws/market
支持 JSON 动态订阅/取消订阅
心跳保活：服务端主动 ping，客户端响应 pong
断连恢复：客户端发送 last_seq，服务端返回缺失的 tick
"""

import asyncio
import json
import logging
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.ws_manager import ws_manager, PING_INTERVAL, PONG_TIMEOUT
from app.services.tick_buffer import tick_buffer
from app.config.settings import get_settings
from app.utils.error_decorator import handle_errors

logger = logging.getLogger(__name__)
router = APIRouter()


def validate_origin(origin: str) -> bool:
    """Validate WebSocket connection origin against allowed origins."""
    if not origin:
        return False

    settings = get_settings()
    allowed_origins = settings.get_allowed_origins_list()

    if allowed_origins == ["*"]:
        return True

    origin_lower = origin.lower()
    for allowed in allowed_origins:
        if allowed.lower() == origin_lower:
            return True
        if allowed.endswith("*") and origin_lower.startswith(allowed[:-1].lower()):
            return True

    return False


@router.websocket("/ws/market")
@handle_errors(module="websocket")
async def ws_market(ws: WebSocket):
    """
    统一 WebSocket 端点。

    客户端连接后，通过发送 JSON 消息订阅股票：
      {"action": "subscribe",   "symbols": ["600519", "000858"]}
      {"action": "unsubscribe", "symbols": ["600519"]}
      {"action": "pong"}        → 客户端响应心跳
      {"action": "recover", "symbols": [{"symbol": "600519", "last_seq": 123}]} → 断连恢复
      {"action": "subscribe", "channel": "timemachine:test123"} → 订阅回放事件
      {"action": "unsubscribe", "channel": "timemachine:test123"} → 取消订阅回放事件

    服务端推送格式（由 scheduler 广播）：
      Tick 消息（实时行情）：
      {"type": "tick", "symbol": "600519", "name": "贵州茅台",
       "price": 1680.5, "chg": 20.5, "chg_pct": 1.23,
       "volume": 123456, "amount": 98765432, "turnover": 0.5,
       "market": "sh", "data_type": "realtime", "timestamp": 1712467200,
       "seq": 124}  # 序列号

      TimeMachine Event message:
      {"type": "timemachine_event", "session_id": "abc123", "data": {
        "bar_index": 42,
        "timestamp": "2024-01-15T10:30:00",
        "bar": {"open": 1800, "high": 1810, "low": 1795, "close": 1805, "volume": 1000000}
      }}
      
      Subscribe: {"action": "subscribe", "channel": "timemachine:{session_id}"}
      Unsubscribe: {"action": "unsubscribe", "channel": "timemachine:{session_id}"}

      断连恢复消息：
      {"type": "tick", "symbol": "600519", ..., "seq": 123, "recovered": true}

      订阅确认：
      {"type": "subscribed", "symbols": ["600519", "000858"]}
      {"type": "subscribed", "channel": "timemachine:abc123"}

      取消订阅确认：
      {"type": "unsubscribed", "symbols": ["600519"]}

      心跳探测：
      {"type": "ping"}

      性能指标广播（全局推送，无需订阅）：
      {"type": "performance_metrics", "data": {...}, "timestamp": "2026-05-30T10:00:00"}
      - data 包含 avg_latency_ms, p95_latency_ms, total_requests, success_rate 等指标
      - 每 5 秒由 scheduler 推送给所有连接

    协议规范：
      - 所有服务端消息必须包含 "type" 字段
      - symbol 订阅匹配不区分大小写（后端统一转小写处理）
      - 服务端每 25 秒发送 ping，客户端需在 10 秒内响应 pong
      - 客户端重连时可发送 last_seq 请求断连期间的 tick
    """
    origin = ws.headers.get("origin", "") or ws.headers.get("Origin", "")
    if not validate_origin(origin):
        logger.warning(f"WebSocket connection rejected from invalid origin: {origin}")
        await ws.close(code=1008, reason="Invalid origin")
        return

    await ws.accept()

    conn = await ws_manager.connect(ws)
    ping_time = None

    async def send_json(data):
        try:
            await ws.send_text(json.dumps(data, ensure_ascii=False))
        except Exception as e:
            logger.warning(
                f"[WS] Failed to send message: {type(e).__name__}: {e}", exc_info=True
            )

    async def handle_message(raw: str):
        nonlocal ping_time
        try:
            msg = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return

        msg_type = msg.get("type", "")
        action = msg.get("action", "")
        symbols = msg.get("symbols", [])
        channel = msg.get("channel", "")

        if action == "subscribe":
            if symbols:
                success, error = await ws_manager.subscribe(conn, symbols)
                if success:
                    await send_json(
                        {"type": "subscribed", "symbols": list(await conn.get_symbols())}
                    )
                else:
                    await send_json({"type": "error", "message": error})
            elif channel and channel.startswith("timemachine:"):
                session_id = channel.split(":")[1]
                async with ws_manager._conn_lock:
                    if channel not in ws_manager._subscriptions:
                        ws_manager._subscriptions[channel] = set()
                    ws_manager._subscriptions[channel].add(conn)
                await send_json({"type": "subscribed", "channel": channel})

        elif action == "unsubscribe":
            if symbols:
                await ws_manager.unsubscribe(conn, symbols)
                await send_json(
                    {"type": "unsubscribed", "symbols": list(await conn.get_symbols())}
                )
            elif channel and channel.startswith("timemachine:"):
                async with ws_manager._conn_lock:
                    if channel in ws_manager._subscriptions:
                        ws_manager._subscriptions[channel].discard(conn)
                        if not ws_manager._subscriptions[channel]:
                            del ws_manager._subscriptions[channel]
                await send_json({"type": "unsubscribed", "channel": channel})

        elif action == "recover":
            # 断连恢复：发送缺失的 tick
            recover_symbols = msg.get("symbols", [])
            total_recovered = 0

            for item in recover_symbols:
                symbol = item.get("symbol", "")
                last_seq = item.get("last_seq", 0)

                if not symbol:
                    continue

                missed_ticks = tick_buffer.get_since(symbol, last_seq)

                for tick_item in missed_ticks:
                    recovered_tick = {
                        **tick_item["tick"],
                        "seq": tick_item["seq"],
                        "recovered": True,
                    }
                    await send_json(recovered_tick)
                    total_recovered += 1

            if total_recovered > 0:
                logger.info(
                    f"[WS] Recovered {total_recovered} ticks for {len(recover_symbols)} symbols"
                )

            # 发送恢复完成确认
            await send_json(
                {"type": "recovery_complete", "recovered_count": total_recovered}
            )

        elif msg_type == "pong":
            if ping_time:
                latency = (time.time() - ping_time) * 1000
                conn.update_pong(latency)
                ping_time = None

        elif msg_type == "ping":
            await send_json({"type": "pong"})

    try:
        first = await asyncio.wait_for(ws.receive_text(), timeout=10.0)
        await handle_message(first)

        while True:
            try:
                data = await asyncio.wait_for(
                    ws.receive_text(), timeout=PING_INTERVAL + PONG_TIMEOUT
                )
            except asyncio.TimeoutError:
                break

            await handle_message(data)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"WebSocket error: {type(e).__name__}: {e}", exc_info=True)
    finally:
        await ws_manager.disconnect(conn)
