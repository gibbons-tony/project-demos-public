```python
%run "./00_setup_and_config"
```

# Generate Calibrated Synthetic Predictions - All Commodities

**v8: Fixed log-normal centering for accurate MAPE targets**
- **FIX**: Log-normal now centered at ±target_mape (not 0) to achieve target MAPE on median
- v7 fix: Saves to volume for download
- v6 fix: Day alignment corrected - 100% accurate shows 0% MAPE
- Keeps run_biases for realistic horizon correlation
- Point accuracy: Median prediction has target MAPE (aligned with forecast_agent)

**Accuracy levels:**
- 100% accurate: MAPE = 0%, MAE = 0 (all predictions exactly match actuals)
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
import pickle
from datetime import datetime
from builtins import min as builtin_min, max as builtin_max
```


```python
# Configuration
SYNTHETIC_START_DATE = '2022-01-01'
ACCURACY_LEVELS = [1.00, 0.90, 0.80, 0.70, 0.60]
VOLUME_PATH = "/Volumes/commodity/trading_agent/files"
VALIDATION_OUTPUT_FILE = f'{VOLUME_PATH}/validation_results_v8.pkl'

print(f"Synthetic prediction configuration:")
print(f"  Synthetic start date: {SYNTHETIC_START_DATE}")
print(f"  Accuracy levels: {[f'{a:.0%}' for a in ACCURACY_LEVELS]}")
print(f"  Validation output: {VALIDATION_OUTPUT_FILE}")
print(f"\n✓ v8 FIX: Log-normal centered at ±target_mape for accurate MAPE")
```

## Load Market Data


```python
MARKET_TABLE = "commodity.bronze.market"
print(f"\nLoading price data from {MARKET_TABLE}...")

market_df = spark.table(MARKET_TABLE).toPandas()
market_df['date'] = pd.to_datetime(market_df['date'])

