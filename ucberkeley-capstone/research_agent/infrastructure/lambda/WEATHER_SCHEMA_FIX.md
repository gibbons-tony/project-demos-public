# Weather Lambda Schema Fix

## Problem
The weather Lambda function schema doesn't match the expected Databricks schema from Stuart's original implementation.

## Current Lambda Output (Historical Daily)
```python
{
    "Type": "HISTORICAL_DAILY",
    "Region": region,
    "Commodity": commodity,
    "Date": date,
    "Max_Temp_C": value,
    "Min_Temp_C": value,
    "Precipitation_mm": value,
    "Humidity_perc": value
}
```

## Expected Databricks Schema (17 fields)
Based on actual Databricks data:
```
Type, Region, Commodity, Date, Time_UTC, Temperature_C, Feels_Like_C,
Humidity_perc, Pressure_hPa, Wind_Speed_m/s, Weather_Main, Weather_Description,
Rain_mm/h, Snow_mm/h, Max_Temp_C, Min_Temp_C, Precipitation_mm
```

## Required Changes

### 1. Update Historical Daily Output (app.py lines 289-299)

**Replace:**
```python
records_all.append({
    "Type": "HISTORICAL_DAILY",
    "Region": region,
    "Commodity": commodity,
    "Date": times[i],
    "Max_Temp_C": tmax[i] if i < len(tmax) else None,
    "Min_Temp_C": tmin[i] if i < len(tmin) else None,
    "Precipitation_mm": precip[i] if i < len(precip) else None,
    "Humidity_perc": rh[i] if i < len(rh) else None,
})
```

**With:**
```python
records_all.append({
    "Type": "HISTORICAL_DAILY",
    "Region": region,
    "Commodity": commodity,
    "Date": times[i],
    "Time_UTC": None,  # Not available for historical daily
    "Temperature_C": None,  # Not available for historical daily
    "Feels_Like_C": None,  # Not available for historical daily
    "Humidity_perc": rh[i] if i < len(rh) else None,
    "Pressure_hPa": None,  # Not available for historical daily
    "Wind_Speed_m/s": None,  # Not available for historical daily
    "Weather_Main": None,  # Not available for historical daily
    "Weather_Description": None,  # Not available for historical daily
    "Rain_mm/h": None,  # Not available for historical daily
    "Snow_mm/h": None,  # Not available for historical daily
    "Max_Temp_C": tmax[i] if i < len(tmax) else None,
    "Min_Temp_C": tmin[i] if i < len(tmin) else None,
    "Precipitation_mm": precip[i] if i < len(precip) else None,
})
```

### 2. Fix Backfill Date

**Current backfill script uses**:
```bash
days_to_fetch: [3650, 0]  # ~10 years
```

**Should be**:
```bash
days_to_fetch: [3955, 0]  # From 2015-01-01 to today
```

Or better, use explicit date calculation to always backfill from 2015-01-01.

### 3. Update Databricks Landing Table SQL

Ensure `01_create_landing_tables.sql` expects the full 17-field schema:

```sql
CREATE OR REPLACE TABLE commodity.landing.weather_data_inc
USING DELTA
AS SELECT
  Type,
  Region,
  Commodity,
  CAST(Date AS DATE) as date,
  Time_UTC,
  CAST(Temperature_C AS DOUBLE) as temperature_c,
  CAST(Feels_Like_C AS DOUBLE) as feels_like_c,
  CAST(Humidity_perc AS INT) as humidity_perc,
  CAST(Pressure_hPa AS DOUBLE) as pressure_hpa,
  CAST(`Wind_Speed_m/s` AS DOUBLE) as wind_speed_ms,
  Weather_Main,
  Weather_Description,
  CAST(`Rain_mm/h` AS DOUBLE) as rain_mm_h,
  CAST(`Snow_mm/h` AS DOUBLE) as snow_mm_h,
  CAST(Max_Temp_C AS DOUBLE) as max_temp_c,
  CAST(Min_Temp_C AS DOUBLE) as min_temp_c,
  CAST(Precipitation_mm AS DOUBLE) as precipitation_mm,
  current_timestamp() as ingest_ts
FROM read_files(
  's3://groundtruth-capstone/landing/weather_data/*.csv',
  format => 'csv',
  header => true
)
WHERE date IS NOT NULL;
```

## Deployment Steps

1. **Fix Lambda function**:
   ```bash
   cd research_agent/infrastructure/lambda/functions/weather-data-fetcher/
   # Edit app.py with changes above
   ```

2. **Redeploy**:
   ```bash
   cd research_agent/infrastructure/lambda
   ./deploy_all_functions.sh
   ```

3. **Run backfill with correct date**:
   ```bash
   # Calculate days from 2015-01-01 to today
   # As of 2025-10-31: 3,955 days
   aws lambda invoke \
     --function-name weather-data-fetcher \
     --region us-west-2 \
     --payload '{"days_to_fetch": [3955, 0]}' \
     --cli-read-timeout 900 \
     /tmp/weather-backfill-response.json
   ```

4. **Update Databricks tables** (if needed):
   ```bash
   export DATABRICKS_TOKEN=<your-token>
   python research_agent/infrastructure/setup_databricks_pipeline.py
   ```

## Testing

After deployment, verify:
1. CSV files in S3 have all 17 columns
2. Databricks table has all fields populated correctly
3. Historical daily data has nulls in the right fields

## Schedule Note

- **Daily pipeline**: 3AM PST via `setup_databricks_pipeline.py`
- **Weather Lambda**: Scheduled via EventBridge at 2AM UTC

## References

- Lambda function: `research_agent/infrastructure/lambda/functions/weather-data-WeatherFetcherFunction-R0gqBD2JibqQ/app.py`
- Databricks SQL: `research_agent/infrastructure/databricks/01_create_landing_tables.sql`
- Original schema: Based on Stuart's Databricks data export
