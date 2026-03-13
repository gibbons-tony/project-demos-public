"""
Production Script: Generate Synthetic Predictions (v8)

Converted from: 01_synthetic_predictions_v8.ipynb
Purpose: Generate calibrated synthetic predictions at multiple accuracy levels
Outputs: Delta tables + validation pickle file

Usage:
    # All commodities, all accuracy levels
    python run_01_synthetic_predictions.py

    # Single commodity
    python run_01_synthetic_predictions.py --commodity coffee

    # Custom accuracy levels
    python run_01_synthetic_predictions.py --accuracies 1.0,0.9,0.8

v8 Features:
- Log-normal centered at ±target_mape (not 0) for accurate MAPE targeting
- Stores actual future_date to avoid calendar misalignment
- Run-specific biases for realistic horizon correlation
"""

import sys
import os
import json
import argparse
import pickle
from datetime import datetime
from builtins import min as builtin_min

import pandas as pd
import numpy as np
import gc

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from production.config import (
    COMMODITY_CONFIGS,
    ANALYSIS_CONFIG,
    OUTPUT_SCHEMA,
    VOLUME_PATH,
    MARKET_TABLE
)


# =============================================================================
# PREDICTION GENERATION FUNCTIONS
# =============================================================================

def generate_calibrated_predictions(prices_df, model_version, target_accuracy=0.90,
                                    n_runs=2000, n_horizons=14, chunk_size=20):
    """
    Generate calibrated synthetic predictions.

    v8: Log-normal centered at ±target_mape (not 0) to achieve target MAPE on median.

    Args:
        prices_df: DataFrame with 'date' and 'price' columns
        model_version: Model identifier (e.g., "synthetic_acc90")
        target_accuracy: Target accuracy level (0.90 = 90% accurate = 10% MAPE)
        n_runs: Number of Monte Carlo runs
        n_horizons: Forecast horizon (days ahead)
        chunk_size: Chunk size for memory management

    Returns:
        DataFrame with predictions
    """
    n_dates = len(prices_df) - n_horizons
    target_mape = 1.0 - target_accuracy

    print(f"    Target MAPE: {target_mape:.1%}")

    all_chunks = []

    for chunk_start in range(0, n_dates, chunk_size):
        chunk_end = builtin_min(chunk_start + chunk_size, n_dates)
        chunk_records = []

        for i in range(chunk_start, chunk_end):
            current_date = prices_df.loc[i, 'date']

            # Get actual future dates AND prices (row-based, not calendar-based)
            future_rows = prices_df.loc[i+1:i+n_horizons]
            future_dates = future_rows['date'].values
            future_prices = future_rows['price'].values

            # Ensure we have exactly n_horizons entries
            if len(future_prices) < n_horizons:
                continue

            if target_accuracy == 1.0:
                # ========================================================================
                # SPECIAL CASE: 100% Accuracy (Perfect Foresight)
                # ========================================================================
                # For acc100, we simply copy the actual realized prices with zero noise.
                # This creates "predictions" that are identical to what actually happened.
                #
                # Data Flow:
                #   commodity.forecast.forecast_actuals (source of truth)
                #     ↓
                #   commodity.silver.unified_data (forward-filled, continuous daily)
                #     ↓
                #   prices_df (loaded in this script)
                #     ↓
                #   future_prices (extracted above from prices_df)
                #     ↓
                #   predicted_prices_matrix (perfect foresight "predictions")
                #
                # NOTE: Unlike acc60/70/80/90, there is NO predictions table for acc100
                #       in commodity.trading_agent (e.g., no predictions_prepared_coffee_synthetic_acc100).
                #       The acc100 "predictions" exist ONLY in the pickle file.
                #       Results tables DO exist: results_{commodity}_synthetic_acc100
                #
                # Why: A predictions table would be redundant - it would just duplicate
                #      the actuals that already exist in forecast_actuals.
                # ========================================================================
                predicted_prices_matrix = np.tile(future_prices, (n_runs, 1))
            else:
                # v8 FIX: Center log-normal at ±target_mape for each timestamp
                # Randomly bias this timestamp's predictions up or down by target_mape
                bias_direction = np.random.choice([-1, 1])  # Randomly high or low
                target_multiplier = 1.0 + bias_direction * target_mape
                log_center = np.log(target_multiplier)

                # Generate log-normal errors centered at log_center (not 0!)
                sigma_lognormal = target_mape * np.sqrt(np.pi / 2)
                log_errors = np.random.normal(log_center, sigma_lognormal, (n_runs, n_horizons))
                multiplicative_errors = np.exp(log_errors)

                future_prices_matrix = np.tile(future_prices, (n_runs, 1))
                predicted_prices_matrix = future_prices_matrix * multiplicative_errors

                # Add run-specific bias for realistic correlation across horizons
                run_biases = np.random.normal(1.0, 0.02, (n_runs, 1))
                predicted_prices_matrix *= run_biases

            # Store predictions with actual future_date
            for run_id in range(1, n_runs + 1):
                for day_ahead in range(1, n_horizons + 1):
                    chunk_records.append({
                        'timestamp': current_date,
                        'future_date': future_dates[day_ahead-1],
                        'run_id': run_id,
                        'day_ahead': day_ahead,
                        'predicted_price': predicted_prices_matrix[run_id-1, day_ahead-1],
                        'model_version': model_version
                    })

        chunk_df = pd.DataFrame(chunk_records)
        all_chunks.append(chunk_df)
        del chunk_records
        gc.collect()

        if chunk_end % 100 == 0 or chunk_end == n_dates:
            print(f"    Progress: {chunk_end}/{n_dates} dates...")

    final_df = pd.concat(all_chunks, ignore_index=True)
    del all_chunks
    gc.collect()

    return final_df


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def calculate_crps(actuals, forecast_paths):
    """
    Calculate Continuous Ranked Probability Score (CRPS).

    Args:
        actuals: Array of actual values (horizon,)
        forecast_paths: Array of forecast paths (n_runs, horizon)

    Returns:
        List of CRPS values per time step
    """
    n_paths, horizon = forecast_paths.shape
    crps_values = []

    for t in range(horizon):
        if np.isnan(actuals[t]):
            continue
        actual = actuals[t]
        sorted_samples = np.sort(forecast_paths[:, t])
        term1 = np.mean(np.abs(sorted_samples - actual))
        n = len(sorted_samples)
        indices = np.arange(1, n + 1)
        term2 = np.sum((2 * indices - 1) * sorted_samples) / (n ** 2) - np.mean(sorted_samples)
        crps_values.append(term1 - 0.5 * term2)

    return crps_values


