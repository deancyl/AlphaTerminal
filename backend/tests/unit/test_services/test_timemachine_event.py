"""
TimeMachine WebSocket Event Tests
测试回放事件广播和订阅功能
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.ws_manager import ConnectionManager, WSConnection


class TestTimeMachineEventBroadcast:
    """测试TimeMachine事件广播功能"""

    @pytest.mark.asyncio
    async def test_broadcast_timemachine_event_no_subscribers(self):
        """测试无订阅者时的广播"""
        manager = ConnectionManager()
        
        # 无订阅者时应不报错
        await manager.broadcast_timemachine_event("test123", {
            "bar_index": 42,
            "timestamp": "2024-01-15T10:30:00",
            "bar": {"open": 1800, "high": 1810, "low": 1795, "close": 1805, "volume": 1000000}
        })

    @pytest.mark.asyncio
    async def test_broadcast_timemachine_event_with_subscribers(self):
        """测试有订阅者时的广播"""
        manager = ConnectionManager()
        
        # 创建mock连接
        mock_ws = AsyncMock()
        mock_conn = WSConnection(mock_ws)
        
        # 添加订阅者
        channel = "timemachine:test123"
        manager._subscriptions[channel] = {mock_conn}
        
        # 广播事件
        event_data = {
            "bar_index": 42,
            "timestamp": "2024-01-15T10:30:00",
            "bar": {"open": 1800, "high": 1810, "low": 1795, "close": 1805, "volume": 1000000}
        }
        await manager.broadcast_timemachine_event("test123", event_data)
        
        # 验证消息已发送
        mock_ws.send_json.assert_called_once()
        message = mock_ws.send_json.call_args[0][0]
        assert message["type"] == "timemachine_event"
        assert message["session_id"] == "test123"
        assert message["data"]["bar_index"] == 42
        assert "timestamp" in message

    @pytest.mark.asyncio
    async def test_broadcast_to_multiple_subscribers(self):
        """测试广播给多个订阅者"""
        manager = ConnectionManager()
        
        # 创建多个mock连接
        mock_ws1 = AsyncMock()
        mock_conn1 = WSConnection(mock_ws1)
        mock_ws2 = AsyncMock()
        mock_conn2 = WSConnection(mock_ws2)
        
        # 添加订阅者
        channel = "timemachine:session456"
        manager._subscriptions[channel] = {mock_conn1, mock_conn2}
        
        # 广播事件
        await manager.broadcast_timemachine_event("session456", {"bar_index": 1})
        
        # 验证两个连接都收到消息
        mock_ws1.send_json.assert_called_once()
        mock_ws2.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_handles_connection_error(self):
        """测试连接错误时的处理"""
        manager = ConnectionManager()
        
        # 创建一个会抛出异常的mock连接
        mock_ws_bad = AsyncMock()
        mock_ws_bad.send_json.side_effect = Exception("Connection error")
        mock_conn_bad = WSConnection(mock_ws_bad)
        
        # 创建一个正常的mock连接
        mock_ws_good = AsyncMock()
        mock_conn_good = WSConnection(mock_ws_good)
        
        # 添加订阅者
        channel = "timemachine:test"
        manager._subscriptions[channel] = {mock_conn_bad, mock_conn_good}
        
        # 广播事件（应不报错，继续发送给正常连接）
        await manager.broadcast_timemachine_event("test", {"bar_index": 1})
        
        # 验证正常连接收到消息
        mock_ws_good.send_json.assert_called_once()


class TestTimeMachineChannelSubscription:
    """测试TimeMachine channel订阅功能"""

    @pytest.mark.asyncio
    async def test_subscribe_timemachine_channel(self):
        """测试订阅timemachine channel"""
        manager = ConnectionManager()
        
        # 创建mock连接
        mock_ws = AsyncMock()
        mock_conn = WSConnection(mock_ws)
        
        # 订阅channel
        channel = "timemachine:session123"
        async with manager._conn_lock:
            if channel not in manager._subscriptions:
                manager._subscriptions[channel] = set()
            manager._subscriptions[channel].add(mock_conn)
        
        # 验证订阅已添加
        assert channel in manager._subscriptions
        assert mock_conn in manager._subscriptions[channel]

    @pytest.mark.asyncio
    async def test_unsubscribe_timemachine_channel(self):
        """测试取消订阅timemachine channel"""
        manager = ConnectionManager()
        
        # 创建mock连接
        mock_ws = AsyncMock()
        mock_conn = WSConnection(mock_ws)
        
        # 添加订阅
        channel = "timemachine:session123"
        manager._subscriptions[channel] = {mock_conn}
        
        # 取消订阅
        async with manager._conn_lock:
            if channel in manager._subscriptions:
                manager._subscriptions[channel].discard(mock_conn)
                if not manager._subscriptions[channel]:
                    del manager._subscriptions[channel]
        
        # 验证订阅已移除
        assert channel not in manager._subscriptions

    @pytest.mark.asyncio
    async def test_multiple_sessions_isolated(self):
        """测试多个session的订阅隔离"""
        manager = ConnectionManager()
        
        # 创建两个连接
        mock_ws1 = AsyncMock()
        mock_conn1 = WSConnection(mock_ws1)
        mock_ws2 = AsyncMock()
        mock_conn2 = WSConnection(mock_ws2)
        
        # 订阅不同的session
        channel1 = "timemachine:session1"
        channel2 = "timemachine:session2"
        manager._subscriptions[channel1] = {mock_conn1}
        manager._subscriptions[channel2] = {mock_conn2}
        
        # 广播给session1
        await manager.broadcast_timemachine_event("session1", {"bar_index": 1})
        
        # 验证只有session1的订阅者收到消息
        mock_ws1.send_json.assert_called_once()
        mock_ws2.send_json.assert_not_called()
