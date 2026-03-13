# WhatsApp Trading Strategy - Source & Implementation

## Which Strategy is Being Used?

**ExpectedValueStrategy** from `03_strategy_implementations.ipynb`

This is the strategy that achieved **+3.4% (+$24,604) over baseline** for Coffee in backtesting.

---

## Source Location

```
/Users/markgibbons/capstone/ucberkeley-capstone/trading_agent/
    commodity_prediction_analysis/03_strategy_implementations.ipynb
```

**Notebook Version**: 3.0 (Enhanced with Indicators)
**Last Updated**: Nov 15, 2024

---

## Strategy Details

### From Backtesting Notebook

```python
class ExpectedValueStrategy(Strategy):
    """
    Standalone Prediction Strategy: Expected Value with Full Indicators

    CHANGES FROM ORIGINAL:
    - Changed: Daily evaluation (was every 10 days)
    - Added: RSI_historical, ADX_historical, Std_dev_historical
    - Added: RSI_predicted, ADX_predicted, Std_dev_predictions
    - Kept: Cost-benefit (already existed)
    - Changed: Batch 10-35% based on EV and confidence

    CONSTRUCTOR: UNCHANGED (already had cost parameters)
    """

    def __init__(self, storage_cost_pct_per_day, transaction_cost_pct,
                 min_ev_improvement=50, baseline_batch=0.15, baseline_frequency=10):
        super().__init__("Expected Value")
        self.storage_cost_pct_per_day = storage_cost_pct_per_day  # 0.025 (not 0.00025!)
        self.transaction_cost_pct = transaction_cost_pct          # 0.25 (not 0.0025!)
        self.min_ev_improvement = min_ev_improvement              # $50/ton
        self.baseline_batch = baseline_batch                       # 15%
        self.cooldown_days = 7  # Changed from implicit 10 to explicit 7
```

### Parameters from Backtesting

**Coffee Configuration** (from notebook cell output):
```json
{
  "commodity": "coffee",
  "harvest_volume": 50,
  "harvest_windows": [[5, 9]],
  "storage_cost_pct_per_day": 0.025,  // 0.025% per day
  "transaction_cost_pct": 0.25        // 0.25% per transaction
}
```

**ExpectedValue Strategy Parameters**:
```json
{
  "min_ev_improvement": 50,      // $50/ton minimum to HOLD
  "baseline_batch": 0.15,        // 15% batch size
  "baseline_frequency": 10       // Reference only (daily eval used)
}
```

---

## How It Works

### Decision Process (Daily Evaluation)

1. **Check Cooldown** (7 days between sales)
   - If < 7 days since last sale → HOLD

2. **Check Predictions Available**
   - If no predictions and >30 days → SELL 15%
   - If no predictions → HOLD

3. **Calculate Expected Value for Each Day (1-14)**
   ```python
   for horizon_day in range(14):
       future_price = median(predictions[:, horizon_day])
       storage_cost = current_price * (0.025/100) * (horizon_day + 1)
       transaction_cost = future_price * (0.25/100)
       ev[horizon_day] = future_price - storage_cost - transaction_cost
   ```

4. **Find Optimal Sale Day**
   ```python
   optimal_day = argmax(ev)
   net_benefit = max(ev) - (current_price - transaction_cost_today)
   ```

5. **Analyze with Technical Indicators**
   - **Historical**: RSI, ADX, Std Dev from price history
   - **Predicted**: RSI, ADX, CV from prediction ensemble

6. **Determine Batch Size** (10-35% dynamic)
   - Peak soon (day ≤3) + high confidence → 20%
   - Peak mid (day ≤7) + good confidence → 15%
   - Peak late (day >7) + high confidence + strong trend → 10% (defer)
   - No EV benefit + high confidence → 10%
   - No EV benefit + moderate confidence → 15%
   - No EV benefit + low confidence → 35% (exit fast)

---

## WhatsApp Lambda Implementation

### Files

1. **`trading_strategies.py`**
   - Extracted ExpectedValueStrategy from notebook
   - Lightweight, Lambda-compatible
   - No heavy dependencies (only numpy)

2. **`lambda_handler_real.py`**
   - Imports ExpectedValueStrategy
   - Uses COMMODITY_CONFIGS from notebook
   - Calls strategy.decide() for recommendations

### Parameters Used

```python
COMMODITY_CONFIGS = {
    'Coffee': {
        'storage_cost_pct_per_day': 0.025,  # 0.025% (notebook value)
        'transaction_cost_pct': 0.25,        # 0.25% (notebook value)
        'min_ev_improvement': 50.0,          # $50/ton
        'baseline_batch': 0.15,              # 15%
        'inventory_default': 50.0            # tons
    }
}
```

**IMPORTANT**: These are percentages (0.025 = 0.025%), NOT decimals (0.00025).
The strategy divides by 100 when calculating costs.

---

## Backtesting Results

### Coffee - Expected Value Strategy

From `EXECUTION_RESULTS_SUMMARY.md`:

| Metric | Value |
|--------|-------|
| Net Earnings | $751,641 |
| Baseline Earnings | $727,037 |
| **Gain vs Baseline** | **+$24,604** |
| **% Improvement** | **+3.4%** |
| Model Used | sarimax_auto_weather_v1 |
| Simulation Period | 2018-2024 |

### Why ExpectedValue Won

1. **Cost-Aware**: Explicitly accounts for storage and transaction costs
2. **Forward-Looking**: Uses full 14-day forecast horizon
3. **Dynamic**: Adjusts batch size based on confidence and timing
4. **Risk-Managed**: Sells faster when uncertainty is high

### Comparison to Other Strategies

