"""
Imputation transformers for handling NULLs in commodity.gold.unified_data_raw.

Provides multiple imputation strategies optimized for time-series forecasting:
- forward_fill: For market data that persists (OHLV, VIX, weather)
- mean_7d: For stable short-term data (FX rates)
- zero: For non-existent historical data (GDELT - assumes neutral news)
- keep_null: For model-native NULL handling (XGBoost)

TODO: Implement forward_fill_decay strategy for GDELT (news relevance decays over time)
- News events should decay to 0 (neutral) over time
- Exponential decay: value * exp(-λ * days_since_observation)
- Half-life parameter (7 days recommended)
- More realistic than forward_fill (current news > old news)
- Add in Month 2-3 after initial validation

Key Design Decisions:
1. Cache after imputation for 2-3x speedup (see CACHING_STRATEGY.md)
2. Use window functions over partitionBy(commodity, region) for correctness
3. Handle edge cases: array fields, date-conditional logic, empty datasets

Performance:
- Target: < 60 seconds imputation overhead for 7k rows
- Total training slowdown: < 1.2x with caching (baseline ~250s)
"""
from pyspark.ml.base import Transformer
from pyspark.ml.param.shared import Param, Params, TypeConverters
from pyspark.sql import DataFrame
from pyspark.sql import Window
from pyspark.sql.functions import (
    col, when, coalesce, avg as spark_avg, lit,
    last as spark_last, size, expr, unix_timestamp
)
from typing import Dict, List, Optional


