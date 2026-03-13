"""Backtest historical forecasts for all models.

This script evaluates forecast performance across 40 historical windows
by comparing forecasts against actuals from commodity.forecast.distributions.

Usage:
    python backtest_forecasts.py

Outputs:
    - Console: Summary table of metrics
    - backtest_results.md: Detailed markdown report
"""

import sys
import os

# Add parent directory to path to import forecast_client
sys.path.insert(0, os.path.dirname(__file__))

from forecast_client import ForecastClient
import pandas as pd
import numpy as np
from datetime import datetime


def calculate_metrics(forecasts_df, actuals_df, horizon_days=[1, 7, 14]):
    """Calculate MAE, RMSE, MAPE, and coverage for given horizons.

    Args:
        forecasts_df: DataFrame with columns [forecast_start_date, model_version, day_1...day_14]
        actuals_df: DataFrame with columns [forecast_start_date, day_1...day_14]
        horizon_days: List of days to calculate metrics for

    Returns:
        DataFrame with metrics by model and horizon
    """
    results = []

    for model in forecasts_df['model_version'].unique():
        model_forecasts = forecasts_df[forecasts_df['model_version'] == model]

        # Merge with actuals
        merged = model_forecasts.merge(actuals_df, on='forecast_start_date', suffixes=('_forecast', '_actual'))

        for day in horizon_days:
            forecast_col = f'day_{day}_forecast'
            actual_col = f'day_{day}_actual'

            if forecast_col in merged.columns and actual_col in merged.columns:
                # Calculate errors
                errors = merged[forecast_col] - merged[actual_col]
                abs_errors = errors.abs()
                pct_errors = (abs_errors / merged[actual_col] * 100)

                # MAE, RMSE, MAPE
                mae = abs_errors.mean()
                rmse = np.sqrt((errors ** 2).mean())
                mape = pct_errors.mean()

                # Bias (mean error - positive = overforecast, negative = underforecast)
                bias = errors.mean()

                results.append({
                    'model_version': model,
                    'horizon_days': day,
                    'n_forecasts': len(merged),
                    'mae': mae,
                    'rmse': rmse,
                    'mape': mape,
                    'bias': bias
                })

    return pd.DataFrame(results)


def calculate_coverage(client, models, commodity='Coffee', percentile=95):
    """Calculate prediction interval coverage.

    For well-calibrated models, 95% of actuals should fall within the 95% prediction interval.

    Args:
        client: ForecastClient instance
        models: List of model versions
        commodity: 'Coffee' or 'Sugar'
        percentile: Prediction interval percentile (default 95)

    Returns:
        DataFrame with coverage by model
    """
    results = []

    # Get connection once and reuse
    conn = client._get_connection()

    for model in models:
        # Query prediction intervals for all forecast dates
        query = f"""
            WITH forecasts AS (
              SELECT
                forecast_start_date,
                PERCENTILE(day_7, {(100-percentile)/200}) as lower_bound,
                PERCENTILE(day_7, {1 - (100-percentile)/200}) as upper_bound
              FROM {client.catalog}.{client.schema}.distributions
              WHERE model_version = '{model}'
                AND commodity = '{commodity}'
                AND is_actuals = FALSE
                AND has_data_leakage = FALSE
              GROUP BY forecast_start_date
            ),
            actuals AS (
              SELECT
                forecast_start_date,
                day_7 as actual
              FROM {client.catalog}.{client.schema}.distributions
              WHERE path_id = 0
                AND is_actuals = TRUE
                AND commodity = '{commodity}'
            )
            SELECT
              COUNT(*) as total,
              SUM(CASE
                WHEN a.actual BETWEEN f.lower_bound AND f.upper_bound THEN 1
                ELSE 0
              END) as in_interval
            FROM forecasts f
            JOIN actuals a ON f.forecast_start_date = a.forecast_start_date
        """

        df = pd.read_sql(query, conn)

        if len(df) > 0 and df['total'].iloc[0] > 0:
            coverage = df['in_interval'].iloc[0] / df['total'].iloc[0] * 100
            results.append({
                'model_version': model,
                'total_forecasts': df['total'].iloc[0],
                f'coverage_{percentile}': coverage
            })

    return pd.DataFrame(results)


