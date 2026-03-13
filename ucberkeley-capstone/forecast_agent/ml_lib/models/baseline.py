"""
Baseline forecasting models (Naive, Random Walk).

These are simple models that serve as benchmarks for more complex approaches.
"""
from pyspark.ml.base import Estimator, Model, Transformer
from pyspark.ml.param.shared import HasInputCol, HasOutputCol, Param, Params
from pyspark.sql import DataFrame
from pyspark.sql.functions import col, lit, last, lag, row_number
from pyspark.sql.window import Window
from typing import Dict, Any
import pandas as pd


class NaiveForecaster(Transformer):
    """
    Naive forecasting: forecast = last observed value.

    This is a stateless transformer that generates 14-day forecasts
    where all days equal the last observed close price.

    For time-series CV, this will be called once per fold with different
    cutoff dates.

    Input columns:
        - date: DATE
        - close: DOUBLE (target variable)

    Output columns (added):
        - forecast_day_1, forecast_day_2, ..., forecast_day_14: DOUBLE

    Example:
        forecaster = NaiveForecaster(inputCol="close")
        df_with_forecasts = forecaster.transform(df)
        # Last row will have forecast columns populated
    """

    horizon = Param(
        Params._dummy(),
        "horizon",
        "Forecast horizon in days"
    )

    inputCol = Param(
        Params._dummy(),
        "inputCol",
        "Input column name (target variable)"
    )

    def __init__(self, inputCol: str = "close", horizon: int = 14):
        super(NaiveForecaster, self).__init__()
        self._setDefault(horizon=14, inputCol="close")
        self._set(horizon=horizon, inputCol=inputCol)

    def _transform(self, df: DataFrame) -> DataFrame:
        """
        Add forecast columns using naive method (last value).

        Assumes df is ordered by date and represents training data
        up to a cutoff point.
        """
        input_col = self.getOrDefault(self.inputCol)
        horizon = self.getOrDefault(self.horizon)

        # Get the last value using window function
        window_spec = Window.orderBy("date").rowsBetween(Window.unboundedPreceding, Window.unboundedFollowing)
        df = df.withColumn("_last_value", last(col(input_col)).over(window_spec))

        # Create forecast columns (all equal to last value)
        for day in range(1, horizon + 1):
            df = df.withColumn(f"forecast_day_{day}", col("_last_value"))

        # Drop temporary column
        df = df.drop("_last_value")

        return df


def naive_forecast_pandas(df_pandas: pd.DataFrame, horizon: int = 14, target: str = 'close') -> pd.DataFrame:
    """
    Naive forecast using pandas (for local execution).

    Args:
        df_pandas: Pandas DataFrame with 'date' and target column
        horizon: Forecast horizon
        target: Target column name

    Returns:
        DataFrame with forecast_day_1...forecast_day_14 columns

    Example:
        forecast_df = naive_forecast_pandas(train_df, horizon=14)
        print(forecast_df[['forecast_day_1', 'forecast_day_14']])
    """
    last_value = df_pandas[target].iloc[-1]

    # Create forecast columns
    forecast_dict = {f'forecast_day_{i}': last_value for i in range(1, horizon + 1)}

    # Create DataFrame with one row per forecast
    forecast_df = pd.DataFrame([forecast_dict])

    return forecast_df


def random_walk_forecast_pandas(df_pandas: pd.DataFrame, horizon: int = 14, target: str = 'close') -> pd.DataFrame:
    """
    Random walk forecast: forecast[t+1] = actual[t].

    This is slightly different from naive:
    - Naive: all days = last_value
    - Random walk with drift: day_i = last_value + (i * average_daily_change)

    For simplicity, we'll implement basic random walk (no drift) which
    is equivalent to naive.

    Args:
        df_pandas: Pandas DataFrame with 'date' and target column
        horizon: Forecast horizon
        target: Target column name

    Returns:
        DataFrame with forecast columns
    """
    # For random walk without drift, this is the same as naive
    return naive_forecast_pandas(df_pandas, horizon, target)
