#!/usr/bin/env python3
"""
Rigorous Validation of Gold Layer Tables

Run after building both commodity.gold.unified_data tables to ensure:
1. Correct row counts
2. Expected NULL rates
3. Missingness flags work correctly
4. GDELT commodity capitalization fixed
5. Production vs experimental differences are correct
"""

from dotenv import load_dotenv
import os
from databricks import sql

# Load credentials
load_dotenv('infra/.env')

token = os.environ['DATABRICKS_TOKEN']
host = os.environ['DATABRICKS_HOST'].replace('https://', '').replace('http://', '')
http_path = os.environ['DATABRICKS_HTTP_PATH']  # Use SQL Warehouse

print('🔍 Rigorous Validation of Gold Tables')
print('=' * 80)

# Connect
connection = sql.connect(server_hostname=host, http_path=http_path, access_token=token)
cursor = connection.cursor()

# ============================================================================
# TEST 1: Row Counts
# ============================================================================
print('\n📊 TEST 1: Row Counts')
print('-' * 80)

cursor.execute("SELECT COUNT(*) FROM commodity.gold.unified_data")
prod_rows = cursor.fetchone()[0]
print(f'Production (unified_data):             {prod_rows:,} rows')

cursor.execute("SELECT COUNT(*) FROM commodity.gold.unified_data_raw")
exp_rows = cursor.fetchone()[0]
print(f'Experimental (unified_data_raw): {exp_rows:,} rows')

if prod_rows == exp_rows:
    print(f'✅ PASS: Both tables have same row count ({prod_rows:,})')
else:
    print(f'❌ FAIL: Row counts differ! ({prod_rows:,} vs {exp_rows:,})')

expected_min_rows = 6500  # ~7k expected
expected_max_rows = 8000
if expected_min_rows <= prod_rows <= expected_max_rows:
    print(f'✅ PASS: Row count in expected range ({expected_min_rows:,}-{expected_max_rows:,})')
else:
    print(f'⚠️  WARNING: Row count outside expected range')

# ============================================================================
# TEST 2: Production Table - Minimal NULLs (Forward-Fill Validation)
# ============================================================================
print('\n📊 TEST 2: Production Table - NULL Rates (should be ~0%)')
print('-' * 80)

cursor.execute("""
    SELECT
        COUNT(*) as total_rows,
        SUM(CASE WHEN vix IS NULL THEN 1 ELSE 0 END) as vix_nulls,
        SUM(CASE WHEN open IS NULL THEN 1 ELSE 0 END) as open_nulls,
        SUM(CASE WHEN close IS NULL THEN 1 ELSE 0 END) as close_nulls,
        SUM(CASE WHEN gdelt_themes IS NULL THEN 1 ELSE 0 END) as gdelt_nulls
    FROM commodity.gold.unified_data
""")
row = cursor.fetchone()
total, vix_nulls, open_nulls, close_nulls, gdelt_nulls = row

vix_pct = (vix_nulls / total) * 100
open_pct = (open_nulls / total) * 100
close_pct = (close_nulls / total) * 100
gdelt_pct = (gdelt_nulls / total) * 100

print(f'VIX NULLs:          {vix_nulls:,} / {total:,} ({vix_pct:.2f}%)')
print(f'Open NULLs:         {open_nulls:,} / {total:,} ({open_pct:.2f}%)')
print(f'Close NULLs:        {close_nulls:,} / {total:,} ({close_pct:.2f}%)')
print(f'GDELT NULLs:        {gdelt_nulls:,} / {total:,} ({gdelt_pct:.2f}%)')

# After forward-fill, should have minimal NULLs (only initial rows before first value)
if vix_pct < 1 and open_pct < 1 and close_pct < 1 and gdelt_pct < 1:
    print('✅ PASS: Production table has minimal NULLs (<1%) - forward-fill working')
else:
    print('⚠️  WARNING: Production table has more NULLs than expected')

