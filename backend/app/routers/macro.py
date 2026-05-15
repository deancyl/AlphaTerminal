"""
宏观经济数据接口
数据来源: akshare (国家统计局、中国人民银行等权威机构)
覆盖: GDP、CPI、PPI、PMI、经济日历
"""
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from fastapi import APIRouter, Query
from typing import Optional, List
from app.utils.response import success_response, error_response, ErrorCode
from app.config.timeout import MACRO_TIMEOUT

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/macro", tags=["macro"])

# ── 线程池执行器（用于并行化 akshare 同步调用）────────────────────
_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="macro_")

# ── 延迟导入工具 ─────────────────────────────────────────────────────
_akshare_module = None
_pandas_module = None

def _get_ak():
    """延迟加载akshare"""
    global _akshare_module
    if _akshare_module is None:
        import akshare as ak
        _akshare_module = ak
    return _akshare_module

def _get_pd():
    """延迟加载pandas"""
    global _pandas_module
    if _pandas_module is None:
        import pandas as pd
        _pandas_module = pd
    return _pandas_module

def _safe_float(val):
    """安全地将值转为float，处理None/NaN"""
    if val is None:
        return None
    pd = _get_pd()
    try:
        if pd.isna(val):
            return None
        return float(val)
    except (TypeError, ValueError):
        return None

def _safe_strftime(val, fmt='%Y年%m月份'):
    """安全地格式化日期"""
    if val is None:
        return None
    pd = _get_pd()
    try:
        if pd.isna(val):
            return None
        return val.strftime(fmt)
    except (AttributeError, TypeError):
        return str(val) if val else None

# ── 线程安全内存缓存（带过期清理）────────────────────────────────────────
import asyncio

_cache = {}
_cache_ttl = {}
_cache_lock = asyncio.Lock()
CACHE_DURATION = 300  # 5分钟缓存
MAX_CACHE_SIZE = 50   # 最大缓存条目数

async def _cleanup_expired():
    """清理过期缓存（需在锁内调用）"""
    now = datetime.now()
    expired = [k for k, v in _cache_ttl.items() if now >= v]
    for k in expired:
        _cache.pop(k, None)
        _cache_ttl.pop(k, None)
    if expired:
        logger.info(f"[Cache CLEANUP] 清理 {len(expired)} 条过期缓存")

async def get_cached(key, allow_stale=False):
    async with _cache_lock:
        await _cleanup_expired()
        if key in _cache and key in _cache_ttl:
            if allow_stale:
                return _cache[key]
            if datetime.now() < _cache_ttl[key]:
                logger.info(f"[Cache HIT] {key}")
                return _cache[key]
    logger.info(f"[Cache MISS] {key}")
    return None

async def set_cached(key, value):
    async with _cache_lock:
        await _cleanup_expired()
        if len(_cache) >= MAX_CACHE_SIZE and key not in _cache:
            oldest_key = min(_cache_ttl, key=_cache_ttl.get)
            _cache.pop(oldest_key, None)
            _cache_ttl.pop(oldest_key, None)
            logger.info(f"[Cache EVICT] 移除最旧缓存: {oldest_key}")
        
        _cache[key] = value
        _cache_ttl[key] = datetime.now() + timedelta(seconds=CACHE_DURATION)
        logger.info(f"[Cache SET] {key}, expires at {_cache_ttl[key]}")

