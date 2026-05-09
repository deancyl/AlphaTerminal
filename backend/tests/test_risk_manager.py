"""
test_risk_manager.py — Unit tests for RiskManager module
Tests all risk management functionality including:
  - Position sizing (fixed fractional, Kelly criterion)
  - Stop loss and take profit management
  - Trailing stop implementation
  - Risk validation and controls
  - Debug logging (10 cycles)
"""
import pytest
import logging
from unittest.mock import Mock, patch
from app.services.risk_manager import (
    RiskManager,
    RiskConfig,
    Position,
)


class TestRiskConfig:
    """Test RiskConfig validation."""
    
    def test_default_config(self):
        """Test default configuration is valid."""
        config = RiskConfig()
        assert config.max_risk_per_trade == 2.0
        assert config.max_portfolio_risk == 6.0
        assert config.default_stop_pct == 8.0
        assert config.default_profit_pct == 15.0
        assert config.trailing_stop_enabled is True
        assert config.trailing_activation_pct == 5.0
        assert config.max_position_size_pct == 20.0
        assert config.min_trade_value == 1000.0
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = RiskConfig(
            max_risk_per_trade=3.0,
            max_portfolio_risk=10.0,
            default_stop_pct=10.0,
            default_profit_pct=20.0,
        )
        assert config.max_risk_per_trade == 3.0
        assert config.max_portfolio_risk == 10.0
        assert config.default_stop_pct == 10.0
        assert config.default_profit_pct == 20.0
    
    def test_invalid_max_risk_per_trade(self):
        """Test invalid max_risk_per_trade raises error."""
        with pytest.raises(ValueError, match="max_risk_per_trade"):
            RiskConfig(max_risk_per_trade=15.0)
        
        with pytest.raises(ValueError, match="max_risk_per_trade"):
            RiskConfig(max_risk_per_trade=0)
        
        with pytest.raises(ValueError, match="max_risk_per_trade"):
            RiskConfig(max_risk_per_trade=-1.0)
    
    def test_invalid_max_portfolio_risk(self):
        """Test invalid max_portfolio_risk raises error."""
        with pytest.raises(ValueError, match="max_portfolio_risk"):
            RiskConfig(max_portfolio_risk=25.0)
        
        with pytest.raises(ValueError, match="max_portfolio_risk"):
            RiskConfig(max_portfolio_risk=0)
    
    def test_invalid_stop_pct(self):
        """Test invalid default_stop_pct raises error."""
        with pytest.raises(ValueError, match="default_stop_pct"):
            RiskConfig(default_stop_pct=25.0)
        
        with pytest.raises(ValueError, match="default_stop_pct"):
            RiskConfig(default_stop_pct=0)


