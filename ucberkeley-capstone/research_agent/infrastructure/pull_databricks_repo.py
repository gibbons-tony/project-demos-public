#!/usr/bin/env python3
"""
Pull latest changes from GitHub into Databricks repo
"""
import requests
import os
from pathlib import Path

# Databricks configuration
DATABRICKS_HOST = "https://dbc-fd7b00f3-7a6d.cloud.databricks.com"
REPO_ID = "3188992172744791"

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

# Pull latest changes
url = f"{DATABRICKS_HOST}/api/2.0/repos/{REPO_ID}"
headers = {
    "Authorization": f"Bearer {DATABRICKS_TOKEN}",
    "Content-Type": "application/json"
}

# Update to main branch (this pulls latest)
payload = {"branch": "main"}

print(f"Pulling latest changes from GitHub to Databricks repo {REPO_ID}...")
response = requests.patch(url, headers=headers, json=payload)

if response.status_code == 200:
    result = response.json()
    print(f"✓ Successfully pulled latest changes")
    print(f"  Repo: {result.get('path', 'N/A')}")
    print(f"  Branch: {result.get('branch', 'N/A')}")
    print(f"  Head commit: {result.get('head_commit_id', 'N/A')[:8]}")
else:
    print(f"✗ Failed to pull changes: {response.status_code}")
    print(f"  {response.text}")
    exit(1)
