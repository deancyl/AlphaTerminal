"""
涨跌停/异动/北向资金 API
数据来源: akshare 东方财富

Timeout Behavior:
    Quote fetching has 10s timeout.
    Search endpoint has 5s timeout.
    Returns 504 on timeout.
"""
import asyncio
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from fastapi import APIRouter
import httpx
import pandas as pd
from app.utils.response import success_response, error_response, ErrorCode
from app.config.timeout import SEARCH_TIMEOUT, QUOTE_TIMEOUT
from app.services.data_cache import get_cache

logger = logging.getLogger(__name__)
router = APIRouter()

CPU_COUNT = os.cpu_count() or 4
_executor = ThreadPoolExecutor(max_workers=min(8, CPU_COUNT * 2), thread_name_prefix="stocks_api_")

# Use DataCache singleton
_cache = get_cache()
NAMESPACE = "stocks:"
TTL = 300  # 5 minutes


def _cache_or_fetch(key, fetch_fn, ttl=TTL):
    """Cache helper using DataCache singleton"""
    cache_key = f"{NAMESPACE}{key}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached
    try:
        data = fetch_fn()
        if data:
            _cache.set(cache_key, data, ttl=ttl)
        return data
    except Exception as e:
        logger.warning(f"[Stocks API] {key} fetch failed: {e}")
        return cached or []


@router.get("/limit_up")
async def get_limit_up():
    def fetch():
        import akshare as ak
        today = datetime.now().strftime('%Y%m%d')
        try:
            df = ak.stock_zt_pool_em(date=today)
            if df is None or len(df) == 0:
                return []
            df_work = df.copy()
            df_work['code'] = df_work['代码'].astype(str)
            df_work['symbol'] = df_work['code'].apply(lambda x: 'sh' + x if x.startswith('6') else 'sz' + x)
            df_work['name'] = df_work['名称'].astype(str)
            df_work['price'] = df_work['最新价'].apply(lambda x: float(x) if x else 0)
            df_work['change_pct'] = df_work['涨跌幅'].apply(lambda x: float(x) if x else 0)
            df_work['turnover'] = df_work['成交额'].apply(lambda x: float(x) if x else 0)
            df_work['float_market_cap'] = df_work['流通市值'].apply(lambda x: float(x) if x else 0)
            df_work['total_market_cap'] = df_work['总市值'].apply(lambda x: float(x) if x else 0)
            df_work['turnover_rate'] = df_work['换手率'].apply(lambda x: float(x) if x else 0)
            df_work['seal_fund'] = df_work.get('封板资金', 0).apply(lambda x: float(x) if x else 0) if '封板资金' in df_work else 0
            df_work['first_seal_time'] = df_work['首次封板时间'].astype(str)
            df_work['last_seal_time'] = df_work.get('最后封板时间', '').astype(str) if '最后封板时间' in df_work else ''
            df_work['board_count'] = df_work['连板数'].apply(lambda x: int(x) if x else 0)
            df_work['industry'] = df_work['所属行业'].astype(str)
            return df_work[['symbol', 'code', 'name', 'price', 'change_pct', 'turnover',
                           'float_market_cap', 'total_market_cap', 'turnover_rate', 'seal_fund',
                           'first_seal_time', 'last_seal_time', 'board_count', 'industry']].to_dict('records')
        except Exception as e:
            logger.warning(f"[Stocks] limit_up fetch error: {e}")
            return []

    loop = asyncio.get_event_loop()
    try:
        data = await asyncio.wait_for(
            loop.run_in_executor(_executor, lambda: _cache_or_fetch('limit_up', fetch)),
            timeout=QUOTE_TIMEOUT
        )
        return success_response({'limit_up': data, 'count': len(data)})
    except asyncio.TimeoutError:
        logger.warning("[Stocks] limit_up timeout")
        return error_response("请求超时，请稍后重试", code=504)


