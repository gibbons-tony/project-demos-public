# Multi-Granularity Statistical Analysis

**Added**: 2025-12-10
**Addresses**: Small sample size problem (n=5 years → n=60 months)

---

## The Problem with Annual-Only Analysis

**Current approach**: Year-by-year comparison (n=5)

**Issues**:
- Low statistical power (~50% for medium effects)
- Wasteful (collapsing 365 days → 1 observation)
- Violates independence anyway (years are autocorrelated)

---

## Solution: Multi-Granularity Analysis

Run the same test at **multiple time scales** with proper corrections for clustering:

| Granularity | Sample Size | Clustering | Method |
|-------------|-------------|------------|--------|
| **Annual** | n=5 | N/A | Paired t-test |
| **Quarterly** | n=20 | Cluster by year | OLS with clustered SE |
| **Monthly** | n=60 | Cluster by year | OLS with clustered SE |

### Why This Works:

1. **Higher power** from larger n (60 vs 5)
2. **Accounts for autocorrelation** via clustered standard errors
3. **Robustness check**: If significant at ALL granularities → strong evidence

---

## How Clustered Standard Errors Work

**Problem**: Months within same year are correlated

**Naive approach**: Treat 60 months as independent → SE too small → false significance

**Clustered SE approach**:
```python
# Regular SE (wrong):
SE_naive = std(differences) / sqrt(60)  # Assumes independence

# Clustered SE (correct):
SE_clustered = sqrt(Var_between_clusters + Var_within_clusters)
# Accounts for within-year correlation
```

**SE inflation factor**: How much larger clustered SE is vs naive
- Factor = 1.0 → no clustering effect (months are independent)
- Factor = 2.5 → strong clustering (months within year are highly correlated)
- Factor > 1.0 is typical and expected

---

## Example Output

```python
from production.analysis.statistical_tests import StatisticalAnalyzer

analyzer = StatisticalAnalyzer(spark=spark)

# Run multi-granularity analysis
results = analyzer.run_multi_granularity_analysis(
    commodity='coffee',
    model_version='naive',
    strategy_name='Rolling Horizon MPC',
    baseline_name='Immediate Sale',
    granularities=['year', 'quarter', 'month'],
    verbose=True
)
```

### Output:

```
================================================================================
MULTI-GRANULARITY ANALYSIS: Rolling Horizon MPC vs Immediate Sale
================================================================================

--------------------------------------------------------------------------------
GRANULARITY: YEAR
--------------------------------------------------------------------------------

Rolling Horizon MPC vs Immediate Sale:
  n=5 years, Δ=$27,220, p=0.0143 ✓

Paired t-test:
  t-statistic: 4.2341
  p-value: 0.0143 ✓ SIGNIFICANT at α=0.05

Effect Size:
  Cohen's d: 3.2214 (Very large effect)

--------------------------------------------------------------------------------
GRANULARITY: QUARTER
--------------------------------------------------------------------------------

Rolling Horizon MPC vs Immediate Sale:
  n=20 periods, 5 clusters (year)
  Δ=$6,805, SE_clustered=$2,450, p=0.0089 ✓
  SE inflation: 2.1x (clustering effect)

95% Confidence Interval (clustered):
  [$2,014, $11,596]
  ✓ Does not include zero

--------------------------------------------------------------------------------
GRANULARITY: MONTH
--------------------------------------------------------------------------------

Rolling Horizon MPC vs Immediate Sale:
  n=60 periods, 5 clusters (year)
  Δ=$2,268, SE_clustered=$685, p=0.0012 ✓
  SE inflation: 2.5x (clustering effect)

95% Confidence Interval (clustered):
  [$922, $3,615]
  ✓ Does not include zero

================================================================================
COMPARISON ACROSS GRANULARITIES
================================================================================

Granularity   n      Mean Diff       p-value    Significant
------------------------------------------------------------
year          5          $27,220    0.0143  ✓
quarter       20          $6,805    0.0089  ✓
month         60          $2,268    0.0012  ✓

Interpretation: Significant at ALL granularities (year, quarter, month) - robust result
```

---

## Interpretation Guide

### **Case 1: Significant at ALL granularities**
```
year: p=0.014 ✓
quarter: p=0.009 ✓
month: p=0.001 ✓
```

**Interpretation**: Very strong evidence. Result is robust to choice of time scale.

**For data scientists**: Effect is real and not an artifact of temporal aggregation.

---

### **Case 2: Significant only at fine granularities**
```
year: p=0.082 ✗
quarter: p=0.031 ✓
month: p=0.008 ✓
```

**Interpretation**: Annual test underpowered (n=5 too small), but finer granularity confirms effect.

**Recommendation**: Trust monthly/quarterly results (higher power).

---

