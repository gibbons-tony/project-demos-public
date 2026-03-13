"""
Quick validation test for production backtest engine
"""

import pandas as pd
import numpy as np
from backtest_engine import BacktestEngine, calculate_metrics


class SimpleStrategy:
    """Minimal strategy for testing"""
    def __init__(self, name="Test"):
        self.name = name
        self.harvest_start_day = 0

    def reset(self):
        self.harvest_start_day = 0

    def set_harvest_start(self, day):
        self.harvest_start_day = day

    def force_liquidate_before_new_harvest(self, inventory):
        return {'action': 'SELL', 'amount': inventory, 'reason': 'pre_harvest_liquidation'}

    def decide(self, day, inventory, current_price, price_history, predictions=None):
        # Sell 25% every 30 days
        if day > 0 and day % 30 == 0 and inventory > 0:
            return {'action': 'SELL', 'amount': inventory * 0.25, 'reason': f'scheduled_day_{day}'}
        return {'action': 'HOLD', 'amount': 0, 'reason': 'waiting'}


def test_production_engine():
    """Test production backtest engine with known inputs"""

    # Create test data: 365 days, constant price
    dates = pd.date_range('2022-01-01', periods=365, freq='D')
    prices = pd.DataFrame({
        'date': dates,
        'price': [7.5] * 365  # 7.5 cents/lb × 20 = $150/ton
    })

    # No predictions for this test
    predictions = {}

    # Coffee config (May-September harvest)
    config = {
        'commodity': 'coffee',
        'harvest_volume': 50,  # tons
        'harvest_windows': [(5, 9)],  # May-September
        'storage_cost_pct_per_day': 0.025,  # 0.025% per day
        'transaction_cost_pct': 0.25,  # 0.25% per transaction
        'min_inventory_to_trade': 1.0,
        'max_holding_days': 365
    }

    # Initialize engine
    engine = BacktestEngine(prices, predictions, config)

    # Run test strategy
    strategy = SimpleStrategy("Test")
    results = engine.run(strategy)

    # Validate results
    print("=" * 60)
    print("PRODUCTION BACKTEST ENGINE VALIDATION")
    print("=" * 60)

    print(f"\nStrategy: {results['strategy_name']}")
    print(f"Net earnings: ${results['net_earnings']:,.2f}")
    print(f"Total revenue: ${results['total_revenue']:,.2f}")
    print(f"Transaction costs: ${results['total_transaction_costs']:,.2f}")
    print(f"Storage costs: ${results['total_storage_costs']:,.2f}")
    print(f"Number of trades: {len(results['trades'])}")

    # Check trades
    if len(results['trades']) > 0:
        print(f"\nFirst trade:")
        first = results['trades'][0]
        print(f"  Day: {first['day']}, Amount: {first['amount']:.2f} tons")
        print(f"  Price: {first['price']:.2f} cents/lb = ${first['price_per_ton']:.2f}/ton")
        print(f"  Revenue: ${first['revenue']:,.2f}")
        print(f"  Transaction cost: ${first['transaction_cost']:.2f}")

    # Check daily state
    daily_state = results['daily_state']
    print(f"\nDaily state rows: {len(daily_state)}")

    # Check harvest accumulation
    harvest_days = daily_state[daily_state['is_harvest_window'] == True]
    print(f"Harvest days: {len(harvest_days)}")
    if len(harvest_days) > 0:
        total_harvested = harvest_days['harvest_added'].sum()
        print(f"Total inventory accumulated: {total_harvested:.2f} tons")
        print(f"Expected: {config['harvest_volume']:.2f} tons")

    # Validate formulas
    print("\n" + "=" * 60)
    print("FORMULA VALIDATION")
    print("=" * 60)

    if len(results['trades']) > 0:
        trade = results['trades'][0]
        price_cents_lb = trade['price']
        price_per_ton = price_cents_lb * 20

        print(f"\nPrice conversion:")
        print(f"  Input: {price_cents_lb:.2f} cents/lb")
        print(f"  Expected: {price_cents_lb} × 20 = ${price_per_ton:.2f}/ton")
        print(f"  Actual: ${trade['price_per_ton']:.2f}/ton")
        print(f"  ✓ Match: {abs(trade['price_per_ton'] - price_per_ton) < 0.01}")

        amount = trade['amount']
        expected_revenue = amount * price_per_ton
        print(f"\nRevenue calculation:")
        print(f"  Amount: {amount:.2f} tons")
        print(f"  Price: ${price_per_ton:.2f}/ton")
        print(f"  Expected: {amount:.2f} × ${price_per_ton:.2f} = ${expected_revenue:.2f}")
        print(f"  Actual: ${trade['revenue']:.2f}")
        print(f"  ✓ Match: {abs(trade['revenue'] - expected_revenue) < 0.01}")

        expected_txn_cost = amount * price_per_ton * (config['transaction_cost_pct'] / 100)
        print(f"\nTransaction cost:")
        print(f"  Formula: amount × price_per_ton × (pct / 100)")
        print(f"  Expected: {amount:.2f} × ${price_per_ton:.2f} × 0.0025 = ${expected_txn_cost:.2f}")
        print(f"  Actual: ${trade['transaction_cost']:.2f}")
        print(f"  ✓ Match: {abs(trade['transaction_cost'] - expected_txn_cost) < 0.01}")

    # Check storage costs
    if len(daily_state) > 0:
        day_with_inventory = daily_state[daily_state['inventory'] > 0].iloc[0]
        inventory = day_with_inventory['inventory']
        price = prices.loc[day_with_inventory['day'], 'price']
        price_per_ton = price * 20
        expected_storage = inventory * price_per_ton * (config['storage_cost_pct_per_day'] / 100)

        print(f"\nStorage cost (day {day_with_inventory['day']}):")
        print(f"  Inventory: {inventory:.2f} tons")
        print(f"  Price: ${price_per_ton:.2f}/ton")
        print(f"  Formula: inventory × price_per_ton × (pct / 100)")
        print(f"  Expected: {inventory:.2f} × ${price_per_ton:.2f} × 0.00025 = ${expected_storage:.4f}")
        print(f"  Actual: ${day_with_inventory['daily_storage_cost']:.4f}")
        print(f"  ✓ Match: {abs(day_with_inventory['daily_storage_cost'] - expected_storage) < 0.01}")

    print("\n" + "=" * 60)
    print("✓ Production backtest engine validation complete")
    print("=" * 60)

    return results


if __name__ == '__main__':
    results = test_production_engine()
