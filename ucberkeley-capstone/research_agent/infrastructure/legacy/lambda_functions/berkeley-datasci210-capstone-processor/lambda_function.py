"""
AWS Lambda Function for GDELT GKG Data Collection
Handles both historical backfill and daily incremental updates
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

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Increase CSV field size limit to handle large GDELT fields (default is 131072 bytes)
# Some GDELT fields can exceed 1MB, so set to max allowed value
csv.field_size_limit(sys.maxsize)

# Initialize AWS clients
s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
sqs = boto3.client('sqs')

# Configuration
S3_BUCKET = 'groundtruth-capstone'
S3_RAW_PREFIX = 'landing/gdelt/raw/'
S3_FILTERED_PREFIX = 'landing/gdelt/filtered/'
TRACKING_TABLE = 'groundtruth-capstone-file-tracking'
SQS_QUEUE_URL = 'https://sqs.us-west-2.amazonaws.com/534150427458/groundtruth-gdelt-backfill-queue'

# Incremental mode: Check for missing files from this many days back
# This makes the system self-healing - automatically catches any gaps
# Use a reasonable lookback window to avoid DynamoDB rate limits
INCREMENTAL_LOOKBACK_DAYS = 90  # Check last 90 days for gaps

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

    Event structure:
    {
        "mode": "incremental" | "initialize_backfill" | "backfill",
        "lookback_start_date": "2021-01-01",  # Optional for incremental (defaults to 90 days)
        "start_date": "2023-09-30",           # For initialize_backfill only
        "end_date": "2023-10-01"              # For initialize_backfill only
    }
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


def process_incremental_update(lookback_start_date: str = None) -> Dict:
    """
    Self-healing incremental update: Check for missing files from start_date to yesterday
    This automatically catches any gaps from failures, missed runs, or other issues
    Processes up to 50 files per run (due to Lambda timeout), prioritizing recent files

    Args:
        lookback_start_date: Optional start date (YYYY-MM-DD). If not provided, uses INCREMENTAL_LOOKBACK_DAYS
    """
    logger.info("Starting incremental update (self-healing mode)")

    # Check from lookback window to yesterday
    yesterday = datetime.utcnow() - timedelta(days=1)

    if lookback_start_date:
        start_date = datetime.strptime(lookback_start_date, '%Y-%m-%d')
        logger.info(f"Using custom lookback start date: {lookback_start_date}")
    else:
        start_date = yesterday - timedelta(days=INCREMENTAL_LOOKBACK_DAYS)
        logger.info(f"Using default {INCREMENTAL_LOOKBACK_DAYS} day lookback")

    logger.info(f"Checking for missing files from {start_date.strftime('%Y-%m-%d')} to {yesterday.strftime('%Y-%m-%d')}")

    # Generate all file URLs in the date range
    file_urls = generate_file_urls(start_date, yesterday)
    logger.info(f"Generated {len(file_urls)} total file URLs to check")

    # Filter to only unprocessed files (self-healing logic)
    files_to_process = []
    for url in file_urls:
        file_name = url.split('/')[-1]
        if not is_file_processed(file_name):
            files_to_process.append({
                'url': url,
                'name': file_name
            })

    logger.info(f"Found {len(files_to_process)} unprocessed files out of {len(file_urls)} total")

    # Prioritize recent files (reverse order, so newest first)
    # This ensures we catch yesterday's data before filling historical gaps
    files_to_process.reverse()

    # Batch processing: limit to 50 files per run (Lambda timeout constraint)
    max_files_per_run = 50
    total_unprocessed = len(files_to_process)
    if total_unprocessed > max_files_per_run:
        logger.info(f"Limiting to {max_files_per_run} most recent files this run ({total_unprocessed - max_files_per_run} will remain for next run)")
        files_to_process = files_to_process[:max_files_per_run]

    # Process each file
    processed_count = 0
    filtered_records = 0
    total_records = 0

    for file_info in files_to_process:
        try:
            stats = download_and_filter_file(
                file_info['url'],
                file_info['name']
            )
            processed_count += 1
            filtered_records += stats['filtered']
            total_records += stats['total']
            # Only mark as processed if download and filtering succeeded
            mark_file_processed(file_info['name'], status='success')
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"File not found: {file_info['name']}")
                # Mark 404s with status to distinguish from successful downloads
                mark_file_processed(file_info['name'], status='404')
            else:
                logger.error(f"HTTP error processing {file_info['name']}: {e}")
                # Don't mark as processed - will retry next run
        except Exception as e:
            logger.error(f"Error processing {file_info['name']}: {e}", exc_info=True)
            # Don't mark as processed - will retry next run

    # Calculate remaining unprocessed files for next run
    remaining_unprocessed = total_unprocessed - processed_count

    result = {
        'processed_files': processed_count,
        'total_records': total_records,
        'filtered_records': filtered_records,
        'filter_rate': f"{(filtered_records/total_records*100):.2f}%" if total_records > 0 else "0%",
        'remaining_unprocessed': remaining_unprocessed,
        'mode': 'self-healing incremental',
        'date_range': {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': yesterday.strftime('%Y-%m-%d')
        }
    }

    logger.info(f"Incremental update complete: {result}")
    return result


def get_all_processed_files() -> Set[str]:
    """
    Query DynamoDB once to get all processed file names
    Returns a set of file names for efficient lookups
    """
    logger.info("Querying DynamoDB for all processed files...")
    try:
        table = dynamodb.Table(TRACKING_TABLE)
        processed_files = set()

        # Scan the table to get all items
        response = table.scan(ProjectionExpression='file_name')
        processed_files.update(item['file_name'] for item in response.get('Items', []))

        # Handle pagination if table has more items
        while 'LastEvaluatedKey' in response:
            response = table.scan(
                ProjectionExpression='file_name',
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            processed_files.update(item['file_name'] for item in response.get('Items', []))

        logger.info(f"Found {len(processed_files)} already-processed files in DynamoDB")
        return processed_files
    except Exception as e:
        logger.error(f"Error querying processed files: {e}")
        return set()


def initialize_backfill(start_date: datetime, end_date: datetime) -> Dict:
    """
    INITIALIZATION PHASE (called once):
    1. Query DynamoDB once to get all processed files
    2. Generate all URLs for date range
    3. Calculate missing files
    4. Send missing files to SQS queue
    5. Return count
    """
    # Cap end_date at today
    today = datetime.utcnow().date()
    if end_date.date() > today:
        logger.info(f"Capping end_date from {end_date.date()} to {today}")
        end_date = datetime.combine(today, datetime.min.time())

    logger.info(f"Initializing backfill from {start_date} to {end_date}")

    # Query DynamoDB ONCE
    processed_files = get_all_processed_files()

    # Generate all file URLs
    all_file_urls = generate_file_urls(start_date, end_date)
    logger.info(f"Generated {len(all_file_urls)} file URLs total for date range")

    # Calculate missing files
    missing_urls = [url for url in all_file_urls if url.split('/')[-1] not in processed_files]
    logger.info(f"Found {len(missing_urls)} files to download (already have {len(all_file_urls) - len(missing_urls)})")

    # Send missing URLs to SQS (batch of 10 at a time)
    batch_size = 10
    sent_count = 0

    for i in range(0, len(missing_urls), batch_size):
        batch = missing_urls[i:i + batch_size]
        entries = [
            {
                'Id': str(j),
                'MessageBody': url
            }
            for j, url in enumerate(batch)
        ]

        try:
            response = sqs.send_message_batch(
                QueueUrl=SQS_QUEUE_URL,
                Entries=entries
            )
            sent_count += len(batch)

            if (i + batch_size) % 1000 == 0:
                logger.info(f"Sent {sent_count}/{len(missing_urls)} messages to SQS")
        except Exception as e:
            logger.error(f"Error sending batch to SQS: {e}")
            raise

    logger.info(f"Sent {sent_count} missing file URLs to SQS queue")

    return {
        'statusCode': 200,
        'body': json.dumps({
            'total_missing_files': len(missing_urls),
            'queue_url': SQS_QUEUE_URL,
            'date_range': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d')
            }
        })
    }


def process_historical_backfill() -> Dict:
    """
    PROCESSING PHASE (called per batch):
    1. Receive messages from SQS (up to 50 at a time)
    2. Process URLs from messages
    3. Delete processed messages
    4. Return progress
    """
    logger.info(f"Processing backfill batch from SQS queue")

    processed_count = 0
    filtered_records = 0
    total_records = 0
    skipped_count = 0
    messages_received = 0

    # Receive up to 50 messages (5 batches of 10)
    max_messages = 50
    all_messages = []

    for _ in range(5):  # 5 batches of 10 = 50 messages max
        try:
            response = sqs.receive_message(
                QueueUrl=SQS_QUEUE_URL,
                MaxNumberOfMessages=10,  # Max allowed by SQS
                WaitTimeSeconds=1  # Short polling to get messages quickly
            )
            messages = response.get('Messages', [])
            all_messages.extend(messages)
            messages_received += len(messages)

            if len(messages) < 10:  # Queue is empty or has fewer than 10 messages
                break
        except Exception as e:
            logger.error(f"Error receiving messages from SQS: {e}")
            raise

    logger.info(f"Received {messages_received} messages from SQS")

    if messages_received == 0:
        return {
            'processed_files': 0,
            'skipped_files': 0,
            'total_records': 0,
            'filtered_records': 0,
            'filter_rate': "0%",
            'messages_processed': 0
        }

    # Process each message
    for i, message in enumerate(all_messages):
        url = message['Body']
        file_name = url.split('/')[-1]

        try:
            stats = download_and_filter_file(url, file_name)
            processed_count += 1
            filtered_records += stats['filtered']
            total_records += stats['total']
            mark_file_processed(file_name, status='success')

            # Delete message after successful processing
            sqs.delete_message(
                QueueUrl=SQS_QUEUE_URL,
                ReceiptHandle=message['ReceiptHandle']
            )

            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i + 1}/{messages_received} files processed")

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"File not found: {file_name}")
                mark_file_processed(file_name, status='404')
                skipped_count += 1
                # Delete message even if file not found
                sqs.delete_message(
                    QueueUrl=SQS_QUEUE_URL,
                    ReceiptHandle=message['ReceiptHandle']
                )
            else:
                logger.error(f"HTTP error processing {file_name}: {e}")
                # Leave message in queue for retry
        except Exception as e:
            logger.error(f"Error processing {file_name}: {e}", exc_info=True)
            # Leave message in queue for retry

    result = {
        'processed_files': processed_count,
        'skipped_files': skipped_count,
        'total_records': total_records,
        'filtered_records': filtered_records,
        'filter_rate': f"{(filtered_records/total_records*100):.2f}%" if total_records > 0 else "0%",
        'messages_processed': messages_received
    }

    logger.info(f"Backfill batch complete: {result}")
    return result


def generate_file_urls(start_date: datetime, end_date: datetime) -> List[str]:
    """
    Generate GDELT GKG file URLs for date range
    GKG 2.0 updates every 15 minutes
    """
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


def download_and_filter_file(url: str, file_name: str) -> Dict:
    """
    Download GDELT file, filter for commodity-relevant records, save to S3
    Returns statistics about processing
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
        
        if len(row) < 27:  # GKG has 27 columns
            continue
        
        # Extract relevant fields
        gkg_record = parse_gkg_row(row)
        
        # Apply filters
        if should_include_record(gkg_record):
            filtered_rows.append(gkg_record)
    
    # Save raw file to S3 (optional, for audit trail)
    # Disabled to save storage costs - raw files are ~5MB vs filtered ~70KB
    # s3.put_object(
    #     Bucket=S3_BUCKET,
    #     Key=f"{S3_RAW_PREFIX}{file_name}",
    #     Body=response.content
    # )
    
    # Save filtered data as JSON Lines (easier for Databricks)
    if filtered_rows:
        filtered_data = '\n'.join([json.dumps(record) for record in filtered_rows])
        
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=f"{S3_FILTERED_PREFIX}{file_name.replace('.zip', '.jsonl')}",
            Body=filtered_data.encode('utf-8'),
            ContentType='application/x-ndjson'
        )
    
    return {
        'total': total_count,
        'filtered': len(filtered_rows)
    }


