"""
Unit tests for Black-Scholes Pricing Engine

Tests cover:
- Option pricing (call/put)
- Greeks calculation (delta, gamma, theta, vega, rho)
- Implied volatility solver (Newton-Raphson)
- Edge cases (expiry, zero volatility)
"""
import pytest
import math
from app.services.options.pricing_engine import BlackScholesEngine, GreeksResult


class TestBlackScholesPricing:
    """Test option pricing calculations."""
    
    @pytest.fixture
    def engine(self):
        return BlackScholesEngine()
    
    def test_atm_call_price(self, engine):
        """Test ATM call option pricing."""
        S = 4000.0
        K = 4000.0
        T = 0.25  # 3 months
        r = 0.03
        sigma = 0.20
        
        price = engine.price(S, K, T, r, sigma, 'call')
        
        # ATM call should be approximately:
        # S*N(d1) - K*e^(-rT)*N(d2)
        # With these params, price should be around 150-200
        assert 150 < price < 200, f"ATM call price {price} out of expected range"
    
    def test_atm_put_price(self, engine):
        """Test ATM put option pricing."""
        S = 4000.0
        K = 4000.0
        T = 0.25
        r = 0.03
        sigma = 0.20
        
        price = engine.price(S, K, T, r, sigma, 'put')
        
        # ATM put should be around 140-150
        assert 130 < price < 160, f"ATM put price {price} out of expected range"
    
    def test_call_put_parity(self, engine):
        """Test put-call parity: C - P = S - K*e^(-rT)"""
        S = 4000.0
        K = 4000.0
        T = 0.25
        r = 0.03
        sigma = 0.20
        
        call_price = engine.price(S, K, T, r, sigma, 'call')
        put_price = engine.price(S, K, T, r, sigma, 'put')
        
        # Put-call parity
        import math
        parity_diff = call_price - put_price
        expected_diff = S - K * math.exp(-r * T)
        
        assert abs(parity_diff - expected_diff) < 0.01, \
            f"Put-call parity violated: {parity_diff} vs {expected_diff}"
    
    def test_itm_call(self, engine):
        """Test in-the-money call."""
        S = 4000.0
        K = 3800.0  # ITM by 200
        T = 0.25
        r = 0.03
        sigma = 0.20
        
        price = engine.price(S, K, T, r, sigma, 'call')
        
        # ITM call should be > intrinsic value (200)
        assert price > 200, f"ITM call price {price} should be > intrinsic value 200"
    
    def test_otm_call(self, engine):
        """Test out-of-the-money call."""
        S = 4000.0
        K = 4200.0  # OTM by 200
        T = 0.25
        r = 0.03
        sigma = 0.20
        
        price = engine.price(S, K, T, r, sigma, 'call')
        
        # OTM call should be < ATM call
        atm_price = engine.price(4000, 4000, 0.25, 0.03, 0.20, 'call')
        assert price < atm_price, f"OTM call {price} should be < ATM call {atm_price}"
        assert price > 0, "OTM call should have positive value"
    
    def test_expired_option(self, engine):
        """Test option at expiry (T=0)."""
        S = 4000.0
        K = 3800.0
        T = 0.0  # Expired
        r = 0.03
        sigma = 0.20
        
        call_price = engine.price(S, K, T, r, sigma, 'call')
        put_price = engine.price(S, K, T, r, sigma, 'put')
        
        # At expiry, value = intrinsic value
        assert call_price == 200.0, f"Expired ITM call should equal intrinsic value: {call_price}"
        assert put_price == 0.0, f"Expired OTM put should be zero: {put_price}"