def calculate_directional_accuracy(actuals, forecasts):
    """
    Calculate directional accuracy metrics.

    Args:
        actuals: Series of actual values
        forecasts: Series of forecast values

    Returns:
        Dictionary with directional accuracy metrics
    """
    metrics = {}

    # Day-to-day directional accuracy
    if len(actuals) > 1:
        actual_direction = np.sign(actuals.diff().dropna())
        forecast_direction = np.sign(forecasts.diff().dropna())
        correct_direction = (actual_direction == forecast_direction).sum()
        metrics['directional_accuracy'] = float(correct_direction / len(actual_direction) * 100)

    # Directional accuracy from day 0
    if len(actuals) > 1:
        day_0_actual = actuals.iloc[0]
        day_0_forecast = forecasts.iloc[0]
        correct_from_day0 = sum(1 for i in range(1, len(actuals))
                               if (actuals.iloc[i] > day_0_actual) == (forecasts.iloc[i] > day_0_forecast))
        metrics['directional_accuracy_from_day0'] = float(correct_from_day0 / (len(actuals) - 1) * 100)

    return metrics


def validate_predictions(predictions_df, prices_df, commodity, model_version,
                        target_accuracy, n_horizons=14):
    """
    Validate predictions against actuals using stored future_date.

    Args:
        predictions_df: DataFrame with predictions
        prices_df: DataFrame with actual prices
        commodity: Commodity name
        model_version: Model identifier
        target_accuracy: Target accuracy level
        n_horizons: Forecast horizon

    Returns:
        Dictionary with validation metrics
    """
    print(f"\n  Validating predictions...")

    # Group by timestamp, day_ahead, future_date and compute median
    medians = predictions_df.groupby(['timestamp', 'day_ahead', 'future_date'])['predicted_price'].median().reset_index()
    medians.columns = ['timestamp', 'day_ahead', 'future_date', 'median_pred']

    prices_df = prices_df.copy()
    prices_df['date'] = pd.to_datetime(prices_df['date'])

    # Merge with actuals using stored future_date (FIXED)
    results = []
    for _, row in medians.iterrows():
        timestamp = row['timestamp']
        day_ahead = int(row['day_ahead'])
        future_date = pd.to_datetime(row['future_date'])
        median_pred = row['median_pred']

        # Use stored future_date instead of calendar calculation
        actual_row = prices_df[prices_df['date'] == future_date]

        if len(actual_row) > 0:
            actual_price = actual_row['price'].values[0]
            ape = abs(median_pred - actual_price) / actual_price
            ae = abs(median_pred - actual_price)
            results.append({
                'timestamp': timestamp,
                'day_ahead': day_ahead,
                'future_date': future_date,
                'median_pred': median_pred,
                'actual': actual_price,
                'ape': ape,
                'ae': ae
            })

    if len(results) == 0:
        print(f"    ⚠️  No matching actuals")
        return None

    results_df = pd.DataFrame(results)
    target_mape = 1.0 - target_accuracy

    # Overall metrics
    overall_mae = results_df['ae'].mean()
    overall_mape = results_df['ape'].mean()

    print(f"\n    Overall: MAE=${overall_mae:.2f}, MAPE={overall_mape:.1%} (target: {target_mape:.1%})")

    # Per-horizon
    per_horizon = results_df.groupby('day_ahead').agg({
        'ae': ['mean', 'std'], 'ape': ['mean', 'std'], 'timestamp': 'count'
    })
    per_horizon.columns = ['mae_mean', 'mae_std', 'mape_mean', 'mape_std', 'n_samples']

    print(f"\n    Per-Horizon:")
    for h in sorted(per_horizon.index)[:5]:  # Show first 5
        mape = per_horizon.loc[h, 'mape_mean']
        status = '✓' if mape <= target_mape * 1.15 else '⚠️'
        print(f"      Day {h:2d}: MAPE={mape:5.1%} {status}")

    # Directional accuracy
    timestamps = results_df['timestamp'].unique()
    dir_data = []
    for ts in timestamps:
        ts_data = results_df[results_df['timestamp'] == ts].sort_values('day_ahead')
        if len(ts_data) >= 2:
            dir_m = calculate_directional_accuracy(
                pd.Series(ts_data['actual'].values),
                pd.Series(ts_data['median_pred'].values)
            )
            dir_m['timestamp'] = ts
            dir_data.append(dir_m)

    dir_df = pd.DataFrame(dir_data)
    if len(dir_df) > 0:
        print(f"    Directional: {dir_df['directional_accuracy'].mean():.1f}% (day-to-day), "
              f"{dir_df['directional_accuracy_from_day0'].mean():.1f}% (from day 0)")

    # CRPS (sample)
    sample_ts = np.random.choice(timestamps, size=min(50, len(timestamps)), replace=False)
    crps_data = []
    for ts in sample_ts:
        ts_pred = predictions_df[predictions_df['timestamp'] == ts]
        matrix = ts_pred.pivot_table(index='run_id', columns='day_ahead', values='predicted_price').values
        actuals = results_df[results_df['timestamp'] == ts].sort_values('day_ahead')['actual'].values
        if len(actuals) == matrix.shape[1]:
            crps_vals = calculate_crps(actuals, matrix)
            if crps_vals:
                crps_data.append({'timestamp': ts, 'crps_mean': np.mean(crps_vals)})

    crps_df = pd.DataFrame(crps_data)
    if len(crps_df) > 0:
        print(f"    CRPS: ${crps_df['crps_mean'].mean():.2f}")

    # Coverage
    intervals = predictions_df.groupby(['timestamp', 'day_ahead'])['predicted_price'].agg(
        p10=lambda x: x.quantile(0.1), p90=lambda x: x.quantile(0.9)
    ).reset_index()
    val = results_df.merge(intervals, on=['timestamp', 'day_ahead'])
    cov80 = ((val['actual'] >= val['p10']) & (val['actual'] <= val['p90'])).mean()
    print(f"    Coverage 80%: {cov80:.1%}")
    print(f"  ✓ Validation complete")

    return {
        'commodity': commodity,
        'model_version': model_version,
        'target_accuracy': target_accuracy,
        'target_mape': target_mape,
        'overall_mae': float(overall_mae),
        'overall_mape': float(overall_mape),
        'results_df': results_df,
        'per_horizon_metrics': per_horizon,
        'directional_df': dir_df,
        'crps_df': crps_df,
        'coverage_80': float(cov80)
    }


