"""
Unit tests for Options Pricing Engine (Black-Scholes-Merton)
"""

import pytest
from datetime import date, timedelta


class TestOptionsPricingEngine:
    """Tests for OptionsPricingEngine class"""

    @pytest.fixture
    def engine(self):
        from app.services.pricing.black_scholes import OptionsPricingEngine

        return OptionsPricingEngine(risk_free_rate=0.025, dividend_yield=0.02)

    def test_engine_initialization(self, engine):
        assert engine.r == 0.025
        assert engine.q == 0.02

    def test_calculate_time_to_expiry(self, engine):
        expiry = date.today() + timedelta(days=30)
        T = engine.calculate_time_to_expiry(expiry)
        assert T > 0
        assert T < 1

        past_expiry = date.today() - timedelta(days=10)
        T_past = engine.calculate_time_to_expiry(past_expiry)
        assert T_past == 1 / 365

    def test_parse_expiry_from_code(self, engine):
        expiry = engine.parse_expiry_from_code("io2506")
        assert expiry is not None
        assert expiry.year == 2025
        assert expiry.month == 6
        assert expiry.day >= 15 and expiry.day <= 21
        assert expiry.weekday() == 4

        expiry2 = engine.parse_expiry_from_code("mo2509")
        assert expiry2 is not None
        assert expiry2.year == 2025
        assert expiry2.month == 9

        invalid = engine.parse_expiry_from_code("invalid")
        assert invalid is None

    def test_calculate_iv_atm(self, engine):
        S = 4000.0
        K = 4000.0
        T = 0.25
        sigma = 0.20

        from py_vollib.black_scholes_merton import black_scholes_merton

        price = black_scholes_merton("c", S, K, T, engine.r, sigma, engine.q)

        iv, method = engine.calculate_iv(price, S, K, T, is_call=True)

        assert iv is not None
        assert method is not None
        assert abs(iv - sigma) < 0.01

    def test_calculate_iv_otm(self, engine):
        S = 4000.0
        K = 4200.0
        T = 0.25
        sigma = 0.25

        from py_vollib.black_scholes_merton import black_scholes_merton

        price = black_scholes_merton("c", S, K, T, engine.r, sigma, engine.q)

        iv, method = engine.calculate_iv(price, S, K, T, is_call=True)

        assert iv is not None
        assert method is not None
        assert abs(iv - sigma) < 0.02

    def test_calculate_iv_put(self, engine):
        S = 4000.0
        K = 3900.0
        T = 0.25
        sigma = 0.22

        from py_vollib.black_scholes_merton import black_scholes_merton

        price = black_scholes_merton("p", S, K, T, engine.r, sigma, engine.q)

        iv, method = engine.calculate_iv(price, S, K, T, is_call=False)

        assert iv is not None
        assert method is not None
        assert abs(iv - sigma) < 0.02

    def test_calculate_iv_edge_cases(self, engine):
        iv, method = engine.calculate_iv(0, 4000, 4000, 0.25, True)
        assert iv is None
        assert method is None

        iv, method = engine.calculate_iv(100, 0, 4000, 0.25, True)
        assert iv is None
        assert method is None

        iv, method = engine.calculate_iv(100, 4000, 0, 0.25, True)
        assert iv is None
        assert method is None

        iv, method = engine.calculate_iv(100, 4000, 4000, 0, True)
        assert iv is None
        assert method is None

    def test_calculate_greeks_atm_call(self, engine):
        S = 4000.0
        K = 4000.0
        T = 0.25
        sigma = 0.20

        greeks = engine.calculate_greeks(S, K, T, sigma, is_call=True)

        assert greeks is not None
        assert 0.45 < greeks.delta < 0.55
        assert greeks.gamma > 0
        assert greeks.theta < 0
        assert greeks.vega > 0
        assert abs(greeks.iv - sigma) < 0.001

    def test_calculate_greeks_itm_call(self, engine):
        S = 4000.0
        K = 3800.0
        T = 0.25
        sigma = 0.20

        greeks = engine.calculate_greeks(S, K, T, sigma, is_call=True)

        assert greeks is not None
        assert greeks.delta > 0.5
        assert greeks.delta < 1.0

    def test_calculate_greeks_otm_call(self, engine):
        S = 4000.0
        K = 4200.0
        T = 0.25
        sigma = 0.20

        greeks = engine.calculate_greeks(S, K, T, sigma, is_call=True)

        assert greeks is not None
        assert 0 < greeks.delta < 0.5

    def test_calculate_greeks_put(self, engine):
        S = 4000.0
        K = 4000.0
        T = 0.25
        sigma = 0.20

        greeks = engine.calculate_greeks(S, K, T, sigma, is_call=False)

        assert greeks is not None
        assert -0.55 < greeks.delta < -0.45
        assert greeks.gamma > 0

    def test_calculate_greeks_edge_cases(self, engine):
        assert engine.calculate_greeks(0, 4000, 0.25, 0.2, True) is None
        assert engine.calculate_greeks(4000, 0, 0.25, 0.2, True) is None
        assert engine.calculate_greeks(4000, 4000, 0, 0.2, True) is None
        assert engine.calculate_greeks(4000, 4000, 0.25, 0, True) is None

    def test_price_option_chain(self, engine):
        options = [
            {"code": "io2506C3800", "strike": 3800.0, "latest": 250.0, "is_call": True},
            {"code": "io2506C4000", "strike": 4000.0, "latest": 100.0, "is_call": True},
            {"code": "io2506C4200", "strike": 4200.0, "latest": 30.0, "is_call": True},
        ]
        spot = 4000.0
        expiry = date.today() + timedelta(days=90)

        results = engine.price_option_chain(options, spot, expiry)

        assert len(results) == 3
        for opt in results:
            assert opt.get("delta") is not None
            assert opt.get("gamma") is not None
            assert opt.get("theta") is not None
            assert opt.get("vega") is not None
            assert opt.get("iv") is not None
            assert -1 <= opt["delta"] <= 1

    def test_price_option_chain_with_puts(self, engine):
        options = [
            {"code": "io2506P3800", "strike": 3800.0, "latest": 20.0, "is_call": False},
            {"code": "io2506P4000", "strike": 4000.0, "latest": 80.0, "is_call": False},
        ]
        spot = 4000.0
        expiry = date.today() + timedelta(days=90)

        results = engine.price_option_chain(options, spot, expiry)

        assert len(results) == 2
        for opt in results:
            assert opt.get("delta") is not None
            assert -1 <= opt["delta"] <= 0

    def test_price_option_chain_default_volatility(self, engine):
        options = [
            {"code": "io2506C4000", "strike": 4000.0, "latest": None, "is_call": True},
        ]
        spot = 4000.0
        expiry = date.today() + timedelta(days=90)

        results = engine.price_option_chain(
            options, spot, expiry, default_volatility=0.25
        )

        assert len(results) == 1
        assert results[0].get("iv") == 0.25

    def test_price_option_chain_empty(self, engine):
        results = engine.price_option_chain([], 4000.0)
        assert results == []

    def test_price_option_chain_zero_spot(self, engine):
        options = [{"code": "test", "strike": 4000.0, "latest": 100.0, "is_call": True}]
        results = engine.price_option_chain(options, 0.0)
        assert results[0].get("delta") is None