# ── GDP数据 ────────────────────────────────────────────────────────
@router.get("/gdp")
async def get_gdp_data(
    limit: int = Query(20, ge=1, le=100, description="返回最近N个季度，范围1-100")
):
    """
    获取中国GDP数据
    
    - **limit**: 返回最近N个季度（默认20，即5年）
    """
    cache_key = f"macro_gdp_{limit}"
    cached = await get_cached(cache_key)
    if cached:
        return cached
    
    try:
        loop = asyncio.get_running_loop()
        df = await asyncio.wait_for(
            loop.run_in_executor(_executor, lambda: _get_ak().macro_china_gdp()),
            timeout=MACRO_TIMEOUT
        )
        df = df.head(limit) if len(df) > limit else df
        
        data = (
            df[['季度', '国内生产总值-绝对值', '国内生产总值-同比增长',
                '第一产业-同比增长', '第二产业-同比增长', '第三产业-同比增长']]
            .assign(
                gdp_absolute=lambda x: x['国内生产总值-绝对值'].apply(_safe_float),
                gdp_yoy=lambda x: x['国内生产总值-同比增长'].apply(_safe_float),
                primary_yoy=lambda x: x['第一产业-同比增长'].apply(_safe_float),
                secondary_yoy=lambda x: x['第二产业-同比增长'].apply(_safe_float),
                tertiary_yoy=lambda x: x['第三产业-同比增长'].apply(_safe_float),
            )
            .rename(columns={'季度': 'quarter'})
            [['quarter', 'gdp_absolute', 'gdp_yoy', 'primary_yoy', 'secondary_yoy', 'tertiary_yoy']]
            .to_dict('records')
        )
        
        result = success_response({
            "indicator": "GDP",
            "name": "国内生产总值",
            "unit": "亿元",
            "frequency": "季度",
            "data": data,
            "last_update": datetime.now().isoformat()
        })
        await set_cached(cache_key, result)
        return result
    except asyncio.TimeoutError:
        logger.warning(f"[Macro] GDP fetch timeout after {MACRO_TIMEOUT}s")
        stale_cached = await get_cached(cache_key, allow_stale=True)
        if stale_cached:
            return stale_cached
        return error_response("GDP数据获取超时，请稍后重试", code=ErrorCode.TIMEOUT_ERROR)
    except Exception as e:
        logger.error(f"[Macro] GDP fetch error: {e}")
        return error_response("GDP数据获取失败，请稍后重试")

# ── CPI数据 ────────────────────────────────────────────────────────
@router.get("/cpi")
async def get_cpi_data(limit: int = 24):
    """
    获取中国CPI数据
    
    - **limit**: 返回最近N个月（默认24，即2年）
    """
    cache_key = f"macro_cpi_{limit}"
    cached = await get_cached(cache_key)
    if cached:
        return cached
    
    try:
        loop = asyncio.get_running_loop()
        df = await asyncio.wait_for(
            loop.run_in_executor(_executor, lambda: _get_ak().macro_china_cpi()),
            timeout=MACRO_TIMEOUT
        )
        df = df.head(limit) if len(df) > limit else df
        
        data = (
            df[['月份', '全国-当月', '全国-同比增长', '全国-环比增长', '城市-同比增长', '农村-同比增长']]
            .assign(
                nation_current=lambda x: x['全国-当月'].apply(_safe_float),
                nation_yoy=lambda x: x['全国-同比增长'].apply(_safe_float),
                nation_mom=lambda x: x['全国-环比增长'].apply(_safe_float),
                city_yoy=lambda x: x['城市-同比增长'].apply(_safe_float),
                rural_yoy=lambda x: x['农村-同比增长'].apply(_safe_float),
            )
            .rename(columns={'月份': 'month'})
            [['month', 'nation_current', 'nation_yoy', 'nation_mom', 'city_yoy', 'rural_yoy']]
            .to_dict('records')
        )
        
        result = success_response({
            "indicator": "CPI",
            "name": "居民消费价格指数",
            "unit": "",
            "frequency": "月度",
            "data": data,
            "last_update": datetime.now().isoformat()
        })
        await set_cached(cache_key, result)
        return result
    except asyncio.TimeoutError:
        logger.warning(f"[Macro] CPI fetch timeout after {MACRO_TIMEOUT}s")
        stale_cached = await get_cached(cache_key, allow_stale=True)
        if stale_cached:
            return stale_cached
        return error_response("CPI数据获取超时，请稍后重试", code=ErrorCode.TIMEOUT_ERROR)
    except Exception as e:
        logger.error(f"[Macro] CPI fetch error: {e}")
        return error_response("CPI数据获取失败，请稍后重试")