@router.get("/limit_down")
async def get_limit_down():
    def fetch():
        import akshare as ak
        today = datetime.now().strftime('%Y%m%d')
        try:
            df = ak.stock_zt_pool_dtgc_em(date=today)
            if df is None or len(df) == 0:
                return []
            df_work = df.copy()
            df_work['code'] = df_work['代码'].astype(str)
            df_work['symbol'] = df_work['code'].apply(lambda x: 'sh' + x if x.startswith('6') else 'sz' + x)
            df_work['name'] = df_work['名称'].astype(str)
            df_work['price'] = df_work['最新价'].apply(lambda x: float(x) if x else 0)
            df_work['change_pct'] = df_work['涨跌幅'].apply(lambda x: float(x) if x else 0)
            df_work['turnover'] = df_work['成交额'].apply(lambda x: float(x) if x else 0)
            df_work['float_market_cap'] = df_work['流通市值'].apply(lambda x: float(x) if x else 0)
            df_work['total_market_cap'] = df_work['总市值'].apply(lambda x: float(x) if x else 0)
            df_work['turnover_rate'] = df_work['换手率'].apply(lambda x: float(x) if x else 0)
            df_work['continue_stop'] = df_work['连续跌停'].apply(lambda x: int(x) if x else 0)
            df_work['open_count'] = df_work.get('开板次数', 0).apply(lambda x: int(x) if x else 0) if '开板次数' in df_work else 0
            df_work['industry'] = df_work['所属行业'].astype(str)
            return df_work[['symbol', 'code', 'name', 'price', 'change_pct', 'turnover',
                           'float_market_cap', 'total_market_cap', 'turnover_rate',
                           'continue_stop', 'open_count', 'industry']].to_dict('records')
        except Exception as e:
            logger.warning(f"[Stocks] limit_down fetch error: {e}")
            return []

    loop = asyncio.get_event_loop()
    try:
        data = await asyncio.wait_for(
            loop.run_in_executor(_executor, lambda: _cache_or_fetch('limit_down', fetch)),
            timeout=QUOTE_TIMEOUT
        )
        return success_response({'limit_down': data, 'count': len(data)})
    except asyncio.TimeoutError:
        logger.warning("[Stocks] limit_down timeout")
        return error_response("请求超时，请稍后重试", code=504)


@router.get("/unusual")
async def get_unusual():
    def fetch():
        import akshare as ak
        today = datetime.now().strftime('%Y%m%d')
        try:
            df = ak.stock_zt_pool_em(date=today)
            if df is None or len(df) == 0:
                return []
            df_work = df.copy()
            df_work['turnover_rate'] = df_work['换手率'].apply(lambda x: float(x) if x else 0)
            df_work['change_pct'] = df_work['涨跌幅'].apply(lambda x: float(x) if x else 0)
            df_filtered = df_work[(df_work['turnover_rate'] > 5) | (df_work['change_pct'] >= 9.5)]
            df_filtered['code'] = df_filtered['代码'].astype(str)
            df_filtered['symbol'] = df_filtered['code'].apply(lambda x: 'sh' + x if x.startswith('6') else 'sz' + x)
            df_filtered['name'] = df_filtered['名称'].astype(str)
            df_filtered['price'] = df_filtered['最新价'].apply(lambda x: float(x) if x else 0)
            df_filtered['turnover'] = df_filtered['成交额'].apply(lambda x: float(x) if x else 0)
            df_filtered['volume_ratio'] = df_filtered['turnover_rate'] / 3
            df_filtered['industry'] = df_filtered['所属行业'].astype(str)
            df_filtered['board_count'] = df_filtered['连板数'].apply(lambda x: int(x) if x else 0)
            result_df = df_filtered[['symbol', 'code', 'name', 'price', 'change_pct', 'turnover_rate',
                                     'turnover', 'volume_ratio', 'industry', 'board_count']]
            result_df = result_df.sort_values('turnover_rate', ascending=False).head(30)
            return result_df.to_dict('records')
        except Exception as e:
            logger.warning(f"[Stocks] unusual fetch error: {e}")
            return []

    loop = asyncio.get_event_loop()
    try:
        data = await asyncio.wait_for(
            loop.run_in_executor(_executor, lambda: _cache_or_fetch('unusual', fetch)),
            timeout=QUOTE_TIMEOUT
        )
        return success_response({'unusual': data, 'count': len(data)})
    except asyncio.TimeoutError:
        logger.warning("[Stocks] unusual timeout")
        return error_response("请求超时，请稍后重试", code=504)


# 缓存的股票列表
_STOCK_CACHE = []
_STOCK_CACHE_LOADED = False


