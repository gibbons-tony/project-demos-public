"""
Quick verification: Do predictions exist?
"""
from pyspark.sql import SparkSession
import pandas as pd

spark = SparkSession.builder.getOrCreate()

print("="*80)
print("PREDICTION DATA VERIFICATION")
print("="*80)
print()

# Check if table exists and has data
print("1. Checking predictions table...")
try:
    pred_df = spark.table("commodity.trading_agent.predictions_coffee")
    total_rows = pred_df.count()
    print(f"✓ Table exists with {total_rows:,} total rows")

    # Check model versions
    print("\n2. Available model versions:")
    versions = pred_df.select("model_version").distinct().toPandas()
    for v in versions['model_version']:
        count = pred_df.filter(f"model_version = '{v}'").count()
        print(f"  - {v}: {count:,} rows")

    # Check synthetic_acc100 specifically
    print("\n3. Checking synthetic_acc100...")
    synth_df = pred_df.filter("model_version = 'synthetic_acc100'")
    synth_count = synth_df.count()

    if synth_count > 0:
        print(f"✓ Found {synth_count:,} rows for synthetic_acc100")

        # Show date range
        synth_pd = synth_df.select("timestamp").toPandas()
        synth_pd['timestamp'] = pd.to_datetime(synth_pd['timestamp'])
        print(f"  Date range: {synth_pd['timestamp'].min()} to {synth_pd['timestamp'].max()}")
        print(f"  Sample timestamps:")
        for ts in sorted(synth_pd['timestamp'].unique())[:5]:
            print(f"    - {ts}")
    else:
        print("❌ NO DATA for synthetic_acc100!")
        print("   This is why predictions aren't being passed to strategies.")

except Exception as e:
    print(f"❌ Error accessing table: {e}")

print("\n" + "="*80)
print("VERIFICATION COMPLETE")
print("="*80)
