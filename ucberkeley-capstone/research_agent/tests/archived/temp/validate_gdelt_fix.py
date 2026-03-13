#!/usr/bin/env python3
"""Validate GDELT arrays are populated after commodity name fix."""

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
warehouses = list(w.warehouses.list())
warehouse = warehouses[0]

print("Validating GDELT Fix")
print("=" * 80)

queries = [
    # 1. Check GDELT array sizes
    ("GDELT array sizes", """
        SELECT
            commodity,
            COUNT(*) as total_rows,
            AVG(COALESCE(size(gdelt_themes), 0)) as avg_themes,
            MIN(COALESCE(size(gdelt_themes), 0)) as min_themes,
            MAX(COALESCE(size(gdelt_themes), 0)) as max_themes,
            SUM(CASE WHEN size(gdelt_themes) > 0 THEN 1 ELSE 0 END) as rows_with_data,
            SUM(CASE WHEN size(gdelt_themes) = 0 OR gdelt_themes IS NULL THEN 1 ELSE 0 END) as rows_without_data
        FROM commodity.gold.unified_data
        GROUP BY commodity
    """),

    # 2. Check GDELT date range
    ("GDELT date coverage", """
        SELECT
            commodity,
            MIN(CASE WHEN size(gdelt_themes) > 0 THEN date END) as first_gdelt_date,
            MAX(CASE WHEN size(gdelt_themes) > 0 THEN date END) as last_gdelt_date,
            COUNT(DISTINCT CASE WHEN size(gdelt_themes) > 0 THEN date END) as dates_with_gdelt
        FROM commodity.gold.unified_data
        GROUP BY commodity
    """),

    # 3. Sample GDELT data
    ("GDELT sample (2024)", """
        SELECT
            date,
            commodity,
            size(gdelt_themes) as theme_count
        FROM commodity.gold.unified_data
        WHERE date >= '2024-01-01'
          AND size(gdelt_themes) > 0
        ORDER BY date DESC
        LIMIT 5
    """),

    # 4. Pre-2021 check (should have 0)
    ("Pre-2021 check (should be 0)", """
        SELECT
            commodity,
            COUNT(*) as total_rows_pre_2021,
            AVG(COALESCE(size(gdelt_themes), 0)) as avg_themes_pre_2021
        FROM commodity.gold.unified_data
        WHERE date < '2021-01-01'
        GROUP BY commodity
    """),
]

for description, sql_query in queries:
    print(f"\n{description}:")
    try:
        statement = w.statement_execution.execute_statement(
            warehouse_id=warehouse.id,
            statement=sql_query,
            wait_timeout="30s"
        )

        if statement.status.state.value == "SUCCEEDED":
            if statement.result and statement.result.data_array:
                results = statement.result.data_array
                for row in results:
                    print(f"  {row}")

                # Validation checks
                if "array sizes" in description.lower():
                    for row in results:
                        commodity, total, avg, min_val, max_val, with_data, without_data = row
                        if avg > 0:
                            print(f"  ✅ {commodity}: GDELT arrays populated! ({with_data:,} rows with data)")
                        else:
                            print(f"  ❌ {commodity}: GDELT arrays still empty!")

                if "date coverage" in description.lower():
                    for row in results:
                        commodity, first_date, last_date, date_count = row
                        if first_date and first_date >= '2021-01-01':
                            print(f"  ✅ {commodity}: GDELT starts on {first_date} (expected 2021+)")
                        elif first_date:
                            print(f"  ⚠️  {commodity}: GDELT starts on {first_date} (unexpected)")
                        else:
                            print(f"  ❌ {commodity}: No GDELT data found!")

                if "pre-2021" in description.lower():
                    for row in results:
                        commodity, total, avg = row
                        if float(avg) == 0.0:
                            print(f"  ✅ {commodity}: Pre-2021 correctly has empty arrays")
                        else:
                            print(f"  ⚠️  {commodity}: Pre-2021 has data (avg={avg})")
            else:
                print(f"  ℹ️  No results")
        else:
            print(f"  ❌ Query failed: {statement.status.state}")
    except Exception as e:
        print(f"  ❌ Error: {str(e)}")

print("\n" + "=" * 80)
print("✅ If you see 'GDELT arrays populated' above, the fix worked!")
print("⚠️  Remember: Pre-2021 dates will always have empty GDELT arrays (by design)")
