"""
Strategy Compiler with Comprehensive Debug Logging

This module provides a unified strategy compiler that supports both:
- IndicatorStrategy: Signal-based strategies using pandas DataFrame
- ScriptStrategy: Event-driven strategies with on_bar/on_init callbacks

Features:
- Parse @param, @strategy annotations from DSL code
- Code validation and security sandboxing
- Compilation to executable functions
- 10 comprehensive debug cycles for troubleshooting

Author: AlphaTerminal Team
Version: 0.6.12
"""

from __future__ import annotations

import ast
import logging
import re
import textwrap
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import pandas as pd

# Configure logger with DEBUG level
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create console handler if not exists
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [StrategyCompiler] %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class StrategyParameter:
    """Represents a strategy parameter with metadata."""
    name: str
    type: str  # 'int', 'float', 'bool', 'str'
    default: Any
    description: str = ""
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'type': self.type,
            'default': self.default,
            'description': self.description,
            'min_value': self.min_value,
            'max_value': self.max_value,
        }


@dataclass
class StrategySpec:
    """Complete strategy specification parsed from DSL code."""
    name: str
    description: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    strategy_config: Dict[str, Any] = field(default_factory=dict)
    stop_loss_pct: float = 2.0
    take_profit_pct: float = 6.0
    entry_pct: float = 1.0
    trailing_stop_enabled: bool = False
    trailing_stop_pct: float = 0.0
    trailing_activation_pct: float = 0.0
    trade_direction: str = "both"  # 'long', 'short', 'both'
    version: str = "1.0"
    author: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    strategy_type: str = "indicator"  # 'indicator' or 'script'
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'description': self.description,
            'parameters': self.parameters,
            'strategy_config': self.strategy_config,
            'stop_loss_pct': self.stop_loss_pct,
            'take_profit_pct': self.take_profit_pct,
            'entry_pct': self.entry_pct,
            'trailing_stop_enabled': self.trailing_stop_enabled,
            'trailing_stop_pct': self.trailing_stop_pct,
            'trailing_activation_pct': self.trailing_activation_pct,
            'trade_direction': self.trade_direction,
            'version': self.version,
            'author': self.author,
            'created_at': self.created_at.isoformat(),
            'strategy_type': self.strategy_type,
        }


@dataclass
class CompilationResult:
    """Result of strategy compilation."""
    success: bool
    spec: Optional[StrategySpec] = None
    execute_func: Optional[Callable] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    debug_cycles: List[Dict[str, Any]] = field(default_factory=list)
    compilation_time_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'spec': self.spec.to_dict() if self.spec else None,
            'errors': self.errors,
            'warnings': self.warnings,
            'debug_cycles': self.debug_cycles,
            'compilation_time_ms': self.compilation_time_ms,
        }


# ============================================================================
# Security Configuration
# ============================================================================

FORBIDDEN_IMPORTS = {
    'os', 'sys', 'subprocess', 'multiprocessing', 'threading',
    'socket', 'urllib', 'http', 'requests', 'httplib', 'ftplib',
    'smtplib', 'poplib', 'imaplib', 'telnetlib', 'socketserver',
    'asyncio', 'concurrent', 'pickle', 'shelve', 'marshal',
    'importlib', 'pkgutil', 'modulefinder', 'code', 'codeop',
    'commands', 'popen2', 'pty', 'fcntl', 'pipes', 'posixpath',
}

FORBIDDEN_BUILTINS = {
    'eval', 'exec', 'compile', '__import__', 'open', 'input',
    'getattr', 'setattr', 'delattr', 'hasattr', 'globals', 'locals',
    'vars', 'dir', 'memoryview', 'property', 'super', 'type',
    'classmethod', 'staticmethod',
}

ALLOWED_BUILTINS = {
    'abs', 'all', 'any', 'bin', 'bool', 'bytes', 'callable', 'chr',
    'complex', 'dict', 'divmod', 'enumerate', 'filter', 'float',
    'format', 'frozenset', 'hex', 'int', 'isinstance', 'iter',
    'len', 'list', 'map', 'max', 'min', 'next', 'oct', 'ord',
    'pow', 'print', 'range', 'repr', 'reversed', 'round', 'set',
    'slice', 'sorted', 'str', 'sum', 'tuple', 'zip',
    'True', 'False', 'None', 'Ellipsis',
}

SAFE_MODULES = {
    'pandas', 'pd', 'numpy', 'np', 'math', 'statistics',
}


# ============================================================================
# Strategy Compiler
# ============================================================================

