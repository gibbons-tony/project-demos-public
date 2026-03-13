"""
Stage 2: Generate forecasts and Monte Carlo paths from trained models.

This script:
1. Loads latest trained model for a commodity
2. Generates point forecasts
3. Generates 2,000 Monte Carlo paths using block bootstrap on CV residuals
4. Writes to commodity.forecast.point_forecasts
5. Writes to commodity.forecast.distributions

Usage:
    # Generate forecasts for Coffee using latest model
    python inference.py --commodity Coffee --model linear_weather_min_max

    # Generate forecasts for specific date
    python inference.py --commodity Coffee --model ridge_top_regions \
        --forecast-date 2024-01-15

    # Custom Monte Carlo settings
    python inference.py --commodity Coffee --model naive_baseline \
        --n-paths 5000 --block-size 7

Example (Databricks notebook):
    %run ./inference.py $commodity="Coffee" $model="linear_weather_min_max"
"""
import argparse
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import json

from pyspark.sql import SparkSession, DataFrame
from pyspark.ml import PipelineModel
import pandas as pd
import numpy as np

from ml_lib.cross_validation import GoldDataLoader
from ml_lib.monte_carlo import BlockBootstrapPathGenerator


# =============================================================================
# CONFIGURATION
# =============================================================================

# Model storage paths
MODEL_BASE_PATH = "dbfs:/commodity/models"
RESIDUAL_BASE_PATH = "dbfs:/commodity/residuals"

# Metadata and output tables
METADATA_TABLE = "commodity.forecast.model_metadata"
POINT_FORECASTS_TABLE = "commodity.forecast.point_forecasts"
DISTRIBUTIONS_TABLE = "commodity.forecast.distributions"

# Monte Carlo defaults
DEFAULT_N_PATHS = 2000
DEFAULT_BLOCK_SIZE = 3


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_latest_model_metadata(
    spark: SparkSession,
    commodity: str,
    model_name: str
) -> Dict[str, Any]:
    """
    Get metadata for latest trained model.

    Args:
        spark: SparkSession
        commodity: Commodity name
        model_name: Model identifier

    Returns:
        Dictionary with model metadata

    Raises:
        ValueError: If no trained model found
    """
    query = f"""
        SELECT *
        FROM {METADATA_TABLE}
        WHERE commodity = '{commodity}'
          AND model_name = '{model_name}'
        ORDER BY training_date DESC
        LIMIT 1
    """

    result = spark.sql(query).collect()

    if not result:
        raise ValueError(
            f"No trained model found for commodity='{commodity}', "
            f"model='{model_name}'. Run train.py first."
        )

    row = result[0]

    return {
        'commodity': row['commodity'],
        'model_name': row['model_name'],
        'training_date': str(row['training_date']),
        'model_path': row['model_path'],
        'residual_path': row['residual_path'],
        'cv_mean_directional_accuracy': row['cv_mean_directional_accuracy'],
        'cv_mean_mae': row['cv_mean_mae'],
        'cv_mean_rmse': row['cv_mean_rmse'],
        'horizon': row['horizon'],
        'features': row['features']
    }


def load_trained_model(spark: SparkSession, model_path: str) -> PipelineModel:
    """
    Load fitted pipeline from DBFS.

    Args:
        spark: SparkSession
        model_path: DBFS path to saved model

    Returns:
        Fitted PipelineModel
    """
    return PipelineModel.load(model_path)


def load_cv_residuals(spark: SparkSession, residual_path: str) -> pd.DataFrame:
    """
    Load CV residuals from Parquet.

    Args:
        spark: SparkSession
        residual_path: DBFS path to residuals

    Returns:
        Pandas DataFrame with residual_day_1...residual_day_14 columns
    """
    spark_df = spark.read.parquet(residual_path)
    return spark_df.toPandas()


