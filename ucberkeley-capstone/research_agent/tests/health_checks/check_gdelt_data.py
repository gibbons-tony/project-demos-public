"""
Check GDELT historical data coverage
"""

from databricks import sql
import os

host = os.getenv("DATABRICKS_HOST", "https://dbc-fd7b00f3-7a6d.cloud.databricks.com")
token = os.getenv("DATABRICKS_TOKEN")
http_path = os.getenv("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/3cede8561503a13c")

print("="*80)
print("GDELT DATA COVERAGE CHECK")
print("="*80)

connection = sql.connect(
    server_hostname=host.replace("https://", ""),
    http_path=http_path,
    access_token=token
)
cursor = connection.cursor()

# Check if GDELT tables exist
print("\n1. GDELT Tables Status:")
print("-"*80)

try:
    cursor.execute("DESCRIBE TABLE commodity.landing.gdelt_sentiment_inc")
    print("  ✅ commodity.landing.gdelt_sentiment_inc exists")
except Exception as e:
    print(f"  ❌ Landing table error: {e}")

try:
    cursor.execute("DESCRIBE TABLE commodity.bronze.gdelt_sentiment")
    print("  ✅ commodity.bronze.gdelt_sentiment exists")
except Exception as e:
    print(f"  ❌ Bronze view error: {e}")

# Check GDELT data in landing
print("\n2. GDELT Landing Data:")
print("-"*80)

try:
    cursor.execute("""
        SELECT
            COUNT(*) as total_rows,
            MIN(date) as earliest_date,
            MAX(date) as latest_date,
            COUNT(DISTINCT date) as unique_dates,
            DATEDIFF(MAX(date), MIN(date)) as date_span_days
        FROM commodity.landing.gdelt_sentiment_inc
    """)
    row = cursor.fetchone()
    if row and row[0] > 0:
        total, earliest, latest, unique_dates, span = row
        print(f"  Total Rows: {total:,}")
        print(f"  Date Range: {earliest} to {latest}")
        print(f"  Unique Dates: {unique_dates:,}")
        print(f"  Span: {span:,} days")

        # Calculate expected vs actual
        expected_days = 3770  # ~2015-2025
        coverage_pct = (unique_dates / expected_days) * 100 if expected_days > 0 else 0

        if unique_dates >= 3000:
            print(f"  Status: ✅ GOOD - {coverage_pct:.1f}% historical coverage")
        elif unique_dates >= 1000:
            print(f"  Status: ⚠️ PARTIAL - {coverage_pct:.1f}% historical coverage")
        else:
            print(f"  Status: ❌ MINIMAL - Only {unique_dates} days ({coverage_pct:.1f}%)")
    else:
        print("  ❌ NO DATA in landing table")
except Exception as e:
    print(f"  Error querying landing: {e}")

# Check GDELT data in bronze
print("\n3. GDELT Bronze Data:")
print("-"*80)

try:
    cursor.execute("""
        SELECT
            COUNT(*) as total_rows,
            MIN(date) as earliest_date,
            MAX(date) as latest_date,
            COUNT(DISTINCT date) as unique_dates
        FROM commodity.bronze.gdelt_sentiment
    """)
    row = cursor.fetchone()
    if row and row[0] > 0:
        total, earliest, latest, unique_dates = row
        print(f"  Total Rows: {total:,}")
        print(f"  Date Range: {earliest} to {latest}")
        print(f"  Unique Dates: {unique_dates:,}")
    else:
        print("  ❌ NO DATA in bronze view")
except Exception as e:
    print(f"  Error querying bronze: {e}")

# Check recent GDELT data (last 7 days)
print("\n4. Recent GDELT Data (last 7 days):")
print("-"*80)

try:
    cursor.execute("""
        SELECT date, COUNT(*) as rows
        FROM commodity.bronze.gdelt_sentiment
        WHERE date >= CURRENT_DATE - 7
        GROUP BY date
        ORDER BY date DESC
    """)
    results = cursor.fetchall()
    if results:
        for date, count in results:
            print(f"  {date}: {count:,} rows")
    else:
        print("  No recent data")
except Exception as e:
    print(f"  Error: {e}")

# Check if GDELT is integrated into unified_data
print("\n5. GDELT Integration Status:")
print("-"*80)

cursor.execute("DESCRIBE TABLE commodity.silver.unified_data")
columns = [row[0] for row in cursor.fetchall()]

gdelt_columns = [col for col in columns if 'gdelt' in col.lower() or 'sentiment' in col.lower() or 'tone' in col.lower()]

if gdelt_columns:
    print(f"  ✅ GDELT columns found in unified_data:")
    for col in gdelt_columns:
        print(f"     - {col}")
else:
    print("  ⚠️ No GDELT columns found in unified_data")
    print("     GDELT data exists but may not be integrated yet")

cursor.close()
connection.close()

print("\n" + "="*80)
print("GDELT CHECK COMPLETE")
print("="*80)
