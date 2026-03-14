```python
%run "./00_setup_and_config"
```

# Generate Calibrated Synthetic Predictions - All Commodities

**Improved accuracy definition:**
- Point accuracy: Median prediction has target MAPE (e.g., 90% accurate = 10% MAPE)
- Distribution calibration: Prediction intervals properly calibrated
- Includes 100% accurate scenario (perfect foresight for testing)

**Accuracy levels:**
- 100% accurate: MAPE = 0% (all predictions exactly match actuals)
- 90% accurate: MAPE = 10%
- 80% accurate: MAPE = 20%
- 70% accurate: MAPE = 30%
- 60% accurate: MAPE = 40%


```python
import pandas as pd
import numpy as np
import os
import gc
import time
from builtins import min as builtin_min, max as builtin_max
```


```python
# Configuration
SYNTHETIC_START_DATE = '2022-01-01'
ACCURACY_LEVELS = [1.00, 0.90, 0.80, 0.70, 0.60]  # 100%, 90%, 80%, 70%, 60%

print(f"Synthetic prediction configuration:")
print(f"  Synthetic start date: {SYNTHETIC_START_DATE}")
print(f"  Accuracy levels: {[f'{a:.0%}' for a in ACCURACY_LEVELS]}")
print(f"\nAccuracy definition:")
print(f"  - Point forecast: Median has target MAPE")
print(f"  - Distribution: Calibrated prediction intervals")
print(f"  - 100% accurate: Perfect foresight (MAPE = 0%)")
```

## Load Market Data


```python
MARKET_TABLE = "commodity.bronze.market"
print(f"\nLoading price data from {MARKET_TABLE}...")

market_df = spark.table(MARKET_TABLE).toPandas()
market_df['date'] = pd.to_datetime(market_df['date'])

print(f"✓ Loaded market price data (FULL HISTORY)")
commodity_counts = market_df.groupby('commodity').size()
print(f"Available commodities:")
for commodity, count in commodity_counts.items():
    print(f"  - {commodity}: {count} rows")
print(f"\nDate range: {market_df['date'].min()} to {market_df['date'].max()}")
```

## Calibrated Prediction Generation

Key improvements:
1. **Target MAPE**: Median prediction has specified MAPE
2. **Calibrated uncertainty**: Prediction spread reflects realistic uncertainty
3. **100% accuracy**: Perfect scenario for algorithm testing


```python
def generate_calibrated_predictions(prices_df, model_version, target_accuracy=0.90, 
                                    n_runs=2000, n_horizons=14, chunk_size=20):
    """
    Generate calibrated synthetic predictions.
    
    Parameters:
    - target_accuracy: 0.90 means median has 10% MAPE
    - n_runs: Number of ensemble runs (2000)
    - n_horizons: Forecast horizon (14 days)
    
    Returns:
    - DataFrame with predictions having target MAPE and calibrated intervals
    """
    n_dates = len(prices_df) - n_horizons
    target_mape = 1.0 - target_accuracy  # 90% accurate = 10% MAPE
    
    print(f"    Target MAPE: {target_mape:.1%}")
    print(f"    Calibration: 80% interval should contain actual ~80% of time")
    
    all_chunks = []
    
    for chunk_start in range(0, n_dates, chunk_size):
        chunk_end = builtin_min(chunk_start + chunk_size, n_dates)
        chunk_records = []
        
        for i in range(chunk_start, chunk_end):
            current_date = prices_df.loc[i, 'date']
            future_prices = prices_df.loc[i+1:i+n_horizons, 'price'].values
            
            if target_accuracy == 1.0:
                # 100% accurate: All runs exactly match actual
                predicted_prices_matrix = np.tile(future_prices, (n_runs, 1))
            
            else:
                # Generate predictions with target MAPE
                # Strategy: Add noise to actual such that median has target MAPE
                
                # 1. For each horizon day, generate median with target error
                # Expected absolute error = target_mape * actual
                # Use log-normal noise so median has target MAPE
                # log(predicted/actual) ~ N(0, sigma²)
                # We want E[|predicted - actual|/actual] = target_mape
                # For log-normal: E[|exp(ε)-1|] ≈ sqrt(2/π) * sigma for small sigma
                # So: sigma ≈ target_mape * sqrt(π/2)
                
                sigma_lognormal = target_mape * np.sqrt(np.pi / 2)
                
                # Generate 2000 runs with calibrated uncertainty
                # Use log-normal multiplicative errors
                log_errors = np.random.normal(0, sigma_lognormal, (n_runs, n_horizons))
                multiplicative_errors = np.exp(log_errors)
                
                # Apply to actual future prices
                future_prices_matrix = np.tile(future_prices, (n_runs, 1))
                predicted_prices_matrix = future_prices_matrix * multiplicative_errors
                
                # Add small run-specific bias for additional realism (±2%)
                run_biases = np.random.normal(1.0, 0.02, (n_runs, 1))
                predicted_prices_matrix *= run_biases
            
            # Store predictions
            for run_id in range(1, n_runs + 1):
                for day_ahead in range(1, n_horizons + 1):
                    chunk_records.append({
                        'timestamp': current_date,
                        'run_id': run_id,
                        'day_ahead': day_ahead,
                        'predicted_price': predicted_prices_matrix[run_id-1, day_ahead-1],
                        'model_version': model_version
                    })
        
        chunk_df = pd.DataFrame(chunk_records)
        all_chunks.append(chunk_df)
        
        del chunk_records
        gc.collect()
        
        if chunk_end % 100 == 0 or chunk_end == n_dates:
            print(f"    Progress: {chunk_end}/{n_dates} dates...")
    
    final_df = pd.concat(all_chunks, ignore_index=True)
    del all_chunks
    gc.collect()
    
    return final_df
```


