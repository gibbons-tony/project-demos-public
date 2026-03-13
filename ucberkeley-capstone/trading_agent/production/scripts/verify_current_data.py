"""
Verify which models are current and if backtest results are up-to-date
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

from pyspark.sql import SparkSession
from pathlib import Path
from datetime import datetime

spark = SparkSession.builder.getOrCreate()

print("=" * 80)
print("VERIFYING CURRENT MODELS AND DATA FRESHNESS")
print("=" * 80)

# Step 1: Get current models from forecast.distributions
print("\nSTEP 1: Discovering CURRENT models from forecast.distributions")
print("-" * 80)

current_models = {}

for commodity in ['Coffee', 'Sugar']:
    print(f"\n{commodity}:")

    # Real forecast models
    query = f"""
    SELECT DISTINCT model_version, COUNT(*) as pred_count
    FROM commodity.forecast.distributions
    WHERE commodity = '{commodity}' AND is_actuals = false
    GROUP BY model_version
    ORDER BY model_version
    """

    df = spark.sql(query)
    models = [(row.model_version, row.pred_count) for row in df.collect()]

    if models:
        current_models[commodity.lower()] = [m[0] for m in models]
        for model, count in models:
            print(f"  ✓ {model:<30} ({count:,} predictions)")
    else:
        current_models[commodity.lower()] = []
        print(f"  ⚠️  No models found in forecast.distributions")

    # Check synthetic models
    try:
        syn_query = f"""
        SELECT DISTINCT model_version, COUNT(*) as pred_count
        FROM commodity.trading_agent.predictions_{commodity.lower()}
        GROUP BY model_version
        ORDER BY model_version
        """
        syn_df = spark.sql(syn_query)
        syn_models = [(row.model_version, row.pred_count) for row in syn_df.collect()]

        if syn_models:
            print(f"\n  Synthetic models:")
            for model, count in syn_models:
                print(f"    ✓ {model:<30} ({count:,} predictions)")
                if model not in current_models[commodity.lower()]:
                    current_models[commodity.lower()].append(model)
    except:
        pass

# Step 2: Check which models have backtest results
print("\n" + "=" * 80)
print("STEP 2: Checking which models have backtest results")
print("-" * 80)

pickle_dir = Path("/Volumes/commodity/trading_agent/files/")

for commodity, models in current_models.items():
    print(f"\n{commodity.upper()}: {len(models)} current models")

    for model in models:
        # Check for detailed results pickle
        pickle_file = pickle_dir / f"results_detailed_{commodity}_{model}.pkl"

        if pickle_file.exists():
            stat = pickle_file.stat()
            mod_time = datetime.fromtimestamp(stat.st_mtime)
            size_mb = stat.st_size / (1024 * 1024)

            print(f"  ✓ {model:<30} (modified: {mod_time.strftime('%Y-%m-%d %H:%M')}, {size_mb:.1f} MB)")
        else:
            print(f"  ✗ {model:<30} NO BACKTEST RESULTS FILE")

# Step 3: Check year-by-year results tables
print("\n" + "=" * 80)
print("STEP 3: Checking year-by-year results tables (Delta)")
print("-" * 80)

tables = spark.sql("""
    SHOW TABLES IN commodity.trading_agent
    LIKE 'results_%_by_year_%'
""").collect()

for commodity, models in current_models.items():
    print(f"\n{commodity.upper()}:")

    for model in models:
        table_name = f"results_{commodity}_by_year_{model}"

        if any(t.tableName == table_name for t in tables):
            # Get last modified time
            try:
                desc = spark.sql(f"DESCRIBE DETAIL commodity.trading_agent.{table_name}").collect()[0]
                mod_time = desc.lastModified

                # Get row count and strategies
                count_df = spark.sql(f"SELECT COUNT(DISTINCT strategy) as n_strategies, COUNT(DISTINCT year) as n_years FROM commodity.trading_agent.{table_name}")
                stats = count_df.collect()[0]

                print(f"  ✓ {model:<30} ({stats.n_strategies} strategies, {stats.n_years} years, modified: {mod_time.strftime('%Y-%m-%d')})")
            except Exception as e:
                print(f"  ✓ {model:<30} (table exists but couldn't read metadata)")
        else:
            print(f"  ✗ {model:<30} NO DELTA TABLE")

# Step 4: Summary and recommendations
print("\n" + "=" * 80)
print("SUMMARY AND RECOMMENDATIONS")
print("=" * 80)

total_current = sum(len(models) for models in current_models.values())
print(f"\nTotal CURRENT models: {total_current}")

for commodity, models in current_models.items():
    print(f"\n{commodity.upper()}: {len(models)} models")
    for model in models:
        print(f"  - {model}")

print("\n" + "-" * 80)
print("NEXT STEPS:")
print("-" * 80)
print("\n1. If backtest results are missing or old:")
print("   Run: python production/run_backtest_workflow.py --mode full")
print("\n2. After confirming data is current, run statistical analysis:")
print("   Only test the models listed above")
print("\n3. For statistical testing, modify batch_rigorous_analysis.py to:")
print("   - Query forecast.distributions to get current models")
print("   - Skip models that aren't in current_models list")

print("\n" + "=" * 80)
