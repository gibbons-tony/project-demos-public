# Databricks notebook source
# MAGIC %md
# MAGIC # Forecast Agent Performance Dashboard
# MAGIC
# MAGIC **Purpose**: Monitor and evaluate forecast model performance across commodities
# MAGIC
# MAGIC **Features**:
# MAGIC - Model accuracy comparison (MAE/RMSE/MAPE)
# MAGIC - Prediction interval calibration
# MAGIC - Time series visualization of forecasts vs actuals
# MAGIC - Extensible design for adding new models and commodities
# MAGIC
# MAGIC **Last Updated**: 2025-11-01

# COMMAND ----------

# MAGIC %md
# MAGIC ## 📊 Dashboard Configuration

# COMMAND ----------

# Configuration: Add new commodities/models here
COMMODITIES = ['Coffee', 'Sugar']
MODELS = [
    'arima_111_v1',
    'sarimax_auto_weather_v1',
    'xgboost_weather_v1',
    'prophet_v1',
    'random_walk_v1'
]
HORIZONS = [1, 7, 14]  # Days ahead

# Display settings
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1️⃣ Model Performance Summary

# COMMAND ----------

# DBTITLE 1,Calculate Performance Metrics for All Commodities
def calculate_performance_metrics(commodity, horizon=7):
    """
    Calculate MAE/RMSE/MAPE for each model at given horizon.

    Extensible: Automatically includes all models in distributions table.
    """
    query = f"""
    WITH forecasts AS (
      SELECT
        model_version,
        forecast_start_date,
        AVG(day_{horizon}) as forecast_mean
      FROM commodity.forecast.distributions
      WHERE commodity = '{commodity}'
        AND is_actuals = FALSE
        AND has_data_leakage = FALSE
      GROUP BY model_version, forecast_start_date
    ),
    actuals AS (
      SELECT
        forecast_start_date,
        day_{horizon} as actual
      FROM commodity.forecast.distributions
      WHERE commodity = '{commodity}'
        AND path_id = 0
        AND is_actuals = TRUE
    )
    SELECT
      f.model_version,
      COUNT(*) as n_forecasts,
      AVG(ABS(f.forecast_mean - a.actual)) as mae,
      SQRT(AVG(POW(f.forecast_mean - a.actual, 2))) as rmse,
      AVG(ABS(f.forecast_mean - a.actual) / a.actual * 100) as mape,
      AVG(f.forecast_mean - a.actual) as bias
    FROM forecasts f
    JOIN actuals a ON f.forecast_start_date = a.forecast_start_date
    GROUP BY f.model_version
    ORDER BY mae ASC
    """
    return spark.sql(query).toPandas()

# Calculate for all commodities
performance_dfs = {}
for commodity in COMMODITIES:
    performance_dfs[commodity] = calculate_performance_metrics(commodity, horizon=7)
    display(performance_dfs[commodity])

# COMMAND ----------

# DBTITLE 1,Visualize Model Comparison
def plot_model_comparison(performance_dict):
    """
    Create interactive bar chart comparing models across commodities.

    Extensible: Automatically adapts to number of commodities/models.
    """
    fig = make_subplots(
        rows=len(performance_dict), cols=3,
        subplot_titles=[f'{commodity} - MAE' for commodity in performance_dict.keys()] +
                       [f'{commodity} - RMSE' for commodity in performance_dict.keys()] +
                       [f'{commodity} - MAPE' for commodity in performance_dict.keys()],
        specs=[[{'type': 'bar'}] * 3 for _ in range(len(performance_dict))]
    )

    for i, (commodity, df) in enumerate(performance_dict.items(), 1):
        # MAE
        fig.add_trace(
            go.Bar(x=df['model_version'], y=df['mae'], name=f'{commodity} MAE',
                   marker_color='lightblue', showlegend=False),
            row=i, col=1
        )
        # RMSE
        fig.add_trace(
            go.Bar(x=df['model_version'], y=df['rmse'], name=f'{commodity} RMSE',
                   marker_color='lightcoral', showlegend=False),
            row=i, col=2
        )
        # MAPE
        fig.add_trace(
            go.Bar(x=df['model_version'], y=df['mape'], name=f'{commodity} MAPE (%)',
                   marker_color='lightgreen', showlegend=False),
            row=i, col=3
        )

    fig.update_layout(height=300 * len(performance_dict), title_text="Model Performance Comparison (7-Day Ahead)")
    fig.update_xaxes(tickangle=45)
    return fig

fig = plot_model_comparison(performance_dfs)
fig.show()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2️⃣ Prediction Interval Calibration

# COMMAND ----------