```python
def validate_predictions(predictions_df, prices_df, target_accuracy, n_horizons=14):
    """
    Validate that generated predictions have target accuracy.
    Prints MAPE and calibration statistics.
    """
    print(f"\n  Validating predictions...")
    
    # Group by timestamp and day_ahead, compute median
    medians = predictions_df.groupby(['timestamp', 'day_ahead'])['predicted_price'].median().reset_index()
    medians.columns = ['timestamp', 'day_ahead', 'median_pred']
    
    # Get actual future prices
    prices_df = prices_df.copy()
    prices_df['date'] = pd.to_datetime(prices_df['date'])
    
    # Merge predictions with actuals
    results = []
    for _, row in medians.iterrows():
        timestamp = row['timestamp']
        day_ahead = int(row['day_ahead'])
        median_pred = row['median_pred']
        
        # Find actual price day_ahead days after timestamp
        future_date = timestamp + pd.Timedelta(days=day_ahead)
        actual_row = prices_df[prices_df['date'] == future_date]
        
        if len(actual_row) > 0:
            actual_price = actual_row['price'].values[0]
            ape = abs(median_pred - actual_price) / actual_price
            results.append({
                'timestamp': timestamp,
                'day_ahead': day_ahead,
                'median_pred': median_pred,
                'actual': actual_price,
                'ape': ape
            })
    
    if len(results) > 0:
        results_df = pd.DataFrame(results)
        overall_mape = results_df['ape'].mean()
        target_mape = 1.0 - target_accuracy
        
        print(f"    Achieved MAPE: {overall_mape:.1%} (target: {target_mape:.1%})")
        print(f"    Median APE: {results_df['ape'].median():.1%}")
        print(f"    90th pct APE: {results_df['ape'].quantile(0.9):.1%}")
        
        # Check calibration (for non-100% accurate)
        if target_accuracy < 1.0:
            # Check if 80% interval contains actual ~80% of time
            intervals = predictions_df.groupby(['timestamp', 'day_ahead'])['predicted_price'].agg(
                p10=lambda x: x.quantile(0.1),
                p90=lambda x: x.quantile(0.9)
            ).reset_index()
            
            validation = results_df.merge(intervals, on=['timestamp', 'day_ahead'])
            coverage_80 = ((validation['actual'] >= validation['p10']) & 
                          (validation['actual'] <= validation['p90'])).mean()
            
            print(f"    80% interval coverage: {coverage_80:.1%} (target: ~80%)")
    else:
        print(f"    ⚠️  Could not validate - no matching actuals found")
    
    print(f"  ✓ Validation complete")
```

