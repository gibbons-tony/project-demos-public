"""
Weather Forecast Fetcher Lambda Function

Fetches 16-day weather forecasts from Open-Meteo for all coffee/sugar regions.
Runs daily via CloudWatch EventBridge to continuously collect REAL forecasts.

⚠️ IMPORTANT: This collects REAL forecasts with NO data leakage (starting 2025-11-06+).
   Historical forecasts (2015-2025) are SYNTHETIC with data leakage.
   See: research_agent/infrastructure/WEATHER_FORECAST_LIMITATION.md

Environment Variables:
- S3_BUCKET: S3 bucket name (e.g., 'groundtruth-capstone')
- S3_PREFIX: S3 prefix (e.g., 'landing/weather_forecast')
- REGIONS_CONFIG: S3 path to region coordinates JSON (config/region_coordinates.json)
"""

import json
import boto3
import requests
from datetime import datetime, timedelta
from typing import List, Dict
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client('s3')

# Open-Meteo API endpoint
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

def lambda_handler(event, context):
    """
    Fetch 14-day weather forecasts for all regions and store in S3.
    """
    try:
        # Get configuration
        s3_bucket = event.get('s3_bucket', 'commodity-data')
        s3_prefix = event.get('s3_prefix', 'weather-forecast')

        # Load region coordinates
        regions = load_region_coordinates(s3_bucket)
        logger.info(f"Loaded {len(regions)} regions")

        # Today's forecast date
        forecast_date = datetime.now().date()

        # Fetch forecasts for all regions
        all_forecasts = []
        successful = 0
        failed = 0

        for region in regions:
            try:
                forecast_data = fetch_forecast_for_region(
                    region['name'],
                    region['latitude'],
                    region['longitude'],
                    forecast_date
                )
                all_forecasts.extend(forecast_data)
                successful += 1
                logger.info(f"✅ {region['name']}: {len(forecast_data)} forecast days")
            except Exception as e:
                failed += 1
                logger.error(f"❌ {region['name']}: {str(e)}")

        # Write to S3
        if all_forecasts:
            s3_key = write_to_s3(all_forecasts, s3_bucket, s3_prefix, forecast_date)
            logger.info(f"✅ Wrote {len(all_forecasts)} forecast records to {s3_key}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Weather forecast fetch complete',
                'forecast_date': str(forecast_date),
                'regions_successful': successful,
                'regions_failed': failed,
                'total_forecasts': len(all_forecasts),
                's3_key': s3_key if all_forecasts else None
            })
        }

    except Exception as e:
        logger.error(f"Lambda execution failed: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }


def load_region_coordinates(s3_bucket: str) -> List[Dict]:
    """
    Load region coordinates from S3.

    Expected format:
    [
        {
            "region": "Antigua_Guatemala",
            "latitude": 14.5600,
            "longitude": -90.7347,
            "commodity": "Coffee",
            "description": "...",
            "elevation_m": 1500,
            "country": "Guatemala"
        },
        ...
    ]
    """
    try:
        # Load from S3
        config_key = 'config/region_coordinates.json'
        response = s3_client.get_object(Bucket=s3_bucket, Key=config_key)
        coordinates = json.loads(response['Body'].read().decode('utf-8'))

        # Normalize format for compatibility
        return [
            {
                'name': r['region'],
                'latitude': r['latitude'],
                'longitude': r['longitude'],
                'commodity': r['commodity'],
                'description': r.get('description', ''),
                'country': r.get('country', '')
            }
            for r in coordinates
        ]
    except Exception as e:
        logger.error(f"Failed to load coordinates from S3: {e}")
        raise


def fetch_forecast_for_region(region_name: str, latitude: float, longitude: float,
                               forecast_date: datetime.date) -> List[Dict]:
    """
    Fetch 16-day weather forecast from Open-Meteo for a single region.

    Returns list of forecast records with schema:
    - forecast_date: Date forecast was made
    - target_date: Date being forecasted
    - days_ahead: 1-16
    - region: Region name
    - temp_max_c, temp_min_c, temp_mean_c
    - precipitation_mm
    - humidity_pct
    - wind_speed_kmh
    """
    params = {
        'latitude': latitude,
        'longitude': longitude,
        'daily': [
            'temperature_2m_max',
            'temperature_2m_min',
            'precipitation_sum',
            'relative_humidity_2m_mean',
            'wind_speed_10m_max'
        ],
        'forecast_days': 16,
        'timezone': 'UTC'
    }

    response = requests.get(OPEN_METEO_URL, params=params, timeout=10)
    response.raise_for_status()

    data = response.json()
    daily = data['daily']

    forecasts = []
    for i in range(len(daily['time'])):
        target_date = datetime.strptime(daily['time'][i], '%Y-%m-%d').date()
        days_ahead = (target_date - forecast_date).days

        temp_max = daily['temperature_2m_max'][i]
        temp_min = daily['temperature_2m_min'][i]
        temp_mean = (temp_max + temp_min) / 2 if temp_max and temp_min else None

        forecast = {
            'forecast_date': str(forecast_date),
            'target_date': str(target_date),
            'days_ahead': days_ahead,
            'region': region_name,
            'temp_max_c': round(temp_max, 2) if temp_max else None,
            'temp_min_c': round(temp_min, 2) if temp_min else None,
            'temp_mean_c': round(temp_mean, 2) if temp_mean else None,
            'precipitation_mm': round(daily['precipitation_sum'][i], 2) if daily['precipitation_sum'][i] else 0.0,
            'humidity_pct': round(daily['relative_humidity_2m_mean'][i], 2) if daily['relative_humidity_2m_mean'][i] else None,
            'wind_speed_kmh': round(daily['wind_speed_10m_max'][i], 2) if daily['wind_speed_10m_max'][i] else None,
            'ingest_ts': datetime.now().isoformat(),
            # Metadata: Mark as REAL forecast (not synthetic)
            'is_synthetic': False,
            'has_data_leakage': False,
            'generation_method': 'open_meteo_api'
        }

        forecasts.append(forecast)

    return forecasts


def write_to_s3(forecasts: List[Dict], bucket: str, prefix: str,
                forecast_date: datetime.date) -> str:
    """
    Write forecast data to S3 in JSON Lines format (one JSON object per line).

    S3 path: s3://{bucket}/{prefix}/year={YYYY}/month={MM}/day={DD}/forecast.jsonl
    """
    # Partition by forecast date
    year = forecast_date.year
    month = f"{forecast_date.month:02d}"
    day = f"{forecast_date.day:02d}"

    s3_key = f"{prefix}/year={year}/month={month}/day={day}/forecast.jsonl"

    # Convert to JSON Lines format
    jsonl_content = '\n'.join(json.dumps(f) for f in forecasts)

    # Upload to S3
    s3_client.put_object(
        Bucket=bucket,
        Key=s3_key,
        Body=jsonl_content.encode('utf-8'),
        ContentType='application/x-ndjson'
    )

    return s3_key


# For local testing
if __name__ == '__main__':
    # Test event
    test_event = {
        's3_bucket': 'commodity-data',
        's3_prefix': 'weather-forecast'
    }

    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))
