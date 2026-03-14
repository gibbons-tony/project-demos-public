# Diagnostic 02: Backtest Engine Trace

**Purpose:** Trace prediction flow through backtest engine

**Test Case:** Coffee synthetic_acc90

**Pass Criteria:**
- >200 days have predictions available during backtest
- Predictions are not None when passed to strategy
- Values look reasonable (match expected prices)


```python
%run ../00_setup_and_config
```


```python
%run ../03_strategy_implementations
```


```python
import pandas as pd
import numpy as np
import pickle

print("="*80)
print("DIAGNOSTIC 02: BACKTEST ENGINE TRACE")
print("="*80)
print("\nTest Case: Coffee synthetic_acc90")
print("Goal: Trace predictions through backtest engine\n")
```

## Step 1: Load Data (with date normalization)


```python
COMMODITY = 'coffee'
MODEL_VERSION = 'synthetic_acc90'
COMMODITY_CONFIG = COMMODITY_CONFIGS[COMMODITY]

DATA_PATHS = get_data_paths(COMMODITY, MODEL_VERSION)

# Load prices
print("Loading prices...")
prices = spark.table(get_data_paths(COMMODITY)['prices_prepared']).toPandas()
prices['date'] = pd.to_datetime(prices['date'])  # NORMALIZE
print(f"✓ Loaded {len(prices)} price records")

# Load predictions
print("\nLoading predictions...")
matrices_path = DATA_PATHS['prediction_matrices']
with open(matrices_path, 'rb') as f:
    prediction_matrices = pickle.load(f)

# NORMALIZE prediction dates
prediction_matrices = {pd.to_datetime(k): v for k, v in prediction_matrices.items()}
print(f"✓ Loaded {len(prediction_matrices)} prediction matrices")

# Verify alignment
pred_set = set(prediction_matrices.keys())
price_set = set(prices['date'].tolist())
overlap = pred_set.intersection(price_set)
overlap_pct = 100 * len(overlap) / len(pred_set) if len(pred_set) > 0 else 0

print(f"\nDate alignment: {overlap_pct:.1f}% overlap")
if overlap_pct > 90:
    print("✓ Good alignment")
else:
    print(f"⚠️  Only {overlap_pct:.1f}% overlap")
```

## Step 2: Create Instrumented Backtest Engine