# DBTITLE 1,Calculate Coverage for 95% Prediction Intervals
def calculate_coverage(commodity, model, percentile=95):
    """
    Check if actuals fall within prediction intervals.

    Well-calibrated models should have ~95% coverage for 95% intervals.
    """
    lower_pct = (100 - percentile) / 2 / 100
    upper_pct = 1 - lower_pct

    query = f"""
    WITH intervals AS (
      SELECT
        forecast_start_date,
        PERCENTILE(day_7, {lower_pct}) as lower_bound,
        PERCENTILE(day_7, {upper_pct}) as upper_bound
      FROM commodity.forecast.distributions
      WHERE commodity = '{commodity}'
        AND model_version = '{model}'
        AND is_actuals = FALSE
        AND has_data_leakage = FALSE
      GROUP BY forecast_start_date
    ),
    actuals AS (
      SELECT
        forecast_start_date,
        day_7 as actual
      FROM commodity.forecast.distributions
      WHERE commodity = '{commodity}'
        AND path_id = 0
        AND is_actuals = TRUE
    )
    SELECT
      COUNT(*) as total_forecasts,
      SUM(CASE WHEN a.actual BETWEEN i.lower_bound AND i.upper_bound THEN 1 ELSE 0 END) as in_interval,
      SUM(CASE WHEN a.actual BETWEEN i.lower_bound AND i.upper_bound THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as coverage_pct
    FROM intervals i
    JOIN actuals a ON i.forecast_start_date = a.forecast_start_date
    """
    return spark.sql(query).toPandas()

# Calculate coverage for all commodity/model combinations
coverage_results = []
for commodity in COMMODITIES:
    for model in MODELS:
        result = calculate_coverage(commodity, model)
        if len(result) > 0 and result['total_forecasts'].iloc[0] > 0:
            coverage_results.append({
                'commodity': commodity,
                'model': model,
                'coverage_pct': result['coverage_pct'].iloc[0],
                'total_forecasts': result['total_forecasts'].iloc[0]
            })

coverage_df = pd.DataFrame(coverage_results)
display(coverage_df)

# COMMAND ----------

# DBTITLE 1,Visualize Coverage Calibration
def plot_coverage_calibration(coverage_df, target=95):
    """
    Heatmap showing calibration quality.

    Green = well-calibrated, Red = poorly calibrated
    """
    # Pivot for heatmap
    pivot = coverage_df.pivot(index='model', columns='commodity', values='coverage_pct')

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=pivot.columns,
        y=pivot.index,
        colorscale='RdYlGn',
        zmid=target,
        text=pivot.values.round(1),
        texttemplate='%{text}%',
        textfont={"size": 12},
        colorbar=dict(title="Coverage %")
    ))

    fig.update_layout(
        title=f"Prediction Interval Calibration (Target: {target}% Coverage)",
        xaxis_title="Commodity",
        yaxis_title="Model",
        height=400
    )

    return fig

fig = plot_coverage_calibration(coverage_df)
fig.show()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3️⃣ Time Series Visualization

# COMMAND ----------

# DBTITLE 1,Forecast vs Actuals Over Time
def plot_forecast_vs_actuals(commodity, model, horizon=7, n_recent=20):
    """
    Time series plot showing forecast accuracy over time.

    Shows mean forecast, 95% interval, and actuals.
    """
    query = f"""
    WITH forecasts AS (
      SELECT
        forecast_start_date,
        AVG(day_{horizon}) as forecast_mean,
        PERCENTILE(day_{horizon}, 0.025) as lower_95,
        PERCENTILE(day_{horizon}, 0.975) as upper_95
      FROM commodity.forecast.distributions
      WHERE commodity = '{commodity}'
        AND model_version = '{model}'
        AND is_actuals = FALSE
        AND has_data_leakage = FALSE
      GROUP BY forecast_start_date
      ORDER BY forecast_start_date DESC
      LIMIT {n_recent}
    ),
    actuals AS (
      SELECT
        forecast_start_date,
        day_{horizon} as actual
      FROM commodity.forecast.distributions
      WHERE commodity = '{commodity}'
        AND path_id = 0
        AND is_actuals = TRUE
    )
    SELECT
      f.forecast_start_date,
      f.forecast_mean,
      f.lower_95,
      f.upper_95,
      a.actual
    FROM forecasts f
    LEFT JOIN actuals a ON f.forecast_start_date = a.forecast_start_date
    ORDER BY f.forecast_start_date
    """
    df = spark.sql(query).toPandas()

    fig = go.Figure()

    # Add 95% confidence interval
    fig.add_trace(go.Scatter(
        x=df['forecast_start_date'].tolist() + df['forecast_start_date'].tolist()[::-1],
        y=df['upper_95'].tolist() + df['lower_95'].tolist()[::-1],
        fill='toself',
        fillcolor='rgba(0,100,250,0.2)',
        line=dict(color='rgba(255,255,255,0)'),
        name='95% Interval',
        showlegend=True
    ))

    # Add forecast mean
    fig.add_trace(go.Scatter(
        x=df['forecast_start_date'],
        y=df['forecast_mean'],
        mode='lines+markers',
        name='Forecast Mean',
        line=dict(color='blue', width=2)
    ))

    # Add actuals
    fig.add_trace(go.Scatter(
        x=df['forecast_start_date'],
        y=df['actual'],
        mode='lines+markers',
        name='Actual',
        line=dict(color='red', width=2, dash='dot')
    ))

    fig.update_layout(
        title=f"{commodity} - {model} ({horizon}-day ahead)",
        xaxis_title="Forecast Date",
        yaxis_title="Price ($)",
        hovermode='x unified',
        height=400
    )

    return fig