def parse_gkg_row(row: List[str]) -> Dict:
    """
    Parse a GKG CSV row into structured dict
    Extracts ALL 27 GKG 2.0 fields for complete data preservation
    """
    return {
        'gkg_record_id': row[0] if len(row) > 0 else '',
        'date': row[1] if len(row) > 1 else '',
        'source_collection_id': row[2] if len(row) > 2 else '',
        'source_common_name': row[3] if len(row) > 3 else '',
        'source_url': row[4] if len(row) > 4 else '',
        'counts': row[5] if len(row) > 5 else '',
        'v2_counts': row[6] if len(row) > 6 else '',
        'themes': row[7] if len(row) > 7 else '',
        'v2_themes': row[8] if len(row) > 8 else '',
        'locations': row[9] if len(row) > 9 else '',
        'v2_locations': row[10] if len(row) > 10 else '',
        'persons': row[11] if len(row) > 11 else '',
        'v2_persons': row[12] if len(row) > 12 else '',
        'organizations': row[13] if len(row) > 13 else '',
        'v2_organizations': row[14] if len(row) > 14 else '',
        'tone': row[15] if len(row) > 15 else '',
        'dates': row[16] if len(row) > 16 else '',
        'gcam': row[17] if len(row) > 17 else '',
        'sharing_image': row[18] if len(row) > 18 else '',
        'related_images': row[19] if len(row) > 19 else '',
        'social_image_embeds': row[20] if len(row) > 20 else '',
        'social_video_embeds': row[21] if len(row) > 21 else '',
        'quotations': row[22] if len(row) > 22 else '',
        'all_names': row[23] if len(row) > 23 else '',
        'amounts': row[24] if len(row) > 24 else '',
        'translation_info': row[25] if len(row) > 25 else '',
        'extras': row[26] if len(row) > 26 else ''
    }


