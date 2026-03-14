```python
%run ./00_setup_and_config

```


```python
# NOTEBOOK 07: FEATURE IMPORTANCE ANALYSIS (MULTI-MODEL)
# ============================================================================
# Databricks notebook source
# MAGIC %md
# MAGIC # Feature Importance Analysis - All Commodities and Model Versions
# MAGIC 
# MAGIC Analyzes which prediction features are most important for forecasting returns.
# MAGIC Runs for all configured commodities and model versions.

# COMMAND ----------

# MAGIC %run ./00_setup_and_config

# COMMAND ----------

import pandas as pd
import numpy as np
import pickle
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import cross_val_score
import matplotlib.pyplot as plt
import seaborn as sns

# COMMAND ----------

# MAGIC %md
# MAGIC ## Feature Extraction and Analysis

# COMMAND ----------

def extract_features(predictions, current_price, eval_day=14):
    """
    Extract features from prediction ensemble for a given evaluation day.
    
    Args:
        predictions: N×H matrix of predictions (N runs × H horizons)
        current_price: Current market price
        eval_day: Which day ahead to evaluate (1-14)
    
    Returns:
        dict of features or None if invalid
    """
    if predictions is None or len(predictions) == 0:
        return None
    
    day_preds = predictions[:, eval_day - 1]
    
    return {
        'directional_consensus': np.mean(day_preds > current_price),
        'expected_return': (np.median(day_preds) - current_price) / current_price,
        'uncertainty': (np.percentile(day_preds, 75) - np.percentile(day_preds, 25)) / np.median(day_preds),
        'skewness': float(pd.Series(day_preds).skew()),
        'prediction_range': (np.max(day_preds) - np.min(day_preds)) / current_price,
        'downside_risk': (np.percentile(day_preds, 10) - current_price) / current_price
    }

# COMMAND ----------

# Loop through all commodities
for CURRENT_COMMODITY in COMMODITY_CONFIGS.keys():
    print("\n" + "=" * 80)
    print(f"FEATURE IMPORTANCE ANALYSIS: {CURRENT_COMMODITY.upper()}")
    print("=" * 80)
    
    # Discover all model versions for this commodity
    print(f"\nDiscovering model versions...")
    
    synthetic_versions = []
    try:
        DATA_PATHS = get_data_paths(CURRENT_COMMODITY)
        synthetic_df = spark.table(DATA_PATHS['predictions']).select("model_version").distinct()
        synthetic_versions = [row.model_version for row in synthetic_df.collect()]
    except:
        pass
    
    real_versions = []
    try:
        real_versions = get_model_versions(CURRENT_COMMODITY)
    except:
        pass
    
    all_model_versions = list(set(synthetic_versions + real_versions))
    
    if len(all_model_versions) == 0:
        print(f"⚠️  No model versions found for {CURRENT_COMMODITY}")
        continue
    
    print(f"✓ Found {len(all_model_versions)} model versions")
    
    # Loop through each model version
    for MODEL_VERSION in all_model_versions:
        print(f"\n{'-' * 80}")
        print(f"MODEL: {MODEL_VERSION}")
        print(f"{'-' * 80}")
        
        MODEL_DATA_PATHS = get_data_paths(CURRENT_COMMODITY, MODEL_VERSION)
        
        # ----------------------------------------------------------------------
        # Load Data
        # ----------------------------------------------------------------------
        print(f"\nLoading prepared data...")
        
        try:
            # Load FULL price history from bronze market table
            prices = spark.table('commodity.bronze.market') \
                .filter(f"commodity = '{CURRENT_COMMODITY}'") \
                .select("date", "close") \
                .toPandas()
            
            prices = prices.rename(columns={'close': 'price'})
            prices['date'] = pd.to_datetime(prices['date']).dt.normalize()
            prices = prices.sort_values('date').reset_index(drop=True)
            
            # Load prediction matrices for this model version
            if MODEL_VERSION.startswith('synthetic_'):
                matrices_path = MODEL_DATA_PATHS['prediction_matrices']
            else:
                matrices_path = MODEL_DATA_PATHS['prediction_matrices_real']
            
            with open(matrices_path, 'rb') as f:
                prediction_matrices = pickle.load(f)
            
            # Normalize prediction matrix keys
            prediction_matrices = {
                pd.Timestamp(k).normalize(): v 
                for k, v in prediction_matrices.items()
            }
            
            print(f"✓ Loaded {len(prices)} days of prices")
            print(f"  Date range: {prices['date'].min()} to {prices['date'].max()}")
            print(f"✓ Loaded {len(prediction_matrices)} prediction matrices")
        
        except Exception as e:
            print(f"⚠️  Could not load data: {e}")
            continue
        
        # ----------------------------------------------------------------------
        # Build Feature Dataset
        # ----------------------------------------------------------------------
        print(f"\nExtracting features...")
        
        eval_day = 14
        feature_data = []
        
        # Create date-to-index mapping
        date_to_idx = {date: idx for idx, date in enumerate(prices['date'])}
        
        # Iterate over prediction matrices
        for pred_date, predictions in prediction_matrices.items():
            if pred_date not in date_to_idx:
                continue
            
            current_idx = date_to_idx[pred_date]
            
            # Need enough future data
            if current_idx + eval_day >= len(prices):
                continue
            
            current_price = prices.loc[current_idx, 'price']
            future_price = prices.loc[current_idx + eval_day, 'price']
            
            features = extract_features(predictions, current_price, eval_day)
            if features is None:
                continue
            
            actual_return = (future_price - current_price) / current_price
            
            feature_data.append({
                'date': pred_date,
                'current_price': current_price,
                'actual_return': actual_return,
                **features
            })
        
        if len(feature_data) == 0:
            print("⚠️  No features extracted")
            continue
        
        feature_df = pd.DataFrame(feature_data)
        print(f"✓ Extracted features for {len(feature_df)} days")
        
        # ----------------------------------------------------------------------
        # Train Random Forest Model
        # ----------------------------------------------------------------------
        print(f"\nTraining Random Forest model...")
        
        feature_cols = ['directional_consensus', 'expected_return', 'uncertainty', 
                       'skewness', 'prediction_range', 'downside_risk']
        
        X = feature_df[feature_cols]
        y = feature_df['actual_return']
        
        rf_model = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            n_jobs=-1
        )
        
        rf_model.fit(X, y)
        
        cv_scores = cross_val_score(rf_model, X, y, cv=5, scoring='r2')
        
        print(f"✓ Model trained")
        print(f"  R² score: {rf_model.score(X, y):.3f}")
        print(f"  CV R² score: {cv_scores.mean():.3f} (+/- {cv_scores.std():.3f})")
        
        # ----------------------------------------------------------------------
        # Feature Importance
        # ----------------------------------------------------------------------
        print(f"\nAnalyzing feature importance...")
        
        importances = rf_model.feature_importances_
        importance_df = pd.DataFrame({
            'feature': feature_cols,
            'importance': importances
        }).sort_values('importance', ascending=False)
        
        print("\nFeature Importances:")
        for _, row in importance_df.iterrows():
            print(f"  {row['feature']:25s}: {row['importance']:.3f}")
        
        # ----------------------------------------------------------------------
        # Visualization
        # ----------------------------------------------------------------------
        print(f"\nGenerating visualization...")
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        ax.barh(importance_df['feature'], importance_df['importance'], color='steelblue', alpha=0.7)
        ax.set_xlabel('Importance', fontsize=12)
        ax.set_title(f'Feature Importance - {CURRENT_COMMODITY.upper()} - {MODEL_VERSION}', 
                     fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='x')
        
        plt.tight_layout()
        
        viz_path = f'{VOLUME_PATH}/feature_importance_{CURRENT_COMMODITY}_{MODEL_VERSION}.png'
        plt.savefig(viz_path, dpi=300, bbox_inches='tight')
        print(f"✓ Saved: {viz_path}")
        plt.show()
        plt.close()
        
        # ----------------------------------------------------------------------
        # Save Results
        # ----------------------------------------------------------------------
        print(f"\nSaving results...")
        
        feature_analysis = {
            'commodity': CURRENT_COMMODITY,
            'model_version': MODEL_VERSION,
            'feature_importance': importance_df,
            'model': rf_model,
            'feature_data': feature_df,
            'cv_scores': cv_scores,
            'r2_score': rf_model.score(X, y)
        }
        
        with open(MODEL_DATA_PATHS['feature_analysis'], 'wb') as f:
            pickle.dump(feature_analysis, f)
        
        print(f"✓ Saved: {MODEL_DATA_PATHS['feature_analysis']}")
        
        importance_csv = f'{VOLUME_PATH}/feature_importance_{CURRENT_COMMODITY}_{MODEL_VERSION}.csv'
        importance_df.to_csv(importance_csv, index=False)
        print(f"✓ Saved: {importance_csv}")
        
        print(f"\n✓ Feature analysis complete for {MODEL_VERSION}")
    
    print(f"\n{'=' * 80}")
    print(f"✓ {CURRENT_COMMODITY.upper()} COMPLETE")
    print(f"{'=' * 80}")

# COMMAND ----------

print("\n" + "=" * 80)
print("ALL FEATURE IMPORTANCE ANALYSES COMPLETE")
print("=" * 80)
print(f"Commodities analyzed: {', '.join([c.upper() for c in COMMODITY_CONFIGS.keys()])}")
print("\n✓ Feature importance analysis complete for all commodities and models")
```
