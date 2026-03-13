"""
Run ImputationTransformer test on Databricks using REST API.

Steps:
1. Upload notebook to Databricks workspace
2. Create one-time job to run on ml-testing-cluster
3. Run job and wait for completion
4. Retrieve and display results
"""
import os
import sys
import time
import base64
import requests
from dotenv import load_dotenv

# Load credentials
load_dotenv('../infra/.env')

DATABRICKS_HOST = os.environ['DATABRICKS_HOST']
DATABRICKS_TOKEN = os.environ['DATABRICKS_TOKEN']

# Remove https:// if present
if DATABRICKS_HOST.startswith('https://'):
    DATABRICKS_HOST = DATABRICKS_HOST.replace('https://', '')

BASE_URL = f"https://{DATABRICKS_HOST}/api/2.0"
HEADERS = {
    "Authorization": f"Bearer {DATABRICKS_TOKEN}",
    "Content-Type": "application/json"
}

print("="*80)
print("Databricks ImputationTransformer Test Runner")
print("="*80)

# Step 1: Read notebook file and convert to base64
print("\n1. Reading notebook file...")
notebook_path = "notebooks/test_imputation_pipeline.py"

with open(notebook_path, 'r') as f:
    notebook_content = f.read()

# Base64 encode
notebook_base64 = base64.b64encode(notebook_content.encode()).decode()
print(f"   ✓ Read {len(notebook_content)} characters from {notebook_path}")

# Step 2: Create folder and upload notebook to workspace
print("\n2. Creating workspace folder...")
folder_path = "/Shared/forecast_agent"

# Try to create folder (ignore if exists)
folder_payload = {
    "path": folder_path
}
response = requests.post(
    f"{BASE_URL}/workspace/mkdirs",
    headers=HEADERS,
    json=folder_payload
)

if response.status_code == 200:
    print(f"   ✓ Created folder: {folder_path}")
elif "already exists" in response.text.lower():
    print(f"   ✓ Folder already exists: {folder_path}")
else:
    print(f"   ⚠️ Folder creation: {response.status_code} - {response.text}")

print("\n3. Uploading notebook to Databricks workspace...")
workspace_path = "/Shared/forecast_agent/test_imputation_pipeline"

upload_payload = {
    "path": workspace_path,
    "content": notebook_base64,
    "language": "PYTHON",
    "overwrite": True,
    "format": "SOURCE"
}

response = requests.post(
    f"{BASE_URL}/workspace/import",
    headers=HEADERS,
    json=upload_payload
)

if response.status_code == 200:
    print(f"   ✓ Uploaded to workspace: {workspace_path}")
else:
    print(f"   ❌ Upload failed: {response.status_code}")
    print(f"   Response: {response.text}")
    sys.exit(1)

# Step 4: Get cluster ID for ml-testing-cluster
print("\n4. Finding ml-testing-cluster...")
response = requests.get(
    f"{BASE_URL}/clusters/list",
    headers=HEADERS
)

if response.status_code != 200:
    print(f"   ❌ Failed to list clusters: {response.status_code}")
    print(f"   Response: {response.text}")
    sys.exit(1)

clusters = response.json().get('clusters', [])
testing_cluster = None

for cluster in clusters:
    if cluster['cluster_name'] == 'ml-testing-cluster':
        testing_cluster = cluster
        break

if not testing_cluster:
    print(f"   ❌ ml-testing-cluster not found!")
    print(f"   Available clusters:")
    for c in clusters:
        print(f"     - {c['cluster_name']} (state: {c['state']})")
    sys.exit(1)

cluster_id = testing_cluster['cluster_id']
cluster_state = testing_cluster['state']
print(f"   ✓ Found ml-testing-cluster (ID: {cluster_id}, state: {cluster_state})")

# Step 5: Start cluster if not running
if cluster_state != 'RUNNING':
    print(f"\n5. Starting cluster (current state: {cluster_state})...")
    response = requests.post(
        f"{BASE_URL}/clusters/start",
        headers=HEADERS,
        json={"cluster_id": cluster_id}
    )

    if response.status_code != 200:
        print(f"   ❌ Failed to start cluster: {response.status_code}")
        print(f"   Response: {response.text}")
        sys.exit(1)

    print(f"   ✓ Cluster start requested, waiting...")

    # Wait for cluster to start (max 5 minutes)
    for i in range(60):
        time.sleep(5)
        response = requests.get(
            f"{BASE_URL}/clusters/get?cluster_id={cluster_id}",
            headers=HEADERS
        )
        state = response.json()['state']
        print(f"   ... {state} ({i*5}s elapsed)")

        if state == 'RUNNING':
            print(f"   ✓ Cluster is running!")
            break
        elif state in ['TERMINATING', 'TERMINATED', 'ERROR']:
            print(f"   ❌ Cluster in bad state: {state}")
            sys.exit(1)
    else:
        print(f"   ❌ Timeout waiting for cluster to start")
        sys.exit(1)
else:
    print(f"\n5. Cluster already running ✓")

# Step 6: Create and run one-time job
print("\n6. Creating one-time job...")
job_payload = {
    "run_name": "ImputationTransformer Test",
    "existing_cluster_id": cluster_id,
    "notebook_task": {
        "notebook_path": workspace_path
    },
    "timeout_seconds": 3600
}

response = requests.post(
    f"{BASE_URL}/jobs/runs/submit",
    headers=HEADERS,
    json=job_payload
)

if response.status_code != 200:
    print(f"   ❌ Failed to create job: {response.status_code}")
    print(f"   Response: {response.text}")
    sys.exit(1)

run_id = response.json()['run_id']
print(f"   ✓ Job created (run_id: {run_id})")

# Step 7: Wait for job to complete
print(f"\n7. Waiting for job to complete...")
print(f"   View live: https://{DATABRICKS_HOST}/#job/{run_id}")

for i in range(120):  # Max 10 minutes
    time.sleep(5)

    response = requests.get(
        f"{BASE_URL}/jobs/runs/get?run_id={run_id}",
        headers=HEADERS
    )

    if response.status_code != 200:
        print(f"   ❌ Failed to get job status: {response.status_code}")
        break

    run_data = response.json()
    state = run_data['state']['life_cycle_state']

    if state in ['PENDING', 'RUNNING']:
        result_state = run_data['state'].get('state_message', '')
        print(f"   ... {state} ({i*5}s elapsed) - {result_state}")
    elif state == 'TERMINATED':
        result = run_data['state']['result_state']
        print(f"\n   ✓ Job completed: {result}")

        if result == 'SUCCESS':
            print(f"\n{'='*80}")
            print("Test Results: ✅ SUCCESS")
            print(f"{'='*80}")
            print(f"\nRun details: https://{DATABRICKS_HOST}/#job/{run_id}")
            print(f"\nTo view full output:")
            print(f"1. Go to https://{DATABRICKS_HOST}")
            print(f"2. Click 'Workflows' → 'Job runs'")
            print(f"3. Find run_id {run_id}")
            print(f"4. View notebook output")
        else:
            print(f"\n{'='*80}")
            print(f"Test Results: ❌ {result}")
            print(f"{'='*80}")
            print(f"\nError details: https://{DATABRICKS_HOST}/#job/{run_id}")
        break
    else:
        print(f"   Unexpected state: {state}")
        break
else:
    print(f"   ⚠️ Timeout after 10 minutes")

print(f"\n{'='*80}")
print("Test run complete!")
print(f"{'='*80}")
