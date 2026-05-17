"""
Options Data Fetcher - AKShare期权数据获取服务

数据源:
- CFFEX (option_cffex_hs300_spot_sina): 沪深300股指期权链
- SSE (option_sse_greeks_sina): 上交所期权Greeks

特点:
- 继承 BaseMarketFetcher 接口
- 集成熔断器保护
- 中文到英文字段映射
- 空值安全处理
"""
import asyncio
import logging
import pandas as pd
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

from .base import BaseMarketFetcher
from app.services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="options_fetch_")

_akshare = None

def _get_akshare():
    global _akshare
    if _akshare is None:
        try:
            import akshare as ak
            _akshare = ak
        except ImportError:
            logger.error("[Options] akshare 未安装，请运行: pip install akshare")
            raise
    return _akshare


def clean_value(val) -> Optional[float]:
    """
    安全地将值转为float，处理NaN和无效值
    
    Args:
        val: 任意值
        
    Returns:
        float 或 None
    """
    if val is None:
        return None
    try:
        f = float(val)
        import math
        if pd.isna(f) or not math.isfinite(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


class OptionsFetcher(BaseMarketFetcher):
    """
    Options数据获取器
    
    使用方式:
        fetcher = OptionsFetcher()
        
        # 获取CFFEX期权链
        chain = await fetcher.get_cffex_chain("io2506")
        
        # 获取Greeks
        greeks = await fetcher.get_sse_greeks("10004023")
        
        # 获取合约列表
        contracts = await fetcher.get_contract_list("CFFEX")
    """
    
    name = "options"
    display_name = "Options 数据源 (AKShare)"
    
    supports_quote = True
    supports_kline = False
    supports_order_book = False
    supports_futures = False
    supports_hk = False
    supports_us = False
    
    # CFFEX支持的品种
    CFFEX_SYMBOLS = {
        "io": "沪深300股指期权",
        "mo": "中证1000股指期权",
    }
    
    # 上交所期权品种
    SSE_ETF_OPTIONS = [
        "510050",  # 上证50ETF期权
        "510300",  # 沪深300ETF期权
        "510500",  # 中证500ETF期权
    ]
    
    def __init__(
        self,
        proxy: Optional[str] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ):
        self.proxy = proxy
        self.cb = circuit_breaker or CircuitBreaker(
            "options",
            CircuitBreakerConfig(
                failure_threshold=5,
                timeout=60.0,
            )
        )
        self._ak = None
        
        self._cache = {}
        self._cache_ttl = {}
        self._cache_lock = asyncio.Lock()
        
    @property
    def ak(self):
        if self._ak is None:
            self._ak = _get_akshare()
        return self._ak
    
    def _get_cached(self, key: str) -> Optional[Any]:
        if key in self._cache and key in self._cache_ttl:
            if datetime.now() < self._cache_ttl[key]:
                logger.debug(f"[Options] Cache HIT: {key}")
                return self._cache[key]
        return None
    
    def _set_cached(self, key: str, value: Any, ttl_seconds: int = 300):
        MAX_CACHE_SIZE = 50
        if len(self._cache) >= MAX_CACHE_SIZE and key not in self._cache:
            oldest_key = min(self._cache_ttl.keys(), key=lambda k: self._cache_ttl.get(k, datetime.max))
            self._cache.pop(oldest_key, None)
            self._cache_ttl.pop(oldest_key, None)
            logger.debug(f"[Options] Cache EVICT: {oldest_key}")
        
        self._cache[key] = value
        self._cache_ttl[key] = datetime.now() + timedelta(seconds=ttl_seconds)
        logger.debug(f"[Options] Cache SET: {key} (TTL={ttl_seconds}s)")

    async def get_cffex_chain(self, symbol: str = "io2506") -> Dict[str, Any]:
        """
        获取CFFEX股指期权链 (option_cffex_hs300_spot_sina)
        
        Args:
            symbol: 期权品种代码，如 io2506 (沪深300股指期权2025年6月合约)
            
        Returns:
            {
                "symbol": "io2506",
                "name": "沪深300股指期权",
                "calls": [...],  # 看涨期权列表
                "puts": [...],   # 看跌期权列表
                "update_time": "10:30:00"
            }
        """
        cache_key = f"cffex_chain_{symbol}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        if not self.cb.is_available():
            logger.warning("[Options] 熔断器打开，返回空数据")
            return self._get_empty_chain(symbol)
        
        try:
            loop = asyncio.get_running_loop()
            
            # 使用akshare获取期权链数据
            df = await asyncio.wait_for(
                loop.run_in_executor(_executor, lambda: self.ak.option_cffex_hs300_spot_sina(symbol=symbol)),
                timeout=30.0
            )
            
            if df is None or df.empty:
                self.cb.record_failure()
                logger.warning(f"[Options] option_cffex_hs300_spot_sina 返回空数据: {symbol}")
                return self._get_empty_chain(symbol)
            
            # akshare返回的格式：每行包含看涨和看跌合约信息在同一行
            # 列名格式：看涨合约-买量, 看涨合约-最新价, 行权价, 看跌合约-最新价, 等
            calls = []
            puts = []
            
            for _, row in df.iterrows():
                # 看涨期权数据
                call_data = {
                    "code": str(row.get('看涨合约-标识', '')),
                    "name": str(row.get('看涨合约-标识', '')),
                    "strike": clean_value(row.get('行权价')),
                    "latest": clean_value(row.get('看涨合约-最新价')),
                    "change": clean_value(row.get('看涨合约-涨跌')),
                    "change_pct": None,
                    "volume": clean_value(row.get('看涨合约-买量')),
                    "open_interest": clean_value(row.get('看涨合约-持仓量')),
                    "delta": None,
                    "gamma": None,
                    "theta": None,
                    "vega": None,
                    "iv": None,
                }
                
                # 看跌期权数据
                put_data = {
                    "code": str(row.get('看跌合约-标识', '')),
                    "name": str(row.get('看跌合约-标识', '')),
                    "strike": clean_value(row.get('行权价')),
                    "latest": clean_value(row.get('看跌合约-最新价')),
                    "change": clean_value(row.get('看跌合约-涨跌')),
                    "change_pct": None,
                    "volume": clean_value(row.get('看跌合约-买量')),
                    "open_interest": clean_value(row.get('看跌合约-持仓量')),
                    "delta": None,
                    "gamma": None,
                    "theta": None,
                    "vega": None,
                    "iv": None,
                }
                
                # 只添加有有效数据的期权
                if call_data.get('code') and call_data.get('strike'):
                    calls.append(call_data)
                if put_data.get('code') and put_data.get('strike'):
                    puts.append(put_data)
            
            # 按行权价排序
            calls.sort(key=lambda x: x.get('strike', 0) or 0)
            puts.sort(key=lambda x: x.get('strike', 0) or 0)
            
            result = {
                "symbol": symbol,
                "name": self.CFFEX_SYMBOLS.get(symbol[:2], "未知品种"),
                "calls": calls,
                "puts": puts,
                "update_time": datetime.now().strftime("%H:%M:%S"),
                "source": "akshare",
            }
            
            self._set_cached(cache_key, result, ttl_seconds=300)
            self.cb.record_success()
            logger.info(f"[Options] 获取CFFEX期权链成功: {symbol} calls={len(calls)} puts={len(puts)}")
            return result
            
        except asyncio.TimeoutError:
            self.cb.record_failure()
            logger.warning(f"[Options] 获取CFFEX期权链超时: {symbol}")
            return self._get_empty_chain(symbol)
        except Exception as e:
            self.cb.record_failure()
            logger.error(f"[Options] 获取CFFEX期权链失败: {symbol} - {e}")
            return self._get_empty_chain(symbol)

    async def get_sse_greeks(self, contract_code: str) -> Dict[str, Any]:
        """
        获取上交所期权Greeks (option_sse_greeks_sina)
        
        Args:
            contract_code: 合约代码，如 10004023
            
        Returns:
            {
                "code": "10004023",
                "name": "50ETF购6月2500",
                "delta": 0.523,
                "gamma": 0.089,
                "theta": -0.012,
                "vega": 0.234,
                "iv": 0.185,
                "price": 0.0456,
                "update_time": "10:30:00"
            }
        """
        cache_key = f"sse_greeks_{contract_code}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        if not self.cb.is_available():
            return self._get_empty_greeks(contract_code)
        
        try:
            loop = asyncio.get_running_loop()
            
            df = await asyncio.wait_for(
                loop.run_in_executor(_executor, lambda: self.ak.option_sse_greeks_sina(symbol=contract_code)),
                timeout=30.0
            )
            
            if df is None or df.empty:
                self.cb.record_failure()
                logger.warning(f"[Options] option_sse_greeks_sina 返回空数据: {contract_code}")
                return self._get_empty_greeks(contract_code)
            
            # 解析Greeks数据
            row = df.iloc[0] if len(df) > 0 else {}
            
            result = {
                "code": contract_code,
                "name": str(row.get('名称', '')),
                "delta": clean_value(row.get('Delta')),
                "gamma": clean_value(row.get('Gamma')),
                "theta": clean_value(row.get('Theta')),
                "vega": clean_value(row.get('Vega')),
                "iv": clean_value(row.get('隐含波动率')),
                "price": clean_value(row.get('最新价')),
                "strike": clean_value(row.get('行权价')),
                "expiry": str(row.get('到期日', '')),
                "update_time": datetime.now().strftime("%H:%M:%S"),
                "source": "akshare",
            }
            
            self._set_cached(cache_key, result, ttl_seconds=300)
            self.cb.record_success()
            logger.info(f"[Options] 获取SSE Greeks成功: {contract_code}")
            return result
            
        except asyncio.TimeoutError:
            self.cb.record_failure()
            logger.warning(f"[Options] 获取SSE Greeks超时: {contract_code}")
            return self._get_empty_greeks(contract_code)
        except Exception as e:
            self.cb.record_failure()
            logger.error(f"[Options] 获取SSE Greeks失败: {contract_code} - {e}")
            return self._get_empty_greeks(contract_code)

    async def get_contract_list(self, exchange: str = "CFFEX") -> Dict[str, Any]:
        """
        获取期权合约列表
        
        Args:
            exchange: 交易所代码 (CFFEX/SSE)
            
        Returns:
            {
                "exchange": "CFFEX",
                "contracts": [
                    {"code": "io2506", "name": "沪深300股指期权2506", "type": "index"},
                    ...
                ]
            }
        """
        cache_key = f"contract_list_{exchange}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        # 返回静态合约列表（可扩展为动态获取）
        contracts = []
        
        if exchange.upper() == "CFFEX":
            # CFFEX股指期权
            current_year = datetime.now().year
            months = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"]
            
            for month in months:
                contracts.append({
                    "code": f"io{str(current_year)[2:]}{month}",
                    "name": f"沪深300股指期权{current_year}{month}",
                    "type": "index",
                    "underlying": "沪深300指数",
                })
                contracts.append({
                    "code": f"mo{str(current_year)[2:]}{month}",
                    "name": f"中证1000股指期权{current_year}{month}",
                    "type": "index",
                    "underlying": "中证1000指数",
                })
        
        elif exchange.upper() == "SSE":
            # 上交所ETF期权
            for etf in self.SSE_ETF_OPTIONS:
                contracts.append({
                    "code": etf,
                    "name": f"{etf}ETF期权",
                    "type": "etf",
                    "underlying": f"{etf}ETF",
                })
        
        result = {
            "exchange": exchange.upper(),
            "contracts": contracts,
            "update_time": datetime.now().strftime("%H:%M:%S"),
        }
        
        self._set_cached(cache_key, result, ttl_seconds=3600)
        return result

    def _get_empty_chain(self, symbol: str) -> Dict[str, Any]:
        """返回空期权链数据"""
        return {
            "symbol": symbol,
            "name": self.CFFEX_SYMBOLS.get(symbol[:2], "未知品种"),
            "calls": [],
            "puts": [],
            "update_time": datetime.now().strftime("%H:%M:%S"),
            "source": "empty",
            "error": "数据获取失败",
        }

    def _get_empty_greeks(self, contract_code: str) -> Dict[str, Any]:
        """返回空Greeks数据"""
        return {
            "code": contract_code,
            "name": "",
            "delta": None,
            "gamma": None,
            "theta": None,
            "vega": None,
            "iv": None,
            "price": None,
            "strike": None,
            "expiry": "",
            "update_time": datetime.now().strftime("%H:%M:%S"),
            "source": "empty",
            "error": "数据获取失败",
        }

    async def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取单个期权报价 (BaseMarketFetcher接口)"""
        # 尝试获取期权链
        chain = await self.get_cffex_chain(symbol)
        if chain.get("calls") or chain.get("puts"):
            return chain
        return None

    async def get_kline(
        self,
        symbol: str,
        period: str = "daily",
        adjust: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """期权暂不支持K线"""
        return None

    async def get_order_book(self, symbol: str) -> Optional[Dict]:
        """不支持订单簿"""
        return None

    async def get_futures_quote(self, symbol: str) -> Optional[Dict]:
        """不支持期货行情"""
        return None

    def is_healthy(self) -> bool:
        """检查数据源是否健康"""
        return self.cb.is_available()

    async def ping(self) -> bool:
        """探测数据源连通性"""
        try:
            chain = await self.get_cffex_chain("io2506")
            return chain.get("source") == "akshare"
        except Exception:
            return False


# 单例实例
options_fetcher = OptionsFetcher()
