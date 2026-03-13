"""
Stage 1: Train forecasting models using time-series cross-validation.

This script:
1. Loads data from commodity.gold.unified_data
2. Runs cross-validation for specified models
3. Saves fitted pipelines to DBFS
4. Tracks metrics in commodity.forecast.model_metadata
5. Saves CV residuals for Monte Carlo path generation

Usage:
    # Train all models for Coffee
    python train.py --commodity Coffee --models naive_baseline linear_weather_min_max

    # Train with custom CV settings
    python train.py --commodity Coffee --models ridge_top_regions \
        --n-folds 10 --window-type rolling

Example (Databricks notebook):
    %run ./train.py $commodity="Coffee" $models="naive_baseline,linear_weather_min_max"
"""
import argparse
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from pyspark.sql import SparkSession
import pandas as pd

from ml_lib.cross_validation import GoldDataLoader, TimeSeriesForecastCV
from ml_lib.pipelines import get_pipeline, list_models, PIPELINE_REGISTRY


# =============================================================================
# CONFIGURATION
# =============================================================================

# Model storage paths (DBFS)
MODEL_BASE_PATH = "dbfs:/commodity/models"
RESIDUAL_BASE_PATH = "dbfs:/commodity/residuals"

# Metadata table
METADATA_TABLE = "commodity.forecast.model_metadata"

# CV defaults
DEFAULT_N_FOLDS = 5
DEFAULT_WINDOW_TYPE = 'expanding'
DEFAULT_HORIZON = 14
DEFAULT_VALIDATION_MONTHS = 6
DEFAULT_MIN_TRAIN_MONTHS = 24


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def save_model_pipeline(
    fitted_pipeline,
    commodity: str,
    model_name: str,
    training_date: str,
    fold_idx: Optional[int] = None
) -> str:
    """
    Save fitted pipeline to DBFS.

    Args:
        fitted_pipeline: Fitted PySpark Pipeline object
        commodity: Commodity name
        model_name: Model identifier from registry
        training_date: Date when model was trained (YYYY-MM-DD)
        fold_idx: CV fold index (None for final model)

    Returns:
        Path where model was saved
    """
    # Build path
    if fold_idx is not None:
        # CV fold model
        path = f"{MODEL_BASE_PATH}/{commodity}/{model_name}/{training_date}/fold_{fold_idx}"
    else:
        # Final model (trained on all data)
        path = f"{MODEL_BASE_PATH}/{commodity}/{model_name}/{training_date}/final"

    # Save pipeline (PySpark native format)
    fitted_pipeline.save(path)

    return path


def save_cv_residuals(
    residuals_df: pd.DataFrame,
    commodity: str,
    model_name: str,
    training_date: str,
    spark: SparkSession
) -> str:
    """
    Save CV residuals as Parquet for Monte Carlo path generation.

    Args:
        residuals_df: Pandas DataFrame with residual_day_1...residual_day_14
        commodity: Commodity name
        model_name: Model identifier
        training_date: Training date
        spark: SparkSession

    Returns:
        Path where residuals were saved
    """
    path = f"{RESIDUAL_BASE_PATH}/{commodity}/{model_name}/{training_date}"

    # Convert to Spark DataFrame and write
    spark_df = spark.createDataFrame(residuals_df)
    spark_df.write.mode("overwrite").parquet(path)

    return path


def write_model_metadata(
    spark: SparkSession,
    commodity: str,
    model_name: str,
    training_date: str,
    cv_metrics: Dict[str, Any],
    model_path: str,
    residual_path: str,
    pipeline_metadata: Dict[str, Any],
    cv_config: Dict[str, Any]
) -> None:
    """
    Write model metadata to Delta table for tracking.

    Schema:
        - commodity (string)
        - model_name (string)
        - training_date (date)
        - cv_mean_directional_accuracy (double)
        - cv_mean_mae (double)
        - cv_mean_rmse (double)
        - cv_metrics_json (string): Full CV metrics as JSON
        - model_path (string): DBFS path to final model
        - residual_path (string): DBFS path to CV residuals
        - n_folds (int)
        - window_type (string)
        - horizon (int)
        - features (array<string>)
        - target_metric (string)
        - created_at (timestamp)
    """
    # Prepare metadata row
    metadata = {
        'commodity': commodity,
        'model_name': model_name,
        'training_date': training_date,
        'cv_mean_directional_accuracy': cv_metrics['mean_directional_accuracy'],
        'cv_mean_mae': cv_metrics['mean_mae'],
        'cv_mean_rmse': cv_metrics['mean_rmse'],
        'cv_metrics_json': json.dumps(cv_metrics),
        'model_path': model_path,
        'residual_path': residual_path,
        'n_folds': cv_config['n_folds'],
        'window_type': cv_config['window_type'],
        'horizon': cv_config['horizon'],
        'features': pipeline_metadata['features'],
        'target_metric': pipeline_metadata['target_metric'],
        'created_at': datetime.now().isoformat()
    }

    # Convert to Spark DataFrame
    df = spark.createDataFrame([metadata])

    # Write to Delta table (append mode)
    df.write.mode("append").format("delta").saveAsTable(METADATA_TABLE)


