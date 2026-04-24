"""
fund_fetcher.py — 基金数据抓取器（Phase 6.2 性能优化版）

核心优化:
1. 严格超时控制：连接 3s + 读取 5s = 8s 最大等待
2. 激进 TTL 缓存：分级缓存策略（60s ~ 24h）
3. 快速熔断：超时立即降级，不阻塞
4. 并发组装：支持 asyncio.gather 并发请求

缓存策略:
- 静态数据（基金信息）: 24 小时
- 低频数据（投资组合）: 12 小时
- 历史序列（净值 K 线）: 4 小时
- 高频数据（ETF 实时）: 60 秒
"""
import requests
import time
import logging
from typing import Optional, Dict, List, Any
from functools import wraps
from cachetools import TTLCache
import asyncio

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════
# 缓存配置（激进策略）
# ══════════════════════════════════════════════════════════════════════

# 最大缓存条目数
CACHE_MAX_SIZE = 1000

# 分级 TTL（秒）
CACHE_TTL = {
    'etf_spot': 60,        # ETF 实时行情：60 秒
    'fund_info': 86400,    # 基金基本信息：24 小时
    'portfolio': 43200,    # 投资组合：12 小时
    'nav_history': 14400,  # 净值历史：4 小时
    'fund_rank': 3600,     # 基金排行：1 小时
}

# 初始化缓存
_etf_spot_cache = TTLCache(maxsize=CACHE_MAX_SIZE, ttl=CACHE_TTL['etf_spot'])
_fund_info_cache = TTLCache(maxsize=CACHE_MAX_SIZE, ttl=CACHE_TTL['fund_info'])
_portfolio_cache = TTLCache(maxsize=CACHE_MAX_SIZE, ttl=CACHE_TTL['portfolio'])
_nav_history_cache = TTLCache(maxsize=CACHE_MAX_SIZE, ttl=CACHE_TTL['nav_history'])
_fund_rank_cache = TTLCache(maxsize=CACHE_MAX_SIZE, ttl=CACHE_TTL['fund_rank'])

# 超时配置（秒）
TIMEOUT_CONNECT = 3   # 连接超时
TIMEOUT_READ = 5      # 读取超时
TIMEOUT_TOTAL = 8     # 总超时


# ══════════════════════════════════════════════════════════════════════
# 装饰器：带缓存和超时的 API 调用
# ══════════════════════════════════════════════════════════════════════

