"""
Clean up stale backtest results that don't correspond to current models

Reads forecast manifests to determine which models are current,
then identifies and optionally removes old pickle files and Delta tables.
"""

import sys
import os

try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = os.getcwd()
    if 'trading_agent' not in script_dir:
        script_dir = '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent/production/scripts'

trading_agent_dir = os.path.dirname(os.path.dirname(script_dir))
if trading_agent_dir not in sys.path:
    sys.path.insert(0, trading_agent_dir)

import json
from pathlib import Path
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

print("=" * 80)
print("CLEANING UP STALE BACKTEST RESULTS")
print("=" * 80)

# Load forecast manifests to determine current models
volume_path = Path("/Volumes/commodity/trading_agent/files/")

current_models = {
    'coffee': set(),
    'sugar': set()
}

for commodity in ['coffee', 'sugar']:
    manifest_path = volume_path / f"forecast_manifest_{commodity}.json"

    if manifest_path.exists():
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)

        # Get models that meet quality criteria
        for model, info in manifest.get('models', {}).items():
            if info.get('meets_criteria', False):
                current_models[commodity].add(model)

        print(f"\n{commodity.upper()}: {len(current_models[commodity])} current models")
        for model in sorted(current_models[commodity]):
            print(f"  ✓ {model}")
    else:
        print(f"\n{commodity.upper()}: No manifest found")

# Also add synthetic models (always current)
print("\nAdding synthetic models (always current):")
for commodity in ['coffee', 'sugar']:
    for acc in [60, 70, 80, 90, 100]:
        model = f"synthetic_acc{acc}"
        current_models[commodity].add(model)
        print(f"  + {commodity}/{model}")

# Find all pickle files
print("\n" + "=" * 80)
print("IDENTIFYING STALE PICKLE FILES")
print("=" * 80)

all_pickles = list(volume_path.glob("results_detailed_*.pkl"))
stale_pickles = []

for pickle_file in all_pickles:
    # Parse filename
    name = pickle_file.name.replace("results_detailed_", "").replace(".pkl", "")
    parts = name.split("_", 1)  # Split into commodity and model

    if len(parts) == 2:
        commodity, model = parts

        if commodity in current_models and model not in current_models[commodity]:
            stale_pickles.append(pickle_file)
            print(f"  ✗ STALE: {pickle_file.name}")
        else:
            print(f"  ✓ Keep:  {pickle_file.name}")

# Find stale Delta tables
print("\n" + "=" * 80)
print("IDENTIFYING STALE DELTA TABLES")
print("=" * 80)

tables = spark.sql("""
    SHOW TABLES IN commodity.trading_agent
    LIKE 'results_%_by_year_%'
""").collect()

stale_tables = []

for table_row in tables:
    table_name = table_row.tableName

    # Parse table name
    name = table_name.replace("results_", "").replace("_by_year_", "|")
    parts = name.split("|")

    if len(parts) == 2:
        commodity, model = parts

        if commodity in current_models and model not in current_models[commodity]:
            stale_tables.append(table_name)
            print(f"  ✗ STALE: {table_name}")
        else:
            print(f"  ✓ Keep:  {table_name}")

# Summary
print("\n" + "=" * 80)
print("CLEANUP SUMMARY")
print("=" * 80)

print(f"\nStale pickle files: {len(stale_pickles)}")
for f in stale_pickles:
    size_mb = f.stat().st_size / (1024 * 1024)
    print(f"  - {f.name} ({size_mb:.1f} MB)")

print(f"\nStale Delta tables: {len(stale_tables)}")
for t in stale_tables:
    print(f"  - {t}")

# Cleanup action (commented out for safety)
print("\n" + "=" * 80)
print("CLEANUP ACTIONS")
print("=" * 80)

print("\n⚠️  DRY RUN MODE - No files will be deleted")
print("\nTo actually delete stale files, uncomment the cleanup code below:")
print("\n# Delete stale pickle files:")
print("# for pickle_file in stale_pickles:")
print("#     pickle_file.unlink()")
print("#     print(f'  Deleted: {pickle_file.name}')")
print("\n# Drop stale Delta tables:")
print("# for table_name in stale_tables:")
print("#     spark.sql(f'DROP TABLE IF EXISTS commodity.trading_agent.{table_name}')")
print("#     print(f'  Dropped: {table_name}')")

print("\n" + "=" * 80)
print(f"TOTAL STALE FILES: {len(stale_pickles)} pickles + {len(stale_tables)} tables")
print("=" * 80)
