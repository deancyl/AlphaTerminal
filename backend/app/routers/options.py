"""
期权分析路由 - Options Chain & Greeks API

数据源：
- CFFEX: 沪深300/中证1000股指期权链
- SSE: 上交所ETF期权Greeks

缓存策略：5分钟 TTL
"""
import logging
import asyncio
from datetime import datetime
from fastapi import APIRouter, Query
from app.utils.response import success_response, error_response, ErrorCode
from app.services.fetchers.options_fetcher import options_fetcher

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/options/cffex/chain")
async def get_cffex_chain(
    symbol: str = Query("io2506", description="期权品种代码，如 io2506")
):
    """
    获取CFFEX股指期权链
    
    返回:
      - symbol: 品种代码
      - name: 品种名称
      - calls: 看涨期权列表 [{code, name, strike, latest, change, change_pct, volume, open_interest, delta, gamma, theta, vega, iv}]
      - puts: 看跌期权列表
      - update_time: 更新时间
    """
    try:
        result = await asyncio.wait_for(
            options_fetcher.get_cffex_chain(symbol),
            timeout=30.0
        )
        
        return success_response({
            "symbol": result.get("symbol", symbol),
            "name": result.get("name", ""),
            "calls": result.get("calls", []),
            "puts": result.get("puts", []),
            "update_time": result.get("update_time", ""),
            "source": result.get("source", "unknown"),
        })
        
    except asyncio.TimeoutError:
        logger.warning(f"[Options] CFFEX chain timeout: {symbol}")
        return error_response(ErrorCode.TIMEOUT_ERROR, "数据获取超时，请稍后重试")
    except Exception as e:
        logger.error(f"[Options] CFFEX chain error: {symbol} - {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取期权链失败: {str(e)}")


@router.get("/options/greeks")
async def get_greeks(
    code: str = Query(..., description="合约代码，如 10004023")
):
    """
    获取期权Greeks数据
    
    返回:
      - code: 合约代码
      - name: 合约名称
      - delta: Delta值
      - gamma: Gamma值
      - theta: Theta值
      - vega: Vega值
      - iv: 隐含波动率
      - price: 最新价
      - strike: 行权价
      - expiry: 到期日
    """
    try:
        result = await asyncio.wait_for(
            options_fetcher.get_sse_greeks(code),
            timeout=30.0
        )
        
        return success_response({
            "code": result.get("code", code),
            "name": result.get("name", ""),
            "delta": result.get("delta"),
            "gamma": result.get("gamma"),
            "theta": result.get("theta"),
            "vega": result.get("vega"),
            "iv": result.get("iv"),
            "price": result.get("price"),
            "strike": result.get("strike"),
            "expiry": result.get("expiry", ""),
            "update_time": result.get("update_time", ""),
            "source": result.get("source", "unknown"),
        })
        
    except asyncio.TimeoutError:
        logger.warning(f"[Options] Greeks timeout: {code}")
        return error_response(ErrorCode.TIMEOUT_ERROR, "数据获取超时，请稍后重试")
    except Exception as e:
        logger.error(f"[Options] Greeks error: {code} - {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取Greeks失败: {str(e)}")


@router.get("/options/contracts")
async def get_contracts(
    exchange: str = Query("CFFEX", description="交易所代码 (CFFEX/SSE)")
):
    """
    获取期权合约列表
    
    返回:
      - exchange: 交易所
      - contracts: 合约列表 [{code, name, type, underlying}]
    """
    try:
        result = await options_fetcher.get_contract_list(exchange)
        
        return success_response({
            "exchange": result.get("exchange", exchange),
            "contracts": result.get("contracts", []),
            "update_time": result.get("update_time", ""),
        })
        
    except Exception as e:
        logger.error(f"[Options] Contracts error: {exchange} - {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取合约列表失败: {str(e)}")


@router.get("/options/health")
async def options_health():
    """期权数据源健康检查"""
    try:
        is_healthy = options_fetcher.is_healthy()
        return success_response({
            "healthy": is_healthy,
            "circuit_breaker": {
                "is_open": not is_healthy,
                "is_available": is_healthy,
            },
            "update_time": datetime.now().strftime("%H:%M:%S"),
        })
    except Exception as e:
        return error_response(ErrorCode.INTERNAL_ERROR, f"健康检查失败: {str(e)}")
