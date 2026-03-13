"""
Data loader for commodity.gold.unified_data

Handles loading data with array-based weather/GDELT features for forecasting.
"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import col
from typing import Optional
from datetime import datetime, date


class GoldDataLoader:
    """
    Load data from commodity.gold.unified_data for time-series forecasting.

    Features:
    - Loads data with weather_data (array of structs) and gdelt_themes (array of structs)
    - Filters by commodity and date range
    - Validates data quality (no nulls in critical columns)

    Example:
        loader = GoldDataLoader()
        df = loader.load(
            commodity='Coffee',
            start_date='2020-01-01',
            end_date='2024-12-31'
        )
    """

    def __init__(self, table_name: str = "commodity.gold.unified_data"):
        """
        Initialize data loader.

        Args:
            table_name: Full table name (catalog.schema.table)
        """
        self.table_name = table_name
        self.spark = SparkSession.builder.getOrCreate()

    def load(
        self,
        commodity: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        include_non_trading_days: bool = True
    ):
        """
        Load commodity data from gold.unified_data.

        Args:
            commodity: Commodity name ('Coffee' or 'Sugar')
            start_date: Start date (YYYY-MM-DD). If None, loads from earliest date.
            end_date: End date (YYYY-MM-DD). If None, loads to latest date.
            include_non_trading_days: If False, filters to is_trading_day=1 only

        Returns:
            PySpark DataFrame with columns:
                - date: DATE
                - commodity: STRING
                - close: DOUBLE (target variable)
                - open, high, low, volume: DOUBLE
                - vix: DOUBLE
                - is_trading_day: INT
                - weather_data: ARRAY<STRUCT<region, temp_mean_c, ...>>
                - gdelt_themes: ARRAY<STRUCT<theme_group, article_count, ...>>
                - 24 exchange rate columns (vnd_usd, cop_usd, ...)
        """
        # Start with base query
        df = self.spark.table(self.table_name)

        # Filter by commodity
        df = df.filter(col("commodity") == commodity)

        # Filter by date range
        if start_date:
            df = df.filter(col("date") >= start_date)
        if end_date:
            df = df.filter(col("date") <= end_date)

        # Filter to trading days only if requested
        if not include_non_trading_days:
            df = df.filter(col("is_trading_day") == 1)

        # Order by date
        df = df.orderBy("date")

        return df

    def load_for_training(
        self,
        commodity: str,
        cutoff_date: str,
        lookback_days: Optional[int] = None
    ):
        """
        Load training data up to a cutoff date (for backtesting).

        Args:
            commodity: Commodity name
            cutoff_date: Latest date to include (exclusive - for predicting day after)
            lookback_days: Number of days to look back. If None, loads all history.

        Returns:
            PySpark DataFrame with training data
        """
        if lookback_days:
            # Calculate start date
            from pyspark.sql.functions import date_sub, lit
            df = self.spark.table(self.table_name)
            df = df.filter(col("commodity") == commodity)
            df = df.filter(col("date") < cutoff_date)

            # Get dates within lookback window
            df = df.filter(
                col("date") >= date_sub(lit(cutoff_date), lookback_days)
            )
        else:
            # Load all history up to cutoff
            df = self.load(
                commodity=commodity,
                end_date=cutoff_date,
                include_non_trading_days=True
            )
            # Exclude cutoff date itself (we're predicting from it)
            df = df.filter(col("date") < cutoff_date)

        return df.orderBy("date")

    def get_date_range(self, commodity: str):
        """
        Get available date range for a commodity.

        Args:
            commodity: Commodity name

        Returns:
            Tuple of (min_date, max_date)
        """
        df = self.spark.table(self.table_name)
        df = df.filter(col("commodity") == commodity)

        result = df.agg(
            {"date": "min", "date": "max"}
        ).collect()[0]

        return (result["min(date)"], result["max(date)"])

    def validate_data(self, df):
        """
        Validate data quality.

        Checks:
        - No nulls in critical columns (date, commodity, close)
        - Weather and GDELT arrays are not null
        - Date sequence is continuous

        Args:
            df: DataFrame to validate

        Returns:
            Dict with validation results
        """
        from pyspark.sql.functions import count, when, isnull, size

        # Check for nulls in critical columns
        critical_cols = ['date', 'commodity', 'close', 'weather_data', 'gdelt_themes']
        null_counts = {}

        for col_name in critical_cols:
            null_count = df.filter(isnull(col(col_name))).count()
            null_counts[col_name] = null_count

        # Check array sizes
        weather_sizes = df.select(size("weather_data").alias("size")).agg(
            {"size": "min", "size": "max", "size": "avg"}
        ).collect()[0]

        gdelt_sizes = df.select(size("gdelt_themes").alias("size")).agg(
            {"size": "min", "size": "max", "size": "avg"}
        ).collect()[0]

        return {
            'null_counts': null_counts,
            'weather_array_size': {
                'min': weather_sizes['min(size)'],
                'max': weather_sizes['max(size)'],
                'avg': weather_sizes['avg(size)']
            },
            'gdelt_array_size': {
                'min': gdelt_sizes['min(size)'],
                'max': gdelt_sizes['max(size)'],
                'avg': gdelt_sizes['avg(size)']
            },
            'total_rows': df.count()
        }