def _load_stock_cache():
    """加载股票缓存"""
    global _STOCK_CACHE, _STOCK_CACHE_LOADED
    if _STOCK_CACHE_LOADED:
        return
    
    try:
        import akshare as ak
        try:
            df_sh = ak.stock_info_sh_name_code()
            if df_sh is not None and len(df_sh) > 0:
                df_work = df_sh.head(1000)[['证券代码', '证券简称']].copy()
                df_work = df_work.dropna(subset=['证券代码', '证券简称'])
                df_work['code'] = df_work['证券代码'].astype(str).str.strip()
                df_work['name'] = df_work['证券简称'].astype(str).str.strip()
                for r in df_work[['code', 'name']].to_dict('records'):
                    if r['code'] and r['name']:
                        _STOCK_CACHE.append({'code': r['code'], 'name': r['name'], 'market': 'SH'})
        except Exception as e:
            logger.warning(f"[Stocks] SH load error: {e}")
        
        try:
            df_sz = ak.stock_info_sz_name_code()
            if df_sz is not None and len(df_sz) > 0:
                df_work = df_sz.head(1000)[['A股代码', 'A股简称']].copy()
                df_work = df_work.dropna(subset=['A股代码', 'A股简称'])
                df_work['code'] = df_work['A股代码'].astype(str).str.strip()
                df_work['name'] = df_work['A股简称'].astype(str).str.strip()
                for r in df_work[['code', 'name']].to_dict('records'):
                    if r['code'] and r['name']:
                        _STOCK_CACHE.append({'code': r['code'], 'name': r['name'], 'market': 'SZ'})
        except Exception as e:
            logger.warning(f"[Stocks] SZ load error: {e}")
        
        _STOCK_CACHE_LOADED = True
        logger.info(f"[Stocks] Stock cache loaded: {len(_STOCK_CACHE)} stocks")
    except Exception as e:
        logger.warning(f"[Stocks] Cache load error: {e}")


# 预加载常用股票（后备）
_COMMON_STOCKS = [
    {'code': '600519', 'name': '贵州茅台', 'market': 'SH'},
    {'code': '000001', 'name': '平安银行', 'market': 'SZ'},
    {'code': '000002', 'name': '万科A', 'market': 'SZ'},
    {'code': '600036', 'name': '招商银行', 'market': 'SH'},
    {'code': '601318', 'name': '中国平安', 'market': 'SH'},
    {'code': '600030', 'name': '中信证券', 'market': 'SH'},
    {'code': '000858', 'name': '五粮液', 'market': 'SZ'},
    {'code': '002594', 'name': '比亚迪', 'market': 'SZ'},
    {'code': '300750', 'name': '宁德时代', 'market': 'SZ'},
    {'code': '600016', 'name': '民生银行', 'market': 'SH'},
    {'code': '601166', 'name': '兴业银行', 'market': 'SH'},
    {'code': '600000', 'name': '浦发银行', 'market': 'SH'},
    {'code': '000333', 'name': '美的集团', 'market': 'SZ'},
    {'code': '002415', 'name': '海康威视', 'market': 'SZ'},
    {'code': '600276', 'name': '恒瑞医药', 'market': 'SH'},
    {'code': '688981', 'name': '中芯国际', 'market': 'SH'},
    {'code': '688111', 'name': '金山办公', 'market': 'SH'},
    {'code': '300059', 'name': '东方财富', 'market': 'SZ'},
    {'code': '002230', 'name': '科大讯飞', 'market': 'SZ'},
    {'code': '000776', 'name': '广发证券', 'market': 'SZ'},
    {'code': '601012', 'name': '隆基绿能', 'market': 'SH'},
    {'code': '600585', 'name': '海螺水泥', 'market': 'SH'},
    {'code': '601628', 'name': '中国人寿', 'market': 'SH'},
    {'code': '600028', 'name': '中国石化', 'market': 'SH'},
    {'code': '601857', 'name': '中国石油', 'market': 'SH'},
    {'code': '600887', 'name': '伊利股份', 'market': 'SH'},
    {'code': '603288', 'name': '海天味业', 'market': 'SH'},
    {'code': '600009', 'name': '上海机场', 'market': 'SH'},
    {'code': '601888', 'name': '中国中免', 'market': 'SH'},
]