def generate_markdown_report(metrics_df, coverage_df, output_path='backtest_results.md'):
    """Generate markdown report with backtest results.

    Args:
        metrics_df: DataFrame with MAE/RMSE/MAPE metrics
        coverage_df: DataFrame with prediction interval coverage
        output_path: Path to save markdown report
    """
    report = []

    report.append("# Forecast Backtest Results\n")
    report.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    report.append(f"**Evaluation Period**: 42 historical forecast windows (July 2018 - Oct 2024)\n")
    report.append("\n---\n\n")

    # Overall best model
    best_model_7d = metrics_df[metrics_df['horizon_days'] == 7].sort_values('mae').iloc[0]
    report.append("## Summary\n\n")
    report.append(f"**Best Model (7-day ahead)**: `{best_model_7d['model_version']}`\n")
    report.append(f"- MAE: ${best_model_7d['mae']:.2f}\n")
    report.append(f"- RMSE: ${best_model_7d['rmse']:.2f}\n")
    report.append(f"- MAPE: {best_model_7d['mape']:.2f}%\n")
    report.append(f"- Bias: ${best_model_7d['bias']:.2f}\n")
    report.append("\n---\n\n")

    # Model comparison table
    report.append("## Model Comparison (7-Day Ahead)\n\n")
    report.append("| Model | MAE | RMSE | MAPE | Bias | Coverage (95%) |\n")
    report.append("|-------|-----|------|------|------|----------------|\n")

    metrics_7d = metrics_df[metrics_df['horizon_days'] == 7].sort_values('mae')
    for _, row in metrics_7d.iterrows():
        coverage_row = coverage_df[coverage_df['model_version'] == row['model_version']]
        coverage = f"{coverage_row['coverage_95'].iloc[0]:.1f}%" if len(coverage_row) > 0 else "N/A"

        report.append(f"| {row['model_version']} | "
                     f"${row['mae']:.2f} | "
                     f"${row['rmse']:.2f} | "
                     f"{row['mape']:.2f}% | "
                     f"${row['bias']:.2f} | "
                     f"{coverage} |\n")

    report.append("\n---\n\n")

    # Multi-horizon performance
    report.append("## Multi-Horizon Performance\n\n")
    report.append("### Mean Absolute Error (MAE) by Horizon\n\n")
    report.append("| Model | 1-Day | 7-Day | 14-Day |\n")
    report.append("|-------|-------|-------|--------|\n")

    for model in metrics_df['model_version'].unique():
        model_data = metrics_df[metrics_df['model_version'] == model].set_index('horizon_days')
        mae_1d = f"${model_data.loc[1, 'mae']:.2f}" if 1 in model_data.index else "N/A"
        mae_7d = f"${model_data.loc[7, 'mae']:.2f}" if 7 in model_data.index else "N/A"
        mae_14d = f"${model_data.loc[14, 'mae']:.2f}" if 14 in model_data.index else "N/A"

        report.append(f"| {model} | {mae_1d} | {mae_7d} | {mae_14d} |\n")

    report.append("\n---\n\n")

    # Prediction interval calibration
    report.append("## Prediction Interval Calibration\n\n")
    report.append("Well-calibrated models should have ~95% coverage for 95% prediction intervals.\n\n")
    report.append("| Model | Coverage | Status |\n")
    report.append("|-------|----------|--------|\n")

    for _, row in coverage_df.iterrows():
        coverage = row['coverage_95']
        status = ""
        if 92 <= coverage <= 98:
            status = "✅ Well-calibrated"
        elif 88 <= coverage < 92 or 98 < coverage <= 102:
            status = "⚠️ Slightly miscalibrated"
        else:
            status = "❌ Poorly calibrated"

        report.append(f"| {row['model_version']} | {coverage:.1f}% | {status} |\n")

    report.append("\n---\n\n")

    # Interpretation
    report.append("## Interpretation\n\n")
    report.append("### Metrics Explained\n\n")
    report.append("- **MAE (Mean Absolute Error)**: Average absolute difference between forecast and actual. Lower is better.\n")
    report.append("- **RMSE (Root Mean Squared Error)**: Square root of average squared errors. Penalizes large errors more than MAE.\n")
    report.append("- **MAPE (Mean Absolute Percentage Error)**: MAE as percentage of actual value. Lower is better.\n")
    report.append("- **Bias**: Average error (forecast - actual). Positive = overforecasting, Negative = underforecasting.\n")
    report.append("- **Coverage**: % of actuals that fall within 95% prediction interval. Should be ~95% for calibrated models.\n\n")

    report.append("### Recommendations\n\n")
    report.append(f"1. **Production Model**: Use `{best_model_7d['model_version']}` for best accuracy\n")
    report.append("2. **Ensemble Strategy**: Consider averaging top 3 models for robustness\n")
    report.append("3. **Risk Management**: Use 95% prediction intervals for position sizing (VaR/CVaR)\n")
    report.append("4. **Model Monitoring**: Track if live forecast errors exceed backtest MAE by >20%\n")

    # Write to file
    with open(output_path, 'w') as f:
        f.writelines(report)

    print(f"\n✅ Markdown report saved to: {output_path}")


