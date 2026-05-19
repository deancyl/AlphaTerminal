"""
Black-Scholes-Merton Option Pricing Engine

Implements European option pricing and Greeks calculation using the BSM model.
All formulas are mathematically precise using scipy.stats.norm for cumulative
distribution functions.

Key Features:
- Delta, Gamma, Theta, Vega, Rho calculation
- Newton-Raphson implied volatility solver
- Support for both Call and Put options
- Numerical stability with edge case handling
"""
import math
import logging
from typing import Optional, Tuple, Literal
from scipy.stats import norm
from dataclasses import dataclass

logger = logging.getLogger(__name__)

OptionType = Literal['call', 'put']


@dataclass
class GreeksResult:
    """Container for option Greeks and price."""
    price: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    iv: Optional[float] = None


class BlackScholesEngine:
    """
    Black-Scholes-Merton option pricing engine.
    
    Usage:
        engine = BlackScholesEngine()
        
        # Calculate Greeks with known volatility
        greeks = engine.calculate_greeks(
            S=4000, K=4000, T=0.25, r=0.03, sigma=0.2, option_type='call'
        )
        
        # Calculate IV from market price
        iv = engine.implied_volatility(
            option_price=50, S=4000, K=4100, T=0.25, r=0.03, option_type='call'
        )
    """
    
    # Newton-Raphson solver parameters
    MAX_ITER = 100
    TOLERANCE = 1e-6
    MIN_VOL = 0.001
    MAX_VOL = 5.0
    
    def __init__(self):
        self._norm_cdf = norm.cdf
        self._norm_pdf = norm.pdf
    
    def _d1(self, S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate d1 parameter for BSM model."""
        if T <= 0 or sigma <= 0:
            return 0.0
        
        sqrt_T = math.sqrt(T)
        d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
        return d1
    
    def _d2(self, d1: float, T: float, sigma: float) -> float:
        """Calculate d2 parameter for BSM model."""
        if T <= 0 or sigma <= 0:
            return 0.0
        return d1 - sigma * math.sqrt(T)
    
    def price(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: OptionType
    ) -> float:
        """
        Calculate option price using Black-Scholes formula.
        
        Args:
            S: Underlying asset price
            K: Strike price
            T: Time to expiry in years
            r: Risk-free interest rate (decimal, e.g., 0.03 for 3%)
            sigma: Volatility (decimal, e.g., 0.2 for 20%)
            option_type: 'call' or 'put'
        
        Returns:
            Option price
        """
        # Edge cases
        if T <= 0:
            # At expiry, option value is intrinsic value
            if option_type == 'call':
                return max(S - K, 0.0)
            else:
                return max(K - S, 0.0)
        
        if sigma <= 0:
            # Zero volatility: deterministic future
            if option_type == 'call':
                return max(S * math.exp(-r * T) - K * math.exp(-r * T), 0.0)
            else:
                return max(K * math.exp(-r * T) - S * math.exp(-r * T), 0.0)
        
        d1 = self._d1(S, K, T, r, sigma)
        d2 = self._d2(d1, T, sigma)
        
        discount = math.exp(-r * T)
        
        if option_type == 'call':
            price = S * self._norm_cdf(d1) - K * discount * self._norm_cdf(d2)
        else:  # put
            price = K * discount * self._norm_cdf(-d2) - S * self._norm_cdf(-d1)
        
        return max(price, 0.0)
    
    def delta(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: OptionType
    ) -> float:
        """
        Calculate option Delta (price sensitivity to underlying).
        
        Call Delta = N(d1)
        Put Delta = N(d1) - 1
        """
        if T <= 0 or sigma <= 0:
            if option_type == 'call':
                return 1.0 if S > K else 0.0
            else:
                return -1.0 if S < K else 0.0
        
        d1 = self._d1(S, K, T, r, sigma)
        
        if option_type == 'call':
            return self._norm_cdf(d1)
        else:  # put
            return self._norm_cdf(d1) - 1.0
    
    def gamma(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float
    ) -> float:
        """
        Calculate option Gamma (delta sensitivity to underlying).
        
        Gamma = N'(d1) / (S * sigma * sqrt(T))
        
        Note: Same for both call and put.
        """
        if T <= 0 or sigma <= 0 or S <= 0:
            return 0.0
        
        d1 = self._d1(S, K, T, r, sigma)
        sqrt_T = math.sqrt(T)
        
        gamma = self._norm_pdf(d1) / (S * sigma * sqrt_T)
        return gamma
    
    def vega(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float
    ) -> float:
        """
        Calculate option Vega (price sensitivity to volatility).
        
        Vega = S * sqrt(T) * N'(d1)
        
        Note: Same for both call and put. Returns value per 1.0 (100%) change in vol.
        For per 1% change, divide by 100.
        """
        if T <= 0 or sigma <= 0:
            return 0.0
        
        d1 = self._d1(S, K, T, r, sigma)
        sqrt_T = math.sqrt(T)
        
        vega = S * sqrt_T * self._norm_pdf(d1)
        return vega
    
    def theta(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: OptionType
    ) -> float:
        """
        Calculate option Theta (time decay per year).
        
        Call Theta = -S * N'(d1) * sigma / (2*sqrt(T)) - r * K * e^(-rT) * N(d2)
        Put Theta = -S * N'(d1) * sigma / (2*sqrt(T)) + r * K * e^(-rT) * N(-d2)
        
        Note: Returns value per year. For per day, divide by 365.
        """
        if T <= 0 or sigma <= 0:
            return 0.0
        
        d1 = self._d1(S, K, T, r, sigma)
        d2 = self._d2(d1, T, sigma)
        sqrt_T = math.sqrt(T)
        discount = math.exp(-r * T)
        
        # Common term
        common = -S * self._norm_pdf(d1) * sigma / (2 * sqrt_T)
        
        if option_type == 'call':
            theta = common - r * K * discount * self._norm_cdf(d2)
        else:  # put
            theta = common + r * K * discount * self._norm_cdf(-d2)
        
        return theta
    
    def rho(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: OptionType
    ) -> float:
        """
        Calculate option Rho (price sensitivity to interest rate).
        
        Call Rho = K * T * e^(-rT) * N(d2)
        Put Rho = -K * T * e^(-rT) * N(-d2)
        
        Note: Returns value per 1.0 (100%) change in rate. For per 1% change, divide by 100.
        """
        if T <= 0 or sigma <= 0:
            return 0.0
        
        d1 = self._d1(S, K, T, r, sigma)
        d2 = self._d2(d1, T, sigma)
        discount = math.exp(-r * T)
        
        if option_type == 'call':
            rho = K * T * discount * self._norm_cdf(d2)
        else:  # put
            rho = -K * T * discount * self._norm_cdf(-d2)
        
        return rho
    
    def calculate_greeks(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: OptionType
    ) -> GreeksResult:
        """
        Calculate all Greeks for an option.
        
        Returns:
            GreeksResult with price, delta, gamma, theta, vega, rho
        """
        price = self.price(S, K, T, r, sigma, option_type)
        delta = self.delta(S, K, T, r, sigma, option_type)
        gamma = self.gamma(S, K, T, r, sigma)
        vega = self.vega(S, K, T, r, sigma)
        theta = self.theta(S, K, T, r, sigma, option_type)
        rho = self.rho(S, K, T, r, sigma, option_type)
        
        return GreeksResult(
            price=price,
            delta=delta,
            gamma=gamma,
            theta=theta,
            vega=vega,
            rho=rho
        )
    
    def implied_volatility(
        self,
        option_price: float,
        S: float,
        K: float,
        T: float,
        r: float,
        option_type: OptionType,
        max_iter: int = None,
        tol: float = None
    ) -> Optional[float]:
        """
        Calculate implied volatility using Newton-Raphson method.
        
        The Newton-Raphson iteration:
            sigma_new = sigma - (price - market_price) / vega
        
        Args:
            option_price: Market price of the option
            S: Underlying asset price
            K: Strike price
            T: Time to expiry in years
            r: Risk-free interest rate
            option_type: 'call' or 'put'
            max_iter: Maximum iterations (default: 100)
            tol: Convergence tolerance (default: 1e-6)
        
        Returns:
            Implied volatility (decimal), or None if solver fails
        """
        max_iter = max_iter or self.MAX_ITER
        tol = tol or self.TOLERANCE
        
        # Edge cases
        if T <= 0:
            logger.warning("[BSM] Cannot calculate IV for expired option")
            return None
        
        if option_price <= 0:
            logger.warning("[BSM] Cannot calculate IV for zero/negative price")
            return None
        
        # Initial guess: 20% volatility
        sigma = 0.2
        
        for i in range(max_iter):
            # Calculate price and vega at current sigma
            price = self.price(S, K, T, r, sigma, option_type)
            vega = self.vega(S, K, T, r, sigma)
            
            # Check for near-zero vega (deep ITM/OTM options)
            if abs(vega) < 1e-10:
                logger.warning(f"[BSM] Vega too small at iteration {i}, cannot solve IV")
                return None
            
            # Newton-Raphson update
            diff = price - option_price
            sigma_new = sigma - diff / vega
            
            # Ensure sigma stays positive
            sigma_new = max(self.MIN_VOL, min(self.MAX_VOL, sigma_new))
            
            # Check convergence
            if abs(sigma_new - sigma) < tol:
                logger.debug(f"[BSM] IV converged at iteration {i}: {sigma_new:.6f}")
                return sigma_new
            
            sigma = sigma_new
        
        # Did not converge
        logger.warning(f"[BSM] IV solver did not converge after {max_iter} iterations")
        return sigma  # Return last estimate
    
    def calculate_greeks_with_iv(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        option_type: OptionType,
        option_price: Optional[float] = None,
        sigma: Optional[float] = None
    ) -> GreeksResult:
        """
        Calculate Greeks, optionally solving for IV from market price.
        
        If option_price is provided, IV is calculated via Newton-Raphson.
        Otherwise, sigma must be provided.
        
        Args:
            S: Underlying price
            K: Strike price
            T: Time to expiry
            r: Risk-free rate
            option_type: 'call' or 'put'
            option_price: Market price (for IV calculation)
            sigma: Volatility (if known)
        
        Returns:
            GreeksResult with all Greeks including IV
        """
        # Determine volatility
        iv = None
        if option_price is not None and option_price > 0:
            iv = self.implied_volatility(option_price, S, K, T, r, option_type)
            sigma = iv or sigma
        
        if sigma is None:
            logger.warning("[BSM] No volatility available, using default 0.2")
            sigma = 0.2
        
        # Calculate Greeks
        result = self.calculate_greeks(S, K, T, r, sigma, option_type)
        result.iv = iv or sigma
        
        return result
