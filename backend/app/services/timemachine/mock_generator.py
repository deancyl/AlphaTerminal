"""
Mock K-line data generator using Geometric Brownian Motion (GBM)
Generates realistic OHLCV data for TimeMachine when all data sources fail
"""
import random
import math
from datetime import date, datetime, timedelta
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


def generate_mock_kline(
    symbol: str,
    start_date: date,
    end_date: date,
    initial_price: float = 100.0,
    volatility: float = 0.02,  # 日波动率 2%
    trend: str = "random"  # "bull", "bear", "sideways", "random"
) -> Dict:
    """
    使用GBM生成模拟K线数据
    
    Args:
        symbol: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        initial_price: 初始价格
        volatility: 日波动率
        trend: 趋势类型
    
    Returns:
        {
            "bars": [...],
            "source_type": "mock",
            "is_mock": True,
            "timestamp": "2024-01-15T10:30:00"
        }
    """
    bars = []
    current_date = start_date
    current_price = initial_price
    
    # 趋势漂移率
    drift_map = {
        "bull": 0.0005,      # 日涨幅 0.05%
        "bear": -0.0003,     # 日跌幅 0.03%
        "sideways": 0.0,
        "random": random.uniform(-0.0002, 0.0004)
    }
    drift = drift_map.get(trend, 0.0)
    
    while current_date <= end_date:
        # 跳过周末
        if current_date.weekday() < 5:  # 周一到周五
            bar = _generate_single_bar(current_date, current_price, volatility, drift)
            bars.append(bar)
            current_price = bar["close"]  # 下一个bar的open = 上一个bar的close
        
        current_date += timedelta(days=1)
    
    logger.info(f"[MockGenerator] Generated {len(bars)} bars for {symbol}")
    
    return {
        "bars": bars,
        "source_type": "mock",
        "is_mock": True,
        "timestamp": datetime.now().isoformat()
    }


def _generate_single_bar(
    date_obj: date,
    open_price: float,
    volatility: float,
    drift: float
) -> Dict:
    """
    生成单根K线
    使用GBM模型: S(t+dt) = S(t) * exp((drift - 0.5*vol^2)*dt + vol*sqrt(dt)*Z)
    其中 Z ~ N(0,1)
    """
    # GBM随机过程
    Z = random.gauss(0, 1)  # 标准正态分布
    dt = 1.0  # 1天
    
    # 计算收盘价
    log_return = (drift - 0.5 * volatility**2) * dt + volatility * math.sqrt(dt) * Z
    close_price = open_price * math.exp(log_return)
    
    # 生成日内高低价
    intraday_range = abs(close_price - open_price) + open_price * volatility * 0.5
    high_price = max(open_price, close_price) + random.uniform(0, intraday_range)
    low_price = min(open_price, close_price) - random.uniform(0, intraday_range)
    
    # 确保价格合理性
    low_price = max(low_price, open_price * 0.95)  # 不低于开盘价-5%
    high_price = min(high_price, open_price * 1.05)  # 不高于开盘价+5%
    
    # 生成成交量（与价格波动相关）
    price_change_pct = abs(close_price - open_price) / open_price
    base_volume = 1000000  # 100万基础成交量
    volume = int(base_volume * (1 + price_change_pct * 10) * random.uniform(0.8, 1.2))
    
    # 生成成交额
    avg_price = (high_price + low_price) / 2
    amount = volume * avg_price
    
    return {
        "date": date_obj.isoformat(),
        "open": round(open_price, 2),
        "high": round(high_price, 2),
        "low": round(low_price, 2),
        "close": round(close_price, 2),
        "volume": volume,
        "amount": round(amount, 2)
    }


def get_mock_fallback(symbol: str, start_date: date, end_date: date) -> Dict:
    """
    获取模拟数据作为最终fallback
    根据symbol选择合适的初始价格
    """
    # 根据symbol前缀估算初始价格
    price_map = {
        "sh600": 1800.0,   # 茅台类
        "sh601": 50.0,     # 大盘股
        "sz000": 30.0,     # 深市主板
        "sz002": 25.0,     # 中小板
        "sz300": 20.0,     # 创业板
    }
    
    prefix = symbol[:5] if len(symbol) >= 5 else symbol
    initial_price = price_map.get(prefix, 50.0)
    
    return generate_mock_kline(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        initial_price=initial_price,
        volatility=0.02,
        trend="random"
    )