| Strategy | Net Earnings | vs Baseline |
|----------|--------------|-------------|
| Immediate Sale | $736,359 | +$9,322 (+1.3%) |
| Equal Batches | $727,037 | Baseline |
| Price Threshold | $741,391 | +$14,354 (+2.0%) |
| Moving Average | $735,087 | +$8,050 (+1.1%) |
| Consensus | $699,504 | -$27,533 (-3.8%) |
| **Expected Value** | **$751,641** | **+$24,604 (+3.4%)** ⭐ |
| Risk-Adjusted | $711,826 | -$15,211 (-2.1%) |

---

## All 9 Strategies in Notebook

### Baseline (No Predictions)
1. **ImmediateSaleStrategy** - Sell all weekly
2. **EqualBatchStrategy** - Fixed batches on schedule
3. **PriceThresholdStrategy** - Sell when price > MA + 5%
4. **MovingAverageStrategy** - Sell on MA crossover

### Prediction-Based
5. **ConsensusStrategy** - Sell based on prediction consensus
6. **ExpectedValueStrategy** ⭐ - EV optimization (WINNER)
7. **RiskAdjustedStrategy** - Sell based on uncertainty
8. **PriceThresholdPredictive** - Threshold + predictions
9. **MovingAveragePredictive** - MA + predictions

---

## Technical Indicators Used

### Historical (from price_history)
- **RSI** (Relative Strength Index) - Overbought/oversold (14-day)
- **ADX** (Average Directional Index) - Trend strength (14-day)
- **Std Dev** - Price volatility (14-day returns)

### Predicted (from forecast ensemble)
- **RSI_predicted** - RSI of median forecast trajectory
- **ADX_predicted** - ADX of forecast trajectory
- **CV** (Coefficient of Variation) - Prediction uncertainty (std/median)

### How They Affect Decisions

**High Confidence Signals** (defer selling):
- CV < 5% + ADX_pred > 25 + net_benefit > $100
- RSI_hist < RSI_pred (momentum building)

**Low Confidence Signals** (sell faster):
- CV > 20% → Increase batch size
- Net_benefit < 0 → Sell now
- ADX_pred < 15 → Momentum fading

---

## Example Decision Flow

### Input
- Commodity: Coffee
- Current Price: $3.93/kg = $3,930/ton
- Inventory: 50 tons
- Days Held: 0
- Predictions: 2000 paths × 14 days

### Strategy Calculation

1. **Check Cooldown**: 0 days since last sale (OK to trade)

2. **Calculate EV by Day**:
   - Day 1: $3,945 - $0.98 (storage) - $9.86 (txn) = $3,934
   - Day 8: $4,020 - $7.86 (storage) - $10.05 (txn) = $4,002 ⭐ Best
   - Day 14: $3,980 - $13.75 (storage) - $9.95 (txn) = $3,956

3. **Compare to Sell Today**:
   - Sell today: $3,930 - $9.83 (txn) = $3,920
   - Wait for day 8: $4,002
   - **Net Benefit**: $4,002 - $3,920 = $82/ton

4. **Technical Indicators**:
   - RSI_hist: 47 (neutral)
   - ADX_hist: 18 (weak trend)
   - RSI_pred: 52 (neutral-bullish)
   - ADX_pred: 22 (moderate trend)
   - CV: 7.0% (medium confidence)

5. **Decision**:
   - Optimal day: 8
   - Net benefit: $82/ton (> $50 threshold)
   - Confidence: Medium (7% CV)
   - **Action**: SELL 15% (baseline batch)
   - **Reasoning**: "peak_mid_day8_ev$82"

### WhatsApp Message
```
☕ *COFFEE MARKET UPDATE*

*FORECAST (14 days)*
🔮 Expected: $3,810-$4,196/ton
📍 Best sale window: Days 8-10

✅ *RECOMMENDATION*
✅ *HOLD - Wait for better prices*
Expected gain: $4,100
Wait for forecast window: $201,000
Sell today: $196,525
```

---

## Verification

### How to Verify Parameters Match Notebook

1. **Check notebook cell output**:
   ```bash
   jupyter nbconvert --to python 03_strategy_implementations.ipynb
   grep -A 10 "class ExpectedValueStrategy" 03_strategy_implementations.py
   ```

2. **Check config cell**:
   Look for "COMMODITY CONFIGURATIONS" output in notebook

3. **Compare with Lambda**:
   ```bash
   grep -A 5 "COMMODITY_CONFIGS" trading_agent/whatsapp/lambda_handler_real.py
   ```

### Current Status

✅ Strategy: ExpectedValueStrategy (from notebook 03)
✅ Parameters: Exactly match Coffee config in notebook
✅ Logic: Extracted from notebook (daily eval, 7-day cooldown)
✅ Indicators: Full implementation (RSI, ADX, CV)
✅ Batch Sizing: Dynamic 10-35% based on signals

---

## References

- **Backtesting Notebook**: `03_strategy_implementations.ipynb`
- **Strategy Comparison**: `05_strategy_comparison.ipynb`
- **Results Summary**: `09_strategy_results_summary.ipynb`
- **Execution Summary**: `EXECUTION_RESULTS_SUMMARY.md`
- **WhatsApp Implementation**: `trading_strategies.py`, `lambda_handler_real.py`

---

## Summary

The WhatsApp Lambda uses the **exact same ExpectedValueStrategy** that achieved **+3.4% returns in backtesting**, with:

- ✅ Same parameters (storage 0.025%/day, transaction 0.25%)
- ✅ Same logic (EV optimization, 7-day cooldown, daily evaluation)
- ✅ Same indicators (RSI, ADX, CV)
- ✅ Same batch sizing (10-35% dynamic)

**Result**: Users receive the same quality of recommendations that outperformed all other strategies in 6+ years of backtesting.