# ============================================================================
# TEST 3: Experimental Table - Expected NULL Rates
# ============================================================================
print('\n📊 TEST 3: Experimental Table - NULL Rates (30% market, 0% close, 73% GDELT)')
print('-' * 80)

cursor.execute("""
    SELECT
        COUNT(*) as total_rows,
        SUM(CASE WHEN vix IS NULL THEN 1 ELSE 0 END) as vix_nulls,
        SUM(CASE WHEN open IS NULL THEN 1 ELSE 0 END) as open_nulls,
        SUM(CASE WHEN close IS NULL THEN 1 ELSE 0 END) as close_nulls,
        SUM(CASE WHEN gdelt_themes IS NULL THEN 1 ELSE 0 END) as gdelt_nulls
    FROM commodity.gold.unified_data_raw
""")
row = cursor.fetchone()
total, vix_nulls, open_nulls, close_nulls, gdelt_nulls = row

vix_pct = (vix_nulls / total) * 100
open_pct = (open_nulls / total) * 100
close_pct = (close_nulls / total) * 100
gdelt_pct = (gdelt_nulls / total) * 100

print(f'VIX NULLs:          {vix_nulls:,} / {total:,} ({vix_pct:.1f}%) [expect ~30%]')
print(f'Open NULLs:         {open_nulls:,} / {total:,} ({open_pct:.1f}%) [expect ~30%]')
print(f'Close NULLs:        {close_nulls:,} / {total:,} ({close_pct:.1f}%) [expect 0%]')
print(f'GDELT NULLs:        {gdelt_nulls:,} / {total:,} ({gdelt_pct:.1f}%) [expect ~73%]')

tests_passed = 0
tests_total = 4

# VIX/Open should be ~30% NULL (weekends/holidays)
if 25 <= vix_pct <= 35:
    print('✅ PASS: VIX NULL rate in expected range (25-35%)')
    tests_passed += 1
else:
    print(f'❌ FAIL: VIX NULL rate out of range ({vix_pct:.1f}%)')

if 25 <= open_pct <= 35:
    print('✅ PASS: Open NULL rate in expected range (25-35%)')
    tests_passed += 1
else:
    print(f'❌ FAIL: Open NULL rate out of range ({open_pct:.1f}%)')

# Close should be 0% NULL (forward-filled)
if close_pct == 0:
    print('✅ PASS: Close has no NULLs (forward-filled)')
    tests_passed += 1
else:
    print(f'❌ FAIL: Close has {close_pct:.1f}% NULLs (should be 0%)')

# GDELT should be ~73% NULL (days without articles)
if 60 <= gdelt_pct <= 85:
    print('✅ PASS: GDELT NULL rate in expected range (60-85%)')
    tests_passed += 1
else:
    print(f'❌ FAIL: GDELT NULL rate out of range ({gdelt_pct:.1f}%)')

print(f'\nExperimental NULL tests: {tests_passed}/{tests_total} passed')

# ============================================================================
# TEST 4: Missingness Flags
# ============================================================================
print('\n📊 TEST 4: Missingness Flags (experimental table only)')
print('-' * 80)

cursor.execute("""
    SELECT
        ROUND(100.0 * AVG(has_market_data), 1) as market_pct,
        ROUND(100.0 * AVG(has_weather_data), 1) as weather_pct,
        ROUND(100.0 * AVG(has_gdelt_data), 1) as gdelt_pct
    FROM commodity.gold.unified_data_raw
""")
market_pct, weather_pct, gdelt_pct = cursor.fetchone()

print(f'has_market_data:    {market_pct}% [expect ~70% for trading days]')
print(f'has_weather_data:   {weather_pct}% [expect ~100% - weather daily]')
print(f'has_gdelt_data:     {gdelt_pct}% [expect ~27% - days with articles]')

tests_passed = 0
tests_total = 3

if 65 <= market_pct <= 75:
    print('✅ PASS: has_market_data in expected range (65-75%)')
    tests_passed += 1
else:
    print(f'❌ FAIL: has_market_data out of range ({market_pct}%)')

