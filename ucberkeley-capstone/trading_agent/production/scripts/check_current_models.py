"""
Check which models are actually in current use vs old pickle files
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

spark = SparkSession.builder.getOrCreate()

print("=" * 80)
print("CHECKING WHICH MODELS ARE CURRENTLY LOADED")
print("=" * 80)

# Check predictions table for coffee
print("\n1. COFFEE - Synthetic Models (commodity.trading_agent.predictions_coffee)")
try:
    coffee_pred_df = spark.sql("""
        SELECT DISTINCT model_version
        FROM commodity.trading_agent.predictions_coffee
        ORDER BY model_version
    """)
    coffee_synth = [row.model_version for row in coffee_pred_df.collect()]
    print(f"   Found {len(coffee_synth)} models:")
    for m in coffee_synth:
        print(f"     - {m}")
except Exception as e:
    print(f"   Error: {e}")
    coffee_synth = []

# Check forecast.distributions for coffee real models
print("\n2. COFFEE - Real Models (commodity.forecast.distributions)")
try:
    coffee_real_df = spark.sql("""
        SELECT DISTINCT model_version
        FROM commodity.forecast.distributions
        WHERE commodity = 'Coffee' AND is_actuals = false
        ORDER BY model_version
    """)
    coffee_real = [row.model_version for row in coffee_real_df.collect()]
    print(f"   Found {len(coffee_real)} models:")
    for m in coffee_real:
        print(f"     - {m}")
except Exception as e:
    print(f"   Error: {e}")
    coffee_real = []

# Check sugar
print("\n3. SUGAR - Synthetic Models (commodity.trading_agent.predictions_sugar)")
try:
    sugar_pred_df = spark.sql("""
        SELECT DISTINCT model_version
        FROM commodity.trading_agent.predictions_sugar
        ORDER BY model_version
    """)
    sugar_synth = [row.model_version for row in sugar_pred_df.collect()]
    print(f"   Found {len(sugar_synth)} models:")
    for m in sugar_synth:
        print(f"     - {m}")
except Exception as e:
    print(f"   Error: {e}")
    sugar_synth = []

print("\n4. SUGAR - Real Models (commodity.forecast.distributions)")
try:
    sugar_real_df = spark.sql("""
        SELECT DISTINCT model_version
        FROM commodity.forecast.distributions
        WHERE commodity = 'Sugar' AND is_actuals = false
        ORDER BY model_version
    """)
    sugar_real = [row.model_version for row in sugar_real_df.collect()]
    print(f"   Found {len(sugar_real)} models:")
    for m in sugar_real:
        print(f"     - {m}")
except Exception as e:
    print(f"   Error: {e}")
    sugar_real = []

# Summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
coffee_total = set(coffee_synth + coffee_real)
sugar_total = set(sugar_synth + sugar_real)
total_models = len(coffee_total) + len(sugar_total)

print(f"\nModels that WOULD BE RUN by current backtest workflow:")
print(f"  Coffee: {len(coffee_total)} models")
print(f"  Sugar: {len(sugar_total)} models")
print(f"  TOTAL: {total_models} models")

# Check year-by-year tables
print("\n" + "=" * 80)
print("YEAR-BY-YEAR RESULTS TABLES (from pickle files)")
print("=" * 80)

tables = spark.sql("""
    SHOW TABLES IN commodity.trading_agent
    LIKE 'results_*_by_year_*'
""").collect()

print(f"\nFound {len(tables)} year-by-year results tables:")

coffee_tables = [t for t in tables if 'coffee' in t.tableName]
sugar_tables = [t for t in tables if 'sugar' in t.tableName]

print(f"\n  Coffee tables: {len(coffee_tables)}")
for t in sorted([t.tableName for t in coffee_tables]):
    model = t.replace('results_coffee_by_year_', '')
    in_current = model in coffee_total
    print(f"    - {model:<30} {'✓ IN CURRENT' if in_current else '✗ OLD PICKLE'}")

print(f"\n  Sugar tables: {len(sugar_tables)}")
for t in sorted([t.tableName for t in sugar_tables]):
    model = t.replace('results_sugar_by_year_', '')
    in_current = model in sugar_total
    print(f"    - {model:<30} {'✓ IN CURRENT' if in_current else '✗ OLD PICKLE'}")

print("\n" + "=" * 80)
print("CONCLUSION")
print("=" * 80)
print(f"\nThe batch statistical analysis tested {len(tables)} models")
print(f"But only {total_models} models are in current use")
print(f"\nDifference: {len(tables) - total_models} models are from old pickle files")
print("\nThis means we tested data that may not match the current backtest workflow!")
