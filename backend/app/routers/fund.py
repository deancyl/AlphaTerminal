"""
fund.py — 基金数据路由（Phase 6.2 性能优化版）

优化:
- 异步端点（async def）
- 性能日志（耗时统计）
- 并发数据组装
"""
import logging
import time
import asyncio
from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List

from app.services.fund_fetcher import get_fetcher

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/fund", tags=["fund"])

fetcher = get_fetcher()


# ══════════════════════════════════════════════════════════════════════
# 场内基金 (ETF/LOF)
# ══════════════════════════════════════════════════════════════════════

@router.get("/etf/info")
async def etf_info(code: str = Query(..., description="ETF 代码（6 位数字）")):
    """
    获取 ETF 实时行情（含折溢价率）
    
    性能日志:
    - 首次请求：记录 AkShare 实际耗时
    - 缓存命中：记录 < 0.01s
    """
    logger.info(f"[ETF Info] 请求 {code}")
    start = time.time()
    
    data = await fetcher.get_etf_info(code)
    if not data:
        raise HTTPException(400, f"无法获取 ETF {code} 数据")
    
    elapsed = time.time() - start
    logger.info(f"[ETF Info] {code} 完成 elapsed={elapsed:.3f}s source={data.get('source', 'unknown')}")
    
    return {
        "code": 0,
        "message": "success",
        "data": data,
        "timestamp": int(time.time() * 1000),
        "_perf": {"elapsed_s": round(elapsed, 3)}
    }


@router.get("/etf/history")
async def etf_history(
    code: str = Query(..., description="ETF 代码"),
    period: str = Query("daily", description="周期：daily/weekly/monthly"),
    limit: int = Query(300, description="返回条数"),
):
    """获取 ETF 历史 K 线"""
    logger.info(f"[ETF History] 请求 {code} {period}")
    start = time.time()
    
    data = await fetcher.get_etf_history(code, period)
    
    elapsed = time.time() - start
    logger.info(f"[ETF History] {code} 完成 elapsed={elapsed:.3f}s records={len(data)}")
    
    return {
        "code": 0,
        "message": "success",
        "data": data,
        "timestamp": int(time.time() * 1000),
        "_perf": {"elapsed_s": round(elapsed, 3)}
    }


# ══════════════════════════════════════════════════════════════════════
# 场外公募基金
# ══════════════════════════════════════════════════════════════════════

@router.get("/open/info")
async def open_fund_info(code: str = Query(..., description="基金代码（6 位数字）")):
    """获取场外公募基金详细信息"""
    logger.info(f"[Open Fund Info] 请求 {code}")
    start = time.time()
    
    data = await fetcher.get_fund_info(code)
    if not data:
        raise HTTPException(400, f"无法获取基金 {code} 数据")
    
    elapsed = time.time() - start
    logger.info(f"[Open Fund Info] {code} 完成 elapsed={elapsed:.3f}s source={data.get('source', 'unknown')}")
    
    return {
        "code": 0,
        "message": "success",
        "data": data,
        "timestamp": int(time.time() * 1000),
        "_perf": {"elapsed_s": round(elapsed, 3)}
    }


@router.get("/open/rank")
async def open_fund_rank(
    type: str = Query("全部", description="基金类型：全部/股票型/混合型/债券型/指数型"),
    limit: int = Query(100, description="返回数量"),
):
    """场外基金排行"""
    logger.info(f"[Open Fund Rank] 请求 type={type}")
    start = time.time()
    
    data = await fetcher.get_fund_rank(type)
    result = data[:limit] if data else []
    
    elapsed = time.time() - start
    logger.info(f"[Open Fund Rank] {type} 完成 elapsed={elapsed:.3f}s count={len(result)}")
    
    return {
        "code": 0,
        "message": "success",
        "data": result,
        "timestamp": int(time.time() * 1000),
        "_perf": {"elapsed_s": round(elapsed, 3)}
    }


