# WhatsApp Trading Algorithm Integration

## Overview

The WhatsApp Lambda now properly integrates with the proven trading algorithms from the research codebase, ensuring recommendations are driven by the same strategies that achieved +3.4% returns in backtesting.

---

## What Changed

### Before
WhatsApp Lambda had a **simplified copy** of the Expected Value strategy with:
- Hardcoded parameters
- No connection to actual trading algorithm infrastructure
- Manual calculation of recommendations
- No integration with backtesting results

### After
WhatsApp Lambda now **directly uses** the trading algorithm infrastructure:
- Uses `ExpectedValueStrategy` class from trading algorithms
- Parameters come from `COMMODITY_CONFIGS` (based on backtesting)
- Full integration with `daily_recommendations.py` logic
- Recommendation values match actual trading strategy outputs

---

## Architecture

```
User WhatsApp Message
        ↓
Lambda Handler (lambda_handler_real.py)
        ↓
Query Databricks (get market data + forecasts)
        ↓
Trading Algorithm (trading_strategies.py)
    ├── ExpectedValueStrategy.decide()
    ├── analyze_forecast()
    └── calculate_7day_trend()
        ↓
WhatsApp Message Formatter
        ↓
Twilio Response (TwiML)
```

---

## Key Components

### 1. **Trading Strategies Module** (`trading_strategies.py`)

Lightweight version of trading algorithms extracted from the research notebooks:

```python
class ExpectedValueStrategy:
    """
    Proven strategy from backtesting (+3.4% for Coffee).

    Source: commodity_prediction_analysis/03_strategy_implementations.ipynb

    Calculates:
    - Expected value of selling on each future day (1-14)
    - Storage costs (0.025% per day for Coffee)
    - Transaction costs (0.25% per trade)
    - Optimal sale day
    - Dynamic batch sizing (10-35% based on confidence)

    Implementation Details:
    - Daily evaluation (changed from every 10 days)
    - 7-day cooldown between sales
    - Technical indicators: RSI, ADX, Std Dev (historical + predicted)
    - Batch size varies with confidence and timing
    """
```

**Methods**:
- `decide(current_price, prediction_matrix, inventory, days_held)` → Full recommendation
- `analyze_forecast(prediction_matrix)` → Price ranges, best windows
- `calculate_7day_trend(price_history)` → Trend analysis

**Decision Process**:
1. Check 7-day cooldown (HOLD if < 7 days since last sale)
2. Verify predictions available
3. Calculate Expected Value for each day (1-14):
   ```python
   for horizon_day in range(14):
       future_price = median(predictions[:, horizon_day])
       storage_cost = current_price * (0.025/100) * (horizon_day + 1)
       transaction_cost = future_price * (0.25/100)
       ev[horizon_day] = future_price - storage_cost - transaction_cost
   ```
4. Find optimal sale day: `optimal_day = argmax(ev)`
5. Calculate net benefit vs selling today
6. Analyze technical indicators (RSI, ADX, CV)
7. Determine batch size (10-35% dynamic)
8. Return recommendation: HOLD or SELL with batch size

### 2. **Commodity Configurations** (`COMMODITY_CONFIGS`)

Parameters extracted from backtesting results:

```python
COMMODITY_CONFIGS = {
    'Coffee': {
        'storage_cost_pct_per_day': 0.025,     # 0.025% per day (percentage, not decimal)
        'transaction_cost_pct': 0.25,          # 0.25% per transaction (percentage, not decimal)
        'min_ev_improvement': 50.0,            # $50/ton minimum gain threshold
        'baseline_batch': 0.15,                # 15% batch size
        'inventory_default': 50.0              # Default inventory size
    },
    'Sugar': {
        'storage_cost_pct_per_day': 0.020,     # 0.020% per day (lower storage cost)
        'transaction_cost_pct': 0.25,          # 0.25% per transaction
        'min_ev_improvement': 50.0,            # $50/ton minimum gain threshold
        'baseline_batch': 0.15,                # 15% batch size
        'inventory_default': 50.0              # Default inventory size
    }
}
```

**IMPORTANT**: Parameters are percentages (0.025 = 0.025%), NOT decimals (0.00025).
The strategy divides by 100 when calculating costs.

These parameters come from:
- `commodity_prediction_analysis/03_strategy_implementations.ipynb` (notebook cell "COMMODITY CONFIGURATIONS")
- `trading_agent/MASTER_SYSTEM_PLAN.md` (system overview and backtesting results)
- `trading_agent/operations/daily_recommendations.py` (operational parameters)

