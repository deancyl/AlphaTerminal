"""
Backtest Engine Core with Comprehensive Debug Logging

Event-driven backtest engine supporting multiple timeframes, commission/slippage modeling,
position tracking, and performance metrics calculation.

Debug Cycles:
  1. Engine initialization
  2. Strategy compilation
  3. Data loading
  4. Bar processing
  5. Order execution
  6. Position update
  7. Metric calculation
  8. Result generation
  9. Error handling
  10. Performance summary
"""
import logging
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Tuple
from datetime import datetime
from enum import Enum
import traceback

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════

class TimeFrame(Enum):
    """Supported timeframes for backtesting"""
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1H"
    H4 = "4H"
    D1 = "1D"


class OrderType(Enum):
    """Order types"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(Enum):
    """Order side (buy/sell)"""
    BUY = "buy"
    SELL = "sell"


class PositionSide(Enum):
    """Position side (long/short)"""
    LONG = "long"
    SHORT = "short"


class TradeDirection(Enum):
    """Trade direction filter"""
    LONG_ONLY = "long_only"
    SHORT_ONLY = "short_only"
    BOTH = "both"


# ═══════════════════════════════════════════════════════════════
# Dataclasses
# ═══════════════════════════════════════════════════════════════

@dataclass
class BacktestConfig:
    """
    Backtest configuration parameters
    
    Attributes:
        initial_capital: Starting capital for backtest
        commission: Commission rate (e.g., 0.0003 = 0.03%)
        slippage: Slippage rate (e.g., 0.0001 = 0.01%)
        leverage: Leverage multiplier (1.0 = no leverage)
        trade_direction: Allowed trade directions
        stop_loss_pct: Stop loss percentage (0 = disabled)
        take_profit_pct: Take profit percentage (0 = disabled)
        position_size_pct: Position size as % of capital (default 95%)
        max_positions: Maximum concurrent positions (default 1)
        timeframe: Data timeframe
        warmup_bars: Number of bars for indicator warmup
    """
    initial_capital: float = 100000.0
    commission: float = 0.0003  # 0.03%
    slippage: float = 0.0001   # 0.01%
    leverage: float = 1.0
    trade_direction: TradeDirection = TradeDirection.BOTH
    stop_loss_pct: float = 0.0
    take_profit_pct: float = 0.0
    position_size_pct: float = 0.95
    max_positions: int = 1
    timeframe: TimeFrame = TimeFrame.D1
    warmup_bars: int = 50
    
    def __post_init__(self):
        """Validate configuration parameters"""
        if self.initial_capital <= 0:
            raise ValueError(f"initial_capital must be positive, got {self.initial_capital}")
        if not 0 <= self.commission < 1:
            raise ValueError(f"commission must be in [0, 1), got {self.commission}")
        if not 0 <= self.slippage < 1:
            raise ValueError(f"slippage must be in [0, 1), got {self.slippage}")
        if self.leverage < 1:
            raise ValueError(f"leverage must be >= 1, got {self.leverage}")
        if not 0 <= self.position_size_pct <= 1:
            raise ValueError(f"position_size_pct must be in [0, 1], got {self.position_size_pct}")
        if self.max_positions < 1:
            raise ValueError(f"max_positions must be >= 1, got {self.max_positions}")


@dataclass
class Order:
    """
    Order representation
    
    Attributes:
        symbol: Trading symbol
        side: Buy or sell
        order_type: Market, limit, stop, etc.
        quantity: Number of shares/contracts
        price: Order price (for limit/stop orders)
        timestamp: Order creation time
        status: Order status
        filled_price: Actual fill price
        filled_quantity: Actually filled quantity
    """
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    price: Optional[float] = None
    timestamp: Optional[datetime] = None
    status: str = "pending"
    filled_price: Optional[float] = None
    filled_quantity: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "quantity": self.quantity,
            "price": self.price,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "status": self.status,
            "filled_price": self.filled_price,
            "filled_quantity": self.filled_quantity
        }


@dataclass
class Position:
    """
    Position tracking
    
    Attributes:
        symbol: Trading symbol
        side: Long or short
        quantity: Position size
        entry_price: Average entry price
        entry_time: Position open time
        unrealized_pnl: Current unrealized P&L
        stop_loss: Stop loss price
        take_profit: Take profit price
    """
    symbol: str
    side: PositionSide
    quantity: int
    entry_price: float
    entry_time: datetime
    unrealized_pnl: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    def update_pnl(self, current_price: float):
        """Update unrealized P&L based on current price"""
        if self.side == PositionSide.LONG:
            self.unrealized_pnl = (current_price - self.entry_price) * self.quantity
        else:
            self.unrealized_pnl = (self.entry_price - current_price) * self.quantity
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": self.quantity,
            "entry_price": round(self.entry_price, 2),
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "stop_loss": round(self.stop_loss, 2) if self.stop_loss else None,
            "take_profit": round(self.take_profit, 2) if self.take_profit else None
        }


@dataclass
class Trade:
    """
    Completed trade representation
    
    Attributes:
        symbol: Trading symbol
        side: Long or short
        entry_price: Entry price
        exit_price: Exit price
        quantity: Position size
        entry_time: Entry timestamp
        exit_time: Exit timestamp
        pnl: Realized P&L
        pnl_pct: P&L percentage
        commission: Total commission paid
        exit_reason: Reason for exit (signal, stop_loss, take_profit, etc.)
    """
    symbol: str
    side: PositionSide
    entry_price: float
    exit_price: float
    quantity: int
    entry_time: datetime
    exit_time: datetime
    pnl: float = 0.0
    pnl_pct: float = 0.0
    commission: float = 0.0
    exit_reason: str = "signal"
    
    def __post_init__(self):
        """Calculate P&L after initialization"""
        if self.pnl == 0.0:
            if self.side == PositionSide.LONG:
                self.pnl = (self.exit_price - self.entry_price) * self.quantity
            else:
                self.pnl = (self.entry_price - self.exit_price) * self.quantity
        
        if self.pnl_pct == 0.0 and self.entry_price > 0:
            if self.side == PositionSide.LONG:
                self.pnl_pct = ((self.exit_price - self.entry_price) / self.entry_price) * 100
            else:
                self.pnl_pct = ((self.entry_price - self.exit_price) / self.entry_price) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "symbol": self.symbol,
            "side": self.side.value,
            "entry_price": round(self.entry_price, 2),
            "exit_price": round(self.exit_price, 2),
            "quantity": self.quantity,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "pnl": round(self.pnl, 2),
            "pnl_pct": round(self.pnl_pct, 2),
            "commission": round(self.commission, 4),
            "exit_reason": self.exit_reason
        }


@dataclass
class EquityPoint:
    """
    Single point on equity curve
    
    Attributes:
        timestamp: Time of equity snapshot
        equity: Total portfolio equity
        cash: Available cash
        position_value: Value of open positions
        drawdown: Current drawdown from peak
        drawdown_pct: Drawdown percentage
    """
    timestamp: datetime
    equity: float
    cash: float
    position_value: float = 0.0
    drawdown: float = 0.0
    drawdown_pct: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "equity": round(self.equity, 2),
            "cash": round(self.cash, 2),
            "position_value": round(self.position_value, 2),
            "drawdown": round(self.drawdown, 2),
            "drawdown_pct": round(self.drawdown_pct, 2)
        }


@dataclass
class PerformanceMetrics:
    """
    Comprehensive performance metrics
    
    Attributes:
        total_return: Total return in currency
        total_return_pct: Total return percentage
        annualized_return_pct: Annualized return percentage
        sharpe_ratio: Sharpe ratio
        sortino_ratio: Sortino ratio
        max_drawdown: Maximum drawdown in currency
        max_drawdown_pct: Maximum drawdown percentage
        win_rate: Percentage of winning trades
        profit_factor: Gross profit / gross loss
        avg_trade_return: Average trade return percentage
        total_trades: Total number of trades
        winning_trades: Number of winning trades
        losing_trades: Number of losing trades
        avg_winning_trade: Average winning trade return
        avg_losing_trade: Average losing trade return
        largest_win: Largest winning trade
        largest_loss: Largest losing trade
        max_consecutive_wins: Maximum consecutive winning trades
        max_consecutive_losses: Maximum consecutive losing trades
        avg_holding_period: Average holding period in bars
        volatility_annualized: Annualized volatility
        calmar_ratio: Calmar ratio (return / max drawdown)
    """
    total_return: float = 0.0
    total_return_pct: float = 0.0
    annualized_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_trade_return: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_winning_trade: float = 0.0
    avg_losing_trade: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    avg_holding_period: float = 0.0
    volatility_annualized: float = 0.0
    calmar_ratio: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "total_return": round(self.total_return, 2),
            "total_return_pct": round(self.total_return_pct, 2),
            "annualized_return_pct": round(self.annualized_return_pct, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 3),
            "sortino_ratio": round(self.sortino_ratio, 3),
            "max_drawdown": round(self.max_drawdown, 2),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "win_rate": round(self.win_rate, 2),
            "profit_factor": round(self.profit_factor, 2),
            "avg_trade_return": round(self.avg_trade_return, 2),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "avg_winning_trade": round(self.avg_winning_trade, 2),
            "avg_losing_trade": round(self.avg_losing_trade, 2),
            "largest_win": round(self.largest_win, 2),
            "largest_loss": round(self.largest_loss, 2),
            "max_consecutive_wins": self.max_consecutive_wins,
            "max_consecutive_losses": self.max_consecutive_losses,
            "avg_holding_period": round(self.avg_holding_period, 1),
            "volatility_annualized": round(self.volatility_annualized, 2),
            "calmar_ratio": round(self.calmar_ratio, 3)
        }


@dataclass
class BacktestResult:
    """
    Complete backtest result
    
    Attributes:
        config: Backtest configuration used
        trades: List of completed trades
        equity_curve: Equity curve over time
        metrics: Performance metrics
        orders: List of all orders
        positions: Final positions (if any)
        benchmark_return_pct: Buy-and-hold return for comparison
        data_info: Information about data used
        execution_time_ms: Total execution time in milliseconds
        debug_log: Debug messages from all cycles
    """
    config: BacktestConfig
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[EquityPoint] = field(default_factory=list)
    metrics: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    orders: List[Order] = field(default_factory=list)
    positions: List[Position] = field(default_factory=list)
    benchmark_return_pct: float = 0.0
    data_info: Dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float = 0.0
    debug_log: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "config": {
                "initial_capital": self.config.initial_capital,
                "commission": self.config.commission,
                "slippage": self.config.slippage,
                "leverage": self.config.leverage,
                "trade_direction": self.config.trade_direction.value,
                "stop_loss_pct": self.config.stop_loss_pct,
                "take_profit_pct": self.config.take_profit_pct,
                "position_size_pct": self.config.position_size_pct,
                "max_positions": self.config.max_positions,
                "timeframe": self.config.timeframe.value
            },
            "trades": [t.to_dict() for t in self.trades],
            "equity_curve": [e.to_dict() for e in self.equity_curve],
            "metrics": self.metrics.to_dict(),
            "orders": [o.to_dict() for o in self.orders],
            "positions": [p.to_dict() for p in self.positions],
            "benchmark_return_pct": round(self.benchmark_return_pct, 2),
            "data_info": self.data_info,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "debug_log": self.debug_log
        }


# ═══════════════════════════════════════════════════════════════
# Strategy Context
# ═══════════════════════════════════════════════════════════════

class StrategyContext:
    """
    Context object passed to strategy on each bar
    
    Provides access to current market data, portfolio state, and order methods.
    """
    
    def __init__(self, engine: 'BacktestEngine', bar_data: Dict[str, Any]):
        self._engine = engine
        self._bar_data = bar_data
        self._orders_to_place: List[Order] = []
    
    @property
    def current_bar(self) -> Dict[str, Any]:
        """Current bar data"""
        return self._bar_data
    
    @property
    def timestamp(self) -> datetime:
        """Current timestamp"""
        return self._bar_data.get('timestamp', datetime.now())
    
    @property
    def open(self) -> float:
        """Current bar open price"""
        return self._bar_data.get('open', 0.0)
    
    @property
    def high(self) -> float:
        """Current bar high price"""
        return self._bar_data.get('high', 0.0)
    
    @property
    def low(self) -> float:
        """Current bar low price"""
        return self._bar_data.get('low', 0.0)
    
    @property
    def close(self) -> float:
        """Current bar close price"""
        return self._bar_data.get('close', 0.0)
    
    @property
    def volume(self) -> float:
        """Current bar volume"""
        return self._bar_data.get('volume', 0.0)
    
    @property
    def symbol(self) -> str:
        """Current symbol"""
        return self._bar_data.get('symbol', '')
    
    @property
    def cash(self) -> float:
        """Available cash"""
        return self._engine._cash
    
    @property
    def equity(self) -> float:
        """Total equity"""
        return self._engine._equity
    
    @property
    def positions(self) -> List[Position]:
        """Current positions"""
        return list(self._engine._positions.values())
    
    @property
    def position_count(self) -> int:
        """Number of open positions"""
        return len(self._engine._positions)
    
    def has_position(self, symbol: str = None) -> bool:
        """Check if has position (for symbol or any)"""
        if symbol:
            return symbol in self._engine._positions
        return len(self._engine._positions) > 0
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for symbol"""
        return self._engine._positions.get(symbol)
    
    def buy(self, symbol: str, quantity: int = None, price: float = None, 
            order_type: OrderType = OrderType.MARKET) -> Order:
        """
        Place buy order
        
        Args:
            symbol: Symbol to buy
            quantity: Number of shares (None = auto-calculate)
            price: Limit price (for limit orders)
            order_type: Order type
            
        Returns:
            Order object
        """
        # Auto-calculate quantity if not specified
        if quantity is None:
            position_value = self.cash * self._engine._config.position_size_pct
            exec_price = price if price else self.close
            quantity = int(position_value / exec_price)
        
        order = Order(
            symbol=symbol,
            side=OrderSide.BUY,
            order_type=order_type,
            quantity=quantity,
            price=price,
            timestamp=self.timestamp
        )
        
        self._orders_to_place.append(order)
        return order
    
    def sell(self, symbol: str, quantity: int = None, price: float = None,
             order_type: OrderType = OrderType.MARKET) -> Order:
        """
        Place sell order
        
        Args:
            symbol: Symbol to sell
            quantity: Number of shares (None = close entire position)
            price: Limit price (for limit orders)
            order_type: Order type
            
        Returns:
            Order object
        """
        # Close entire position if quantity not specified
        if quantity is None:
            position = self.get_position(symbol)
            quantity = position.quantity if position else 0
        
        order = Order(
            symbol=symbol,
            side=OrderSide.SELL,
            order_type=order_type,
            quantity=quantity,
            price=price,
            timestamp=self.timestamp
        )
        
        self._orders_to_place.append(order)
        return order
    
    def close_position(self, symbol: str = None):
        """Close position for symbol (or all positions)"""
        if symbol:
            self.sell(symbol)
        else:
            for pos in self.positions:
                self.sell(pos.symbol)


