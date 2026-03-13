#!/usr/bin/env python3
"""Check for commodity name mismatch between GDELT and gold tables."""

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
warehouses = list(w.warehouses.list())
warehouse = warehouses[0]

print("Checking Commodity Name Mismatch")
print("=" * 80)

queries = [
    ("GDELT commodities", "SELECT DISTINCT commodity FROM commodity.silver.gdelt_wide ORDER BY commodity"),
    ("Gold commodities", "SELECT DISTINCT commodity FROM commodity.gold.unified_data ORDER BY commodity"),
    ("Test join with case sensitivity", """
        SELECT
            'GDELT rows' as source,
            COUNT(*) as cnt,
            collect_set(commodity) as commodities
        FROM commodity.silver.gdelt_wide
        UNION ALL
        SELECT
            'Gold rows' as source,
            COUNT(*) as cnt,
            collect_set(commodity) as commodities
        FROM commodity.gold.unified_data
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
        else:
            print(f"  ❌ Query failed")
    except Exception as e:
        print(f"  ❌ Error: {str(e)}")

print("\n" + "=" * 80)
print("\n🔍 If commodities differ in case (coffee vs Coffee), the join will fail!")
print("   Need to use LOWER() or UPPER() in the join condition.")
