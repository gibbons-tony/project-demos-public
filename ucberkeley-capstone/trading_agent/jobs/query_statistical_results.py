# Query statistical test results from Delta tables
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

print("=" * 80)
print("STATISTICAL TEST RESULTS FROM DELTA TABLES")
print("=" * 80)

# Try the main table
tables_to_check = [
    "commodity.trading_agent.statistical_tests_coffee_naive",
    "commodity.trading_agent.statistical_tests_coffee_xgboost", 
    "commodity.trading_agent.statistical_tests_sugar_naive"
]

for table_name in tables_to_check:
    try:
        df = spark.table(table_name).toPandas()
        print(f"\n{'=' * 80}")
        print(f"TABLE: {table_name}")
        print(f"{'=' * 80}")
        print(f"Rows: {len(df)}")
        if len(df) > 0:
            print(f"\nColumns: {list(df.columns)}\n")
            print(df.to_string(index=False))
        else:
            print("(empty table)")
    except Exception as e:
        print(f"\n❌ {table_name}: {str(e)[:100]}")

print("\n" + "=" * 80)
print("DONE")
print("=" * 80)