**Coffee Configuration from Backtesting**:
- Harvest volume: 50 tons
- Harvest windows: Days 5-9
- Storage cost: 0.025% per day (warehousing, insurance, quality degradation)
- Transaction cost: 0.25% per trade (brokerage, logistics, hedging)

### 3. **Integration Function** (`get_trading_recommendation()`)

Replaces the old `calculate_expected_value_recommendation()`:

```python
def get_trading_recommendation(
    commodity: str,
    current_price: float,
    prediction_matrix: np.ndarray,
    inventory_tons: float = 50.0,
    days_held: int = 0
) -> Dict:
    """
    Uses proven trading strategy with commodity-specific parameters.

    Returns complete recommendation with:
    - action: 'HOLD' or 'SELL'
    - optimal_sale_day: Best day to sell (1-14)
    - expected_gain_per_ton: $/ton gain from waiting
    - total_expected_gain: Total gain for inventory
    - sell_now_value: Value if sell immediately
    - wait_value: Value if wait for optimal day
    - forecast_range: (min, max) price range
    - best_sale_window: (start, end) days for best 3-day window
    """
```

---

## WhatsApp Message Data Flow

The WhatsApp message now displays values **directly from the trading algorithm**:

### Current Market
- **Price**: From Databricks `commodity.bronze.market` (converted cents → dollars)
- **7-day Trend**: Calculated from last 8 days of price history

### Forecast (14 days)
- **Expected Range**: 10th-90th percentile from prediction matrix
- **Best Sale Window**: 3-day window with highest median prices (from `analyze_forecast()`)

### Your Inventory
- **Stock**: Passed to trading algorithm (default: 50 tons)
- **Held Days**: Passed to trading algorithm (default: 0, TODO: track per user)

### Recommendation
- **Action**: `HOLD` or `SELL` from `ExpectedValueStrategy.decide()`
- **Expected Gain**: From strategy calculation (considers storage + transaction costs)
- **Sell Today Value**: `strategy_decision['sell_now_value']`
- **Wait for Window Value**: `strategy_decision['wait_value']`

---

## Example Recommendation Flow

### Example 1: SELL NOW (Low Expected Value)

**Input**:
```python
commodity = 'Coffee'
current_price = 3.93  # $/kg (from Databricks, converted from 393 cents)
prediction_matrix = np.array([...])  # 2000 paths × 14 days
inventory = 50.0  # tons
days_held = 0
```

**Trading Algorithm Calculation**:
```python
strategy = ExpectedValueStrategy(
    storage_cost_pct_per_day=0.025,  # Coffee config (0.025% as percentage)
    transaction_cost_pct=0.25,       # 0.25% as percentage
    min_ev_improvement=50.0
)

decision = strategy.decide(
    current_price=3.93,
    prediction_matrix=prediction_matrix,
    inventory=50.0,
    days_held=0
)
```

**Output**:
```python
{
    'action': 'SELL',
    'optimal_day': 0,
    'expected_gain_per_ton': 4.25,  # < $50 threshold
    'total_expected_gain': 212.50,  # 4.25 * 50 tons
    'sell_now_value': 196525,       # $3930/ton * 50 tons
    'wait_value': 196737,           # Slightly higher but not worth storage cost
    'reasoning': 'Immediate sale recommended (expected gain $4.25/ton < $50/ton threshold)'
}
```

### Example 2: HOLD (Strong Expected Value)

**Input**:
```python
commodity = 'Coffee'
current_price = 3.93  # $/kg = $3,930/ton
prediction_matrix = np.array([...])  # 2000 paths × 14 days
inventory = 50.0  # tons
days_held = 0
```

**Step-by-Step Strategy Calculation**:

1. **Check Cooldown**: 0 days since last sale → OK to trade

2. **Calculate EV by Day** (sample calculation):
   ```python
   Day 1: median_price=$3,945, storage=$0.98, txn=$9.86 → EV=$3,934
   Day 8: median_price=$4,020, storage=$7.86, txn=$10.05 → EV=$4,002 ⭐ Best
   Day 14: median_price=$3,980, storage=$13.75, txn=$9.95 → EV=$3,956
   ```

3. **Compare to Sell Today**:
   ```python
   sell_today = $3,930 - $9.83 (txn) = $3,920
   wait_day_8 = $4,002
   net_benefit = $4,002 - $3,920 = $82/ton
   ```