```python
class InstrumentedBacktestEngine:
    """Backtest engine with diagnostic logging"""
    
    def __init__(self, prices, prediction_matrices, commodity_config):
        self.prices = prices
        self.prediction_matrices = prediction_matrices
        self.config = commodity_config
        
        # Diagnostic tracking
        self.prediction_log = []
    
    def run(self, strategy):
        """Run backtest with diagnostic logging"""
        
        # Setup (same as original)
        total_volume = self.config['harvest_volume']
        harvest_start = pd.to_datetime(self.config['harvest_start'])
        harvest_end = pd.to_datetime(self.config['harvest_end'])
        
        # Initialize state
        daily_state = self.prices.copy()
        daily_state['inventory'] = 0.0
        daily_state['daily_storage_cost'] = 0.0
        daily_state['day'] = range(len(daily_state))
        
        # Accumulate inventory during harvest
        harvest_days = daily_state[
            (daily_state['date'] >= harvest_start) & 
            (daily_state['date'] <= harvest_end)
        ]
        
        if len(harvest_days) > 0:
            daily_harvest = total_volume / len(harvest_days)
            for idx in harvest_days.index:
                daily_state.loc[idx, 'inventory'] = daily_harvest
        
        # Forward fill inventory
        for i in range(1, len(daily_state)):
            if daily_state.loc[i, 'inventory'] == 0:
                daily_state.loc[i, 'inventory'] = daily_state.loc[i-1, 'inventory']
        
        # Track trades
        trades = []
        
        # Diagnostic counters
        days_with_predictions = 0
        days_without_predictions = 0
        first_pred_logged = False
        first_no_pred_logged = False
        
        # Main backtest loop
        for idx, row in daily_state.iterrows():
            day = row['day']
            current_date = row['date']
            inventory = daily_state.loc[idx, 'inventory']
            price = row['price']
            
            if inventory <= 0:
                continue
            
            # DIAGNOSTIC: Get predictions
            prediction_matrix = self.prediction_matrices.get(current_date, None)
            
            # DIAGNOSTIC: Log prediction availability
            if prediction_matrix is not None:
                days_with_predictions += 1
                
                if not first_pred_logged:
                    print(f"\n✓ First prediction found:")
                    print(f"  Day: {day}")
                    print(f"  Date: {current_date}")
                    print(f"  Matrix shape: {prediction_matrix.shape}")
                    print(f"  Sample values: {prediction_matrix[0, :5]}")
                    first_pred_logged = True
                
                # Log this prediction
                self.prediction_log.append({
                    'day': day,
                    'date': current_date,
                    'has_prediction': True,
                    'shape': prediction_matrix.shape,
                    'mean_pred': prediction_matrix.mean(),
                    'current_price': price
                })
            else:
                days_without_predictions += 1
                
                if not first_no_pred_logged:
                    print(f"\n⚠️  First missing prediction:")
                    print(f"  Day: {day}")
                    print(f"  Date: {current_date}")
                    first_no_pred_logged = True
                
                self.prediction_log.append({
                    'day': day,
                    'date': current_date,
                    'has_prediction': False,
                    'current_price': price
                })
            
            # Calculate technical indicators (simplified)
            tech_indicators = {}
            
            # Call strategy
            should_sell, batch_size = strategy.should_sell(
                day=day,
                inventory=inventory,
                price=price,
                predictions=prediction_matrix,
                technical_indicators=tech_indicators
            )
            
            # Execute trade if should_sell
            if should_sell and batch_size > 0:
                amount = min(inventory * batch_size, inventory)
                revenue = amount * price
                transaction_cost = revenue * self.config['transaction_cost_pct']
                net_revenue = revenue - transaction_cost
                
                trades.append({
                    'day': day,
                    'date': current_date,
                    'amount': amount,
                    'price': price,
                    'revenue': revenue,
                    'transaction_cost': transaction_cost,
                    'net_revenue': net_revenue,
                    'reason': f'Strategy sell signal (batch={batch_size:.2f})'
                })
                
                # Update inventory
                for future_idx in range(idx, len(daily_state)):
                    daily_state.loc[future_idx, 'inventory'] -= amount
            
            # Storage costs
            remaining_inventory = daily_state.loc[idx, 'inventory']
            if remaining_inventory > 0:
                inventory_value = remaining_inventory * price
                storage_cost = inventory_value * self.config['storage_cost_pct_per_day']
                daily_state.loc[idx, 'daily_storage_cost'] = storage_cost
        
        # Print summary
        print(f"\n" + "="*80)
        print(f"BACKTEST TRACE SUMMARY")
        print("="*80)
        print(f"\nTotal days simulated: {len(daily_state)}")
        print(f"Days with predictions: {days_with_predictions}")
        print(f"Days without predictions: {days_without_predictions}")
        total_days = days_with_predictions + days_without_predictions
        if total_days > 0:
            coverage = 100 * days_with_predictions / total_days
            print(f"Coverage: {coverage:.1f}%")
            
            if coverage > 80:
                print("✓ PASS: Good prediction coverage")
            elif coverage > 50:
                print(f"⚠️  WARNING: Only {coverage:.1f}% coverage")
            else:
                print(f"✗ FAIL: Only {coverage:.1f}% coverage")
        
        print(f"\nTotal trades: {len(trades)}")
        
        return {
            'daily_state': daily_state,
            'trades': trades,
            'strategy_name': strategy.name
        }

print("✓ Instrumented backtest engine created")
```

## Step 3: Run Instrumented Backtest


```python
print("\n" + "="*80)
print("RUNNING INSTRUMENTED BACKTEST")
print("="*80)

# Create engine
engine = InstrumentedBacktestEngine(prices, prediction_matrices, COMMODITY_CONFIG)

# Create a simple strategy (Expected Value)
strategy = ExpectedValueStrategy(
    storage_cost_pct_per_day=COMMODITY_CONFIG['storage_cost_pct_per_day'],
    transaction_cost_pct=COMMODITY_CONFIG['transaction_cost_pct'],
    **PREDICTION_PARAMS['expected_value']
)

print(f"\nTesting strategy: {strategy.name}")
print("\nRunning backtest...")

results = engine.run(strategy)
```

## Step 4: Analyze Prediction Log


