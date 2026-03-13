#!/usr/bin/env python3
"""
Weather v2 Migration - Phase 8: Validation

Validates the weather v2 migration completed successfully:
- bronze.weather table exists with v2 coordinates
- No weather_v2 table exists
- gold.unified_data was rebuilt
- Forecast tables regenerated (after Phase 7)
"""
import os
from databricks import sql
from dotenv import load_dotenv

# Load from infra/.env
env_path = '../../infra/.env'
load_dotenv(env_path)

token = os.getenv('DATABRICKS_TOKEN')
server_hostname_raw = os.getenv('DATABRICKS_HOST')
if server_hostname_raw:
    server_hostname = server_hostname_raw.replace('https://', '')
else:
    raise ValueError(f"DATABRICKS_HOST not found in {env_path}")
http_path = os.getenv('DATABRICKS_HTTP_PATH')

print("="*80)
print("PHASE 8: WEATHER V2 MIGRATION VALIDATION")
print("="*80)
print(f"Server: {server_hostname}")
print()

connection = sql.connect(
    server_hostname=server_hostname,
    http_path=http_path,
    access_token=token
)
cursor = connection.cursor()

validation_results = []

# 1. Verify bronze.weather exists (not weather_v2)
print("1. Checking bronze weather tables...")
cursor.execute("SHOW TABLES IN commodity.bronze LIKE 'weather*'")
weather_tables = cursor.fetchall()

has_weather = False
has_weather_v2 = False

for table in weather_tables:
    table_name = table[1]
    if table_name == 'weather':
        has_weather = True
        cursor.execute(f"SELECT COUNT(*) FROM commodity.bronze.{table_name}")
        count = cursor.fetchone()[0]
        print(f"   ✅ bronze.weather exists: {count:,} rows")
        validation_results.append(("bronze.weather exists", True))
    elif table_name == 'weather_v2':
        has_weather_v2 = True
        print(f"   ❌ bronze.weather_v2 still exists (should be renamed)")
        validation_results.append(("bronze.weather_v2 removed", False))

if not has_weather:
    print(f"   ❌ bronze.weather does NOT exist")
    validation_results.append(("bronze.weather exists", False))

if not has_weather_v2:
    print(f"   ✅ bronze.weather_v2 removed (correctly renamed)")
    validation_results.append(("bronze.weather_v2 removed", True))

# 2. Verify v2 coordinates
print("\n2. Verifying v2 coordinates (sample regions)...")
test_regions = [
    ('Minas_Gerais_Brazil', -20.3155, -45.4108),
    ('Sao_Paulo_Brazil', -21.2426, -48.2990),
    ('Parana_Brazil', -23.4209, -51.9331)
]

coords_valid = True
for region, expected_lat, expected_lon in test_regions:
    cursor.execute(f"""
        SELECT latitude, longitude
        FROM commodity.bronze.weather
        WHERE region = '{region}'
        LIMIT 1
    """)
    result = cursor.fetchone()

    if result:
        lat, lon = float(result[0]), float(result[1])
        if abs(lat - expected_lat) < 0.01 and abs(lon - expected_lon) < 0.01:
            print(f"   ✅ {region}: ({lat}, {lon}) - CORRECT")
        else:
            print(f"   ❌ {region}: ({lat}, {lon}) - WRONG (expected {expected_lat}, {expected_lon})")
            coords_valid = False
    else:
        print(f"   ⚠️  {region}: No data found")
        coords_valid = False

validation_results.append(("Coordinates are v2", coords_valid))

# 3. Verify gold.unified_data exists and has data
print("\n3. Checking gold.unified_data...")
try:
    cursor.execute("SELECT COUNT(*) FROM commodity.gold.unified_data")
    unified_count = cursor.fetchone()[0]
    if unified_count > 0:
        print(f"   ✅ gold.unified_data exists: {unified_count:,} rows")
        validation_results.append(("gold.unified_data rebuilt", True))
    else:
        print(f"   ❌ gold.unified_data exists but is empty")
        validation_results.append(("gold.unified_data rebuilt", False))
except Exception as e:
    print(f"   ❌ gold.unified_data error: {e}")
    validation_results.append(("gold.unified_data rebuilt", False))

# 4. Check forecast tables (should exist after Phase 7)
print("\n4. Checking forecast tables (after regeneration)...")
cursor.execute("SHOW TABLES IN commodity.forecast")
forecast_tables = cursor.fetchall()

if forecast_tables:
    print(f"   ✅ Found {len(forecast_tables)} forecast tables:")
    for table in forecast_tables:
        table_name = table[1]
        cursor.execute(f"SELECT COUNT(*) FROM commodity.forecast.{table_name}")
        count = cursor.fetchone()[0]
        print(f"      - {table_name}: {count:,} rows")
    validation_results.append(("Forecasts regenerated", True))
else:
    print(f"   ⚠️  No forecast tables found (run Phase 7 to regenerate)")
    validation_results.append(("Forecasts regenerated", False))

# 5. Check table comment
print("\n5. Verifying table metadata...")
cursor.execute("DESCRIBE EXTENDED commodity.bronze.weather")
table_info = cursor.fetchall()

comment_found = False
for row in table_info:
    if row[0] == 'Comment':
        comment = row[1]
        if 'v2' in comment.lower() or 'correct' in comment.lower():
            print(f"   ✅ Table comment documents migration")
            comment_found = True
        break

if not comment_found:
    print(f"   ⚠️  Table comment not found or doesn't document migration")

validation_results.append(("Table comment updated", comment_found))

cursor.close()
connection.close()

# Summary
print("\n" + "="*80)
print("VALIDATION SUMMARY")
print("="*80)

all_passed = True
for check_name, passed in validation_results:
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}: {check_name}")
    if not passed:
        all_passed = False

print("\n" + "="*80)
if all_passed:
    print("✅ ALL VALIDATION CHECKS PASSED")
    print("Weather v2 migration is complete!")
else:
    print("⚠️  SOME VALIDATION CHECKS FAILED")
    print("Review failures above and address before proceeding")
print("="*80)
