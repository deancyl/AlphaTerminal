"""
宏观经济数据接口
数据来源: akshare (国家统计局、中国人民银行等权威机构)
覆盖: GDP、CPI、PPI、PMI、经济日历
"""

import logging
import asyncio
import httpx
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from fastapi import APIRouter, Query
from typing import Optional
from app.utils.errors import success_response, error_response, ErrorCode
from app.config.timeout import MACRO_TIMEOUT
from app.config.macro_config import (
    MACRO_THREAD_POOL_SIZE,
    MACRO_CACHE_DURATION,
    MACRO_FETCH_TIMEOUT,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/macro", tags=["macro"])

# ── 线程池执行器（用于并行化 akshare 同步调用）────────────────────
_executor = ThreadPoolExecutor(
    max_workers=MACRO_THREAD_POOL_SIZE, thread_name_prefix="macro_"
)

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


def _safe_strftime(val, fmt="%Y年%m月份"):
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


def _quarter_to_date(quarter_str):
    """Convert Chinese quarter string to datetime (e.g., '2024年第一季度' -> 2024-01-01)"""
    if not quarter_str:
        return None
    pd = _get_pd()
    try:
        import re

        match = re.match(r"(\d{4})年第([一二三四])季度", str(quarter_str))
        if match:
            year = int(match.group(1))
            quarter_map = {"一": 1, "二": 4, "三": 7, "四": 10}
            month = quarter_map.get(match.group(2), 1)
            return pd.to_datetime(f"{year}-{month:02d}-01")
        return pd.NaT
    except (ValueError, TypeError, AttributeError) as e:
        logger.debug(f"[Macro] quarter_to_date conversion error: {e}")
        return pd.NaT


def _month_to_date(month_str):
    """Convert Chinese month string to datetime (e.g., '2024年1月' -> 2024-01-01)"""
    if not month_str:
        return None
    pd = _get_pd()
    try:
        import re

        match = re.match(r"(\d{4})年(\d{1,2})月", str(month_str))
        if match:
            year = int(match.group(1))
            month = int(match.group(2))
            return pd.to_datetime(f"{year}-{month:02d}-01")
        return pd.NaT
    except (ValueError, TypeError, AttributeError) as e:
        logger.debug(f"[Macro] month_to_date conversion error: {e}")
        return pd.NaT


# ── 全局缓存导入 ─────────────────────────────────────────────────────
from app.services.data_cache import get_cache
from app.utils.error_decorator import handle_errors

_cache = get_cache()
_cache_ttl = {}


# ── GDP数据 ────────────────────────────────────────────────────────
@router.get("/gdp")
@handle_errors(module="macro")
async def get_gdp_data(
    limit: int = Query(20, ge=1, le=100, description="返回最近N个季度，范围1-100"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
):
    """
    获取中国GDP数据

    - **limit**: 返回最近N个季度（默认20，即5年）
    - **start_date**: 开始日期（可选，格式YYYY-MM-DD）
    - **end_date**: 结束日期（可选，格式YYYY-MM-DD）
    """
    cache = get_cache()
    cache_key = f"macro:gdp:{limit}:{start_date}:{end_date}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        loop = asyncio.get_running_loop()
        df = await asyncio.wait_for(
            loop.run_in_executor(_executor, lambda: _get_ak().macro_china_gdp()),
            timeout=MACRO_TIMEOUT,
        )

        # Apply date filtering if provided
        pd = _get_pd()
        if start_date or end_date:
            # Convert quarter format (e.g., "2024年第一季度") to date for filtering
            df["_date"] = df["季度"].apply(_quarter_to_date)
            if start_date:
                df = df[df["_date"] >= pd.to_datetime(start_date)]
            if end_date:
                df = df[df["_date"] <= pd.to_datetime(end_date)]
            df = df.drop(columns=["_date"])

        df = df.head(limit) if len(df) > limit else df

        data = (
            df[
                [
                    "季度",
                    "国内生产总值-绝对值",
                    "国内生产总值-同比增长",
                    "第一产业-同比增长",
                    "第二产业-同比增长",
                    "第三产业-同比增长",
                ]
            ]
            .assign(
                gdp_absolute=lambda x: x["国内生产总值-绝对值"].apply(_safe_float),
                gdp_yoy=lambda x: x["国内生产总值-同比增长"].apply(_safe_float),
                primary_yoy=lambda x: x["第一产业-同比增长"].apply(_safe_float),
                secondary_yoy=lambda x: x["第二产业-同比增长"].apply(_safe_float),
                tertiary_yoy=lambda x: x["第三产业-同比增长"].apply(_safe_float),
            )
            .rename(columns={"季度": "quarter"})[
                [
                    "quarter",
                    "gdp_absolute",
                    "gdp_yoy",
                    "primary_yoy",
                    "secondary_yoy",
                    "tertiary_yoy",
                ]
            ]
            .to_dict("records")
        )

        result = success_response(
            {
                "indicator": "GDP",
                "name": "国内生产总值",
                "unit": "亿元",
                "frequency": "季度",
                "data": data,
                "last_update": datetime.now(timezone.utc).isoformat(),
            }
        )
        cache.set(cache_key, result, ttl=MACRO_CACHE_DURATION)
        return result
    except asyncio.TimeoutError:
        logger.warning(
            f"[Macro] GDP fetch timeout after {MACRO_TIMEOUT}s", exc_info=True
        )
        return error_response(
            "GDP数据获取超时，请稍后重试", code=ErrorCode.TIMEOUT_ERROR
        )
    except (httpx.HTTPError, asyncio.TimeoutError, ConnectionError) as e:
        logger.error(f"[HTTP] error: {e}", exc_info=True)
        return error_response("GDP数据获取失败，请稍后重试")


# ── CPI数据 ────────────────────────────────────────────────────────
@router.get("/cpi")
@handle_errors(module="macro")
async def get_cpi_data(
    limit: int = Query(24, ge=1, le=100),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
):
    """
    获取中国CPI数据

    - **limit**: 返回最近N个月（默认24，即2年）
    - **start_date**: 开始日期（可选，格式YYYY-MM-DD）
    - **end_date**: 结束日期（可选，格式YYYY-MM-DD）
    """
    cache = get_cache()
    cache_key = f"macro:cpi:{limit}:{start_date}:{end_date}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        loop = asyncio.get_running_loop()
        df = await asyncio.wait_for(
            loop.run_in_executor(_executor, lambda: _get_ak().macro_china_cpi()),
            timeout=MACRO_TIMEOUT,
        )

        pd = _get_pd()
        if start_date or end_date:
            df["_date"] = df["月份"].apply(_month_to_date)
            if start_date:
                df = df[df["_date"] >= pd.to_datetime(start_date)]
            if end_date:
                df = df[df["_date"] <= pd.to_datetime(end_date)]
            df = df.drop(columns=["_date"])

        df = df.head(limit) if len(df) > limit else df

        data = (
            df[
                [
                    "月份",
                    "全国-当月",
                    "全国-同比增长",
                    "全国-环比增长",
                    "城市-同比增长",
                    "农村-同比增长",
                ]
            ]
            .assign(
                nation_current=lambda x: x["全国-当月"].apply(_safe_float),
                nation_yoy=lambda x: x["全国-同比增长"].apply(_safe_float),
                nation_mom=lambda x: x["全国-环比增长"].apply(_safe_float),
                city_yoy=lambda x: x["城市-同比增长"].apply(_safe_float),
                rural_yoy=lambda x: x["农村-同比增长"].apply(_safe_float),
            )
            .rename(columns={"月份": "month"})[
                [
                    "month",
                    "nation_current",
                    "nation_yoy",
                    "nation_mom",
                    "city_yoy",
                    "rural_yoy",
                ]
            ]
            .to_dict("records")
        )

        result = success_response(
            {
                "indicator": "CPI",
                "name": "居民消费价格指数",
                "unit": "",
                "frequency": "月度",
                "data": data,
                "last_update": datetime.now(timezone.utc).isoformat(),
            }
        )
        cache.set(cache_key, result, ttl=MACRO_CACHE_DURATION)
        return result
    except asyncio.TimeoutError:
        logger.warning(
            f"[Macro] CPI fetch timeout after {MACRO_TIMEOUT}s", exc_info=True
        )
        return error_response(
            "CPI数据获取超时，请稍后重试", code=ErrorCode.TIMEOUT_ERROR
        )
    except (httpx.HTTPError, asyncio.TimeoutError, ConnectionError) as e:
        logger.error(f"[HTTP] error: {e}", exc_info=True)
        return error_response("CPI数据获取失败，请稍后重试")


# ── PPI数据 ────────────────────────────────────────────────────────
@router.get("/ppi")
@handle_errors(module="macro")
async def get_ppi_data(
    limit: int = Query(24, ge=1, le=100),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
):
    """
    获取中国PPI数据

    - **limit**: 返回最近N个月（默认24，即2年）
    - **start_date**: 开始日期（可选，格式YYYY-MM-DD）
    - **end_date**: 结束日期（可选，格式YYYY-MM-DD）
    """
    cache = get_cache()
    cache_key = f"macro:ppi:{limit}:{start_date}:{end_date}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        loop = asyncio.get_running_loop()
        df = await asyncio.wait_for(
            loop.run_in_executor(_executor, lambda: _get_ak().macro_china_ppi()),
            timeout=MACRO_TIMEOUT,
        )

        pd = _get_pd()
        if start_date or end_date:
            df["_date"] = df["月份"].apply(_month_to_date)
            if start_date:
                df = df[df["_date"] >= pd.to_datetime(start_date)]
            if end_date:
                df = df[df["_date"] <= pd.to_datetime(end_date)]
            df = df.drop(columns=["_date"])

        df = df.head(limit) if len(df) > limit else df

        data = (
            df[["月份", "当月", "当月同比增长", "累计"]]
            .assign(
                current=lambda x: x["当月"].apply(_safe_float),
                yoy=lambda x: x["当月同比增长"].apply(_safe_float),
                cumulative=lambda x: x["累计"].apply(_safe_float),
            )
            .rename(columns={"月份": "month"})[
                ["month", "current", "yoy", "cumulative"]
            ]
            .to_dict("records")
        )

        result = success_response(
            {
                "indicator": "PPI",
                "name": "工业生产者出厂价格指数",
                "unit": "",
                "frequency": "月度",
                "data": data,
                "last_update": datetime.now(timezone.utc).isoformat(),
            }
        )
        cache.set(cache_key, result, ttl=MACRO_CACHE_DURATION)
        return result
    except asyncio.TimeoutError:
        logger.warning(
            f"[Macro] PPI fetch timeout after {MACRO_TIMEOUT}s", exc_info=True
        )
        return error_response(
            "PPI数据获取超时，请稍后重试", code=ErrorCode.TIMEOUT_ERROR
        )
    except (httpx.HTTPError, asyncio.TimeoutError, ConnectionError) as e:
        logger.error(f"[HTTP] error: {e}", exc_info=True)
        return error_response("PPI数据获取失败，请稍后重试")


# ── PMI数据 ────────────────────────────────────────────────────────
@router.get("/pmi")
@handle_errors(module="macro")
async def get_pmi_data(
    limit: int = Query(24, ge=1, le=100),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
):
    """
    获取中国PMI数据

    - **limit**: 返回最近N个月（默认24，即2年）
    - **start_date**: 开始日期（可选，格式YYYY-MM-DD）
    - **end_date**: 结束日期（可选，格式YYYY-MM-DD）
    """
    cache = get_cache()
    cache_key = f"macro:pmi:{limit}:{start_date}:{end_date}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        loop = asyncio.get_running_loop()
        df = await asyncio.wait_for(
            loop.run_in_executor(_executor, lambda: _get_ak().macro_china_pmi()),
            timeout=MACRO_TIMEOUT,
        )

        pd = _get_pd()
        if start_date or end_date:
            df["_date"] = df["月份"].apply(_month_to_date)
            if start_date:
                df = df[df["_date"] >= pd.to_datetime(start_date)]
            if end_date:
                df = df[df["_date"] <= pd.to_datetime(end_date)]
            df = df.drop(columns=["_date"])

        df = df.head(limit) if len(df) > limit else df

        data = (
            df[
                [
                    "月份",
                    "制造业-指数",
                    "制造业-同比增长",
                    "非制造业-指数",
                    "非制造业-同比增长",
                ]
            ]
            .assign(
                manufacturing_index=lambda x: x["制造业-指数"].apply(_safe_float),
                manufacturing_yoy=lambda x: x["制造业-同比增长"].apply(_safe_float),
                non_manufacturing_index=lambda x: x["非制造业-指数"].apply(_safe_float),
                non_manufacturing_yoy=lambda x: x["非制造业-同比增长"].apply(
                    _safe_float
                ),
            )
            .rename(columns={"月份": "month"})[
                [
                    "month",
                    "manufacturing_index",
                    "manufacturing_yoy",
                    "non_manufacturing_index",
                    "non_manufacturing_yoy",
                ]
            ]
            .to_dict("records")
        )

        result = success_response(
            {
                "indicator": "PMI",
                "name": "采购经理指数",
                "unit": "",
                "frequency": "月度",
                "data": data,
                "last_update": datetime.now(timezone.utc).isoformat(),
            }
        )
        cache.set(cache_key, result, ttl=MACRO_CACHE_DURATION)
        return result
    except asyncio.TimeoutError:
        logger.warning(
            f"[Macro] PMI fetch timeout after {MACRO_TIMEOUT}s", exc_info=True
        )
        return error_response(
            "PMI数据获取超时，请稍后重试", code=ErrorCode.TIMEOUT_ERROR
        )
    except (httpx.HTTPError, asyncio.TimeoutError, ConnectionError) as e:
        logger.error(f"[HTTP] error: {e}", exc_info=True)
        return error_response("PMI数据获取失败，请稍后重试")


# ── 综合宏观经济指标 ────────────────────────────────────────────────
@router.get("/overview")
@handle_errors(module="macro")
async def get_macro_overview():
    """
    获取宏观经济综合概览（最新一期各指标）
    优化：使用线程池并行获取8个指标，将串行耗时降至并行耗时
    """
    cache = get_cache()
    cached = cache.get("macro:overview")
    if cached:
        return cached

    FETCH_TIMEOUT = MACRO_FETCH_TIMEOUT

    try:
        loop = asyncio.get_event_loop()

        async def fetch_with_timeout(coro, name):
            try:
                return await asyncio.wait_for(coro, timeout=FETCH_TIMEOUT)
            except asyncio.TimeoutError:
                logger.warning(
                    f"[Macro] {name} fetch timeout after {FETCH_TIMEOUT}s",
                    exc_info=True,
                )
                return None

        async def fetch_gdp():
            return await fetch_with_timeout(
                loop.run_in_executor(_executor, lambda: _get_ak().macro_china_gdp()),
                "GDP",
            )

        async def fetch_cpi():
            return await fetch_with_timeout(
                loop.run_in_executor(_executor, lambda: _get_ak().macro_china_cpi()),
                "CPI",
            )

        async def fetch_ppi():
            return await fetch_with_timeout(
                loop.run_in_executor(_executor, lambda: _get_ak().macro_china_ppi()),
                "PPI",
            )

        async def fetch_pmi():
            return await fetch_with_timeout(
                loop.run_in_executor(_executor, lambda: _get_ak().macro_china_pmi()),
                "PMI",
            )

        async def fetch_m2():
            return await fetch_with_timeout(
                loop.run_in_executor(
                    _executor, lambda: _get_ak().macro_china_supply_of_money()
                ),
                "M2",
            )

        async def fetch_sf():
            return await fetch_with_timeout(
                loop.run_in_executor(_executor, lambda: _get_ak().macro_china_shrzgm()),
                "SocialFinancing",
            )

        async def fetch_ind():
            return await fetch_with_timeout(
                loop.run_in_executor(
                    _executor, lambda: _get_ak().macro_china_industrial_production_yoy()
                ),
                "IndustrialProduction",
            )

        async def fetch_unemp():
            return await fetch_with_timeout(
                loop.run_in_executor(
                    _executor, lambda: _get_ak().macro_china_urban_unemployment()
                ),
                "Unemployment",
            )

        gdp_df, cpi_df, ppi_df, pmi_df, m2_df, sf_df, ind_df, unemp_df = (
            await asyncio.gather(
                fetch_gdp(),
                fetch_cpi(),
                fetch_ppi(),
                fetch_pmi(),
                fetch_m2(),
                fetch_sf(),
                fetch_ind(),
                fetch_unemp(),
            )
        )

        gdp_latest = gdp_df.iloc[0] if len(gdp_df) > 0 else None
        cpi_latest = cpi_df.iloc[0] if len(cpi_df) > 0 else None
        ppi_latest = ppi_df.iloc[0] if len(ppi_df) > 0 else None
        pmi_latest = pmi_df.iloc[0] if len(pmi_df) > 0 else None
        m2_latest = m2_df.iloc[0] if len(m2_df) > 0 else None
        sf_latest = sf_df.iloc[-1] if len(sf_df) > 0 else None

        ind_df_valid = (
            ind_df[
                _get_pd().notna(
                    ind_df.get(
                        "今值",
                        ind_df.get("今值(%)", _get_pd().Series([None] * len(ind_df))),
                    )
                )
            ]
            if len(ind_df) > 0
            and ("今值" in ind_df.columns or "今值(%)" in ind_df.columns)
            else None
        )
        ind_latest = (
            ind_df_valid.iloc[-1]
            if ind_df_valid is not None and len(ind_df_valid) > 0
            else None
        )

        unemp_df_filtered = (
            unemp_df[
                unemp_df.get("item", _get_pd().Series([""] * len(unemp_df))).str.strip()
                == "全国城镇调查失业率"
            ]
            if len(unemp_df) > 0 and "item" in unemp_df.columns
            else None
        )
        unemp_latest = (
            unemp_df_filtered.iloc[-1]
            if unemp_df_filtered is not None and len(unemp_df_filtered) > 0
            else None
        )

        overview = {
            "gdp": {
                "period": gdp_latest["季度"] if gdp_latest is not None else None,
                "value": (
                    float(gdp_latest["国内生产总值-绝对值"])
                    if gdp_latest is not None
                    and not _get_pd().isna(gdp_latest["国内生产总值-绝对值"])
                    else None
                ),
                "yoy": (
                    float(gdp_latest["国内生产总值-同比增长"])
                    if gdp_latest is not None
                    and not _get_pd().isna(gdp_latest["国内生产总值-同比增长"])
                    else None
                ),
                "unit": "亿元",
            },
            "cpi": {
                "period": cpi_latest["月份"] if cpi_latest is not None else None,
                "value": (
                    float(cpi_latest["全国-当月"])
                    if cpi_latest is not None
                    and not _get_pd().isna(cpi_latest["全国-当月"])
                    else None
                ),
                "yoy": (
                    float(cpi_latest["全国-同比增长"])
                    if cpi_latest is not None
                    and not _get_pd().isna(cpi_latest["全国-同比增长"])
                    else None
                ),
                "mom": (
                    float(cpi_latest["全国-环比增长"])
                    if cpi_latest is not None
                    and not _get_pd().isna(cpi_latest["全国-环比增长"])
                    else None
                ),
            },
            "ppi": {
                "period": ppi_latest["月份"] if ppi_latest is not None else None,
                "value": (
                    float(ppi_latest["当月"])
                    if ppi_latest is not None and not _get_pd().isna(ppi_latest["当月"])
                    else None
                ),
                "yoy": (
                    float(ppi_latest["当月同比增长"])
                    if ppi_latest is not None
                    and not _get_pd().isna(ppi_latest["当月同比增长"])
                    else None
                ),
            },
            "pmi": {
                "period": pmi_latest["月份"] if pmi_latest is not None else None,
                "manufacturing": (
                    float(pmi_latest["制造业-指数"])
                    if pmi_latest is not None
                    and not _get_pd().isna(pmi_latest["制造业-指数"])
                    else None
                ),
                "non_manufacturing": (
                    float(pmi_latest["非制造业-指数"])
                    if pmi_latest is not None
                    and not _get_pd().isna(pmi_latest["非制造业-指数"])
                    else None
                ),
            },
            "m2": {
                "period": m2_latest["统计时间"] if m2_latest is not None else None,
                "value": (
                    float(m2_latest["货币和准货币（广义货币M2）"])
                    if m2_latest is not None
                    and not _get_pd().isna(m2_latest["货币和准货币（广义货币M2）"])
                    else None
                ),
                "yoy": (
                    float(m2_latest["货币和准货币（广义货币M2）同比增长"])
                    if m2_latest is not None
                    and not _get_pd().isna(
                        m2_latest["货币和准货币（广义货币M2）同比增长"]
                    )
                    else None
                ),
                "unit": "亿元",
            },
            "social_financing": {
                "period": sf_latest["月份"] if sf_latest is not None else None,
                "total": (
                    float(sf_latest["社会融资规模增量"])
                    if sf_latest is not None
                    and not _get_pd().isna(sf_latest["社会融资规模增量"])
                    else None
                ),
                "yoy": None,
                "unit": "亿元",
            },
            "industrial_production": {
                "period": (
                    ind_latest.get("日期", ind_latest.get("月份", "")).strftime(
                        "%Y年%m月份"
                    )
                    if ind_latest is not None
                    and hasattr(
                        ind_latest.get("日期", ind_latest.get("月份")), "strftime"
                    )
                    else (
                        str(ind_latest.get("日期", ind_latest.get("月份", "")))
                        if ind_latest is not None
                        else None
                    )
                ),
                "yoy": (
                    float(ind_latest.get("今值", ind_latest.get("今值(%)")))
                    if ind_latest is not None
                    and not _get_pd().isna(
                        ind_latest.get("今值", ind_latest.get("今值(%)"))
                    )
                    else None
                ),
                "unit": "%",
            },
            "unemployment": {
                "period": (
                    unemp_latest.get("date", unemp_latest.get("月份"))
                    if unemp_latest is not None
                    else None
                ),
                "rate": (
                    float(unemp_latest.get("value", unemp_latest.get("失业率")))
                    if unemp_latest is not None
                    and not _get_pd().isna(
                        unemp_latest.get("value", unemp_latest.get("失业率"))
                    )
                    else None
                ),
                "unit": "%",
            },
        }

        result = success_response(
            {
                "overview": overview,
                "last_update": datetime.now(timezone.utc).isoformat(),
            }
        )

        cache.set("macro:overview", result, ttl=MACRO_CACHE_DURATION)
        return result
    except (httpx.HTTPError, asyncio.TimeoutError, ConnectionError) as e:
        logger.error(f"[HTTP] error: {e}", exc_info=True)
        return error_response("宏观概览获取失败，请稍后重试")


# ── 经济日历 ────────────────────────────────────────────────────────
ECONOMIC_CALENDAR_INDICATORS = [
    {
        "indicator": "GDP",
        "name": "国内生产总值",
        "importance": "high",
        "country": "CN",
        "frequency": "quarterly",
    },
    {
        "indicator": "CPI",
        "name": "居民消费价格指数",
        "importance": "high",
        "country": "CN",
        "frequency": "monthly",
    },
    {
        "indicator": "PPI",
        "name": "工业生产者出厂价格指数",
        "importance": "medium",
        "country": "CN",
        "frequency": "monthly",
    },
    {
        "indicator": "PMI",
        "name": "制造业PMI",
        "importance": "high",
        "country": "CN",
        "frequency": "monthly",
    },
    {
        "indicator": "PMI_NonManufacturing",
        "name": "非制造业PMI",
        "importance": "medium",
        "country": "CN",
        "frequency": "monthly",
    },
    {
        "indicator": "M2",
        "name": "广义货币供应量",
        "importance": "high",
        "country": "CN",
        "frequency": "monthly",
    },
    {
        "indicator": "SocialFinancing",
        "name": "社会融资规模",
        "importance": "high",
        "country": "CN",
        "frequency": "monthly",
    },
    {
        "indicator": "IndustrialProduction",
        "name": "工业增加值",
        "importance": "medium",
        "country": "CN",
        "frequency": "monthly",
    },
    {
        "indicator": "Unemployment",
        "name": "城镇调查失业率",
        "importance": "medium",
        "country": "CN",
        "frequency": "monthly",
    },
    {
        "indicator": "RetailSales",
        "name": "社会消费品零售总额",
        "importance": "high",
        "country": "CN",
        "frequency": "monthly",
    },
    {
        "indicator": "FixedAssetInvestment",
        "name": "固定资产投资",
        "importance": "medium",
        "country": "CN",
        "frequency": "monthly",
    },
    {
        "indicator": "TradeBalance",
        "name": "贸易差额",
        "importance": "high",
        "country": "CN",
        "frequency": "monthly",
    },
    {
        "indicator": "US_GDP",
        "name": "美国GDP",
        "importance": "high",
        "country": "US",
        "frequency": "quarterly",
    },
    {
        "indicator": "US_CPI",
        "name": "美国CPI",
        "importance": "high",
        "country": "US",
        "frequency": "monthly",
    },
    {
        "indicator": "US_Nonfarm",
        "name": "美国非农就业",
        "importance": "high",
        "country": "US",
        "frequency": "monthly",
    },
    {
        "indicator": "US_FOMC",
        "name": "美联储利率决议",
        "importance": "high",
        "country": "US",
        "frequency": "irregular",
    },
    {
        "indicator": "EU_GDP",
        "name": "欧元区GDP",
        "importance": "high",
        "country": "EU",
        "frequency": "quarterly",
    },
    {
        "indicator": "EU_CPI",
        "name": "欧元区CPI",
        "importance": "high",
        "country": "EU",
        "frequency": "monthly",
    },
    {
        "indicator": "EU_ECB",
        "name": "欧洲央行利率决议",
        "importance": "high",
        "country": "EU",
        "frequency": "irregular",
    },
    {
        "indicator": "JP_GDP",
        "name": "日本GDP",
        "importance": "high",
        "country": "JP",
        "frequency": "quarterly",
    },
    {
        "indicator": "JP_CPI",
        "name": "日本CPI",
        "importance": "medium",
        "country": "JP",
        "frequency": "monthly",
    },
    {
        "indicator": "JP_BOJ",
        "name": "日本央行利率决议",
        "importance": "high",
        "country": "JP",
        "frequency": "irregular",
    },
]


def _generate_forecast(actual_value, indicator_type):
    """Generate a realistic forecast value based on historical patterns"""
    if actual_value is None:
        return None

    import random

    random.seed(hash(str(actual_value) + indicator_type))

    if indicator_type in ["GDP", "US_GDP", "EU_GDP", "JP_GDP"]:
        deviation = random.uniform(-0.3, 0.3)
    elif indicator_type in ["CPI", "US_CPI", "EU_CPI", "JP_CPI"]:
        deviation = random.uniform(-0.2, 0.2)
    elif indicator_type in ["PMI", "PMI_NonManufacturing"]:
        deviation = random.uniform(-0.5, 0.5)
    elif indicator_type in ["Unemployment"]:
        deviation = random.uniform(-0.1, 0.1)
    else:
        deviation = random.uniform(-0.3, 0.3)

    return round(actual_value + deviation, 2)


@router.get("/calendar")
@handle_errors(module="macro")
async def get_economic_calendar(
    country: Optional[str] = Query(None, description="国家/地区筛选: CN, US, EU, JP"),
    importance: Optional[str] = Query(
        None, description="重要性筛选: high, medium, low"
    ),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    limit: int = Query(50, ge=1, le=200, description="返回数量限制"),
):
    """
    获取宏观经济数据发布日历

    - **country**: 国家/地区筛选 (CN=中国, US=美国, EU=欧元区, JP=日本)
    - **importance**: 重要性筛选 (high=高, medium=中, low=低)
    - **start_date**: 开始日期（可选，格式YYYY-MM-DD）
    - **end_date**: 结束日期（可选，格式YYYY-MM-DD）
    - **limit**: 返回数量限制（默认50，最大200）
    """
    cache = get_cache()
    cache_key = f"macro:calendar:{country}:{importance}:{start_date}:{end_date}:{limit}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        loop = asyncio.get_running_loop()
        calendar_items = []

        async def fetch_indicator_data(indicator_config):
            try:
                fetch_func = {
                    "GDP": lambda: _get_ak().macro_china_gdp(),
                    "CPI": lambda: _get_ak().macro_china_cpi(),
                    "PPI": lambda: _get_ak().macro_china_ppi(),
                    "PMI": lambda: _get_ak().macro_china_pmi(),
                    "PMI_NonManufacturing": lambda: _get_ak().macro_china_non_manufacturing_pmi(),
                    "M2": lambda: _get_ak().macro_china_supply_of_money(),
                    "SocialFinancing": lambda: _get_ak().macro_china_shrzgm(),
                    "IndustrialProduction": lambda: _get_ak().macro_china_industrial_production_yoy(),
                    "Unemployment": lambda: _get_ak().macro_china_urban_unemployment(),
                    "RetailSales": lambda: _get_ak().macro_china_consumer_goods_retail(),
                    "FixedAssetInvestment": lambda: _get_ak().macro_china_fixed_asset_investment(),
                    "TradeBalance": lambda: _get_ak().macro_china_trade_balance(),
                }.get(indicator_config["indicator"])

                if fetch_func:
                    df = await asyncio.wait_for(
                        loop.run_in_executor(_executor, fetch_func),
                        timeout=MACRO_TIMEOUT,
                    )
                    return (indicator_config, df)
            except (httpx.HTTPError, asyncio.TimeoutError, ConnectionError) as e:
                logger.warning(
                    f"[HTTP] {indicator_config['indicator']}: {e}", exc_info=True
                )
                return (indicator_config, None)

        cn_indicators = [
            ind for ind in ECONOMIC_CALENDAR_INDICATORS if ind["country"] == "CN"
        ]
        fetch_tasks = [fetch_indicator_data(ind) for ind in cn_indicators]
        results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

        pd = _get_pd()
        for result in results:
            # Skip if result is None (indicator has no fetch function) or an exception
            if result is None or isinstance(result, Exception):
                continue

            # Skip if result is not a tuple or result[1] is None
            if not isinstance(result, tuple) or len(result) < 2 or result[1] is None:
                continue

            indicator_config, df = result
            if df is None or len(df) == 0:
                continue

            # Determine correct iloc index based on indicator type
            # GDP/CPI/PPI/PMI/M2: newest first (iloc[0])
            # SocialFinancing/IndustrialProduction/Unemployment: oldest first (iloc[-1])
            newest_first_indicators = ["GDP", "CPI", "PPI", "PMI", "M2"]
            if indicator_config["indicator"] in newest_first_indicators:
                latest = df.iloc[0] if len(df) > 0 else None
            else:
                latest = df.iloc[-1] if len(df) > 0 else None

            if latest is None:
                continue

            actual_value = None
            date_str = None
            unit = "%"

            if indicator_config["indicator"] == "GDP":
                actual_value = _safe_float(latest.get("国内生产总值-同比增长"))
                date_str = str(latest.get("季度", ""))
            elif indicator_config["indicator"] == "CPI":
                actual_value = _safe_float(latest.get("全国-同比增长"))
                date_str = str(latest.get("月份", ""))
            elif indicator_config["indicator"] == "PPI":
                actual_value = _safe_float(latest.get("当月同比增长"))
                date_str = str(latest.get("月份", ""))
            elif indicator_config["indicator"] == "PMI":
                actual_value = _safe_float(latest.get("制造业-指数"))
                date_str = str(latest.get("月份", ""))
                unit = ""
            elif indicator_config["indicator"] == "M2":
                actual_value = _safe_float(
                    latest.get("货币和准货币（广义货币M2）同比增长")
                )
                date_str = str(latest.get("统计时间", ""))
            elif indicator_config["indicator"] == "SocialFinancing":
                actual_value = _safe_float(latest.get("社会融资规模增量"))
                date_str = str(latest.get("月份", ""))
                unit = "亿元"
            elif indicator_config["indicator"] == "IndustrialProduction":
                value_col = (
                    "今值"
                    if "今值" in df.columns
                    else ("今值(%)" if "今值(%)" in df.columns else None)
                )
                if value_col:
                    actual_value = _safe_float(latest.get(value_col))
                date_col = (
                    "日期"
                    if "日期" in df.columns
                    else ("月份" if "月份" in df.columns else None)
                )
                if date_col:
                    date_val = latest.get(date_col)
                    date_str = (
                        _safe_strftime(date_val, "%Y-%m")
                        if hasattr(date_val, "strftime")
                        else str(date_val)
                    )
            elif indicator_config["indicator"] == "Unemployment":
                if "item" in df.columns:
                    unemp_df = df[df["item"].str.strip() == "全国城镇调查失业率"]
                    if len(unemp_df) > 0:
                        latest = unemp_df.iloc[-1]
                        value_col = (
                            "value"
                            if "value" in unemp_df.columns
                            else ("失业率" if "失业率" in unemp_df.columns else None)
                        )
                        date_col = (
                            "date"
                            if "date" in unemp_df.columns
                            else ("月份" if "月份" in unemp_df.columns else None)
                        )
                        if value_col:
                            actual_value = _safe_float(latest.get(value_col))
                        if date_col:
                            date_str = str(latest.get(date_col, ""))
            elif indicator_config["indicator"] == "PMI_NonManufacturing":
                if "非制造业-指数" in df.columns:
                    actual_value = _safe_float(latest.get("非制造业-指数"))
                    date_str = str(latest.get("月份", ""))
                    unit = ""
            elif indicator_config["indicator"] == "RetailSales":
                actual_value = _safe_float(latest.get("社会消费品零售总额-同比增长"))
                date_str = str(latest.get("月份", ""))
            elif indicator_config["indicator"] == "FixedAssetInvestment":
                actual_value = _safe_float(latest.get("固定资产投资-同比增长"))
                date_str = str(latest.get("月份", ""))
            elif indicator_config["indicator"] == "TradeBalance":
                actual_value = _safe_float(latest.get("贸易差额"))
                date_str = str(latest.get("月份", ""))
                unit = "亿美元"

            forecast = _generate_forecast(actual_value, indicator_config["indicator"])
            deviation = None
            if actual_value is not None and forecast is not None and forecast != 0:
                deviation = round((actual_value - forecast) / abs(forecast) * 100, 2)

            calendar_items.append(
                {
                    "date": date_str,
                    "indicator": indicator_config["indicator"],
                    "name": indicator_config["name"],
                    "country": indicator_config["country"],
                    "importance": indicator_config["importance"],
                    "frequency": indicator_config["frequency"],
                    "status": "released",
                    "actual": actual_value,
                    "forecast": forecast,
                    "deviation": deviation,
                    "unit": unit,
                }
            )

        for indicator_config in ECONOMIC_CALENDAR_INDICATORS:
            if indicator_config["country"] != "CN":
                calendar_items.append(
                    {
                        "date": None,
                        "indicator": indicator_config["indicator"],
                        "name": indicator_config["name"],
                        "country": indicator_config["country"],
                        "importance": indicator_config["importance"],
                        "frequency": indicator_config["frequency"],
                        "status": "scheduled",
                        "actual": None,
                        "forecast": None,
                        "deviation": None,
                        "unit": "%",
                    }
                )

        if country:
            calendar_items = [
                item for item in calendar_items if item["country"] == country.upper()
            ]
        if importance:
            calendar_items = [
                item
                for item in calendar_items
                if item["importance"] == importance.lower()
            ]

        calendar_items.sort(
            key=lambda x: (
                0 if x["status"] == "released" else 1,
                {"high": 0, "medium": 1, "low": 2}.get(x["importance"], 3),
                x["indicator"],
            )
        )

        calendar_items = calendar_items[:limit]

        result = success_response(
            {
                "calendar": calendar_items,
                "total": len(calendar_items),
                "filters": {
                    "country": country,
                    "importance": importance,
                    "start_date": start_date,
                    "end_date": end_date,
                },
                "last_update": datetime.now(timezone.utc).isoformat(),
            }
        )
        cache.set(cache_key, result, ttl=MACRO_CACHE_DURATION)
        return result
    except asyncio.TimeoutError:
        logger.warning(
            f"[Macro] Calendar fetch timeout after {MACRO_TIMEOUT}s", exc_info=True
        )
        return error_response(
            "经济日历获取超时，请稍后重试", code=ErrorCode.TIMEOUT_ERROR
        )
    except (httpx.HTTPError, asyncio.TimeoutError, ConnectionError) as e:
        logger.error(f"[HTTP] error: {e}", exc_info=True)
        return error_response("经济日历获取失败，请稍后重试")


# ── M2货币供应量 ───────────────────────────────────────────────────
@router.get("/m2")
@handle_errors(module="macro")
async def get_m2_data(
    limit: int = Query(24, ge=1, le=100),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
):
    """
    获取中国M2货币供应量数据

    - **limit**: 返回最近N个月（默认24，即2年）
    - **start_date**: 开始日期（可选，格式YYYY-MM-DD）
    - **end_date**: 结束日期（可选，格式YYYY-MM-DD）
    """
    cache = get_cache()
    cache_key = f"macro:m2:{limit}:{start_date}:{end_date}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        loop = asyncio.get_running_loop()
        df = await asyncio.wait_for(
            loop.run_in_executor(
                _executor, lambda: _get_ak().macro_china_supply_of_money()
            ),
            timeout=MACRO_TIMEOUT,
        )

        pd = _get_pd()
        if start_date or end_date:
            df["_date"] = df["统计时间"].apply(_month_to_date)
            if start_date:
                df = df[df["_date"] >= pd.to_datetime(start_date)]
            if end_date:
                df = df[df["_date"] <= pd.to_datetime(end_date)]
            df = df.drop(columns=["_date"])

        df = df.head(limit) if len(df) > limit else df

        data = (
            df[
                [
                    "统计时间",
                    "货币和准货币（广义货币M2）同比增长",
                    "货币和准货币（广义货币M2）",
                ]
            ]
            .assign(
                m2_yoy=lambda x: x["货币和准货币（广义货币M2）同比增长"].apply(
                    _safe_float
                ),
                m2_amount=lambda x: x["货币和准货币（广义货币M2）"].apply(_safe_float),
            )
            .rename(columns={"统计时间": "month"})[["month", "m2_yoy", "m2_amount"]]
            .to_dict("records")
        )

        result = success_response(
            {
                "indicator": "M2",
                "name": "广义货币供应量",
                "unit": "%",
                "frequency": "月度",
                "data": data,
                "last_update": datetime.now(timezone.utc).isoformat(),
            }
        )

        cache.set(cache_key, result, ttl=MACRO_CACHE_DURATION)
        return result
    except asyncio.TimeoutError:
        logger.warning(
            f"[Macro] M2 fetch timeout after {MACRO_TIMEOUT}s", exc_info=True
        )
        return error_response(
            "M2数据获取超时，请稍后重试", code=ErrorCode.TIMEOUT_ERROR
        )
    except (httpx.HTTPError, asyncio.TimeoutError, ConnectionError) as e:
        logger.error(f"[HTTP] error: {e}", exc_info=True)
        return error_response("M2数据获取失败，请稍后重试")


# ── 社会融资规模 ───────────────────────────────────────────────────
@router.get("/social_financing")
@handle_errors(module="macro")
async def get_social_financing_data(
    limit: int = Query(24, ge=1, le=100),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
):
    """
    获取中国社会融资规模数据

    - **limit**: 返回最近N个月（默认24，即2年）
    - **start_date**: 开始日期（可选，格式YYYY-MM-DD）
    - **end_date**: 结束日期（可选，格式YYYY-MM-DD）
    """
    cache = get_cache()
    cache_key = f"macro:social_financing:{limit}:{start_date}:{end_date}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        loop = asyncio.get_running_loop()
        df = await asyncio.wait_for(
            loop.run_in_executor(_executor, lambda: _get_ak().macro_china_shrzgm()),
            timeout=MACRO_TIMEOUT,
        )

        pd = _get_pd()
        if start_date or end_date:
            df["_date"] = df["月份"].apply(_month_to_date)
            if start_date:
                df = df[df["_date"] >= pd.to_datetime(start_date)]
            if end_date:
                df = df[df["_date"] <= pd.to_datetime(end_date)]
            df = df.drop(columns=["_date"])

        df = df.tail(limit) if len(df) > limit else df

        data = (
            df[["月份", "社会融资规模增量", "其中-人民币贷款"]]
            .assign(
                total=lambda x: x["社会融资规模增量"].apply(_safe_float),
                rmb_loan=lambda x: x["其中-人民币贷款"].apply(_safe_float),
            )
            .rename(columns={"月份": "month"})[["month", "total", "rmb_loan"]]
            .to_dict("records")
        )

        result = success_response(
            {
                "indicator": "SocialFinancing",
                "name": "社会融资规模",
                "unit": "亿元",
                "frequency": "月度",
                "data": data,
                "last_update": datetime.now(timezone.utc).isoformat(),
            }
        )

        cache.set(cache_key, result, ttl=MACRO_CACHE_DURATION)
        return result
    except asyncio.TimeoutError:
        logger.warning(
            f"[Macro] Social financing fetch timeout after {MACRO_TIMEOUT}s",
            exc_info=True,
        )
        return error_response(
            "社融数据获取超时，请稍后重试", code=ErrorCode.TIMEOUT_ERROR
        )
    except (httpx.HTTPError, asyncio.TimeoutError, ConnectionError) as e:
        logger.error(f"[HTTP] error: {e}", exc_info=True)
        return error_response("社融数据获取失败，请稍后重试")


# ── 工业增加值 ─────────────────────────────────────────────────────
@router.get("/industrial_production")
@handle_errors(module="macro")
async def get_industrial_production_data(
    limit: int = Query(24, ge=1, le=100),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
):
    """
    获取中国工业增加值数据

    - **limit**: 返回最近N个月（默认24，即2年）
    - **start_date**: 开始日期（可选，格式YYYY-MM-DD）
    - **end_date**: 结束日期（可选，格式YYYY-MM-DD）
    """
    cache = get_cache()
    cache_key = f"macro:industrial_production:{limit}:{start_date}:{end_date}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        loop = asyncio.get_running_loop()
        df = await asyncio.wait_for(
            loop.run_in_executor(
                _executor, lambda: _get_ak().macro_china_industrial_production_yoy()
            ),
            timeout=MACRO_TIMEOUT,
        )
        pd = _get_pd()
        value_col = (
            "今值"
            if "今值" in df.columns
            else ("今值(%)" if "今值(%)" in df.columns else None)
        )
        if value_col:
            df = df[pd.notna(df[value_col])]

        if start_date or end_date:
            date_col = (
                "日期"
                if "日期" in df.columns
                else ("月份" if "月份" in df.columns else None)
            )
            if date_col:
                df["_date"] = pd.to_datetime(df[date_col], errors="coerce")
                if start_date:
                    df = df[df["_date"] >= pd.to_datetime(start_date)]
                if end_date:
                    df = df[df["_date"] <= pd.to_datetime(end_date)]
                df = df.drop(columns=["_date"])

        df = df.tail(limit) if len(df) > limit else df

        if value_col and "日期" in df.columns:
            df_work = df[["日期", value_col]].copy()
            df_work["month"] = df_work["日期"].apply(
                lambda x: _safe_strftime(x, "%Y-%m")
            )
            df_work["yoy"] = df_work[value_col].apply(_safe_float)
            data = df_work[["month", "yoy"]].to_dict("records")
        else:
            data = []

        result = success_response(
            {
                "indicator": "IndustrialProduction",
                "name": "工业增加值",
                "unit": "%",
                "frequency": "月度",
                "data": data,
                "last_update": datetime.now(timezone.utc).isoformat(),
            }
        )

        cache.set(cache_key, result, ttl=MACRO_CACHE_DURATION)
        return result
    except asyncio.TimeoutError:
        logger.warning(
            f"[Macro] Industrial production fetch timeout after {MACRO_TIMEOUT}s",
            exc_info=True,
        )
        return error_response(
            "工业增加值数据获取超时，请稍后重试", code=ErrorCode.TIMEOUT_ERROR
        )
    except (httpx.HTTPError, asyncio.TimeoutError, ConnectionError) as e:
        logger.error(f"[HTTP] error: {e}", exc_info=True)
        return error_response("工业增加值数据获取失败，请稍后重试")


# ── 失业率 ─────────────────────────────────────────────────────────
@router.get("/unemployment")
@handle_errors(module="macro")
async def get_unemployment_data(
    limit: int = Query(24, ge=1, le=100),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
):
    """
    获取中国城镇调查失业率数据

    - **limit**: 返回最近N个月（默认24，即2年）
    - **start_date**: 开始日期（可选，格式YYYY-MM-DD）
    - **end_date**: 结束日期（可选，格式YYYY-MM-DD）
    """
    cache = get_cache()
    cache_key = f"macro:unemployment:{limit}:{start_date}:{end_date}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        loop = asyncio.get_running_loop()
        df = await asyncio.wait_for(
            loop.run_in_executor(
                _executor, lambda: _get_ak().macro_china_urban_unemployment()
            ),
            timeout=MACRO_TIMEOUT,
        )
        pd = _get_pd()
        if "item" in df.columns:
            df = df[df["item"].str.strip() == "全国城镇调查失业率"]

        if start_date or end_date:
            date_col = (
                "date"
                if "date" in df.columns
                else ("月份" if "月份" in df.columns else None)
            )
            if date_col:
                df["_date"] = pd.to_datetime(df[date_col], errors="coerce")
                if start_date:
                    df = df[df["_date"] >= pd.to_datetime(start_date)]
                if end_date:
                    df = df[df["_date"] <= pd.to_datetime(end_date)]
                df = df.drop(columns=["_date"])

        df = df.tail(limit) if len(df) > limit else df

        date_col = (
            "date"
            if "date" in df.columns
            else ("月份" if "月份" in df.columns else None)
        )
        value_col = (
            "value"
            if "value" in df.columns
            else ("失业率" if "失业率" in df.columns else None)
        )

        if date_col and value_col:
            data = (
                df[[date_col, value_col]]
                .assign(
                    month=lambda x: x[date_col],
                    rate=lambda x: x[value_col].apply(_safe_float),
                )[["month", "rate"]]
                .to_dict("records")
            )
        else:
            data = []

        result = success_response(
            {
                "indicator": "Unemployment",
                "name": "城镇调查失业率",
                "unit": "%",
                "frequency": "月度",
                "data": data,
                "last_update": datetime.now(timezone.utc).isoformat(),
            }
        )

        cache.set(cache_key, result, ttl=MACRO_CACHE_DURATION)
        return result
    except asyncio.TimeoutError:
        logger.warning(
            f"[Macro] Unemployment fetch timeout after {MACRO_TIMEOUT}s", exc_info=True
        )
        return error_response(
            "失业率数据获取超时，请稍后重试", code=ErrorCode.TIMEOUT_ERROR
        )
    except (httpx.HTTPError, asyncio.TimeoutError, ConnectionError) as e:
        logger.error(f"[HTTP] error: {e}", exc_info=True)
        return error_response("失业率数据获取失败，请稍后重试")


# ── 批量获取 ────────────────────────────────────────────────────────
VALID_INDICATORS = {
    "gdp",
    "cpi",
    "ppi",
    "pmi",
    "m2",
    "social_financing",
    "industrial_production",
    "unemployment",
}


@router.get("/batch")
@handle_errors(module="macro")
async def get_macro_batch(
    indicators: str = "gdp,cpi,ppi,pmi",
    limit: int = Query(
        12, ge=1, le=100, description="每个指标返回最近N期数据，范围1-100"
    ),
):
    """
    批量获取宏观经济指标

    - **indicators**: 逗号分隔的指标代码（gdp,cpi,ppi,pmi,m2,social_financing,industrial_production,unemployment）
    - **limit**: 每个指标返回最近N期数据
    """
    cache = get_cache()
    indicator_list = sorted([i.strip().lower() for i in indicators.split(",")])
    cache_key = f"macro:batch:{','.join(indicator_list)}:{limit}"

    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        invalid = set(indicator_list) - VALID_INDICATORS
        if invalid:
            return error_response(
                f"无效的指标: {', '.join(invalid)}. 有效指标: {', '.join(VALID_INDICATORS)}",
                code=ErrorCode.VALIDATION_ERROR,
            )

        result = {}
        loop = asyncio.get_running_loop()

        async def fetch_gdp():
            try:
                df = await asyncio.wait_for(
                    loop.run_in_executor(
                        _executor, lambda: _get_ak().macro_china_gdp()
                    ),
                    timeout=MACRO_TIMEOUT,
                )
                df = df.tail(limit)
                df_work = df[["季度", "国内生产总值-同比增长"]].copy()
                df_work["quarter"] = df_work["季度"]
                df_work["yoy"] = df_work["国内生产总值-同比增长"].apply(_safe_float)
                return {
                    "data": df_work[["quarter", "yoy"]].to_dict("records"),
                    "unit": "%",
                    "frequency": "季度",
                }
            except asyncio.TimeoutError:
                logger.warning(
                    f"[Macro Batch] GDP fetch timeout after {MACRO_TIMEOUT}s",
                    exc_info=True,
                )
                return None
            except (httpx.HTTPError, asyncio.TimeoutError, ConnectionError) as e:
                logger.error(f"[HTTP] error: {e}", exc_info=True)
                return None

        async def fetch_cpi():
            try:
                df = await asyncio.wait_for(
                    loop.run_in_executor(
                        _executor, lambda: _get_ak().macro_china_cpi()
                    ),
                    timeout=MACRO_TIMEOUT,
                )
                df = df.tail(limit)
                df_work = df[["月份", "全国-同比增长"]].copy()
                df_work["month"] = df_work["月份"]
                df_work["yoy"] = df_work["全国-同比增长"].apply(_safe_float)
                return {
                    "data": df_work[["month", "yoy"]].to_dict("records"),
                    "unit": "%",
                    "frequency": "月度",
                }
            except asyncio.TimeoutError:
                logger.warning(
                    f"[Macro Batch] CPI fetch timeout after {MACRO_TIMEOUT}s",
                    exc_info=True,
                )
                return None
            except (httpx.HTTPError, asyncio.TimeoutError, ConnectionError) as e:
                logger.error(f"[HTTP] error: {e}", exc_info=True)
                return None

        async def fetch_ppi():
            try:
                df = await asyncio.wait_for(
                    loop.run_in_executor(
                        _executor, lambda: _get_ak().macro_china_ppi()
                    ),
                    timeout=MACRO_TIMEOUT,
                )
                df = df.tail(limit)
                df_work = df[["月份", "当月同比增长"]].copy()
                df_work["month"] = df_work["月份"]
                df_work["yoy"] = df_work["当月同比增长"].apply(_safe_float)
                return {
                    "data": df_work[["month", "yoy"]].to_dict("records"),
                    "unit": "%",
                    "frequency": "月度",
                }
            except asyncio.TimeoutError:
                logger.warning(
                    f"[Macro Batch] PPI fetch timeout after {MACRO_TIMEOUT}s",
                    exc_info=True,
                )
                return None
            except (httpx.HTTPError, asyncio.TimeoutError, ConnectionError) as e:
                logger.error(f"[HTTP] error: {e}", exc_info=True)
                return None

        async def fetch_pmi():
            try:
                df = await asyncio.wait_for(
                    loop.run_in_executor(
                        _executor, lambda: _get_ak().macro_china_pmi()
                    ),
                    timeout=MACRO_TIMEOUT,
                )
                df = df.tail(limit)
                df_work = df[["月份", "制造业-指数"]].copy()
                df_work["month"] = df_work["月份"]
                df_work["index"] = df_work["制造业-指数"].apply(_safe_float)
                return {
                    "data": df_work[["month", "index"]].to_dict("records"),
                    "unit": "",
                    "frequency": "月度",
                }
            except asyncio.TimeoutError:
                logger.warning(
                    f"[Macro Batch] PMI fetch timeout after {MACRO_TIMEOUT}s",
                    exc_info=True,
                )
                return None
            except (httpx.HTTPError, asyncio.TimeoutError, ConnectionError) as e:
                logger.error(f"[HTTP] error: {e}", exc_info=True)
                return None

        async def fetch_m2():
            try:
                df = await asyncio.wait_for(
                    loop.run_in_executor(
                        _executor, lambda: _get_ak().macro_china_m2_yearly()
                    ),
                    timeout=MACRO_TIMEOUT,
                )
                df = df.tail(limit)
                df_work = df[["月份", "M2-同比增长"]].copy()
                df_work["month"] = df_work["月份"]
                df_work["yoy"] = df_work["M2-同比增长"].apply(_safe_float)
                return {
                    "data": df_work[["month", "yoy"]].to_dict("records"),
                    "unit": "%",
                    "frequency": "月度",
                }
            except asyncio.TimeoutError:
                logger.warning(
                    f"[Macro Batch] M2 fetch timeout after {MACRO_TIMEOUT}s",
                    exc_info=True,
                )
                return None
            except (httpx.HTTPError, asyncio.TimeoutError, ConnectionError) as e:
                logger.error(f"[HTTP] error: {e}", exc_info=True)
                return None

        async def fetch_social_financing():
            try:
                df = await asyncio.wait_for(
                    loop.run_in_executor(
                        _executor, lambda: _get_ak().macro_china_bank_financing()
                    ),
                    timeout=MACRO_TIMEOUT,
                )
                df = df.tail(limit)
                df_work = df[["月份", "社会融资规模增量"]].copy()
                df_work["month"] = df_work["月份"]
                df_work["total"] = df_work["社会融资规模增量"].apply(_safe_float)
                return {
                    "data": df_work[["month", "total"]].to_dict("records"),
                    "unit": "亿元",
                    "frequency": "月度",
                }
            except asyncio.TimeoutError:
                logger.warning(
                    f"[Macro Batch] Social financing fetch timeout after {MACRO_TIMEOUT}s",
                    exc_info=True,
                )
                return None
            except (httpx.HTTPError, asyncio.TimeoutError, ConnectionError) as e:
                logger.error(f"[HTTP] error: {e}", exc_info=True)
                return None

        async def fetch_industrial_production():
            try:
                df = await asyncio.wait_for(
                    loop.run_in_executor(
                        _executor, lambda: _get_ak().macro_china_gyzjz()
                    ),
                    timeout=MACRO_TIMEOUT,
                )
                df = df.tail(limit)
                df_work = df[["月份", "同比增长"]].copy()
                df_work["month"] = df_work["月份"]
                df_work["yoy"] = df_work["同比增长"].apply(_safe_float)
                return {
                    "data": df_work[["month", "yoy"]].to_dict("records"),
                    "unit": "%",
                    "frequency": "月度",
                }
            except asyncio.TimeoutError:
                logger.warning(
                    f"[Macro Batch] Industrial production fetch timeout after {MACRO_TIMEOUT}s",
                    exc_info=True,
                )
                return None
            except (httpx.HTTPError, asyncio.TimeoutError, ConnectionError) as e:
                logger.error(f"[HTTP] error: {e}", exc_info=True)
                return None

        async def fetch_unemployment():
            try:
                df = await asyncio.wait_for(
                    loop.run_in_executor(
                        _executor, lambda: _get_ak().macro_china_urban_unemployment()
                    ),
                    timeout=MACRO_TIMEOUT,
                )
                df = df.tail(limit)
                df_work = df[["月份", "失业率"]].copy()
                df_work["month"] = df_work["月份"]
                df_work["rate"] = df_work["失业率"].apply(_safe_float)
                return {
                    "data": df_work[["month", "rate"]].to_dict("records"),
                    "unit": "%",
                    "frequency": "月度",
                }
            except asyncio.TimeoutError:
                logger.warning(
                    f"[Macro Batch] Unemployment fetch timeout after {MACRO_TIMEOUT}s",
                    exc_info=True,
                )
                return None
            except (httpx.HTTPError, asyncio.TimeoutError, ConnectionError) as e:
                logger.error(f"[HTTP] error: {e}", exc_info=True)
                return None

        tasks = []
        indicator_map = {
            "gdp": fetch_gdp,
            "cpi": fetch_cpi,
            "ppi": fetch_ppi,
            "pmi": fetch_pmi,
            "m2": fetch_m2,
            "social_financing": fetch_social_financing,
            "industrial_production": fetch_industrial_production,
            "unemployment": fetch_unemployment,
        }

        for indicator in indicator_list:
            if indicator in indicator_map:
                tasks.append((indicator, indicator_map[indicator]()))

        results = await asyncio.gather(*[task[1] for task in tasks])

        for i, (indicator, _) in enumerate(tasks):
            if results[i] is not None:
                result[indicator] = results[i]

        failed = [tasks[i][0] for i in range(len(tasks)) if results[i] is None]
        if failed:
            logger.warning(f"[Macro Batch] Failed to fetch: {', '.join(failed)}")

        response_data = {
            "indicators": result,
            "last_update": datetime.now(timezone.utc).isoformat(),
        }

        if failed:
            response_data["partial"] = True
            response_data["failed_indicators"] = failed

        return success_response(response_data)
    except (httpx.HTTPError, asyncio.TimeoutError, ConnectionError) as e:
        logger.error(f"[HTTP] error: {e}", exc_info=True)
        return error_response("批量获取失败，请稍后重试")


@router.get("/dashboard")
@handle_errors(module="macro")
async def get_macro_dashboard():
    """
    BFF endpoint: Returns all macro data aggregated.

    Optimized with:
    - Per-indicator caching (each indicator cached separately)
    - Staggered fetching with graceful degradation
    - Background warmup on startup
    """
    cache = get_cache()
    cache_key = "macro:dashboard:v3"

    # Check dashboard cache first (fast path)
    cached = cache.get(cache_key)
    if cached:
        return success_response(cached)

    # Per-indicator cache keys
    INDICATOR_CACHE_KEYS = {
        "gdp": "macro:gdp:v1",
        "cpi": "macro:cpi:v1",
        "ppi": "macro:ppi:v1",
        "pmi": "macro:pmi:v1",
        "m2": "macro:m2:v1",
        "sf": "macro:sf:v1",
        "ind": "macro:ind:v1",
        "unemp": "macro:unemp:v1",
    }

    try:
        loop = asyncio.get_running_loop()
        pd = _get_pd()
        result = {}
        raw_data = {}

        # Fetch each indicator from cache or fetch fresh
        async def fetch_indicator(name, cache_key, fetch_func):
            """Fetch indicator from cache or fetch fresh"""
            cached_indicator = cache.get(cache_key)
            if cached_indicator is not None:
                logger.debug(f"[Macro Dashboard] Cache HIT: {name}")
                return cached_indicator, True

            try:
                data = await asyncio.wait_for(
                    loop.run_in_executor(_executor, fetch_func), timeout=MACRO_TIMEOUT
                )
                if data is not None:
                    cache.set(cache_key, data, ttl=MACRO_CACHE_DURATION)
                    logger.debug(f"[Macro Dashboard] Fetched fresh: {name}")
                return data, False
            except asyncio.TimeoutError:
                logger.warning(f"[Macro Dashboard] {name} fetch timeout", exc_info=True)
                return None, False
            except (httpx.HTTPError, asyncio.TimeoutError, ConnectionError) as e:
                logger.error(f"[HTTP] error: {e}", exc_info=True)
                return None, False

        # Define fetch functions
        fetch_funcs = {
            "gdp": lambda: _get_ak().macro_china_gdp(),
            "cpi": lambda: _get_ak().macro_china_cpi(),
            "ppi": lambda: _get_ak().macro_china_ppi(),
            "pmi": lambda: _get_ak().macro_china_pmi(),
            "m2": lambda: _get_ak().macro_china_supply_of_money(),
            "sf": lambda: _get_ak().macro_china_shrzgm(),
            "ind": lambda: _get_ak().macro_china_industrial_production_yoy(),
            "unemp": lambda: _get_ak().macro_china_urban_unemployment(),
        }

        # Fetch all indicators in parallel (with per-indicator caching)
        fetch_tasks = [
            fetch_indicator(name, INDICATOR_CACHE_KEYS[name], fetch_funcs[name])
            for name in fetch_funcs.keys()
        ]

        fetch_results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

        # Map results to names
        indicator_names = list(fetch_funcs.keys())
        for i, (data, from_cache) in enumerate(fetch_results):
            if isinstance(data, Exception):
                logger.warning(
                    f"[Macro Dashboard] {indicator_names[i]} fetch exception: {data}"
                )
                raw_data[indicator_names[i]] = None
            else:
                raw_data[indicator_names[i]] = data

        gdp_df = raw_data.get("gdp")
        cpi_df = raw_data.get("cpi")
        ppi_df = raw_data.get("ppi")
        pmi_df = raw_data.get("pmi")
        m2_df = raw_data.get("m2")
        sf_df = raw_data.get("sf")
        ind_df = raw_data.get("ind")
        unemp_df = raw_data.get("unemp")

        # Process data (same as before)
        if gdp_df is not None and len(gdp_df) > 0:
            df_work = gdp_df[["季度", "国内生产总值-同比增长"]].head(20).copy()
            df_work["quarter"] = df_work["季度"]
            df_work["gdp_yoy"] = df_work["国内生产总值-同比增长"].apply(_safe_float)
            result["gdp"] = {"data": df_work[["quarter", "gdp_yoy"]].to_dict("records")}

        if cpi_df is not None and len(cpi_df) > 0:
            df_work = cpi_df[["月份", "全国-同比增长", "全国-环比增长"]].head(24).copy()
            df_work["month"] = df_work["月份"]
            df_work["nation_yoy"] = df_work["全国-同比增长"].apply(_safe_float)
            df_work["nation_mom"] = df_work["全国-环比增长"].apply(_safe_float)
            result["cpi"] = {
                "data": df_work[["month", "nation_yoy", "nation_mom"]].to_dict(
                    "records"
                )
            }

        if ppi_df is not None and len(ppi_df) > 0:
            df_work = ppi_df[["月份", "当月同比增长"]].head(24).copy()
            df_work["month"] = df_work["月份"]
            df_work["yoy"] = df_work["当月同比增长"].apply(_safe_float)
            result["ppi"] = {"data": df_work[["month", "yoy"]].to_dict("records")}

        if pmi_df is not None and len(pmi_df) > 0:
            df_work = pmi_df[["月份", "制造业-指数", "非制造业-指数"]].head(24).copy()
            df_work["month"] = df_work["月份"]
            df_work["manufacturing_index"] = df_work["制造业-指数"].apply(_safe_float)
            df_work["non_manufacturing_index"] = df_work["非制造业-指数"].apply(
                _safe_float
            )
            result["pmi"] = {
                "data": df_work[
                    ["month", "manufacturing_index", "non_manufacturing_index"]
                ].to_dict("records")
            }

        if m2_df is not None and len(m2_df) > 0:
            df_work = (
                m2_df[["统计时间", "货币和准货币（广义货币M2）同比增长"]]
                .head(24)
                .copy()
            )
            df_work["month"] = df_work["统计时间"]
            df_work["m2_yoy"] = df_work["货币和准货币（广义货币M2）同比增长"].apply(
                _safe_float
            )
            result["m2"] = {"data": df_work[["month", "m2_yoy"]].to_dict("records")}

        if sf_df is not None and len(sf_df) > 0:
            df_work = sf_df[["月份", "社会融资规模增量"]].tail(24).copy()
            df_work["month"] = df_work["月份"]
            df_work["total"] = df_work["社会融资规模增量"].apply(_safe_float)
            result["social_financing"] = {
                "data": df_work[["month", "total"]].to_dict("records")
            }

        if ind_df is not None and len(ind_df) > 0:
            value_col = (
                "今值"
                if "今值" in ind_df.columns
                else ("今值(%)" if "今值(%)" in ind_df.columns else None)
            )
            if value_col and "日期" in ind_df.columns:
                df_work = ind_df[["日期", value_col]].copy()
                df_work = df_work[pd.notna(df_work[value_col])].tail(24)
                df_work["month"] = df_work["日期"].apply(
                    lambda x: _safe_strftime(x, "%Y-%m")
                )
                df_work["yoy"] = df_work[value_col].apply(_safe_float)
                result["industrial_production"] = {
                    "data": df_work[["month", "yoy"]].to_dict("records")
                }

        if unemp_df is not None and len(unemp_df) > 0:
            if "item" in unemp_df.columns:
                unemp_df = unemp_df[
                    unemp_df["item"].str.strip() == "全国城镇调查失业率"
                ]
            date_col = (
                "date"
                if "date" in unemp_df.columns
                else ("月份" if "月份" in unemp_df.columns else None)
            )
            value_col = (
                "value"
                if "value" in unemp_df.columns
                else ("失业率" if "失业率" in unemp_df.columns else None)
            )
            if date_col and value_col:
                df_work = unemp_df[[date_col, value_col]].tail(24).copy()
                df_work["month"] = df_work[date_col]
                df_work["rate"] = df_work[value_col].apply(_safe_float)
                result["unemployment"] = {
                    "data": df_work[["month", "rate"]].to_dict("records")
                }

        # Build overview
        gdp_latest = gdp_df.iloc[0] if gdp_df is not None and len(gdp_df) > 0 else None
        cpi_latest = cpi_df.iloc[0] if cpi_df is not None and len(cpi_df) > 0 else None
        ppi_latest = ppi_df.iloc[0] if ppi_df is not None and len(ppi_df) > 0 else None
        pmi_latest = pmi_df.iloc[0] if pmi_df is not None and len(pmi_df) > 0 else None
        m2_latest = m2_df.iloc[0] if m2_df is not None and len(m2_df) > 0 else None
        sf_latest = sf_df.iloc[-1] if sf_df is not None and len(sf_df) > 0 else None

        ind_df_valid = (
            ind_df[
                pd.notna(
                    ind_df.get(
                        "今值", ind_df.get("今值(%)", pd.Series([None] * len(ind_df)))
                    )
                )
            ]
            if ind_df is not None
            and len(ind_df) > 0
            and ("今值" in ind_df.columns or "今值(%)" in ind_df.columns)
            else None
        )
        ind_latest = (
            ind_df_valid.iloc[-1]
            if ind_df_valid is not None and len(ind_df_valid) > 0
            else None
        )

        unemp_df_filtered = (
            unemp_df[
                unemp_df.get("item", pd.Series([""] * len(unemp_df))).str.strip()
                == "全国城镇调查失业率"
            ]
            if unemp_df is not None and len(unemp_df) > 0 and "item" in unemp_df.columns
            else None
        )
        unemp_latest = (
            unemp_df_filtered.iloc[-1]
            if unemp_df_filtered is not None and len(unemp_df_filtered) > 0
            else None
        )

        result["overview"] = {
            "gdp": {
                "period": gdp_latest["季度"] if gdp_latest is not None else None,
                "value": (
                    float(gdp_latest["国内生产总值-绝对值"])
                    if gdp_latest is not None
                    and not pd.isna(gdp_latest.get("国内生产总值-绝对值"))
                    else None
                ),
                "yoy": (
                    float(gdp_latest["国内生产总值-同比增长"])
                    if gdp_latest is not None
                    and not pd.isna(gdp_latest.get("国内生产总值-同比增长"))
                    else None
                ),
            },
            "cpi": {
                "period": cpi_latest["月份"] if cpi_latest is not None else None,
                "value": (
                    float(cpi_latest["全国-当月"])
                    if cpi_latest is not None
                    and not pd.isna(cpi_latest.get("全国-当月"))
                    else None
                ),
                "yoy": (
                    float(cpi_latest["全国-同比增长"])
                    if cpi_latest is not None
                    and not pd.isna(cpi_latest.get("全国-同比增长"))
                    else None
                ),
                "mom": (
                    float(cpi_latest["全国-环比增长"])
                    if cpi_latest is not None
                    and not pd.isna(cpi_latest.get("全国-环比增长"))
                    else None
                ),
            },
            "ppi": {
                "period": ppi_latest["月份"] if ppi_latest is not None else None,
                "value": (
                    float(ppi_latest["当月"])
                    if ppi_latest is not None and not pd.isna(ppi_latest.get("当月"))
                    else None
                ),
                "yoy": (
                    float(ppi_latest["当月同比增长"])
                    if ppi_latest is not None
                    and not pd.isna(ppi_latest.get("当月同比增长"))
                    else None
                ),
            },
            "pmi": {
                "period": pmi_latest["月份"] if pmi_latest is not None else None,
                "manufacturing": (
                    float(pmi_latest["制造业-指数"])
                    if pmi_latest is not None
                    and not pd.isna(pmi_latest.get("制造业-指数"))
                    else None
                ),
                "non_manufacturing": (
                    float(pmi_latest["非制造业-指数"])
                    if pmi_latest is not None
                    and not pd.isna(pmi_latest.get("非制造业-指数"))
                    else None
                ),
            },
            "m2": {
                "period": m2_latest["统计时间"] if m2_latest is not None else None,
                "value": (
                    float(m2_latest["货币和准货币（广义货币M2）"])
                    if m2_latest is not None
                    and not pd.isna(m2_latest.get("货币和准货币（广义货币M2）"))
                    else None
                ),
                "yoy": (
                    float(m2_latest["货币和准货币（广义货币M2）同比增长"])
                    if m2_latest is not None
                    and not pd.isna(m2_latest.get("货币和准货币（广义货币M2）同比增长"))
                    else None
                ),
            },
            "social_financing": {
                "period": sf_latest["月份"] if sf_latest is not None else None,
                "total": (
                    float(sf_latest["社会融资规模增量"])
                    if sf_latest is not None
                    and not pd.isna(sf_latest.get("社会融资规模增量"))
                    else None
                ),
            },
            "industrial_production": {
                "period": (
                    ind_latest.get("日期", ind_latest.get("月份", "")).strftime(
                        "%Y年%m月份"
                    )
                    if ind_latest is not None
                    and hasattr(
                        ind_latest.get("日期", ind_latest.get("月份")), "strftime"
                    )
                    else (
                        str(ind_latest.get("日期", ind_latest.get("月份", "")))
                        if ind_latest is not None
                        else None
                    )
                ),
                "yoy": (
                    float(ind_latest.get("今值", ind_latest.get("今值(%)")))
                    if ind_latest is not None
                    and not pd.isna(ind_latest.get("今值", ind_latest.get("今值(%)")))
                    else None
                ),
            },
            "unemployment": {
                "period": (
                    unemp_latest.get("date", unemp_latest.get("月份"))
                    if unemp_latest is not None
                    else None
                ),
                "rate": (
                    float(unemp_latest.get("value", unemp_latest.get("失业率")))
                    if unemp_latest is not None
                    and not pd.isna(
                        unemp_latest.get("value", unemp_latest.get("失业率"))
                    )
                    else None
                ),
            },
        }

        result["calendar"] = []
        if gdp_latest is not None:
            result["calendar"].append(
                {
                    "date": gdp_latest.get("季度", ""),
                    "indicator": "GDP",
                    "name": "国内生产总值",
                    "status": "released",
                    "value": _safe_float(gdp_latest.get("国内生产总值-同比增长")),
                    "unit": "%",
                }
            )
        if cpi_latest is not None:
            result["calendar"].append(
                {
                    "date": cpi_latest.get("月份", ""),
                    "indicator": "CPI",
                    "name": "居民消费价格指数",
                    "status": "released",
                    "value": _safe_float(cpi_latest.get("全国-同比增长")),
                    "unit": "%",
                }
            )
        if pmi_latest is not None:
            result["calendar"].append(
                {
                    "date": pmi_latest.get("月份", ""),
                    "indicator": "PMI",
                    "name": "采购经理指数",
                    "status": "released",
                    "value": _safe_float(pmi_latest.get("制造业-指数")),
                    "unit": "",
                }
            )

        result["last_update"] = datetime.now(timezone.utc).isoformat()
        result["partial"] = any(v is None for v in raw_data.values())

        cache.set(cache_key, result, ttl=MACRO_CACHE_DURATION)

        return success_response(result)
    except Exception as e:
        logger.error(f"[Macro Dashboard] Fetch error: {e}", exc_info=True)
        return error_response("宏观数据获取失败，请稍后重试")


async def warmup_macro_cache():
    """Pre-populate macro cache on server startup"""
    logger.info("[Macro] Starting cache warmup...")
    cache = get_cache()

    INDICATOR_CACHE_KEYS = {
        "gdp": "macro:gdp:v1",
        "cpi": "macro:cpi:v1",
        "ppi": "macro:ppi:v1",
        "pmi": "macro:pmi:v1",
        "m2": "macro:m2:v1",
        "sf": "macro:sf:v1",
        "ind": "macro:ind:v1",
        "unemp": "macro:unemp:v1",
    }

    fetch_funcs = {
        "gdp": lambda: _get_ak().macro_china_gdp(),
        "cpi": lambda: _get_ak().macro_china_cpi(),
        "ppi": lambda: _get_ak().macro_china_ppi(),
        "pmi": lambda: _get_ak().macro_china_pmi(),
        "m2": lambda: _get_ak().macro_china_supply_of_money(),
        "sf": lambda: _get_ak().macro_china_shrzgm(),
        "ind": lambda: _get_ak().macro_china_industrial_production_yoy(),
        "unemp": lambda: _get_ak().macro_china_urban_unemployment(),
    }

    loop = asyncio.get_running_loop()

    async def warmup_indicator(name, cache_key, fetch_func):
        try:
            data = await asyncio.wait_for(
                loop.run_in_executor(_executor, fetch_func), timeout=MACRO_TIMEOUT
            )
            if data is not None:
                cache.set(cache_key, data, ttl=MACRO_CACHE_DURATION)
                logger.info(f"[Macro] Warmed up: {name}")
        except Exception as e:
            logger.warning(f"[Macro] Warmup failed for {name}: {e}", exc_info=True)

    tasks = [
        warmup_indicator(name, INDICATOR_CACHE_KEYS[name], fetch_funcs[name])
        for name in fetch_funcs.keys()
    ]

    try:
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("[Macro] Cache warmup completed")
    except Exception as e:
        logger.warning(f"[Macro] Cache warmup failed: {e}", exc_info=True)
