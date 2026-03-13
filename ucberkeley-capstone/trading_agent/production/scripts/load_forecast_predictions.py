"""
Production Script 02: Load Real Forecast Predictions

Purpose:
    Loads real forecast predictions from commodity.forecast.distributions table
    and transforms them to matrix format for backtesting.

Inputs:
    - Delta table: commodity.forecast.distributions

Outputs:
    - Pickle files: prediction_matrices_{commodity}_{model_version}_real.pkl
    - Matrix format: {timestamp: numpy_array(n_paths, 14)}

Process:
    1. Discover model versions available for each commodity
    2. Load prediction data from table (wide format)
    3. Transform to matrix format (timestamp -> matrix)
    4. Save to pickle file for backtesting

Usage:
    # Process all commodities and all model versions
    python run_02_forecast_predictions.py

    # Process specific commodity
    python run_02_forecast_predictions.py --commodity coffee

    # Process specific commodity and model version
    python run_02_forecast_predictions.py --commodity coffee --model-version arima_v1

Returns:
    Exit code 0 on success, 1 on failure
    Prints JSON summary to stdout for orchestrator integration
"""

import sys
import os
import json
import argparse
from datetime import datetime
import pickle
import pandas as pd
import numpy as np

# Add parent directory to path for imports
# Note: __file__ is not defined in Databricks spark_python_task execution context
# The script is at dbfs:/production/scripts/, so we need to add /dbfs/ to import production.config
sys.path.insert(0, '/dbfs/')

# Configuration imports
from production.config import (
    COMMODITY_CONFIGS,
    get_data_paths,
    get_model_versions,
    load_forecast_data,
    FORECAST_TABLE
)


