"""
Black-Scholes-Merton Options Pricing Engine

Uses py_vollib for vectorized Greeks calculation.
Default parameters calibrated for Chinese A-share market.
"""
import logging
import math
from dataclasses import dataclass
from datetime import datetime, date, timezone
from typing import Optional, Dict, Any, List, Tuple

import numpy as np
import httpx

logger = logging.getLogger(__name__)


@dataclass
class GreeksResult:
    """Container for all Greeks values"""
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    iv: Optional[float] = None


class OptionsPricingEngine:
    """
    Black-Scholes-Merton pricing engine using py_vollib.
    
    Default parameters:
        - Risk-free rate: 2.5% (China 10Y treasury)
        - Dividend yield: 2.0% (HS300 average dividend)
    """
    
    def __init__(
        self,
        risk_free_rate: float = 0.025,
        dividend_yield: float = 0.02,
    ):
        self.r = risk_free_rate
        self.q = dividend_yield
        self._vol_lib = None
        self._vol_lib_vec = None
    
    @property
    def vol_lib(self):
        """Lazy load vollib (py_vollib is deprecated)"""
        if self._vol_lib is None:
            try:
                from vollib.black_scholes_merton import black_scholes_merton
                from vollib.black_scholes_merton.implied_volatility import implied_volatility
                from vollib.black_scholes_merton.greeks.analytical import (
                    delta as calc_delta,
                    gamma as calc_gamma,
                    vega as calc_vega,
                    theta as calc_theta,
                    rho as calc_rho,
                )
                self._vol_lib = {
                    'bsm': black_scholes_merton,
                    'iv': implied_volatility,
                    'delta': calc_delta,
                    'gamma': calc_gamma,
                    'vega': calc_vega,
                    'theta': calc_theta,
                    'rho': calc_rho,
                }
            except ImportError as e:
                logger.error(f"[Pricing] vollib not installed: {e}", exc_info=True)
                raise ImportError("vollib required. Install: pip install py_vollib")
        return self._vol_lib
    
    @property
    def vol_lib_vec(self):
        """Lazy load py_vollib_vectorized"""
        if self._vol_lib_vec is None:
            try:
                import py_vollib_vectorized
                self._vol_lib_vec = py_vollib_vectorized
            except ImportError:
                logger.warning("[Pricing] py_vollib_vectorized not available, using scalar mode", exc_info=True)
                self._vol_lib_vec = None
        return self._vol_lib_vec
    
    def calculate_time_to_expiry(
        self,
        expiry_date: date,
        current_date: Optional[date] = None,
    ) -> float:
        """
        Calculate time to expiry in years.
        
        Args:
            expiry_date: Option expiration date
            current_date: Current date (defaults to today)
            
        Returns:
            Time to expiry in years (minimum 1/365 to avoid division by zero)
        """
        if current_date is None:
            current_date = date.today()
        
        days = (expiry_date - current_date).days
        days = max(days, 1)
        return days / 365.0
    
    def parse_expiry_from_code(self, code: str) -> Optional[date]:
        """
        Parse expiry date from CFFEX contract code.
        
        Examples:
            io2506 -> 2025-06-21 (third Friday of June)
            mo2509 -> 2025-09-19 (third Friday of September)
        
        Args:
            code: Contract code like "io2506" or "mo2509"
            
        Returns:
            Expiration date (third Friday of the month)
        """
        try:
            if len(code) < 5:
                return None
            
            year_part = code[-4:-2]
            month_part = code[-2:]
            
            year = 2000 + int(year_part)
            month = int(month_part)
            
            first_day = date(year, month, 1)
            
            first_friday = 1 + (4 - first_day.weekday()) % 7
            third_friday = first_friday + 14
            
            return date(year, month, third_friday)
            
        except (ValueError, IndexError) as e:
            logger.warning(f"[Pricing] Failed to parse expiry from code: {code} - {e}", exc_info=True)
            return None
    
    def bisection_iv(
        self,
        price: float,
        S: float,
        K: float,
        T: float,
        r: float,
        q: float,
        option_type: str,
        max_iterations: int = 100,
        tolerance: float = 1e-6
    ) -> Optional[float]:
        """
        Bisection method for implied volatility (fallback).
        
        Used when vollib's lets_be_rational fails for edge cases
        (deep OTM, near expiry).
        
        Args:
            price: Option market price
            S: Underlying spot price
            K: Strike price
            T: Time to expiry in years
            r: Risk-free rate
            q: Dividend yield
            option_type: 'call' or 'put'
            max_iterations: Maximum iterations (default 100)
            tolerance: Price tolerance for convergence (default 1e-6)
            
        Returns:
            Implied volatility, or None if calculation fails
        """
        sigma_low = 0.001
        sigma_high = 5.0
        
        flag = 'c' if option_type == 'call' else 'p'
        
        for _ in range(max_iterations):
            sigma_mid = (sigma_low + sigma_high) / 2
            
            try:
                price_mid = self.vol_lib['bsm'](flag, S, K, T, r, sigma_mid, q)
            except (ValueError, TypeError, ZeroDivisionError):
                price_mid = None
            
            if price_mid is None:
                sigma_high = sigma_mid
                continue
            
            if abs(price_mid - price) < tolerance:
                return sigma_mid
            
            if price_mid < price:
                sigma_low = sigma_mid
            else:
                sigma_high = sigma_mid
        
        return (sigma_low + sigma_high) / 2
    
    def calculate_iv(
        self,
        price: float,
        spot: float,
        strike: float,
        time_to_expiry: float,
        is_call: bool = True,
    ) -> Tuple[Optional[float], Optional[str]]:
        """
        Calculate implied volatility using Householder 3rd order method.
        
        Falls back to bisection method for edge cases where lets_be_rational fails.
        
        Args:
            price: Option market price
            spot: Underlying spot price
            strike: Strike price
            time_to_expiry: Time to expiry in years
            is_call: True for call, False for put
            
        Returns:
            Tuple of (implied volatility, method name)
            - method: 'rational_approximation' or 'bisection' or None
        """
        if price <= 0 or spot <= 0 or strike <= 0 or time_to_expiry <= 0:
            return None, None
        
        flag = 'c' if is_call else 'p'
        option_type = 'call' if is_call else 'put'
        
        # Try vollib's lets_be_rational first
        try:
            iv = self.vol_lib['iv'](
                price, spot, strike, time_to_expiry, self.r, self.q, flag
            )
            
            if math.isfinite(iv) and iv > 0:
                return iv, 'rational_approximation'
        except Exception as e:
            logger.debug(f"[Pricing] IV rational_approximation failed: S={spot}, K={strike}, T={time_to_expiry:.4f}, P={price} - {e}")
        
        # Fallback to bisection method
        iv = self.bisection_iv(price, spot, strike, time_to_expiry, is_call)
        if iv is not None and math.isfinite(iv) and iv > 0:
            return iv, 'bisection'
        
        return None, None
    

    async def get_risk_free_rate_async(self) -> float:
        """
        Fetch current risk-free rate from Bond module's 10Y treasury yield.
        
        Returns:
            Risk-free rate as decimal (e.g., 0.0275 for 2.75%)
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    'http://localhost:8002/api/v1/bond/risk_free_rate'
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success') and data.get('data', {}).get('rate'):
                        return float(data['data']['rate'])
        except Exception as e:
            logger.debug(f"[Pricing] Failed to fetch risk-free rate: {e}")
        
        # Fallback to default
        return self.r
    
    def bisection_iv(
        self,
        price: float,
        spot: float,
        strike: float,
        time_to_expiry: float,
        is_call: bool = True,
        max_iterations: int = 100,
        tolerance: float = 1e-6
    ) -> Optional[float]:
        """
        Bisection method for implied volatility calculation.
        
        Used as fallback when rational approximation fails.
        
        Args:
            price: Option market price
            spot: Underlying spot price
            strike: Strike price
            time_to_expiry: Time to expiry in years
            is_call: True for call, False for put
            max_iterations: Maximum iterations (default: 100)
            tolerance: Convergence tolerance (default: 1e-6)
            
        Returns:
            Implied volatility or None if convergence fails
        """
        if price <= 0 or spot <= 0 or strike <= 0 or time_to_expiry <= 0:
            return None
        
        flag = 'c' if is_call else 'p'
        
        sigma_low = 0.001
        sigma_high = 5.0
        
        for _ in range(max_iterations):
            sigma_mid = (sigma_low + sigma_high) / 2
            
            try:
                price_mid = self.vol_lib['bsm'](
                    flag, spot, strike, time_to_expiry, self.r, sigma_mid, self.q
                )
                
                if abs(price_mid - price) < tolerance:
                    return sigma_mid
                
                if price_mid < price:
                    sigma_low = sigma_mid
                else:
                    sigma_high = sigma_mid
            except (ValueError, TypeError, ZeroDivisionError):
                # If BSM fails, narrow the range
                sigma_high = sigma_mid
        
        return None

    def calculate_greeks(
        self,
        spot: float,
        strike: float,
        time_to_expiry: float,
        volatility: float,
        is_call: bool = True,
    ) -> Optional[GreeksResult]:
        """
        Calculate all Greeks using Black-Scholes-Merton model.
        
        Args:
            spot: Underlying spot price
            strike: Strike price
            time_to_expiry: Time to expiry in years
            volatility: Implied or historical volatility (annualized)
            is_call: True for call, False for put
            
        Returns:
            GreeksResult with delta, gamma, theta, vega, rho
        """
        if spot <= 0 or strike <= 0 or time_to_expiry <= 0 or volatility <= 0:
            return None
        
        flag = 'c' if is_call else 'p'
        
        try:
            delta = self.vol_lib['delta'](
                flag, spot, strike, time_to_expiry, self.r, volatility, self.q
            )
            gamma = self.vol_lib['gamma'](
                flag, spot, strike, time_to_expiry, self.r, volatility, self.q
            )
            theta = self.vol_lib['theta'](
                flag, spot, strike, time_to_expiry, self.r, volatility, self.q
            )
            vega = self.vol_lib['vega'](
                flag, spot, strike, time_to_expiry, self.r, volatility, self.q
            )
            rho = self.vol_lib['rho'](
                flag, spot, strike, time_to_expiry, self.r, volatility, self.q
            )
            
            if not all(math.isfinite(g) for g in [delta, gamma, theta, vega, rho]):
                return None
            
            return GreeksResult(
                delta=delta,
                gamma=gamma,
                theta=theta,
                vega=vega,
                rho=rho,
                iv=volatility,
            )
            
        except (ValueError, RuntimeError) as e:
            logger.debug(f"[Pricing] Greeks calculation failed: {e}")
            return None
    
    def price_option_chain(
        self,
        options: List[Dict[str, Any]],
        spot: float,
        expiry_date: Optional[date] = None,
        default_volatility: float = 0.20,
    ) -> List[Dict[str, Any]]:
        """
        Calculate Greeks for an entire option chain.
        
        Args:
            options: List of option dicts with keys:
                - code: Contract code
                - strike: Strike price
                - latest: Market price
                - is_call: True for call, False for put
            spot: Underlying spot price
            expiry_date: Expiration date (parsed from code if None)
            default_volatility: Default IV if calculation fails (20% annual)
            
        Returns:
            List of options with Greeks added
        """
        if not options or spot <= 0:
            return options
        
        results = []
        
        for opt in options:
            result = opt.copy()
            
            strike = opt.get('strike')
            price = opt.get('latest')
            is_call = opt.get('is_call', True)
            code = opt.get('code', '')
            
            if strike is None or strike <= 0:
                results.append(result)
                continue
            
            if expiry_date is None:
                expiry_date = self.parse_expiry_from_code(code)
            
            if expiry_date is None:
                expiry_date = date.today()
            
            T = self.calculate_time_to_expiry(expiry_date)
            
            iv = None
            iv_method = None
            if price and price > 0:
                iv, iv_method = self.calculate_iv(price, spot, strike, T, is_call)
            
            if iv is None:
                iv = default_volatility
            
            greeks = self.calculate_greeks(spot, strike, T, iv, is_call)
            
            if greeks:
                result['delta'] = round(greeks.delta, 4)
                result['gamma'] = round(greeks.gamma, 4)
                result['theta'] = round(greeks.theta, 4)
                result['vega'] = round(greeks.vega, 4)
                result['rho'] = round(greeks.rho, 4)
                result['iv'] = round(greeks.iv, 4) if greeks.iv else None
            
            results.append(result)
        
        return results


pricing_engine = OptionsPricingEngine()