@router.get("/portfolio/{code}")
async def fund_portfolio(code: str):
    """获取基金投资组合（重仓股 + 资产配置）"""
    logger.info(f"[Fund Portfolio] 请求 {code}")
    start = time.time()
    
    data = await fetcher.get_fund_portfolio(code)
    
    elapsed = time.time() - start
    
    if not data:
        logger.warning(f"[Fund Portfolio] {code} 返回空数据 elapsed={elapsed:.3f}s")
        return {
            "code": 0,
            "message": "success",
            "data": {"stocks": [], "assets": [], "source": "none"},
            "timestamp": int(time.time() * 1000),
            "_perf": {"elapsed_s": round(elapsed, 3)}
        }
    
    logger.info(f"[Fund Portfolio] {code} 完成 elapsed={elapsed:.3f}s stocks={len(data.get('stocks', []))}")
    
    return {
        "code": 0,
        "message": "success",
        "data": {
            "quarter": data.get('quarter', ''),
            "stocks": data.get('stocks', []),
            "assets": data.get('assets', []),
            "source": data.get('source', 'unknown'),
        },
        "timestamp": int(time.time() * 1000),
        "_perf": {"elapsed_s": round(elapsed, 3)}
    }


@router.get("/open/nav/{code}")
async def fund_nav_history(
    code: str,
    period: str = Query("6m", description="周期：1m/3m/6m/1y/3y"),
):
    """获取场外基金净值历史"""
    logger.info(f"[Fund NAV History] 请求 {code} {period}")
    start = time.time()
    
    data = await fetcher.get_fund_nav_history(code, period)
    
    elapsed = time.time() - start
    logger.info(f"[Fund NAV History] {code} {period} 完成 elapsed={elapsed:.3f}s records={len(data)}")
    
    return {
        "code": 0,
        "message": "success",
        "data": data,
        "timestamp": int(time.time() * 1000),
        "_perf": {"elapsed_s": round(elapsed, 3)}
    }


# ══════════════════════════════════════════════════════════════════════
# 并发完整数据（新端点）
# ══════════════════════════════════════════════════════════════════════

@router.get("/open/full/{code}")
async def fund_full_data(
    code: str,
    period: str = Query("6m", description="净值历史周期"),
):
    """
    并发获取基金完整数据（信息 + 净值 + 组合）
    
    使用 asyncio.gather 并发请求，总耗时 ≈ max(各请求耗时)
    而不是 sum(各请求耗时)
    """
    logger.info(f"[Fund Full] 请求 {code}")
    start = time.time()
    
    results = await fetcher.get_fund_full_data(code, is_etf=False)
    
    elapsed = time.time() - start
    logger.info(f"[Fund Full] {code} 完成 elapsed={elapsed:.3f}s")
    
    return {
        "code": 0,
        "message": "success",
        "data": results,
        "timestamp": int(time.time() * 1000),
        "_perf": {"elapsed_s": round(elapsed, 3)}
    }


# ══════════════════════════════════════════════════════════════════════
# 货币基金
# ══════════════════════════════════════════════════════════════════════

@router.get("/money/rank")
async def money_fund_rank(limit: int = Query(50, description="返回数量")):
    """货币基金行情排行"""
    logger.info(f"[Money Fund Rank] 请求 limit={limit}")
    start = time.time()
    
    try:
        import akshare as ak
        df = await asyncio.to_thread(ak.fund_money_fund_daily_em)
        
        if df is None or df.empty:
            return {
                "code": 0,
                "message": "success",
                "data": [],
                "timestamp": int(time.time() * 1000)
            }
        
        result = []
        for _, row in df.head(limit).iterrows():
            result.append({
                "code": str(row.get("基金代码", "")),
                "name": row.get("基金简称", ""),
                "return_7d": float(row.get("7 日年化", 0) or 0),
                "return_1d": float(row.get("万份收益", 0) or 0),
                "manager": row.get("基金经理", ""),
            })
        
        elapsed = time.time() - start
        logger.info(f"[Money Fund Rank] 完成 elapsed={elapsed:.3f}s count={len(result)}")
        
        return {
            "code": 0,
            "message": "success",
            "data": result,
            "timestamp": int(time.time() * 1000),
            "_perf": {"elapsed_s": round(elapsed, 3)}
        }
    
    except Exception as e:
        logger.error(f"[Money Fund Rank] 获取失败：{e}")
        return {
            "code": 0,
            "message": "success",
            "data": [],
            "timestamp": int(time.time() * 1000)
        }
