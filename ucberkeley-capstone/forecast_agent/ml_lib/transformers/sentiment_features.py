"""
GDELT sentiment feature transformers for unpacking gdelt_themes arrays.

Provides aggregation strategies:
- Weighted average by article count
- Individual theme features (expanded columns)
"""
from pyspark.ml.base import Transformer
from pyspark.ml.param.shared import HasInputCol, Param, Params
from pyspark.sql import DataFrame
from pyspark.sql.functions import col, expr


class GdeltAggregator(Transformer, HasInputCol):
    """
    Aggregate gdelt_themes array into scalar sentiment features.

    Transforms ARRAY<STRUCT<theme_group, article_count, tone_metrics>> into
    individual columns using weighted average by article count.

    Input schema:
        gdelt_themes: ARRAY<STRUCT<
            theme_group: STRING,
            article_count: BIGINT,
            tone_avg: DOUBLE,
            tone_positive: DOUBLE,
            tone_negative: DOUBLE,
            tone_polarity: DOUBLE
        >>

    Output columns (added to DataFrame):
        - gdelt_tone_avg: DOUBLE (weighted by article_count)
        - gdelt_tone_positive: DOUBLE
        - gdelt_tone_negative: DOUBLE
        - gdelt_tone_polarity: DOUBLE
        - gdelt_total_articles: BIGINT

    Example:
        transformer = GdeltAggregator(inputCol="gdelt_themes")
        df_transformed = transformer.transform(df)
    """

    def __init__(self, inputCol: str = "gdelt_themes"):
        super(GdeltAggregator, self).__init__()
        self._set(inputCol=inputCol)

    def _transform(self, df: DataFrame) -> DataFrame:
        """
        Transform GDELT array into aggregate sentiment features.

        Uses weighted average by article_count across all theme groups.
        """
        input_col = self.getInputCol()

        # Total article count across all themes
        df = df.withColumn(
            "gdelt_total_articles",
            expr(f"aggregate({input_col}, 0L, (acc, x) -> acc + x.article_count)")
        )

        # Weighted average tone metrics
        # Formula: sum(tone * article_count) / sum(article_count)
        df = df.withColumn(
            "gdelt_tone_avg",
            expr(f"""
                aggregate({input_col}, 0D, (acc, x) -> acc + (x.tone_avg * x.article_count))
                / NULLIF(gdelt_total_articles, 0)
            """)
        )

        df = df.withColumn(
            "gdelt_tone_positive",
            expr(f"""
                aggregate({input_col}, 0D, (acc, x) -> acc + (x.tone_positive * x.article_count))
                / NULLIF(gdelt_total_articles, 0)
            """)
        )

        df = df.withColumn(
            "gdelt_tone_negative",
            expr(f"""
                aggregate({input_col}, 0D, (acc, x) -> acc + (x.tone_negative * x.article_count))
                / NULLIF(gdelt_total_articles, 0)
            """)
        )

        df = df.withColumn(
            "gdelt_tone_polarity",
            expr(f"""
                aggregate({input_col}, 0D, (acc, x) -> acc + (x.tone_polarity * x.article_count))
                / NULLIF(gdelt_total_articles, 0)
            """)
        )

        return df

    def setInputCol(self, value: str):
        return self._set(inputCol=value)


class GdeltThemeExpander(Transformer, HasInputCol):
    """
    Expand gdelt_themes array into separate columns for each theme group.

    Creates 4 columns per theme group (7 groups = 28 columns):
    - gdelt_{theme}_count
    - gdelt_{theme}_tone_avg
    - gdelt_{theme}_tone_positive
    - gdelt_{theme}_tone_polarity

    Theme groups: SUPPLY, LOGISTICS, TRADE, MARKET, POLICY, CORE, OTHER

    Use this when you want to treat each theme separately rather than aggregating.
    """

    def __init__(self, inputCol: str = "gdelt_themes"):
        super(GdeltThemeExpander, self).__init__()
        self._set(inputCol=inputCol)

    def _transform(self, df: DataFrame) -> DataFrame:
        """Expand array into columns for each theme group."""
        input_col = self.getInputCol()

        # Theme groups we expect
        themes = ['SUPPLY', 'LOGISTICS', 'TRADE', 'MARKET', 'POLICY', 'CORE', 'OTHER']

        for theme in themes:
            theme_lower = theme.lower()

            # Extract metrics for this theme using filter + element_at
            # filter(array, lambda) returns matching elements
            # element_at(array, 1) gets first element (or null if empty)
            df = df.withColumn(
                f"gdelt_{theme_lower}_count",
                expr(f"element_at(filter({input_col}, x -> x.theme_group = '{theme}'), 1).article_count")
            )
            df = df.withColumn(
                f"gdelt_{theme_lower}_tone_avg",
                expr(f"element_at(filter({input_col}, x -> x.theme_group = '{theme}'), 1).tone_avg")
            )
            df = df.withColumn(
                f"gdelt_{theme_lower}_tone_positive",
                expr(f"element_at(filter({input_col}, x -> x.theme_group = '{theme}'), 1).tone_positive")
            )
            df = df.withColumn(
                f"gdelt_{theme_lower}_tone_polarity",
                expr(f"element_at(filter({input_col}, x -> x.theme_group = '{theme}'), 1).tone_polarity")
            )

        return df

    def setInputCol(self, value: str):
        return self._set(inputCol=value)