class TestPositionSizing:
    """Test position sizing calculations."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.risk_manager = RiskManager()
    
    def test_calculate_position_size_basic(self):
        """Test basic position size calculation."""
        # Risk $2000, entry $100, stop $92
        # Risk per share = $8
        # Position size = 2000 / 8 = 250 shares
        # But capped at 20% of capital = 200 shares
        shares = self.risk_manager.calculate_position_size(
            capital=100000,
            risk_pct=2.0,
            entry_price=100.0,
            stop_price=92.0,
        )
        assert shares == 200  # Capped at 20% of capital
    
    def test_calculate_position_size_with_default_risk(self):
        """Test position size with default risk percentage."""
        shares = self.risk_manager.calculate_position_size(
            capital=100000,
            entry_price=50.0,
            stop_price=46.0,
        )
        # Default risk: 2% of 100000 = 2000
        # Risk per share: 50 - 46 = 4
        # Position: 2000 / 4 = 500 shares
        # But capped at 20% of capital = 400 shares
        assert shares == 400  # Capped at 20% of capital
    
    def test_calculate_position_size_max_position_constraint(self):
        """Test position size is capped by max_position_size_pct."""
        # Large capital, small risk per share
        # Would calculate large position, but capped at 20%
        shares = self.risk_manager.calculate_position_size(
            capital=1000000,
            risk_pct=2.0,
            entry_price=100.0,
            stop_price=99.0,
        )
        # Risk: 20000, Risk per share: 1
        # Uncapped: 20000 shares
        # Max position: 20% of 1000000 / 100 = 2000 shares
        assert shares == 2000
    
    def test_calculate_position_size_invalid_capital(self):
        """Test invalid capital raises error."""
        with pytest.raises(ValueError, match="capital must be > 0"):
            self.risk_manager.calculate_position_size(
                capital=0,
                entry_price=100.0,
                stop_price=92.0,
            )
        
        with pytest.raises(ValueError, match="capital must be > 0"):
            self.risk_manager.calculate_position_size(
                capital=-100000,
                entry_price=100.0,
                stop_price=92.0,
            )
    
    def test_calculate_position_size_invalid_prices(self):
        """Test invalid prices raise errors."""
        with pytest.raises(ValueError, match="entry_price must be > 0"):
            self.risk_manager.calculate_position_size(
                capital=100000,
                entry_price=0,
                stop_price=92.0,
            )
        
        with pytest.raises(ValueError, match="stop_price must be > 0"):
            self.risk_manager.calculate_position_size(
                capital=100000,
                entry_price=100.0,
                stop_price=0,
            )
        
        with pytest.raises(ValueError, match="stop_price .* must be < entry_price"):
            self.risk_manager.calculate_position_size(
                capital=100000,
                entry_price=100.0,
                stop_price=105.0,
            )
    
    def test_calculate_kelly_size_basic(self):
        """Test Kelly criterion calculation."""
        # Win rate: 60%, Win/Loss ratio: 2.0
        # Kelly% = 0.60 - (1 - 0.60) / 2.0 = 0.60 - 0.20 = 0.40 = 40%
        # Half Kelly: 20%
        kelly_pct = self.risk_manager.calculate_kelly_size(
            capital=100000,
            win_rate=0.60,
            win_loss_ratio=2.0,
        )
        assert 19.0 <= kelly_pct <= 20.0  # Allow for rounding
    
    def test_calculate_kelly_size_negative_expectancy(self):
        """Test Kelly criterion with negative expectancy."""
        # Win rate: 40%, Win/Loss ratio: 1.0
        # Kelly% = 0.40 - (1 - 0.40) / 1.0 = 0.40 - 0.60 = -0.20 = -20%
        # Should return 0 (don't trade)
        kelly_pct = self.risk_manager.calculate_kelly_size(
            capital=100000,
            win_rate=0.40,
            win_loss_ratio=1.0,
        )
        assert kelly_pct == 0.0
    
    def test_calculate_kelly_size_max_cap(self):
        """Test Kelly criterion is capped at max_kelly_pct."""
        # Very high win rate and ratio
        # Kelly% = 0.80 - (1 - 0.80) / 3.0 = 0.80 - 0.067 = 0.733 = 73.3%
        # Half Kelly: 36.7%, but capped at 25%
        # But also capped at max_position_size_pct (20%)
        kelly_pct = self.risk_manager.calculate_kelly_size(
            capital=100000,
            win_rate=0.80,
            win_loss_ratio=3.0,
            max_kelly_pct=25.0,
        )
        assert kelly_pct == 20.0  # Capped at max_position_size_pct
    
    def test_calculate_kelly_size_invalid_inputs(self):
        """Test Kelly criterion with invalid inputs."""
        with pytest.raises(ValueError, match="win_rate must be in"):
            self.risk_manager.calculate_kelly_size(
                capital=100000,
                win_rate=1.5,
                win_loss_ratio=2.0,
            )
        
        with pytest.raises(ValueError, match="win_loss_ratio must be > 0"):
            self.risk_manager.calculate_kelly_size(
                capital=100000,
                win_rate=0.60,
                win_loss_ratio=0,
            )


class TestStopLossManagement:
    """Test stop loss and take profit management."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.risk_manager = RiskManager()
    
    def test_set_stop_loss_default(self):
        """Test stop loss with default percentage."""
        position = Position(
            symbol="AAPL",
            entry_price=100.0,
            current_price=100.0,
            shares=100,
        )
        stop_price = self.risk_manager.set_stop_loss(position)
        # Default: 8% below entry
        assert stop_price == 92.0
    
    def test_set_stop_loss_custom(self):
        """Test stop loss with custom percentage."""
        position = Position(
            symbol="AAPL",
            entry_price=100.0,
            current_price=100.0,
            shares=100,
        )
        stop_price = self.risk_manager.set_stop_loss(position, stop_pct=10.0)
        # 10% below entry
        assert stop_price == 90.0
    
    def test_set_stop_loss_invalid_pct(self):
        """Test stop loss with invalid percentage."""
        position = Position(
            symbol="AAPL",
            entry_price=100.0,
            current_price=100.0,
            shares=100,
        )
        with pytest.raises(ValueError, match="stop_pct must be in"):
            self.risk_manager.set_stop_loss(position, stop_pct=25.0)
    
    def test_set_take_profit_default(self):
        """Test take profit with default percentage."""
        position = Position(
            symbol="AAPL",
            entry_price=100.0,
            current_price=100.0,
            shares=100,
        )
        target_price = self.risk_manager.set_take_profit(position)
        # Default: 15% above entry
        assert target_price == 115.0
    
    def test_set_take_profit_custom(self):
        """Test take profit with custom percentage."""
        position = Position(
            symbol="AAPL",
            entry_price=100.0,
            current_price=100.0,
            shares=100,
        )
        target_price = self.risk_manager.set_take_profit(position, profit_pct=20.0)
        # 20% above entry
        assert target_price == 120.0


