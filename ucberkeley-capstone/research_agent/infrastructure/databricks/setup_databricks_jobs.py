"""
Setup Databricks Jobs for Data Pipeline

Creates scheduled jobs for:
1. Daily Data Refresh - Load new data from S3 landing to bronze tables
2. Silver Layer Update - Rebuild unified_data from bronze tables
3. Data Quality Validation - Check for nulls, completeness, freshness
"""

import os
import sys
import requests
import json
from dotenv import load_dotenv

# Load credentials
load_dotenv(dotenv_path="../.env")
DATABRICKS_HOST = os.getenv("DATABRICKS_HOST")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN")

if not all([DATABRICKS_HOST, DATABRICKS_TOKEN]):
    print("ERROR: Missing DATABRICKS_HOST or DATABRICKS_TOKEN in .env")
    sys.exit(1)

# API endpoint
API_BASE = f"{DATABRICKS_HOST}/api/2.1/jobs"
HEADERS = {"Authorization": f"Bearer {DATABRICKS_TOKEN}"}


def create_job(job_config):
    """Create a Databricks job"""
    response = requests.post(
        f"{API_BASE}/create",
        headers=HEADERS,
        json=job_config
    )
    if response.status_code == 200:
        job_id = response.json().get("job_id")
        print(f"✅ Created job: {job_config['name']} (ID: {job_id})")
        return job_id
    else:
        print(f"❌ Failed to create job: {job_config['name']}")
        print(f"   Error: {response.text}")
        return None


