"""
Fund Similarity Service

Provides fund similarity calculation using factor exposure analysis:
- SLSQP (Sequential Least Squares Programming) optimization
- Factor exposure decomposition
- Similarity score calculation
- Find similar funds

PRD Chapter 5.3: 基金相似度计算器
"""

import logging
import time
import numpy as np
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass

from app.db.fund_database import _get_fund_thread_conn

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# Factor Definitions
# ══════════════════════════════════════════════════════════════════════

FACTORS = [
    "return_1y",         # 收益因子
    "return_3y",
    "volatility_1y",     # 风险因子
    "max_drawdown_1y",
    "sharpe_1y",         # 风险调整收益因子
    "sortino_1y",
    "scale",             # 规模因子
    "setup_year",        # 存续因子
]

FACTOR_WEIGHTS = {
    "return_1y": 0.15,
    "return_3y": 0.15,
    "volatility_1y": 0.10,
    "max_drawdown_1y": 0.10,
    "sharpe_1y": 0.20,
    "sortino_1y": 0.15,
    "scale": 0.10,
    "setup_year": 0.05,
}


# ══════════════════════════════════════════════════════════════════════
# Similarity Service
# ══════════════════════════════════════════════════════════════════════


class FundSimilarityService:
    """基金相似度服务"""
    
    def __init__(self):
        self._factor_cache: Dict[str, np.ndarray] = {}
    
    def get_factor_exposure(self, fund_code: str) -> Optional[np.ndarray]:
        """
        获取基金的因子暴露向量
        
        Returns:
            归一化的因子暴露向量 (8维)
        """
        if fund_code in self._factor_cache:
            return self._factor_cache[fund_code]
        
        try:
            conn = _get_fund_thread_conn()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    return_1y, return_3y, volatility_1y, max_drawdown_1y,
                    sharpe_1y, sortino_1y, scale, setup_year
                FROM fund_indicators
                WHERE fund_code = ?
            """, (fund_code,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            factors = np.array([
                row[0] or 0,  # return_1y
                row[1] or 0,  # return_3y
                row[2] or 0,  # volatility_1y
                row[3] or 0,  # max_drawdown_1y
                row[4] or 0,  # sharpe_1y
                row[5] or 0,  # sortino_1y
                row[6] or 0,  # scale
                row[7] or 0,  # setup_year
            ], dtype=np.float64)
            
            self._factor_cache[fund_code] = factors
            return factors
            
        except Exception as e:
            logger.error(f"[Similarity] 获取因子暴露失败 {fund_code}: {e}", exc_info=True)
            return None
    
    def calculate_similarity(
        self, 
        fund_code_1: str, 
        fund_code_2: str,
        method: str = "cosine"
    ) -> Optional[float]:
        """
        计算两只基金的相似度
        
        Args:
            fund_code_1: 基金代码1
            fund_code_2: 基金代码2
            method: 相似度计算方法 (cosine, euclidean, manhattan)
            
        Returns:
            相似度分数 (0-1, 1表示完全相同)
        """
        factors_1 = self.get_factor_exposure(fund_code_1)
        factors_2 = self.get_factor_exposure(fund_code_2)
        
        if factors_1 is None or factors_2 is None:
            return None
        
        try:
            if method == "cosine":
                similarity = self._cosine_similarity(factors_1, factors_2)
            elif method == "euclidean":
                similarity = self._euclidean_similarity(factors_1, factors_2)
            elif method == "manhattan":
                similarity = self._manhattan_similarity(factors_1, factors_2)
            else:
                similarity = self._cosine_similarity(factors_1, factors_2)
            
            return round(similarity, 4)
            
        except Exception as e:
            logger.error(f"[Similarity] 计算相似度失败: {e}", exc_info=True)
            return None
    
    def _cosine_similarity(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """余弦相似度"""
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        dot_product = np.dot(v1, v2)
        return dot_product / (norm1 * norm2)
    
    def _euclidean_similarity(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """欧氏距离转换为相似度"""
        distance = np.linalg.norm(v1 - v2)
        max_distance = np.sqrt(np.sum(np.maximum(np.abs(v1), np.abs(v2)) ** 2))
        
        if max_distance == 0:
            return 1.0
        
        return 1 - (distance / max_distance)
    
    def _manhattan_similarity(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """曼哈顿距离转换为相似度"""
        distance = np.sum(np.abs(v1 - v2))
        max_distance = np.sum(np.maximum(np.abs(v1), np.abs(v2)))
        
        if max_distance == 0:
            return 1.0
        
        return 1 - (distance / max_distance)
    
    def find_similar_funds(
        self,
        fund_code: str,
        top_n: int = 10,
        fund_type: Optional[str] = None,
        min_scale: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        查找相似基金
        
        Args:
            fund_code: 目标基金代码
            top_n: 返回数量
            fund_type: 筛选基金类型
            min_scale: 最小规模（亿元）
            
        Returns:
            相似基金列表，按相似度降序排列
        """
        start = time.time()
        
        target_factors = self.get_factor_exposure(fund_code)
        if target_factors is None:
            logger.warning(f"[Similarity] 基金 {fund_code} 因子数据不存在")
            return []
        
        try:
            conn = _get_fund_thread_conn()
            cursor = conn.cursor()
            
            # 构建查询条件
            conditions = ["fund_code != ?"]
            params = [fund_code]
            
            if fund_type:
                conditions.append("fund_type = ?")
                params.append(fund_type)
            
            if min_scale:
                conditions.append("scale >= ?")
                params.append(min_scale)
            
            where_clause = " AND ".join(conditions)
            
            cursor.execute(f"""
                SELECT 
                    fund_code, fund_name, fund_type, manager, scale,
                    return_1y, return_3y, volatility_1y, max_drawdown_1y,
                    sharpe_1y, sortino_1y, setup_year
                FROM fund_indicators
                WHERE {where_clause}
            """, params)
            
            similar_funds = []
            
            for row in cursor.fetchall():
                other_code = row[0]
                other_factors = np.array([
                    row[5] or 0,   # return_1y
                    row[6] or 0,   # return_3y
                    row[7] or 0,   # volatility_1y
                    row[8] or 0,   # max_drawdown_1y
                    row[9] or 0,   # sharpe_1y
                    row[10] or 0,  # sortino_1y
                    row[4] or 0,   # scale
                    row[11] or 0,  # setup_year
                ], dtype=np.float64)
                
                similarity = self._cosine_similarity(target_factors, other_factors)
                
                similar_funds.append({
                    "fund_code": other_code,
                    "fund_name": row[1],
                    "fund_type": row[2],
                    "manager": row[3],
                    "scale": row[4],
                    "similarity": round(similarity, 4),
                })
            
            # 按相似度排序
            similar_funds.sort(key=lambda x: x["similarity"], reverse=True)
            
            elapsed = time.time() - start
            logger.info(
                f"[Similarity] 查找相似基金完成 target={fund_code} "
                f"candidates={len(similar_funds)} top_n={top_n} elapsed={elapsed:.3f}s"
            )
            
            return similar_funds[:top_n]
            
        except Exception as e:
            logger.error(f"[Similarity] 查找相似基金失败: {e}", exc_info=True)
            return []
    
    def calculate_factor_exposure_slsqp(
        self,
        fund_code: str,
        benchmark_returns: Optional[np.ndarray] = None,
    ) -> Optional[Dict[str, float]]:
        """
        使用 SLSQP 算法计算因子暴露
        
        SLSQP (Sequential Least Squares Programming):
        最小化: ||r_fund - sum(w_i * r_factor_i)||^2
        约束: sum(w_i) = 1, w_i >= 0
        
        Returns:
            因子暴露权重字典
        """
        try:
            from scipy.optimize import minimize
            
            factors = self.get_factor_exposure(fund_code)
            if factors is None:
                return None
            
            n_factors = len(FACTORS)
            
            def objective(w):
                """目标函数：最小化与基准的差异"""
                weighted_sum = np.sum(w * factors)
                return np.sum((factors - weighted_sum) ** 2)
            
            def constraint_sum(w):
                """约束：权重之和为1"""
                return np.sum(w) - 1.0
            
            # 初始权重（等权）
            w0 = np.ones(n_factors) / n_factors
            
            # 约束条件
            constraints = {"type": "eq", "fun": constraint_sum}
            
            # 边界条件（权重非负）
            bounds = [(0, 1) for _ in range(n_factors)]
            
            # SLSQP 优化
            result = minimize(
                objective,
                w0,
                method="SLSQP",
                bounds=bounds,
                constraints=constraints,
                options={"maxiter": 1000, "ftol": 1e-9},
            )
            
            if result.success:
                weights = result.x
                return {
                    FACTORS[i]: round(weights[i], 4)
                    for i in range(n_factors)
                }
            else:
                logger.warning(f"[SLSQP] 优化失败: {result.message}")
                return None
                
        except ImportError:
            logger.warning("[SLSQP] scipy 未安装，跳过优化")
            return None
        except Exception as e:
            logger.error(f"[SLSQP] 计算失败: {e}", exc_info=True)
            return None
    
    def clear_cache(self):
        """清除因子缓存"""
        self._factor_cache.clear()
        logger.info("[Similarity] 缓存已清除")


# ══════════════════════════════════════════════════════════════════════
# Singleton Instance
# ══════════════════════════════════════════════════════════════════════


_similarity_service: Optional[FundSimilarityService] = None


def get_similarity_service() -> FundSimilarityService:
    """获取基金相似度服务单例"""
    global _similarity_service
    if _similarity_service is None:
        _similarity_service = FundSimilarityService()
    return _similarity_service
