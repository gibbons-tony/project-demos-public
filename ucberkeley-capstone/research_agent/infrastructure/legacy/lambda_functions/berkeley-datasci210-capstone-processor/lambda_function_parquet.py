"""
AWS Lambda Function for GDELT GKG Data Collection - PARQUET VERSION
Handles both historical backfill and daily incremental updates
Writes directly to Parquet bronze layer (no JSONL intermediate)
Optimized for commodity price prediction (coffee/sugar)
"""

import json
import boto3
import requests
import zipfile
from io import BytesIO, StringIO
import csv
from datetime import datetime, timedelta
from typing import List, Dict, Set
import logging
import sys
import pandas as pd
import awswrangler as wr

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Increase CSV field size limit to handle large GDELT fields
csv.field_size_limit(sys.maxsize)

# Initialize AWS clients
s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
sqs = boto3.client('sqs')

# Configuration
S3_BUCKET = 'groundtruth-capstone'
S3_BRONZE_PATH = 's3://groundtruth-capstone/processed/gdelt/bronze/gdelt/'
TRACKING_TABLE = 'groundtruth-capstone-file-tracking'
SQS_QUEUE_URL = 'https://sqs.us-west-2.amazonaws.com/534150427458/groundtruth-gdelt-backfill-queue'

# Incremental mode: Check for missing files from this many days back
INCREMENTAL_LOOKBACK_DAYS = 90

# Commodity-specific filters
CORE_THEMES = {
    'AGRICULTURE', 'FOOD_STAPLE', 'FOOD_SECURITY'
}

DRIVER_THEMES = {
    'NATURAL_DISASTER', 'CLIMATE_CHANGE', 'TAX_DISEASE', 'TAX_PLANTDISEASE',
    'TAX_PESTS', 'ECON_SUBSIDIES', 'WB_2044_RURAL_WATER', 'STRIKE',
    'ECON_UNIONS', 'CRISIS_LOGISTICS', 'BLOCKADE', 'DELAY', 'CLOSURE',
    'BORDER', 'GENERAL_HEALTH', 'ECON_DEBT', 'ECON_INTEREST_RATES',
    'ECON_CURRENCY_EXCHANGE_RATE', 'ECON_STOCKMARKET', 'ECON_COST_OF_LIVING',
    'ENERGY', 'OIL', 'ECON_FREETRADE', 'ECON_TRADE_DISPUTE', 'TAX_TARIFFS',
    'LEGISLATION', 'GOV_REFORM', 'NEGOTIATIONS', 'ALLIANCE', 'CEASEFIRE',
    'STATE_OF_EMERGENCY', 'ELECTION', 'CORRUPTION', 'GENERAL_GOVERNMENT',
    'ECON_EARNINGSREPORT', 'ECON_IPO'
}

COMMODITY_KEYWORDS = {
    'coffee', 'arabica', 'robusta', 'sugar', 'sugarcane', 'sugar beet'
}

DRIVER_KEYWORDS = {
    'drought', 'frost', 'flood', 'rainfall', 'la nina', 'el nino',
    'fertilizer', 'pesticide', 'water scarcity', 'labor shortage',
    'port congestion', 'shipping', 'inflation', 'recession',
    'ethanol', 'biofuel', 'crude oil', 'tariff', 'trade deal',
    'geopolitical', 'political instability'
}

ALL_THEMES = CORE_THEMES | DRIVER_THEMES
ALL_KEYWORDS = COMMODITY_KEYWORDS | DRIVER_KEYWORDS