def _search_stocks_local(q):
    """本地搜索：同时搜索 _COMMON_STOCKS 和 _STOCK_CACHE"""
    q_lower = q.lower()
    results = []
    seen = set()
    
    def add_stock(stock):
        key = stock['code']
        if key not in seen:
            seen.add(key)
            results.append(stock)
    
    # 优先搜索常用股票
    for stock in _COMMON_STOCKS:
        if q_lower in stock['code'].lower() or q_lower in stock['name'].lower():
            add_stock(stock)
            if len(results) >= 20:
                return results
    
    # 再搜索全量缓存（沪/深股票）
    _load_stock_cache()  # 确保缓存已加载
    for stock in _STOCK_CACHE:
        if q_lower in stock['code'].lower() or q_lower in stock['name'].lower():
            add_stock(stock)
            if len(results) >= 20:
                break
    
    return results


@router.get("/search")
async def search_stocks(q: str = ""):
    logger.info(f"[Stocks] search called with q='{q}'")
    
    if not q or len(q) < 1:
        return success_response({'stocks': [], 'count': 0})

    loop = asyncio.get_event_loop()
    try:
        results = await asyncio.wait_for(
            loop.run_in_executor(_executor, _search_stocks_local, q),
            timeout=SEARCH_TIMEOUT
        )
        logger.info(f"[Stocks] search returned {len(results)} results")
    except asyncio.TimeoutError:
        logger.warning("[Stocks] search timeout")
        return error_response("搜索超时，请稍后重试", code=504)
    except Exception as e:
        logger.warning(f"[Stocks] search error: {e}")
        results = []
    
    return success_response({'stocks': results, 'count': len(results)})


