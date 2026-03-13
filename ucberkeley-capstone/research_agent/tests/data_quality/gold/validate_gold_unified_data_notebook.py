# Databricks notebook source
# MAGIC %md
# MAGIC # Validate commodity.gold.unified_data
# MAGIC
# MAGIC **Purpose:** Validate the gold-layer unified data table after creation
# MAGIC
# MAGIC **Checks:**
# MAGIC - Table exists and row counts
# MAGIC - Date ranges and continuity
# MAGIC - Array sizes (weather regions, GDELT themes)
# MAGIC - Sample data quality
# MAGIC - No critical nulls
# MAGIC
# MAGIC **Expected results:**
# MAGIC - ~7,000 rows (vs ~75,000 in silver.unified_data)
# MAGIC - Weather array: 30-65 regions per row
# MAGIC - GDELT array: 7 theme groups per row
# MAGIC - Date range: 2015-07-07 to present

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check 1: Table Exists and Row Counts

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Verify table exists
# MAGIC DESCRIBE TABLE commodity.gold.unified_data

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Row count and basic stats
# MAGIC SELECT
#     COUNT(*) as total_rows,
#     COUNT(DISTINCT commodity) as num_commodities,
#     COUNT(DISTINCT date) as num_dates,
#     MIN(date) as min_date,
#     MAX(date) as max_date
# MAGIC FROM commodity.gold.unified_data

# COMMAND ----------

# Compare to silver.unified_data row count
silver_count = spark.sql("SELECT COUNT(*) as cnt FROM commodity.silver.unified_data").collect()[0]['cnt']
gold_count = spark.sql("SELECT COUNT(*) as cnt FROM commodity.gold.unified_data").collect()[0]['cnt']