def generate_point_forecast(
    model: PipelineModel,
    data: DataFrame,
    forecast_date: str,
    horizon: int
) -> Dict[str, float]:
    """
    Generate point forecast for a specific date.

    Args:
        model: Fitted PipelineModel
        data: Data to forecast from (should include forecast_date)
        forecast_date: Date to generate forecast from (YYYY-MM-DD)
        horizon: Forecast horizon (number of days)

    Returns:
        Dictionary with day_1, day_2, ..., day_14 keys
    """
    # Filter to forecast date
    forecast_row = data.filter(f"date = '{forecast_date}'")

    if forecast_row.count() == 0:
        raise ValueError(f"No data found for forecast_date={forecast_date}")

    # Generate predictions
    predictions = model.transform(forecast_row)

    # Extract forecast values
    forecast_dict = {}
    for day in range(1, horizon + 1):
        col_name = f'forecast_day_{day}'
        value = predictions.select(col_name).collect()[0][0]
        forecast_dict[f'day_{day}'] = float(value)

    return forecast_dict


def generate_monte_carlo_paths(
    point_forecast: Dict[str, float],
    residuals: pd.DataFrame,
    n_paths: int,
    block_size: int,
    seed: Optional[int] = None
) -> np.ndarray:
    """
    Generate Monte Carlo paths using block bootstrap.

    Args:
        point_forecast: Dict with day_1, day_2, ..., day_14
        residuals: CV residuals DataFrame
        n_paths: Number of paths to generate
        block_size: Block size for bootstrap
        seed: Random seed for reproducibility

    Returns:
        Array of shape (n_paths, horizon)
    """
    # Convert point forecast to array
    horizon = len(point_forecast)
    point_forecast_array = np.array([
        point_forecast[f'day_{i}'] for i in range(1, horizon + 1)
    ])

    # Initialize path generator
    path_gen = BlockBootstrapPathGenerator(
        residuals=residuals,
        n_paths=n_paths,
        block_size=block_size,
        seed=seed
    )

    # Generate paths
    paths = path_gen.generate_paths(point_forecast_array)

    return paths


def write_point_forecast(
    spark: SparkSession,
    commodity: str,
    model_name: str,
    forecast_date: str,
    forecast_horizon_date: str,  # date + horizon days
    point_forecast: Dict[str, float],
    metadata: Dict[str, Any]
) -> None:
    """
    Write point forecast to Delta table.

    Schema:
        - commodity (string)
        - model_name (string)
        - forecast_date (date): Date forecast was generated
        - forecast_horizon_date (date): Date of last forecast day (forecast_date + 14 days)
        - day_1, day_2, ..., day_14 (double): Point forecasts
        - cv_directional_accuracy (double): From training
        - created_at (timestamp)
    """
    forecast_row = {
        'commodity': commodity,
        'model_name': model_name,
        'forecast_date': forecast_date,
        'forecast_horizon_date': forecast_horizon_date,
        **point_forecast,  # day_1, day_2, ..., day_14
        'cv_directional_accuracy': metadata['cv_mean_directional_accuracy'],
        'created_at': datetime.now().isoformat()
    }

    df = spark.createDataFrame([forecast_row])
    df.write.mode("append").format("delta").saveAsTable(POINT_FORECASTS_TABLE)


def write_monte_carlo_paths(
    spark: SparkSession,
    commodity: str,
    model_name: str,
    forecast_date: str,
    paths: np.ndarray
) -> None:
    """
    Write Monte Carlo paths to Delta table.

    Schema:
        - commodity (string)
        - model_name (string)
        - forecast_date (date)
        - path_id (int): 0 to n_paths-1
        - day_1, day_2, ..., day_14 (double)
        - created_at (timestamp)
    """
    horizon = paths.shape[1]
    n_paths = paths.shape[0]

    # Convert to list of dicts
    rows = []
    for path_id in range(n_paths):
        row = {
            'commodity': commodity,
            'model_name': model_name,
            'forecast_date': forecast_date,
            'path_id': path_id,
            'created_at': datetime.now().isoformat()
        }

        # Add day columns
        for day in range(1, horizon + 1):
            row[f'day_{day}'] = float(paths[path_id, day - 1])

        rows.append(row)

    # Write to Delta
    df = spark.createDataFrame(rows)
    df.write.mode("append").format("delta").partitionBy("commodity", "model_name").saveAsTable(DISTRIBUTIONS_TABLE)


