"""
Check if Step 2 pickle files exist and map data flow
"""
from pyspark.sql import SparkSession
import os

spark = SparkSession.builder.getOrCreate()

print("="*80)
print("CHECKING STEP 2 PICKLE FILE OUTPUTS")
print("="*80)

# Check if production/files directory exists
volume_path = "/dbfs/production/files"
print(f"\n1. Checking volume path: {volume_path}")

if os.path.exists(volume_path):
    print(f"   ✓ Directory exists")

    # List all files
    try:
        files = os.listdir(volume_path)
        print(f"   Found {len(files)} files:")

        # Show pickle files
        pickle_files = [f for f in files if f.endswith('.pkl')]
        if pickle_files:
            print(f"\n   Pickle files ({len(pickle_files)}):")
            for f in sorted(pickle_files):
                file_path = os.path.join(volume_path, f)
                size_mb = os.path.getsize(file_path) / (1024 * 1024)
                print(f"     - {f} ({size_mb:.2f} MB)")
        else:
            print(f"   ⚠️  No pickle files found")

        # Show manifest files
        manifest_files = [f for f in files if 'manifest' in f.lower()]
        if manifest_files:
            print(f"\n   Manifest files ({len(manifest_files)}):")
            for f in sorted(manifest_files)[:10]:
                print(f"     - {f}")

        # Show other files
        other_files = [f for f in files if not f.endswith('.pkl') and 'manifest' not in f.lower()]
        if other_files:
            print(f"\n   Other files ({len(other_files)}):")
            for f in sorted(other_files)[:10]:
                print(f"     - {f}")

    except Exception as e:
        print(f"   ❌ Error listing files: {e}")
else:
    print(f"   ❌ Directory does not exist")

print("\n" + "="*80)
print("DATA FLOW MAPPING")
print("="*80)

print("\nStep 1: Forecast Generation")
print("  Output: commodity.forecast.distributions")
try:
    count = spark.sql("""
        SELECT COUNT(*) as cnt
        FROM commodity.forecast.distributions
        WHERE commodity = 'Coffee' AND is_actuals = false
    """).first().cnt
    print(f"  ✓ Has {count:,} forecast rows for Coffee")
except Exception as e:
    print(f"  ❌ Error: {e}")

print("\nStep 2: Load Forecast Predictions")
print("  Input: commodity.forecast.distributions")
print("  Output: Pickle files in /dbfs/production/files/")
print(f"  Status: {'✓ Pickle files exist' if pickle_files else '❌ No pickle files found'}")

print("\nStep 3: Parameter Optimization")
print("  Expected input: commodity.trading_agent.predictions_coffee")
try:
    models = spark.sql("""
        SELECT DISTINCT model_version
        FROM commodity.trading_agent.predictions_coffee
    """).collect()
    print(f"  Current data: {len(models)} models")
    for m in models:
        print(f"    - {m.model_version}")
except Exception as e:
    print(f"  ❌ Error: {e}")

print("\n" + "="*80)
print("DIAGNOSIS")
print("="*80)
print("\nISSUE: Optimizer queries predictions_coffee table,")
print("       but Step 2 saves to pickle files, not the table!")
print("\nSOLUTION OPTIONS:")
print("  A) Modify optimizer to load from pickle files")
print("  B) Add step to load pickle files into predictions_coffee table")
print("  C) Modify Step 2 to write directly to predictions_coffee table")
