"""
Full end-to-end pipeline validation after catalog cleanup.

Tests:
1. Bronze layer - clean table names
2. Silver layer - unified_data
3. Forecast schema - all forecast tables
4. Data integrity across all layers
"""
from databricks import sql
import os

host = os.getenv("DATABRICKS_HOST", "https://dbc-fd7b00f3-7a6d.cloud.databricks.com")
token = os.getenv("DATABRICKS_TOKEN")
http_path = os.getenv("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/3cede8561503a13c")

connection = sql.connect(
    server_hostname=host.replace("https://", ""),
    http_path=http_path,
    access_token=token
)
cursor = connection.cursor()

print("="*80)
print("FULL PIPELINE VALIDATION - POST CATALOG CLEANUP")
print("="*80)
print()

# ============================================================================
# TEST 1: Bronze Layer - Clean Names
# ============================================================================
print("TEST 1: Bronze Layer")
print("-"*80)

bronze_tables = {
    'market': 'Market OHLCV data',
    'vix': 'VIX volatility data',
    'macro': 'Macro economic data',
    'weather': 'Weather data',
    'cftc': 'CFTC commitment of traders',
    'gdelt': 'GDELT sentiment data'
}

bronze_pass = True
for table, desc in bronze_tables.items():
    try:
        cursor.execute(f"SELECT COUNT(*) FROM commodity.bronze.{table}")
        count = cursor.fetchone()[0]
        if count > 0:
            print(f"  ✅ {table:<20} {count:>10,} rows  ({desc})")
        else:
            print(f"  ❌ {table:<20} EMPTY")
            bronze_pass = False
    except Exception as e:
        print(f"  ❌ {table:<20} ERROR: {e}")
        bronze_pass = False

print()

# ============================================================================
# TEST 2: Silver Layer - Unified Data Only
# ============================================================================
print("TEST 2: Silver Layer")
print("-"*80)

silver_pass = True
try:
    cursor.execute("SELECT COUNT(*) FROM commodity.silver.unified_data")
    count = cursor.fetchone()[0]
    if count > 0:
        print(f"  ✅ unified_data: {count:,} rows")

        # Verify no forecast tables in silver
        cursor.execute("SHOW TABLES IN commodity.silver")
        silver_tables = [row[1] for row in cursor.fetchall()]

        if len(silver_tables) == 1 and silver_tables[0] == 'unified_data':
            print(f"  ✅ Silver schema contains only unified_data (correct)")
        else:
            print(f"  ⚠️  Silver schema has extra tables: {silver_tables}")
            silver_pass = False
    else:
        print(f"  ❌ unified_data is EMPTY")
        silver_pass = False
except Exception as e:
    print(f"  ❌ Error: {e}")
    silver_pass = False

print()

# ============================================================================
# TEST 3: Forecast Schema
# ============================================================================
print("TEST 3: Forecast Schema")
print("-"*80)

forecast_tables = {
    'point_forecasts': 'Point forecast estimates',
    'distributions': 'Monte Carlo distributions',
    'forecast_actuals': 'Actual values for evaluation',
    'forecast_metadata': 'Forecast generation metadata'
}

forecast_pass = True
for table, desc in forecast_tables.items():
    try:
        cursor.execute(f"SELECT COUNT(*) FROM commodity.forecast.{table}")
        count = cursor.fetchone()[0]
        print(f"  ✅ {table:<25} {count:>10,} rows  ({desc})")
    except Exception as e:
        print(f"  ❌ {table:<25} ERROR: {e}")
        forecast_pass = False

# Check no forecasts schema exists
try:
    cursor.execute("SHOW SCHEMAS IN commodity")
    schemas = [row[0] for row in cursor.fetchall()]
    if 'forecasts' in schemas:
        print(f"  ⚠️  Old 'forecasts' schema still exists - should be deleted")
        forecast_pass = False
    else:
        print(f"  ✅ No duplicate 'forecasts' schema (correct)")
except Exception as e:
    print(f"  ⚠️  Error checking schemas: {e}")

print()

# ============================================================================
# TEST 4: Data Integrity
# ============================================================================
print("TEST 4: Data Integrity")
print("-"*80)

integrity_pass = True

# Check unified_data has data from all bronze sources
try:
    cursor.execute("""
        SELECT
            COUNT(DISTINCT commodity) as commodities,
            COUNT(DISTINCT region) as regions,
            MIN(date) as earliest_date,
            MAX(date) as latest_date,
            SUM(CASE WHEN close IS NULL THEN 1 ELSE 0 END) as null_prices,
            SUM(CASE WHEN temp_mean_c IS NULL THEN 1 ELSE 0 END) as null_temps
        FROM commodity.silver.unified_data
    """)
    row = cursor.fetchone()
    print(f"  Commodities: {row[0]} (expected: 2)")
    print(f"  Regions: {row[1]} (expected: ~67)")
    print(f"  Date range: {row[2]} to {row[3]}")
    print(f"  Null prices: {row[4]} (expected: 0)")
    print(f"  Null temps: {row[5]} (expected: 0)")

    if row[0] != 2:
        print(f"  ⚠️  Expected 2 commodities, found {row[0]}")
        integrity_pass = False
    if row[4] > 0 or row[5] > 0:
        print(f"  ⚠️  Found null values in critical columns")
        integrity_pass = False
    else:
        print(f"  ✅ Data integrity checks passed")

except Exception as e:
    print(f"  ❌ Error: {e}")
    integrity_pass = False

print()

# ============================================================================
# FINAL SUMMARY
# ============================================================================
print("="*80)
print("VALIDATION SUMMARY")
print("="*80)

all_pass = bronze_pass and silver_pass and forecast_pass and integrity_pass

tests = [
    ("Bronze Layer (clean names)", bronze_pass),
    ("Silver Layer (unified_data only)", silver_pass),
    ("Forecast Schema (4 tables)", forecast_pass),
    ("Data Integrity", integrity_pass)
]

for test_name, passed in tests:
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {status}  {test_name}")

print()
if all_pass:
    print("🎉 ALL TESTS PASSED - Catalog cleanup successful!")
else:
    print("⚠️  Some tests failed - review output above")

print("="*80)

cursor.close()
connection.close()