def process_model_version(commodity, model_version, spark):
    """
    Process a single commodity and model version

    Args:
        commodity: Commodity name (e.g., 'coffee')
        model_version: Model version (e.g., 'arima_v1')
        spark: SparkSession

    Returns:
        dict: Processing results or None on failure
    """
    print(f"\n{'-' * 80}")
    print(f"PROCESSING MODEL VERSION: {model_version}")
    print(f"{'-' * 80}")

    # Get data paths for this model version
    DATA_PATHS = get_data_paths(commodity, model_version)

    # ----------------------------------------------------------------------
    # Load Real Predictions from Table
    # ----------------------------------------------------------------------
    print(f"\nLoading predictions from {FORECAST_TABLE}...")

    try:
        # Load from table for this specific model version
        predictions_wide = load_forecast_data(commodity, model_version, spark)
        print(f"✓ Loaded {len(predictions_wide):,} prediction paths")

        # Display structure
        print(f"\nData structure:")
        print(f"  Columns: {list(predictions_wide.columns)}")
        print(f"  Shape: {predictions_wide.shape}")
        print(f"  Date range: {predictions_wide['forecast_start_date'].min()} to {predictions_wide['forecast_start_date'].max()}")

    except Exception as e:
        print(f"\n❌ Error loading predictions: {e}")
        return None

    # ----------------------------------------------------------------------
    # Check Forecast Quality (Sparsity)
    # ----------------------------------------------------------------------
    print(f"\nChecking forecast quality...")

    # Calculate coverage metrics
    n_forecast_dates = predictions_wide['forecast_start_date'].nunique()
    n_runs_per_date = predictions_wide.groupby('forecast_start_date')['run_id'].nunique()
    avg_runs_per_date = n_runs_per_date.mean()
    min_runs = n_runs_per_date.min()
    max_runs = n_runs_per_date.max()

    # Calculate date coverage (% of expected range that has forecasts)
    min_date = predictions_wide['forecast_start_date'].min()
    max_date = predictions_wide['forecast_start_date'].max()
    expected_days = (max_date - min_date).days + 1  # Total calendar days in range
    coverage_pct = (n_forecast_dates / expected_days) * 100

    print(f"  Date range: {min_date} to {max_date}")
    print(f"  Forecast dates: {n_forecast_dates} / {expected_days} days ({coverage_pct:.1f}% coverage)")
    print(f"  Runs per date: avg={avg_runs_per_date:.1f}, min={min_runs}, max={max_runs}")

    # Quality thresholds
    MIN_DATE_RANGE_DAYS = 730  # Minimum 2 years of data required
    MIN_COVERAGE_PCT = 90.0    # 90%+ date coverage required

    # Check minimum date range
    if expected_days < MIN_DATE_RANGE_DAYS:
        print(f"\n⚠️  SKIPPING: Insufficient date range ({expected_days} days < {MIN_DATE_RANGE_DAYS} days minimum)")
        print(f"   Need at least 2 years of forecasts for meaningful backtesting")
        return None

    # Check date coverage
    if coverage_pct < MIN_COVERAGE_PCT:
        print(f"\n⚠️  SKIPPING: Insufficient date coverage ({coverage_pct:.1f}% < {MIN_COVERAGE_PCT}%)")
        print(f"   Too many gaps in the forecast timeline")
        print(f"   Expected {expected_days} dates in range, only have {n_forecast_dates}")
        return None

    # Quality rating based on coverage
    if coverage_pct >= 95:
        quality = "EXCELLENT"
    else:
        quality = "GOOD"

    print(f"\n✓ Forecast quality: {quality}")
    print(f"  Suitable for backtesting - proceeding with transformation")

    # ----------------------------------------------------------------------
    # Transform to Matrix Format
    # ----------------------------------------------------------------------
    print(f"\nTransforming to matrix format...")

    # Convert forecast_start_date to datetime
    predictions_wide['forecast_start_date'] = pd.to_datetime(predictions_wide['forecast_start_date']).dt.normalize()

    # Identify day columns (day_1 through day_14)
    day_columns = [f'day_{i}' for i in range(1, 15)]

    # Verify all day columns exist
    missing_cols = [col for col in day_columns if col not in predictions_wide.columns]
    if missing_cols:
        print(f"\n❌ Error: Missing day columns: {missing_cols}")
        return None

    # Create prediction matrices dictionary
    # Structure: {timestamp: numpy_array(n_paths, 14)}
    prediction_matrices = {}

    for timestamp in predictions_wide['forecast_start_date'].unique():
        # Get all prediction paths for this timestamp
        day_data = predictions_wide[predictions_wide['forecast_start_date'] == timestamp]

        # Extract the 14-day forecast values into a matrix
        # Each row is a prediction path, each column is a day ahead
        matrix = day_data[day_columns].values

        # Store in dictionary with timestamp as key
        prediction_matrices[pd.Timestamp(timestamp)] = matrix

    print(f"✓ Created {len(prediction_matrices)} prediction matrices")

    # Verify structure
    if len(prediction_matrices) > 0:
        sample_timestamp = list(prediction_matrices.keys())[0]
        sample_matrix = prediction_matrices[sample_timestamp]
        print(f"  Sample matrix shape: {sample_matrix.shape}")
        print(f"  (n_paths={sample_matrix.shape[0]}, n_days={sample_matrix.shape[1]})")

    # ----------------------------------------------------------------------
    # Save Prediction Matrices to Volume
    # ----------------------------------------------------------------------
    matrices_path = DATA_PATHS['prediction_matrices_real']

    # Ensure directory exists
    os.makedirs(os.path.dirname(matrices_path), exist_ok=True)

    with open(matrices_path, 'wb') as f:
        pickle.dump(prediction_matrices, f)

    print(f"\n✓ Saved prediction matrices: {matrices_path}")
    print(f"\n✓ {model_version} complete")

    # Calculate years span and years available
    years_span = expected_days / 365.25
    pred_dates = sorted(prediction_matrices.keys())
    years_available = sorted(set(d.year for d in pred_dates))

    # Return comprehensive metadata for manifest
    return {
        'commodity': commodity,
        'model_version': model_version,
        'type': 'real',
        'n_matrices': len(prediction_matrices),
        'n_paths': sample_matrix.shape[0] if len(prediction_matrices) > 0 else 0,
        'quality': quality,
        'avg_runs_per_date': float(avg_runs_per_date),
        'date_range': {
            'start': str(min_date),
            'end': str(max_date)
        },
        'years_span': float(years_span),
        'expected_days': int(expected_days),
        'prediction_dates': int(n_forecast_dates),
        'coverage_pct': float(coverage_pct),
        'years_available': years_available,
        'meets_criteria': True,  # Already validated before reaching here
        'validation_thresholds': {
            'min_years': 2.0,
            'min_coverage_pct': 90.0
        },
        'pickle_file': os.path.basename(matrices_path),
        'output_path': matrices_path
    }


