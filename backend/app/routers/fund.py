"""
fund.py — 基金数据路由（Phase 6.1 重构版）

支持:
  - 场内基金 (ETF/LOF): 实时行情、折溢价、K 线
  - 场外公募基金：净值、排行、投资组合、净值历史
  
数据源矩阵（瀑布降级）:
  1. AkShare (东方财富) — 主力
  2. TuShare Pro — 基本面补充  
  3. Sina/Tencent — 行情兜底
  4. Mock — 最终降级
"""
import logging
import time
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
    
    数据源优先级:
    1. AkShare (含 IOPV、折价率)
    2. Sina (纯行情)
    3. Mock (兜底)
    
    返回字段:
    - code: 基金代码
    - name: 基金名称
    - price: 最新价
    - change_pct: 涨跌幅%
    - volume: 成交量
    - amount: 成交额
    - iopv: 净值参考 (IOPV)
    - premium_rate: 折溢价率%
    - source: 数据来源
    """
    logger.info(f"[ETF Info] 请求 {code}")
    
    data = fetcher.get_etf_info(code)
    if not data:
        raise HTTPException(400, f"无法获取 ETF {code} 数据")
    
    return {
        "code": 0,
        "message": "success",
        "data": data,
        "timestamp": int(time.time() * 1000)
    }


@router.get("/etf/history")
async def etf_history(
    code: str = Query(..., description="ETF 代码"),
    period: str = Query("daily", description="周期：daily/weekly/monthly"),
    limit: int = Query(300, description="返回条数"),
):
    """
    获取 ETF 历史 K 线（Sina 数据源）
    """
    logger.info(f"[ETF History] 请求 {code} {period}")
    
    data = fetcher.get_etf_history(code, period, limit)
    
    return {
        "code": 0,
        "message": "success",
        "data": data,
        "timestamp": int(time.time() * 1000)
    }


# ══════════════════════════════════════════════════════════════════════
# 场外公募基金
# ══════════════════════════════════════════════════════════════════════

@router.get("/open/info")
async def open_fund_info(code: str = Query(..., description="基金代码（6 位数字）")):
    """
    获取场外公募基金详细信息
    
    数据源优先级:
    1. AkShare (东方财富)
    2. TuShare Pro
    3. Mock
    
    返回字段:
    - code: 基金代码
    - name: 基金名称
    - type: 基金类型
    - nav: 单位净值
    - nav_change_pct: 日增长率%
    - nav_date: 净值日期
    - scale: 基金规模
    - found_date: 成立日期
    - manager: 基金经理
    - company: 基金公司
    - source: 数据来源
    """
    logger.info(f"[Open Fund Info] 请求 {code}")
    
    data = fetcher.get_fund_info(code)
    if not data:
        raise HTTPException(400, f"无法获取基金 {code} 数据")
    
    return {
        "code": 0,
        "message": "success",
        "data": data,
        "timestamp": int(time.time() * 1000)
    }


@router.get("/open/rank")
async def open_fund_rank(
    type: str = Query("全部", description="基金类型：全部/股票型/混合型/债券型/指数型"),
    limit: int = Query(100, description="返回数量"),
):
    """
    场外基金排行（AkShare）
    
    返回字段:
    - code: 基金代码
    - name: 基金简称
    - nav: 单位净值
    - nav_growthrate: 日增长率%
    - type: 基金类型
    - scale: 基金规模
    - find_date: 成立日期
    - manager: 基金经理
    """
    logger.info(f"[Open Fund Rank] 请求 type={type}")
    
    try:
        import akshare as ak
        df = ak.fund_open_fund_rank_em(symbol=type)
        if df is None or df.empty:
            return {"code": 0, "message": "success", "data": [], "timestamp": int(time.time() * 1000)}
        
        result = []
        for _, row in df.head(limit).iterrows():
            result.append({
                "code": str(row.get("基金代码", "")),
                "name": row.get("基金简称", ""),
                "nav": float(row.get("单位净值", 0) or 0),
                "nav_growthrate": float(row.get("日增长率", 0) or 0),
                "type": row.get("基金类型", ""),
                "scale": row.get("基金规模", ""),
                "find_date": row.get("成立日期", ""),
                "manager": row.get("基金经理", ""),
                "company": row.get("基金公司", ""),
            })
        
        return {"code": 0, "message": "success", "data": result, "timestamp": int(time.time() * 1000)}
    
    except Exception as e:
        logger.error(f"[Open Fund Rank] 获取失败：{e}")
        return {"code": 0, "message": "success", "data": [], "timestamp": int(time.time() * 1000)}


@router.get("/portfolio/{code}")
async def fund_portfolio(code: str):
    """
    获取基金投资组合（重仓股 + 资产配置）
    
    数据源：AkShare
    
    返回字段:
    - quarter: 报告期
    - stocks: 前 10 大重仓股列表
      - code: 股票代码
      - name: 股票名称
      - price: 最新价
      - change_pct: 涨跌幅%
      - ratio: 占净值比%
      - change: 较上期变化%
    - assets: 资产配置列表
      - name: 资产类型
      - ratio: 占净值比例%
    - source: 数据来源
    """
    logger.info(f"[Fund Portfolio] 请求 {code}")
    
    data = fetcher.get_fund_portfolio(code)
    if not data:
        return {"code": 0, "message": "success", "data": {"stocks": [], "assets": []}, "timestamp": int(time.time() * 1000)}
    
    return {
        "code": 0,
        "message": "success",
        "data": {
            "quarter": data.get('quarter', ''),
            "stocks": data.get('stocks', []),
            "assets": data.get('assets', []),
            "source": data.get('source', 'unknown'),
        },
        "timestamp": int(time.time() * 1000)
    }


@router.get("/open/nav/{code}")
async def fund_nav_history(
    code: str,
    period: str = Query("6m", description="周期：1m/3m/6m/1y/3y"),
):
    """
    获取场外基金净值历史
    
    数据源：AkShare
    
    返回字段:
    - date: 日期
    - nav: 单位净值
    - accumulated_nav: 累计净值
    """
    logger.info(f"[Fund NAV History] 请求 {code} {period}")
    
    data = fetcher.get_fund_nav_history(code, period)
    
    return {
        "code": 0,
        "message": "success",
        "data": data,
        "timestamp": int(time.time() * 1000)
    }


# ══════════════════════════════════════════════════════════════════════
# 货币基金
# ══════════════════════════════════════════════════════════════════════

@router.get("/money/rank")
async def money_fund_rank(limit: int = Query(50, description="返回数量")):
    """
    货币基金行情排行（AkShare）
    
    返回字段:
    - code: 基金代码
    - name: 基金简称
    - return_7d: 7 日年化收益率%
    - return_1d: 万份收益
    - manager: 基金经理
    """
    logger.info(f"[Money Fund Rank] 请求 limit={limit}")
    
    try:
        import akshare as ak
        df = ak.fund_money_fund_daily_em()
        if df is None or df.empty:
            return {"code": 0, "message": "success", "data": [], "timestamp": int(time.time() * 1000)}
        
        result = []
        for _, row in df.head(limit).iterrows():
            result.append({
                "code": str(row.get("基金代码", "")),
                "name": row.get("基金简称", ""),
                "return_7d": float(row.get("7 日年化", 0) or 0),
                "return_1d": float(row.get("万份收益", 0) or 0),
                "manager": row.get("基金经理", ""),
            })
        
        return {"code": 0, "message": "success", "data": result, "timestamp": int(time.time() * 1000)}
    
    except Exception as e:
        logger.error(f"[Money Fund Rank] 获取失败：{e}")
        return {"code": 0, "message": "success", "data": [], "timestamp": int(time.time() * 1000)}
