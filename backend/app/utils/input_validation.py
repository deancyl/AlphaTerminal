"""
Input Validation Utilities for AlphaTerminal.

Provides reusable validation functions for:
- Stock symbols (A股、港股、美股)
- Date strings
- Numeric bounds
- Pagination parameters
"""
import re
from datetime import datetime
from typing import Optional, Tuple


SYMBOL_PATTERN_A_STOCK = re.compile(r'^((sh|sz)?[0-9]{6}|[0-9]{6})$')
SYMBOL_PATTERN_HK_STOCK = re.compile(r'^((hk)?[0-9]{5}|[0-9]{4,5})$')
SYMBOL_PATTERN_US_STOCK = re.compile(r'^((us)?[A-Z]{1,5}|[A-Z]{1,5})$')
SYMBOL_PATTERN_ALL = re.compile(r'^((sh|sz|hk|us)?[0-9A-Z]{4,6}|[0-9A-Z]{4,6})$')


def validate_stock_symbol(symbol: str, market: str = "all") -> Tuple[bool, str, str]:
    """
    Validate stock symbol format.
    
    Args:
        symbol: Stock symbol to validate
        market: Market type ("astock", "hk", "us", "all")
    
    Returns:
        (is_valid, normalized_symbol, error_message)
    """
    if not symbol:
        return False, "", "股票代码不能为空"
    
    symbol = symbol.strip().upper()
    
    if len(symbol) > 20:
        return False, "", "股票代码长度不能超过20字符"
    
    if market == "astock":
        if not SYMBOL_PATTERN_A_STOCK.match(symbol):
            return False, "", "A股代码格式错误，应为6位数字（如 600519）"
    elif market == "hk":
        if not SYMBOL_PATTERN_HK_STOCK.match(symbol):
            return False, "", "港股代码格式错误，应为4-5位数字（如 00700）"
    elif market == "us":
        if not SYMBOL_PATTERN_US_STOCK.match(symbol):
            return False, "", "美股代码格式错误，应为1-5位字母（如 AAPL）"
    else:
        if not SYMBOL_PATTERN_ALL.match(symbol):
            return False, "", "股票代码格式错误"
    
    normalized = normalize_symbol(symbol)
    return True, normalized, ""


def normalize_symbol(symbol: str) -> str:
    """
    Normalize symbol to standard format.
    
    A股: sh600519, sz000001
    港股: hk00700
    股: usAAPL
    """
    if not symbol:
        return symbol
    
    symbol = symbol.strip().upper()
    
    if symbol.startswith("SH") or symbol.startswith("SZ"):
        return symbol.lower()
    
    if symbol.startswith("HK"):
        return symbol.lower()
    
    if symbol.startswith("US"):
        return symbol.lower()
    
    if re.match(r'^[0-9]{6}$', symbol):
        if symbol.startswith('6'):
            return f"sh{symbol}"
        else:
            return f"sz{symbol}"
    
    if re.match(r'^[0-9]{4,5}$', symbol):
        return f"hk{symbol}"
    
    if re.match(r'^[A-Z]{1,5}$', symbol):
        return f"us{symbol}"
    
    return symbol


def validate_date_string(date_str: str, format: str = "%Y-%m-%d") -> Tuple[bool, Optional[datetime], str]:
    """
    Validate date string format.
    
    Args:
        date_str: Date string to validate
        format: Expected date format
    
    Returns:
        (is_valid, parsed_date, error_message)
    """
    if not date_str:
        return False, None, "日期不能为空"
    
    try:
        parsed = datetime.strptime(date_str.strip(), format)
        return True, parsed, ""
    except ValueError:
        return False, None, f"日期格式错误，应为 {format.replace('%Y', 'YYYY').replace('%m', 'MM').replace('%d', 'DD')}"


def validate_date_range(
    start_date: str,
    end_date: str,
    max_days: int = 3650,
    min_days: int = 1
) -> Tuple[bool, int, str]:
    """
    Validate date range.
    
    Args:
        start_date: Start date string
        end_date: End date string
        max_days: Maximum allowed days between dates
        min_days: Minimum required days between dates
    
    Returns:
        (is_valid, days_span, error_message)
    """
    valid_start, start, err_start = validate_date_string(start_date)
    if not valid_start or start is None:
        return False, 0, err_start
    
    valid_end, end, err_end = validate_date_string(end_date)
    if not valid_end or end is None:
        return False, 0, err_end
    
    days_span = (end - start).days
    
    if days_span < min_days:
        return False, days_span, f"时间跨度不足 {min_days} 天"
    
    if days_span > max_days:
        return False, days_span, f"时间跨度超过 {max_days} 天"
    
    return True, days_span, ""


def validate_numeric_bounds(
    value: float,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None,
    field_name: str = "数值"
) -> Tuple[bool, float, str]:
    """
    Validate numeric value within bounds.
    
    Args:
        value: Numeric value to validate
        min_val: Minimum allowed value
        max_val: Maximum allowed value
        field_name: Field name for error message
    
    Returns:
        (is_valid, value, error_message)
    """
    if value is None:
        return False, 0, f"{field_name}不能为空"
    
    try:
        value = float(value)
    except (TypeError, ValueError):
        return False, 0, f"{field_name}必须是数字"
    
    if min_val is not None and value < min_val:
        return False, value, f"{field_name}不能小于 {min_val}"
    
    if max_val is not None and value > max_val:
        return False, value, f"{field_name}不能大于 {max_val}"
    
    return True, value, ""


def validate_pagination(
    page: int,
    page_size: int,
    max_page_size: int = 100,
    max_page: int = 10000
) -> Tuple[bool, int, int, str]:
    """
    Validate pagination parameters.
    
    Args:
        page: Page number
        page_size: Page size
        max_page_size: Maximum allowed page size
        max_page: Maximum allowed page number
    
    Returns:
        (is_valid, normalized_page, normalized_page_size, error_message)
    """
    if page is None or page < 1:
        page = 1
    
    if page_size is None or page_size < 1:
        page_size = 20
    
    if page > max_page:
        return False, 1, 20, f"页码不能超过 {max_page}"
    
    if page_size > max_page_size:
        return False, 1, 20, f"每页数量不能超过 {max_page_size}"
    
    return True, page, page_size, ""


def sanitize_string(value: str, max_length: int = 500) -> str:
    """
    Sanitize string input.
    
    - Strip whitespace
    - Limit length
    - Remove dangerous characters
    """
    if not value:
        return ""
    
    value = value.strip()
    
    if len(value) > max_length:
        value = value[:max_length]
    
    dangerous_chars = ['<', '>', '"', "'", '\n', '\r', '\t']
    for char in dangerous_chars:
        value = value.replace(char, '')
    
    return value


__all__ = [
    "validate_stock_symbol",
    "normalize_symbol",
    "validate_date_string",
    "validate_date_range",
    "validate_numeric_bounds",
    "validate_pagination",
    "sanitize_string",
]