def create_forecast_manifest(commodity, results_list, volume_path):
    """
    Create manifest file with metadata for all loaded forecast models

    Args:
        commodity: Commodity name
        results_list: List of result dicts from process_model_version
        volume_path: Base path for volume storage

    Returns:
        str: Path to manifest file
    """
    manifest = {
        'commodity': commodity,
        'generated_at': datetime.now().isoformat(),
        'models': {}
    }

    # Add each model's metadata
    for result in results_list:
        model_version = result['model_version']
        manifest['models'][model_version] = {
            'type': result['type'],
            'date_range': result['date_range'],
            'years_span': result['years_span'],
            'expected_days': result['expected_days'],
            'prediction_dates': result['prediction_dates'],
            'coverage_pct': result['coverage_pct'],
            'years_available': result['years_available'],
            'meets_criteria': result['meets_criteria'],
            'validation_thresholds': result['validation_thresholds'],
            'quality': result['quality'],
            'n_paths': result['n_paths'],
            'pickle_file': result['pickle_file']
        }

    # Save manifest
    manifest_path = os.path.join(volume_path, f'forecast_manifest_{commodity}.json')

    # Ensure directory exists
    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)

    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    print(f"\n✓ Created forecast manifest: {manifest_path}")
    print(f"  Models included: {len(manifest['models'])}")

    return manifest_path


