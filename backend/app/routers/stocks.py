"""
涨跌停/异动/北向资金 API
数据来源: akshare 东方财富
"""
import asyncio
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from fastapi import APIRouter
import httpx

# 代理由 proxy_config.py 统一管理，从环境变量读取
# 用户需在启动前设置 HTTP_PROXY/HTTPS_PROXY 环境变量

logger = logging.getLogger(__name__)
router = APIRouter()

# 线程池执行器用于运行阻塞代码
_executor = ThreadPoolExecutor(max_workers=2)

# 缓存配置（带大小限制和过期清理）
_CACHE = {}
_CACHE_TTL = 300  # 5分钟
_MAX_CACHE_SIZE = 30  # 最大缓存条目数


def _cleanup_expired():
    """清理过期缓存"""
    now = time.time()
    expired = [k for k, v in _CACHE.items() if (now - v['time']) >= _CACHE_TTL]
    for k in expired:
        del _CACHE[k]
    if expired:
        logger.info(f"[Stocks Cache CLEANUP] 清理 {len(expired)} 条过期缓存")


def _evict_oldest():
    """淘汰最旧的缓存"""
    if len(_CACHE) >= _MAX_CACHE_SIZE:
        oldest_key = min(_CACHE, key=lambda k: _CACHE[k]['time'])
        del _CACHE[oldest_key]
        logger.info(f"[Stocks Cache EVICT] 移除缓存: {oldest_key}")


def _cache_or_fetch(key, fetch_fn, ttl=_CACHE_TTL):
    """缓存装饰器（带过期清理和大小限制）"""
    now = time.time()
    
    # 定期清理（每10次访问清理一次）
    if len(_CACHE) > 0 and now % 10 < 1:
        _cleanup_expired()
    
    if key in _CACHE and (now - _CACHE[key]['time']) < ttl:
        return _CACHE[key]['data']
    try:
        data = fetch_fn()
        # 不缓存空结果，只缓存有效数据
        if data:
            _evict_oldest()
            _CACHE[key] = {'data': data, 'time': now}
        return data
    except Exception as e:
        logger.warning(f"[Stocks API] {key} fetch failed: {e}")
        if key in _CACHE:
            return _CACHE[key]['data']
        return []


def success_response(data, message="success"):
    return {
        "code": 0,
        "message": message,
        "data": data,
        "timestamp": int(datetime.now().timestamp() * 1000)
    }


@router.get("/limit_up")
async def get_limit_up():
    """
    获取今日涨停股票列表
    来源: akshare stock_zt_pool_em
    """
    def fetch():
        import akshare as ak
        today = datetime.now().strftime('%Y%m%d')
        try:
            df = ak.stock_zt_pool_em(date=today)
            if df is None or len(df) == 0:
                return []
            result = []
            for _, row in df.iterrows():
                code = str(row.get('代码', ''))
                # 判断交易所: 0/2/3开头为深圳，6开头为上海
                symbol = 'sh' + code if code.startswith('6') else 'sz' + code
                result.append({
                    'symbol': symbol,
                    'code': code,
                    'name': str(row.get('名称', '')),
                    'price': float(row.get('最新价', 0)),
                    'change_pct': float(row.get('涨跌幅', 0)),
                    'turnover': float(row.get('成交额', 0)),
                    'float_market_cap': float(row.get('流通市值', 0)),
                    'total_market_cap': float(row.get('总市值', 0)),
                    'turnover_rate': float(row.get('换手率', 0)),
                    'seal_fund': float(row.get('封板资金', 0)) if '封板资金' in row else 0,
                    'first_seal_time': str(row.get('首次封板时间', '')),
                    'last_seal_time': str(row.get('最后封板时间', '')) if '最后封板时间' in row else '',
                    'board_count': int(row.get('连板数', 0)),
                    'industry': str(row.get('所属行业', '')),
                })
            return result
        except Exception as e:
            logger.warning(f"[Stocks] limit_up fetch error: {e}")
            return []

    # P2-11 修复: 使用 run_in_executor 避免阻塞事件循环
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(_executor, lambda: _cache_or_fetch('limit_up', fetch))
    return success_response({'limit_up': data, 'count': len(data)})


@router.get("/limit_down")
async def get_limit_down():
    """
    获取今日跌停股票列表
    来源: akshare stock_zt_pool_dtgc_em
    """
    def fetch():
        import akshare as ak
        today = datetime.now().strftime('%Y%m%d')
        try:
            df = ak.stock_zt_pool_dtgc_em(date=today)
            if df is None or len(df) == 0:
                return []
            result = []
            for _, row in df.iterrows():
                code = str(row.get('代码', ''))
                symbol = 'sh' + code if code.startswith('6') else 'sz' + code
                result.append({
                    'symbol': symbol,
                    'code': code,
                    'name': str(row.get('名称', '')),
                    'price': float(row.get('最新价', 0)),
                    'change_pct': float(row.get('涨跌幅', 0)),
                    'turnover': float(row.get('成交额', 0)),
                    'float_market_cap': float(row.get('流通市值', 0)),
                    'total_market_cap': float(row.get('总市值', 0)),
                    'turnover_rate': float(row.get('换手率', 0)),
                    'continue_stop': int(row.get('连续跌停', 0)),
                    'open_count': int(row.get('开板次数', 0)) if '开板次数' in row else 0,
                    'industry': str(row.get('所属行业', '')),
                })
            return result
        except Exception as e:
            logger.warning(f"[Stocks] limit_down fetch error: {e}")
            return []

    # P2-11 修复: 使用 run_in_executor 避免阻塞事件循环
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(_executor, lambda: _cache_or_fetch('limit_down', fetch))
    return success_response({'limit_down': data, 'count': len(data)})


