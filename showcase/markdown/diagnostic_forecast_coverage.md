```python
# DIAGNOSTIC: FORECAST COVERAGE IN DISTRIBUTIONS TABLE
# ============================================================================
# Purpose: Comprehensive check of what forecasts are available per model
# 
# This diagnostic answers:
# 1. How many unique forecast dates exist per model?
# 2. What is the date range coverage?
# 3. Are there gaps in the forecast dates?
# 4. How many paths per forecast date?
# 5. What is the actual vs expected forecast density?
```


```python
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
```


```python
# Configuration
FORECAST_TABLE = 'commodity.forecast.distributions'
COMMODITIES = ['coffee', 'sugar']

print(f"Querying: {FORECAST_TABLE}")
print(f"Commodities: {COMMODITIES}")
```

## Step 1: Get All Models and Date Ranges


```python
# Query all forecasts (not actuals) to see what's available
query = f"""
SELECT 
    commodity,
    model_version,
    COUNT(DISTINCT forecast_start_date) as n_forecast_dates,
    MIN(forecast_start_date) as first_forecast,
    MAX(forecast_start_date) as last_forecast,
    COUNT(DISTINCT path_id) as n_paths_per_date,
    COUNT(*) as total_rows
FROM {FORECAST_TABLE}
WHERE is_actuals = FALSE
GROUP BY commodity, model_version
ORDER BY commodity, model_version
"""

summary_df = spark.sql(query).toPandas()

print("=" * 100)
print("FORECAST AVAILABILITY SUMMARY")
print("=" * 100)
print(summary_df.to_string(index=False))
print(f"\nTotal models found: {len(summary_df)}")
```

## Step 2: Detailed Analysis Per Commodity and Model


```python
def analyze_forecast_coverage(commodity, model_version):
    """
    Detailed analysis of forecast coverage for a specific commodity-model pair.
    """
    
    # Get all forecast dates for this model
    query = f"""
    SELECT DISTINCT 
        forecast_start_date,
        COUNT(DISTINCT path_id) as n_paths
    FROM {FORECAST_TABLE}
    WHERE commodity = '{commodity.capitalize()}'
      AND model_version = '{model_version}'
      AND is_actuals = FALSE
    GROUP BY forecast_start_date
    ORDER BY forecast_start_date
    """
    
    dates_df = spark.sql(query).toPandas()
    dates_df['forecast_start_date'] = pd.to_datetime(dates_df['forecast_start_date'])
    
    if len(dates_df) == 0:
        print(f"\n⚠️  No forecasts found for {commodity} - {model_version}")
        return None
    
    # Calculate gaps
    dates_df = dates_df.sort_values('forecast_start_date').reset_index(drop=True)
    dates_df['days_since_prev'] = dates_df['forecast_start_date'].diff().dt.days
    
    # Analysis
    first_date = dates_df['forecast_start_date'].min()
    last_date = dates_df['forecast_start_date'].max()
    total_days = (last_date - first_date).days
    n_forecasts = len(dates_df)
    
    # Expected forecasts if 14-day cadence
    expected_forecasts_14d = total_days // 14 + 1
    coverage_pct = (n_forecasts / expected_forecasts_14d * 100) if expected_forecasts_14d > 0 else 0
    
    # Gap analysis
    gaps = dates_df['days_since_prev'].dropna()
    avg_gap = gaps.mean() if len(gaps) > 0 else 0
    max_gap = gaps.max() if len(gaps) > 0 else 0
    
    # Paths per date
    avg_paths = dates_df['n_paths'].mean()
    min_paths = dates_df['n_paths'].min()
    max_paths = dates_df['n_paths'].max()
    
    print(f"\n{'='*100}")
    print(f"{commodity.upper()} - {model_version}")
    print(f"{'='*100}")
    
    print(f"\n📅 DATE COVERAGE:")
    print(f"  First forecast: {first_date.strftime('%Y-%m-%d')}")
    print(f"  Last forecast:  {last_date.strftime('%Y-%m-%d')}")
    print(f"  Total span:     {total_days} days ({total_days/365:.1f} years)")
    print(f"  Forecast dates: {n_forecasts}")
    
    print(f"\n📊 DENSITY:")
    print(f"  Expected (14-day cadence): {expected_forecasts_14d} forecasts")
    print(f"  Actual coverage:           {coverage_pct:.1f}%")
    print(f"  Average gap:               {avg_gap:.1f} days")
    print(f"  Maximum gap:               {max_gap:.0f} days")
    
    print(f"\n🔢 PATHS PER FORECAST:")
    print(f"  Average: {avg_paths:.0f}")
    print(f"  Min:     {min_paths}")
    print(f"  Max:     {max_paths}")
    
    # Show gap distribution
    if len(gaps) > 0:
        print(f"\n📈 GAP DISTRIBUTION:")
        gap_counts = gaps.value_counts().sort_index()
        for gap_days, count in gap_counts.head(10).items():
            print(f"  {gap_days:3.0f} days: {count:3d} occurrences")
        
        if len(gap_counts) > 10:
            print(f"  ... ({len(gap_counts) - 10} more gap sizes)")
    
    # Large gaps (>30 days)
    large_gaps = dates_df[dates_df['days_since_prev'] > 30]
    if len(large_gaps) > 0:
        print(f"\n⚠️  LARGE GAPS (>30 days):")
        for idx, row in large_gaps.iterrows():
            prev_date = dates_df.loc[idx-1, 'forecast_start_date'] if idx > 0 else None
            if prev_date:
                print(f"  {prev_date.strftime('%Y-%m-%d')} → {row['forecast_start_date'].strftime('%Y-%m-%d')}: {row['days_since_prev']:.0f} days")
    
    # Show first and last 10 dates
    print(f"\n📋 FIRST 10 FORECAST DATES:")
    for idx, row in dates_df.head(10).iterrows():
        print(f"  {row['forecast_start_date'].strftime('%Y-%m-%d')}: {row['n_paths']} paths")
    
    if len(dates_df) > 10:
        print(f"\n📋 LAST 10 FORECAST DATES:")
        for idx, row in dates_df.tail(10).iterrows():
            print(f"  {row['forecast_start_date'].strftime('%Y-%m-%d')}: {row['n_paths']} paths")
    
    return dates_df
```


