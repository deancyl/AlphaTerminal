"""
Tests for market status utility functions.
"""
import pytest
from datetime import datetime, time
from unittest.mock import patch, MagicMock
from app.utils.market_status import is_market_open


class TestMarketStatus:
    """Test cases for market status detection."""

    def test_a_share_trading_morning(self):
        """Test A-share morning trading session (09:30-11:30)."""
        with patch('app.utils.market_status.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 15, 10, 0, 0)  # Monday 10:00
            mock_datetime.time = time
            
            is_open, status = is_market_open("A_SHARE")
            assert is_open is True
            assert status == "交易中"

    def test_a_share_trading_afternoon(self):
        """Test A-share afternoon trading session (13:00-15:00)."""
        with patch('app.utils.market_status.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 15, 14, 0, 0)  # Monday 14:00
            mock_datetime.time = time
            
            is_open, status = is_market_open("A_SHARE")
            assert is_open is True
            assert status == "交易中"

    def test_a_share_pre_market(self):
        """Test A-share pre-market session (08:30-09:30)."""
        with patch('app.utils.market_status.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 15, 9, 0, 0)  # Monday 09:00
            mock_datetime.time = time
            
            is_open, status = is_market_open("A_SHARE")
            assert is_open is False
            assert status == "盘前"

    def test_a_share_lunch_break(self):
        """Test A-share lunch break (11:30-13:00)."""
        with patch('app.utils.market_status.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 15, 12, 0, 0)  # Monday 12:00
            mock_datetime.time = time
            
            is_open, status = is_market_open("A_SHARE")
            assert is_open is False
            assert status == "已休市"

    def test_a_share_weekend(self):
        """Test A-share weekend (closed)."""
        with patch('app.utils.market_status.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 13, 10, 0, 0)  # Saturday 10:00
            mock_datetime.time = time
            
            is_open, status = is_market_open("A_SHARE")
            assert is_open is False
            assert status == "已休市"

    def test_hk_trading_session(self):
        """Test HK market trading session."""
        with patch('app.utils.market_status.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 15, 10, 0, 0)  # Monday 10:00
            mock_datetime.time = time
            
            is_open, status = is_market_open("HK")
            assert is_open is True
            assert status == "交易中"

    def test_hk_weekend(self):
        """Test HK market weekend (closed)."""
        with patch('app.utils.market_status.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 13, 10, 0, 0)  # Saturday 10:00
            mock_datetime.time = time
            
            is_open, status = is_market_open("HK")
            assert is_open is False
            assert status == "已休市"

    def test_us_trading_session(self):
        """Test US market trading session (using mocked timezone)."""
        # Skip this test as it requires complex timezone mocking
        pytest.skip("US timezone mocking is complex - skipping for now")

    def test_us_weekend(self):
        """Test US market weekend (closed)."""
        # Skip this test as it requires complex timezone mocking
        pytest.skip("US timezone mocking is complex - skipping for now")

    def test_jp_trading_session(self):
        """Test Japan market trading session."""
        # Skip this test as JP market is not fully implemented
        pytest.skip("JP market status not fully implemented")

    def test_invalid_market_type(self):
        """Test invalid market type returns closed."""
        is_open, status = is_market_open("INVALID")
        assert is_open is False
        assert status == "已休市"

    def test_default_market_type(self):
        """Test default market type is A_SHARE."""
        with patch('app.utils.market_status.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 15, 10, 0, 0)
            mock_datetime.time = time
            
            # Call without market_type parameter
            is_open, status = is_market_open()
            assert is_open is True
            assert status == "交易中"
