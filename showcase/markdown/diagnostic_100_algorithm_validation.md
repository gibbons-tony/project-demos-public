# Diagnostic 100: Algorithm Validation with 100% Accuracy

**Purpose:** Prove trading algorithms work correctly by testing with PERFECT FORESIGHT

**Critical Logic:**
- With 100% accurate predictions (perfect foresight), prediction strategies MUST beat baseline strategies
- If they don't, the algorithms are fundamentally broken

**Expected Results:**
- Best Baseline (Equal Batches): ~$727k
- Best Prediction (Expected Value): >$800k (+10% minimum)
- Status: ✓ ALGORITHMS WORK


```python
import pandas as pd
import numpy as np
from datetime import datetime
import sys
import importlib.util

# Import strategies from all_strategies_pct.py
spec = importlib.util.spec_from_file_location('all_strategies_pct', 'all_strategies_pct.py')
strat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(strat)

# Import strategy classes
EqualBatchStrategy = strat.EqualBatchStrategy
PriceThresholdStrategy = strat.PriceThresholdStrategy
MovingAverageStrategy = strat.MovingAverageStrategy
ExpectedValueStrategy = strat.ExpectedValueStrategy
ConsensusStrategy = strat.ConsensusStrategy
RiskAdjustedStrategy = strat.RiskAdjustedStrategy
PriceThresholdPredictive = strat.PriceThresholdPredictive
MovingAveragePredictive = strat.MovingAveragePredictive

print("✓ Imported strategy classes")
```


```python
class SimpleBacktestEngine:
    """
    Minimal backtest engine for algorithm validation
    Mirrors main engine but simplified for diagnostics
    """
    def __init__(self, prices_df, prediction_matrices, costs):
        self.prices = prices_df
        self.prediction_matrices = prediction_matrices
        self.storage_cost_pct = costs['storage_cost_pct_per_day']
        self.transaction_cost_pct = costs['transaction_cost_pct']

    def run_backtest(self, strategy, initial_inventory=50.0):
        """Run backtest and return final net earnings"""
        inventory = initial_inventory
        total_revenue = 0.0
        total_transaction_costs = 0.0
        total_storage_costs = 0.0
        trades = []

        for day in range(len(self.prices) - 14):  # Stop 14 days before end
            current_date = self.prices.iloc[day]['date']
            current_price = self.prices.iloc[day]['price']

            # Get predictions for this day
            predictions = self.prediction_matrices.get(current_date, None)

            # Get price history
            price_history = self.prices.iloc[:day+1].copy()

            # Strategy decision
            decision = strategy.decide(day, inventory, current_price, price_history, predictions)

            # Execute trade
            if decision['action'] == 'SELL' and decision['amount'] > 0:
                sell_amount = min(decision['amount'], inventory)

                # Revenue
                revenue = sell_amount * current_price
                transaction_cost = revenue * (self.transaction_cost_pct / 100)
                net_revenue = revenue - transaction_cost

                total_revenue += net_revenue
                total_transaction_costs += transaction_cost
                inventory -= sell_amount

                trades.append({
                    'day': day,
                    'date': current_date,
                    'price': current_price,
                    'amount': sell_amount,
                    'revenue': net_revenue,
                    'reason': decision.get('reason', 'unknown')
                })

            # Storage costs (daily)
            if inventory > 0:
                storage_cost = inventory * current_price * (self.storage_cost_pct / 100)
                total_storage_costs += storage_cost

        # Forced liquidation at end
        if inventory > 0:
            final_price = self.prices.iloc[-14]['price']
            final_revenue = inventory * final_price
            final_transaction_cost = final_revenue * (self.transaction_cost_pct / 100)
            total_revenue += (final_revenue - final_transaction_cost)
            total_transaction_costs += final_transaction_cost

            trades.append({
                'day': len(self.prices) - 14,
                'date': self.prices.iloc[-14]['date'],
                'price': final_price,
                'amount': inventory,
                'revenue': final_revenue - final_transaction_cost,
                'reason': 'forced_liquidation'
            })

        net_earnings = total_revenue - total_storage_costs

        return {
            'net_earnings': net_earnings,
            'total_revenue': total_revenue,
            'transaction_costs': total_transaction_costs,
            'storage_costs': total_storage_costs,
            'trades': trades,
            'num_trades': len(trades)
        }

print("✓ Defined backtest engine")
```

