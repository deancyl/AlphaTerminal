"""
WebSocket 路由 — 统一端点 /ws/market
支持 JSON 动态订阅/取消订阅
心跳保活 55 秒
"""
import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.ws_manager import ws_manager, WSConnection

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/market")
async def ws_market(ws: WebSocket):
    """
    统一 WebSocket 端点。

    客户端连接后，通过发送 JSON 消息订阅股票：
      {"action": "subscribe",   "symbols": ["600519", "000858"]}
      {"action": "unsubscribe", "symbols": ["600519"]}
      {"action": "ping"}       → 服务端回复 {"type": "pong"}

    服务端推送格式（由 scheduler 广播）：
      Tick 消息（实时行情）：
      {"type": "tick", "symbol": "600519", "name": "贵州茅台",
       "price": 1680.5, "chg": 20.5, "chg_pct": 1.23,
       "volume": 123456, "amount": 98765432, "turnover": 0.5,
       "market": "sh", "data_type": "realtime", "timestamp": 1712467200}
      
      订阅确认：
      {"type": "subscribed", "symbols": ["600519", "000858"]}
      
      取消订阅确认：
      {"type": "unsubscribed", "symbols": ["600519"]}
      
      心跳响应：
      {"type": "pong"}

    协议规范：
      - 所有服务端消息必须包含 "type" 字段
      - symbol 订阅匹配不区分大小写（后端统一转小写处理）
    """
    # 接受WebSocket连接
    await ws.accept()
    
    # 注册连接
    conn = await ws_manager.connect(ws)

    async def send_json(data):
        try:
            await ws.send_text(json.dumps(data, ensure_ascii=False))
        except Exception:
            pass

    async def handle_message(raw: str):
        try:
            msg = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return

        action = msg.get("action", "")
        symbols = msg.get("symbols", [])

        if action == "subscribe":
            await conn.subscribe(symbols)
            await send_json({
                "type": "subscribed",
                "symbols": list(await conn.get_symbols())
            })

        elif action == "unsubscribe":
            await conn.unsubscribe(symbols)
            await send_json({
                "type": "unsubscribed",
                "symbols": list(await conn.get_symbols())
            })

        elif action == "ping":
            await send_json({"type": "pong"})

    try:
        # 处理连接后的第一条消息：通常是 subscribe
        first = await asyncio.wait_for(ws.receive_text(), timeout=10.0)
        await handle_message(first)

        # 主循环
        while True:
            try:
                data = await asyncio.wait_for(ws.receive_text(), timeout=55.0)
            except asyncio.TimeoutError:
                # 55s 无消息，发送心跳探测
                try:
                    await ws.send_text(json.dumps({"type": "pong"}))
                except Exception:
                    break
                continue

            await handle_message(data)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"WebSocket error: {type(e).__name__}: {e}")
    finally:
        await ws_manager.disconnect(conn)
