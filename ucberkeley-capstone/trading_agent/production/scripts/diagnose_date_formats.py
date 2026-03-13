"""
Diagnostic script to check actual date formats in prices and prediction matrices
"""
import sys
sys.path.insert(0, '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent')

import pandas as pd
import pickle
from pyspark.sql import SparkSession

# Initialize Spark
spark = SparkSession.builder.getOrCreate()

commodity = 'coffee'
model_version = 'synthetic_acc90'

print("=" * 80)
print("DATE FORMAT DIAGNOSTIC")
print("=" * 80)

# Load prices
print(f"\n1. Loading prices from prices_prepared_{commodity}...")
prices = spark.table(f'commodity.trading_agent.prices_prepared_{commodity}').toPandas()
print(f"   Loaded {len(prices)} rows")
print(f"   First 5 date values:")
for i, date in enumerate(prices['date'].head()):
    print(f"     [{i}] {date} | Type: {type(date)} | Repr: {repr(date)}")

# Normalize prices dates
prices['date'] = pd.to_datetime(prices['date']).dt.normalize()
print(f"\n   After normalization:")
for i, date in enumerate(prices['date'].head()):
    print(f"     [{i}] {date} | Type: {type(date)} | Repr: {repr(date)}")

# Load prediction matrices
print(f"\n2. Loading prediction matrices for {model_version}...")
matrix_path = f'/Volumes/commodity/trading_agent/files/prediction_matrices_{commodity}_{model_version}.pkl'
with open(matrix_path, 'rb') as f:
    prediction_matrices = pickle.load(f)

print(f"   Loaded {len(prediction_matrices)} prediction matrices")
print(f"   First 5 dictionary keys:")
sample_keys = list(prediction_matrices.keys())[:5]
for i, key in enumerate(sample_keys):
    print(f"     [{i}] {key} | Type: {type(key)} | Repr: {repr(key)}")

# Check overlap
print(f"\n3. Checking overlap...")
pred_keys_set = set(prediction_matrices.keys())
price_dates_set = set(prices['date'].tolist())

print(f"   Prediction matrix keys (first 5): {sorted(list(pred_keys_set))[:5]}")
print(f"   Price dates (first 5): {sorted(list(price_dates_set))[:5]}")

overlap = pred_keys_set.intersection(price_dates_set)
print(f"   Overlap: {len(overlap)} dates")
print(f"   Match rate: {len(overlap) / len(pred_keys_set) * 100:.1f}%")

if len(overlap) > 0:
    print(f"   Sample overlapping dates: {sorted(list(overlap))[:5]}")
else:
    print(f"\n   NO OVERLAP FOUND!")
    print(f"   Sample pred key: {sample_keys[0]} ({type(sample_keys[0])})")
    print(f"   Sample price date: {prices['date'].iloc[0]} ({type(prices['date'].iloc[0])})")

    # Try to understand the difference
    pred_sample = sample_keys[0]
    price_sample = prices['date'].iloc[0]

    if isinstance(pred_sample, pd.Timestamp) and isinstance(price_sample, pd.Timestamp):
        print(f"\n   Both are Timestamps. Comparing:")
        print(f"     pred_sample == price_sample: {pred_sample == price_sample}")
        print(f"     pred_sample.normalize() == price_sample.normalize(): {pred_sample.normalize() == price_sample.normalize()}")
        print(f"     str(pred_sample): {str(pred_sample)}")
        print(f"     str(price_sample): {str(price_sample)}")

print("\n" + "=" * 80)