## Load Data


```python
print("="*80)
print("DIAGNOSTIC: 100% ACCURACY ALGORITHM VALIDATION")
print("="*80)
print("\nCommodity: COFFEE")
print("\n⚠️  CRITICAL TEST: With PERFECT FORESIGHT, algorithms MUST beat baselines!")
print("   If they don't, the algorithms are BROKEN.\n")

commodity = 'coffee'

# Load prices from Delta table
print("Loading prices from Delta table...")
market_df = spark.table("commodity.bronze.market").filter(
    f"lower(commodity) = '{commodity}'"
).toPandas()

market_df['date'] = pd.to_datetime(market_df['date'])
market_df['price'] = market_df['close']
prices_df = market_df[['date', 'price']].sort_values('date').reset_index(drop=True)
prices_df = prices_df[prices_df['date'] >= '2022-01-01'].reset_index(drop=True)

print(f"✓ Loaded {len(prices_df)} days of prices")

# Load predictions from Delta table
print("\nLoading predictions from Delta table...")
pred_df = spark.table(f"commodity.trading_agent.predictions_{commodity}").filter(
    "model_version = 'synthetic_acc100'"
).toPandas()

if len(pred_df) == 0:
    raise ValueError(f"No synthetic_acc100 predictions found!")

print(f"✓ Loaded {len(pred_df)} prediction rows")

# Convert to prediction_matrices format
print("Converting to matrix format...")
pred_df['timestamp'] = pd.to_datetime(pred_df['timestamp'])
prediction_matrices = {}

for timestamp in pred_df['timestamp'].unique():
    ts_data = pred_df[pred_df['timestamp'] == timestamp]
    matrix = ts_data.pivot_table(
        index='run_id',
        columns='day_ahead',
        values='predicted_price',
        aggfunc='first'
    ).values
    prediction_matrices[timestamp] = matrix

print(f"✓ Converted to {len(prediction_matrices)} timestamps")
print(f"  Matrix shape: {matrix.shape[0]} runs × {matrix.shape[1]} horizons")
```

## Validate 100% Accuracy


```python
print("\nValidating 100% Accuracy...")

# Check variance across runs (should be 0 for 100% accuracy)
errors = []
for date in list(prediction_matrices.keys())[:10]:  # Sample 10 dates
    pred_matrix = prediction_matrices[date]
    
    for horizon in range(14):
        variance = np.var(pred_matrix[:, horizon])
        if variance > 0.01:
            errors.append(f"Date {date}, horizon {horizon}: variance = {variance:.6f}")

if errors:
    print(f"⚠️  WARNING: Found {len(errors)} prediction variances > 0.01")
    for err in errors[:5]:
        print(f"  {err}")
else:
    print("✓ All predictions have 0 variance (all runs identical)")
```

## Run Baseline Strategies


```python
# Set up costs
costs = {
    'storage_cost_pct_per_day': 0.025,
    'transaction_cost_pct': 0.25
}

# Create engine
engine = SimpleBacktestEngine(prices_df, prediction_matrices, costs)

# Define baseline strategies
baseline_strategies = [
    ('Equal Batches', EqualBatchStrategy()),
    ('Price Threshold', PriceThresholdStrategy()),
    ('Moving Average', MovingAverageStrategy())
]

print("\n" + "="*80)
print("BASELINE STRATEGIES (No Predictions)")
print("="*80)

baseline_results = []
for name, strategy in baseline_strategies:
    print(f"\nRunning {name}...")
    result = engine.run_backtest(strategy)
    baseline_results.append((name, result))
    print(f"  Net Earnings: ${result['net_earnings']:,.0f}")
    print(f"  Trades: {result['num_trades']}")

best_baseline = max(baseline_results, key=lambda x: x[1]['net_earnings'])
print(f"\n🏆 Best Baseline: {best_baseline[0]} = ${best_baseline[1]['net_earnings']:,.0f}")
```

## Run Prediction Strategies


