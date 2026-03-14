```python
# NOTEBOOK 00: SETUP AND CONFIGURATION (UPDATED)
# ============================================================================
# Databricks notebook source
# MAGIC %md
# MAGIC # Configuration and Setup
# MAGIC Define all parameters for both commodities

# COMMAND ----------

import json
import pandas as pd
from datetime import datetime
import os
import pickle

# COMMAND ----------

# Commodity-Specific Configurations
# Each commodity has its own harvest schedule, costs, and constraints
COMMODITY_CONFIGS = {
    'coffee': {
        'commodity': 'coffee',
        'harvest_volume': 50,  # tons per year
        'harvest_windows': [(5, 9)],  # May-September (list of tuples: (start_month, end_month))
        'storage_cost_pct_per_day': 0.025,
        'transaction_cost_pct': 0.25,
        'min_inventory_to_trade': 1.0,
        'max_holding_days': 365  # 12 months from harvest start
    },
    'sugar': {
        'commodity': 'sugar',
        'harvest_volume': 50,  # tons per year (same as coffee for MVP)
        'harvest_windows': [(10, 12)],  # October-December (simplified assumption)
        'storage_cost_pct_per_day': 0.025,  # Same as coffee for MVP
        'transaction_cost_pct': 0.25,  # Same as coffee for MVP
        'min_inventory_to_trade': 1.0,
        'max_holding_days': 365  # Same constraint for MVP
    }
}

# COMMAND ----------

# Strategy Parameters (shared across commodities)
BASELINE_PARAMS = {
    'equal_batch': {
        'batch_size': 0.25,
        'frequency_days': 30
    },
    'price_threshold': {
        'threshold_pct': 0.05
        # batch_fraction added directly in strategy init: 0.33
    },
    'moving_average': {
        'ma_period': 30
        # batch_fraction added directly in strategy init: 0.50
    }
}

PREDICTION_PARAMS = {
    'consensus': {
        'consensus_threshold': 0.70,
        'min_return': 0.03,
        'evaluation_day': 14
    },
    'expected_value': {
        'min_ev_improvement': 50,  # Minimum $ improvement to defer sale
        'baseline_batch': 0.15,    # Baseline batch size (15%)
        'baseline_frequency': 10   # Days between scheduled sales
    },
    'risk_adjusted': {
        'min_return': 0.03,  # Lower from 5% to 3% (realistic for commodity markets)
        'max_uncertainty': 0.35, # Increase from 8% to 35% (matches your prediction range)
        'consensus_threshold': 0.60, # Lower from 65% to 60% (more lenient)
        'evaluation_day': 14
    }
}

# COMMAND ----------

# Data Configuration - Unity Catalog
# Source table (contains both forecasts and actuals)
FORECAST_TABLE = "commodity.forecast.distributions"

# Output schema for Delta tables
OUTPUT_SCHEMA = "commodity.trading_agent"

# Volume path for binary files (pickle, png)
VOLUME_PATH = "/Volumes/commodity/trading_agent/files"

def get_model_versions(commodity_name):
    """Get all model versions available for a commodity"""
    df = spark.table(FORECAST_TABLE) \
        .filter(f"commodity = '{commodity_name.title()}' AND is_actuals = false") \
        .select("model_version") \
        .distinct() \
        .orderBy("model_version")
    
    versions = [row.model_version for row in df.collect()]
    return versions

def load_forecast_data(commodity_name, model_version, spark):
    """Load forecast data from commodity.forecast.distributions table"""
    df = spark.table(FORECAST_TABLE) \
        .filter(f"commodity = '{commodity_name.title()}' AND is_actuals = false AND model_version = '{model_version}'")
    
    return df.toPandas()

def load_actual_prices(commodity_name, spark):
    """Load actual price data from commodity.forecast.distributions table"""
    df = spark.table(FORECAST_TABLE) \
        .filter(f"commodity = '{commodity_name.title()}' AND is_actuals = true")
    
    return df.toPandas()

def check_real_prediction_exists(commodity_name, model_version=None):
    """Check if real prediction data exists in table"""
    try:
        if model_version:
            count = spark.table(FORECAST_TABLE) \
                .filter(f"commodity = '{commodity_name.title()}' AND is_actuals = false AND model_version = '{model_version}'") \
                .count()
        else:
            count = spark.table(FORECAST_TABLE) \
                .filter(f"commodity = '{commodity_name.title()}' AND is_actuals = false") \
                .count()
        return count > 0
    except Exception as e:
        print(f"Error checking predictions: {e}")
        return False

def get_data_paths(commodity_name, model_version=None):
    """Generate data paths for a specific commodity and model version"""
    # Clean model version for use in file/table names
    model_suffix = f"_{model_version.replace('.', '_')}" if model_version else ""
    
    return {
        # Delta tables in Unity Catalog
        'historical_prices': f'{OUTPUT_SCHEMA}.historical_prices_{commodity_name.lower()}',
        'predictions': f'{OUTPUT_SCHEMA}.predictions_{commodity_name.lower()}{model_suffix}',
        'prices_prepared': f'{OUTPUT_SCHEMA}.prices_prepared_{commodity_name.lower()}',
        'predictions_prepared': f'{OUTPUT_SCHEMA}.predictions_prepared_{commodity_name.lower()}{model_suffix}',
        'results': f'{OUTPUT_SCHEMA}.results_{commodity_name.lower()}{model_suffix}',
        
        # Binary files in volume
        'prediction_matrices': f'{VOLUME_PATH}/prediction_matrices_{commodity_name.lower()}{model_suffix}.pkl',
        'prediction_matrices_real': f'{VOLUME_PATH}/prediction_matrices_{commodity_name.lower()}{model_suffix}_real.pkl',
        'results_detailed': f'{VOLUME_PATH}/results_detailed_{commodity_name.lower()}{model_suffix}.pkl',
        'statistical_results': f'{VOLUME_PATH}/statistical_results_{commodity_name.lower()}{model_suffix}.pkl',
        'feature_analysis': f'{VOLUME_PATH}/feature_analysis_{commodity_name.lower()}{model_suffix}.pkl',
        'sensitivity_results': f'{VOLUME_PATH}/sensitivity_results_{commodity_name.lower()}{model_suffix}.pkl',
        
        # Images in volume
        'cumulative_returns': f'{VOLUME_PATH}/cumulative_returns_{commodity_name.lower()}{model_suffix}.png',
        'final_dashboard': f'{VOLUME_PATH}/final_dashboard_{commodity_name.lower()}{model_suffix}.png',
        
        # CSV exports in volume
        'final_summary': f'{VOLUME_PATH}/final_summary_{commodity_name.lower()}{model_suffix}.csv',
        'statistical_comparisons': f'{VOLUME_PATH}/statistical_comparisons_{commodity_name.lower()}{model_suffix}.csv',
        'bootstrap_summary': f'{VOLUME_PATH}/bootstrap_summary_{commodity_name.lower()}{model_suffix}.csv',
        'summary_stats': f'{VOLUME_PATH}/summary_stats_{commodity_name.lower()}{model_suffix}.csv'
    }

# COMMAND ----------

# Analysis Configuration
ANALYSIS_CONFIG = {
    'backtest_start_date': '2018-01-01',  # Match prediction start
    'backtest_end_date': '2025-09-24',    # Match prediction end
    'bootstrap_iterations': 1000,
    'confidence_level': 0.95,
    'random_seed': 42,
    'prediction_runs': 500,  # For synthetic generation
    'forecast_horizon': 14    # Days ahead
}

# COMMAND ----------

# Harvest Schedule Calculation Functions

def calculate_weeks_in_window(start_month, end_month):
    """
    Calculate approximate number of weeks in a harvest window.
    
    Args:
        start_month: 1-12 (January = 1)
        end_month: 1-12 (December = 12)
    
    Returns:
        int: Approximate number of weeks
    """
    if end_month >= start_month:
        months = end_month - start_month + 1
    else:
        months = (12 - start_month + 1) + end_month
    
    return int(months * 4.33)

def get_harvest_schedule(commodity_name):
    """
    Get harvest schedule for a commodity.
    
    Returns:
        dict with 'windows' (list of tuples) and 'total_weeks'
    """
    config = COMMODITY_CONFIGS[commodity_name]
    windows = config['harvest_windows']
    
    total_weeks = sum(
        calculate_weeks_in_window(start, end) 
        for start, end in windows
    )
    
    return {
        'windows': windows,
        'total_weeks': total_weeks
    }

# COMMAND ----------

# Display Configuration
print("=" * 80)
print("COMMODITY CONFIGURATIONS")
print("=" * 80)

# Typical market prices for cost calculations
typical_prices = {
    'coffee': 150,  # $/ton
    'sugar': 400    # $/ton
}

for commodity_name, config in COMMODITY_CONFIGS.items():
    print(f"\n{commodity_name.upper()}:")
    print(f"  Harvest volume: {config['harvest_volume']} tons/year")
    
    schedule = get_harvest_schedule(commodity_name)
    print(f"  Harvest windows: {schedule['windows']}")
    print(f"  Total harvest weeks: {schedule['total_weeks']}")
    print(f"  Weekly harvest rate: {config['harvest_volume'] / schedule['total_weeks']:.2f} tons/week")
    
    print(f"\n  Costs (percentage-based):")
    print(f"    Storage: {config['storage_cost_pct_per_day']}% of value per day")
    print(f"    Transaction: {config['transaction_cost_pct']}% of sale value")
    print(f"    Max holding: {config['max_holding_days']} days from harvest start")
    
    if commodity_name in typical_prices:
        typical_price = typical_prices[commodity_name]
        storage_per_day = config['harvest_volume'] * typical_price * (config['storage_cost_pct_per_day'] / 100)
        transaction_full = config['harvest_volume'] * typical_price * (config['transaction_cost_pct'] / 100)
        print(f"\n  Example at ${typical_price}/ton:")
        print(f"    Transaction cost (full harvest): ${transaction_full:,.2f}")
        print(f"    Storage per day (full harvest): ${storage_per_day:.2f}")
        print(f"    Storage per month (full harvest): ${storage_per_day * 30:,.2f}")
        print(f"    Storage for 6 months: ${storage_per_day * 180:,.2f}")
    
    # Check for real prediction data and list model versions
    print(f"\nReal Prediction Data:")
    has_real = check_real_prediction_exists(commodity_name)
    if has_real:
        model_versions = get_model_versions(commodity_name)
        print(f"  ✓ Real prediction data found in table: {FORECAST_TABLE}")
        print(f"  Model versions available: {len(model_versions)}")
        for mv in model_versions:
            print(f"    - {mv}")
    else:
        print(f"  ⓘ No real prediction data found (will use synthetic)")

print("\n" + "=" * 80)
print("STRATEGY PARAMETERS (SHARED)")
print("=" * 80)
print("\nBaseline Strategy Parameters:")
print(json.dumps(BASELINE_PARAMS, indent=2))
print("\nPrediction Strategy Parameters:")
print(json.dumps(PREDICTION_PARAMS, indent=2))

print("\n" + "=" * 80)
print("ANALYSIS CONFIGURATION")
print("=" * 80)
print(json.dumps(ANALYSIS_CONFIG, indent=2))
print(f"\nForecast table: {FORECAST_TABLE}")
print(f"Output schema: {OUTPUT_SCHEMA}")
print(f"Volume path: {VOLUME_PATH}")

print("\n" + "=" * 80)
print("COMMODITIES TO ANALYZE")
print("=" * 80)
print(f"Will run analysis for: {list(COMMODITY_CONFIGS.keys())}")

print("\n✓ Configuration complete")
```

    ================================================================================
    COMMODITY CONFIGURATIONS
    ================================================================================
    
    COFFEE:
      Harvest volume: 50 tons/year
      Harvest windows: [(5, 9)]
      Total harvest weeks: 21
      Weekly harvest rate: 2.38 tons/week
    
      Costs (percentage-based):
        Storage: 0.025% of value per day
        Transaction: 0.25% of sale value
        Max holding: 365 days from harvest start
    
      Example at $150/ton:
        Transaction cost (full harvest): $18.75
        Storage per day (full harvest): $1.88
        Storage per month (full harvest): $56.25
        Storage for 6 months: $337.50
    
    Real Prediction Data:
      ✓ Real prediction data found in table: commodity.forecast.distributions
      Model versions available: 12
        - arima_111_v1
        - arima_v1
        - naive
        - naive_baseline
        - prophet_v1
        - random_walk_baseline
        - random_walk_v1
        - random_walk_v1_test
        - sarimax_auto_weather_v1
        - sarimax_weather_v1
        - xgboost
        - xgboost_weather_v1
    
    SUGAR:
      Harvest volume: 50 tons/year
      Harvest windows: [(10, 12)]
      Total harvest weeks: 12
      Weekly harvest rate: 4.17 tons/week
    
      Costs (percentage-based):
        Storage: 0.025% of value per day
        Transaction: 0.25% of sale value
        Max holding: 365 days from harvest start
    
      Example at $400/ton:
        Transaction cost (full harvest): $50.00
        Storage per day (full harvest): $5.00
        Storage per month (full harvest): $150.00
        Storage for 6 months: $900.00
    
    Real Prediction Data:
      ✓ Real prediction data found in table: commodity.forecast.distributions
      Model versions available: 5
        - arima_111_v1
        - prophet_v1
        - random_walk_v1
        - sarimax_auto_weather_v1
        - xgboost_weather_v1
    
    ================================================================================
    STRATEGY PARAMETERS (SHARED)
    ================================================================================
    
    Baseline Strategy Parameters:
    {
      "equal_batch": {
        "batch_size": 0.25,
        "frequency_days": 30
      },
      "price_threshold": {
        "threshold_pct": 0.05
      },
      "moving_average": {
        "ma_period": 30
      }
    }
    
    Prediction Strategy Parameters:
    {
      "consensus": {
        "consensus_threshold": 0.7,
        "min_return": 0.03,
        "evaluation_day": 14
      },
      "expected_value": {
        "min_ev_improvement": 50,
        "baseline_batch": 0.15,
        "baseline_frequency": 10
      },
      "risk_adjusted": {
        "min_return": 0.03,
        "max_uncertainty": 0.35,
        "consensus_threshold": 0.6,
        "evaluation_day": 14
      }
    }
    
    ================================================================================
    ANALYSIS CONFIGURATION
    ================================================================================
    {
      "backtest_start_date": "2018-01-01",
      "backtest_end_date": "2025-09-24",
      "bootstrap_iterations": 1000,
      "confidence_level": 0.95,
      "random_seed": 42,
      "prediction_runs": 500,
      "forecast_horizon": 14
    }
    
    Forecast table: commodity.forecast.distributions
    Output schema: commodity.trading_agent
    Volume path: /Volumes/commodity/trading_agent/files
    
    ================================================================================
    COMMODITIES TO ANALYZE
    ================================================================================
    Will run analysis for: ['coffee', 'sugar']
    
    ✓ Configuration complete

