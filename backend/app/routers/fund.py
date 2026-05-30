"""
fund.py — 基金数据路由（Phase 6.2 性能优化版）

优化:
- 异步端点（async def）
- 性能日志（耗时统计）
- 并发数据组装
- 超时保护（asyncio.wait_for）

Wave 1 新增:
- 基金筛选 (screener) 端点
- 多条件过滤、排序、分页
"""

import logging
import time
import asyncio
import re
from typing import Optional
from fastapi import APIRouter, Query, HTTPException

from app.services.fund_fetcher import get_fetcher
from app.services.fund_screener import (
    get_fund_screener,
    FundFilterCriteria,
    FundSortCriteria,
    FundPagination,
)
from app.utils.error_decorator import handle_errors
from app.utils.error_sanitizer import sanitize_error

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/fund", tags=["fund"])

fetcher = get_fetcher()
screener = get_fund_screener()

FUND_API_TIMEOUT = 30.0


def validate_fund_code(code: str) -> str:
    """Validate fund code format (6 digits)."""
    if not re.match(r'^\d{6}$', code):
        raise HTTPException(400, "基金代码格式错误，应为6位数字")
    return code


# ══════════════════════════════════════════════════════════════════════
# 场内基金 (ETF/LOF)
# ══════════════════════════════════════════════════════════════════════


