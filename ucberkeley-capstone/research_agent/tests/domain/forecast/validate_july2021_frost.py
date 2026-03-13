"""
Validate July 2021 Brazil Frost Event in Corrected Weather Data

This script validates that the corrected weather_v2 data properly captures
the July 2021 frost event in Sul de Minas, Brazil - a critical weather event
that significantly impacted coffee prices.

Expected:
- v1 (wrong coordinates): Missed the frost (Belo Horizonte is too far north)
- v2 (correct coordinates): Captured the frost (Sul de Minas actual location)

References:
- Event dates: July 18-20, 2021
- Location: Sul de Minas coffee region (-20.3155, -45.4108)
- Impact: Temperatures dropped to -3°C to -1°C, damaging coffee crops
"""

import os
import json
import boto3
from datetime import datetime, timedelta
from databricks import sql
from dotenv import load_dotenv
import pathlib

# Load credentials from .env (NO HARDCODED CREDENTIALS!)
env_path = pathlib.Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

DATABRICKS_HOST = os.getenv("DATABRICKS_HOST")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN")
DATABRICKS_HTTP_PATH = os.getenv("DATABRICKS_HTTP_PATH")

if not all([DATABRICKS_HOST, DATABRICKS_TOKEN, DATABRICKS_HTTP_PATH]):
    print("ERROR: Missing credentials in .env")
    exit(1)

S3_BUCKET = "groundtruth-capstone"
WEATHER_V2_PREFIX = "landing/weather_v2"

# Event details
FROST_DATES = ["2021-07-18", "2021-07-19", "2021-07-20"]
FROST_REGION = "Minas_Gerais"  # Sul de Minas
EXPECTED_TEMP_THRESHOLD = 5.0  # Temperatures should be below 5°C during frost


def check_s3_weather_v2():
    """Check if weather_v2 data exists in S3 for July 2021"""
    print("\n" + "=" * 80)
    print("Checking S3 for weather_v2 July 2021 data")
    print("=" * 80)

    s3 = boto3.client('s3')

    frost_data_found = []
    for date in FROST_DATES:
        year, month, day = date.split('-')
        prefix = f"{WEATHER_V2_PREFIX}/year={year}/month={month}/day={day}/"

        try:
            response = s3.list_objects_v2(
                Bucket=S3_BUCKET,
                Prefix=prefix,
                MaxKeys=10
            )

            if 'Contents' in response:
                print(f"✅ Found data for {date}: {len(response['Contents'])} files")
                frost_data_found.append(date)

                # Download and check one file to see the data
                first_file = response['Contents'][0]['Key']
                obj = s3.get_object(Bucket=S3_BUCKET, Key=first_file)
                content = obj['Body'].read().decode('utf-8')

                # Parse first line
                first_record = json.loads(content.split('\n')[0])
                if first_record.get('region') == FROST_REGION:
                    temp_min = first_record.get('temperature_min_c')
                    print(f"   📍 Minas Gerais min temp: {temp_min}°C")
                    if temp_min and temp_min < EXPECTED_TEMP_THRESHOLD:
                        print(f"   ❄️  FROST DETECTED! Temp below {EXPECTED_TEMP_THRESHOLD}°C")
            else:
                print(f"⚠️  No data found for {date}")
        except Exception as e:
            print(f"❌ Error checking {date}: {e}")

    return frost_data_found


