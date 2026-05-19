"""
Stock Screener Service for Factor Sandbox

Provides real-time stock screening with factor filters using akshare data.
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple

import numpy as np
import pandas as pd

from app.services.attribution import get_factor_registry

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=20, thread_name_prefix="screener_")


class Universe(str, Enum):
    """Stock universe for screening"""
    ALL = "all"
    HS300 = "hs300"
    ZZ500 = "zz500"
    CYB50 = "cyb50"


@dataclass
class ScreeningFactor:
    """Factor filter configuration"""
    id: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScreeningResult:
    """Screening result for a single stock"""
    symbol: str
    name: str
    score: float
    factor_values: Dict[str, Any]
    passed: bool = True


class StockScreener:
    """
    Stock screening engine with factor-based filtering
    
    Features:
    - Multi-factor filtering with configurable parameters
    - Real-time data from akshare
    - 5-minute factor value caching
    - Partial results on errors
    """
    
    def __init__(self):
        self._akshare = None
        self._cache: Dict[str, Tuple[float, Any]] = {}
        self._cache_ttl = 300  # 5 minutes
        self._universe_cache: Dict[str, Tuple[float, List[Dict]]] = {}
    
    @property
    def ak(self):
        """Lazy load akshare module"""
        if self._akshare is None:
            try:
                import akshare as ak
                self._akshare = ak
            except ImportError:
                logger.error("[Screener] akshare not installed")
                raise
        return self._akshare
    
    async def screen_stocks(
        self,
        factors: List[ScreeningFactor],
        universe: Universe,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Screen stocks based on factor filters
        
        Args:
            factors: List of factor filters with parameters
            universe: Stock universe to screen
            limit: Maximum number of results
            
        Returns:
            Dict with 'stocks' and 'total' keys
        """
        loop = asyncio.get_event_loop()
        
        def _sync_screen():
            start_time = time.time()
            
            stocks = self._get_universe_stocks(universe)
            if not stocks:
                return {"stocks": [], "total": 0, "error": "Failed to get universe stocks"}
            
            results = []
            registry = get_factor_registry()
            
            for stock in stocks[:500]:  # Limit to 500 for performance
                try:
                    symbol = stock.get("symbol", "")
                    name = stock.get("name", "")
                    
                    if not symbol:
                        continue
                    
                    factor_values = {}
                    total_score = 0.0
                    passed_all = True
                    
                    for factor in factors:
                        factor_def = registry.get_factor(factor.id)
                        if not factor_def:
                            logger.warning(f"[Screener] Unknown factor: {factor.id}")
                            continue
                        
                        value = self._calculate_factor_value(
                            symbol, factor.id, factor.params
                        )
                        
                        if value is not None:
                            factor_values[factor.id] = value
                            
                            if factor_def.higher_is_better:
                                total_score += min(value, 1.0)
                            else:
                                total_score += min(1.0 - value, 1.0)
                        else:
                            passed_all = False
                    
                    if passed_all and factor_values:
                        results.append(ScreeningResult(
                            symbol=symbol,
                            name=name,
                            score=total_score / len(factors) if factors else 0,
                            factor_values=factor_values,
                            passed=True,
                        ))
                        
                except Exception as e:
                    logger.debug(f"[Screener] Error screening {stock.get('symbol')}: {e}")
                    continue
            
            results.sort(key=lambda x: x.score, reverse=True)
            results = results[:limit]
            
            elapsed = time.time() - start_time
            logger.info(f"[Screener] Screened {len(stocks)} stocks in {elapsed:.2f}s, found {len(results)} matches")
            
            return {
                "stocks": [
                    {
                        "symbol": r.symbol,
                        "name": r.name,
                        "score": round(r.score, 4),
                        "factor_values": r.factor_values,
                    }
                    for r in results
                ],
                "total": len(results),
            }
        
        return await loop.run_in_executor(_executor, _sync_screen)
    
    def _get_universe_stocks(self, universe: Universe) -> List[Dict]:
        """Get stock list for the specified universe"""
        cache_key = f"universe:{universe.value}"
        
        if cache_key in self._universe_cache:
            timestamp, data = self._universe_cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                return data
        
        try:
            if universe == Universe.ALL:
                df = self.ak.stock_zh_a_spot_em()
                stocks = [
                    {"symbol": row["代码"], "name": row["名称"]}
                    for _, row in df.iterrows()
                ]
            elif universe == Universe.HS300:
                df = self.ak.index_stock_cons_weight_csindex(symbol="000300")
                stocks = [
                    {"symbol": str(row["成分券代码"]), "name": row["成分券名称"]}
                    for _, row in df.iterrows()
                ]
            elif universe == Universe.ZZ500:
                df = self.ak.index_stock_cons_weight_csindex(symbol="000905")
                stocks = [
                    {"symbol": str(row["成分券代码"]), "name": row["成分券名称"]}
                    for _, row in df.iterrows()
                ]
            elif universe == Universe.CYB50:
                df = self.ak.index_stock_cons_weight_csindex(symbol="399673")
                stocks = [
                    {"symbol": str(row["成分券代码"]), "name": row["成分券名称"]}
                    for _, row in df.iterrows()
                ]
            else:
                stocks = []
            
            self._universe_cache[cache_key] = (time.time(), stocks)
            return stocks
            
        except Exception as e:
            logger.error(f"[Screener] Failed to get universe {universe}: {e}")
            return []
    
    def _calculate_factor_value(
        self,
        symbol: str,
        factor_id: str,
        params: Dict[str, Any],
    ) -> Optional[float]:
        """
        Calculate factor value for a stock
        
        Returns normalized value between 0 and 1, or None if calculation fails
        """
        cache_key = f"{symbol}:{factor_id}:{str(params)}"
        
        if cache_key in self._cache:
            timestamp, value = self._cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                return value
        
        try:
            if factor_id == "macd_golden_cross":
                value = self._check_macd_golden_cross(symbol, params)
            elif factor_id == "rsi_oversold":
                value = self._check_rsi_oversold(symbol, params)
            elif factor_id == "breakout_ma":
                value = self._check_breakout_ma(symbol, params)
            elif factor_id == "foreign_inflow":
                value = self._check_foreign_inflow(symbol, params)
            elif factor_id == "llm_sentiment":
                value = self._check_llm_sentiment(symbol, params)
            elif factor_id == "volume_surge":
                value = self._check_volume_surge(symbol, params)
            elif factor_id == "institution_research":
                value = self._check_institution_research(symbol, params)
            elif factor_id == "new_high":
                value = self._check_new_high(symbol, params)
            else:
                value = None
            
            if value is not None:
                self._cache[cache_key] = (time.time(), value)
            
            return value
            
        except Exception as e:
            logger.debug(f"[Screener] Factor calculation error for {symbol}/{factor_id}: {e}")
            return None
    
    def _get_kline_data(self, symbol: str, days: int = 60) -> Optional[pd.DataFrame]:
        """Get K-line data for a stock"""
        try:
            db_symbol = symbol.replace("sh", "").replace("sz", "")
            df = self.ak.stock_zh_a_hist(
                symbol=db_symbol,
                period="daily",
                adjust="qfq",
            )
            
            if df is None or len(df) == 0:
                return None
            
            df = df.tail(days)
            df.columns = ['date', 'open', 'close', 'high', 'low', 'volume', 'turnover', 'amplitude', 'pct_change', 'change', 'turnover_rate']
            
            return df
            
        except Exception as e:
            logger.debug(f"[Screener] Failed to get kline for {symbol}: {e}")
            return None
    
    def _check_macd_golden_cross(self, symbol: str, params: Dict) -> Optional[float]:
        """Check for MACD golden cross signal"""
        df = self._get_kline_data(symbol, 60)
        if df is None or len(df) < 30:
            return None
        
        closes = df['close'].values
        
        fast = params.get("fast", 12)
        slow = params.get("slow", 26)
        signal = params.get("signal", 9)
        
        def ema(data, period):
            k = 2 / (period + 1)
            result = np.zeros(len(data))
            result[0] = data[0]
            for i in range(1, len(data)):
                result[i] = data[i] * k + result[i - 1] * (1 - k)
            return result
        
        ema_fast = ema(closes, fast)
        ema_slow = ema(closes, slow)
        dif = ema_fast - ema_slow
        dea = ema(dif, signal)
        
        if len(dif) < 2:
            return None
        
        if dif[-2] < dea[-2] and dif[-1] > dea[-1]:
            return 1.0
        
        return 0.0
    
    def _check_rsi_oversold(self, symbol: str, params: Dict) -> Optional[float]:
        """Check for RSI oversold signal"""
        df = self._get_kline_data(symbol, 60)
        if df is None or len(df) < 20:
            return None
        
        closes = df['close'].values
        period = params.get("period", 14)
        threshold = params.get("threshold", 30)
        
        if len(closes) < period + 1:
            return None
        
        closes_arr = np.asarray(closes, dtype=np.float64)
        deltas = np.diff(closes_arr)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = float(np.mean(gains[-period:]))
        avg_loss = float(np.mean(losses[-period:]))
        
        if avg_loss == 0:
            rsi = 100
        else:
            rsi = 100 - 100 / (1 + avg_gain / avg_loss)
        
        if rsi < threshold:
            return 1.0
        elif rsi < 50:
            return (50 - rsi) / 50
        return 0.0
    
    def _check_breakout_ma(self, symbol: str, params: Dict) -> Optional[float]:
        """Check for price breakout above MA"""
        df = self._get_kline_data(symbol, 60)
        if df is None or len(df) < 30:
            return None
        
        closes = df['close'].values
        period = params.get("period", 20)
        
        if len(closes) < period:
            return None
        
        closes_arr = np.asarray(closes, dtype=np.float64)
        ma = float(np.mean(closes_arr[-period:]))
        current_price = float(closes_arr[-1])
        
        if current_price > ma:
            return min((current_price - ma) / ma * 10, 1.0)
        return 0.0
    
    def _check_foreign_inflow(self, symbol: str, params: Dict) -> Optional[float]:
        """Check for foreign capital inflow"""
        try:
            db_symbol = symbol.replace("sh", "").replace("sz", "")
            min_amount = params.get("min_amount", 10000000)
            
            df = self.ak.stock_hsgt_individual_em(symbol=db_symbol)
            
            if df is None or len(df) == 0:
                return None
            
            latest = df.iloc[-1]
            inflow = float(latest.get("北向资金净流入", 0))
            
            if inflow >= min_amount:
                return min(inflow / min_amount, 1.0)
            return max(inflow / min_amount, 0.0)
            
        except Exception as e:
            logger.debug(f"[Screener] Foreign inflow check failed for {symbol}: {e}")
            return None
    
    def _check_llm_sentiment(self, symbol: str, params: Dict) -> Optional[float]:
        """Check LLM sentiment score (placeholder - requires copilot integration)"""
        min_score = params.get("min_score", 0.8)
        
        return 0.5
    
    def _check_volume_surge(self, symbol: str, params: Dict) -> Optional[float]:
        """Check for volume surge"""
        df = self._get_kline_data(symbol, 60)
        if df is None or len(df) < 30:
            return None
        
        volumes = df['volume'].values
        multiplier = params.get("multiplier", 2.0)
        period = params.get("period", 20)
        
        if len(volumes) < period + 1:
            return None
        
        volumes_arr = np.asarray(volumes, dtype=np.float64)
        avg_volume = float(np.mean(volumes_arr[-period-1:-1]))
        current_volume = float(volumes_arr[-1])
        
        if avg_volume == 0:
            return None
        
        ratio = current_volume / avg_volume
        
        if ratio >= multiplier:
            return min(ratio / multiplier, 1.0)
        return max(ratio / multiplier - 0.5, 0.0)
    
    def _check_institution_research(self, symbol: str, params: Dict) -> Optional[float]:
        """Check for institution research activity"""
        try:
            db_symbol = symbol.replace("sh", "").replace("sz", "")
            days = params.get("days", 30)
            
            df = self.ak.stock_jgdy_tj_em()
            
            if df is None or len(df) == 0:
                return 0.0
            
            recent = df[df['调研日期'] >= (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')]
            stock_research = recent[recent['股票代码'] == db_symbol]
            count = len(stock_research)
            
            return min(count / 10, 1.0)
            
        except Exception as e:
            logger.debug(f"[Screener] Institution research check failed for {symbol}: {e}")
            return None
    
    def _check_new_high(self, symbol: str, params: Dict) -> Optional[float]:
        """Check if stock made new high"""
        df = self._get_kline_data(symbol, 120)
        if df is None or len(df) < 30:
            return None
        
        closes = df['close'].values
        period = params.get("period", 60)
        
        if len(closes) < period:
            return None
        
        closes_arr = np.asarray(closes, dtype=np.float64)
        current_price = float(closes_arr[-1])
        period_high = float(np.max(closes_arr[-period:]))
        all_time_high = float(np.max(closes_arr))
        
        if current_price >= period_high * 0.98:
            if current_price >= all_time_high * 0.98:
                return 1.0
            return 0.8
        return 0.0


_screener: Optional[StockScreener] = None


def get_stock_screener() -> StockScreener:
    """Get or create singleton screener instance"""
    global _screener
    if _screener is None:
        _screener = StockScreener()
    return _screener