print(f"Silver unified_data rows: {silver_count:,}")
print(f"Gold unified_data rows:   {gold_count:,}")
print(f"Reduction: {(1 - gold_count/silver_count)*100:.1f}%")
print(f"\nExpected: ~90% reduction (75k → 7k rows)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check 2: Commodity Distribution

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Rows per commodity
# MAGIC SELECT
#     commodity,
#     COUNT(*) as row_count,
#     MIN(date) as start_date,
#     MAX(date) as end_date,
#     DATEDIFF(MAX(date), MIN(date)) as date_span_days
# MAGIC FROM commodity.gold.unified_data
# MAGIC GROUP BY commodity
# MAGIC ORDER BY commodity

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check 3: Weather Array Structure

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Weather array sizes
# MAGIC SELECT
#     commodity,
#     SIZE(weather_data) as num_regions,
#     COUNT(*) as row_count
# MAGIC FROM commodity.gold.unified_data
# MAGIC WHERE weather_data IS NOT NULL
# MAGIC GROUP BY commodity, SIZE(weather_data)
# MAGIC ORDER BY commodity, num_regions

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Sample weather data (first 3 regions for Coffee on recent date)
# MAGIC SELECT
#     date,
#     commodity,
#     weather_data[0].region as region_1,
#     weather_data[0].temp_mean_c as temp_1,
#     weather_data[0].precipitation_mm as precip_1,
#     weather_data[1].region as region_2,
#     weather_data[1].temp_mean_c as temp_2,
#     weather_data[2].region as region_3,
#     weather_data[2].temp_mean_c as temp_3
# MAGIC FROM commodity.gold.unified_data
# MAGIC WHERE commodity = 'Coffee'
# MAGIC   AND date >= '2024-01-01'
# MAGIC ORDER BY date DESC
# MAGIC LIMIT 5

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check 4: GDELT Array Structure

# COMMAND ----------

# MAGIC %sql
# MAGIC -- GDELT array sizes
# MAGIC SELECT
#     commodity,
#     SIZE(gdelt_themes) as num_themes,
#     COUNT(*) as row_count
# MAGIC FROM commodity.gold.unified_data
# MAGIC WHERE gdelt_themes IS NOT NULL
# MAGIC GROUP BY commodity, SIZE(gdelt_themes)
# MAGIC ORDER BY commodity, num_themes

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Sample GDELT themes for Coffee
# MAGIC SELECT
#     date,
#     commodity,
#     gdelt_themes[0].theme_group as theme_1,
#     gdelt_themes[0].article_count as count_1,
#     gdelt_themes[0].tone_avg as tone_1,
#     gdelt_themes[1].theme_group as theme_2,
#     gdelt_themes[1].article_count as count_2,
#     gdelt_themes[2].theme_group as theme_3,
#     gdelt_themes[2].article_count as count_3
# MAGIC FROM commodity.gold.unified_data
# MAGIC WHERE commodity = 'Coffee'
#     AND date >= '2024-01-01'
# MAGIC   AND gdelt_themes IS NOT NULL
# MAGIC ORDER BY date DESC
# MAGIC LIMIT 5

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check 5: Data Quality - Nulls in Critical Columns

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Check for nulls in critical columns
# MAGIC SELECT
#     'date' as column_name,
#     SUM(CASE WHEN date IS NULL THEN 1 ELSE 0 END) as null_count
# MAGIC FROM commodity.gold.unified_data
# MAGIC UNION ALL
# MAGIC SELECT
#     'commodity',
#     SUM(CASE WHEN commodity IS NULL THEN 1 ELSE 0 END)
# MAGIC FROM commodity.gold.unified_data
# MAGIC UNION ALL
# MAGIC SELECT
#     'close',
#     SUM(CASE WHEN close IS NULL THEN 1 ELSE 0 END)
# MAGIC FROM commodity.gold.unified_data
# MAGIC UNION ALL
# MAGIC SELECT
#     'weather_data',
#     SUM(CASE WHEN weather_data IS NULL THEN 1 ELSE 0 END)
# MAGIC FROM commodity.gold.unified_data
# MAGIC UNION ALL
# MAGIC SELECT
#     'gdelt_themes',
#     SUM(CASE WHEN gdelt_themes IS NULL THEN 1 ELSE 0 END)
# MAGIC FROM commodity.gold.unified_data

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check 6: Date Continuity (No Gaps)

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Check for date gaps (should have every day from min to max)
# MAGIC WITH date_range AS (
#     SELECT
#         commodity,
#         MIN(date) as min_date,
#         MAX(date) as max_date,
#         DATEDIFF(MAX(date), MIN(date)) + 1 as expected_days,
#         COUNT(DISTINCT date) as actual_days
#     FROM commodity.gold.unified_data
#     GROUP BY commodity
# MAGIC )
# MAGIC SELECT
#     commodity,
#     min_date,
#     max_date,
#     expected_days,
#     actual_days,
#     expected_days - actual_days as missing_days,
#     CASE
#         WHEN expected_days = actual_days THEN '✅ Complete'
#         ELSE '⚠️ Gaps detected'
#     END as status
# MAGIC FROM date_range

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check 7: Scalar Features (Market Data, VIX, etc.)

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Verify scalar features are populated
# MAGIC SELECT
#     commodity,
#     COUNT(*) as total_rows,
#     SUM(CASE WHEN close IS NOT NULL THEN 1 ELSE 0 END) as close_populated,
#     SUM(CASE WHEN vix IS NOT NULL THEN 1 ELSE 0 END) as vix_populated,
#     SUM(CASE WHEN is_trading_day = 1 THEN 1 ELSE 0 END) as trading_days,
#     SUM(CASE WHEN is_trading_day = 0 THEN 1 ELSE 0 END) as non_trading_days
# MAGIC FROM commodity.gold.unified_data
# MAGIC GROUP BY commodity

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check 8: Sample Full Row

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Sample complete row for Coffee
# MAGIC SELECT *
# MAGIC FROM commodity.gold.unified_data
# MAGIC WHERE commodity = 'Coffee'
#     AND date = '2024-01-01'
# MAGIC LIMIT 1

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check 9: Explode Arrays to Verify Structure

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Explode weather array to see all regions for one date
# MAGIC SELECT
#     date,
#     commodity,
#     weather.region,
#     weather.temp_mean_c,
#     weather.precipitation_mm,
#     weather.humidity_mean_pct
# MAGIC FROM commodity.gold.unified_data
# MAGIC LATERAL VIEW explode(weather_data) AS weather
# MAGIC WHERE commodity = 'Coffee'
#     AND date = '2024-01-01'
# MAGIC ORDER BY weather.region

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Explode GDELT array to see all themes for one date
# MAGIC SELECT
#     date,
#     commodity,
#     theme.theme_group,
#     theme.article_count,
#     theme.tone_avg,
#     theme.tone_positive,
#     theme.tone_negative,
#     theme.tone_polarity
# MAGIC FROM commodity.gold.unified_data
# MAGIC LATERAL VIEW explode(gdelt_themes) AS theme
# MAGIC WHERE commodity = 'Coffee'
#     AND date >= '2024-01-01'
# MAGIC ORDER BY date DESC, theme.article_count DESC
# MAGIC LIMIT 20

# COMMAND ----------

# MAGIC %md
# MAGIC ## ✅ Validation Summary

# COMMAND ----------

# Generate validation summary
from datetime import datetime

print("=" * 80)
print("VALIDATION SUMMARY - commodity.gold.unified_data")
print("=" * 80)
print(f"Validation Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# Get key metrics
stats = spark.sql("""
    SELECT
        COUNT(*) as total_rows,
        COUNT(DISTINCT commodity) as num_commodities,
        COUNT(DISTINCT date) as num_dates,
        MIN(date) as min_date,
        MAX(date) as max_date
    FROM commodity.gold.unified_data
""").collect()[0]

weather_size = spark.sql("""
    SELECT AVG(SIZE(weather_data)) as avg_regions
    FROM commodity.gold.unified_data
    WHERE weather_data IS NOT NULL
""").collect()[0]['avg_regions']

gdelt_size = spark.sql("""
    SELECT AVG(SIZE(gdelt_themes)) as avg_themes
    FROM commodity.gold.unified_data
    WHERE gdelt_themes IS NOT NULL
""").collect()[0]['avg_themes']

null_check = spark.sql("""
    SELECT
        SUM(CASE WHEN date IS NULL THEN 1 ELSE 0 END) as date_nulls,
        SUM(CASE WHEN close IS NULL THEN 1 ELSE 0 END) as close_nulls,
        SUM(CASE WHEN weather_data IS NULL THEN 1 ELSE 0 END) as weather_nulls,
        SUM(CASE WHEN gdelt_themes IS NULL THEN 1 ELSE 0 END) as gdelt_nulls
    FROM commodity.gold.unified_data
""").collect()[0]

print("📊 Table Statistics:")
print(f"  Total rows: {stats['total_rows']:,}")
print(f"  Commodities: {stats['num_commodities']}")
print(f"  Date range: {stats['min_date']} to {stats['max_date']}")
print(f"  Unique dates: {stats['num_dates']:,}")
print()

print("🌦️  Weather Data:")
print(f"  Avg regions per row: {weather_size:.1f}")
print(f"  Null weather arrays: {null_check['weather_nulls']}")
print()

print("📰 GDELT Data:")
print(f"  Avg theme groups per row: {gdelt_size:.1f}")
print(f"  Null GDELT arrays: {null_check['gdelt_nulls']}")
print()

print("✅ Critical Checks:")
print(f"  Date nulls: {null_check['date_nulls']} (expect 0)")
print(f"  Close price nulls: {null_check['close_nulls']} (expect 0)")
print()

# Compare to silver
silver_count = spark.sql("SELECT COUNT(*) FROM commodity.silver.unified_data").collect()[0][0]
reduction = (1 - stats['total_rows']/silver_count) * 100

print("📉 Size Reduction from Silver:")
print(f"  Silver rows: {silver_count:,}")
print(f"  Gold rows: {stats['total_rows']:,}")
print(f"  Reduction: {reduction:.1f}%")
print()

print("=" * 80)
print("✅ VALIDATION COMPLETE")
print("=" * 80)
print()
print("Next steps:")
print("  1. If validation passed, proceed to ml_lib pipeline testing")
print("  2. Test data loader: GoldDataLoader().load(commodity='Coffee')")
print("  3. Test transformers on sample data")

# COMMAND ----------
