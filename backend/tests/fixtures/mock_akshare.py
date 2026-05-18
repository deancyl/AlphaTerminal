"""
Mock Akshare fixtures for testing.

Provides mock functions and data for testing Akshare-related functionality
without requiring actual network calls to data providers.
"""
from typing import Dict, Any, List, Optional, Callable
from unittest.mock import MagicMock, AsyncMock
import pandas as pd
from datetime import datetime, timedelta


class MockAkshareData:
    """
    Mock data provider for Akshare API responses.
    
    Provides realistic mock data for various Akshare functions:
    - Stock quotes
    - Financial indicators
    - Market indices
    - Sector data
    
    Usage:
        mock_data = MockAkshareData()
        df = mock_data.get_stock_zh_a_spot_em()
        assert len(df) > 0
    """
    
    @staticmethod
    def get_stock_zh_a_spot_em() -> pd.DataFrame:
        """Mock real-time A-share stock data."""
        return pd.DataFrame({
            '代码': ['600519', '000858', '601318', '000001', '000002'],
            '名称': ['贵州茅台', '五粮液', '中国平安', '平安银行', '万科A'],
            '最新价': [1795.00, 145.50, 48.20, 10.50, 8.30],
            '涨跌幅': [-7.62, 2.15, -1.23, 0.95, -0.48],
            '涨跌额': [-148.55, 3.05, -0.60, 0.10, -0.04],
            '成交量': [1250000, 8500000, 15000000, 25000000, 30000000],
            '成交额': [2240000000, 1235000000, 723000000, 262500000, 249000000],
            '最高': [1810.00, 148.00, 49.50, 10.80, 8.50],
            '最低': [1780.00, 142.00, 47.50, 10.20, 8.10],
            '今开': [1800.00, 143.00, 48.50, 10.40, 8.20],
            '昨收': [1948.55, 142.45, 48.80, 10.40, 8.34],
            '市盈率-动态': [28.5, 22.3, 8.5, 6.2, 12.8],
            '市净率': [8.2, 5.6, 1.2, 0.8, 1.1],
            '总市值': [2250000000000, 565000000000, 875000000000, 228000000000, 185000000000],
        })
    
    @staticmethod
    def get_stock_financial_analysis_indicator(symbol: str) -> pd.DataFrame:
        """Mock financial analysis indicators for a stock."""
        quarters = ['2024Q3', '2024Q2', '2024Q1', '2023Q4', '2023Q3', '2023Q2', '2023Q1', '2022Q4']
        return pd.DataFrame({
            '日期': quarters,
            '净资产收益率': [18.5, 17.2, 16.8, 19.1, 18.0, 17.5, 16.2, 18.8],
            '毛利率': [91.2, 90.8, 91.5, 92.1, 91.0, 90.5, 91.8, 92.3],
            '净利率': [52.3, 51.8, 52.1, 53.5, 52.0, 51.5, 52.8, 53.2],
            '资产负债率': [28.5, 27.8, 28.2, 29.1, 28.0, 27.5, 28.8, 29.5],
            '流动比率': [2.8, 2.9, 2.7, 2.6, 2.8, 2.9, 2.7, 2.6],
            '速动比率': [2.5, 2.6, 2.4, 2.3, 2.5, 2.6, 2.4, 2.3],
            '每股收益': [15.2, 14.8, 14.5, 15.8, 15.0, 14.6, 14.2, 15.5],
            '每股净资产': [82.5, 80.2, 78.5, 76.8, 75.2, 73.5, 71.8, 70.2],
            '营业收入同比增长率': [12.5, 11.8, 10.5, 13.2, 12.0, 11.5, 10.8, 14.0],
            '净利润同比增长率': [15.2, 14.5, 13.8, 16.5, 15.0, 14.2, 13.5, 17.0],
        })
    
    @staticmethod
    def get_stock_institute_hold_detail(symbol: str) -> pd.DataFrame:
        """Mock institutional holding data."""
        quarters = ['2024Q3', '2024Q2', '2024Q1', '2023Q4', '2023Q3', '2023Q2', '2023Q1', '2022Q4']
        return pd.DataFrame({
            '报告期': quarters,
            '机构家数': [1250, 1180, 1150, 1200, 1100, 1050, 1000, 950],
            '持股数量': [850000000, 820000000, 800000000, 780000000, 750000000, 720000000, 700000000, 680000000],
            '持股比例': [67.5, 65.2, 63.5, 62.0, 59.5, 57.2, 55.5, 54.0],
            '持股市值': [1525000000000, 1450000000000, 1400000000000, 1350000000000, 1280000000000, 1200000000000, 1150000000000, 1100000000000],
        })
    
    @staticmethod
    def get_stock_margin_detail(symbol: str) -> pd.DataFrame:
        """Mock margin trading data."""
        dates = [(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(30)]
        return pd.DataFrame({
            '日期': dates,
            '融资余额': [12500000000 + i * 10000000 for i in range(30)],
            '融券余额': [850000000 - i * 2000000 for i in range(30)],
            '融资买入额': [500000000 + (i % 5) * 10000000 for i in range(30)],
            '融券卖出额': [5000000 + (i % 3) * 500000 for i in range(30)],
        })
    
    @staticmethod
    def get_index_zh_a_hist(symbol: str) -> pd.DataFrame:
        """Mock historical index data."""
        dates = pd.date_range(end=datetime.now(), periods=100, freq='D')
        return pd.DataFrame({
            '日期': dates.strftime('%Y-%m-%d'),
            '开盘': [3900 + (i % 10) * 5 for i in range(100)],
            '收盘': [3910 + (i % 10) * 5 for i in range(100)],
            '最高': [3920 + (i % 10) * 5 for i in range(100)],
            '最低': [3890 + (i % 10) * 5 for i in range(100)],
            '成交量': [100000000 + i * 1000000 for i in range(100)],
            '成交额': [500000000000 + i * 500000000 for i in range(100)],
        })
    
    @staticmethod
    def get_macro_china() -> pd.DataFrame:
        """Mock macro economic indicators."""
        return pd.DataFrame({
            '指标': ['GDP', 'CPI', 'PPI', 'PMI', 'M2', '社会融资规模'],
            '数值': [5.2, 0.2, -2.8, 50.1, 10.3, 35.2],
            '单位': ['%', '%', '%', '', '%', '万亿元'],
            '日期': ['2024Q3', '2024-09', '2024-09', '2024-09', '2024-09', '2024-09'],
        })


class MockAkshareClient:
    """
    Mock Akshare client for testing.
    
    Provides mock implementations of Akshare API functions
    with configurable behavior for testing edge cases.
    
    Usage:
        client = MockAkshareClient()
        client.set_error_mode(True)
        result = await client.get_quote("600519")
        assert result is None
    """
    
    def __init__(self):
        self._error_mode = False
        self._error_message = "Network error"
        self._latency_ms = 0
        self._call_count = 0
        self._call_history: List[Dict[str, Any]] = []
        self._data_provider = MockAkshareData()
    
    def set_error_mode(self, enabled: bool, message: str = "Network error") -> None:
        """Configure client to return errors."""
        self._error_mode = enabled
        self._error_message = message
    
    def set_latency(self, latency_ms: int) -> None:
        """Simulate network latency."""
        self._latency_ms = latency_ms
    
    def get_call_count(self) -> int:
        """Get total number of API calls made."""
        return self._call_count
    
    def get_call_history(self) -> List[Dict[str, Any]]:
        """Get history of all API calls."""
        return self._call_history
    
    def reset(self) -> None:
        """Reset client state."""
        self._error_mode = False
        self._latency_ms = 0
        self._call_count = 0
        self._call_history.clear()
    
    def _record_call(self, function_name: str, args: tuple, kwargs: dict) -> None:
        """Record an API call."""
        self._call_count += 1
        self._call_history.append({
            'function': function_name,
            'args': args,
            'kwargs': kwargs,
            'timestamp': datetime.now().isoformat(),
        })
    
    def get_stock_zh_a_spot_em(self) -> Optional[pd.DataFrame]:
        """Get mock real-time stock data."""
        self._record_call('get_stock_zh_a_spot_em', (), {})
        if self._error_mode:
            return None
        return self._data_provider.get_stock_zh_a_spot_em()
    
    def get_stock_financial_analysis_indicator(self, symbol: str) -> Optional[pd.DataFrame]:
        """Get mock financial indicators."""
        self._record_call('get_stock_financial_analysis_indicator', (symbol,), {})
        if self._error_mode:
            return None
        return self._data_provider.get_stock_financial_analysis_indicator(symbol)
    
    def get_stock_institute_hold_detail(self, symbol: str) -> Optional[pd.DataFrame]:
        """Get mock institutional holdings."""
        self._record_call('get_stock_institute_hold_detail', (symbol,), {})
        if self._error_mode:
            return None
        return self._data_provider.get_stock_institute_hold_detail(symbol)
    
    def get_stock_margin_detail(self, symbol: str) -> Optional[pd.DataFrame]:
        """Get mock margin data."""
        self._record_call('get_stock_margin_detail', (symbol,), {})
        if self._error_mode:
            return None
        return self._data_provider.get_stock_margin_detail(symbol)
    
    def get_index_zh_a_hist(self, symbol: str) -> Optional[pd.DataFrame]:
        """Get mock historical index data."""
        self._record_call('get_index_zh_a_hist', (symbol,), {})
        if self._error_mode:
            return None
        return self._data_provider.get_index_zh_a_hist(symbol)
    
    def get_macro_china(self) -> Optional[pd.DataFrame]:
        """Get mock macro indicators."""
        self._record_call('get_macro_china', (), {})
        if self._error_mode:
            return None
        return self._data_provider.get_macro_china()


def create_mock_akshare_client(
    error_mode: bool = False,
    latency_ms: int = 0
) -> MockAkshareClient:
    """Create a configured MockAkshareClient."""
    client = MockAkshareClient()
    if error_mode:
        client.set_error_mode(True)
    if latency_ms > 0:
        client.set_latency(latency_ms)
    return client


def create_sample_stock_quote(symbol: str = "600519") -> Dict[str, Any]:
    """Create a sample stock quote for testing."""
    return {
        'symbol': symbol,
        'name': '贵州茅台' if symbol == '600519' else '测试股票',
        'price': 1795.00,
        'change_pct': -7.62,
        'change_amount': -148.55,
        'volume': 1250000,
        'amount': 2240000000,
        'high': 1810.00,
        'low': 1780.00,
        'open': 1800.00,
        'prev_close': 1948.55,
        'pe_ratio': 28.5,
        'pb_ratio': 8.2,
        'market_cap': 2250000000000,
        'source': 'mock',
    }


def create_sample_index_quote(symbol: str = "sh000001") -> Dict[str, Any]:
    """Create a sample index quote for testing."""
    return {
        'symbol': symbol,
        'name': '上证指数',
        'price': 3948.55,
        'change_pct': 0.64,
        'change_amount': 25.27,
        'volume': 250000000,
        'amount': 500000000000,
        'high': 3950.12,
        'low': 3910.45,
        'open': 3923.28,
        'prev_close': 3923.28,
        'source': 'mock',
    }