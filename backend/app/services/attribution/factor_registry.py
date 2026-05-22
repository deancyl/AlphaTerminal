"""
Factor Registry for Multi-Factor Attribution Analysis

Provides a centralized registry for factor definitions, categories, and calculations.
"""

import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Union
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class FactorCategory(str, Enum):
    """Factor category enumeration"""

    VALUE = "value"
    GROWTH = "growth"
    QUALITY = "quality"
    MOMENTUM = "momentum"
    TECHNICAL = "technical"
    VOLATILITY = "volatility"
    SENTIMENT = "sentiment"
    SCREENING = "screening"  # 筛选专用因子


@dataclass
class FactorDefinition:
    """Factor definition with metadata and calculation function"""

    id: str
    name: str
    category: FactorCategory
    description: str
    calc_func: Optional[Callable] = None
    params: Dict[str, Any] = field(default_factory=dict)
    unit: str = ""
    higher_is_better: bool = True

    def to_dict(self) -> dict:
        """Convert to dictionary for API response"""
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category.value,
            "description": self.description,
            "params": self.params,
            "unit": self.unit,
            "higher_is_better": self.higher_is_better,
        }


class FactorRegistry:
    """
    Centralized registry for factor definitions.

    Supports:
    - Factor registration with metadata
    - Factor calculation with data
    - Category-based filtering
    """

    def __init__(self):
        self._factors: Dict[str, FactorDefinition] = {}
        self._register_default_factors()

    def register(self, factor: FactorDefinition) -> None:
        """Register a factor definition"""
        if factor.id in self._factors:
            logger.warning(f"[FactorRegistry] Overwriting existing factor: {factor.id}")
        self._factors[factor.id] = factor

    def get_factor(self, factor_id: str) -> Optional[FactorDefinition]:
        """Get a factor by ID"""
        return self._factors.get(factor_id)

    def list_factors(
        self, category: Optional[FactorCategory] = None
    ) -> List[FactorDefinition]:
        """List all factors, optionally filtered by category"""
        if category is None:
            return list(self._factors.values())
        return [f for f in self._factors.values() if f.category == category]

    def list_categories(self) -> List[dict]:
        """List all factor categories with metadata"""
        category_info = {
            FactorCategory.VALUE: {
                "id": "value",
                "name": "价值因子",
                "icon": "💰",
                "description": "估值相关指标",
            },
            FactorCategory.GROWTH: {
                "id": "growth",
                "name": "成长因子",
                "icon": "📈",
                "description": "增长相关指标",
            },
            FactorCategory.QUALITY: {
                "id": "quality",
                "name": "质量因子",
                "icon": "⭐",
                "description": "盈利质量指标",
            },
            FactorCategory.MOMENTUM: {
                "id": "momentum",
                "name": "动量因子",
                "icon": "🚀",
                "description": "价格动量指标",
            },
            FactorCategory.TECHNICAL: {
                "id": "technical",
                "name": "技术因子",
                "icon": "📊",
                "description": "技术分析指标",
            },
            FactorCategory.VOLATILITY: {
                "id": "volatility",
                "name": "波动因子",
                "icon": "📉",
                "description": "波动率相关指标",
            },
            FactorCategory.SENTIMENT: {
                "id": "sentiment",
                "name": "情绪因子",
                "icon": "🧠",
                "description": "市场情绪指标",
            },
            FactorCategory.SCREENING: {
                "id": "screening",
                "name": "筛选因子",
                "icon": "🔍",
                "description": "条件选股专用",
            },
        }
        return [category_info[cat] for cat in FactorCategory]

    def calculate(
        self, factor_id: str, data: pd.DataFrame
    ) -> Optional[Union[np.ndarray, Any]]:
        """
        Calculate factor values for given data.

        Args:
            factor_id: Factor identifier
            data: DataFrame with OHLCV and fundamental data

        Returns:
            Array of factor values, or None if factor not found
        """
        factor = self.get_factor(factor_id)
        if factor is None or factor.calc_func is None:
            return None

        try:
            return factor.calc_func(data, **factor.params)
        except Exception as e:
            logger.error(
                f"[FactorRegistry] Error calculating factor {factor_id}: {e}",
                exc_info=True,
            )
            return None

    def _register_default_factors(self) -> None:
        """Register default factor definitions"""

        # ── Value Factors ─────────────────────────────────────────────
        self.register(
            FactorDefinition(
                id="PE",
                name="市盈率",
                category=FactorCategory.VALUE,
                description="股价/每股收益，衡量估值水平",
                calc_func=self._calc_pe,
                unit="倍",
                higher_is_better=False,
            )
        )

        self.register(
            FactorDefinition(
                id="PB",
                name="市净率",
                category=FactorCategory.VALUE,
                description="股价/每股净资产，衡量相对账面价值",
                calc_func=self._calc_pb,
                unit="倍",
                higher_is_better=False,
            )
        )

        self.register(
            FactorDefinition(
                id="PS",
                name="市销率",
                category=FactorCategory.VALUE,
                description="市值/销售收入，衡量相对营收估值",
                calc_func=self._calc_ps,
                unit="倍",
                higher_is_better=False,
            )
        )

        # ── Growth Factors ────────────────────────────────────────────
        self.register(
            FactorDefinition(
                id="ROE",
                name="净资产收益率",
                category=FactorCategory.GROWTH,
                description="净利润/净资产，衡量股东权益回报",
                calc_func=self._calc_roe,
                unit="%",
                higher_is_better=True,
            )
        )

        self.register(
            FactorDefinition(
                id="ROA",
                name="总资产收益率",
                category=FactorCategory.GROWTH,
                description="净利润/总资产，衡量资产利用效率",
                calc_func=self._calc_roa,
                unit="%",
                higher_is_better=True,
            )
        )

        self.register(
            FactorDefinition(
                id="REVENUE_GROWTH",
                name="营收增长率",
                category=FactorCategory.GROWTH,
                description="同比营收增长率",
                calc_func=self._calc_revenue_growth,
                params={"period": 1},
                unit="%",
                higher_is_better=True,
            )
        )

        self.register(
            FactorDefinition(
                id="PROFIT_GROWTH",
                name="利润增长率",
                category=FactorCategory.GROWTH,
                description="同比净利润增长率",
                calc_func=self._calc_profit_growth,
                params={"period": 1},
                unit="%",
                higher_is_better=True,
            )
        )

        # ── Quality Factors ───────────────────────────────────────────
        self.register(
            FactorDefinition(
                id="GROSS_MARGIN",
                name="毛利率",
                category=FactorCategory.QUALITY,
                description="毛利/营业收入，衡量盈利质量",
                calc_func=self._calc_gross_margin,
                unit="%",
                higher_is_better=True,
            )
        )

        self.register(
            FactorDefinition(
                id="NET_MARGIN",
                name="净利率",
                category=FactorCategory.QUALITY,
                description="净利润/营业收入，衡量盈利能力",
                calc_func=self._calc_net_margin,
                unit="%",
                higher_is_better=True,
            )
        )

        self.register(
            FactorDefinition(
                id="DEBT_RATIO",
                name="资产负债率",
                category=FactorCategory.QUALITY,
                description="负债/资产，衡量财务风险",
                calc_func=self._calc_debt_ratio,
                unit="%",
                higher_is_better=False,
            )
        )

        # ── Momentum Factors ──────────────────────────────────────────
        self.register(
            FactorDefinition(
                id="PRICE_MOMENTUM_1M",
                name="1月动量",
                category=FactorCategory.MOMENTUM,
                description="过去1个月价格涨跌幅",
                calc_func=self._calc_price_momentum,
                params={"period": 20},
                unit="%",
                higher_is_better=True,
            )
        )

        self.register(
            FactorDefinition(
                id="PRICE_MOMENTUM_3M",
                name="3月动量",
                category=FactorCategory.MOMENTUM,
                description="过去3个月价格涨跌幅",
                calc_func=self._calc_price_momentum,
                params={"period": 60},
                unit="%",
                higher_is_better=True,
            )
        )

        self.register(
            FactorDefinition(
                id="PRICE_MOMENTUM_6M",
                name="6月动量",
                category=FactorCategory.MOMENTUM,
                description="过去6个月价格涨跌幅",
                calc_func=self._calc_price_momentum,
                params={"period": 120},
                unit="%",
                higher_is_better=True,
            )
        )

        # ── Technical Factors ────────────────────────────────────────
        self.register(
            FactorDefinition(
                id="MA5",
                name="5日均线",
                category=FactorCategory.TECHNICAL,
                description="5日移动平均线",
                calc_func=self._calc_ma,
                params={"period": 5},
                unit="元",
                higher_is_better=True,
            )
        )

        self.register(
            FactorDefinition(
                id="MA20",
                name="20日均线",
                category=FactorCategory.TECHNICAL,
                description="20日移动平均线",
                calc_func=self._calc_ma,
                params={"period": 20},
                unit="元",
                higher_is_better=True,
            )
        )

        self.register(
            FactorDefinition(
                id="MACD",
                name="MACD指标",
                category=FactorCategory.TECHNICAL,
                description="指数平滑异同移动平均线",
                calc_func=self._calc_macd,
                params={"fast": 12, "slow": 26, "signal": 9},
                unit="",
                higher_is_better=True,
            )
        )

        self.register(
            FactorDefinition(
                id="RSI",
                name="RSI指标",
                category=FactorCategory.TECHNICAL,
                description="相对强弱指标",
                calc_func=self._calc_rsi,
                params={"period": 14},
                unit="",
                higher_is_better=True,
            )
        )

        self.register(
            FactorDefinition(
                id="BOLL",
                name="布林带",
                category=FactorCategory.TECHNICAL,
                description="布林带指标（中轨）",
                calc_func=self._calc_boll,
                params={"period": 20, "std_dev": 2},
                unit="元",
                higher_is_better=True,
            )
        )

        # ── Volatility Factors ───────────────────────────────────────
        self.register(
            FactorDefinition(
                id="VOLATILITY_20D",
                name="20日波动率",
                category=FactorCategory.VOLATILITY,
                description="20日收益率标准差（年化）",
                calc_func=self._calc_volatility,
                params={"period": 20},
                unit="%",
                higher_is_better=False,
            )
        )

        self.register(
            FactorDefinition(
                id="TURNOVER_RATE",
                name="换手率",
                category=FactorCategory.VOLATILITY,
                description="成交量/流通股本",
                calc_func=self._calc_turnover,
                params={"period": 20},
                unit="%",
                higher_is_better=False,
            )
        )

        # ── Sentiment Factors ────────────────────────────────────────
        self.register(
            FactorDefinition(
                id="NEWS_SENTIMENT",
                name="新闻情绪",
                category=FactorCategory.SENTIMENT,
                description="基于新闻的情感分析得分",
                calc_func=self._calc_news_sentiment,
                unit="",
                higher_is_better=True,
            )
        )

        self.register(
            FactorDefinition(
                id="ANALYST_RATING",
                name="分析师评级",
                category=FactorCategory.SENTIMENT,
                description="分析师平均评级（1-5分）",
                calc_func=self._calc_analyst_rating,
                unit="分",
                higher_is_better=True,
            )
        )

        # ── Screening Factors ───────────────────────────────────────────
        self.register(
            FactorDefinition(
                id="macd_golden_cross",
                name="MACD金叉",
                category=FactorCategory.SCREENING,
                description="MACD金叉信号（DIF上穿DEA）",
                calc_func=self._calc_macd_golden_cross,
                params={"fast": 12, "slow": 26, "signal": 9},
                unit="",
                higher_is_better=True,
            )
        )

        self.register(
            FactorDefinition(
                id="rsi_oversold",
                name="RSI超卖",
                category=FactorCategory.SCREENING,
                description="RSI低于30的超卖信号",
                calc_func=self._calc_rsi_oversold,
                params={"period": 14, "threshold": 30},
                unit="",
                higher_is_better=True,
            )
        )

        self.register(
            FactorDefinition(
                id="breakout_ma",
                name="突破均线",
                category=FactorCategory.SCREENING,
                description="价格突破N日均线",
                calc_func=self._calc_breakout_ma,
                params={"period": 20},
                unit="",
                higher_is_better=True,
            )
        )

        self.register(
            FactorDefinition(
                id="foreign_inflow",
                name="外资净流入",
                category=FactorCategory.SCREENING,
                description="北向资金净流入金额",
                calc_func=self._calc_foreign_inflow,
                params={"min_amount": 10000000},
                unit="元",
                higher_is_better=True,
            )
        )

        self.register(
            FactorDefinition(
                id="llm_sentiment",
                name="LLM情绪得分",
                category=FactorCategory.SCREENING,
                description="AI情绪分析得分（0-1）",
                calc_func=self._calc_llm_sentiment,
                params={"min_score": 0.8},
                unit="",
                higher_is_better=True,
            )
        )

        self.register(
            FactorDefinition(
                id="volume_surge",
                name="放量突破",
                category=FactorCategory.SCREENING,
                description="成交量放大超过N倍均量",
                calc_func=self._calc_volume_surge,
                params={"multiplier": 2.0, "period": 20},
                unit="倍",
                higher_is_better=True,
            )
        )

        self.register(
            FactorDefinition(
                id="institution_research",
                name="机构调研",
                category=FactorCategory.SCREENING,
                description="近期机构调研次数",
                calc_func=self._calc_institution_research,
                params={"days": 30},
                unit="次",
                higher_is_better=True,
            )
        )

        self.register(
            FactorDefinition(
                id="new_high",
                name="创新高",
                category=FactorCategory.SCREENING,
                description="创N日新高",
                calc_func=self._calc_new_high,
                params={"period": 60},
                unit="",
                higher_is_better=True,
            )
        )

    # ── Calculation Functions ─────────────────────────────────────────────

    def _calc_pe(self, data: pd.DataFrame) -> np.ndarray:
        """Calculate PE ratio"""
        if "pe" in data.columns:
            return data["pe"].values
        if "close" in data.columns and "eps" in data.columns:
            return (data["close"] / data["eps"].replace(0, np.nan)).values
        return np.full(len(data), np.nan)

    def _calc_pb(self, data: pd.DataFrame) -> np.ndarray:
        """Calculate PB ratio"""
        if "pb" in data.columns:
            return data["pb"].values
        if "close" in data.columns and "bps" in data.columns:
            return (data["close"] / data["bps"].replace(0, np.nan)).values
        return np.full(len(data), np.nan)

    def _calc_ps(self, data: pd.DataFrame) -> np.ndarray:
        """Calculate PS ratio"""
        if "ps" in data.columns:
            return data["ps"].values
        return np.full(len(data), np.nan)

    def _calc_roe(self, data: pd.DataFrame) -> np.ndarray:
        """Calculate ROE"""
        if "roe" in data.columns:
            return data["roe"].values
        return np.full(len(data), np.nan)

    def _calc_roa(self, data: pd.DataFrame) -> np.ndarray:
        """Calculate ROA"""
        if "roa" in data.columns:
            return data["roa"].values
        return np.full(len(data), np.nan)

    def _calc_revenue_growth(self, data: pd.DataFrame, period: int = 1) -> np.ndarray:
        """Calculate revenue growth"""
        if "revenue_growth" in data.columns:
            return data["revenue_growth"].values
        return np.full(len(data), np.nan)

    def _calc_profit_growth(self, data: pd.DataFrame, period: int = 1) -> np.ndarray:
        """Calculate profit growth"""
        if "profit_growth" in data.columns:
            return data["profit_growth"].values
        return np.full(len(data), np.nan)

    def _calc_gross_margin(self, data: pd.DataFrame) -> np.ndarray:
        """Calculate gross margin"""
        if "gross_margin" in data.columns:
            return data["gross_margin"].values
        return np.full(len(data), np.nan)

    def _calc_net_margin(self, data: pd.DataFrame) -> np.ndarray:
        """Calculate net margin"""
        if "net_margin" in data.columns:
            return data["net_margin"].values
        return np.full(len(data), np.nan)

    def _calc_debt_ratio(self, data: pd.DataFrame) -> np.ndarray:
        """Calculate debt ratio"""
        if "debt_ratio" in data.columns:
            return data["debt_ratio"].values
        return np.full(len(data), np.nan)

    def _calc_price_momentum(self, data: pd.DataFrame, period: int = 20) -> np.ndarray:
        """Calculate price momentum"""
        if "close" not in data.columns:
            return np.full(len(data), np.nan)

        closes = data["close"].values
        result = np.full(len(closes), np.nan)

        for i in range(period, len(closes)):
            if closes[i - period] > 0:
                result[i] = (closes[i] - closes[i - period]) / closes[i - period] * 100

        return result

    def _calc_ma(self, data: pd.DataFrame, period: int = 5) -> np.ndarray:
        """Calculate moving average"""
        if "close" not in data.columns:
            return np.full(len(data), np.nan)

        closes = data["close"].values
        result = np.full(len(closes), np.nan)

        for i in range(period - 1, len(closes)):
            result[i] = np.mean(closes[i - period + 1 : i + 1])

        return result

    def _calc_macd(
        self, data: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> np.ndarray:
        """Calculate MACD"""
        if "close" not in data.columns:
            return np.full(len(data), np.nan)

        closes = data["close"].values

        # Calculate EMAs
        def ema(data, period):
            k = 2 / (period + 1)
            result = np.zeros(len(data))
            result[0] = data[0]
            for i in range(1, len(data)):
                result[i] = data[i] * k + result[i - 1] * (1 - k)
            return result

        ema_fast = ema(closes, fast)
        ema_slow = ema(closes, slow)
        dif = ema_fast - ema_slow
        dea = ema(dif, signal)
        macd = (dif - dea) * 2

        return macd

    def _calc_rsi(self, data: pd.DataFrame, period: int = 14) -> np.ndarray:
        """Calculate RSI"""
        if "close" not in data.columns:
            return np.full(len(data), np.nan)

        closes = data["close"].values
        result = np.full(len(closes), np.nan)

        if len(closes) < period + 1:
            return result

        # Calculate price changes
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        # Calculate initial averages
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])

        # Calculate RSI
        for i in range(period, len(closes)):
            if i == period:
                result[i] = 100 - 100 / (1 + avg_gain / (avg_loss + 1e-10))
            else:
                avg_gain = (avg_gain * (period - 1) + gains[i - 1]) / period
                avg_loss = (avg_loss * (period - 1) + losses[i - 1]) / period
                result[i] = 100 - 100 / (1 + avg_gain / (avg_loss + 1e-10))

        return result

    def _calc_boll(
        self, data: pd.DataFrame, period: int = 20, std_dev: float = 2
    ) -> np.ndarray:
        """Calculate Bollinger Bands middle band"""
        if "close" not in data.columns:
            return np.full(len(data), np.nan)

        closes = data["close"].values
        result = np.full(len(closes), np.nan)

        for i in range(period - 1, len(closes)):
            result[i] = np.mean(closes[i - period + 1 : i + 1])

        return result

    def _calc_volatility(self, data: pd.DataFrame, period: int = 20) -> np.ndarray:
        """Calculate annualized volatility"""
        if "close" not in data.columns:
            return np.full(len(data), np.nan)

        closes = data["close"].values
        returns = np.zeros(len(closes))
        returns[1:] = np.diff(np.log(closes + 1e-10))

        result = np.full(len(closes), np.nan)

        for i in range(period, len(closes)):
            result[i] = np.std(returns[i - period + 1 : i + 1]) * np.sqrt(252) * 100

        return result

    def _calc_turnover(self, data: pd.DataFrame, period: int = 20) -> np.ndarray:
        """Calculate turnover rate"""
        if "turnover" in data.columns:
            return data["turnover"].values

        if "volume" in data.columns and "float_shares" in data.columns:
            volume = data["volume"].values
            float_shares = data["float_shares"].values
            return (volume / (float_shares + 1e-10) * 100).values

        return np.full(len(data), np.nan)

    def _calc_news_sentiment(self, data: pd.DataFrame) -> np.ndarray:
        """Calculate news sentiment score"""
        if "news_sentiment" in data.columns:
            return data["news_sentiment"].values
        return np.full(len(data), np.nan)

    def _calc_analyst_rating(self, data: pd.DataFrame) -> np.ndarray:
        """Calculate analyst rating"""
        if "analyst_rating" in data.columns:
            return data["analyst_rating"].values
        return np.full(len(data), np.nan)

    def _calc_macd_golden_cross(
        self, data: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> np.ndarray:
        if "close" not in data.columns:
            return np.full(len(data), np.nan)

        closes = data["close"].values
        result = np.zeros(len(closes))

        def ema(data, period):
            k = 2 / (period + 1)
            result = np.zeros(len(data))
            result[0] = data[0]
            for i in range(1, len(data)):
                result[i] = data[i] * k + result[i - 1] * (1 - k)
            return result

        ema_fast = ema(closes, fast)
        ema_slow = ema(closes, slow)
        dif = ema_fast - ema_slow
        dea = ema(dif, signal)

        for i in range(1, len(closes)):
            if dif[i] > dea[i] and dif[i - 1] <= dea[i - 1]:
                result[i] = 1

        return result

    def _calc_rsi_oversold(
        self, data: pd.DataFrame, period: int = 14, threshold: int = 30
    ) -> np.ndarray:
        rsi = self._calc_rsi(data, period)
        result = np.zeros(len(rsi))
        result[rsi < threshold] = 1
        return result

    def _calc_breakout_ma(self, data: pd.DataFrame, period: int = 20) -> np.ndarray:
        if "close" not in data.columns:
            return np.full(len(data), np.nan)

        closes = data["close"].values
        result = np.zeros(len(closes))

        for i in range(period, len(closes)):
            ma = np.mean(closes[i - period : i])
            if closes[i] > ma and closes[i - 1] <= ma:
                result[i] = 1

        return result

    def _calc_foreign_inflow(
        self, data: pd.DataFrame, min_amount: int = 10000000
    ) -> np.ndarray:
        if "foreign_inflow" in data.columns:
            inflow = data["foreign_inflow"].values
            result = np.zeros(len(inflow))
            result[inflow >= min_amount] = 1
            return result
        return np.full(len(data), np.nan)

    def _calc_llm_sentiment(
        self, data: pd.DataFrame, min_score: float = 0.8
    ) -> np.ndarray:
        if "llm_sentiment" in data.columns:
            sentiment = data["llm_sentiment"].values
            result = np.zeros(len(sentiment))
            result[sentiment >= min_score] = 1
            return result
        return np.full(len(data), np.nan)

    def _calc_volume_surge(
        self, data: pd.DataFrame, multiplier: float = 2.0, period: int = 20
    ) -> np.ndarray:
        if "volume" not in data.columns:
            return np.full(len(data), np.nan)

        volumes = data["volume"].values
        result = np.zeros(len(volumes))

        for i in range(period, len(volumes)):
            avg_vol = np.mean(volumes[i - period : i])
            if avg_vol > 0 and volumes[i] >= avg_vol * multiplier:
                result[i] = volumes[i] / avg_vol

        return result

    def _calc_institution_research(
        self, data: pd.DataFrame, days: int = 30
    ) -> np.ndarray:
        if "institution_research_count" in data.columns:
            return data["institution_research_count"].values
        return np.full(len(data), np.nan)

    def _calc_new_high(self, data: pd.DataFrame, period: int = 60) -> np.ndarray:
        if "close" not in data.columns:
            return np.full(len(data), np.nan)

        closes = data["close"].values
        result = np.zeros(len(closes))

        for i in range(period, len(closes)):
            if closes[i] >= np.max(closes[i - period : i + 1]):
                result[i] = 1

        return result


# Singleton instance
_factor_registry: Optional[FactorRegistry] = None


def get_factor_registry() -> FactorRegistry:
    """Get or create the singleton FactorRegistry instance"""
    global _factor_registry
    if _factor_registry is None:
        _factor_registry = FactorRegistry()
    return _factor_registry
