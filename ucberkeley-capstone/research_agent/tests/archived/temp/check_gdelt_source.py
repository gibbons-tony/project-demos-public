#!/usr/bin/env python3
"""Check if GDELT source table exists and has data."""

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# Get SQL Warehouse
warehouses = list(w.warehouses.list())
warehouse = warehouses[0]

print("Checking GDELT source tables...")
print("=" * 80)

# Check if commodity.silver.gdelt_wide exists
queries = [
    ("commodity.silver.gdelt_wide exists", "SHOW TABLES IN commodity.silver LIKE 'gdelt_wide'"),
    ("commodity.silver.gdelt_wide row count", "SELECT COUNT(*) FROM commodity.silver.gdelt_wide"),
    ("commodity.silver.gdelt_wide date range", "SELECT MIN(article_date), MAX(article_date) FROM commodity.silver.gdelt_wide"),
    ("commodity.silver.gdelt_wide sample", "SELECT * FROM commodity.silver.gdelt_wide LIMIT 1"),
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
                if "row count" in description:
                    print(f"  ✅ {int(results[0][0]):,} rows")
                elif "date range" in description:
                    print(f"  ✅ {results[0][0]} to {results[0][1]}")
                elif "exists" in description:
                    if results:
                        print(f"  ✅ Table exists")
                    else:
                        print(f"  ❌ Table does not exist")
                elif "sample" in description:
                    print(f"  ✅ Sample row:")
                    # Get column names
                    cols = [col.name for col in statement.result.data_typed_array[0].values]
                    # Show first few columns
                    for i, col in enumerate(cols[:5]):
                        print(f"     {col}: {results[0][i]}")
            else:
                print(f"  ℹ️  No results")
        else:
            print(f"  ❌ Query failed: {statement.status.state}")
            if statement.status.error:
                print(f"     Error: {statement.status.error.message}")
    except Exception as e:
        print(f"  ❌ Error: {str(e)}")

print("\n" + "=" * 80)
print("\n💡 If table doesn't exist, you need to run the GDELT pipeline first.")
print("   See research_agent/DATA_SOURCES.md for GDELT pipeline details.")
