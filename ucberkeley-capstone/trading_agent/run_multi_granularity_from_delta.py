"""
Run multi-granularity statistical analysis using Delta tables (production flow).
"""
import sys
sys.path.insert(0, '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent')

from pyspark.sql import SparkSession
import pandas as pd
import numpy as np
from scipy import stats

spark = SparkSession.builder.getOrCreate()

print("=" * 80)
print("MULTI-GRANULARITY STATISTICAL ANALYSIS (PRODUCTION DELTA TABLES)")
print("=" * 80)

# Load yearly data from production Delta table
print("\n1. Loading yearly results from Delta...")
df = spark.table("commodity.trading_agent.results_coffee_by_year_naive").toPandas()

print(f"   ✓ Loaded {len(df)} rows")
print(f"   ✓ Years: {df['year'].min()}-{df['year'].max()}")
print(f"   ✓ Strategies: {df['strategy'].unique().tolist()}")

# Filter to MPC and Immediate Sale
mpc_data = df[df['strategy'] == 'RollingHorizonMPC'].sort_values('year')
baseline_data = df[df['strategy'] == 'Immediate Sale'].sort_values('year')

print(f"\n   ✓ MPC years: {len(mpc_data)}")
print(f"   ✓ Baseline years: {len(baseline_data)}")

# Statistical test (paired t-test)
print("\n2. Running paired t-test...")

# Align years
common_years = sorted(set(mpc_data['year']) & set(baseline_data['year']))
print(f"   ✓ Common years: {len(common_years)} ({min(common_years)}-{max(common_years)})")

mpc_aligned = mpc_data[mpc_data['year'].isin(common_years)].set_index('year').sort_index()
baseline_aligned = baseline_data[baseline_data['year'].isin(common_years)].set_index('year').sort_index()

# Calculate differences
differences = mpc_aligned['net_earnings'] - baseline_aligned['net_earnings']
mean_diff = differences.mean()
std_diff = differences.std()

# Paired t-test
t_stat, p_value = stats.ttest_rel(mpc_aligned['net_earnings'], baseline_aligned['net_earnings'])

# Baseline mean for percentage
baseline_mean = baseline_aligned['net_earnings'].mean()
pct_improvement = (mean_diff / baseline_mean * 100) if baseline_mean != 0 else 0

print("\n" + "=" * 80)
print("RESULTS")
print("=" * 80)

print(f"\nYEARLY ANALYSIS (n={len(common_years)} years)")
print(f"  Mean difference: ${mean_diff:,.2f}")
print(f"  Std difference: ${std_diff:,.2f}")
print(f"  Percentage improvement: {pct_improvement:.2f}%")
print(f"  T-statistic: {t_stat:.4f}")
print(f"  P-value: {p_value:.4f}")

if p_value < 0.05:
    print(f"\n  ✓ STATISTICALLY SIGNIFICANT at α=0.05")
    print(f"    RollingHorizonMPC outperforms Immediate Sale by ${mean_diff:,.2f}/year ({pct_improvement:.2f}%)")
else:
    print(f"\n  ✗ NOT SIGNIFICANT at α=0.05")

# Year-by-year breakdown
print("\n" + "=" * 80)
print("YEAR-BY-YEAR BREAKDOWN")
print("=" * 80)

comparison = pd.DataFrame({
    'Year': common_years,
    'MPC': mpc_aligned['net_earnings'].values,
    'Baseline': baseline_aligned['net_earnings'].values,
    'Difference': differences.values,
    'Pct_Improvement': (differences.values / baseline_aligned['net_earnings'].values * 100)
})

for _, row in comparison.iterrows():
    sign = "+" if row['Difference'] >= 0 else ""
    print(f"{int(row['Year'])}: MPC=${row['MPC']:>10,.0f}  Baseline=${row['Baseline']:>10,.0f}  "
          f"Diff={sign}${row['Difference']:>8,.0f} ({sign}{row['Pct_Improvement']:>5.1f}%)")

print("\n" + "=" * 80)