def run_forecast_predictions(commodities=None, model_versions_filter=None):
    """
    Main runner: Load and transform forecast predictions for all commodities and models

    Args:
        commodities: List of commodity names, or None for all
        model_versions_filter: List of model versions to filter, or None for all

    Returns:
        Tuple of (status_code, summary_dict)
    """
    start_time = datetime.now()
    print("=" * 80)
    print("FORECAST PREDICTIONS - LOAD AND TRANSFORM")
    print("=" * 80)
    print(f"Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Initialize Spark
    try:
        from pyspark.sql import SparkSession
        spark = SparkSession.builder.appName("ForecastPredictions").getOrCreate()
        print("✓ Spark session initialized")
    except Exception as e:
        print(f"✗ Failed to initialize Spark: {e}")
        return 1, {"error": str(e), "status": "failed"}

    # Determine commodities to process
    if commodities is None:
        commodities = list(COMMODITY_CONFIGS.keys())
    elif isinstance(commodities, str):
        commodities = [commodities]

    print(f"\nCommodities to process: {commodities}")

    # Track results
    all_results = []
    failed_processes = []
    manifests_created = []

    # Get volume path from config
    from production.config import VOLUME_PATH

    # Loop through all commodities
    for CURRENT_COMMODITY in commodities:
        print(f"\n{'=' * 80}")
        print(f"PROCESSING: {CURRENT_COMMODITY.upper()}")
        print(f"{'=' * 80}")

        # Get configuration for this commodity
        CURRENT_CONFIG = COMMODITY_CONFIGS[CURRENT_COMMODITY]

        # --------------------------------------------------------------------------
        # Get Model Versions Available for This Commodity
        # --------------------------------------------------------------------------
        print(f"\nDiscovering model versions for {CURRENT_COMMODITY}...")

        try:
            model_versions = get_model_versions(CURRENT_COMMODITY)
        except Exception as e:
            print(f"⚠️  Error discovering model versions: {e}")
            model_versions = []

        # Apply filter if provided
        if model_versions_filter:
            model_versions = [mv for mv in model_versions if mv in model_versions_filter]

        if len(model_versions) == 0:
            print(f"\n⚠️  No forecast data found in table for {CURRENT_COMMODITY}")
            print(f"   Skipping {CURRENT_COMMODITY.upper()}")
            continue

        print(f"✓ Found {len(model_versions)} model versions:")
        for mv in model_versions:
            print(f"  - {mv}")

        # --------------------------------------------------------------------------
        # Process Each Model Version
        # --------------------------------------------------------------------------
        commodity_results = []  # Track results for this commodity only

        for MODEL_VERSION in model_versions:
            try:
                result = process_model_version(CURRENT_COMMODITY, MODEL_VERSION, spark)
                if result:
                    all_results.append(result)
                    commodity_results.append(result)
                else:
                    failed_processes.append({
                        'commodity': CURRENT_COMMODITY,
                        'model_version': MODEL_VERSION,
                        'reason': 'No results returned'
                    })
            except Exception as e:
                print(f"\n✗ ERROR processing {CURRENT_COMMODITY} - {MODEL_VERSION}: {e}")
                failed_processes.append({
                    'commodity': CURRENT_COMMODITY,
                    'model_version': MODEL_VERSION,
                    'error': str(e)
                })

        # --------------------------------------------------------------------------
        # Create Forecast Manifest for This Commodity
        # --------------------------------------------------------------------------
        if commodity_results:
            try:
                manifest_path = create_forecast_manifest(
                    CURRENT_COMMODITY,
                    commodity_results,
                    VOLUME_PATH
                )
                manifests_created.append(manifest_path)
            except Exception as e:
                print(f"\n⚠️  Warning: Could not create manifest for {CURRENT_COMMODITY}: {e}")

        print(f"\n{'=' * 80}")
        print(f"✓ {CURRENT_COMMODITY.upper()} COMPLETE")
        print(f"{'=' * 80}")

    # Final summary
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    print("\n" + "=" * 80)
    print("ALL COMMODITIES AND MODEL VERSIONS PROCESSED")
    print("=" * 80)
    print(f"Completed: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Duration: {duration:.1f} seconds")
    print(f"Successful processes: {len(all_results)}")
    print(f"Failed processes: {len(failed_processes)}")
    print(f"Manifests created: {len(manifests_created)}")

    if failed_processes:
        print("\nFailed processes:")
        for failure in failed_processes:
            print(f"  - {failure['commodity']} - {failure['model_version']}: {failure.get('reason', failure.get('error', 'Unknown'))}")

    # Prepare summary for orchestrator
    summary = {
        'script': 'load_forecast_predictions.py',
        'status': 'success' if len(failed_processes) == 0 else 'partial',
        'start_time': start_time.isoformat(),
        'end_time': end_time.isoformat(),
        'duration_seconds': duration,
        'commodities_processed': commodities,
        'successful_processes': len(all_results),
        'failed_processes': len(failed_processes),
        'manifests_created': len(manifests_created),
        'manifest_paths': manifests_created,
        'results': all_results,
        'failures': failed_processes
    }

    return 0 if len(failed_processes) == 0 else 1, summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Load and transform forecast predictions for all commodities and model versions'
    )
    parser.add_argument(
        '--commodity',
        type=str,
        help='Single commodity to process (e.g., coffee). Default: all commodities'
    )
    parser.add_argument(
        '--commodities',
        type=str,
        help='Comma-separated list of commodities (e.g., coffee,sugar). Default: all commodities'
    )
    parser.add_argument(
        '--model-version',
        type=str,
        help='Single model version to process (e.g., arima_v1). Default: all model versions'
    )
    parser.add_argument(
        '--model-versions',
        type=str,
        help='Comma-separated list of model versions. Default: all model versions'
    )

    args = parser.parse_args()

    # Parse commodities
    commodities = None
    if args.commodities:
        commodities = [c.strip() for c in args.commodities.split(',')]
    elif args.commodity:
        commodities = [args.commodity]

    # Parse model versions
    model_versions = None
    if args.model_versions:
        model_versions = [mv.strip() for mv in args.model_versions.split(',')]
    elif args.model_version:
        model_versions = [args.model_version]

    # Run processing
    status_code, summary = run_forecast_predictions(
        commodities=commodities,
        model_versions_filter=model_versions
    )

    # Print JSON summary for orchestrator
    print("\n" + "=" * 80)
    print("JSON SUMMARY (for orchestrator)")
    print("=" * 80)
    print(json.dumps(summary, indent=2))

    sys.exit(status_code)
