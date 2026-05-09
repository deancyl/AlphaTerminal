"""
risk_manager.py — Task 14: Risk Management Module
Provides comprehensive risk management for position sizing and risk control.

Features:
  - Position sizing (fixed fractional, Kelly criterion)
  - Stop loss and take profit management
  - Trailing stop implementation
  - Risk validation and controls
  - Comprehensive debug logging (10 cycles)
"""
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
import math

logger = logging.getLogger(__name__)


# ── Risk Configuration ──────────────────────────────────────────────────────
@dataclass
class RiskConfig:
    """
    Risk management configuration with conservative defaults.
    
    Attributes:
        max_risk_per_trade: Maximum risk per trade as percentage (default: 2%)
        max_portfolio_risk: Maximum portfolio risk as percentage (default: 6%)
        default_stop_pct: Default stop loss percentage (default: 8%)
        default_profit_pct: Default take profit percentage (default: 15%)
        trailing_stop_enabled: Enable trailing stop (default: True)
        trailing_activation_pct: Activation threshold for trailing stop (default: 5%)
        max_position_size_pct: Maximum position size as % of portfolio (default: 20%)
        min_trade_value: Minimum trade value in currency (default: 1000)
    """
    max_risk_per_trade: float = 2.0  # 2% per trade
    max_portfolio_risk: float = 6.0   # 6% total portfolio risk
    default_stop_pct: float = 8.0     # 8% stop loss
    default_profit_pct: float = 15.0  # 15% take profit
    trailing_stop_enabled: bool = True
    trailing_activation_pct: float = 5.0  # Activate after 5% profit
    max_position_size_pct: float = 20.0   # Max 20% in single position
    min_trade_value: float = 1000.0
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate_config()
    
    def _validate_config(self):
        """Validate all risk parameters."""
        # Cycle 1: Risk config validation
        logger.debug("=" * 60)
        logger.debug("[Cycle 1: Risk Config Validation]")
        logger.debug(f"  max_risk_per_trade: {self.max_risk_per_trade}%")
        logger.debug(f"  max_portfolio_risk: {self.max_portfolio_risk}%")
        logger.debug(f"  default_stop_pct: {self.default_stop_pct}%")
        logger.debug(f"  default_profit_pct: {self.default_profit_pct}%")
        logger.debug(f"  trailing_stop_enabled: {self.trailing_stop_enabled}")
        logger.debug(f"  trailing_activation_pct: {self.trailing_activation_pct}%")
        logger.debug(f"  max_position_size_pct: {self.max_position_size_pct}%")
        logger.debug(f"  min_trade_value: {self.min_trade_value}")
        
        errors = []
        
        if self.max_risk_per_trade <= 0 or self.max_risk_per_trade > 10:
            errors.append(f"max_risk_per_trade must be in (0, 10], got {self.max_risk_per_trade}")
        
        if self.max_portfolio_risk <= 0 or self.max_portfolio_risk > 20:
            errors.append(f"max_portfolio_risk must be in (0, 20], got {self.max_portfolio_risk}")
        
        if self.default_stop_pct <= 0 or self.default_stop_pct > 20:
            errors.append(f"default_stop_pct must be in (0, 20], got {self.default_stop_pct}")
        
        if self.default_profit_pct <= 0:
            errors.append(f"default_profit_pct must be > 0, got {self.default_profit_pct}")
        
        if self.trailing_activation_pct <= 0:
            errors.append(f"trailing_activation_pct must be > 0, got {self.trailing_activation_pct}")
        
        if self.max_position_size_pct <= 0 or self.max_position_size_pct > 100:
            errors.append(f"max_position_size_pct must be in (0, 100], got {self.max_position_size_pct}")
        
        if self.min_trade_value <= 0:
            errors.append(f"min_trade_value must be > 0, got {self.min_trade_value}")
        
        if errors:
            logger.error(f"  [VALIDATION FAILED] {len(errors)} errors:")
            for err in errors:
                logger.error(f"    - {err}")
            raise ValueError(f"Invalid risk configuration: {'; '.join(errors)}")
        
        logger.debug(f"  [VALIDATION PASSED] All parameters within acceptable ranges")
        logger.debug("=" * 60)


