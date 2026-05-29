"""
期权分析路由 - Options Chain & Greeks API

数据源：
- CFFEX: 沪深300/中证1000股指期权链
- SSE: 上交所ETF期权Greeks

缓存策略：5分钟 TTL
"""

import logging
import asyncio
import re
from datetime import datetime
from fastapi import APIRouter, Query
from app.utils.errors import success_response, error_response, ErrorCode
from app.services.fetchers.options_fetcher import options_fetcher
from app.utils.error_decorator import handle_errors
from app.utils.error_sanitizer import sanitize_error

logger = logging.getLogger(__name__)
router = APIRouter()


def validate_option_symbol(symbol: str) -> str:
    """验证期权品种代码"""
    if not symbol or len(symbol) > 10:
        raise ValueError("无效的期权品种代码")
    if not re.match(r'^[a-z]{2}\d{4}$', symbol.lower()):
        raise ValueError("期权品种代码格式错误")
    return symbol.lower()


def validate_contract_code(code: str) -> str:
    """验证合约代码"""
    if not code or len(code) > 20:
        raise ValueError("无效的合约代码")
    if not re.match(r'^[a-zA-Z0-9]+$', code):
        raise ValueError("合约代码格式错误")
    return code


def validate_exchange(exchange: str) -> str:
    """验证交易所代码"""
    allowed = {"CFFEX", "SSE"}
    if exchange.upper() not in allowed:
        raise ValueError("不支持的交易所")
    return exchange.upper()


@router.get("/options/cffex/chain")
@handle_errors(module="options")
async def get_cffex_chain(
    symbol: str = Query("io2506", description="期权品种代码，如 io2506")
):
    """
    获取CFFEX股指期权链

    返回:
      - symbol: 品种代码
      - name: 品种名称
      - underlying_spot: 标的指数现价
      - expiry_date: 到期日
      - calls: 看涨期权列表 [{code, name, strike, latest, change, change_pct, volume, open_interest, delta, gamma, theta, vega, iv}]
      - puts: 看跌期权列表
      - update_time: 更新时间
    """
    try:
        # 验证期权品种代码
        symbol = validate_option_symbol(symbol)
        
        result = await asyncio.wait_for(
            options_fetcher.get_cffex_chain(symbol), timeout=30.0
        )

        return success_response(
            {
                "symbol": result.get("symbol", symbol),
                "name": result.get("name", ""),
                "underlying_spot": result.get("underlying_spot"),
                "expiry_date": result.get("expiry_date"),
                "calls": result.get("calls", []),
                "puts": result.get("puts", []),
                "update_time": result.get("update_time", ""),
                "source": result.get("source", "unknown"),
            }
        )

    except ValueError as e:
        logger.warning(f"[Options] Invalid symbol: {e}")
        return error_response(ErrorCode.INVALID_PARAMS, str(e))
    except asyncio.TimeoutError:
        logger.warning(f"[Options] CFFEX chain timeout: {symbol}", exc_info=True)
        return error_response(ErrorCode.TIMEOUT_ERROR, "数据获取超时，请稍后重试")
    except Exception as e:
        logger.error(f"[Options] CFFEX chain error: {symbol} - {e}", exc_info=True)
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取期权链失败: {sanitize_error(e)}")


@router.get("/options/greeks")
@handle_errors(module="options")
async def get_greeks(code: str = Query(..., description="合约代码，如 10004023")):
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
        # 验证合约代码
        code = validate_contract_code(code)
        
        result = await asyncio.wait_for(
            options_fetcher.get_sse_greeks(code), timeout=30.0
        )

        return success_response(
            {
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
            }
        )

    except ValueError as e:
        logger.warning(f"[Options] Invalid contract code: {e}")
        return error_response(ErrorCode.INVALID_PARAMS, str(e))
    except asyncio.TimeoutError:
        logger.warning(f"[Options] Greeks timeout: {code}", exc_info=True)
        return error_response(ErrorCode.TIMEOUT_ERROR, "数据获取超时，请稍后重试")
    except Exception as e:
        logger.error(f"[Options] Greeks error: {code} - {e}", exc_info=True)
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取Greeks失败: {sanitize_error(e)}")


@router.get("/options/contracts")
@handle_errors(module="options")
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
        # 验证交易所代码
        exchange = validate_exchange(exchange)
        
        result = await asyncio.wait_for(
            options_fetcher.get_contract_list(exchange),
            timeout=30.0
        )

        return success_response(
            {
                "exchange": result.get("exchange", exchange),
                "contracts": result.get("contracts", []),
                "update_time": result.get("update_time", ""),
            }
        )

    except ValueError as e:
        logger.warning(f"[Options] Invalid exchange: {e}")
        return error_response(ErrorCode.INVALID_PARAMS, str(e))
    except asyncio.TimeoutError:
        logger.warning(f"[Options] Contracts timeout: {exchange}", exc_info=True)
        return error_response(ErrorCode.TIMEOUT_ERROR, "数据获取超时，请稍后重试")
    except Exception as e:
        logger.error(f"[Options] Contracts error: {exchange} - {e}", exc_info=True)
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取合约列表失败: {sanitize_error(e)}")


@router.get("/options/health")
@handle_errors(module="options")
async def options_health():
    """期权数据源健康检查"""
    try:
        is_healthy = options_fetcher.is_healthy()
        return success_response(
            {
                "healthy": is_healthy,
                "circuit_breaker": {
                    "is_open": not is_healthy,
                    "is_available": is_healthy,
                },
                "update_time": datetime.now().strftime("%H:%M:%S"),
            }
        )
    except Exception as e:
        return error_response(ErrorCode.INTERNAL_ERROR, f"健康检查失败: {sanitize_error(e)}")


@router.post("/options/circuit_breaker/reset")
@handle_errors(module="options")
async def reset_options_circuit_breaker():
    """重置期权数据源熔断器"""
    try:
        options_fetcher.cb.reset()
        is_healthy = options_fetcher.is_healthy()
        return success_response(
            {
                "success": True,
                "healthy": is_healthy,
                "circuit_breaker": {
                    "is_open": not is_healthy,
                    "is_available": is_healthy,
                },
                "message": "熔断器已重置",
            }
        )
    except Exception as e:
        logger.error(f"[Options] Circuit breaker reset error: {e}", exc_info=True)
        return error_response(ErrorCode.INTERNAL_ERROR, f"重置熔断器失败: {sanitize_error(e)}")