def cached_api(cache: TTLCache, max_attempts=2, timeout=TIMEOUT_TOTAL):
    """
    带缓存和超时的 API 调用装饰器
    
    - 先查缓存，命中直接返回
    - 未命中则调用原函数，带超时控制
    - 成功结果写入缓存
    - 失败快速降级
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{args}:{kwargs}"
            
            # 1. 查缓存
            if cache_key in cache:
                logger.debug(f"[Cache HIT] {func.__name__} {cache_key[:50]}...")
                return cache[cache_key]
            
            # 2. 执行请求（带超时）
            start = time.time()
            last_exc = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    # 异步超时控制
                    result = await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=timeout
                    )
                    
                    if result:  # 非空结果视为成功
                        elapsed = time.time() - start
                        cache[cache_key] = result
                        logger.info(f"[{func.__name__}] 成功 source={result.get('source', 'unknown')} elapsed={elapsed:.2f}s cache=MISS")
                        return result
                        
                except asyncio.TimeoutError:
                    last_exc = TimeoutError(f"API timeout after {timeout}s")
                    logger.warning(f"[{func.__name__}] 尝试 {attempt}/{max_attempts} 超时 ({timeout}s)")
                    break  # 超时不重试，立即降级
                    
                except Exception as e:
                    last_exc = e
                    logger.warning(f"[{func.__name__}] 尝试 {attempt}/{max_attempts} 失败：{e}")
                    if attempt < max_attempts:
                        await asyncio.sleep(0.2 * attempt)  # 短暂退避
            
            # 3. 所有尝试失败，返回 None 触发降级
            elapsed = time.time() - start
            logger.error(f"[{func.__name__}] {max_attempts} 次尝试后仍失败 elapsed={elapsed:.2f}s")
            return None
        
        return wrapper
    return decorator


# ══════════════════════════════════════════════════════════════════════
# 数据源客户端（异步 + 超时）
# ══════════════════════════════════════════════════════════════════════

class AkShareClient:
    """AkShare 东方财富数据源（主力）"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    @cached_api(_etf_spot_cache, max_attempts=1, timeout=TIMEOUT_TOTAL)
    async def get_etf_spot(self, code: str) -> Optional[Dict]:
        """获取 ETF 实时行情（含折溢价）"""
        start = time.time()
        try:
            import akshare as ak
            df = await asyncio.to_thread(ak.fund_etf_spot_em)
            
            if df is not None and not df.empty:
                matched = df[df['基金代码'] == code]
                if not matched.empty:
                    row = matched.iloc[0]
                    elapsed = time.time() - start
                    logger.info(f"[AkShare ETF] {code} 成功 elapsed={elapsed:.2f}s")
                    return {
                        'source': 'akshare',
                        'code': code,
                        'name': str(row.get('基金简称', '')),
                        'price': float(row.get('最新价', 0) or 0),
                        'change_pct': float(row.get('涨跌幅', 0) or 0),
                        'change': float(row.get('涨跌额', 0) or 0),
                        'volume': float(row.get('成交量', 0) or 0),
                        'amount': float(row.get('成交额', 0) or 0),
                        'high': float(row.get('最高价', 0) or 0),
                        'low': float(row.get('最低价', 0) or 0),
                        'prev_close': float(row.get('昨收', 0) or 0),
                        'iopv': float(row.get('IOPV', 0) or 0),
                        'premium_rate': float(row.get('折价率', 0) or 0),
                    }
        except Exception as e:
            logger.warning(f"[AkShare ETF] {code} 获取失败：{e}")
        return None
    
    @cached_api(_fund_info_cache, max_attempts=1, timeout=TIMEOUT_TOTAL)
    async def get_fund_info(self, code: str) -> Optional[Dict]:
        """获取场外公募基金基本信息"""
        start = time.time()
        try:
            import akshare as ak
            # 缓存的基金排行数据中查找
            df = await asyncio.to_thread(ak.fund_open_fund_rank_em, symbol="全部")
            
            if df is not None and not df.empty:
                matched = df[df['基金代码'] == code]
                if not matched.empty:
                    row = matched.iloc[0]
                    elapsed = time.time() - start
                    logger.info(f"[AkShare Fund] {code} 成功 elapsed={elapsed:.2f}s")
                    return {
                        'source': 'akshare',
                        'code': code,
                        'name': str(row.get('基金简称', '')),
                        'type': str(row.get('基金类型', '')),
                        'nav': float(row.get('单位净值', 0) or 0),
                        'nav_change_pct': float(row.get('日增长率', 0) or 0),
                        'nav_date': str(row.get('日期', '')),
                        'scale': str(row.get('基金规模', '')),
                        'found_date': str(row.get('成立日期', '')),
                        'manager': str(row.get('基金经理', '')),
                        'company': str(row.get('基金公司', '')),
                        'rating': str(row.get('评级', '')),
                    }
        except Exception as e:
            logger.warning(f"[AkShare Fund] {code} 获取失败：{e}")
        return None
    
    @cached_api(_portfolio_cache, max_attempts=1, timeout=TIMEOUT_TOTAL)
    async def get_fund_portfolio(self, code: str) -> Optional[Dict]:
        """获取基金投资组合（重仓股 + 资产配置）"""
        start = time.time()
        try:
            import akshare as ak
            df = await asyncio.to_thread(ak.fund_portfolio_hold_em, symbol=code)
            
            if df is not None and not df.empty:
                stock_df = df[df['股票名称'].notna()]
                stocks = []
                for _, row in stock_df.head(10).iterrows():
                    stocks.append({
                        'code': str(row.get('股票代码', '')),
                        'name': str(row.get('股票名称', '')),
                        'price': float(row.get('最新价', 0) or 0),
                        'change_pct': float(row.get('涨跌幅', 0) or 0),
                        'ratio': float(row.get('占净值比', 0) or 0),
                        'shares': float(row.get('持股数', 0) or 0),
                        'mkt_value': float(row.get('持仓市值', 0) or 0),
                        'change': float(row.get('较上期变化', 0) or 0),
                    })
                
                asset_alloc = []
                try:
                    asset_df = await asyncio.to_thread(ak.fund_portfolio_asset_em, symbol=code)
                    if asset_df is not None and not asset_df.empty:
                        for _, row in asset_df.iterrows():
                            asset_alloc.append({
                                'name': str(row.get('项目', '')),
                                'ratio': float(row.get('占净值比例', 0) or 0),
                                'amount': float(row.get('金额', 0) or 0),
                            })
                except:
                    pass
                
                elapsed = time.time() - start
                logger.info(f"[AkShare Portfolio] {code} 成功 elapsed={elapsed:.2f}s stocks={len(stocks)}")
                return {
                    'source': 'akshare',
                    'code': code,
                    'quarter': str(df.iloc[0].get('报告期', '')) if not df.empty else '',
                    'stocks': stocks,
                    'assets': asset_alloc,
                }
        except Exception as e:
            logger.warning(f"[AkShare Portfolio] {code} 获取失败：{e}")
        return None
    
    @cached_api(_nav_history_cache, max_attempts=1, timeout=TIMEOUT_TOTAL)
    async def get_fund_nav_history(self, code: str, period: str = '6m') -> Optional[List[Dict]]:
        """获取场外基金净值历史"""
        start = time.time()
        try:
            import akshare as ak
            df = await asyncio.to_thread(ak.fund_open_fund_info_em, symbol=code, indicator="单位净值走势")
            
            if df is not None and not df.empty:
                result = []
                for _, row in df.iterrows():
                    result.append({
                        'date': str(row.get('日期', '')),
                        'nav': float(row.get('单位净值', 0) or 0),
                        'accumulated_nav': float(row.get('累计净值', 0) or 0),
                    })
                
                elapsed = time.time() - start
                logger.info(f"[AkShare NAV] {code} 成功 elapsed={elapsed:.2f}s records={len(result)}")
                return result[-180:]
        except Exception as e:
            logger.warning(f"[AkShare NAV] {code} 获取失败：{e}")
        return None
    
    @cached_api(_fund_rank_cache, max_attempts=1, timeout=TIMEOUT_TOTAL)
    async def get_fund_rank(self, type: str = '全部') -> Optional[List[Dict]]:
        """获取基金排行"""
        start = time.time()
        try:
            import akshare as ak
            df = await asyncio.to_thread(ak.fund_open_fund_rank_em, symbol=type)
            
            if df is not None and not df.empty:
                result = []
                for _, row in df.iterrows():
                    result.append({
                        'code': str(row.get('基金代码', '')),
                        'name': str(row.get('基金简称', '')),
                        'nav': float(row.get('单位净值', 0) or 0),
                        'nav_growthrate': float(row.get('日增长率', 0) or 0),
                        'type': str(row.get('基金类型', '')),
                        'scale': str(row.get('基金规模', '')),
                        'find_date': str(row.get('成立日期', '')),
                        'manager': str(row.get('基金经理', '')),
                    })
                
                elapsed = time.time() - start
                logger.info(f"[AkShare Rank] {type} 成功 elapsed={elapsed:.2f}s count={len(result)}")
                return result
        except Exception as e:
            logger.warning(f"[AkShare Rank] 获取失败：{e}")
        return None


