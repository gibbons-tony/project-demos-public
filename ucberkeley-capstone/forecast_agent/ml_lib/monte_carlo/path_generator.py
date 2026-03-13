"""
Monte Carlo path generation using block bootstrap on CV residuals.

Generates 2,000 realistic autocorrelated paths for uncertainty quantification.
"""
import pandas as pd
import numpy as np
from typing import Optional


class BlockBootstrapPathGenerator:
    """
    Generate Monte Carlo paths using block bootstrap on forecast residuals.

    Why block bootstrap?
    - Preserves autocorrelation structure of forecast errors
    - Works for ANY model type (ARIMA, XGBoost, LSTM, etc.)
    - Uses model-specific CV residuals (realistic uncertainty)

    How it works:
    1. Take forecast residuals from CV: errors = actual - predicted
    2. Bootstrap blocks of residuals (e.g., 3-day blocks) to preserve autocorrelation
    3. Add bootstrapped residuals to point forecast
    4. Repeat 2,000 times

    Example:
        from ml_lib.cross_validation import TimeSeriesForecastCV
        from ml_lib.monte_carlo import BlockBootstrapPathGenerator

        # Run CV
        cv = TimeSeriesForecastCV(...)
        results = cv.fit()
        residuals = cv.get_residuals()

        # Generate paths
        path_gen = BlockBootstrapPathGenerator(
            residuals=residuals,
            n_paths=2000,
            block_size=3
        )

        # Point forecast from model
        point_forecast = np.array([165.2, 165.5, 166.0, ...])  # 14 days

        # Generate 2000 paths
        paths = path_gen.generate_paths(point_forecast)
        # Shape: (2000, 14)
    """

    def __init__(
        self,
        residuals: pd.DataFrame,
        n_paths: int = 2000,
        block_size: int = 3,
        seed: Optional[int] = None
    ):
        """
        Initialize path generator.

        Args:
            residuals: DataFrame with residual_day_1...residual_day_14 columns
            n_paths: Number of Monte Carlo paths to generate
            block_size: Block size for bootstrap (preserves autocorrelation)
                       - 1 = simple bootstrap (no autocorrelation)
                       - 3 = 3-day blocks (recommended for daily forecasts)
                       - 7 = weekly blocks
            seed: Random seed for reproducibility
        """
        self.residuals = residuals
        self.n_paths = n_paths
        self.block_size = block_size
        self.rng = np.random.default_rng(seed)

        # Extract residual matrix (rows = dates, cols = horizon)
        residual_cols = [f'residual_day_{i}' for i in range(1, 15)]
        self.residual_matrix = residuals[residual_cols].values  # Shape: (n_samples, 14)

    def _block_bootstrap_sample(self, horizon: int) -> np.ndarray:
        """
        Sample one path using block bootstrap.

        Args:
            horizon: Forecast horizon

        Returns:
            Array of residuals (length = horizon)
        """
        sampled_residuals = []
        idx = 0

        while idx < horizon:
            # Randomly select a starting point for the block
            block_start_idx = self.rng.integers(0, len(self.residual_matrix))

            # Extract block (up to block_size days)
            block_end = min(idx + self.block_size, horizon)
            block_length = block_end - idx

            # Get residuals for this block
            block_residuals = self.residual_matrix[block_start_idx, idx:idx+block_length]
            sampled_residuals.extend(block_residuals)

            idx += block_length

        return np.array(sampled_residuals[:horizon])

    def generate_paths(
        self,
        point_forecast: np.ndarray,
        return_dataframe: bool = False
    ) -> np.ndarray:
        """
        Generate Monte Carlo paths around a point forecast.

        Args:
            point_forecast: Point forecast array (length = horizon)
                           Example: [165.2, 165.5, 166.0, ...]
            return_dataframe: If True, returns DataFrame with path_id column

        Returns:
            If return_dataframe=False (default):
                Array of shape (n_paths, horizon)
            If return_dataframe=True:
                DataFrame with columns: path_id, day_1, day_2, ..., day_14
        """
        horizon = len(point_forecast)
        paths = np.zeros((self.n_paths, horizon))

        for path_id in range(self.n_paths):
            # Sample residuals using block bootstrap
            sampled_residuals = self._block_bootstrap_sample(horizon)

            # Add to point forecast
            paths[path_id] = point_forecast + sampled_residuals

        if return_dataframe:
            # Convert to DataFrame for easy table writing
            df_paths = pd.DataFrame(
                paths,
                columns=[f'day_{i}' for i in range(1, horizon + 1)]
            )
            df_paths['path_id'] = range(self.n_paths)
            return df_paths

        return paths

    def generate_paths_batch(
        self,
        point_forecasts: pd.DataFrame,
        forecast_cols: Optional[list] = None
    ) -> pd.DataFrame:
        """
        Generate paths for multiple point forecasts (batch processing).

        Args:
            point_forecasts: DataFrame with point forecast columns
                            Must have: date, commodity, model_name, day_1...day_14
            forecast_cols: List of forecast column names. If None, uses day_1...day_14

        Returns:
            DataFrame with columns:
                date, commodity, model_name, path_id, day_1, day_2, ..., day_14
        """
        if forecast_cols is None:
            forecast_cols = [f'day_{i}' for i in range(1, 15)]

        all_paths = []

        for idx, row in point_forecasts.iterrows():
            # Extract point forecast
            point_forecast = row[forecast_cols].values

            # Generate paths for this forecast
            paths = self.generate_paths(point_forecast, return_dataframe=True)

            # Add metadata
            paths['date'] = row['date']
            paths['commodity'] = row['commodity']
            paths['model_name'] = row['model_name']

            all_paths.append(paths)

        return pd.concat(all_paths, ignore_index=True)


def simple_gaussian_paths(
    point_forecast: np.ndarray,
    std_dev: float,
    n_paths: int = 2000,
    seed: Optional[int] = None
) -> np.ndarray:
    """
    Simple Gaussian path generation (baseline, not recommended).

    WARNING: This does NOT preserve autocorrelation! Paths will look zig-zaggy.
    Use BlockBootstrapPathGenerator instead for realistic paths.

    This function is provided for comparison/debugging only.

    Args:
        point_forecast: Point forecast array
        std_dev: Standard deviation of Gaussian noise
        n_paths: Number of paths
        seed: Random seed

    Returns:
        Array of shape (n_paths, horizon)
    """
    rng = np.random.default_rng(seed)
    horizon = len(point_forecast)

    # Generate paths: forecast + Gaussian noise
    paths = rng.normal(
        loc=point_forecast,
        scale=std_dev,
        size=(n_paths, horizon)
    )

    return paths
