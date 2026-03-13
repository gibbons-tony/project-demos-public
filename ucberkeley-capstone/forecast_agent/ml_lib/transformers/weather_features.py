"""
Weather feature transformers for unpacking weather_data arrays.

Provides aggregation strategies:
- Min/Max across all regions (captures extreme weather events)
- Mean across all regions (general conditions)
- Individual region features (expanded columns)
- Selected region features (high-importance regions only)

Key insight: Extreme weather events (frost, drought, excessive heat) harm
production more than average conditions, so min/max aggregations are often
more predictive than mean.
"""
from pyspark.ml.base import Transformer
from pyspark.ml.param.shared import HasInputCol, HasOutputCols, Param, Params, TypeConverters
from pyspark.sql import DataFrame
from pyspark.sql.functions import col, expr, avg as spark_avg, explode, element_at, filter as spark_filter
from typing import List, Optional


class WeatherAggregator(Transformer, HasInputCol):
    """
    Aggregate weather_data array into scalar features.

    Transforms ARRAY<STRUCT<region, temp_mean_c, ...>> into individual columns
    using specified aggregation strategy across all regions.

    Input schema:
        weather_data: ARRAY<STRUCT<
            region: STRING,
            temp_max_c: DOUBLE,
            temp_min_c: DOUBLE,
            temp_mean_c: DOUBLE,
            precipitation_mm: DOUBLE,
            rain_mm: DOUBLE,
            snowfall_cm: DOUBLE,
            humidity_mean_pct: DOUBLE,
            wind_speed_max_kmh: DOUBLE
        >>

    Output columns (added to DataFrame):
        Aggregation='mean':
            - weather_temp_mean_c_avg, weather_precipitation_mm_avg, ...
        Aggregation='min_max' (recommended for production forecasting):
            - weather_temp_mean_c_min, weather_temp_mean_c_max
            - weather_precipitation_mm_min, weather_precipitation_mm_max
            - Captures extreme weather events (frost, drought, excessive heat)
        Aggregation='all':
            - All of the above (mean + min + max)

    Example:
        # Capture extreme weather events (recommended)
        transformer = WeatherAggregator(
            inputCol="weather_data",
            aggregation="min_max"
        )
        df_transformed = transformer.transform(df)
    """

    aggregation = Param(
        Params._dummy(),
        "aggregation",
        "Aggregation strategy: 'mean', 'min_max', or 'all'"
    )

    def __init__(self, inputCol: str = "weather_data", aggregation: str = "min_max"):
        super(WeatherAggregator, self).__init__()
        self._setDefault(aggregation="min_max")
        self._set(inputCol=inputCol, aggregation=aggregation)

    def _transform(self, df: DataFrame) -> DataFrame:
        """
        Transform weather array into aggregate features.

        Uses aggregate() with min/max/avg functions across regions.
        """
        input_col = self.getInputCol()
        agg_type = self.getOrDefault(self.aggregation)

        # Weather fields to aggregate
        fields = [
            'temp_mean_c', 'temp_max_c', 'temp_min_c',
            'precipitation_mm', 'rain_mm', 'snowfall_cm',
            'humidity_mean_pct', 'wind_speed_max_kmh'
        ]

        if agg_type in ['mean', 'all']:
            # Mean aggregation across regions
            for field in fields:
                df = df.withColumn(
                    f"weather_{field}_avg",
                    expr(f"aggregate({input_col}, 0D, (acc, x) -> acc + x.{field}, acc -> acc / size({input_col}))")
                )

        if agg_type in ['min_max', 'all']:
            # Min/Max aggregation (captures extreme events)
            for field in fields:
                # Min across all regions
                df = df.withColumn(
                    f"weather_{field}_min",
                    expr(f"""
                        aggregate({input_col},
                                  CAST(1e308 AS DOUBLE),  -- Initialize with max double value
                                  (acc, x) -> CASE WHEN x.{field} < acc THEN x.{field} ELSE acc END)
                    """)
                )
                # Max across all regions
                df = df.withColumn(
                    f"weather_{field}_max",
                    expr(f"""
                        aggregate({input_col},
                                  CAST(-1e308 AS DOUBLE),  -- Initialize with min double value
                                  (acc, x) -> CASE WHEN x.{field} > acc THEN x.{field} ELSE acc END)
                    """)
                )

        if agg_type not in ['mean', 'min_max', 'all']:
            raise ValueError(f"Unsupported aggregation type: {agg_type}. Use 'mean', 'min_max', or 'all'")

        return df

    def setInputCol(self, value: str):
        return self._set(inputCol=value)

    def setAggregation(self, value: str):
        return self._set(aggregation=value)


