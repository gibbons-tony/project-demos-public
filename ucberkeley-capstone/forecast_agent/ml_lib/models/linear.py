"""
Linear regression models for commodity price forecasting.

Includes:
- Simple Linear Regression
- Ridge Regression (L2 regularization)
- LASSO (L1 regularization)
- ElasticNet (L1 + L2)
"""
from pyspark.ml.regression import LinearRegression
from pyspark.ml.feature import VectorAssembler
from pyspark.ml import Pipeline
from typing import List


def build_linear_regression_pipeline(
    feature_cols: List[str],
    target_col: str = "close",
    reg_param: float = 0.0,
    elastic_net_param: float = 0.0
) -> Pipeline:
    """
    Build a linear regression pipeline.

    Args:
        feature_cols: List of feature column names to use
        target_col: Target variable column name
        reg_param: Regularization parameter (0 = no regularization)
        elastic_net_param: ElasticNet mixing parameter (0 = L2/Ridge, 1 = L1/LASSO)

    Returns:
        PySpark ML Pipeline with VectorAssembler + LinearRegression

    Example:
        # Simple linear regression
        pipeline = build_linear_regression_pipeline(
            feature_cols=['weather_temp_mean_c_min', 'weather_temp_mean_c_max', 'gdelt_tone_avg'],
            target_col='close',
            reg_param=0.0
        )

        # Ridge regression
        pipeline = build_linear_regression_pipeline(
            feature_cols=[...],
            reg_param=0.1,
            elastic_net_param=0.0
        )

        # LASSO
        pipeline = build_linear_regression_pipeline(
            feature_cols=[...],
            reg_param=0.1,
            elastic_net_param=1.0
        )
    """
    # Assemble features into vector
    assembler = VectorAssembler(
        inputCols=feature_cols,
        outputCol="features",
        handleInvalid="skip"  # Skip rows with null/NaN values
    )

    # Linear regression
    lr = LinearRegression(
        featuresCol="features",
        labelCol=target_col,
        predictionCol="prediction",
        regParam=reg_param,
        elasticNetParam=elastic_net_param,
        maxIter=100,
        tol=1e-6
    )

    # Create pipeline
    pipeline = Pipeline(stages=[assembler, lr])

    return pipeline
