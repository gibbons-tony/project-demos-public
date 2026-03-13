# Statistical Testing Review & Presentation Ideas

**Date**: 2025-12-10
**Script**: `production/analysis/statistical_tests.py`

## What's Being Tested

### 1. Core Question
**"Is the improvement statistically significant or just random chance?"**

The framework tests whether prediction-based trading strategies meaningfully outperform baselines across multiple years.

### 2. Statistical Tests Applied

#### A. **Paired t-test** (Primary test)
- Compares SAME years for both strategies
- Controls for year-to-year market variation
- Tests: H₀: mean difference = 0 vs H₁: strategy > baseline
- Output: t-statistic, p-value, significance at α=0.05

#### B. **Effect Size** (Cohen's d)
- Measures practical significance (not just statistical)
- Interpretation:
  - Small: |d| = 0.2
  - Medium: |d| = 0.5
  - Large: |d| = 0.8+

#### C. **Confidence Intervals** (95% CI)
- Range of plausible values for mean difference
- If CI excludes zero → statistically significant improvement

#### D. **Sign Test** (Non-parametric)
- Robustness check (doesn't assume normality)
- Tests: Do most years show improvement?
- Binomial test: p(positive) > 50%

#### E. **Bootstrap CI** (Robustness)
- 10,000 resamples
- Distribution-free confidence interval
- Validates parametric CI

### 3. Comparison Types

**Primary Comparisons:**
- Prediction strategies vs Immediate Sale (most conservative baseline)
- Example: "Rolling Horizon MPC" vs "Immediate Sale"

**Matched Pairs** (Forecast Integration Benefit):
- Price Threshold Predictive vs Price Threshold
- Moving Average Predictive vs Moving Average
- Tests: Does adding forecasts improve the base strategy?

### 4. Data Structure

**Input**: Year-by-year results from `commodity.trading_agent.results_{commodity}_by_year_{model}`

**Grain**: (year, strategy) → net_earnings

**Requirement**: ≥3 overlapping years for valid test

## Current Presentation

### Console Output (Lines 176-212)
```
🏆 Rolling Horizon MPC vs Immediate Sale

Sample Size: 5 years (2020-2024)

Descriptive Statistics:
  Mean earnings (Rolling Horizon MPC): $125,450
  Mean earnings (Immediate Sale): $98,230
  Mean difference: $27,220
  Std of differences: $8,450

Paired t-test:
  t-statistic: 4.2341
  p-value: 0.0143 ✓ SIGNIFICANT at α=0.05

Effect Size:
  Cohen's d: 3.2214 (Very large effect)

95% Confidence Interval:
  [11,450, 42,990]
  ✓ Does not include zero

Sign Test (Non-Parametric):
  Years positive: 5/5
  Years negative: 0/5
  p-value: 0.0312 ✓ SIGNIFICANT
```

### Delta Table Storage
- Table: `commodity.trading_agent.statistical_tests_{commodity}_{model}`
- Flattened results with all metrics
- Queryable for dashboards/reports

## Ideas for Enhanced Presentation

### 1. **Executive Summary Card**
```
┌─────────────────────────────────────────────────┐
│ 🏆 BEST PREDICTION STRATEGY                     │
│                                                 │
│ Rolling Horizon MPC vs Immediate Sale           │
│                                                 │
│ ✓ $27,220/year improvement (28% increase)      │
│ ✓ 95% CI: [$11.4K, $43.0K]                     │
│ ✓ Statistically significant (p=0.014)          │
│ ✓ Large effect size (d=3.22)                   │
│ ✓ Consistent: Won 5/5 years                    │
└─────────────────────────────────────────────────┘
```

### 2. **Comparative Table** (All Strategies)
| Strategy | Mean Improvement | p-value | Effect Size | Years Won | Verdict |
|----------|------------------|---------|-------------|-----------|---------|
| **Rolling Horizon MPC** | **+$27,220** | **0.014*** | **3.22 (L)** | **5/5** | **✓ SIGNIFICANT** |
| Expected Value | +$18,450 | 0.032* | 2.15 (L) | 4/5 | ✓ SIGNIFICANT |
| Consensus | +$12,330 | 0.089 | 1.45 (L) | 4/5 | ⚠️ Marginal |
| Risk-Adjusted | +$8,220 | 0.145 | 0.97 (L) | 3/5 | ✗ Not significant |

Legend: L=Large, M=Medium, S=Small; *p<0.05, **p<0.01

### 3. **Visualization Ideas**

#### A. **Forest Plot** (Confidence Intervals)
```
Strategy           Mean Difference (95% CI)
────────────────────────────────────────────────────
MPC               ●────────┤
Expected Value        ●──────┤
Consensus                ●─────┤
Risk-Adjusted               ●──────┤
                   │        │       │
                   0     10K    20K   30K   40K   50K

● = Point estimate
─ = 95% CI
│ = Zero (no effect)
```

#### B. **Win Rate Chart** (Years beating baseline)
```
Strategy           Win Rate
────────────────────────────
MPC               █████ 100% (5/5)
Expected Value    ████  80% (4/5)
Consensus         ████  80% (4/5)
Risk-Adjusted     ███   60% (3/5)
```

#### C. **Year-over-Year Comparison**
```
Earnings by Year
$150K│           ●MPC
     │          ●
     │         ●    ●
$100K│    ●   ○     ○ ○Baseline
     │   ○   ○
$ 50K│  ○
     └─────────────────────
      2020 2021 2022 2023 2024

Shaded area = MPC advantage
```

### 4. **Matched Pair Analysis** (Forecast Value)
```
Does adding forecasts improve the base strategy?

Price Threshold:
  Without forecasts: $105K/year
  With forecasts:    $118K/year (+$13K, p=0.021*)
  ✓ Forecasts add significant value

Moving Average:
  Without forecasts: $110K/year
  With forecasts:    $115K/year (+$5K, p=0.312)
  ✗ No significant forecast benefit
```

### 5. **Risk-Adjusted Metrics**
```
┌─────────────────────────────────────────┐
│ Risk-Adjusted Performance               │
│                                         │
│ Strategy        Sharpe   Max DD   Wins │
│ MPC             2.14    -$12K     5/5  │
│ Expected Value  1.85    -$18K     4/5  │
│ Baseline        1.23    -$22K     N/A  │
└─────────────────────────────────────────┘
```

### 6. **Sensitivity Analysis Table**
```
Robustness Checks:
┌──────────────────┬────────┬────────┬────────┐
│ Test             │ Result │ p-val  │ Status │
├──────────────────┼────────┼────────┼────────┤
│ Paired t-test    │ +$27K  │ 0.014  │ ✓ Sig  │
│ Sign test        │ 5/5    │ 0.031  │ ✓ Sig  │
│ Bootstrap CI     │ [12K,  │        │ ✓ Sig  │
│                  │  44K]  │        │        │
│ Wilcoxon signed  │        │ 0.019  │ ✓ Sig  │
└──────────────────┴────────┴────────┴────────┘
All tests agree: Improvement is robust
```

## Recommended Presentation Sequence

### For Academic/Technical Audience:
1. Research question & methodology
2. Sample description (N years, commodities, models)
3. Full statistical table with all metrics
4. Forest plot of confidence intervals
5. Sensitivity/robustness checks
6. Limitations & assumptions

### For Business/Executive Audience:
1. **Executive Summary Card** (most important finding)
2. **Comparative Table** (all strategies ranked)
3. **Year-over-Year Chart** (visual proof of consistency)
4. **Forecast Value Analysis** (ROI of predictions)
5. **Risk metrics** (downside protection)
6. One-sentence takeaway: *"MPC strategy beats baseline by $27K/year (28%) with high statistical confidence (p=0.014) and consistency (won 5/5 years)"*

## Key Strengths of Current Framework

✓ Paired design (controls for year-to-year variation)
✓ Multiple tests (parametric + non-parametric)
✓ Effect sizes (practical significance)
✓ Bootstrap validation (robustness)
✓ Clear interpretation guidelines
✓ Saves to queryable Delta tables

## Potential Enhancements

1. **Add**: Wilcoxon signed-rank test (non-parametric alternative to t-test)
2. **Add**: Stratified analysis by market conditions (bull/bear years)
3. **Add**: Multiple testing correction (Bonferroni/Holm) for many comparisons
4. **Add**: Power analysis (can we detect smaller effects with more years?)
5. **Add**: Trading frequency as covariate (more trades → higher costs?)

## Data Requirements for Results Presentation

**Need from Step 3 (Parameter Optimization):**
- Optimized parameters for each strategy
- Backtest results with optimized parameters

**Need from Step 4 (Backtesting):**
- Year-by-year earnings: `results_{commodity}_by_year_{model}`
- Trade-level data: For detailed analysis
- Multiple models: naive, sarimax_auto_weather, xgboost

**Then Statistical Tests can run on the backtest results**

## Next Steps

Once Step 3 (optimizer) completes:
1. Run Step 4: Backtesting with optimized parameters
2. Generate year-by-year results tables
3. Run statistical tests
4. Create presentation materials (dashboards, slides, reports)
