#!/usr/bin/env python3
"""
Check data types of silver files saved by gdelt-silver-backfill lambda.
"""
import awswrangler as wr
import pandas as pd

# Read the silver files
print("Reading silver files from S3...")
df = wr.s3.read_parquet(
    path='s3://groundtruth-capstone/processed/gdelt/silver/gdelt_wide/',
    dataset=True
)

print(f"\nTotal rows: {len(df)}")
print(f"Total columns: {len(df.columns)}")
print(f"Dates: {df['article_date'].unique()}")
print(f"Commodities: {df['commodity'].unique()}")

# Check for group_ALL columns
all_cols = [c for c in df.columns if 'group_ALL_' in c]
print(f"\ngroup_ALL columns found: {len(all_cols)}")
print(f"  {all_cols[:5]}...")

# Check count columns
count_cols = [c for c in df.columns if '_count' in c]
print(f"\nCount columns: {len(count_cols)}")
print("\nCount column data types:")
for col in count_cols[:10]:
    print(f"  {col:50s} {str(df[col].dtype):15s}")

# Check tone columns
tone_cols = [c for c in df.columns if 'tone_' in c and '_count' not in c]
print(f"\nTone columns: {len(tone_cols)}")
print("\nTone column data types:")
for col in tone_cols[:10]:
    print(f"  {col:50s} {str(df[col].dtype):15s}")

# Find any wrong types
wrong_count_types = [c for c in count_cols if str(df[c].dtype) != 'int64']
wrong_tone_types = [c for c in tone_cols if str(df[c].dtype) != 'float64']

print("\n" + "="*70)
if not wrong_count_types and not wrong_tone_types and len(all_cols) > 0:
    print("✅ TEST PASSED")
    print(f"  - All {len(count_cols)} count columns are int64")
    print(f"  - All {len(tone_cols)} tone columns are float64")
    print(f"  - group_ALL columns exist ({len(all_cols)} found)")
else:
    print("❌ TEST FAILED")
    if wrong_count_types:
        print(f"\n  Wrong count types ({len(wrong_count_types)}):")
        for col in wrong_count_types[:5]:
            print(f"    {col}: {df[col].dtype} (should be int64)")
    if wrong_tone_types:
        print(f"\n  Wrong tone types ({len(wrong_tone_types)}):")
        for col in wrong_tone_types[:5]:
            print(f"    {col}: {df[col].dtype} (should be float64)")
    if len(all_cols) == 0:
        print(f"\n  Missing group_ALL columns!")

print("="*70)

# Show sample data
print("\nSample row (coffee):")
coffee_row = df[df['commodity'] == 'coffee'].iloc[0]
print(f"  article_date: {coffee_row['article_date']}")
print(f"  commodity: {coffee_row['commodity']}")
print(f"  group_ALL_count: {coffee_row['group_ALL_count']} (type: {type(coffee_row['group_ALL_count']).__name__})")
print(f"  group_ALL_tone_avg: {coffee_row['group_ALL_tone_avg']} (type: {type(coffee_row['group_ALL_tone_avg']).__name__})")