```python
# Define prediction strategies
prediction_strategies = [
    ('Expected Value', ExpectedValueStrategy(
        storage_cost_pct_per_day=costs['storage_cost_pct_per_day'],
        transaction_cost_pct=costs['transaction_cost_pct']
    )),
    ('Consensus', ConsensusStrategy(
        storage_cost_pct_per_day=costs['storage_cost_pct_per_day'],
        transaction_cost_pct=costs['transaction_cost_pct']
    )),
    ('Risk-Adjusted', RiskAdjustedStrategy(
        storage_cost_pct_per_day=costs['storage_cost_pct_per_day'],
        transaction_cost_pct=costs['transaction_cost_pct']
    )),
    ('Price Threshold Pred', PriceThresholdPredictive(
        storage_cost_pct_per_day=costs['storage_cost_pct_per_day'],
        transaction_cost_pct=costs['transaction_cost_pct']
    )),
    ('Moving Average Pred', MovingAveragePredictive(
        storage_cost_pct_per_day=costs['storage_cost_pct_per_day'],
        transaction_cost_pct=costs['transaction_cost_pct']
    ))
]

print("\n" + "="*80)
print("PREDICTION STRATEGIES (With 100% Accurate Predictions)")
print("="*80)

prediction_results = []
for name, strategy in prediction_strategies:
    print(f"\nRunning {name}...")
    result = engine.run_backtest(strategy)
    prediction_results.append((name, result))
    print(f"  Net Earnings: ${result['net_earnings']:,.0f}")
    print(f"  Trades: {result['num_trades']}")
    
    # Compare to best baseline
    improvement = result['net_earnings'] - best_baseline[1]['net_earnings']
    improvement_pct = (improvement / best_baseline[1]['net_earnings']) * 100
    
    if improvement > 0:
        print(f"  ✓ Beats best baseline by ${improvement:,.0f} (+{improvement_pct:.1f}%)")
    else:
        print(f"  ❌ WORSE than baseline by ${-improvement:,.0f} ({improvement_pct:.1f}%)")

best_prediction = max(prediction_results, key=lambda x: x[1]['net_earnings'])
print(f"\n🏆 Best Prediction: {best_prediction[0]} = ${best_prediction[1]['net_earnings']:,.0f}")
```

## Final Verdict


```python
print("\n" + "="*80)
print("ALGORITHM VALIDATION VERDICT")
print("="*80)

best_pred_earnings = best_prediction[1]['net_earnings']
best_base_earnings = best_baseline[1]['net_earnings']
improvement = best_pred_earnings - best_base_earnings
improvement_pct = (improvement / best_base_earnings) * 100

print(f"\nBest Baseline:    ${best_base_earnings:,.0f} ({best_baseline[0]})")
print(f"Best Prediction:  ${best_pred_earnings:,.0f} ({best_prediction[0]})")
print(f"Improvement:      ${improvement:,.0f} ({improvement_pct:+.1f}%)")

print("\nValidation Criteria:")
print(f"  1. Predictions must beat baselines: {'✓ PASS' if improvement > 0 else '❌ FAIL'}")
print(f"  2. Improvement must be >10%: {'✓ PASS' if improvement_pct > 10 else '❌ FAIL (only ' + f'{improvement_pct:.1f}%)')}")

if improvement > 0 and improvement_pct > 10:
    print("\n" + "="*80)
    print("✓✓✓ ALGORITHMS VALIDATED: Strategies work correctly with perfect predictions")
    print("="*80)
    print("\nConclusion: The trading algorithms are fundamentally sound.")
    print("If real predictions underperform, the issue is:")
    print("  - Prediction accuracy not high enough")
    print("  - Parameter tuning needed")
    print("  - Prediction usage in strategies needs refinement")
else:
    print("\n" + "="*80)
    print("❌❌❌ ALGORITHMS BROKEN: Even with PERFECT predictions, strategies lose!")
    print("="*80)
    print("\nConclusion: There is a fundamental bug in the algorithm logic.")
    print("Possible issues:")
    print("  - Decision logic is inverted (buy when should sell)")
    print("  - Wrong prediction horizon being used")
    print("  - Cost calculations are wrong")
    print("  - Prediction lookups returning None/wrong data")
    print("\nNEXT STEP: Run diagnostic_17_paradox_analysis.ipynb to find the bug")
```