# =============================================================================
# COMMODITY PROCESSING
# =============================================================================

def process_single_commodity(commodity_name, market_df, config, accuracy_levels,
                            synthetic_start_date, spark):
    """
    Process a single commodity: generate predictions and validate.

    Args:
        commodity_name: Commodity name (e.g., "coffee")
        market_df: DataFrame with market data
        config: Analysis configuration
        accuracy_levels: List of accuracy levels to generate
        synthetic_start_date: Start date for synthetic predictions
        spark: Spark session

    Returns:
        Dictionary with results
    """
    print(f"\n{'='*80}")
    print(f"PROCESSING: {commodity_name.upper()}")
    print(f"{'='*80}")

    # Filter for this commodity
    prices_full = market_df[market_df['commodity'].str.lower() == commodity_name.lower()].copy()
    prices_full['date'] = pd.to_datetime(prices_full['date'])
    prices_full['price'] = prices_full['close']
    prices_full = prices_full[['date', 'price']].sort_values('date').reset_index(drop=True)

    # Filter to synthetic period
    prices = prices_full[prices_full['date'] >= synthetic_start_date].copy().reset_index(drop=True)
    print(f"✓ {len(prices)} days of data (from {synthetic_start_date})")

    all_predictions = []
    validation_data = []

    # Generate predictions for each accuracy level
    for accuracy in accuracy_levels:
        model_version = f"synthetic_acc{int(accuracy*100)}"
        print(f"\n  {model_version}: {accuracy:.0%} accurate")

        predictions_df = generate_calibrated_predictions(
            prices, model_version, accuracy,
            config['prediction_runs'],
            config['forecast_horizon'], 20
        )
        print(f"    ✓ Generated {len(predictions_df):,} rows")

        val_data = validate_predictions(
            predictions_df, prices, commodity_name, model_version,
            accuracy, config['forecast_horizon']
        )

        if val_data:
            validation_data.append(val_data)

        all_predictions.append(predictions_df)
        del predictions_df
        gc.collect()

    # Combine all accuracy levels
    combined = pd.concat(all_predictions, ignore_index=True)
    del all_predictions
    gc.collect()

    # Save to Delta table
    predictions_table = f"{OUTPUT_SCHEMA}.predictions_{commodity_name.lower()}"
    spark.createDataFrame(combined).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(predictions_table)
    print(f"\n✓ Saved to {predictions_table}")

    del combined
    gc.collect()

    return {
        'commodity': commodity_name,
        'table': predictions_table,
        'validation_data': validation_data
    }


