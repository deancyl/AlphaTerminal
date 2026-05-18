"""
AST-based Security Validator for Strategy Code

This module provides comprehensive AST-level validation to prevent code injection
attacks in user-provided strategy code. It goes beyond simple string matching by
analyzing the Abstract Syntax Tree to detect:
- Dynamic imports and module access
- Dangerous function calls (eval, exec, compile, etc.)
- File system operations
- Network operations
- Reflection attacks (getattr, setattr, etc.)
- Class introspection attacks
- Memory bombs and resource exhaustion patterns

Author: AlphaTerminal Security Team
Version: 1.0
"""

import ast
import logging
from dataclasses import dataclass, field
from typing import List, Set, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class SecurityViolation:
    """Represents a security violation found in code."""
    node_type: str
    message: str
    line: int
    column: int
    severity: str = "error"  # error, warning
    
    def __str__(self):
        return f"[Line {self.line}:{self.column}] {self.node_type}: {self.message}"


@dataclass
class ValidationResult:
    """Result of AST security validation."""
    is_valid: bool
    violations: List[SecurityViolation] = field(default_factory=list)
    warnings: List[SecurityViolation] = field(default_factory=list)
    
    def add_violation(self, violation: SecurityViolation):
        """Add a security violation."""
        self.violations.append(violation)
        self.is_valid = False
    
    def add_warning(self, warning: SecurityViolation):
        """Add a security warning."""
        self.warnings.append(warning)
    
    def get_error_messages(self) -> List[str]:
        """Get all error messages."""
        return [str(v) for v in self.violations]


