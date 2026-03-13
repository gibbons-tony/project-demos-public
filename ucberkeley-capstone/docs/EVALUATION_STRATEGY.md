# Evaluation Strategy

**Goal**: Demonstrate ML engineering excellence through rigorous, statistically sound evaluation.

## Philosophy

This project prioritizes:
1. **Proving the approach generalizes** (not just one lucky model)
2. **Statistical significance** over raw accuracy numbers
3. **Beating baselines** (naive, random walk) with confidence
4. **Robust backtesting** without data leakage
5. **Performance monitoring** for production degradation

## Baselines - Multi-Level Comparison

```
Naive Persistence → Random Walk → ARIMA → SARIMAX → Advanced Models
    (weakest)                                              (strongest)
```

### Baseline Models

1. **Naive Persistence**: Tomorrow = Today
   - Simplest possible forecast
   - Surprisingly hard to beat for many time series

2. **Random Walk with Drift**: Tomorrow = Today + avg_drift + noise
   - Accounts for long-term trends
   - Industry-standard baseline

3. **ARIMA(1,1,1)**: Classical statistical approach
   - Fixed parameters
   - No covariates

4. **SARIMAX (auto-fitted)**: Our initial target
   - Auto-selected (p,d,q)
   - Weather covariates
   - Covariate projection strategies

## Backtesting Strategy - Walk-Forward Validation

### Approach

**Not allowed**: Train on all data, test on last N days (data leakage risk)

**Correct**: Walk-forward with dynamic cutoff_date

```python
# Generate cutoff dates - weekly over 2 years
end_date = datetime.now() - timedelta(days=14)  # Leave forecast horizon
start_date = end_date - timedelta(days=730)  # 2 years back

cutoff_dates = pd.date_range(start=start_date, end=end_date, freq='W')

# For each cutoff date:
for cutoff in cutoff_dates:  # ~104 test points
    # 1. Train on data up to cutoff (no future data)
    model.fit(df, cutoff_date=cutoff)

    # 2. Forecast 14 days ahead
    forecast = model.predict(horizon=14)

    # 3. Compare with actual (7-day ahead for consistency)
    actual = get_actual(cutoff + timedelta(days=7))

    # 4. Calculate errors
    errors.append(forecast_day_7 - actual)
```

### Why Weekly?

- **~104 independent test points** over 2 years
- Balances sample size vs computational cost
- Avoids autocorrelation in errors (7 days apart)
- Statistically sufficient for significance tests

### Alternative Strategies by Model Type

**SARIMAX/ARIMA**: Weekly backtesting (rolling window)
- Retrain every week
- Computationally feasible

**Transformers/TimesFM**: Longer holdout periods
- Too expensive to retrain weekly
- Use 6-month training windows with quarterly updates
- Holdout: Q1 2024 for training, Q2 2024 for testing

## Data Leakage Prevention

### Automatic Detection

```python
# forecast_writer.py checks on every write
def write_point_forecasts(forecasts_df, model_metadata):
    # CRITICAL: Detect leakage
    leakage = forecasts_df.filter(
        f"forecast_date <= '{model_metadata['training_cutoff_date']}'"
    )

    if leakage.count() > 0:
        raise ValueError(f"DATA LEAKAGE: {leakage.count()} forecasts")

    # Add metadata
    forecasts_df = forecasts_df.withColumn(
        "training_cutoff_date",
        lit(model_metadata['training_cutoff_date'])
    )

    # Write
    forecasts_df.write.mode("append").saveAsTable(...)
```

### Manual Checks

```sql
-- Verify no leakage in stored forecasts
SELECT COUNT(*) as leakage_count
FROM commodity.forecast.point_forecasts
WHERE forecast_date <= training_cutoff_date;

-- Should ALWAYS return 0
```

## Evaluation Metrics

### Accuracy Metrics

| Metric | Description | Threshold |
|--------|-------------|-----------|
| **RMSE** | Root Mean Squared Error | < Naive RMSE |
| **MAE** | Mean Absolute Error | < Naive MAE |
| **MAPE** | Mean Absolute % Error | < 10% |
| **Directional Accuracy** | % correct up/down | > 55% (baseline: 54.95%) |

### Statistical Significance Tests

```python
# 1. Paired t-test: Are our errors smaller than baseline?
from scipy import stats

our_errors = abs(our_forecasts - actuals)
baseline_errors = abs(baseline_forecasts - actuals)

t_stat, p_value = stats.ttest_rel(our_errors, baseline_errors, alternative='less')

if p_value < 0.05:
    print(f"✓ Significantly better than baseline (p={p_value:.4f})")
```

```python
# 2. Diebold-Mariano test: Forecast accuracy comparison
from statsmodels.stats.diagnostic import DieboldMariano

dm_stat, dm_p = DieboldMariano(our_errors, baseline_errors)

if dm_p < 0.05:
    print(f"✓ Superior forecast accuracy (DM p={dm_p:.4f})")
```

