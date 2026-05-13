"""
外汇行情 API
数据来源: AkShare currency_boc_safe (中国银行外汇牌价)
功能: 外汇报价查询、历史数据、货币转换
"""
import logging
import random
import math
from datetime import datetime, timedelta
from fastapi import APIRouter, Query
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from app.utils.response import success_response, error_response, ErrorCode

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/forex", tags=["forex"])

_akshare_module = None

def _get_ak():
    global _akshare_module
    if _akshare_module is None:
        import akshare as ak
        _akshare_module = ak
    return _akshare_module

_cache = {}
_cache_ttl = {}
CACHE_DURATION = 3600  # 1小时缓存

def _get_cache(key):
    if key in _cache and key in _cache_ttl:
        if datetime.now() < _cache_ttl[key]:
            return _cache[key]
    return None

def _set_cache(key, value):
    _cache[key] = value
    _cache_ttl[key] = datetime.now() + timedelta(seconds=CACHE_DURATION)

class ForexQuote(BaseModel):
    symbol: str
    name: str
    buy_rate: Optional[float] = None
    sell_rate: Optional[float] = None
    middle_rate: Optional[float] = None
    change_pct: Optional[float] = None
    date: Optional[str] = None

class ForexQuotesResponse(BaseModel):
    quotes: List[ForexQuote]
    total: int

class OHLCData(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: Optional[int] = None

class ConvertRequest(BaseModel):
    amount: float = Field(..., gt=0, description="转换金额")
    from_currency: str = Field(..., description="源货币代码")
    to_currency: str = Field(..., description="目标货币代码")

class ConvertResponse(BaseModel):
    from_currency: str
    to_currency: str
    amount: float
    rate: float
    result: float
    rate_source: str
    timestamp: str

# 主要货币对映射（中行外汇牌价）
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

@router.get("/quotes")
async def get_forex_quotes():
    """
    获取主要货币对报价
    
    数据来源: 中国银行外汇牌价 (AkShare currency_boc_safe)
    """
    cache_key = "forex_quotes"
    cached = _get_cache(cache_key)
    if cached:
        return success_response(cached)
    
    # Return fallback immediately, fetch real data in background
    async def background_fetch():
        try:
            import concurrent.futures
            import asyncio
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                df = await asyncio.wait_for(
                    loop.run_in_executor(executor, _fetch_forex_sync),
                    timeout=30
                )
                if df is not None:
                    _set_cache(cache_key, {"quotes": df, "total": len(df), "is_fallback": False})
                    logger.info(f"[Forex] 后台获取成功，{len(df)} 条数据")
        except Exception as e:
            logger.warning(f"[Forex] 后台获取失败: {e}")
    
    import asyncio
    asyncio.create_task(background_fetch())
    
    return success_response({
        "quotes": FALLBACK_FOREX_QUOTES,
        "total": len(FALLBACK_FOREX_QUOTES),
        "is_fallback": True,
        "message": "数据源响应缓慢，显示示例数据（后台正在获取真实数据）"
    })

def _fetch_forex_sync():
    """同步获取外汇数据"""
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

@router.get("/history/{pair}")
async def get_forex_history(
    pair: str,
    days: int = Query(30, ge=1, le=365, description="返回天数，支持 7/30/90/365")
):
    """
    获取货币对历史数据
    
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
    
    cache_key = f"forex_history_{pair}_{days}"
    cached = _get_cache(cache_key)
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
        _set_cache(cache_key, result)
        return success_response(result)
        
    except Exception as e:
        logger.error(f"获取外汇历史数据失败: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取外汇历史数据失败: {str(e)}")

@router.get("/health")
async def health_check():
    """健康检查"""
    return success_response({
        "status": "ok",
        "service": "forex",
        "cache_size": len(_cache),
        "supported_pairs": list(CURRENCY_PAIRS.keys()),
        "supported_currencies": SUPPORTED_CURRENCIES
    })

@router.get("/convert")
async def convert_currency(
    amount: float = Query(..., gt=0, description="转换金额"),
    from_currency: str = Query(..., description="源货币代码 (USD/EUR/GBP/JPY/HKD/AUD/CNY)"),
    to_currency: str = Query(..., description="目标货币代码 (USD/EUR/GBP/JPY/HKD/AUD/CNY)")
):
    """
    货币转换
    
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
    cached_quotes = _get_cache("forex_quotes")
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
    """安全地将值转为float"""
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None

def _generate_realistic_ohlc(base_rate: float, days: int, pair: str) -> List[Dict]:
    """
    生成逼真的OHLC历史数据
    
    特点:
    - 基于当前汇率作为基准
    - 包含趋势、波动、日内振幅
    - OHLC关系符合真实市场规律
    """
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
    """获取货币对CNY的当前汇率"""
    if currency == "CNY":
        return 1.0
    
    pair = f"{currency}/CNY"
    
    cache_key = "forex_quotes"
    cached = _get_cache(cache_key)
    if cached and not cached.get("is_fallback", True):
        for q in cached.get("quotes", []):
            if q.get("symbol") == pair:
                return q.get("middle_rate") or q.get("buy_rate")
    
    return DEFAULT_RATES.get(pair)

def _calculate_cross_rate(from_curr: str, to_curr: str) -> Optional[float]:
    """计算交叉汇率"""
    from_rate = _get_current_rate(from_curr)
    to_rate = _get_current_rate(to_curr)
    
    if from_rate is None or to_rate is None:
        return None
    
    return round(from_rate / to_rate, 6)