# Databricks notebook source
# MAGIC %md
# MAGIC # End-to-End Forecasting Workflow Example
# MAGIC
# MAGIC **Purpose:** Demonstrate the complete two-stage forecasting workflow
# MAGIC
# MAGIC **Prerequisites:**
# MAGIC 1. `commodity.gold.unified_data` table exists (run `create_gold_unified_data.sql`)
# MAGIC 2. Validation passed (run `validate_gold_unified_data.py`)
# MAGIC
# MAGIC **Workflow:**
# MAGIC 1. **Stage 1 (Training)**: Train models with CV, save fitted pipelines
# MAGIC 2. **Stage 2 (Inference)**: Load models, generate forecasts and distributions
# MAGIC 3. **Validation**: Query results and verify
# MAGIC
# MAGIC **Expected Duration:** ~10-15 minutes for naive baseline + 1 linear model

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup

# COMMAND ----------

# Import libraries
from pyspark.sql import SparkSession
import sys
import os

# Add ml_lib to path (adjust if running locally vs Databricks)
# For Databricks repo:
ml_lib_path = "/Workspace/Repos/Project_Git/ucberkeley-capstone/forecast_agent/ml_lib"
sys.path.insert(0, ml_lib_path)

# For local development:
# sys.path.insert(0, "/path/to/forecast_agent/ml_lib")

# Verify imports work
from ml_lib.pipelines import list_models
from ml_lib.cross_validation import GoldDataLoader

print("✅ Imports successful")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Available Models

# COMMAND ----------

# List all available models from registry
list_models()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Quick Data Check

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Verify gold.unified_data exists
# MAGIC SELECT
# MAGIC     commodity,
# MAGIC     COUNT(*) as row_count,
# MAGIC     MIN(date) as min_date,
# MAGIC     MAX(date) as max_date
# MAGIC FROM commodity.gold.unified_data
# MAGIC GROUP BY commodity
# MAGIC ORDER BY commodity

# COMMAND ----------

# Test data loader
loader = GoldDataLoader(spark=spark)
df = loader.load(commodity='Coffee', start_date='2024-01-01')

print(f"Loaded {df.count():,} rows for Coffee (2024+)")
df.select('date', 'commodity', 'close', 'vix').show(5)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Stage 1: Training
# MAGIC
# MAGIC Train two models:
# MAGIC 1. **Naive Baseline** - Simple benchmark (forecast = last value)
# MAGIC 2. **Linear Weather Min/Max** - Linear regression with extreme weather features
# MAGIC
# MAGIC **CV Settings:**
# MAGIC - 5 folds
# MAGIC - Expanding window (growing training set)
# MAGIC - 14-day horizon
# MAGIC - 6 months per validation fold

# COMMAND ----------

from ml_lib.train import train_multiple_models