```python
# Run detailed analysis for each commodity-model pair
all_coverage_data = {}

for _, row in summary_df.iterrows():
    commodity = row['commodity'].lower()
    model_version = row['model_version']
    
    coverage_df = analyze_forecast_coverage(commodity, model_version)
    
    if coverage_df is not None:
        all_coverage_data[f"{commodity}_{model_version}"] = coverage_df
```

## Step 3: Visual Timeline of Forecast Coverage


```python
# Create visualization of forecast coverage for each model
fig, axes = plt.subplots(len(summary_df), 1, figsize=(16, 3 * len(summary_df)))

if len(summary_df) == 1:
    axes = [axes]

for idx, (key, coverage_df) in enumerate(all_coverage_data.items()):
    ax = axes[idx]
    
    # Plot forecast dates as vertical lines
    dates = coverage_df['forecast_start_date']
    y_vals = np.ones(len(dates))
    
    ax.scatter(dates, y_vals, marker='|', s=100, c='blue', alpha=0.6)
    
    # Highlight large gaps
    large_gaps = coverage_df[coverage_df['days_since_prev'] > 30]
    if len(large_gaps) > 0:
        for idx_gap, row in large_gaps.iterrows():
            if idx_gap > 0:
                prev_date = coverage_df.loc[idx_gap-1, 'forecast_start_date']
                curr_date = row['forecast_start_date']
                ax.axvspan(prev_date, curr_date, alpha=0.2, color='red')
    
    ax.set_ylim([0.5, 1.5])
    ax.set_yticks([])
    ax.set_xlabel('Date')
    ax.set_title(f"{key.upper()} - Forecast Coverage Timeline (red = gaps >30 days)")
    ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('/tmp/forecast_coverage_timeline.png', dpi=150, bbox_inches='tight')
print("\n✓ Saved timeline visualization: /tmp/forecast_coverage_timeline.png")
plt.show()
```

## Step 4: Check for Continuous Coverage Potential


```python
# Check if there are any models with near-continuous coverage
print("\n" + "=" * 100)
print("CONTINUOUS COVERAGE ASSESSMENT")
print("=" * 100)

for key, coverage_df in all_coverage_data.items():
    gaps = coverage_df['days_since_prev'].dropna()
    
    # Count forecasts within different gap tolerances
    n_total = len(coverage_df)
    n_within_14d = sum(gaps <= 14) if len(gaps) > 0 else 0
    n_within_21d = sum(gaps <= 21) if len(gaps) > 0 else 0
    n_within_30d = sum(gaps <= 30) if len(gaps) > 0 else 0
    
    pct_14d = (n_within_14d / len(gaps) * 100) if len(gaps) > 0 else 0
    pct_21d = (n_within_21d / len(gaps) * 100) if len(gaps) > 0 else 0
    pct_30d = (n_within_30d / len(gaps) * 100) if len(gaps) > 0 else 0
    
    print(f"\n{key.upper()}:")
    print(f"  Total forecasts: {n_total}")
    print(f"  Gaps ≤14 days: {n_within_14d}/{len(gaps)} ({pct_14d:.1f}%)")
    print(f"  Gaps ≤21 days: {n_within_21d}/{len(gaps)} ({pct_21d:.1f}%)")
    print(f"  Gaps ≤30 days: {n_within_30d}/{len(gaps)} ({pct_30d:.1f}%)")
    
    if pct_14d >= 80:
        print(f"  ✓ GOOD: {pct_14d:.1f}% of gaps are ≤14 days (near-continuous)")
    elif pct_21d >= 80:
        print(f"  ⚠️  MODERATE: {pct_21d:.1f}% of gaps are ≤21 days (somewhat sparse)")
    else:
        print(f"  ❌ SPARSE: Only {pct_30d:.1f}% of gaps are ≤30 days (very sparse)")
```

## Step 5: Summary Report


```python
print("\n" + "=" * 100)
print("FINAL SUMMARY")
print("=" * 100)

print(f"\nTotal models analyzed: {len(all_coverage_data)}")

# Group by commodity
for commodity in COMMODITIES:
    commodity_models = [k for k in all_coverage_data.keys() if k.startswith(commodity)]
    
    if commodity_models:
        print(f"\n{commodity.upper()}:")
        print(f"  Models: {len(commodity_models)}")
        
        total_forecasts = sum([len(all_coverage_data[k]) for k in commodity_models])
        avg_forecasts = total_forecasts / len(commodity_models)
        
        print(f"  Total forecast dates across all models: {total_forecasts}")
        print(f"  Average per model: {avg_forecasts:.1f}")
        
        # Find model with most coverage
        best_model = max(commodity_models, key=lambda k: len(all_coverage_data[k]))
        best_count = len(all_coverage_data[best_model])
        print(f"  Best coverage: {best_model.split('_', 1)[1]} ({best_count} forecasts)")

print("\n" + "=" * 100)
print("✓ DIAGNOSTIC COMPLETE")
print("=" * 100)

print("\nNEXT STEPS:")
print("1. Review the gap distributions above")
print("2. Check if large gaps (>30 days) are expected or data issues")
print("3. Verify with forecast team if sparse coverage is intentional")
print("4. If continuous forecasts exist, they may be in a different table/filter")
```
