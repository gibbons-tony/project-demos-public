```python
%run "./00_setup_and_config"
```


```python
# NOTEBOOK 01A: GENERATE SYNTHETIC PREDICTIONS (MEMORY-EFFICIENT) - FIXED
# ============================================================================
# Databricks notebook source
# MAGIC %md
# MAGIC # Generate Synthetic Predictions - All Commodities (Memory-Efficient)
# MAGIC 
# MAGIC Generates synthetic predictions using chunk-based processing for Unity Catalog tables.
# MAGIC Creates multiple versions with different accuracy levels.
# MAGIC 
# MAGIC **Note**: Does NOT save prices_prepared - notebooks read directly from bronze.market

# COMMAND ----------

# MAGIC %run ./00_setup_and_config

# COMMAND ----------

import pandas as pd
import numpy as np
import os
import gc
import time
from builtins import min as builtin_min, max as builtin_max

# COMMAND ----------

# Configuration for synthetic predictions
SYNTHETIC_START_DATE = '2022-01-01'  # Only generate synthetic predictions from 2022 onward
ACCURACY_LEVELS = [0.60, 0.70, 0.80, 0.90]  # Test multiple accuracy levels

print(f"Synthetic prediction configuration:")
print(f"  Synthetic start date: {SYNTHETIC_START_DATE}")
print(f"  Accuracy levels: {ACCURACY_LEVELS}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Generate Predictions for All Commodities

# COMMAND ----------

# Load price data from bronze market table
MARKET_TABLE = "commodity.bronze.market"
print(f"\nLoading price data from {MARKET_TABLE}...")

# Get all market data (full history)
market_df = spark.table(MARKET_TABLE).toPandas()
market_df['date'] = pd.to_datetime(market_df['date'])

print(f"✓ Loaded market price data (FULL HISTORY)")
commodity_counts = market_df.groupby('commodity').size()
print(f"Available commodities:")
for commodity, count in commodity_counts.items():
    print(f"  - {commodity}: {count} rows")
print(f"\nDate range: {market_df['date'].min()} to {market_df['date'].max()}")

# COMMAND ----------

def generate_predictions_for_accuracy(prices_df, model_version, n_runs=2000, n_horizons=14,
                                     base_accuracy=0.65, noise_level=0.10, chunk_size=20):
    """
    Generate synthetic predictions for a single accuracy level.
    Returns a DataFrame with a model_version column.
    
    Parameters:
    - chunk_size: Number of dates to process per chunk (smaller = less memory per chunk)
    """
    n_dates = len(prices_df) - n_horizons
    
    # Collect chunks
    all_chunks = []
    
    # Process in small chunks to manage memory
    for chunk_start in range(0, n_dates, chunk_size):
        chunk_end = builtin_min(chunk_start + chunk_size, n_dates)
        
        # Build predictions for this chunk
        chunk_records = []
        
        for i in range(chunk_start, chunk_end):
            current_date = prices_df.loc[i, 'date']
            current_price = prices_df.loc[i, 'price']
            future_prices = prices_df.loc[i+1:i+n_horizons, 'price'].values
            
            # Generate predictions for this date (vectorized per date)
            random_components = current_price * (1 + np.random.normal(0, noise_level, (n_runs, n_horizons)))
            run_biases = np.random.normal(0, noise_level * 0.3, (n_runs, 1))
            
            future_prices_matrix = np.tile(future_prices, (n_runs, 1))
            predicted_prices_matrix = (base_accuracy * future_prices_matrix + 
                                      (1 - base_accuracy) * random_components)
            predicted_prices_matrix *= (1 + run_biases)
            
            # Append to chunk records with model_version
            for run_id in range(1, n_runs + 1):
                for day_ahead in range(1, n_horizons + 1):
                    chunk_records.append({
                        'timestamp': current_date,
                        'run_id': run_id,
                        'day_ahead': day_ahead,
                        'predicted_price': predicted_prices_matrix[run_id-1, day_ahead-1],
                        'model_version': model_version
                    })
        
        # Convert chunk to DataFrame and store
        chunk_df = pd.DataFrame(chunk_records)
        all_chunks.append(chunk_df)
        
        # Clear memory
        del chunk_records
        gc.collect()
        
        # Progress update
        if chunk_end % 100 == 0 or chunk_end == n_dates:
            print(f"    Progress: {chunk_end}/{n_dates} dates... ({len(all_chunks)} chunks collected)")
    
    # Concatenate all chunks
    final_df = pd.concat(all_chunks, ignore_index=True)
    
    # Clear memory
    del all_chunks
    gc.collect()
    
    return final_df

# COMMAND ----------

def process_single_commodity(commodity_name, prices_raw_pd, analysis_config, output_schema, accuracy_levels, synthetic_start_date):
    """
    Process a single commodity with multiple accuracy levels.
    Only generates synthetic predictions from synthetic_start_date onward.
    """
    print(f"\n{'='*80}")
    print(f"PROCESSING: {commodity_name.upper()}")
    print(f"{'='*80}")
    
    # --------------------------------------------------------------------------
    # Filter and prepare price data
    # --------------------------------------------------------------------------
    print(f"\nPreparing price data...")
    
    # Filter to commodity
    prices_full = prices_raw_pd[prices_raw_pd['commodity'].str.lower() == commodity_name.lower()].copy()
    
    # Extract date and close price
    prices_full['date'] = pd.to_datetime(prices_full['date'])
    prices_full['price'] = prices_full['close']
    prices_full = prices_full[['date', 'price']].sort_values('date').reset_index(drop=True)
    
    print(f"✓ Full price history: {len(prices_full)} days")
    print(f"  Date range: {prices_full['date'].min()} to {prices_full['date'].max()}")
    
    # --------------------------------------------------------------------------
    # Filter to synthetic_start_date+ for SYNTHETIC prediction generation
    # --------------------------------------------------------------------------
    print(f"\nFiltering to {synthetic_start_date}+ for synthetic predictions...")
    prices = prices_full[prices_full['date'] >= synthetic_start_date].copy().reset_index(drop=True)
    print(f"✓ Filtered to {len(prices)} days for synthetic generation")
    print(f"  Synthetic date range: {prices['date'].min()} to {prices['date'].max()}")
    
    # --------------------------------------------------------------------------
    # Generate predictions for all accuracy levels
    # --------------------------------------------------------------------------
    print(f"\nGenerating predictions for {len(accuracy_levels)} accuracy levels...")
    
    all_predictions = []
    
    for accuracy in accuracy_levels:
        model_version = f"synthetic_acc{int(accuracy*100)}"
        
        print(f"\n  Generating {model_version}...")
        print(f"    Accuracy: {accuracy:.0%}")
        print(f"    Runs per date: {analysis_config['prediction_runs']}")
        print(f"    Horizon: {analysis_config['forecast_horizon']} days")
        
        start_time = time.time()
        
        predictions_df = generate_predictions_for_accuracy(
            prices,
            model_version=model_version,
            n_runs=analysis_config['prediction_runs'],
            n_horizons=analysis_config['forecast_horizon'],
            base_accuracy=accuracy,
            noise_level=0.10,
            chunk_size=20
        )
        
        elapsed = time.time() - start_time
        print(f"    ✓ Generated {len(predictions_df):,} prediction rows in {elapsed:.1f}s")
        
        all_predictions.append(predictions_df)
        
        # Clear memory
        del predictions_df
        gc.collect()
    
    # --------------------------------------------------------------------------
    # Combine all accuracy levels
    # --------------------------------------------------------------------------
    print(f"\nCombining all accuracy levels...")
    
    combined_predictions = pd.concat(all_predictions, ignore_index=True)
    print(f"✓ Combined: {len(combined_predictions):,} total rows")
    
    # Clear memory
    del all_predictions
    gc.collect()
    
    # --------------------------------------------------------------------------
    # Save to Delta table
    # --------------------------------------------------------------------------
    predictions_table = f"{output_schema}.predictions_{commodity_name.lower()}"
    
    print(f"\nSaving to Delta table: {predictions_table}")
    print(f"  Total rows: {len(combined_predictions):,}")
    print(f"  Model versions: {combined_predictions['model_version'].nunique()}")
    
    # Convert to Spark and save
    predictions_spark = spark.createDataFrame(combined_predictions)
    predictions_spark.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(predictions_table)
    
    print(f"✓ Saved successfully")
    
    # Verify
    saved_count = spark.table(predictions_table).count()
    print(f"✓ Verified: {saved_count:,} rows in table")
    
    # Clear memory
    del combined_predictions
    gc.collect()
    
    print(f"\n✓ {commodity_name.upper()} COMPLETE")
    
    return {
        'commodity': commodity_name,
        'n_dates_full': len(prices_full),
        'n_dates_synthetic': len(prices),
        'n_accuracy_levels': len(accuracy_levels),
        'total_predictions': len(accuracy_levels) * (len(prices) - analysis_config['forecast_horizon']) * analysis_config['prediction_runs'] * analysis_config['forecast_horizon'],
        'table': predictions_table
    }

# COMMAND ----------

# Process all commodities with all accuracy levels
all_results = []

for commodity_name in COMMODITY_CONFIGS.keys():
    try:
        result = process_single_commodity(
            commodity_name,
            market_df,
            ANALYSIS_CONFIG,
            OUTPUT_SCHEMA,
            ACCURACY_LEVELS,
            SYNTHETIC_START_DATE
        )
        all_results.append(result)
    except Exception as e:
        print(f"\n❌ Error processing {commodity_name.upper()}: {e}")
        import traceback
        traceback.print_exc()
        print(f"   Skipping...")

# COMMAND ----------

# Summary
print("\n" + "="*80)
print("GENERATION COMPLETE - SUMMARY")
print("="*80)

if len(all_results) > 0:
    summary_df = pd.DataFrame(all_results)
    print(f"\nSuccessfully processed {len(all_results)} commodities:")
    print(summary_df.to_string(index=False))
    
    print(f"\nPrediction tables created:")
    for table in sorted(summary_df['table'].unique()):
        print(f"  - {table}")
        model_versions = spark.table(table).select("model_version").distinct().collect()
        for mv in model_versions:
            print(f"      • {mv.model_version}")
else:
    print("\n⚠️  No commodities were successfully processed")

print("\n✓ Block 01A complete")
```