class ImputationTransformer(Transformer):
    """
    Impute missing values in unified_data_raw using time-series aware strategies.

    This transformer handles NULLs introduced by the two-table gold layer strategy:
    - commodity.gold.unified_data (forward-filled, production)
    - commodity.gold.unified_data_raw (NULLs preserved, experimental)

    Input Table Requirements:
    - Must have 'date' column (DATE type)
    - Must have 'commodity' column (for partitioning)
    - Must have 'region' column if using region-specific models

    NULL Patterns in unified_data_raw:
    - GDELT: ~73% NULL (data only available post-2021)
    - VIX, FX (24 cols), OHLV: ~30% NULL (weekends/holidays)
    - Weather: < 5% NULL (occasional API gaps)
    - close: 0% NULL (target variable, always forward-filled)

    Imputation Strategies:

    1. forward_fill (OHLV, VIX)
       - Last observed value carried forward
       - Use case: Market state persists over weekends
       - Implementation: last(..., ignorenulls=True).over(window)

    2. mean_7d (FX rates)
       - 7-day rolling average
       - Use case: Currency rates stable short-term
       - Implementation: avg(...).over(window_7d)

    3. zero (GDELT pre-2021)
       - Fill with 0
       - Use case: Data didn't exist historically
       - Implementation: coalesce(..., lit(0))

    4. keep_null (XGBoost-native handling)
       - Leave NULLs for model to handle
       - Use case: Tree models with native NULL support
       - Implementation: No transformation

    Configuration Options:

    Option 1: Default strategy for all features
        imputer = ImputationTransformer(default_strategy='forward_fill')

    Option 2: Per-feature strategy overrides
        imputer = ImputationTransformer(
            default_strategy='forward_fill',
            feature_strategies={
                'vix_close': 'forward_fill',
                'eur_usd': 'mean_7d',
                'weather_temp_mean_c_avg': 'forward_fill',
                'gdelt_*': 'zero'  # Wildcard for all GDELT features
            }
        )

    Option 3: Date-conditional strategies (GDELT)
        imputer = ImputationTransformer(
            default_strategy='forward_fill',
            date_conditional_strategies={
                'gdelt_*': {
                    'before': ('2021-01-01', 'zero'),
                    'after': ('2021-01-01', 'forward_fill')
                }
            }
        )

    Example Usage:

        # Load raw data with NULLs
        df_raw = spark.table('commodity.gold.unified_data_raw')

        # Impute and cache (critical for performance!)
        imputer = ImputationTransformer(default_strategy='forward_fill')
        df_imputed = imputer.transform(df_raw)
        df_imputed.cache()
        df_imputed.count()  # Materialize cache

        # Use in cross-validation (all folds use cached data)
        cv = TimeSeriesForecastCV(...)
        results = cv.fit(df_imputed)

    Performance Notes:
    - Always cache after imputation (see CACHING_STRATEGY.md)
    - Window functions are expensive, cache avoids recomputation
    - Expected speedup: 2-3x on 5-fold CV (250s → 90s total)
    - Imputation overhead budget: < 60 seconds

    Validation:
    - Compare metrics on unified_data vs unified_data_raw
    - Directional accuracy difference should be < 0.01
    - Total training time < 1.2x baseline (with caching)
    """

    default_strategy = Param(
        Params._dummy(),
        "default_strategy",
        "Default imputation strategy: 'forward_fill', 'mean_7d', 'zero', 'keep_null'",
        typeConverter=TypeConverters.toString
    )

    feature_strategies = Param(
        Params._dummy(),
        "feature_strategies",
        "Dict[str, str] mapping feature names to strategies. Supports wildcards like 'gdelt_*'",
        typeConverter=TypeConverters.identity
    )

    date_conditional_strategies = Param(
        Params._dummy(),
        "date_conditional_strategies",
        "Dict[str, Dict] for date-conditional imputation (e.g., GDELT pre/post 2021)",
        typeConverter=TypeConverters.identity
    )

    window_days = Param(
        Params._dummy(),
        "window_days",
        "Number of days for rolling window strategies (mean_7d, interpolate)",
        typeConverter=TypeConverters.toInt
    )

    def __init__(
        self,
        default_strategy: str = 'forward_fill',
        feature_strategies: Optional[Dict[str, str]] = None,
        date_conditional_strategies: Optional[Dict[str, Dict]] = None,
        window_days: int = 7
    ):
        super(ImputationTransformer, self).__init__()
        self._setDefault(
            default_strategy='forward_fill',
            feature_strategies={},
            date_conditional_strategies={},
            window_days=7
        )
        self._set(
            default_strategy=default_strategy,
            feature_strategies=feature_strategies or {},
            date_conditional_strategies=date_conditional_strategies or {},
            window_days=window_days
        )

    def _transform(self, df: DataFrame) -> DataFrame:
        """
        Apply imputation strategies to all features with NULLs.

        Process:
        1. Identify columns with NULLs (skip if no NULLs)
        2. Determine strategy for each column (per-feature > default)
        3. Apply appropriate imputation method
        4. Return transformed DataFrame
        """
        default_strat = self.getOrDefault(self.default_strategy)
        feature_strats = self.getOrDefault(self.feature_strategies)
        date_conditional_strats = self.getOrDefault(self.date_conditional_strategies)
        window_size = self.getOrDefault(self.window_days)

        # Define window for time-series operations
        # Partition by commodity (and region if exists) to avoid data leakage
        partition_cols = ['commodity']
        if 'region' in df.columns:
            partition_cols.append('region')

        window = Window.partitionBy(*partition_cols).orderBy('date').rowsBetween(Window.unboundedPreceding, 0)
        window_rolling = Window.partitionBy(*partition_cols).orderBy('date').rowsBetween(-window_size, 0)

        # Get columns to impute (exclude key columns and target)
        exclude_cols = {'date', 'commodity', 'region', 'close', 'is_trading_day',
                       'has_market_data', 'has_weather_data', 'has_gdelt_data'}
        impute_cols = [c for c in df.columns if c not in exclude_cols]

        # Apply imputation for each column
        for col_name in impute_cols:
            # Skip array columns (weather_data, gdelt_data) - these are aggregated later
            if col_name in ['weather_data', 'gdelt_data']:
                continue

            # Determine strategy for this column
            strategy = self._get_strategy_for_column(col_name, feature_strats, default_strat)

            # Check if date-conditional strategy applies
            date_conditional = self._get_date_conditional_strategy(col_name, date_conditional_strats)

            if date_conditional:
                # Apply different strategies before/after threshold date
                threshold_date, before_strategy, after_strategy = date_conditional
                df = self._apply_date_conditional_imputation(
                    df, col_name, threshold_date, before_strategy, after_strategy, window, window_rolling
                )
            else:
                # Apply single strategy
                df = self._apply_imputation(df, col_name, strategy, window, window_rolling)

        return df

    def _get_strategy_for_column(
        self,
        col_name: str,
        feature_strategies: Dict[str, str],
        default_strategy: str
    ) -> str:
        """Determine imputation strategy for a column, handling wildcards."""
        # Exact match
        if col_name in feature_strategies:
            return feature_strategies[col_name]

        # Wildcard match (e.g., 'gdelt_*')
        for pattern, strategy in feature_strategies.items():
            if '*' in pattern:
                prefix = pattern.replace('*', '')
                if col_name.startswith(prefix):
                    return strategy

        # Default
        return default_strategy

    def _get_date_conditional_strategy(
        self,
        col_name: str,
        date_conditional_strategies: Dict[str, Dict]
    ) -> Optional[tuple]:
        """
        Get date-conditional strategy if applicable.

        Returns:
            (threshold_date, before_strategy, after_strategy) or None
        """
        # Exact match
        if col_name in date_conditional_strategies:
            config = date_conditional_strategies[col_name]
            threshold = config['before'][0]
            before_strat = config['before'][1]
            after_strat = config['after'][1]
            return (threshold, before_strat, after_strat)

        # Wildcard match
        for pattern, config in date_conditional_strategies.items():
            if '*' in pattern:
                prefix = pattern.replace('*', '')
                if col_name.startswith(prefix):
                    threshold = config['before'][0]
                    before_strat = config['before'][1]
                    after_strat = config['after'][1]
                    return (threshold, before_strat, after_strat)

        return None

    def _apply_date_conditional_imputation(
        self,
        df: DataFrame,
        col_name: str,
        threshold_date: str,
        before_strategy: str,
        after_strategy: str,
        window: Window,
        window_rolling: Window
    ) -> DataFrame:
        """Apply different imputation strategies before/after a threshold date."""
        # Create temporary columns for before/after periods
        temp_before = f"__{col_name}_before"
        temp_after = f"__{col_name}_after"

        # Apply before strategy
        df_before = df.withColumn(
            temp_before,
            when(col(col_name).isNull() & (col('date') < lit(threshold_date)),
                 self._get_imputed_value(col_name, before_strategy, window, window_rolling))
            .otherwise(col(col_name))
        )

        # Apply after strategy
        df_after = df_before.withColumn(
            temp_after,
            when(col(temp_before).isNull() & (col('date') >= lit(threshold_date)),
                 self._get_imputed_value(col_name, after_strategy, window, window_rolling))
            .otherwise(col(temp_before))
        )

        # Replace original column
        df_final = df_after.withColumn(col_name, col(temp_after)).drop(temp_before, temp_after)

        return df_final

    def _apply_imputation(
        self,
        df: DataFrame,
        col_name: str,
        strategy: str,
        window: Window,
        window_rolling: Window
    ) -> DataFrame:
        """Apply imputation strategy to a column."""
        if strategy == 'keep_null':
            # No transformation
            return df

        imputed_value = self._get_imputed_value(col_name, strategy, window, window_rolling)

        # Replace NULLs with imputed values
        df_imputed = df.withColumn(
            col_name,
            coalesce(col(col_name), imputed_value)
        )

        return df_imputed

    def _get_imputed_value(self, col_name: str, strategy: str, window: Window, window_rolling: Window):
        """Get the imputed value expression for a given strategy."""
        if strategy == 'forward_fill':
            # Last observed value (ignoring NULLs)
            return spark_last(col(col_name), ignorenulls=True).over(window)

        elif strategy == 'mean_7d':
            # 7-day rolling average
            return spark_avg(col(col_name)).over(window_rolling)

        elif strategy == 'zero':
            # Fill with 0
            return lit(0)

        else:
            raise ValueError(f"Unknown imputation strategy: {strategy}")

    def setDefaultStrategy(self, value: str):
        """Set default imputation strategy."""
        return self._set(default_strategy=value)

    def setFeatureStrategies(self, value: Dict[str, str]):
        """Set per-feature imputation strategies."""
        return self._set(feature_strategies=value)

    def setDateConditionalStrategies(self, value: Dict[str, Dict]):
        """Set date-conditional imputation strategies."""
        return self._set(date_conditional_strategies=value)

    def setWindowDays(self, value: int):
        """Set rolling window size in days."""
        return self._set(window_days=value)


