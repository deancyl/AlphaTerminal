"""
期权分析路由 - Options Chain & Greeks API

数据源：
- CFFEX: 沪深300/中证1000股指期权链
- SSE: 上交所ETF期权Greeks
- Black-Scholes: 本地Greeks计算引擎

缓存策略：5分钟 TTL
"""
import logging
import asyncio
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Query, Body
from pydantic import BaseModel, Field

from app.utils.response import success_response, error_response, ErrorCode
from app.services.fetchers.options_fetcher import options_fetcher
from app.services.options.pricing_engine import BlackScholesEngine
from app.services.options.greeks_calculator import GreeksCalculator

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize engines
bsm_engine = BlackScholesEngine()
greeks_calculator = GreeksCalculator()


class GreeksRequest(BaseModel):
    """Request model for Greeks calculation."""
    S: float = Field(..., gt=0, description="标的资产价格")
    K: float = Field(..., gt=0, description="行权价")
    T: float = Field(..., gt=0, le=10, description="到期时间（年）")
    r: float = Field(..., ge=0, le=1, description="无风险利率（小数，如0.03表示3%）")
    option_type: str = Field(..., pattern="^(call|put)$", description="期权类型：call或put")
    option_price: Optional[float] = Field(None, ge=0, description="期权市场价格（用于计算IV）")
    sigma: Optional[float] = Field(None, gt=0, le=5, description="波动率（小数，如0.2表示20%）")


@router.get("/options/cffex/chain")
async def get_cffex_chain(
    symbol: str = Query("io2506", description="期权品种代码，如 io2506"),
    calculate_greeks: bool = Query(True, description="是否计算Greeks"),
    underlying_price: Optional[float] = Query(None, gt=0, description="标的指数价格（可选，不提供则自动获取）"),
    risk_free_rate: Optional[float] = Query(None, ge=0, le=1, description="无风险利率（可选，默认2.5%）")
):
    """
    获取CFFEX股指期权链（含Greeks）
    
    返回:
      - symbol: 品种代码
      - name: 品种名称
      - calls: 看涨期权列表 [{code, name, strike, latest, change, change_pct, volume, open_interest, delta, gamma, theta, vega, iv}]
      - puts: 看跌期权列表
      - greeks_params: Greeks计算参数
      - update_time: 更新时间
    """
    try:
        result = await asyncio.wait_for(
            options_fetcher.get_cffex_chain(symbol),
            timeout=30.0
        )
        
        # Calculate Greeks if requested
        if calculate_greeks and result.get("calls") or result.get("puts"):
            try:
                # Get underlying price
                if underlying_price is None:
                    underlying_price = await _get_underlying_price(symbol)
                
                if underlying_price and underlying_price > 0:
                    result = greeks_calculator.calculate_chain_greeks(
                        chain_data=result,
                        underlying_price=underlying_price,
                        risk_free_rate=risk_free_rate,
                        contract_code=symbol
                    )
                    logger.info(f"[Options] Calculated Greeks for {symbol} with S={underlying_price}")
                else:
                    logger.warning(f"[Options] Cannot calculate Greeks: invalid underlying price")
                    
            except Exception as e:
                logger.warning(f"[Options] Greeks calculation failed: {e}")
        
        return success_response({
            "symbol": result.get("symbol", symbol),
            "name": result.get("name", ""),
            "calls": result.get("calls", []),
            "puts": result.get("puts", []),
            "greeks_params": result.get("greeks_params"),
            "update_time": result.get("update_time", ""),
            "source": result.get("source", "unknown"),
        })
        
    except asyncio.TimeoutError:
        logger.warning(f"[Options] CFFEX chain timeout: {symbol}")
        return error_response(ErrorCode.TIMEOUT_ERROR, "数据获取超时，请稍后重试")
    except Exception as e:
        logger.error(f"[Options] CFFEX chain error: {symbol} - {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"获取期权链失败: {str(e)}")


@router.post("/options/calculate_greeks")
async def calculate_greeks(request: GreeksRequest):
    """
    计算期权Greeks（Black-Scholes模型）
    
    输入:
      - S: 标的资产价格
      - K: 行权价
      - T: 到期时间（年）
      - r: 无风险利率
      - option_type: 'call' 或 'put'
      - option_price: 期权市场价格（可选，用于计算IV）
      - sigma: 波动率（可选，不提供则使用默认值）
    
    返回:
      - price: 期权理论价格
      - delta: Delta值
      - gamma: Gamma值
      - theta: Theta值（年化）
      - vega: Vega值
      - rho: Rho值
      - iv: 隐含波动率（如果提供了option_price）
    """
    try:
        result = bsm_engine.calculate_greeks_with_iv(
            S=request.S,
            K=request.K,
            T=request.T,
            r=request.r,
            option_type=request.option_type,
            option_price=request.option_price,
            sigma=request.sigma
        )
        
        return success_response({
            "price": round(result.price, 4),
            "delta": round(result.delta, 6),
            "gamma": round(result.gamma, 8),
            "theta": round(result.theta, 4),
            "vega": round(result.vega, 4),
            "rho": round(result.rho, 4),
            "iv": round(result.iv, 6) if result.iv else None,
            "params": {
                "S": request.S,
                "K": request.K,
                "T": request.T,
                "r": request.r,
                "option_type": request.option_type,
                "option_price": request.option_price,
                "sigma": request.sigma,
            }
        })
        
    except Exception as e:
        logger.error(f"[Options] Greeks calculation error: {e}")
        return error_response(ErrorCode.INTERNAL_ERROR, f"Greeks计算失败: {str(e)}")


@router.get("/options/greeks")
async def get_greeks(
    code: str = Query(..., description="合约代码，如 10004023")
):
    """
    获取期权Greeks数据（SSE ETF期权）
    
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
            "pricing_engine": {
                "status": "available",
                "model": "Black-Scholes-Merton",
            },
            "update_time": datetime.now().strftime("%H:%M:%S"),
        })
    except Exception as e:
        return error_response(ErrorCode.INTERNAL_ERROR, f"健康检查失败: {str(e)}")


async def _get_underlying_price(option_symbol: str) -> Optional[float]:
    """
    Get underlying index price for option symbol.
    
    Args:
        option_symbol: Option symbol like 'io2506'
    
    Returns:
        Underlying price or None
    """
    try:
        from app.services.data_fetcher import data_fetcher
        
        underlying_symbol = greeks_calculator.get_underlying_symbol(option_symbol)
        
        quote = await asyncio.wait_for(
            data_fetcher.get_quote(underlying_symbol),
            timeout=10.0
        )
        
        if quote and 'close' in quote:
            return float(quote['close'])
        elif quote and 'price' in quote:
            return float(quote['price'])
        
        return None
        
    except Exception as e:
        logger.warning(f"[Options] Failed to get underlying price for {option_symbol}: {e}")
        return None
