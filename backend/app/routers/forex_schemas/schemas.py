"""
Forex Module - Pydantic Schemas
外汇模块数据模型定义

数据来源: AKShare (EastMoney, CFETS, SAFE)
功能: 实时报价、历史K线、交叉汇率矩阵、银行间报价、官方中间价
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal
from datetime import date, datetime


# ==================== 基础模型 ====================

class ForexSpotQuote(BaseModel):
    """实时外汇报价 (EastMoney)"""
    symbol: str = Field(..., description="货币对代码，如 USDCNH")
    name: str = Field(..., description="货币对名称，如 美元兑离岸人民币")
    latest: Optional[float] = Field(None, description="最新价")
    change: Optional[float] = Field(None, description="涨跌额")
    change_pct: Optional[float] = Field(None, description="涨跌幅(%)")
    open: Optional[float] = Field(None, description="今开")
    high: Optional[float] = Field(None, description="最高")
    low: Optional[float] = Field(None, description="最低")
    prev_close: Optional[float] = Field(None, description="昨收")

    @field_validator('change_pct')
    @classmethod
    def round_change_pct(cls, v):
        """涨跌幅保留2位小数"""
        return round(v, 2) if v is not None else v


class ForexSpotQuoteList(BaseModel):
    """实时报价列表响应"""
    quotes: List[ForexSpotQuote]
    total: int
    source: str = "akshare"
    timestamp: int = Field(default_factory=lambda: int(datetime.now().timestamp()))


class ForexCFETSQuote(BaseModel):
    """CFETS银行间报价"""
    pair: str = Field(..., description="货币对，如 USD/CNY")
    bid: Optional[float] = Field(None, description="买入报价")
    ask: Optional[float] = Field(None, description="卖出报价")
    spread: Optional[float] = Field(None, description="点差")
    mid: Optional[float] = Field(None, description="中间价")


class ForexCFETSQuoteList(BaseModel):
    """CFETS报价列表响应"""
    rmb_pairs: List[ForexCFETSQuote] = Field(default_factory=list, description="人民币货币对")
    cross_pairs: List[ForexCFETSQuote] = Field(default_factory=list, description="交叉货币对")
    last_update: str
    source: str = "cfets"


class ForexOfficialRate(BaseModel):
    """官方中间价 (SAFE)"""
    date: str = Field(..., description="日期")
    usd: Optional[float] = Field(None, description="美元")
    eur: Optional[float] = Field(None, description="欧元")
    jpy: Optional[float] = Field(None, description="日元(100日元)")
    gbp: Optional[float] = Field(None, description="英镑")
    hkd: Optional[float] = Field(None, description="港币")
    aud: Optional[float] = Field(None, description="澳元")
    cad: Optional[float] = Field(None, description="加元")
    chf: Optional[float] = Field(None, description="瑞郎")


class ForexOfficialRateList(BaseModel):
    """官方中间价列表响应"""
    rates: List[ForexOfficialRate]
    total: int
    source: str = "safe"


class ForexKline(BaseModel):
    """单根K线数据"""
    date: str = Field(..., description="日期 YYYY-MM-DD")
    open: Optional[float] = Field(None, description="开盘价")
    close: Optional[float] = Field(None, description="收盘价")
    high: Optional[float] = Field(None, description="最高价")
    low: Optional[float] = Field(None, description="最低价")
    amplitude: Optional[float] = Field(None, description="振幅(%)")


class ForexHistoryRequest(BaseModel):
    """历史K线请求参数"""
    symbol: str = Field(..., description="货币对代码")
    period: Literal["daily", "weekly", "monthly"] = Field(
        "daily", description="周期: daily/weekly/monthly"
    )
    start_date: Optional[str] = Field(
        None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="开始日期 YYYY-MM-DD"
    )
    end_date: Optional[str] = Field(
        None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="结束日期 YYYY-MM-DD"
    )
    limit: int = Field(100, ge=1, le=1000, description="返回条数限制")


class ForexHistoryResponse(BaseModel):
    """历史K线响应"""
    symbol: str
    name: str
    period: str
    data: List[ForexKline]
    total: int
    source: str = "akshare"


# ==================== 交叉汇率矩阵模型 ====================

class CrossRateCell(BaseModel):
    """交叉汇率单元格"""
    rate: Optional[float] = Field(None, description="汇率值")
    change_pct: Optional[float] = Field(None, description="涨跌幅(%)")
    is_base: bool = Field(False, description="是否为基准货币(对角线)")
    is_calculated: bool = Field(False, description="是否为计算得出(非直接报价)")


class CrossRateRow(BaseModel):
    """交叉汇率行"""
    base_currency: str = Field(..., description="基准货币")
    rates: List[CrossRateCell] = Field(..., description="该行所有汇率")


class CrossRateMatrix(BaseModel):
    """交叉汇率矩阵响应"""
    currencies: List[str] = Field(..., description="货币列表(行列顺序)")
    matrix: List[CrossRateRow] = Field(..., description="汇率矩阵")
    last_update: str
    source: str = "akshare"


class CrossRateRequest(BaseModel):
    """交叉汇率计算请求"""
    from_currency: str = Field(..., min_length=3, max_length=3, description="源货币代码")
    to_currency: str = Field(..., min_length=3, max_length=3, description="目标货币代码")
    amount: float = Field(..., gt=0, le=1000000000, description="转换金额")

    @field_validator('from_currency', 'to_currency')
    @classmethod
    def uppercase_currency(cls, v):
        return v.upper()


class CrossRateResponse(BaseModel):
    """交叉汇率计算响应"""
    from_currency: str
    to_currency: str
    amount: float
    rate: float
    result: float
    path: List[str] = Field(default_factory=list, description="计算路径，如 ['EUR', 'USD', 'JPY']")
    rate_source: str = Field("triangular", description="汇率来源: direct/triangular/fallback")
    timestamp: str


# ==================== 货币转换模型 ====================

class CurrencyConvertRequest(BaseModel):
    """货币转换请求"""
    amount: float = Field(..., gt=0, le=1000000000, description="转换金额")
    from_currency: str = Field(..., min_length=3, max_length=3, description="源货币代码")
    to_currency: str = Field(..., min_length=3, max_length=3, description="目标货币代码")

    @field_validator('from_currency', 'to_currency')
    @classmethod
    def uppercase_currency(cls, v):
        return v.upper()


class CurrencyConvertResponse(BaseModel):
    """货币转换响应"""
    from_currency: str
    to_currency: str
    amount: float
    rate: float
    result: float
    rate_source: str
    timestamp: str


# ==================== 兼容旧版模型 ====================

class ForexQuote(BaseModel):
    """外汇报价 (兼容旧版)"""
    symbol: str
    name: str
    buy_rate: Optional[float] = None
    sell_rate: Optional[float] = None
    middle_rate: Optional[float] = None
    change_pct: Optional[float] = None
    date: Optional[str] = None


class ForexQuotesResponse(BaseModel):
    """报价列表响应 (兼容旧版)"""
    quotes: List[ForexQuote]
    total: int


class OHLCData(BaseModel):
    """OHLC数据 (兼容旧版)"""
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: Optional[int] = None
