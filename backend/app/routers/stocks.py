"""
涨跌停/异动/北向资金 API
数据来源: akshare 东方财富
"""
import logging
import time
from datetime import datetime
from fastapi import APIRouter
import httpx

logger = logging.getLogger(__name__)
router = APIRouter()

# 缓存配置
_CACHE = {}
_CACHE_TTL = 300  # 5分钟


def _cache_or_fetch(key, fetch_fn, ttl=_CACHE_TTL):
    """缓存装饰器"""
    now = time.time()
    if key in _CACHE and (now - _CACHE[key]['time']) < ttl:
        return _CACHE[key]['data']
    try:
        data = fetch_fn()
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

    data = _cache_or_fetch('limit_up', fetch)
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

    data = _cache_or_fetch('limit_down', fetch)
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

    data = _cache_or_fetch('unusual', fetch)
    return success_response({'unusual': data, 'count': len(data)})


@router.get("/search")
async def search_stocks(q: str = ""):
    """
    搜索股票代码和名称
    返回 A 股全市场股票基础信息
    来源: akshare stock_info_a_code_name
    """
    if not q or len(q) < 1:
        return success_response({'stocks': [], 'count': 0})

    def fetch():
        import akshare as ak
        try:
            df = ak.stock_info_a_code_name()
            if df is None or len(df) == 0:
                return []
            # 搜索
            q_lower = q.lower()
            mask = df.apply(lambda r: 
                q_lower in str(r.get('code', '')).lower() or 
                q_lower in str(r.get('name', '')).lower(), axis=1)
            results = df[mask].head(20)
            return results.to_dict('records')
        except Exception as e:
            logger.warning(f"[Stocks] search error: {e}")
            return []

    data = _cache_or_fetch(f'search_{q}', fetch, ttl=600)
    return success_response({'stocks': data, 'count': len(data) if isinstance(data, list) else 0})


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
            
            # 强势股（换手率最高的）
            strong_df = zt_df.sort_values('换手率', ascending=False).head(5) if zt_df is not None and len(zt_df) > 0 else None
            
            return {
                'date': today,
                'zt_count': zt_count,
                'dt_count': dt_count,
                'market_sentiment': '极强' if zt_count > 50 else '强势' if zt_count > 30 else '偏强' if zt_count > 15 else '偏弱' if zt_count > 5 else '极弱',
                'zt_industry': dict(sorted(industry_dist.items(), key=lambda x: x[1], reverse=True)[:5]),
                'strongest': [
                    {'name': str(r['名称']), 'turnover_rate': float(r['换手率']), 'change_pct': float(r['涨跌幅'])}
                    for r in strong_df.to_dict('records')
                ] if strong_df is not None else [],
            }
        except Exception as e:
            logger.warning(f"[Stocks] limit_summary error: {e}")
            return {'zt_count': 0, 'dt_count': 0, 'market_sentiment': '未知'}

    data = _cache_or_fetch('limit_summary', fetch)
    return success_response(data)