# ── PPI数据 ────────────────────────────────────────────────────────
@router.get("/ppi")
async def get_ppi_data(limit: int = 24):
    """
    获取中国PPI数据
    
    - **limit**: 返回最近N个月（默认24，即2年）
    """
    cache_key = f"macro_ppi_{limit}"
    cached = await get_cached(cache_key)
    if cached:
        return cached
    
    try:
        loop = asyncio.get_running_loop()
        df = await asyncio.wait_for(
            loop.run_in_executor(_executor, lambda: _get_ak().macro_china_ppi()),
            timeout=MACRO_TIMEOUT
        )
        df = df.head(limit) if len(df) > limit else df
        
        data = (
            df[['月份', '当月', '当月同比增长', '累计']]
            .assign(
                current=lambda x: x['当月'].apply(_safe_float),
                yoy=lambda x: x['当月同比增长'].apply(_safe_float),
                cumulative=lambda x: x['累计'].apply(_safe_float),
            )
            .rename(columns={'月份': 'month'})
            [['month', 'current', 'yoy', 'cumulative']]
            .to_dict('records')
        )
        
        result = success_response({
            "indicator": "PPI",
            "name": "工业生产者出厂价格指数",
            "unit": "",
            "frequency": "月度",
            "data": data,
            "last_update": datetime.now().isoformat()
        })
        await set_cached(cache_key, result)
        return result
    except asyncio.TimeoutError:
        logger.warning(f"[Macro] PPI fetch timeout after {MACRO_TIMEOUT}s")
        stale_cached = await get_cached(cache_key, allow_stale=True)
        if stale_cached:
            return stale_cached
        return error_response("PPI数据获取超时，请稍后重试", code=ErrorCode.TIMEOUT_ERROR)
    except Exception as e:
        logger.error(f"[Macro] PPI fetch error: {e}")
        return error_response("PPI数据获取失败，请稍后重试")

# ── PMI数据 ────────────────────────────────────────────────────────
@router.get("/pmi")
async def get_pmi_data(limit: int = 24):
    """
    获取中国PMI数据
    
    - **limit**: 返回最近N个月（默认24，即2年）
    """
    cache_key = f"macro_pmi_{limit}"
    cached = await get_cached(cache_key)
    if cached:
        return cached
    
    try:
        loop = asyncio.get_running_loop()
        df = await asyncio.wait_for(
            loop.run_in_executor(_executor, lambda: _get_ak().macro_china_pmi()),
            timeout=MACRO_TIMEOUT
        )
        df = df.head(limit) if len(df) > limit else df
        
        data = (
            df[['月份', '制造业-指数', '制造业-同比增长', '非制造业-指数', '非制造业-同比增长']]
            .assign(
                manufacturing_index=lambda x: x['制造业-指数'].apply(_safe_float),
                manufacturing_yoy=lambda x: x['制造业-同比增长'].apply(_safe_float),
                non_manufacturing_index=lambda x: x['非制造业-指数'].apply(_safe_float),
                non_manufacturing_yoy=lambda x: x['非制造业-同比增长'].apply(_safe_float),
            )
            .rename(columns={'月份': 'month'})
            [['month', 'manufacturing_index', 'manufacturing_yoy', 'non_manufacturing_index', 'non_manufacturing_yoy']]
            .to_dict('records')
        )
        
        result = success_response({
            "indicator": "PMI",
            "name": "采购经理指数",
            "unit": "",
            "frequency": "月度",
            "data": data,
            "last_update": datetime.now().isoformat()
        })
        await set_cached(cache_key, result)
        return result
    except asyncio.TimeoutError:
        logger.warning(f"[Macro] PMI fetch timeout after {MACRO_TIMEOUT}s")
        stale_cached = await get_cached(cache_key, allow_stale=True)
        if stale_cached:
            return stale_cached
        return error_response("PMI数据获取超时，请稍后重试", code=ErrorCode.TIMEOUT_ERROR)
    except Exception as e:
        logger.error(f"[Macro] PMI fetch error: {e}")
        return error_response("PMI数据获取失败，请稍后重试")

