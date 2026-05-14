"""
AkShare Fetcher — 基于 AkShare 的数据获取器

功能：
- A股历史K线（支持前复权qfq/后复权hfq）
- 基金净值数据
- 实时行情快照

特点：
- 继承 BaseMarketFetcher 接口
- 集成熔断器保护
- 支持 SQLite 缓存持久化
"""
import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from .base import BaseMarketFetcher
from app.services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

logger = logging.getLogger(__name__)

# 延迟导入 AkShare（避免启动时加载）
_akshare = None

def _get_akshare():
    global _akshare
    if _akshare is None:
        try:
            import akshare as ak
            _akshare = ak
        except ImportError:
            logger.error("[AkShare] akshare 未安装，请运行: pip install akshare")
            raise
    return _akshare


class AkShareFetcher(BaseMarketFetcher):
    """
    AkShare 数据源获取器
    
    使用方式：
        fetcher = AkShareFetcher()
        
        # 获取K线（默认前复权）
        kline = await fetcher.get_kline("sh600519", period="day", adjust="qfq")
        
        # 获取基金净值
        nav = await fetcher.get_fund_nav("000001")
    """
    
    name = "akshare"
    display_name = "AkShare 数据源"
    
    supports_quote = True
    supports_kline = True
    supports_order_book = False
    supports_futures = False
    supports_hk = False
    supports_us = False
    
    # 默认复权方式：前复权
    DEFAULT_ADJUST = "qfq"
    
    def __init__(
        self,
        proxy: Optional[str] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ):
        self.proxy = proxy
        # 使用独立的熔断器实例
        self.cb = circuit_breaker or CircuitBreaker(
            "akshare",
            CircuitBreakerConfig(
                failure_threshold=5,
                timeout=60.0,  # AkShare 可能较慢，延长超时
            )
        )
        self._ak = None
    
    @property
    def ak(self):
        """延迟加载 AkShare 模块"""
        if self._ak is None:
            self._ak = _get_akshare()
        return self._ak
    
    async def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取实时行情（使用 ak.stock_zh_a_spot_em）
        
        Args:
            symbol: 股票代码，如 "sh600519"
            
        Returns:
            行情字典或 None
        """
        if not self.cb.is_available():
            logger.debug(f"[AkShare] 熔断器打开，跳过 {symbol}")
            return None
        
        try:
            # 转换代码格式：sh600519 -> 600519
            code = symbol[2:] if symbol.startswith(('sh', 'sz')) else symbol
            
            # 在线程池中执行同步调用
            def _fetch():
                df = self.ak.stock_zh_a_spot_em()
                row = df[df['代码'] == code]
                if row.empty:
                    return None
                r = row.iloc[0]
                return {
                    "source": "akshare",
                    "symbol": symbol,
                    "name": r.get('名称', ''),
                    "price": float(r.get('最新价', 0) or 0),
                    "change_pct": float(r.get('涨跌幅', 0) or 0),
                    "change": float(r.get('涨跌额', 0) or 0),
                    "volume": float(r.get('成交量', 0) or 0),
                    "amount": float(r.get('成交额', 0) or 0),
                    "high": float(r.get('最高', 0) or 0),
                    "low": float(r.get('最低', 0) or 0),
                    "open": float(r.get('今开', 0) or 0),
                    "prev_close": float(r.get('昨收', 0) or 0),
                }
            
            result = await asyncio.get_event_loop().run_in_executor(None, _fetch)
            
            if result:
                self.cb.record_success()
                logger.debug(f"[AkShare] {symbol} 行情获取成功")
            else:
                self.cb.record_failure()
                logger.warning(f"[AkShare] {symbol} 未找到数据")
            
            return result
            
        except Exception as e:
            self.cb.record_failure()
            logger.warning(f"[AkShare] {symbol} 行情获取失败: {e}")
            return None
    
    async def get_kline(
        self,
        symbol: str,
        period: str = "day",
        adjust: str = None,
        start_date: str = None,
        end_date: str = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取历史K线数据
        
        Args:
            symbol: 股票代码，如 "sh600519"
            period: 周期，"daily"(日线)/"weekly"(周线)/"monthly"(月线)
            adjust: 复权方式，"qfq"(前复权)/"hfq"(后复权)/""(不复权)
            start_date: 起始日期，格式 "20200101"
            end_date: 结束日期，格式 "20231231"
            
        Returns:
            K线数据列表或 None
        """
        if not self.cb.is_available():
            logger.debug(f"[AkShare] 熔断器打开，跳过 {symbol}")
            return None
        
        # 默认使用前复权
        adjust = adjust or self.DEFAULT_ADJUST
        
        # 转换代码格式
        code = symbol[2:] if symbol.startswith(('sh', 'sz')) else symbol
        
        # AkShare 使用不同的周期参数名
        period_map = {
            "day": "daily",
            "daily": "daily",
            "week": "weekly",
            "weekly": "weekly",
            "month": "monthly",
            "monthly": "monthly",
        }
        ak_period = period_map.get(period, "daily")
        
        try:
            def _fetch():
                # 使用 stock_zh_a_hist 接口
                df = self.ak.stock_zh_a_hist(
                    symbol=code,
                    period=ak_period,
                    adjust=adjust,
                    start_date=start_date or "19900101",
                    end_date=end_date or datetime.now().strftime("%Y%m%d"),
                )
                
                if df is None or df.empty:
                    return None
                
                # 标准化输出格式
                result = []
                for _, row in df.iterrows():
                    result.append({
                        "date": str(row.get('日期', '')),
                        "open": float(row.get('开盘', 0) or 0),
                        "high": float(row.get('最高', 0) or 0),
                        "low": float(row.get('最低', 0) or 0),
                        "close": float(row.get('收盘', 0) or 0),
                        "volume": float(row.get('成交量', 0) or 0),
                        "amount": float(row.get('成交额', 0) or 0),
                        "amplitude": float(row.get('振幅', 0) or 0),
                        "change_pct": float(row.get('涨跌幅', 0) or 0),
                        "change": float(row.get('涨跌额', 0) or 0),
                        "turnover": float(row.get('换手率', 0) or 0),
                    })
                return result
            
            result = await asyncio.get_event_loop().run_in_executor(None, _fetch)
            
            if result:
                self.cb.record_success()
                logger.info(f"[AkShare] {symbol} K线获取成功: {len(result)} 条 ({period}, {adjust})")
            else:
                self.cb.record_failure()
                logger.warning(f"[AkShare] {symbol} K线数据为空")
            
            return result
            
        except Exception as e:
            self.cb.record_failure()
            logger.warning(f"[AkShare] {symbol} K线获取失败: {e}")
            return None
    
    async def get_fund_nav(
        self,
        fund_code: str,
        period: str = "1年",
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取基金净值历史数据
        
        Args:
            fund_code: 基金代码，如 "000001"
            period: 时间段，"1年"/"3年"/"5年"/"全部"
            
        Returns:
            净值数据列表或 None
        """
        if not self.cb.is_available():
            logger.debug(f"[AkShare] 熔断器打开，跳过基金 {fund_code}")
            return None
        
        try:
            def _fetch():
                # 使用 fund_open_fund_info_em 接口
                df = self.ak.fund_open_fund_info_em(
                    fund=fund_code,
                    indicator=period,
                )
                
                if df is None or df.empty:
                    return None
                
                # 标准化输出
                result = []
                for _, row in df.iterrows():
                    result.append({
                        "date": str(row.get('净值日期', '')),
                        "unit_nav": float(row.get('单位净值', 0) or 0),
                        "acc_nav": float(row.get('累计净值', 0) or 0),
                        "daily_growth": float(row.get('日增长率', 0) or 0),
                    })
                return result
            
            result = await asyncio.get_event_loop().run_in_executor(None, _fetch)
            
            if result:
                self.cb.record_success()
                logger.info(f"[AkShare] 基金 {fund_code} 净值获取成功: {len(result)} 条")
            else:
                self.cb.record_failure()
                logger.warning(f"[AkShare] 基金 {fund_code} 净值数据为空")
            
            return result
            
        except Exception as e:
            self.cb.record_failure()
            logger.warning(f"[AkShare] 基金 {fund_code} 净值获取失败: {e}")
            return None
    
    async def get_order_book(self, symbol: str) -> Optional[Dict]:
        """AkShare 不支持订单簿"""
        return None
    
    async def get_futures_quote(self, symbol: str) -> Optional[Dict]:
        """AkShare 不支持期货行情（由专门的期货模块处理）"""
        return None
    
    def is_healthy(self) -> bool:
        """检查数据源是否健康"""
        return self.cb.is_available()
    
    async def ping(self) -> bool:
        """探测数据源连通性"""
        try:
            result = await self.get_quote("sh000001")
            return result is not None
        except Exception:
            return False
