"""
分笔数据缓冲区

功能：
- 缓存最近的tick数据，用于WebSocket断连恢复
- 支持按序列号查询缺失的tick
- 自动清理过期数据

设计原则：
- 固定大小环形缓冲区（1000条）
- 每个symbol独立缓冲
- 序列号全局递增
"""

from collections import deque
from typing import Dict, List, Optional
import time
import logging

logger = logging.getLogger(__name__)


class TickBuffer:
    """
    分笔数据缓冲区
    
    用于WebSocket断连恢复：
    - 客户端重连时发送last_seq
    - 服务端返回last_seq之后的所有tick
    """
    
    def __init__(self, max_size: int = 1000):
        """
        初始化缓冲区
        
        Args:
            max_size: 每个symbol的最大缓冲条数
        """
        self.max_size = max_size
        # {symbol: deque([{seq, tick, timestamp}, ...])}
        self._buffers: Dict[str, deque] = {}
        self._seq_counter = 0
        self._lock = None  # 异步锁，在需要时初始化
    
    def push(self, symbol: str, tick: dict) -> int:
        """
        推送tick到缓冲区
        
        Args:
            symbol: 股票代码
            tick: tick数据
            
        Returns:
            序列号
        """
        if symbol not in self._buffers:
            self._buffers[symbol] = deque(maxlen=self.max_size)
        
        self._seq_counter += 1
        seq = self._seq_counter
        
        self._buffers[symbol].append({
            'seq': seq,
            'tick': tick,
            'timestamp': time.time()
        })
        
        return seq
    
    def get_since(self, symbol: str, last_seq: int) -> List[dict]:
        """
        获取指定序列号之后的所有tick
        
        Args:
            symbol: 股票代码
            last_seq: 客户端最后的序列号
            
        Returns:
            tick列表
        """
        if symbol not in self._buffers:
            return []
        
        buffer = self._buffers[symbol]
        result = []
        
        for item in buffer:
            if item['seq'] > last_seq:
                result.append(item)
        
        return result
    
    def get_latest_seq(self, symbol: str) -> int:
        """
        获取指定symbol的最新序列号
        
        Args:
            symbol: 股票代码
            
        Returns:
            最新序列号，如果没有数据返回0
        """
        if symbol not in self._buffers or not self._buffers[symbol]:
            return 0
        return self._buffers[symbol][-1]['seq']
    
    def get_global_latest_seq(self) -> int:
        """
        获取全局最新序列号
        
        Returns:
            全局最新序列号
        """
        return self._seq_counter
    
    def clear_symbol(self, symbol: str):
        """
        清除指定symbol的缓冲区
        
        Args:
            symbol: 股票代码
        """
        if symbol in self._buffers:
            del self._buffers[symbol]
    
    def clear_all(self):
        """清空所有缓冲区"""
        self._buffers.clear()
    
    def get_stats(self) -> dict:
        """
        获取缓冲区统计信息
        
        Returns:
            统计信息字典
        """
        total_ticks = sum(len(buf) for buf in self._buffers.values())
        
        return {
            'symbols': len(self._buffers),
            'total_ticks': total_ticks,
            'max_size': self.max_size,
            'global_seq': self._seq_counter
        }
    
    def cleanup_old_ticks(self, max_age_seconds: int = 3600):
        """
        清理过期的tick数据
        
        Args:
            max_age_seconds: 最大保留时间（秒）
            
        Returns:
            清理的tick数量
        """
        now = time.time()
        cleaned = 0
        
        for symbol, buffer in list(self._buffers.items()):
            # 由于deque不支持随机删除，我们重建buffer
            new_buffer = deque(maxlen=self.max_size)
            
            for item in buffer:
                if now - item['timestamp'] <= max_age_seconds:
                    new_buffer.append(item)
                else:
                    cleaned += 1
            
            if new_buffer:
                self._buffers[symbol] = new_buffer
            else:
                del self._buffers[symbol]
        
        if cleaned > 0:
            logger.info(f"[TickBuffer] Cleaned {cleaned} old ticks")
        
        return cleaned


# 全局实例
tick_buffer = TickBuffer(max_size=1000)
