"""
Validate region_coordinates.json against actual Databricks weather regions
"""
from databricks import sql
import os
import json

host = os.getenv("DATABRICKS_HOST", "https://dbc-fd7b00f3-7a6d.cloud.databricks.com")
token = os.getenv("DATABRICKS_TOKEN")
http_path = os.getenv("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/3cede8561503a13c")

# Load coordinates file
with open('research_agent/infrastructure/lambda/functions/weather-data-fetcher/region_coordinates.json', 'r') as f:
    coordinates = json.load(f)

coordinate_regions = {r['region'] for r in coordinates}

# Get actual regions from Databricks
connection = sql.connect(
    server_hostname=host.replace("https://", ""),
    http_path=http_path,
    access_token=token
)
cursor = connection.cursor()

cursor.execute("SELECT DISTINCT region FROM commodity.bronze.weather ORDER BY region")
db_regions = {row[0] for row in cursor.fetchall()}

print("="*80)
print("REGION COORDINATE VALIDATION")
print("="*80)
print()

print(f"Regions in coordinates file: {len(coordinate_regions)}")
print(f"Regions in Databricks:       {len(db_regions)}")
print()

# Check for missing regions
missing_in_coords = db_regions - coordinate_regions
missing_in_db = coordinate_regions - db_regions

if missing_in_coords:
    print("❌ MISSING IN COORDINATES FILE:")
    for region in sorted(missing_in_coords):
        print(f"   - {region}")
    print()
else:
    print("✅ All Databricks regions have coordinates")
    print()

if missing_in_db:
    print("⚠️  EXTRA IN COORDINATES FILE (not in Databricks):")
    for region in sorted(missing_in_db):
        print(f"   - {region}")
    print()
else:
    print("✅ All coordinate regions exist in Databricks")
    print()

# Show coordinate summary
print("COORDINATE SUMMARY:")
print("-"*80)
coffee_count = sum(1 for r in coordinates if r['commodity'] == 'Coffee')
sugar_count = sum(1 for r in coordinates if r['commodity'] == 'Sugar')
print(f"  Coffee regions: {coffee_count}")
print(f"  Sugar regions:  {sugar_count}")
print(f"  Total:          {len(coordinates)}")
print()

# Show sample coordinates
print("SAMPLE COORDINATES:")
print("-"*80)
for region in list(coordinates)[:5]:
    print(f"  {region['region']:<40} ({region['latitude']:.4f}, {region['longitude']:.4f})")
    print(f"    → {region['description']}, {region['country']}")
print()

print("="*80)
if not missing_in_coords and not missing_in_db:
    print("✅ VALIDATION PASSED - All regions mapped!")
else:
    print("⚠️  VALIDATION WARNINGS - Review missing regions above")
print("="*80)

cursor.close()
connection.close()
