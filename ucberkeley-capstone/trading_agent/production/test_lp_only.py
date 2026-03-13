#!/usr/bin/env python3
"""
Standalone test for LP optimizer - separate from Optuna

Tests ONLY the LP theoretical maximum calculation
"""
import sys
from pathlib import Path

try:
    script_dir = Path(__file__).parent
    sys.path.insert(0, str(script_dir.parent))
except NameError:
    sys.path.insert(0, '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent')

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from production.strategies.lp_optimizer import solve_optimal_liquidation_lp
from production.core.backtest_engine import BacktestEngine
import pandas as pd

def test_lp_optimizer():
    """Test LP optimizer in isolation."""

    print(f"\n{'='*80}")
    print(f"TESTING LP OPTIMIZER (Standalone)")
    print(f"{'='*80}\n")

    # Get Spark session
    spark = SparkSession.builder.getOrCreate()

    # Load data
    commodity = 'coffee'
    model_version = 'synthetic_acc90'

    print(f"Loading data:")
    print(f"  Commodity: {commodity}")
    print(f"  Model: {model_version}")

    # Load prices from unified_data (continuous daily coverage, forward-filled)
    # Grain is (date, commodity, region) but price is same across regions
    # So aggregate by date to get one row per date
    prices = spark.table("commodity.silver.unified_data").filter(
        f"lower(commodity) = '{commodity}'"
    ).groupBy("date").agg(
        F.first("close").alias("price")  # Price is same across regions, take first
    ).toPandas()

    prices['date'] = pd.to_datetime(prices['date']).dt.normalize()
    prices = prices.sort_values('date').reset_index(drop=True)

    print(f"  Price data: {len(prices)} days ({prices['date'].min()} to {prices['date'].max()})")

    # Load predictions
    pred_table = f"commodity.trading_agent.predictions_{commodity}"
    pred_df = spark.table(pred_table).filter(f"model_version = '{model_version}'").toPandas()

    # Find overlapping dates
    price_dates = set(prices['date'])
    pred_dates = set(pd.to_datetime(pred_df['timestamp']).dt.normalize())
    common_dates = price_dates & pred_dates

    # Filter to common range
    prices = prices[prices['date'].isin(common_dates)].sort_values('date').reset_index(drop=True)

    print(f"  Overlapping data: {len(prices)} days")

    # Create harvest schedule using BacktestEngine
    config = {
        'commodity': commodity,
        'harvest_volume': 50.0,
        'harvest_windows': [(9, 11)],  # Sept-Nov
        'storage_cost_pct_per_day': 0.3,
        'transaction_cost_pct': 2.0
    }

    # Create dummy prediction matrices (empty dict for LP test - no predictions needed)
    dummy_predictions = {}

    dummy_engine = BacktestEngine(prices, dummy_predictions, config)
    harvest_dict = dummy_engine.harvest_schedule

    # Convert to DataFrame
    harvest_data = []
    for date in prices['date']:
        info = harvest_dict.get(date, {'daily_increment': 0.0})
        harvest_data.append({
            'date': date,
            'daily_increment': info.get('daily_increment', 0.0)
        })
    harvest_schedule = pd.DataFrame(harvest_data)

    total_harvest = harvest_schedule['daily_increment'].sum()
    print(f"  Total harvest: {total_harvest:.1f} tons")

    # Run LP optimizer
    print(f"\nRunning LP optimizer...")

    try:
        result = solve_optimal_liquidation_lp(
            prices_df=prices,
            harvest_schedule=harvest_schedule,
            storage_cost_pct_per_day=config['storage_cost_pct_per_day'],
            transaction_cost_pct=config['transaction_cost_pct']
        )

        print(f"\n✅ LP OPTIMIZER SUCCESS")
        print(f"\nResults:")
        print(f"  Max net earnings: ${result['max_net_earnings']:,.2f}")
        print(f"  Total revenue: ${result['total_revenue']:,.2f}")
        print(f"  Transaction costs: ${result['total_transaction_costs']:,.2f}")
        print(f"  Storage costs: ${result['total_storage_costs']:,.2f}")
        print(f"  Number of trades: {len(result['trades'])}")

        # Validation
        total_sold = sum(t['amount'] for t in result['trades'])
        print(f"\nValidation:")
        print(f"  Total sold: {total_sold:.1f} tons")
        print(f"  Total harvested: {total_harvest:.1f} tons")
        print(f"  Match: {'✓' if abs(total_sold - total_harvest) < 0.1 else '✗ MISMATCH!'}")

        if abs(total_sold - total_harvest) >= 0.1:
            print(f"  ERROR: Sold {total_sold:.1f} but harvested {total_harvest:.1f}")
            return False

        return True

    except Exception as e:
        print(f"\n❌ LP OPTIMIZER FAILED")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_lp_optimizer()

    print(f"\n{'='*80}")
    if success:
        print("✅ LP OPTIMIZER TEST PASSED")
    else:
        print("❌ LP OPTIMIZER TEST FAILED")
    print(f"{'='*80}\n")

    if not success:
        raise RuntimeError("LP optimizer test failed")