class WeatherRegionExpander(Transformer, HasInputCol):
    """
    Expand weather_data array into separate columns for each region.

    Creates columns like:
    - weather_Brazil_Minas_Gerais_temp_mean_c
    - weather_Ethiopia_Sidamo_precipitation_mm
    - etc.

    This allows models to learn region-specific weather patterns.

    Use this when:
    - You want full regional granularity
    - You're using tree-based models (can handle many features)
    - You have enough data for region-specific patterns

    Warning: Creates many columns (~65 regions × 8 fields = 520 columns)

    Example:
        transformer = WeatherRegionExpander(inputCol="weather_data")
        df_expanded = transformer.transform(df)
    """

    def __init__(self, inputCol: str = "weather_data"):
        super(WeatherRegionExpander, self).__init__()
        self._set(inputCol=inputCol)

    def _transform(self, df: DataFrame) -> DataFrame:
        """Expand array into columns for each region."""
        input_col = self.getInputCol()

        # Get unique regions from first row (assumes all rows have same regions)
        first_row = df.select(input_col).first()
        if not first_row or not first_row[0]:
            raise ValueError(f"No data in {input_col} column")

        weather_array = first_row[0]
        regions = [item['region'] for item in weather_array]

        # Fields to extract
        fields = [
            'temp_mean_c', 'temp_max_c', 'temp_min_c',
            'precipitation_mm', 'rain_mm', 'snowfall_cm',
            'humidity_mean_pct', 'wind_speed_max_kmh'
        ]

        # Create column for each region × field combination
        for region in regions:
            # Sanitize region name for column name (replace spaces/special chars)
            region_clean = region.replace(' ', '_').replace('-', '_')

            for field in fields:
                col_name = f"weather_{region_clean}_{field}"

                # Extract field value for this region
                # filter() returns matching elements, element_at(1) gets first match
                df = df.withColumn(
                    col_name,
                    expr(f"element_at(filter({input_col}, x -> x.region = '{region}'), 1).{field}")
                )

        return df

    def setInputCol(self, value: str):
        return self._set(inputCol=value)


class WeatherRegionSelector(Transformer, HasInputCol):
    """
    Expand weather_data array for selected high-importance regions only.

    Use this after feature selection to expand only the most predictive regions.

    Major coffee regions by production:
    - Brazil: Minas_Gerais, Sao_Paulo, Espirito_Santo
    - Colombia: Antioquia, Huila, Tolima
    - Ethiopia: Sidamo, Yirgacheffe
    - Vietnam: Central_Highlands

    Example:
        # Focus on top 3 producing regions
        transformer = WeatherRegionSelector(
            inputCol="weather_data",
            regions=['Minas_Gerais_Brazil', 'Antioquia_Colombia', 'Central_Highlands_Vietnam']
        )
        df_selected = transformer.transform(df)
    """

    regions = Param(
        Params._dummy(),
        "regions",
        "List of region names to expand",
        typeConverter=TypeConverters.toListString
    )

    def __init__(self, inputCol: str = "weather_data", regions: Optional[List[str]] = None):
        super(WeatherRegionSelector, self).__init__()
        if regions is None:
            # Default to top coffee producing regions
            regions = [
                'Minas_Gerais_Brazil',
                'Sao_Paulo_Brazil',
                'Antioquia_Colombia',
                'Huila_Colombia',
                'Sidamo_Ethiopia',
                'Central_Highlands_Vietnam'
            ]
        self._set(inputCol=inputCol, regions=regions)

    def _transform(self, df: DataFrame) -> DataFrame:
        """Expand array into columns for selected regions only."""
        input_col = self.getInputCol()
        selected_regions = self.getOrDefault(self.regions)

        # Fields to extract
        fields = [
            'temp_mean_c', 'temp_max_c', 'temp_min_c',
            'precipitation_mm', 'rain_mm', 'snowfall_cm',
            'humidity_mean_pct', 'wind_speed_max_kmh'
        ]

        # Create columns for selected regions only
        for region in selected_regions:
            region_clean = region.replace(' ', '_').replace('-', '_')

            for field in fields:
                col_name = f"weather_{region_clean}_{field}"

                # Extract field value for this region
                df = df.withColumn(
                    col_name,
                    expr(f"element_at(filter({input_col}, x -> x.region = '{region}'), 1).{field}")
                )

        return df

    def setInputCol(self, value: str):
        return self._set(inputCol=value)

    def setRegions(self, value: List[str]):
        return self._set(regions=value)
