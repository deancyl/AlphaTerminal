"""
Safe math utilities to prevent division by zero and invalid number operations.
Mirrors frontend/src/utils/safeMath.js for consistency.
"""

from typing import Union, List, Optional
import math
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation


def safe_divide(dividend: Union[int, float], divisor: Union[int, float], default_value: float = 0.0) -> float:
    """
    Safely divide two numbers, returning default_value if division is invalid.
    
    Args:
        dividend: The number to divide
        divisor: The number to divide by
        default_value: Value to return if division is invalid (default: 0.0)
    
    Returns:
        Result of division, or default_value if divisor is 0, None, NaN, or Infinity
    
    Examples:
        >>> safe_divide(100, 10)
        10.0
        >>> safe_divide(100, 0)
        0.0
        >>> safe_divide(100, 0, default_value=-1)
        -1.0
        >>> safe_divide(100, float('inf'))
        0.0
    """
    if divisor is None or divisor == 0 or (isinstance(divisor, float) and (math.isnan(divisor) or math.isinf(divisor))):
        return default_value
    
    result = dividend / divisor
    
    if math.isnan(result) or math.isinf(result):
        return default_value
    
    return result


def safe_percent(part: Union[int, float], total: Union[int, float], default_value: float = 0.0) -> float:
    """
    Safely calculate percentage, returning default_value if total is invalid.
    
    Args:
        part: The part value
        total: The total value
        default_value: Value to return if calculation is invalid
    
    Returns:
        Percentage (part/total * 100), or default_value if invalid
    
    Examples:
        >>> safe_percent(50, 100)
        50.0
        >>> safe_percent(50, 0)
        0.0
    """
    return safe_divide(part * 100, total, default_value)


def safe_average(values: Optional[List[Union[int, float]]], default_value: float = 0.0) -> float:
    """
    Safely calculate average of a list, filtering out None/NaN/Infinity values.
    
    Args:
        values: List of numbers
        default_value: Value to return if list is empty or all values are invalid
    
    Returns:
        Average of valid values, or default_value if no valid values
    
    Examples:
        >>> safe_average([1, 2, 3])
        2.0
        >>> safe_average([1, None, 3])
        2.0
        >>> safe_average([])
        0.0
        >>> safe_average([None, float('nan')])
        0.0
    """
    if not values or not isinstance(values, (list, tuple)):
        return default_value
    
    valid_values = [
        v for v in values 
        if v is not None and isinstance(v, (int, float)) and not math.isnan(v) and not math.isinf(v)
    ]
    
    if not valid_values:
        return default_value
    
    return sum(valid_values) / len(valid_values)


def safe_round(value: Union[int, float], decimals: int = 2, default_value: float = 0.0) -> float:
    """
    Safely round a number, returning default_value if value is invalid.
    
    Args:
        value: The number to round
        decimals: Number of decimal places
        default_value: Value to return if value is invalid
    
    Returns:
        Rounded value, or default_value if value is None/NaN/Infinity
    """
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return default_value
    
    return round(float(value), decimals)


def precise_pnl(shares: Union[int, float], sell_price: Union[int, float], avg_cost: Union[int, float], decimals: int = 4) -> float:
    """
    Calculate PnL with Decimal precision to avoid floating-point errors.
    
    Args:
        shares: Number of shares
        sell_price: Sell price per share
        avg_cost: Average cost per share
        decimals: Number of decimal places for result (default: 4)
    
    Returns:
        Realized PnL with precise calculation
    
    Examples:
        >>> precise_pnl(100, 10.5, 10.0)
        50.0
        >>> precise_pnl(100, 10.123456789, 10.0)
        12.3457
    """
    try:
        s = Decimal(str(shares))
        sp = Decimal(str(sell_price))
        ac = Decimal(str(avg_cost))
        result = s * (sp - ac)
        quantize_str = '0.' + '0' * decimals
        return float(result.quantize(Decimal(quantize_str), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError, TypeError):
        return 0.0


def precise_multiply(*values: Union[int, float], decimals: int = 4) -> float:
    """
    Multiply values with Decimal precision.
    
    Args:
        *values: Values to multiply
        decimals: Number of decimal places for result
    
    Returns:
        Product with precise calculation
    """
    try:
        result = Decimal('1')
        for v in values:
            result *= Decimal(str(v))
        quantize_str = '0.' + '0' * decimals
        return float(result.quantize(Decimal(quantize_str), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError, TypeError):
        return 0.0


def precise_add(*values: Union[int, float], decimals: int = 4) -> float:
    """
    Add values with Decimal precision.
    
    Args:
        *values: Values to add
        decimals: Number of decimal places for result
    
    Returns:
        Sum with precise calculation
    """
    try:
        result = Decimal('0')
        for v in values:
            result += Decimal(str(v))
        quantize_str = '0.' + '0' * decimals
        return float(result.quantize(Decimal(quantize_str), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError, TypeError):
        return 0.0
