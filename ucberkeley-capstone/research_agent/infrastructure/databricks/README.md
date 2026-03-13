# Databricks Infrastructure

Databricks notebooks and scripts for data infrastructure management.

## Files

### Gold Layer

**`create_gold_fillforward.sql`** - (If exists) Legacy forward-fill logic
**`refresh_fillforward.py`** - (If exists) Refresh forward-filled tables

### Validation

**`validate_gold_unified_data.py`** - Validate commodity.gold.unified_data table
- Run this notebook after executing `research_agent/sql/create_gold_unified_data.sql`
- Checks: row counts, date ranges, array sizes, data quality, null counts
- Expected output: ~7k rows, weather arrays with 30-65 regions, GDELT arrays with 7 themes

## Usage

### Creating Gold Unified Data

1. **Execute SQL directly in Databricks SQL Editor:**
   ```sql
   -- Copy/paste from: research_agent/sql/create_gold_unified_data.sql
   -- Or upload the file and run
   ```

2. **Validate the result:**
   - Open: `validate_gold_unified_data.py`
   - Attach to cluster: "SQL Job Runner" (or any all-purpose cluster)
   - Run all cells
   - Verify checks pass

### Expected Validation Results

✅ **Row counts:**
- ~7,000 rows (vs ~75,000 in silver.unified_data)
- 90% reduction in size

✅ **Arrays:**
- Weather: 30-65 regions per row (varies by commodity)
- GDELT: 7 theme groups per row

✅ **Date coverage:**
- Continuous daily data from 2015-07-07 to present
- No gaps

✅ **Critical nulls:**
- date: 0 nulls
- commodity: 0 nulls
- close: 0 nulls
- weather_data: 0 nulls
- gdelt_themes: May have nulls (not every day has GDELT articles)

## Next Steps After Validation

Once gold.unified_data is validated, proceed to ml_lib testing:

```python
# In forecast_agent/ml_lib
from cross_validation import GoldDataLoader

# Test data loader
loader = GoldDataLoader()
df = loader.load(commodity='Coffee', start_date='2024-01-01')
df.show(5)

# Verify array structure
df.select('weather_data', 'gdelt_themes').show(1, truncate=False)
```