# =============================================================================
# MAIN RUNNER
# =============================================================================

def run_synthetic_predictions(commodities=None, accuracy_levels=None,
                              synthetic_start_date='2022-01-01'):
    """
    Main runner: Generate synthetic predictions for all commodities.

    Args:
        commodities: List of commodity names (None = all)
        accuracy_levels: List of accuracy levels (None = default)
        synthetic_start_date: Start date for synthetic predictions

    Returns:
        Tuple of (status_code, summary_dict)
    """
    try:
        # Initialize Spark (assumes running in Databricks)
        from pyspark.sql import SparkSession
        spark = SparkSession.builder.getOrCreate()

        # Default configuration
        if commodities is None:
            commodities = list(COMMODITY_CONFIGS.keys())
        if accuracy_levels is None:
            accuracy_levels = [1.00, 0.90, 0.80, 0.70, 0.60]

        print(f"\n{'='*80}")
        print(f"SYNTHETIC PREDICTION GENERATION (v8)")
        print(f"{'='*80}")
        print(f"Configuration:")
        print(f"  Commodities: {', '.join(commodities)}")
        print(f"  Accuracy levels: {[f'{a:.0%}' for a in accuracy_levels]}")
        print(f"  Start date: {synthetic_start_date}")
        print(f"  Runs per forecast: {ANALYSIS_CONFIG['prediction_runs']}")
        print(f"  Forecast horizon: {ANALYSIS_CONFIG['forecast_horizon']} days")
        print(f"  Output schema: {OUTPUT_SCHEMA}")
        print(f"  Volume path: {VOLUME_PATH}")

        # Load market data
        print(f"\n{'='*80}")
        print(f"LOADING MARKET DATA")
        print(f"{'='*80}")
        print(f"Loading from {MARKET_TABLE}...")
        market_df = spark.table(MARKET_TABLE).toPandas()
        market_df['date'] = pd.to_datetime(market_df['date'])
        print(f"✓ Loaded {len(market_df):,} rows")
        print(f"  Date range: {market_df['date'].min()} to {market_df['date'].max()}")
        print(f"  Commodities: {', '.join(market_df['commodity'].unique())}")

        # Process each commodity
        all_results = []
        all_validation_data = {}

        for commodity_name in commodities:
            try:
                result = process_single_commodity(
                    commodity_name, market_df, ANALYSIS_CONFIG,
                    accuracy_levels, synthetic_start_date, spark
                )
                all_results.append({
                    'commodity': result['commodity'],
                    'table': result['table']
                })
                all_validation_data[commodity_name] = result['validation_data']
            except Exception as e:
                print(f"\n❌ Error processing {commodity_name}: {e}")
                import traceback
                traceback.print_exc()
                # Continue with other commodities

        # Save validation data
        validation_output_file = f'{VOLUME_PATH}/validation_results_v8.pkl'
        validation_output = {
            'generation_timestamp': datetime.now(),
            'config': {
                'synthetic_start_date': synthetic_start_date,
                'accuracy_levels': accuracy_levels,
                'commodities': commodities
            },
            'commodities': all_validation_data,
            'summary': all_results
        }

        with open(validation_output_file, 'wb') as f:
            pickle.dump(validation_output, f)

        file_size_mb = os.path.getsize(validation_output_file) / (1024*1024)

        print(f"\n{'='*80}")
        print(f"COMPLETE")
        print(f"{'='*80}")
        print(f"✓ Saved validation data to: {validation_output_file}")
        print(f"  Size: {file_size_mb:.1f} MB")
        print(f"\n✓ Generated synthetic predictions for {len(all_results)} commodities")
        print(f"✓ 100% accurate should show 0% MAPE")

        # Summary for orchestrator
        summary = {
            'status': 'SUCCESS',
            'commodities_processed': len(all_results),
            'tables_created': [r['table'] for r in all_results],
            'validation_file': validation_output_file,
            'validation_file_size_mb': round(file_size_mb, 2),
            'accuracy_levels': [f'{a:.0%}' for a in accuracy_levels],
            'synthetic_start_date': synthetic_start_date
        }

        return 0, summary

    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()

        summary = {
            'status': 'FAILED',
            'error': str(e),
            'traceback': traceback.format_exc()
        }

        return 1, summary