@router.get("/quote")
async def get_quote(symbol: str):
    def fetch():
        try:
            sym = symbol
            bare_symbol = symbol.replace('sh', '').replace('sz', '')
            if not sym.startswith('sh') and not sym.startswith('sz'):
                if sym.startswith('6'):
                    sym = 'sh' + sym
                else:
                    sym = 'sz' + sym
                bare_symbol = symbol
            
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"https://qt.gtimg.cn/q={sym}")
                resp.raise_for_status()
                raw = resp.text
            
            result = {
                'symbol': symbol,
                'name': '',
                'price': 0,
                'change_pct': 0,
                'open': 0,
                'high': 0,
                'low': 0,
                'volume': 0,
                'amount': 0,
                'bid1': 0,
                'ask1': 0,
                'update_time': '',
                'industry': '--',
                'totalShares': None,
                'floatShares': None,
                'totalMarketCap': None,
                'floatMarketCap': None,
                'listDate': None,
                'business': '暂无主营业务数据',
            }
            
            for line in raw.splitlines():
                line = line.strip()
                if "=" not in line or "none_match" in line:
                    continue
                try:
                    value_part = line.split("=", 1)[1].strip('";\n')
                    parts = value_part.split("~")
                    if len(parts) > 35:
                        result.update({
                            'name': parts[1] if len(parts) > 1 else '',
                            'price': float(parts[3]) if parts[3] else 0,
                            'change_pct': float(parts[32]) if parts[32] else 0,
                            'open': float(parts[5]) if parts[5] else 0,
                            'high': float(parts[33]) if parts[33] else 0,
                            'low': float(parts[34]) if parts[34] else 0,
                            'volume': float(parts[6]) if parts[6] else 0,
                            'amount': float(parts[37]) if parts[37] else 0,
                            'bid1': float(parts[9]) if parts[9] else 0,
                            'ask1': float(parts[19]) if parts[19] else 0,
                            'update_time': parts[30] if len(parts) > 30 else '',
                        })
                        break
                except (ValueError, IndexError) as e:
                    logger.debug(f"[Stocks] parse line error: {e}")
                    continue
            
            try:
                import akshare as ak
                
                if bare_symbol.startswith('6'):
                    try:
                        info_df = ak.stock_info_sh_name_code()
                        if info_df is not None and len(info_df) > 0:
                            row = info_df[info_df['证券代码'] == bare_symbol]
                            if len(row) > 0:
                                list_date = row.iloc[0].get('上市日期')
                                if list_date:
                                    result['listDate'] = str(list_date)
                    except Exception as e:
                        logger.debug(f"[Stocks] stock_info_sh_name_code error: {e}")
                
                try:
                    profile_df = ak.stock_profile_cninfo(symbol=bare_symbol)
                    if profile_df is not None and len(profile_df) > 0:
                        profile = profile_df.iloc[0]
                        if not result.get('industry') or result['industry'] == '--':
                            result['industry'] = profile.get('所属行业', '--') or '--'
                        if not result.get('business') or result['business'] == '暂无主营业务数据':
                            result['business'] = profile.get('主营业务', '暂无主营业务数据') or '暂无主营业务数据'
                        if not result.get('listDate'):
                            result['listDate'] = str(profile.get('上市日期', '')) if profile.get('上市日期') else None
                except Exception as e:
                    logger.debug(f"[Stocks] stock_profile_cninfo error for {bare_symbol}: {e}")
                
                try:
                    exchange = "SH" if bare_symbol.startswith('6') else "SZ"
                    spot_df = ak.stock_individual_spot_xq(symbol=f"{exchange}{bare_symbol}")
                    if spot_df is not None and len(spot_df) > 0:
                        spot_data = dict(zip(spot_df['item'], spot_df['value']))
                        
                        float_shares = spot_data.get('流通股')
                        float_market_cap = spot_data.get('流通值')
                        
                        if float_shares:
                            try:
                                result['floatShares'] = float(float_shares)
                            except (ValueError, TypeError) as e:
                                logger.debug(f"[Stocks] Failed to parse floatShares for {bare_symbol}: {e}")
                        if float_market_cap:
                            try:
                                result['floatMarketCap'] = float(float_market_cap)
                            except (ValueError, TypeError) as e:
                                logger.debug(f"[Stocks] Failed to parse floatMarketCap for {bare_symbol}: {e}")
                except Exception as e:
                    logger.debug(f"[Stocks] stock_individual_spot_xq error for {bare_symbol}: {e}")
                
                if not result.get('totalShares'):
                    try:
                        from datetime import datetime
                        today = datetime.now().strftime('%Y%m%d')
                        one_year_ago = (datetime.now() - __import__('datetime').timedelta(days=365)).strftime('%Y%m%d')
                        share_df = ak.stock_share_change_cninfo(symbol=bare_symbol, start_date=one_year_ago, end_date=today)
                        if share_df is not None and len(share_df) > 0 and '总股本' in share_df.columns:
                            latest = share_df.sort_values('变动日期', ascending=False).iloc[0]
                            total_wan = latest.get('总股本')
                            if total_wan is not None and pd.notna(total_wan):
                                result['totalShares'] = float(total_wan) * 10000
                    except Exception as e:
                        logger.debug(f"[Stocks] stock_share_change_cninfo error for {bare_symbol}: {e}")
                
                if not result.get('totalShares'):
                    try:
                        holder_df = ak.stock_main_stock_holder(stock=bare_symbol)
                        if holder_df is not None and len(holder_df) > 0:
                            first = holder_df.iloc[0]
                            shares = first.get('持股数量')
                            ratio = first.get('持股比例')
                            if pd.notna(shares) and pd.notna(ratio) and ratio > 0:
                                result['totalShares'] = float(shares) / (float(ratio) / 100)
                                logger.debug(f"[Stocks] Derived totalShares from stock_main_stock_holder: {result['totalShares']}")
                    except Exception as e:
                        logger.debug(f"[Stocks] stock_main_stock_holder error for {bare_symbol}: {e}")
                
                if not result.get('industry') or result['industry'] == '--':
                    try:
                        info_df = ak.stock_individual_info_em(symbol=bare_symbol)
                        if info_df is not None and len(info_df) > 0:
                            info_dict = dict(zip(info_df['item'], info_df['value']))
                            if not result.get('industry') or result['industry'] == '--':
                                result['industry'] = info_dict.get('行业', '--') or '--'
                            if not result.get('business') or result['business'] == '暂无主营业务数据':
                                result['business'] = info_dict.get('主营业务', '暂无主营业务数据') or '暂无主营业务数据'
                            
                            def parse_capital(value):
                                if not value:
                                    return None
                                try:
                                    value = str(value).strip()
                                    if '亿' in value:
                                        return float(value.replace('亿', '').strip()) * 100000000
                                    elif '万' in value:
                                        return float(value.replace('万', '').strip()) * 10000
                                    else:
                                        return float(value)
                                except Exception:
                                    return None
                            
                            if not result.get('totalShares'):
                                result['totalShares'] = parse_capital(info_dict.get('总股本', None))
                            if not result.get('floatShares'):
                                result['floatShares'] = parse_capital(info_dict.get('流通股', None))
                            
                            if result['price'] > 0:
                                if result.get('totalShares') and not result.get('totalMarketCap'):
                                    result['totalMarketCap'] = result['price'] * result['totalShares']
                                if result.get('floatShares') and not result.get('floatMarketCap'):
                                    result['floatMarketCap'] = result['price'] * result['floatShares']
                    except Exception as e:
                        logger.debug(f"[Stocks] stock_individual_info_em error for {bare_symbol}: {e}")
                    
            except Exception as e:
                logger.debug(f"[Stocks] akshare info error for {bare_symbol}: {e}")
            
            return result
        except Exception as e:
            logger.warning(f"[Stocks] quote error for {symbol}: {e}")
            return {}

    try:
        data = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(_executor, lambda: _cache_or_fetch(f'quote_{symbol}', fetch, ttl=10)),
            timeout=QUOTE_TIMEOUT
        )
        return success_response(data)
    except asyncio.TimeoutError:
        logger.warning(f"[Stocks] quote timeout for {symbol}")
        return error_response("请求超时，请稍后重试", code=504)


