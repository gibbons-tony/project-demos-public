# Diagnostic 04: Fixed Strategy Implementations

**Purpose:** Implement corrected versions of strategies based on diagnostic findings

**Test Case:** Coffee synthetic_acc90

**Expected Fixes:**
- Date alignment (datetime normalization)
- Prediction passing verification
- Decision logic validation

**Pass Criteria:**
- Expected Value beats baseline by >$30k (+4%)
- Decision log shows predictions driving decisions
- >80% of days have predictions available


```python
%run ../00_setup_and_config
```


```python
import pandas as pd
import numpy as np
import pickle

print("="*80)
print("DIAGNOSTIC 04: FIXED STRATEGY IMPLEMENTATIONS")
print("="*80)
print("\nTest Case: Coffee synthetic_acc90")
print("Goal: Implement corrected strategies and test on 90% accuracy\n")
```

## Step 1: Load Data with Date Normalization (FIX A)


```python
COMMODITY = 'coffee'
MODEL_VERSION = 'synthetic_acc90'
COMMODITY_CONFIG = COMMODITY_CONFIGS[COMMODITY]

DATA_PATHS = get_data_paths(COMMODITY, MODEL_VERSION)

print("Loading prices...")
prices = spark.table(get_data_paths(COMMODITY)['prices_prepared']).toPandas()

# FIX A: Normalize date types
print(f"Before normalization: {type(prices['date'].iloc[0])}")
prices['date'] = pd.to_datetime(prices['date'])
print(f"After normalization: {type(prices['date'].iloc[0])}")
print(f"✓ Loaded {len(prices)} price records")

print("\nLoading predictions...")
matrices_path = DATA_PATHS['prediction_matrices']
with open(matrices_path, 'rb') as f:
    prediction_matrices = pickle.load(f)

# FIX A: Normalize prediction date keys
print(f"Before normalization: {type(list(prediction_matrices.keys())[0])}")
prediction_matrices = {pd.to_datetime(k): v for k, v in prediction_matrices.items()}
print(f"After normalization: {type(list(prediction_matrices.keys())[0])}")
print(f"✓ Loaded {len(prediction_matrices)} prediction matrices")

# Verify alignment
pred_set = set(prediction_matrices.keys())
price_set = set(prices['date'].tolist())
overlap = pred_set.intersection(price_set)
overlap_pct = 100 * len(overlap) / len(pred_set) if len(pred_set) > 0 else 0

print(f"\nDate alignment check:")
print(f"  Overlap: {overlap_pct:.1f}% ({len(overlap)} days)")

if overlap_pct > 90:
    print("  ✓ PASS: Good alignment after date normalization")
else:
    print(f"  ✗ FAIL: Only {overlap_pct:.1f}% overlap")
```

## Step 2: Fixed Expected Value Strategy


```python
class FixedExpectedValueStrategy:
    """Expected Value strategy with fixes and diagnostics"""
    
    def __init__(self, storage_cost_pct_per_day, transaction_cost_pct, 
                 evaluation_day=7, min_return=0.03):
        self.name = "Expected Value (Fixed)"
        self.storage_cost_pct_per_day = storage_cost_pct_per_day
        self.transaction_cost_pct = transaction_cost_pct
        self.evaluation_day = evaluation_day
        self.min_return = min_return
        
        # Diagnostic tracking
        self.decision_log = []
        self.predictions_received = 0
        self.predictions_missing = 0
    
    def should_sell(self, day, inventory, price, predictions, technical_indicators):
        """Make sell decision with extensive logging"""
        
        # FIX B: Verify predictions are not None
        if predictions is None:
            self.predictions_missing += 1
            # Fallback to immediate sale if no predictions
            self.decision_log.append({
                'day': day,
                'price': price,
                'has_predictions': False,
                'decision': 'SELL',
                'batch_size': 1.0,
                'reason': 'No predictions available - fallback to immediate sale'
            })
            return True, 1.0
        
        self.predictions_received += 1
        
        # FIX C: Correct decision logic
        # Calculate expected future price at evaluation day
        if predictions.shape[1] <= self.evaluation_day:
            # Not enough forecast horizon
            expected_future_price = np.mean(predictions[:, -1])
            eval_day_used = predictions.shape[1] - 1
        else:
            expected_future_price = np.mean(predictions[:, self.evaluation_day])
            eval_day_used = self.evaluation_day
        
        # Calculate expected return
        expected_return = (expected_future_price - price) / price
        
        # Calculate costs to wait
        storage_cost = self.storage_cost_pct_per_day * eval_day_used
        transaction_cost = self.transaction_cost_pct
        total_cost = storage_cost + transaction_cost
        
        # Calculate net benefit of waiting
        net_benefit = expected_return - total_cost
        
        # Decision logic:
        # - If net_benefit > min_return: WAIT (better to hold)
        # - If net_benefit <= min_return: SELL NOW
        
        if net_benefit > self.min_return:
            decision = 'WAIT'
            batch_size = 0.0
            reason = f'Net benefit {net_benefit:.3f} > min_return {self.min_return:.3f}'
        else:
            decision = 'SELL'
            batch_size = 0.1  # Sell 10% of inventory
            reason = f'Net benefit {net_benefit:.3f} <= min_return {self.min_return:.3f}'
        
        # Log this decision
        self.decision_log.append({
            'day': day,
            'price': price,
            'has_predictions': True,
            'expected_future_price': expected_future_price,
            'expected_return': expected_return,
            'storage_cost': storage_cost,
            'transaction_cost': transaction_cost,
            'total_cost': total_cost,
            'net_benefit': net_benefit,
            'decision': decision,
            'batch_size': batch_size,
            'reason': reason,
            'eval_day_used': eval_day_used
        })
        
        return decision == 'SELL', batch_size

print("✓ Fixed Expected Value strategy defined")
```