if weather_pct >= 95:
    print('✅ PASS: has_weather_data high (≥95%)')
    tests_passed += 1
else:
    print(f'❌ FAIL: has_weather_data low ({weather_pct}%)')

if 20 <= gdelt_pct <= 35:
    print('✅ PASS: has_gdelt_data in expected range (20-35%)')
    tests_passed += 1
else:
    print(f'❌ FAIL: has_gdelt_data out of range ({gdelt_pct}%)')

print(f'\nMissingness flag tests: {tests_passed}/{tests_total} passed')

# ============================================================================
# TEST 5: GDELT Commodity Capitalization
# ============================================================================
print('\n📊 TEST 5: GDELT Commodity Capitalization (should be Coffee/Sugar, not coffee/sugar)')
print('-' * 80)

# Production table
cursor.execute("""
    SELECT DISTINCT commodity
    FROM commodity.gold.unified_data
    WHERE gdelt_themes IS NOT NULL AND size(gdelt_themes) > 0
    ORDER BY commodity
""")
prod_commodities = [row[0] for row in cursor.fetchall()]
print(f'Production commodities with GDELT: {prod_commodities}')

# Experimental table
cursor.execute("""
    SELECT DISTINCT commodity
    FROM commodity.gold.unified_data_raw
    WHERE gdelt_themes IS NOT NULL AND size(gdelt_themes) > 0
    ORDER BY commodity
""")
exp_commodities = [row[0] for row in cursor.fetchall()]
print(f'Experimental commodities with GDELT: {exp_commodities}')

expected = ['Coffee', 'Sugar']
if prod_commodities == expected and exp_commodities == expected:
    print('✅ PASS: GDELT commodities properly capitalized in both tables')
else:
    print(f'❌ FAIL: GDELT commodity capitalization incorrect')
    print(f'   Expected: {expected}')
    print(f'   Production: {prod_commodities}')
    print(f'   Experimental: {exp_commodities}')

# ============================================================================
# TEST 6: Sample Data Inspection
# ============================================================================
print('\n📊 TEST 6: Sample Data Inspection')
print('-' * 80)

print('\nProduction table (latest 3 Coffee rows):')
cursor.execute("""
    SELECT date, close, vix, size(weather_data) as weather_regions, size(gdelt_themes) as gdelt_themes_count
    FROM commodity.gold.unified_data
    WHERE commodity = 'Coffee'
    ORDER BY date DESC
    LIMIT 3
""")
for row in cursor.fetchall():
    vix_str = f"{row[2]:.2f}" if row[2] is not None else "NULL"
    gdelt_count = row[4] if row[4] is not None else 0
    print(f'  {row[0]} | close={row[1]:.2f} | vix={vix_str} | weather={row[3]} regions | GDELT={gdelt_count} themes')

print('\nExperimental table (latest 3 Coffee rows with NULL indicators):')
cursor.execute("""
    SELECT date, close, vix, open,
           has_market_data, has_weather_data, has_gdelt_data
    FROM commodity.gold.unified_data_raw
    WHERE commodity = 'Coffee'
    ORDER BY date DESC
    LIMIT 3
""")
for row in cursor.fetchall():
    date, close, vix, open_val, market_flag, weather_flag, gdelt_flag = row
    vix_str = f"{vix:.2f}" if vix else "NULL"
    open_str = f"{open_val:.2f}" if open_val else "NULL"
    print(f'  {date} | close={close:.2f} | vix={vix_str} | open={open_str} | flags: market={market_flag} weather={weather_flag} GDELT={gdelt_flag}')

cursor.close()
connection.close()

print('\n' + '=' * 80)
print('✅ Validation Complete')
print('=' * 80)
print('\nNext steps:')
print('  1. Review GOLD_MIGRATION_GUIDE.md to choose which table to use')
print('  2. Update forecast models to query the appropriate gold table')
print('  3. For experimental table: implement ImputationTransformer in your pipeline')
