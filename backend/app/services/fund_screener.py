"""
Fund Screener Service

Provides fund screening functionality with:
- Multi-criteria filtering (fund_type, scale, return, sharpe, etc.)
- Sorting (return_1y, return_3y, sharpe_1y, scale, etc.)
- Pagination
- Data source integration (fund_indicators table + akshare)

PRD Chapter 5.1: 基金漏斗筛选
"""

import sqlite3
import logging
import time
import asyncio
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

from app.db.fund_database import get_fund_conn, _get_fund_thread_conn

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# Filter Criteria
# ══════════════════════════════════════════════════════════════════════


@dataclass
class FundFilterCriteria:
    """基金筛选条件"""
    # 基金类型
    fund_type: Optional[str] = None  # 股票型, 混合型, 债券型, 指数型, QDII, etc.
    
    # 规模范围 (亿元)
    scale_min: Optional[float] = None
    scale_max: Optional[float] = None
    
    # 收益率范围 (%)
    return_1y_min: Optional[float] = None
    return_1y_max: Optional[float] = None
    return_3y_min: Optional[float] = None
    return_3y_max: Optional[float] = None
    return_5y_min: Optional[float] = None
    return_5y_max: Optional[float] = None
    
    # 风险指标
    max_drawdown_1y_max: Optional[float] = None  # 最大回撤上限
    volatility_1y_max: Optional[float] = None    # 波动率上限
    
    # 风险调整收益
    sharpe_1y_min: Optional[float] = None
    sortino_1y_min: Optional[float] = None
    
    # 基金经理
    manager: Optional[str] = None
    
    # 基金公司
    company_name: Optional[str] = None
    
    # 评级
    rating_morningstar_min: Optional[float] = None
    rating_3y_min: Optional[float] = None
    
    # 成立年限
    setup_years_min: Optional[int] = None
    
    # 申购状态
    subscription_status: Optional[str] = None  # 开放申购, 暂停申购


@dataclass
class FundSortCriteria:
    """基金排序条件"""
    field: str = "return_1y"  # return_1y, return_3y, sharpe_1y, scale, max_drawdown_1y
    order: str = "desc"       # asc, desc


@dataclass
class FundPagination:
    """分页参数"""
    page: int = 1
    page_size: int = 20
    
    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size
    
    @property
    def limit(self) -> int:
        return self.page_size


# ══════════════════════════════════════════════════════════════════════
# Screener Service
# ══════════════════════════════════════════════════════════════════════