# ── 综合宏观经济指标 ────────────────────────────────────────────────
@router.get("/overview")
async def get_macro_overview():
    """
    获取宏观经济综合概览（最新一期各指标）
    优化：使用线程池并行获取8个指标，将串行耗时降至并行耗时
    """
    cached = await get_cached("macro_overview")
    if cached:
        return cached
    
    FETCH_TIMEOUT = 30  # 30秒超时
    
    try:
        loop = asyncio.get_event_loop()
        
        async def fetch_with_timeout(coro, name):
            try:
                return await asyncio.wait_for(coro, timeout=FETCH_TIMEOUT)
            except asyncio.TimeoutError:
                logger.warning(f"[Macro] {name} fetch timeout after {FETCH_TIMEOUT}s")
                return None
        
        async def fetch_gdp():
            return await fetch_with_timeout(
                loop.run_in_executor(_executor, lambda: _get_ak().macro_china_gdp()),
                "GDP"
            )
        
        async def fetch_cpi():
            return await fetch_with_timeout(
                loop.run_in_executor(_executor, lambda: _get_ak().macro_china_cpi()),
                "CPI"
            )
        
        async def fetch_ppi():
            return await fetch_with_timeout(
                loop.run_in_executor(_executor, lambda: _get_ak().macro_china_ppi()),
                "PPI"
            )
        
        async def fetch_pmi():
            return await fetch_with_timeout(
                loop.run_in_executor(_executor, lambda: _get_ak().macro_china_pmi()),
                "PMI"
            )
        
        async def fetch_m2():
            return await fetch_with_timeout(
                loop.run_in_executor(_executor, lambda: _get_ak().macro_china_supply_of_money()),
                "M2"
            )
        
        async def fetch_sf():
            return await fetch_with_timeout(
                loop.run_in_executor(_executor, lambda: _get_ak().macro_china_shrzgm()),
                "SocialFinancing"
            )
        
        async def fetch_ind():
            return await fetch_with_timeout(
                loop.run_in_executor(_executor, lambda: _get_ak().macro_china_industrial_production_yoy()),
                "IndustrialProduction"
            )
        
        async def fetch_unemp():
            return await fetch_with_timeout(
                loop.run_in_executor(_executor, lambda: _get_ak().macro_china_urban_unemployment()),
                "Unemployment"
            )
        
        gdp_df, cpi_df, ppi_df, pmi_df, m2_df, sf_df, ind_df, unemp_df = await asyncio.gather(
            fetch_gdp(),
            fetch_cpi(),
            fetch_ppi(),
            fetch_pmi(),
            fetch_m2(),
            fetch_sf(),
            fetch_ind(),
            fetch_unemp()
        )
        
        gdp_latest = gdp_df.iloc[0] if len(gdp_df) > 0 else None
        cpi_latest = cpi_df.iloc[0] if len(cpi_df) > 0 else None
        ppi_latest = ppi_df.iloc[0] if len(ppi_df) > 0 else None
        pmi_latest = pmi_df.iloc[0] if len(pmi_df) > 0 else None
        m2_latest = m2_df.iloc[0] if len(m2_df) > 0 else None
        sf_latest = sf_df.iloc[-1] if len(sf_df) > 0 else None
        
        ind_df_valid = ind_df[_get_pd().notna(ind_df['今值'])] if len(ind_df) > 0 else None
        ind_latest = ind_df_valid.iloc[-1] if ind_df_valid is not None and len(ind_df_valid) > 0 else None
        
        unemp_df_filtered = unemp_df[unemp_df['item'].str.strip() == '全国城镇调查失业率'] if len(unemp_df) > 0 else None
        unemp_latest = unemp_df_filtered.iloc[-1] if unemp_df_filtered is not None and len(unemp_df_filtered) > 0 else None
        
        overview = {
            "gdp": {
                "period": gdp_latest["季度"] if gdp_latest is not None else None,
                "value": float(gdp_latest["国内生产总值-绝对值"]) if gdp_latest is not None and not _get_pd().isna(gdp_latest["国内生产总值-绝对值"]) else None,
                "yoy": float(gdp_latest["国内生产总值-同比增长"]) if gdp_latest is not None and not _get_pd().isna(gdp_latest["国内生产总值-同比增长"]) else None,
                "unit": "亿元"
            },
            "cpi": {
                "period": cpi_latest["月份"] if cpi_latest is not None else None,
                "value": float(cpi_latest["全国-当月"]) if cpi_latest is not None and not _get_pd().isna(cpi_latest["全国-当月"]) else None,
                "yoy": float(cpi_latest["全国-同比增长"]) if cpi_latest is not None and not _get_pd().isna(cpi_latest["全国-同比增长"]) else None,
                "mom": float(cpi_latest["全国-环比增长"]) if cpi_latest is not None and not _get_pd().isna(cpi_latest["全国-环比增长"]) else None,
            },
            "ppi": {
                "period": ppi_latest["月份"] if ppi_latest is not None else None,
                "value": float(ppi_latest["当月"]) if ppi_latest is not None and not _get_pd().isna(ppi_latest["当月"]) else None,
                "yoy": float(ppi_latest["当月同比增长"]) if ppi_latest is not None and not _get_pd().isna(ppi_latest["当月同比增长"]) else None,
            },
            "pmi": {
                "period": pmi_latest["月份"] if pmi_latest is not None else None,
                "manufacturing": float(pmi_latest["制造业-指数"]) if pmi_latest is not None and not _get_pd().isna(pmi_latest["制造业-指数"]) else None,
                "non_manufacturing": float(pmi_latest["非制造业-指数"]) if pmi_latest is not None and not _get_pd().isna(pmi_latest["非制造业-指数"]) else None,
            },
            "m2": {
                "period": m2_latest["统计时间"] if m2_latest is not None else None,
                "value": float(m2_latest["货币和准货币（广义货币M2）"]) if m2_latest is not None and not _get_pd().isna(m2_latest["货币和准货币（广义货币M2）"]) else None,
                "yoy": float(m2_latest["货币和准货币（广义货币M2）同比增长"]) if m2_latest is not None and not _get_pd().isna(m2_latest["货币和准货币（广义货币M2）同比增长"]) else None,
                "unit": "亿元"
            },
            "social_financing": {
                "period": sf_latest["月份"] if sf_latest is not None else None,
                "total": float(sf_latest["社会融资规模增量"]) if sf_latest is not None and not _get_pd().isna(sf_latest["社会融资规模增量"]) else None,
                "yoy": None,  # akshare数据中没有同比增长
                "unit": "亿元"
            },
            "industrial_production": {
                "period": ind_latest["日期"].strftime('%Y年%m月份') if ind_latest is not None and not _get_pd().isna(ind_latest["日期"]) else None,
                "yoy": float(ind_latest["今值"]) if ind_latest is not None and not _get_pd().isna(ind_latest["今值"]) else None,
                "unit": "%"
            },
            "unemployment": {
                "period": unemp_latest["date"] if unemp_latest is not None else None,
                "rate": float(unemp_latest["value"]) if unemp_latest is not None and not _get_pd().isna(unemp_latest["value"]) else None,
                "unit": "%"
            }
        }
        
        result = success_response({
            "overview": overview,
            "last_update": datetime.now().isoformat()
        })
        
        # 缓存结果
        await set_cached("macro_overview", result)
        return result
    except Exception as e:
        logger.error(f"[Macro] Overview fetch error: {e}")
        return error_response("宏观概览获取失败，请稍后重试")

