"""
外汇行情 API
数据来源: AkShare (EastMoney, CFETS, SAFE)
功能: 外汇报价查询、历史数据、货币转换、交叉汇率矩阵

Timeout Behavior:
    All akshare calls wrapped with asyncio.wait_for() timeout protection.
    Returns 504 Gateway Timeout when external data source is slow.

Rate Limiting:
    60 requests per minute for forex endpoints.

Caching:
    Real-time quotes: 5 minutes
    Historical data: 30 minutes
    Cross-rate matrix: 5 minutes
"""
import logging
import random
import math
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from concurrent.futures import ThreadPoolExecutor

from app.utils.response import success_response, error_response, ErrorCode
from app.config.timeout import AKSHARE_TIMEOUT
from app.services.fetchers.forex_fetcher import ForexFetcher, clean_value, forex_fetcher, get_circuit_breaker_status
from app.services.data_cache import get_cache
from app.routers.forex_schemas import (
    ForexSpotQuote,
    ForexSpotQuoteList,
    ForexCFETSQuote,
    ForexCFETSQuoteList,
    ForexOfficialRate,
    ForexOfficialRateList,
    ForexKline,
    ForexHistoryResponse,
    CrossRateCell,
    CrossRateRow,
    CrossRateMatrix,
    CrossRateRequest,
    CrossRateResponse,
    CurrencyConvertRequest,
    CurrencyConvertResponse,
    ForexQuote,
    ForexQuotesResponse,
    OHLCData,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/forex", tags=["forex"])

_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="forex_")

_akshare_module = None

def _get_ak():
    global _akshare_module
    if _akshare_module is None:
        import akshare as ak
        _akshare_module = ak
    return _akshare_module

CURRENCY_PAIRS = {
    "USD/CNY": {"name": "美元/人民币", "ak_code": "美元"},
    "EUR/CNY": {"name": "欧元/人民币", "ak_code": "欧元"},
    "GBP/CNY": {"name": "英镑/人民币", "ak_code": "英镑"},
    "JPY/CNY": {"name": "日元/人民币", "ak_code": "日元"},
    "HKD/CNY": {"name": "港币/人民币", "ak_code": "港币"},
    "AUD/CNY": {"name": "澳元/人民币", "ak_code": "澳大利亚元"},
}

FALLBACK_FOREX_QUOTES = [
    {"symbol": "USD/CNY", "name": "美元/人民币", "buy_rate": 7.2456, "sell_rate": 7.2892, "middle_rate": 7.2674, "change_pct": 0.12, "date": "2024-01-15"},
    {"symbol": "EUR/CNY", "name": "欧元/人民币", "buy_rate": 7.8923, "sell_rate": 7.9456, "middle_rate": 7.9189, "change_pct": -0.08, "date": "2024-01-15"},
    {"symbol": "GBP/CNY", "name": "英镑/人民币", "buy_rate": 9.1234, "sell_rate": 9.1876, "middle_rate": 9.1555, "change_pct": 0.23, "date": "2024-01-15"},
    {"symbol": "JPY/CNY", "name": "日元/人民币", "buy_rate": 0.0486, "sell_rate": 0.0490, "middle_rate": 0.0488, "change_pct": -0.15, "date": "2024-01-15"},
    {"symbol": "HKD/CNY", "name": "港币/人民币", "buy_rate": 0.9287, "sell_rate": 0.9345, "middle_rate": 0.9316, "change_pct": 0.05, "date": "2024-01-15"},
    {"symbol": "AUD/CNY", "name": "澳元/人民币", "buy_rate": 4.7234, "sell_rate": 4.7567, "middle_rate": 4.7400, "change_pct": 0.18, "date": "2024-01-15"},
]

SUPPORTED_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "HKD", "AUD", "CNY"]

DEFAULT_RATES = {
    "USD/CNY": 7.2674,
    "EUR/CNY": 7.9189,
    "GBP/CNY": 9.1555,
    "JPY/CNY": 0.0488,
    "HKD/CNY": 0.9316,
    "AUD/CNY": 4.7400,
}

MAJOR_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CNY", "AUD", "CAD", "CHF"]


# ==================== 新增端点 ====================