```python
# 3. Binomial test: Directional accuracy better than 50%?
correct_directions = sum(sign(forecast - prev) == sign(actual - prev))
total = len(forecasts)

binom_test = stats.binom_test(correct_directions, total, 0.5, alternative='greater')

if binom_test < 0.05:
    print(f"✓ Directional accuracy: {correct_directions/total:.1%} (p={binom_test:.4f})")
```

### Calibration Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| **Brier Score** | Probability calibration quality | < 0.20 |
| **Coverage** | % actuals within 95% CI | 90-95% |

## Performance Regression Monitoring

### Concept

Monitor model performance over time to detect when retraining is needed.

### Implementation

```python
class PerformanceMonitor:
    def check_regression(self, model_version, window_days=30):
        """
        Compare recent performance (last 30 days) vs baseline (30-60 days ago)
        """

        # Get recent forecast errors
        recent_errors = get_errors(days_back=window_days)
        baseline_errors = get_errors(days_back=60, days_forward=30)

        # Statistical test
        stat, p_value = stats.mannwhitneyu(
            recent_errors,
            baseline_errors,
            alternative='greater'  # Are recent errors worse?
        )

        # Calculate degradation
        recent_mae = recent_errors.mean()
        baseline_mae = baseline_errors.mean()
        degradation_pct = ((recent_mae - baseline_mae) / baseline_mae) * 100

        # Alert thresholds
        regression_detected = (p_value < 0.05 and degradation_pct > 10)

        if regression_detected:
            alert_level = "critical" if degradation_pct > 25 else "warning"
            return {
                "status": "RETRAIN_NEEDED",
                "alert_level": alert_level,
                "degradation_pct": degradation_pct,
                "p_value": p_value
            }
        else:
            return {"status": "OK"}
```

### Alert Thresholds

- **Warning** (10-25% degradation, p < 0.05): Schedule retrain within 1 week
- **Critical** (>25% degradation, p < 0.05): Retrain immediately
- **OK** (<10% or not significant): Continue monitoring

## Model Comparison Framework

### Side-by-Side Comparison

```python
# Compare all models on same test set
results = {}

for model_name in MODELS.keys():
    model = load_model(model_name)
    forecasts = model.predict_on_test_set()
    actuals = load_actuals()

    results[model_name] = {
        "rmse": rmse(forecasts, actuals),
        "mae": mae(forecasts, actuals),
        "directional_acc": directional_accuracy(forecasts, actuals),
        "vs_naive_p": test_vs_baseline(forecasts, naive_forecasts),
        "vs_random_walk_p": test_vs_baseline(forecasts, rw_forecasts)
    }

# Visualize
comparison_df = pd.DataFrame(results).T
comparison_df.plot(kind='bar', ...)
```

### Evaluation Notebook Output

**For AI (text)**:
```
Model Performance Summary:
==========================

sarimax_auto_v1:
  - RMSE: 10.54 (vs Naive: 11.23, p=0.023) ✓ SIGNIFICANT
  - MAE: 8.45 (vs Naive: 9.12, p=0.019) ✓ SIGNIFICANT
  - Directional: 56.3% (p=0.012 vs random) ✓ SIGNIFICANT
  - Recommendation: DEPLOY - beats all baselines

arima_baseline_v1:
  - RMSE: 11.87 (vs Naive: 11.23, p=0.234) ✗ NOT SIGNIFICANT
  - MAE: 9.76 (vs Naive: 9.12, p=0.189) ✗ NOT SIGNIFICANT
  - Directional: 51.2% (p=0.456 vs random) ✗ NOT SIGNIFICANT
  - Recommendation: DO NOT USE - no improvement over naive
```

**For Humans (visuals)**:
- Forecast vs Actual time series plots
- Error distribution histograms
- Performance comparison bar charts
- Calibration plots (predicted vs actual probabilities)

## Documentation of Findings

### Format: Experiment Log

```markdown
# Experiment: SARIMAX Auto-Order vs Fixed (1,1,1)

**Date**: 2024-10-28
**Hypothesis**: Auto-fitting (p,d,q) improves accuracy vs fixed order
**Test Period**: 2022-01-01 to 2024-10-28 (weekly backtesting)

**Results**:
- Auto-order avg (p,d,q): (2.3, 1.0, 1.8)
- RMSE: 10.54 vs 11.23 (improvement: 6.1%)
- Statistical test: p=0.019 (significant)

**Conclusion**: Auto-order provides modest but statistically significant improvement. Deploy.

**Next Steps**: Test with seasonal component (SARIMA)
```

### Living Document

Connor and AI will collaboratively maintain:
- `docs/experiment_log.md` - All experiments with results
- AI uses this to learn what works/doesn't work
- Guides autonomous experimentation decisions

## Autonomous Evaluation Loop

When AI runs autonomously:

1. **Train new model** variant
2. **Run backtesting** (automated)
3. **Compare vs baselines** (statistical tests)
4. **Log results** to experiment_log.md
5. **If significant improvement**: Flag for Connor to review
6. **If regression**: Don't deploy, document why
7. **Iterate**: Use learnings to try next variant
