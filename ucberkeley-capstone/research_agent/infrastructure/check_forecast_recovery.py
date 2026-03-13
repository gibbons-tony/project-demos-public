#!/usr/bin/env python3
"""Check if we can recover dropped forecast tables via Delta time travel"""
import os
from databricks import sql
from dotenv import load_dotenv

env_path = '../../infra/.env'
load_dotenv(env_path)

token = os.getenv('DATABRICKS_TOKEN')
server_hostname = os.getenv('DATABRICKS_HOST').replace('https://', '')
http_path = os.getenv('DATABRICKS_HTTP_PATH')

connection = sql.connect(
    server_hostname=server_hostname,
    http_path=http_path,
    access_token=token
)
cursor = connection.cursor()

# Check if we can see table history
tables = ['distributions', 'forecast_actuals', 'forecast_metadata', 'point_forecasts', 'trained_models']

for table in tables:
    print(f"\n{table}:")
    try:
        cursor.execute(f"DESCRIBE HISTORY commodity.forecast.{table}")
        history = cursor.fetchall()
        print(f"  Found {len(history)} history entries")
        if history:
            print(f"  Latest: {history[0]}")
    except Exception as e:
        print(f"  ERROR: {e}")

cursor.close()
connection.close()
