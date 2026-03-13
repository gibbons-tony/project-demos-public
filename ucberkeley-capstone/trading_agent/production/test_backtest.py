#!/usr/bin/env python3
"""
Simple test script to verify production backtest functionality.

This tests:
1. Loading data and predictions
2. Running production BacktestEngine
3. Basic strategy execution (ImmediateSaleStrategy)
"""
import sys
from pathlib import Path

# Add parent directory to path
try:
    script_dir = Path(__file__).parent
    sys.path.insert(0, str(script_dir.parent))
except NameError:
    # __file__ not defined in Databricks jobs
    sys.path.insert(0, '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent')

import pandas as pd
from pyspark.sql import SparkSession
from production.config import COMMODITY_CONFIGS, VOLUME_PATH, OUTPUT_SCHEMA, get_data_paths
from production.core.backtest_engine import BacktestEngine
from production.strategies.baseline import ImmediateSaleStrategy
from production.runners.data_loader import DataLoader

def test_production_backtest(commodity='coffee', model_version='synthetic_acc90'):
    """Test production backtest with ImmediateSaleStrategy using production DataLoader."""

    print(f"\n{'='*80}")
    print(f"TESTING PRODUCTION BACKTEST - {commodity.upper()}")
    print(f"Model: {model_version}")
    print(f"{'='*80}\n")

    # Get Spark session
    try:
        spark = SparkSession.builder.getOrCreate()
        print(f"✓ Got Spark session")
    except Exception as e:
        print(f"❌ ERROR getting Spark session: {e}")
        return False

    # Get commodity config
    config = COMMODITY_CONFIGS.get(commodity)
    if not config:
        print(f"❌ ERROR: No config found for commodity '{commodity}'")
        return False

    print(f"\n✓ Loaded config for {commodity}")
    print(f"  - Harvest volume: {config['harvest_volume']:,} bags")
    print(f"  - Harvest windows: {len(config['harvest_windows'])}")
    print(f"  - Storage cost: {config['storage_cost_pct_per_day']*100:.4f}%/day")
    print(f"  - Transaction cost: {config['transaction_cost_pct']*100:.2f}%")

    # Get data paths
    data_paths = get_data_paths(commodity, model_version)

    # Load data using production DataLoader
    try:
        loader = DataLoader(spark=spark)
        prices, prediction_matrices = loader.load_commodity_data(
            commodity=commodity,
            model_version=model_version,
            data_paths=data_paths
        )
        print(f"\n✓ Loaded data via production DataLoader")
        print(f"  - Prices: {len(prices)} rows")
        print(f"  - Date range: {prices['date'].min()} to {prices['date'].max()}")
        print(f"  - Price range: ${prices['price'].min():.2f} - ${prices['price'].max():.2f}")
        print(f"  - Predictions: {len(prediction_matrices)} matrices")
    except Exception as e:
        print(f"❌ ERROR loading data: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Initialize BacktestEngine
    try:
        engine = BacktestEngine(prices, prediction_matrices, config)
        print(f"\n✓ Initialized BacktestEngine")
    except Exception as e:
        print(f"❌ ERROR initializing BacktestEngine: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Initialize ImmediateSaleStrategy (simplest baseline)
    # Use default parameters from strategy class (like original notebook 05)
    try:
        strategy = ImmediateSaleStrategy()
        print(f"\n✓ Initialized ImmediateSaleStrategy")
        print(f"  - Min batch size: {strategy.min_batch_size} bags")
        print(f"  - Sale frequency: {strategy.sale_frequency_days} days")
    except Exception as e:
        print(f"❌ ERROR initializing strategy: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Run backtest
    try:
        print(f"\n{'='*80}")
        print("RUNNING BACKTEST...")
        print(f"{'='*80}\n")

        results = engine.run_backtest(strategy)

        print(f"\n{'='*80}")
        print("BACKTEST RESULTS")
        print(f"{'='*80}\n")

        print(f"✓ Backtest completed successfully!")
        print(f"\n  Net Earnings: ${results['net_earnings']:,.2f}")
        print(f"  Total Revenue: ${results['total_revenue']:,.2f}")
        print(f"  Transaction Costs: ${results['total_transaction_costs']:,.2f}")
        print(f"  Storage Costs: ${results['total_storage_costs']:,.2f}")
        print(f"  Number of Trades: {len(results['trades'])}")

        # Get final inventory from daily_state
        final_inventory = results['daily_state']['inventory'].iloc[-1] if len(results['daily_state']) > 0 else 0
        print(f"  Final Inventory: {final_inventory:,.0f} tons")

        if results['trades']:
            print(f"\n  First trade:")
            first_trade = results['trades'][0]
            print(f"    Day: {first_trade['day']}")
            print(f"    Date: {first_trade['date']}")
            print(f"    Amount: {first_trade['amount']:,.2f} tons")
            print(f"    Price: ${first_trade['price']:.2f}/lb")
            print(f"    Revenue: ${first_trade['revenue']:,.2f}")
            print(f"    Reason: {first_trade['reason']}")

            print(f"\n  Last trade:")
            last_trade = results['trades'][-1]
            print(f"    Day: {last_trade['day']}")
            print(f"    Date: {last_trade['date']}")
            print(f"    Amount: {last_trade['amount']:,.2f} tons")
            print(f"    Price: ${last_trade['price']:.2f}/lb")
            print(f"    Revenue: ${last_trade['revenue']:,.2f}")
            print(f"    Reason: {last_trade['reason']}")

        return True

    except Exception as e:
        print(f"❌ ERROR running backtest: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    # Test with coffee
    success = test_production_backtest('coffee')

    if success:
        print(f"\n{'='*80}")
        print("✅ PRODUCTION BACKTEST TEST PASSED")
        print(f"{'='*80}\n")
        sys.exit(0)
    else:
        print(f"\n{'='*80}")
        print("❌ PRODUCTION BACKTEST TEST FAILED")
        print(f"{'='*80}\n")
        sys.exit(1)