# ══════════════════════════════════════════════════════════════════════
# 统一抓取器（并发 + 降级）
# ══════════════════════════════════════════════════════════════════════

class FundFetcher:
    """
    基金数据统一抓取器（Phase 6.2 性能优化版）
    
    降级策略:
    1. ETF: AkShare → Mock
    2. 公募：AkShare → Mock
    3. 组合：AkShare → Mock
    
    并发策略:
    - 使用 asyncio.gather 并发请求多个数据
    """
    
    def __init__(self):
        self.ak = AkShareClient()
    
    # ── ETF 相关 ───────────────────────────────────────────────────────
    
    async def get_etf_info(self, code: str) -> Optional[Dict]:
        """获取 ETF 信息（带缓存）"""
        logger.info(f"[FundFetcher] 获取 ETF {code} 信息...")
        start = time.time()
        
        data = await self.ak.get_etf_spot(code)
        if data:
            return data
        
        elapsed = time.time() - start
        logger.warning(f"[FundFetcher] {code} AkShare 失败，降级到 Mock elapsed={elapsed:.2f}s")
        return self._mock_etf_info(code)
    
    async def get_etf_history(self, code: str, period: str = 'daily') -> List[Dict]:
        """获取 ETF 历史 K 线"""
        from app.routers.fund import _sina_etf_history
        # Sina 数据同步获取，已有超时控制
        return await asyncio.to_thread(_sina_etf_history, code, period, 300)
    
    # ── 公募基金相关 ───────────────────────────────────────────────────
    
    async def get_fund_info(self, code: str) -> Optional[Dict]:
        """获取公募基金信息（带缓存）"""
        logger.info(f"[FundFetcher] 获取公募基金 {code} 信息...")
        start = time.time()
        
        data = await self.ak.get_fund_info(code)
        if data:
            return data
        
        elapsed = time.time() - start
        logger.warning(f"[FundFetcher] {code} AkShare 失败，降级到 Mock elapsed={elapsed:.2f}s")
        return self._mock_fund_info(code)
    
    async def get_fund_portfolio(self, code: str) -> Optional[Dict]:
        """获取基金投资组合（带缓存）"""
        logger.info(f"[FundFetcher] 获取 {code} 投资组合...")
        start = time.time()
        
        data = await self.ak.get_fund_portfolio(code)
        if data:
            return data
        
        elapsed = time.time() - start
        logger.warning(f"[FundFetcher] {code} 组合获取失败，降级到 Mock elapsed={elapsed:.2f}s")
        return self._mock_portfolio(code)
    
    async def get_fund_nav_history(self, code: str, period: str = '6m') -> List[Dict]:
        """获取基金净值历史（带缓存）"""
        logger.info(f"[FundFetcher] 获取 {code} 净值历史...")
        start = time.time()
        
        data = await self.ak.get_fund_nav_history(code, period)
        if data:
            return data
        
        elapsed = time.time() - start
        logger.warning(f"[FundFetcher] {code} 净值历史获取失败，降级到 Mock elapsed={elapsed:.2f}s")
        return self._mock_nav_history(period)
    
    async def get_fund_rank(self, type: str = '全部') -> List[Dict]:
        """获取基金排行（带缓存）"""
        logger.info(f"[FundFetcher] 获取基金排行 {type}...")
        start = time.time()
        
        data = await self.ak.get_fund_rank(type)
        if data:
            return data
        
        elapsed = time.time() - start
        logger.warning(f"[FundFetcher] 排行获取失败 elapsed={elapsed:.2f}s")
        return []
    
    # ── 并发组装 ───────────────────────────────────────────────────────
    
    async def get_fund_full_data(self, code: str, is_etf: bool = False) -> Dict:
        """
        并发获取基金完整数据（基本信息 + 历史 + 组合）
        
        使用 asyncio.gather 并发请求，而不是串行阻塞
        """
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
    
    # ── Mock 数据（兜底）────────────────────────────────────────────────
    
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
                {'code': '600519', 'name': '贵州茅台', 'ratio': 5.89, 'price': 1700, 'change_pct': 1.2},
                {'code': '300750', 'name': '宁德时代', 'ratio': 2.78, 'price': 190, 'change_pct': -0.5},
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
        days = {'1m': 20, '3m': 60, '6m': 120, '1y': 240, '3y': 720}.get(period, 120)
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