def main():
    print("=" * 80)
    print("DATABRICKS JOB SETUP")
    print("=" * 80)

    # Job 1: Daily Bronze Layer Refresh
    bronze_refresh_job = {
        "name": "Daily Bronze Layer Refresh",
        "description": "Load latest data from S3 landing zone to bronze tables",
        "tasks": [
            {
                "task_key": "refresh_market_data",
                "description": "Refresh market data from S3",
                "sql_task": {
                    "query": {
                        "query": """
                        COPY INTO commodity.bronze.market
                        FROM 's3://groundtruth-capstone/landing/market/'
                        FILEFORMAT = JSON
                        FORMAT_OPTIONS ('mergeSchema' = 'true')
                        COPY_OPTIONS ('mergeSchema' = 'true')
                        """
                    },
                    "warehouse_id": os.getenv("DATABRICKS_HTTP_PATH", "").split("/")[-1]
                }
            },
            {
                "task_key": "refresh_weather_data",
                "description": "Refresh weather data from S3",
                "depends_on": [{"task_key": "refresh_market_data"}],
                "sql_task": {
                    "query": {
                        "query": """
                        COPY INTO commodity.bronze.weather
                        FROM 's3://groundtruth-capstone/landing/weather/'
                        FILEFORMAT = JSON
                        FORMAT_OPTIONS ('mergeSchema' = 'true')
                        COPY_OPTIONS ('mergeSchema' = 'true')
                        """
                    },
                    "warehouse_id": os.getenv("DATABRICKS_HTTP_PATH", "").split("/")[-1]
                }
            },
            {
                "task_key": "refresh_vix_data",
                "description": "Refresh VIX data from S3",
                "depends_on": [{"task_key": "refresh_market_data"}],
                "sql_task": {
                    "query": {
                        "query": """
                        COPY INTO commodity.bronze.vix
                        FROM 's3://groundtruth-capstone/landing/vix/'
                        FILEFORMAT = JSON
                        FORMAT_OPTIONS ('mergeSchema' = 'true')
                        COPY_OPTIONS ('mergeSchema' = 'true')
                        """
                    },
                    "warehouse_id": os.getenv("DATABRICKS_HTTP_PATH", "").split("/")[-1]
                }
            }
        ],
        "schedule": {
            "quartz_cron_expression": "0 0 2 * * ?",  # Daily at 2 AM
            "timezone_id": "America/Los_Angeles",
            "pause_status": "UNPAUSED"
        },
        "email_notifications": {},
        "timeout_seconds": 3600,
        "max_concurrent_runs": 1
    }

    # Job 2: Silver Layer Update
    silver_update_job = {
        "name": "Silver Layer - Unified Data Update",
        "description": "Rebuild unified_data table from bronze layer",
        "tasks": [
            {
                "task_key": "rebuild_unified_data",
                "description": "Rebuild unified_data from bronze tables",
                "sql_task": {
                    "query": {
                        "query": """
                        -- This will be replaced with actual unified_data rebuild SQL
                        INSERT OVERWRITE commodity.silver.unified_data
                        SELECT
                            m.date,
                            m.commodity,
                            w.region,
                            m.price_close,
                            w.temperature_mean_c,
                            w.precipitation_sum_mm,
                            v.vix,
                            CURRENT_TIMESTAMP() as updated_at
                        FROM commodity.bronze.market m
                        LEFT JOIN commodity.bronze.weather w
                            ON m.date = w.date
                            AND m.commodity = w.commodity
                        LEFT JOIN commodity.bronze.vix v
                            ON m.date = v.date
                        WHERE m.date >= CURRENT_DATE() - INTERVAL '90' DAY
                        """
                    },
                    "warehouse_id": os.getenv("DATABRICKS_HTTP_PATH", "").split("/")[-1]
                }
            },
            {
                "task_key": "optimize_unified_data",
                "description": "Optimize unified_data table",
                "depends_on": [{"task_key": "rebuild_unified_data"}],
                "sql_task": {
                    "query": {
                        "query": "OPTIMIZE commodity.silver.unified_data ZORDER BY (date, commodity, region)"
                    },
                    "warehouse_id": os.getenv("DATABRICKS_HTTP_PATH", "").split("/")[-1]
                }
            }
        ],
        "schedule": {
            "quartz_cron_expression": "0 0 3 * * ?",  # Daily at 3 AM (after bronze refresh)
            "timezone_id": "America/Los_Angeles",
            "pause_status": "UNPAUSED"
        },
        "email_notifications": {},
        "timeout_seconds": 1800,
        "max_concurrent_runs": 1
    }

    # Job 3: Data Quality Validation
    dq_validation_job = {
        "name": "Data Quality Validation",
        "description": "Validate data quality across all layers",
        "tasks": [
            {
                "task_key": "check_bronze_nulls",
                "description": "Check for null values in bronze tables",
                "sql_task": {
                    "query": {
                        "query": """
                        SELECT
                            'market' as table_name,
                            COUNT(*) as total_rows,
                            COUNT(*) - COUNT(date) as date_nulls,
                            COUNT(*) - COUNT(price_close) as price_nulls
                        FROM commodity.bronze.market
                        WHERE date >= CURRENT_DATE() - INTERVAL '7' DAY
                        UNION ALL
                        SELECT
                            'weather' as table_name,
                            COUNT(*) as total_rows,
                            COUNT(*) - COUNT(date) as date_nulls,
                            COUNT(*) - COUNT(temperature_mean_c) as temp_nulls
                        FROM commodity.bronze.weather
                        WHERE date >= CURRENT_DATE() - INTERVAL '7' DAY
                        """
                    },
                    "warehouse_id": os.getenv("DATABRICKS_HTTP_PATH", "").split("/")[-1]
                }
            },
            {
                "task_key": "check_data_freshness",
                "description": "Check if data is fresh (updated recently)",
                "depends_on": [{"task_key": "check_bronze_nulls"}],
                "sql_task": {
                    "query": {
                        "query": """
                        SELECT
                            'market' as table_name,
                            MAX(date) as latest_date,
                            DATEDIFF(CURRENT_DATE(), MAX(date)) as days_stale
                        FROM commodity.bronze.market
                        UNION ALL
                        SELECT
                            'unified_data' as table_name,
                            MAX(date) as latest_date,
                            DATEDIFF(CURRENT_DATE(), MAX(date)) as days_stale
                        FROM commodity.silver.unified_data
                        """
                    },
                    "warehouse_id": os.getenv("DATABRICKS_HTTP_PATH", "").split("/")[-1]
                }
            }
        ],
        "schedule": {
            "quartz_cron_expression": "0 0 4 * * ?",  # Daily at 4 AM (after silver update)
            "timezone_id": "America/Los_Angeles",
            "pause_status": "UNPAUSED"
        },
        "email_notifications": {},
        "timeout_seconds": 600,
        "max_concurrent_runs": 1
    }

    # Create jobs
    jobs = [bronze_refresh_job, silver_update_job, dq_validation_job]
    created_jobs = []

    for job in jobs:
        print(f"\nCreating job: {job['name']}...")
        job_id = create_job(job)
        if job_id:
            created_jobs.append((job['name'], job_id))

    # Summary
    print("\n" + "=" * 80)
    print("SETUP COMPLETE!")
    print("=" * 80)
    print(f"\n✅ Created {len(created_jobs)} Databricks jobs:")
    for name, job_id in created_jobs:
        print(f"   - {name} (ID: {job_id})")

    print("\n📋 Job Schedule:")
    print("   2:00 AM - Bronze Layer Refresh (load from S3)")
    print("   3:00 AM - Silver Layer Update (rebuild unified_data)")
    print("   4:00 AM - Data Quality Validation")

    print("\n🔗 View jobs in Databricks:")
    print(f"   {DATABRICKS_HOST}/#job/list")
    print("=" * 80)


if __name__ == "__main__":
    main()