# ── 经济日历 ────────────────────────────────────────────────────────
@router.get("/calendar")
async def get_economic_calendar():
    """
    获取中国宏观经济数据发布日历（近期重要数据预告）
    """
    cache_key = "macro_calendar"
    cached = await get_cached(cache_key)
    if cached:
        return cached
    
    try:
        loop = asyncio.get_running_loop()
        calendar_items = []
        
        async def fetch_gdp():
            return await asyncio.wait_for(
                loop.run_in_executor(_executor, lambda: _get_ak().macro_china_gdp()),
                timeout=MACRO_TIMEOUT
            )
        
        async def fetch_cpi():
            return await asyncio.wait_for(
                loop.run_in_executor(_executor, lambda: _get_ak().macro_china_cpi()),
                timeout=MACRO_TIMEOUT
            )
        
        async def fetch_pmi():
            return await asyncio.wait_for(
                loop.run_in_executor(_executor, lambda: _get_ak().macro_china_pmi()),
                timeout=MACRO_TIMEOUT
            )
        
        gdp_df, cpi_df, pmi_df = await asyncio.gather(
            fetch_gdp(),
            fetch_cpi(),
            fetch_pmi()
        )
        
        if len(gdp_df) > 0:
            latest = gdp_df.iloc[0]
            calendar_items.append({
                "date": latest["季度"],
                "indicator": "GDP",
                "name": "国内生产总值",
                "status": "released",
                "value": _safe_float(latest["国内生产总值-同比增长"]),
                "unit": "%"
            })
        
        if len(cpi_df) > 0:
            latest = cpi_df.iloc[0]
            calendar_items.append({
                "date": latest["月份"],
                "indicator": "CPI",
                "name": "居民消费价格指数",
                "status": "released",
                "value": _safe_float(latest["全国-同比增长"]),
                "unit": "%"
            })
        
        if len(pmi_df) > 0:
            latest = pmi_df.iloc[0]
            calendar_items.append({
                "date": latest["月份"],
                "indicator": "PMI",
                "name": "采购经理指数",
                "status": "released",
                "value": _safe_float(latest["制造业-指数"]),
                "unit": ""
            })
        
        result = success_response({
            "calendar": calendar_items,
            "last_update": datetime.now().isoformat()
        })
        await set_cached(cache_key, result)
        return result
    except asyncio.TimeoutError:
        logger.warning(f"[Macro] Calendar fetch timeout after {MACRO_TIMEOUT}s")
        stale_cached = await get_cached(cache_key, allow_stale=True)
        if stale_cached:
            return stale_cached
        return error_response("经济日历获取超时，请稍后重试", code=ErrorCode.TIMEOUT_ERROR)
    except Exception as e:
        logger.error(f"[Macro] Calendar fetch error: {e}")
        return error_response("经济日历获取失败，请稍后重试")

