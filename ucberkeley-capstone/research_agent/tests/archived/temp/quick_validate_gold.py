#!/usr/bin/env python3
"""
Quick validation of gold.unified_data using Databricks SDK.
Runs SQL queries on unity-catalog-cluster via SDK.
"""

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState
import time
import os

# Initialize Databricks client (uses default credentials)
w = WorkspaceClient()

# Find unity-catalog-cluster
clusters = w.clusters.list()
unity_cluster = None
for cluster in clusters:
    if cluster.cluster_name == "unity-catalog-cluster":
        unity_cluster = cluster
        break

if not unity_cluster:
    print("❌ unity-catalog-cluster not found!")
    exit(1)

print(f"✅ Found cluster: {unity_cluster.cluster_name} (ID: {unity_cluster.cluster_id})")
print(f"   State: {unity_cluster.state}")

# If cluster is terminated, start it
if unity_cluster.state.value in ["TERMINATED", "TERMINATING"]:
    print(f"⚠️  Cluster is {unity_cluster.state}, starting it...")
    w.clusters.start(unity_cluster.cluster_id)

    # Wait for cluster to start (max 5 minutes)
    for i in range(60):
        cluster_info = w.clusters.get(unity_cluster.cluster_id)
        if cluster_info.state.value == "RUNNING":
            print(f"✅ Cluster is now RUNNING")
            break
        print(f"   Waiting for cluster to start... ({i*5}s)")
        time.sleep(5)
    else:
        print("❌ Cluster failed to start within 5 minutes")
        exit(1)

# Get SQL Warehouse (needed for SQL execution API)
warehouses = list(w.warehouses.list())
if not warehouses:
    print("❌ No SQL Warehouses found")
    exit(1)

warehouse = warehouses[0]
print(f"✅ Using SQL Warehouse: {warehouse.name} (ID: {warehouse.id})")

# Run validation queries
print("\n" + "=" * 80)
print("RUNNING VALIDATION QUERIES")
print("=" * 80)

def run_query(sql_query, description):
    """Execute SQL query and return results."""
    print(f"\n{description}...")

    try:
        # Execute statement
        statement = w.statement_execution.execute_statement(
            warehouse_id=warehouse.id,
            statement=sql_query,
            wait_timeout="30s"
        )

        # Check if completed
        if statement.status.state == StatementState.SUCCEEDED:
            # Get results
            if statement.result and statement.result.data_array:
                return statement.result.data_array
            else:
                return []
        else:
            print(f"   ❌ Query failed: {statement.status.state}")
            if statement.status.error:
                print(f"      Error: {statement.status.error.message}")
            return None

    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        return None

# 1. Check table exists and row count
results = run_query(
    "SELECT COUNT(*) as cnt FROM commodity.gold.unified_data",
    "1. Checking table exists and row count"
)
if results:
    row_count = int(results[0][0])
    print(f"   ✅ Table exists with {row_count:,} rows")
else:
    print("   ❌ Table does not exist or query failed")
    exit(1)

# 2. Check commodities
results = run_query(
    "SELECT DISTINCT commodity FROM commodity.gold.unified_data ORDER BY commodity",
    "2. Checking commodities"
)
if results:
    commodities = [row[0] for row in results]
    print(f"   ✅ Commodities: {', '.join(commodities)}")

# 3. Check date range
results = run_query(
    "SELECT MIN(date) as min_date, MAX(date) as max_date FROM commodity.gold.unified_data",
    "3. Checking date range"
)
if results:
    min_date, max_date = results[0]
    print(f"   ✅ Date range: {min_date} to {max_date}")

# 4. Check schema columns
results = run_query(
    "DESCRIBE commodity.gold.unified_data",
    "4. Checking schema"
)
if results:
    print(f"   ✅ Schema columns:")
    for row in results[:10]:  # Show first 10 columns
        col_name, col_type = row[0], row[1]
        print(f"      - {col_name}: {col_type}")

# 5. Check weather_data array
results = run_query(
    """SELECT
        AVG(size(weather_data)) as avg_regions,
        MIN(size(weather_data)) as min_regions,
        MAX(size(weather_data)) as max_regions
    FROM commodity.gold.unified_data""",
    "5. Checking weather_data array structure"
)
if results:
    avg, min_val, max_val = float(results[0][0]), int(results[0][1]), int(results[0][2])
    print(f"   ✅ Weather regions per row: avg={avg:.1f}, min={min_val}, max={max_val}")

# 6. Check gdelt_themes array
results = run_query(
    """SELECT
        AVG(COALESCE(size(gdelt_themes), 0)) as avg_themes,
        MIN(COALESCE(size(gdelt_themes), 0)) as min_themes,
        MAX(COALESCE(size(gdelt_themes), 0)) as max_themes
    FROM commodity.gold.unified_data""",
    "6. Checking gdelt_themes array structure"
)
if results and results[0][0] is not None:
    avg, min_val, max_val = float(results[0][0]), int(results[0][1]), int(results[0][2])
    print(f"   ✅ GDELT themes per row: avg={avg:.1f}, min={min_val}, max={max_val}")
elif results:
    print(f"   ⚠️  GDELT themes may have NULL values")

# 7. Check for nulls in key columns
results = run_query(
    """SELECT
        SUM(CASE WHEN date IS NULL THEN 1 ELSE 0 END) as null_dates,
        SUM(CASE WHEN commodity IS NULL THEN 1 ELSE 0 END) as null_commodity,
        SUM(CASE WHEN close IS NULL THEN 1 ELSE 0 END) as null_close
    FROM commodity.gold.unified_data""",
    "7. Checking for NULLs in key columns"
)
if results:
    null_dates, null_commodity, null_close = int(results[0][0]), int(results[0][1]), int(results[0][2])
    if null_dates == 0 and null_commodity == 0 and null_close == 0:
        print(f"   ✅ No NULLs in key columns (date, commodity, close)")
    else:
        print(f"   ❌ Found NULLs: dates={null_dates}, commodity={null_commodity}, close={null_close}")

print("\n" + "=" * 80)
print("VALIDATION COMPLETE")
print("=" * 80)
print("\n💡 For comprehensive validation (47+ checks), upload and run:")
print("   research_agent/infrastructure/tests/validate_gold_databricks.py")
print("   on unity-catalog-cluster in Databricks UI")
