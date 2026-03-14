# Diagnostic 03: Strategy Decision Logic Trace

**Purpose:** Instrument Expected Value strategy to understand decision-making

**Test Case:** Coffee synthetic_acc90

**Pass Criteria:**
- Strategy receives predictions (not None) on >80% of days
- Mix of SELL and WAIT decisions
- Expected returns vary based on predictions
- Decisions correlate with prediction values


```python
%run ../00_setup_and_config
```


```python
import pandas as pd
import numpy as np
import pickle
import matplotlib.pyplot as plt

print("="*80)
print("DIAGNOSTIC 03: STRATEGY DECISION LOGIC TRACE")
print("="*80)
print("\nTest Case: Coffee synthetic_acc90")
print("Goal: Instrument Expected Value strategy decision logic\n")
```

## Step 1: Create Instrumented Strategy


```python
class InstrumentedExpectedValueStrategy:
    """Expected Value strategy with detailed logging"""
    
    def __init__(self, storage_cost_pct_per_day, transaction_cost_pct, 
                 evaluation_day=7, min_return=0.03):
        self.name = "Expected Value (Instrumented)"
        self.storage_cost_pct_per_day = storage_cost_pct_per_day
        self.transaction_cost_pct = transaction_cost_pct
        self.evaluation_day = evaluation_day
        self.min_return = min_return
        
        # Decision log
        self.decision_log = []
        self.log_count = 0
    
    def should_sell(self, day, inventory, price, predictions, technical_indicators):
        """Decide whether to sell based on expected value (with logging)"""
        
        # Create log entry
        log_entry = {
            'day': day,
            'price': price,
            'inventory': inventory,
            'has_predictions': predictions is not None,
        }
        
        # If no predictions, can't make informed decision
        if predictions is None or len(predictions) == 0:
            log_entry['decision'] = 'WAIT'
            log_entry['reason'] = 'No predictions available'
            log_entry['batch_size'] = 0.0
            self.decision_log.append(log_entry)
            
            # Print first few occurrences
            if self.log_count < 3:
                print(f"\n⚠️  Day {day}: No predictions available")
                self.log_count += 1
            
            return False, 0.0
        
        # Check if we have enough horizon
        log_entry['pred_shape'] = predictions.shape
        
        if predictions.shape[1] <= self.evaluation_day:
            log_entry['decision'] = 'WAIT'
            log_entry['reason'] = f'Insufficient horizon (need {self.evaluation_day}, have {predictions.shape[1]})'
            log_entry['batch_size'] = 0.0
            self.decision_log.append(log_entry)
            return False, 0.0
        
        # Get expected future price
        future_prices = predictions[:, self.evaluation_day]
        expected_future_price = np.mean(future_prices)
        
        # Log prediction details
        log_entry['expected_future_price'] = expected_future_price
        log_entry['pred_min'] = future_prices.min()
        log_entry['pred_max'] = future_prices.max()
        log_entry['pred_std'] = future_prices.std()
        log_entry['sample_predictions'] = future_prices[:5].tolist()
        
        # Calculate expected return
        expected_return = (expected_future_price - price) / price
        log_entry['expected_return'] = expected_return
        
        # Calculate cost to wait
        days_to_wait = self.evaluation_day
        storage_cost = self.storage_cost_pct_per_day * days_to_wait
        transaction_cost = self.transaction_cost_pct
        total_cost = storage_cost + transaction_cost
        
        log_entry['storage_cost'] = storage_cost
        log_entry['transaction_cost'] = transaction_cost
        log_entry['total_cost'] = total_cost
        
        # Net benefit of waiting
        net_benefit = expected_return - total_cost
        log_entry['net_benefit'] = net_benefit
        
        # Decision logic
        if expected_return > total_cost:
            # Wait - future price is higher
            log_entry['decision'] = 'WAIT'
            log_entry['reason'] = f'Wait for higher price (exp_ret={expected_return:.2%} > cost={total_cost:.2%})'
            log_entry['batch_size'] = 0.0
            
            # Print first few WAIT decisions
            if self.log_count < 5:
                print(f"\n✓ Day {day}: WAIT decision")
                print(f"  Current price: ${price:.2f}")
                print(f"  Expected future: ${expected_future_price:.2f}")
                print(f"  Expected return: {expected_return:.2%}")
                print(f"  Cost to wait: {total_cost:.2%}")
                print(f"  Net benefit: {net_benefit:.2%}")
                self.log_count += 1
            
            self.decision_log.append(log_entry)
            return False, 0.0
        else:
            # Sell now - price won't be much higher (or will drop)
            batch_size = 0.25  # 25% batch
            
            log_entry['decision'] = 'SELL'
            log_entry['reason'] = f'Sell now (exp_ret={expected_return:.2%} <= cost={total_cost:.2%})'
            log_entry['batch_size'] = batch_size
            
            # Print first few SELL decisions
            if log_entry['decision'] == 'SELL' and self.log_count < 10:
                print(f"\n✓ Day {day}: SELL decision")
                print(f"  Current price: ${price:.2f}")
                print(f"  Expected future: ${expected_future_price:.2f}")
                print(f"  Expected return: {expected_return:.2%}")
                print(f"  Cost to wait: {total_cost:.2%}")
                print(f"  Batch size: {batch_size:.0%}")
                self.log_count += 1
            
            self.decision_log.append(log_entry)
            return True, batch_size

print("✓ Instrumented Expected Value strategy created")
```