# ── M2货币供应量 ───────────────────────────────────────────────────
@router.get("/m2")
async def get_m2_data(limit: int = 24):
    """
    获取中国M2货币供应量数据
    
    - **limit**: 返回最近N个月（默认24，即2年）
    """
    cache_key = f"macro_m2_{limit}"
    cached = await get_cached(cache_key)
    if cached:
        return cached
    
    try:
        loop = asyncio.get_running_loop()
        df = await asyncio.wait_for(
            loop.run_in_executor(_executor, lambda: _get_ak().macro_china_supply_of_money()),
            timeout=MACRO_TIMEOUT
        )
        df = df.head(limit) if len(df) > limit else df
        
        data = (
            df[['统计时间', '货币和准货币（广义货币M2）同比增长', '货币和准货币（广义货币M2）']]
            .assign(
                m2_yoy=lambda x: x['货币和准货币（广义货币M2）同比增长'].apply(_safe_float),
                m2_amount=lambda x: x['货币和准货币（广义货币M2）'].apply(_safe_float),
            )
            .rename(columns={'统计时间': 'month'})
            [['month', 'm2_yoy', 'm2_amount']]
            .to_dict('records')
        )
        
        result = success_response({
            "indicator": "M2",
            "name": "广义货币供应量",
            "unit": "%",
            "frequency": "月度",
            "data": data,
            "last_update": datetime.now().isoformat()
        })
        
        await set_cached(cache_key, result)
        return result
    except asyncio.TimeoutError:
        logger.warning(f"[Macro] M2 fetch timeout after {MACRO_TIMEOUT}s")
        stale_cached = await get_cached(cache_key, allow_stale=True)
        if stale_cached:
            return stale_cached
        return error_response("M2数据获取超时，请稍后重试", code=ErrorCode.TIMEOUT_ERROR)
    except Exception as e:
        logger.error(f"[Macro] M2 fetch error: {e}")
        return error_response("M2数据获取失败，请稍后重试")

# ── 社会融资规模 ───────────────────────────────────────────────────
@router.get("/social_financing")
async def get_social_financing_data(limit: int = 24):
    """
    获取中国社会融资规模数据
    
    - **limit**: 返回最近N个月（默认24，即2年）
    """
    cache_key = f"macro_social_financing_{limit}"
    cached = await get_cached(cache_key)
    if cached:
        return cached
    
    try:
        loop = asyncio.get_running_loop()
        df = await asyncio.wait_for(
            loop.run_in_executor(_executor, lambda: _get_ak().macro_china_shrzgm()),
            timeout=MACRO_TIMEOUT
        )
        df = df.tail(limit) if len(df) > limit else df
        
        data = (
            df[['月份', '社会融资规模增量', '其中-人民币贷款']]
            .assign(
                total=lambda x: x['社会融资规模增量'].apply(_safe_float),
                rmb_loan=lambda x: x['其中-人民币贷款'].apply(_safe_float),
            )
            .rename(columns={'月份': 'month'})
            [['month', 'total', 'rmb_loan']]
            .to_dict('records')
        )
        
        result = success_response({
            "indicator": "SocialFinancing",
            "name": "社会融资规模",
            "unit": "亿元",
            "frequency": "月度",
            "data": data,
            "last_update": datetime.now().isoformat()
        })
        
        await set_cached(cache_key, result)
        return result
    except asyncio.TimeoutError:
        logger.warning(f"[Macro] Social financing fetch timeout after {MACRO_TIMEOUT}s")
        stale_cached = await get_cached(cache_key, allow_stale=True)
        if stale_cached:
            return stale_cached
        return error_response("社融数据获取超时，请稍后重试", code=ErrorCode.TIMEOUT_ERROR)
    except Exception as e:
        logger.error(f"[Macro] Social financing fetch error: {e}")
        return error_response("社融数据获取失败，请稍后重试")

