"""
Mootdx数据源获取器

功能：
- 高性能实时行情获取（TCP协议，11ms延迟）
- 支持A股沪深两市
- 比Sina/Tencent更实时
- 支持批量行情、K线、分笔成交、除权除息

依赖：
- pip install mootdx

注意：
- mootdx需要单独安装
- 如果未安装，get_quote返回None
"""

# pyright: reportOptionalMemberAccess=false, reportAttributeAccessIssue=false

import logging
from typing import Dict, Optional, List
import asyncio
from datetime import datetime
from .base import BaseMarketFetcher

logger = logging.getLogger(__name__)

FREQ_5M = 0
FREQ_15M = 1
FREQ_30M = 2
FREQ_1H = 3
FREQ_DAILY = 9
FREQ_WEEKLY = 5
FREQ_MONTHLY = 6

PERIOD_MAP = {
    'daily': FREQ_DAILY,
    'weekly': FREQ_WEEKLY,
    'monthly': FREQ_MONTHLY,
    '5min': FREQ_5M,
    '15min': FREQ_15M,
    '30min': FREQ_30M,
    '60min': FREQ_1H,
}

_mootdx_client = None


def _get_mootdx_client():
    """延迟加载mootdx客户端"""
    global _mootdx_client
    if _mootdx_client is None:
        try:
            from mootdx.quotes import Quotes
            _mootdx_client = Quotes.factory(
                market='std',
                multithread=True,
                heartbeat=True,
                timeout=15,
                quiet=True
            )
            logger.info("[Mootdx] Client initialized successfully")
        except ImportError:
            logger.warning("[Mootdx] mootdx not installed, fetcher will return None")
        except Exception as e:
            logger.warning(f"[Mootdx] Failed to initialize client: {e}")
    return _mootdx_client