class ASTSecurityValidator(ast.NodeVisitor):
    """
    AST-based security validator for strategy code.
    
    Visits all AST nodes and checks for security violations:
    - Forbidden imports
    - Forbidden function calls
    - Dangerous attribute access
    - Resource exhaustion patterns
    """
    
    FORBIDDEN_MODULES = {
        'os', 'sys', 'subprocess', 'multiprocessing', 'threading',
        'socket', 'urllib', 'http', 'requests', 'httplib', 'ftplib',
        'smtplib', 'poplib', 'imaplib', 'telnetlib', 'socketserver',
        'asyncio', 'concurrent', 'pickle', 'shelve', 'marshal',
        'importlib', 'pkgutil', 'modulefinder', 'code', 'codeop',
        'commands', 'popen2', 'pty', 'fcntl', 'pipes', 'posixpath',
        'builtins', '__builtin__', '__builtins__',
    }
    
    FORBIDDEN_FUNCTIONS = {
        'eval', 'exec', 'compile', '__import__', 'open', 'input',
        'getattr', 'setattr', 'delattr', 'hasattr', 'globals', 'locals',
        'vars', 'dir', 'memoryview', 'property', 'super', 'type',
        'classmethod', 'staticmethod', 'breakpoint',
    }
    
    FORBIDDEN_ATTRIBUTES = {
        '__class__', '__base__', '__bases__', '__subclasses__', '__mro__',
        '__builtins__', '__builtin__', '__globals__', '__locals__',
        '__code__', '__dict__', '__doc__', '__module__',
        '__import__', '__name__', '__qualname__',
    }
    
    ALLOWED_MODULES = {
        'pandas', 'pd', 'numpy', 'np', 'math', 'statistics',
        'datetime', 'date', 'time', 'timedelta',
    }
    
    MAX_LIST_SIZE = 10**7  # Maximum allowed list size
    MAX_STRING_MULTIPLICATION = 10**6  # Maximum string multiplication
    
    def __init__(self):
        self.result = ValidationResult(is_valid=True)
        self._current_function = None
        self._imported_modules: Set[str] = set()
        self._defined_functions: Set[str] = set()
    
    def validate(self, code: str) -> ValidationResult:
        """
        Validate code by parsing AST and checking for violations.
        
        Args:
            code: Python code to validate
            
        Returns:
            ValidationResult with violations and warnings
        """
        self.result = ValidationResult(is_valid=True)
        self._imported_modules = set()
        self._defined_functions = set()
        
        try:
            tree = ast.parse(code)
            self.visit(tree)
        except SyntaxError as e:
            self.result.add_violation(SecurityViolation(
                node_type="SyntaxError",
                message=f"Syntax error: {e.msg}",
                line=e.lineno or 0,
                column=e.offset or 0,
            ))
        except Exception as e:
            self.result.add_violation(SecurityViolation(
                node_type="ParseError",
                message=f"Failed to parse code: {str(e)}",
                line=0,
                column=0,
            ))
        
        return self.result
    
    def visit_Import(self, node: ast.Import):
        """Check import statements."""
        for alias in node.names:
            module_name = alias.name.split('.')[0]
            self._imported_modules.add(module_name)
            
            if module_name in self.FORBIDDEN_MODULES:
                self.result.add_violation(SecurityViolation(
                    node_type="Import",
                    message=f"Forbidden import: {alias.name}",
                    line=node.lineno,
                    column=node.col_offset,
                ))
            elif module_name not in self.ALLOWED_MODULES:
                self.result.add_warning(SecurityViolation(
                    node_type="Import",
                    message=f"Potentially unsafe import: {alias.name}",
                    line=node.lineno,
                    column=node.col_offset,
                    severity="warning",
                ))
        
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Check from ... import statements."""
        if node.module:
            module_name = node.module.split('.')[0]
            self._imported_modules.add(module_name)
            
            if module_name in self.FORBIDDEN_MODULES:
                self.result.add_violation(SecurityViolation(
                    node_type="ImportFrom",
                    message=f"Forbidden import from: {node.module}",
                    line=node.lineno,
                    column=node.col_offset,
                ))
            elif module_name not in self.ALLOWED_MODULES:
                self.result.add_warning(SecurityViolation(
                    node_type="ImportFrom",
                    message=f"Potentially unsafe import from: {node.module}",
                    line=node.lineno,
                    column=node.col_offset,
                    severity="warning",
                ))
        
        self.generic_visit(node)
    
    def visit_Call(self, node: ast.Call):
        """Check function calls for forbidden functions."""
        func_name = self._get_func_name(node)
        
        if func_name in self.FORBIDDEN_FUNCTIONS:
            self.result.add_violation(SecurityViolation(
                node_type="Call",
                message=f"Forbidden function call: {func_name}",
                line=node.lineno,
                column=node.col_offset,
            ))
        
        # Check for __import__ calls
        if func_name == '__import__':
            self.result.add_violation(SecurityViolation(
                node_type="Call",
                message="Dynamic import via __import__ is forbidden",
                line=node.lineno,
                column=node.col_offset,
            ))
        
        # Check for method calls on forbidden attributes
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in self.FORBIDDEN_ATTRIBUTES:
                self.result.add_violation(SecurityViolation(
                    node_type="Call",
                    message=f"Forbidden attribute access: {node.func.attr}",
                    line=node.lineno,
                    column=node.col_offset,
                ))
        
        self.generic_visit(node)
    
    def visit_Attribute(self, node: ast.Attribute):
        """Check attribute access for forbidden attributes."""
        if node.attr in self.FORBIDDEN_ATTRIBUTES:
            self.result.add_violation(SecurityViolation(
                node_type="Attribute",
                message=f"Forbidden attribute access: {node.attr}",
                line=node.lineno,
                column=node.col_offset,
            ))
        
        # Check for dunder methods
        if node.attr.startswith('__') and node.attr.endswith('__'):
            if node.attr not in {'__init__', '__str__', '__repr__', '__len__'}:
                self.result.add_warning(SecurityViolation(
                    node_type="Attribute",
                    message=f"Accessing dunder method: {node.attr}",
                    line=node.lineno,
                    column=node.col_offset,
                    severity="warning",
                ))
        
        self.generic_visit(node)
    
    def visit_Name(self, node: ast.Name):
        """Check name references for forbidden builtins."""
        if node.id in self.FORBIDDEN_FUNCTIONS:
            self.result.add_violation(SecurityViolation(
                node_type="Name",
                message=f"Reference to forbidden builtin: {node.id}",
                line=node.lineno,
                column=node.col_offset,
            ))
        
        self.generic_visit(node)
    
    def visit_BinOp(self, node: ast.BinOp):
        """Check binary operations for resource exhaustion."""
        # Check for large list/string multiplication
        if isinstance(node.op, ast.Mult):
            left_size = self._estimate_size(node.left)
            right_size = self._estimate_size(node.right)
            
            if left_size > self.MAX_LIST_SIZE or right_size > self.MAX_LIST_SIZE:
                self.result.add_violation(SecurityViolation(
                    node_type="BinOp",
                    message=f"Potential memory bomb: large multiplication detected",
                    line=node.lineno,
                    column=node.col_offset,
                ))
        
        self.generic_visit(node)
    
    def visit_List(self, node: ast.List):
        """Check list creation for large lists."""
        # Check for list comprehension that might create large lists
        if len(node.elts) > 1000:
            self.result.add_warning(SecurityViolation(
                node_type="List",
                message=f"Large list literal with {len(node.elts)} elements",
                line=node.lineno,
                column=node.col_offset,
                severity="warning",
            ))
        
        self.generic_visit(node)
    
    def visit_ListComp(self, node: ast.ListComp):
        """Check list comprehensions for potential issues."""
        # Warn about nested comprehensions
        if any(isinstance(generator.iter, ast.ListComp) for generator in node.generators):
            self.result.add_warning(SecurityViolation(
                node_type="ListComp",
                message="Nested list comprehension may be slow",
                line=node.lineno,
                column=node.col_offset,
                severity="warning",
            ))
        
        self.generic_visit(node)
    
    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Track function definitions."""
        self._defined_functions.add(node.name)
        old_function = self._current_function
        self._current_function = node.name
        
        self.generic_visit(node)
        
        self._current_function = old_function
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Track async function definitions."""
        self._defined_functions.add(node.name)
        old_function = self._current_function
        self._current_function = node.name
        
        self.generic_visit(node)
        
        self._current_function = old_function
    
    def visit_While(self, node: ast.While):
        """Check while loops for potential infinite loops."""
        # Check if while True without break
        if self._is_while_true(node):
            has_break = self._has_break(node.body)
            if not has_break:
                self.result.add_violation(SecurityViolation(
                    node_type="While",
                    message="Potential infinite loop: while True without break",
                    line=node.lineno,
                    column=node.col_offset,
                ))
        
        self.generic_visit(node)
    
    def visit_For(self, node: ast.For):
        """Check for loops for potential issues."""
        # Check for very large range
        if isinstance(node.iter, ast.Call):
            func_name = self._get_func_name(node.iter)
            if func_name == 'range':
                if len(node.iter.args) >= 1:
                    size = self._estimate_size(node.iter.args[0])
                    if size > 10**8:
                        self.result.add_warning(SecurityViolation(
                            node_type="For",
                            message=f"Large range iteration: {size} iterations",
                            line=node.lineno,
                            column=node.col_offset,
                            severity="warning",
                        ))
        
        self.generic_visit(node)
    
    def _get_func_name(self, node: ast.AST) -> str:
        """Extract function name from a Call node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        elif isinstance(node, ast.Call):
            return self._get_func_name(node.func)
        elif isinstance(node, ast.Subscript):
            return self._get_func_name(node.value)
        return ""
    
    def _estimate_size(self, node: ast.AST) -> int:
        """Estimate the size of a value from AST node."""
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return int(abs(node.value))
        elif isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.USub):
                return self._estimate_size(node.operand)
        elif isinstance(node, ast.BinOp):
            if isinstance(node.op, ast.Pow):
                left = self._estimate_size(node.left)
                right = self._estimate_size(node.right)
                return left ** right if left < 100 and right < 10 else 10**10
            elif isinstance(node.op, ast.Mult):
                return self._estimate_size(node.left) * self._estimate_size(node.right)
        return 1
    
    def _is_while_true(self, node: ast.While) -> bool:
        """Check if while loop is 'while True'."""
        if isinstance(node.test, ast.Constant):
            return node.test.value is True
        elif isinstance(node.test, ast.NameConstant):  # Python 3.7
            return node.test.value is True
        return False
    
    def _has_break(self, body: List[ast.stmt]) -> bool:
        """Check if body contains a break statement."""
        for stmt in body:
            if isinstance(stmt, ast.Break):
                return True
            elif isinstance(stmt, ast.If):
                if self._has_break(stmt.body) or self._has_break(stmt.orelse):
                    return True
            elif isinstance(stmt, ast.While):
                # Nested while doesn't count
                pass
            elif isinstance(stmt, ast.For):
                # Nested for doesn't count
                pass
            elif hasattr(stmt, 'body'):
                if isinstance(stmt.body, list):
                    if self._has_break(stmt.body):
                        return True
        return False