# Train models
results = train_multiple_models(
    spark=spark,
    commodity='Coffee',
    model_names=['naive_baseline', 'linear_weather_min_max'],
    n_folds=5,
    window_type='expanding',
    horizon=14,
    validation_months=6,
    min_train_months=24,
    save_fold_models=False  # Only save final model (not each fold)
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check Model Metadata

# COMMAND ----------

# MAGIC %sql
# MAGIC -- View trained models
# MAGIC SELECT
# MAGIC     commodity,
# MAGIC     model_name,
# MAGIC     training_date,
# MAGIC     ROUND(cv_mean_directional_accuracy, 4) as directional_accuracy,
# MAGIC     ROUND(cv_mean_mae, 2) as mae,
# MAGIC     ROUND(cv_mean_rmse, 2) as rmse,
# MAGIC     n_folds,
# MAGIC     window_type,
# MAGIC     model_path
# MAGIC FROM commodity.forecast.model_metadata
# MAGIC WHERE commodity = 'Coffee'
# MAGIC ORDER BY training_date DESC, model_name

# COMMAND ----------

# MAGIC %md
# MAGIC ## Stage 2: Inference
# MAGIC
# MAGIC Generate forecasts using the trained models:
# MAGIC 1. Load latest trained model
# MAGIC 2. Generate point forecast (14 days)
# MAGIC 3. Generate 2,000 Monte Carlo paths (block bootstrap)
# MAGIC 4. Write to `point_forecasts` and `distributions` tables

# COMMAND ----------

from ml_lib.inference import generate_multiple_forecasts

# Generate forecasts for latest date
forecast_results = generate_multiple_forecasts(
    spark=spark,
    commodity='Coffee',
    model_names=['naive_baseline', 'linear_weather_min_max'],
    forecast_date=None,  # Use latest available date
    n_paths=2000,
    block_size=3,
    seed=42  # For reproducibility
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify Point Forecasts

# COMMAND ----------

# MAGIC %sql
# MAGIC -- View latest point forecasts
# MAGIC SELECT
# MAGIC     model_name,
# MAGIC     forecast_date,
# MAGIC     forecast_horizon_date,
# MAGIC     ROUND(day_1, 2) as day_1,
# MAGIC     ROUND(day_7, 2) as day_7,
# MAGIC     ROUND(day_14, 2) as day_14,
# MAGIC     ROUND(cv_directional_accuracy, 4) as cv_da,
# MAGIC     created_at
# MAGIC FROM commodity.forecast.point_forecasts
# MAGIC WHERE commodity = 'Coffee'
# MAGIC ORDER BY created_at DESC, model_name
# MAGIC LIMIT 10

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify Monte Carlo Distributions

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Check distributions table (count paths per model)
# MAGIC SELECT
# MAGIC     model_name,
# MAGIC     forecast_date,
# MAGIC     COUNT(*) as num_paths,
# MAGIC     ROUND(AVG(day_14), 2) as avg_day_14,
# MAGIC     ROUND(STDDEV(day_14), 2) as std_day_14,
# MAGIC     ROUND(PERCENTILE(day_14, 0.10), 2) as p10_day_14,
# MAGIC     ROUND(PERCENTILE(day_14, 0.50), 2) as p50_day_14,
# MAGIC     ROUND(PERCENTILE(day_14, 0.90), 2) as p90_day_14
# MAGIC FROM commodity.forecast.distributions
# MAGIC WHERE commodity = 'Coffee'
# MAGIC GROUP BY model_name, forecast_date
# MAGIC ORDER BY forecast_date DESC, model_name

# COMMAND ----------

# MAGIC %md
# MAGIC ## Visualize Uncertainty (Sample Paths)

# COMMAND ----------

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Fetch a sample of paths for visualization
query = """
    SELECT
        model_name,
        path_id,
        day_1, day_2, day_3, day_4, day_5, day_6, day_7,
        day_8, day_9, day_10, day_11, day_12, day_13, day_14
    FROM commodity.forecast.distributions
    WHERE commodity = 'Coffee'
      AND model_name = 'linear_weather_min_max'
      AND path_id < 100  -- Sample 100 paths
    ORDER BY forecast_date DESC
    LIMIT 100
"""

paths_df = spark.sql(query).toPandas()

# Extract day columns
day_cols = [f'day_{i}' for i in range(1, 15)]
paths_matrix = paths_df[day_cols].values  # Shape: (100, 14)

# Plot
fig, ax = plt.subplots(figsize=(12, 6))

# Plot individual paths (light blue, transparent)
for i in range(paths_matrix.shape[0]):
    ax.plot(range(1, 15), paths_matrix[i], color='lightblue', alpha=0.3, linewidth=0.5)

# Plot median path (dark blue)
median_path = np.median(paths_matrix, axis=0)
ax.plot(range(1, 15), median_path, color='darkblue', linewidth=2, label='Median')

# Plot 10th and 90th percentiles (dashed)
p10 = np.percentile(paths_matrix, 10, axis=0)
p90 = np.percentile(paths_matrix, 90, axis=0)
ax.plot(range(1, 15), p10, color='red', linestyle='--', linewidth=1.5, label='10th Percentile')
ax.plot(range(1, 15), p90, color='red', linestyle='--', linewidth=1.5, label='90th Percentile')

ax.set_xlabel('Forecast Day')
ax.set_ylabel('Price (USD)')
ax.set_title('Monte Carlo Forecast Uncertainty (100 sample paths)')
ax.legend()
ax.grid(True, alpha=0.3)

plt.tight_layout()
display(fig)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary Statistics

# COMMAND ----------

# Print summary
print("=" * 80)
print("END-TO-END WORKFLOW SUMMARY")
print("=" * 80)

print("\n📊 Training Results:")
for result in results:
    da = result['cv_metrics']['mean_directional_accuracy']
    mae = result['cv_metrics']['mean_mae']
    print(f"  {result['model_name']:<30} DA: {da:.4f}  MAE: {mae:.2f}")

print("\n🔮 Forecast Results:")
for result in forecast_results:
    day_14 = result['point_forecast']['day_14']
    p10 = result['uncertainty']['day_14_p10']
    p90 = result['uncertainty']['day_14_p90']
    print(f"  {result['model_name']:<30} Day 14: {day_14:.2f} [{p10:.2f}, {p90:.2f}]")

print("\n✅ Workflow Complete!")
print("=" * 80)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Expected Results
# MAGIC
# MAGIC **Training (Stage 1):**
# MAGIC - Naive baseline: ~0.50 directional accuracy (random)
# MAGIC - Linear weather min/max: 0.52-0.55 directional accuracy (slight improvement)
# MAGIC - Models saved to: `dbfs:/commodity/models/Coffee/<model_name>/<date>/final`
# MAGIC - Residuals saved to: `dbfs:/commodity/residuals/Coffee/<model_name>/<date>`
# MAGIC
# MAGIC **Inference (Stage 2):**
# MAGIC - Point forecasts written to `commodity.forecast.point_forecasts`
# MAGIC - 2,000 Monte Carlo paths per model in `commodity.forecast.distributions`
# MAGIC - Uncertainty band (10th-90th percentile) captures autocorrelation structure
# MAGIC
# MAGIC **Next Steps:**
# MAGIC 1. Add more sophisticated models (XGBoost, LSTM, TFT)
# MAGIC 2. Backfill historical forecasts for evaluation
# MAGIC 3. Integrate with trading_agent for signal generation
# MAGIC 4. Monitor forecast accuracy over time

# COMMAND ----------

# MAGIC %md
# MAGIC ## Cleanup (Optional)

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Drop test results (uncomment to run)
# MAGIC -- DELETE FROM commodity.forecast.model_metadata WHERE commodity = 'Coffee';
# MAGIC -- DELETE FROM commodity.forecast.point_forecasts WHERE commodity = 'Coffee';
# MAGIC -- DELETE FROM commodity.forecast.distributions WHERE commodity = 'Coffee';

# COMMAND ----------


