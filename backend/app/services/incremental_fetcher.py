"""
增量数据获取服务

功能:
- K线增量更新（只获取last_date之后的数据）
- 利用数据源的start_date参数
- 自动合并增量数据到现有数据
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import akshare as ak

logger = logging.getLogger(__name__)


class IncrementalKlineFetcher:
    """增量K线获取器"""
    
    def __init__(self):
        self._last_dates: Dict[str, str] = {}
    
    def get_last_date(self, symbol: str) -> Optional[str]:
        """获取该股票的最后数据日期"""
        return self._last_dates.get(symbol)
    
    def set_last_date(self, symbol: str, date: str):
        """记录最后数据日期"""
        self._last_dates[symbol] = date
    
    async def fetch_incremental(
        self,
        symbol: str,
        period: str = "daily",
        last_date: Optional[str] = None
    ) -> List[Dict]:
        """
        获取增量K线数据
        
        Args:
            symbol: 股票代码
            period: 周期
            last_date: 最后数据日期（YYYY-MM-DD）
        
        Returns:
            增量K线数据列表
        """
        if last_date is None:
            last_date = self.get_last_date(symbol)
        
        if last_date is None:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
        else:
            start_dt = datetime.strptime(last_date, "%Y-%m-%d") + timedelta(days=1)
            start_date = start_dt.strftime("%Y%m%d")
        
        try:
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period=period,
                start_date=start_date,
                adjust="qfq"
            )
            
            if df.empty:
                return []
            
            result = []
            for _, row in df.iterrows():
                result.append({
                    "date": row["日期"],
                    "open": row["开盘"],
                    "high": row["最高"],
                    "low": row["最低"],
                    "close": row["收盘"],
                    "volume": row["成交量"],
                    "amount": row["成交额"],
                })
            
            if result:
                self.set_last_date(symbol, result[-1]["date"])
            
            logger.info(f"[IncrementalFetcher] {symbol} 增量获取 {len(result)} 条")
            return result
            
        except Exception as e:
            logger.error(f"[IncrementalFetcher] {symbol} 增量获取失败: {e}")
            return []
    
    def merge_data(
        self,
        existing: List[Dict],
        incremental: List[Dict]
    ) -> List[Dict]:
        """
        合并增量数据到现有数据
        
        Args:
            existing: 现有数据
            incremental: 增量数据
        
        Returns:
            合并后的数据
        """
        if not incremental:
            return existing
        
        existing_dates = {item["date"] for item in existing}
        
        new_data = [
            item for item in incremental
            if item["date"] not in existing_dates
        ]
        
        result = existing + new_data
        result.sort(key=lambda x: x["date"])
        
        return result


_fetcher: Optional[IncrementalKlineFetcher] = None


def get_incremental_fetcher() -> IncrementalKlineFetcher:
    """获取全局增量获取器实例"""
    global _fetcher
    if _fetcher is None:
        _fetcher = IncrementalKlineFetcher()
    return _fetcher