# ── Position Data Structure ────────────────────────────────────────────────
@dataclass
class Position:
    """
    Position data structure for risk management.
    
    Attributes:
        symbol: Trading symbol
        entry_price: Entry price
        current_price: Current market price
        shares: Number of shares
        stop_price: Stop loss price
        target_price: Take profit target price
        trailing_stop_price: Current trailing stop price
        trailing_activated: Whether trailing stop is activated
        highest_price: Highest price since entry (for trailing stop)
    """
    symbol: str
    entry_price: float
    current_price: float
    shares: int
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    trailing_stop_price: Optional[float] = None
    trailing_activated: bool = False
    highest_price: Optional[float] = None
    
    def __post_init__(self):
        """Initialize derived fields."""
        if self.highest_price is None:
            self.highest_price = self.entry_price


# ── Risk Manager ────────────────────────────────────────────────────────────
class RiskManager:
    """
    Comprehensive risk management system for position sizing and risk control.
    
    Features:
        - Position sizing using fixed fractional or Kelly criterion
        - Stop loss and take profit management
        - Trailing stop implementation
        - Risk validation and controls
    """
    
    def __init__(self, config: Optional[RiskConfig] = None):
        """Initialize risk manager with configuration."""
        self.config = config or RiskConfig()
        self.positions: Dict[str, Position] = {}
        self.risk_history: List[Dict[str, Any]] = []
        
        logger.info(f"[RiskManager] Initialized with config:")
        logger.info(f"  max_risk_per_trade: {self.config.max_risk_per_trade}%")
        logger.info(f"  max_portfolio_risk: {self.config.max_portfolio_risk}%")
    
    # ── Position Sizing ────────────────────────────────────────────────────
    
    def calculate_position_size(
        self,
        capital: float,
        risk_pct: Optional[float] = None,
        entry_price: float = 0,
        stop_price: float = 0,
    ) -> float:
        """
        Calculate position size using fixed fractional method.
        
        Formula: Position Size = (Capital × Risk%) / (Entry Price - Stop Price)
        
        Args:
            capital: Total capital available
            risk_pct: Risk percentage (uses config default if None)
            entry_price: Planned entry price
            stop_price: Planned stop loss price
            
        Returns:
            Number of shares to trade
            
        Raises:
            ValueError: If parameters are invalid
        """
        # Cycle 2: Position size calculation
        logger.debug("=" * 60)
        logger.debug("[Cycle 2: Position Size Calculation]")
        logger.debug(f"  capital: {capital}")
        logger.debug(f"  risk_pct: {risk_pct} (default: {self.config.max_risk_per_trade}%)")
        logger.debug(f"  entry_price: {entry_price}")
        logger.debug(f"  stop_price: {stop_price}")
        
        # Validate inputs
        if capital <= 0:
            logger.error(f"  [ERROR] capital must be > 0, got {capital}")
            raise ValueError(f"capital must be > 0, got {capital}")
        
        if entry_price <= 0:
            logger.error(f"  [ERROR] entry_price must be > 0, got {entry_price}")
            raise ValueError(f"entry_price must be > 0, got {entry_price}")
        
        if stop_price <= 0:
            logger.error(f"  [ERROR] stop_price must be > 0, got {stop_price}")
            raise ValueError(f"stop_price must be > 0, got {stop_price}")
        
        if stop_price >= entry_price:
            logger.error(f"  [ERROR] stop_price ({stop_price}) must be < entry_price ({entry_price})")
            raise ValueError(f"stop_price ({stop_price}) must be < entry_price ({entry_price})")
        
        # Use default risk if not specified
        risk_pct = risk_pct or self.config.max_risk_per_trade
        
        if risk_pct <= 0 or risk_pct > self.config.max_risk_per_trade:
            logger.error(f"  [ERROR] risk_pct must be in (0, {self.config.max_risk_per_trade}], got {risk_pct}")
            raise ValueError(f"risk_pct must be in (0, {self.config.max_risk_per_trade}], got {risk_pct}")
        
        # Calculate position size
        risk_amount = capital * (risk_pct / 100)
        risk_per_share = entry_price - stop_price
        
        logger.debug(f"  risk_amount: {risk_amount:.2f}")
        logger.debug(f"  risk_per_share: {risk_per_share:.2f}")
        
        shares = risk_amount / risk_per_share
        
        # Apply maximum position size constraint
        max_position_value = capital * (self.config.max_position_size_pct / 100)
        max_shares = max_position_value / entry_price
        
        if shares > max_shares:
            logger.debug(f"  [ADJUSTED] Position size capped from {shares:.0f} to {max_shares:.0f} shares")
            shares = max_shares
        
        # Round down to whole shares
        shares = math.floor(shares)
        
        # Validate minimum trade value
        trade_value = shares * entry_price
        if trade_value < self.config.min_trade_value:
            logger.warning(f"  [WARNING] Trade value {trade_value:.2f} below minimum {self.config.min_trade_value}")
        
        logger.debug(f"  [RESULT] Position size: {shares} shares")
        logger.debug(f"  [RESULT] Trade value: {shares * entry_price:.2f}")
        logger.debug("=" * 60)
        
        return shares
    
    def calculate_kelly_size(
        self,
        capital: float,
        win_rate: float,
        win_loss_ratio: float,
        max_kelly_pct: float = 25.0,
    ) -> float:
        """
        Calculate position size using Kelly Criterion.
        
        Formula: Kelly% = W - (1-W)/R
        Where:
            W = Win rate (probability of winning)
            R = Win/Loss ratio (average win / average loss)
        
        Args:
            capital: Total capital available
            win_rate: Historical win rate (0.0 to 1.0)
            win_loss_ratio: Average win divided by average loss
            max_kelly_pct: Maximum Kelly percentage (default: 25% for safety)
            
        Returns:
            Position size as percentage of capital
            
        Raises:
            ValueError: If parameters are invalid
        """
        # Cycle 3: Kelly criterion calculation
        logger.debug("=" * 60)
        logger.debug("[Cycle 3: Kelly Criterion Calculation]")
        logger.debug(f"  capital: {capital}")
        logger.debug(f"  win_rate: {win_rate}")
        logger.debug(f"  win_loss_ratio: {win_loss_ratio}")
        logger.debug(f"  max_kelly_pct: {max_kelly_pct}%")
        
        # Validate inputs
        if capital <= 0:
            logger.error(f"  [ERROR] capital must be > 0, got {capital}")
            raise ValueError(f"capital must be > 0, got {capital}")
        
        if win_rate < 0 or win_rate > 1:
            logger.error(f"  [ERROR] win_rate must be in [0, 1], got {win_rate}")
            raise ValueError(f"win_rate must be in [0, 1], got {win_rate}")
        
        if win_loss_ratio <= 0:
            logger.error(f"  [ERROR] win_loss_ratio must be > 0, got {win_loss_ratio}")
            raise ValueError(f"win_loss_ratio must be > 0, got {win_loss_ratio}")
        
        # Calculate Kelly percentage
        # Kelly% = W - (1-W)/R
        kelly_pct = (win_rate - (1 - win_rate) / win_loss_ratio) * 100
        
        logger.debug(f"  [RAW KELLY] {kelly_pct:.2f}%")
        
        # Kelly can be negative (don't trade)
        if kelly_pct < 0:
            logger.warning(f"  [WARNING] Negative Kelly ({kelly_pct:.2f}%) - strategy has negative expectancy")
            logger.debug(f"  [RESULT] Position size: 0% (don't trade)")
            logger.debug("=" * 60)
            return 0.0
        
        # Apply safety cap (use fractional Kelly for risk reduction)
        # Most traders use half-Kelly for safety
        safe_kelly = min(kelly_pct * 0.5, max_kelly_pct)
        
        logger.debug(f"  [HALF KELLY] {kelly_pct * 0.5:.2f}%")
        logger.debug(f"  [CAPPED KELLY] {safe_kelly:.2f}%")
        
        # Ensure it doesn't exceed max position size
        if safe_kelly > self.config.max_position_size_pct:
            safe_kelly = self.config.max_position_size_pct
            logger.debug(f"  [ADJUSTED] Capped to max_position_size_pct: {safe_kelly:.2f}%")
        
        logger.debug(f"  [RESULT] Position size: {safe_kelly:.2f}% of capital")
        logger.debug(f"  [RESULT] Position value: {capital * safe_kelly / 100:.2f}")
        logger.debug("=" * 60)
        
        return safe_kelly
    
    # ── Stop Loss Management ───────────────────────────────────────────────
    
    def set_stop_loss(
        self,
        position: Position,
        stop_pct: Optional[float] = None,
    ) -> float:
        """
        Set stop loss price for a position.
        
        Args:
            position: Position to set stop loss for
            stop_pct: Stop loss percentage (uses config default if None)
            
        Returns:
            Stop loss price
            
        Raises:
            ValueError: If parameters are invalid
        """
        # Cycle 4: Stop loss setting
        logger.debug("=" * 60)
        logger.debug("[Cycle 4: Stop Loss Setting]")
        logger.debug(f"  symbol: {position.symbol}")
        logger.debug(f"  entry_price: {position.entry_price}")
        logger.debug(f"  stop_pct: {stop_pct} (default: {self.config.default_stop_pct}%)")
        
        # Use default if not specified
        stop_pct = stop_pct or self.config.default_stop_pct
        
        if stop_pct <= 0 or stop_pct > 20:
            logger.error(f"  [ERROR] stop_pct must be in (0, 20], got {stop_pct}")
            raise ValueError(f"stop_pct must be in (0, 20], got {stop_pct}")
        
        if position.entry_price <= 0:
            logger.error(f"  [ERROR] entry_price must be > 0, got {position.entry_price}")
            raise ValueError(f"entry_price must be > 0, got {position.entry_price}")
        
        # Calculate stop price
        stop_price = position.entry_price * (1 - stop_pct / 100)
        
        # Round to 2 decimal places
        stop_price = round(stop_price, 2)
        
        logger.debug(f"  [CALCULATION] {position.entry_price} × (1 - {stop_pct}/100)")
        logger.debug(f"  [RESULT] Stop loss price: {stop_price}")
        logger.debug(f"  [RESULT] Stop loss amount: {position.entry_price - stop_price:.2f}")
        logger.debug("=" * 60)
        
        return stop_price
    
    def set_take_profit(
        self,
        position: Position,
        profit_pct: Optional[float] = None,
    ) -> float:
        """
        Set take profit target price for a position.
        
        Args:
            position: Position to set take profit for
            profit_pct: Take profit percentage (uses config default if None)
            
        Returns:
            Take profit target price
            
        Raises:
            ValueError: If parameters are invalid
        """
        # Cycle 5: Take profit setting
        logger.debug("=" * 60)
        logger.debug("[Cycle 5: Take Profit Setting]")
        logger.debug(f"  symbol: {position.symbol}")
        logger.debug(f"  entry_price: {position.entry_price}")
        logger.debug(f"  profit_pct: {profit_pct} (default: {self.config.default_profit_pct}%)")
        
        # Use default if not specified
        profit_pct = profit_pct or self.config.default_profit_pct
        
        if profit_pct <= 0:
            logger.error(f"  [ERROR] profit_pct must be > 0, got {profit_pct}")
            raise ValueError(f"profit_pct must be > 0, got {profit_pct}")
        
        if position.entry_price <= 0:
            logger.error(f"  [ERROR] entry_price must be > 0, got {position.entry_price}")
            raise ValueError(f"entry_price must be > 0, got {position.entry_price}")
        
        # Calculate target price
        target_price = position.entry_price * (1 + profit_pct / 100)
        
        # Round to 2 decimal places
        target_price = round(target_price, 2)
        
        logger.debug(f"  [CALCULATION] {position.entry_price} × (1 + {profit_pct}/100)")
        logger.debug(f"  [RESULT] Take profit price: {target_price}")
        logger.debug(f"  [RESULT] Profit amount: {target_price - position.entry_price:.2f}")
        logger.debug("=" * 60)
        
        return target_price
    
    # ── Trailing Stop Management ───────────────────────────────────────────
    
    def update_trailing_stop(
        self,
        position: Position,
        current_price: float,
        trail_pct: float = 8.0,
    ) -> float:
        """
        Update trailing stop price based on current price.
        
        Logic:
            1. Check if trailing stop is activated (profit >= activation threshold)
            2. Update highest price if current price is higher
            3. Calculate new trailing stop from highest price
            4. Only move trailing stop UP, never down
        
        Args:
            position: Position to update trailing stop for
            current_price: Current market price
            trail_pct: Trailing stop percentage (default: 8%)
            
        Returns:
            Updated trailing stop price
            
        Raises:
            ValueError: If parameters are invalid
        """
        # Cycle 6: Trailing stop update
        logger.debug("=" * 60)
        logger.debug("[Cycle 6: Trailing Stop Update]")
        logger.debug(f"  symbol: {position.symbol}")
        logger.debug(f"  entry_price: {position.entry_price}")
        logger.debug(f"  current_price: {current_price}")
        logger.debug(f"  trail_pct: {trail_pct}%")
        logger.debug(f"  trailing_activated: {position.trailing_activated}")
        logger.debug(f"  highest_price: {position.highest_price}")
        logger.debug(f"  current_trailing_stop: {position.trailing_stop_price}")
        
        if not self.config.trailing_stop_enabled:
            logger.debug(f"  [SKIPPED] Trailing stop disabled in config")
            logger.debug("=" * 60)
            return position.trailing_stop_price or 0.0
        
        if current_price <= 0:
            logger.error(f"  [ERROR] current_price must be > 0, got {current_price}")
            raise ValueError(f"current_price must be > 0, got {current_price}")
        
        if trail_pct <= 0 or trail_pct > 20:
            logger.error(f"  [ERROR] trail_pct must be in (0, 20], got {trail_pct}")
            raise ValueError(f"trail_pct must be in (0, 20], got {trail_pct}")
        
        # Check activation threshold
        profit_pct = (current_price - position.entry_price) / position.entry_price * 100
        logger.debug(f"  [PROFIT] Current profit: {profit_pct:.2f}%")
        
        if not position.trailing_activated:
            if profit_pct >= self.config.trailing_activation_pct:
                position.trailing_activated = True
                logger.debug(f"  [ACTIVATED] Profit {profit_pct:.2f}% >= activation threshold {self.config.trailing_activation_pct}%")
            else:
                logger.debug(f"  [NOT ACTIVATED] Profit {profit_pct:.2f}% < activation threshold {self.config.trailing_activation_pct}%")
                logger.debug("=" * 60)
                return position.trailing_stop_price or 0.0
        
        # Update highest price
        if position.highest_price is None:
            position.highest_price = position.entry_price
        
        if current_price > position.highest_price:
            logger.debug(f"  [NEW HIGH] {position.highest_price} → {current_price}")
            position.highest_price = current_price
        
        # Calculate new trailing stop from highest price
        new_trailing_stop = position.highest_price * (1 - trail_pct / 100)
        new_trailing_stop = round(new_trailing_stop, 2)
        
        # Only move trailing stop UP, never down
        if position.trailing_stop_price is None or new_trailing_stop > position.trailing_stop_price:
            logger.debug(f"  [UPDATED] Trailing stop: {position.trailing_stop_price} → {new_trailing_stop}")
            position.trailing_stop_price = new_trailing_stop
        else:
            logger.debug(f"  [HELD] Trailing stop remains at {position.trailing_stop_price} (new: {new_trailing_stop})")
        
        logger.debug(f"  [RESULT] Trailing stop price: {position.trailing_stop_price}")
        logger.debug("=" * 60)
        
        return position.trailing_stop_price
    
    # ── Risk Checks ─────────────────────────────────────────────────────────
    
    def check_stop_triggered(
        self,
        position: Position,
        current_price: float,
    ) -> bool:
        """
        Check if stop loss or trailing stop is triggered.
        
        Args:
            position: Position to check
            current_price: Current market price
            
        Returns:
            True if stop is triggered, False otherwise
        """
        # Cycle 7: Stop trigger check
        logger.debug("=" * 60)
        logger.debug("[Cycle 7: Stop Trigger Check]")
        logger.debug(f"  symbol: {position.symbol}")
        logger.debug(f"  current_price: {current_price}")
        logger.debug(f"  stop_price: {position.stop_price}")
        logger.debug(f"  trailing_stop_price: {position.trailing_stop_price}")
        
        if current_price <= 0:
            logger.error(f"  [ERROR] current_price must be > 0, got {current_price}")
            raise ValueError(f"current_price must be > 0, got {current_price}")
        
        triggered = False
        trigger_type = None
        trigger_price = None
        
        # Check trailing stop first (higher priority)
        if position.trailing_stop_price and position.trailing_stop_price > 0:
            if current_price <= position.trailing_stop_price:
                triggered = True
                trigger_type = "trailing_stop"
                trigger_price = position.trailing_stop_price
                logger.debug(f"  [TRIGGERED] Trailing stop hit: {current_price} <= {position.trailing_stop_price}")
        
        # Check regular stop loss
        if not triggered and position.stop_price and position.stop_price > 0:
            if current_price <= position.stop_price:
                triggered = True
                trigger_type = "stop_loss"
                trigger_price = position.stop_price
                logger.debug(f"  [TRIGGERED] Stop loss hit: {current_price} <= {position.stop_price}")
        
        if triggered:
            loss_pct = (position.entry_price - current_price) / position.entry_price * 100
            logger.debug(f"  [RESULT] STOP TRIGGERED")
            logger.debug(f"  [RESULT] Type: {trigger_type}")
            logger.debug(f"  [RESULT] Trigger price: {trigger_price}")
            logger.debug(f"  [RESULT] Loss: {loss_pct:.2f}%")
        else:
            logger.debug(f"  [RESULT] No stop triggered")
        
        logger.debug("=" * 60)
        
        return triggered
    
    def check_profit_target(
        self,
        position: Position,
        current_price: float,
    ) -> bool:
        """
        Check if take profit target is reached.
        
        Args:
            position: Position to check
            current_price: Current market price
            
        Returns:
            True if profit target is reached, False otherwise
        """
        # Cycle 8: Profit target check
        logger.debug("=" * 60)
        logger.debug("[Cycle 8: Profit Target Check]")
        logger.debug(f"  symbol: {position.symbol}")
        logger.debug(f"  current_price: {current_price}")
        logger.debug(f"  target_price: {position.target_price}")
        
        if current_price <= 0:
            logger.error(f"  [ERROR] current_price must be > 0, got {current_price}")
            raise ValueError(f"current_price must be > 0, got {current_price}")
        
        if not position.target_price or position.target_price <= 0:
            logger.debug(f"  [SKIPPED] No target price set")
            logger.debug("=" * 60)
            return False
        
        triggered = current_price >= position.target_price
        
        if triggered:
            profit_pct = (current_price - position.entry_price) / position.entry_price * 100
            logger.debug(f"  [TRIGGERED] Profit target reached: {current_price} >= {position.target_price}")
            logger.debug(f"  [RESULT] Profit: {profit_pct:.2f}%")
        else:
            distance_pct = (position.target_price - current_price) / current_price * 100
            logger.debug(f"  [NOT TRIGGERED] Distance to target: {distance_pct:.2f}%")
        
        logger.debug("=" * 60)
        
        return triggered
    
    # ── Risk Adjustment ─────────────────────────────────────────────────────
    
    def adjust_risk_after_loss(
        self,
        current_risk_pct: float,
        consecutive_losses: int,
        max_reduction: float = 50.0,
    ) -> float:
        """
        Adjust risk percentage after consecutive losses.
        
        Strategy: Reduce risk by 10% for each consecutive loss, up to max_reduction.
        
        Args:
            current_risk_pct: Current risk percentage
            consecutive_losses: Number of consecutive losses
            max_reduction: Maximum reduction percentage (default: 50%)
            
        Returns:
            Adjusted risk percentage
        """
        # Cycle 9: Risk adjustment
        logger.debug("=" * 60)
        logger.debug("[Cycle 9: Risk Adjustment]")
        logger.debug(f"  current_risk_pct: {current_risk_pct}%")
        logger.debug(f"  consecutive_losses: {consecutive_losses}")
        logger.debug(f"  max_reduction: {max_reduction}%")
        
        if consecutive_losses <= 0:
            logger.debug(f"  [NO CHANGE] No consecutive losses")
            logger.debug("=" * 60)
            return current_risk_pct
        
        # Calculate reduction
        reduction_pct = min(consecutive_losses * 10, max_reduction)
        adjusted_risk = current_risk_pct * (1 - reduction_pct / 100)
        
        # Ensure minimum risk
        min_risk = 0.5  # Minimum 0.5% risk
        if adjusted_risk < min_risk:
            adjusted_risk = min_risk
            logger.debug(f"  [FLOOR] Risk adjusted to minimum: {min_risk}%")
        
        logger.debug(f"  [REDUCTION] {reduction_pct}%")
        logger.debug(f"  [RESULT] Adjusted risk: {adjusted_risk:.2f}%")
        logger.debug("=" * 60)
        
        return adjusted_risk
    
    # ── Risk Summary ───────────────────────────────────────────────────────
    
    def get_risk_summary(
        self,
        positions: List[Position],
        capital: float,
    ) -> Dict[str, Any]:
        """
        Generate comprehensive risk summary for portfolio.
        
        Args:
            positions: List of positions
            capital: Total portfolio capital
            
        Returns:
            Risk summary dictionary
        """
        # Cycle 10: Risk summary
        logger.debug("=" * 60)
        logger.debug("[Cycle 10: Risk Summary]")
        logger.debug(f"  capital: {capital}")
        logger.debug(f"  positions: {len(positions)}")
        
        if capital <= 0:
            logger.error(f"  [ERROR] capital must be > 0, got {capital}")
            raise ValueError(f"capital must be > 0, got {capital}")
        
        # Calculate portfolio metrics
        total_position_value = sum(p.shares * p.current_price for p in positions)
        total_risk = 0.0
        stops_active = 0
        trailing_stops_active = 0
        targets_set = 0
        
        for pos in positions:
            # Calculate risk per position
            if pos.stop_price and pos.stop_price > 0:
                risk_per_share = pos.entry_price - pos.stop_price
                total_risk += pos.shares * risk_per_share
                stops_active += 1
            
            if pos.trailing_stop_price and pos.trailing_stop_price > 0:
                trailing_stops_active += 1
            
            if pos.target_price and pos.target_price > 0:
                targets_set += 1
        
        # Calculate percentages
        position_pct = (total_position_value / capital) * 100 if capital > 0 else 0
        risk_pct = (total_risk / capital) * 100 if capital > 0 else 0
        
        # Determine risk level
        if risk_pct <= self.config.max_risk_per_trade:
            risk_level = "LOW"
        elif risk_pct <= self.config.max_portfolio_risk:
            risk_level = "MEDIUM"
        else:
            risk_level = "HIGH"
        
        summary = {
            "capital": capital,
            "total_positions": len(positions),
            "total_position_value": round(total_position_value, 2),
            "position_pct": round(position_pct, 2),
            "total_risk": round(total_risk, 2),
            "risk_pct": round(risk_pct, 2),
            "risk_level": risk_level,
            "stops_active": stops_active,
            "trailing_stops_active": trailing_stops_active,
            "targets_set": targets_set,
            "config": {
                "max_risk_per_trade": self.config.max_risk_per_trade,
                "max_portfolio_risk": self.config.max_portfolio_risk,
                "max_position_size_pct": self.config.max_position_size_pct,
            },
            "timestamp": datetime.now().isoformat(),
        }
        
        logger.debug(f"  [SUMMARY]")
        logger.debug(f"    total_position_value: {summary['total_position_value']}")
        logger.debug(f"    position_pct: {summary['position_pct']}%")
        logger.debug(f"    total_risk: {summary['total_risk']}")
        logger.debug(f"    risk_pct: {summary['risk_pct']}%")
        logger.debug(f"    risk_level: {summary['risk_level']}")
        logger.debug(f"    stops_active: {summary['stops_active']}")
        logger.debug(f"    trailing_stops_active: {summary['trailing_stops_active']}")
        logger.debug(f"    targets_set: {summary['targets_set']}")
        logger.debug("=" * 60)
        
        return summary
    
    # ── Position Registration ───────────────────────────────────────────────
    
    def register_position(
        self,
        symbol: str,
        entry_price: float,
        shares: int,
        current_price: Optional[float] = None,
        stop_pct: Optional[float] = None,
        profit_pct: Optional[float] = None,
    ) -> Position:
        """
        Register a new position with risk management.
        
        Args:
            symbol: Trading symbol
            entry_price: Entry price
            shares: Number of shares
            current_price: Current market price (defaults to entry_price)
            stop_pct: Stop loss percentage (uses config default if None)
            profit_pct: Take profit percentage (uses config default if None)
            
        Returns:
            Registered Position object
        """
        current_price = current_price or entry_price
        
        position = Position(
            symbol=symbol,
            entry_price=entry_price,
            current_price=current_price,
            shares=shares,
        )
        
        # Set stop loss
        position.stop_price = self.set_stop_loss(position, stop_pct)
        
        # Set take profit
        position.target_price = self.set_take_profit(position, profit_pct)
        
        # Store position
        self.positions[symbol] = position
        
        logger.info(f"[RiskManager] Registered position: {symbol} {shares} shares @ {entry_price}")
        logger.info(f"  Stop loss: {position.stop_price}")
        logger.info(f"  Take profit: {position.target_price}")
        
        return position
    
    def update_position(
        self,
        symbol: str,
        current_price: float,
    ) -> Dict[str, Any]:
        """
        Update position with current price and check risk triggers.
        
        Args:
            symbol: Trading symbol
            current_price: Current market price
            
        Returns:
            Update result dictionary
        """
        if symbol not in self.positions:
            raise ValueError(f"Position {symbol} not found")
        
        position = self.positions[symbol]
        position.current_price = current_price
        
        # Update trailing stop
        self.update_trailing_stop(position, current_price)
        
        # Check triggers
        stop_triggered = self.check_stop_triggered(position, current_price)
        profit_reached = self.check_profit_target(position, current_price)
        
        # Calculate P&L
        pnl = (current_price - position.entry_price) * position.shares
        pnl_pct = (current_price - position.entry_price) / position.entry_price * 100
        
        result = {
            "symbol": symbol,
            "current_price": current_price,
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "stop_triggered": stop_triggered,
            "profit_reached": profit_reached,
            "stop_price": position.stop_price,
            "trailing_stop_price": position.trailing_stop_price,
            "target_price": position.target_price,
        }
        
        return result