class TestTrailingStop:
    """Test trailing stop functionality."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.risk_manager = RiskManager()
    
    def test_trailing_stop_not_activated(self):
        """Test trailing stop not activated below threshold."""
        position = Position(
            symbol="AAPL",
            entry_price=100.0,
            current_price=103.0,
            shares=100,
        )
        # Profit: 3%, below activation threshold (5%)
        trailing_stop = self.risk_manager.update_trailing_stop(
            position, current_price=103.0, trail_pct=8.0
        )
        assert trailing_stop == 0.0
        assert not position.trailing_activated
    
    def test_trailing_stop_activation(self):
        """Test trailing stop activation at threshold."""
        position = Position(
            symbol="AAPL",
            entry_price=100.0,
            current_price=105.0,
            shares=100,
        )
        # Profit: 5%, at activation threshold
        trailing_stop = self.risk_manager.update_trailing_stop(
            position, current_price=105.0, trail_pct=8.0
        )
        # Should activate and set trailing stop at 105 * 0.92 = 96.6
        assert position.trailing_activated
        assert trailing_stop == 96.6
    
    def test_trailing_stop_moves_up(self):
        """Test trailing stop only moves up."""
        position = Position(
            symbol="AAPL",
            entry_price=100.0,
            current_price=110.0,
            shares=100,
            trailing_activated=True,
            highest_price=110.0,
            trailing_stop_price=101.2,  # 110 * 0.92
        )
        
        # Price drops to 108
        trailing_stop = self.risk_manager.update_trailing_stop(
            position, current_price=108.0, trail_pct=8.0
        )
        # Trailing stop should stay at 101.2 (doesn't move down)
        assert trailing_stop == 101.2
        
        # Price rises to 115
        trailing_stop = self.risk_manager.update_trailing_stop(
            position, current_price=115.0, trail_pct=8.0
        )
        # Trailing stop should move up to 115 * 0.92 = 105.8
        assert trailing_stop == 105.8
    
    def test_trailing_stop_disabled(self):
        """Test trailing stop when disabled in config."""
        config = RiskConfig(trailing_stop_enabled=False)
        risk_manager = RiskManager(config)
        
        position = Position(
            symbol="AAPL",
            entry_price=100.0,
            current_price=110.0,
            shares=100,
        )
        
        trailing_stop = risk_manager.update_trailing_stop(
            position, current_price=110.0, trail_pct=8.0
        )
        assert trailing_stop == 0.0


class TestRiskChecks:
    """Test risk trigger checks."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.risk_manager = RiskManager()
    
    def test_stop_loss_triggered(self):
        """Test stop loss trigger."""
        position = Position(
            symbol="AAPL",
            entry_price=100.0,
            current_price=91.0,
            shares=100,
            stop_price=92.0,
        )
        
        # Price below stop loss
        triggered = self.risk_manager.check_stop_triggered(position, current_price=91.0)
        assert triggered is True
    
    def test_stop_loss_not_triggered(self):
        """Test stop loss not triggered."""
        position = Position(
            symbol="AAPL",
            entry_price=100.0,
            current_price=95.0,
            shares=100,
            stop_price=92.0,
        )
        
        # Price above stop loss
        triggered = self.risk_manager.check_stop_triggered(position, current_price=95.0)
        assert triggered is False
    
    def test_trailing_stop_triggered(self):
        """Test trailing stop trigger."""
        position = Position(
            symbol="AAPL",
            entry_price=100.0,
            current_price=96.0,
            shares=100,
            stop_price=92.0,
            trailing_stop_price=97.0,
        )
        
        # Price below trailing stop (higher priority than regular stop)
        triggered = self.risk_manager.check_stop_triggered(position, current_price=96.0)
        assert triggered is True
    
    def test_profit_target_reached(self):
        """Test profit target check."""
        position = Position(
            symbol="AAPL",
            entry_price=100.0,
            current_price=116.0,
            shares=100,
            target_price=115.0,
        )
        
        # Price above target
        reached = self.risk_manager.check_profit_target(position, current_price=116.0)
        assert reached is True
    
    def test_profit_target_not_reached(self):
        """Test profit target not reached."""
        position = Position(
            symbol="AAPL",
            entry_price=100.0,
            current_price=110.0,
            shares=100,
            target_price=115.0,
        )
        
        # Price below target
        reached = self.risk_manager.check_profit_target(position, current_price=110.0)
        assert reached is False


