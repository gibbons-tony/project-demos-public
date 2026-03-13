#!/usr/bin/env python3
"""
List all Databricks repos to find the correct ID
"""
import requests
import os
from pathlib import Path

# Databricks configuration
DATABRICKS_HOST = "https://dbc-fd7b00f3-7a6d.cloud.databricks.com"

# Get token
DATABRICKS_TOKEN = os.environ.get("DATABRICKS_TOKEN")
if not DATABRICKS_TOKEN:
    config_path = Path(__file__).parent.parent.parent / "infra" / ".databrickscfg"
    if config_path.exists():
        with open(config_path, "r") as f:
            for line in f:
                if line.startswith("token"):
                    DATABRICKS_TOKEN = line.split("=")[1].strip()
                    break

if not DATABRICKS_TOKEN:
    print("ERROR: DATABRICKS_TOKEN not found")
    exit(1)

# List all repos
url = f"{DATABRICKS_HOST}/api/2.0/repos"
headers = {
    "Authorization": f"Bearer {DATABRICKS_TOKEN}",
    "Content-Type": "application/json"
}

print("Listing all Databricks repos...")
response = requests.get(url, headers=headers)

if response.status_code == 200:
    result = response.json()
    repos = result.get("repos", [])
    print(f"\nFound {len(repos)} repo(s):\n")
    for repo in repos:
        print(f"ID: {repo.get('id')}")
        print(f"  Path: {repo.get('path')}")
        print(f"  URL: {repo.get('url')}")
        print(f"  Branch: {repo.get('branch')}")
        print(f"  Head commit: {repo.get('head_commit_id', 'N/A')[:8]}")
        print()
else:
    print(f"✗ Failed to list repos: {response.status_code}")
    print(f"  {response.text}")
    exit(1)