## Step 3: Fixed Backtest Engine


```python
class FixedBacktestEngine:
    """Backtest engine with date normalization fixes"""
    
    def __init__(self, prices, prediction_matrices, commodity_config):
        self.prices = prices
        self.prediction_matrices = prediction_matrices
        self.config = commodity_config
        
        # Ensure dates are normalized
        if len(self.prices) > 0:
            if not isinstance(self.prices['date'].iloc[0], pd.Timestamp):
                self.prices['date'] = pd.to_datetime(self.prices['date'])
    
    def run(self, strategy):
        """Run backtest with fixed date handling"""
        
        # Setup
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
        
        # Main backtest loop
        for idx, row in daily_state.iterrows():
            day = row['day']
            current_date = row['date']
            inventory = daily_state.loc[idx, 'inventory']
            price = row['price']
            
            if inventory <= 0:
                continue
            
            # FIX B: Get predictions with date normalization
            # Ensure current_date is pandas Timestamp for dictionary lookup
            if not isinstance(current_date, pd.Timestamp):
                current_date = pd.to_datetime(current_date)
            
            prediction_matrix = self.prediction_matrices.get(current_date, None)
            
            # Track prediction availability
            if prediction_matrix is not None:
                days_with_predictions += 1
            else:
                days_without_predictions += 1
            
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
        print(f"\nBacktest completed:")
        print(f"  Days with predictions: {days_with_predictions}")
        print(f"  Days without predictions: {days_without_predictions}")
        total_days = days_with_predictions + days_without_predictions
        if total_days > 0:
            coverage = 100 * days_with_predictions / total_days
            print(f"  Coverage: {coverage:.1f}%")
        print(f"  Total trades: {len(trades)}")
        
        return {
            'daily_state': daily_state,
            'trades': trades,
            'strategy_name': strategy.name,
            'days_with_predictions': days_with_predictions,
            'days_without_predictions': days_without_predictions
        }

print("✓ Fixed backtest engine defined")
```

## Step 4: Run Fixed Expected Value Strategy


```python
print("="*80)
print("RUNNING FIXED EXPECTED VALUE STRATEGY")
print("="*80)

# Create engine
engine = FixedBacktestEngine(prices, prediction_matrices, COMMODITY_CONFIG)

# Create fixed strategy
strategy = FixedExpectedValueStrategy(
    storage_cost_pct_per_day=COMMODITY_CONFIG['storage_cost_pct_per_day'],
    transaction_cost_pct=COMMODITY_CONFIG['transaction_cost_pct'],
    **PREDICTION_PARAMS['expected_value']
)

print(f"\nTesting strategy: {strategy.name}")
print(f"  Evaluation day: {strategy.evaluation_day}")
print(f"  Min return: {strategy.min_return}")
print("\nRunning backtest...")

results = engine.run(strategy)
```

## Step 5: Calculate Performance Metrics


