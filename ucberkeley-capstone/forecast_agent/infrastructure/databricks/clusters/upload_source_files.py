#!/usr/bin/env python3
"""
Upload forecast_agent source files to Databricks workspace.

Alternative lightweight approach: upload .py files directly to workspace
and use importlib pattern (like DS261 graph features demo).

This script uploads the ml_lib package to:
    /Workspace/Shared/forecast_agent/ml_lib/

Usage in notebooks:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "imputation",
        "/Workspace/Shared/forecast_agent/ml_lib/transformers/imputation.py"
    )
    imputation = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(imputation)

    imputer = imputation.create_production_imputer()

Usage:
    cd forecast_agent
    python infrastructure/databricks/clusters/upload_source_files.py
"""

import os
import sys
import requests
import base64
from pathlib import Path

# Databricks credentials
DATABRICKS_HOST = os.environ.get('DATABRICKS_HOST')
DATABRICKS_TOKEN = os.environ.get('DATABRICKS_TOKEN')

if not DATABRICKS_HOST or not DATABRICKS_TOKEN:
    print("❌ Error: DATABRICKS_HOST and DATABRICKS_TOKEN required")
    sys.exit(1)

BASE_URL = f"{DATABRICKS_HOST}/api/2.0"
HEADERS = {
    "Authorization": f"Bearer {DATABRICKS_TOKEN}",
    "Content-Type": "application/json"
}

WORKSPACE_BASE = "/Shared/forecast_agent"

print("=" * 80)
print("Uploading forecast_agent Source Files to Databricks Workspace")
print("=" * 80)

def upload_file(local_path: str, workspace_path: str):
    """Upload a single Python file to workspace."""
    with open(local_path, 'r') as f:
        content = f.read()

    # Convert to base64
    content_b64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')

    payload = {
        "path": workspace_path,
        "content": content_b64,
        "language": "PYTHON",
        "overwrite": True,
        "format": "SOURCE"
    }

    response = requests.post(
        f"{BASE_URL}/workspace/import",
        headers=HEADERS,
        json=payload
    )

    if response.status_code == 200:
        print(f"   ✓ {workspace_path}")
        return True
    else:
        print(f"   ❌ Failed: {workspace_path}")
        print(f"      {response.text}")
        return False

def create_folder(workspace_path: str):
    """Create a workspace folder."""
    payload = {"path": workspace_path}
    response = requests.post(f"{BASE_URL}/workspace/mkdirs", headers=HEADERS, json=payload)
    return response.status_code == 200

# Create folder structure
print("\n1. Creating folder structure...")
folders = [
    f"{WORKSPACE_BASE}",
    f"{WORKSPACE_BASE}/ml_lib",
    f"{WORKSPACE_BASE}/ml_lib/transformers",
    f"{WORKSPACE_BASE}/ml_lib/cross_validation",
]

for folder in folders:
    create_folder(folder)
    print(f"   ✓ {folder}")

# Upload ml_lib files
print("\n2. Uploading ml_lib package files...")

files_to_upload = [
    ("ml_lib/__init__.py", f"{WORKSPACE_BASE}/ml_lib/__init__.py"),
    ("ml_lib/transformers/__init__.py", f"{WORKSPACE_BASE}/ml_lib/transformers/__init__.py"),
    ("ml_lib/transformers/imputation.py", f"{WORKSPACE_BASE}/ml_lib/transformers/imputation.py"),
    ("ml_lib/cross_validation/__init__.py", f"{WORKSPACE_BASE}/ml_lib/cross_validation/__init__.py"),
    ("ml_lib/cross_validation/data_loader.py", f"{WORKSPACE_BASE}/ml_lib/cross_validation/data_loader.py"),
]

success_count = 0
for local_path, workspace_path in files_to_upload:
    if upload_file(local_path, workspace_path):
        success_count += 1

print(f"\n✅ Uploaded {success_count}/{len(files_to_upload)} files")

print("\n" + "=" * 80)
print("Usage in Databricks notebooks:")
print("=" * 80)
print("""
# Load imputation module
import importlib.util

imputation_path = "/Workspace/Shared/forecast_agent/ml_lib/transformers/imputation.py"
spec = importlib.util.spec_from_file_location("imputation", imputation_path)
imputation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(imputation)

# Use it
imputer = imputation.create_production_imputer()
df_imputed = imputer.transform(df_raw)
""")
print("=" * 80)