## Step 2: Load Data and Run Backtest


```python
# Load from diagnostic_02 if available, otherwise reload
try:
    # Try to use existing data
    print("Using data from previous diagnostics...")
except:
    # Reload
    COMMODITY = 'coffee'
    MODEL_VERSION = 'synthetic_acc90'
    COMMODITY_CONFIG = COMMODITY_CONFIGS[COMMODITY]
    DATA_PATHS = get_data_paths(COMMODITY, MODEL_VERSION)
    
    print("Loading data...")
    prices = spark.table(get_data_paths(COMMODITY)['prices_prepared']).toPandas()
    prices['date'] = pd.to_datetime(prices['date'])
    
    with open(DATA_PATHS['prediction_matrices'], 'rb') as f:
        prediction_matrices = pickle.load(f)
    prediction_matrices = {pd.to_datetime(k): v for k, v in prediction_matrices.items()}
    
    print(f"✓ Loaded {len(prices)} prices, {len(prediction_matrices)} predictions")
```


```python
# Import backtest engine from diagnostic_02 or create simple version
%run ./04_backtesting_engine

print("\nCreating instrumented strategy...")
strategy = InstrumentedExpectedValueStrategy(
    storage_cost_pct_per_day=COMMODITY_CONFIG['storage_cost_pct_per_day'],
    transaction_cost_pct=COMMODITY_CONFIG['transaction_cost_pct'],
    evaluation_day=7,
    min_return=0.03
)

print("Running backtest...")
engine = BacktestEngine(prices, prediction_matrices, COMMODITY_CONFIG)
results = engine.run(strategy)

print("\n✓ Backtest complete")
```

## Step 3: Analyze Decision Log