@router.get("/unusual")
async def get_unusual():
    """
    获取异动股票（涨幅大或换手率高）
    来源: 基于涨停池 + 强势股 + 炸板股综合
    """
    def fetch():
        import akshare as ak
        today = datetime.now().strftime('%Y%m%d')
        try:
            df = ak.stock_zt_pool_em(date=today)
            if df is None or len(df) == 0:
                return []
            result = []
            for _, row in df.iterrows():
                turnover_rate = float(row.get('换手率', 0))
                change_pct = float(row.get('涨跌幅', 0))
                # 异动: 换手率>5% 或 涨幅>9.5%
                if turnover_rate > 5 or change_pct >= 9.5:
                    code = str(row.get('代码', ''))
                    symbol = 'sh' + code if code.startswith('6') else 'sz' + code
                    result.append({
                        'symbol': symbol,
                        'code': code,
                        'name': str(row.get('名称', '')),
                        'price': float(row.get('最新价', 0)),
                        'change_pct': change_pct,
                        'turnover_rate': turnover_rate,
                        'turnover': float(row.get('成交额', 0)),
                        'volume_ratio': round(turnover_rate / 3, 1),  # 估算量比
                        'industry': str(row.get('所属行业', '')),
                        'board_count': int(row.get('连板数', 0)),
                    })
            # 按换手率排序
            result.sort(key=lambda x: x['turnover_rate'], reverse=True)
            return result[:30]
        except Exception as e:
            logger.warning(f"[Stocks] unusual fetch error: {e}")
            return []

    # P2-11 修复: 使用 run_in_executor 避免阻塞事件循环
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(_executor, lambda: _cache_or_fetch('unusual', fetch))
    return success_response({'unusual': data, 'count': len(data)})


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
                for _, row in df_sh.head(1000).iterrows():
                    code = str(row.get('证券代码', '')).strip()
                    name = str(row.get('证券简称', '')).strip()
                    if code and name:
                        _STOCK_CACHE.append({'code': code, 'name': name, 'market': 'SH'})
        except Exception as e:
            logger.warning(f"[Stocks] SH load error: {e}")
        
        try:
            df_sz = ak.stock_info_sz_name_code()
            if df_sz is not None and len(df_sz) > 0:
                for _, row in df_sz.head(1000).iterrows():
                    code = str(row.get('A股代码', '')).strip()
                    name = str(row.get('A股简称', '')).strip()
                    if code and name:
                        _STOCK_CACHE.append({'code': code, 'name': name, 'market': 'SZ'})
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
    """
    搜索股票代码和名称
    """
    logger.info(f"[Stocks] search called with q='{q}'")
    
    if not q or len(q) < 1:
        return success_response({'stocks': [], 'count': 0})

    loop = asyncio.get_event_loop()
    try:
        results = await asyncio.wait_for(
            loop.run_in_executor(_executor, _search_stocks_local, q),
            timeout=10.0
        )
        logger.info(f"[Stocks] search returned {len(results)} results")
    except asyncio.TimeoutError:
        logger.warning("[Stocks] search timeout")
        results = []
    except Exception as e:
        logger.warning(f"[Stocks] search error: {e}")
        results = []
    
    return success_response({'stocks': results, 'count': len(results)})


@router.get("/quote")
async def get_quote(symbol: str):
    """
    获取单个股票实时行情
    来源: 腾讯 qt.gtimg.cn
    """
    def fetch():
        try:
            # symbol 格式: sh600519 或 sz000001
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"https://qt.gtimg.cn/q={symbol}")
                resp.raise_for_status()
                raw = resp.text
            for line in raw.splitlines():
                line = line.strip()
                if "=" not in line or "none_match" in line:
                    continue
                parts = line.split("=")[1].strip('";\n').split(",")
                if len(parts) > 32:
                    return {
                        'symbol': symbol,
                        'name': parts[1] if len(parts) > 1 else '',
                        'price': float(parts[1]) if parts[1] else 0,
                        'change_pct': float(parts[32]) if parts[32] else 0,
                        'open': float(parts[5]) if parts[5] else 0,
                        'high': float(parts[33]) if parts[33] else 0,
                        'low': float(parts[34]) if parts[34] else 0,
                        'volume': float(parts[7]) if parts[7] else 0,
                        'amount': float(parts[9]) if parts[9] else 0,
                        'bid1': float(parts[20]) if parts[20] else 0,
                        'ask1': float(parts[21]) if parts[21] else 0,
                        'update_time': parts[30] if len(parts) > 30 else '',
                    }
            return {}
        except Exception as e:
            logger.warning(f"[Stocks] quote error for {symbol}: {e}")
            return {}

    data = _cache_or_fetch(f'quote_{symbol}', fetch, ttl=10)
    return success_response(data)


@router.get("/limit_summary")
async def get_limit_summary():
    """
    获取涨跌停汇总（市场情绪指标）
    """
    def fetch():
        import akshare as ak
        today = datetime.now().strftime('%Y%m%d')
        try:
            zt_df = ak.stock_zt_pool_em(date=today)
            dt_df = ak.stock_zt_pool_dtgc_em(date=today)
            
            zt_count = len(zt_df) if zt_df is not None else 0
            dt_count = len(dt_df) if dt_df is not None else 0
            
            # 涨停行业分布
            industry_dist = {}
            if zt_df is not None and len(zt_df) > 0:
                for _, row in zt_df.iterrows():
                    ind = str(row.get('所属行业', '其他'))
                    industry_dist[ind] = industry_dist.get(ind, 0) + 1
            
            # 强势股（换手率最高的）- 兼容列名变化
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

    # P2-11 修复: 使用 run_in_executor 避免阻塞事件循环
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(_executor, lambda: _cache_or_fetch('limit_summary', fetch))
    return success_response(data)
