"""
Forex Data Fetcher - AKShare外汇数据获取服务

数据源:
- EastMoney (forex_spot_em): 实时报价 (190+ 货币对)
- EastMoney (forex_hist_em): 历史K线
- CFETS (fx_spot_quote): 银行间人民币报价
- CFETS (fx_pair_quote): 银行间交叉汇率
- SAFE (currency_boc_safe): 官方中间价

特点:
- 继承 BaseMarketFetcher 接口
- 集成熔断器保护
- 中文到英文字段映射
- 空值安全处理
- 交叉汇率计算 (USD三角套利)
"""
import asyncio
import logging
import pandas as pd
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

from .base import BaseMarketFetcher
from app.services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="forex_fetch_")

_akshare = None

def _get_akshare():
    global _akshare
    if _akshare is None:
        try:
            import akshare as ak
            _akshare = ak
        except ImportError:
            logger.error("[Forex] akshare 未安装，请运行: pip install akshare")
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


class ForexFetcher(BaseMarketFetcher):
    """
    Forex数据获取器
    
    使用方式:
        fetcher = ForexFetcher()
        
        # 获取实时报价
        quotes = await fetcher.get_spot_quotes()
        
        # 获取历史K线
        history = await fetcher.get_history("USDCNH", days=30)
        
        # 获取CFETS报价
        cfets = await fetcher.get_cfets_spot()
        
        # 计算交叉汇率
        rate = fetcher.calculate_cross_rate("EUR", "JPY", rates_dict)
    """
    
    name = "forex"
    display_name = "Forex 数据源 (AKShare)"
    
    supports_quote = True
    supports_kline = True
    supports_order_book = False
    supports_futures = False
    supports_hk = False
    supports_us = False
    
    MAJOR_PAIRS = {
        "USDCNY": "美元兑人民币",
        "EURUSD": "欧元兑美元",
        "GBPUSD": "英镑兑美元",
        "USDJPY": "美元兑日元",
        "AUDUSD": "澳元兑美元",
        "USDCAD": "美元兑加元",
        "USDCHF": "美元兑瑞郎",
        "EURCNY": "欧元兑人民币",
        "GBPCNY": "英镑兑人民币",
        "JPYCNY": "日元兑人民币",
    }
    
    MAJOR_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CNY", "AUD", "CAD", "CHF"]
    
    def __init__(
        self,
        proxy: Optional[str] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ):
        self.proxy = proxy
        self.cb = circuit_breaker or CircuitBreaker(
            "forex",
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
                logger.debug(f"[Forex] Cache HIT: {key}")
                return self._cache[key]
        return None
    
    def _set_cached(self, key: str, value: Any, ttl_seconds: int = 300):
        MAX_CACHE_SIZE = 50
        if len(self._cache) >= MAX_CACHE_SIZE and key not in self._cache:
            oldest_key = min(self._cache_ttl.keys(), key=lambda k: self._cache_ttl.get(k, datetime.max))
            self._cache.pop(oldest_key, None)
            self._cache_ttl.pop(oldest_key, None)
            logger.debug(f"[Forex] Cache EVICT: {oldest_key}")
        
        self._cache[key] = value
        self._cache_ttl[key] = datetime.now() + timedelta(seconds=ttl_seconds)
        logger.debug(f"[Forex] Cache SET: {key} (TTL={ttl_seconds}s)")

    def _get_fallback_quotes(self) -> List[Dict[str, Any]]:
        """
        返回静态回退数据（当电路熔断器打开时）

        Returns:
            静态外汇报价列表 - 包含完整的 bid/ask/spread 字段
        """
        from datetime import datetime
        ts = int(datetime.now().timestamp())
        return [
            {"symbol": "USDCNY", "name": "美元/人民币", "latest": 7.2456, "bid": 7.2420, "ask": 7.2492, "spread": 0.0072, "change": 0.0087, "change_pct": 0.12, "open": 7.2369, "high": 7.2521, "low": 7.2312, "prev_close": 7.2369, "source": "fallback", "timestamp": ts},
            {"symbol": "EURCNY", "name": "欧元/人民币", "latest": 7.8923, "bid": 7.8880, "ask": 7.8966, "spread": 0.0086, "change": -0.0063, "change_pct": -0.08, "open": 7.8986, "high": 7.9012, "low": 7.8856, "prev_close": 7.8986, "source": "fallback", "timestamp": ts},
            {"symbol": "GBPCNY", "name": "英镑/人民币", "latest": 9.1234, "bid": 9.1180, "ask": 9.1288, "spread": 0.0108, "change": 0.0210, "change_pct": 0.23, "open": 9.1024, "high": 9.1345, "low": 9.0912, "prev_close": 9.1024, "source": "fallback", "timestamp": ts},
            {"symbol": "JPYCNY", "name": "日元/人民币", "latest": 0.0486, "bid": 0.0484, "ask": 0.0488, "spread": 0.0004, "change": -0.00007, "change_pct": -0.15, "open": 0.04867, "high": 0.04889, "low": 0.04845, "prev_close": 0.04867, "source": "fallback", "timestamp": ts},
            {"symbol": "HKDCNY", "name": "港币/人民币", "latest": 0.9287, "bid": 0.9265, "ask": 0.9309, "spread": 0.0044, "change": 0.0005, "change_pct": 0.05, "open": 0.9282, "high": 0.9301, "low": 0.9275, "prev_close": 0.9282, "source": "fallback", "timestamp": ts},
            {"symbol": "AUDCNY", "name": "澳元/人民币", "latest": 4.7234, "bid": 4.7180, "ask": 4.7288, "spread": 0.0108, "change": 0.0085, "change_pct": 0.18, "open": 4.7149, "high": 4.7356, "low": 4.7098, "prev_close": 4.7149, "source": "fallback", "timestamp": ts},
            {"symbol": "EURUSD", "name": "欧元/美元", "latest": 1.0892, "bid": 1.0888, "ask": 1.0896, "spread": 0.0008, "change": 0.0012, "change_pct": 0.11, "open": 1.0880, "high": 1.0905, "low": 1.0875, "prev_close": 1.0880, "source": "fallback", "timestamp": ts},
            {"symbol": "GBPUSD", "name": "英镑/美元", "latest": 1.2634, "bid": 1.2628, "ask": 1.2640, "spread": 0.0012, "change": 0.0025, "change_pct": 0.20, "open": 1.2609, "high": 1.2655, "low": 1.2600, "prev_close": 1.2609, "source": "fallback", "timestamp": ts},
            {"symbol": "USDJPY", "name": "美元/日元", "latest": 149.85, "bid": 149.80, "ask": 149.90, "spread": 0.10, "change": 0.25, "change_pct": 0.17, "open": 149.60, "high": 150.05, "low": 149.50, "prev_close": 149.60, "source": "fallback", "timestamp": ts},
            {"symbol": "AUDUSD", "name": "澳元/美元", "latest": 0.6520, "bid": 0.6515, "ask": 0.6525, "spread": 0.0010, "change": 0.0015, "change_pct": 0.23, "open": 0.6505, "high": 0.6535, "low": 0.6500, "prev_close": 0.6505, "source": "fallback", "timestamp": ts},
        ]

    async def reset_circuit_breaker(self) -> dict:
        """
        手动重置熔断器

        Returns:
            dict: {"success": bool, "state": str}
        """
        from app.services.circuit_breaker import CircuitState
        async with self._cache_lock:
            old_state = self.cb.state.value
            self.cb._stats._consecutive_failures = 0
            self.cb._stats._consecutive_successes = 0
            self.cb._stats._last_failure_time = None
            self.cb._state = CircuitState.CLOSED
            logger.info(f"[Forex] 熔断器手动重置: {old_state} -> closed")
            return {"success": True, "state": "closed"}
    
    async def get_spot_quotes(self) -> List[Dict[str, Any]]:
        """
        获取所有实时报价 (EastMoney forex_spot_em)
        
        字段映射 (中文 -> 英文):
        - 代码 -> symbol
        - 名称 -> name
        - 最新价 -> latest
        - 涨跌额 -> change
        - 涨跌幅 -> change_pct
        - 今开 -> open
        - 最高 -> high
        - 最低 -> low
        - 昨收 -> prev_close
        
        Returns:
            报价列表
        """
        cache_key = "spot_quotes"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        if not self.cb.is_available():
            logger.warning("[Forex] 熔断器打开，返回回退数据")
            return self._get_fallback_quotes()
        
        try:
            loop = asyncio.get_running_loop()
            df = await asyncio.wait_for(
                loop.run_in_executor(_executor, self.ak.forex_spot_em),
                timeout=30.0
            )
            
            if df is None or df.empty:
                self.cb.record_failure()
                logger.warning("[Forex] forex_spot_em 返回空数据，返回回退数据")
                return self._get_fallback_quotes()
            
            quotes = []
            for _, row in df.iterrows():
                quote = {
                    "symbol": str(row.get('代码', '')),
                    "name": str(row.get('名称', '')),
                    "latest": clean_value(row.get('最新价')),
                    "change": clean_value(row.get('涨跌额')),
                    "change_pct": clean_value(row.get('涨跌幅')),
                    "open": clean_value(row.get('今开')),
                    "high": clean_value(row.get('最高')),
                    "low": clean_value(row.get('最低')),
                    "prev_close": clean_value(row.get('昨收')),
                    "source": "akshare",
                    "timestamp": int(datetime.now().timestamp()),
                }
                quotes.append(quote)
            
            self._set_cached(cache_key, quotes, ttl_seconds=300)
            self.cb.record_success()
            logger.info(f"[Forex] 获取实时报价成功: {len(quotes)} 条")
            return quotes
            
        except asyncio.TimeoutError:
            self.cb.record_failure()
            logger.warning("[Forex] 获取实时报价超时，返回回退数据")
            return self._get_fallback_quotes()
        except Exception as e:
            self.cb.record_failure()
            logger.error(f"[Forex] 获取实时报价失败: {e}，返回回退数据")
            return self._get_fallback_quotes()
    
    async def get_history(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        获取历史K线数据 (EastMoney forex_hist_em)
        
        字段映射 (中文 -> 英文):
        - 日期 -> date
        - 今开 -> open
        - 最新价 -> close
        - 最高 -> high
        - 最低 -> low
        - 振幅 -> amplitude
        
        Args:
            symbol: 货币对代码，如 USDCNH
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            limit: 返回条数限制
            
        Returns:
            K线数据列表
        """
        cache_key = f"history_{symbol}_{start_date}_{end_date}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached[-limit:] if limit else cached
        
        if not self.cb.is_available():
            return []
        
        try:
            loop = asyncio.get_running_loop()
            df = await asyncio.wait_for(
                loop.run_in_executor(_executor, lambda: self.ak.forex_hist_em(symbol=symbol)),
                timeout=30.0
            )
            
            if df is None or df.empty:
                self.cb.record_failure()
                return []
            
            result_df = df.copy()
            if start_date:
                mask = result_df['日期'] >= start_date
                result_df = result_df.loc[mask]
            if end_date:
                mask = result_df['日期'] <= end_date
                result_df = result_df.loc[mask]
            
            history = []
            for _, row in result_df.iterrows():
                kline = {
                    "date": str(row.get('日期', '')),
                    "open": clean_value(row.get('今开')),
                    "close": clean_value(row.get('最新价')),
                    "high": clean_value(row.get('最高')),
                    "low": clean_value(row.get('最低')),
                    "amplitude": clean_value(row.get('振幅')),
                }
                history.append(kline)
            
            self._set_cached(cache_key, history, ttl_seconds=1800)
            self.cb.record_success()
            logger.info(f"[Forex] 获取历史K线成功: {symbol} {len(history)} 条")
            return history[-limit:] if limit else history
            
        except asyncio.TimeoutError:
            self.cb.record_failure()
            logger.warning(f"[Forex] 获取历史K线超时: {symbol}")
            return []
        except Exception as e:
            self.cb.record_failure()
            logger.error(f"[Forex] 获取历史K线失败: {symbol} - {e}")
            return []
    
    async def get_cfets_spot(self) -> List[Dict[str, Any]]:
        """
        获取CFETS银行间人民币报价 (fx_spot_quote)
        
        字段映射 (中文 -> 英文):
        - 货币对 -> pair
        - 买报价 -> bid
        - 卖报价 -> ask
        
        Returns:
            CFETS报价列表
        """
        cache_key = "cfets_spot"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        if not self.cb.is_available():
            return []
        
        try:
            loop = asyncio.get_running_loop()
            df = await asyncio.wait_for(
                loop.run_in_executor(_executor, self.ak.fx_spot_quote),
                timeout=30.0
            )
            
            if df is None or df.empty:
                self.cb.record_failure()
                return []
            
            quotes = []
            for _, row in df.iterrows():
                bid = clean_value(row.get('买报价'))
                ask = clean_value(row.get('卖报价'))
                quote = {
                    "pair": str(row.get('货币对', '')),
                    "bid": bid,
                    "ask": ask,
                    "spread": round(ask - bid, 6) if bid and ask else None,
                    "mid": round((bid + ask) / 2, 6) if bid and ask else None,
                    "source": "cfets",
                    "timestamp": int(datetime.now().timestamp()),
                }
                quotes.append(quote)
            
            self._set_cached(cache_key, quotes, ttl_seconds=300)
            self.cb.record_success()
            logger.info(f"[Forex] 获取CFETS人民币报价成功: {len(quotes)} 条")
            return quotes
            
        except asyncio.TimeoutError:
            self.cb.record_failure()
            logger.warning("[Forex] 获取CFETS报价超时")
            return []
        except Exception as e:
            self.cb.record_failure()
            logger.error(f"[Forex] 获取CFETS报价失败: {e}")
            return []
    
    async def get_cfets_crosses(self) -> List[Dict[str, Any]]:
        """
        获取CFETS非人民币交叉汇率 (fx_pair_quote)
        
        Returns:
            CFETS交叉汇率列表
        """
        cache_key = "cfets_crosses"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        if not self.cb.is_available():
            return []
        
        try:
            loop = asyncio.get_running_loop()
            df = await asyncio.wait_for(
                loop.run_in_executor(_executor, self.ak.fx_pair_quote),
                timeout=30.0
            )
            
            if df is None or df.empty:
                self.cb.record_failure()
                return []
            
            quotes = []
            for _, row in df.iterrows():
                bid = clean_value(row.get('买报价'))
                ask = clean_value(row.get('卖报价'))
                quote = {
                    "pair": str(row.get('货币对', '')),
                    "bid": bid,
                    "ask": ask,
                    "spread": round(ask - bid, 6) if bid and ask else None,
                    "mid": round((bid + ask) / 2, 6) if bid and ask else None,
                    "source": "cfets",
                    "timestamp": int(datetime.now().timestamp()),
                }
                quotes.append(quote)
            
            self._set_cached(cache_key, quotes, ttl_seconds=300)
            self.cb.record_success()
            logger.info(f"[Forex] 获取CFETS交叉汇率成功: {len(quotes)} 条")
            return quotes
            
        except asyncio.TimeoutError:
            self.cb.record_failure()
            logger.warning("[Forex] 获取CFETS交叉汇率超时")
            return []
        except Exception as e:
            self.cb.record_failure()
            logger.error(f"[Forex] 获取CFETS交叉汇率失败: {e}")
            return []
    
    async def get_official_rates(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        获取SAFE官方人民币中间价 (currency_boc_safe)
        
        Returns:
            官方中间价列表
        """
        cache_key = f"official_rates_{days}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        if not self.cb.is_available():
            return []
        
        try:
            loop = asyncio.get_running_loop()
            df = await asyncio.wait_for(
                loop.run_in_executor(_executor, self.ak.currency_boc_safe),
                timeout=30.0
            )
            
            if df is None or df.empty:
                self.cb.record_failure()
                return []
            
            if days and len(df) > days:
                df = df.tail(days)
            
            rates = []
            for _, row in df.iterrows():
                rate = {
                    "date": str(row.get('日期', '')),
                    "usd": clean_value(row.get('美元')),
                    "eur": clean_value(row.get('欧元')),
                    "jpy": clean_value(row.get('日元')),
                    "gbp": clean_value(row.get('英镑')),
                    "hkd": clean_value(row.get('港币')),
                    "aud": clean_value(row.get('澳大利亚元')),
                    "cad": clean_value(row.get('加拿大元')),
                    "chf": clean_value(row.get('瑞士法郎')),
                }
                rates.append(rate)
            
            self._set_cached(cache_key, rates, ttl_seconds=3600)
            self.cb.record_success()
            logger.info(f"[Forex] 获取官方中间价成功: {len(rates)} 条")
            return rates
            
        except asyncio.TimeoutError:
            self.cb.record_failure()
            logger.warning("[Forex] 获取官方中间价超时")
            return []
        except Exception as e:
            self.cb.record_failure()
            logger.error(f"[Forex] 获取官方中间价失败: {e}")
            return []
    
    def calculate_cross_rate(
        self,
        from_curr: str,
        to_curr: str,
        rates: Dict[str, Decimal],
    ) -> Optional[Decimal]:
        """
        计算交叉汇率 (USD三角套利)
        
        算法:
        - 如果 from == to，返回 1.0
        - 尝试直接获取 from/to 汇率
        - 如果没有直接汇率，通过 USD 计算:
          - EUR/JPY = EUR/USD × USD/JPY
          - GBP/AUD = GBP/USD ÷ AUD/USD
          
        Args:
            from_curr: 源货币
            to_curr: 目标货币
            rates: 汇率字典，格式 {"EUR/USD": Decimal("1.08"), ...}
            
        Returns:
            交叉汇率 (6位小数精度) 或 None
        """
        from_curr = from_curr.upper()
        to_curr = to_curr.upper()
        
        if from_curr == to_curr:
            return Decimal('1.0')
        
        direct_key = f"{from_curr}/{to_curr}"
        if direct_key in rates:
            return rates[direct_key]
        
        inverse_key = f"{to_curr}/{from_curr}"
        if inverse_key in rates:
            return Decimal('1') / rates[inverse_key]
        
        from_usd_key = f"{from_curr}/USD"
        to_usd_key = f"{to_curr}/USD"
        usd_from_key = f"USD/{from_curr}"
        usd_to_key = f"USD/{to_curr}"
        
        from_rate = None
        to_rate = None
        
        if from_usd_key in rates:
            from_rate = rates[from_usd_key]
        elif usd_from_key in rates:
            from_rate = Decimal('1') / rates[usd_from_key]
        
        if to_usd_key in rates:
            to_rate = rates[to_usd_key]
        elif usd_to_key in rates:
            to_rate = Decimal('1') / rates[usd_to_key]
        
        if from_curr == "USD":
            if usd_to_key in rates:
                return rates[usd_to_key]
            elif to_usd_key in rates:
                return Decimal('1') / rates[to_usd_key]
        
        if to_curr == "USD":
            if usd_from_key in rates:
                return Decimal('1') / rates[usd_from_key]
            elif from_usd_key in rates:
                return rates[from_usd_key]
        
        if from_rate is None or to_rate is None:
            return None
        
        cross_rate = from_rate / to_rate
        
        return cross_rate.quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
    
    async def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取单个货币对报价 (BaseMarketFetcher接口)"""
        quotes = await self.get_spot_quotes()
        for q in quotes:
            if q.get('symbol') == symbol:
                return q
        return None
    
    async def get_kline(
        self,
        symbol: str,
        period: str = "daily",
        adjust: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """获取K线数据 (BaseMarketFetcher接口)"""
        return await self.get_history(symbol, start_date, end_date)
    
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
            quotes = await self.get_spot_quotes()
            return len(quotes) > 0
        except Exception:
            return False


def get_circuit_breaker_status() -> dict:
    """
    返回熔断器状态
    
    Returns:
        dict: {
            "is_open": bool,           # 熔断器是否打开
            "failure_count": int,      # 连续失败次数
            "last_failure_time": str,  # 最后失败时间 (ISO格式)
            "is_available": bool       # 是否可用（与is_open相反）
        }
    """
    from datetime import datetime
    
    last_failure_ts = forex_fetcher.cb._stats.last_failure_time
    last_failure_iso = None
    if last_failure_ts is not None:
        last_failure_iso = datetime.fromtimestamp(last_failure_ts).isoformat()
    
    return {
        "is_open": not forex_fetcher.cb.is_available(),
        "failure_count": forex_fetcher.cb._stats.consecutive_failures,
        "last_failure_time": last_failure_iso,
        "is_available": forex_fetcher.cb.is_available(),
        "state": forex_fetcher.cb.state.value,
    }


forex_fetcher = ForexFetcher()