```python
print("\n" + "="*80)
print("DECISION LOG ANALYSIS")
print("="*80)

log_df = pd.DataFrame(strategy.decision_log)

print(f"\nTotal decisions: {len(log_df)}")
print(f"\nDecisions with predictions: {log_df['has_predictions'].sum()}")
print(f"Decisions without predictions: {(~log_df['has_predictions']).sum()}")

if len(log_df[log_df['has_predictions']]) > 0:
    pred_log = log_df[log_df['has_predictions']].copy()
    
    print(f"\nDecision breakdown (with predictions):")
    print(pred_log['decision'].value_counts())
    
    # Statistics
    print(f"\nExpected return statistics:")
    print(f"  Mean: {pred_log['expected_return'].mean():.2%}")
    print(f"  Min: {pred_log['expected_return'].min():.2%}")
    print(f"  Max: {pred_log['expected_return'].max():.2%}")
    print(f"  Std: {pred_log['expected_return'].std():.2%}")
    
    print(f"\nCost to wait:")
    print(f"  Mean: {pred_log['total_cost'].mean():.2%}")
    
    print(f"\nNet benefit statistics:")
    print(f"  Mean: {pred_log['net_benefit'].mean():.2%}")
    print(f"  Positive benefit days: {(pred_log['net_benefit'] > 0).sum()}")
    print(f"  Negative benefit days: {(pred_log['net_benefit'] <= 0).sum()}")
    
    # Check if predictions actually vary
    pred_variation = pred_log['expected_future_price'].std()
    price_variation = pred_log['price'].std()
    
    print(f"\nPrice variation:")
    print(f"  Current price std: ${price_variation:.2f}")
    print(f"  Predicted price std: ${pred_variation:.2f}")
    
    if pred_variation < price_variation * 0.1:
        print("  ✗ CRITICAL: Predictions have very low variance!")
        print("  Predictions may all be the same value.")
    elif abs(pred_variation - price_variation) / price_variation < 0.2:
        print("  ✓ PASS: Prediction variation is reasonable")
    
    # Check correlation
    if len(pred_log) > 1:
        corr = pred_log[['price', 'expected_future_price']].corr().iloc[0, 1]
        print(f"\nCorrelation (current vs predicted price): {corr:.3f}")
        
        if corr > 0.99:
            print("  ✗ CRITICAL: Predictions are just current price! (correlation > 0.99)")
        elif corr > 0.95:
            print("  ⚠️  WARNING: Very high correlation (>0.95)")
        elif 0.5 <= corr <= 0.95:
            print("  ✓ PASS: Reasonable correlation (predictions informative but distinct)")
        else:
            print(f"  ⚠️  Unusual correlation: {corr:.3f}")
    
else:
    print("\n✗ CRITICAL: No decisions with predictions!")
    print("Predictions are not reaching the strategy.")
```

## Step 4: Visualize Decision Logic


```python
if len(log_df[log_df['has_predictions']]) > 10:
    pred_log = log_df[log_df['has_predictions']].copy()
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    # Plot 1: Current vs Predicted Price
    ax1 = axes[0, 0]
    ax1.scatter(pred_log['price'], pred_log['expected_future_price'], alpha=0.5)
    ax1.plot([pred_log['price'].min(), pred_log['price'].max()],
             [pred_log['price'].min(), pred_log['price'].max()],
             'r--', label='y=x')
    ax1.set_xlabel('Current Price ($)')
    ax1.set_ylabel('Expected Future Price ($)')
    ax1.set_title('Current vs Predicted Prices')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: Expected Return Distribution
    ax2 = axes[0, 1]
    ax2.hist(pred_log['expected_return'] * 100, bins=30, alpha=0.7, edgecolor='black')
    ax2.axvline(x=0, color='red', linestyle='--', label='Zero return')
    ax2.axvline(x=pred_log['total_cost'].mean() * 100, color='orange', 
                linestyle='--', label='Mean cost')
    ax2.set_xlabel('Expected Return (%)')
    ax2.set_ylabel('Frequency')
    ax2.set_title('Distribution of Expected Returns')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # Plot 3: Net Benefit Over Time
    ax3 = axes[1, 0]
    ax3.plot(pred_log['day'], pred_log['net_benefit'] * 100, alpha=0.7)
    ax3.axhline(y=0, color='red', linestyle='--')
    ax3.set_xlabel('Day')
    ax3.set_ylabel('Net Benefit (%)')
    ax3.set_title('Net Benefit of Waiting Over Time')
    ax3.grid(True, alpha=0.3)
    
    # Plot 4: Decision Breakdown
    ax4 = axes[1, 1]
    decision_counts = pred_log['decision'].value_counts()
    ax4.bar(decision_counts.index, decision_counts.values, color=['green', 'red'])
    ax4.set_ylabel('Count')
    ax4.set_title('Decision Breakdown')
    ax4.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig(f'{VOLUME_PATH}/diagnostic_03_decision_analysis.png', dpi=300, bbox_inches='tight')
    print(f"\n✓ Saved visualization: {VOLUME_PATH}/diagnostic_03_decision_analysis.png")
    plt.show()
else:
    print("\n⚠️  Not enough data for visualization")
```

