"""
CSV缓存管理器

功能：
- 本地CSV文件缓存K线数据
- 减少对数据源API的请求
- 支持缓存过期检测

设计原则：
- 缓存目录: cache/kline/
- 文件命名: {symbol}_{period}.csv
- 过期检测: 根据周期自动判断
"""

import os
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class CsvCacheManager:
    """本地CSV缓存管理器"""
    
    def __init__(self, cache_dir: str = 'cache/kline'):
        """
        初始化缓存管理器
        
        Args:
            cache_dir: 缓存目录路径
        """
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
    
    def get(self, symbol: str, period: str) -> Optional[pd.DataFrame]:
        """
        从CSV缓存读取数据
        
        Args:
            symbol: 股票代码
            period: 周期
            
        Returns:
            DataFrame或None（缓存不存在或已过期）
        """
        path = self._get_path(symbol, period)
        
        if not os.path.exists(path):
            logger.debug(f"[CsvCache] {symbol} {period} not cached")
            return None
        
        try:
            df = pd.read_csv(path, parse_dates=['date'])
            
            # 检查缓存是否过期
            if self._is_stale(df, period):
                logger.info(f"[CsvCache] {symbol} {period} cache stale, will refresh")
                return None
            
            logger.debug(f"[CsvCache] {symbol} {period} cache hit: {len(df)} rows")
            return df
            
        except Exception as e:
            logger.warning(f"[CsvCache] Failed to read {path}: {e}")
            return None
    
    def set(self, symbol: str, period: str, df: pd.DataFrame):
        """
        写入CSV缓存
        
        Args:
            symbol: 股票代码
            period: 周期
            df: K线数据DataFrame
        """
        if df is None or df.empty:
            return
        
        path = self._get_path(symbol, period)
        
        try:
            # 确保date列是字符串格式
            if 'date' in df.columns:
                df['date'] = df['date'].astype(str)
            
            df.to_csv(path, index=False)
            logger.debug(f"[CsvCache] Saved {symbol} {period}: {len(df)} rows")
            
        except Exception as e:
            logger.warning(f"[CsvCache] Failed to write {path}: {e}")
    
    def delete(self, symbol: str, period: str):
        """
        删除缓存文件
        
        Args:
            symbol: 股票代码
            period: 周期
        """
        path = self._get_path(symbol, period)
        
        if os.path.exists(path):
            try:
                os.remove(path)
                logger.debug(f"[CsvCache] Deleted {symbol} {period}")
            except Exception as e:
                logger.warning(f"[CsvCache] Failed to delete {path}: {e}")
    
    def clear_all(self):
        """清空所有缓存"""
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.csv'):
                    filepath = os.path.join(self.cache_dir, filename)
                    os.remove(filepath)
            logger.info(f"[CsvCache] Cleared all cache files")
        except Exception as e:
            logger.warning(f"[CsvCache] Failed to clear cache: {e}")
    
    def get_cache_stats(self) -> Dict:
        """
        获取缓存统计信息
        
        Returns:
            统计信息字典
        """
        total_files = 0
        total_size = 0
        
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.csv'):
                    filepath = os.path.join(self.cache_dir, filename)
                    total_files += 1
                    total_size += os.path.getsize(filepath)
        except Exception:
            pass
        
        return {
            'total_files': total_files,
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'cache_dir': self.cache_dir
        }
    
    def _get_path(self, symbol: str, period: str) -> str:
        """
        获取缓存文件路径
        
        Args:
            symbol: 股票代码
            period: 周期
            
        Returns:
            文件路径
        """
        # 清理symbol格式
        clean_symbol = symbol.replace('/', '_').replace(':', '_')
        return os.path.join(self.cache_dir, f"{clean_symbol}_{period}.csv")
    
    def _is_stale(self, df: pd.DataFrame, period: str) -> bool:
        """
        检查缓存是否过期
        
        Args:
            df: 缓存数据
            period: 周期
            
        Returns:
            是否过期
        """
        if df.empty:
            return True
        
        try:
            # 获取最后日期
            last_date = df['date'].max()
            
            if isinstance(last_date, str):
                last_date = datetime.strptime(last_date.split()[0], '%Y-%m-%d')
            elif isinstance(last_date, pd.Timestamp):
                last_date = last_date.to_pydatetime()
            
            now = datetime.now()
            
            # 根据周期判断过期
            if period == 'daily':
                # 日K：超过1天视为过期
                return (now - last_date).days > 1
            
            elif period == 'weekly':
                # 周K：超过7天视为过期
                return (now - last_date).days > 7
            
            elif period == 'monthly':
                # 月K：超过30天视为过期
                return (now - last_date).days > 30
            
            elif period in ('1min', '5min', '15min', '30min', '60min'):
                # 分钟K：超过1小时视为过期
                return (now - last_date).seconds > 3600
            
            # 默认：超过1天过期
            return (now - last_date).days > 1
            
        except Exception as e:
            logger.warning(f"[CsvCache] Failed to check staleness: {e}")
            return True


# 全局实例
csv_cache = CsvCacheManager()
