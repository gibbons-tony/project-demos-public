# GDELT Databricks Migration Guide

## Overview

This guide explains the migration from the old GDELT implementation (reading JSONL directly) to the new implementation (reading Parquet from Bronze/Silver layers).

## Architecture Changes

### Old Implementation (Deprecated)
- **Landing**: `commodity.landing.gdelt_sentiment_inc`
  - Read JSONL files directly from `s3://groundtruth-capstone/landing/gdelt/filtered/*.jsonl`
  - No data transformations
  - Raw GDELT schema

- **Bronze**: `commodity.bronze.gdelt`
  - Simple copy from landing table
  - No deduplication or transformations

### New Implementation (Current)
- **Bronze**: `commodity.bronze.gdelt_bronze`
  - External table pointing to `s3://groundtruth-capstone/processed/gdelt/bronze/gdelt/`
  - Parquet format (Snappy compressed)
  - Created by `gdelt-bronze-transform` Lambda
  - Schema transformations:
    - Parsed `article_date` from GDELT timestamp
    - Split `tone` into 4 separate columns (avg, positive, negative, polarity)
    - Added `has_coffee` and `has_sugar` boolean flags
    - Filtered to commodity-relevant records

- **Silver**: `commodity.silver.gdelt_wide`
  - External table pointing to `s3://groundtruth-capstone/processed/gdelt/silver/gdelt_wide/`
  - Parquet format, partitioned by commodity
  - Created by `gdelt-silver-transform` Lambda
  - Wide-format aggregations:
    - Theme groups (SUPPLY, LOGISTICS, TRADE, MARKET, POLICY, CORE, OTHER)
    - Individual themes
    - Daily aggregated metrics (count, tone metrics per theme)

## Data Flow

```
Landing JSONL (16,647 files)
    ↓
[gdelt-bronze-transform Lambda]
    ↓
Bronze Parquet (schema transformations, commodity flags)
    ↓
[gdelt-silver-transform Lambda]
    ↓
Silver Parquet (wide-format aggregations by theme)
    ↓
Databricks External Tables
```

## Migration Steps

### 1. Drop Old Tables (if they exist)
```sql
USE CATALOG commodity;
DROP TABLE IF EXISTS commodity.landing.gdelt_sentiment_inc;
DROP TABLE IF EXISTS commodity.bronze.gdelt;
```

### 2. Create Bronze External Table
```bash
# Run from Databricks SQL Editor or notebook
%sql
-- Execute: gdelt_bronze_external_table.sql
```

This creates `commodity.bronze.gdelt_bronze` pointing to Bronze Parquet files.

### 3. Create Silver External Table
```bash
# Run from Databricks SQL Editor or notebook
%sql
-- Execute: gdelt_silver_external_table.sql
```

This creates `commodity.silver.gdelt_wide` pointing to Silver Parquet files, partitioned by commodity.

### 4. Verify Data
```sql
-- Check Bronze table
SELECT COUNT(*) FROM commodity.bronze.gdelt_bronze;

-- Check Silver table
SELECT commodity, COUNT(*) as days
FROM commodity.silver.gdelt_wide
GROUP BY commodity;
```

## Schema Comparison

### Bronze Schema
| Column | Type | Description |
|--------|------|-------------|
| article_date | DATE | Parsed from GDELT timestamp |
| source_url | STRING | Article URL |
| themes | STRING | Semicolon-separated GDELT themes |
| locations | STRING | Mentioned locations |
| all_names | STRING | All named entities |
| tone_avg | DOUBLE | Average tone (-100 to +100) |
| tone_positive | DOUBLE | Positive score |
| tone_negative | DOUBLE | Negative score |
| tone_polarity | DOUBLE | Polarity score |
| has_coffee | BOOLEAN | Coffee mention flag |
| has_sugar | BOOLEAN | Sugar mention flag |

### Silver Schema (Partial - 100+ columns)
| Column | Type | Description |
|--------|------|-------------|
| article_date | DATE | Date of articles |
| commodity | STRING | 'coffee' or 'sugar' (partition key) |
| group_SUPPLY_count | BIGINT | Article count for SUPPLY theme group |
| group_SUPPLY_tone_avg | DOUBLE | Average tone for SUPPLY articles |
| ... | ... | (Similar for each theme group) |
| theme_AGRICULTURE_count | BIGINT | Article count for AGRICULTURE theme |
| theme_AGRICULTURE_tone_avg | DOUBLE | Average tone for AGRICULTURE articles |
| ... | ... | (Similar for each individual theme) |

## Benefits of New Implementation

1. **Performance**: Parquet is columnar and compressed (much faster than JSONL)
2. **Schema Enforcement**: Proper data types and transformations
3. **Incremental Processing**: Lambda functions only process new/missing data
4. **Deduplication**: Partition overwrite prevents duplicates
5. **Feature Engineering**: Pre-computed aggregations and flags
6. **Commodity Filtering**: Bronze layer only contains coffee/sugar-relevant articles

## Maintenance

### Refreshing Tables
Tables automatically pick up new Parquet files, but you may need to refresh metadata:

```sql
-- Refresh Bronze table
REFRESH TABLE commodity.bronze.gdelt_bronze;

-- Refresh Silver partitions
REFRESH TABLE commodity.silver.gdelt_wide;
```

### Adding New Data
1. Bronze Lambda processes new JSONL files (triggered by Step Functions or manually)
2. Silver Lambda aggregates Bronze data for date range
3. Databricks tables automatically see new Parquet files after REFRESH

## Files

- `gdelt_bronze_external_table.sql` - Bronze external table definition
- `gdelt_silver_external_table.sql` - Silver external table definition
- `01_create_landing_tables.sql` - Old landing table (deprecated for GDELT)
- `02_create_bronze_views.sql` - Old bronze view (deprecated for GDELT)
