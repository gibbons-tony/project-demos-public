# Diagnostic 11: Expected Value Calculation Trace

**Purpose:** Trace EV calculations step-by-step to verify decision logic

**Key Questions:**
1. Is the strategy using the correct prediction horizon (day 13 for 14-day forecast)?
2. Is the EV calculation mathematically correct?
3. Do decisions make sense given the predictions?

**Method:** Compare manual calculations with strategy's actual calculations


```
%run ../00_setup_and_config
```


```
import pandas as pd
import numpy as np
import pickle

print("="*80)
print("DIAGNOSTIC 11: EXPECTED VALUE CALCULATION TRACE")
print("="*80)
print("\nGoal: Verify EV calculations are correct")
```

## Step 1: Load Data


```
COMMODITY = 'coffee'
MODEL_VERSION = 'synthetic_acc90'

DATA_PATHS = get_data_paths(COMMODITY, MODEL_VERSION)
COMMODITY_CONFIG = COMMODITY_CONFIGS[COMMODITY]

print("Loading prices...")
prices_table = get_data_paths(COMMODITY)['prices_prepared']
prices = spark.table(prices_table).toPandas()
prices['date'] = pd.to_datetime(prices['date'])
print(f"✓ Loaded {len(prices)} price records")

print("\nLoading predictions...")
matrices_path = DATA_PATHS['prediction_matrices']
with open(matrices_path, 'rb') as f:
    prediction_matrices = pickle.load(f)
print(f"✓ Loaded {len(prediction_matrices)} prediction matrices")

# Normalize dates
prediction_matrices = {pd.to_datetime(k): v for k, v in prediction_matrices.items()}

print("\nLoading results to find sample trades...")
results_path = DATA_PATHS['results_detailed']
with open(results_path, 'rb') as f:
    all_results = pickle.load(f)
print(f"✓ Loaded results")
```

## Step 2: Get Sample Days from Actual Trades


```
# Get Expected Value trades
ev_trades = all_results['Expected Value']['trades']

print("Sample trades from Expected Value strategy:")
print(f"\nTotal trades: {len(ev_trades)}")

# Find trades with different reasons
sample_trades = []
reasons_seen = set()

for trade in ev_trades[:50]:  # Check first 50
    reason = trade.get('reason', '')
    reason_type = reason.split('_')[0] if '_' in reason else reason
    
    if reason_type not in reasons_seen and len(sample_trades) < 5:
        sample_trades.append(trade)
        reasons_seen.add(reason_type)

print("\nSample trades to analyze:")
for i, trade in enumerate(sample_trades):
    print(f"  {i+1}. Day {trade['day']}: {trade['amount']:.1f}t @ ${trade['price']:.2f} - {trade['reason']}")
```

## Step 3: Manual EV Calculation for Sample Days