# ── 工业增加值 ─────────────────────────────────────────────────────
@router.get("/industrial_production")
async def get_industrial_production_data(limit: int = 24):
    """
    获取中国工业增加值数据
    
    - **limit**: 返回最近N个月（默认24，即2年）
    """
    cache_key = f"macro_industrial_production_{limit}"
    cached = await get_cached(cache_key)
    if cached:
        return cached
    
    try:
        loop = asyncio.get_running_loop()
        df = await asyncio.wait_for(
            loop.run_in_executor(_executor, lambda: _get_ak().macro_china_industrial_production_yoy()),
            timeout=MACRO_TIMEOUT
        )
        df = df[_get_pd().notna(df['今值'])]
        df = df.tail(limit) if len(df) > limit else df
        
        df_work = df[['日期', '今值', '前值']].copy()
        df_work['month'] = df_work['日期'].apply(lambda x: _safe_strftime(x, '%Y-%m'))
        df_work['yoy'] = df_work['今值'].apply(_safe_float)
        df_work['previous'] = df_work['前值'].apply(_safe_float)
        data = df_work[['month', 'yoy', 'previous']].to_dict('records')
        
        result = success_response({
            "indicator": "IndustrialProduction",
            "name": "工业增加值",
            "unit": "%",
            "frequency": "月度",
            "data": data,
            "last_update": datetime.now().isoformat()
        })
        
        await set_cached(cache_key, result)
        return result
    except asyncio.TimeoutError:
        logger.warning(f"[Macro] Industrial production fetch timeout after {MACRO_TIMEOUT}s")
        stale_cached = await get_cached(cache_key, allow_stale=True)
        if stale_cached:
            return stale_cached
        return error_response("工业增加值数据获取超时，请稍后重试", code=ErrorCode.TIMEOUT_ERROR)
    except Exception as e:
        logger.error(f"[Macro] Industrial production fetch error: {e}")
        return error_response("工业增加值数据获取失败，请稍后重试")

# ── 失业率 ─────────────────────────────────────────────────────────
@router.get("/unemployment")
async def get_unemployment_data(limit: int = 24):
    """
    获取中国城镇调查失业率数据
    
    - **limit**: 返回最近N个月（默认24，即2年）
    """
    cache_key = f"macro_unemployment_{limit}"
    cached = await get_cached(cache_key)
    if cached:
        return cached
    
    try:
        loop = asyncio.get_running_loop()
        df = await asyncio.wait_for(
            loop.run_in_executor(_executor, lambda: _get_ak().macro_china_urban_unemployment()),
            timeout=MACRO_TIMEOUT
        )
        df = df[df['item'].str.strip() == '全国城镇调查失业率']
        df = df.tail(limit) if len(df) > limit else df
        
        data = (
            df[['date', 'value']]
            .assign(
                month=lambda x: x['date'],
                rate=lambda x: x['value'].apply(_safe_float),
            )
            [['month', 'rate']]
            .to_dict('records')
        )
        
        result = success_response({
            "indicator": "Unemployment",
            "name": "城镇调查失业率",
            "unit": "%",
            "frequency": "月度",
            "data": data,
            "last_update": datetime.now().isoformat()
        })
        
        await set_cached(cache_key, result)
        return result
    except asyncio.TimeoutError:
        logger.warning(f"[Macro] Unemployment fetch timeout after {MACRO_TIMEOUT}s")
        stale_cached = await get_cached(cache_key, allow_stale=True)
        if stale_cached:
            return stale_cached
        return error_response("失业率数据获取超时，请稍后重试", code=ErrorCode.TIMEOUT_ERROR)
    except Exception as e:
        logger.error(f"[Macro] Unemployment fetch error: {e}")
        return error_response("失业率数据获取失败，请稍后重试")

# ── 批量获取 ────────────────────────────────────────────────────────
VALID_INDICATORS = {"gdp", "cpi", "ppi", "pmi", "m2", "social_financing", "industrial_production", "unemployment"}

