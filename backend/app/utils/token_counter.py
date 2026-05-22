"""
Token counting utility using tiktoken for accurate token counting.

Handles Chinese content correctly (unlike len(text.split())).
Falls back gracefully if tiktoken is not available.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_tiktoken_available = None
_encoding_cache = {}


def clear_cache():
    """Clear the encoding cache."""
    global _encoding_cache
    _encoding_cache = {}


def _check_tiktoken() -> bool:
    """Check if tiktoken is available (cached)."""
    global _tiktoken_available
    if _tiktoken_available is None:
        try:
            import tiktoken
            _tiktoken_available = True
        except ImportError:
            _tiktoken_available = False
            logger.warning("[TokenCounter] tiktoken not installed, falling back to word count", exc_info=True)
    return _tiktoken_available


def _get_encoding(model: str):
    """Get tiktoken encoding for a model (cached)."""
    if model in _encoding_cache:
        return _encoding_cache[model]
    
    try:
        import tiktoken
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")
        _encoding_cache[model] = encoding
        return encoding
    except ImportError:
        return None


def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    """
    Count tokens in text using tiktoken.
    
    Args:
        text: Text to count tokens for
        model: Model name (e.g., "gpt-3.5-turbo", "gpt-4", "deepseek-chat")
               Falls back to cl100k_base encoding for unknown models.
    
    Returns:
        Number of tokens in the text.
        Falls back to word count if tiktoken is not available.
    
    Examples:
        >>> count_tokens("Hello world")
        2
        >>> count_tokens("你好世界")  # Chinese text
        4
        >>> count_tokens("Hello 世界")  # Mixed
        4
    """
    if not text:
        return 0
    
    if not _check_tiktoken():
        return len(text.split())
    
    encoding = _get_encoding(model)
    if encoding is None:
        return len(text.split())
    
    try:
        return len(encoding.encode(text))
    except Exception as e:
        logger.warning(f"[TokenCounter] Error encoding text: {e}, falling back to word count", exc_info=True)
        return len(text.split())


def count_messages_tokens(messages: list[dict], model: str = "gpt-3.5-turbo") -> int:
    """
    Count tokens in a list of chat messages.
    
    Args:
        messages: List of message dicts with "role" and "content" keys
        model: Model name for token counting
    
    Returns:
        Total token count including message formatting overhead.
    """
    if not messages:
        return 0
    
    total = 0
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        total += count_tokens(role, model)
        total += count_tokens(content, model)
        total += 4  # Approximate overhead for message formatting
    
    total += 2  # Approximate overhead for reply priming
    return total