# Convenience functions for common configurations

def get_default_imputation_config() -> Dict[str, str]:
    """
    Get default imputation configuration matching approved strategy.

    Returns:
        Dict mapping feature patterns to strategies
    """
    return {
        # Market data (OHLV)
        'open': 'forward_fill',
        'high': 'forward_fill',
        'low': 'forward_fill',
        'volume': 'forward_fill',

        # VIX
        'vix_*': 'forward_fill',

        # FX rates (24 columns)
        'eur_usd': 'mean_7d',
        'jpy_usd': 'mean_7d',
        'gbp_usd': 'mean_7d',
        'chf_usd': 'mean_7d',
        'cad_usd': 'mean_7d',
        'aud_usd': 'mean_7d',
        'nzd_usd': 'mean_7d',
        'brl_usd': 'mean_7d',
        'mxn_usd': 'mean_7d',
        'zar_usd': 'mean_7d',
        'try_usd': 'mean_7d',
        'inr_usd': 'mean_7d',
        'cny_usd': 'mean_7d',
        'krw_usd': 'mean_7d',
        'sgd_usd': 'mean_7d',
        'hkd_usd': 'mean_7d',
        'sek_usd': 'mean_7d',
        'nok_usd': 'mean_7d',
        'dkk_usd': 'mean_7d',
        'pln_usd': 'mean_7d',
        'czk_usd': 'mean_7d',
        'huf_usd': 'mean_7d',
        'rub_usd': 'mean_7d',
        'ils_usd': 'mean_7d',

        # Weather (aggregated features)
        'weather_*': 'forward_fill',

        # GDELT (handled via date-conditional below)
        'gdelt_*': 'forward_fill'  # Default for post-2021
    }


