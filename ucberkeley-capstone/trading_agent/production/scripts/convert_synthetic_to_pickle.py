"""
Convert Synthetic Predictions from Delta Tables to Pickle Files

Purpose:
    Reads synthetic predictions from Delta tables and converts them to
    prediction matrix pickle files for use by the backtest runner.

Inputs:
    - Delta table: commodity.trading_agent.predictions_{commodity}

Outputs:
    - Pickle files: prediction_matrices_{commodity}_{model_version}.pkl
    - Format: {timestamp: numpy_array(n_runs, n_horizons)}

Usage:
    # Convert all synthetic predictions
    python convert_synthetic_to_pickle.py

    # Convert specific commodity
    python convert_synthetic_to_pickle.py --commodity coffee

    # Convert specific model version
    python convert_synthetic_to_pickle.py --commodity coffee --model-version synthetic_acc100
"""

import sys
import os
import argparse
import pickle
import pandas as pd
import numpy as np
from datetime import datetime

# Add parent directory to path for imports
# Use try/except to handle both local and Databricks environments
try:
    # Try local import first
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from production.config import COMMODITY_CONFIGS, OUTPUT_SCHEMA, VOLUME_PATH
except (NameError, ModuleNotFoundError):
    # Databricks environment - define constants directly
    print("⚠️  Running in Databricks - using hardcoded config constants")
    COMMODITY_CONFIGS = {
        'coffee': {'commodity': 'coffee'},
        'sugar': {'commodity': 'sugar'}
    }
    OUTPUT_SCHEMA = "commodity.trading_agent"
    VOLUME_PATH = "/Volumes/commodity/trading_agent/files"


def convert_model_to_pickle(spark, commodity, model_version):
    """
    Convert a single model's predictions from Delta to pickle format.

    Args:
        spark: SparkSession
        commodity: Commodity name (e.g., 'coffee')
        model_version: Model version (e.g., 'synthetic_acc100')

    Returns:
        dict with conversion results
    """
    print(f"\n{'='*80}")
    print(f"Converting: {commodity.upper()} - {model_version}")
    print(f"{'='*80}")

    # Load from Delta table
    table_name = f"{OUTPUT_SCHEMA}.predictions_{commodity.lower()}"

    print(f"\n1. Loading from Delta table: {table_name}")
    try:
        df = spark.table(table_name).filter(
            f"model_version = '{model_version}'"
        ).toPandas()
    except Exception as e:
        print(f"❌ Error loading table: {e}")
        return None

    if len(df) == 0:
        print(f"⚠️  No data found for {model_version} in {table_name}")
        return None

    print(f"   ✓ Loaded {len(df):,} rows")

    # Get dimensions
    n_runs = df['run_id'].nunique()
    n_horizons = df['day_ahead'].nunique()
    n_timestamps = df['timestamp'].nunique()

    print(f"\n2. Prediction structure:")
    print(f"   • Timestamps: {n_timestamps}")
    print(f"   • Runs: {n_runs}")
    print(f"   • Horizons: {n_horizons}")

    # Convert to matrix format
    print(f"\n3. Converting to matrix format...")

    # Ensure datetime types
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    prediction_matrices = {}

    # Group by timestamp and convert each to matrix
    for timestamp, group in df.groupby('timestamp'):
        # Pivot to create matrix: rows=runs, cols=horizons
        matrix_df = group.pivot(
            index='run_id',
            columns='day_ahead',
            values='predicted_price'
        )

        # Convert to numpy array (sorted by run_id and day_ahead)
        matrix = matrix_df.sort_index(axis=0).sort_index(axis=1).values

        # Validate shape
        if matrix.shape != (n_runs, n_horizons):
            print(f"⚠️  Warning: Unexpected shape at {timestamp}: {matrix.shape}")
            continue

        prediction_matrices[timestamp] = matrix

    print(f"   ✓ Converted {len(prediction_matrices)} timestamp matrices")

    # Validate all timestamps have data
    if len(prediction_matrices) != n_timestamps:
        print(f"   ⚠️  Warning: {n_timestamps - len(prediction_matrices)} timestamps missing")

    # Save to pickle
    pickle_filename = f"prediction_matrices_{commodity.lower()}_{model_version}.pkl"
    pickle_path = os.path.join(VOLUME_PATH, pickle_filename)

    print(f"\n4. Saving to pickle file:")
    print(f"   Path: {pickle_path}")

    try:
        with open(pickle_path, 'wb') as f:
            pickle.dump(prediction_matrices, f)

        file_size_mb = os.path.getsize(pickle_path) / (1024 * 1024)
        print(f"   ✓ Saved: {file_size_mb:.1f} MB")

        return {
            'commodity': commodity,
            'model_version': model_version,
            'n_timestamps': len(prediction_matrices),
            'n_runs': n_runs,
            'n_horizons': n_horizons,
            'pickle_path': pickle_path,
            'file_size_mb': round(file_size_mb, 2)
        }

    except Exception as e:
        print(f"   ❌ Error saving pickle: {e}")
        return None