# Plot for each commodity's best model
for commodity in COMMODITIES:
    best_model = performance_dfs[commodity].iloc[0]['model_version']
    fig = plot_forecast_vs_actuals(commodity, best_model)
    fig.show()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4️⃣ Multi-Horizon Performance

# COMMAND ----------

# DBTITLE 1,Error Growth by Forecast Horizon
def plot_error_by_horizon(commodity, model):
    """
    Show how forecast error increases with horizon.

    Extensible: Automatically uses HORIZONS config.
    """
    errors = []
    for horizon in HORIZONS:
        df = calculate_performance_metrics(commodity, horizon)
        model_row = df[df['model_version'] == model]
        if len(model_row) > 0:
            errors.append({
                'horizon': horizon,
                'mae': model_row['mae'].iloc[0],
                'rmse': model_row['rmse'].iloc[0],
                'mape': model_row['mape'].iloc[0]
            })

    errors_df = pd.DataFrame(errors)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=errors_df['horizon'], y=errors_df['mae'], name='MAE', mode='lines+markers'))
    fig.add_trace(go.Scatter(x=errors_df['horizon'], y=errors_df['rmse'], name='RMSE', mode='lines+markers'))

    fig.update_layout(
        title=f"{commodity} - {model}: Error Growth by Horizon",
        xaxis_title="Forecast Horizon (days)",
        yaxis_title="Error ($)",
        height=400
    )

    return fig

# Plot for each commodity's best model
for commodity in COMMODITIES:
    best_model = performance_dfs[commodity].iloc[0]['model_version']
    fig = plot_error_by_horizon(commodity, best_model)
    fig.show()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5️⃣ Model Recommendations

# COMMAND ----------

# DBTITLE 1,Generate Automated Recommendations
def generate_recommendations():
    """
    Automatically generate model selection recommendations.

    Criteria:
    - Best accuracy (lowest MAE)
    - Best calibration (coverage closest to 95%)
    - Most robust (lowest MAPE variance)
    """
    recommendations = []

    for commodity in COMMODITIES:
        perf_df = performance_dfs[commodity]
        cov_df = coverage_df[coverage_df['commodity'] == commodity]

        # Best accuracy
        best_acc = perf_df.iloc[0]

        # Best calibration
        cov_df['calib_error'] = abs(cov_df['coverage_pct'] - 95)
        best_calib = cov_df.loc[cov_df['calib_error'].idxmin()] if len(cov_df) > 0 else None

        recommendations.append({
            'commodity': commodity,
            'best_accuracy_model': best_acc['model_version'],
            'best_accuracy_mae': best_acc['mae'],
            'best_calibration_model': best_calib['model'] if best_calib is not None else 'N/A',
            'best_calibration_coverage': best_calib['coverage_pct'] if best_calib is not None else 'N/A'
        })

    return pd.DataFrame(recommendations)

recommendations = generate_recommendations()
display(recommendations)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 🔄 Adding New Models/Commodities
# MAGIC
# MAGIC **To add a new model:**
# MAGIC 1. Add model name to `MODELS` list in Config cell
# MAGIC 2. Ensure model data exists in `commodity.forecast.distributions`
# MAGIC 3. Re-run all cells
# MAGIC
# MAGIC **To add a new commodity:**
# MAGIC 1. Add commodity name to `COMMODITIES` list in Config cell
# MAGIC 2. Ensure commodity data exists in `commodity.forecast.distributions`
# MAGIC 3. Re-run all cells
# MAGIC
# MAGIC **To add new metrics:**
# MAGIC - Modify `calculate_performance_metrics()` function
# MAGIC - Add new columns to performance summary
# MAGIC
# MAGIC All visualizations will automatically update!
