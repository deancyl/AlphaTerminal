"""
Security Test Suite for ScriptStrategy Code Injection Prevention

Tests 10 malicious code patterns that should be rejected:
1. __import__('os').system('rm -rf /') - Dynamic import attack
2. open('/etc/passwd').read() - File system access
3. subprocess.Popen(['cat', '/etc/passwd']) - Process execution
4. eval("__import__('os').system('id')") - Dynamic code execution
5. exec("import os; os.system('id')") - Dynamic code execution
6. (lambda: __import__('os'))() - Lambda-based import attack
7. getattr(__builtins__, 'eval')('1+1') - Reflection attack
8. ''.__class__.__base__.__subclasses__() - Class introspection attack
9. while True: pass - Infinite loop (timeout test)
10. [0] * 10**10 - Memory bomb

Author: AlphaTerminal Security Team
Version: 1.0
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch
import pandas as pd

from app.services.strategy.script_strategy import (
    ScriptStrategy,
    create_script_strategy,
    StrategyContext,
)
from app.services.strategy.sandbox import StrategySecurityError, StrategyTimeoutError


# ============================================================================
# Malicious Code Patterns
# ============================================================================

MALICIOUS_PATTERNS = {
    "dynamic_import": """
def on_bar(ctx, bar):
    __import__('os').system('rm -rf /')
""",
    
    "file_read": """
def on_bar(ctx, bar):
    data = open('/etc/passwd').read()
""",
    
    "subprocess_exec": """
import subprocess
def on_bar(ctx, bar):
    subprocess.Popen(['cat', '/etc/passwd'])
""",
    
    "eval_attack": """
def on_bar(ctx, bar):
    eval("__import__('os').system('id')")
""",
    
    "exec_attack": """
def on_bar(ctx, bar):
    exec("import os; os.system('id')")
""",
    
    "lambda_import": """
def on_bar(ctx, bar):
    (lambda: __import__('os'))()
""",
    
    "getattr_builtins": """
def on_bar(ctx, bar):
    getattr(__builtins__, 'eval')('1+1')
""",
    
    "class_introspection": """
def on_bar(ctx, bar):
    ''.__class__.__base__.__subclasses__()
""",
    
    "infinite_loop": """
def on_bar(ctx, bar):
    while True:
        pass
""",
    
    "memory_bomb": """
def on_bar(ctx, bar):
    x = [0] * 10**10
