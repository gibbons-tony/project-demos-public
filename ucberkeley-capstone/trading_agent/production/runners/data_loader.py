"""
Data Loading Module
Handles loading prices and prediction matrices for backtesting
"""

import pandas as pd
import pickle
import json
import os
from typing import Dict, Tuple, Optional, Any
from pyspark.sql import functions as F


class DataLoader:
    """Loads price data and prediction matrices for commodity-model pairs"""

    def __init__(self, spark=None, volume_path=None):
        """
        Initialize data loader

        Args:
            spark: Spark session (required for loading from Delta tables)
            volume_path: Base path for volume storage (for manifest loading)
        """
        self.spark = spark
        self.volume_path = volume_path
        self._manifest_cache = {}  # Cache loaded manifests

    def load_forecast_manifest(self, commodity: str) -> Optional[Dict]:
        """
        Load forecast manifest for a commodity

        Args:
            commodity: Commodity name

        Returns:
            Dict with manifest data or None if not found
        """
        # Check cache first
        if commodity in self._manifest_cache:
            return self._manifest_cache[commodity]

        if not self.volume_path:
            return None

        manifest_path = os.path.join(self.volume_path, f'forecast_manifest_{commodity}.json')

        try:
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            self._manifest_cache[commodity] = manifest
            return manifest
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"  ⚠️  Warning: Could not load manifest: {e}")
            return None

    def load_commodity_data(
        self,
        commodity: str,
        model_version: str,
        data_paths: Dict[str, str]
    ) -> Tuple[pd.DataFrame, Dict[Any, Any]]:
        """
        Load prices and prediction matrices for a commodity-model pair

        Args:
            commodity: Commodity name (e.g., 'coffee', 'sugar')
            model_version: Model version identifier
            data_paths: Dictionary of data paths from config

        Returns:
            Tuple of (prices_df, prediction_matrices_dict)

        Raises:
            ValueError: If required data cannot be loaded
        """
        print(f"\nLoading data for {commodity.upper()} - {model_version}...")

        # Load manifest for this commodity (if available)
        manifest = self.load_forecast_manifest(commodity)

        # Load prices
        prices = self._load_prices(commodity, data_paths)
        print(f"  ✓ Loaded {len(prices)} days of prices")

        # Load prediction matrices (passing manifest for enhanced logging)
        prediction_matrices = self._load_prediction_matrices(
            commodity, model_version, data_paths, manifest
        )
        print(f"  ✓ Loaded {len(prediction_matrices)} prediction matrices")

        # CRITICAL: Filter data to manifest date range for this model
        # TEMPORARILY DISABLED FOR TESTING - to check if this causes performance difference
        if False and manifest and 'models' in manifest:
            model_info = manifest['models'].get(model_version)
            if model_info:
                start_date = pd.to_datetime(model_info['date_range']['start'])
                end_date = pd.to_datetime(model_info['date_range']['end'])

                # Filter prices to manifest date range
                original_price_count = len(prices)
                prices = prices[(prices['date'] >= start_date) & (prices['date'] <= end_date)].copy()

                # Filter prediction matrices to manifest date range
                original_pred_count = len(prediction_matrices)
                prediction_matrices = {
                    k: v for k, v in prediction_matrices.items()
                    if start_date <= k <= end_date
                }

                print(f"  ✓ Filtered to manifest date range: {start_date.date()} to {end_date.date()}")
                print(f"    • Prices: {original_price_count} → {len(prices)} days")
                print(f"    • Predictions: {original_pred_count} → {len(prediction_matrices)} matrices")
            else:
                print(f"  ⚠️  Model {model_version} not in manifest - using all available data")
        else:
            print(f"  ⚠️  Manifest filtering DISABLED for testing - using all available data")

        # Validate data
        self._validate_data(prices, prediction_matrices, model_version)

        return prices, prediction_matrices

    def _load_prices(self, commodity: str, data_paths: Dict[str, str]) -> pd.DataFrame:
        """
        Load price data from commodity.silver.unified_data (continuous daily coverage)

        Uses unified_data table which provides:
        - Continuous daily coverage (every day since 2015-07-07, no gaps)
        - Forward-filled prices (no NULL values)
        - Multi-region grain, but prices are identical across regions

        Args:
            commodity: Commodity name to filter by (e.g., 'coffee')
            data_paths: Dictionary containing data paths (not used for prices, kept for compatibility)

        Returns:
            DataFrame with columns ['date', 'price']
        """
        if self.spark is None:
            raise ValueError("Spark session required to load prices from Delta table")

        # Load from unified_data (continuous daily coverage, forward-filled)
        # unified_data grain is (date, commodity, region) but price is same across regions
        # Aggregate by date to get one row per date
        prices = self.spark.table("commodity.silver.unified_data").filter(
            f"lower(commodity) = '{commodity.lower()}'"
        ).groupBy("date").agg(
            F.first("close").alias("price")  # Price is identical across regions, take first
        ).toPandas()

        # CRITICAL: Normalize dates to midnight for dictionary lookup compatibility
        prices['date'] = pd.to_datetime(prices['date']).dt.normalize()
        prices = prices.sort_values('date').reset_index(drop=True)

        return prices

    def _load_prediction_matrices(
        self,
        commodity: str,
        model_version: str,
        data_paths: Dict[str, str],
        manifest: Optional[Dict] = None
    ) -> Dict[Any, Any]:
        """
        Load prediction matrices from pickle file

        Args:
            commodity: Commodity name
            model_version: Model version to determine source type
            data_paths: Dictionary with matrix file paths
            manifest: Optional forecast manifest with metadata

        Returns:
            Dictionary mapping {timestamp: numpy_array(n_paths, n_horizons)}
        """
        # Determine source type and select appropriate path
        if model_version.startswith('synthetic_'):
            matrix_path = data_paths['prediction_matrices']
            source_type = "SYNTHETIC"
        else:
            matrix_path = data_paths['prediction_matrices_real']
            source_type = "REAL"

        try:
            with open(matrix_path, 'rb') as f:
                prediction_matrices = pickle.load(f)

            # CRITICAL: Normalize dictionary keys to midnight for price alignment
            # Prices are normalized with .dt.normalize(), so matrices must match
            normalized_matrices = {}
            for key, value in prediction_matrices.items():
                normalized_key = pd.to_datetime(key).normalize()
                normalized_matrices[normalized_key] = value
            prediction_matrices = normalized_matrices

            # Log forecast availability (use manifest if available, otherwise calculate)
            if len(prediction_matrices) > 0:
                sample_matrix = list(prediction_matrices.values())[0]
                print(f"  ✓ Source: {source_type}")
                print(f"  ✓ Matrix structure: {sample_matrix.shape[0]} runs × {sample_matrix.shape[1]} horizons")

                # Check if manifest has info for this model
                model_info = None
                if manifest and 'models' in manifest:
                    model_info = manifest['models'].get(model_version)

                if model_info:
                    # Use manifest data (faster, already validated)
                    print(f"  ✓ Forecast metadata (from manifest):")
                    print(f"    • Date range: {model_info['date_range']['start']} to {model_info['date_range']['end']}")
                    print(f"    • Time span: {model_info['years_span']:.2f} years ({model_info['expected_days']} days)")
                    print(f"    • Prediction dates: {model_info['prediction_dates']}")
                    print(f"    • Coverage: {model_info['coverage_pct']:.1f}%")
                    print(f"    • Years available: {model_info['years_available']}")
                    print(f"    • Quality: {model_info['quality']}")
                    print(f"    • Validated: {'✅ PASS' if model_info['meets_criteria'] else '⚠️ FAIL'}")
                else:
                    # Calculate from loaded data (fallback if no manifest)
                    print(f"  ⚠️  No manifest found - calculating metrics from pickle...")
                    pred_dates = sorted(prediction_matrices.keys())
                    min_date = pred_dates[0]
                    max_date = pred_dates[-1]

                    total_days_span = (max_date - min_date).days + 1
                    years_span = total_days_span / 365.25
                    prediction_days = len(prediction_matrices)
                    coverage_pct = (prediction_days / total_days_span * 100) if total_days_span > 0 else 0
                    years_available = sorted(set(d.year for d in pred_dates))

                    print(f"  ✓ Forecast availability:")
                    print(f"    • Date range: {min_date.date()} to {max_date.date()}")
                    print(f"    • Time span: {years_span:.2f} years ({total_days_span} days)")
                    print(f"    • Prediction dates: {prediction_days}")
                    print(f"    • Coverage: {coverage_pct:.1f}%")
                    print(f"    • Years available: {years_available}")

            return prediction_matrices

        except FileNotFoundError:
            raise ValueError(
                f"Prediction matrices not found at {matrix_path}. "
                f"Run data preparation first (notebook 01 or 02)."
            )
        except Exception as e:
            raise ValueError(f"Error loading prediction matrices: {e}")

    def _validate_data(
        self,
        prices: pd.DataFrame,
        prediction_matrices: Dict[Any, Any],
        model_version: str
    ) -> None:
        """
        Validate loaded data quality and alignment

        Args:
            prices: Price DataFrame
            prediction_matrices: Prediction matrix dictionary
            model_version: Model version for error messages
        """
        # Check prices structure
        required_cols = ['date', 'price']
        missing_cols = set(required_cols) - set(prices.columns)
        if missing_cols:
            raise ValueError(f"Prices missing required columns: {missing_cols}")

        # Check for null prices
        if prices['price'].isna().any():
            null_count = prices['price'].isna().sum()
            raise ValueError(f"Found {null_count} null prices in data")

        # Check prediction matrices structure
        if len(prediction_matrices) == 0:
            raise ValueError(f"No prediction matrices found for {model_version}")

        # Date alignment check
        pred_keys = set(prediction_matrices.keys())
        price_dates = set(prices['date'].tolist())
        overlap = pred_keys.intersection(price_dates)

        match_rate = len(overlap) / len(pred_keys) if len(pred_keys) > 0 else 0

        if match_rate < 0.5:
            raise ValueError(
                f"Poor date alignment between prices and predictions. "
                f"Match rate: {match_rate*100:.1f}%. "
                f"Expected at least 50% overlap."
            )

        print(f"  ✓ Validation passed - {len(overlap)} matching dates ({match_rate*100:.1f}% coverage)")

    def get_data_summary(
        self,
        prices: pd.DataFrame,
        prediction_matrices: Dict[Any, Any]
    ) -> Dict[str, Any]:
        """
        Get summary statistics for loaded data

        Args:
            prices: Price DataFrame
            prediction_matrices: Prediction matrix dictionary

        Returns:
            Dictionary with summary statistics
        """
        summary = {
            'n_price_days': len(prices),
            'price_date_range': (prices['date'].min(), prices['date'].max()),
            'price_range': (prices['price'].min(), prices['price'].max()),
            'n_prediction_dates': len(prediction_matrices),
            'avg_price': prices['price'].mean(),
            'std_price': prices['price'].std()
        }

        if len(prediction_matrices) > 0:
            sample_matrix = list(prediction_matrices.values())[0]
            summary['prediction_runs'] = sample_matrix.shape[0]
            summary['prediction_horizons'] = sample_matrix.shape[1]

        return summary

    def discover_model_versions(
        self,
        commodity: str,
        forecast_table: str = "commodity.forecast.distributions"
    ) -> Tuple[list, list]:
        """
        Discover all available model versions for a commodity

        Args:
            commodity: Commodity name
            forecast_table: Unity Catalog table with forecasts

        Returns:
            Tuple of (synthetic_versions, real_versions)
        """
        if self.spark is None:
            raise ValueError("Spark session required to discover model versions")

        print(f"\nDiscovering model versions for {commodity}...")

        # Check synthetic predictions (from generated tables)
        synthetic_versions = []
        try:
            output_schema = "commodity.trading_agent"
            pred_table = f"{output_schema}.predictions_{commodity.lower()}"
            synthetic_df = self.spark.table(pred_table).select("model_version").distinct()
            synthetic_versions = [row.model_version for row in synthetic_df.collect()]
            if synthetic_versions:
                print(f"  Synthetic models: {synthetic_versions}")
        except Exception:
            pass  # Table may not exist yet

        # Check real predictions (from forecast table)
        real_versions = []
        try:
            real_df = self.spark.table(forecast_table) \
                .filter(f"commodity = '{commodity.title()}' AND is_actuals = false") \
                .select("model_version") \
                .distinct() \
                .orderBy("model_version")
            real_versions = [row.model_version for row in real_df.collect()]
            if real_versions:
                print(f"  Real models: {real_versions}")
        except Exception as e:
            print(f"  Warning: Could not check real predictions: {e}")

        # Combine
        all_versions = list(set(synthetic_versions + real_versions))

        if len(all_versions) == 0:
            print(f"  ⚠️  No model versions found for {commodity}")
        else:
            print(f"  ✓ Found {len(all_versions)} total model versions")

        return synthetic_versions, real_versions
