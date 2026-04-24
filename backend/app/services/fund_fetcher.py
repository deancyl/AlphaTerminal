"""
fund_fetcher.py — 基金数据抓取器（Phase 6.3 修复版）

修复内容:
1. 移除 cachetools.TTLCache（与 async 不兼容）
2. 实现手动异步安全缓存（字典 + expire_at）
3. 统一数据格式（英文 key，NaN → None）
4. 保持超时控制（8s max）
"""
import requests
import time
import logging
import asyncio
from typing import Optional, Dict, List, Any
import pandas as pd

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════
# 异步安全缓存（手动实现）
# ══════════════════════════════════════════════════════════════════════

class AsyncCache:
    """
    异步安全的内存缓存
    
    使用方式:
    cache = AsyncCache()
    
    @cache.cached(ttl=3600)
    async def get_data(key):
        return await fetch_data()
    """
    
    def __init__(self):
        self._cache: Dict[str, Dict] = {}
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存（检查过期）"""
        async with self._lock:
            if key not in self._cache:
                return None
            
            entry = self._cache[key]
            if entry['expire_at'] > time.time():
                return entry['data']
            
            # 过期删除
            del self._cache[key]
            return None
    
    async def set(self, key: str, data: Any, ttl: int) -> None:
        """设置缓存"""
        async with self._lock:
            self._cache[key] = {
                'data': data,
                'expire_at': time.time() + ttl,
            }
    
    async def delete(self, key: str) -> None:
        """删除缓存"""
        async with self._lock:
            self._cache.pop(key, None)
    
    def cached(self, ttl: int, key_prefix: str = ''):
        """缓存装饰器（用于 async 函数）"""
        def decorator(func):
            async def wrapper(*args, **kwargs):
                # 生成缓存键
                cache_key = f"{key_prefix}{func.__name__}:{args}:{kwargs}"
                
                # 查缓存
                result = await self.get(cache_key)
                if result is not None:
                    logger.debug(f"[Cache HIT] {cache_key[:60]}...")
                    return result
                
                # 执行函数
                start = time.time()
                result = await func(*args, **kwargs)
                elapsed = time.time() - start
                
                # 写入缓存
                if result is not None:
                    await self.set(cache_key, result, ttl)
                    logger.info(f"[{func.__name__}] 成功 elapsed={elapsed:.2f}s ttl={ttl}s cache=MISS")
                
                return result
            return wrapper
        return decorator
    
    def stats(self) -> Dict:
        """缓存统计"""
        now = time.time()
        valid = sum(1 for e in self._cache.values() if e['expire_at'] > now)
        return {
            'total_keys': len(self._cache),
            'valid_keys': valid,
            'expired_keys': len(self._cache) - valid,
        }


# 全局缓存实例
fund_cache = AsyncCache()

# 缓存 TTL 配置（秒）
CACHE_TTL = {
    'etf_spot': 60,        # ETF 实时：60 秒
    'fund_info': 86400,    # 基金信息：24 小时
    'portfolio': 43200,    # 投资组合：12 小时
    'nav_history': 14400,  # 净值历史：4 小时
    'fund_rank': 3600,     # 基金排行：1 小时
}

# 超时配置（秒）
TIMEOUT_TOTAL = 8


# ══════════════════════════════════════════════════════════════════════
# 数据清洗工具
# ══════════════════════════════════════════════════════════════════════

def clean_value(val) -> Any:
    """
    清洗 Pandas 特殊值
    NaN/NaT → None
    numpy 类型 → Python 原生类型
    """
    import numpy as np
    
    if val is None:
        return None
    
    # 处理 Pandas 时间类型
    if hasattr(pd, 'isna') and pd.isna(val):
        return None
    
    # 处理 numpy 类型
    if isinstance(val, (np.floating, np.integer)):
        return val.item()  # numpy → Python
    
    if isinstance(val, float):
        if val != val:  # NaN check
            return None
        return val
    
    if isinstance(val, str):
        return val.strip() if val.strip() else None
    
    return val


def clean_dataframe_row(row: pd.Series) -> Dict:
    """清洗 DataFrame 行"""
    return {k: clean_value(v) for k, v in row.items()}


# ══════════════════════════════════════════════════════════════════════
# 数据源客户端（异步 + 缓存 + 超时）
# ══════════════════════════════════════════════════════════════════════

class AkShareClient:
    """AkShare 东方财富数据源（主力）"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    @fund_cache.cached(CACHE_TTL['etf_spot'], key_prefix='etf:')
    async def get_etf_spot(self, code: str) -> Optional[Dict]:
        """获取 ETF 实时行情（含折溢价）"""
        try:
            import akshare as ak
            
            # 同步调用转异步（带超时）
            df = await asyncio.wait_for(
                asyncio.to_thread(ak.fund_etf_spot_em),
                timeout=TIMEOUT_TOTAL
            )
            
            if df is not None and not df.empty:
                matched = df[df['基金代码'] == code]
                if not matched.empty:
                    row = matched.iloc[0]
                    return {
                        'source': 'akshare',
                        'code': clean_value(row.get('基金代码')),
                        'name': clean_value(row.get('基金简称')),
                        'price': clean_value(row.get('最新价')),
                        'change_pct': clean_value(row.get('涨跌幅')),
                        'change': clean_value(row.get('涨跌额')),
                        'volume': clean_value(row.get('成交量')),
                        'amount': clean_value(row.get('成交额')),
                        'high': clean_value(row.get('最高价')),
                        'low': clean_value(row.get('最低价')),
                        'prev_close': clean_value(row.get('昨收')),
                        'iopv': clean_value(row.get('IOPV')),
                        'premium_rate': clean_value(row.get('折价率')),
                    }
        except asyncio.TimeoutError:
            logger.warning(f"[AkShare ETF] {code} 超时 ({TIMEOUT_TOTAL}s)")
        except Exception as e:
            logger.warning(f"[AkShare ETF] {code} 获取失败：{e}")
        
        return None
    
    @fund_cache.cached(CACHE_TTL['fund_info'], key_prefix='fund:')
    async def get_fund_info(self, code: str) -> Optional[Dict]:
        """获取场外公募基金基本信息"""
        try:
            import akshare as ak
            
            df = await asyncio.wait_for(
                asyncio.to_thread(ak.fund_open_fund_rank_em, symbol="全部"),
                timeout=TIMEOUT_TOTAL
            )
            
            if df is not None and not df.empty:
                matched = df[df['基金代码'] == code]
                if not matched.empty:
                    row = matched.iloc[0]
                    return {
                        'source': 'akshare',
                        'code': clean_value(row.get('基金代码')),
                        'name': clean_value(row.get('基金简称')),
                        'type': clean_value(row.get('基金类型')),
                        'nav': clean_value(row.get('单位净值')),
                        'nav_change_pct': clean_value(row.get('日增长率')),
                        'nav_date': clean_value(row.get('日期')),
                        'scale': clean_value(row.get('基金规模')),
                        'found_date': clean_value(row.get('成立日期')),
                        'manager': clean_value(row.get('基金经理')),
                        'company': clean_value(row.get('基金公司')),
                        'rating': clean_value(row.get('评级')),
                    }
        except asyncio.TimeoutError:
            logger.warning(f"[AkShare Fund] {code} 超时 ({TIMEOUT_TOTAL}s)")
        except Exception as e:
            logger.warning(f"[AkShare Fund] {code} 获取失败：{e}")
        
        return None
    
    @fund_cache.cached(CACHE_TTL['portfolio'], key_prefix='portfolio:')
    async def get_fund_portfolio(self, code: str) -> Optional[Dict]:
        """获取基金投资组合（重仓股 + 资产配置）"""
        try:
            import akshare as ak
            
            df = await asyncio.wait_for(
                asyncio.to_thread(ak.fund_portfolio_hold_em, symbol=code),
                timeout=TIMEOUT_TOTAL
            )
            
            if df is not None and not df.empty:
                stock_df = df[df['股票名称'].notna()]
                stocks = []
                for _, row in stock_df.head(10).iterrows():
                    stocks.append({
                        'code': clean_value(row.get('股票代码')),
                        'name': clean_value(row.get('股票名称')),
                        'price': clean_value(row.get('最新价')),
                        'change_pct': clean_value(row.get('涨跌幅')),
                        'ratio': clean_value(row.get('占净值比')),
                        'shares': clean_value(row.get('持股数')),
                        'mkt_value': clean_value(row.get('持仓市值')),
                        'change': clean_value(row.get('较上期变化')),
                    })
                
                asset_alloc = []
                try:
                    asset_df = await asyncio.wait_for(
                        asyncio.to_thread(ak.fund_portfolio_asset_em, symbol=code),
                        timeout=TIMEOUT_TOTAL
                    )
                    if asset_df is not None and not asset_df.empty:
                        for _, row in asset_df.iterrows():
                            asset_alloc.append({
                                'name': clean_value(row.get('项目')),
                                'ratio': clean_value(row.get('占净值比例')),
                                'amount': clean_value(row.get('金额')),
                            })
                except:
                    pass
                
                return {
                    'source': 'akshare',
                    'code': code,
                    'quarter': clean_value(df.iloc[0].get('报告期')) if not df.empty else '',
                    'stocks': stocks,
                    'assets': asset_alloc,
                }
        except asyncio.TimeoutError:
            logger.warning(f"[AkShare Portfolio] {code} 超时 ({TIMEOUT_TOTAL}s)")
        except Exception as e:
            logger.warning(f"[AkShare Portfolio] {code} 获取失败：{e}")
        
        return None
    
    @fund_cache.cached(CACHE_TTL['nav_history'], key_prefix='nav:')
    async def get_fund_nav_history(self, code: str, period: str = '6m') -> Optional[List[Dict]]:
        """获取场外基金净值历史"""
        try:
            import akshare as ak
            
            df = await asyncio.wait_for(
                asyncio.to_thread(ak.fund_open_fund_info_em, symbol=code, indicator="单位净值走势"),
                timeout=TIMEOUT_TOTAL
            )
            
            if df is not None and not df.empty:
                result = []
                for _, row in df.iterrows():
                    result.append({
                        'date': clean_value(row.get('日期')),
                        'nav': clean_value(row.get('单位净值')),
                        'accumulated_nav': clean_value(row.get('累计净值')),
                    })
                return result[-180:]
        except asyncio.TimeoutError:
            logger.warning(f"[AkShare NAV] {code} 超时 ({TIMEOUT_TOTAL}s)")
        except Exception as e:
            logger.warning(f"[AkShare NAV] {code} 获取失败：{e}")
        
        return None
    
    @fund_cache.cached(CACHE_TTL['fund_rank'], key_prefix='rank:')
    async def get_fund_rank(self, type: str = '全部') -> Optional[List[Dict]]:
        """获取基金排行"""
        try:
            import akshare as ak
            
            df = await asyncio.wait_for(
                asyncio.to_thread(ak.fund_open_fund_rank_em, symbol=type),
                timeout=TIMEOUT_TOTAL
            )
            
            if df is not None and not df.empty:
                result = []
                for _, row in df.iterrows():
                    result.append({
                        'code': clean_value(row.get('基金代码')),
                        'name': clean_value(row.get('基金简称')),
                        'nav': clean_value(row.get('单位净值')),
                        'nav_growthrate': clean_value(row.get('日增长率')),
                        'type': clean_value(row.get('基金类型')),
                        'scale': clean_value(row.get('基金规模')),
                        'find_date': clean_value(row.get('成立日期')),
                        'manager': clean_value(row.get('基金经理')),
                    })
                return result
        except asyncio.TimeoutError:
            logger.warning(f"[AkShare Rank] 超时 ({TIMEOUT_TOTAL}s)")
        except Exception as e:
            logger.warning(f"[AkShare Rank] 获取失败：{e}")
        
        return None


