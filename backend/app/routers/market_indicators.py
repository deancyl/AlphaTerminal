"""
Market Indicators Router

Provides market indicator endpoints:
- Fear & Greed Index
- Style Strength
- ERP Spread
- Crowding Analysis

PRD Chapter 5.4-5.7: Market Indicators
"""

import logging
import time
import sqlite3
from fastapi import APIRouter, Query
from typing import Optional

from app.db.fund_database import _get_fund_thread_conn
from app.utils.error_decorator import handle_errors
from app.utils.response import success_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/market-indicators", tags=["market-indicators"])


# ══════════════════════════════════════════════════════════════════════
# Fear & Greed Index
# ══════════════════════════════════════════════════════════════════════


@router.get("/fear-greed")
@handle_errors(module="market_indicators")
async def get_fear_greed_index(
    limit: int = Query(30, ge=1, le=365, description="返回天数"),
):
    """
    获取恐慌贪婪指数历史
    
    PRD Chapter 5.4: 恐贪指数 FGI
    """
    logger.info(f"[FGI] 获取恐慌贪婪指数 limit={limit}")
    start = time.time()
    
    try:
        conn = _get_fund_thread_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                trade_date, composite_score, sentiment_status,
                factor_volatility, factor_safe_haven, factor_margin_ratio,
                factor_volume_deviation, factor_futures_basis, factor_stock_strength
            FROM market_fear_greed_sentiment_history
            ORDER BY trade_date DESC
            LIMIT ?
        """, (limit,))
        
        data = []
        for row in cursor.fetchall():
            data.append({
                "trade_date": row[0],
                "composite_score": row[1],
                "sentiment_status": row[2],
                "factors": {
                    "volatility": row[3],
                    "safe_haven": row[4],
                    "margin_ratio": row[5],
                    "volume_deviation": row[6],
                    "futures_basis": row[7],
                    "stock_strength": row[8],
                }
            })
        
        elapsed = time.time() - start
        logger.info(f"[FGI] 返回 {len(data)} 条记录 elapsed={elapsed:.3f}s")
        
        return success_response({
            "data": data,
            "total": len(data),
        })
        
    except sqlite3.Error as e:
        logger.error(f"[FGI] 数据库错误: {e}", exc_info=True)
        return success_response({
            "data": [],
            "total": 0,
            "error": "数据暂未填充",
        })


# ══════════════════════════════════════════════════════════════════════
# Style Strength
# ══════════════════════════════════════════════════════════════════════


@router.get("/style-strength")
@handle_errors(module="market_indicators")
async def get_style_strength(
    limit: int = Query(60, ge=1, le=365, description="返回天数"),
):
    """
    获取风格强度历史
    
    PRD Chapter 5.5: 风格强度轮动
    """
    logger.info(f"[StyleStrength] 获取风格强度 limit={limit}")
    start = time.time()
    
    try:
        conn = _get_fund_thread_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                trade_date, index_code_num, index_code_den,
                ratio_value, percentile_rank_3y
            FROM market_style_strength_history
            ORDER BY trade_date DESC
            LIMIT ?
        """, (limit,))
        
        data = []
        for row in cursor.fetchall():
            data.append({
                "trade_date": row[0],
                "index_num": row[1],
                "index_den": row[2],
                "ratio": row[3],
                "percentile_3y": row[4],
            })
        
        elapsed = time.time() - start
        logger.info(f"[StyleStrength] 返回 {len(data)} 条记录 elapsed={elapsed:.3f}s")
        
        return success_response({
            "data": data,
            "total": len(data),
        })
        
    except sqlite3.Error as e:
        logger.error(f"[StyleStrength] 数据库错误: {e}", exc_info=True)
        return success_response({
            "data": [],
            "total": 0,
            "error": "数据暂未填充",
        })


# ══════════════════════════════════════════════════════════════════════
# ERP Spread (Equity Risk Premium)
# ══════════════════════════════════════════════════════════════════════


