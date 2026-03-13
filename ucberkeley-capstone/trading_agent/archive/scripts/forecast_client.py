"""Simple client library for querying forecast distributions from Databricks.

Usage:
    from forecast_client import ForecastClient

    client = ForecastClient()

    # Get latest forecast
    dist = client.get_latest_forecast(model='sarimax_auto_weather_v1')
    print(f"Mean 7-day forecast: ${dist[:, 6].mean():.2f}")

    # Calculate VaR
    var = client.calculate_var(model='sarimax_auto_weather_v1', day=7, percentile=0.05)
    print(f"VaR 95%: ${var:.2f}")
"""

import os
import numpy as np
import pandas as pd
from databricks import sql
from typing import Optional, Tuple
from datetime import datetime


class ForecastClient:
    """Client for querying commodity.forecast.distributions table."""

    def __init__(self,
                 server_hostname: Optional[str] = None,
                 http_path: Optional[str] = None,
                 token: Optional[str] = None):
        """
        Initialize Databricks connection.

        Args:
            server_hostname: Databricks workspace URL
            http_path: SQL warehouse HTTP path
            token: Personal access token

        If not provided, reads from environment variables:
        - DATABRICKS_HOST
        - DATABRICKS_HTTP_PATH
        - DATABRICKS_TOKEN
        """
        self.server_hostname = server_hostname or os.environ.get("DATABRICKS_HOST", "").replace("https://", "")
        self.http_path = http_path or os.environ.get("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/3cede8561503a13c")
        self.token = token or os.environ.get("DATABRICKS_TOKEN")

        if not all([self.server_hostname, self.http_path, self.token]):
            raise ValueError(
                "Missing Databricks credentials. Set environment variables:\n"
                "  DATABRICKS_HOST, DATABRICKS_HTTP_PATH, DATABRICKS_TOKEN"
            )

        self.catalog = "commodity"
        self.schema = "forecast"
        self._conn = None

    def _get_connection(self):
        """Get or create Databricks connection."""
        if self._conn is None:
            self._conn = sql.connect(
                server_hostname=self.server_hostname,
                http_path=self.http_path,
                access_token=self.token
            )
        return self._conn

    def close(self):
        """Close connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def get_latest_forecast(self,
                           model: str = 'sarimax_auto_weather_v1',
                           commodity: str = 'Coffee') -> np.ndarray:
        """
        Get latest forecast distributions (2,000 Monte Carlo paths × 14 days).

        Args:
            model: Model version (e.g., 'sarimax_auto_weather_v1')
            commodity: 'Coffee' or 'Sugar'

        Returns:
            numpy array of shape (2000, 14) - 2,000 paths, 14 days
        """
        query = f"""
            SELECT
                day_1, day_2, day_3, day_4, day_5, day_6, day_7,
                day_8, day_9, day_10, day_11, day_12, day_13, day_14
            FROM {self.catalog}.{self.schema}.distributions
            WHERE model_version = '{model}'
              AND commodity = '{commodity}'
              AND is_actuals = FALSE
              AND has_data_leakage = FALSE
              AND forecast_start_date = (
                SELECT MAX(forecast_start_date)
                FROM {self.catalog}.{self.schema}.distributions
                WHERE model_version = '{model}'
              )
            ORDER BY path_id
        """

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            cursor.close()

        if not rows:
            raise ValueError(f"No forecast found for model={model}, commodity={commodity}")

        # Convert to numpy array
        distributions = np.array([[row[i] for i in range(14)] for row in rows])
        return distributions

    def get_forecast_metadata(self,
                             model: str = 'sarimax_auto_weather_v1',
                             commodity: str = 'Coffee') -> dict:
        """
        Get metadata about latest forecast.

        Returns:
            dict with keys: forecast_start_date, data_cutoff_date, generation_timestamp
        """
        query = f"""
            SELECT
                forecast_start_date,
                data_cutoff_date,
                generation_timestamp
            FROM {self.catalog}.{self.schema}.distributions
            WHERE model_version = '{model}'
              AND commodity = '{commodity}'
              AND forecast_start_date = (
                SELECT MAX(forecast_start_date)
                FROM {self.catalog}.{self.schema}.distributions
                WHERE model_version = '{model}'
              )
            LIMIT 1
        """

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            row = cursor.fetchone()
            cursor.close()

        if not row:
            raise ValueError(f"No forecast found for model={model}, commodity={commodity}")

        return {
            'forecast_start_date': row[0],
            'data_cutoff_date': row[1],
            'generation_timestamp': row[2]
        }

    def calculate_var(self,
                     model: str = 'sarimax_auto_weather_v1',
                     commodity: str = 'Coffee',
                     day: int = 7,
                     percentile: float = 0.05) -> float:
        """
        Calculate Value at Risk (VaR) for a specific day.

        Args:
            model: Model version
            commodity: 'Coffee' or 'Sugar'
            day: Forecast day (1-14)
            percentile: Risk percentile (0.05 = 5th percentile, 0.01 = 1st percentile)

        Returns:
            VaR price level
        """
        distributions = self.get_latest_forecast(model=model, commodity=commodity)
        day_prices = distributions[:, day - 1]  # day=1 is index 0
        var = np.percentile(day_prices, percentile * 100)
        return var

    def calculate_cvar(self,
                      model: str = 'sarimax_auto_weather_v1',
                      commodity: str = 'Coffee',
                      day: int = 7,
                      percentile: float = 0.01) -> float:
        """
        Calculate Conditional Value at Risk (CVaR / Expected Shortfall).

        CVaR is the expected value of losses beyond the VaR threshold.

        Args:
            model: Model version
            commodity: 'Coffee' or 'Sugar'
            day: Forecast day (1-14)
            percentile: Risk percentile (0.01 = worst 1%, 0.05 = worst 5%)

        Returns:
            CVaR (expected price in worst-case scenarios)
        """
        distributions = self.get_latest_forecast(model=model, commodity=commodity)
        day_prices = distributions[:, day - 1]

        var = np.percentile(day_prices, percentile * 100)
        cvar = day_prices[day_prices <= var].mean()
        return cvar

    def get_forecast_statistics(self,
                                model: str = 'sarimax_auto_weather_v1',
                                commodity: str = 'Coffee',
                                day: int = 7) -> dict:
        """
        Get summary statistics for a specific forecast day.

        Returns:
            dict with keys: mean, std, var_95, var_99, cvar_99, min, max
        """
        distributions = self.get_latest_forecast(model=model, commodity=commodity)
        day_prices = distributions[:, day - 1]

        return {
            'mean': day_prices.mean(),
            'std': day_prices.std(),
            'var_95': np.percentile(day_prices, 5),
            'var_99': np.percentile(day_prices, 1),
            'cvar_99': day_prices[day_prices <= np.percentile(day_prices, 1)].mean(),
            'min': day_prices.min(),
            'max': day_prices.max()
        }

    def get_actuals(self,
                   model: str = 'sarimax_auto_weather_v1',
                   commodity: str = 'Coffee',
                   limit: int = 10) -> pd.DataFrame:
        """
        Get historical actuals (path_id=0) for backtesting.

        Args:
            model: Model version (not used, actuals are model-agnostic)
            commodity: 'Coffee' or 'Sugar'
            limit: Number of recent forecast dates to return

        Returns:
            DataFrame with columns: forecast_start_date, day_1...day_14
        """
        query = f"""
            SELECT
                forecast_start_date,
                day_1, day_2, day_3, day_4, day_5, day_6, day_7,
                day_8, day_9, day_10, day_11, day_12, day_13, day_14
            FROM {self.catalog}.{self.schema}.distributions
            WHERE path_id = 0
              AND is_actuals = TRUE
              AND commodity = '{commodity}'
            ORDER BY forecast_start_date DESC
            LIMIT {limit}
        """

        with self._get_connection() as conn:
            df = pd.read_sql(query, conn)

        return df

    def compare_models(self,
                      models: list = None,
                      commodity: str = 'Coffee',
                      day: int = 7) -> pd.DataFrame:
        """
        Compare forecast statistics across multiple models.

        Args:
            models: List of model versions (default: all 5 production models)
            commodity: 'Coffee' or 'Sugar'
            day: Forecast day to compare (1-14)

        Returns:
            DataFrame with columns: model_version, mean, std, var_95, var_99
        """
        if models is None:
            models = [
                'sarimax_auto_weather_v1',
                'prophet_v1',
                'xgboost_weather_v1',
                'arima_111_v1',
                'random_walk_v1'
            ]

        results = []
        for model in models:
            try:
                stats = self.get_forecast_statistics(model=model, commodity=commodity, day=day)
                results.append({
                    'model_version': model,
                    **stats
                })
            except ValueError:
                # Model not available
                continue

        return pd.DataFrame(results)


# Example usage
if __name__ == "__main__":
    # Initialize client
    client = ForecastClient()

    print("="*80)
    print("FORECAST CLIENT DEMO")
    print("="*80)

    # Get latest forecast
    print("\n[1/4] Fetching latest forecast...")
    dist = client.get_latest_forecast(model='sarimax_auto_weather_v1')
    print(f"  ✓ Loaded {len(dist)} Monte Carlo paths")
    print(f"  ✓ Shape: {dist.shape} (2000 paths × 14 days)")

    # Get metadata
    print("\n[2/4] Forecast metadata...")
    meta = client.get_forecast_metadata()
    print(f"  Forecast start: {meta['forecast_start_date']}")
    print(f"  Data cutoff: {meta['data_cutoff_date']}")
    print(f"  Generated: {meta['generation_timestamp']}")

    # Calculate risk metrics
    print("\n[3/4] Risk metrics (7-day ahead)...")
    stats = client.get_forecast_statistics(day=7)
    print(f"  Mean forecast: ${stats['mean']:.2f}")
    print(f"  Std deviation: ${stats['std']:.2f}")
    print(f"  VaR 95% (downside): ${stats['var_95']:.2f}")
    print(f"  VaR 99% (extreme): ${stats['var_99']:.2f}")
    print(f"  CVaR 99%: ${stats['cvar_99']:.2f}")

    # Compare models
    print("\n[4/4] Model comparison (7-day ahead)...")
    comparison = client.compare_models(day=7)
    print(comparison[['model_version', 'mean', 'std', 'var_95']].to_string(index=False))

    print("\n" + "="*80)
    print("✅ DEMO COMPLETE")
    print("="*80)

    client.close()