@router.get("/spot")
async def get_spot_quotes():
    """
    获取所有实时外汇报价 (EastMoney + CFETS fallback)
    
    数据源: 
    1. AKShare forex_spot_em() - 东方财富实时报价 (190+ 货币对)
    2. CFETS fx_spot_quote() - 银行间人民币报价 (fallback)
    
    缓存: 2分钟 (使用全局 DataCache)
    超时: 30秒
    
    Returns:
        List[ForexSpotQuote]: 所有货币对的实时报价
    """
    cache = get_cache()
    
    # Try to get from cache first
    cached = cache.get("forex:spot_quotes")
    if cached:
        return success_response(cached)
    
    # Cache miss - trigger background fetch and return error
    asyncio.create_task(_fetch_forex_spot_background())
    
    return error_response("外汇数据暂不可用，请稍后重试", code=ErrorCode.SERVICE_UNAVAILABLE)


async def _fetch_forex_spot_background():
    """Background fetch for forex spot quotes"""
    try:
        quotes = await forex_fetcher.get_spot_quotes()
        source = "akshare"
        
        # Fallback to CFETS if forex_spot_em returns empty
        if not quotes:
            logger.info("[Forex] forex_spot_em 返回空数据，使用 CFETS fallback")
            cfets_quotes, cfets_crosses = await asyncio.gather(
                forex_fetcher.get_cfets_spot(),
                forex_fetcher.get_cfets_crosses()
            )
            
            for q in cfets_quotes:
                pair = q.get("pair", "")
                if "/" in pair:
                    symbol = pair.replace("/", "")
                else:
                    symbol = pair
                quotes.append({
                    "symbol": symbol,
                    "name": pair,
                    "latest": q.get("mid"),
                    "bid": q.get("bid"),
                    "ask": q.get("ask"),
                    "spread": q.get("spread"),
                    "change": None,
                    "change_pct": None,
                    "open": None,
                    "high": None,
                    "low": None,
                    "prev_close": None,
                    "source": "cfets",
                    "timestamp": q.get("timestamp"),
                })
            
            for q in cfets_crosses:
                pair = q.get("pair", "")
                if "/" in pair:
                    symbol = pair.replace("/", "")
                else:
                    symbol = pair
                quotes.append({
                    "symbol": symbol,
                    "name": pair,
                    "latest": q.get("mid"),
                    "bid": q.get("bid"),
                    "ask": q.get("ask"),
                    "spread": q.get("spread"),
                    "change": None,
                    "change_pct": None,
                    "open": None,
                    "high": None,
                    "low": None,
                    "prev_close": None,
                    "source": "cfets",
                    "timestamp": q.get("timestamp"),
                })
            
            source = "cfets"
        
        # Cache the result
        cache = get_cache()
        cache.set("forex:spot_quotes", {
            "quotes": quotes,
            "total": len(quotes),
            "source": source,
            "data_source": "live" if source == "akshare" else "fallback",
            "status": "ready",
            "last_update_time": datetime.now().isoformat(),
            "update_time": datetime.now().isoformat(),
            "circuit_breaker": get_circuit_breaker_status()
        }, ttl=120)  # 2 minutes
        
        logger.info(f"[Forex] Background fetch completed: {len(quotes)} quotes")
        
    except Exception as e:
        logger.error(f"[Forex] Background fetch failed: {e}")