class TestGreeksCalculation:
    """Test Greeks calculations."""
    
    @pytest.fixture
    def engine(self):
        return BlackScholesEngine()
    
    def test_atm_call_delta(self, engine):
        """Test ATM call delta should be ~0.5."""
        S = 4000.0
        K = 4000.0
        T = 0.25
        r = 0.03
        sigma = 0.20
        
        delta = engine.delta(S, K, T, r, sigma, 'call')
        
        # ATM call delta should be slightly > 0.5 due to forward price effect
        assert 0.50 < delta < 0.60, f"ATM call delta {delta} out of expected range"
    
    def test_atm_put_delta(self, engine):
        """Test ATM put delta should be ~-0.5."""
        S = 4000.0
        K = 4000.0
        T = 0.25
        r = 0.03
        sigma = 0.20
        
        delta = engine.delta(S, K, T, r, sigma, 'put')
        
        # ATM put delta should be around -0.45
        assert -0.51 < delta < -0.44, f"ATM put delta {delta} out of expected range"
    
    def test_call_put_delta_sum(self, engine):
        """Test call delta - put delta = 1 (approximately)."""
        S = 4000.0
        K = 4000.0
        T = 0.25
        r = 0.03
        sigma = 0.20
        
        call_delta = engine.delta(S, K, T, r, sigma, 'call')
        put_delta = engine.delta(S, K, T, r, sigma, 'put')
        
        # Call delta - Put delta should be approximately 1
        assert abs(call_delta - put_delta - 1.0) < 0.01, \
            f"Delta relationship violated: {call_delta} - {put_delta} != 1"
    
    def test_gamma_positive(self, engine):
        """Test gamma is always positive."""
        S = 4000.0
        K = 4000.0
        T = 0.25
        r = 0.03
        sigma = 0.20
        
        gamma = engine.gamma(S, K, T, r, sigma)
        
        assert gamma > 0, f"Gamma should be positive: {gamma}"
        
        # ATM gamma should be around 0.001 for these params
        assert 0.0005 < gamma < 0.002, f"ATM gamma {gamma} out of expected range"
    
    def test_vega_positive(self, engine):
        """Test vega is always positive."""
        S = 4000.0
        K = 4000.0
        T = 0.25
        r = 0.03
        sigma = 0.20
        
        vega = engine.vega(S, K, T, r, sigma)
        
        assert vega > 0, f"Vega should be positive: {vega}"
        
        # ATM vega should be around 700-900 for these params
        assert 600 < vega < 1000, f"ATM vega {vega} out of expected range"
    
    def test_theta_negative(self, engine):
        """Test theta is typically negative (time decay)."""
        S = 4000.0
        K = 4000.0
        T = 0.25
        r = 0.03
        sigma = 0.20
        
        call_theta = engine.theta(S, K, T, r, sigma, 'call')
        put_theta = engine.theta(S, K, T, r, sigma, 'put')
        
        # ATM theta should be negative (time decay)
        assert call_theta < 0, f"Call theta should be negative: {call_theta}"
        
        # Put theta can be positive for deep ITM puts due to interest rate effect
        # But ATM put theta should be negative
        assert put_theta < 0, f"ATM put theta should be negative: {put_theta}"
    
    def test_calculate_all_greeks(self, engine):
        """Test calculate_greeks returns all values."""
        result = engine.calculate_greeks(
            S=4000, K=4000, T=0.25, r=0.03, sigma=0.20, option_type='call'
        )
        
        assert isinstance(result, GreeksResult)
        assert result.price > 0
        assert 0 < result.delta < 1
        assert result.gamma > 0
        assert result.theta < 0
        assert result.vega > 0
        assert result.rho > 0


class TestImpliedVolatility:
    """Test implied volatility calculation."""
    
    @pytest.fixture
    def engine(self):
        return BlackScholesEngine()
    
    def test_iv_recovery(self, engine):
        """Test IV solver can recover known volatility."""
        S = 4000.0
        K = 4000.0
        T = 0.25
        r = 0.03
        true_sigma = 0.20
        
        # Calculate price with known sigma
        price = engine.price(S, K, T, r, true_sigma, 'call')
        
        # Recover IV from price
        iv = engine.implied_volatility(price, S, K, T, r, 'call')
        
        assert iv is not None, "IV solver failed to converge"
        assert abs(iv - true_sigma) < 0.01, \
            f"IV {iv} does not match true sigma {true_sigma}"
    
    def test_iv_otm_option(self, engine):
        """Test IV for OTM option."""
        S = 4000.0
        K = 4200.0  # OTM
        T = 0.25
        r = 0.03
        true_sigma = 0.25
        
        price = engine.price(S, K, T, r, true_sigma, 'call')
        iv = engine.implied_volatility(price, S, K, T, r, 'call')
        
        assert iv is not None
        assert abs(iv - true_sigma) < 0.02, \
            f"OTM IV {iv} does not match {true_sigma}"
    
    def test_iv_put_option(self, engine):
        """Test IV for put option."""
        S = 4000.0
        K = 4000.0
        T = 0.25
        r = 0.03
        true_sigma = 0.18
        
        price = engine.price(S, K, T, r, true_sigma, 'put')
        iv = engine.implied_volatility(price, S, K, T, r, 'put')
        
        assert iv is not None
        assert abs(iv - true_sigma) < 0.01, \
            f"Put IV {iv} does not match {true_sigma}"
    
    def test_iv_zero_price(self, engine):
        """Test IV solver handles zero price."""
        iv = engine.implied_volatility(0.0, 4000, 4000, 0.25, 0.03, 'call')
        
        assert iv is None, "IV should be None for zero price"
    
    def test_iv_expired_option(self, engine):
        """Test IV solver handles expired option."""
        iv = engine.implied_volatility(50.0, 4000, 4000, 0.0, 0.03, 'call')
        
        assert iv is None, "IV should be None for expired option"
    
    def test_iv_convergence_iterations(self, engine):
        """Test IV solver converges within reasonable iterations."""
        S = 4000.0
        K = 4000.0
        T = 0.25
        r = 0.03
        sigma = 0.30
        
        price = engine.price(S, K, T, r, sigma, 'call')
        
        # Should converge within 100 iterations (default)
        iv = engine.implied_volatility(price, S, K, T, r, 'call', max_iter=20)
        
        assert iv is not None
        assert abs(iv - sigma) < 0.02


