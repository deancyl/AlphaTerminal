"""
data_validator.py — Pydantic 字段契约 & 行情数据强校验

所有数据源（sina / tencent / eastmoney / alphavantage）返回的原始数据
必须经过此模块的 Schema 校验，才能进入业务层。

防止：
- 价格字段解析错位（parts[3] vs parts[2] 混淆）
- 核心标的（上证指数 sh000001）价格异常（如 3948.55 → 3.94）
- 涨跌停数据超出 [-20%, +20%] 合理范围
- OHLC 内部不一致（close > high）
"""
from __future__ import annotations

import logging
from datetime import datetime
from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, field_validator, field_serializer, model_validator

logger = logging.getLogger(__name__)


class MarketType(str, Enum):
    AShare = "AShare"
    US = "US"
    HK = "HK"
    JP = "JP"
    FUTURES = "Futures"
    BOND = "Bond"
    FOREX = "Forex"


class DataType(str, Enum):
    REALTIME = "realtime"
    INDEX = "index"
    STOCK = "stock"
    FUTURES = "futures"
    BOND = "bond"
    FOREX = "forex"


# ─────────────────────────────────────────────────────────────────────────────
# 核心标的指数价格白名单（额外严苛校验）
# key: symbol，value: (合理最低价, 合理最高价)
# ─────────────────────────────────────────────────────────────────────────────
CRITICAL_INDICES: dict[str, tuple[float, float]] = {
    "sh000001": (2000.0, 6000.0),   # 上证指数
    "sh000300": (2000.0, 6000.0),   # 沪深300
    "sh000016": (1500.0, 8000.0),   # 上证50
    "sh000688": (500.0,  3000.0),   # 科创50
    "sz399001": (5000.0, 20000.0),  # 深证成指
    "sz399006": (1000.0,  6000.0),  # 创业板指
    "sz399005": (2000.0, 10000.0),  # 中小板指
}

# A股个股价格合理范围（防止数量级错位，如 3948.55 → 3.94）
STOCK_PRICE_RANGES: dict[str, tuple[float, float]] = {
    "stock":   (0.01, 10000.0),   # A股普通股
    "index":   (0.01, 100000.0),  # 指数
    "bond":    (50.0,   200.0),   # 债券（价格100左右）
    "futures": (0.01, 100000.0),  # 期货（部分品种价格高）
}


class QuoteData(BaseModel):
    """
    实时行情字段契约 — 所有数据源通用。

    设计原则：
    - price / prev_close / open / high / low 必须是正数
    - change_pct 必须在 [-20, +20] 区间（涨跌停 10%/20%，允许一点余量）
    - OHLC 内部必须自洽：low ≤ price/open ≤ high
    - change_pct 与 (price, prev_close) 的计算值误差 ≤ 0.01%
    """
    symbol: str
    name: str
    market: MarketType = MarketType.AShare
    price: float
    prev_close: float
    open: float
    high: float
    low: float
    change_pct: float
    change: float
    volume: float = 0.0
    amount: Optional[float] = None
    turnover: Optional[float] = None
    timestamp: int = 0          # Unix 秒
    data_type: DataType = DataType.REALTIME
    source: str = ""            # "sina" | "tencent" | "eastmoney" | "alphavantage"

    # ── 基础类型校验 ────────────────────────────────────────────────────────

    @field_validator("price", "prev_close", "open", "high", "low")
    @classmethod
    def price_must_be_positive(cls, v: float) -> float:
        if v is None or v <= 0:
            raise ValueError(f"价格字段必须为正数，实际值: {v}")
        return v

    @field_validator("change_pct")
    @classmethod
    def change_pct_in_reasonable_range(cls, v: float) -> float:
        if not (-25 <= v <= 25):
            raise ValueError(f"涨跌幅超出合理范围 [-25%, +25%]，实际值: {v}")
        return v

    @field_validator("volume")
    @classmethod
    def volume_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError(f"volume 不能为负数: {v}")
        return v

    # ── 内部一致性校验 ──────────────────────────────────────────────────────

    @model_validator(mode="after")
    def validate_ohlc_consistency(self) -> "QuoteData":
        """OHLC 四价内部一致性"""
        p, o, h, l = self.price, self.open, self.high, self.low
        if not (l <= p <= h):
            raise ValueError(
                f"OHLC 不一致: price={p} 不在 [low={l}, high={h}] 之间"
            )
        if not (l <= o <= h):
            raise ValueError(
                f"OHLC 不一致: open={o} 不在 [low={l}, high={h}] 之间"
            )
        # 允许 open == close == low == high（科创板新股等）
        return self

    @model_validator(mode="after")
    def validate_change_pct_consistency(self) -> "QuoteData":
        """涨跌幅与价格必须自洽"""
        pc = self.prev_close
        if pc <= 0:
            raise ValueError(f"prev_close 必须为正数: {pc}")

        expected_chg_pct = (self.price - pc) / pc * 100
        computed_chg_pct = round(expected_chg_pct, 4)

        if abs(self.change_pct - computed_chg_pct) > 0.02:
            raise ValueError(
                f"涨跌幅与价格不符: change_pct={self.change_pct}% "
                f"但由 price={self.price}/prev_close={pc} 计算为 {computed_chg_pct}%"
            )
        return self

    # ── 核心标的额外价格范围检查 ─────────────────────────────────────────────

    def validate_critical_symbol(self) -> bool:
        """
        核心标的（sh000001 等）额外价格合理性检查。
        超出白名单范围 → 拒绝写入，返回 False。
        """
        key = self.symbol.lower()
        if key not in CRITICAL_INDICES:
            return True  # 非核心标的，不校验范围

        lo, hi = CRITICAL_INDICES[key]
        if not (lo <= self.price <= hi):
            logger.error(
                f"[Validator] 核心标的 {self.name}({self.symbol}) "
                f"价格 {self.price} 超出预期范围 [{lo}, {hi}]，拒绝写入！"
            )
            return False
        return True

    @field_validator("timestamp", mode="before")
    @classmethod
    def normalize_timestamp(cls, v) -> int:
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return int(v)
        if isinstance(v, str):
            try:
                return int(datetime.fromisoformat(v).timestamp())
            except Exception:
                return int(time.time()) if "time" in dir() else 0
        return int(datetime.now().timestamp())

    @field_serializer("market", "data_type")
    def serialize_enum(self, v) -> str:
        return v.value