## Step 5: Sample Decision Details


```python
if len(log_df[log_df['has_predictions']]) > 0:
    pred_log = log_df[log_df['has_predictions']].copy()
    
    print("\n" + "="*80)
    print("SAMPLE DECISIONS")
    print("="*80)
    
    # Show 5 SELL and 5 WAIT decisions
    sell_decisions = pred_log[pred_log['decision'] == 'SELL'].head(5)
    wait_decisions = pred_log[pred_log['decision'] == 'WAIT'].head(5)
    
    if len(sell_decisions) > 0:
        print("\nSample SELL decisions:")
        print(sell_decisions[['day', 'price', 'expected_future_price', 'expected_return', 
                              'total_cost', 'net_benefit', 'reason']].to_string())
    
    if len(wait_decisions) > 0:
        print("\nSample WAIT decisions:")
        print(wait_decisions[['day', 'price', 'expected_future_price', 'expected_return', 
                              'total_cost', 'net_benefit', 'reason']].to_string())
```

## Step 6: Diagnostic Summary


```python
print("\n" + "="*80)
print("DIAGNOSTIC 03 SUMMARY")
print("="*80)

# Count key metrics
has_preds = log_df['has_predictions'].sum()
total = len(log_df)
pred_pct = 100 * has_preds / total if total > 0 else 0

# Determine verdict
if has_preds > total * 0.8:
    pred_check = "✓ PASS"
elif has_preds > 0:
    pred_check = "⚠️  PARTIAL"
else:
    pred_check = "✗ FAIL"

print(f"\nPrediction availability: {pred_check} ({pred_pct:.1f}%)")

if len(log_df[log_df['has_predictions']]) > 0:
    pred_log = log_df[log_df['has_predictions']]
    
    # Check decision mix
    decision_counts = pred_log['decision'].value_counts()
    if len(decision_counts) > 1:
        decision_check = "✓ PASS"
    else:
        decision_check = "✗ FAIL"
    
    print(f"Decision variety: {decision_check} ({len(decision_counts)} types)")
    
    # Check correlation
    if len(pred_log) > 1:
        corr = pred_log[['price', 'expected_future_price']].corr().iloc[0, 1]
        if corr > 0.99:
            corr_check = "✗ FAIL (predictions = current price)"
        elif 0.5 <= corr <= 0.95:
            corr_check = "✓ PASS"
        else:
            corr_check = "⚠️  UNUSUAL"
        
        print(f"Prediction correlation: {corr_check} ({corr:.3f})")

print("\n" + "="*80)

if pred_check == "✓ PASS" and (decision_check == "✓ PASS" if has_preds > 0 else True):
    print("✓✓✓ DIAGNOSTIC 03 PASS")
    print("\nConclusion: Strategy IS receiving and using predictions correctly")
    print("\nIf results still show losses, the issue is likely:")
    print("  1. Decision logic is correct but predictions are bad quality")
    print("  2. Costs are too high relative to prediction edge")
    print("  3. Parameters (evaluation_day, min_return) need tuning")
elif has_preds == 0:
    print("✗✗✗ DIAGNOSTIC 03 CRITICAL FAIL")
    print("\nConclusion: Predictions NOT reaching strategy")
    print("\nThis confirms the bug is in the backtest engine (diagnostic_02)")
else:
    print("⚠️⚠️⚠️ DIAGNOSTIC 03 PARTIAL FAIL")
    print("\nConclusion: Strategy receives some predictions but has issues")
    print("Review the detailed logs above to identify specific problems.")

print("\nNext step: Create fixed strategies (diagnostic_04)")
```