def lambda_handler(event, context):
    """
    Main Lambda handler - routes to initialization, backfill, or incremental update
    """
    mode = event.get('mode', 'incremental')

    try:
        if mode == 'initialize_backfill':
            start_date = datetime.strptime(event['start_date'], '%Y-%m-%d')
            end_date = datetime.strptime(event['end_date'], '%Y-%m-%d')
            return initialize_backfill(start_date, end_date)
        elif mode == 'backfill':
            result = process_historical_backfill()
            return {
                'statusCode': 200,
                'body': json.dumps(result)
            }
        else:
            lookback_start_date = event.get('lookback_start_date')
            result = process_incremental_update(lookback_start_date)
            return {
                'statusCode': 200,
                'body': json.dumps(result)
            }
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def process_incremental_update(lookback_start_date: str = None, use_master_list: bool = True) -> Dict:
    """
    Self-healing incremental update: Check for missing files using master list or timestamp generation.

    Args:
        lookback_start_date: Optional start date (YYYY-MM-DD) for lookback window
        use_master_list: If True, sync against GDELT master file list (recommended)
    """
    logger.info(f"Starting incremental update (master_list={'enabled' if use_master_list else 'disabled'})")

    yesterday = datetime.utcnow() - timedelta(days=1)

    if lookback_start_date:
        start_date = datetime.strptime(lookback_start_date, '%Y-%m-%d')
    else:
        start_date = yesterday - timedelta(days=INCREMENTAL_LOOKBACK_DAYS)

    logger.info(f"Checking for missing files from {start_date.strftime('%Y-%m-%d')} to {yesterday.strftime('%Y-%m-%d')}")

    # Get list of files from master list or generate URLs
    if use_master_list:
        file_urls = sync_with_master_file_list(start_date, yesterday)
        logger.info(f"Fetched {len(file_urls)} files from GDELT master list")
    else:
        file_urls = generate_file_urls(start_date, yesterday)
        logger.info(f"Generated {len(file_urls)} file URLs from timestamps")

    # Get already processed files
    processed_files = get_all_processed_files()
    files_to_process = []

    for url in file_urls:
        file_name = url.split('/')[-1]
        if file_name not in processed_files:
            files_to_process.append({'url': url, 'name': file_name})

    logger.info(f"Found {len(files_to_process)} unprocessed files")
    files_to_process.reverse()  # Newest first

    max_files_per_run = 50
    if len(files_to_process) > max_files_per_run:
        files_to_process = files_to_process[:max_files_per_run]

    processed_count = 0
    filtered_records = 0
    total_records = 0

    for file_info in files_to_process:
        try:
            stats = download_filter_and_write_parquet(file_info['url'], file_info['name'])
            processed_count += 1
            filtered_records += stats['filtered']
            total_records += stats['total']
            mark_file_processed(file_info['name'], status='success')
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                mark_file_processed(file_info['name'], status='404')
            else:
                logger.error(f"HTTP error processing {file_info['name']}: {e}")
        except Exception as e:
            logger.error(f"Error processing {file_info['name']}: {e}", exc_info=True)

    return {
        'processed_files': processed_count,
        'total_records': total_records,
        'filtered_records': filtered_records,
        'filter_rate': f"{(filtered_records/total_records*100):.2f}%" if total_records > 0 else "0%"
    }


