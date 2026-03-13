# Data Flow Analysis - Optimizer Issue

**Date**: 2025-12-10
**Status**: ISSUE IDENTIFIED

## Current State

### Step 2 Outputs (EXIST):
✓ Pickle files in `/dbfs/production/files/`:
- `prediction_matrices_coffee_naive_real.pkl` (429.32 MB)
- `prediction_matrices_coffee_sarimax_auto_weather_real.pkl` (97.15 MB)
- `prediction_matrices_coffee_xgboost_real.pkl` (391.72 MB)

### Optimizer Inputs (MISSING):
❌ Database table `commodity.trading_agent.predictions_coffee`:
- Only has 5 synthetic models (acc60, acc70, acc80, acc90, acc100)
- Does NOT have real forecast models (naive, sarimax, xgboost, etc.)

## Data Flow Map

```
commodity.forecast.distributions (18.4M rows)
  ↓ (Step 2: load_forecast_predictions.py)
/dbfs/production/files/prediction_matrices_{commodity}_{model}_real.pkl
  ↓ (MISSING STEP!)
commodity.trading_agent.predictions_{commodity}
  ↓ (Step 3: run_parameter_optimization.py)
Optimized parameters
```

## The Problem

**Disconnect**: Step 2 saves to pickle files, but optimizer loads from database table.

Step 2 (`production/scripts/load_forecast_predictions.py`):
- Line 222 in config.py: `'prediction_matrices_real': f"{VOLUME_PATH}/prediction_matrices_{commodity.lower()}_{model_version}_real.pkl"`
- **Saves to**: Pickle files
- **Does NOT save to**: `commodity.trading_agent.predictions_coffee` table

Optimizer (`production/optimization/run_parameter_optimization.py`):
- Line 79: `pred_table = f"commodity.trading_agent.predictions_{commodity}"`
- **Loads from**: Database table
- **Does NOT load from**: Pickle files

## Solution Options

### Option A: Modify Optimizer to Load Pickle Files
**Pros**: Quick fix, uses existing Step 2 outputs
**Cons**: Breaks table-based architecture, pickle files are less discoverable

### Option B: Add Step to Load Pickle Files into Table ⭐ RECOMMENDED
**Pros**:
- Clean separation of concerns
- Preserves table-based architecture
- Optimizer code unchanged
- Makes data discoverable via SQL

**Cons**: Adds one more step to workflow

### Option C: Modify Step 2 to Write Directly to Table
**Pros**: Eliminates intermediate pickle files
**Cons**:
- Most invasive change to Step 2
- Step 2 already ran - would need to re-run
- May be storing pickle files for other reasons

## Recommended Fix

**Create Step 2.5**: Load pickle files → `predictions_coffee` table

Script: `production/scripts/load_pickle_to_table.py`

```python
# For each pickle file in /dbfs/production/files/:
# 1. Load prediction_matrices_{commodity}_{model}_real.pkl
# 2. Transform to long format (timestamp, run_id, day_ahead, predicted_price)
# 3. Add model_version column
# 4. Write to commodity.trading_agent.predictions_{commodity}
```

This allows:
- Use existing Step 2 outputs (no re-run needed)
- Optimizer runs unchanged
- Clean, maintainable architecture

## Files to Create

1. `production/scripts/load_pickle_to_table.py` - Transform pickle → table
2. `jobs/run_load_pickle_to_table.json` - Databricks job config
3. Update `README.md` to document Step 2.5

## Next Steps

1. Create Step 2.5 script
2. Test on one model (sarimax_auto_weather)
3. Run for all models
4. Verify predictions_coffee has real models
5. Run Step 3 (parameter optimizer)