```python
print("\n" + "="*80)
print("PERFORMANCE METRICS")
print("="*80)

# Calculate metrics
total_revenue = sum(t['revenue'] for t in results['trades'])
total_transaction_costs = sum(t['transaction_cost'] for t in results['trades'])
total_storage_costs = results['daily_state']['daily_storage_cost'].sum()
net_earnings = total_revenue - total_transaction_costs - total_storage_costs

print(f"\nFixed Expected Value Results:")
print(f"  Total revenue: ${total_revenue:,.2f}")
print(f"  Transaction costs: ${total_transaction_costs:,.2f}")
print(f"  Storage costs: ${total_storage_costs:,.2f}")
print(f"  Net earnings: ${net_earnings:,.2f}")
print(f"  Trades: {len(results['trades'])}")

# Baseline comparison
baseline_earnings = 727037  # Equal Batches from production results
advantage = net_earnings - baseline_earnings
advantage_pct = 100 * advantage / baseline_earnings

print(f"\nComparison to Baseline (Equal Batches):")
print(f"  Baseline: ${baseline_earnings:,.2f}")
print(f"  Fixed strategy: ${net_earnings:,.2f}")
print(f"  Advantage: ${advantage:+,.2f} ({advantage_pct:+.2f}%)")

if advantage > 30000:
    print("\n  ✓✓✓ PASS: Strategy beats baseline by >$30k!")
elif advantage > 10000:
    print("\n  ✓ PARTIAL PASS: Strategy beats baseline by >$10k")
elif advantage > 0:
    print("\n  ⚠️  MARGINAL: Strategy beats baseline but <$10k")
else:
    print("\n  ✗ FAIL: Strategy still underperforms baseline")
```

## Step 6: Analyze Strategy Decisions


```python
print("\n" + "="*80)
print("STRATEGY DECISION ANALYSIS")
print("="*80)

log_df = pd.DataFrame(strategy.decision_log)

print(f"\nPrediction availability:")
print(f"  Predictions received: {strategy.predictions_received}")
print(f"  Predictions missing: {strategy.predictions_missing}")
total = strategy.predictions_received + strategy.predictions_missing
if total > 0:
    coverage = 100 * strategy.predictions_received / total
    print(f"  Coverage: {coverage:.1f}%")
    
    if coverage > 80:
        print("  ✓ PASS: >80% prediction coverage")
    else:
        print(f"  ⚠️  WARNING: Only {coverage:.1f}% coverage")

# Analyze decisions with predictions
if len(log_df[log_df['has_predictions']]) > 0:
    pred_log = log_df[log_df['has_predictions']].copy()
    
    print(f"\nDecision breakdown (when predictions available):")
    print(f"  SELL decisions: {len(pred_log[pred_log['decision'] == 'SELL'])}")
    print(f"  WAIT decisions: {len(pred_log[pred_log['decision'] == 'WAIT'])}")
    
    # Check if decisions vary
    sell_count = len(pred_log[pred_log['decision'] == 'SELL'])
    wait_count = len(pred_log[pred_log['decision'] == 'WAIT'])
    
    if sell_count > 0 and wait_count > 0:
        print("  ✓ PASS: Mix of SELL and WAIT decisions")
    else:
        print("  ⚠️  WARNING: All decisions are the same (not using predictions?)")
    
    # Show statistics
    print(f"\nPrediction statistics:")
    print(f"  Mean current price: ${pred_log['price'].mean():.2f}")
    if 'expected_future_price' in pred_log.columns:
        print(f"  Mean expected future price: ${pred_log['expected_future_price'].mean():.2f}")
        print(f"  Mean expected return: {pred_log['expected_return'].mean():.3f}")
        print(f"  Mean net benefit: {pred_log['net_benefit'].mean():.3f}")
    
    # Show sample decisions
    print(f"\nSample decisions (first 10 with predictions):")
    display_cols = ['day', 'price', 'expected_future_price', 'net_benefit', 'decision']
    available_cols = [c for c in display_cols if c in pred_log.columns]
    display(pred_log[available_cols].head(10))
else:
    print("\n✗ CRITICAL: No decisions made with predictions!")
```

## Step 7: Verify Predictions Are Being Used