class TestRiskAdjustment:
    """Test risk adjustment after losses."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.risk_manager = RiskManager()
    
    def test_no_adjustment_no_losses(self):
        """Test no adjustment with no consecutive losses."""
        adjusted = self.risk_manager.adjust_risk_after_loss(
            current_risk_pct=2.0,
            consecutive_losses=0,
        )
        assert adjusted == 2.0
    
    def test_adjustment_one_loss(self):
        """Test adjustment after one loss."""
        adjusted = self.risk_manager.adjust_risk_after_loss(
            current_risk_pct=2.0,
            consecutive_losses=1,
        )
        # 10% reduction: 2.0 * 0.9 = 1.8
        assert adjusted == 1.8
    
    def test_adjustment_multiple_losses(self):
        """Test adjustment after multiple losses."""
        adjusted = self.risk_manager.adjust_risk_after_loss(
            current_risk_pct=2.0,
            consecutive_losses=3,
        )
        # 30% reduction: 2.0 * 0.7 = 1.4
        assert adjusted == 1.4
    
    def test_adjustment_max_reduction(self):
        """Test adjustment capped at max reduction."""
        adjusted = self.risk_manager.adjust_risk_after_loss(
            current_risk_pct=2.0,
            consecutive_losses=10,
            max_reduction=50.0,
        )
        # 50% reduction: 2.0 * 0.5 = 1.0
        assert adjusted == 1.0
    
    def test_adjustment_minimum_floor(self):
        """Test adjustment doesn't go below minimum."""
        adjusted = self.risk_manager.adjust_risk_after_loss(
            current_risk_pct=1.0,
            consecutive_losses=10,
            max_reduction=90.0,
        )
        # Would be 0.1, but floored at 0.5
        assert adjusted == 0.5


