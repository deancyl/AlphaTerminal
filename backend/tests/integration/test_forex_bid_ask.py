"""
Integration tests for Forex bid/ask precision fix.

Tests:
1. Cross-rate calculation with bid/ask multiplication
2. Triangular arbitrage precision
3. Spread calculation accuracy
"""
import pytest
from decimal import Decimal
from app.services.fetchers.forex_fetcher import forex_fetcher


class TestForexBidAskPrecision:
    """Test suite for Forex bid/ask precision."""
    
    def test_calculate_cross_rate_with_spread_direct(self):
        """Test direct rate calculation with bid/ask."""
        bid_rates = {"EUR/USD": Decimal("1.0795")}
        ask_rates = {"EUR/USD": Decimal("1.0805")}
        
        result = forex_fetcher.calculate_cross_rate_with_spread(
            "EUR", "USD", bid_rates, ask_rates
        )
        
        assert result is not None
        assert result["bid"] == Decimal("1.079500")
        assert result["ask"] == Decimal("1.080500")
        assert result["mid"] == Decimal("1.080000")
        # Spread = (ask - bid) / mid * 100 = (1.0805 - 1.0795) / 1.08 * 100
        assert abs(result["spread"] - Decimal("0.093")) < Decimal("0.001")
    
    def test_calculate_cross_rate_with_spread_inverse(self):
        """Test inverse rate calculation with bid/ask."""
        bid_rates = {"USD/EUR": Decimal("0.9255")}
        ask_rates = {"USD/EUR": Decimal("0.9265")}
        
        result = forex_fetcher.calculate_cross_rate_with_spread(
            "EUR", "USD", bid_rates, ask_rates
        )
        
        assert result is not None
        # EUR/USD = 1 / USD/EUR
        # bid = 1 / ask(USD/EUR) = 1 / 0.9265 = 1.0793
        # ask = 1 / bid(USD/EUR) = 1 / 0.9255 = 1.0805
        assert abs(result["bid"] - Decimal("1.079300")) < Decimal("0.001")
        assert abs(result["ask"] - Decimal("1.080500")) < Decimal("0.001")
    
    def test_calculate_cross_rate_triangular_arbitrage(self):
        """Test triangular arbitrage: EUR/JPY = EUR/USD × USD/JPY."""
        bid_rates = {
            "EUR/USD": Decimal("1.0795"),
            "USD/JPY": Decimal("149.95")
        }
        ask_rates = {
            "EUR/USD": Decimal("1.0805"),
            "USD/JPY": Decimal("150.05")
        }
        
        result = forex_fetcher.calculate_cross_rate_with_spread(
            "EUR", "JPY", bid_rates, ask_rates
        )
        
        assert result is not None
        # EUR/JPY_bid = EUR/USD_bid × USD/JPY_bid = 1.0795 × 149.95 = 161.88
        # EUR/JPY_ask = EUR/USD_ask × USD/JPY_ask = 1.0805 × 150.05 = 162.13
        expected_bid = Decimal("1.0795") * Decimal("149.95")
        expected_ask = Decimal("1.0805") * Decimal("150.05")
        
        assert abs(result["bid"] - expected_bid.quantize(Decimal("0.000001"))) < Decimal("0.01")
        assert abs(result["ask"] - expected_ask.quantize(Decimal("0.000001"))) < Decimal("0.01")
    
    def test_calculate_cross_rate_same_currency(self):
        """Test same currency returns 1.0."""
        bid_rates = {}
        ask_rates = {}
        
        result = forex_fetcher.calculate_cross_rate_with_spread(
            "USD", "USD", bid_rates, ask_rates
        )
        
        assert result is not None
        assert result["bid"] == Decimal("1.0")
        assert result["ask"] == Decimal("1.0")
        assert result["spread"] == Decimal("0.0")
    
    def test_calculate_cross_rate_missing_rates(self):
        """Test returns None when rates are missing."""
        bid_rates = {}
        ask_rates = {}
        
        result = forex_fetcher.calculate_cross_rate_with_spread(
            "EUR", "JPY", bid_rates, ask_rates
        )
        
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