```python
print("\n" + "="*80)
print("PREDICTION USAGE VERIFICATION")
print("="*80)

if len(log_df[log_df['has_predictions']]) > 0:
    pred_log = log_df[log_df['has_predictions']].copy()
    
    # Check correlation between predictions and decisions
    if 'expected_future_price' in pred_log.columns and 'decision' in pred_log.columns:
        # Calculate correlation between expected return and decision
        pred_log['decision_numeric'] = (pred_log['decision'] == 'SELL').astype(int)
        
        if 'net_benefit' in pred_log.columns:
            # Correlation between net_benefit and decision
            # Should be negative: lower benefit → more likely to sell
            corr = pred_log[['net_benefit', 'decision_numeric']].corr().iloc[0, 1]
            print(f"\nCorrelation between net_benefit and SELL decision: {corr:.3f}")
            print(f"(Expected: negative correlation - lower benefit → more selling)")
            
            if corr < -0.3:
                print("✓ PASS: Strong negative correlation - predictions driving decisions!")
            elif corr < 0:
                print("⚠️  Weak correlation - predictions may be having limited impact")
            else:
                print("✗ FAIL: Wrong correlation direction - logic error?")
        
        # Check variance in expected future prices
        future_price_std = pred_log['expected_future_price'].std()
        current_price_std = pred_log['price'].std()
        
        print(f"\nPrice variance:")
        print(f"  Current price std: ${current_price_std:.2f}")
        print(f"  Expected future price std: ${future_price_std:.2f}")
        
        if future_price_std > current_price_std * 0.5:
            print("  ✓ PASS: Predictions show reasonable variance")
        else:
            print("  ⚠️  WARNING: Low prediction variance")
        
        # Check if predictions differ from current price
        pred_log['price_diff'] = pred_log['expected_future_price'] - pred_log['price']
        mean_diff = pred_log['price_diff'].mean()
        std_diff = pred_log['price_diff'].std()
        
        print(f"\nPrediction vs current price:")
        print(f"  Mean difference: ${mean_diff:+.2f}")
        print(f"  Std of difference: ${std_diff:.2f}")
        
        if abs(mean_diff) > 1 or std_diff > 5:
            print("  ✓ PASS: Predictions differ from current prices")
        else:
            print("  ✗ FAIL: Predictions too similar to current prices (data leak?)")
else:
    print("\n✗ CRITICAL: Cannot verify - no predictions used!")
```

## Step 8: Diagnostic Summary


```python
print("\n" + "="*80)
print("DIAGNOSTIC 04 SUMMARY")
print("="*80)

# Collect pass/fail criteria
checks = {}

# Check 1: Date alignment
checks['date_alignment'] = overlap_pct > 90

# Check 2: Prediction coverage
pred_coverage = 100 * strategy.predictions_received / (strategy.predictions_received + strategy.predictions_missing)
checks['prediction_coverage'] = pred_coverage > 80

# Check 3: Beats baseline
checks['beats_baseline'] = advantage > 30000

# Check 4: Decision variety
if len(log_df[log_df['has_predictions']]) > 0:
    pred_log = log_df[log_df['has_predictions']].copy()
    sell_count = len(pred_log[pred_log['decision'] == 'SELL'])
    wait_count = len(pred_log[pred_log['decision'] == 'WAIT'])
    checks['decision_variety'] = (sell_count > 0 and wait_count > 0)
else:
    checks['decision_variety'] = False

print("\nPass/Fail Summary:")
print(f"  {'✓' if checks['date_alignment'] else '✗'} Date alignment: {overlap_pct:.1f}% (need >90%)")
print(f"  {'✓' if checks['prediction_coverage'] else '✗'} Prediction coverage: {pred_coverage:.1f}% (need >80%)")
print(f"  {'✓' if checks['beats_baseline'] else '✗'} Beats baseline: ${advantage:+,.2f} (need >$30k)")
print(f"  {'✓' if checks['decision_variety'] else '✗'} Decision variety: Mix of SELL/WAIT")

all_pass = all(checks.values())

print("\n" + "="*80)
if all_pass:
    print("✓✓✓ DIAGNOSTIC 04 PASS")
    print("="*80)
    print("\nConclusion: Fixes are working! Strategy now uses predictions correctly.")
    print(f"\nFixed strategy achieves ${net_earnings:,.2f} (${advantage:+,.2f} vs baseline)")
    print("\nNext step: Test all strategies (diagnostic_05)")
else:
    failed_checks = [k for k, v in checks.items() if not v]
    print("⚠️⚠️⚠️ DIAGNOSTIC 04 PARTIAL FAIL")
    print("="*80)
    print(f"\nFailed checks: {', '.join(failed_checks)}")
    print("\nSome fixes may need adjustment. Review decision log above.")
    print("\nNext step: Analyze specific failures and iterate on fixes")
```
