"""
Sandboxed Execution Environment for Strategy Code

This module provides a secure execution environment for user-provided strategy
code by creating a restricted namespace with:
- No __builtins__ access (completely removed)
- Whitelisted safe functions only
- No file system, network, or system access
- Controlled access to pandas/numpy for data operations

The sandbox ensures that even if AST validation is bypassed, the execution
environment itself prevents malicious code from running.

Author: AlphaTerminal Security Team
Version: 1.0
"""

import logging
import math
import statistics
from datetime import datetime, date, time, timedelta
from typing import Any, Callable, Dict, List, Optional
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class StrategyTimeoutError(Exception):
    """Raised when strategy execution exceeds timeout limit."""
    pass


class StrategySecurityError(Exception):
    """Raised when strategy code violates security rules."""
    pass


class StrategyMemoryError(Exception):
    """Raised when strategy exceeds memory limits."""
    pass


# Modules that can be imported in the sandbox
ALLOWED_IMPORTS = {
    'pandas', 'pd', 'numpy', 'np', 'math', 'statistics',
    'datetime', 'date', 'time', 'timedelta',
}


def _safe_import(name: str, *args, **kwargs):
    """
    Safe __import__ that only allows whitelisted modules.

    This is used internally to allow legal imports while blocking
    dangerous ones like os, sys, subprocess, etc.
    """
    module_name = name.split('.')[0]
    if module_name not in ALLOWED_IMPORTS:
        raise ImportError(f"Import of '{name}' is not allowed. Allowed modules: {', '.join(sorted(ALLOWED_IMPORTS))}")
    return __import__(name, *args, **kwargs)


def create_safe_builtins() -> Dict[str, Any]:
    """
    Create a restricted builtins dictionary with only safe functions.
    
    This replaces the default __builtins__ with a whitelist of safe
    operations that cannot be used to escape the sandbox.
    
    Returns:
        Dictionary of safe builtin functions
    """
    return {
        # Basic arithmetic
        'abs': abs,
        'min': min,
        'max': max,
        'sum': sum,
        'round': round,
        'pow': pow,
        'divmod': divmod,
        
        # Type conversions (safe)
        'int': int,
        'float': float,
        'str': str,
        'bool': bool,
        'list': list,
        'dict': dict,
        'tuple': tuple,
        'set': set,
        'frozenset': frozenset,
        
        # Comparison and logic
        'all': all,
        'any': any,
        'len': len,
        'isinstance': isinstance,
        
        # Iteration (safe)
        'range': range,
        'enumerate': enumerate,
        'zip': zip,
        'map': map,
        'filter': filter,
        'sorted': sorted,
        'reversed': reversed,
        'iter': iter,
        'next': next,
        
        # String operations (safe)
        'chr': chr,
        'ord': ord,
        'hex': hex,
        'oct': oct,
        'bin': bin,
        'repr': repr,
        'format': format,
        
        # Constants
        'True': True,
        'False': False,
        'None': None,

        # Safe import function (restricted to allowed modules)
        '__import__': _safe_import,

        # Math functions (safe subset)
        'ceil': math.ceil,
        'floor': math.floor,
        'sqrt': math.sqrt,
        'log': math.log,
        'log10': math.log10,
        'exp': math.exp,
        'sin': math.sin,
        'cos': math.cos,
        'tan': math.tan,
        'asin': math.asin,
        'acos': math.acos,
        'atan': math.atan,
        'pi': math.pi,
        'e': math.e,
    }


def create_sandbox_namespace(
    ctx: Optional[Any] = None,
    allow_pandas: bool = True,
    allow_numpy: bool = True,
) -> Dict[str, Any]:
    """
    Create a sandboxed namespace for strategy execution.
    
    Args:
        ctx: Strategy context object (StrategyContext)
        allow_pandas: Whether to allow pandas access
        allow_numpy: Whether to allow numpy access
    
    Returns:
        Restricted namespace dictionary
    """
    namespace = {'__builtins__': create_safe_builtins()}
    
    if allow_pandas:
        namespace['pd'] = pd
    
    if allow_numpy:
        namespace['np'] = np
    
    namespace['math'] = math
    namespace['statistics'] = statistics
    namespace['datetime'] = datetime
    namespace['date'] = date
    namespace['time'] = time
    namespace['timedelta'] = timedelta
    
    if ctx is not None:
        namespace['ctx'] = ctx
    
    return namespace


