# Risk Manager Module

Comprehensive risk management system for position sizing and risk control.

## Features

### 1. Position Sizing

#### Fixed Fractional Method
Calculate position size based on risk percentage and stop loss distance:
```python
shares = risk_manager.calculate_position_size(
    capital=100000,
    risk_pct=2.0,
    entry_price=100.0,
    stop_price=92.0,
)
# Result: 200 shares (capped at 20% of capital)
```

#### Kelly Criterion
Calculate optimal position size using Kelly formula:
```python
kelly_pct = risk_manager.calculate_kelly_size(
    capital=100000,
    win_rate=0.60,
    win_loss_ratio=2.0,
)
# Result: 20% (uses half-Kelly for safety)
```

### 2. Stop Loss & Take Profit

#### Stop Loss
```python
position = Position(
    symbol="AAPL",
    entry_price=100.0,
    current_price=100.0,
    shares=100,
)
stop_price = risk_manager.set_stop_loss(position, stop_pct=8.0)
# Result: $92.0 (8% below entry)
```

#### Take Profit
```python
target_price = risk_manager.set_take_profit(position, profit_pct=15.0)
# Result: $115.0 (15% above entry)
```

### 3. Trailing Stop

Automatically adjusts stop loss as price moves up:
```python
# Trailing stop activates at 5% profit
result = risk_manager.update_position("AAPL", current_price=105.0)
# Trailing stop: $96.6 (8% below $105)

result = risk_manager.update_position("AAPL", current_price=110.0)
# Trailing stop: $101.2 (8% below $110)

result = risk_manager.update_position("AAPL", current_price=108.0)
# Trailing stop: $101.2 (doesn't move down)
```

### 4. Risk Checks

#### Stop Loss Trigger
```python
triggered = risk_manager.check_stop_triggered(position, current_price=91.0)
# Returns True if price <= stop_price
```

#### Profit Target Check
```python
reached = risk_manager.check_profit_target(position, current_price=116.0)
# Returns True if price >= target_price
```

### 5. Risk Adjustment

Adjust risk after consecutive losses:
```python
adjusted_risk = risk_manager.adjust_risk_after_loss(
    current_risk_pct=2.0,
    consecutive_losses=3,
)
# Result: 1.4% (30% reduction)
```

### 6. Risk Summary

Generate comprehensive portfolio risk summary:
```python
summary = risk_manager.get_risk_summary(
    positions=[position1, position2],
    capital=100000,
)
# Returns: total_value, risk_pct, risk_level, etc.
```

## Configuration

Default configuration (conservative):
```python
RiskConfig(
    max_risk_per_trade=2.0,      # 2% per trade
    max_portfolio_risk=6.0,       # 6% total portfolio
    default_stop_pct=8.0,         # 8% stop loss
    default_profit_pct=15.0,      # 15% take profit
    trailing_stop_enabled=True,   # Enable trailing
    trailing_activation_pct=5.0,  # Activate at 5% profit
    max_position_size_pct=20.0,   # Max 20% in single position
    min_trade_value=1000.0,       # Minimum $1000 trade
)
```

## Debug Logging (10 Cycles)

The module includes comprehensive debug logging for 10 key operations:

1. **Cycle 1**: Risk config validation
2. **Cycle 2**: Position size calculation
3. **Cycle 3**: Kelly criterion calculation
4. **Cycle 4**: Stop loss setting
5. **Cycle 5**: Take profit setting
6. **Cycle 6**: Trailing stop update
7. **Cycle 7**: Stop trigger check
8. **Cycle 8**: Profit target check
9. **Cycle 9**: Risk adjustment
10. **Cycle 10**: Risk summary

Enable debug logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Usage Example

```python
from app.services.risk_manager import RiskManager, RiskConfig

# Initialize with default config
risk_manager = RiskManager()

# Calculate position size
shares = risk_manager.calculate_position_size(
    capital=100000,
    risk_pct=2.0,
    entry_price=100.0,
    stop_price=92.0,
)

# Register position
position = risk_manager.register_position(
    symbol="AAPL",
    entry_price=100.0,
    shares=shares,
    stop_pct=8.0,
    profit_pct=15.0,
)

# Update with price changes
result = risk_manager.update_position("AAPL", current_price=105.0)

# Check if stop triggered
if result['stop_triggered']:
    print("Stop loss triggered!")

# Check if profit target reached
if result['profit_reached']:
    print("Profit target reached!")

# Get risk summary
summary = risk_manager.get_risk_summary(
    positions=[position],
    capital=100000,
)
print(f"Risk Level: {summary['risk_level']}")
```

## Testing

Run unit tests:
```bash
cd backend
python3 -m pytest tests/test_risk_manager.py -v
```

All 45 tests pass, covering:
- Configuration validation
- Position sizing (fixed fractional & Kelly)
- Stop loss and take profit
- Trailing stop functionality
- Risk checks and triggers
- Risk adjustment
- Risk summary
- Integration workflows

## Risk Management Best Practices

1. **Never risk more than 2% per trade**
2. **Maximum portfolio risk: 6%**
3. **Use trailing stops to lock in profits**
4. **Reduce risk after consecutive losses**
5. **Always use stop losses**
6. **Position size based on risk, not targets**

## Industry Standards

This module follows industry-standard risk management practices:
- Fixed fractional position sizing
- Kelly criterion (with safety adjustments)
- Trailing stop implementation
- Risk per trade limits
- Portfolio risk limits
- Risk adjustment after losses

## Files

- `backend/app/services/risk_manager.py` - Main module
- `backend/tests/test_risk_manager.py` - Unit tests
- `backend/scripts/demo_risk_manager.py` - Demonstration script