def validate_weather_v1_vs_v2():
    """Compare weather v1 (wrong coords) vs v2 (correct coords) for frost event"""
    print("\n" + "=" * 80)
    print("Validating July 2021 Frost: v1 vs v2")
    print("=" * 80)

    connection = sql.connect(
        server_hostname=DATABRICKS_HOST.replace("https://", ""),
        http_path=DATABRICKS_HTTP_PATH,
        access_token=DATABRICKS_TOKEN
    )
    cursor = connection.cursor()

    # Check weather v1 (should MISS the frost)
    print("\n" + "-" * 80)
    print("Weather v1 (Belo Horizonte - WRONG coordinates)")
    print("-" * 80)

    v1_query = """
    SELECT
        date,
        region,
        temperature_min_c,
        temperature_max_c,
        temperature_mean_c
    FROM commodity.bronze.weather
    WHERE region = 'Minas_Gerais'
      AND date >= '2021-07-18'
      AND date <= '2021-07-20'
    ORDER BY date
    """

    cursor.execute(v1_query)
    v1_results = cursor.fetchall()

    v1_detected_frost = False
    for row in v1_results:
        date, region, temp_min, temp_max, temp_mean = row
        print(f"  {date}: Min={temp_min}°C, Max={temp_max}°C, Mean={temp_mean}°C")
        if temp_min and temp_min < EXPECTED_TEMP_THRESHOLD:
            v1_detected_frost = True
            print(f"    ❄️  Frost temperature detected")

    if not v1_detected_frost:
        print("  ⚠️  NO FROST DETECTED in v1 (as expected - wrong location)")

    # Check weather v2 (should CAPTURE the frost)
    print("\n" + "-" * 80)
    print("Weather v2 (Sul de Minas - CORRECT coordinates)")
    print("-" * 80)

    # Check if weather_v2 table exists yet
    try:
        v2_query = """
        SELECT
            date,
            region,
            temperature_min_c,
            temperature_max_c,
            temperature_mean_c,
            latitude,
            longitude
        FROM commodity.bronze.weather_v2
        WHERE region = 'Minas_Gerais'
          AND date >= '2021-07-18'
          AND date <= '2021-07-20'
        ORDER BY date
        """

        cursor.execute(v2_query)
        v2_results = cursor.fetchall()

        v2_detected_frost = False
        for row in v2_results:
            date, region, temp_min, temp_max, temp_mean, lat, lon = row
            print(f"  {date}: Min={temp_min}°C, Max={temp_max}°C, Mean={temp_mean}°C")
            print(f"    Coordinates: ({lat}, {lon})")
            if temp_min and temp_min < EXPECTED_TEMP_THRESHOLD:
                v2_detected_frost = True
                print(f"    ❄️  FROST DETECTED! Temperature: {temp_min}°C")

        if v2_detected_frost:
            print("  ✅ FROST CAPTURED in v2 (correct location)!")
        else:
            print("  ⚠️  NO FROST DETECTED in v2 (unexpected)")

        # Summary
        print("\n" + "=" * 80)
        print("VALIDATION SUMMARY")
        print("=" * 80)
        print(f"v1 (Wrong coordinates): {'❌ Missed frost' if not v1_detected_frost else '⚠️  Unexpectedly detected frost'}")
        print(f"v2 (Correct coordinates): {'✅ Captured frost' if v2_detected_frost else '❌ Failed to capture frost'}")

        if not v1_detected_frost and v2_detected_frost:
            print("\n🎉 SUCCESS! Corrected coordinates properly capture the July 2021 frost event!")
            print("   This validates that weather_v2 data is more accurate for price forecasting.")
        else:
            print("\n⚠️  Unexpected results - review the data and coordinates")

    except Exception as e:
        if "TABLE_OR_VIEW_NOT_FOUND" in str(e) or "not found" in str(e).lower():
            print("  ⚠️  Table commodity.bronze.weather_v2 does not exist yet")
            print("  ℹ️  Run weather_v2_delta_migration.sql to create the table")
        else:
            print(f"  ❌ Error: {e}")

    cursor.close()
    connection.close()


def main():
    print("=" * 80)
    print("July 2021 Brazil Frost Validation")
    print("=" * 80)
    print("\nValidating that corrected weather coordinates capture the")
    print("July 18-20, 2021 frost event in Sul de Minas coffee region.")
    print("\nExpected results:")
    print("  - v1 (Belo Horizonte): ❌ Missed the frost (too far north)")
    print("  - v2 (Sul de Minas):   ✅ Captured the frost (correct location)")

    # Check S3 data
    frost_data = check_s3_weather_v2()

    if len(frost_data) == len(FROST_DATES):
        print(f"\n✅ All {len(FROST_DATES)} frost dates found in S3")
    else:
        print(f"\n⚠️  Only {len(frost_data)}/{len(FROST_DATES)} frost dates found in S3")
        print("   Weather backfill may still be running...")

    # Validate against existing weather tables
    validate_weather_v1_vs_v2()

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