def validate_strategy_ast(code: str) -> Tuple[bool, List[str]]:
    """
    Validate strategy code using AST analysis.
    
    Args:
        code: Python code to validate
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    validator = ASTSecurityValidator()
    result = validator.validate(code)
    
    return result.is_valid, result.get_error_messages()


def get_security_report(code: str) -> ValidationResult:
    """
    Get detailed security report for strategy code.
    
    Args:
        code: Python code to validate
        
    Returns:
        ValidationResult with detailed violations and warnings
    """
    validator = ASTSecurityValidator()
    return validator.validate(code)


# Example usage and testing
if __name__ == "__main__":
    test_codes = [
        # Test 1: Valid code
        ("""
import pandas as pd

def on_bar(ctx, bar):
    if bar['close'] > bar['open']:
        ctx.buy(bar['close'], 100)
""", True, "Valid pandas import"),
        
        # Test 2: Forbidden import
        ("""
import os

def on_bar(ctx, bar):
    os.system('ls')
""", False, "Forbidden os import"),
        
        # Test 3: Eval attack
        ("""
def on_bar(ctx, bar):
    eval("print('hello')")
""", False, "Forbidden eval call"),
        
        # Test 4: Class introspection
        ("""
def on_bar(ctx, bar):
    x = ''.__class__.__base__.__subclasses__()
""", False, "Forbidden attribute access"),
        
        # Test 5: Infinite loop
        ("""
def on_bar(ctx, bar):
    while True:
        pass
""", False, "Infinite loop detection"),
        
        # Test 6: Memory bomb
        ("""
def on_bar(ctx, bar):
    x = [0] * 10**10
""", False, "Memory bomb detection"),
    ]
    
    print("=" * 80)
    print("AST Security Validator Tests")
    print("=" * 80)
    
    for code, expected_valid, description in test_codes:
        print(f"\nTest: {description}")
        is_valid, errors = validate_strategy_ast(code)
        status = "PASS" if is_valid == expected_valid else "FAIL"
        print(f"  Result: {status}")
        print(f"  Valid: {is_valid} (expected: {expected_valid})")
        if errors:
            print(f"  Errors: {errors}")