# ══════════════════════════════════════════════════════════════════════
# 统一抓取器
# ══════════════════════════════════════════════════════════════════════

class FundFetcher:
    """基金数据统一抓取器"""
    
    def __init__(self):
        self.ak = AkShareClient()
    
    async def get_etf_info(self, code: str) -> Optional[Dict]:
        """获取 ETF 信息"""
        logger.info(f"[FundFetcher] 获取 ETF {code} 信息...")
        data = await self.ak.get_etf_spot(code)
        if data:
            return data
        logger.warning(f"[FundFetcher] {code} 降级到 Mock")
        return self._mock_etf_info(code)
    
    async def get_etf_history(self, code: str, period: str = 'daily') -> List[Dict]:
        """获取 ETF 历史 K 线"""
        from app.routers.fund import _sina_etf_history
        return await asyncio.to_thread(_sina_etf_history, code, period, 300)
    
    async def get_fund_info(self, code: str) -> Optional[Dict]:
        """获取公募基金信息"""
        logger.info(f"[FundFetcher] 获取公募基金 {code} 信息...")
        data = await self.ak.get_fund_info(code)
        if data:
            return data
        logger.warning(f"[FundFetcher] {code} 降级到 Mock")
        return self._mock_fund_info(code)
    
    async def get_fund_portfolio(self, code: str) -> Optional[Dict]:
        """获取基金投资组合"""
        logger.info(f"[FundFetcher] 获取 {code} 投资组合...")
        data = await self.ak.get_fund_portfolio(code)
        if data:
            return data
        logger.warning(f"[FundFetcher] {code} 降级到 Mock")
        return self._mock_portfolio(code)
    
    async def get_fund_nav_history(self, code: str, period: str = '6m') -> List[Dict]:
        """获取基金净值历史"""
        logger.info(f"[FundFetcher] 获取 {code} 净值历史...")
        data = await self.ak.get_fund_nav_history(code, period)
        if data:
            return data
        logger.warning(f"[FundFetcher] {code} 降级到 Mock")
        return self._mock_nav_history(period)
    
    async def get_fund_rank(self, type: str = '全部') -> List[Dict]:
        """获取基金排行"""
        logger.info(f"[FundFetcher] 获取基金排行 {type}...")
        data = await self.ak.get_fund_rank(type)
        return data if data else []
    
    async def get_fund_full_data(self, code: str, is_etf: bool = False) -> Dict:
        """并发获取基金完整数据"""
        if is_etf:
            results = await asyncio.gather(
                self.get_etf_info(code),
                self.get_etf_history(code),
                return_exceptions=True
            )
            return {
                'info': results[0] if not isinstance(results[0], Exception) else None,
                'history': results[1] if not isinstance(results[1], Exception) else [],
            }
        else:
            results = await asyncio.gather(
                self.get_fund_info(code),
                self.get_fund_nav_history(code),
                self.get_fund_portfolio(code),
                return_exceptions=True
            )
            return {
                'info': results[0] if not isinstance(results[0], Exception) else None,
                'nav_history': results[1] if not isinstance(results[1], Exception) else [],
                'portfolio': results[2] if not isinstance(results[2], Exception) else None,
            }
    
    def _mock_etf_info(self, code: str) -> Dict:
        return {
            'source': 'mock',
            'code': code,
            'name': f'ETF-{code}',
            'price': 1.0 + hash(code) % 1000 / 1000,
            'change_pct': (hash(code + 'c') % 200 - 100) / 10,
            'volume': hash(code + 'v') % 10000000,
            'iopv': 1.0 + hash(code) % 1000 / 1000,
            'premium_rate': (hash(code + 'p') % 100 - 50) / 10,
        }
    
    def _mock_fund_info(self, code: str) -> Dict:
        return {
            'source': 'mock',
            'code': code,
            'name': f'基金-{code}',
            'type': '混合型',
            'nav': 1.0 + hash(code) % 2000 / 1000,
            'nav_change_pct': (hash(code + 'c') % 200 - 100) / 10,
            'scale': f'{hash(code) % 100}.{hash(code) % 10}',
            'manager': '张三',
            'company': 'XX 基金',
        }
    
    def _mock_portfolio(self, code: str) -> Dict:
        return {
            'source': 'mock',
            'code': code,
            'quarter': '2024 年 1 季度',
            'stocks': [
                {'code': '600519', 'name': '贵州茅台', 'ratio': 5.89},
                {'code': '300750', 'name': '宁德时代', 'ratio': 2.78},
            ],
            'assets': [
                {'name': '股票', 'ratio': 85.5},
                {'name': '债券', 'ratio': 5.2},
                {'name': '现金', 'ratio': 8.3},
                {'name': '其他', 'ratio': 1.0},
            ]
        }
    
    def _mock_nav_history(self, period: str) -> List[Dict]:
        import datetime
        days = {'1m': 20, '3m': 60, '6m': 120, '1y': 240}.get(period, 120)
        result = []
        base = 1.0 + hash(period) % 2000 / 1000
        for i in range(days):
            date = datetime.date.today() - datetime.timedelta(days=days - i)
            base = base * (1 + (hash(str(i)) % 100 - 48) / 1000)
            result.append({
                'date': date.isoformat(),
                'nav': round(base, 4),
                'accumulated_nav': round(base * 1.1, 4),
            })
        return result


# 单例
_fetcher_instance = None

def get_fetcher() -> FundFetcher:
    global _fetcher_instance
    if _fetcher_instance is None:
        _fetcher_instance = FundFetcher()
    return _fetcher_instance
