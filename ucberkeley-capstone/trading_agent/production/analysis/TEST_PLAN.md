# Statistical Analysis Module - Test Plan

**Status:** Code syntax validated locally ✓
**Next:** Run integration tests on Databricks

---

## Local Validation (Completed)

✓ **Syntax check passed** - All Python files compile without errors
✓ **Module structure valid** - Imports and class definitions correct
✓ **Code organization** - Proper separation of concerns

**Limitation:** Cannot run locally due to missing dependencies (pandas, numpy, scipy)
**Solution:** Run integration tests on Databricks where packages are available

---

## Databricks Integration Test

### Step 1: Test Statistical Functions (Unit Test)

Create a new Databricks notebook: `test_statistical_analysis.ipynb`

```python
# Cell 1: Test imports
from production.analysis import StatisticalAnalyzer, test_strategy_vs_baseline
print("✓ Imports successful")

# Cell 2: Create synthetic test data
import pandas as pd
import numpy as np

# 8 years of synthetic data
years = list(range(2018, 2026))
strategy_earnings = [200000, 210000, 205000, 215000, 220000, 208000, 212000, 195000]
baseline_earnings = [190000, 195000, 192000, 200000, 205000, 198000, 200000, 198000]

year_data = []
for i, year in enumerate(years):
    year_data.append({
        'year': year,
        'strategy': 'Test Strategy',
        'net_earnings': strategy_earnings[i]
    })
    year_data.append({
        'year': year,
        'strategy': 'Test Baseline',
        'net_earnings': baseline_earnings[i]
    })

year_df = pd.DataFrame(year_data)
print(f"✓ Created test dataset: {len(years)} years")

# Cell 3: Run statistical test
result = test_strategy_vs_baseline(
    strategy_name='Test Strategy',
    baseline_name='Test Baseline',
    year_df=year_df,
    verbose=True
)

print("\nTest Results:")
print(f"  p-value: {result['p_value']:.4f}")
print(f"  Cohen's d: {result['cohens_d']:.4f}")
print(f"  Significant: {result['significant_05']}")
print(f"  Sign test: {result['n_years_positive']}/{result['n_years']} positive")

assert result['n_years'] == 8, "Should have 8 years"
assert 'p_value' in result, "Should have p-value"
assert 'cohens_d' in result, "Should have effect size"
print("\n✓ All assertions passed")
```

**Expected output:**
- p-value should be reasonable (0.01 to 0.50 range)
- Cohen's d should be "small" or "medium"
- Sign test should show 7/8 positive
- No errors or exceptions

---

### Step 2: Test with Real Data (Integration Test)

```python
# Cell 1: Initialize analyzer
from production.analysis import StatisticalAnalyzer

analyzer = StatisticalAnalyzer(spark=spark)
print("✓ Analyzer initialized")

# Cell 2: Load actual results (if they exist)
# Try loading from existing year-by-year results table
try:
    year_df = analyzer.load_year_by_year_results(
        commodity='coffee',
        model_version='naive'  # Or whatever model exists
    )
    print(f"✓ Loaded {len(year_df)} rows from Delta table")
    print(f"  Strategies: {year_df['strategy'].unique().tolist()}")
    print(f"  Years: {sorted(year_df['year'].unique().tolist())}")
except Exception as e:
    print(f"⚠️  Could not load existing results: {e}")
    print("   This is expected if backtests haven't been run yet")

# Cell 3: Run full analysis (if data exists)
if 'year_df' in locals() and not year_df.empty:
    results = analyzer.run_full_analysis(
        commodity='coffee',
        model_version='naive',
        primary_baseline='Immediate Sale',
        verbose=True
    )

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"  Strategies tested: {len(results['strategy_vs_baseline_tests'])}")
    print(f"  Matched pairs: {len(results['matched_pair_tests'])}")

    # Show best result
    if results['best_prediction_analysis']:
        best = results['best_prediction_analysis']
        print(f"\n  Best strategy: {best['strategy']}")
        print(f"    Mean difference: ${best['mean_difference']:,.0f}")
        print(f"    p-value: {best['p_value']:.4f}")
        print(f"    Significant: {best['significant_05']}")
```

