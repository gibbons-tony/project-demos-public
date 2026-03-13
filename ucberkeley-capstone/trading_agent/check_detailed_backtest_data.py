"""
Check if detailed backtest data exists for multi-granularity analysis

Investigates:
1. What results tables exist
2. Table schemas (columns available)
3. Granularity of data (daily, monthly, annual)
4. Whether we can perform quarterly/monthly statistical tests
"""

from pyspark.sql import SparkSession
import pyspark.sql.functions as F

# Initialize Spark
spark = SparkSession.builder \
    .appName("Check Detailed Backtest Data") \
    .getOrCreate()

print("=" * 80)
print("INVESTIGATING BACKTEST DATA STRUCTURE")
print("=" * 80)
print()

# Check all results tables
all_tables = spark.sql("SHOW TABLES IN commodity.trading_agent").collect()

results_tables = [
    row.tableName for row in all_tables
    if 'results_coffee' in row.tableName
]

print(f"Found {len(results_tables)} results tables for coffee:")
for table in sorted(results_tables):
    print(f"  - {table}")
print()

# Check schema of a representative table
test_table = "commodity.trading_agent.results_coffee_by_year_naive"

print("=" * 80)
print(f"SCHEMA: {test_table}")
print("=" * 80)

df = spark.table(test_table)
df.printSchema()
print()

print("Sample data:")
df.show(5, truncate=False)
print()

# Check granularity
print("=" * 80)
print("DATA GRANULARITY CHECK")
print("=" * 80)

# Are there date columns?
columns = df.columns
print(f"Columns: {columns}")
print()

# Check if there's a 'date' column for daily data
if 'date' in columns:
    print("✓ 'date' column found - daily granularity data exists!")
    date_count = df.select('date').distinct().count()
    print(f"  Unique dates: {date_count}")

    # Check date range
    date_range = df.select(
        F.min('date').alias('min_date'),
        F.max('date').alias('max_date')
    ).collect()[0]
    print(f"  Date range: {date_range['min_date']} to {date_range['max_date']}")

elif 'month' in columns or 'quarter' in columns:
    print("✓ Monthly/quarterly columns found")

else:
    print("✗ Only annual aggregates found (year column only)")
    print()

    # Check for detailed results pickle files
    print("Checking for detailed pickle files...")
    print("(These would contain daily/period-by-period data)")

# Check if there are non-aggregated tables
print()
print("=" * 80)
print("CHECKING FOR NON-AGGREGATED TABLES")
print("=" * 80)

non_year_tables = [
    t for t in results_tables
    if 'by_year' not in t
]

print(f"Found {len(non_year_tables)} non-aggregated tables:")
for table in sorted(non_year_tables):
    print(f"  - {table}")

    # Check schema of first one
    if non_year_tables and table == non_year_tables[0]:
        print()
        print(f"Schema of {table}:")
        df_detail = spark.table(f"commodity.trading_agent.{table}")
        df_detail.printSchema()

        print(f"\nRow count: {df_detail.count()}")
        print("\nSample data:")
        df_detail.show(5, truncate=False)

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)

# Determine if multi-granularity analysis is possible
has_detailed_data = any([
    'date' in df.columns,
    len(non_year_tables) > 0
])

if has_detailed_data:
    print("✓ Detailed data available for multi-granularity analysis")
    print("  Can perform quarterly/monthly statistical tests")
else:
    print("✗ Only annual aggregates available")
    print("  Multi-granularity analysis requires modification to backtest runner")
    print("  to save day-by-day or month-by-month results")
