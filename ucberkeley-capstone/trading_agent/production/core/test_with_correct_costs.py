"""Test production engine with CORRECT costs (from diagnostics)"""

import pandas as pd
from backtest_engine import BacktestEngine

class SimpleStrategy:
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
        if day > 0 and day % 30 == 0 and inventory > 0:
            return {'action': 'SELL', 'amount': inventory * 0.25, 'reason': f'scheduled_day_{day}'}
        return {'action': 'HOLD', 'amount': 0, 'reason': 'waiting'}

# Test data
dates = pd.date_range('2022-01-01', periods=365, freq='D')
prices = pd.DataFrame({'date': dates, 'price': [7.5] * 365})
predictions = {}

# Coffee config with CORRECT costs
config = {
    'commodity': 'coffee',
    'harvest_volume': 50,
    'harvest_windows': [(5, 9)],
    'storage_cost_pct_per_day': 0.005,   # CORRECT: 0.005% (not 0.025%)
    'transaction_cost_pct': 0.01,        # CORRECT: 0.01% (not 0.25%)
    'min_inventory_to_trade': 1.0,
    'max_holding_days': 365
}

engine = BacktestEngine(prices, predictions, config)
strategy = SimpleStrategy("Test")
results = engine.run(strategy)

print("Production engine with CORRECT costs:")
print(f"Net earnings: ${results['net_earnings']:,.2f}")
print(f"Transaction costs: ${results['total_transaction_costs']:,.2f}")
print(f"Storage costs: ${results['total_storage_costs']:,.2f}")
print(f"\nFormula check:")
if len(results['trades']) > 0:
    t = results['trades'][0]
    expected_txn = t['amount'] * t['price_per_ton'] * (0.01 / 100)
    print(f"Transaction: {t['amount']:.2f} × ${t['price_per_ton']:.2f} × 0.0001 = ${expected_txn:.4f}")
    print(f"Actual: ${t['transaction_cost']:.4f}")
    print(f"Match: {abs(t['transaction_cost'] - expected_txn) < 0.01}")
