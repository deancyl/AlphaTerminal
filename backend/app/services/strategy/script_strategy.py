from __future__ import annotations

import asyncio
import logging
import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from .ast_validator import validate_strategy_ast, get_security_report
from .sandbox import (
    create_sandbox_namespace,
    SecureExecutor,
    StrategyTimeoutError,
    StrategySecurityError,
)
from .audit import log_strategy_execution, compute_code_hash

logger = logging.getLogger(__name__)


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


@dataclass
class Order:
    id: str
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    status: str = "pending"
    filled_price: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)
    filled_at: Optional[datetime] = None


@dataclass
class Position:
    side: str
    size: float
    entry_price: float
    unrealized_pnl: float = 0.0


@dataclass
class StrategyContext:
    df: pd.DataFrame
    current_index: int = 0
    position: Optional[Position] = None
    balance: float = 100000.0
    equity: float = 100000.0
    orders: List[Order] = field(default_factory=list)
    trades: List[Dict] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)

    def log(self, message: str):
        self.logs.append(f"[{self.current_index}] {message}")

    def buy(self, price: float, quantity: float):
        order = Order(
            id=f"buy_{len(self.orders)}",
            symbol=self.df.iloc[self.current_index].name if hasattr(self.df.iloc[self.current_index], 'name') else str(self.current_index),
            side=OrderSide.BUY,
            quantity=quantity,
            price=price,
        )
        self.orders.append(order)
        self.log(f"BUY {quantity} @ {price}")
        return order

    def sell(self, price: float, quantity: float):
        order = Order(
            id=f"sell_{len(self.orders)}",
            symbol=self.df.iloc[self.current_index].name if hasattr(self.df.iloc[self.current_index], 'name') else str(self.current_index),
            side=OrderSide.SELL,
            quantity=quantity,
            price=price,
        )
        self.orders.append(order)
        self.log(f"SELL {quantity} @ {price}")
        return order

    def close_position(self):
        if self.position:
            self.log(f"CLOSE position: {self.position.size} @ market")
            self.position = None