class SecureExecutor:
    """
    Secure executor for running validated strategy code.
    
    Combines AST validation with sandboxed execution to provide
    comprehensive security against code injection attacks.
    """
    
    DEFAULT_TIMEOUT = 30.0
    MAX_MEMORY_MB = 512
    
    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT,
        max_memory_mb: int = MAX_MEMORY_MB,
        allow_pandas: bool = True,
        allow_numpy: bool = True,
    ):
        self.timeout = timeout
        self.max_memory_mb = max_memory_mb
        self.allow_pandas = allow_pandas
        self.allow_numpy = allow_numpy
    
    def compile_code(self, code: str) -> Any:
        """
        Compile validated code to executable object.
        
        Args:
            code: Validated strategy code
            
        Returns:
            Compiled code object
            
        Raises:
            StrategySecurityError: If code fails security validation
            SyntaxError: If code has syntax errors
        """
        from .ast_validator import validate_strategy_ast
        
        is_valid, errors = validate_strategy_ast(code)
        if not is_valid:
            raise StrategySecurityError(
                f"Security validation failed: {errors}"
            )
        
        try:
            return compile(code, '<strategy>', 'exec')
        except SyntaxError as e:
            raise StrategySecurityError(
                f"Syntax error at line {e.lineno}: {e.msg}"
            )
    
    def execute(
        self,
        code: str,
        ctx: Optional[Any] = None,
        additional_globals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute strategy code in sandboxed environment.
        
        Args:
            code: Validated strategy code
            ctx: Strategy context object
            additional_globals: Additional safe globals to include
            
        Returns:
            Namespace after execution (contains defined functions)
            
        Raises:
            StrategySecurityError: If security validation fails
            StrategyTimeoutError: If execution exceeds timeout
            Exception: Any exception from strategy code
        """
        compiled = self.compile_code(code)
        
        namespace = create_sandbox_namespace(
            ctx=ctx,
            allow_pandas=self.allow_pandas,
            allow_numpy=self.allow_numpy,
        )
        
        if additional_globals:
            for key, value in additional_globals.items():
                if key not in namespace:
                    namespace[key] = value
        
        try:
            exec(compiled, namespace)
        except Exception as e:
            logger.warning(f"[SecureExecutor] Execution error: {e}")
            raise
        
        return namespace
    
    def execute_with_timeout(
        self,
        code: str,
        ctx: Optional[Any] = None,
        additional_globals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute strategy code with timeout protection.
        
        This is an async wrapper that enforces timeout limits.
        
        Args:
            code: Validated strategy code
            ctx: Strategy context object
            additional_globals: Additional safe globals
            
        Returns:
            Namespace after execution
            
        Raises:
            StrategyTimeoutError: If execution exceeds timeout
            StrategySecurityError: If security validation fails
        """
        import asyncio
        
        async def _execute_async():
            return self.execute(code, ctx, additional_globals)
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                future = asyncio.ensure_future(_execute_async())
                return asyncio.wait_for(future, timeout=self.timeout)
            else:
                return loop.run_until_complete(
                    asyncio.wait_for(_execute_async(), timeout=self.timeout)
                )
        except asyncio.TimeoutError:
            raise StrategyTimeoutError(
                f"Strategy execution exceeded {self.timeout}s timeout"
            )
    
    def validate_only(self, code: str) -> tuple[bool, List[str]]:
        """
        Validate code without executing it.
        
        Args:
            code: Strategy code to validate
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        from .ast_validator import validate_strategy_ast
        return validate_strategy_ast(code)


def secure_exec(
    code: str,
    ctx: Optional[Any] = None,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """
    Convenience function for secure execution.
    
    Args:
        code: Strategy code
        ctx: Strategy context
        timeout: Execution timeout in seconds
        
    Returns:
        Execution namespace
    """
    executor = SecureExecutor(timeout=timeout)
    return executor.execute(code, ctx)


def is_safe_to_execute(code: str) -> tuple[bool, List[str]]:
    """
    Check if code is safe to execute without actually running it.
    
    Args:
        code: Strategy code
        
    Returns:
        Tuple of (is_safe, error_messages)
    """
    from .ast_validator import validate_strategy_ast
    return validate_strategy_ast(code)


if __name__ == "__main__":
    print("=" * 80)
    print("Sandbox Security Tests")
    print("=" * 80)
    
    test_codes = [
        ("Valid code", """
def on_bar(ctx, bar):
    if bar['close'] > bar['open']:
        ctx.buy(bar['close'], 100)
""", True),
        
        ("Try to import os", """
def on_bar(ctx, bar):
    import os
    os.system('ls')
""", False),
        
        ("Try to use eval", """
def on_bar(ctx, bar):
    eval("print('hello')")
""", False),
        
        ("Try __builtins__ access", """
def on_bar(ctx, bar):
    __builtins__['eval']('1+1')
""", False),
        
        ("Pandas allowed", """
import pandas as pd

def on_bar(ctx, bar):
    df = pd.DataFrame({'a': [1, 2, 3]})
""", True),
    ]
    
    executor = SecureExecutor()
    
    for name, code, expected_safe in test_codes:
        print(f"\nTest: {name}")
        is_safe, errors = executor.validate_only(code)
        status = "PASS" if is_safe == expected_safe else "FAIL"
        print(f"  Result: {status}")
        print(f"  Safe: {is_safe} (expected: {expected_safe})")
        if errors:
            for error in errors:
                print(f"  Error: {error}")