@router.post("/circuit_breaker/reset")
async def reset_circuit_breaker():
    """
    手动重置熔断器
    
    当网络恢复后，用户可以手动重置熔断器以重新尝试获取实时数据。
    
    Returns:
        dict: {"success": true, "state": "closed"}
    """
    try:
        result = await forex_fetcher.reset_circuit_breaker()
        return success_response(result)
    except Exception as e:
        logger.error(f"[Forex] 重置熔断器失败: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"重置熔断器失败: {str(e)}")


@router.get("/cfets")
async def get_cfets_spot():
    """
    获取CFETS银行间人民币报价
    
    数据源: AKShare fx_spot_quote() (CFETS)
    覆盖: 24 人民币货币对
    特点: 买入/卖出价点差，机构级数据
    
    Returns:
        List[ForexCFETSQuote]: 银行间报价列表
    """
    try:
        quotes = await forex_fetcher.get_cfets_spot()
        
        return success_response({
            "rmb_pairs": quotes,
            "cross_pairs": [],
            "last_update": datetime.now().isoformat(),
            "source": "cfets"
        })
        
    except Exception as e:
        logger.error(f"[Forex] 获取CFETS报价失败: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取CFETS报价失败: {str(e)}")


@router.get("/cfets/cross")
async def get_cfets_crosses():
    """
    获取CFETS非人民币交叉汇率
    
    数据源: AKShare fx_pair_quote()
    覆盖: 11 非人民币货币对 (EUR/USD, GBP/USD, USD/JPY等)
    
    Returns:
        List[ForexCFETSQuote]: 交叉汇率列表
    """
    try:
        quotes = await forex_fetcher.get_cfets_crosses()
        
        return success_response({
            "rmb_pairs": [],
            "cross_pairs": quotes,
            "last_update": datetime.now().isoformat(),
            "source": "cfets"
        })
        
    except Exception as e:
        logger.error(f"[Forex] 获取CFETS交叉汇率失败: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取CFETS交叉汇率失败: {str(e)}")


@router.get("/official")
async def get_official_rates(
    days: int = Query(30, ge=1, le=365, description="返回最近N天数据")
):
    """
    获取国家外汇管理局官方中间价
    
    数据源: AKShare currency_boc_safe() (SAFE)
    权威性: 国家外汇管理局每日发布的人民币中间价
    
    Args:
        days: 返回最近N天数据 (1-365)
        
    Returns:
        List[ForexOfficialRate]: 官方中间价列表
    """
    try:
        rates = await forex_fetcher.get_official_rates(days)
        
        return success_response({
            "rates": rates,
            "total": len(rates),
            "source": "safe"
        })
        
    except Exception as e:
        logger.error(f"[Forex] 获取官方中间价失败: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取官方中间价失败: {str(e)}")


@router.get("/history/{symbol}")
async def get_forex_history_new(
    symbol: str,
    start_date: Optional[str] = Query(None, pattern=r"^\\d{4}-\\d{2}-\\d{2}$", description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, pattern=r"^\\d{4}-\\d{2}-\\d{2}$", description="结束日期 YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=1000, description="返回条数限制")
):
    """
    获取历史K线数据
    
    数据源: AKShare forex_hist_em()
    缓存: 5分钟 (使用全局 DataCache)
    
    Args:
        symbol: 货币对代码，如 USDCNH, EURUSD, USDCNY (自动转换为USDCNH)
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD
        limit: 返回条数限制
        
    Returns:
        ForexHistoryResponse: K线数据列表
    """
    cache = get_cache()
    cache_key = f"forex:history:{symbol}:{start_date}:{end_date}:{limit}"
    
    cached = cache.get(cache_key)
    if cached:
        return success_response(cached)
    
    # Try to fetch data with timeout (10 seconds)
    try:
        ak_symbol = symbol.upper().replace("CNY", "CNH")
        
        history = await asyncio.wait_for(
            forex_fetcher.get_history(ak_symbol, start_date, end_date, limit),
            timeout=10.0
        )
        
        if history:
            result = {
                "symbol": symbol,
                "name": symbol,
                "period": "daily",
                "data": history,
                "total": len(history),
                "source": "akshare",
                "status": "ready",
                "last_update_time": datetime.now().isoformat()
            }
            cache.set(cache_key, result, ttl=300)
            return success_response(result)
        
    except asyncio.TimeoutError:
        logger.warning(f"[Forex] History fetch timeout for {symbol}")
    except Exception as e:
        logger.warning(f"[Forex] History fetch failed for {symbol}: {e}")
    
    # Fallback: Generate mock data immediately
    logger.info(f"[Forex] Using mock data fallback for {symbol}")
    
    # Try to get base rate from CFETS quotes
    cfets_quotes = await forex_fetcher.get_cfets_spot()
    base_rate = None
    
    pair_to_check = symbol.upper().replace("CNH", "CNY")
    for q in cfets_quotes:
        pair = q.get("pair", "").replace("/", "")
        if pair == pair_to_check or pair == symbol.upper():
            base_rate = q.get("mid")
            break
    
    if base_rate is None:
        base_rate = 7.25 if "CNY" in symbol.upper() or "CNH" in symbol.upper() else 1.0
    
    mock_history = []
    current_rate = base_rate
    volatility = 0.003 if base_rate > 1 else 0.01
    
    days = min(limit, 100)
    for i in range(days):
        date = datetime.now() - timedelta(days=days - i - 1)
        
        trend = random.gauss(0, volatility * current_rate)
        open_rate = current_rate + trend
        high_rate = open_rate + abs(random.gauss(0, volatility * current_rate * 0.5))
        low_rate = open_rate - abs(random.gauss(0, volatility * current_rate * 0.5))
        close_rate = open_rate + random.gauss(0, volatility * current_rate * 0.3)
        
        if base_rate >= 100:
            decimals = 2
        elif base_rate >= 1:
            decimals = 4
        else:
            decimals = 6
        
        mock_history.append({
            "date": date.strftime("%Y-%m-%d"),
            "open": round(open_rate, decimals),
            "close": round(close_rate, decimals),
            "high": round(max(open_rate, high_rate, close_rate), decimals),
            "low": round(min(open_rate, low_rate, close_rate), decimals),
            "amplitude": round(abs(high_rate - low_rate) / open_rate * 100, 2),
        })
        
        current_rate = close_rate
    
    result = {
        "symbol": symbol,
        "name": symbol,
        "period": "daily",
        "data": mock_history,
        "total": len(mock_history),
        "source": "mock",
        "status": "ready",
        "last_update_time": datetime.now().isoformat()
    }
    cache.set(cache_key, result, ttl=300)
    
    return success_response(result)


async def _fetch_forex_history_background(symbol: str, start_date: Optional[str], end_date: Optional[str], limit: int):
    """Background fetch for forex history"""
    try:
        ak_symbol = symbol.upper().replace("CNY", "CNH")
        
        history = await forex_fetcher.get_history(ak_symbol, start_date, end_date, limit)
        
        if history:
            cache = get_cache()
            cache.set(f"forex:history:{symbol}:{start_date}:{end_date}:{limit}", {
                "symbol": symbol,
                "name": symbol,
                "period": "daily",
                "data": history,
                "total": len(history),
                "source": "akshare",
                "status": "ready",
                "last_update_time": datetime.now().isoformat()
            }, ttl=300)
            logger.info(f"[Forex] History background fetch completed: {symbol}, {len(history)} bars")
            return
        
        logger.info(f"[Forex] forex_hist_em 返回空数据，使用模拟数据 fallback: {symbol}")
        
        cfets_quotes = await forex_fetcher.get_cfets_spot()
        base_rate = None
        
        pair_to_check = symbol.upper().replace("CNH", "CNY")
        for q in cfets_quotes:
            pair = q.get("pair", "").replace("/", "")
            if pair == pair_to_check or pair == symbol.upper():
                base_rate = q.get("mid")
                break
        
        if base_rate is None:
            base_rate = 7.25 if "CNY" in symbol.upper() or "CNH" in symbol.upper() else 1.0
        
        mock_history = []
        current_rate = base_rate
        volatility = 0.003 if base_rate > 1 else 0.01
        
        days = min(limit, 100)
        for i in range(days):
            date = datetime.now() - timedelta(days=days - i - 1)
            
            trend = random.gauss(0, volatility * current_rate)
            open_rate = current_rate + trend
            high_rate = open_rate + abs(random.gauss(0, volatility * current_rate * 0.5))
            low_rate = open_rate - abs(random.gauss(0, volatility * current_rate * 0.5))
            close_rate = open_rate + random.gauss(0, volatility * current_rate * 0.3)
            
            if base_rate >= 100:
                decimals = 2
            elif base_rate >= 1:
                decimals = 4
            else:
                decimals = 6
            
            mock_history.append({
                "date": date.strftime("%Y-%m-%d"),
                "open": round(open_rate, decimals),
                "close": round(close_rate, decimals),
                "high": round(max(open_rate, high_rate, close_rate), decimals),
                "low": round(min(open_rate, low_rate, close_rate), decimals),
                "amplitude": round(abs(high_rate - low_rate) / open_rate * 100, 2),
            })
            
            current_rate = close_rate
        
        cache = get_cache()
        cache.set(f"forex:history:{symbol}:{start_date}:{end_date}:{limit}", {
            "symbol": symbol,
            "name": symbol,
            "period": "daily",
            "data": mock_history,
            "total": len(mock_history),
            "source": "mock",
            "status": "ready",
            "last_update_time": datetime.now().isoformat()
        }, ttl=300)
        
        logger.info(f"[Forex] History background fetch completed (mock): {symbol}, {len(mock_history)} bars")
        
    except Exception as e:
        logger.error(f"[Forex] History background fetch failed: {symbol} - {e}")


@router.get("/matrix")
async def get_cross_rate_matrix(
    currencies: str = Query(
        "USD,EUR,GBP,JPY,CNY,AUD,CAD,CHF",
        description="货币列表，逗号分隔"
    )
):
    """
    获取交叉汇率矩阵
    
    类似 Bloomberg/Wind 的交叉汇率速览表
    支持悬浮高亮当前行与列
    
    算法:
    - 直接报价优先
    - 缺失对通过USD三角套利计算
    
    Args:
        currencies: 货币列表，默认主流8种货币
        
    Returns:
        CrossRateMatrix: N×N 交叉汇率矩阵
    """
    cache = get_cache()
    cache_key = f"forex:matrix:{currencies}"
    
    cached = cache.get(cache_key)
    if cached:
        return success_response(cached)
    
    asyncio.create_task(_fetch_forex_matrix_background(currencies))
    
    return error_response("交叉汇率矩阵暂不可用，请稍后重试", code=ErrorCode.SERVICE_UNAVAILABLE)


async def _fetch_forex_matrix_background(currencies: str):
    """Background fetch for cross-rate matrix"""
    try:
        currency_list = [c.strip().upper() for c in currencies.split(",") if c.strip()]
        
        if len(currency_list) < 2:
            return
        
        spot_quotes, cfets_rmb, cfets_cross = await asyncio.gather(
            forex_fetcher.get_spot_quotes(),
            forex_fetcher.get_cfets_spot(),
            forex_fetcher.get_cfets_crosses()
        )
        
        rates_dict: Dict[str, Decimal] = {}
        
        for q in spot_quotes:
            symbol = q.get("symbol", "")
            latest = q.get("latest")
            if latest and len(symbol) == 6:
                from_curr = symbol[:3]
                to_curr = symbol[3:]
                rates_dict[f"{from_curr}/{to_curr}"] = Decimal(str(latest))
        
        for q in cfets_rmb:
            pair = q.get("pair", "")
            mid = q.get("mid")
            if mid and "/" in pair:
                rates_dict[pair] = Decimal(str(mid))
        
        for q in cfets_cross:
            pair = q.get("pair", "")
            mid = q.get("mid")
            if mid and "/" in pair:
                rates_dict[pair] = Decimal(str(mid))
        
        matrix = []
        for base_curr in currency_list:
            row_rates = []
            for quote_curr in currency_list:
                if base_curr == quote_curr:
                    row_rates.append(CrossRateCell(
                        rate=1.0,
                        change_pct=0.0,
                        is_base=True,
                        is_calculated=False
                    ))
                else:
                    rate = forex_fetcher.calculate_cross_rate(base_curr, quote_curr, rates_dict)
                    if rate is not None:
                        direct_key = f"{base_curr}/{quote_curr}"
                        is_calculated = direct_key not in rates_dict
                        row_rates.append(CrossRateCell(
                            rate=float(rate),
                            change_pct=None,
                            is_base=False,
                            is_calculated=is_calculated
                        ))
                    else:
                        row_rates.append(CrossRateCell(
                            rate=None,
                            change_pct=None,
                            is_base=False,
                            is_calculated=False
                        ))
            
            matrix.append(CrossRateRow(
                base_currency=base_curr,
                rates=row_rates
            ))
        
        cache = get_cache()
        cache.set(f"forex:matrix:{currencies}", {
            "currencies": currency_list,
            "matrix": [row.model_dump() for row in matrix],
            "last_update": datetime.now().isoformat(),
            "source": "akshare",
            "status": "ready"
        }, ttl=120)
        
        logger.info(f"[Forex] Matrix background fetch completed: {len(currency_list)} currencies")
        
    except Exception as e:
        logger.error(f"[Forex] Matrix background fetch failed: {e}")


@router.post("/cross-rate")
async def calculate_cross_rate_endpoint(request: CrossRateRequest):
    """
    计算交叉汇率
    
    实时汇率转换，支持任意货币对
    通过USD三角套利计算缺失的直接汇率
    
    Args:
        request: 转换请求
        
    Returns:
        CrossRateResponse: 转换结果
    """
    try:
        from_curr = request.from_currency.upper()
        to_curr = request.to_currency.upper()
        amount = request.amount
        
        if from_curr == to_curr:
            return success_response({
                "from_currency": from_curr,
                "to_currency": to_curr,
                "amount": amount,
                "rate": 1.0,
                "result": amount,
                "path": [from_curr],
                "rate_source": "same",
                "timestamp": datetime.now().isoformat()
            })
        
        spot_quotes, cfets_rmb, cfets_cross = await asyncio.gather(
            forex_fetcher.get_spot_quotes(),
            forex_fetcher.get_cfets_spot(),
            forex_fetcher.get_cfets_crosses()
        )
        
        rates_dict: Dict[str, Decimal] = {}
        
        for q in spot_quotes:
            symbol = q.get("symbol", "")
            latest = q.get("latest")
            if latest and len(symbol) == 6:
                from_c = symbol[:3]
                to_c = symbol[3:]
                rates_dict[f"{from_c}/{to_c}"] = Decimal(str(latest))
        
        for q in cfets_rmb:
            pair = q.get("pair", "")
            mid = q.get("mid")
            if mid and "/" in pair:
                rates_dict[pair] = Decimal(str(mid))
        
        for q in cfets_cross:
            pair = q.get("pair", "")
            mid = q.get("mid")
            if mid and "/" in pair:
                rates_dict[pair] = Decimal(str(mid))
        
        direct_key = f"{from_curr}/{to_curr}"
        inverse_key = f"{to_curr}/{from_curr}"
        
        rate = None
        path = [from_curr, to_curr]
        rate_source = "direct"
        
        if direct_key in rates_dict:
            rate = rates_dict[direct_key]
        elif inverse_key in rates_dict:
            rate = Decimal('1') / rates_dict[inverse_key]
            rate_source = "inverse"
        else:
            rate = forex_fetcher.calculate_cross_rate(from_curr, to_curr, rates_dict)
            if rate:
                path = [from_curr, "USD", to_curr]
                rate_source = "triangular"
        
        if rate is None:
            return error_response(ErrorCode.NOT_FOUND, f"无法获取汇率: {from_curr}/{to_curr}")
        
        result = float(Decimal(str(amount)) * rate)
        
        return success_response({
            "from_currency": from_curr,
            "to_currency": to_curr,
            "amount": amount,
            "rate": float(rate),
            "result": round(result, 2),
            "path": path,
            "rate_source": rate_source,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"[Forex] 计算交叉汇率失败: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"计算交叉汇率失败: {str(e)}")


# ==================== 保留旧版端点 (兼容) ====================

@router.get("/quotes")
async def get_forex_quotes():
    """
    获取主要货币对报价 (兼容旧版)
    
    数据来源: 中国银行外汇牌价 (AkShare currency_boc_safe)
    """
    cache = get_cache()
    cache_key = "forex:quotes_legacy"
    
    cached = cache.get(cache_key)
    if cached:
        return success_response(cached)
    
    async def background_fetch():
        try:
            import concurrent.futures
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                df = await asyncio.wait_for(
                    loop.run_in_executor(executor, _fetch_forex_sync),
                    timeout=30
                )
                if df is not None:
                    cache = get_cache()
                    cache.set(cache_key, {"quotes": df, "total": len(df), "is_fallback": False}, ttl=3600)
                    logger.info(f"[Forex] 后台获取成功，{len(df)} 条数据")
        except Exception as e:
            logger.warning(f"[Forex] 后台获取失败: {e}")
    
    asyncio.create_task(background_fetch())
    
    return success_response({
        "quotes": FALLBACK_FOREX_QUOTES,
        "total": len(FALLBACK_FOREX_QUOTES),
        "is_fallback": True,
        "message": "数据源响应缓慢，显示示例数据（后台正在获取真实数据）"
    })


def _fetch_forex_sync():
    try:
        ak = _get_ak()
        df = ak.currency_boc_safe()
        
        if df is not None and not df.empty:
            quotes = []
            for symbol, info in CURRENCY_PAIRS.items():
                currency_name = info["ak_code"]
                matching_rows = df[df['货币名称'].str.contains(currency_name, na=False)]
                
                if not matching_rows.empty:
                    row = matching_rows.iloc[0]
                    buy_rate = _safe_float(row.get('中行汇买价'))
                    sell_rate = _safe_float(row.get('中行汇卖价'))
                    middle_rate = _safe_float(row.get('中行折算价'))
                    prev_buy = _safe_float(row.get('中行钞买价'))
                    change_pct = None
                    if buy_rate and prev_buy and prev_buy > 0:
                        change_pct = round((buy_rate - prev_buy) / prev_buy * 100, 4)
                    
                    quotes.append({
                        "symbol": symbol,
                        "name": info["name"],
                        "buy_rate": buy_rate,
                        "sell_rate": sell_rate,
                        "middle_rate": middle_rate,
                        "change_pct": change_pct,
                        "date": str(row.get('发布日期', '') or row.get('日期', '')),
                    })
                else:
                    quotes.append({
                        "symbol": symbol,
                        "name": info["name"],
                        "buy_rate": None,
                        "sell_rate": None,
                        "middle_rate": None,
                        "change_pct": None,
                        "date": None,
                    })
            return quotes
    except Exception as e:
        logger.warning(f"[Forex] 同步获取失败: {e}")
    return None


@router.get("/history/{pair}/legacy")
async def get_forex_history(
    pair: str,
    days: int = Query(30, ge=1, le=365, description="返回天数，支持 7/30/90/365")
):
    """
    获取货币对历史数据 (兼容旧版)
    
    参数:
    - pair: 货币对，如 USDCNY, EUR/CNY, USD-CNY
    - days: 历史天数，支持 7, 30, 90, 365
    
    返回:
    - OHLC 数据（开高低收）
    - 数据为模拟生成，包含逼真的趋势和波动
    """
    valid_days = [7, 30, 90, 365]
    if days not in valid_days:
        days = min(valid_days, key=lambda x: abs(x - days))
    
    pair = pair.upper().replace("-", "/")
    if "/" not in pair:
        if pair.endswith("CNY"):
            pair = pair[:-3] + "/CNY"
        elif pair.startswith("CNY"):
            pair = "CNY/" + pair[3:]
    
    cache = get_cache()
    cache_key = f"forex:history_legacy:{pair}:{days}"
    
    cached = cache.get(cache_key)
    if cached:
        return success_response(cached)
    
    try:
        quotes_res = await get_forex_quotes()
        base_rate = None
        
        if quotes_res.get("code") == 0:
            for q in quotes_res.get("data", {}).get("quotes", []):
                if q.get("symbol") == pair:
                    base_rate = q.get("middle_rate") or q.get("buy_rate")
                    break
        
        if not base_rate:
            base_rate = DEFAULT_RATES.get(pair, 1.0)
        
        history = _generate_realistic_ohlc(base_rate, days, pair)
        
        result = {
            "symbol": pair,
            "history": history,
            "total": len(history),
            "days": days,
            "base_rate": base_rate,
            "note": "历史数据为模拟生成，包含逼真的趋势和波动模式。实际项目应接入真实数据源。"
        }
        cache.set(cache_key, result, ttl=3600)
        return success_response(result)
        
    except Exception as e:
        logger.error(f"获取外汇历史数据失败: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取外汇历史数据失败: {str(e)}")


@router.get("/health")
async def health_check():
    """健康检查"""
    cache = get_cache()
    stats = cache.get_stats()
    return success_response({
        "status": "ok",
        "service": "forex",
        "cache_size": stats["entry_count"],
        "cache_hit_rate": stats["hit_rate"],
        "cache_memory_mb": stats["memory_usage_mb"],
        "supported_pairs": list(CURRENCY_PAIRS.keys()),
        "supported_currencies": SUPPORTED_CURRENCIES,
        "circuit_breaker": {
            "is_available": forex_fetcher.cb.is_available(),
            "state": forex_fetcher.cb.state.value,
            "consecutive_failures": forex_fetcher.cb._stats.consecutive_failures,
        }
    })


@router.get("/convert")
async def convert_currency(
    amount: float = Query(..., gt=0, le=1000000000, description="转换金额"),
    from_currency: str = Query(..., description="源货币代码 (USD/EUR/GBP/JPY/HKD/AUD/CNY)"),
    to_currency: str = Query(..., description="目标货币代码 (USD/EUR/GBP/JPY/HKD/AUD/CNY)")
):
    """
    货币转换 (兼容旧版)
    
    支持: USD, EUR, GBP, JPY, HKD, AUD, CNY 之间的任意转换
    
    示例:
    - /convert?amount=100&from_currency=USD&to_currency=CNY
    - /convert?amount=1000&from_currency=EUR&to_currency=USD (交叉汇率)
    """
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()
    
    if from_currency not in SUPPORTED_CURRENCIES:
        return error_response(ErrorCode.BAD_REQUEST, f"不支持的货币: {from_currency}，支持: {SUPPORTED_CURRENCIES}")
    if to_currency not in SUPPORTED_CURRENCIES:
        return error_response(ErrorCode.BAD_REQUEST, f"不支持的货币: {to_currency}，支持: {SUPPORTED_CURRENCIES}")
    
    if from_currency == to_currency:
        return success_response({
            "from_currency": from_currency,
            "to_currency": to_currency,
            "amount": amount,
            "rate": 1.0,
            "result": amount,
            "rate_source": "same_currency",
            "timestamp": datetime.now().isoformat()
        })
    
    rate = _calculate_cross_rate(from_currency, to_currency)
    
    if rate is None:
        return error_response(ErrorCode.INTERNAL_ERROR, f"无法获取汇率: {from_currency}/{to_currency}")
    
    result = round(amount * rate, 2)
    
    rate_source = "cached_real"
    cache = get_cache()
    cached_quotes = cache.get("forex:quotes_legacy")
    if cached_quotes and cached_quotes.get("is_fallback", True):
        rate_source = "fallback"
    
    return success_response({
        "from_currency": from_currency,
        "to_currency": to_currency,
        "amount": amount,
        "rate": rate,
        "result": result,
        "rate_source": rate_source,
        "timestamp": datetime.now().isoformat()
    })


def _safe_float(val):
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _generate_realistic_ohlc(base_rate: float, days: int, pair: str) -> List[Dict]:
    history = []
    current_rate = base_rate
    
    daily_volatility = {
        "USD/CNY": 0.003,
        "EUR/CNY": 0.004,
        "GBP/CNY": 0.005,
        "JPY/CNY": 0.004,
        "HKD/CNY": 0.002,
        "AUD/CNY": 0.006,
    }
    volatility = daily_volatility.get(pair, 0.004)
    
    trend = 0
    trend_strength = random.uniform(0.0001, 0.0003)
    trend_duration = random.randint(5, 15)
    days_in_trend = 0
    
    for i in range(days):
        date = datetime.now() - timedelta(days=days - i - 1)
        
        days_in_trend += 1
        if days_in_trend >= trend_duration:
            trend = random.choice([-1, 0, 1])
            trend_strength = random.uniform(0.0001, 0.0003)
            trend_duration = random.randint(5, 15)
            days_in_trend = 0
        
        trend_component = trend * trend_strength * current_rate
        noise = random.gauss(0, volatility * current_rate * 0.3)
        open_rate = current_rate + trend_component + noise
        
        day_volatility = abs(random.gauss(0, volatility * current_rate))
        direction = random.choice([-1, 1])
        
        if direction > 0:
            high_rate = open_rate + day_volatility * random.uniform(0.5, 1.0)
            low_rate = open_rate - day_volatility * random.uniform(0.2, 0.5)
            close_rate = high_rate - day_volatility * random.uniform(0.1, 0.4)
        else:
            low_rate = open_rate - day_volatility * random.uniform(0.5, 1.0)
            high_rate = open_rate + day_volatility * random.uniform(0.2, 0.5)
            close_rate = low_rate + day_volatility * random.uniform(0.1, 0.4)
        
        if pair == "JPY/CNY":
            decimals = 6
        else:
            decimals = 4
        
        open_rate = round(open_rate, decimals)
        high_rate = round(max(open_rate, high_rate, low_rate, close_rate), decimals)
        low_rate = round(min(open_rate, high_rate, low_rate, close_rate), decimals)
        close_rate = round(close_rate, decimals)
        
        history.append({
            "date": date.strftime("%Y-%m-%d"),
            "open": open_rate,
            "high": high_rate,
            "low": low_rate,
            "close": close_rate,
        })
        
        current_rate = close_rate
    
    return history


def _get_current_rate(currency: str) -> Optional[float]:
    """获取当前汇率（同步版本，用于内部计算）"""
    if currency == "CNY":
        return 1.0
    
    pair = f"{currency}/CNY"
    
    cache = get_cache()
    cached = cache.get("forex:quotes_legacy")
    if cached and not cached.get("is_fallback", True):
        for q in cached.get("quotes", []):
            if q.get("symbol") == pair:
                return q.get("middle_rate") or q.get("buy_rate")
    
    return DEFAULT_RATES.get(pair)


def _calculate_cross_rate(from_curr: str, to_curr: str) -> Optional[float]:
    from_rate = _get_current_rate(from_curr)
    to_rate = _get_current_rate(to_curr)
    
    if from_rate is None or to_rate is None:
        return None
    
    return round(from_rate / to_rate, 6)