class ScriptStrategy:
    DEFAULT_TIMEOUT = 30.0
    
    def __init__(
        self, 
        code: str, 
        initial_capital: float = 100000.0, 
        commission: float = 0.001,
        timeout: float = DEFAULT_TIMEOUT,
        validate_security: bool = True,
    ):
        self.code = code
        self.initial_capital = initial_capital
        self.commission = commission
        self.timeout = timeout
        self.validate_security = validate_security
        self._namespace: Dict[str, Any] = {}
        self._compile()

    def _compile(self):
        if not self.code or not self.code.strip():
            raise ValueError("Strategy code cannot be empty")
        
        if self.validate_security:
            is_valid, errors = validate_strategy_ast(self.code)
            if not is_valid:
                raise StrategySecurityError(
                    f"Security validation failed: {'; '.join(errors)}"
                )
        
        if self.validate_security:
            self._namespace = create_sandbox_namespace(ctx=None)
        else:
            self._namespace = {"pd": pd}
        
        self._namespace["OrderSide"] = OrderSide
        self._namespace["OrderType"] = OrderType
        self._namespace["buy"] = self._buy
        self._namespace["sell"] = self._sell
        self._namespace["close_position"] = self._close_position
        self._namespace["log"] = self._log
        
        try:
            exec(self.code, self._namespace)
        except SyntaxError as e:
            raise ValueError(f"Strategy syntax error at line {e.lineno}: {e.msg}")
        except Exception as e:
            logger.warning(f"[ScriptStrategy] Compilation error: {e}")
            raise ValueError(f"Strategy compilation failed: {e}")
    
    def _create_context(self, df: pd.DataFrame) -> StrategyContext:
        ctx = StrategyContext(df=df, balance=self.initial_capital, equity=self.initial_capital)
        self._namespace["ctx"] = ctx
        return ctx

    def _log(self, message: str):
        if "ctx" in self._namespace and self._namespace["ctx"]:
            self._namespace["ctx"].log(message)
        else:
            logger.info(f"[ScriptStrategy] {message}")

    def _buy(self, price: float, quantity: float):
        ctx = self._namespace.get("ctx")
        if ctx:
            return ctx.buy(price, quantity)
        return None

    def _sell(self, price: float, quantity: float):
        ctx = self._namespace.get("ctx")
        if ctx:
            return ctx.sell(price, quantity)
        return None

    def _close_position(self):
        ctx = self._namespace.get("ctx")
        if ctx:
            ctx.close_position()

    def on_init(self, ctx: StrategyContext):
        if "on_init" in self._namespace:
            old_ctx = self._namespace["ctx"]
            self._namespace["ctx"] = ctx
            try:
                self._namespace["on_init"](ctx)
            except Exception as e:
                logger.warning(f"[ScriptStrategy] on_init error: {e}")
            finally:
                self._namespace["ctx"] = old_ctx

    def on_bar(self, ctx: StrategyContext, bar: pd.Series):
        if "on_bar" in self._namespace:
            old_ctx = self._namespace["ctx"]
            self._namespace["ctx"] = ctx
            try:
                self._namespace["on_bar"](ctx, bar)
            except Exception as e:
                logger.warning(f"[ScriptStrategy] on_bar error at {ctx.current_index}: {e}")
            finally:
                self._namespace["ctx"] = old_ctx

    def run(self, df: pd.DataFrame, user_id: str = "anonymous") -> Dict[str, Any]:
        return self._run_with_timeout(df, user_id)

    def _run_with_timeout(self, df: pd.DataFrame, user_id: str = "anonymous") -> Dict[str, Any]:
        import signal
        import time

        def timeout_handler(signum, frame):
            raise StrategyTimeoutError(
                f"Strategy execution exceeded {self.timeout}s timeout"
            )

        start_time = time.time()
        execution_status = "success"
        error_message = None

        original_handler = None
        timeout_enabled = False

        try:
            try:
                original_handler = signal.signal(signal.SIGALRM, timeout_handler)
                signal.setitimer(signal.ITIMER_REAL, self.timeout)
                timeout_enabled = True
            except (ValueError, OSError):
                pass

            result = self._execute_strategy(df)
            return result
        except StrategyTimeoutError as e:
            execution_status = "timeout"
            error_message = str(e)
            raise
        except StrategySecurityError as e:
            execution_status = "security_error"
            error_message = str(e)
            raise
        except Exception as e:
            execution_status = "failed"
            error_message = str(e)
            raise
        finally:
            if timeout_enabled:
                try:
                    signal.setitimer(signal.ITIMER_REAL, 0)
                    if original_handler is not None:
                        signal.signal(signal.SIGALRM, original_handler)
                except (ValueError, OSError):
                    pass

            execution_time_ms = (time.time() - start_time) * 1000

            try:
                log_strategy_execution(
                    user_id=user_id,
                    code=self.code,
                    action="execute",
                    is_validated=True,
                    execution_status=execution_status,
                    execution_time_ms=execution_time_ms,
                    error_message=error_message,
                )
            except Exception as e:
                logger.warning(f"[Audit] Failed to log execution: {e}")
    
    def _execute_strategy(self, df: pd.DataFrame) -> Dict[str, Any]:
        ctx = self._create_context(df)

        self.on_init(ctx)

        for i in range(len(df)):
            ctx.current_index = i
            bar = df.iloc[i]

            self.on_bar(ctx, bar)

            self._process_orders(ctx, bar)

            ctx.equity = ctx.balance
            if ctx.position:
                ctx.position.unrealized_pnl = (bar["close"] - ctx.position.entry_price) * ctx.position.size
                ctx.equity += ctx.position.unrealized_pnl

        return {
            "context": ctx,
            "final_equity": ctx.equity,
            "total_return": (ctx.equity - self.initial_capital) / self.initial_capital,
            "trades": ctx.trades,
            "logs": ctx.logs,
        }

    def _process_orders(self, ctx: StrategyContext, bar: pd.Series):
        for order in ctx.orders:
            if order.status == "pending":
                if order.side == OrderSide.BUY:
                    cost = order.quantity * order.price * (1 + self.commission)
                    if ctx.balance >= cost:
                        ctx.balance -= cost
                        if ctx.position is None:
                            ctx.position = Position(
                                side="long",
                                size=order.quantity,
                                entry_price=order.price,
                            )
                            ctx.trades.append({
                                "side": "BUY",
                                "price": order.price,
                                "quantity": order.quantity,
                                "cost": cost,
                                "index": ctx.current_index,
                            })
                        order.status = "filled"
                        order.filled_price = order.price
                elif order.side == OrderSide.SELL:
                    if ctx.position and ctx.position.size >= order.quantity:
                        proceeds = order.quantity * order.price * (1 - self.commission)
                        ctx.balance += proceeds
                        ctx.position.size -= order.quantity
                        if ctx.position.size == 0:
                            ctx.position = None
                        ctx.trades.append({
                            "side": "SELL",
                            "price": order.price,
                            "quantity": order.quantity,
                            "proceeds": proceeds,
                            "index": ctx.current_index,
                        })
                        order.status = "filled"
                        order.filled_price = order.price


def create_script_strategy(code: str, initial_capital: float = 100000.0, commission: float = 0.001) -> ScriptStrategy:
    return ScriptStrategy(code, initial_capital, commission)


EXAMPLE_SCRIPT_STRATEGIES = {
    "ma_cross_script": '''
def on_init(ctx):
    ctx.log("Strategy initialized with capital: " + str(ctx.balance))

def on_bar(ctx, bar):
    fast_ma = bar["close"]
    slow_ma = bar["close"]

    if not ctx.position:
        if fast_ma > slow_ma:
            amount = ctx.balance * 0.95 / bar["close"]
            ctx.buy(bar["close"], amount)
    else:
        if fast_ma < slow_ma:
            ctx.close_position()
''',
}


def get_builtin_script_strategy(name: str) -> ScriptStrategy:
    if name not in EXAMPLE_SCRIPT_STRATEGIES:
        raise ValueError(f"Unknown builtin script strategy: {name}")
    return create_script_strategy(EXAMPLE_SCRIPT_STRATEGIES[name])