class TestGreeksResult:
    """Tests for GreeksResult dataclass"""

    def test_greeks_result_creation(self):
        from app.services.pricing.black_scholes import GreeksResult

        result = GreeksResult(
            delta=0.5, gamma=0.001, theta=-0.02, vega=0.15, rho=0.01, iv=0.20
        )

        assert result.delta == 0.5
        assert result.gamma == 0.001
        assert result.theta == -0.02
        assert result.vega == 0.15
        assert result.rho == 0.01
        assert result.iv == 0.20

    def test_greeks_result_optional_iv(self):
        from app.services.pricing.black_scholes import GreeksResult

        result = GreeksResult(delta=0.5, gamma=0.001, theta=-0.02, vega=0.15, rho=0.01)

        assert result.iv is None


class TestPricingEngineIntegration:
    """Integration tests with py_vollib"""

    def test_py_vollib_available(self):
        try:
            from py_vollib import black_scholes_merton

            assert True
        except ImportError:
            pytest.skip("py_vollib not installed")

    def test_full_workflow(self):
        from app.services.pricing.black_scholes import OptionsPricingEngine

        engine = OptionsPricingEngine(risk_free_rate=0.025, dividend_yield=0.02)

        S = 4000.0
        K = 4000.0
        T = 0.25
        sigma = 0.20

        from py_vollib.black_scholes_merton import black_scholes_merton

        price = black_scholes_merton("c", S, K, T, engine.r, sigma, engine.q)

        iv, method = engine.calculate_iv(price, S, K, T, is_call=True)
        assert iv is not None

        greeks = engine.calculate_greeks(S, K, T, iv, is_call=True)
        assert greeks is not None

        assert abs(greeks.delta - 0.5) < 0.1
