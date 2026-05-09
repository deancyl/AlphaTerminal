"""
Unit tests for Strategy Compiler

Tests:
- Annotation parsing
- Parameter extraction
- Security validation
- Indicator strategy compilation
- Script strategy compilation
- Debug cycles
- Error handling
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from app.services.strategy.compiler import (
    StrategyCompiler,
    StrategySpec,
    StrategyParameter,
    CompilationResult,
    compile_strategy,
    validate_strategy_code,
    EXAMPLE_STRATEGIES,
    FORBIDDEN_IMPORTS,
    FORBIDDEN_BUILTINS,
)


class TestStrategySpec:
    """Test StrategySpec dataclass."""
    
    def test_default_values(self):
        """Test default values are set correctly."""
        spec = StrategySpec(name="Test Strategy")
        
        assert spec.name == "Test Strategy"
        assert spec.description == ""
        assert spec.parameters == {}
        assert spec.stop_loss_pct == 2.0
        assert spec.take_profit_pct == 6.0
        assert spec.entry_pct == 1.0
        assert spec.trailing_stop_enabled is False
        assert spec.trade_direction == "both"
        assert spec.strategy_type == "indicator"
    
    def test_custom_values(self):
        """Test custom values are set correctly."""
        spec = StrategySpec(
            name="Custom Strategy",
            description="Test description",
            parameters={"period": {"type": "int", "default": 10}},
            stop_loss_pct=5.0,
            take_profit_pct=10.0,
            trade_direction="long",
        )
        
        assert spec.name == "Custom Strategy"
        assert spec.description == "Test description"
        assert spec.parameters["period"]["default"] == 10
        assert spec.stop_loss_pct == 5.0
        assert spec.trade_direction == "long"
    
    def test_to_dict(self):
        """Test serialization to dict."""
        spec = StrategySpec(name="Test", description="Desc")
        result = spec.to_dict()
        
        assert result["name"] == "Test"
        assert result["description"] == "Desc"
        assert "created_at" in result


class TestStrategyParameter:
    """Test StrategyParameter dataclass."""
    
    def test_parameter_creation(self):
        """Test parameter creation."""
        param = StrategyParameter(
            name="period",
            type="int",
            default=10,
            description="Lookback period",
            min_value=1,
            max_value=100,
        )
        
        assert param.name == "period"
        assert param.type == "int"
        assert param.default == 10
        assert param.min_value == 1
        assert param.max_value == 100
    
    def test_to_dict(self):
        """Test parameter serialization."""
        param = StrategyParameter(name="test", type="float", default=0.5)
        result = param.to_dict()
        
        assert result["name"] == "test"
        assert result["type"] == "float"
        assert result["default"] == 0.5


class TestStrategyCompiler:
    """Test StrategyCompiler class."""
    
    @pytest.fixture
    def compiler(self):
        """Create compiler instance."""
        return StrategyCompiler(debug_level=10)
    
    @pytest.fixture
    def sample_indicator_code(self):
        """Sample indicator strategy code."""
        return '''
# @name Test MA Strategy
# @description Simple moving average crossover
# @param fast_period int 5 Fast period
# @param slow_period int 20 Slow period
# @strategy stopLossPct 3
# @strategy takeProfitPct 8

ma_fast = df['close'].rolling(fast_period).mean()
ma_slow = df['close'].rolling(slow_period).mean()
buy = ma_fast > ma_slow
sell = ma_fast < ma_slow
output = {
    'indicators': {'ma_fast': ma_fast, 'ma_slow': ma_slow},
    'signals': {'buy': buy, 'sell': sell}
}
'''
    
    @pytest.fixture
    def sample_script_code(self):
        """Sample script strategy code."""
        return '''
# @name Test Script Strategy
# @type script
# @strategy stopLossPct 2

def on_init(ctx):
    ctx.log("Initialized")

def on_bar(ctx, bar):
    if not ctx.position:
        if bar['close'] > bar['open']:
            ctx.buy(bar['close'], 100)
'''
    
    @pytest.fixture
    def sample_df(self):
        """Create sample DataFrame for testing."""
        return pd.DataFrame({
            'open': [100.0, 101.0, 102.0, 101.5, 103.0],
            'high': [101.0, 102.0, 103.0, 103.5, 104.0],
            'low': [99.0, 100.0, 101.0, 101.0, 102.0],
            'close': [100.5, 101.5, 102.5, 103.0, 103.5],
            'volume': [1000000, 1100000, 1050000, 1200000, 1150000],
        })
    
    def test_compiler_initialization(self, compiler):
        """Test compiler initializes correctly."""
        assert compiler.debug_level == 10
        assert compiler._debug_cycles == []
    
    def test_compile_indicator_strategy(self, compiler, sample_indicator_code):
        """Test compiling indicator strategy."""
        result = compiler.compile(sample_indicator_code)
        
        assert result.success is True
        assert result.spec is not None
        assert result.spec.name == "Test MA Strategy"
        assert result.execute_func is not None
        # Indicator strategies run cycles 1-7, 9-10 (skips cycle 8)
        assert len(result.debug_cycles) == 9
        assert result.compilation_time_ms > 0
    
    def test_compile_script_strategy(self, compiler, sample_script_code):
        """Test compiling script strategy."""
        result = compiler.compile(sample_script_code)
        
        assert result.success is True
        assert result.spec is not None
        assert result.spec.strategy_type == "script"
        assert result.execute_func is not None
    
    def test_auto_detect_indicator_type(self, compiler, sample_indicator_code):
        """Test auto-detection of indicator strategy."""
        result = compiler.compile(sample_indicator_code, strategy_type="auto")
        
        assert result.spec.strategy_type == "indicator"
    
    def test_auto_detect_script_type(self, compiler, sample_script_code):
        """Test auto-detection of script strategy."""
        result = compiler.compile(sample_script_code, strategy_type="auto")
        
        assert result.spec.strategy_type == "script"
    
    def test_parse_annotations(self, compiler, sample_indicator_code):
        """Test annotation parsing."""
        spec = compiler._parse_annotations(sample_indicator_code, "indicator")
        
        assert spec.name == "Test MA Strategy"
        assert spec.description == "Simple moving average crossover"
        assert "fast_period" in spec.parameters
        assert "slow_period" in spec.parameters
        assert spec.stop_loss_pct == 3.0
        assert spec.take_profit_pct == 8.0
    
    def test_parameter_extraction(self, compiler, sample_indicator_code):
        """Test parameter extraction."""
        spec = compiler._parse_annotations(sample_indicator_code, "indicator")
        
        assert spec.parameters["fast_period"]["type"] == "int"
        assert spec.parameters["fast_period"]["default"] == "5"
        assert spec.parameters["slow_period"]["type"] == "int"
        assert spec.parameters["slow_period"]["default"] == "20"
    
    def test_execute_indicator_strategy(self, compiler, sample_indicator_code, sample_df):
        """Test executing compiled indicator strategy."""
        result = compiler.compile(sample_indicator_code)
        
        assert result.success is True
        
        # Execute with sample data
        params = {"fast_period": 5, "slow_period": 20}
        output = result.execute_func(sample_df, params)
        
        assert "indicators" in output
        assert "signals" in output
        assert "ma_fast" in output["indicators"]
        assert "ma_slow" in output["indicators"]
        assert "buy" in output["signals"]
        assert "sell" in output["signals"]
    
    def test_execute_script_strategy(self, compiler, sample_script_code, sample_df):
        """Test executing compiled script strategy."""
        result = compiler.compile(sample_script_code)
        
        assert result.success is True
        
        # Execute with sample data
        output = result.execute_func(sample_df)
        
        assert "context" in output
        assert "final_equity" in output
        assert "trades" in output
    
    def test_debug_cycle_1_input_validation(self, compiler):
        """Test debug cycle 1: input validation."""
        # Valid code with annotations
        cycle_data = compiler._debug_cycle_1_input_validation("# @name Test\noutput = {}")
        assert cycle_data["passed"] is True
        
        # Empty code
        with pytest.raises(ValueError):
            compiler._debug_cycle_1_input_validation("")
        
        # Too short code - needs at least 20 chars
        with pytest.raises(ValueError):
            compiler._debug_cycle_1_input_validation("short")
    
    def test_debug_cycle_2_annotation_parsing(self, compiler, sample_indicator_code):
        """Test debug cycle 2: annotation parsing."""
        spec = compiler._debug_cycle_2_annotation_parsing(
            sample_indicator_code, "indicator"
        )
        
        assert spec.name == "Test MA Strategy"
        assert len(compiler._debug_cycles) == 1
    
    def test_debug_cycle_5_syntax_validation(self, compiler):
        """Test debug cycle 5: syntax validation."""
        # Valid syntax with output
        is_valid, errors = compiler._debug_cycle_5_code_validation("x = 1\noutput = {}")
        assert is_valid is True
        
        # Invalid syntax
        is_valid, errors = compiler._debug_cycle_5_code_validation("x = ")
        assert is_valid is False
        assert len(errors) > 0
    
    def test_debug_cycle_6_security_checks(self, compiler):
        """Test debug cycle 6: security checks."""
        # Safe code
        is_secure, errors = compiler._debug_cycle_6_security_checks("x = 1")
        assert is_secure is True
        
        # Dangerous code - forbidden import
        is_secure, errors = compiler._debug_cycle_6_security_checks("import os")
        assert is_secure is False
        assert any("os" in e for e in errors)
        
        # Dangerous code - eval
        is_secure, errors = compiler._debug_cycle_6_security_checks("eval('1+1')")
        assert is_secure is False
        assert any("eval" in e for e in errors)
    
    def test_security_validation_forbidden_imports(self, compiler):
        """Test security validation catches forbidden imports."""
        for mod in ["os", "sys", "subprocess", "socket"]:
            code = f"import {mod}"
            is_secure, errors = compiler._validate_security(code)
            assert is_secure is False
            assert any(mod in e for e in errors)
    
    def test_security_validation_forbidden_builtins(self, compiler):
        """Test security validation catches forbidden builtins."""
        for builtin in ["eval", "exec", "open", "__import__"]:
            code = f"{builtin}('test')"
            is_secure, errors = compiler._validate_security(code)
            assert is_secure is False
            assert any(builtin in e for e in errors)
    
    def test_security_validation_file_operations(self, compiler):
        """Test security validation catches file operations."""
        dangerous_patterns = [
            "open('file.txt', 'r')",
        ]
        
        for pattern in dangerous_patterns:
            is_secure, errors = compiler._validate_security(pattern)
            assert is_secure is False
    
    def test_security_validation_network_calls(self, compiler):
        """Test security validation catches network calls."""
        dangerous_patterns = [
            "import requests",
            "socket.connect()",
            "urllib.request.urlopen()",
        ]
        
        for pattern in dangerous_patterns:
            is_secure, errors = compiler._validate_security(pattern)
            assert is_secure is False
    
    def test_empty_code_compilation(self, compiler):
        """Test compilation with empty code."""
        result = compiler.compile("")
        
        assert result.success is False
        assert len(result.errors) > 0
    
    def test_syntax_error_compilation(self, compiler):
        """Test compilation with syntax error."""
        code = '''
# @name Bad Syntax
x = 
'''
        result = compiler.compile(code)
        
        assert result.success is False
        assert any("Syntax error" in e for e in result.errors)
    
    def test_security_violation_compilation(self, compiler):
        """Test compilation with security violation."""
        code = '''
# @name Dangerous Strategy
import os
output = {'signals': {'buy': True}}
'''
        result = compiler.compile(code)
        
        assert result.success is False
        assert any("os" in e for e in result.errors)
    
    def test_debug_level_control(self):
        """Test debug level controls cycle execution."""
        # Low debug level
        compiler_low = StrategyCompiler(debug_level=3)
        result = compiler_low.compile(EXAMPLE_STRATEGIES['ma_cross_indicator'])
        
        assert result.success is True
        assert len(result.debug_cycles) <= 3
        
        # High debug level - indicator strategies skip cycle 8
        compiler_high = StrategyCompiler(debug_level=10)
        result = compiler_high.compile(EXAMPLE_STRATEGIES['ma_cross_indicator'])
        
        assert result.success is True
        # Indicator strategies: cycles 1-7, 9-10 = 9 cycles
        assert len(result.debug_cycles) == 9
    
    def test_compilation_result_structure(self, compiler, sample_indicator_code):
        """Test compilation result has correct structure."""
        result = compiler.compile(sample_indicator_code)
        
        assert hasattr(result, 'success')
        assert hasattr(result, 'spec')
        assert hasattr(result, 'execute_func')
        assert hasattr(result, 'errors')
        assert hasattr(result, 'warnings')
        assert hasattr(result, 'debug_cycles')
        assert hasattr(result, 'compilation_time_ms')
    
    def test_debug_cycle_structure(self, compiler, sample_indicator_code):
        """Test debug cycle data structure."""
        result = compiler.compile(sample_indicator_code)
        
        for cycle in result.debug_cycles:
            assert 'cycle' in cycle
            assert 'name' in cycle
            # Cycle 10 (summary) doesn't have 'passed' key
            if cycle.get('cycle') != 10:
                assert 'passed' in cycle


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_compile_strategy_function(self):
        """Test compile_strategy convenience function."""
        result = compile_strategy(
            EXAMPLE_STRATEGIES['ma_cross_indicator'],
            debug_level=5
        )
        
        assert result.success is True
        assert result.spec is not None
    
    def test_validate_strategy_code_function(self):
        """Test validate_strategy_code convenience function."""
        # Valid code
        is_valid, errors = validate_strategy_code(
            EXAMPLE_STRATEGIES['ma_cross_indicator']
        )
        assert is_valid is True
        assert len(errors) == 0
        
        # Invalid code
        is_valid, errors = validate_strategy_code("import os")
        assert is_valid is False
        assert len(errors) > 0


class TestExampleStrategies:
    """Test example strategies."""
    
    @pytest.fixture
    def sample_df(self):
        """Create sample DataFrame."""
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        np.random.seed(42)
        
        close = 100 + np.cumsum(np.random.randn(100) * 2)
        
        return pd.DataFrame({
            'open': close + np.random.randn(100) * 0.5,
            'high': close + np.abs(np.random.randn(100) * 1),
            'low': close - np.abs(np.random.randn(100) * 1),
            'close': close,
            'volume': np.random.randint(1000000, 2000000, 100),
        }, index=dates)
    
    def test_ma_cross_strategy(self, sample_df):
        """Test MA cross example strategy."""
        result = compile_strategy(EXAMPLE_STRATEGIES['ma_cross_indicator'])
        
        assert result.success is True
        assert result.spec.name == "均线金叉策略"
        
        output = result.execute_func(sample_df, {"fast_period": 5, "slow_period": 20})
        
        assert "indicators" in output
        assert "signals" in output
        assert "ma_fast" in output["indicators"]
        assert "ma_slow" in output["indicators"]
    
    def test_rsi_strategy(self, sample_df):
        """Test RSI example strategy."""
        result = compile_strategy(EXAMPLE_STRATEGIES['rsi_oscillator'])
        
        assert result.success is True
        assert result.spec.name == "RSI 超买超卖策略"
        
        output = result.execute_func(sample_df, {
            "rsi_period": 14,
            "rsi_buy": 30,
            "rsi_sell": 70
        })
        
        assert "indicators" in output
        assert "rsi" in output["indicators"]
    
    def test_script_example_strategy(self, sample_df):
        """Test script example strategy."""
        result = compile_strategy(EXAMPLE_STRATEGIES['script_example'])
        
        assert result.success is True
        assert result.spec.strategy_type == "script"
        
        output = result.execute_func(sample_df)
        
        assert "context" in output
        assert "final_equity" in output


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_missing_output_variable(self):
        """Test code without output variable."""
        code = '''
# @name No Output
x = 1
y = 2
'''
        result = compile_strategy(code)
        
        assert result.success is False
        assert any("output" in e.lower() for e in result.errors)
    
    def test_unicode_in_annotations(self):
        """Test unicode characters in annotations."""
        code = '''
# @name 测试策略 🚀
# @description 这是一个测试策略
# @param 周期 int 10 均线周期

output = {'signals': {'buy': True}}
'''
        result = compile_strategy(code)
        
        assert result.success is True
        assert result.spec.name == "测试策略 🚀"
    
    def test_multiline_description(self):
        """Test multiline description."""
        code = '''
# @name Test
# @description Line 1
# Line 2 of description
output = {'signals': {'buy': True}}
'''
        result = compile_strategy(code)
        
        assert result.success is True
    
    def test_parameter_type_conversion(self):
        """Test parameter type conversion."""
        code = '''
# @name Test
# @param period int 10 Period
# @param threshold float 0.5 Threshold
# @param enabled bool true Enable flag

output = {'signals': {'buy': True}}
'''
        result = compile_strategy(code)
        
        assert result.success is True
        assert result.spec.parameters["period"]["type"] == "int"
        assert result.spec.parameters["threshold"]["type"] == "float"
        assert result.spec.parameters["enabled"]["type"] == "bool"
    
    def test_strategy_config_validation(self):
        """Test strategy config validation."""
        code = '''
# @name Test
# @strategy stopLossPct 5
# @strategy takeProfitPct 10
# @strategy tradeDirection long

output = {'signals': {'buy': True}}
'''
        result = compile_strategy(code)
        
        assert result.success is True
        assert result.spec.stop_loss_pct == 5.0
        assert result.spec.take_profit_pct == 10.0
        assert result.spec.trade_direction == "long"
    
    def test_trailing_stop_config(self):
        """Test trailing stop configuration."""
        code = '''
# @name Test
# @strategy trailingEnabled true
# @strategy trailingStopPct 2
# @strategy trailingActivationPct 3

output = {'signals': {'buy': True}}
'''
        result = compile_strategy(code)
        
        assert result.success is True
        assert result.spec.trailing_stop_enabled is True
        assert result.spec.trailing_stop_pct == 2.0
        assert result.spec.trailing_activation_pct == 3.0
    
    def test_version_and_author(self):
        """Test version and author annotations."""
        code = '''
# @name Test
# @version 2.0
# @author Test Author

output = {'signals': {'buy': True}}
'''
        result = compile_strategy(code)
        
        assert result.success is True
        assert result.spec.version == "2.0"
        assert result.spec.author == "Test Author"


class TestPerformance:
    """Test performance characteristics."""
    
    def test_compilation_time(self):
        """Test compilation completes in reasonable time."""
        import time
        
        start = time.time()
        result = compile_strategy(EXAMPLE_STRATEGIES['ma_cross_indicator'])
        elapsed = time.time() - start
        
        assert result.success is True
        assert elapsed < 1.0  # Should complete in under 1 second
        assert result.compilation_time_ms < 1000
    
    def test_multiple_compilations(self):
        """Test multiple compilations don't leak resources."""
        compiler = StrategyCompiler(debug_level=5)
        
        for _ in range(10):
            result = compiler.compile(EXAMPLE_STRATEGIES['ma_cross_indicator'])
            assert result.success is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