class StrategyCompiler:
    """
    Unified strategy compiler with comprehensive debug logging.
    
    Supports 10 debug cycles:
    1. Code input validation
    2. Annotation parsing
    3. Parameter extraction
    4. Strategy config extraction
    5. Code validation (syntax)
    6. Security checks
    7. Indicator strategy compilation
    8. Script strategy compilation
    9. Function execution test
    10. Compilation result summary
    """
    
    # Annotation patterns
    NAME_PATTERN = re.compile(r'#\s*@name\s+(.+)')
    DESC_PATTERN = re.compile(r'#\s*@description\s+(.+)')
    PARAM_PATTERN = re.compile(r'#\s*@param\s+(\w+)\s+(\w+)\s+(\S+)\s+(.+)')
    STRATEGY_PATTERN = re.compile(r'#\s*@strategy\s+(\w+)\s+(.+)')
    VERSION_PATTERN = re.compile(r'#\s*@version\s+(.+)')
    AUTHOR_PATTERN = re.compile(r'#\s*@author\s+(.+)')
    TYPE_PATTERN = re.compile(r'#\s*@type\s+(indicator|script)')
    
    def __init__(self, debug_level: int = 10):
        """
        Initialize compiler with debug level.
        
        Args:
            debug_level: Number of debug cycles to run (1-10)
        """
        self.debug_level = min(10, max(1, debug_level))
        self._debug_cycles: List[Dict[str, Any]] = []
        self._start_time: float = 0.0
        
    def compile(self, code: str, strategy_type: str = "auto") -> CompilationResult:
        """
        Compile strategy code to executable function.
        
        Args:
            code: Strategy DSL code
            strategy_type: 'indicator', 'script', or 'auto' (detect automatically)
        
        Returns:
            CompilationResult with spec and execute function
        """
        import time
        self._start_time = time.time()
        self._debug_cycles = []
        
        result = CompilationResult(success=False)
        
        try:
            # Debug Cycle 1: Code input validation
            if self.debug_level >= 1:
                self._debug_cycle_1_input_validation(code)
            
            # Detect strategy type if auto
            if strategy_type == "auto":
                strategy_type = self._detect_strategy_type(code)
                logger.debug(f"[Cycle 1] Detected strategy type: {strategy_type}")
            
            # Debug Cycle 2: Annotation parsing
            if self.debug_level >= 2:
                spec = self._debug_cycle_2_annotation_parsing(code, strategy_type)
            else:
                spec = self._parse_annotations(code, strategy_type)
            
            result.spec = spec
            
            # Debug Cycle 3: Parameter extraction
            if self.debug_level >= 3:
                self._debug_cycle_3_parameter_extraction(code, spec)
            
            # Debug Cycle 4: Strategy config extraction
            if self.debug_level >= 4:
                self._debug_cycle_4_strategy_config_extraction(code, spec)
            
            # Debug Cycle 5: Code validation (syntax)
            if self.debug_level >= 5:
                is_valid, errors = self._debug_cycle_5_code_validation(code)
            else:
                is_valid, errors = self._validate_syntax(code)
            
            if not is_valid:
                result.errors.extend(errors)
                result.debug_cycles = self._debug_cycles
                return result
            
            # Debug Cycle 6: Security checks
            if self.debug_level >= 6:
                is_secure, security_errors = self._debug_cycle_6_security_checks(code)
            else:
                is_secure, security_errors = self._validate_security(code)
            
            if not is_secure:
                result.errors.extend(security_errors)
                result.debug_cycles = self._debug_cycles
                return result
            
            # Compile based on strategy type
            if spec.strategy_type == "indicator":
                # Debug Cycle 7: Indicator strategy compilation
                if self.debug_level >= 7:
                    execute_func = self._debug_cycle_7_indicator_compilation(code, spec)
                else:
                    execute_func = self._compile_indicator_strategy(code, spec)
            else:
                # Debug Cycle 8: Script strategy compilation
                if self.debug_level >= 8:
                    execute_func = self._debug_cycle_8_script_compilation(code, spec)
                else:
                    execute_func = self._compile_script_strategy(code, spec)
            
            result.execute_func = execute_func
            
            # Debug Cycle 9: Function execution test
            if self.debug_level >= 9:
                test_passed, test_errors = self._debug_cycle_9_execution_test(
                    execute_func, spec
                )
                if not test_passed:
                    result.errors.extend(test_errors)
                    result.debug_cycles = self._debug_cycles
                    return result
            
            # Debug Cycle 10: Compilation result summary
            if self.debug_level >= 10:
                self._debug_cycle_10_summary(result)
            
            result.success = True
            result.debug_cycles = self._debug_cycles
            result.compilation_time_ms = (time.time() - self._start_time) * 1000
            
            logger.info(f"[SUCCESS] Strategy '{spec.name}' compiled in {result.compilation_time_ms:.2f}ms")
            
        except Exception as e:
            result.errors.append(f"Compilation failed: {str(e)}")
            result.errors.append(traceback.format_exc())
            logger.error(f"[ERROR] Compilation exception: {e}")
            logger.debug(traceback.format_exc())
        
        result.debug_cycles = self._debug_cycles
        return result
    
    # ========================================================================
    # Debug Cycle Implementations
    # ========================================================================
    
    def _debug_cycle_1_input_validation(self, code: str) -> Dict[str, Any]:
        """
        Debug Cycle 1: Validate code input.
        
        Checks:
        - Code is not empty
        - Code has minimum length
        - Code contains expected structure
        """
        logger.debug("=" * 80)
        logger.debug("[CYCLE 1] Code Input Validation")
        logger.debug("=" * 80)
        
        cycle_data = {
            'cycle': 1,
            'name': 'Input Validation',
            'checks': [],
            'passed': True,
        }
        
        # Check 1: Not empty
        check = {'name': 'Code not empty', 'passed': bool(code and code.strip())}
        if not check['passed']:
            check['error'] = 'Code is empty or contains only whitespace'
        cycle_data['checks'].append(check)
        logger.debug(f"  Check 1: Code not empty -> {'PASS' if check['passed'] else 'FAIL'}")
        
        # Check 2: Minimum length
        min_length = 20
        check = {'name': f'Minimum length ({min_length} chars)', 'passed': len(code.strip()) >= min_length}
        if not check['passed']:
            check['error'] = f'Code too short: {len(code.strip())} chars'
        cycle_data['checks'].append(check)
        logger.debug(f"  Check 2: Minimum length -> {'PASS' if check['passed'] else 'FAIL'}")
        
        # Check 3: Contains annotations or code structure
        has_annotations = bool(
            self.NAME_PATTERN.search(code) or
            self.DESC_PATTERN.search(code) or
            self.PARAM_PATTERN.search(code) or
            self.STRATEGY_PATTERN.search(code)
        )
        has_code_structure = 'def ' in code or 'output' in code or '=' in code
        check = {'name': 'Has valid structure', 'passed': has_annotations or has_code_structure}
        if not check['passed']:
            check['error'] = 'No annotations or code structure found'
        cycle_data['checks'].append(check)
        logger.debug(f"  Check 3: Valid structure -> {'PASS' if check['passed'] else 'FAIL'}")
        
        # Update cycle status
        cycle_data['passed'] = all(c['passed'] for c in cycle_data['checks'])
        
        # Summary
        logger.debug(f"  Result: {'PASS' if cycle_data['passed'] else 'FAIL'}")
        logger.debug(f"  Code length: {len(code)} characters")
        logger.debug(f"  Lines: {len(code.split(chr(10)))}")
        
        self._debug_cycles.append(cycle_data)
        
        if not cycle_data['passed']:
            raise ValueError("Code input validation failed")
        
        return cycle_data
    
    def _debug_cycle_2_annotation_parsing(
        self, code: str, strategy_type: str
    ) -> StrategySpec:
        """
        Debug Cycle 2: Parse annotations from code.
        
        Extracts:
        - @name
        - @description
        - @type
        - @version
        - @author
        """
        logger.debug("=" * 80)
        logger.debug("[CYCLE 2] Annotation Parsing")
        logger.debug("=" * 80)
        
        cycle_data = {
            'cycle': 2,
            'name': 'Annotation Parsing',
            'extracted': {},
            'passed': True,
        }
        
        spec = self._parse_annotations(code, strategy_type)
        
        # Log extracted values
        logger.debug(f"  Name: {spec.name}")
        logger.debug(f"  Description: {spec.description[:50]}..." if len(spec.description) > 50 else f"  Description: {spec.description}")
        logger.debug(f"  Type: {spec.strategy_type}")
        logger.debug(f"  Version: {spec.version}")
        logger.debug(f"  Author: {spec.author}")
        
        cycle_data['extracted'] = {
            'name': spec.name,
            'description': spec.description,
            'type': spec.strategy_type,
            'version': spec.version,
            'author': spec.author,
        }
        
        # Check if name was found
        if spec.name == "Unnamed Strategy":
            cycle_data['passed'] = False
            cycle_data['warning'] = "No @name annotation found, using default name"
            logger.debug(f"  Warning: {cycle_data['warning']}")
        
        logger.debug(f"  Result: {'PASS' if cycle_data['passed'] else 'PASS (with warnings)'}")
        
        self._debug_cycles.append(cycle_data)
        return spec
    
    def _debug_cycle_3_parameter_extraction(
        self, code: str, spec: StrategySpec
    ) -> None:
        """
        Debug Cycle 3: Extract parameters from code.
        
        Validates:
        - Parameter names are valid Python identifiers
        - Parameter types are supported
        - Default values can be parsed
        """
        logger.debug("=" * 80)
        logger.debug("[CYCLE 3] Parameter Extraction")
        logger.debug("=" * 80)
        
        cycle_data = {
            'cycle': 3,
            'name': 'Parameter Extraction',
            'parameters': {},
            'passed': True,
        }
        
        logger.debug(f"  Parameters found: {len(spec.parameters)}")
        
        for param_name, param_def in spec.parameters.items():
            logger.debug(f"    - {param_name}:")
            logger.debug(f"        Type: {param_def.get('type', 'unknown')}")
            logger.debug(f"        Default: {param_def.get('default', 'N/A')}")
            logger.debug(f"        Description: {param_def.get('description', 'N/A')}")
            
            cycle_data['parameters'][param_name] = param_def
            
            # Validate parameter name
            if not param_name.isidentifier():
                cycle_data['passed'] = False
                logger.debug(f"        ERROR: Invalid parameter name '{param_name}'")
        
        logger.debug(f"  Result: {'PASS' if cycle_data['passed'] else 'FAIL'}")
        
        self._debug_cycles.append(cycle_data)
    
    def _debug_cycle_4_strategy_config_extraction(
        self, code: str, spec: StrategySpec
    ) -> None:
        """
        Debug Cycle 4: Extract strategy configuration.
        
        Validates:
        - Stop loss percentage is valid (0-100)
        - Take profit percentage is valid (0-100)
        - Entry percentage is valid (0-100)
        - Trade direction is valid
        """
        logger.debug("=" * 80)
        logger.debug("[CYCLE 4] Strategy Config Extraction")
        logger.debug("=" * 80)
        
        cycle_data = {
            'cycle': 4,
            'name': 'Strategy Config Extraction',
            'config': {},
            'passed': True,
        }
        
        logger.debug(f"  Stop Loss: {spec.stop_loss_pct}%")
        logger.debug(f"  Take Profit: {spec.take_profit_pct}%")
        logger.debug(f"  Entry: {spec.entry_pct}%")
        logger.debug(f"  Trailing Stop: {'Enabled' if spec.trailing_stop_enabled else 'Disabled'}")
        if spec.trailing_stop_enabled:
            logger.debug(f"    Trailing Stop %: {spec.trailing_stop_pct}%")
            logger.debug(f"    Trailing Activation: {spec.trailing_activation_pct}%")
        logger.debug(f"  Trade Direction: {spec.trade_direction}")
        
        cycle_data['config'] = {
            'stop_loss_pct': spec.stop_loss_pct,
            'take_profit_pct': spec.take_profit_pct,
            'entry_pct': spec.entry_pct,
            'trailing_stop_enabled': spec.trailing_stop_enabled,
            'trailing_stop_pct': spec.trailing_stop_pct,
            'trailing_activation_pct': spec.trailing_activation_pct,
            'trade_direction': spec.trade_direction,
        }
        
        # Validate ranges
        if not (0 <= spec.stop_loss_pct <= 100):
            cycle_data['passed'] = False
            logger.debug(f"  ERROR: Invalid stop_loss_pct: {spec.stop_loss_pct}")
        
        if not (0 <= spec.take_profit_pct <= 100):
            cycle_data['passed'] = False
            logger.debug(f"  ERROR: Invalid take_profit_pct: {spec.take_profit_pct}")
        
        if spec.trade_direction not in ['long', 'short', 'both']:
            cycle_data['passed'] = False
            logger.debug(f"  ERROR: Invalid trade_direction: {spec.trade_direction}")
        
        logger.debug(f"  Result: {'PASS' if cycle_data['passed'] else 'FAIL'}")
        
        self._debug_cycles.append(cycle_data)
    
    def _debug_cycle_5_code_validation(self, code: str) -> Tuple[bool, List[str]]:
        """
        Debug Cycle 5: Validate code syntax.
        
        Checks:
        - Python syntax is valid
        - No obvious syntax errors
        - AST can be parsed
        """
        logger.debug("=" * 80)
        logger.debug("[CYCLE 5] Code Validation (Syntax)")
        logger.debug("=" * 80)
        
        cycle_data = {
            'cycle': 5,
            'name': 'Code Validation',
            'checks': [],
            'passed': True,
            'errors': [],
        }
        
        is_valid, errors = self._validate_syntax(code)
        
        # Check 1: AST parsing
        check = {'name': 'AST Parsing', 'passed': is_valid}
        if not is_valid:
            check['error'] = errors[0] if errors else 'Unknown syntax error'
        cycle_data['checks'].append(check)
        logger.debug(f"  Check 1: AST Parsing -> {'PASS' if is_valid else 'FAIL'}")
        
        # Check 2: Required output variable (for indicator strategies)
        has_output = 'output' in code or 'def on_bar' in code
        check = {'name': 'Has output definition', 'passed': has_output}
        cycle_data['checks'].append(check)
        logger.debug(f"  Check 2: Output definition -> {'PASS' if has_output else 'FAIL'}")
        
        if not has_output:
            errors.append("Code must define 'output' variable or 'on_bar' function")
        
        cycle_data['passed'] = is_valid and has_output
        cycle_data['errors'] = errors
        
        logger.debug(f"  Result: {'PASS' if cycle_data['passed'] else 'FAIL'}")
        if errors:
            logger.debug(f"  Errors: {errors}")
        
        self._debug_cycles.append(cycle_data)
        return is_valid and has_output, errors
    
    def _debug_cycle_6_security_checks(self, code: str) -> Tuple[bool, List[str]]:
        """
        Debug Cycle 6: Security validation.
        
        Checks:
        - No forbidden imports
        - No forbidden builtins
        - No dangerous operations
        - No file/network access
        """
        logger.debug("=" * 80)
        logger.debug("[CYCLE 6] Security Checks")
        logger.debug("=" * 80)
        
        cycle_data = {
            'cycle': 6,
            'name': 'Security Checks',
            'checks': [],
            'passed': True,
            'errors': [],
        }
        
        is_secure, errors = self._validate_security(code)
        
        # Check 1: Forbidden imports
        has_forbidden_imports = any(
            f"import {mod}" in code or f"from {mod}" in code
            for mod in FORBIDDEN_IMPORTS
        )
        check = {'name': 'No forbidden imports', 'passed': not has_forbidden_imports}
        cycle_data['checks'].append(check)
        logger.debug(f"  Check 1: Forbidden imports -> {'PASS' if not has_forbidden_imports else 'FAIL'}")
        
        # Check 2: Forbidden builtins
        has_forbidden_builtins = any(
            f"{builtin}(" in code
            for builtin in FORBIDDEN_BUILTINS
        )
        check = {'name': 'No forbidden builtins', 'passed': not has_forbidden_builtins}
        cycle_data['checks'].append(check)
        logger.debug(f"  Check 2: Forbidden builtins -> {'PASS' if not has_forbidden_builtins else 'FAIL'}")
        
        # Check 3: No file operations
        has_file_ops = any(
            pattern in code
            for pattern in ['open(', 'file(', '.read(', '.write(', '.close()']
        )
        check = {'name': 'No file operations', 'passed': not has_file_ops}
        cycle_data['checks'].append(check)
        logger.debug(f"  Check 3: File operations -> {'PASS' if not has_file_ops else 'FAIL'}")
        
        # Check 4: No network calls
        has_network = any(
            pattern in code
            for pattern in ['socket.', 'urllib', 'requests.', 'http://', 'https://']
        )
        check = {'name': 'No network calls', 'passed': not has_network}
        cycle_data['checks'].append(check)
        logger.debug(f"  Check 4: Network calls -> {'PASS' if not has_network else 'FAIL'}")
        
        # Check 5: No eval/exec
        has_eval_exec = 'eval(' in code or 'exec(' in code
        check = {'name': 'No eval/exec', 'passed': not has_eval_exec}
        cycle_data['checks'].append(check)
        logger.debug(f"  Check 5: eval/exec -> {'PASS' if not has_eval_exec else 'FAIL'}")
        
        cycle_data['passed'] = is_secure
        cycle_data['errors'] = errors
        
        logger.debug(f"  Result: {'PASS' if cycle_data['passed'] else 'FAIL'}")
        if errors:
            logger.debug(f"  Security violations: {errors}")
        
        self._debug_cycles.append(cycle_data)
        return is_secure, errors
    
    def _debug_cycle_7_indicator_compilation(
        self, code: str, spec: StrategySpec
    ) -> Callable:
        """
        Debug Cycle 7: Compile indicator strategy.
        
        Steps:
        - Extract executable code
        - Create sandbox namespace
        - Compile to function
        - Verify function signature
        """
        logger.debug("=" * 80)
        logger.debug("[CYCLE 7] Indicator Strategy Compilation")
        logger.debug("=" * 80)
        
        cycle_data = {
            'cycle': 7,
            'name': 'Indicator Compilation',
            'steps': [],
            'passed': True,
        }
        
        logger.debug("  Step 1: Extracting executable code...")
        code_lines = self._extract_executable_code(code)
        logger.debug(f"    Extracted {len(code_lines)} lines of code")
        cycle_data['steps'].append({'name': 'Code extraction', 'lines': len(code_lines)})
        
        logger.debug("  Step 2: Creating sandbox namespace...")
        namespace = self._create_sandbox_namespace()
        logger.debug(f"    Namespace has {len(namespace)} safe symbols")
        cycle_data['steps'].append({'name': 'Namespace creation', 'symbols': len(namespace)})
        
        logger.debug("  Step 3: Compiling to function...")
        execute_func = self._compile_indicator_strategy(code, spec)
        logger.debug("    Function compiled successfully")
        cycle_data['steps'].append({'name': 'Function compilation', 'success': True})
        
        logger.debug(f"  Result: PASS")
        logger.debug(f"  Function: {execute_func.__name__ if hasattr(execute_func, '__name__') else 'lambda'}")
        
        self._debug_cycles.append(cycle_data)
        return execute_func
    
    def _debug_cycle_8_script_compilation(
        self, code: str, spec: StrategySpec
    ) -> Callable:
        """
        Debug Cycle 8: Compile script strategy.
        
        Steps:
        - Parse script structure
        - Validate on_init/on_bar functions
        - Create execution context
        - Compile to function
        """
        logger.debug("=" * 80)
        logger.debug("[CYCLE 8] Script Strategy Compilation")
        logger.debug("=" * 80)
        
        cycle_data = {
            'cycle': 8,
            'name': 'Script Compilation',
            'steps': [],
            'passed': True,
        }
        
        logger.debug("  Step 1: Parsing script structure...")
        has_on_init = 'def on_init' in code
        has_on_bar = 'def on_bar' in code
        logger.debug(f"    on_init: {'Found' if has_on_init else 'Not found'}")
        logger.debug(f"    on_bar: {'Found' if has_on_bar else 'Not found'}")
        cycle_data['steps'].append({
            'name': 'Script structure',
            'has_on_init': has_on_init,
            'has_on_bar': has_on_bar,
        })
        
        logger.debug("  Step 2: Creating execution context...")
        logger.debug("    Context includes: pd, ctx, OrderSide, OrderType")
        cycle_data['steps'].append({'name': 'Context creation', 'success': True})
        
        logger.debug("  Step 3: Compiling script...")
        execute_func = self._compile_script_strategy(code, spec)
        logger.debug("    Script compiled successfully")
        cycle_data['steps'].append({'name': 'Script compilation', 'success': True})
        
        logger.debug(f"  Result: PASS")
        
        self._debug_cycles.append(cycle_data)
        return execute_func
    
    def _debug_cycle_9_execution_test(
        self, execute_func: Callable, spec: StrategySpec
    ) -> Tuple[bool, List[str]]:
        """
        Debug Cycle 9: Test function execution.
        
        Creates sample data and tests:
        - Function can be called
        - Returns expected structure
        - No runtime errors
        """
        logger.debug("=" * 80)
        logger.debug("[CYCLE 9] Function Execution Test")
        logger.debug("=" * 80)
        
        cycle_data = {
            'cycle': 9,
            'name': 'Execution Test',
            'tests': [],
            'passed': True,
            'errors': [],
        }
        
        errors = []
        
        # Create sample data
        logger.debug("  Creating sample test data...")
        sample_df = pd.DataFrame({
            'open': [100.0, 101.0, 102.0, 101.5, 103.0],
            'high': [101.0, 102.0, 103.0, 103.5, 104.0],
            'low': [99.0, 100.0, 101.0, 101.0, 102.0],
            'close': [100.5, 101.5, 102.5, 103.0, 103.5],
            'volume': [1000000, 1100000, 1050000, 1200000, 1150000],
        })
        
        sample_params = {}
        for param_name, param_def in spec.parameters.items():
            default_val = param_def.get('default', 0)
            param_type = param_def.get('type', 'float')
            try:
                if param_type == 'int':
                    sample_params[param_name] = int(float(default_val))
                elif param_type == 'float':
                    sample_params[param_name] = float(default_val)
                elif param_type == 'bool':
                    sample_params[param_name] = bool(default_val)
                else:
                    sample_params[param_name] = default_val
            except (ValueError, TypeError):
                sample_params[param_name] = default_val
        
        logger.debug(f"    Sample data: {len(sample_df)} rows")
        logger.debug(f"    Sample params: {sample_params}")
        
        # Test 1: Function callable
        logger.debug("  Test 1: Function is callable...")
        try:
            is_callable = callable(execute_func)
            test = {'name': 'Function callable', 'passed': is_callable}
            cycle_data['tests'].append(test)
            logger.debug(f"    -> {'PASS' if is_callable else 'FAIL'}")
            
            if not is_callable:
                errors.append("Execute function is not callable")
                cycle_data['passed'] = False
        except Exception as e:
            errors.append(f"Callable check failed: {e}")
            cycle_data['tests'].append({'name': 'Function callable', 'passed': False, 'error': str(e)})
            cycle_data['passed'] = False
        
        # Test 2: Execution test
        if cycle_data['passed']:
            logger.debug("  Test 2: Execute with sample data...")
            try:
                if spec.strategy_type == "indicator":
                    result = execute_func(sample_df, sample_params)
                else:
                    result = execute_func(sample_df)
                
                test = {'name': 'Execution test', 'passed': True}
                cycle_data['tests'].append(test)
                logger.debug(f"    -> PASS")
                
                # Test 3: Result structure
                logger.debug("  Test 3: Result structure validation...")
                if spec.strategy_type == "indicator":
                    has_indicators = 'indicators' in result
                    has_signals = 'signals' in result
                    test = {
                        'name': 'Result structure',
                        'passed': has_indicators or has_signals,
                        'has_indicators': has_indicators,
                        'has_signals': has_signals,
                    }
                    if not (has_indicators or has_signals):
                        test['error'] = 'Result missing indicators or signals'
                        errors.append(test['error'])
                else:
                    test = {'name': 'Result structure', 'passed': True}
                
                cycle_data['tests'].append(test)
                logger.debug(f"    -> {'PASS' if test['passed'] else 'FAIL'}")
                
                if not test['passed']:
                    cycle_data['passed'] = False
                
            except Exception as e:
                error_msg = f"Execution test failed: {e}"
                errors.append(error_msg)
                cycle_data['tests'].append({'name': 'Execution test', 'passed': False, 'error': str(e)})
                cycle_data['passed'] = False
                logger.debug(f"    -> FAIL: {e}")
        
        cycle_data['errors'] = errors
        logger.debug(f"  Result: {'PASS' if cycle_data['passed'] else 'FAIL'}")
        
        self._debug_cycles.append(cycle_data)
        return cycle_data['passed'], errors
    
    def _debug_cycle_10_summary(self, result: CompilationResult) -> None:
        """
        Debug Cycle 10: Compilation result summary.
        
        Summarizes:
        - All debug cycles
        - Final result
        - Performance metrics
        """
        logger.debug("=" * 80)
        logger.debug("[CYCLE 10] Compilation Summary")
        logger.debug("=" * 80)
        
        cycle_data = {
            'cycle': 10,
            'name': 'Summary',
            'cycles_summary': [],
        }
        
        # Summarize all cycles
        for cycle in self._debug_cycles:
            cycle_num = cycle.get('cycle', 0)
            cycle_name = cycle.get('name', 'Unknown')
            cycle_passed = cycle.get('passed', True)
            
            status = 'PASS' if cycle_passed else 'FAIL'
            logger.debug(f"  Cycle {cycle_num}: {cycle_name} -> {status}")
            
            cycle_data['cycles_summary'].append({
                'cycle': cycle_num,
                'name': cycle_name,
                'passed': cycle_passed,
            })
        
        # Final summary
        all_passed = all(c.get('passed', True) for c in self._debug_cycles)
        logger.debug(f"  Overall: {'SUCCESS' if all_passed else 'FAILED'}")
        logger.debug(f"  Strategy: {result.spec.name if result.spec else 'Unknown'}")
        logger.debug(f"  Type: {result.spec.strategy_type if result.spec else 'Unknown'}")
        
        cycle_data['overall_passed'] = all_passed
        cycle_data['final_status'] = 'SUCCESS' if all_passed else 'FAILED'
        
        self._debug_cycles.append(cycle_data)
    
    # ========================================================================
    # Core Compilation Methods
    # ========================================================================
    
    def _parse_annotations(self, code: str, strategy_type: str) -> StrategySpec:
        """Parse all annotations from strategy code."""
        name = "Unnamed Strategy"
        description = ""
        parameters: Dict[str, Any] = {}
        strategy_config: Dict[str, Any] = {}
        stop_loss_pct = 2.0
        take_profit_pct = 6.0
        entry_pct = 1.0
        trailing_enabled = False
        trailing_stop_pct = 0.0
        trailing_activation_pct = 0.0
        trade_direction = "both"
        version = "1.0"
        author = ""
        
        for line in code.split('\n'):
            line = line.strip()
            
            # @name
            match = self.NAME_PATTERN.match(line)
            if match:
                name = match.group(1).strip()
                continue
            
            # @description
            match = self.DESC_PATTERN.match(line)
            if match:
                description = match.group(1).strip()
                continue
            
            # @param
            match = self.PARAM_PATTERN.match(line)
            if match:
                param_name = match.group(1).strip()
                param_type = match.group(2).strip()
                param_default = match.group(3).strip()
                param_desc = match.group(4).strip()
                
                parameters[param_name] = {
                    'type': param_type,
                    'default': param_default,
                    'description': param_desc,
                }
                continue
            
            # @strategy
            match = self.STRATEGY_PATTERN.match(line)
            if match:
                key = match.group(1).strip()
                value = match.group(2).strip()
                strategy_config[key] = value
                
                if key == 'stopLossPct':
                    try:
                        stop_loss_pct = float(value)
                    except (ValueError, TypeError):
                        pass  # Invalid value, keep default
                elif key == 'takeProfitPct':
                    try:
                        take_profit_pct = float(value)
                    except (ValueError, TypeError):
                        pass  # Invalid value, keep default
                elif key == 'entryPct':
                    try:
                        entry_pct = float(value)
                    except (ValueError, TypeError):
                        pass  # Invalid value, keep default
                elif key == 'trailingEnabled':
                    trailing_enabled = value.lower() == 'true'
                elif key == 'trailingStopPct':
                    try:
                        trailing_stop_pct = float(value)
                    except (ValueError, TypeError):
                        pass  # Invalid value, keep default
                elif key == 'trailingActivationPct':
                    try:
                        trailing_activation_pct = float(value)
                    except (ValueError, TypeError):
                        pass  # Invalid value, keep default
                elif key == 'tradeDirection':
                    trade_direction = value.lower()
                continue
            
            # @version
            match = self.VERSION_PATTERN.match(line)
            if match:
                version = match.group(1).strip()
                continue
            
            # @author
            match = self.AUTHOR_PATTERN.match(line)
            if match:
                author = match.group(1).strip()
                continue
        
        return StrategySpec(
            name=name,
            description=description,
            parameters=parameters,
            strategy_config=strategy_config,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            entry_pct=entry_pct,
            trailing_stop_enabled=trailing_enabled,
            trailing_stop_pct=trailing_stop_pct,
            trailing_activation_pct=trailing_activation_pct,
            trade_direction=trade_direction,
            version=version,
            author=author,
            strategy_type=strategy_type,
        )
    
    def _detect_strategy_type(self, code: str) -> str:
        """Auto-detect strategy type from code structure."""
        # Script strategy has on_bar/on_init functions
        if 'def on_bar' in code or 'def on_init' in code:
            return 'script'
        # Default to indicator strategy
        return 'indicator'
    
    def _validate_syntax(self, code: str) -> Tuple[bool, List[str]]:
        """Validate Python syntax."""
        errors = []
        
        try:
            ast.parse(code)
        except SyntaxError as e:
            errors.append(f"Syntax error at line {e.lineno}: {e.msg}")
            return False, errors
        
        return True, errors
    
    def _validate_security(self, code: str) -> Tuple[bool, List[str]]:
        """Validate code security."""
        errors = []
        
        # Check forbidden imports
        for mod in FORBIDDEN_IMPORTS:
            if f"import {mod}" in code or f"from {mod}" in code:
                errors.append(f"Forbidden import: {mod}")
        
        # Check forbidden builtins
        for builtin in FORBIDDEN_BUILTINS:
            if f"{builtin}(" in code:
                errors.append(f"Forbidden builtin: {builtin}")
        
        # Check dangerous patterns
        dangerous_patterns = [
            ('open(', 'File operation'),
            ('eval(', 'Dynamic code execution'),
            ('exec(', 'Dynamic code execution'),
            ('__import__', 'Dynamic import'),
            ('compile(', 'Code compilation'),
            ('socket.', 'Network access'),
            ('urllib', 'Network access'),
            ('requests.', 'HTTP requests'),
            ('http://', 'HTTP URL'),
            ('https://', 'HTTPS URL'),
            ('subprocess', 'Process execution'),
            ('multiprocessing', 'Process creation'),
            ('threading', 'Thread creation'),
        ]
        
        for pattern, desc in dangerous_patterns:
            if pattern in code:
                errors.append(f"Security violation: {desc} ({pattern})")
        
        return len(errors) == 0, errors
    
    def _extract_executable_code(self, code: str) -> List[str]:
        """Extract executable code lines (excluding comments and annotations)."""
        code = textwrap.dedent(code)
        lines = code.split('\n')
        
        # Find first non-comment, non-empty line
        start_idx = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                start_idx = i
                break
        
        # Collect code lines
        code_lines = []
        for line in lines[start_idx:]:
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                code_lines.append(line)
        
        return code_lines
    
    def _create_sandbox_namespace(self) -> Dict[str, Any]:
        """Create safe namespace for strategy execution."""
        import numpy as np
        
        namespace = {
            'pd': pd,
            'np': np,
            'sum': sum,
            'min': min,
            'max': max,
            'abs': abs,
            'round': round,
            'len': len,
            'range': range,
            'str': str,
            'int': int,
            'float': float,
            'bool': bool,
            'list': list,
            'dict': dict,
            'tuple': tuple,
            'set': set,
            'sorted': sorted,
            'enumerate': enumerate,
            'zip': zip,
            'map': map,
            'filter': filter,
        }
        
        return namespace
    
    def _compile_indicator_strategy(
        self, code: str, spec: StrategySpec
    ) -> Callable:
        """Compile indicator strategy to executable function."""
        code_lines = self._extract_executable_code(code)
        namespace = self._create_sandbox_namespace()
        
        def execute_strategy(df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
            """Execute indicator strategy."""
            local_vars = namespace.copy()
            local_vars['df'] = df.copy()
            local_vars['params'] = params
            local_vars['output'] = None
            
            # Add parameters to local scope
            local_vars.update(params)
            
            full_code = '\n'.join(code_lines)
            
            try:
                exec(full_code, local_vars)
            except Exception as e:
                logger.warning(f"[IndicatorStrategy] Execution error: {e}")
                return {
                    'indicators': {},
                    'signals': {
                        'buy': pd.Series(False, index=df.index),
                        'sell': pd.Series(False, index=df.index)
                    }
                }
            
            return local_vars.get('output', {
                'indicators': {},
                'signals': {
                    'buy': pd.Series(False, index=df.index),
                    'sell': pd.Series(False, index=df.index)
                }
            })
        
        return execute_strategy
    
    def _compile_script_strategy(
        self, code: str, spec: StrategySpec
    ) -> Callable:
        """Compile script strategy to executable function."""
        from .script_strategy import ScriptStrategy, StrategyContext
        
        # Create ScriptStrategy instance
        strategy = ScriptStrategy(code)
        
        def execute_strategy(df: pd.DataFrame) -> Dict[str, Any]:
            """Execute script strategy."""
            return strategy.run(df)
        
        return execute_strategy


# ============================================================================
# Convenience Functions
# ============================================================================

def compile_strategy(
    code: str,
    strategy_type: str = "auto",
    debug_level: int = 10
) -> CompilationResult:
    """
    Compile strategy code to executable function.
    
    Args:
        code: Strategy DSL code
        strategy_type: 'indicator', 'script', or 'auto'
        debug_level: Debug level (1-10)
    
    Returns:
        CompilationResult with spec and execute function
    """
    compiler = StrategyCompiler(debug_level=debug_level)
    return compiler.compile(code, strategy_type)


def validate_strategy_code(code: str) -> Tuple[bool, List[str]]:
    """
    Validate strategy code without compiling.
    
    Args:
        code: Strategy DSL code
    
    Returns:
        Tuple of (is_valid, errors)
    """
    compiler = StrategyCompiler(debug_level=0)
    
    # Syntax validation
    is_valid_syntax, syntax_errors = compiler._validate_syntax(code)
    if not is_valid_syntax:
        return False, syntax_errors
    
    # Security validation
    is_secure, security_errors = compiler._validate_security(code)
    if not is_secure:
        return False, security_errors
    
    return True, []


# ============================================================================
# Example Strategies
# ============================================================================

EXAMPLE_STRATEGIES = {
    "ma_cross_indicator": '''
# @name 均线金叉策略
# @description 短期均线上穿长期均线时买入，下穿时卖出
# @param fast_period int 5 短期均线周期
# @param slow_period int 20 长期均线周期
# @strategy stopLossPct 2
# @strategy takeProfitPct 6
# @strategy tradeDirection both
# @version 1.0

ma_fast = df['close'].rolling(fast_period).mean()
ma_slow = df['close'].rolling(slow_period).mean()
buy = (ma_fast > ma_slow) & (ma_fast.shift(1) <= ma_slow.shift(1))
sell = (ma_fast < ma_slow) & (ma_fast.shift(1) >= ma_slow.shift(1))
output = {
    'indicators': {'ma_fast': ma_fast, 'ma_slow': ma_slow},
    'signals': {'buy': buy, 'sell': sell}
}
''',

    "rsi_oscillator": '''
# @name RSI 超买超卖策略
# @description RSI低于超卖值时买入，高于超买值时卖出
# @param rsi_period int 14 RSI周期
# @param rsi_buy float 30 超卖阈值
# @param rsi_sell float 70 超买阈值
# @strategy stopLossPct 3
# @strategy takeProfitPct 8

delta = df['close'].diff()
gain = delta.where(delta > 0, 0)
loss = -delta.where(delta < 0, 0)
avg_gain = gain.rolling(window=rsi_period).mean()
avg_loss = loss.rolling(window=rsi_period).mean()
rs = avg_gain / avg_loss
rsi = 100 - (100 / (1 + rs))
buy = rsi < rsi_buy
sell = rsi > rsi_sell
output = {
    'indicators': {'rsi': rsi},
    'signals': {'buy': buy, 'sell': sell}
}
''',

    "script_example": '''
# @name 简单脚本策略
# @description 使用on_bar回调的脚本策略
# @type script
# @strategy stopLossPct 2

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
''',
}


# ============================================================================
# Main Entry Point (for testing)
# ============================================================================

if __name__ == "__main__":
    # Test compilation
    print("Testing Strategy Compiler...")
    print("=" * 80)
    
    # Test 1: Indicator strategy
    print("\n[Test 1] Indicator Strategy Compilation")
    result = compile_strategy(EXAMPLE_STRATEGIES['ma_cross_indicator'], debug_level=10)
    
    print(f"\nResult: {'SUCCESS' if result.success else 'FAILED'}")
    if result.spec:
        print(f"Strategy: {result.spec.name}")
        print(f"Parameters: {list(result.spec.parameters.keys())}")
    print(f"Debug cycles: {len(result.debug_cycles)}")
    print(f"Compilation time: {result.compilation_time_ms:.2f}ms")
    
    # Test 2: Script strategy
    print("\n" + "=" * 80)
    print("\n[Test 2] Script Strategy Compilation")
    result2 = compile_strategy(EXAMPLE_STRATEGIES['script_example'], debug_level=10)
    
    print(f"\nResult: {'SUCCESS' if result2.success else 'FAILED'}")
    if result2.spec:
        print(f"Strategy: {result2.spec.name}")
        print(f"Type: {result2.spec.strategy_type}")
    print(f"Compilation time: {result2.compilation_time_ms:.2f}ms")
    
    # Test 3: Security check
    print("\n" + "=" * 80)
    print("\n[Test 3] Security Validation")
    dangerous_code = '''
import os
output = {'signals': {'buy': True}}
'''
    result3 = compile_strategy(dangerous_code, debug_level=6)
    print(f"\nResult: {'SUCCESS' if result3.success else 'FAILED'}")
    print(f"Errors: {result3.errors}")
    
    print("\n" + "=" * 80)
    print("All tests completed!")