class IndexQuoteData(QuoteData):
    """指数行情专用 Schema"""
    data_type: DataType = DataType.INDEX
    market: MarketType = MarketType.AShare


class KlineData(BaseModel):
    """
    K线数据契约。
    校验：
    - close 必须在 [low, high] 之间
    - open 必须在 [low, high] 之间
    - volume 非负
    """
    symbol: str
    date: str                    # "2026-04-21"
    period: str = "day"         # "minute" | "day" | "week" | "month"
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: Optional[float] = None
    turnover_rate: Optional[float] = None
    amplitude: Optional[float] = None   # 振幅 (high-low)/prev_close*100
    timestamp: int = 0
    source: str = ""

    @field_validator("open", "high", "low", "close")
    @classmethod
    def ohlc_positive(cls, v: float) -> float:
        if v is None or v <= 0:
            raise ValueError(f"K线价格必须为正数: {v}")
        return v

    @field_validator("volume")
    @classmethod
    def volume_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError(f"K线 volume 不能为负: {v}")
        return v

    @model_validator(mode="after")
    def validate_ohlc(self) -> "KlineData":
        if not (self.low <= self.close <= self.high):
            raise ValueError(
                f"K线 OHLC 不一致: close={self.close} 不在 [low={self.low}, high={self.high}]"
            )
        if not (self.low <= self.open <= self.high):
            raise ValueError(
                f"K线 OHLC 不一致: open={self.open} 不在 [low={self.low}, high={self.high}]"
            )
        return self


class FXQuoteData(BaseModel):
    """外汇行情契约（Alphavantage FX）"""
    from_symbol: str
    to_symbol: str
    price: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    prev_close: Optional[float] = None
    timestamp: int = 0
    source: str = "alphavantage"

    @field_validator("price")
    @classmethod
    def price_positive(cls, v: float) -> float:
        if v is None or v <= 0:
            raise ValueError(f"FX price 必须为正数: {v}")
        return v

    @model_validator(mode="after")
    def validate_bid_ask(self) -> "FXQuoteData":
        if self.bid is not None and self.ask is not None:
            if not (0 < self.bid <= self.ask):
                raise ValueError(f"bid={self.bid} <= ask={self.ask} 不合法")
        return self


# ─────────────────────────────────────────────────────────────────────────────
# 校验入口函数（供各 fetcher 调用）
# ─────────────────────────────────────────────────────────────────────────────

def validate_quote(raw: dict, source: str) -> Optional[QuoteData]:
    """
    统一校验入口。
    raw: 解析后的原始 dict
    source: "sina" | "tencent" | "eastmoney" | "alphavantage"

    返回:
    - 校验通过: QuoteData 实例
    - 校验失败: None（已打 error log）
    """
    try:
        # 注入来源
        raw["source"] = source
        data = QuoteData(**raw)

        # 核心标的价格范围检查
        if not data.validate_critical_symbol():
            return None

        return data
    except Exception as e:
        logger.error(f"[Validator] QuoteData 校验失败 (source={source}): {e}")
        return None


def validate_kline(raw: dict, source: str) -> Optional[KlineData]:
    """K线数据校验入口"""
    try:
        raw["source"] = source
        return KlineData(**raw)
    except Exception as e:
        logger.error(f"[Validator] KlineData 校验失败 (source={source}): {e}")
        return None
