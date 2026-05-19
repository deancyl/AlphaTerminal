"""
Greeks Calculator - High-level interface for chain-wide Greeks calculation

Integrates with market data to calculate Greeks for entire option chains.
"""
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

from app.services.options.pricing_engine import BlackScholesEngine, GreeksResult

logger = logging.getLogger(__name__)


class GreeksCalculator:
    """
    High-level Greeks calculator for option chains.
    
    Usage:
        calc = GreeksCalculator()
        
        # Calculate Greeks for CFFEX chain
        chain_with_greeks = await calc.calculate_chain_greeks(
            chain_data=chain,
            underlying_price=4000.0,
            risk_free_rate=0.03
        )
    """
    
    # Contract code pattern: io2506C1800 (index option call 1800 strike)
    CFFEX_PATTERN = re.compile(r'([a-z]+)(\d{4})([CP])(\d+)', re.IGNORECASE)
    
    # Default risk-free rate (can be overridden)
    DEFAULT_RISK_FREE_RATE = 0.025  # 2.5%
    
    # Default volatility for initial calculation
    DEFAULT_VOLATILITY = 0.20  # 20%
    
    def __init__(self):
        self.engine = BlackScholesEngine()
    
    def parse_expiry_from_code(self, contract_code: str) -> Optional[datetime]:
        """
        Parse expiry date from CFFEX contract code.
        
        Examples:
            io2506 -> June 2025 (third Friday)
            mo2506 -> June 2025 (third Friday)
        
        Returns:
            Expiry date (third Friday of the month) or None
        """
        # Extract year and month from code
        match = re.match(r'[a-z]+(\d{4})', contract_code, re.IGNORECASE)
        if not match:
            return None
        
        yymm = match.group(1)
        if len(yymm) != 4:
            return None
        
        try:
            year = 2000 + int(yymm[:2])
            month = int(yymm[2:4])
            
            # Find third Friday of the month
            first_day = datetime(year, month, 1)
            
            # Find first Friday
            days_until_friday = (4 - first_day.weekday()) % 7
            first_friday = first_day + timedelta(days=days_until_friday)
            
            # Third Friday
            third_friday = first_friday + timedelta(weeks=2)
            
            return third_friday
            
        except (ValueError, IndexError):
            return None
    
    def calculate_time_to_expiry(
        self,
        expiry_date: datetime,
        current_time: Optional[datetime] = None
    ) -> float:
        """
        Calculate time to expiry in years.
        
        Args:
            expiry_date: Option expiry date
            current_time: Current time (default: now)
        
        Returns:
            Time to expiry in years (minimum: 0.001 to avoid division by zero)
        """
        if current_time is None:
            current_time = datetime.now()
        
        delta = expiry_date - current_time
        days = delta.total_seconds() / 86400.0
        
        # Minimum 1 day to avoid numerical issues
        return max(days / 365.0, 1.0 / 365.0)
    
    def calculate_option_greeks(
        self,
        strike: float,
        underlying_price: float,
        time_to_expiry: float,
        risk_free_rate: float,
        option_type: str,
        option_price: Optional[float] = None,
        volatility: Optional[float] = None
    ) -> Dict[str, Optional[float]]:
        """
        Calculate Greeks for a single option.
        
        Args:
            strike: Strike price
            underlying_price: Current underlying price
            time_to_expiry: Time to expiry in years
            risk_free_rate: Risk-free rate (decimal)
            option_type: 'call' or 'put'
            option_price: Market price (for IV calculation)
            volatility: Volatility (if known)
        
        Returns:
            Dict with delta, gamma, theta, vega, rho, iv
        """
        try:
            result = self.engine.calculate_greeks_with_iv(
                S=underlying_price,
                K=strike,
                T=time_to_expiry,
                r=risk_free_rate,
                option_type=option_type,
                option_price=option_price,
                sigma=volatility
            )
            
            return {
                'delta': round(result.delta, 6),
                'gamma': round(result.gamma, 8),
                'theta': round(result.theta, 4),
                'vega': round(result.vega, 4),
                'rho': round(result.rho, 4),
                'iv': round(result.iv, 6) if result.iv else None,
            }
            
        except Exception as e:
            logger.warning(f"[Greeks] Calculation failed: {e}")
            return {
                'delta': None,
                'gamma': None,
                'theta': None,
                'vega': None,
                'rho': None,
                'iv': None,
            }
    
    def calculate_chain_greeks(
        self,
        chain_data: Dict[str, Any],
        underlying_price: float,
        risk_free_rate: Optional[float] = None,
        volatility: Optional[float] = None,
        contract_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate Greeks for entire option chain.
        
        Args:
            chain_data: Chain data from options_fetcher
                {
                    'calls': [...],
                    'puts': [...],
                    'symbol': 'io2506',
                    ...
                }
            underlying_price: Current underlying index price
            risk_free_rate: Risk-free rate (default: 2.5%)
            volatility: Default volatility (default: 20%)
            contract_code: Contract code for expiry parsing
        
        Returns:
            Chain data with Greeks added to each option
        """
        risk_free_rate = risk_free_rate or self.DEFAULT_RISK_FREE_RATE
        volatility = volatility or self.DEFAULT_VOLATILITY
        
        # Parse expiry from contract code
        symbol = contract_code or chain_data.get('symbol', '')
        expiry_date = self.parse_expiry_from_code(symbol)
        
        if expiry_date is None:
            logger.warning(f"[Greeks] Cannot parse expiry from: {symbol}")
            return chain_data
        
        time_to_expiry = self.calculate_time_to_expiry(expiry_date)
        
        logger.info(
            f"[Greeks] Calculating Greeks for {symbol}: "
            f"S={underlying_price:.2f}, T={time_to_expiry:.4f}y, r={risk_free_rate:.4f}"
        )
        
        # Calculate Greeks for calls
        calls = chain_data.get('calls', [])
        for call in calls:
            strike = call.get('strike')
            price = call.get('latest')
            
            if strike is None:
                continue
            
            greeks = self.calculate_option_greeks(
                strike=strike,
                underlying_price=underlying_price,
                time_to_expiry=time_to_expiry,
                risk_free_rate=risk_free_rate,
                option_type='call',
                option_price=price,
                volatility=volatility
            )
            
            call.update(greeks)
        
        # Calculate Greeks for puts
        puts = chain_data.get('puts', [])
        for put in puts:
            strike = put.get('strike')
            price = put.get('latest')
            
            if strike is None:
                continue
            
            greeks = self.calculate_option_greeks(
                strike=strike,
                underlying_price=underlying_price,
                time_to_expiry=time_to_expiry,
                risk_free_rate=risk_free_rate,
                option_type='put',
                option_price=price,
                volatility=volatility
            )
            
            put.update(greeks)
        
        # Add metadata
        chain_data['greeks_calculated'] = True
        chain_data['greeks_params'] = {
            'underlying_price': underlying_price,
            'risk_free_rate': risk_free_rate,
            'time_to_expiry': time_to_expiry,
            'expiry_date': expiry_date.isoformat() if expiry_date else None,
        }
        
        return chain_data
    
    def get_underlying_symbol(self, option_symbol: str) -> str:
        """
        Get underlying index symbol from option symbol.
        
        Examples:
            io2506 -> sh000300 (沪深300)
            mo2506 -> sh000852 (中证1000)
        """
        prefix = option_symbol[:2].lower()
        
        mapping = {
            'io': 'sh000300',  # 沪深300
            'mo': 'sh000852',  # 中证1000
        }
        
        return mapping.get(prefix, 'sh000300')
