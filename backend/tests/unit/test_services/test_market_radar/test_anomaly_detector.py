"""
Unit tests for Anomaly Detector

Tests for P1-4: True 60-day high detection
"""

import pytest
from unittest.mock import patch


class TestNewHighDetection:
    """Test new high detection logic."""

    def test_detect_new_high_simple_fallback(self):
        """Test fallback detection when K-line data unavailable."""
        from app.services.market_radar.anomaly_detector import _detect_new_high_simple

        stocks = [
            {"symbol": "600519", "name": "贵州茅台", "price": 1800, "change_pct": 5.0},
            {"symbol": "000001", "name": "平安银行", "price": 10, "change_pct": 2.0},  # Below threshold
            {"symbol": "600036", "name": "招商银行", "price": 30, "change_pct": 8.0},
        ]

        result = _detect_new_high_simple(stocks, top_n=10)

        assert result.type.value == "new_high"
        assert result.title == "涨幅居前"
        assert len(result.stocks) == 2  # Only stocks with change_pct > 3

    def test_detect_new_high_with_kline_current_above_period_high(self):
        """Test true 60-day high detection when current price exceeds period high."""
        from app.services.market_radar.anomaly_detector import _detect_new_high_with_kline

        # Stock data: current price 1850
        stocks = [
            {"symbol": "600519", "name": "贵州茅台", "price": 1850, "change_pct": 3.0},
        ]

        # K-line data: need at least 10 days
        # Period high (excluding today) = 1800
        kline_data = {
            "600519": [
                {"date": "2024-01-01", "high": 1700, "close": 1680},
                {"date": "2024-01-02", "high": 1750, "close": 1720},
                {"date": "2024-01-03", "high": 1720, "close": 1700},
                {"date": "2024-01-04", "high": 1740, "close": 1720},
                {"date": "2024-01-05", "high": 1760, "close": 1740},
                {"date": "2024-01-06", "high": 1780, "close": 1760},
                {"date": "2024-01-07", "high": 1790, "close": 1770},
                {"date": "2024-01-08", "high": 1800, "close": 1780},  # Period high
                {"date": "2024-01-09", "high": 1790, "close": 1770},
                {"date": "2024-01-10", "high": 1850, "close": 1850},  # Today (excluded from period high)
            ]
        }

        result = _detect_new_high_with_kline(stocks, kline_data, top_n=10)

        assert result.type.value == "new_high"
        assert result.title == "创60日新高"
        # Current price 1850 >= period_high 1800 * 0.98 = 1764
        assert len(result.stocks) >= 1
        assert result.stocks[0].symbol == "sh600519"

    def test_detect_new_high_with_kline_below_period_high(self):
        """Test that stocks below period high are not detected."""
        from app.services.market_radar.anomaly_detector import _detect_new_high_with_kline

        # Stock data: current price 1700, below period high
        stocks = [
            {"symbol": "600519", "name": "贵州茅台", "price": 1700, "change_pct": 1.0},
        ]

        # K-line data: period high = 1800, need at least 10 days
        kline_data = {
            "600519": [
                {"date": "2024-01-01", "high": 1700, "close": 1680},
                {"date": "2024-01-02", "high": 1750, "close": 1720},
                {"date": "2024-01-03", "high": 1720, "close": 1700},
                {"date": "2024-01-04", "high": 1740, "close": 1720},
                {"date": "2024-01-05", "high": 1760, "close": 1740},
                {"date": "2024-01-06", "high": 1780, "close": 1760},
                {"date": "2024-01-07", "high": 1790, "close": 1770},
                {"date": "2024-01-08", "high": 1800, "close": 1780},  # Period high
                {"date": "2024-01-09", "high": 1790, "close": 1770},
                {"date": "2024-01-10", "high": 1700, "close": 1700},  # Today
            ]
        }

        result = _detect_new_high_with_kline(stocks, kline_data, top_n=10)

        # 1700 < 1800 * 0.98 = 1764, so should not be detected
        assert len(result.stocks) == 0

    def test_detect_new_high_tolerance_at_98_percent(self):
        """Test 2% tolerance for new high detection."""
        from app.services.market_radar.anomaly_detector import _detect_new_high_with_kline

        # Price at exactly 98% of period high (1764 = 1800 * 0.98)
        stocks = [
            {"symbol": "600519", "name": "贵州茅台", "price": 1764, "change_pct": 1.0},
        ]

        # Period high = 1800, need at least 10 days
        kline_data = {
            "600519": [
                {"date": "2024-01-01", "high": 1700, "close": 1680},
                {"date": "2024-01-02", "high": 1750, "close": 1720},
                {"date": "2024-01-03", "high": 1720, "close": 1700},
                {"date": "2024-01-04", "high": 1740, "close": 1720},
                {"date": "2024-01-05", "high": 1760, "close": 1740},
                {"date": "2024-01-06", "high": 1780, "close": 1760},
                {"date": "2024-01-07", "high": 1790, "close": 1770},
                {"date": "2024-01-08", "high": 1800, "close": 1780},  # Period high
                {"date": "2024-01-09", "high": 1790, "close": 1770},
                {"date": "2024-01-10", "high": 1764, "close": 1764},  # Today at 98%
            ]
        }

        result = _detect_new_high_with_kline(stocks, kline_data, top_n=10)

        # Should be detected due to tolerance (1764 >= 1800 * 0.98 = 1764)
        assert len(result.stocks) >= 1

    def test_detect_new_high_insufficient_kline_data(self):
        """Test that stocks with insufficient K-line data are skipped."""
        from app.services.market_radar.anomaly_detector import _detect_new_high_with_kline

        stocks = [
            {"symbol": "600519", "name": "贵州茅台", "price": 1850, "change_pct": 3.0},
        ]

        # Only 5 days of data (< 10 minimum)
        kline_data = {
            "600519": [
                {"date": "2024-01-01", "high": 1700, "close": 1680},
                {"date": "2024-01-02", "high": 1750, "close": 1720},
                {"date": "2024-01-03", "high": 1800, "close": 1780},
                {"date": "2024-01-04", "high": 1850, "close": 1850},
                {"date": "2024-01-05", "high": 1860, "close": 1860},
            ]
        }

        result = _detect_new_high_with_kline(stocks, kline_data, top_n=10)

        # Should be empty due to insufficient data
        assert len(result.stocks) == 0


class TestAnomalyDetectionIntegration:
    """Test full anomaly detection flow."""

    @pytest.mark.asyncio
    async def test_detect_anomalies_timeout(self):
        """Test that timeout returns proper error response."""
        from app.services.market_radar.anomaly_detector import detect_anomalies

        with patch('app.services.market_radar.anomaly_detector._detect_anomalies_internal') as mock_internal:
            import asyncio
            mock_internal.side_effect = asyncio.TimeoutError()

            result = await detect_anomalies(timeout=0.001)  # Very short timeout

            assert "error" in result
            assert result["error"] == "timeout"
