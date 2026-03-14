```python
%run ./00_setup_and_config
```


```python
# NOTEBOOK 02: DATA PREPARATION (Real Predictions)
# ============================================================================
# Databricks notebook source
# MAGIC %md
# MAGIC # Data Preparation - Real Predictions from Table
# MAGIC Load real predictions from commodity.forecast.distributions

# COMMAND ----------


# COMMAND ----------

import pandas as pd
import numpy as np
import pickle

# COMMAND ----------

# MAGIC %md
# MAGIC ## Load Real Predictions from Table

# COMMAND ----------

for CURRENT_COMMODITY in COMMODITY_CONFIGS.keys():
    print(f"\n{'=' * 80}")
    print(f"PROCESSING: {CURRENT_COMMODITY.upper()}")
    print(f"{'=' * 80}")
    
    # Get configuration for this commodity
    CURRENT_CONFIG = COMMODITY_CONFIGS[CURRENT_COMMODITY]
    
    # --------------------------------------------------------------------------
    # Get Model Versions Available for This Commodity
    # --------------------------------------------------------------------------
    print(f"\nDiscovering model versions for {CURRENT_COMMODITY}...")
    
    model_versions = get_model_versions(CURRENT_COMMODITY)
    
    if len(model_versions) == 0:
        print(f"\n⓵ No forecast data found in table for {CURRENT_COMMODITY}")
        print(f"   Skipping {CURRENT_COMMODITY.upper()}")
        continue
    
    print(f"✓ Found {len(model_versions)} model versions:")
    for mv in model_versions:
        print(f"  - {mv}")
    
    # --------------------------------------------------------------------------
    # Process Each Model Version
    # --------------------------------------------------------------------------
    for MODEL_VERSION in model_versions:
        print(f"\n{'-' * 80}")
        print(f"PROCESSING MODEL VERSION: {MODEL_VERSION}")
        print(f"{'-' * 80}")
        
        # Get data paths for this model version
        DATA_PATHS = get_data_paths(CURRENT_COMMODITY, MODEL_VERSION)
        
        # ----------------------------------------------------------------------
        # Load Real Predictions from Table
        # ----------------------------------------------------------------------
        print(f"\nLoading predictions from {FORECAST_TABLE}...")
        
        try:
            # Load from table for this specific model version
            predictions_wide = load_forecast_data(CURRENT_COMMODITY, MODEL_VERSION, spark)
            print(f"✓ Loaded {len(predictions_wide):,} prediction paths")
            
            # Display structure
            print(f"\nData structure:")
            print(f"  Columns: {list(predictions_wide.columns)}")
            print(f"  Shape: {predictions_wide.shape}")
            print(f"  Date range: {predictions_wide['forecast_start_date'].min()} to {predictions_wide['forecast_start_date'].max()}")
            
        except Exception as e:
            print(f"\n❌ Error loading predictions for {CURRENT_COMMODITY.upper()} - {MODEL_VERSION}: {e}")
            print(f"   Skipping this model version")
            continue
        
        # ----------------------------------------------------------------------
        # Transform to Matrix Format
        # ----------------------------------------------------------------------
        print(f"\nTransforming to matrix format...")
        
        # Convert forecast_start_date to datetime
        predictions_wide['forecast_start_date'] = pd.to_datetime(predictions_wide['forecast_start_date']).dt.normalize()
        
        # Identify day columns (day_1 through day_14)
        day_columns = [f'day_{i}' for i in range(1, 15)]
        
        # Verify all day columns exist
        missing_cols = [col for col in day_columns if col not in predictions_wide.columns]
        if missing_cols:
            print(f"\n❌ Error: Missing day columns: {missing_cols}")
            print(f"   Skipping {MODEL_VERSION}")
            continue
        
        # Create prediction matrices dictionary
        # Structure: {timestamp: numpy_array(n_paths, 14)}
        prediction_matrices = {}
        
        for timestamp in predictions_wide['forecast_start_date'].unique():
            # Get all prediction paths for this timestamp
            day_data = predictions_wide[predictions_wide['forecast_start_date'] == timestamp]
            
            # Extract the 14-day forecast values into a matrix
            # Each row is a prediction path, each column is a day ahead
            matrix = day_data[day_columns].values
            
            # Store in dictionary with timestamp as key
            prediction_matrices[pd.Timestamp(timestamp)] = matrix
        
        print(f"✓ Created {len(prediction_matrices)} prediction matrices")
        
        # Verify structure
        if len(prediction_matrices) > 0:
            sample_timestamp = list(prediction_matrices.keys())[0]
            sample_matrix = prediction_matrices[sample_timestamp]
            print(f"  Sample matrix shape: {sample_matrix.shape}")
            print(f"  (n_paths={sample_matrix.shape[0]}, n_days={sample_matrix.shape[1]})")
        
        # ----------------------------------------------------------------------
        # Save Prediction Matrices to Volume
        # ----------------------------------------------------------------------
        matrices_path = DATA_PATHS['prediction_matrices_real']
        
        with open(matrices_path, 'wb') as f:
            pickle.dump(prediction_matrices, f)
        
        print(f"\n✓ Saved prediction matrices: {matrices_path}")
        
        print(f"\n✓ {MODEL_VERSION} complete")
    
    print(f"\n{'=' * 80}")
    print(f"✓ {CURRENT_COMMODITY.upper()} COMPLETE")
    print(f"{'=' * 80}")

print("\n✓ All commodities and model versions processed")
```