def get_gdelt_date_conditional_config() -> Dict[str, Dict]:
    """
    Get GDELT date-conditional configuration.

    GDELT data only exists post-2021, so:
    - Before 2021-01-01: Fill with 0 (data didn't exist)
    - After 2021-01-01: Fill with 0 (missing data = assume neutral news)

    Note: 0 is the neutral baseline for GDELT features:
    - avg_tone: 0 = neutral sentiment (range -10 to +10)
    - avg_goldstein_scale: 0 = neutral cooperation/conflict (range -10 to +10)
    - event_count: 0 = no events

    TODO: Consider forward_fill_decay in Month 2-3 (news relevance decays over time)

    Returns:
        Dict with date-conditional strategies
    """
    return {
        'gdelt_*': {
            'before': ('2021-01-01', 'zero'),
            'after': ('2021-01-01', 'zero')
        }
    }


def create_production_imputer() -> ImputationTransformer:
    """
    Create ImputationTransformer with production-ready configuration.

    This matches the approved imputation strategy from NULL handling collaboration:
    - OHLV: forward_fill
    - VIX: forward_fill
    - FX (24 cols): mean_7d
    - Weather: forward_fill (< 5% NULLs, weather changes gradually)
    - GDELT (all dates): zero (0 = neutral news, see TODO for decay strategy)

    Usage:
        imputer = create_production_imputer()
        df_imputed = imputer.transform(df_raw)
        df_imputed.cache()
        df_imputed.count()
    """
    return ImputationTransformer(
        default_strategy='forward_fill',
        feature_strategies=get_default_imputation_config(),
        date_conditional_strategies=get_gdelt_date_conditional_config(),
        window_days=7
    )