```python
# NOTEBOOK 01B: DATA PREPARATION (Synthetic Predictions) - FIXED
# ============================================================================
# Databricks notebook source
# MAGIC %md
# MAGIC # Data Preparation - All Commodities (Synthetic)
# MAGIC 
# MAGIC Prepares data for all configured commodities and synthetic model versions.
# MAGIC Uses memory-efficient Spark PIVOT to handle large synthetic prediction datasets.
# MAGIC 
# MAGIC **FIXED**: Now loads prices directly from bronze.market

# COMMAND ----------

# MAGIC %run ./00_setup_and_config

# COMMAND ----------

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import pickle
from pyspark.sql.functions import to_date, col
from builtins import min as builtin_min, max as builtin_max

# COMMAND ----------

# MAGIC %md
# MAGIC ## Process All Commodities and Model Versions

# COMMAND ----------

# Loop through all commodities
for CURRENT_COMMODITY in COMMODITY_CONFIGS.keys():
    print("\n" + "=" * 80)
    print(f"PROCESSING: {CURRENT_COMMODITY.upper()}")
    print("=" * 80)
    
    # Get configuration for this commodity
    CURRENT_CONFIG = COMMODITY_CONFIGS[CURRENT_COMMODITY]
    DATA_PATHS = get_data_paths(CURRENT_COMMODITY)
    
    print(f"\nConfiguration:")
    print(f"  Harvest windows: {CURRENT_CONFIG['harvest_windows']}")
    print(f"  Annual volume: {CURRENT_CONFIG['harvest_volume']} tons")
    
    # --------------------------------------------------------------------------
    # Load Prices from Bronze Market Table
    # --------------------------------------------------------------------------
    print(f"\nLoading prices from commodity.bronze.market...")
    
    prices = spark.table('commodity.bronze.market') \
        .filter(f"commodity = '{CURRENT_COMMODITY}'") \
        .select("date", "close") \
        .toPandas()
    
    prices = prices.rename(columns={'close': 'price'})
    prices['date'] = pd.to_datetime(prices['date'])
    prices = prices.sort_values('date').reset_index(drop=True)
    
    print(f"✓ Loaded {len(prices)} days of {CURRENT_COMMODITY.upper()} price data")
    print(f"  Date range: {prices['date'].min()} to {prices['date'].max()}")
    print(f"  Price range: ${prices['price'].min():.2f} to ${prices['price'].max():.2f}")
    
    # Validation
    assert prices['date'].is_unique, "Duplicate dates found"
    assert prices['price'].isnull().sum() == 0, "Missing prices"
    assert (prices['price'] > 0).all(), "Non-positive prices"
    print("✓ Price data validated")
    
    # --------------------------------------------------------------------------
    # Calculate Harvest Information
    # --------------------------------------------------------------------------
    print(f"\nCalculating harvest schedule...")
    
    harvest_schedule = get_harvest_schedule(CURRENT_COMMODITY)
    harvest_weeks = harvest_schedule['total_weeks']
    weekly_harvest = CURRENT_CONFIG['harvest_volume'] / harvest_weeks
    
    print(f"✓ Harvest schedule:")
    print(f"  Total weeks: {harvest_weeks}")
    print(f"  Weekly harvest: {weekly_harvest:.2f} tons")
    
    # --------------------------------------------------------------------------
    # Discover synthetic model versions for this commodity
    # --------------------------------------------------------------------------
    print(f"\nDiscovering synthetic model versions...")
    
    try:
        synthetic_df = spark.table(DATA_PATHS['predictions']).select("model_version").distinct()
        model_versions = [row.model_version for row in synthetic_df.collect()]
        print(f"✓ Found {len(model_versions)} synthetic models: {model_versions}")
    except Exception as e:
        print(f"⚠️  No synthetic predictions found: {e}")
        continue
    
    # --------------------------------------------------------------------------
    # Process each synthetic model version
    # --------------------------------------------------------------------------
    for MODEL_VERSION in model_versions:
        print(f"\n{'-' * 80}")
        print(f"MODEL VERSION: {MODEL_VERSION}")
        print(f"{'-' * 80}")
        
        MODEL_DATA_PATHS = get_data_paths(CURRENT_COMMODITY, MODEL_VERSION)
        
        # ----------------------------------------------------------------------
        # Load Synthetic Predictions for this model version
        # ----------------------------------------------------------------------
        print(f"\nLoading synthetic predictions for {MODEL_VERSION}...")
        
        predictions_table = DATA_PATHS['predictions']
        
        # Load predictions for this model version
        predictions_spark = spark.table(predictions_table) \
            .filter(f"model_version = '{MODEL_VERSION}'")
        
        n_predictions = predictions_spark.count()
        print(f"✓ Loaded {n_predictions:,} prediction rows from: {predictions_table}")
        
        # ----------------------------------------------------------------------
        # Transform to Prediction Matrices using Spark PIVOT (memory-efficient)
        # ----------------------------------------------------------------------
        print(f"\nTransforming to prediction matrices...")
        
        # Pivot: timestamp × run_id → day_ahead columns
        pivot_df = predictions_spark.groupBy("timestamp", "run_id").pivot("day_ahead").agg({"predicted_price": "first"})
        
        # Rename columns to day_1, day_2, etc.
        day_cols = [str(i) for i in range(1, 15)]
        new_cols = ["timestamp", "run_id"] + [f"day_{i}" for i in range(1, 15)]
        
        for old_col, new_col in zip(pivot_df.columns, new_cols):
            pivot_df = pivot_df.withColumnRenamed(old_col, new_col)
        
        # Convert to Pandas
        predictions_pivot_pd = pivot_df.toPandas()
        predictions_pivot_pd['timestamp'] = pd.to_datetime(predictions_pivot_pd['timestamp'])
        
        print(f"✓ Transformed to pivot format: {len(predictions_pivot_pd):,} rows")
        
        # Save prepared predictions to Delta table
        pivot_spark = spark.createDataFrame(predictions_pivot_pd)
        pivot_spark.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(MODEL_DATA_PATHS['predictions_prepared'])
        print(f"✓ Saved: {MODEL_DATA_PATHS['predictions_prepared']}")
        
        # ----------------------------------------------------------------------
        # Convert to Prediction Matrices Dictionary
        # ----------------------------------------------------------------------
        print(f"\nBuilding prediction matrices...")
        
        prediction_matrices = {}
        day_cols = [f'day_{i}' for i in range(1, 15)]
        
        for timestamp, group in predictions_pivot_pd.groupby('timestamp'):
            # Each row is a run, columns are days
            matrix = group[day_cols].values
            prediction_matrices[pd.Timestamp(timestamp)] = matrix
        
        print(f"✓ Created {len(prediction_matrices)} prediction matrices")
        
        if len(prediction_matrices) > 0:
            sample_matrix = list(prediction_matrices.values())[0]
            print(f"  Matrix shape: {sample_matrix.shape[0]} runs × {sample_matrix.shape[1]} days")
        
        # ----------------------------------------------------------------------
        # Save Prediction Matrices to Pickle
        # ----------------------------------------------------------------------
        print(f"\nSaving prediction matrices...")
        
        with open(MODEL_DATA_PATHS['prediction_matrices'], 'wb') as f:
            pickle.dump(prediction_matrices, f)
        
        print(f"✓ Saved: {MODEL_DATA_PATHS['prediction_matrices']}")
        print(f"✓ {MODEL_VERSION} complete")
    
    print(f"\n{'=' * 80}")
    print(f"✓ {CURRENT_COMMODITY.upper()} COMPLETE")
    print(f"{'=' * 80}")

# COMMAND ----------

print("\n" + "=" * 80)
print("ALL COMMODITIES PROCESSED")
print("=" * 80)
print("\n✓ Block 01B complete")
```
