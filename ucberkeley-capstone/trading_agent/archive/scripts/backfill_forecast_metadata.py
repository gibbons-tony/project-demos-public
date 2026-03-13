"""Backfill forecast_metadata table with performance metrics.

This script calculates MAE/RMSE/MAPE for each (model, forecast_start_date) combination
from the distributions table and populates the forecast_metadata table.

Usage:
    python backfill_forecast_metadata.py

Populates:
    commodity.forecast.forecast_metadata table with 210 rows (42 dates × 5 models)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'forecast_agent'))

from forecast_client import ForecastClient
from ground_truth.storage.databricks_writer import DatabricksForecastWriter
import pandas as pd
import numpy as np
from datetime import datetime


def calculate_window_metrics(forecasts_df, actuals_df, forecast_start_date, model_version):
    """Calculate MAE/RMSE/MAPE for a single forecast window.

    Args:
        forecasts_df: DataFrame with columns [path_id, day_1...day_14]
        actuals_df: DataFrame with columns [forecast_start_date, day_1...day_14]
        forecast_start_date: Date for this forecast window
        model_version: Model identifier

    Returns:
        dict with mae_1d, mae_7d, mae_14d, rmse_1d, rmse_7d, rmse_14d, mape_1d, mape_7d, mape_14d
    """
    # Get mean forecast across all paths
    forecast_mean = forecasts_df[['day_1', 'day_7', 'day_14']].mean()

    # Get actual values for this forecast date
    actual_row = actuals_df[actuals_df['forecast_start_date'] == forecast_start_date]

    if len(actual_row) == 0:
        # No actuals available for this date
        return {
            'mae_1d': None, 'mae_7d': None, 'mae_14d': None,
            'rmse_1d': None, 'rmse_7d': None, 'rmse_14d': None,
            'mape_1d': None, 'mape_7d': None, 'mape_14d': None,
            'actuals_available': 0
        }

    actual = actual_row.iloc[0]

    # Calculate metrics for each horizon
    metrics = {}
    actuals_count = 0

    for day_col, horizon in [('day_1', '1d'), ('day_7', '7d'), ('day_14', '14d')]:
        if pd.notna(actual[day_col]):
            actuals_count += 1
            error = forecast_mean[day_col] - actual[day_col]
            abs_error = abs(error)
            pct_error = (abs_error / actual[day_col]) * 100

            metrics[f'mae_{horizon}'] = abs_error
            metrics[f'rmse_{horizon}'] = error ** 2  # Will sqrt later
            metrics[f'mape_{horizon}'] = pct_error
        else:
            metrics[f'mae_{horizon}'] = None
            metrics[f'rmse_{horizon}'] = None
            metrics[f'mape_{horizon}'] = None

    # Square root RMSE values
    for horizon in ['1d', '7d', '14d']:
        if metrics[f'rmse_{horizon}'] is not None:
            metrics[f'rmse_{horizon}'] = np.sqrt(metrics[f'rmse_{horizon}'])

    metrics['actuals_available'] = actuals_count

    return metrics


def main():
    """Backfill forecast_metadata table with performance metrics."""

    print("="*80)
    print("FORECAST METADATA BACKFILL")
    print("="*80)

    # Initialize client
    print("\n[1/5] Connecting to Databricks...")
    try:
        client = ForecastClient()
        print(f"  ✓ Connected to {client.catalog}.{client.schema}")
    except Exception as e:
        print(f"  ✗ Connection failed: {e}")
        print("\nPlease ensure DATABRICKS_HOST, DATABRICKS_HTTP_PATH, and DATABRICKS_TOKEN are set.")
        return

    # Get all models
    models = [
        'sarimax_auto_weather_v1',
        'prophet_v1',
        'xgboost_weather_v1',
        'arima_111_v1',
        'random_walk_v1'
    ]

    # Get all actuals
    print("\n[2/5] Loading all actuals...")
    actuals_query = f"""
        SELECT
            forecast_start_date,
            data_cutoff_date,
            generation_timestamp,
            day_1, day_2, day_3, day_4, day_5, day_6, day_7,
            day_8, day_9, day_10, day_11, day_12, day_13, day_14
        FROM {client.catalog}.{client.schema}.distributions
        WHERE path_id = 0
          AND is_actuals = TRUE
          AND commodity = 'Coffee'
        ORDER BY forecast_start_date
    """

    conn = client._get_connection()
    actuals_df = pd.read_sql(actuals_query, conn)
    print(f"  ✓ Loaded {len(actuals_df)} actual observations")

    # Iterate over each model and forecast date
    print("\n[3/5] Calculating metrics for each (model, date) combination...")
    metadata_rows = []

    for model in models:
        # Get all forecast windows for this model
        query = f"""
            SELECT DISTINCT
                forecast_start_date,
                data_cutoff_date,
                generation_timestamp
            FROM {client.catalog}.{client.schema}.distributions
            WHERE model_version = '{model}'
              AND commodity = 'Coffee'
              AND is_actuals = FALSE
              AND has_data_leakage = FALSE
            ORDER BY forecast_start_date
        """

        windows_df = pd.read_sql(query, conn)
        print(f"\n  {model}: {len(windows_df)} forecast windows")

        for _, window in windows_df.iterrows():
            forecast_start_date = window['forecast_start_date']

            # Get forecast distributions for this window
            forecast_query = f"""
                SELECT
                    day_1, day_7, day_14
                FROM {client.catalog}.{client.schema}.distributions
                WHERE model_version = '{model}'
                  AND commodity = 'Coffee'
                  AND forecast_start_date = '{forecast_start_date}'
                  AND is_actuals = FALSE
                  AND has_data_leakage = FALSE
            """

            forecasts_df = pd.read_sql(forecast_query, conn)

            # Calculate metrics
            metrics = calculate_window_metrics(
                forecasts_df, actuals_df, forecast_start_date, model
            )

            # Build metadata row
            forecast_id = f"{model}_Coffee_{forecast_start_date}"

            metadata_row = {
                'forecast_id': forecast_id,
                'forecast_start_date': forecast_start_date,
                'data_cutoff_date': window['data_cutoff_date'],
                'generation_timestamp': window['generation_timestamp'],
                'model_version': model,
                'commodity': 'Coffee',

                # Performance metrics
                'mae_1d': metrics['mae_1d'],
                'mae_7d': metrics['mae_7d'],
                'mae_14d': metrics['mae_14d'],
                'rmse_1d': metrics['rmse_1d'],
                'rmse_7d': metrics['rmse_7d'],
                'rmse_14d': metrics['rmse_14d'],
                'mape_1d': metrics['mape_1d'],
                'mape_7d': metrics['mape_7d'],
                'mape_14d': metrics['mape_14d'],

                # Timing metrics (not available from distributions table)
                'training_time_seconds': None,
                'inference_time_seconds': None,
                'total_time_seconds': None,

                # Infrastructure (local execution)
                'hardware_type': 'local',
                'num_cores': None,
                'memory_gb': None,
                'cluster_id': None,

                # Data quality
                'training_days': None,  # Not tracked in distributions
                'actuals_available': metrics['actuals_available'],
                'has_data_leakage': False,  # Already filtered
                'model_success': True,  # Only successful forecasts in distributions

                # Additional metadata
                'notes': f'Backfilled from distributions table on {datetime.now().date()}'
            }

            metadata_rows.append(metadata_row)

            # Progress indicator
            if len(metadata_rows) % 10 == 0:
                print(f"    Processed {len(metadata_rows)} forecast windows...")

    print(f"\n  ✓ Calculated metrics for {len(metadata_rows)} forecast windows")

    # Convert to DataFrame
    print("\n[4/5] Creating metadata DataFrame...")
    metadata_df = pd.DataFrame(metadata_rows)

    # Data type conversions
    metadata_df['forecast_start_date'] = pd.to_datetime(metadata_df['forecast_start_date'])
    metadata_df['data_cutoff_date'] = pd.to_datetime(metadata_df['data_cutoff_date'])
    metadata_df['generation_timestamp'] = pd.to_datetime(metadata_df['generation_timestamp'])

    print(f"  ✓ Created DataFrame with {len(metadata_df)} rows")
    print(f"\n  Sample metrics:")
    print(f"    Models: {metadata_df['model_version'].nunique()}")
    print(f"    Forecast dates: {metadata_df['forecast_start_date'].nunique()}")
    print(f"    Avg MAE (7-day): ${metadata_df['mae_7d'].mean():.2f}")

    # Upload to Databricks
    print("\n[5/5] Uploading to Databricks...")
    writer = DatabricksForecastWriter()

    # Upload using databricks-sql connector
    with writer._get_connection() as conn:
        cursor = conn.cursor()

        # Clear existing metadata (if any)
        print("  Clearing existing forecast_metadata table...")
        cursor.execute(f"DELETE FROM {writer.catalog}.{writer.schema}.forecast_metadata WHERE commodity = 'Coffee'")

        # Insert rows in batches
        print(f"  Inserting {len(metadata_df)} rows...")

        insert_query = f"""
            INSERT INTO {writer.catalog}.{writer.schema}.forecast_metadata
            (forecast_id, forecast_start_date, data_cutoff_date, generation_timestamp,
             model_version, commodity,
             mae_1d, mae_7d, mae_14d, rmse_1d, rmse_7d, rmse_14d,
             mape_1d, mape_7d, mape_14d,
             training_time_seconds, inference_time_seconds, total_time_seconds,
             hardware_type, num_cores, memory_gb, cluster_id,
             training_days, actuals_available, has_data_leakage, model_success,
             notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        # Prepare rows for insertion
        rows = []
        for _, row in metadata_df.iterrows():
            rows.append((
                row['forecast_id'],
                row['forecast_start_date'].date() if pd.notna(row['forecast_start_date']) else None,
                row['data_cutoff_date'].date() if pd.notna(row['data_cutoff_date']) else None,
                row['generation_timestamp'] if pd.notna(row['generation_timestamp']) else None,
                row['model_version'],
                row['commodity'],
                float(row['mae_1d']) if pd.notna(row['mae_1d']) else None,
                float(row['mae_7d']) if pd.notna(row['mae_7d']) else None,
                float(row['mae_14d']) if pd.notna(row['mae_14d']) else None,
                float(row['rmse_1d']) if pd.notna(row['rmse_1d']) else None,
                float(row['rmse_7d']) if pd.notna(row['rmse_7d']) else None,
                float(row['rmse_14d']) if pd.notna(row['rmse_14d']) else None,
                float(row['mape_1d']) if pd.notna(row['mape_1d']) else None,
                float(row['mape_7d']) if pd.notna(row['mape_7d']) else None,
                float(row['mape_14d']) if pd.notna(row['mape_14d']) else None,
                row['training_time_seconds'],
                row['inference_time_seconds'],
                row['total_time_seconds'],
                row['hardware_type'],
                row['num_cores'],
                row['memory_gb'],
                row['cluster_id'],
                row['training_days'],
                int(row['actuals_available']) if pd.notna(row['actuals_available']) else 0,
                bool(row['has_data_leakage']),
                bool(row['model_success']),
                row['notes']
            ))

        # Execute batch insert
        cursor.executemany(insert_query, rows)
        cursor.close()

    print(f"  ✓ Uploaded {len(metadata_df)} rows to forecast_metadata")

    # Verify
    print("\n" + "="*80)
    print("VERIFICATION")
    print("="*80)

    verify_query = f"""
        SELECT
            model_version,
            COUNT(*) as n_forecasts,
            AVG(mae_7d) as avg_mae_7d,
            AVG(rmse_7d) as avg_rmse_7d,
            AVG(mape_7d) as avg_mape_7d
        FROM {client.catalog}.{client.schema}.forecast_metadata
        WHERE commodity = 'Coffee'
        GROUP BY model_version
        ORDER BY avg_mae_7d
    """

    summary_df = pd.read_sql(verify_query, conn)
    print("\nSummary by model (7-day ahead):")
    print(summary_df.to_string(index=False))

    print("\n" + "="*80)
    print("✅ BACKFILL COMPLETE")
    print("="*80)
    print(f"\nPopulated {len(metadata_df)} rows in commodity.forecast.forecast_metadata")
    print(f"Models: {', '.join(models)}")
    print(f"Forecast windows: {metadata_df['forecast_start_date'].nunique()}")

    # Close connection
    client.close()


if __name__ == "__main__":
    main()
