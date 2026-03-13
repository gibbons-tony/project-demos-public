#!/usr/bin/env python3
"""
Deploy forecast_agent package to Databricks cluster.

This script:
1. Builds a wheel file from forecast_agent
2. Uploads the wheel to DBFS
3. Installs the library on ml-testing-cluster
4. Restarts the cluster to activate the library

Usage:
    cd forecast_agent
    python infrastructure/databricks/clusters/deploy_package.py

Requirements:
    - Databricks credentials in environment (DATABRICKS_HOST, DATABRICKS_TOKEN)
    - setuptools and wheel packages installed locally
"""

import os
import sys
import subprocess
import requests
import json
import time
import base64

# Databricks credentials
DATABRICKS_HOST = os.environ.get('DATABRICKS_HOST')
DATABRICKS_TOKEN = os.environ.get('DATABRICKS_TOKEN')

if not DATABRICKS_HOST or not DATABRICKS_TOKEN:
    print("❌ Error: DATABRICKS_HOST and DATABRICKS_TOKEN environment variables required")
    print("   Load from ../infra/.env: set -a && source ../infra/.env && set +a")
    sys.exit(1)

BASE_URL = f"{DATABRICKS_HOST}/api/2.0"
HEADERS = {
    "Authorization": f"Bearer {DATABRICKS_TOKEN}",
    "Content-Type": "application/json"
}

CLUSTER_NAME = "ml-testing-cluster"
DBFS_PATH = "dbfs:/FileStore/forecast_agent/forecast_agent-0.1.0-py3-none-any.whl"

print("=" * 80)
print("Deploying forecast_agent Package to Databricks")
print("=" * 80)

# Step 1: Build wheel file
print("\n1. Building wheel file...")
build_cmd = [sys.executable, "setup.py", "bdist_wheel"]
result = subprocess.run(build_cmd, capture_output=True, text=True)

if result.returncode != 0:
    print(f"❌ Failed to build wheel:")
    print(result.stderr)
    sys.exit(1)

# Find the wheel file
wheel_dir = "dist"
wheel_files = [f for f in os.listdir(wheel_dir) if f.endswith('.whl')]
if not wheel_files:
    print(f"❌ No wheel file found in {wheel_dir}/")
    sys.exit(1)

wheel_file = os.path.join(wheel_dir, wheel_files[0])
print(f"   ✓ Built wheel: {wheel_file}")

# Step 2: Upload wheel to DBFS
print("\n2. Uploading wheel to DBFS...")

# Read wheel file as bytes
with open(wheel_file, 'rb') as f:
    wheel_bytes = f.read()

# Encode as base64
wheel_b64 = base64.b64encode(wheel_bytes).decode('utf-8')

# Upload to DBFS (create)
dbfs_file_path = "/FileStore/forecast_agent/forecast_agent-0.1.0-py3-none-any.whl"
create_payload = {
    "path": dbfs_file_path,
    "overwrite": True
}

# Use DBFS API 1.2 for file upload
response = requests.post(
    f"{DATABRICKS_HOST}/api/2.0/dbfs/put",
    headers=HEADERS,
    json={
        "path": dbfs_file_path,
        "contents": wheel_b64,
        "overwrite": True
    }
)

if response.status_code != 200:
    print(f"❌ Failed to upload wheel to DBFS:")
    print(response.text)
    sys.exit(1)

print(f"   ✓ Uploaded to: {DBFS_PATH}")

# Step 3: Find cluster
print(f"\n3. Finding {CLUSTER_NAME}...")
response = requests.get(f"{BASE_URL}/clusters/list", headers=HEADERS)
if response.status_code != 200:
    print(f"❌ Failed to list clusters: {response.text}")
    sys.exit(1)

clusters = response.json().get('clusters', [])
cluster = next((c for c in clusters if c['cluster_name'] == CLUSTER_NAME), None)

if not cluster:
    print(f"❌ Cluster '{CLUSTER_NAME}' not found")
    sys.exit(1)

cluster_id = cluster['cluster_id']
print(f"   ✓ Found cluster: {CLUSTER_NAME} (ID: {cluster_id})")

# Step 4: Install library on cluster
print("\n4. Installing library on cluster...")

install_payload = {
    "cluster_id": cluster_id,
    "libraries": [
        {
            "whl": DBFS_PATH
        }
    ]
}

response = requests.post(
    f"{BASE_URL}/libraries/install",
    headers=HEADERS,
    json=install_payload
)

if response.status_code != 200:
    print(f"❌ Failed to install library:")
    print(response.text)
    sys.exit(1)

print(f"   ✓ Library installation requested")

# Step 5: Restart cluster to activate library
print("\n5. Restarting cluster to activate library...")

# Check current state
response = requests.get(f"{BASE_URL}/clusters/get?cluster_id={cluster_id}", headers=HEADERS)
current_state = response.json().get('state')

if current_state == 'RUNNING':
    # Restart running cluster
    response = requests.post(
        f"{BASE_URL}/clusters/restart",
        headers=HEADERS,
        json={"cluster_id": cluster_id}
    )

    if response.status_code != 200:
        print(f"❌ Failed to restart cluster:")
        print(response.text)
        sys.exit(1)

    print(f"   ✓ Cluster restart requested")
    print(f"   ⏳ Waiting for restart to complete...")

    # Wait for restart
    max_wait = 600  # 10 minutes
    elapsed = 0
    while elapsed < max_wait:
        time.sleep(10)
        elapsed += 10

        response = requests.get(f"{BASE_URL}/clusters/get?cluster_id={cluster_id}", headers=HEADERS)
        state = response.json().get('state')

        if state == 'RUNNING':
            print(f"   ✓ Cluster is running with new library!")
            break
        elif state in ['TERMINATED', 'ERROR']:
            print(f"   ⚠️  Cluster is {state}, start manually to activate library")
            break

        print(f"   ... {state} ({elapsed}s elapsed)")

else:
    print(f"   ℹ️  Cluster is {current_state}, library will activate on next start")

print("\n" + "=" * 80)
print("✅ Package Deployment Complete!")
print("=" * 80)
print()
print("The forecast_agent package is now available on ml-testing-cluster.")
print("You can import it in notebooks:")
print()
print("    from forecast_agent.ml_lib.transformers import create_production_imputer")
print("    from forecast_agent.ml_lib.cross_validation.data_loader import GoldDataLoader")
print()
print("=" * 80)
