"""Quick check if Step 4 backtesting results are available in Delta tables"""

from pyspark.sql import SparkSession

# Initialize Spark
spark = SparkSession.builder \
    .appName("Check Step 4 Results") \
    .getOrCreate()

# Check each model's results
models = ['naive', 'sarimax_auto_weather', 'xgboost']

print("=" * 80)
print("CHECKING STEP 4 BACKTESTING RESULTS")
print("=" * 80)
print()

for model in models:
    table_name = f"commodity.trading_agent.results_coffee_by_year_{model}"

    try:
        df = spark.table(table_name)
        count = df.count()

        print(f"✓ {model}:")
        print(f"  Table: {table_name}")
        print(f"  Rows: {count}")

        if count > 0:
            # Show sample data
            print(f"  Sample strategies: {df.select('strategy').distinct().limit(5).rdd.map(lambda r: r[0]).collect()}")
            print(f"  Years: {sorted(df.select('year').distinct().rdd.map(lambda r: r[0]).collect())}")
        print()

    except Exception as e:
        print(f"✗ {model}: Table not found or error")
        print(f"  Error: {str(e)}")
        print()

print("=" * 80)
print("SUMMARY")
print("=" * 80)
print()
print("If all 3 models show data, Step 5 statistical analysis can proceed.")
print("If any are missing, Step 4 needs to be re-run.")
