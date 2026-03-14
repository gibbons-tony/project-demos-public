```python
%run ./00_setup_and_config
```


```python
%run ./03_strategy_implementations

```


```python
%run ./04_backtesting_engine
```


```python
# NOTEBOOK 08: SENSITIVITY ANALYSIS (MULTI-MODEL)
# ============================================================================
# Databricks notebook source
# MAGIC %md
# MAGIC # Sensitivity Analysis - All Commodities and Model Versions
# MAGIC 
# MAGIC Tests how robust strategies are to parameter and cost changes.

# COMMAND ----------



# COMMAND ----------

import pandas as pd
import numpy as np
import pickle
import matplotlib.pyplot as plt
import seaborn as sns

# COMMAND ----------

# MAGIC %md
# MAGIC ## Sensitivity Analysis Functions

# COMMAND ----------

def run_sensitivity_consensus(prices, prediction_matrices, commodity_config):
    """Test sensitivity of Consensus strategy to parameter changes."""
    engine = BacktestEngine(prices, prediction_matrices, commodity_config)
    results = []
    
    # Test different consensus thresholds and minimum returns
    for cons_thresh in [0.60, 0.65, 0.70, 0.75, 0.80]:
        for min_ret in [0.02, 0.03, 0.04, 0.05, 0.06]:
            strategy = ConsensusStrategy(
                consensus_threshold=cons_thresh, 
                min_return=min_ret, 
                evaluation_day=ANALYSIS_CONFIG['forecast_horizon']
            )
            backtest_result = engine.run(strategy)
            metrics = calculate_metrics(backtest_result)
            results.append({
                'consensus_threshold': cons_thresh, 
                'min_return': min_ret, 
                **metrics
            })
    
    return pd.DataFrame(results)

def run_cost_sensitivity(prices, prediction_matrices, commodity_config, cost_type='transaction'):
    """Test sensitivity to transaction or storage cost changes (percentage-based)."""
    results = []
    
    for multiplier in [0.5, 0.75, 1.0, 1.5, 2.0]:
        config = commodity_config.copy()
        
        if cost_type == 'transaction':
            config['transaction_cost_pct'] = commodity_config['transaction_cost_pct'] * multiplier
        elif cost_type == 'storage':
            config['storage_cost_pct_per_day'] = commodity_config['storage_cost_pct_per_day'] * multiplier
        
        engine = BacktestEngine(prices, prediction_matrices, config)
        
        # Run prediction strategy
        pred_strategy = RiskAdjustedStrategy(**PREDICTION_PARAMS['risk_adjusted'])
        pred_result = engine.run(pred_strategy)
        pred_metrics = calculate_metrics(pred_result)
        
        # Run baseline strategy
        baseline_strategy = MovingAverageStrategy(ma_period=BASELINE_PARAMS['moving_average']['ma_period'])
        baseline_result = engine.run(baseline_strategy)
        baseline_metrics = calculate_metrics(baseline_result)
        
        results.append({
            'cost_multiplier': multiplier,
            'prediction_earnings': pred_metrics['net_earnings'],
            'baseline_earnings': baseline_metrics['net_earnings'],
            'advantage': pred_metrics['net_earnings'] - baseline_metrics['net_earnings']
        })
    
    return pd.DataFrame(results)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Run Sensitivity Analysis for All Commodities and Models

# COMMAND ----------

# Loop through all commodities
for CURRENT_COMMODITY in COMMODITY_CONFIGS.keys():
    print("\n" + "=" * 80)
    print(f"SENSITIVITY ANALYSIS: {CURRENT_COMMODITY.upper()}")
    print("=" * 80)
    
    CURRENT_CONFIG = COMMODITY_CONFIGS[CURRENT_COMMODITY]
    
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
            prices = spark.table(get_data_paths(CURRENT_COMMODITY)['prices_prepared']).toPandas()
            prices['date'] = pd.to_datetime(prices['date'])
            
            # Load prediction matrices for this model version
            if MODEL_VERSION.startswith('synthetic_'):
                matrices_path = MODEL_DATA_PATHS['prediction_matrices']
            else:
                matrices_path = MODEL_DATA_PATHS['prediction_matrices_real']
            
            with open(matrices_path, 'rb') as f:
                prediction_matrices = pickle.load(f)
            
            print(f"✓ Loaded {len(prices)} days of prices")
            print(f"✓ Loaded {len(prediction_matrices)} prediction matrices")
        
        except Exception as e:
            print(f"⚠️  Could not load data: {e}")
            continue
        
        # ----------------------------------------------------------------------
        # Consensus Strategy Parameter Sensitivity
        # ----------------------------------------------------------------------
        print(f"\nRunning Consensus strategy parameter sensitivity...")
        
        consensus_sensitivity = run_sensitivity_consensus(prices, prediction_matrices, CURRENT_CONFIG)
        
        print(f"✓ Tested {len(consensus_sensitivity)} parameter combinations")
        
        # Find optimal parameters
        best_params = consensus_sensitivity.loc[consensus_sensitivity['net_earnings'].idxmax()]
        print(f"\nOptimal parameters:")
        print(f"  Consensus threshold: {best_params['consensus_threshold']:.2f}")
        print(f"  Minimum return: {best_params['min_return']:.2%}")
        print(f"  Net earnings: ${best_params['net_earnings']:,.2f}")
        
        # ----------------------------------------------------------------------
        # Transaction Cost Sensitivity
        # ----------------------------------------------------------------------
        print(f"\nRunning transaction cost sensitivity...")
        
        transaction_sensitivity = run_cost_sensitivity(prices, prediction_matrices, CURRENT_CONFIG, cost_type='transaction')
        
        print(f"✓ Tested {len(transaction_sensitivity)} cost scenarios")
        
        # ----------------------------------------------------------------------
        # Storage Cost Sensitivity
        # ----------------------------------------------------------------------
        print(f"\nRunning storage cost sensitivity...")
        
        storage_sensitivity = run_cost_sensitivity(prices, prediction_matrices, CURRENT_CONFIG, cost_type='storage')
        
        print(f"✓ Tested {len(storage_sensitivity)} cost scenarios")
        
        # ----------------------------------------------------------------------
        # Visualizations
        # ----------------------------------------------------------------------
        print(f"\nGenerating visualizations...")
        
        # 1. Consensus parameter heatmap
        fig, ax = plt.subplots(figsize=(10, 8))
        
        pivot_data = consensus_sensitivity.pivot(
            index='min_return', 
            columns='consensus_threshold', 
            values='net_earnings'
        )
        
        sns.heatmap(pivot_data, annot=True, fmt='.0f', cmap='RdYlGn', ax=ax, 
                   cbar_kws={'label': 'Net Earnings ($)'})
        
        ax.set_title(f'Consensus Strategy Parameter Sensitivity\n{CURRENT_COMMODITY.upper()} - {MODEL_VERSION}', 
                    fontsize=14, fontweight='bold')
        ax.set_xlabel('Consensus Threshold', fontsize=12)
        ax.set_ylabel('Minimum Return', fontsize=12)
        
        plt.tight_layout()
        
        heatmap_path = f'{VOLUME_PATH}/consensus_sensitivity_{CURRENT_COMMODITY}_{MODEL_VERSION}.png'
        plt.savefig(heatmap_path, dpi=300, bbox_inches='tight')
        print(f"✓ Saved: {heatmap_path}")
        plt.close()
        
        # 2. Transaction cost sensitivity
        fig, ax = plt.subplots(figsize=(12, 6))
        
        ax.plot(transaction_sensitivity['cost_multiplier'], 
               transaction_sensitivity['prediction_earnings'], 
               marker='o', linewidth=2, label='Prediction Strategy', color='orangered')
        ax.plot(transaction_sensitivity['cost_multiplier'], 
               transaction_sensitivity['baseline_earnings'], 
               marker='s', linewidth=2, label='Baseline Strategy', color='steelblue')
        
        ax.set_xlabel('Transaction Cost Multiplier', fontsize=12)
        ax.set_ylabel('Net Earnings ($)', fontsize=12)
        ax.set_title(f'Transaction Cost Sensitivity\n{CURRENT_COMMODITY.upper()} - {MODEL_VERSION}', 
                    fontsize=14, fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.axvline(x=1.0, color='black', linestyle='--', linewidth=1, alpha=0.5, label='Baseline Cost')
        
        plt.tight_layout()
        
        trans_path = f'{VOLUME_PATH}/transaction_sensitivity_{CURRENT_COMMODITY}_{MODEL_VERSION}.png'
        plt.savefig(trans_path, dpi=300, bbox_inches='tight')
        print(f"✓ Saved: {trans_path}")
        plt.close()
        
        # 3. Storage cost sensitivity
        fig, ax = plt.subplots(figsize=(12, 6))
        
        ax.plot(storage_sensitivity['cost_multiplier'], 
               storage_sensitivity['prediction_earnings'], 
               marker='o', linewidth=2, label='Prediction Strategy', color='orangered')
        ax.plot(storage_sensitivity['cost_multiplier'], 
               storage_sensitivity['baseline_earnings'], 
               marker='s', linewidth=2, label='Baseline Strategy', color='steelblue')
        
        ax.set_xlabel('Storage Cost Multiplier', fontsize=12)
        ax.set_ylabel('Net Earnings ($)', fontsize=12)
        ax.set_title(f'Storage Cost Sensitivity\n{CURRENT_COMMODITY.upper()} - {MODEL_VERSION}', 
                    fontsize=14, fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.axvline(x=1.0, color='black', linestyle='--', linewidth=1, alpha=0.5, label='Baseline Cost')
        
        plt.tight_layout()
        
        storage_path = f'{VOLUME_PATH}/storage_sensitivity_{CURRENT_COMMODITY}_{MODEL_VERSION}.png'
        plt.savefig(storage_path, dpi=300, bbox_inches='tight')
        print(f"✓ Saved: {storage_path}")
        plt.close()
        
        # ----------------------------------------------------------------------
        # Save Results
        # ----------------------------------------------------------------------
        print(f"\nSaving results...")
        
        sensitivity_results = {
            'commodity': CURRENT_COMMODITY,
            'model_version': MODEL_VERSION,
            'consensus_sensitivity': consensus_sensitivity,
            'transaction_sensitivity': transaction_sensitivity,
            'storage_sensitivity': storage_sensitivity,
            'optimal_consensus_params': {
                'consensus_threshold': best_params['consensus_threshold'],
                'min_return': best_params['min_return'],
                'net_earnings': best_params['net_earnings']
            }
        }
        
        with open(MODEL_DATA_PATHS['sensitivity_results'], 'wb') as f:
            pickle.dump(sensitivity_results, f)
        
        print(f"✓ Saved: {MODEL_DATA_PATHS['sensitivity_results']}")
        
        # Save as CSVs
        consensus_csv = f'{VOLUME_PATH}/consensus_sensitivity_{CURRENT_COMMODITY}_{MODEL_VERSION}.csv'
        consensus_sensitivity.to_csv(consensus_csv, index=False)
        print(f"✓ Saved: {consensus_csv}")
        
        trans_csv = f'{VOLUME_PATH}/transaction_sensitivity_{CURRENT_COMMODITY}_{MODEL_VERSION}.csv'
        transaction_sensitivity.to_csv(trans_csv, index=False)
        print(f"✓ Saved: {trans_csv}")
        
        storage_csv = f'{VOLUME_PATH}/storage_sensitivity_{CURRENT_COMMODITY}_{MODEL_VERSION}.csv'
        storage_sensitivity.to_csv(storage_csv, index=False)
        print(f"✓ Saved: {storage_csv}")
        
        print(f"\n✓ Sensitivity analysis complete for {MODEL_VERSION}")
    
    print(f"\n{'=' * 80}")
    print(f"✓ {CURRENT_COMMODITY.upper()} COMPLETE")
    print(f"{'=' * 80}")

# COMMAND ----------

print("\n" + "=" * 80)
print("ALL SENSITIVITY ANALYSES COMPLETE")
print("=" * 80)
print(f"Commodities analyzed: {', '.join([c.upper() for c in COMMODITY_CONFIGS.keys()])}")
print("\n✓ Sensitivity analysis complete for all commodities and models")
```
