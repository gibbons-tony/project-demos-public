"""
Unity Catalog Query Workaround

This notebook provides a workaround for the /etc/hosts redirect issue
that causes spark.sql() and spark.table() to hang indefinitely.

Use this approach until the PrivateLink configuration is fixed.
"""

# Install databricks-sql-connector if not already installed
# %pip install databricks-sql-connector

from databricks import sql
import pandas as pd
import os

# Connection parameters (NO HARDCODED CREDENTIALS!)
from dotenv import load_dotenv
load_dotenv()

DATABRICKS_HOST = os.getenv("DATABRICKS_HOST")
DATABRICKS_HTTP_PATH = os.getenv("DATABRICKS_HTTP_PATH")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN")

if not all([DATABRICKS_HOST, DATABRICKS_TOKEN, DATABRICKS_HTTP_PATH]):
    raise ValueError("Missing env vars! Create research_agent/infrastructure/.env")

# ============================================================================
# WORKAROUND: Use databricks-sql-connector instead of spark.sql()
# ============================================================================

def query_unity_catalog(sql_query):
    """
    Execute a query against Unity Catalog using the SQL connector.

    This bypasses the broken /etc/hosts redirect that causes spark.sql() to hang.

    Args:
        sql_query: SQL query string

    Returns:
        pandas DataFrame with results
    """
    connection = sql.connect(
        server_hostname=DATABRICKS_HOST,
        http_path=DATABRICKS_HTTP_PATH,
        access_token=DATABRICKS_TOKEN
    )

    cursor = connection.cursor()
    cursor.execute(sql_query)

    # Fetch results
    columns = [desc[0] for desc in cursor.description]
    results = cursor.fetchall()

    cursor.close()
    connection.close()

    # Convert to pandas DataFrame
    df = pd.DataFrame(results, columns=columns)
    return df

# ============================================================================
# EXAMPLE 1: Query commodity.forecast.distributions
# ============================================================================

print("Example 1: Query commodity.forecast.distributions")
print("=" * 80)

query = """
SELECT *
FROM commodity.forecast.distributions
LIMIT 10
"""

df_distributions = query_unity_catalog(query)
print(f"Retrieved {len(df_distributions)} rows")
print(df_distributions.head())

# ============================================================================
# EXAMPLE 2: Query commodity.bronze.weather
# ============================================================================

print("\nExample 2: Query commodity.bronze.weather")
print("=" * 80)

query = """
SELECT *
FROM commodity.bronze.weather
WHERE date >= '2024-01-01'
LIMIT 10
"""

df_weather = query_unity_catalog(query)
print(f"Retrieved {len(df_weather)} rows")
print(df_weather.head())

# ============================================================================
# EXAMPLE 3: Aggregation query
# ============================================================================

print("\nExample 3: Count records by commodity")
print("=" * 80)

query = """
SELECT commodity, COUNT(*) as count
FROM commodity.forecast.distributions
GROUP BY commodity
ORDER BY count DESC
"""

df_counts = query_unity_catalog(query)
print(df_counts)

# ============================================================================
# CONVERTING TO SPARK DATAFRAME (if needed)
# ============================================================================

# If you need a Spark DataFrame for further processing, convert the pandas DataFrame:
# spark_df = spark.createDataFrame(df_distributions)
# spark_df.show()

print("\n" + "=" * 80)
print("USAGE INSTRUCTIONS")
print("=" * 80)
print("""
1. Copy this code to a Databricks notebook
2. Replace spark.sql("...") with query_unity_catalog("...")
3. Replace spark.table("commodity.forecast.distributions")
   with query_unity_catalog("SELECT * FROM commodity.forecast.distributions")

LIMITATIONS:
- This workaround uses SQL Warehouse, not compute cluster
- More expensive than direct Spark access
- Good for querying, but not for long-running transformations

WHEN TO USE THIS:
- Reading data from Unity Catalog tables
- Ad-hoc queries and exploration
- Trading agent data loading

WHEN NOT TO USE THIS:
- Large ETL jobs (use direct S3 access instead)
- Complex Spark transformations (read via this, then process with Spark)
""")