# =============================================================================
# MAIN TRAINING FUNCTION
# =============================================================================

def train_model(
    spark: SparkSession,
    commodity: str,
    model_name: str,
    n_folds: int = DEFAULT_N_FOLDS,
    window_type: str = DEFAULT_WINDOW_TYPE,
    horizon: int = DEFAULT_HORIZON,
    validation_months: int = DEFAULT_VALIDATION_MONTHS,
    min_train_months: int = DEFAULT_MIN_TRAIN_MONTHS,
    save_fold_models: bool = False
) -> Dict[str, Any]:
    """
    Train a single model with cross-validation.

    Args:
        spark: SparkSession
        commodity: Commodity name (e.g., 'Coffee')
        model_name: Model identifier from PIPELINE_REGISTRY
        n_folds: Number of CV folds
        window_type: 'expanding' or 'rolling'
        horizon: Forecast horizon in days
        validation_months: Months per validation fold
        min_train_months: Minimum training data required
        save_fold_models: If True, save fitted model for each fold (not just final)

    Returns:
        Dictionary with training results
    """
    print("=" * 80)
    print(f"Training: {model_name} for {commodity}")
    print("=" * 80)

    training_date = datetime.now().strftime("%Y-%m-%d")

    # 1. Get pipeline from registry
    print(f"\n[1/6] Loading pipeline: {model_name}")
    pipeline, pipeline_metadata = get_pipeline(model_name)
    print(f"  Features: {', '.join(pipeline_metadata['features'])}")
    print(f"  Target metric: {pipeline_metadata['target_metric']}")

    # 2. Load data
    print(f"\n[2/6] Loading data for {commodity}")
    loader = GoldDataLoader(spark=spark)
    df = loader.load(commodity=commodity)

    # Validate data
    validation_stats = loader.validate_data(df)
    print(f"  Rows: {validation_stats['row_count']:,}")
    print(f"  Date range: {validation_stats['min_date']} to {validation_stats['max_date']}")
    print(f"  Avg weather regions: {validation_stats['avg_weather_regions']:.1f}")
    print(f"  Avg GDELT themes: {validation_stats['avg_gdelt_themes']:.1f}")

    # 3. Run cross-validation
    print(f"\n[3/6] Running {n_folds}-fold {window_type} window CV")
    cv = TimeSeriesForecastCV(
        pipeline=pipeline,
        commodity=commodity,
        n_folds=n_folds,
        window_type=window_type,
        horizon=horizon,
        validation_months=validation_months,
        min_train_months=min_train_months
    )

    cv_results = cv.fit()

    # Print results
    print(f"\n  CV Results:")
    print(f"    Directional Accuracy: {cv_results['mean_directional_accuracy']:.4f}")
    print(f"    MAE: {cv_results['mean_mae']:.2f}")
    print(f"    RMSE: {cv_results['mean_rmse']:.2f}")

    # 4. Save fold models (optional)
    if save_fold_models:
        print(f"\n[4/6] Saving CV fold models")
        for fold_idx, fold_model in enumerate(cv_results['fold_models']):
            fold_path = save_model_pipeline(
                fitted_pipeline=fold_model,
                commodity=commodity,
                model_name=model_name,
                training_date=training_date,
                fold_idx=fold_idx
            )
            print(f"  Fold {fold_idx} saved: {fold_path}")
    else:
        print(f"\n[4/6] Skipping fold model saves (save_fold_models=False)")

    # 5. Train final model (on all data)
    print(f"\n[5/6] Training final model on all data")
    final_model = pipeline.fit(df)

    # Save final model
    final_model_path = save_model_pipeline(
        fitted_pipeline=final_model,
        commodity=commodity,
        model_name=model_name,
        training_date=training_date,
        fold_idx=None  # Final model
    )
    print(f"  Final model saved: {final_model_path}")

    # 6. Save CV residuals for Monte Carlo
    print(f"\n[6/6] Saving CV residuals for Monte Carlo path generation")
    residuals = cv.get_residuals()
    residual_path = save_cv_residuals(
        residuals_df=residuals,
        commodity=commodity,
        model_name=model_name,
        training_date=training_date,
        spark=spark
    )
    print(f"  Residuals saved: {residual_path}")
    print(f"  Shape: {residuals.shape} (for {cv_results['n_predictions']} forecasts)")

    # 7. Write metadata
    print(f"\nWriting metadata to {METADATA_TABLE}")
    cv_config = {
        'n_folds': n_folds,
        'window_type': window_type,
        'horizon': horizon,
        'validation_months': validation_months,
        'min_train_months': min_train_months
    }

    write_model_metadata(
        spark=spark,
        commodity=commodity,
        model_name=model_name,
        training_date=training_date,
        cv_metrics=cv_results,
        model_path=final_model_path,
        residual_path=residual_path,
        pipeline_metadata=pipeline_metadata,
        cv_config=cv_config
    )

    print("\n" + "=" * 80)
    print(f"✅ Training complete: {model_name}")
    print("=" * 80)

    return {
        'commodity': commodity,
        'model_name': model_name,
        'training_date': training_date,
        'cv_metrics': cv_results,
        'model_path': final_model_path,
        'residual_path': residual_path
    }


