"""
Fund Comparison Service

Provides multi-fund comparison functionality:
- Support for up to 15 funds comparison
- Radar chart data generation
- Returns comparison table
- Risk metrics comparison
- NAV history comparison

PRD Chapter 5.2: 基金对比（扩展至 15 只）
"""

import logging
import time
import asyncio
from typing import Optional, Dict, List, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════════

MAX_COMPARE_FUNDS = 15  # PRD 要求支持 15 只基金对比

# 雷达图维度
RADAR_DIMENSIONS = [
    "return_1y",       # 近1年收益
    "return_3y",       # 近3年收益
    "sharpe_1y",       # 夏普比率
    "max_drawdown",    # 最大回撤（反向，越小越好）
    "scale",           # 基金规模
    "experience",      # 经理经验
]


# ══════════════════════════════════════════════════════════════════════
# Comparison Service
# ══════════════════════════════════════════════════════════════════════


class FundComparisonService:
    """基金对比服务"""
    
    def __init__(self):
        self._cache: Dict[str, Dict] = {}
    
    async def compare_funds(
        self, 
        fund_codes: List[str],
        include_nav_history: bool = True,
        nav_period: str = "1y",
    ) -> Dict[str, Any]:
        """
        对比多只基金
        
        Args:
            fund_codes: 基金代码列表（最多15只）
            include_nav_history: 是否包含净值历史
            nav_period: 净值历史周期
            
        Returns:
            {
                "funds": [...],          # 基金基本信息列表
                "returns_table": {...},  # 收益对比表
                "risk_table": {...},     # 风险指标对比表
                "radar_data": {...},     # 雷达图数据
                "nav_history": {...},    # 净值历史对比（可选）
            }
        """
        start = time.time()
        
        # 校验数量
        if len(fund_codes) > MAX_COMPARE_FUNDS:
            raise ValueError(f"最多支持 {MAX_COMPARE_FUNDS} 只基金对比")
        
        if len(fund_codes) < 2:
            raise ValueError("至少需要 2 只基金进行对比")
        
        logger.info(f"[FundComparison] 开始对比 {len(fund_codes)} 只基金")
        
        try:
            from app.services.fund_fetcher import get_fetcher
            fetcher = get_fetcher()
            
            # 并行获取基金信息
            tasks = [fetcher.get_fund_info(code) for code in fund_codes]
            fund_infos = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 并行获取收益数据
            tasks_returns = [fetcher.get_fund_returns(code) for code in fund_codes]
            fund_returns = await asyncio.gather(*tasks_returns, return_exceptions=True)
            
            # 并行获取净值历史
            nav_histories = {}
            if include_nav_history:
                tasks_nav = [fetcher.get_fund_nav_history(code, nav_period) for code in fund_codes]
                nav_results = await asyncio.gather(*tasks_nav, return_exceptions=True)
                for i, code in enumerate(fund_codes):
                    if not isinstance(nav_results[i], Exception) and nav_results[i]:
                        nav_histories[code] = nav_results[i]
            
            # 组装数据
            funds = []
            for i, code in enumerate(fund_codes):
                if isinstance(fund_infos[i], Exception):
                    logger.warning(f"[FundComparison] 基金 {code} 信息获取失败")
                    continue
                
                info = fund_infos[i] or {}
                returns = fund_returns[i] if not isinstance(fund_returns[i], Exception) else {}
                
                funds.append({
                    "code": code,
                    "name": info.get("name", "-"),
                    "type": info.get("type", "-"),
                    "manager": info.get("manager", "-"),
                    "company": info.get("company", "-"),
                    "scale": info.get("scale"),
                    "nav": info.get("nav"),
                    "nav_date": info.get("nav_date"),
                    "setup_date": info.get("found_date"),
                    "rating": info.get("rating"),
                    **self._extract_returns(returns),
                    **self._extract_risk(info),
                })
            
            # 构建对比表
            returns_table = self._build_returns_table(funds)
            risk_table = self._build_risk_table(funds)
            radar_data = self._build_radar_data(funds)
            
            elapsed = time.time() - start
            logger.info(f"[FundComparison] 对比完成 funds={len(funds)} elapsed={elapsed:.3f}s")
            
            return {
                "funds": funds,
                "returns_table": returns_table,
                "risk_table": risk_table,
                "radar_data": radar_data,
                "nav_history": nav_histories if include_nav_history else None,
                "total": len(funds),
            }
            
        except Exception as e:
            logger.error(f"[FundComparison] 对比失败: {e}", exc_info=True)
            raise
    
    def _extract_returns(self, returns: Dict) -> Dict:
        """提取收益数据"""
        if not returns:
            return {}
        
        r = returns.get("returns", {})
        return {
            "return_1w": r.get("1w"),
            "return_1m": r.get("1m"),
            "return_3m": r.get("3m"),
            "return_6m": r.get("6m"),
            "return_ytd": r.get("ytd"),
            "return_1y": r.get("1y"),
            "return_3y": r.get("3y"),
            "return_5y": r.get("5y"),
        }
    
    def _extract_risk(self, info: Dict) -> Dict:
        """提取风险数据"""
        risk = info.get("risk_metrics", {})
        return {
            "sharpe_1y": risk.get("sharpe_1y"),
            "max_drawdown_1y": risk.get("max_drawdown_1y"),
            "volatility_1y": risk.get("volatility_1y"),
            "alpha": risk.get("alpha"),
            "beta": risk.get("beta"),
        }
    
    def _build_returns_table(self, funds: List[Dict]) -> Dict[str, Any]:
        """构建收益对比表"""
        periods = ["1w", "1m", "3m", "6m", "ytd", "1y", "3y", "5y"]
        
        # 表头：基金名称
        headers = ["收益指标"] + [f"{f['name'][:6]}..." if len(f.get('name', '')) > 6 else f.get('name', '-') for f in funds]
        
        # 表格行
        rows = []
        period_labels = {
            "1w": "近1周", "1m": "近1月", "3m": "近3月", "6m": "近6月",
            "ytd": "今年以来", "1y": "近1年", "3y": "近3年", "5y": "近5年",
        }
        
        for period in periods:
            row = [period_labels.get(period, period)]
            for fund in funds:
                val = fund.get(f"return_{period}")
                if val is not None:
                    row.append(f"{val:.2f}%")
                else:
                    row.append("-")
            rows.append(row)
        
        return {
            "headers": headers,
            "rows": rows,
        }
    
    def _build_risk_table(self, funds: List[Dict]) -> Dict[str, Any]:
        """构建风险指标对比表"""
        headers = ["风险指标"] + [f"{f['name'][:6]}..." if len(f.get('name', '')) > 6 else f.get('name', '-') for f in funds]
        
        metrics = [
            ("夏普比率", "sharpe_1y", "{:.2f}"),
            ("最大回撤", "max_drawdown_1y", "{:.2f}%"),
            ("年化波动率", "volatility_1y", "{:.2f}%"),
            ("Alpha", "alpha", "{:.2f}"),
            ("Beta", "beta", "{:.2f}"),
        ]
        
        rows = []
        for label, key, fmt in metrics:
            row = [label]
            for fund in funds:
                val = fund.get(key)
                if val is not None:
                    row.append(fmt.format(val))
                else:
                    row.append("-")
            rows.append(row)
        
        return {
            "headers": headers,
            "rows": rows,
        }
    
    def _build_radar_data(self, funds: List[Dict]) -> Dict[str, Any]:
        """
        构建雷达图数据
        
        维度说明：
        - return_1y: 近1年收益率（越高越好）
        - return_3y: 近3年收益率（越高越好）
        - sharpe_1y: 夏普比率（越高越好）
        - max_drawdown: 最大回撤（反向，越小越好，所以取负值）
        - scale: 基金规模（归一化）
        - experience: 经理经验年限（从成立日期推算）
        """
        import numpy as np
        
        # 提取原始值
        raw_values = {}
        for dim in RADAR_DIMENSIONS:
            raw_values[dim] = []
            for fund in funds:
                if dim == "max_drawdown":
                    # 最大回撤取负值（因为越小越好）
                    val = fund.get("max_drawdown_1y")
                    raw_values[dim].append(-val if val else 0)
                elif dim == "scale":
                    val = fund.get("scale")
                    raw_values[dim].append(val if val else 0)
                elif dim == "experience":
                    # 从成立日期计算经验年限
                    setup_date = fund.get("setup_date")
                    if setup_date:
                        try:
                            from datetime import datetime
                            setup = datetime.strptime(setup_date, "%Y-%m-%d")
                            years = (datetime.now() - setup).days / 365
                            raw_values[dim].append(years)
                        except:
                            raw_values[dim].append(0)
                    else:
                        raw_values[dim].append(0)
                else:
                    val = fund.get(dim)
                    raw_values[dim].append(val if val else 0)
        
        # 归一化到 0-100
        normalized = {}
        for dim in RADAR_DIMENSIONS:
            values = raw_values[dim]
            if not values:
                normalized[dim] = [50] * len(funds)
                continue
            
            min_val = min(v for v in values if v != 0) if any(v != 0 for v in values) else 0
            max_val = max(values) if max(values) != 0 else 1
            
            if max_val == min_val:
                normalized[dim] = [50] * len(funds)
            else:
                normalized[dim] = [
                    50 + 50 * (v - min_val) / (max_val - min_val) if v != 0 else 50
                    for v in values
                ]
        
        # 构建雷达图数据
        indicator = [
            {"name": "近1年收益", "max": 100},
            {"name": "近3年收益", "max": 100},
            {"name": "夏普比率", "max": 100},
            {"name": "回撤控制", "max": 100},
            {"name": "基金规模", "max": 100},
            {"name": "经理经验", "max": 100},
        ]
        
        series_data = []
        for i, fund in enumerate(funds):
            series_data.append({
                "value": [normalized[dim][i] for dim in RADAR_DIMENSIONS],
                "name": fund.get("name", f"基金{i+1}"),
                "code": fund.get("code"),
            })
        
        return {
            "indicator": indicator,
            "series_data": series_data,
        }


# ══════════════════════════════════════════════════════════════════════
# Singleton Instance
# ══════════════════════════════════════════════════════════════════════


_comparison_service: Optional[FundComparisonService] = None


def get_comparison_service() -> FundComparisonService:
    """获取基金对比服务单例"""
    global _comparison_service
    if _comparison_service is None:
        _comparison_service = FundComparisonService()
    return _comparison_service