@router.get("/limit_summary")
async def get_limit_summary():
    def fetch():
        import akshare as ak
        today = datetime.now().strftime('%Y%m%d')
        try:
            zt_df = ak.stock_zt_pool_em(date=today)
            dt_df = ak.stock_zt_pool_dtgc_em(date=today)
            
            zt_count = len(zt_df) if zt_df is not None else 0
            dt_count = len(dt_df) if dt_df is not None else 0
            
            industry_dist = {}
            if zt_df is not None and len(zt_df) > 0:
                industry_counts = zt_df['所属行业'].astype(str).value_counts()
                industry_dist = industry_counts.to_dict()
            
            def _safe_sort_by_turnover(df):
                if df is None or len(df) == 0:
                    return None
                TURNOVER_COLS = ['换手率', '换手率(%)', 'turnover_rate']
                col = next((c for c in TURNOVER_COLS if c in df.columns), None)
                if col is None:
                    return None
                return df.sort_values(col, ascending=False).head(5)
            
            strong_df = _safe_sort_by_turnover(zt_df)
            CHANGE_COLS = ['涨跌幅', '涨跌额', 'change_pct']
            NAME_COLS = ['名称', 'name', '股票名称']
            
            return {
                'date': today,
                'zt_count': zt_count,
                'dt_count': dt_count,
                'market_sentiment': '极强' if zt_count > 50 else '强势' if zt_count > 30 else '偏强' if zt_count > 15 else '偏弱' if zt_count > 5 else '极弱',
                'zt_industry': dict(sorted(industry_dist.items(), key=lambda x: x[1], reverse=True)[:5]),
                'strongest': [
                    {
                        'name': str(r.get('名称') or r.get('name') or r.get('股票名称', '')),
                        'turnover_rate': float(r.get('换手率') or r.get('换手率(%)') or r.get('turnover_rate', 0)),
                        'change_pct': float(r.get('涨跌幅') or r.get('涨跌额') or r.get('change_pct', 0))
                    }
                    for r in (strong_df.to_dict('records') if strong_df is not None else [])
                ],
            }
        except Exception as e:
            logger.warning(f"[Stocks] limit_summary error: {e}")
            return {'zt_count': 0, 'dt_count': 0, 'market_sentiment': '未知'}

    loop = asyncio.get_event_loop()
    try:
        data = await asyncio.wait_for(
            loop.run_in_executor(_executor, lambda: _cache_or_fetch('limit_summary', fetch)),
            timeout=QUOTE_TIMEOUT
        )
        return success_response(data)
    except asyncio.TimeoutError:
        logger.warning("[Stocks] limit_summary timeout")
        return error_response("请求超时，请稍后重试", code=504)