def train_multiple_models(
    spark: SparkSession,
    commodity: str,
    model_names: List[str],
    **cv_kwargs
) -> List[Dict[str, Any]]:
    """
    Train multiple models sequentially.

    Args:
        spark: SparkSession
        commodity: Commodity name
        model_names: List of model identifiers from registry
        **cv_kwargs: Additional arguments passed to train_model()

    Returns:
        List of training results
    """
    results = []

    for model_name in model_names:
        try:
            result = train_model(
                spark=spark,
                commodity=commodity,
                model_name=model_name,
                **cv_kwargs
            )
            results.append(result)

        except Exception as e:
            print(f"\n❌ Error training {model_name}: {e}")
            print(f"Skipping to next model...\n")
            continue

    # Summary
    print("\n" + "=" * 80)
    print("TRAINING SUMMARY")
    print("=" * 80)
    for result in results:
        da = result['cv_metrics']['mean_directional_accuracy']
        print(f"{result['model_name']:<30} DA: {da:.4f}")

    return results


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    """Main entry point for CLI usage."""
    parser = argparse.ArgumentParser(
        description="Train forecasting models with time-series cross-validation"
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
        default=['naive_baseline'],
        help='Model names from registry (space-separated)'
    )

    parser.add_argument(
        '--n-folds',
        type=int,
        default=DEFAULT_N_FOLDS,
        help=f'Number of CV folds (default: {DEFAULT_N_FOLDS})'
    )

    parser.add_argument(
        '--window-type',
        type=str,
        choices=['expanding', 'rolling'],
        default=DEFAULT_WINDOW_TYPE,
        help=f'CV window type (default: {DEFAULT_WINDOW_TYPE})'
    )

    parser.add_argument(
        '--horizon',
        type=int,
        default=DEFAULT_HORIZON,
        help=f'Forecast horizon in days (default: {DEFAULT_HORIZON})'
    )

    parser.add_argument(
        '--validation-months',
        type=int,
        default=DEFAULT_VALIDATION_MONTHS,
        help=f'Months per validation fold (default: {DEFAULT_VALIDATION_MONTHS})'
    )

    parser.add_argument(
        '--min-train-months',
        type=int,
        default=DEFAULT_MIN_TRAIN_MONTHS,
        help=f'Minimum training months (default: {DEFAULT_MIN_TRAIN_MONTHS})'
    )

    parser.add_argument(
        '--save-fold-models',
        action='store_true',
        help='Save fitted model for each CV fold (not just final)'
    )

    parser.add_argument(
        '--list-models',
        action='store_true',
        help='List available models and exit'
    )

    args = parser.parse_args()

    # List models if requested
    if args.list_models:
        list_models()
        return

    # Validate models exist
    invalid_models = [m for m in args.models if m not in PIPELINE_REGISTRY]
    if invalid_models:
        print(f"Error: Invalid models: {', '.join(invalid_models)}")
        print(f"\nAvailable models:")
        list_models()
        return

    # Initialize Spark
    spark = SparkSession.builder \
        .appName(f"ForecastTraining-{args.commodity}") \
        .getOrCreate()

    # Train models
    results = train_multiple_models(
        spark=spark,
        commodity=args.commodity,
        model_names=args.models,
        n_folds=args.n_folds,
        window_type=args.window_type,
        horizon=args.horizon,
        validation_months=args.validation_months,
        min_train_months=args.min_train_months,
        save_fold_models=args.save_fold_models
    )

    print(f"\n✅ All training complete. {len(results)}/{len(args.models)} models succeeded.")


if __name__ == "__main__":
    main()