@router.get("/erp-spread")
@handle_errors(module="market_indicators")
async def get_erp_spread(
    index_code: Optional[str] = Query(None, description="指数代码（如：000300）"),
    limit: int = Query(60, ge=1, le=365, description="返回天数"),
):
    """
    获取股权风险溢价历史
    
    PRD Chapter 5.6: ERP 利差
    """
    logger.info(f"[ERP] 获取ERP利差 index={index_code} limit={limit}")
    start = time.time()
    
    try:
        conn = _get_fund_thread_conn()
        cursor = conn.cursor()
        
        if index_code:
            cursor.execute("""
                SELECT 
                    index_code, trade_date, pe_ttm, treasury_yield_10y,
                    erp_spread, moving_mean_10y, std_dev_1y_10y, std_dev_2y_10y,
                    percentile_rank_10y, index_close_price
                FROM bond_equity_yield_spread_history
                WHERE index_code = ?
                ORDER BY trade_date DESC
                LIMIT ?
            """, (index_code, limit))
        else:
            cursor.execute("""
                SELECT 
                    index_code, trade_date, pe_ttm, treasury_yield_10y,
                    erp_spread, moving_mean_10y, std_dev_1y_10y, std_dev_2y_10y,
                    percentile_rank_10y, index_close_price
                FROM bond_equity_yield_spread_history
                ORDER BY trade_date DESC
                LIMIT ?
            """, (limit,))
        
        data = []
        for row in cursor.fetchall():
            data.append({
                "index_code": row[0],
                "trade_date": row[1],
                "pe_ttm": row[2],
                "treasury_yield_10y": row[3],
                "erp_spread": row[4],
                "moving_mean_10y": row[5],
                "std_dev_1y": row[6],
                "std_dev_2y": row[7],
                "percentile_10y": row[8],
                "close_price": row[9],
            })
        
        elapsed = time.time() - start
        logger.info(f"[ERP] 返回 {len(data)} 条记录 elapsed={elapsed:.3f}s")
        
        return success_response({
            "data": data,
            "total": len(data),
        })
        
    except sqlite3.Error as e:
        logger.error(f"[ERP] 数据库错误: {e}", exc_info=True)
        return success_response({
            "data": [],
            "total": 0,
            "error": "数据暂未填充",
        })


# ══════════════════════════════════════════════════════════════════════
# Crowding Analysis
# ══════════════════════════════════════════════════════════════════════


@router.get("/crowding")
@handle_errors(module="market_indicators")
async def get_crowding_analysis(
    asset_code: Optional[str] = Query(None, description="资产代码"),
    category: Optional[str] = Query(None, description="类别"),
    limit: int = Query(60, ge=1, le=365, description="返回天数"),
):
    """
    获取拥挤度分析历史
    
    PRD Chapter 5.7: 拥挤度分析
    """
    logger.info(f"[Crowding] 获取拥挤度分析 asset={asset_code} limit={limit}")
    start = time.time()
    
    try:
        conn = _get_fund_thread_conn()
        cursor = conn.cursor()
        
        conditions = []
        params = []
        
        if asset_code:
            conditions.append("asset_code = ?")
            params.append(asset_code)
        if category:
            conditions.append("category = ?")
            params.append(category)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        cursor.execute(f"""
            SELECT 
                asset_code, trade_date, category, crowding_score
            FROM market_crowding_valuation_history
            WHERE {where_clause}
            ORDER BY trade_date DESC
            LIMIT ?
        """, params + [limit])
        
        data = []
        for row in cursor.fetchall():
            data.append({
                "asset_code": row[0],
                "trade_date": row[1],
                "category": row[2],
                "crowding_score": row[3],
            })
        
        elapsed = time.time() - start
        logger.info(f"[Crowding] 返回 {len(data)} 条记录 elapsed={elapsed:.3f}s")
        
        return success_response({
            "data": data,
            "total": len(data),
        })
        
    except sqlite3.Error as e:
        logger.error(f"[Crowding] 数据库错误: {e}", exc_info=True)
        return success_response({
            "data": [],
            "total": 0,
            "error": "数据暂未填充",
        })


# ══════════════════════════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════════════════════════


@router.get("/summary")
@handle_errors(module="market_indicators")
async def get_indicators_summary():
    """
    获取市场指标汇总
    
    返回最新的 FGI、ERP、拥挤度等指标
    """
    logger.info("[Indicators] 获取市场指标汇总")
    start = time.time()
    
    try:
        conn = _get_fund_thread_conn()
        cursor = conn.cursor()
        
        summary = {}
        
        cursor.execute("""
            SELECT composite_score, sentiment_status, trade_date
            FROM market_fear_greed_sentiment_history
            ORDER BY trade_date DESC LIMIT 1
        """)
        row = cursor.fetchone()
        summary["fear_greed"] = {
            "score": row[0] if row else None,
            "status": row[1] if row else None,
            "date": row[2] if row else None,
        }
        
        cursor.execute("""
            SELECT erp_spread, percentile_rank_10y, trade_date
            FROM bond_equity_yield_spread_history
            ORDER BY trade_date DESC LIMIT 1
        """)
        row = cursor.fetchone()
        summary["erp"] = {
            "spread": row[0] if row else None,
            "percentile": row[1] if row else None,
            "date": row[2] if row else None,
        }
        
        elapsed = time.time() - start
        logger.info(f"[Indicators] 汇总完成 elapsed={elapsed:.3f}s")
        
        return success_response(summary)
        
    except sqlite3.Error as e:
        logger.error(f"[Indicators] 数据库错误: {e}", exc_info=True)
        return success_response({
            "error": "数据暂未填充",
        })