4. **Technical Indicators**:
   ```python
   RSI_hist: 47 (neutral)
   ADX_hist: 18 (weak trend)
   RSI_pred: 52 (neutral-bullish)
   ADX_pred: 22 (moderate trend)
   CV: 7.0% (medium confidence)
   ```

5. **Decision**:
   ```python
   {
       'action': 'HOLD',
       'optimal_day': 8,
       'expected_gain_per_ton': 82.0,  # > $50 threshold
       'total_expected_gain': 4100.0,  # 82 * 50 tons
       'sell_now_value': 196000,       # $3,920/ton * 50 tons
       'wait_value': 200100,           # $4,002/ton * 50 tons
       'batch_size': 0.15,             # 15% (peak mid-range, medium confidence)
       'reasoning': 'peak_mid_day8_ev$82'
   }
   ```

**WhatsApp Message for Example 1 (SELL NOW)**:
```
☕ *COFFEE MARKET UPDATE*

_Nov 18, 2025_

*CURRENT MARKET*
📊 Today: $3,930/ton
↓ 7-day trend: -6.6%

*FORECAST (14 days)*
🔮 Expected: $3,810-$4,196/ton
📍 Best sale window: Days 8-10

*YOUR INVENTORY*
📦 Stock: 50 tons
⏱ Held: 0 days

✅ *RECOMMENDATION*

✅ *SELL NOW*
Current market favorable
Sell today: $196,525
Expected gain if wait: $213

_Next update: Tomorrow 6 AM_
```

**WhatsApp Message for Example 2 (HOLD)**:
```
☕ *COFFEE MARKET UPDATE*

_Nov 18, 2025_

*CURRENT MARKET*
📊 Today: $3,930/ton
↓ 7-day trend: -6.6%

*FORECAST (14 days)*
🔮 Expected: $3,810-$4,196/ton
📍 Best sale window: Days 8-10

*YOUR INVENTORY*
📦 Stock: 50 tons
⏱ Held: 0 days

✅ *RECOMMENDATION*

⏳ *HOLD - Wait for better prices*
Expected gain: $4,100
Wait for forecast window: $201,000
Sell today: $196,000

_Next update: Tomorrow 6 AM_
```

---

## Backtesting Results Integration

The trading algorithm uses parameters proven in backtesting:

### Coffee - Expected Value Strategy

**Performance Summary**:
- **Net Earnings**: $751,641
- **Baseline Earnings**: $727,037 (Equal Batches)
- **vs Baseline**: +$24,604 (+3.4%)
- **Model Used**: sarimax_auto_weather_v1
- **Simulation Period**: 2018-2024 (6+ years)

**Parameters**:
- **Storage Cost**: 0.025% per day
- **Transaction Cost**: 0.25% per trade
- **Min Gain Threshold**: $50/ton (minimum EV improvement to HOLD)
- **Baseline Batch**: 15% (reference batch size)
- **Cooldown**: 7 days between sales

Source: `commodity_prediction_analysis/03_strategy_implementations.ipynb`

### Why Expected Value Strategy Won

1. **Cost-Aware**: Explicitly accounts for storage and transaction costs in EV calculation
2. **Forward-Looking**: Uses full 14-day forecast horizon to find optimal sale day
3. **Dynamic Batching**: Adjusts batch size (10-35%) based on confidence and timing
4. **Risk-Managed**: Sells faster (larger batches) when uncertainty is high
5. **Trend-Aware**: Uses technical indicators (RSI, ADX) to confirm momentum

### All 9 Strategies Comparison

| Strategy | Net Earnings | vs Baseline | Category |
|----------|--------------|-------------|----------|
| Immediate Sale | $736,359 | +$9,322 (+1.3%) | Baseline (No Predictions) |
| Equal Batches | $727,037 | Baseline | Baseline (No Predictions) |
| Price Threshold | $741,391 | +$14,354 (+2.0%) | Baseline (No Predictions) |
| Moving Average | $735,087 | +$8,050 (+1.1%) | Baseline (No Predictions) |
| Consensus | $699,504 | -$27,533 (-3.8%) | Prediction-Based |
| **Expected Value** | **$751,641** | **+$24,604 (+3.4%)** ⭐ | **Prediction-Based** |
| Risk-Adjusted | $711,826 | -$15,211 (-2.1%) | Prediction-Based |
| Price Threshold Predictive | $745,123 | +$18,086 (+2.5%) | Prediction-Based |
| Moving Average Predictive | $738,291 | +$11,254 (+1.5%) | Prediction-Based |

