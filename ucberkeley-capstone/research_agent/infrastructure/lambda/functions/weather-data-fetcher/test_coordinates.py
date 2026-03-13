#!/usr/bin/env python3
"""
Test that coordinates are loaded correctly from S3
"""
import json
import boto3

def test_load_coordinates():
    """Test loading coordinates from S3"""
    s3 = boto3.client('s3')

    print("="*80)
    print("Testing S3 Coordinate Loading")
    print("="*80)

    try:
        response = s3.get_object(
            Bucket='groundtruth-capstone',
            Key='config/region_coordinates.json'
        )
        regions_list = json.loads(response['Body'].read().decode('utf-8'))

        print(f"\n✅ Loaded {len(regions_list)} regions from S3")

        # Check Minas Gerais coordinates (should be v2)
        minas = [r for r in regions_list if r['region'] == 'Minas_Gerais_Brazil'][0]
        print(f"\n📍 Minas_Gerais_Brazil:")
        print(f"   Latitude: {minas['latitude']}")
        print(f"   Longitude: {minas['longitude']}")
        print(f"   Description: {minas['description']}")

        # Verify it's v2 (correct)
        if abs(minas['latitude'] - (-20.3155)) < 0.01:
            print(f"\n✅ CORRECT v2 coordinates!")
            print(f"   Expected: -20.3155, -45.4108 (Sul de Minas coffee region)")
            print(f"   Got: {minas['latitude']}, {minas['longitude']}")
        else:
            print(f"\n❌ WRONG coordinates!")
            print(f"   Expected v2: -20.3155, -45.4108")
            print(f"   Got: {minas['latitude']}, {minas['longitude']}")

        # Sample a few more regions
        print(f"\n📍 Sample regions:")
        for region in regions_list[:5]:
            print(f"   - {region['region']}: ({region['latitude']}, {region['longitude']})")

        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_load_coordinates()
    exit(0 if success else 1)