# =============================================================================
# COMMAND-LINE INTERFACE
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Generate synthetic predictions at multiple accuracy levels (v8)'
    )
    parser.add_argument(
        '--commodity',
        type=str,
        help='Single commodity to process (default: all)'
    )
    parser.add_argument(
        '--commodities',
        type=str,
        help='Comma-separated list of commodities (e.g., "coffee,sugar")'
    )
    parser.add_argument(
        '--accuracies',
        type=str,
        default='1.0,0.9,0.8,0.7,0.6',
        help='Comma-separated accuracy levels (default: 1.0,0.9,0.8,0.7,0.6)'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        default='2022-01-01',
        help='Synthetic prediction start date (default: 2022-01-01)'
    )

    args = parser.parse_args()

    # Parse commodities
    if args.commodity:
        commodities = [args.commodity]
    elif args.commodities:
        commodities = [c.strip() for c in args.commodities.split(',')]
    else:
        commodities = None  # All commodities

    # Parse accuracy levels
    accuracy_levels = [float(a.strip()) for a in args.accuracies.split(',')]

    # Run
    status_code, summary = run_synthetic_predictions(
        commodities=commodities,
        accuracy_levels=accuracy_levels,
        synthetic_start_date=args.start_date
    )

    # Output JSON summary for orchestrator
    print(f"\n{'='*80}")
    print("SUMMARY (JSON):")
    print(json.dumps(summary, indent=2))

    sys.exit(status_code)