```
def manual_ev_calculation(day_idx, current_price, predictions, inventory, config):
    """
    Manually calculate expected value to compare with strategy.
    """
    print(f"\n{'='*80}")
    print(f"MANUAL EV CALCULATION FOR DAY {day_idx}")
    print(f"{'='*80}")
    
    print(f"\nInputs:")
    print(f"  Current price: ${current_price:.2f}")
    print(f"  Inventory: {inventory:.2f} tons")
    print(f"  Predictions shape: {predictions.shape if predictions is not None else 'None'}")
    
    if predictions is None:
        print(f"\n✗ No predictions available for this day")
        return None
    
    # Check prediction horizon
    n_runs, n_horizons = predictions.shape
    print(f"\nPrediction array info:")
    print(f"  Runs: {n_runs}")
    print(f"  Horizons: {n_horizons} (days 0-{n_horizons-1})")
    
    # For a 14-day forecast, we should use day 13 (0-indexed)
    forecast_day = 13
    print(f"\n  Using horizon day: {forecast_day} (14 days out, 0-indexed)")
    
    # Get predictions for that horizon
    future_prices = predictions[:, forecast_day]
    
    print(f"\nFuture price predictions (day {forecast_day}):")
    print(f"  Mean: ${np.mean(future_prices):.2f}")
    print(f"  Median: ${np.median(future_prices):.2f}")
    print(f"  Std: ${np.std(future_prices):.2f}")
    print(f"  Min: ${np.min(future_prices):.2f}")
    print(f"  Max: ${np.max(future_prices):.2f}")
    print(f"  CV: {100*np.std(future_prices)/np.mean(future_prices):.1f}%")
    
    # Calculate costs
    price_per_ton = current_price * 20  # cents/lb to $/ton
    storage_cost_pct = config['storage_cost_pct_per_day']
    transaction_cost_pct = config['transaction_cost_pct']
    
    print(f"\nCost parameters:")
    print(f"  Storage: {storage_cost_pct}% per day")
    print(f"  Transaction: {transaction_cost_pct}% per sale")
    print(f"  Price per ton: ${price_per_ton:.2f}")
    
    # Scenario 1: Sell today
    sell_today_revenue = inventory * price_per_ton
    sell_today_transaction = sell_today_revenue * (transaction_cost_pct / 100)
    sell_today_net = sell_today_revenue - sell_today_transaction
    
    print(f"\nScenario 1: SELL TODAY")
    print(f"  Revenue: ${sell_today_revenue:,.2f}")
    print(f"  Transaction cost: ${sell_today_transaction:,.2f}")
    print(f"  Net: ${sell_today_net:,.2f}")
    
    # Scenario 2: Wait 14 days
    expected_future_price_per_ton = np.mean(future_prices) * 20
    wait_revenue = inventory * expected_future_price_per_ton
    wait_transaction = wait_revenue * (transaction_cost_pct / 100)
    wait_storage = inventory * price_per_ton * (storage_cost_pct / 100) * 14
    wait_net = wait_revenue - wait_transaction - wait_storage
    
    print(f"\nScenario 2: WAIT 14 DAYS")
    print(f"  Expected future price: ${np.mean(future_prices):.2f} (${expected_future_price_per_ton:.2f}/ton)")
    print(f"  Revenue: ${wait_revenue:,.2f}")
    print(f"  Transaction cost: ${wait_transaction:,.2f}")
    print(f"  Storage cost (14 days): ${wait_storage:,.2f}")
    print(f"  Net: ${wait_net:,.2f}")
    
    # Expected Value improvement
    ev_improvement = wait_net - sell_today_net
    
    print(f"\nExpected Value Analysis:")
    print(f"  EV(wait) - EV(sell_today): ${ev_improvement:,.2f}")
    print(f"  Percentage gain: {100*ev_improvement/sell_today_net:.2f}%")
    
    # Decision threshold
    min_ev_improvement = 50  # From strategy params
    print(f"\nDecision threshold: ${min_ev_improvement}")
    
    if ev_improvement >= min_ev_improvement:
        decision = "WAIT"
        print(f"  → Expected decision: {decision} (EV improvement ${ev_improvement:.2f} >= ${min_ev_improvement})")
    else:
        decision = "SELL"
        print(f"  → Expected decision: {decision} (EV improvement ${ev_improvement:.2f} < ${min_ev_improvement})")
    
    return {
        'current_price': current_price,
        'future_price_mean': np.mean(future_prices),
        'future_price_std': np.std(future_prices),
        'sell_today_net': sell_today_net,
        'wait_net': wait_net,
        'ev_improvement': ev_improvement,
        'expected_decision': decision
    }
```


```
# Analyze the first sample trade
if len(sample_trades) > 0:
    trade = sample_trades[0]
    day_idx = trade['day']
    
    # Get the data for that day
    current_date = prices.iloc[day_idx]['date']
    current_price = prices.iloc[day_idx]['price']
    predictions = prediction_matrices.get(current_date, None)
    
    # Assume inventory from trade amount (approximate)
    inventory = 50.0  # Typical inventory level
    
    result = manual_ev_calculation(
        day_idx, 
        current_price, 
        predictions, 
        inventory, 
        COMMODITY_CONFIG
    )
    
    print(f"\nActual trade that was made:")
    print(f"  Action: SELL {trade['amount']:.1f}t")
    print(f"  Reason: {trade['reason']}")
    
    if result:
        print(f"\nComparison:")
        print(f"  Manual calculation says: {result['expected_decision']}")
        print(f"  Strategy actually did: SELL")
        if result['expected_decision'] != 'SELL':
            print(f"  ⚠️  MISMATCH! Strategy should have chosen to WAIT")
```