def get_all_processed_files() -> Set[str]:
    """Query DynamoDB once to get all processed file names"""
    logger.info("Querying DynamoDB for all processed files...")
    try:
        table = dynamodb.Table(TRACKING_TABLE)
        processed_files = set()

        response = table.scan(ProjectionExpression='file_name')
        processed_files.update(item['file_name'] for item in response.get('Items', []))

        while 'LastEvaluatedKey' in response:
            response = table.scan(
                ProjectionExpression='file_name',
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            processed_files.update(item['file_name'] for item in response.get('Items', []))

        logger.info(f"Found {len(processed_files)} already-processed files")
        return processed_files
    except Exception as e:
        logger.error(f"Error querying processed files: {e}")
        return set()


def sync_with_master_file_list(start_date: datetime, end_date: datetime) -> List[str]:
    """
    Fetch GDELT master file list and filter by date range.
    More reliable than generating URLs since it reflects actual available files.

    Args:
        start_date: Start date for filtering files
        end_date: End date for filtering files

    Returns:
        List of file URLs from master list within date range
    """
    logger.info("Fetching GDELT master file list...")

    try:
        # Fetch master file list
        master_list_url = 'http://data.gdeltproject.org/gdeltv2/masterfilelist.txt'
        response = requests.get(master_list_url, timeout=30)
        response.raise_for_status()

        # Parse master list (format: size hash url)
        file_urls = []
        start_timestamp = int(start_date.timestamp())
        end_timestamp = int(end_date.timestamp())

        for line in response.text.strip().split('\n'):
            parts = line.split()
            if len(parts) < 3:
                continue

            url = parts[2]
            filename = url.split('/')[-1]

            # Filter for GKG files only
            if not filename.endswith('.gkg.csv.zip'):
                continue

            # Extract timestamp from filename (format: YYYYMMDDHHMMSS.gkg.csv.zip)
            try:
                timestamp_str = filename[:14]  # YYYYMMDDHHMMSS
                file_date = datetime.strptime(timestamp_str, '%Y%m%d%H%M%S')
                file_timestamp = int(file_date.timestamp())

                # Check if within date range
                if start_timestamp <= file_timestamp <= end_timestamp:
                    file_urls.append(url)
            except (ValueError, IndexError):
                continue

        logger.info(f"Found {len(file_urls)} GKG files in master list for date range")
        return file_urls

    except Exception as e:
        logger.error(f"Error fetching master file list: {e}")
        logger.warning("Falling back to URL generation")
        return generate_file_urls(start_date, end_date)


def initialize_backfill(start_date: datetime, end_date: datetime) -> Dict:
    """Initialize backfill by queuing missing files to SQS"""
    today = datetime.utcnow().date()
    if end_date.date() > today:
        end_date = datetime.combine(today, datetime.min.time())

    logger.info(f"Initializing backfill from {start_date} to {end_date}")

    processed_files = get_all_processed_files()
    all_file_urls = generate_file_urls(start_date, end_date)
    missing_urls = [url for url in all_file_urls if url.split('/')[-1] not in processed_files]

    logger.info(f"Found {len(missing_urls)} files to download")

    batch_size = 10
    sent_count = 0

    for i in range(0, len(missing_urls), batch_size):
        batch = missing_urls[i:i + batch_size]
        entries = [{'Id': str(j), 'MessageBody': url} for j, url in enumerate(batch)]

        try:
            sqs.send_message_batch(QueueUrl=SQS_QUEUE_URL, Entries=entries)
            sent_count += len(batch)
        except Exception as e:
            logger.error(f"Error sending batch to SQS: {e}")
            raise

    return {
        'statusCode': 200,
        'body': json.dumps({
            'total_missing_files': len(missing_urls),
            'queue_url': SQS_QUEUE_URL
        })
    }


def process_historical_backfill() -> Dict:
    """Process backfill batch from SQS queue"""
    logger.info("Processing backfill batch from SQS")

    processed_count = 0
    filtered_records = 0
    total_records = 0
    all_messages = []

    for _ in range(5):
        try:
            response = sqs.receive_message(
                QueueUrl=SQS_QUEUE_URL,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=1
            )
            messages = response.get('Messages', [])
            all_messages.extend(messages)
            if len(messages) < 10:
                break
        except Exception as e:
            logger.error(f"Error receiving messages: {e}")
            raise

    if not all_messages:
        return {'processed_files': 0, 'filtered_records': 0}

    for message in all_messages:
        url = message['Body']
        file_name = url.split('/')[-1]

        try:
            stats = download_filter_and_write_parquet(url, file_name)
            processed_count += 1
            filtered_records += stats['filtered']
            total_records += stats['total']
            mark_file_processed(file_name, status='success')

            sqs.delete_message(QueueUrl=SQS_QUEUE_URL, ReceiptHandle=message['ReceiptHandle'])
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                mark_file_processed(file_name, status='404')
                sqs.delete_message(QueueUrl=SQS_QUEUE_URL, ReceiptHandle=message['ReceiptHandle'])
        except Exception as e:
            logger.error(f"Error processing {file_name}: {e}", exc_info=True)

    return {
        'processed_files': processed_count,
        'total_records': total_records,
        'filtered_records': filtered_records
    }


def generate_file_urls(start_date: datetime, end_date: datetime) -> List[str]:
    """Generate GDELT GKG file URLs for date range"""
    urls = []
    current = start_date

    while current <= end_date:
        for hour in range(24):
            for minute in [0, 15, 30, 45]:
                timestamp = current.replace(hour=hour, minute=minute, second=0)
                url = f"http://data.gdeltproject.org/gdeltv2/{timestamp.strftime('%Y%m%d%H%M%S')}.gkg.csv.zip"
                urls.append(url)
        current += timedelta(days=1)

    return urls


def download_filter_and_write_parquet(url: str, file_name: str) -> Dict:
    """
    Download GDELT file, filter, transform to bronze schema, write as Parquet
    Combines filtering + bronze transformation in one step
    """
    logger.info(f"Processing file: {file_name}")

    # Download and decompress
    response = requests.get(url, timeout=60, stream=True)
    response.raise_for_status()

    zip_data = BytesIO(response.content)

    with zipfile.ZipFile(zip_data, 'r') as zip_ref:
        csv_filename = zip_ref.namelist()[0]
        csv_data = zip_ref.read(csv_filename).decode('utf-8', errors='replace')

    # Parse CSV and filter
    csv_reader = csv.reader(StringIO(csv_data), delimiter='\t')
    filtered_rows = []
    total_count = 0

    for row in csv_reader:
        total_count += 1
        if len(row) < 27:
            continue

        gkg_record = parse_gkg_row(row)
        if should_include_record(gkg_record):
            filtered_rows.append(gkg_record)

    # Transform to bronze schema and write as Parquet
    if filtered_rows:
        df = pd.DataFrame(filtered_rows)
        df_bronze = transform_to_bronze(df)

        # Write directly to bronze Parquet
        wr.s3.to_parquet(
            df=df_bronze,
            path=S3_BRONZE_PATH,
            dataset=True,
            mode='append',
            compression='snappy'
        )

        logger.info(f"Wrote {len(df_bronze)} records to bronze for {file_name}")

    return {
        'total': total_count,
        'filtered': len(filtered_rows)
    }


def transform_to_bronze(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform filtered records to Bronze Parquet schema
    Matches the schema from gdelt-bronze-transform Lambda
    """
    df_bronze = pd.DataFrame()

    # Parse article_date from date field (format: yyyyMMddHHmmss)
    date_str = df['date'].astype(str).str[:8]
    df_bronze['article_date'] = pd.to_datetime(
        date_str,
        format='%Y%m%d',
        errors='coerce'
    ).dt.date

    df_bronze['source_url'] = df['source_url'].astype(str)
    df_bronze['themes'] = df['themes'].astype(str)
    df_bronze['locations'] = df['locations'].astype(str)
    df_bronze['all_names'] = df['all_names'].astype(str)

    # Parse tone fields (comma-separated: avg,positive,negative,polarity)
    tone_split = df['tone'].astype(str).str.split(',', expand=True)
    df_bronze['tone_avg'] = pd.to_numeric(tone_split[0], errors='coerce')
    df_bronze['tone_positive'] = pd.to_numeric(tone_split[1], errors='coerce')
    df_bronze['tone_negative'] = pd.to_numeric(tone_split[2], errors='coerce')
    df_bronze['tone_polarity'] = pd.to_numeric(tone_split[3], errors='coerce')

    # Flag commodities
    all_names_lower = df['all_names'].astype(str).str.lower()

    df_bronze['has_coffee'] = all_names_lower.str.contains(
        'coffee|arabica|robusta',
        regex=True,
        na=False
    )

    df_bronze['has_sugar'] = (
        all_names_lower.str.contains('sugarcane|sugar cane', regex=True, na=False) |
        (all_names_lower.str.contains('sugar', regex=False, na=False) &
         ~all_names_lower.str.contains('sugar ray', regex=False, na=False))
    )

    # Drop rows with invalid dates
    df_bronze = df_bronze.dropna(subset=['article_date'])

    return df_bronze


def parse_gkg_row(row: List[str]) -> Dict:
    """Parse a GKG CSV row into structured dict"""
    return {
        'date': row[1] if len(row) > 1 else '',
        'source_url': row[4] if len(row) > 4 else '',
        'themes': row[7] if len(row) > 7 else '',
        'locations': row[9] if len(row) > 9 else '',
        'tone': row[15] if len(row) > 15 else '',
        'all_names': row[23] if len(row) > 23 else ''
    }


def should_include_record(record: Dict) -> bool:
    """Filter logic for commodity-relevant records"""
    themes = record.get('themes', '').upper()
    all_names = record.get('all_names', '').lower()

    for theme in ALL_THEMES:
        if f';{theme}' in themes or themes.startswith(theme):
            return True

    for keyword in ALL_KEYWORDS:
        if keyword in all_names:
            return True

    return False


def is_file_processed(file_name: str) -> bool:
    """Check if file has already been processed"""
    try:
        table = dynamodb.Table(TRACKING_TABLE)
        response = table.get_item(Key={'file_name': file_name})
        return 'Item' in response
    except Exception as e:
        logger.warning(f"Error checking file status: {e}")
        return False


def mark_file_processed(file_name: str, status: str = 'success'):
    """Mark file as processed in DynamoDB"""
    try:
        table = dynamodb.Table(TRACKING_TABLE)
        table.put_item(Item={
            'file_name': file_name,
            'processed_at': datetime.utcnow().isoformat(),
            'status': status,
            'ttl': int((datetime.utcnow() + timedelta(days=90)).timestamp())
        })
    except Exception as e:
        logger.error(f"Error marking file processed: {e}")


if __name__ == "__main__":
    test_event = {"mode": "incremental"}
    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))