# =============================================================================
# MAIN INFERENCE FUNCTION
# =============================================================================

def generate_forecast(
    spark: SparkSession,
    commodity: str,
    model_name: str,
    forecast_date: Optional[str] = None,
    n_paths: int = DEFAULT_N_PATHS,
    block_size: int = DEFAULT_BLOCK_SIZE,
    seed: Optional[int] = None
) -> Dict[str, Any]:
    """
    Generate forecast and Monte Carlo paths for a commodity.

    Args:
        spark: SparkSession
        commodity: Commodity name
        model_name: Model identifier
        forecast_date: Date to forecast from (default: latest available date)
        n_paths: Number of Monte Carlo paths
        block_size: Block size for bootstrap
        seed: Random seed

    Returns:
        Dictionary with forecast results
    """
    print("=" * 80)
    print(f"Generating Forecast: {model_name} for {commodity}")
    print("=" * 80)

    # 1. Get latest model metadata
    print(f"\n[1/7] Loading model metadata")
    metadata = get_latest_model_metadata(spark, commodity, model_name)
    print(f"  Model trained: {metadata['training_date']}")
    print(f"  CV Directional Accuracy: {metadata['cv_mean_directional_accuracy']:.4f}")
    print(f"  Horizon: {metadata['horizon']} days")

    # 2. Load trained model
    print(f"\n[2/7] Loading trained model")
    model = load_trained_model(spark, metadata['model_path'])
    print(f"  Model path: {metadata['model_path']}")

    # 3. Load data
    print(f"\n[3/7] Loading data for {commodity}")
    loader = GoldDataLoader(spark=spark)
    data = loader.load(commodity=commodity)

    # Determine forecast date
    if forecast_date is None:
        latest_date = data.agg({"date": "max"}).collect()[0][0]
        forecast_date = str(latest_date)
        print(f"  Using latest date: {forecast_date}")
    else:
        print(f"  Using specified date: {forecast_date}")

    # Calculate forecast horizon date
    forecast_date_obj = datetime.strptime(forecast_date, "%Y-%m-%d")
    horizon_date_obj = forecast_date_obj + timedelta(days=metadata['horizon'])
    forecast_horizon_date = horizon_date_obj.strftime("%Y-%m-%d")

    # 4. Generate point forecast
    print(f"\n[4/7] Generating point forecast")
    point_forecast = generate_point_forecast(
        model=model,
        data=data,
        forecast_date=forecast_date,
        horizon=metadata['horizon']
    )
    print(f"  Day 1: {point_forecast['day_1']:.2f}")
    print(f"  Day 7: {point_forecast['day_7']:.2f}")
    print(f"  Day 14: {point_forecast['day_14']:.2f}")

    # 5. Load CV residuals
    print(f"\n[5/7] Loading CV residuals")
    residuals = load_cv_residuals(spark, metadata['residual_path'])
    print(f"  Residuals shape: {residuals.shape}")
    print(f"  Residual path: {metadata['residual_path']}")

    # 6. Generate Monte Carlo paths
    print(f"\n[6/7] Generating {n_paths:,} Monte Carlo paths (block_size={block_size})")
    paths = generate_monte_carlo_paths(
        point_forecast=point_forecast,
        residuals=residuals,
        n_paths=n_paths,
        block_size=block_size,
        seed=seed
    )
    print(f"  Paths shape: {paths.shape}")

    # Calculate percentiles
    p10 = np.percentile(paths[:, -1], 10)  # Day 14 10th percentile
    p50 = np.percentile(paths[:, -1], 50)  # Day 14 median
    p90 = np.percentile(paths[:, -1], 90)  # Day 14 90th percentile
    print(f"  Day 14 uncertainty (10-90 percentile): [{p10:.2f}, {p90:.2f}]")
    print(f"  Day 14 median: {p50:.2f} (point: {point_forecast['day_14']:.2f})")

    # 7. Write to tables
    print(f"\n[7/7] Writing to Delta tables")

    # Write point forecast
    write_point_forecast(
        spark=spark,
        commodity=commodity,
        model_name=model_name,
        forecast_date=forecast_date,
        forecast_horizon_date=forecast_horizon_date,
        point_forecast=point_forecast,
        metadata=metadata
    )
    print(f"  ✅ Point forecast written to {POINT_FORECASTS_TABLE}")

    # Write Monte Carlo paths
    write_monte_carlo_paths(
        spark=spark,
        commodity=commodity,
        model_name=model_name,
        forecast_date=forecast_date,
        paths=paths
    )
    print(f"  ✅ {n_paths:,} paths written to {DISTRIBUTIONS_TABLE}")

    print("\n" + "=" * 80)
    print(f"✅ Forecast complete: {model_name} for {commodity}")
    print("=" * 80)

    return {
        'commodity': commodity,
        'model_name': model_name,
        'forecast_date': forecast_date,
        'forecast_horizon_date': forecast_horizon_date,
        'point_forecast': point_forecast,
        'n_paths': n_paths,
        'uncertainty': {
            'day_14_p10': p10,
            'day_14_p50': p50,
            'day_14_p90': p90
        }
    }