class MootdxFetcher(BaseMarketFetcher):
    """
    Mootdx数据源获取器
    
    特点：
    - 高性能：直接连接交易所数据（TCP协议）
    - 实时性：延迟11-13ms，低于Sina/Tencent
    - 稳定性：有备用服务器，不封IP
    """
    
    name = "mootdx"
    display_name = "Mootdx (通达信)"
    supports_order_book = True
    
    def __init__(self):
        self.client = None
    
    def _ensure_client(self):
        """确保客户端已初始化"""
        if self.client is None:
            self.client = _get_mootdx_client()
        return self.client is not None
    
    def _parse_symbol(self, symbol: str) -> tuple:
        """解析股票代码，返回 (market, code)"""
        symbol_lower = symbol.lower().strip()
        
        if symbol_lower.startswith('sh') or symbol_lower.startswith('sz'):
            market = 1 if symbol_lower.startswith('sh') else 0
            code = symbol_lower[2:]
        else:
            code = symbol_lower
            market = 0 if code.startswith(('0', '3')) else 1
        
        return market, code
    
    async def get_quote(self, symbol: str) -> Optional[Dict]:
        """
        获取实时行情
        
        Args:
            symbol: 股票代码 (如 'sh600519', 'sz000001')
            
        Returns:
            行情数据字典或None
        """
        if not self._ensure_client():
            return None
        
        try:
            market, code = self._parse_symbol(symbol)
            
            data = await asyncio.to_thread(
                self.client.quotes, symbol=code  # type: ignore
            )
            
            if data is None or data.empty:
                return None
            
            row = data.iloc[0]
            
            return {
                'symbol': symbol,
                'price': float(row.get('price', 0)),
                'open': float(row.get('open', 0)),
                'high': float(row.get('high', 0)),
                'low': float(row.get('low', 0)),
                'prev_close': float(row.get('last_close', 0)),
                'volume': int(row.get('vol', 0)),
                'amount': float(row.get('amount', 0)),
                'chg': float(row.get('change', 0)),
                'chg_pct': float(row.get('pct_change', 0)),
                'source': 'mootdx'
            }
            
        except Exception as e:
            logger.debug(f"[Mootdx] get_quote failed for {symbol}: {e}")
            return None
    
    async def get_quotes_batch(self, symbols: List[str]) -> List[Dict]:
        """
        批量获取行情（比循环调用更高效）
        
        Args:
            symbols: 股票代码列表
            
        Returns:
            行情数据列表
        """
        if not self._ensure_client():
            return []
        
        try:
            codes = []
            for sym in symbols:
                market, code = self._parse_symbol(sym)
                codes.append(code)
            
            data = await asyncio.to_thread(
                self.client.quotes, symbol=codes  # type: ignore
            )
            
            if data is None or data.empty:
                return []
            
            results = []
            for idx, row in data.iterrows():
                results.append({
                    'symbol': symbols[idx] if idx < len(symbols) else row.get('code', ''),
                    'price': float(row.get('price', 0)),
                    'open': float(row.get('open', 0)),
                    'high': float(row.get('high', 0)),
                    'low': float(row.get('low', 0)),
                    'prev_close': float(row.get('last_close', 0)),
                    'volume': int(row.get('vol', 0)),
                    'amount': float(row.get('amount', 0)),
                    'chg': float(row.get('change', 0)),
                    'chg_pct': float(row.get('pct_change', 0)),
                    'source': 'mootdx'
                })
            
            return results
            
        except Exception as e:
            logger.debug(f"[Mootdx] get_quotes_batch failed: {e}")
            return []
    
    async def get_quotes(self, symbols: List[str]) -> List[Dict]:
        """批量获取行情（兼容旧接口）"""
        return await self.get_quotes_batch(symbols)
    
    async def get_history(
        self, 
        symbol: str, 
        period: str = 'daily',
        start_date: str = None, 
        end_date: str = None,
        offset: int = 800
    ) -> Optional[List[Dict]]:
        """
        获取历史K线
        
        Args:
            symbol: 股票代码
            period: 周期 ('daily', 'weekly', 'monthly', '5min', '15min', '30min', '60min')
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            offset: K线条数（最大800）
            
        Returns:
            K线数据列表或None
        """
        if not self._ensure_client():
            return None
        
        try:
            market, code = self._parse_symbol(symbol)
            frequency = PERIOD_MAP.get(period, FREQ_DAILY)
            
            if start_date and end_date:
                start_fmt = start_date.replace('-', '')
                end_fmt = end_date.replace('-', '')
                
                data = await asyncio.to_thread(
                    self.client.k,  # type: ignore
                    symbol=code,
                    begin=start_fmt,
                    end=end_fmt
                )
            else:
                data = await asyncio.to_thread(
                    self.client.bars,  # type: ignore
                    symbol=code,
                    frequency=frequency,
                    offset=min(offset, 800)
                )
            
            if data is None or data.empty:
                return None
            
            results = []
            for _, row in data.iterrows():
                results.append({
                    'date': str(row.get('datetime', row.get('date', ''))),
                    'open': float(row.get('open', 0)),
                    'high': float(row.get('high', 0)),
                    'low': float(row.get('low', 0)),
                    'close': float(row.get('close', 0)),
                    'volume': int(row.get('vol', row.get('volume', 0))),
                    'amount': float(row.get('amount', 0)),
                    'source': 'mootdx'
                })
            
            return results
            
        except Exception as e:
            logger.debug(f"[Mootdx] get_history failed for {symbol}: {e}")
            return None
    
    async def get_ticks(
        self, 
        symbol: str, 
        date: str = None,
        offset: int = 1000
    ) -> Optional[List[Dict]]:
        """
        获取分笔成交数据
        
        Args:
            symbol: 股票代码
            date: 日期 (YYYYMMDD)，None表示当天
            offset: 返回条数（最大2000）
            
        Returns:
            分笔成交列表或None
        """
        if not self._ensure_client():
            return None
        
        try:
            market, code = self._parse_symbol(symbol)
            
            if date:
                data = await asyncio.to_thread(
                    self.client.transactions,  # type: ignore
                    symbol=code,
                    date=date,
                    start=0,
                    offset=min(offset, 2000)
                )
            else:
                data = await asyncio.to_thread(
                    self.client.transaction,  # type: ignore
                    symbol=code,
                    start=0,
                    offset=min(offset, 2000)
                )
            
            if data is None or data.empty:
                return None
            
            results = []
            for _, row in data.iterrows():
                results.append({
                    'time': str(row.get('time', '')),
                    'price': float(row.get('price', 0)),
                    'volume': int(row.get('vol', 0)),
                    'num': int(row.get('num', 0)),
                    'buyorsell': int(row.get('buyorsell', 0)),
                    'source': 'mootdx'
                })
            
            return results
            
        except Exception as e:
            logger.debug(f"[Mootdx] get_ticks failed for {symbol}: {e}")
            return None
    
    async def get_xdxr(self, symbol: str) -> Optional[List[Dict]]:
        """
        获取除权除息数据
        
        Args:
            symbol: 股票代码
            
        Returns:
            除权除息列表或None
        """
        if not self._ensure_client():
            return None
        
        try:
            market, code = self._parse_symbol(symbol)
            
            data = await asyncio.to_thread(
                self.client.xdxr, symbol=code  # type: ignore
            )
            
            if data is None or data.empty:
                return None
            
            results = []
            for _, row in data.iterrows():
                results.append({
                    'date': str(row.get('date', '')),
                    'category': row.get('category', ''),
                    'fhps': float(row.get('fhps', 0)),
                    'sg': float(row.get('sg', 0)),
                    'pg': float(row.get('pg', 0)),
                    'source': 'mootdx'
                })
            
            return results
            
        except Exception as e:
            logger.debug(f"[Mootdx] get_xdxr failed for {symbol}: {e}")
            return None
    
    async def get_finance(self, symbol: str) -> Optional[Dict]:
        """
        获取财务数据（简要）
        
        Args:
            symbol: 股票代码
            
        Returns:
            财务数据字典或None
        """
        if not self._ensure_client():
            return None
        
        try:
            market, code = self._parse_symbol(symbol)
            
            data = await asyncio.to_thread(
                self.client.finance, symbol=code  # type: ignore
            )
            
            if data is None or data.empty:
                return None
            
            row = data.iloc[0]
            
            return {
                'symbol': symbol,
                'eps': float(row.get('eps', 0)),
                'bvps': float(row.get('bvps', 0)),
                'roe': float(row.get('roe', 0)),
                'source': 'mootdx'
            }
            
        except Exception as e:
            logger.debug(f"[Mootdx] get_finance failed for {symbol}: {e}")
            return None
    
    def is_available(self) -> bool:
        """检查数据源是否可用"""
        return self._ensure_client()
    
    async def get_kline(self, symbol: str, period: str = "day") -> Optional[List[Dict]]:
        """
        获取K线数据（BaseMarketFetcher接口要求）
        
        Args:
            symbol: 股票代码
            period: "minute", "day", "week", "month"
            
        Returns:
            K线数据列表或None
        """
        period_map = {
            'minute': '5min',
            'day': 'daily',
            'week': 'weekly',
            'month': 'monthly'
        }
        mootdx_period = period_map.get(period, 'daily')
        return await self.get_history(symbol, period=mootdx_period)