# ═══════════════════════════════════════════════════════════════
# Backtest Engine
# ═══════════════════════════════════════════════════════════════

class BacktestEngine:
    """
    Event-Driven Backtest Engine with Comprehensive Debug Logging
    
    Features:
    - Multiple timeframe support (1m, 5m, 15m, 30m, 1H, 4H, 1D)
    - Commission and slippage modeling
    - Long and short position support
    - Stop loss and take profit
    - Position and portfolio tracking
    - Comprehensive performance metrics
    - 10 debug cycles for detailed logging
    
    Usage:
        config = BacktestConfig(initial_capital=100000)
        engine = BacktestEngine(config)
        result = engine.run_strategy(strategy_func, data)
    """
    
    def __init__(self, config: BacktestConfig):
        """
        Initialize backtest engine
        
        Args:
            config: Backtest configuration
        """
        self._config = config
        self._debug_log: List[str] = []
        
        # ═════════════════════════════════════════════════════════
        # DEBUG CYCLE 1: Engine Initialization
        # ═════════════════════════════════════════════════════════
        self._log_debug("=" * 70)
        self._log_debug("DEBUG CYCLE 1: ENGINE INITIALIZATION")
        self._log_debug("=" * 70)
        self._log_debug(f"Initial Capital: ${config.initial_capital:,.2f}")
        self._log_debug(f"Commission Rate: {config.commission * 100:.4f}%")
        self._log_debug(f"Slippage Rate: {config.slippage * 100:.4f}%")
        self._log_debug(f"Leverage: {config.leverage}x")
        self._log_debug(f"Trade Direction: {config.trade_direction.value}")
        self._log_debug(f"Stop Loss: {config.stop_loss_pct}% (0 = disabled)")
        self._log_debug(f"Take Profit: {config.take_profit_pct}% (0 = disabled)")
        self._log_debug(f"Position Size: {config.position_size_pct * 100}% of capital")
        self._log_debug(f"Max Positions: {config.max_positions}")
        self._log_debug(f"Timeframe: {config.timeframe.value}")
        self._log_debug(f"Warmup Bars: {config.warmup_bars}")
        self._log_debug("-" * 70)
        
        # Initialize state
        self._cash = config.initial_capital
        self._equity = config.initial_capital
        self._peak_equity = config.initial_capital
        self._positions: Dict[str, Position] = {}
        self._trades: List[Trade] = []
        self._orders: List[Order] = []
        self._equity_curve: List[EquityPoint] = []
        
        # Data storage
        self._data: pd.DataFrame = None
        self._data_index = 0
        
        # Strategy function
        self._strategy_func: Callable = None
        self._strategy_compiled = False
        
        self._log_debug("✓ Engine initialized successfully")
        self._log_debug("")
    
    def _log_debug(self, message: str):
        """Add message to debug log"""
        self._debug_log.append(message)
        logger.debug(message)
    
    def run_strategy(
        self,
        strategy_func: Callable[[StrategyContext], None],
        data: pd.DataFrame,
        symbol: str = "ASSET"
    ) -> BacktestResult:
        """
        Run backtest with given strategy and data
        
        Args:
            strategy_func: Strategy function that takes StrategyContext
            data: DataFrame with columns [timestamp, open, high, low, close, volume]
            symbol: Symbol name for the data
            
        Returns:
            BacktestResult with trades, equity curve, and metrics
        """
        start_time = datetime.now()
        
        try:
            # ═════════════════════════════════════════════════════════
            # DEBUG CYCLE 2: Strategy Compilation
            # ═════════════════════════════════════════════════════════
            self._log_debug("=" * 70)
            self._log_debug("DEBUG CYCLE 2: STRATEGY COMPILATION")
            self._log_debug("=" * 70)
            
            if not callable(strategy_func):
                raise ValueError("strategy_func must be callable")
            
            self._strategy_func = strategy_func
            self._strategy_compiled = True
            
            self._log_debug(f"Strategy Function: {strategy_func.__name__ if hasattr(strategy_func, '__name__') else 'lambda'}")
            self._log_debug("✓ Strategy compiled successfully")
            self._log_debug("")
            
            # ═════════════════════════════════════════════════════════
            # DEBUG CYCLE 3: Data Loading
            # ═════════════════════════════════════════════════════════
            self._log_debug("=" * 70)
            self._log_debug("DEBUG CYCLE 3: DATA LOADING")
            self._log_debug("=" * 70)
            
            # Validate data
            if data is None or len(data) == 0:
                raise ValueError("Data cannot be empty")
            
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            missing_cols = [col for col in required_cols if col not in data.columns]
            if missing_cols:
                raise ValueError(f"Missing required columns: {missing_cols}")
            
            # Ensure timestamp column
            if 'timestamp' not in data.columns:
                if isinstance(data.index, pd.DatetimeIndex):
                    data = data.reset_index()
                    data.rename(columns={'index': 'timestamp'}, inplace=True)
                else:
                    data['timestamp'] = pd.date_range(start='2020-01-01', periods=len(data), freq='D')
            
            self._data = data.copy()
            self._data['symbol'] = symbol
            
            self._log_debug(f"Data Shape: {data.shape[0]} rows × {data.shape[1]} columns")
            self._log_debug(f"Date Range: {data['timestamp'].min()} to {data['timestamp'].max()}")
            self._log_debug(f"Price Range: ${data['close'].min():.2f} to ${data['close'].max():.2f}")
            self._log_debug(f"Volume Range: {data['volume'].min():,.0f} to {data['volume'].max():,.0f}")
            self._log_debug(f"Symbol: {symbol}")
            self._log_debug("✓ Data loaded successfully")
            self._log_debug("")
            
            # Calculate benchmark return
            first_close = data['close'].iloc[0]
            last_close = data['close'].iloc[-1]
            benchmark_return_pct = ((last_close - first_close) / first_close) * 100 if first_close > 0 else 0
            
            # ═════════════════════════════════════════════════════════
            # Main Backtest Loop
            # ═════════════════════════════════════════════════════════
            self._log_debug("=" * 70)
            self._log_debug("STARTING BACKTEST SIMULATION")
            self._log_debug("=" * 70)
            self._log_debug(f"Total Bars to Process: {len(data)}")
            self._log_debug(f"Warmup Period: {self._config.warmup_bars} bars")
            self._log_debug("")
            
            # Process each bar
            for idx in range(len(data)):
                self._data_index = idx
                bar_data = data.iloc[idx].to_dict()
                
                # ═════════════════════════════════════════════════════════
                # DEBUG CYCLE 4: Bar Processing
                # ═════════════════════════════════════════════════════════
                if idx < self._config.warmup_bars:
                    # Skip warmup period
                    if idx == 0:
                        self._log_debug(f"Skipping warmup period (bars 0-{self._config.warmup_bars-1})")
                    continue
                
                # Log progress every 100 bars
                if idx % 100 == 0:
                    self._log_debug(f"Processing bar {idx}/{len(data)} ({idx/len(data)*100:.1f}%)")
                
                # Create strategy context
                context = StrategyContext(self, bar_data)
                
                # Call strategy function
                try:
                    self._strategy_func(context)
                except Exception as e:
                    self._log_debug(f"ERROR in strategy at bar {idx}: {e}")
                    raise
                
                # ═════════════════════════════════════════════════════════
                # DEBUG CYCLE 5: Order Execution
                # ═════════════════════════════════════════════════════════
                for order in context._orders_to_place:
                    self._execute_order(order, bar_data)
                
                # ═════════════════════════════════════════════════════════
                # DEBUG CYCLE 6: Position Update
                # ═════════════════════════════════════════════════════════
                self._update_positions(bar_data)
                
                # Check stop loss / take profit
                self._check_exit_orders(bar_data)
                
                # Update equity curve
                self._update_equity_curve(bar_data)
            
            self._log_debug("")
            self._log_debug("✓ Backtest simulation completed")
            self._log_debug("")
            
            # ═════════════════════════════════════════════════════════
            # DEBUG CYCLE 7: Metric Calculation
            # ═════════════════════════════════════════════════════════
            self._log_debug("=" * 70)
            self._log_debug("DEBUG CYCLE 7: METRIC CALCULATION")
            self._log_debug("=" * 70)
            
            metrics = self._calculate_metrics()
            
            self._log_debug(f"Total Return: ${metrics.total_return:,.2f} ({metrics.total_return_pct:.2f}%)")
            self._log_debug(f"Annualized Return: {metrics.annualized_return_pct:.2f}%")
            self._log_debug(f"Sharpe Ratio: {metrics.sharpe_ratio:.3f}")
            self._log_debug(f"Sortino Ratio: {metrics.sortino_ratio:.3f}")
            self._log_debug(f"Max Drawdown: ${metrics.max_drawdown:,.2f} ({metrics.max_drawdown_pct:.2f}%)")
            self._log_debug(f"Win Rate: {metrics.win_rate:.2f}%")
            self._log_debug(f"Profit Factor: {metrics.profit_factor:.2f}")
            self._log_debug(f"Total Trades: {metrics.total_trades}")
            self._log_debug(f"Winning/Losing: {metrics.winning_trades}/{metrics.losing_trades}")
            self._log_debug("✓ Metrics calculated successfully")
            self._log_debug("")
            
            # ═════════════════════════════════════════════════════════
            # DEBUG CYCLE 8: Result Generation
            # ═════════════════════════════════════════════════════════
            self._log_debug("=" * 70)
            self._log_debug("DEBUG CYCLE 8: RESULT GENERATION")
            self._log_debug("=" * 70)
            
            execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            result = BacktestResult(
                config=self._config,
                trades=self._trades,
                equity_curve=self._equity_curve,
                metrics=metrics,
                orders=self._orders,
                positions=list(self._positions.values()),
                benchmark_return_pct=benchmark_return_pct,
                data_info={
                    "symbol": symbol,
                    "start_date": str(data['timestamp'].min()),
                    "end_date": str(data['timestamp'].max()),
                    "total_bars": len(data),
                    "timeframe": self._config.timeframe.value
                },
                execution_time_ms=execution_time_ms,
                debug_log=self._debug_log
            )
            
            self._log_debug(f"Result generated with {len(self._trades)} trades")
            self._log_debug(f"Equity curve points: {len(self._equity_curve)}")
            self._log_debug(f"Execution time: {execution_time_ms:.2f}ms")
            self._log_debug("✓ Result generated successfully")
            self._log_debug("")
            
            # ═════════════════════════════════════════════════════════
            # DEBUG CYCLE 10: Performance Summary
            # ═════════════════════════════════════════════════════════
            self._log_debug("=" * 70)
            self._log_debug("DEBUG CYCLE 10: PERFORMANCE SUMMARY")
            self._log_debug("=" * 70)
            self._log_debug(f"Initial Capital: ${self._config.initial_capital:,.2f}")
            self._log_debug(f"Final Equity: ${self._equity:,.2f}")
            self._log_debug(f"Total Return: ${metrics.total_return:,.2f} ({metrics.total_return_pct:.2f}%)")
            self._log_debug(f"Benchmark Return: {benchmark_return_pct:.2f}%")
            self._log_debug(f"Excess Return: {metrics.total_return_pct - benchmark_return_pct:.2f}%")
            self._log_debug(f"Sharpe Ratio: {metrics.sharpe_ratio:.3f}")
            self._log_debug(f"Max Drawdown: {metrics.max_drawdown_pct:.2f}%")
            self._log_debug(f"Win Rate: {metrics.win_rate:.2f}%")
            self._log_debug(f"Profit Factor: {metrics.profit_factor:.2f}")
            self._log_debug(f"Total Trades: {metrics.total_trades}")
            self._log_debug(f"Execution Time: {execution_time_ms:.2f}ms")
            self._log_debug("=" * 70)
            self._log_debug("✓ BACKTEST COMPLETED SUCCESSFULLY")
            self._log_debug("=" * 70)
            
            return result
            
        except Exception as e:
            # ═════════════════════════════════════════════════════════
            # DEBUG CYCLE 9: Error Handling
            # ═════════════════════════════════════════════════════════
            self._log_debug("=" * 70)
            self._log_debug("DEBUG CYCLE 9: ERROR HANDLING")
            self._log_debug("=" * 70)
            self._log_debug(f"ERROR: {type(e).__name__}: {e}")
            self._log_debug(f"Traceback:\n{traceback.format_exc()}")
            self._log_debug("=" * 70)
            
            # Return partial result with error info
            execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            result = BacktestResult(
                config=self._config,
                trades=self._trades,
                equity_curve=self._equity_curve,
                metrics=PerformanceMetrics(),
                orders=self._orders,
                positions=list(self._positions.values()),
                benchmark_return_pct=0.0,
                data_info={"error": str(e), "traceback": traceback.format_exc()},
                execution_time_ms=execution_time_ms,
                debug_log=self._debug_log
            )
            
            return result
    
    def _execute_order(self, order: Order, bar_data: Dict[str, Any]):
        """
        Execute an order
        
        Args:
            order: Order to execute
            bar_data: Current bar data
        """
        symbol = order.symbol
        current_price = bar_data['close']
        
        # Check trade direction
        if self._config.trade_direction == TradeDirection.LONG_ONLY and order.side == OrderSide.SELL:
            # Allow sell only to close long positions
            if symbol not in self._positions:
                order.status = "rejected"
                self._orders.append(order)
                return
        
        if self._config.trade_direction == TradeDirection.SHORT_ONLY and order.side == OrderSide.BUY:
            # Allow buy only to close short positions
            if symbol not in self._positions:
                order.status = "rejected"
                self._orders.append(order)
                return
        
        # Calculate execution price with slippage
        if order.side == OrderSide.BUY:
            exec_price = current_price * (1 + self._config.slippage)
        else:
            exec_price = current_price * (1 - self._config.slippage)
        
        # Calculate commission
        trade_value = exec_price * order.quantity
        commission = trade_value * self._config.commission
        
        # Execute based on order side
        if order.side == OrderSide.BUY:
            # Check if we have enough cash
            required_cash = trade_value + commission
            if required_cash > self._cash:
                # Adjust quantity to available cash
                max_quantity = int(self._cash / (exec_price * (1 + self._config.commission)))
                if max_quantity <= 0:
                    order.status = "rejected"
                    self._orders.append(order)
                    return
                order.quantity = max_quantity
                trade_value = exec_price * order.quantity
                commission = trade_value * self._config.commission
            
            # Open or add to position
            if symbol in self._positions:
                # Add to existing position
                pos = self._positions[symbol]
                total_quantity = pos.quantity + order.quantity
                avg_price = (pos.entry_price * pos.quantity + exec_price * order.quantity) / total_quantity
                pos.quantity = total_quantity
                pos.entry_price = avg_price
            else:
                # Open new position
                position = Position(
                    symbol=symbol,
                    side=PositionSide.LONG,
                    quantity=order.quantity,
                    entry_price=exec_price,
                    entry_time=order.timestamp
                )
                
                # Set stop loss / take profit
                if self._config.stop_loss_pct > 0:
                    position.stop_loss = exec_price * (1 - self._config.stop_loss_pct / 100)
                if self._config.take_profit_pct > 0:
                    position.take_profit = exec_price * (1 + self._config.take_profit_pct / 100)
                
                self._positions[symbol] = position
            
            # Deduct cash
            self._cash -= (trade_value + commission)
            
        else:  # SELL
            # Check if we have position
            if symbol not in self._positions:
                # Open short position
                position = Position(
                    symbol=symbol,
                    side=PositionSide.SHORT,
                    quantity=order.quantity,
                    entry_price=exec_price,
                    entry_time=order.timestamp
                )
                
                # Set stop loss / take profit for short
                if self._config.stop_loss_pct > 0:
                    position.stop_loss = exec_price * (1 + self._config.stop_loss_pct / 100)
                if self._config.take_profit_pct > 0:
                    position.take_profit = exec_price * (1 - self._config.take_profit_pct / 100)
                
                self._positions[symbol] = position
                
                # Add cash from short sale
                self._cash += (trade_value - commission)
            else:
                # Close existing position
                pos = self._positions[symbol]
                close_quantity = min(order.quantity, pos.quantity)
                
                # Calculate P&L
                if pos.side == PositionSide.LONG:
                    pnl = (exec_price - pos.entry_price) * close_quantity
                else:
                    pnl = (pos.entry_price - exec_price) * close_quantity
                
                # Create trade record
                trade = Trade(
                    symbol=symbol,
                    side=pos.side,
                    entry_price=pos.entry_price,
                    exit_price=exec_price,
                    quantity=close_quantity,
                    entry_time=pos.entry_time,
                    exit_time=order.timestamp,
                    pnl=pnl,
                    commission=commission
                )
                self._trades.append(trade)
                
                # Update position
                pos.quantity -= close_quantity
                if pos.quantity <= 0:
                    del self._positions[symbol]
                
                # Add cash from sale
                self._cash += (exec_price * close_quantity - commission)
        
        # Update order status
        order.status = "filled"
        order.filled_price = exec_price
        order.filled_quantity = order.quantity
        self._orders.append(order)
    
    def _update_positions(self, bar_data: Dict[str, Any]):
        """
        Update all positions with current prices
        
        Args:
            bar_data: Current bar data
        """
        current_price = bar_data['close']
        
        for symbol, pos in self._positions.items():
            pos.update_pnl(current_price)
    
    def _check_exit_orders(self, bar_data: Dict[str, Any]):
        """
        Check and execute stop loss / take profit orders
        
        Args:
            bar_data: Current bar data
        """
        symbols_to_close = []
        
        for symbol, pos in self._positions.items():
            current_price = bar_data['close']
            low = bar_data['low']
            high = bar_data['high']
            
            # Check stop loss
            if pos.stop_loss:
                if pos.side == PositionSide.LONG and low <= pos.stop_loss:
                    symbols_to_close.append((symbol, "stop_loss", pos.stop_loss))
                    continue
                elif pos.side == PositionSide.SHORT and high >= pos.stop_loss:
                    symbols_to_close.append((symbol, "stop_loss", pos.stop_loss))
                    continue
            
            # Check take profit
            if pos.take_profit:
                if pos.side == PositionSide.LONG and high >= pos.take_profit:
                    symbols_to_close.append((symbol, "take_profit", pos.take_profit))
                    continue
                elif pos.side == PositionSide.SHORT and low <= pos.take_profit:
                    symbols_to_close.append((symbol, "take_profit", pos.take_profit))
                    continue
        
        # Execute exit orders
        for symbol, reason, price in symbols_to_close:
            pos = self._positions[symbol]
            
            # Create exit order
            order = Order(
                symbol=symbol,
                side=OrderSide.SELL if pos.side == PositionSide.LONG else OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=pos.quantity,
                price=price,
                timestamp=bar_data.get('timestamp', datetime.now())
            )
            
            # Execute with exit price
            exec_price = price
            trade_value = exec_price * pos.quantity
            commission = trade_value * self._config.commission
            
            # Calculate P&L
            if pos.side == PositionSide.LONG:
                pnl = (exec_price - pos.entry_price) * pos.quantity
            else:
                pnl = (pos.entry_price - exec_price) * pos.quantity
            
            # Create trade record
            trade = Trade(
                symbol=symbol,
                side=pos.side,
                entry_price=pos.entry_price,
                exit_price=exec_price,
                quantity=pos.quantity,
                entry_time=pos.entry_time,
                exit_time=order.timestamp,
                pnl=pnl,
                commission=commission,
                exit_reason=reason
            )
            self._trades.append(trade)
            
            # Update cash
            self._cash += (trade_value - commission)
            
            # Remove position
            del self._positions[symbol]
            
            # Update order
            order.status = "filled"
            order.filled_price = exec_price
            order.filled_quantity = pos.quantity
            self._orders.append(order)
    
    def _update_equity_curve(self, bar_data: Dict[str, Any]):
        """
        Update equity curve with current state
        
        Args:
            bar_data: Current bar data
        """
        current_price = bar_data['close']
        timestamp = bar_data.get('timestamp', datetime.now())
        
        # Calculate position value
        position_value = 0.0
        for pos in self._positions.values():
            if pos.side == PositionSide.LONG:
                position_value += current_price * pos.quantity
            else:
                position_value += (2 * pos.entry_price - current_price) * pos.quantity
        
        # Calculate total equity
        self._equity = self._cash + position_value
        
        # Update peak
        if self._equity > self._peak_equity:
            self._peak_equity = self._equity
        
        # Calculate drawdown
        drawdown = self._peak_equity - self._equity
        drawdown_pct = (drawdown / self._peak_equity * 100) if self._peak_equity > 0 else 0
        
        # Add to equity curve
        equity_point = EquityPoint(
            timestamp=timestamp,
            equity=self._equity,
            cash=self._cash,
            position_value=position_value,
            drawdown=drawdown,
            drawdown_pct=drawdown_pct
        )
        self._equity_curve.append(equity_point)
    
    def _calculate_metrics(self) -> PerformanceMetrics:
        """
        Calculate comprehensive performance metrics
        
        Returns:
            PerformanceMetrics object
        """
        metrics = PerformanceMetrics()
        
        if not self._trades:
            return metrics
        
        # Basic metrics
        metrics.total_trades = len(self._trades)
        
        # Separate winning and losing trades
        winning_trades = [t for t in self._trades if t.pnl > 0]
        losing_trades = [t for t in self._trades if t.pnl <= 0]
        
        metrics.winning_trades = len(winning_trades)
        metrics.losing_trades = len(losing_trades)
        
        # Win rate
        metrics.win_rate = (metrics.winning_trades / metrics.total_trades * 100) if metrics.total_trades > 0 else 0
        
        # Total return
        metrics.total_return = self._equity - self._config.initial_capital
        metrics.total_return_pct = (metrics.total_return / self._config.initial_capital * 100) if self._config.initial_capital > 0 else 0
        
        # Annualized return
        if len(self._equity_curve) > 0:
            start_date = self._equity_curve[0].timestamp
            end_date = self._equity_curve[-1].timestamp
            days = (end_date - start_date).days if hasattr(end_date, 'days') else len(self._equity_curve)
            years = max(days / 365, 1/365)
            metrics.annualized_return_pct = ((self._equity / self._config.initial_capital) ** (1 / years) - 1) * 100
        
        # Max drawdown
        if self._equity_curve:
            metrics.max_drawdown = max(e.drawdown for e in self._equity_curve)
            metrics.max_drawdown_pct = max(e.drawdown_pct for e in self._equity_curve)
        
        # Average trade metrics
        if winning_trades:
            metrics.avg_winning_trade = np.mean([t.pnl_pct for t in winning_trades])
            metrics.largest_win = max(t.pnl for t in winning_trades)
        
        if losing_trades:
            metrics.avg_losing_trade = np.mean([t.pnl_pct for t in losing_trades])
            metrics.largest_loss = min(t.pnl for t in losing_trades)
        
        metrics.avg_trade_return = np.mean([t.pnl_pct for t in self._trades])
        
        # Profit factor
        gross_profit = sum(t.pnl for t in winning_trades)
        gross_loss = abs(sum(t.pnl for t in losing_trades))
        metrics.profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf') if gross_profit > 0 else 0
        
        # Sharpe ratio
        if len(self._trades) >= 2:
            returns = [t.pnl_pct / 100 for t in self._trades]
            avg_return = np.mean(returns)
            std_return = np.std(returns, ddof=1)
            
            if std_return > 0:
                # Annualize based on timeframe
                periods_per_year = {
                    TimeFrame.M1: 252 * 24 * 60,
                    TimeFrame.M5: 252 * 24 * 12,
                    TimeFrame.M15: 252 * 24 * 4,
                    TimeFrame.M30: 252 * 24 * 2,
                    TimeFrame.H1: 252 * 24,
                    TimeFrame.H4: 252 * 6,
                    TimeFrame.D1: 252
                }
                periods = periods_per_year.get(self._config.timeframe, 252)
                
                annualized_return = avg_return * periods
                annualized_vol = std_return * np.sqrt(periods)
                metrics.sharpe_ratio = annualized_return / annualized_vol if annualized_vol > 0 else 0
                
                # Volatility
                metrics.volatility_annualized = annualized_vol * 100
        
        # Sortino ratio (downside deviation)
        if len(self._trades) >= 2:
            returns = [t.pnl_pct / 100 for t in self._trades]
            negative_returns = [r for r in returns if r < 0]
            
            if negative_returns:
                downside_std = np.std(negative_returns, ddof=1)
                periods_per_year = {
                    TimeFrame.M1: 252 * 24 * 60,
                    TimeFrame.M5: 252 * 24 * 12,
                    TimeFrame.M15: 252 * 24 * 4,
                    TimeFrame.M30: 252 * 24 * 2,
                    TimeFrame.H1: 252 * 24,
                    TimeFrame.H4: 252 * 6,
                    TimeFrame.D1: 252
                }
                periods = periods_per_year.get(self._config.timeframe, 252)
                
                annualized_return = np.mean(returns) * periods
                downside_vol = downside_std * np.sqrt(periods)
                metrics.sortino_ratio = annualized_return / downside_vol if downside_vol > 0 else 0
        
        # Calmar ratio
        if metrics.max_drawdown_pct > 0:
            metrics.calmar_ratio = metrics.annualized_return_pct / metrics.max_drawdown_pct
        
        # Consecutive wins/losses
        if self._trades:
            max_consec_wins = 0
            max_consec_losses = 0
            current_wins = 0
            current_losses = 0
            
            for t in self._trades:
                if t.pnl > 0:
                    current_wins += 1
                    current_losses = 0
                    max_consec_wins = max(max_consec_wins, current_wins)
                else:
                    current_losses += 1
                    current_wins = 0
                    max_consec_losses = max(max_consec_losses, current_losses)
            
            metrics.max_consecutive_wins = max_consec_wins
            metrics.max_consecutive_losses = max_consec_losses
        
        # Average holding period
        if self._trades:
            holding_periods = []
            for t in self._trades:
                if t.entry_time and t.exit_time:
                    if hasattr(t.exit_time, 'timestamp') and hasattr(t.entry_time, 'timestamp'):
                        period = (t.exit_time - t.entry_time).total_seconds() / 3600  # hours
                        holding_periods.append(period)
            
            if holding_periods:
                metrics.avg_holding_period = np.mean(holding_periods)
        
        return metrics