def generate_multiple_forecasts(
    spark: SparkSession,
    commodity: str,
    model_names: List[str],
    **inference_kwargs
) -> List[Dict[str, Any]]:
    """
    Generate forecasts for multiple models.

    Args:
        spark: SparkSession
        commodity: Commodity name
        model_names: List of model identifiers
        **inference_kwargs: Additional arguments passed to generate_forecast()

    Returns:
        List of forecast results
    """
    results = []

    for model_name in model_names:
        try:
            result = generate_forecast(
                spark=spark,
                commodity=commodity,
                model_name=model_name,
                **inference_kwargs
            )
            results.append(result)

        except Exception as e:
            print(f"\n❌ Error generating forecast for {model_name}: {e}")
            print(f"Skipping to next model...\n")
            continue

    # Summary
    print("\n" + "=" * 80)
    print("FORECAST SUMMARY")
    print("=" * 80)
    for result in results:
        day_14 = result['point_forecast']['day_14']
        p10 = result['uncertainty']['day_14_p10']
        p90 = result['uncertainty']['day_14_p90']
        print(f"{result['model_name']:<30} Day 14: {day_14:.2f} [{p10:.2f}, {p90:.2f}]")

    return results


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    """Main entry point for CLI usage."""
    parser = argparse.ArgumentParser(
        description="Generate forecasts and Monte Carlo paths from trained models"
    )

    parser.add_argument(
        '--commodity',
        type=str,
        required=True,
        help='Commodity name (e.g., Coffee, Wheat)'
    )

    parser.add_argument(
        '--models',
        type=str,
        nargs='+',
        required=True,
        help='Model names (space-separated)'
    )

    parser.add_argument(
        '--forecast-date',
        type=str,
        default=None,
        help='Date to forecast from (YYYY-MM-DD). Default: latest available'
    )

    parser.add_argument(
        '--n-paths',
        type=int,
        default=DEFAULT_N_PATHS,
        help=f'Number of Monte Carlo paths (default: {DEFAULT_N_PATHS})'
    )

    parser.add_argument(
        '--block-size',
        type=int,
        default=DEFAULT_BLOCK_SIZE,
        help=f'Block size for bootstrap (default: {DEFAULT_BLOCK_SIZE})'
    )

    parser.add_argument(
        '--seed',
        type=int,
        default=None,
        help='Random seed for reproducibility'
    )

    args = parser.parse_args()

    # Initialize Spark
    spark = SparkSession.builder \
        .appName(f"ForecastInference-{args.commodity}") \
        .getOrCreate()

    # Generate forecasts
    results = generate_multiple_forecasts(
        spark=spark,
        commodity=args.commodity,
        model_names=args.models,
        forecast_date=args.forecast_date,
        n_paths=args.n_paths,
        block_size=args.block_size,
        seed=args.seed
    )

    print(f"\n✅ All forecasts complete. {len(results)}/{len(args.models)} models succeeded.")


if __name__ == "__main__":
    main()
