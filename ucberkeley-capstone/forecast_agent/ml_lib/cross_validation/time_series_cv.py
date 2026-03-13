"""
Time-series cross-validation for commodity price forecasting.

Implements expanding and rolling window CV with:
- Directional accuracy as primary metric
- Residual collection for Monte Carlo simulation
- Support for any PySpark ML Pipeline
"""
from pyspark.sql import DataFrame, SparkSession
from pyspark.ml import Pipeline, PipelineModel
from pyspark.sql.functions import col, lit, datediff, expr
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np


class TimeSeriesForecastCV:
    """
    Time-series cross-validation for forecasting models.

    Supports two window strategies:
    - Expanding: Training window grows over time (2018-2020, 2018-2021, ...)
    - Rolling: Training window slides with fixed size (2018-2020, 2019-2021, ...)

    Metrics:
    - Directional Accuracy from Day 0 (primary): Is day_i > day_0?
    - MAE, RMSE (secondary)

    Residual Collection:
    - Stores forecast errors for block bootstrap Monte Carlo

    Example:
        from ml_lib.cross_validation import TimeSeriesForecastCV
        from ml_lib.pipelines import get_pipeline

        # Get pipeline
        pipeline, metadata = get_pipeline('linear_weather')

        # Run CV
        cv = TimeSeriesForecastCV(
            pipeline=pipeline,
            commodity='Coffee',
            n_folds=5,
            window_type='expanding',
            horizon=14
        )
        results = cv.fit()

        # View metrics
        print(results['cv_metrics'])
        print(f"Mean Directional Accuracy: {results['mean_directional_accuracy']:.3f}")

        # Get residuals for Monte Carlo
        residuals = cv.get_residuals()
    """

    def __init__(
        self,
        pipeline: Pipeline,
        commodity: str,
        n_folds: int = 5,
        window_type: str = 'expanding',
        horizon: int = 14,
        validation_months: int = 6,
        min_train_months: int = 24,
        table_name: str = "commodity.gold.unified_data"
    ):
        """
        Initialize time-series CV.

        Args:
            pipeline: PySpark ML Pipeline to evaluate
            commodity: Commodity name ('Coffee' or 'Sugar')
            n_folds: Number of CV folds
            window_type: 'expanding' (growing) or 'rolling' (fixed size)
            horizon: Forecast horizon in days
            validation_months: Size of validation period per fold (months)
            min_train_months: Minimum training data size (months)
            table_name: Gold unified data table name
        """
        self.pipeline = pipeline
        self.commodity = commodity
        self.n_folds = n_folds
        self.window_type = window_type
        self.horizon = horizon
        self.validation_months = validation_months
        self.min_train_months = min_train_months
        self.table_name = table_name

        self.spark = SparkSession.builder.getOrCreate()

        # Storage for results
        self.fold_models: List[PipelineModel] = []
        self.fold_metrics: List[Dict[str, float]] = []
        self.residuals: List[pd.DataFrame] = []

    def _create_folds(self, df: DataFrame) -> List[Tuple[DataFrame, DataFrame]]:
        """
        Create time-series CV folds.

        Returns:
            List of (train_df, validation_df) tuples
        """
        # Get date range
        date_range = df.agg({"date": "min", "date": "max"}).collect()[0]
        min_date = date_range["min(date)"]
        max_date = date_range["max(date)"]

        folds = []

        # Calculate fold boundaries
        # Start validation at min_date + min_train_months
        val_start = min_date + timedelta(days=30 * self.min_train_months)

        for fold_idx in range(self.n_folds):
            # Validation period for this fold
            val_start_date = val_start + timedelta(days=30 * self.validation_months * fold_idx)
            val_end_date = val_start_date + timedelta(days=30 * self.validation_months)

            if val_end_date > max_date:
                break  # Not enough data for this fold

            # Training period
            if self.window_type == 'expanding':
                # Expanding: train from beginning up to validation start
                train_start_date = min_date
                train_end_date = val_start_date
            else:  # rolling
                # Rolling: fixed window size ending at validation start
                train_end_date = val_start_date
                train_start_date = train_end_date - timedelta(days=30 * self.min_train_months)

            # Filter data for this fold
            train_df = df.filter(
                (col("date") >= lit(train_start_date)) &
                (col("date") < lit(train_end_date))
            )

            val_df = df.filter(
                (col("date") >= lit(val_start_date)) &
                (col("date") < lit(val_end_date))
            )

            folds.append((train_df, val_df))

        return folds

    def _evaluate_fold(
        self,
        predictions: DataFrame,
        actuals: DataFrame,
        fold_idx: int
    ) -> Dict[str, float]:
        """
        Evaluate predictions for one fold.

        Calculates:
        - Directional accuracy from day 0
        - MAE, RMSE

        Args:
            predictions: DataFrame with forecast_day_1...forecast_day_14
            actuals: DataFrame with actual values
            fold_idx: Fold index for logging

        Returns:
            Dict with metrics
        """
        # Convert to pandas for easier calculation
        pred_pd = predictions.toPandas()
        actual_pd = actuals.toPandas()

        # Join on date
        merged = pred_pd.merge(actual_pd, on='date', suffixes=('_pred', '_actual'))

        # Calculate directional accuracy from day 0
        dir_accuracies = []
        for day in range(1, self.horizon + 1):
            # Actual direction: is day_i > day_0?
            actual_dir = merged[f'close_day_{day}_actual'] > merged['close_day_0_actual']
            forecast_dir = merged[f'forecast_day_{day}'] > merged['close_day_0_actual']

            # Accuracy: did we get the direction right?
            correct = (actual_dir == forecast_dir).mean()
            dir_accuracies.append(correct)

        # Calculate MAE and RMSE
        forecast_cols = [f'forecast_day_{i}' for i in range(1, self.horizon + 1)]
        actual_cols = [f'close_day_{i}_actual' for i in range(1, self.horizon + 1)]

        forecasts = merged[forecast_cols].values.flatten()
        actuals_flat = merged[actual_cols].values.flatten()

        mae = np.abs(forecasts - actuals_flat).mean()
        rmse = np.sqrt(((forecasts - actuals_flat) ** 2).mean())

        # Store residuals for Monte Carlo
        residuals_df = pd.DataFrame({
            f'residual_day_{i}': merged[f'close_day_{i}_actual'] - merged[f'forecast_day_{i}']
            for i in range(1, self.horizon + 1)
        })
        residuals_df['fold'] = fold_idx
        self.residuals.append(residuals_df)

        return {
            'directional_accuracy_day0': np.mean(dir_accuracies),
            'mae': mae,
            'rmse': rmse,
            'fold': fold_idx
        }

    def fit(self) -> Dict[str, Any]:
        """
        Run time-series cross-validation.

        Returns:
            Dict with:
                - cv_metrics: List of metrics per fold
                - mean_directional_accuracy: Average across folds
                - mean_mae: Average MAE
                - mean_rmse: Average RMSE
                - fold_models: List of fitted PipelineModels
        """
        # Load data
        df = self.spark.table(self.table_name)
        df = df.filter(col("commodity") == self.commodity)

        # Create folds
        folds = self._create_folds(df)
        print(f"Created {len(folds)} CV folds ({self.window_type} window)")

        # Train and evaluate each fold
        for fold_idx, (train_df, val_df) in enumerate(folds):
            print(f"\nFold {fold_idx + 1}/{len(folds)}:")
            print(f"  Train: {train_df.count()} rows")
            print(f"  Val: {val_df.count()} rows")

            # Fit pipeline
            model = self.pipeline.fit(train_df)
            self.fold_models.append(model)

            # Generate predictions
            predictions = model.transform(val_df)

            # Evaluate
            metrics = self._evaluate_fold(predictions, val_df, fold_idx)
            self.fold_metrics.append(metrics)

            print(f"  Directional Accuracy: {metrics['directional_accuracy_day0']:.3f}")
            print(f"  MAE: {metrics['mae']:.2f}")
            print(f"  RMSE: {metrics['rmse']:.2f}")

        # Aggregate metrics
        mean_metrics = {
            'mean_directional_accuracy': np.mean([m['directional_accuracy_day0'] for m in self.fold_metrics]),
            'mean_mae': np.mean([m['mae'] for m in self.fold_metrics]),
            'mean_rmse': np.mean([m['rmse'] for m in self.fold_metrics]),
            'std_directional_accuracy': np.std([m['directional_accuracy_day0'] for m in self.fold_metrics]),
            'std_mae': np.std([m['mae'] for m in self.fold_metrics]),
            'std_rmse': np.std([m['rmse'] for m in self.fold_metrics])
        }

        return {
            'cv_metrics': self.fold_metrics,
            'fold_models': self.fold_models,
            **mean_metrics
        }

    def get_residuals(self) -> pd.DataFrame:
        """
        Get residuals from all CV folds for Monte Carlo simulation.

        Returns:
            DataFrame with columns: residual_day_1...residual_day_14, fold
        """
        if not self.residuals:
            raise ValueError("Must call fit() before get_residuals()")

        return pd.concat(self.residuals, ignore_index=True)

    def get_final_model(self, df: Optional[DataFrame] = None) -> PipelineModel:
        """
        Train final model on all available data.

        Args:
            df: Optional DataFrame. If None, loads from table.

        Returns:
            Fitted PipelineModel on full dataset
        """
        if df is None:
            df = self.spark.table(self.table_name)
            df = df.filter(col("commodity") == self.commodity)

        print(f"Training final model on {df.count()} rows...")
        final_model = self.pipeline.fit(df)

        return final_model