```python
print("\n" + "="*80)
print("PREDICTION LOG ANALYSIS")
print("="*80)

log_df = pd.DataFrame(engine.prediction_log)

print(f"\nTotal entries: {len(log_df)}")
print(f"With predictions: {log_df['has_prediction'].sum()}")
print(f"Without predictions: {(~log_df['has_prediction']).sum()}")

if len(log_df[log_df['has_prediction']]) > 0:
    pred_log = log_df[log_df['has_prediction']].copy()
    
    print(f"\nPrediction statistics:")
    print(f"  Mean predicted price: ${pred_log['mean_pred'].mean():.2f}")
    print(f"  Mean current price: ${pred_log['current_price'].mean():.2f}")
    
    # Check correlation
    if 'mean_pred' in pred_log.columns and len(pred_log) > 1:
        corr = pred_log[['current_price', 'mean_pred']].corr().iloc[0, 1]
        print(f"  Correlation: {corr:.3f}")
        
        if corr > 0.99:
            print("  ✗ CRITICAL: Predictions are just current price! (data leak)")
        elif corr > 0.9:
            print("  ⚠️  WARNING: Very high correlation (>0.9)")
        elif 0.5 <= corr <= 0.9:
            print("  ✓ PASS: Reasonable correlation (predictions related but not identical)")
        else:
            print(f"  ⚠️  Unusual correlation: {corr:.3f}")
    
    print(f"\nSample prediction log (first 10 days with predictions):")
    display(pred_log[['day', 'date', 'current_price', 'mean_pred']].head(10))
else:
    print("\n✗ CRITICAL: No predictions found during backtest!")
    print("This is THE bug - predictions aren't reaching the backtest engine.")
```

## Step 5: Compare to Production Results


```python
print("\n" + "="*80)
print("COMPARISON TO PRODUCTION")
print("="*80)

# Calculate metrics
total_revenue = sum(t['revenue'] for t in results['trades'])
total_transaction_costs = sum(t['transaction_cost'] for t in results['trades'])
total_storage_costs = results['daily_state']['daily_storage_cost'].sum()
net_earnings = total_revenue - total_transaction_costs - total_storage_costs

print(f"\nDiagnostic backtest results:")
print(f"  Total revenue: ${total_revenue:,.2f}")
print(f"  Transaction costs: ${total_transaction_costs:,.2f}")
print(f"  Storage costs: ${total_storage_costs:,.2f}")
print(f"  Net earnings: ${net_earnings:,.2f}")
print(f"  Trades: {len(results['trades'])}")

# Load production results for comparison
try:
    prod_results = spark.table(DATA_PATHS['results']).toPandas()
    prod_ev = prod_results[prod_results['strategy'] == 'Expected Value'].iloc[0]
    
    print(f"\nProduction results (from notebook 05):")
    print(f"  Net earnings: ${prod_ev['net_earnings']:,.2f}")
    print(f"  Trades: {int(prod_ev['n_trades'])}")
    
    diff = net_earnings - prod_ev['net_earnings']
    print(f"\nDifference: ${diff:+,.2f}")
    
    if abs(diff) < 100:
        print("✓ MATCH: Diagnostic matches production (within $100)")
    elif abs(diff) < 1000:
        print(f"⚠️  Small difference: ${abs(diff):,.2f}")
    else:
        print(f"✗ LARGE DIFFERENCE: ${abs(diff):,.2f}")
        print("This suggests the diagnostic has different behavior")
        
except Exception as e:
    print(f"\n⚠️  Could not load production results: {e}")
    print("(This is OK if production hasn't been run yet)")
```

## Step 6: Diagnostic Summary


```python
print("\n" + "="*80)
print("DIAGNOSTIC 02 SUMMARY")
print("="*80)

days_with_pred = log_df['has_prediction'].sum()
total_days = len(log_df)
coverage = 100 * days_with_pred / total_days if total_days > 0 else 0

# Determine pass/fail
if days_with_pred > 200 and coverage > 80:
    print("\n✓✓✓ DIAGNOSTIC 02 PASS")
    print("\nConclusion: Predictions ARE reaching the backtest engine")
    print(f"Coverage: {coverage:.1f}% ({days_with_pred} days)")
    print("\nIf results still show predictions losing money, the bug is likely")
    print("in the strategy decision logic (diagnostic_03).")
elif days_with_pred == 0:
    print("\n✗✗✗ DIAGNOSTIC 02 CRITICAL FAIL")
    print("\nConclusion: Predictions NOT reaching backtest engine")
    print("\nThis is THE bug! Despite loading predictions, they're not")
    print("being accessed during the backtest loop.")
    print("\nLikely causes:")
    print("  1. Date type mismatch in backtest loop")
    print("  2. Dictionary key lookup failing")
    print("  3. Predictions not passed to engine correctly")
else:
    print("\n⚠️⚠️⚠️ DIAGNOSTIC 02 PARTIAL FAIL")
    print(f"\nConclusion: Only {coverage:.1f}% coverage ({days_with_pred} days)")
    print("\nPredictions are partially reaching the engine, but coverage is low.")
    print("This could explain poor performance.")

print("\nNext step: diagnostic_03_strategy_decisions.ipynb")
```