class FundScreener:
    """基金筛选服务"""
    
    # 支持的排序字段
    SORT_FIELDS = {
        "return_1y": "return_1y",
        "return_3y": "return_3y",
        "return_5y": "return_5y",
        "sharpe_1y": "sharpe_1y",
        "sortino_1y": "sortino_1y",
        "scale": "scale",
        "max_drawdown_1y": "max_drawdown_1y",
        "volatility_1y": "volatility_1y",
        "rating_morningstar": "rating_morningstar",
        "setup_year": "setup_year",
    }
    
    def __init__(self):
        self._cache: Dict[str, Tuple[float, List[Dict]]] = {}
        self._cache_ttl = 300  # 5 minutes
    
    def _build_where_clause(
        self, 
        criteria: FundFilterCriteria
    ) -> Tuple[str, List[Any]]:
        """构建 WHERE 子句和参数"""
        conditions = []
        params = []
        
        # 基金类型
        if criteria.fund_type:
            conditions.append("fund_type = ?")
            params.append(criteria.fund_type)
        
        # 规模范围
        if criteria.scale_min is not None:
            conditions.append("scale >= ?")
            params.append(criteria.scale_min)
        if criteria.scale_max is not None:
            conditions.append("scale <= ?")
            params.append(criteria.scale_max)
        
        # 收益率范围
        if criteria.return_1y_min is not None:
            conditions.append("return_1y >= ?")
            params.append(criteria.return_1y_min)
        if criteria.return_1y_max is not None:
            conditions.append("return_1y <= ?")
            params.append(criteria.return_1y_max)
        if criteria.return_3y_min is not None:
            conditions.append("return_3y >= ?")
            params.append(criteria.return_3y_min)
        if criteria.return_3y_max is not None:
            conditions.append("return_3y <= ?")
            params.append(criteria.return_3y_max)
        if criteria.return_5y_min is not None:
            conditions.append("return_5y >= ?")
            params.append(criteria.return_5y_min)
        if criteria.return_5y_max is not None:
            conditions.append("return_5y <= ?")
            params.append(criteria.return_5y_max)
        
        # 风险指标
        if criteria.max_drawdown_1y_max is not None:
            conditions.append("max_drawdown_1y <= ?")
            params.append(criteria.max_drawdown_1y_max)
        if criteria.volatility_1y_max is not None:
            conditions.append("volatility_1y <= ?")
            params.append(criteria.volatility_1y_max)
        
        # 风险调整收益
        if criteria.sharpe_1y_min is not None:
            conditions.append("sharpe_1y >= ?")
            params.append(criteria.sharpe_1y_min)
        if criteria.sortino_1y_min is not None:
            conditions.append("sortino_1y >= ?")
            params.append(criteria.sortino_1y_min)
        
        # 基金经理
        if criteria.manager:
            conditions.append("manager LIKE ?")
            params.append(f"%{criteria.manager}%")
        
        # 基金公司
        if criteria.company_name:
            conditions.append("company_name LIKE ?")
            params.append(f"%{criteria.company_name}%")
        
        # 评级
        if criteria.rating_morningstar_min is not None:
            conditions.append("rating_morningstar >= ?")
            params.append(criteria.rating_morningstar_min)
        if criteria.rating_3y_min is not None:
            conditions.append("rating_3y >= ?")
            params.append(criteria.rating_3y_min)
        
        # 成立年限
        if criteria.setup_years_min is not None:
            conditions.append("setup_year <= ?")
            params.append(datetime.now().year - criteria.setup_years_min)
        
        # 申购状态
        if criteria.subscription_status:
            conditions.append("subscription_status = ?")
            params.append(criteria.subscription_status)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        return where_clause, params
    
    def _build_order_clause(self, sort: FundSortCriteria) -> str:
        """构建 ORDER BY 子句"""
        field = self.SORT_FIELDS.get(sort.field, "return_1y")
        order = "DESC" if sort.order.lower() == "desc" else "ASC"
        
        # 处理 NULL 值排序
        if order == "DESC":
            return f"{field} DESC NULLS LAST"
        else:
            return f"{field} ASC NULLS FIRST"
    
    def screen(
        self,
        criteria: FundFilterCriteria,
        sort: FundSortCriteria,
        pagination: FundPagination,
    ) -> Dict[str, Any]:
        """
        执行基金筛选
        
        Returns:
            {
                "funds": [...],
                "total": int,
                "page": int,
                "page_size": int,
                "total_pages": int,
            }
        """
        start = time.time()
        
        try:
            conn = _get_fund_thread_conn()
            cursor = conn.cursor()
            
            # 构建 WHERE 子句
            where_clause, params = self._build_where_clause(criteria)
            
            # 构建 ORDER BY 子句
            order_clause = self._build_order_clause(sort)
            
            # 查询总数
            count_sql = f"""
                SELECT COUNT(*) FROM fund_indicators
                WHERE {where_clause}
            """
            cursor.execute(count_sql, params)
            total = cursor.fetchone()[0]
            
            # 查询数据
            data_sql = f"""
                SELECT 
                    fund_code, fund_name, fund_type, manager, scale,
                    return_1y, return_3y, return_5y,
                    volatility_1y, max_drawdown_1y, sharpe_1y, sortino_1y,
                    company_name, rating_morningstar, setup_year,
                    subscription_status, update_time
                FROM fund_indicators
                WHERE {where_clause}
                ORDER BY {order_clause}
                LIMIT ? OFFSET ?
            """
            cursor.execute(data_sql, params + [pagination.limit, pagination.offset])
            
            funds = []
            for row in cursor.fetchall():
                funds.append({
                    "fund_code": row[0],
                    "fund_name": row[1],
                    "fund_type": row[2],
                    "manager": row[3],
                    "scale": row[4],
                    "return_1y": row[5],
                    "return_3y": row[6],
                    "return_5y": row[7],
                    "volatility_1y": row[8],
                    "max_drawdown_1y": row[9],
                    "sharpe_1y": row[10],
                    "sortino_1y": row[11],
                    "company_name": row[12],
                    "rating_morningstar": row[13],
                    "setup_year": row[14],
                    "subscription_status": row[15],
                    "update_time": row[16],
                })
            
            total_pages = (total + pagination.page_size - 1) // pagination.page_size
            
            elapsed = time.time() - start
            logger.info(
                f"[FundScreener] 筛选完成 total={total} page={pagination.page} "
                f"elapsed={elapsed:.3f}s"
            )
            
            return {
                "funds": funds,
                "total": total,
                "page": pagination.page,
                "page_size": pagination.page_size,
                "total_pages": total_pages,
            }
            
        except sqlite3.Error as e:
            logger.error(f"[FundScreener] 数据库错误: {e}", exc_info=True)
            raise
    
    def get_fund_types(self) -> List[str]:
        """获取所有基金类型"""
        try:
            conn = _get_fund_thread_conn()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT DISTINCT fund_type FROM fund_indicators
                WHERE fund_type IS NOT NULL
                ORDER BY fund_type
            """)
            
            return [row[0] for row in cursor.fetchall()]
            
        except sqlite3.Error as e:
            logger.error(f"[FundScreener] 获取基金类型失败: {e}", exc_info=True)
            return []
    
    def get_companies(self) -> List[str]:
        """获取所有基金公司"""
        try:
            conn = _get_fund_thread_conn()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT DISTINCT company_name FROM fund_indicators
                WHERE company_name IS NOT NULL
                ORDER BY company_name
            """)
            
            return [row[0] for row in cursor.fetchall()]
            
        except sqlite3.Error as e:
            logger.error(f"[FundScreener] 获取基金公司失败: {e}", exc_info=True)
            return []
    
    def get_managers(self) -> List[str]:
        """获取所有基金经理"""
        try:
            conn = _get_fund_thread_conn()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT DISTINCT manager FROM fund_indicators
                WHERE manager IS NOT NULL
                ORDER BY manager
            """)
            
            return [row[0] for row in cursor.fetchall()]
            
        except sqlite3.Error as e:
            logger.error(f"[FundScreener] 获取基金经理失败: {e}", exc_info=True)
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取基金统计数据"""
        try:
            conn = _get_fund_thread_conn()
            cursor = conn.cursor()
            
            # 总数
            cursor.execute("SELECT COUNT(*) FROM fund_indicators")
            total = cursor.fetchone()[0]
            
            # 按类型统计
            cursor.execute("""
                SELECT fund_type, COUNT(*) as cnt
                FROM fund_indicators
                WHERE fund_type IS NOT NULL
                GROUP BY fund_type
                ORDER BY cnt DESC
            """)
            by_type = {row[0]: row[1] for row in cursor.fetchall()}
            
            # 按公司统计 (Top 10)
            cursor.execute("""
                SELECT company_name, COUNT(*) as cnt
                FROM fund_indicators
                WHERE company_name IS NOT NULL
                GROUP BY company_name
                ORDER BY cnt DESC
                LIMIT 10
            """)
            by_company = {row[0]: row[1] for row in cursor.fetchall()}
            
            # 平均收益
            cursor.execute("""
                SELECT 
                    AVG(return_1y) as avg_return_1y,
                    AVG(return_3y) as avg_return_3y,
                    AVG(sharpe_1y) as avg_sharpe_1y,
                    AVG(scale) as avg_scale
                FROM fund_indicators
                WHERE return_1y IS NOT NULL
            """)
            row = cursor.fetchone()
            averages = {
                "return_1y": round(row[0], 2) if row[0] else None,
                "return_3y": round(row[1], 2) if row[1] else None,
                "sharpe_1y": round(row[2], 2) if row[2] else None,
                "scale": round(row[3], 2) if row[3] else None,
            }
            
            return {
                "total": total,
                "by_type": by_type,
                "by_company": by_company,
                "averages": averages,
            }
            
        except sqlite3.Error as e:
            logger.error(f"[FundScreener] 获取统计数据失败: {e}", exc_info=True)
            return {}


# ══════════════════════════════════════════════════════════════════════
# Singleton Instance
# ══════════════════════════════════════════════════════════════════════


_fund_screener: Optional[FundScreener] = None


def get_fund_screener() -> FundScreener:
    """获取基金筛选器单例"""
    global _fund_screener
    if _fund_screener is None:
        _fund_screener = FundScreener()
    return _fund_screener
