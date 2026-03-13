# Gold.Unified_Data Validation Guide

**Script**: `validate_gold_unified_data.py`

**Purpose**: Comprehensive validation of the `commodity.gold.unified_data` table to ensure schema correctness, data quality, and pipeline integrity.

---

## What Gets Validated

### 1. Schema Validation
- ✅ Table exists in `commodity.gold` schema
- ✅ All expected columns are present
- ✅ Column types are correct (date, string, double, array)
- ✅ Array structures (weather_data, gdelt_themes) are properly formatted

### 2. Data Completeness
- ✅ Row count is reasonable (~7k rows for 2 commodities)
- ✅ Grain (date, commodity) is unique - no duplicates
- ✅ Both commodities (Coffee, Sugar) have data
- ✅ Date range starts at 2015-07-07 and extends to present
- ✅ No date gaps - continuous daily coverage

### 3. Null Value Checks
- ✅ No nulls in critical columns (date, close, open, vix)
- ✅ Forward-filled values have no unexpected nulls
- ✅ Exchange rate data is complete
- ✅ is_trading_day flag is never null

### 4. Array Structure Validation

#### weather_data
- ✅ Arrays are not null
- ✅ Arrays contain reasonable number of regions
- ✅ Struct fields (region, temp_max_c, precipitation_mm, etc.) are valid

#### gdelt_themes
- ✅ Arrays contain 7 theme groups (SUPPLY, LOGISTICS, TRADE, MARKET, POLICY, CORE, OTHER)
- ✅ Struct fields (theme_group, article_count, tone_avg, etc.) are valid
- ⚠️  Arrays may be null/empty for days without articles (OK - forward-filled)

### 5. Data Quality Checks
- ✅ All prices are positive
- ✅ Price ranges are reasonable (<$10,000)
- ✅ Volume values are non-negative
- ✅ Trading day percentage is ~70% (weekdays minus holidays)

### 6. Pipeline Correctness
- ✅ 90% row reduction vs silver.unified_data (region aggregation)
- ✅ Same date coverage as silver.unified_data
- ✅ Same commodities as silver.unified_data

---

## Usage

### Run Full Validation

```bash
# From project root
cd research_agent/infrastructure
python tests/validate_gold_unified_data.py
```

### Expected Output

```
================================================================================
GOLD.UNIFIED_DATA VALIDATION
================================================================================
Timestamp: 2025-12-06 12:34:56
================================================================================

1. TABLE EXISTENCE & SCHEMA VALIDATION
--------------------------------------------------------------------------------
✅ PASS: Table commodity.gold.unified_data exists
✅ PASS: Column 'date' has correct type
✅ PASS: Column 'commodity' has correct type
✅ PASS: Column 'weather_data' has correct type
...

2. ROW COUNTS & GRAIN VALIDATION
--------------------------------------------------------------------------------
Total rows: 7,142
✅ PASS: Row count is reasonable (7,142 rows for 3,571 days)
✅ PASS: Grain (date, commodity) is unique - no duplicates
...

================================================================================
VALIDATION SUMMARY
================================================================================

Total checks: 47
✅ Passed:    45
⚠️  Warnings:  2
❌ Failed:    0

🎉 ALL CHECKS PASSED! gold.unified_data is valid and ready for use.
================================================================================
```

---

## Exit Codes

- **0**: Validation passed (all checks passed or warnings only)
- **1**: Validation failed (one or more critical checks failed)

---

## When to Run

### Required
- ✅ **After creating/rebuilding gold.unified_data** - Ensure table was created correctly
- ✅ **Before training ML models** - Verify data quality before model training
- ✅ **After schema changes** - Confirm migrations didn't break anything

### Recommended
- 🔄 **Weekly** - Catch data quality degradation early
- 🔄 **After upstream changes** - When bronze/silver tables are updated
- 🔄 **Before major releases** - Final check before production deployments

---

## Common Issues & Fixes

### ❌ "Table does not exist"

**Problem**: `commodity.gold.unified_data` hasn't been created yet

**Solution**: Run the creation SQL
```bash
# In Databricks SQL Editor on unity-catalog-cluster:
# Open and run: research_agent/sql/create_gold_unified_data.sql
```

### ⚠️ "Row reduction is only 50% (expected ~90%)"

**Problem**: Weather data might not have all regions, or GDELT data is missing

**Solution**: Check upstream silver.unified_data table
```bash
python tests/validate_data_quality.py
```

### ❌ "Null close prices found"

**Problem**: Forward-fill logic failed or missing market data

**Solution**: Check bronze.market table for gaps
```bash
SELECT date, commodity, close
FROM commodity.bronze.market
WHERE close IS NULL
ORDER BY date DESC
LIMIT 10;
```

### ⚠️ "Empty weather arrays: 100 rows have no weather data"

**Problem**: Some commodities/regions don't have weather coverage

**Solution**: Verify this is expected (e.g., if a commodity doesn't have regional data)
```bash
SELECT commodity, COUNT(*) as empty_weather_rows
FROM commodity.gold.unified_data
WHERE size(weather_data) = 0
GROUP BY commodity;
```

---

## Integration with CI/CD

### In Databricks Notebooks

```python
# Run validation after creating table
%run ../tests/validate_gold_unified_data

# Script exits with code 1 on failure, stopping notebook execution
```

### In Python Scripts

```python
import subprocess

result = subprocess.run(
    ["python", "tests/validate_gold_unified_data.py"],
    cwd="research_agent/infrastructure"
)

if result.returncode != 0:
    raise Exception("❌ Gold table validation failed!")
print("✅ Gold table validation passed!")
```

---

## Related Tests

- `validate_data_quality.py` - Validates silver.unified_data (source table)
- `validate_pipeline.py` - End-to-end pipeline validation
- `check_catalog_structure.py` - Unity Catalog schema validation

---

## Schema Reference

See [research_agent/sql/create_gold_unified_data.sql](../../sql/create_gold_unified_data.sql) for:
- Full table schema definition
- Forward-fill logic
- Array aggregation approach
- Comment documentation

---

**Last Updated**: 2025-12-06
**Owner**: Research Agent Team