def discover_synthetic_models(spark, commodity):
    """
    Discover all synthetic model versions for a commodity.

    Args:
        spark: SparkSession
        commodity: Commodity name

    Returns:
        List of model version strings
    """
    table_name = f"{OUTPUT_SCHEMA}.predictions_{commodity.lower()}"

    try:
        models_df = spark.table(table_name).select('model_version').distinct()
        all_models = [row.model_version for row in models_df.collect()]
        synthetic_models = [m for m in all_models if m.startswith('synthetic_')]
        return sorted(synthetic_models)
    except Exception as e:
        print(f"⚠️  Error discovering models for {commodity}: {e}")
        return []


def main():
    """Main conversion runner"""
    parser = argparse.ArgumentParser(
        description='Convert synthetic predictions from Delta tables to pickle files'
    )
    parser.add_argument(
        '--commodity',
        type=str,
        help='Commodity to convert (default: all)'
    )
    parser.add_argument(
        '--model-version',
        type=str,
        help='Specific model version to convert (default: all synthetic)'
    )

    args = parser.parse_args()

    # Initialize Spark
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.getOrCreate()

    print("="*80)
    print("SYNTHETIC PREDICTIONS: DELTA TO PICKLE CONVERSION")
    print("="*80)
    print(f"\nOutput directory: {VOLUME_PATH}")

    # Determine commodities to process
    if args.commodity:
        commodities = [args.commodity]
    else:
        commodities = list(COMMODITY_CONFIGS.keys())

    print(f"Commodities: {', '.join(commodities)}")

    # Process each commodity
    all_results = []

    for commodity in commodities:
        print(f"\n{'#'*80}")
        print(f"# COMMODITY: {commodity.upper()}")
        print(f"{'#'*80}")

        # Discover or use specified model versions
        if args.model_version:
            model_versions = [args.model_version]
        else:
            model_versions = discover_synthetic_models(spark, commodity)

        if not model_versions:
            print(f"⚠️  No synthetic models found for {commodity}")
            continue

        print(f"\nFound {len(model_versions)} synthetic models:")
        for mv in model_versions:
            print(f"  - {mv}")

        # Convert each model version
        for model_version in model_versions:
            result = convert_model_to_pickle(spark, commodity, model_version)
            if result:
                all_results.append(result)

    # Summary
    print(f"\n{'='*80}")
    print("CONVERSION COMPLETE")
    print(f"{'='*80}")
    print(f"\nSuccessfully converted: {len(all_results)} model versions")

    for result in all_results:
        print(f"\n  {result['commodity']} - {result['model_version']}:")
        print(f"    • Timestamps: {result['n_timestamps']}")
        print(f"    • Matrix shape: {result['n_runs']} runs × {result['n_horizons']} horizons")
        print(f"    • File size: {result['file_size_mb']} MB")
        print(f"    • Path: {result['pickle_path']}")

    print(f"\n✓ Pickle files are now ready for backtest runner")

    return 0 if len(all_results) > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