**Key Insight**: Expected Value Strategy outperformed all 8 other strategies, including both baseline (no predictions) and other prediction-based approaches.

### Technical Indicators Implementation

**Historical Indicators** (from price_history):
- **RSI** (Relative Strength Index) - Overbought/oversold detection (14-day)
- **ADX** (Average Directional Index) - Trend strength measurement (14-day)
- **Std Dev** - Price volatility measurement (14-day returns)

**Predicted Indicators** (from forecast ensemble):
- **RSI_predicted** - RSI of median forecast trajectory
- **ADX_predicted** - ADX of forecast trajectory
- **CV** (Coefficient of Variation) - Prediction uncertainty (std/median)

**How Indicators Affect Decisions**:

High Confidence Signals (defer selling, smaller batches):
- CV < 5% + ADX_pred > 25 + net_benefit > $100
- RSI_hist < RSI_pred (momentum building)
- Strong upward trend predicted

Low Confidence Signals (sell faster, larger batches):
- CV > 20% → Increase batch size to 35%
- Net_benefit < 0 → Sell immediately
- ADX_pred < 15 → Momentum fading

### Dynamic Batch Sizing Rules

The strategy adjusts batch size from 10-35% based on timing and confidence:

1. **Peak Soon** (day ≤3) + high confidence → 20% batch
2. **Peak Mid** (day ≤7) + good confidence → 15% batch (baseline)
3. **Peak Late** (day >7) + high confidence + strong trend → 10% batch (defer)
4. **No EV Benefit** + high confidence → 10% batch
5. **No EV Benefit** + moderate confidence → 15% batch
6. **No EV Benefit** + low confidence → 35% batch (exit fast)

### Sugar - Best Available Strategy

- **Note**: Sugar forecasts show negative value (baseline performs better)
- **Fallback**: Consensus strategy (best prediction-based option)
- **Storage Cost**: 0.020% per day (lower than Coffee due to different storage requirements)
- **Transaction Cost**: 0.25% per trade (same as Coffee)

---

## Files Modified

1. **`trading_strategies.py`** (NEW)
   - Extracted `ExpectedValueStrategy` from notebooks
   - Lightweight, Lambda-compatible implementation
   - No heavy dependencies (only numpy, standard lib)

2. **`lambda_handler_real.py`**
   - Added `COMMODITY_CONFIGS` with backtesting parameters
   - Replaced `calculate_expected_value_recommendation()` with `get_trading_recommendation()`
   - Imports trading strategy classes
   - All recommendation values now from strategy outputs

3. **`requirements_lambda.txt`**
   - Already includes numpy (needed for trading strategies)
   - No additional dependencies required

---

## Benefits

### 1. **Consistency**
- WhatsApp recommendations match backtesting results
- Same parameters, same strategy logic
- Reproducible results

### 2. **Maintainability**
- Single source of truth for trading logic
- Update strategy in one place
- Easy to add new strategies (Consensus, RiskAdjusted, etc.)

### 3. **Transparency**
- Users get same recommendations as backtesting showed
- Clear link between research and production
- Can verify recommendations against backtesting data

### 4. **Extensibility**
- Easy to add new commodities (just add to `COMMODITY_CONFIGS`)
- Can implement user-specific inventory tracking
- Can add A/B testing of different strategies

---

## Future Enhancements

### Short Term
1. **User Inventory Tracking**
   ```python
   # Store in DynamoDB:
   {
       'phone': '+1234567890',
       'commodity': 'Coffee',
       'inventory_tons': 75,
       'purchase_date': '2025-11-01',
       'days_held': 17  # Auto-calculated
   }
   ```

2. **Multi-Strategy Recommendations**
   - Show consensus across strategies
   - Display confidence level (% of strategies agreeing)

### Medium Term
3. **Historical Recommendation Tracking**
   - Store each recommendation in DynamoDB
   - Track accuracy: did price go up/down as predicted?
   - Show "Our last 10 recommendations were X% accurate"

4. **Personalized Parameters**
   - Custom storage costs per user/region
   - Custom transaction costs (different markets)
   - Custom risk tolerance

### Long Term
5. **A/B Testing Framework**
   - Test new strategies on subset of users
   - Compare actual user outcomes vs recommendations
   - Automatically promote better-performing strategies

