# Data Snapshots

This folder contains local snapshots of the unified data table for development and testing.

## Files

| File | Rows | Columns | Size | Description |
|------|------|---------|------|-------------|
| `unified_data_snapshot_2022_06.parquet` | 24,934 | 37 | 0.18 MB | Data through June 2022 |
| `unified_data_snapshot_all.parquet` | 75,354 | 37 | 0.46 MB | Full historical dataset |

## Schema

Source: `commodity.silver.unified_data`

Key columns:
- `date`: Trading date
- `is_trading_day`: Binary flag (1 = trading day, 0 = non-trading day)
- `commodity`: Coffee or Sugar
- `close, high, low, open, volume`: Market data
- `vix`: Volatility index
- `region`: Coffee/sugar producing region
- `temp_c, humidity_pct, precipitation_mm`: Weather data
- `*_usd`: Exchange rates (vnd_usd, cop_usd, idr_usd, etc.)

## Reproducing Snapshots from Databricks

```python
# Export sample through 2022-06
df_sample = spark.sql("""
    SELECT * FROM commodity.silver.unified_data
    WHERE date <= '2022-06-30'
""")
df_sample.coalesce(1).write \
    .mode("overwrite") \
    .option("header", "true") \
    .csv("/FileStore/exports/unified_data_snapshot_2022_06.csv")

# Export full dataset
df_full = spark.table("commodity.silver.unified_data")
df_full.coalesce(1).write \
    .mode("overwrite") \
    .option("header", "true") \
    .csv("/FileStore/exports/unified_data_snapshot_all.csv")
```

Download from Databricks:
- Navigate to **Data** → **DBFS** → **FileStore** → **exports**
- Download the CSV files
- Place in this `data/` folder

## Local Usage

```python
# Using PySpark (Databricks)
df = spark.read.parquet("data/unified_data_snapshot_all.parquet")

# Using pandas (local development)
import pandas as pd
df = pd.read_parquet("data/unified_data_snapshot_all.parquet")
```

## Notes

- CSV files are kept for reference but **not committed to git** (too large)
- Parquet files are preferred (98% smaller, faster to read)
- Snapshots should be refreshed periodically as new data arrives
- All data files are gitignored - see `.gitignore`