def should_include_record(record: Dict) -> bool:
    """
    Filter logic for commodity-relevant records
    Returns True if record matches any of our criteria
    """
    themes = record.get('themes', '').upper()
    all_names = record.get('all_names', '').lower()
    
    # Check themes
    for theme in ALL_THEMES:
        if f';{theme}' in themes or themes.startswith(theme):
            return True
    
    # Check keywords in all_names
    for keyword in ALL_KEYWORDS:
        if keyword in all_names:
            return True
    
    return False


def is_file_processed(file_name: str) -> bool:
    """
    Check if file has already been processed
    Uses DynamoDB for tracking
    """
    try:
        table = dynamodb.Table(TRACKING_TABLE)
        response = table.get_item(Key={'file_name': file_name})
        return 'Item' in response
    except Exception as e:
        logger.warning(f"Error checking file status: {e}")
        return False


def mark_file_processed(file_name: str, status: str = 'success', error_message: str = None):
    """
    Mark file as processed in DynamoDB with status tracking

    Args:
        file_name: Name of the file
        status: 'success', '404', or 'error'
        error_message: Optional error message for failures
    """
    try:
        table = dynamodb.Table(TRACKING_TABLE)
        item = {
            'file_name': file_name,
            'processed_at': datetime.utcnow().isoformat(),
            'status': status,
            'ttl': int((datetime.utcnow() + timedelta(days=90)).timestamp())
        }
        if error_message:
            item['error_message'] = error_message

        table.put_item(Item=item)
    except Exception as e:
        logger.error(f"Error marking file processed: {e}")


# For local testing
if __name__ == "__main__":
    # Test incremental mode
    test_event_incremental = {
        "mode": "incremental"
    }
    
    # Test backfill mode
    test_event_backfill = {
        "mode": "backfill",
        "start_date": "2023-09-30",
        "end_date": "2023-10-01"
    }
    
    result = lambda_handler(test_event_incremental, None)
    print(json.dumps(result, indent=2))