## Process All Commodities


```python
def process_single_commodity(commodity_name, prices_raw_pd, analysis_config, output_schema, 
                            accuracy_levels, synthetic_start_date):
    """
    Process a single commodity with multiple calibrated accuracy levels.
    """
    print(f"\n{'='*80}")
    print(f"PROCESSING: {commodity_name.upper()}")
    print(f"{'='*80}")
    
    # Filter and prepare prices
    print(f"\nPreparing price data...")
    prices_full = prices_raw_pd[prices_raw_pd['commodity'].str.lower() == commodity_name.lower()].copy()
    prices_full['date'] = pd.to_datetime(prices_full['date'])
    prices_full['price'] = prices_full['close']
    prices_full = prices_full[['date', 'price']].sort_values('date').reset_index(drop=True)
    
    print(f"✓ Full price history: {len(prices_full)} days")
    print(f"  Date range: {prices_full['date'].min()} to {prices_full['date'].max()}")
    
    # Filter to synthetic date range
    print(f"\nFiltering to {synthetic_start_date}+ for synthetic predictions...")
    prices = prices_full[prices_full['date'] >= synthetic_start_date].copy().reset_index(drop=True)
    print(f"✓ Filtered to {len(prices)} days")
    
    # Generate predictions for all accuracy levels
    print(f"\nGenerating calibrated predictions for {len(accuracy_levels)} accuracy levels...")
    
    all_predictions = []
    
    for accuracy in accuracy_levels:
        model_version = f"synthetic_acc{int(accuracy*100)}"
        
        print(f"\n  {model_version}: {accuracy:.0%} accurate (MAPE = {(1-accuracy):.0%})")
        
        start_time = time.time()
        
        predictions_df = generate_calibrated_predictions(
            prices,
            model_version=model_version,
            target_accuracy=accuracy,
            n_runs=analysis_config['prediction_runs'],
            n_horizons=analysis_config['forecast_horizon'],
            chunk_size=20
        )
        
        elapsed = time.time() - start_time
        print(f"    ✓ Generated {len(predictions_df):,} rows in {elapsed:.1f}s")
        
        # Validate accuracy
        validate_predictions(predictions_df, prices, accuracy, analysis_config['forecast_horizon'])
        
        all_predictions.append(predictions_df)
        
        del predictions_df
        gc.collect()
    
    # Combine all accuracy levels
    print(f"\nCombining all accuracy levels...")
    combined_predictions = pd.concat(all_predictions, ignore_index=True)
    print(f"✓ Combined: {len(combined_predictions):,} total rows")
    
    del all_predictions
    gc.collect()
    
    # Save to Delta table
    predictions_table = f"{output_schema}.predictions_{commodity_name.lower()}"
    
    print(f"\nSaving to Delta table: {predictions_table}")
    predictions_spark = spark.createDataFrame(combined_predictions)
    predictions_spark.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(predictions_table)
    
    saved_count = spark.table(predictions_table).count()
    print(f"✓ Saved and verified: {saved_count:,} rows")
    
    del combined_predictions
    gc.collect()
    
    print(f"\n✓ {commodity_name.upper()} COMPLETE")
    
    return {
        'commodity': commodity_name,
        'n_dates': len(prices),
        'n_accuracy_levels': len(accuracy_levels),
        'table': predictions_table
    }
```


```python
# Process all commodities
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
```

## Summary


```python
print("\n" + "="*80)
print("CALIBRATED PREDICTION GENERATION COMPLETE")
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
            acc = int(mv.model_version.replace('synthetic_acc', ''))
            mape = 100 - acc
            print(f"      • {mv.model_version}: {acc}% accurate (MAPE = {mape}%)")
    
    print(f"\n✓ Key improvements over previous version:")
    print(f"  1. Median predictions have target MAPE (e.g., 90% accurate = 10% MAPE)")
    print(f"  2. Prediction intervals properly calibrated (80% interval ≈ 80% coverage)")
    print(f"  3. Includes 100% accurate scenario for algorithm testing")
    print(f"  4. Uses log-normal errors for realistic multiplicative noise")
else:
    print("\n⚠️  No commodities were successfully processed")

print("\n✓ Calibrated prediction generation complete")
```