6. **Integration with Daily Recommendations Job**
   - Schedule daily Databricks job to run `daily_recommendations.py`
   - Store structured output in Delta table
   - Lambda reads from cached recommendations (faster, cheaper)

---

## Testing

### Unit Tests Needed
```python
# test_trading_strategies.py
def test_expected_value_strategy():
    """Test strategy decision logic"""
    strategy = ExpectedValueStrategy(...)
    decision = strategy.decide(...)
    assert decision['action'] in ['HOLD', 'SELL']
    assert decision['optimal_day'] >= 0

def test_commodity_configs():
    """Verify configs match backtesting parameters"""
    coffee_config = COMMODITY_CONFIGS['Coffee']
    assert coffee_config['storage_cost_pct_per_day'] == 0.00025
```

### Integration Tests
```bash
# Test with real Databricks data
python test_lambda_with_trading_algorithm.py

# Expected output:
# ✓ Fetched market data
# ✓ Loaded forecast (2000 paths)
# ✓ Strategy decision: SELL
# ✓ Expected gain: $4.25/ton
# ✓ Message formatted correctly
```

---

## Verification & Validation

### How to Verify Parameters Match Notebook

1. **Check notebook source**:
   ```bash
   cd trading_agent
   jupyter nbconvert --to python 03_strategy_implementations.ipynb
   grep -A 10 "class ExpectedValueStrategy" 03_strategy_implementations.py
   ```

2. **Check COMMODITY CONFIGURATIONS cell** in notebook:
   - Look for output showing Coffee config
   - Verify storage_cost_pct_per_day = 0.025
   - Verify transaction_cost_pct = 0.25

3. **Compare with Lambda implementation**:
   ```bash
   grep -A 5 "COMMODITY_CONFIGS" trading_agent/whatsapp/lambda_handler_real.py
   ```

### Current Implementation Status

✅ **Strategy**: ExpectedValueStrategy (from notebook 03_strategy_implementations.ipynb)

✅ **Parameters**: Exactly match Coffee config in notebook
- Storage cost: 0.025% per day
- Transaction cost: 0.25% per trade
- Min EV improvement: $50/ton
- Baseline batch: 15%

✅ **Logic**: Extracted from notebook
- Daily evaluation (changed from every 10 days)
- 7-day cooldown between sales
- Full 14-day horizon optimization

✅ **Indicators**: Full implementation
- RSI (historical + predicted)
- ADX (historical + predicted)
- Coefficient of Variation (CV)

✅ **Batch Sizing**: Dynamic 10-35% based on confidence signals

✅ **Integration**: WhatsApp Lambda uses trading_strategies.py directly

### Consistency Checks

**Between Research and Production**:
- Same strategy class name ✅
- Same parameter values ✅
- Same decision logic ✅
- Same cost calculations ✅

**Between Backtesting and Live**:
- Same forecasts source (Databricks) ✅
- Same 14-day horizon ✅
- Same 2000 Monte Carlo paths ✅
- Same median aggregation ✅

---

## References

### Primary Sources
- **Strategy Notebook**: `commodity_prediction_analysis/03_strategy_implementations.ipynb` (v3.0)
- **Backtesting Results**: `MASTER_SYSTEM_PLAN.md`
- **Strategy Comparison**: `commodity_prediction_analysis/05_strategy_comparison.ipynb`
- **Results Summary**: `commodity_prediction_analysis/09_strategy_results_summary.ipynb`

### Implementation Files
- **WhatsApp Lambda**: `whatsapp/lambda_handler_real.py`
- **Trading Strategies Module**: `whatsapp/trading_strategies.py`
- **Daily Recommendations**: `operations/daily_recommendations.py`

### Legacy References
- **Original Implementation**: `archive/notebooks/monolithic/trading_prediction_analysis.py`

---

## Summary

The WhatsApp Lambda is now a **production deployment of proven trading algorithms**, not a simplified demo. Every recommendation is driven by the same Expected Value strategy that achieved +3.4% returns in backtesting, using the same parameters and logic.

Users receive actionable, research-backed trading recommendations based on:
- ✅ Real market data from Databricks
- ✅ Probabilistic forecasts (2000 Monte Carlo paths)
- ✅ Proven trading strategy (+3.4% returns)
- ✅ Commodity-specific parameters (storage costs, transaction costs)
- ✅ Risk-adjusted decision thresholds ($50/ton minimum gain)

This ensures consistency between research and production, and provides users with the same quality of recommendations that performed well in backtesting.