### **Case 3: Significant only at annual**
```
year: p=0.041 ✓
quarter: p=0.125 ✗
month: p=0.210 ✗
```

**Interpretation**: May be seasonal aggregation effect or Type I error.

**Recommendation**: Investigate why finer granularity doesn't show effect. Possible issues:
- Within-year variation is high
- Effect only manifests over full year
- Annual result may be false positive

---

### **Case 4: Not significant at any granularity**
```
year: p=0.152 ✗
quarter: p=0.103 ✗
month: p=0.085 ✗
```

**Interpretation**: No evidence of strategy advantage.

**Note**: Monthly comes closest → may be underpowered even at n=60.

---

## SE Inflation Factor

**What it means**: How much clustering increases standard errors

```python
SE_inflation_factor = SE_clustered / SE_naive
```

**Typical values for monthly data**:
- **1.0-1.5**: Weak clustering (months mostly independent)
- **1.5-2.5**: Moderate clustering (typical for financial data)
- **2.5-4.0**: Strong clustering (months within year highly correlated)
- **>4.0**: Very strong clustering (consider different model)

**Example**:
```
Monthly analysis:
  SE_naive = $274 (assumes 60 independent observations)
  SE_clustered = $685 (accounts for within-year correlation)
  Inflation factor: 2.5x
```

**Interpretation**: Treating months as independent would underestimate SE by 2.5x → would get false significance.

---

## When to Use Each Granularity

### **Annual (n=5)**
- **Pros**: Simple, accounts for full seasonal cycle, conservative
- **Cons**: Low power, wastes information
- **Use when**: You need very conservative test, n_years ≥ 10

### **Quarterly (n=20)**
- **Pros**: Captures seasonality (4 quarters), good balance
- **Cons**: Still moderate sample size
- **Use when**: Want seasonal detail without excessive autocorrelation

### **Monthly (n=60)**
- **Pros**: High power, uses all available temporal information
- **Cons**: Requires clustered SE, more complex
- **Use when**: You have ≥5 years of data, want maximum power

---

## Statistical Rigor Notes

### **Why cluster by year?**

Months within the same year share:
- Same economic conditions (recession/boom)
- Same weather patterns (El Niño years)
- Same commodity supply shocks
- Same strategy parameters (if re-optimized annually)

**Result**: Within-year correlation violates independence assumption.

**Solution**: Cluster standard errors by year → accounts for this correlation.

### **What if I have <5 years?**

Clustered SE requires ≥5 clusters for reliable inference.

With fewer years:
- Use annual only (paired t-test)
- Or use block bootstrap (resamples entire years)

### **Can I use daily data?**

**Yes, but**: Daily observations are VERY autocorrelated.

**Better approach**: Mixed-effects model with AR(1) errors
```python
# Account for daily autocorrelation + year-level clustering
model = smf.mixedlm("earnings ~ C(strategy)", data=daily_df,
                    groups=daily_df["year"],
                    re_formula="1")
```

---

## Advantages Over Annual-Only

| Aspect | Annual Only | Multi-Granularity |
|--------|-------------|-------------------|
| **Sample size** | n=5 | n=5, 20, 60 |
| **Power** | ~50% (medium effect) | ~80% (medium effect, monthly) |
| **Information use** | 1.4% (5/365 days) | 16% (monthly) |
| **Robustness** | Single test | Multiple confirming tests |
| **Temporal detail** | Coarse (year) | Fine (month) |
| **Clustering** | Ignored | Accounted for |

**Bottom line**: Multi-granularity gives you:
1. **More power** (better chance of detecting real effects)
2. **Robustness** (multiple independent confirmations)
3. **Transparency** (shows effect is not artifact of aggregation)

---

## Usage in Full Analysis

The multi-granularity analysis is **automatically included** when you run the full statistical analysis:

```python
analyzer = StatisticalAnalyzer(spark=spark)

# This now includes multi-granularity for best strategies
results = analyzer.run_full_analysis(
    commodity='coffee',
    model_version='naive',
    primary_baseline='Immediate Sale',
    verbose=True
)

# Access multi-granularity results
multi_gran = results.get('multi_granularity_analysis', {})
```

Or run it standalone for specific strategy:

```python
# Just the multi-granularity analysis
multi_results = analyzer.run_multi_granularity_analysis(
    commodity='coffee',
    model_version='naive',
    strategy_name='Rolling Horizon MPC',
    baseline_name='Immediate Sale'
)
```

---

## Summary

**Old approach**: Annual only (n=5) → low power, wastes data

**New approach**: Test at multiple granularities with clustered SE
- Annual: n=5 (robustness check)
- Quarterly: n=20 (good balance)
- Monthly: n=60 (maximum power)

**Result**: More powerful tests that properly account for temporal autocorrelation while using all available data.

**For data scientists**: This is the econometrically rigorous way to handle panel data with temporal clustering.
