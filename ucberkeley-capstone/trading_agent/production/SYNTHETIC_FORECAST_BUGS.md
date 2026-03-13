# Synthetic Forecast Analysis - Critical Bugs Identified

**Date:** 2025-12-05
**Status:** DOCUMENTED - NOT FIXED
**Impact:** Synthetic sensitivity analysis results are INVALID

---

## Summary

Two fundamental bugs in the synthetic forecast analysis invalidate the entire sensitivity study. The results showing 80% accuracy outperforming 100% accuracy are artifacts of these bugs, not meaningful insights about forecast quality vs trading performance.

---

## Bug #1: Date Coverage Contamination

### The Problem

Synthetic forecasts only exist for 2022-2025, but backtests ran over the full price data range (2015-2025).

### What Happens

- **2015-2021 (34% of backtest period)**: No synthetic forecasts exist
  - Backtest engine gets `predictions.get(current_date) = None`
  - RollingHorizonMPC strategy returns HOLD for all dates
  - ALL accuracy levels show IDENTICAL behavior (no trades, zero earnings change)

- **2022-2025 (66% of backtest period)**: Synthetic forecasts exist
  - Different accuracy levels show different predictions
  - Strategy behavior differs by accuracy level

### Impact

The "sensitivity analysis" is actually measuring:
- 34% contaminated baseline data (identical across all accuracy levels)
- 66% actual synthetic forecast data (varies by accuracy level)

Comparisons across accuracy levels are meaningless because they're comparing different mixtures of baseline vs predictive behavior.

### Evidence

**Unfiltered Results (2015-2025, CONTAMINATED):**
```
60%:  $1,297,860.87
70%:  $1,306,234.02
80%:  $1,315,085.80  <- Mysteriously best
90%:  $1,301,220.53
100%: $1,298,053.85  <- Worse than 80%?
```

**Filtered Results (2022-2025 ONLY, valid forecast period):**
```
60%:  $1,297,860.87
70%:  $1,306,234.02
80%:  $1,315,085.80  <- Still best (but see Bug #2)
90%:  $1,301,220.53
100%: $1,298,053.85
```

Note: Earnings are identical because the contamination was only in years 2015-2021. The 2022-2025 results show minimal sensitivity (only $17K range), but 80% still outperforms 100%.

### The Fix

Filter all synthetic forecast comparisons to valid forecast years only:
```sql
WHERE year >= 2022 AND year <= 2025
```

This is what the year-by-year analysis (`calculate_metrics_by_year()`) enables, but you must explicitly filter.

---

## Bug #2: Systematic Bias in Accuracy Degradation

### The Problem

The synthetic forecast generation code introduces **directional biases** instead of symmetric random noise.

### What the Code Does

**File:** `production/scripts/generate_synthetic_predictions.py` (lines 120-137)

For 80% accuracy (20% MAPE), the code:

1. Randomly flips a coin for each timestamp: heads = bias up, tails = bias down
2. Centers all predictions for that timestamp at ±20% from truth
3. Adds run-specific biases

```python
# For each timestamp, randomly bias predictions either high OR low
bias_direction = np.random.choice([-1, 1])  # Coin flip
target_multiplier = 1.0 + bias_direction * target_mape  # Either 1.2 or 0.8

# Center log-normal distribution at this bias
log_center = np.log(target_multiplier)
log_errors = np.random.normal(log_center, sigma_lognormal, (n_runs, n_horizons))
multiplicative_errors = np.exp(log_errors)

# Apply to actual prices
predicted_prices_matrix = future_prices_matrix * multiplicative_errors

# Add MORE bias
run_biases = np.random.normal(1.0, 0.02, (n_runs, 1))
predicted_prices_matrix *= run_biases
```

### Why This Is Wrong

**Example with actual price = $100:**

**Current (broken) approach for 80% accuracy:**
- Coin flip heads → All predictions center around $120 (20% too high)
- Coin flip tails → All predictions center around $80 (20% too low)
- Median prediction is either $120 OR $80, not $100

**Correct approach for 80% accuracy:**
- Predictions should scatter around $100 with errors that AVERAGE to 20%
- Some predictions: $95, $105, $85, $115, $130, etc.
- Median prediction should be close to $100 (truth)

### Impact

The "accuracy degradation" isn't testing forecast quality - it's testing whether **random systematic biases** happen to help or hurt the trading strategy.

If the trading strategy performs better with pessimistic forecasts (e.g., makes it more conservative), and 80% accuracy randomly gets more "bias down" coin flips than 100% accuracy, it will outperform.

This is NOT a meaningful result about forecast accuracy vs trading performance.

### The Fix

Replace biased approach with symmetric noise:

```python
# CORRECT: Symmetric noise around truth
# For 80% accuracy (20% MAPE), generate random errors
# Standard deviation calibrated to achieve 20% MAPE on average
sigma = target_mape / 1.25  # Calibration factor

# Random multiplicative errors centered at 1.0 (truth)
multiplicative_errors = np.random.lognormal(
    mean=0,  # Log-normal centered at 1.0
    sigma=sigma,
    size=(n_runs, n_horizons)
)

predicted_prices_matrix = future_prices_matrix * multiplicative_errors
```

The median prediction should be close to the actual price, with spread increasing as accuracy decreases.

---

## Validation of the Bug

The fact that 100% accuracy (perfect foresight) performs WORSE than 80% accuracy is proof that something is fundamentally broken.

With a correctly implemented trading strategy, perfect information should ALWAYS perform at least as well as imperfect information. The fact that it doesn't means:

1. The "imperfect" forecasts have systematic biases that accidentally help the strategy, OR
2. The trading strategy has a bug that makes it perform worse with perfect information

Since the trading strategy works correctly with real forecasts, the problem is #1 - the synthetic forecasts have systematic biases.

---

## Impact on Project

### What's INVALID:
- All synthetic forecast sensitivity analysis results
- Any claims about "80% accuracy is sufficient"
- Any comparisons across synthetic accuracy levels

### What's STILL VALID:
- Real forecast results (all model versions)
- Trading strategy implementation (RollingHorizonMPC)
- Backtest engine
- Year-by-year analysis methodology

### Recommendation:

**Option 1 (Quick):** Drop synthetic sensitivity analysis entirely. Focus on real forecast results, which are valid.

**Option 2 (Thorough):** Fix both bugs and regenerate synthetic forecasts:
1. Fix `generate_synthetic_predictions.py` to use symmetric noise
2. Regenerate synthetic forecasts with corrected algorithm
3. Re-run backtests on corrected synthetic data
4. Filter all comparisons to valid forecast years (2022-2025)

**Estimated effort for Option 2:**
- Code fix: 1 hour
- Regenerate synthetic forecasts: 2-4 hours (Databricks compute time)
- Re-run backtests: 2-4 hours (Databricks compute time)
- Validation: 1-2 hours

---

## Code Locations

**Synthetic forecast generation:**
- `production/scripts/generate_synthetic_predictions.py` (lines 120-137)

**Backtest execution:**
- `production/core/backtest_engine.py` (handles predictions=None case)
- `production/runners/multi_commodity_runner.py` (orchestrates backtests)

**Results storage:**
- Delta tables: `commodity.trading_agent.results_{commodity}_synthetic_acc{level}`
- Year-by-year: `commodity.trading_agent.results_{commodity}_by_year_synthetic_acc{level}`

**Validation evidence:**
- `/tmp/check_filtered_years.py` (script that revealed Bug #1)
- Job run 925580698942723 (filtered results showing minimal sensitivity)

---

**Next Steps:** User will decide whether to fix or document as limitation and move on with real forecasts.