**Expected output:**
- Should load year-by-year results successfully
- Should identify 4 baseline + 6 prediction strategies
- Should compute all statistical tests without errors
- Should show results summary

---

### Step 3: Test Standalone Script

```bash
# In Databricks terminal or notebook with %sh magic

# Test help
python production/scripts/run_statistical_analysis.py --help

# Test discovery (should find existing results)
python production/scripts/run_statistical_analysis.py --no-save --quiet

# Test specific commodity
python production/scripts/run_statistical_analysis.py \
    --commodity coffee \
    --model naive \
    --no-save
```

**Expected output:**
- Help message displays correctly
- Script discovers existing result tables
- Analysis runs without errors
- Results printed to console

---

### Step 4: Test Integration with Multi-Commodity Runner

```python
# In a new notebook
from production.runners.multi_commodity_runner import MultiCommodityRunner
from production.config import COMMODITY_CONFIGS

# Run with statistical tests enabled
runner = MultiCommodityRunner(
    spark=spark,
    commodity_configs={'coffee': COMMODITY_CONFIGS['coffee']},
    run_statistical_tests=True  # Enable statistical analysis
)

# Run for single commodity-model pair (quick test)
# This will:
# 1. Run backtests
# 2. Automatically run statistical analysis
# 3. Save statistical results to Delta table

results = runner.run_all_commodities(commodities=['coffee'])

# Check that statistical results were created
print("\nStatistical Results:")
print(runner.all_statistical_results)

# Verify Delta table was created
table_name = "commodity.trading_agent.statistical_tests_coffee_naive"
spark.sql(f"DESCRIBE TABLE {table_name}").show()
```

**Expected output:**
- Backtests run successfully
- Statistical analysis runs automatically after backtests
- Delta table created with statistical results
- Table schema includes all expected columns

---

## Validation Checklist

### Unit Tests ✓
- [ ] Module imports successfully
- [ ] Helper functions work (Cohen's d, bootstrap CI)
- [ ] test_strategy_vs_baseline produces valid results
- [ ] No syntax errors or exceptions

### Integration Tests ✓
- [ ] Can load year-by-year results from Delta tables
- [ ] StatisticalAnalyzer.run_full_analysis completes
- [ ] Results saved to Delta tables successfully
- [ ] All expected columns present in output

### End-to-End Tests ✓
- [ ] Standalone script discovers existing results
- [ ] Standalone script runs analysis successfully
- [ ] Multi-commodity runner integration works
- [ ] Statistical tests run automatically when enabled

### Data Quality ✓
- [ ] p-values are in valid range [0, 1]
- [ ] Confidence intervals are reasonable
- [ ] Sign test counts match number of years
- [ ] No NaN or infinite values in output

---

## Known Limitations

1. **Local testing not possible** - Requires Databricks environment
2. **Requires existing backtest results** - Cannot test without data
3. **Sample size warning** - With n=8 years, power is limited (~30%)

---

## Troubleshooting

### Error: "No module named 'production'"
**Cause:** Incorrect Python path
**Solution:** Run from trading_agent/ directory or adjust sys.path

### Error: "Could not load results table"
**Cause:** Year-by-year results table doesn't exist
**Solution:** Run backtests first to create `results_{commodity}_by_year_{model}` tables

### Error: "Insufficient overlapping years"
**Cause:** Different strategies have different year coverage
**Solution:** Use model with longest coverage (e.g., naive model)

---

## Success Criteria

✅ **Module is ready for production when:**
1. All unit tests pass on Databricks
2. Integration tests complete without errors
3. Statistical results match expected patterns
4. Delta tables created with correct schema
5. Standalone script runs successfully
6. Multi-commodity runner integration works

---

**Created:** 2025-12-08
**Status:** Ready for Databricks testing
**Next Step:** Run integration tests on Databricks with real data