@router.get("/etf/info", summary="获取ETF信息")
@handle_errors(module="fund")
async def etf_info(code: str = Query(..., description="ETF 代码（6 位数字）")):
    """
    获取 ETF 实时行情（含折溢价率）

    性能日志:
    - 首次请求：记录 AkShare 实际耗时
    - 缓存命中：记录 < 0.01s
    """
    code = validate_fund_code(code)
    logger.info(f"[ETF Info] 请求 {code}")
    start = time.time()

    try:
        data = await asyncio.wait_for(
            fetcher.get_etf_info(code),
            timeout=FUND_API_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.error(f"[ETF Info] {code} timeout after {FUND_API_TIMEOUT}s", exc_info=True)
        raise HTTPException(status_code=504, detail="请求超时，请稍后重试")

    if not data:
        raise HTTPException(400, f"无法获取 ETF {code} 数据")

    elapsed = time.time() - start
    logger.info(
        f"[ETF Info] {code} 完成 elapsed={elapsed:.3f}s source={data.get('source', 'unknown')}"
    )

    return {
        "code": 0,
        "message": "success",
        "data": data,
        "timestamp": int(time.time() * 1000),
        "_perf": {"elapsed_s": round(elapsed, 3)},
    }


@router.get("/etf/history")
@handle_errors(module="fund")
async def etf_history(
    code: str = Query(..., description="ETF 代码"),
    period: str = Query("daily", description="周期：daily/weekly/monthly"),
    limit: int = Query(300, description="返回条数"),
):
    """获取 ETF 历史 K 线"""
    logger.info(f"[ETF History] 请求 {code} {period}")
    start = time.time()

    try:
        data = await asyncio.wait_for(
            fetcher.get_etf_history(code, period),
            timeout=FUND_API_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.error(f"[ETF History] {code} timeout after {FUND_API_TIMEOUT}s", exc_info=True)
        raise HTTPException(status_code=504, detail="请求超时，请稍后重试")

    elapsed = time.time() - start
    logger.info(f"[ETF History] {code} 完成 elapsed={elapsed:.3f}s records={len(data)}")

    return {
        "code": 0,
        "message": "success",
        "data": data,
        "timestamp": int(time.time() * 1000),
        "_perf": {"elapsed_s": round(elapsed, 3)},
    }


@router.get("/etf/list", summary="获取ETF列表")
@handle_errors(module="fund")
async def etf_list(
    type: str = Query("全部", description="ETF 类型：全部/股票型/债券型/货币型/商品型/跨境型"),
    limit: int = Query(100, description="返回数量"),
):
    """获取 ETF 列表"""
    logger.info(f"[ETF List] 请求 type={type}")
    start = time.time()

    try:
        data = await asyncio.wait_for(
            fetcher.get_etf_list(type),
            timeout=FUND_API_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.error(f"[ETF List] timeout after {FUND_API_TIMEOUT}s", exc_info=True)
        raise HTTPException(status_code=504, detail="请求超时，请稍后重试")

    result = data[:limit] if data else []

    elapsed = time.time() - start
    logger.info(f"[ETF List] 完成 elapsed={elapsed:.3f}s count={len(result)}")

    return {
        "code": 0,
        "message": "success",
        "data": result,
        "timestamp": int(time.time() * 1000),
        "_perf": {"elapsed_s": round(elapsed, 3)},
    }


@router.get("/ranking", summary="基金收益排名")
@handle_errors(module="fund")
async def fund_ranking(
    type: str = Query("全部", description="基金类型：全部/股票型/混合型/债券型/指数型"),
    sort_by: str = Query("return_1y", description="排序字段：return_1y/return_3y/scale"),
    limit: int = Query(50, description="返回数量"),
):
    """基金收益排名"""
    logger.info(f"[Fund Ranking] 请求 type={type} sort_by={sort_by}")
    start = time.time()

    try:
        data = await asyncio.wait_for(
            fetcher.get_fund_rank(type),
            timeout=FUND_API_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.error(f"[Fund Ranking] timeout after {FUND_API_TIMEOUT}s", exc_info=True)
        raise HTTPException(status_code=504, detail="请求超时，请稍后重试")

    # 根据排序字段排序
    if data:
        if sort_by == "return_1y":
            data = sorted(data, key=lambda x: x.get("return_1y", 0), reverse=True)
        elif sort_by == "return_3y":
            data = sorted(data, key=lambda x: x.get("return_3y", 0), reverse=True)
        elif sort_by == "scale":
            data = sorted(data, key=lambda x: x.get("scale", 0), reverse=True)

    result = data[:limit] if data else []

    elapsed = time.time() - start
    logger.info(f"[Fund Ranking] 完成 elapsed={elapsed:.3f}s count={len(result)}")

    return {
        "code": 0,
        "message": "success",
        "data": result,
        "timestamp": int(time.time() * 1000),
        "_perf": {"elapsed_s": round(elapsed, 3)},
    }


# ══════════════════════════════════════════════════════════════════════
# 场外公募基金
# ══════════════════════════════════════════════════════════════════════


@router.get("/open/info")
@handle_errors(module="fund")
async def open_fund_info(code: str = Query(..., description="基金代码（6 位数字）")):
    """获取场外公募基金详细信息"""
    code = validate_fund_code(code)
    logger.info(f"[Open Fund Info] 请求 {code}")
    start = time.time()

    try:
        data = await asyncio.wait_for(
            fetcher.get_fund_info(code),
            timeout=FUND_API_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.error(f"[Open Fund Info] {code} timeout after {FUND_API_TIMEOUT}s", exc_info=True)
        raise HTTPException(status_code=504, detail="请求超时，请稍后重试")

    if not data:
        raise HTTPException(400, f"无法获取基金 {code} 数据")

    elapsed = time.time() - start
    logger.info(
        f"[Open Fund Info] {code} 完成 elapsed={elapsed:.3f}s source={data.get('source', 'unknown')}"
    )

    return {
        "code": 0,
        "message": "success",
        "data": data,
        "timestamp": int(time.time() * 1000),
        "_perf": {"elapsed_s": round(elapsed, 3)},
    }


@router.get("/open/rank")
@handle_errors(module="fund")
async def open_fund_rank(
    type: str = Query("全部", description="基金类型：全部/股票型/混合型/债券型/指数型"),
    limit: int = Query(100, description="返回数量"),
):
    """场外基金排行"""
    logger.info(f"[Open Fund Rank] 请求 type={type}")
    start = time.time()

    try:
        data = await asyncio.wait_for(
            fetcher.get_fund_rank(type),
            timeout=FUND_API_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.error(f"[Open Fund Rank] {type} timeout after {FUND_API_TIMEOUT}s", exc_info=True)
        raise HTTPException(status_code=504, detail="请求超时，请稍后重试")

    result = data[:limit] if data else []

    elapsed = time.time() - start
    logger.info(
        f"[Open Fund Rank] {type} 完成 elapsed={elapsed:.3f}s count={len(result)}"
    )

    return {
        "code": 0,
        "message": "success",
        "data": result,
        "timestamp": int(time.time() * 1000),
        "_perf": {"elapsed_s": round(elapsed, 3)},
    }


@router.get("/portfolio/{code}")
@handle_errors(module="fund")
async def fund_portfolio(code: str):
    """获取基金投资组合（重仓股 + 资产配置）"""
    logger.info(f"[Fund Portfolio] 请求 {code}")
    start = time.time()

    try:
        data = await asyncio.wait_for(
            fetcher.get_fund_portfolio(code),
            timeout=FUND_API_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.error(f"[Fund Portfolio] {code} timeout after {FUND_API_TIMEOUT}s", exc_info=True)
        raise HTTPException(status_code=504, detail="请求超时，请稍后重试")

    elapsed = time.time() - start

    if not data:
        logger.warning(f"[Fund Portfolio] {code} 返回空数据 elapsed={elapsed:.3f}s")
        return {
            "code": 0,
            "message": "success",
            "data": {"stocks": [], "assets": [], "source": "none"},
            "timestamp": int(time.time() * 1000),
            "_perf": {"elapsed_s": round(elapsed, 3)},
        }

    logger.info(
        f"[Fund Portfolio] {code} 完成 elapsed={elapsed:.3f}s stocks={len(data.get('stocks', []))}"
    )

    return {
        "code": 0,
        "message": "success",
        "data": {
            "quarter": data.get("quarter", ""),
            "stocks": data.get("stocks", []),
            "assets": data.get("assets", []),
            "source": data.get("source", "unknown"),
        },
        "timestamp": int(time.time() * 1000),
        "_perf": {"elapsed_s": round(elapsed, 3)},
    }


@router.get("/open/nav/{code}")
@handle_errors(module="fund")
async def fund_nav_history(
    code: str,
    period: str = Query("6m", description="周期：1m/3m/6m/1y/3y"),
):
    """获取场外基金净值历史"""
    code = validate_fund_code(code)
    logger.info(f"[Fund NAV History] 请求 {code} {period}")
    start = time.time()

    try:
        data = await asyncio.wait_for(
            fetcher.get_fund_nav_history(code, period),
            timeout=FUND_API_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.error(f"[Fund NAV History] {code} timeout after {FUND_API_TIMEOUT}s", exc_info=True)
        raise HTTPException(status_code=504, detail="请求超时，请稍后重试")

    elapsed = time.time() - start
    logger.info(
        f"[Fund NAV History] {code} {period} 完成 elapsed={elapsed:.3f}s records={len(data)}"
    )

    return {
        "code": 0,
        "message": "success",
        "data": data,
        "timestamp": int(time.time() * 1000),
        "_perf": {"elapsed_s": round(elapsed, 3)},
    }


@router.get("/open/returns/{code}")
@handle_errors(module="fund")
async def fund_returns(code: str):
    """
    获取基金阶段收益

    返回: 近1周/1月/3月/6月/1年/2年/3年/今年来/成立来 收益率
    """
    logger.info(f"[Fund Returns] 请求 {code}")
    start = time.time()

    try:
        data = await asyncio.wait_for(
            fetcher.get_fund_returns(code),
            timeout=FUND_API_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.error(f"[Fund Returns] {code} timeout after {FUND_API_TIMEOUT}s", exc_info=True)
        raise HTTPException(status_code=504, detail="请求超时，请稍后重试")

    elapsed = time.time() - start
    logger.info(
        f"[Fund Returns] {code} 完成 elapsed={elapsed:.3f}s source={data.get('source', 'unknown')}"
    )

    return {
        "code": 0,
        "message": "success",
        "data": data,
        "timestamp": int(time.time() * 1000),
        "_perf": {"elapsed_s": round(elapsed, 3)},
    }


@router.get("/open/risk/{code}")
@handle_errors(module="fund")
async def fund_risk_metrics(code: str):
    """
    获取基金风险指标

    返回: 夏普比率、最大回撤、Alpha、Beta、波动率
    """
    logger.info(f"[Fund Risk Metrics] 请求 {code}")
    start = time.time()

    try:
        data = await asyncio.wait_for(
            fetcher.get_fund_risk_metrics(code),
            timeout=FUND_API_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.error(f"[Fund Risk Metrics] {code} timeout after {FUND_API_TIMEOUT}s", exc_info=True)
        raise HTTPException(status_code=504, detail="请求超时，请稍后重试")

    elapsed = time.time() - start
    logger.info(
        f"[Fund Risk Metrics] {code} 完成 elapsed={elapsed:.3f}s source={data.get('source', 'unknown')}"
    )

    return {
        "code": 0,
        "message": "success",
        "data": data,
        "timestamp": int(time.time() * 1000),
        "_perf": {"elapsed_s": round(elapsed, 3)},
    }


# ══════════════════════════════════════════════════════════════════════
# 并发完整数据（新端点）
# ══════════════════════════════════════════════════════════════════════


@router.get("/open/full/{code}")
@handle_errors(module="fund")
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

    try:
        results = await asyncio.wait_for(
            fetcher.get_fund_full_data(code, is_etf=False),
            timeout=FUND_API_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.error(f"[Fund Full] {code} timeout after {FUND_API_TIMEOUT}s", exc_info=True)
        raise HTTPException(status_code=504, detail="请求超时，请稍后重试")

    elapsed = time.time() - start
    logger.info(f"[Fund Full] {code} 完成 elapsed={elapsed:.3f}s")

    return {
        "code": 0,
        "message": "success",
        "data": results,
        "timestamp": int(time.time() * 1000),
        "_perf": {"elapsed_s": round(elapsed, 3)},
    }


# ══════════════════════════════════════════════════════════════════════
# 货币基金
# ══════════════════════════════════════════════════════════════════════


@router.get("/money/rank")
@handle_errors(module="fund")
async def money_fund_rank(limit: int = Query(50, description="返回数量")):
    """货币基金行情排行"""
    logger.info(f"[Money Fund Rank] 请求 limit={limit}")
    start = time.time()

    try:
        import akshare as ak

        df = await asyncio.wait_for(
            asyncio.to_thread(ak.fund_money_fund_daily_em),
            timeout=FUND_API_TIMEOUT
        )

        if df is None or df.empty:
            return {
                "code": 0,
                "message": "success",
                "data": [],
                "timestamp": int(time.time() * 1000),
            }

        result = []
        for _, row in df.head(limit).iterrows():
            result.append(
                {
                    "code": str(row.get("基金代码", "")),
                    "name": row.get("基金简称", ""),
                    "return_7d": float(row.get("7 日年化", 0) or 0),
                    "return_1d": float(row.get("万份收益", 0) or 0),
                    "manager": row.get("基金经理", ""),
                }
            )

        elapsed = time.time() - start
        logger.info(
            f"[Money Fund Rank] 完成 elapsed={elapsed:.3f}s count={len(result)}"
        )

        return {
            "code": 0,
            "message": "success",
            "data": result,
            "timestamp": int(time.time() * 1000),
            "_perf": {"elapsed_s": round(elapsed, 3)},
        }

    except asyncio.TimeoutError:
        logger.error(f"[Money Fund Rank] timeout after {FUND_API_TIMEOUT}s", exc_info=True)
        raise HTTPException(status_code=504, detail="请求超时，请稍后重试")
    except Exception as e:
        logger.error(f"[Money Fund Rank] 获取失败：{e}", exc_info=True)
        return {
            "code": 0,
            "message": "success",
            "data": [],
            "timestamp": int(time.time() * 1000),
        }

        result = []
        for _, row in df.head(limit).iterrows():
            result.append(
                {
                    "code": str(row.get("基金代码", "")),
                    "name": row.get("基金简称", ""),
                    "return_7d": float(row.get("7 日年化", 0) or 0),
                    "return_1d": float(row.get("万份收益", 0) or 0),
                    "manager": row.get("基金经理", ""),
                }
            )

        elapsed = time.time() - start
        logger.info(
            f"[Money Fund Rank] 完成 elapsed={elapsed:.3f}s count={len(result)}"
        )

        return {
            "code": 0,
            "message": "success",
            "data": result,
            "timestamp": int(time.time() * 1000),
            "_perf": {"elapsed_s": round(elapsed, 3)},
        }

    except Exception as e:
        logger.error(f"[Money Fund Rank] 获取失败：{e}", exc_info=True)
        return {
            "code": 0,
            "message": sanitize_error(e),
            "data": [],
            "timestamp": int(time.time() * 1000),
        }


# ══════════════════════════════════════════════════════════════════════
# 基金筛选 (Wave 1 - PRD Chapter 5.1)
# ══════════════════════════════════════════════════════════════════════


@router.get("/screener/screen")
@handle_errors(module="fund")
async def screener_screen(
    # 基金类型
    fund_type: Optional[str] = Query(None, description="基金类型：股票型/混合型/债券型/指数型/QDII"),
    # 规模范围
    scale_min: Optional[float] = Query(None, description="最小规模（亿元）"),
    scale_max: Optional[float] = Query(None, description="最大规模（亿元）"),
    # 收益率范围
    return_1y_min: Optional[float] = Query(None, description="最小1年收益率（%）"),
    return_1y_max: Optional[float] = Query(None, description="最大1年收益率（%）"),
    return_3y_min: Optional[float] = Query(None, description="最小3年收益率（%）"),
    return_3y_max: Optional[float] = Query(None, description="最大3年收益率（%）"),
    return_5y_min: Optional[float] = Query(None, description="最小5年收益率（%）"),
    return_5y_max: Optional[float] = Query(None, description="最大5年收益率（%）"),
    # 风险指标
    max_drawdown_1y_max: Optional[float] = Query(None, description="最大回撤上限（%）"),
    volatility_1y_max: Optional[float] = Query(None, description="波动率上限（%）"),
    # 风险调整收益
    sharpe_1y_min: Optional[float] = Query(None, description="最小夏普比率"),
    sortino_1y_min: Optional[float] = Query(None, description="最小索提诺比率"),
    # 基金经理/公司
    manager: Optional[str] = Query(None, description="基金经理（模糊匹配）"),
    company_name: Optional[str] = Query(None, description="基金公司（模糊匹配）"),
    # 评级
    rating_morningstar_min: Optional[float] = Query(None, description="最小晨星评级"),
    rating_3y_min: Optional[float] = Query(None, description="最小3年评级"),
    # 成立年限
    setup_years_min: Optional[int] = Query(None, description="最小成立年限"),
    # 申购状态
    subscription_status: Optional[str] = Query(None, description="申购状态：开放申购/暂停申购"),
    # 排序
    sort_field: str = Query("return_1y", description="排序字段：return_1y/return_3y/sharpe_1y/scale"),
    sort_order: str = Query("desc", description="排序方向：asc/desc"),
    # 分页
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
):
    """
    基金漏斗筛选
    
    支持多条件过滤、排序、分页
    PRD Chapter 5.1: 基金漏斗筛选
    """
    logger.info(f"[Screener] 筛选请求 type={fund_type} page={page}")
    start = time.time()
    
    # 构建筛选条件
    criteria = FundFilterCriteria(
        fund_type=fund_type,
        scale_min=scale_min,
        scale_max=scale_max,
        return_1y_min=return_1y_min,
        return_1y_max=return_1y_max,
        return_3y_min=return_3y_min,
        return_3y_max=return_3y_max,
        return_5y_min=return_5y_min,
        return_5y_max=return_5y_max,
        max_drawdown_1y_max=max_drawdown_1y_max,
        volatility_1y_max=volatility_1y_max,
        sharpe_1y_min=sharpe_1y_min,
        sortino_1y_min=sortino_1y_min,
        manager=manager,
        company_name=company_name,
        rating_morningstar_min=rating_morningstar_min,
        rating_3y_min=rating_3y_min,
        setup_years_min=setup_years_min,
        subscription_status=subscription_status,
    )
    
    # 构建排序条件
    sort = FundSortCriteria(field=sort_field, order=sort_order)
    
    # 构建分页条件
    pagination = FundPagination(page=page, page_size=page_size)
    
    # 执行筛选
    result = screener.screen(criteria, sort, pagination)
    
    elapsed = time.time() - start
    logger.info(
        f"[Screener] 筛选完成 total={result['total']} "
        f"page={page}/{result['total_pages']} elapsed={elapsed:.3f}s"
    )
    
    return {
        "code": 0,
        "message": "success",
        "data": result,
        "timestamp": int(time.time() * 1000),
        "_perf": {"elapsed_s": round(elapsed, 3)},
    }


@router.get("/screener/types")
@handle_errors(module="fund")
async def screener_types():
    """获取所有基金类型（用于筛选下拉框）"""
    types = screener.get_fund_types()
    return {
        "code": 0,
        "message": "success",
        "data": types,
        "timestamp": int(time.time() * 1000),
    }


@router.get("/screener/companies")
@handle_errors(module="fund")
async def screener_companies():
    """获取所有基金公司（用于筛选下拉框）"""
    companies = screener.get_companies()
    return {
        "code": 0,
        "message": "success",
        "data": companies,
        "timestamp": int(time.time() * 1000),
    }


@router.get("/screener/managers")
@handle_errors(module="fund")
async def screener_managers():
    """获取所有基金经理（用于筛选下拉框）"""
    managers = screener.get_managers()
    return {
        "code": 0,
        "message": "success",
        "data": managers,
        "timestamp": int(time.time() * 1000),
    }


@router.get("/screener/statistics")
@handle_errors(module="fund")
async def screener_statistics():
    """获取基金统计数据"""
    stats = screener.get_statistics()
    return {
        "code": 0,
        "message": "success",
        "data": stats,
        "timestamp": int(time.time() * 1000),
    }


# ══════════════════════════════════════════════════════════════════════
# 基金对比 (Wave 2 - PRD Chapter 5.2)
# ══════════════════════════════════════════════════════════════════════


@router.post("/compare", summary="基金收益对比")
@handle_errors(module="fund")
async def fund_compare(
    codes: str = Query(..., description="基金代码列表，逗号分隔（最多15只）"),
    include_nav: bool = Query(True, description="是否包含净值历史"),
    nav_period: str = Query("1y", description="净值历史周期：1m/3m/6m/1y/3y"),
):
    """
    多基金对比
    
    支持 2-15 只基金对比
    返回：收益对比表、风险对比表、雷达图数据、净值历史
    
    PRD Chapter 5.2: 基金对比（扩展至 15 只）
    """
    from app.services.fund_comparison import get_comparison_service
    
    # 解析代码列表
    fund_codes = [c.strip() for c in codes.split(",") if c.strip()]
    
    if len(fund_codes) < 2:
        raise HTTPException(400, "至少需要 2 只基金进行对比")
    
    if len(fund_codes) > 15:
        raise HTTPException(400, "最多支持 15 只基金对比")
    
    logger.info(f"[Compare] 对比请求 codes={fund_codes}")
    start = time.time()
    
    service = get_comparison_service()
    result = await service.compare_funds(fund_codes, include_nav, nav_period)
    
    elapsed = time.time() - start
    logger.info(
        f"[Compare] 对比完成 funds={result['total']} elapsed={elapsed:.3f}s"
    )
    
    return {
        "code": 0,
        "message": "success",
        "data": result,
        "timestamp": int(time.time() * 1000),
        "_perf": {"elapsed_s": round(elapsed, 3)},
    }


@router.get("/compare/max")
@handle_errors(module="fund")
async def compare_max_limit():
    """获取对比上限（15只）"""
    return {
        "code": 0,
        "message": "success",
        "data": {"max_funds": 15},
        "timestamp": int(time.time() * 1000),
    }


# ══════════════════════════════════════════════════════════════════════
# 基金相似度 (Wave 3 - PRD Chapter 5.3)
# ══════════════════════════════════════════════════════════════════════


@router.get("/similarity/{code1}/{code2}")
@handle_errors(module="fund")
async def calculate_similarity(
    code1: str,
    code2: str,
    method: str = Query("cosine", description="相似度计算方法：cosine/euclidean/manhattan"),
):
    """
    计算两只基金的相似度
    
    返回: 相似度分数 (0-1, 1表示完全相同)
    
    PRD Chapter 5.3: 基金相似度计算器
    """
    from app.services.fund_similarity import get_similarity_service
    
    logger.info(f"[Similarity] 计算相似度 {code1} vs {code2}")
    start = time.time()
    
    service = get_similarity_service()
    similarity = service.calculate_similarity(code1, code2, method)
    
    if similarity is None:
        raise HTTPException(400, f"无法计算基金 {code1} 和 {code2} 的相似度")
    
    elapsed = time.time() - start
    logger.info(f"[Similarity] 相似度: {similarity} elapsed={elapsed:.3f}s")
    
    return {
        "code": 0,
        "message": "success",
        "data": {
            "fund_code_1": code1,
            "fund_code_2": code2,
            "similarity": similarity,
            "method": method,
        },
        "timestamp": int(time.time() * 1000),
        "_perf": {"elapsed_s": round(elapsed, 3)},
    }


@router.get("/similar/{code}")
@handle_errors(module="fund")
async def find_similar_funds(
    code: str,
    top_n: int = Query(10, ge=1, le=50, description="返回数量"),
    fund_type: Optional[str] = Query(None, description="筛选基金类型"),
    min_scale: Optional[float] = Query(None, description="最小规模（亿元）"),
):
    """
    查找相似基金
    
    返回: 相似基金列表，按相似度降序排列
    
    PRD Chapter 5.3: 基金相似度计算器
    """
    from app.services.fund_similarity import get_similarity_service
    
    logger.info(f"[Similar] 查找相似基金 {code} top_n={top_n}")
    start = time.time()
    
    service = get_similarity_service()
    similar_funds = service.find_similar_funds(code, top_n, fund_type, min_scale)
    
    elapsed = time.time() - start
    logger.info(f"[Similar] 找到 {len(similar_funds)} 只相似基金 elapsed={elapsed:.3f}s")
    
    return {
        "code": 0,
        "message": "success",
        "data": {
            "target_fund": code,
            "similar_funds": similar_funds,
            "total": len(similar_funds),
        },
        "timestamp": int(time.time() * 1000),
        "_perf": {"elapsed_s": round(elapsed, 3)},
    }


@router.get("/factor-exposure/{code}")
@handle_errors(module="fund")
async def get_factor_exposure(code: str):
    """
    获取基金因子暴露
    
    使用 SLSQP 算法计算因子权重
    
    PRD Chapter 5.3: 基金相似度计算器
    """
    from app.services.fund_similarity import get_similarity_service, FACTORS
    
    logger.info(f"[FactorExposure] 获取因子暴露 {code}")
    start = time.time()
    
    service = get_similarity_service()
    exposure = service.calculate_factor_exposure_slsqp(code)
    
    if exposure is None:
        raise HTTPException(400, f"无法获取基金 {code} 的因子暴露")
    
    elapsed = time.time() - start
    logger.info(f"[FactorExposure] 完成 elapsed={elapsed:.3f}s")
    
    return {
        "code": 0,
        "message": "success",
        "data": {
            "fund_code": code,
            "factor_exposure": exposure,
            "factors": FACTORS,
        },
        "timestamp": int(time.time() * 1000),
        "_perf": {"elapsed_s": round(elapsed, 3)},
    }
