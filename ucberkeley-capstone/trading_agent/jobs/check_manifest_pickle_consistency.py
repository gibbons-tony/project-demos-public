"""
Check if pickle files are consistent with manifest contents
"""
from pyspark.sql import SparkSession
import os
import json

spark = SparkSession.builder.getOrCreate()

print("="*80)
print("CHECKING MANIFEST VS PICKLE FILE CONSISTENCY")
print("="*80)

volume_path = "/dbfs/production/files"

# Read coffee manifest
manifest_path = f"{volume_path}/forecast_manifest_coffee.json"
print(f"\n1. Reading manifest: {manifest_path}")

try:
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)

    print(f"   ✓ Manifest loaded")
    print(f"   Commodity: {manifest.get('commodity', 'N/A')}")
    print(f"   Created: {manifest.get('created_at', 'N/A')}")

    # List models in manifest
    models_in_manifest = manifest.get('models', [])
    print(f"\n   Models listed in manifest ({len(models_in_manifest)}):")
    for model_info in models_in_manifest:
        model_name = model_info.get('model_version', 'unknown')
        status = model_info.get('status', 'unknown')
        print(f"     - {model_name}: {status}")

except Exception as e:
    print(f"   ❌ Error reading manifest: {e}")
    models_in_manifest = []

# List actual pickle files
print(f"\n2. Checking pickle files in {volume_path}:")
try:
    files = os.listdir(volume_path)
    pickle_files = [f for f in files if f.endswith('_real.pkl') and 'coffee' in f and 'prediction_matrices' in f]

    print(f"   Found {len(pickle_files)} coffee prediction pickle files:")
    for pf in sorted(pickle_files):
        size_mb = os.path.getsize(os.path.join(volume_path, pf)) / (1024 * 1024)
        # Extract model name from filename: prediction_matrices_coffee_{model}_real.pkl
        model = pf.replace('prediction_matrices_coffee_', '').replace('_real.pkl', '')
        print(f"     - {model}: {pf} ({size_mb:.2f} MB)")

except Exception as e:
    print(f"   ❌ Error listing pickle files: {e}")
    pickle_files = []

# Compare
print(f"\n3. Consistency Check:")

if models_in_manifest:
    manifest_models = set(m.get('model_version', '') for m in models_in_manifest)
    pickle_models = set(pf.replace('prediction_matrices_coffee_', '').replace('_real.pkl', '') for pf in pickle_files)

    print(f"   Models in manifest: {sorted(manifest_models)}")
    print(f"   Models with pickle files: {sorted(pickle_models)}")

    # Check for mismatches
    in_manifest_not_pickle = manifest_models - pickle_models
    in_pickle_not_manifest = pickle_models - manifest_models

    if in_manifest_not_pickle:
        print(f"\n   ⚠️  In manifest but NO pickle file:")
        for m in sorted(in_manifest_not_pickle):
            print(f"       - {m}")

    if in_pickle_not_manifest:
        print(f"\n   ⚠️  Has pickle file but NOT in manifest:")
        for m in sorted(in_pickle_not_manifest):
            print(f"       - {m}")

    if not in_manifest_not_pickle and not in_pickle_not_manifest:
        print(f"\n   ✓ Perfectly consistent!")
else:
    print(f"   ⚠️  Cannot compare - manifest not readable")

print("\n" + "="*80)
print("CONCLUSION")
print("="*80)
print("\nIf there are mismatches, the optimizer may fail when trying to load")
print("models that don't have corresponding pickle files.")