@router.get("/batch")
async def get_macro_batch(
    indicators: str = "gdp,cpi,ppi,pmi",
    limit: int = Query(12, ge=1, le=100, description="每个指标返回最近N期数据，范围1-100")
):
    """
    批量获取宏观经济指标
    
    - **indicators**: 逗号分隔的指标代码（gdp,cpi,ppi,pmi,m2,social_financing,industrial_production,unemployment）
    - **limit**: 每个指标返回最近N期数据
    """
    try:
        indicator_list = [i.strip().lower() for i in indicators.split(",")]
        invalid = set(indicator_list) - VALID_INDICATORS
        if invalid:
            return error_response(
                f"无效的指标: {', '.join(invalid)}. 有效指标: {', '.join(VALID_INDICATORS)}",
                code=ErrorCode.VALIDATION_ERROR
            )
        
        result = {}
        
        if "gdp" in indicator_list:
            df = _get_ak().macro_china_gdp().tail(limit)
            df_work = df[['季度', '国内生产总值-同比增长']].copy()
            df_work['quarter'] = df_work['季度']
            df_work['yoy'] = df_work['国内生产总值-同比增长'].apply(_safe_float)
            result["gdp"] = {
                "data": df_work[['quarter', 'yoy']].to_dict('records'),
                "unit": "%",
                "frequency": "季度"
            }
        
        if "cpi" in indicator_list:
            df = _get_ak().macro_china_cpi().tail(limit)
            df_work = df[['月份', '全国-同比增长']].copy()
            df_work['month'] = df_work['月份']
            df_work['yoy'] = df_work['全国-同比增长'].apply(_safe_float)
            result["cpi"] = {
                "data": df_work[['month', 'yoy']].to_dict('records'),
                "unit": "%",
                "frequency": "月度"
            }
        
        if "ppi" in indicator_list:
            df = _get_ak().macro_china_ppi().tail(limit)
            df_work = df[['月份', '当月同比增长']].copy()
            df_work['month'] = df_work['月份']
            df_work['yoy'] = df_work['当月同比增长'].apply(_safe_float)
            result["ppi"] = {
                "data": df_work[['month', 'yoy']].to_dict('records'),
                "unit": "%",
                "frequency": "月度"
            }
        
        if "pmi" in indicator_list:
            df = _get_ak().macro_china_pmi().tail(limit)
            df_work = df[['月份', '制造业-指数']].copy()
            df_work['month'] = df_work['月份']
            df_work['index'] = df_work['制造业-指数'].apply(_safe_float)
            result["pmi"] = {
                "data": df_work[['month', 'index']].to_dict('records'),
                "unit": "",
                "frequency": "月度"
            }
        
        if "m2" in indicator_list:
            df = _get_ak().macro_china_m2_yearly().tail(limit)
            df_work = df[['月份', 'M2-同比增长']].copy()
            df_work['month'] = df_work['月份']
            df_work['yoy'] = df_work['M2-同比增长'].apply(_safe_float)
            result["m2"] = {
                "data": df_work[['month', 'yoy']].to_dict('records'),
                "unit": "%",
                "frequency": "月度"
            }
        
        if "social_financing" in indicator_list:
            df = _get_ak().macro_china_bank_financing().tail(limit)
            df_work = df[['月份', '社会融资规模增量']].copy()
            df_work['month'] = df_work['月份']
            df_work['total'] = df_work['社会融资规模增量'].apply(_safe_float)
            result["social_financing"] = {
                "data": df_work[['month', 'total']].to_dict('records'),
                "unit": "亿元",
                "frequency": "月度"
            }
        
        if "industrial_production" in indicator_list:
            df = _get_ak().macro_china_gyzjz().tail(limit)
            df_work = df[['月份', '同比增长']].copy()
            df_work['month'] = df_work['月份']
            df_work['yoy'] = df_work['同比增长'].apply(_safe_float)
            result["industrial_production"] = {
                "data": df_work[['month', 'yoy']].to_dict('records'),
                "unit": "%",
                "frequency": "月度"
            }
        
        if "unemployment" in indicator_list:
            df = _get_ak().macro_china_urban_unemployment().tail(limit)
            df_work = df[['月份', '失业率']].copy()
            df_work['month'] = df_work['月份']
            df_work['rate'] = df_work['失业率'].apply(_safe_float)
            result["unemployment"] = {
                "data": df_work[['month', 'rate']].to_dict('records'),
                "unit": "%",
                "frequency": "月度"
            }
        
        return success_response({
            "indicators": result,
            "last_update": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"[Macro] Batch fetch error: {e}")
        return error_response("批量获取失败，请稍后重试")
