"""
demo_risk_manager.py — Demonstration of RiskManager functionality
Shows comprehensive usage of all risk management features with debug logging.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from app.services.risk_manager import RiskManager, RiskConfig, Position

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def main():
    print("\n" + "=" * 80)
    print("RISK MANAGER DEMONSTRATION")
    print("=" * 80)
    
    risk_manager = RiskManager()
    
    print("\n" + "-" * 80)
    print("1. POSITION SIZING (Fixed Fractional Method)")
    print("-" * 80)
    
    capital = 100000
    entry_price = 100.0
    stop_price = 92.0
    risk_pct = 2.0
    
    print(f"Capital: ${capital}")
    print(f"Entry Price: ${entry_price}")
    print(f"Stop Price: ${stop_price}")
    print(f"Risk Percentage: {risk_pct}%")
    
    shares = risk_manager.calculate_position_size(
        capital=capital,
        risk_pct=risk_pct,
        entry_price=entry_price,
        stop_price=stop_price,
    )
    
    print(f"\n✓ Recommended Position Size: {shares} shares")
    print(f"✓ Position Value: ${shares * entry_price}")
    print(f"✓ Risk Amount: ${capital * risk_pct / 100}")
    
    print("\n" + "-" * 80)
    print("2. POSITION SIZING (Kelly Criterion)")
    print("-" * 80)
    
    win_rate = 0.60
    win_loss_ratio = 2.0
    
    print(f"Win Rate: {win_rate * 100}%")
    print(f"Win/Loss Ratio: {win_loss_ratio}")
    
    kelly_pct = risk_manager.calculate_kelly_size(
        capital=capital,
        win_rate=win_rate,
        win_loss_ratio=win_loss_ratio,
    )
    
    print(f"\n✓ Kelly Percentage: {kelly_pct:.2f}%")
    print(f"✓ Position Value: ${capital * kelly_pct / 100:.2f}")
    
    print("\n" + "-" * 80)
    print("3. REGISTERING A POSITION")
    print("-" * 80)
    
    symbol = "AAPL"
    print(f"Symbol: {symbol}")
    print(f"Entry Price: ${entry_price}")
    print(f"Shares: {shares}")
    
    position = risk_manager.register_position(
        symbol=symbol,
        entry_price=entry_price,
        shares=shares,
        stop_pct=8.0,
        profit_pct=15.0,
    )
    
    print(f"\n✓ Stop Loss: ${position.stop_price}")
    print(f"✓ Take Profit: ${position.target_price}")
    
    print("\n" + "-" * 80)
    print("4. TRAILING STOP DEMONSTRATION")
    print("-" * 80)
    
    prices = [100.0, 103.0, 105.0, 110.0, 108.0, 115.0]
    
    print("Price progression:")
    for i, price in enumerate(prices, 1):
        print(f"  Day {i}: ${price}")
        result = risk_manager.update_position(symbol, current_price=price)
        
        if position.trailing_activated:
            print(f"    ✓ Trailing Stop: ${position.trailing_stop_price}")
            print(f"    ✓ Highest Price: ${position.highest_price}")
        
        print(f"    P&L: ${result['pnl']} ({result['pnl_pct']:.2f}%)")
        
        if result['stop_triggered']:
            print(f"    ⚠️  STOP TRIGGERED!")
        
        if result['profit_reached']:
            print(f"    🎯 PROFIT TARGET REACHED!")
    
    print("\n" + "-" * 80)
    print("5. RISK SUMMARY")
    print("-" * 80)
    
    summary = risk_manager.get_risk_summary(
        positions=[position],
        capital=capital,
    )
    
    print(f"Total Positions: {summary['total_positions']}")
    print(f"Position Value: ${summary['total_position_value']}")
    print(f"Position %: {summary['position_pct']}%")
    print(f"Total Risk: ${summary['total_risk']}")
    print(f"Risk %: {summary['risk_pct']}%")
    print(f"Risk Level: {summary['risk_level']}")
    print(f"Stops Active: {summary['stops_active']}")
    print(f"Trailing Stops Active: {summary['trailing_stops_active']}")
    print(f"Targets Set: {summary['targets_set']}")
    
    print("\n" + "-" * 80)
    print("6. RISK ADJUSTMENT AFTER LOSSES")
    print("-" * 80)
    
    current_risk = 2.0
    consecutive_losses = 3
    
    print(f"Current Risk: {current_risk}%")
    print(f"Consecutive Losses: {consecutive_losses}")
    
    adjusted_risk = risk_manager.adjust_risk_after_loss(
        current_risk_pct=current_risk,
        consecutive_losses=consecutive_losses,
    )
    
    print(f"\n✓ Adjusted Risk: {adjusted_risk:.2f}%")
    print(f"✓ Reduction: {(current_risk - adjusted_risk) / current_risk * 100:.1f}%")
    
    print("\n" + "-" * 80)
    print("7. MULTIPLE POSITIONS")
    print("-" * 80)
    
    risk_manager2 = RiskManager()
    
    positions_data = [
        ("AAPL", 100.0, 200),
        ("GOOGL", 150.0, 100),
        ("MSFT", 300.0, 50),
    ]
    
    for symbol, price, shares in positions_data:
        pos = risk_manager2.register_position(
            symbol=symbol,
            entry_price=price,
            shares=shares,
        )
        print(f"✓ {symbol}: {shares} shares @ ${price}")
        print(f"  Stop: ${pos.stop_price}, Target: ${pos.target_price}")
    
    summary2 = risk_manager2.get_risk_summary(
        positions=list(risk_manager2.positions.values()),
        capital=capital,
    )
    
    print(f"\nPortfolio Summary:")
    print(f"  Total Positions: {summary2['total_positions']}")
    print(f"  Total Value: ${summary2['total_position_value']}")
    print(f"  Risk Level: {summary2['risk_level']}")
    
    print("\n" + "=" * 80)
    print("DEMONSTRATION COMPLETE")
    print("=" * 80)
    print("\nAll 10 debug cycles executed:")
    print("  ✓ Cycle 1: Risk config validation")
    print("  ✓ Cycle 2: Position size calculation")
    print("  ✓ Cycle 3: Kelly criterion calculation")
    print("  ✓ Cycle 4: Stop loss setting")
    print("  ✓ Cycle 5: Take profit setting")
    print("  ✓ Cycle 6: Trailing stop update")
    print("  ✓ Cycle 7: Stop trigger check")
    print("  ✓ Cycle 8: Profit target check")
    print("  ✓ Cycle 9: Risk adjustment")
    print("  ✓ Cycle 10: Risk summary")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()