class TestRiskSummary:
    """Test risk summary generation."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.risk_manager = RiskManager()
    
    def test_risk_summary_empty(self):
        """Test risk summary with no positions."""
        summary = self.risk_manager.get_risk_summary(
            positions=[],
            capital=100000,
        )
        assert summary["total_positions"] == 0
        assert summary["total_position_value"] == 0
        assert summary["risk_pct"] == 0
        assert summary["risk_level"] == "LOW"
    
    def test_risk_summary_single_position(self):
        """Test risk summary with single position."""
        position = Position(
            symbol="AAPL",
            entry_price=100.0,
            current_price=105.0,
            shares=100,
            stop_price=92.0,
            target_price=115.0,
        )
        
        summary = self.risk_manager.get_risk_summary(
            positions=[position],
            capital=100000,
        )
        
        assert summary["total_positions"] == 1
        assert summary["total_position_value"] == 10500  # 100 * 105
        assert summary["stops_active"] == 1
        assert summary["targets_set"] == 1
    
    def test_risk_summary_multiple_positions(self):
        """Test risk summary with multiple positions."""
        positions = [
            Position(
                symbol="AAPL",
                entry_price=100.0,
                current_price=105.0,
                shares=100,
                stop_price=92.0,
            ),
            Position(
                symbol="GOOGL",
                entry_price=150.0,
                current_price=155.0,
                shares=50,
                stop_price=138.0,
            ),
        ]
        
        summary = self.risk_manager.get_risk_summary(
            positions=positions,
            capital=100000,
        )
        
        assert summary["total_positions"] == 2
        assert summary["total_position_value"] == 18250  # 10500 + 7750
        assert summary["stops_active"] == 2
    
    def test_risk_summary_high_risk(self):
        """Test risk summary identifies high risk."""
        # Large position with wide stop
        position = Position(
            symbol="AAPL",
            entry_price=100.0,
            current_price=100.0,
            shares=1000,
            stop_price=80.0,  # 20% stop
        )
        
        summary = self.risk_manager.get_risk_summary(
            positions=[position],
            capital=100000,
        )
        
        # Risk: 1000 * (100 - 80) = 20000, which is 20% of capital
        assert summary["risk_level"] == "HIGH"


class TestPositionRegistration:
    """Test position registration and updates."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.risk_manager = RiskManager()
    
    def test_register_position(self):
        """Test position registration."""
        position = self.risk_manager.register_position(
            symbol="AAPL",
            entry_price=100.0,
            shares=100,
        )
        
        assert position.symbol == "AAPL"
        assert position.entry_price == 100.0
        assert position.shares == 100
        assert position.stop_price == 92.0  # Default 8% stop
        assert position.target_price == 115.0  # Default 15% profit
    
    def test_register_position_custom_params(self):
        """Test position registration with custom parameters."""
        position = self.risk_manager.register_position(
            symbol="AAPL",
            entry_price=100.0,
            shares=100,
            current_price=102.0,
            stop_pct=10.0,
            profit_pct=20.0,
        )
        
        assert position.current_price == 102.0
        assert position.stop_price == 90.0  # 10% stop
        assert position.target_price == 120.0  # 20% profit
    
    def test_update_position(self):
        """Test position update."""
        self.risk_manager.register_position(
            symbol="AAPL",
            entry_price=100.0,
            shares=100,
        )
        
        result = self.risk_manager.update_position(
            symbol="AAPL",
            current_price=105.0,
        )
        
        assert result["symbol"] == "AAPL"
        assert result["current_price"] == 105.0
        assert result["pnl"] == 500  # (105 - 100) * 100
        assert result["pnl_pct"] == 5.0
    
    def test_update_position_stop_triggered(self):
        """Test position update detects stop trigger."""
        self.risk_manager.register_position(
            symbol="AAPL",
            entry_price=100.0,
            shares=100,
        )
        
        result = self.risk_manager.update_position(
            symbol="AAPL",
            current_price=91.0,  # Below stop at 92
        )
        
        assert result["stop_triggered"] is True
    
    def test_update_position_profit_reached(self):
        """Test position update detects profit target."""
        self.risk_manager.register_position(
            symbol="AAPL",
            entry_price=100.0,
            shares=100,
        )
        
        result = self.risk_manager.update_position(
            symbol="AAPL",
            current_price=116.0,  # Above target at 115
        )
        
        assert result["profit_reached"] is True
    
    def test_update_nonexistent_position(self):
        """Test updating non-existent position raises error."""
        with pytest.raises(ValueError, match="Position .* not found"):
            self.risk_manager.update_position(
                symbol="NONEXISTENT",
                current_price=100.0,
            )


class TestIntegration:
    """Integration tests for complete risk management workflow."""
    
    def test_complete_workflow(self):
        """Test complete risk management workflow."""
        risk_manager = RiskManager()
        
        # 1. Calculate position size
        shares = risk_manager.calculate_position_size(
            capital=100000,
            risk_pct=2.0,
            entry_price=100.0,
            stop_price=92.0,
        )
        assert shares == 200  # Capped at 20% of capital
        
        # 2. Register position
        position = risk_manager.register_position(
            symbol="AAPL",
            entry_price=100.0,
            shares=shares,
            stop_pct=8.0,
            profit_pct=15.0,
        )
        
        # 3. Update with price increase
        result = risk_manager.update_position("AAPL", current_price=105.0)
        assert result["pnl"] == 1000  # 5 * 200
        assert not result["stop_triggered"]
        assert not result["profit_reached"]
        
        # 4. Update with trailing stop activation
        result = risk_manager.update_position("AAPL", current_price=110.0)
        assert position.trailing_activated
        
        # 5. Update with profit target reached
        result = risk_manager.update_position("AAPL", current_price=116.0)
        assert result["profit_reached"]
    
    def test_risk_adjustment_workflow(self):
        """Test risk adjustment after losses."""
        risk_manager = RiskManager()
        
        # Start with 2% risk
        current_risk = 2.0
        
        # After 2 consecutive losses
        current_risk = risk_manager.adjust_risk_after_loss(
            current_risk_pct=current_risk,
            consecutive_losses=2,
        )
        assert current_risk == 1.6  # 20% reduction
        
        # After 3 more consecutive losses (5 total)
        current_risk = risk_manager.adjust_risk_after_loss(
            current_risk_pct=current_risk,
            consecutive_losses=5,
        )
        assert current_risk == 0.8  # 50% reduction from original 1.6


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