class TestEdgeCases:
    """Test edge cases and numerical stability."""
    
    @pytest.fixture
    def engine(self):
        return BlackScholesEngine()
    
    def test_deep_itm_call(self, engine):
        """Test deep in-the-money call."""
        S = 4000.0
        K = 3000.0  # Deep ITM
        T = 0.25
        r = 0.03
        sigma = 0.20
        
        price = engine.price(S, K, T, r, sigma, 'call')
        delta = engine.delta(S, K, T, r, sigma, 'call')
        
        # Deep ITM call should be close to intrinsic value
        assert price > 950, f"Deep ITM call price {price} too low"
        assert delta > 0.95, f"Deep ITM delta {delta} should be close to 1"
    
    def test_deep_otm_call(self, engine):
        """Test deep out-of-the-money call."""
        S = 4000.0
        K = 5000.0  # Deep OTM
        T = 0.25
        r = 0.03
        sigma = 0.20
        
        price = engine.price(S, K, T, r, sigma, 'call')
        delta = engine.delta(S, K, T, r, sigma, 'call')
        
        # Deep OTM call should have minimal value
        assert price < 10, f"Deep OTM call price {price} too high"
        assert delta < 0.1, f"Deep OTM delta {delta} should be close to 0"
    
    def test_short_dated_option(self, engine):
        """Test option with very short time to expiry."""
        S = 4000.0
        K = 4000.0
        T = 0.01  # ~3.6 days
        r = 0.03
        sigma = 0.20
        
        price = engine.price(S, K, T, r, sigma, 'call')
        
        # Short-dated ATM option should have minimal time value
        assert price < 40, f"Short-dated ATM call price {price} too high"
    
    def test_long_dated_option(self, engine):
        """Test option with long time to expiry."""
        S = 4000.0
        K = 4000.0
        T = 2.0  # 2 years
        r = 0.03
        sigma = 0.20
        
        price = engine.price(S, K, T, r, sigma, 'call')
        
        # Long-dated option should have significant time value
        assert price > 300, f"Long-dated ATM call price {price} too low"
    
    def test_high_volatility(self, engine):
        """Test option with high volatility."""
        S = 4000.0
        K = 4000.0
        T = 0.25
        r = 0.03
        sigma = 0.80  # 80% vol
        
        price = engine.price(S, K, T, r, sigma, 'call')
        
        # High vol should increase option price
        assert price > 300, f"High vol call price {price} too low"
    
    def test_zero_volatility(self, engine):
        """Test option with zero volatility."""
        S = 4000.0
        K = 3800.0  # ITM
        T = 0.25
        r = 0.03
        sigma = 0.0
        
        price = engine.price(S, K, T, r, sigma, 'call')
        
        # Zero vol: deterministic future, price = discounted intrinsic
        import math
        expected = max(S * math.exp(-r * T) - K * math.exp(-r * T), 0)
        assert abs(price - expected) < 0.5, f"Zero vol price {price} != {expected}"


class TestGreeksWithIV:
    """Test calculate_greeks_with_iv method."""
    
    @pytest.fixture
    def engine(self):
        return BlackScholesEngine()
    
    def test_greeks_with_market_price(self, engine):
        """Test Greeks calculation with IV from market price."""
        S = 4000.0
        K = 4000.0
        T = 0.25
        r = 0.03
        
        # Simulate market price at 20% vol
        market_price = engine.price(S, K, T, r, 0.20, 'call')
        
        result = engine.calculate_greeks_with_iv(
            S=S, K=K, T=T, r=r, option_type='call', option_price=market_price
        )
        
        assert result.iv is not None
        assert abs(result.iv - 0.20) < 0.01, f"IV {result.iv} != 0.20"
        assert result.price > 0
        assert result.delta > 0
    
    def test_greeks_with_known_sigma(self, engine):
        """Test Greeks calculation with known volatility."""
        result = engine.calculate_greeks_with_iv(
            S=4000, K=4000, T=0.25, r=0.03, option_type='call', sigma=0.25
        )
        
        assert result.iv == 0.25
        assert result.price > 0