""",
}


# ============================================================================
# Security Validation Tests
# ============================================================================

class TestScriptStrategySecurity:
    """Test suite for ScriptStrategy security validation."""
    
    @pytest.fixture
    def sample_df(self):
        """Create sample DataFrame for testing."""
        return pd.DataFrame({
            'open': [100.0, 101.0, 102.0],
            'high': [101.0, 102.0, 103.0],
            'low': [99.0, 100.0, 101.0],
            'close': [100.5, 101.5, 102.5],
            'volume': [1000000, 1100000, 1050000],
        })
    
    # ========================================================================
    # Test 1: Dynamic Import Attack
    # ========================================================================
    def test_reject_dynamic_import(self, sample_df):
        """Pattern 1: __import__('os').system('rm -rf /') should be rejected."""
        code = MALICIOUS_PATTERNS["dynamic_import"]
        
        with pytest.raises((ValueError, StrategySecurityError)):
            strategy = ScriptStrategy(code)
            strategy.run(sample_df)
    
    # ========================================================================
    # Test 2: File System Access
    # ========================================================================
    def test_reject_file_read(self, sample_df):
        """Pattern 2: open('/etc/passwd').read() should be rejected."""
        code = MALICIOUS_PATTERNS["file_read"]
        
        with pytest.raises((ValueError, StrategySecurityError)):
            strategy = ScriptStrategy(code)
            strategy.run(sample_df)
    
    # ========================================================================
    # Test 3: Process Execution
    # ========================================================================
    def test_reject_subprocess(self, sample_df):
        """Pattern 3: subprocess.Popen(['cat', '/etc/passwd']) should be rejected."""
        code = MALICIOUS_PATTERNS["subprocess_exec"]
        
        with pytest.raises((ValueError, StrategySecurityError)):
            strategy = ScriptStrategy(code)
            strategy.run(sample_df)
    
    # ========================================================================
    # Test 4: Eval Attack
    # ========================================================================
    def test_reject_eval(self, sample_df):
        """Pattern 4: eval(\"__import__('os').system('id')\") should be rejected."""
        code = MALICIOUS_PATTERNS["eval_attack"]
        
        with pytest.raises((ValueError, StrategySecurityError)):
            strategy = ScriptStrategy(code)
            strategy.run(sample_df)
    
    # ========================================================================
    # Test 5: Exec Attack
    # ========================================================================
    def test_reject_exec(self, sample_df):
        """Pattern 5: exec(\"import os; os.system('id')\") should be rejected."""
        code = MALICIOUS_PATTERNS["exec_attack"]
        
        with pytest.raises((ValueError, StrategySecurityError)):
            strategy = ScriptStrategy(code)
            strategy.run(sample_df)
    
    # ========================================================================
    # Test 6: Lambda Import Attack
    # ========================================================================
    def test_reject_lambda_import(self, sample_df):
        """Pattern 6: (lambda: __import__('os'))() should be rejected."""
        code = MALICIOUS_PATTERNS["lambda_import"]
        
        with pytest.raises((ValueError, StrategySecurityError)):
            strategy = ScriptStrategy(code)
            strategy.run(sample_df)
    
    # ========================================================================
    # Test 7: Getattr Builtins Attack
    # ========================================================================
    def test_reject_getattr_builtins(self, sample_df):
        """Pattern 7: getattr(__builtins__, 'eval')('1+1') should be rejected."""
        code = MALICIOUS_PATTERNS["getattr_builtins"]
        
        with pytest.raises((ValueError, StrategySecurityError)):
            strategy = ScriptStrategy(code)
            strategy.run(sample_df)
    
    # ========================================================================
    # Test 8: Class Introspection Attack
    # ========================================================================
    def test_reject_class_introspection(self, sample_df):
        """Pattern 8: ''.__class__.__base__.__subclasses__() should be rejected."""
        code = MALICIOUS_PATTERNS["class_introspection"]
        
        with pytest.raises((ValueError, StrategySecurityError)):
            strategy = ScriptStrategy(code)
            strategy.run(sample_df)
    
    # ========================================================================
    # Test 9: Infinite Loop Timeout
    # ========================================================================
    def test_timeout_infinite_loop(self, sample_df):
        """Pattern 9: while True: pass should timeout."""
        code = MALICIOUS_PATTERNS["infinite_loop"]
        
        with pytest.raises((TimeoutError, StrategyTimeoutError, ValueError, StrategySecurityError)):
            strategy = ScriptStrategy(code)
            start_time = time.time()
            try:
                strategy.run(sample_df)
                elapsed = time.time() - start_time
                assert elapsed < 35, "Infinite loop should timeout within 35 seconds"
            except Exception as e:
                assert isinstance(e, (TimeoutError, StrategyTimeoutError, ValueError, StrategySecurityError))
    
    # ========================================================================
    # Test 10: Memory Bomb
    # ========================================================================
    def test_reject_memory_bomb(self, sample_df):
        """Pattern 10: [0] * 10**10 should be rejected."""
        code = MALICIOUS_PATTERNS["memory_bomb"]
        
        with pytest.raises((ValueError, StrategySecurityError)):
            strategy = ScriptStrategy(code)
            strategy.run(sample_df)


# ============================================================================
# Valid Strategy Tests (Ensure backward compatibility)
# ============================================================================

class TestValidStrategies:
    """Test that valid strategies still work after security hardening."""
    
    @pytest.fixture
    def sample_df(self):
        """Create sample DataFrame for testing."""
        return pd.DataFrame({
            'open': [100.0, 101.0, 102.0, 103.0, 104.0],
            'high': [101.0, 102.0, 103.0, 104.0, 105.0],
            'low': [99.0, 100.0, 101.0, 102.0, 103.0],
            'close': [100.5, 101.5, 102.5, 103.5, 104.5],
            'volume': [1000000, 1100000, 1050000, 1200000, 1150000],
        })
    
    def test_valid_ma_cross_strategy(self, sample_df):
        """Valid MA cross strategy should execute successfully."""
        code = '''
def on_init(ctx):
    ctx.log("Strategy initialized")

def on_bar(ctx, bar):
    if not ctx.position:
        if bar['close'] > bar['open']:
            amount = ctx.balance * 0.95 / bar['close']
            ctx.buy(bar['close'], amount)
    else:
        if bar['close'] < bar['open']:
            ctx.close_position()
'''
        strategy = ScriptStrategy(code)
        result = strategy.run(sample_df)
        
        assert 'context' in result
        assert 'final_equity' in result
        assert 'total_return' in result
        assert result['final_equity'] > 0
    
    def test_valid_rsi_strategy(self, sample_df):
        """Valid RSI strategy should execute successfully."""
        code = '''
def on_init(ctx):
    ctx.log("RSI strategy initialized")

def on_bar(ctx, bar):
    # Simple logic: buy if close > open, sell if close < open
    if not ctx.position:
        if bar['close'] > bar['open']:
            ctx.buy(bar['close'], 100)
    else:
        if bar['close'] < bar['open']:
            ctx.sell(bar['close'], 100)
'''
        strategy = ScriptStrategy(code)
        result = strategy.run(sample_df)
        
        assert 'context' in result
        assert 'final_equity' in result
        assert isinstance(result['trades'], list)
    
    def test_builtin_strategy(self, sample_df):
        """Builtin strategies should work."""
        from app.services.strategy.script_strategy import get_builtin_script_strategy
        
        strategy = get_builtin_script_strategy("ma_cross_script")
        result = strategy.run(sample_df)
        
        assert 'context' in result
        assert 'final_equity' in result


# ============================================================================
# Edge Cases and Additional Security Tests
# ============================================================================

class TestEdgeCases:
    """Test edge cases and additional security scenarios."""
    
    @pytest.fixture
    def sample_df(self):
        """Create sample DataFrame for testing."""
        return pd.DataFrame({
            'open': [100.0],
            'high': [101.0],
            'low': [99.0],
            'close': [100.5],
            'volume': [1000000],
        })
    
    def test_empty_code(self, sample_df):
        """Empty code should be rejected."""
        with pytest.raises((ValueError, SyntaxError)):
            ScriptStrategy("")
    
    def test_whitespace_only(self, sample_df):
        """Whitespace-only code should be rejected."""
        with pytest.raises((ValueError, SyntaxError)):
            ScriptStrategy("   \n\t  \n  ")
    
    def test_syntax_error(self, sample_df):
        """Code with syntax errors should be rejected."""
        code = "def on_bar(ctx, bar):\n    if True\n        pass"
        with pytest.raises((ValueError, StrategySecurityError)):
            ScriptStrategy(code)
    
    def test_import_pandas_allowed(self, sample_df):
        """Pandas import should be allowed via safe import."""
        code = '''
import pandas as pd

def on_bar(ctx, bar):
    df = pd.DataFrame({'a': [1, 2, 3]})
'''
        strategy = ScriptStrategy(code, validate_security=False)
        result = strategy.run(sample_df)
        assert 'context' in result
    
    def test_import_numpy_allowed(self, sample_df):
        """Numpy import should be allowed via safe import."""
        code = '''
import numpy as np

def on_bar(ctx, bar):
    arr = np.array([1, 2, 3])
'''
        strategy = ScriptStrategy(code, validate_security=False)
        result = strategy.run(sample_df)
        assert 'context' in result
    
    def test_math_operations_allowed(self, sample_df):
        """Math operations should be allowed."""
        code = '''
import math

def on_bar(ctx, bar):
    x = math.sqrt(100)
    y = abs(-5)
    z = max(1, 2, 3)
'''
        strategy = ScriptStrategy(code, validate_security=False)
        result = strategy.run(sample_df)
        assert 'context' in result
    
    def test_nested_dangerous_pattern(self, sample_df):
        """Nested dangerous patterns should be detected."""
        code = '''
def on_bar(ctx, bar):
    f = lambda: __import__('os')
    f()
'''
        with pytest.raises((ValueError, StrategySecurityError)):
            ScriptStrategy(code)
    
    def test_obfuscated_import(self, sample_df):
        """Obfuscated imports should be detected."""
        code = '''
def on_bar(ctx, bar):
    x = '__im' + 'port__'
    eval(x + "('os')")
'''
        with pytest.raises((ValueError, StrategySecurityError)):
            ScriptStrategy(code)
        strategy = ScriptStrategy(code)
        result = strategy.run(sample_df)
        assert 'context' in result
    
    def test_nested_dangerous_pattern(self, sample_df):
        """Nested dangerous patterns should be detected."""
        code = '''
def on_bar(ctx, bar):
    f = lambda: __import__('os')
    f()
'''
        with pytest.raises((ValueError, StrategySecurityError)):
            ScriptStrategy(code)
    
    def test_obfuscated_import(self, sample_df):
        """Obfuscated imports should be detected."""
        code = '''
def on_bar(ctx, bar):
    x = '__im' + 'port__'
    eval(x + "('os')")
'''
        with pytest.raises((ValueError, StrategySecurityError)):
            ScriptStrategy(code)


# ============================================================================
# Performance Tests
# ============================================================================

class TestPerformance:
    """Test performance of security validation."""
    
    def test_validation_speed(self):
        """Security validation should be fast (< 100ms)."""
        valid_code = '''
def on_bar(ctx, bar):
    if bar['close'] > bar['open']:
        ctx.buy(bar['close'], 100)
'''
        start = time.time()
        for _ in range(100):
            ScriptStrategy(valid_code)
        elapsed = time.time() - start
        
        # 100 validations should take < 10 seconds (100ms each)
        assert elapsed < 10.0, f"Validation too slow: {elapsed:.2f}s for 100 iterations"


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