## Step 4: Check Multiple Samples


```
print("="*80)
print("ANALYZING MULTIPLE SAMPLE DAYS")
print("="*80)

mismatches = []

for i, trade in enumerate(sample_trades[:3]):  # Analyze first 3
    day_idx = trade['day']
    current_date = prices.iloc[day_idx]['date']
    current_price = prices.iloc[day_idx]['price']
    predictions = prediction_matrices.get(current_date, None)
    inventory = 50.0
    
    result = manual_ev_calculation(
        day_idx, current_price, predictions, inventory, COMMODITY_CONFIG
    )
    
    if result:
        print(f"\nActual trade: SELL {trade['amount']:.1f}t - {trade['reason']}")
        
        if result['expected_decision'] != 'SELL':
            mismatches.append({
                'day': day_idx,
                'expected': result['expected_decision'],
                'actual': 'SELL',
                'ev_improvement': result['ev_improvement'],
                'reason': trade['reason']
            })

print(f"\n{'='*80}")
print(f"MISMATCH SUMMARY")
print(f"{'='*80}")
print(f"Samples analyzed: {min(3, len(sample_trades))}")
print(f"Mismatches found: {len(mismatches)}")

if len(mismatches) > 0:
    print(f"\n⚠️  DECISION LOGIC PROBLEM DETECTED")
    for m in mismatches:
        print(f"  Day {m['day']}: Expected {m['expected']}, got {m['actual']} (EV improvement: ${m['ev_improvement']:.2f})")
```

## Step 5: Check Prediction Horizon Usage


```
print("="*80)
print("PREDICTION HORIZON CHECK")
print("="*80)

# Get a sample prediction matrix
sample_date = list(prediction_matrices.keys())[100]
sample_preds = prediction_matrices[sample_date]

print(f"\nSample prediction matrix shape: {sample_preds.shape}")
print(f"  Runs: {sample_preds.shape[0]}")
print(f"  Horizons: {sample_preds.shape[1]}")

print(f"\nPrice progression across horizons (mean of all runs):")
for h in range(sample_preds.shape[1]):
    mean_price = np.mean(sample_preds[:, h])
    print(f"  Day {h:2d}: ${mean_price:.2f}")

print(f"\nKey question: Which horizon should strategy use for 14-day forecast?")
print(f"  Answer: Day 13 (0-indexed) = 14 days from today")

# Check if using wrong horizon would explain results
price_day_0 = np.mean(sample_preds[:, 0])
price_day_13 = np.mean(sample_preds[:, 13])

print(f"\nComparison:")
print(f"  Using Day 0 (today): ${price_day_0:.2f} ← WRONG (this is current price!)")
print(f"  Using Day 13 (14 days): ${price_day_13:.2f} ← CORRECT")
print(f"\nIf strategy uses Day 0, it sees no price change → always sells!")
```

## Step 6: Summary


```
print("="*80)
print("DIAGNOSTIC 11 SUMMARY")
print("="*80)

print(f"\nFindings:")
print(f"1. Prediction arrays have shape: {sample_preds.shape}")
print(f"2. For 14-day forecast, should use horizon index 13")
print(f"3. Manual EV calculations show expected decisions")
print(f"4. Mismatches found: {len(mismatches)}")

if len(mismatches) > 0:
    print(f"\n✗✗✗ BUG CONFIRMED: Decision logic problem")
    print(f"\nMost likely causes:")
    print(f"  1. Using wrong prediction horizon (e.g., day 0 instead of day 13)")
    print(f"  2. EV calculation error in strategy")
    print(f"  3. Decision threshold logic inverted")
    print(f"\nNext step: Create diagnostic_12 to check exact horizon used")
else:
    print(f"\n✓ Manual calculations match strategy decisions")
    print(f"\nNext step: Check if issue is in other strategies or parameters")
```
