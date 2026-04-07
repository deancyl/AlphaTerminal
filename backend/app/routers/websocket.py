"""
WebSocket 路由：/ws/market/{symbol}
订阅指定股票的实时行情 tick
"""
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.ws_manager import ws_manager

router = APIRouter()


@router.websocket("/ws/market/{symbol}")
async def ws_market(ws: WebSocket, symbol: str):
    """
    前端 WS 客户端连接格式:
      ws://host:8002/ws/market/600519

    后端推送格式 (JSON):
      {
        "symbol": "600519",
        "price": 1680.5,
        "chg": 20.5,
        "chg_pct": 1.23,
        "volume": 1234567,
        "amount": 9876543210,
        "timestamp": 1712467200
      }

    前端可发送心跳 (text: "ping")，服务端回复 "pong"
    """
    # 标准化 symbol（去掉 sh/sz 前缀）
    clean = symbol.strip().lower()
    for p in ("sh", "sz", "hk", "us", "jp"):
        if clean.startswith(p):
            clean = clean[len(p):]
            break
    sym = clean

    await ws_manager.connect(ws, sym)
    try:
        while True:
            try:
                data = await asyncio.wait_for(ws.receive_text(), timeout=55.0)
            except asyncio.TimeoutError:
                # 心跳保活：55秒无消息则发送 ping
                try:
                    await ws.send_text("pong")
                except Exception:
                    break
                continue

            if data == "ping":
                await ws.send_text("pong")
                continue

            # 忽略其他客户端消息
            await ws.receive_text()

    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(ws, sym)