def main():
    """Run backtest evaluation."""

    print("="*80)
    print("FORECAST BACKTEST EVALUATION")
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

    # Fetch historical forecasts and actuals
    print("\n[2/5] Loading historical forecasts...")
    forecasts_list = []
    conn = client._get_connection()  # Get connection once and reuse
    for model in models:
        query = f"""
            SELECT
                forecast_start_date,
                '{model}' as model_version,
                AVG(day_1) as day_1, AVG(day_7) as day_7, AVG(day_14) as day_14
            FROM {client.catalog}.{client.schema}.distributions
            WHERE model_version = '{model}'
              AND commodity = 'Coffee'
              AND is_actuals = FALSE
              AND has_data_leakage = FALSE
            GROUP BY forecast_start_date
            ORDER BY forecast_start_date
        """
        try:
            df = pd.read_sql(query, conn)
            forecasts_list.append(df)
            print(f"  ✓ {model}: {len(df)} forecasts")
        except Exception as e:
            print(f"  ✗ {model}: {e}")

    forecasts_df = pd.concat(forecasts_list, ignore_index=True)

    # Fetch actuals
    print("\n[3/5] Loading actuals...")
    actuals_query = f"""
        SELECT
            forecast_start_date,
            day_1, day_7, day_14
        FROM {client.catalog}.{client.schema}.distributions
        WHERE path_id = 0
          AND is_actuals = TRUE
          AND commodity = 'Coffee'
        ORDER BY forecast_start_date
    """
    actuals_df = pd.read_sql(actuals_query, conn)
    print(f"  ✓ Loaded {len(actuals_df)} actual observations")

    # Calculate metrics
    print("\n[4/5] Calculating performance metrics...")
    metrics_df = calculate_metrics(forecasts_df, actuals_df, horizon_days=[1, 7, 14])
    print(f"  ✓ Calculated MAE, RMSE, MAPE for {len(models)} models")

    # Calculate coverage
    print("\n[5/5] Calculating prediction interval coverage...")
    coverage_df = calculate_coverage(client, models, commodity='Coffee', percentile=95)
    print(f"  ✓ Calculated 95% coverage for {len(coverage_df)} models")

    # Display summary
    print("\n" + "="*80)
    print("RESULTS SUMMARY (7-Day Ahead)")
    print("="*80 + "\n")

    metrics_7d = metrics_df[metrics_df['horizon_days'] == 7].sort_values('mae')
    print(metrics_7d[['model_version', 'mae', 'rmse', 'mape', 'bias']].to_string(index=False))

    print("\n" + "="*80)
    print("PREDICTION INTERVAL CALIBRATION")
    print("="*80 + "\n")
    print(coverage_df.to_string(index=False))

    # Generate report
    print("\n" + "="*80)
    generate_markdown_report(metrics_df, coverage_df, output_path='backtest_results.md')
    print("="*80)

    # Close connection
    client.close()


if __name__ == "__main__":
    main()