print(f"✓ Loaded market price data")
print(f"Date range: {market_df['date'].min()} to {market_df['date'].max()}")
```

## Calibrated Prediction Generation (with future_date fix)


```python
def generate_calibrated_predictions(prices_df, model_version, target_accuracy=0.90, 
                                    n_runs=2000, n_horizons=14, chunk_size=20):
    """
    Generate calibrated synthetic predictions.
    v8: Log-normal centered at ±target_mape (not 0) to achieve target MAPE on median.
    """
    n_dates = len(prices_df) - n_horizons
    target_mape = 1.0 - target_accuracy
    
    print(f"    Target MAPE: {target_mape:.1%}")
    
    all_chunks = []
    
    for chunk_start in range(0, n_dates, chunk_size):
        chunk_end = builtin_min(chunk_start + chunk_size, n_dates)
        chunk_records = []
        
        for i in range(chunk_start, chunk_end):
            current_date = prices_df.loc[i, 'date']
            
            # Get actual future dates AND prices (row-based, not calendar-based)
            future_rows = prices_df.loc[i+1:i+n_horizons]
            future_dates = future_rows['date'].values
            future_prices = future_rows['price'].values
            
            # Ensure we have exactly n_horizons entries
            if len(future_prices) < n_horizons:
                continue
            
            if target_accuracy == 1.0:
                # 100% accurate: perfect predictions
                predicted_prices_matrix = np.tile(future_prices, (n_runs, 1))
            else:
                # v8 FIX: Center log-normal at ±target_mape for each timestamp
                # Randomly bias this timestamp's predictions up or down by target_mape
                bias_direction = np.random.choice([-1, 1])  # Randomly high or low
                target_multiplier = 1.0 + bias_direction * target_mape
                log_center = np.log(target_multiplier)
                
                # Generate log-normal errors centered at log_center (not 0!)
                sigma_lognormal = target_mape * np.sqrt(np.pi / 2)
                log_errors = np.random.normal(log_center, sigma_lognormal, (n_runs, n_horizons))
                multiplicative_errors = np.exp(log_errors)
                
                future_prices_matrix = np.tile(future_prices, (n_runs, 1))
                predicted_prices_matrix = future_prices_matrix * multiplicative_errors
                
                # Add run-specific bias for realistic correlation across horizons
                run_biases = np.random.normal(1.0, 0.02, (n_runs, 1))
                predicted_prices_matrix *= run_biases
            
            # Store predictions with actual future_date
            for run_id in range(1, n_runs + 1):
                for day_ahead in range(1, n_horizons + 1):
                    chunk_records.append({
                        'timestamp': current_date,
                        'future_date': future_dates[day_ahead-1],
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

## Validation Functions


```python
def calculate_crps(actuals: np.ndarray, forecast_paths: np.ndarray) -> list:
    """Calculate CRPS"""
    n_paths, horizon = forecast_paths.shape
    crps_values = []
    
    for t in range(horizon):
        if np.isnan(actuals[t]):
            continue
        actual = actuals[t]
        sorted_samples = np.sort(forecast_paths[:, t])
        term1 = np.mean(np.abs(sorted_samples - actual))
        n = len(sorted_samples)
        indices = np.arange(1, n + 1)
        term2 = np.sum((2 * indices - 1) * sorted_samples) / (n ** 2) - np.mean(sorted_samples)
        crps_values.append(term1 - 0.5 * term2)
    
    return crps_values


def calculate_directional_accuracy(actuals: pd.Series, forecasts: pd.Series) -> dict:
    """Calculate directional accuracy"""
    metrics = {}
    
    if len(actuals) > 1:
        actual_direction = np.sign(actuals.diff().dropna())
        forecast_direction = np.sign(forecasts.diff().dropna())
        correct_direction = (actual_direction == forecast_direction).sum()
        metrics['directional_accuracy'] = float(correct_direction / len(actual_direction) * 100)
    
    if len(actuals) > 1:
        day_0_actual = actuals.iloc[0]
        day_0_forecast = forecasts.iloc[0]
        correct_from_day0 = sum(1 for i in range(1, len(actuals)) 
                               if (actuals.iloc[i] > day_0_actual) == (forecasts.iloc[i] > day_0_forecast))
        metrics['directional_accuracy_from_day0'] = float(correct_from_day0 / (len(actuals) - 1) * 100)
    
    return metrics
```


```python
def validate_predictions(predictions_df, prices_df, commodity, model_version, target_accuracy, n_horizons=14):
    """
    Validation using stored future_date (FIXED).
    """
    print(f"\n  Validating predictions...")
    
    # Group by timestamp, day_ahead, future_date and compute median
    medians = predictions_df.groupby(['timestamp', 'day_ahead', 'future_date'])['predicted_price'].median().reset_index()
    medians.columns = ['timestamp', 'day_ahead', 'future_date', 'median_pred']
    
    prices_df = prices_df.copy()
    prices_df['date'] = pd.to_datetime(prices_df['date'])
    
    # Merge with actuals using stored future_date (FIXED)
    results = []
    for _, row in medians.iterrows():
        timestamp = row['timestamp']
        day_ahead = int(row['day_ahead'])
        future_date = pd.to_datetime(row['future_date'])
        median_pred = row['median_pred']
        
        # Use stored future_date instead of calendar calculation
        actual_row = prices_df[prices_df['date'] == future_date]
        
        if len(actual_row) > 0:
            actual_price = actual_row['price'].values[0]
            ape = abs(median_pred - actual_price) / actual_price
            ae = abs(median_pred - actual_price)
            results.append({
                'timestamp': timestamp,
                'day_ahead': day_ahead,
                'future_date': future_date,
                'median_pred': median_pred,
                'actual': actual_price,
                'ape': ape,
                'ae': ae
            })
    
    if len(results) == 0:
        print(f"    ⚠️  No matching actuals")
        return None
    
    results_df = pd.DataFrame(results)
    target_mape = 1.0 - target_accuracy
    
    # Overall metrics
    overall_mae = results_df['ae'].mean()
    overall_mape = results_df['ape'].mean()
    
    print(f"\n    Overall: MAE=${overall_mae:.2f}, MAPE={overall_mape:.1%} (target: {target_mape:.1%})")
    
    # Per-horizon
    per_horizon = results_df.groupby('day_ahead').agg({
        'ae': ['mean', 'std'], 'ape': ['mean', 'std'], 'timestamp': 'count'
    })
    per_horizon.columns = ['mae_mean', 'mae_std', 'mape_mean', 'mape_std', 'n_samples']
    
    print(f"\n    Per-Horizon:")
    for h in sorted(per_horizon.index)[:5]:  # Show first 5
        mape = per_horizon.loc[h, 'mape_mean']
        status = '✓' if mape <= target_mape * 1.15 else '⚠️'
        print(f"      Day {h:2d}: MAPE={mape:5.1%} {status}")
    
    # Directional accuracy
    timestamps = results_df['timestamp'].unique()
    dir_data = []
    for ts in timestamps:
        ts_data = results_df[results_df['timestamp'] == ts].sort_values('day_ahead')
        if len(ts_data) >= 2:
            dir_m = calculate_directional_accuracy(
                pd.Series(ts_data['actual'].values),
                pd.Series(ts_data['median_pred'].values)
            )
            dir_m['timestamp'] = ts
            dir_data.append(dir_m)
    
    dir_df = pd.DataFrame(dir_data)
    if len(dir_df) > 0:
        print(f"    Directional: {dir_df['directional_accuracy'].mean():.1f}% (day-to-day), "
              f"{dir_df['directional_accuracy_from_day0'].mean():.1f}% (from day 0)")
    
    # CRPS (sample)
    sample_ts = np.random.choice(timestamps, size=min(50, len(timestamps)), replace=False)
    crps_data = []
    for ts in sample_ts:
        ts_pred = predictions_df[predictions_df['timestamp'] == ts]
        matrix = ts_pred.pivot_table(index='run_id', columns='day_ahead', values='predicted_price').values
        actuals = results_df[results_df['timestamp'] == ts].sort_values('day_ahead')['actual'].values
        if len(actuals) == matrix.shape[1]:
            crps_vals = calculate_crps(actuals, matrix)
            if crps_vals:
                crps_data.append({'timestamp': ts, 'crps_mean': np.mean(crps_vals)})
    
    crps_df = pd.DataFrame(crps_data)
    if len(crps_df) > 0:
        print(f"    CRPS: ${crps_df['crps_mean'].mean():.2f}")
    
    # Coverage
    intervals = predictions_df.groupby(['timestamp', 'day_ahead'])['predicted_price'].agg(
        p10=lambda x: x.quantile(0.1), p90=lambda x: x.quantile(0.9)
    ).reset_index()
    val = results_df.merge(intervals, on=['timestamp', 'day_ahead'])
    cov80 = ((val['actual'] >= val['p10']) & (val['actual'] <= val['p90'])).mean()
    print(f"    Coverage 80%: {cov80:.1%}")
    print(f"  ✓ Validation complete")
    
    return {
        'commodity': commodity,
        'model_version': model_version,
        'target_accuracy': target_accuracy,
        'target_mape': target_mape,
        'overall_mae': float(overall_mae),
        'overall_mape': float(overall_mape),
        'results_df': results_df,
        'per_horizon_metrics': per_horizon,
        'directional_df': dir_df,
        'crps_df': crps_df,
        'coverage_80': float(cov80)
    }
```

## Process All Commodities


```python
def process_single_commodity(commodity_name, prices_raw_pd, analysis_config, output_schema, 
                            accuracy_levels, synthetic_start_date):
    print(f"\n{'='*80}")
    print(f"PROCESSING: {commodity_name.upper()}")
    print(f"{'='*80}")
    
    prices_full = prices_raw_pd[prices_raw_pd['commodity'].str.lower() == commodity_name.lower()].copy()
    prices_full['date'] = pd.to_datetime(prices_full['date'])
    prices_full['price'] = prices_full['close']
    prices_full = prices_full[['date', 'price']].sort_values('date').reset_index(drop=True)
    
    prices = prices_full[prices_full['date'] >= synthetic_start_date].copy().reset_index(drop=True)
    print(f"✓ {len(prices)} days of data")
    
    all_predictions = []
    validation_data = []
    
    for accuracy in accuracy_levels:
        model_version = f"synthetic_acc{int(accuracy*100)}"
        print(f"\n  {model_version}: {accuracy:.0%} accurate")
        
        predictions_df = generate_calibrated_predictions(
            prices, model_version, accuracy,
            analysis_config['prediction_runs'],
            analysis_config['forecast_horizon'], 20
        )
        print(f"    ✓ Generated {len(predictions_df):,} rows")
        
        val_data = validate_predictions(
            predictions_df, prices, commodity_name, model_version, 
            accuracy, analysis_config['forecast_horizon']
        )
        
        if val_data:
            validation_data.append(val_data)
        
        all_predictions.append(predictions_df)
        del predictions_df
        gc.collect()
    
    combined = pd.concat(all_predictions, ignore_index=True)
    del all_predictions
    gc.collect()
    
    predictions_table = f"{output_schema}.predictions_{commodity_name.lower()}"
    spark.createDataFrame(combined).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(predictions_table)
    print(f"\n✓ Saved to {predictions_table}")
    
    del combined
    gc.collect()
    
    return {'commodity': commodity_name, 'table': predictions_table, 'validation_data': validation_data}
```


```python
# Process all
all_results = []
all_validation_data = {}

for commodity_name in COMMODITY_CONFIGS.keys():
    try:
        result = process_single_commodity(
            commodity_name, market_df, ANALYSIS_CONFIG, OUTPUT_SCHEMA,
            ACCURACY_LEVELS, SYNTHETIC_START_DATE
        )
        all_results.append({'commodity': result['commodity'], 'table': result['table']})
        all_validation_data[commodity_name] = result['validation_data']
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
```

## Save Validation Data


```python
validation_output = {
    'generation_timestamp': datetime.now(),
    'config': {'synthetic_start_date': SYNTHETIC_START_DATE, 'accuracy_levels': ACCURACY_LEVELS},
    'commodities': all_validation_data,
    'summary': all_results
}

with open(VALIDATION_OUTPUT_FILE, 'wb') as f:
    pickle.dump(validation_output, f)

print(f"\n{'='*80}")
print(f"✓ Saved validation data to: {VALIDATION_OUTPUT_FILE}")
print(f"  Size: {os.path.getsize(VALIDATION_OUTPUT_FILE) / (1024*1024):.1f} MB")
print(f"\n✓ COMPLETE - 100% accurate should show 0% MAPE")
```
