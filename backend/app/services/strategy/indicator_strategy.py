from __future__ import annotations

import ast
import logging
import re
import textwrap
import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class StrategySpec:
    name: str
    description: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    stop_loss_pct: float = 2.0
    take_profit_pct: float = 6.0
    entry_pct: float = 1.0
    trailing_enabled: bool = False
    trailing_stop_pct: float = 0.0
    trailing_activation_pct: float = 0.0
    trade_direction: str = "both"
    version: str = "1.0"
    author: str = ""
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class StrategyParameter:
    name: str
    type: str
    default: Any
    description: str = ""
    min_value: Optional[float] = None
    max_value: Optional[float] = None


class IndicatorStrategyParser:
    NAME_PATTERN = re.compile(r"#\s*@name\s+(.+)")
    DESC_PATTERN = re.compile(r"#\s*@description\s+(.+)")
    PARAM_PATTERN = re.compile(r"#\s*@param\s+(\w+)\s+(\w+)\s+(\S+)\s+(.+)")
    STRATEGY_PATTERN = re.compile(r"#\s*@strategy\s+(\w+)\s+(.+)")

    BUILTIN_FUNCTIONS = {
        'pd': pd,
        'np': None,
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

    def __init__(self):
        self._logger = logging.getLogger(__name__)

    def parse(self, code: str) -> Tuple[StrategySpec, Callable]:
        spec = self._parse_metadata(code)
        compiled_func = self._compile_code(code)
        return spec, compiled_func

    def _parse_metadata(self, code: str) -> StrategySpec:
        name = "Unnamed Strategy"
        description = ""
        parameters: Dict[str, Any] = {}
        stop_loss_pct = 2.0
        take_profit_pct = 6.0
        entry_pct = 1.0
        trailing_enabled = False
        trailing_stop_pct = 0.0
        trailing_activation_pct = 0.0
        trade_direction = "both"

        for line in code.split('\n'):
            match = self.NAME_PATTERN.match(line.strip())
            if match:
                name = match.group(1).strip()
                continue

            match = self.DESC_PATTERN.match(line.strip())
            if match:
                description = match.group(1).strip()
                continue

            match = self.PARAM_PATTERN.match(line.strip())
            if match:
                param_name = match.group(1).strip()
                param_type = match.group(2).strip()
                param_default = match.group(3).strip()
                param_desc = match.group(4).strip()
                parameters[param_name] = {
                    'type': param_type,
                    'default': param_default,
                    'description': param_desc
                }
                continue

            match = self.STRATEGY_PATTERN.match(line.strip())
            if match:
                key = match.group(1).strip()
                value = match.group(2).strip()
                if key == 'stopLossPct':
                    stop_loss_pct = float(value)
                elif key == 'takeProfitPct':
                    take_profit_pct = float(value)
                elif key == 'entryPct':
                    entry_pct = float(value)
                elif key == 'trailingEnabled':
                    trailing_enabled = value.lower() == 'true'
                elif key == 'trailingStopPct':
                    trailing_stop_pct = float(value)
                elif key == 'trailingActivationPct':
                    trailing_activation_pct = float(value)
                elif key == 'tradeDirection':
                    trade_direction = value.lower()

        return StrategySpec(
            name=name,
            description=description,
            parameters=parameters,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            entry_pct=entry_pct,
            trailing_enabled=trailing_enabled,
            trailing_stop_pct=trailing_stop_pct,
            trailing_activation_pct=trailing_activation_pct,
            trade_direction=trade_direction,
        )

    def _parse_param_default(self, param_type: str) -> Any:
        type_defaults = {
            'int': 0,
            'float': 0.0,
            'bool': False,
            'str': '',
        }
        return type_defaults.get(param_type, None)

    def _compile_code(self, code: str) -> Callable:
        code = textwrap.dedent(code)
        lines = code.split('\n')
        
        # Find the first non-comment, non-empty line
        start_idx = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                start_idx = i
                break
        
        # Collect all code lines (excluding comments)
        code_lines = []
        for line in lines[start_idx:]:
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                code_lines.append(line)
        
        def execute_strategy(df: pd.DataFrame, params: Dict[str, Any]) -> Dict[str, Any]:
            local_vars = {
                'pd': pd,
                'df': df.copy(),
                'params': params,
                'output': None,
            }
            local_vars.update(self.BUILTIN_FUNCTIONS)
            local_vars.update(params)

            full_code = '\n'.join(code_lines)
            try:
                exec(full_code, local_vars)
            except Exception as e:
                logger.warning(f"[IndicatorStrategy] Execution error: {e}")
                return {'indicators': {}, 'signals': {'buy': pd.Series(False, index=df.index), 'sell': pd.Series(False, index=df.index)}}

            return local_vars.get('output', {'indicators': {}, 'signals': {'buy': pd.Series(False, index=df.index), 'sell': pd.Series(False, index=df.index)}})

        return execute_strategy


class IndicatorStrategy:
    def __init__(self, code: str, spec: Optional[StrategySpec] = None):
        self.code = code
        self.parser = IndicatorStrategyParser()

        if spec is not None:
            self.spec = spec
            _, self._execute_func = self.parser.parse(code)
        else:
            self.spec, self._execute_func = self.parser.parse(code)

    def evaluate(self, df: pd.DataFrame, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        merged_params = {**self.spec.parameters}
        if params:
            merged_params.update(params)

        converted_params = {}
        for key, value in merged_params.items():
            if isinstance(value, dict) and 'type' in value:
                type_str = value.get('type', 'float')
                default_val = value.get('default', 0)
                if type_str == 'int':
                    converted_params[key] = int(params.get(key, default_val) if params else default_val)
                elif type_str == 'float':
                    converted_params[key] = float(params.get(key, default_val) if params else default_val)
                elif type_str == 'bool':
                    converted_params[key] = bool(params.get(key, default_val) if params else default_val)
                else:
                    converted_params[key] = params.get(key, default_val) if params else default_val
            else:
                converted_params[key] = value

        result = self._execute_func(df, converted_params)

        return {
            'indicators': result.get('indicators', {}),
            'signals': result.get('signals', {}),
            'params': converted_params,
        }

    def to_signal_df(self, df: pd.DataFrame, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        result = self.evaluate(df, params)
        signals = result.get('signals', {})

        buy_signal = signals.get('buy', pd.Series(False, index=df.index))
        sell_signal = signals.get('sell', pd.Series(False, index=df.index))

        if not isinstance(buy_signal, pd.Series):
            buy_signal = pd.Series(buy_signal, index=df.index)
        if not isinstance(sell_signal, pd.Series):
            sell_signal = pd.Series(sell_signal, index=df.index)

        signal = pd.Series(0, index=df.index)
        signal[buy_signal.astype(bool)] = 1
        signal[sell_signal.astype(bool)] = -1

        return pd.DataFrame({
            'buy': buy_signal,
            'sell': sell_signal,
            'signal': signal,
        }, index=df.index)

    def get_indicator_names(self) -> List[str]:
        return list(self.spec.parameters.keys())

    def __repr__(self) -> str:
        return f"<IndicatorStrategy: {self.spec.name}>"


class BuiltinIndicators:
    @staticmethod
    def sma(series: pd.Series, period: int) -> pd.Series:
        return series.rolling(window=period).mean()

    @staticmethod
    def ema(series: pd.Series, period: int) -> pd.Series:
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def rsi(series: pd.Series, period: int = 14) -> pd.Series:
        delta = series.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=signal, adjust=False).mean()
        histogram = (dif - dea) * 2
        return dif, dea, histogram

    @staticmethod
    def bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
        middle = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        upper = middle + std_dev * std
        lower = middle - std_dev * std
        return upper, middle, lower

    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()

    @staticmethod
    def kdj(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 9, m1: int = 3, m2: int = 3) -> Tuple[pd.Series, pd.Series, pd.Series]:
        lowest_low = low.rolling(window=n).min()
        highest_high = high.rolling(window=n).max()
        rsv = (close - lowest_low) / (highest_high - lowest_low) * 100
        k = rsv.ewm(com=m1-1, adjust=False).mean()
        d = k.ewm(com=m2-1, adjust=False).mean()
        j = 3 * k - 2 * d
        return k, d, j


class StrategyValidator:
    FORBIDDEN_PATTERNS = [
        'import os', 'import sys', 'import subprocess', 'import multiprocessing',
        'import threading', 'import socket', 'import urllib', 'import http',
        'import requests', 'eval(', 'exec(', 'open(', 'file(', '__import__',
        'compile(', 'getattr(', 'setattr(', 'delattr(',
    ]

    @classmethod
    def validate(cls, code: str) -> Tuple[bool, Optional[str]]:
        if not code or not code.strip():
            return False, "Strategy code cannot be empty"

        for pattern in cls.FORBIDDEN_PATTERNS:
            if pattern in code:
                return False, f"Code contains forbidden pattern: {pattern}"

        if 'output' not in code:
            return False, "Code must contain 'output' variable definition"

        try:
            ast.parse(code)
        except SyntaxError as e:
            return False, f"Syntax error: {e}"

        return True, None

    @classmethod
    def validate_params(cls, spec: StrategySpec, params: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        for param_name, param_def in spec.parameters.items():
            if param_name not in params:
                continue

            value = params[param_name]
            param_type = param_def.get('type', 'float')

            if param_type == 'int' and not isinstance(value, int):
                try:
                    params[param_name] = int(value)
                except (ValueError, TypeError):
                    return False, f"Parameter {param_name} must be integer"
            elif param_type == 'float' and not isinstance(value, (int, float)):
                try:
                    params[param_name] = float(value)
                except (ValueError, TypeError):
                    return False, f"Parameter {param_name} must be numeric"

            min_val = param_def.get('min_value')
            max_val = param_def.get('max_value')
            if min_val is not None and value < min_val:
                return False, f"Parameter {param_name} below minimum {min_val}"
            if max_val is not None and value > max_val:
                return False, f"Parameter {param_name} exceeds maximum {max_val}"

        return True, None


EXAMPLE_STRATEGIES = {
    "ma_cross": '''
# @name 均线金叉策略
# @description 短期均线上穿长期均线时买入，下穿时卖出
# @param fast_period int 5 短期均线周期
# @param slow_period int 20 长期均线周期
# @strategy stopLossPct 2
# @strategy takeProfitPct 6

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

    "bollinger_bounce": '''
# @name 布林带均值回归策略
# @description 价格触及布林带下轨时买入，上轨时卖出
# @param bb_period int 20 布林带周期
# @param bb_std float 2 布林带标准差倍数
# @strategy stopLossPct 2
# @strategy takeProfitPct 5

middle = df['close'].rolling(bb_period).mean()
std = df['close'].rolling(bb_period).std()
upper = middle + bb_std * std
lower = middle - bb_std * std
buy = (df['close'] < lower) & (df['close'].shift(1) >= lower.shift(1))
sell = (df['close'] > upper) & (df['close'].shift(1) <= upper.shift(1))
output = {
    'indicators': {'upper': upper, 'middle': middle, 'lower': lower},
    'signals': {'buy': buy, 'sell': sell}
}
''',

    "macd_cross": '''
# @name MACD 金叉死叉策略
# @description DIF上穿DEA买入，下穿卖出
# @param macd_fast int 12 快线周期
# @param macd_slow int 26 慢线周期
# @param macd_signal int 9 信号线周期
# @strategy stopLossPct 2
# @strategy takeProfitPct 6

ema_fast = df['close'].ewm(span=macd_fast, adjust=False).mean()
ema_slow = df['close'].ewm(span=macd_slow, adjust=False).mean()
dif = ema_fast - ema_slow
dea = dif.ewm(span=macd_signal, adjust=False).mean()
histogram = (dif - dea) * 2
buy = (dif > dea) & (dif.shift(1) <= dea.shift(1))
sell = (dif < dea) & (dif.shift(1) >= dea.shift(1))
output = {
    'indicators': {'dif': dif, 'dea': dea, 'histogram': histogram},
    'signals': {'buy': buy, 'sell': sell}
}
''',
}


def create_indicator_strategy(code: str) -> IndicatorStrategy:
    is_valid, error = StrategyValidator.validate(code)
    if not is_valid:
        raise ValueError(f"Strategy validation failed: {error}")
    return IndicatorStrategy(code)


def get_builtin_strategy(name: str) -> IndicatorStrategy:
    if name not in EXAMPLE_STRATEGIES:
        raise ValueError(f"Unknown builtin strategy: {name}")
    return create_indicator_strategy(EXAMPLE_STRATEGIES[name])
