"""
AWS Lambda Function for Direct CSV to Bronze Parquet Transformation
Downloads GDELT CSV files, filters for commodity relevance, and writes to Bronze layer
Skips JSONL intermediate step for efficiency

Triggered by SQS Event Source Mapping
Uses DynamoDB for deduplication and status tracking
"""

import json
import boto3
import requests
import zipfile
from io import BytesIO, StringIO
import csv
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging
import sys
import os
import pyarrow as pa
import pyarrow.parquet as pq

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Increase CSV field size limit to handle large GDELT fields
csv.field_size_limit(sys.maxsize)

# Initialize AWS clients
s3 = boto3.client('s3', region_name='us-west-2')
sqs = boto3.client('sqs', region_name='us-west-2')
dynamodb = boto3.resource('dynamodb', region_name='us-west-2')

# Configuration
S3_BUCKET = 'groundtruth-capstone'
S3_BRONZE_PATH = 's3://groundtruth-capstone/processed/gdelt/bronze/gdelt/'
TRACKING_TABLE = 'groundtruth-capstone-file-tracking'
DEDUP_TABLE = 'groundtruth-capstone-bronze-tracking'
SILVER_QUEUE_URL = 'https://sqs.us-west-2.amazonaws.com/534150427458/groundtruth-gdelt-silver-backfill-queue'

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
    Main Lambda handler - processes files from SQS Event Source Mapping

    Event structure (SQS Event Source Mapping):
    {
        "Records": [
            {
                "body": "http://data.gdeltproject.org/gdeltv2/20230101000000.gkg.csv.zip",
                "messageId": "...",
                "receiptHandle": "..."
            }
        ]
    }
    """
    logger.info(f"Received {len(event.get('Records', []))} messages from SQS")

    processed_count = 0
    skipped_count = 0
    error_count = 0
    processed_dates = set()  # Track unique dates processed in this batch

    for record in event.get('Records', []):
        url = record['body']
        file_name = url.split('/')[-1]

        try:
            # Check if should process (deduplication + status check)
            should_process, skip_reason = should_process_file(file_name)

            if not should_process:
                logger.info(f"Skipping {file_name}: {skip_reason}")
                skipped_count += 1
                continue

            # Mark as in progress
            mark_bronze_in_progress(file_name)

            # Download, filter, and transform to Bronze Parquet
            record_count = process_csv_to_bronze(url, file_name)

            if record_count > 0:
                # Mark as success
                mark_bronze_success(file_name, record_count)
                processed_count += 1

                # Extract date and add to set (YYYYMMDDHHMMSS.gkg.csv.zip -> YYYY-MM-DD)
                date_str = extract_date_from_filename(file_name)
                if date_str:
                    processed_dates.add(date_str)

                logger.info(f"✓ Successfully processed {file_name} ({record_count} records)")
            else:
                # No records after filtering - still mark as success
                mark_bronze_success(file_name, 0)
                skipped_count += 1
                logger.info(f"⊘ No relevant records in {file_name}")

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"File not found: {file_name}")
                mark_bronze_404(file_name)
                skipped_count += 1
            else:
                logger.error(f"HTTP error processing {file_name}: {e}")
                mark_bronze_error(file_name, str(e))
                error_count += 1
        except Exception as e:
            logger.error(f"Error processing {file_name}: {e}", exc_info=True)
            mark_bronze_error(file_name, str(e))
            error_count += 1

    # Queue unique dates to silver processing
    if processed_dates:
        queue_dates_for_silver(processed_dates)

    result = {
        'processed': processed_count,
        'skipped': skipped_count,
        'errors': error_count,
        'total': len(event.get('Records', [])),
        'dates_queued_for_silver': len(processed_dates)
    }

    logger.info(f"Batch complete: {result}")

    return {
        'statusCode': 200,
        'body': json.dumps(result)
    }


def should_process_file(filename: str) -> tuple[bool, Optional[str]]:
    """
    Check if file should be processed based on deduplication and tracking.

    Checks:
    1. Not already in deduplication table (prevents duplicate processing)
    2. Bronze processing not yet complete in tracking table
    3. CSV source exists (not 404)
    """
    try:
        # Check deduplication table first (fast rejection)
        dedup_table = dynamodb.Table(DEDUP_TABLE)
        response = dedup_table.get_item(Key={'file_name': filename})

        if 'Item' in response:
            return False, "already_in_dedup_table"

        # Check tracking table for status
        tracking_table = dynamodb.Table(TRACKING_TABLE)
        response = tracking_table.get_item(Key={'file_name': filename})

        if 'Item' not in response:
            # No tracking entry - file is ready to process
            return True, None

        item = response['Item']

        # Check if bronze already complete
        if item.get('bronze_status') == 'success':
            return False, "bronze_already_complete"

        # Check if source CSV doesn't exist (404)
        if item.get('csv_status') == '404':
            return False, "source_csv_404"

        # Check if bronze processing is currently in progress (shouldn't happen with Event Source Mapping, but safety check)
        if item.get('bronze_status') == 'in_progress':
            return False, "bronze_in_progress"

        # Ready to process
        return True, None

    except Exception as e:
        logger.error(f"Error checking file status for {filename}: {e}")
        return False, "dynamodb_error"


def process_csv_to_bronze(url: str, file_name: str) -> int:
    """
    Download CSV, filter for commodity relevance, transform to Bronze Parquet.

    Returns: Number of records written to Bronze
    """
    logger.info(f"Processing {file_name} from CSV to Bronze")

    # Download and decompress CSV
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

    logger.info(f"Filtered {len(filtered_rows)} relevant records from {total_count} total")

    # If no relevant records, return 0
    if not filtered_rows:
        return 0

    # Convert to PyArrow Table
    table = pa.Table.from_pylist(filtered_rows)

    # Write to temporary Parquet file
    parquet_filename = file_name.replace('.zip', '.parquet')
    tmp_path = f'/tmp/{parquet_filename}'

    pq.write_table(table, tmp_path, compression='snappy')

    # Upload to S3
    s3_key = f'processed/gdelt/bronze/gdelt/{parquet_filename}'
    with open(tmp_path, 'rb') as f:
        s3.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=f)

    # Clean up temp file
    os.remove(tmp_path)

    parquet_path = f"s3://{S3_BUCKET}/{s3_key}"
    logger.info(f"✓ Wrote {len(filtered_rows)} records to {parquet_path}")

    return len(filtered_rows)


def parse_gkg_row(row: list) -> Dict:
    """
    Parse a GKG CSV row into structured dict.
    Extracts ALL 27 GKG 2.0 fields for complete data preservation.
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
    Filter logic for commodity-relevant records.
    Returns True if record matches any of our criteria.
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


def mark_bronze_in_progress(filename: str):
    """Mark bronze processing as in progress in both tables."""
    try:
        now = datetime.utcnow().isoformat()
        ttl = int((datetime.utcnow() + timedelta(days=90)).timestamp())

        # Update tracking table
        tracking_table = dynamodb.Table(TRACKING_TABLE)
        tracking_table.update_item(
            Key={'file_name': filename},
            UpdateExpression='SET bronze_status = :status, bronze_started_at = :ts, '
                           'last_updated_at = :updated, #ttl = :ttl',
            ExpressionAttributeNames={'#ttl': 'ttl'},
            ExpressionAttributeValues={
                ':status': 'in_progress',
                ':ts': now,
                ':updated': now,
                ':ttl': ttl
            }
        )

        # Add to deduplication table
        dedup_table = dynamodb.Table(DEDUP_TABLE)
        dedup_table.put_item(
            Item={
                'file_name': filename,
                'processed_at': now,
                'ttl': ttl
            }
        )

    except Exception as e:
        logger.error(f"Error marking bronze in progress for {filename}: {e}")


def mark_bronze_success(filename: str, record_count: int):
    """Mark bronze processing as successful in tracking table."""
    try:
        now = datetime.utcnow().isoformat()
        ttl = int((datetime.utcnow() + timedelta(days=90)).timestamp())

        tracking_table = dynamodb.Table(TRACKING_TABLE)
        tracking_table.update_item(
            Key={'file_name': filename},
            UpdateExpression='SET bronze_parquet_at = :ts, bronze_status = :status, '
                           'last_updated_at = :updated, #ttl = :ttl, record_count = :count',
            ExpressionAttributeNames={'#ttl': 'ttl'},
            ExpressionAttributeValues={
                ':ts': now,
                ':status': 'success',
                ':updated': now,
                ':ttl': ttl,
                ':count': record_count
            }
        )

        logger.info(f"✓ Marked {filename} as bronze complete ({record_count} records)")

    except Exception as e:
        logger.error(f"Error marking bronze success for {filename}: {e}")


def mark_bronze_404(filename: str):
    """Mark file as 404 (not found) in tracking table."""
    try:
        now = datetime.utcnow().isoformat()
        ttl = int((datetime.utcnow() + timedelta(days=90)).timestamp())

        tracking_table = dynamodb.Table(TRACKING_TABLE)
        tracking_table.update_item(
            Key={'file_name': filename},
            UpdateExpression='SET csv_status = :csv_status, bronze_status = :bronze_status, '
                           'last_updated_at = :updated, #ttl = :ttl',
            ExpressionAttributeNames={'#ttl': 'ttl'},
            ExpressionAttributeValues={
                ':csv_status': '404',
                ':bronze_status': '404',
                ':updated': now,
                ':ttl': ttl
            }
        )

        # Add to dedup table to prevent retry
        dedup_table = dynamodb.Table(DEDUP_TABLE)
        dedup_table.put_item(
            Item={
                'file_name': filename,
                'processed_at': now,
                'ttl': ttl
            }
        )

    except Exception as e:
        logger.error(f"Error marking 404 for {filename}: {e}")


def mark_bronze_error(filename: str, error_message: str):
    """Mark bronze processing error in tracking table."""
    try:
        now = datetime.utcnow().isoformat()
        ttl = int((datetime.utcnow() + timedelta(days=90)).timestamp())

        tracking_table = dynamodb.Table(TRACKING_TABLE)
        tracking_table.update_item(
            Key={'file_name': filename},
            UpdateExpression='SET bronze_status = :status, bronze_error = :error, '
                           'last_updated_at = :updated, #ttl = :ttl',
            ExpressionAttributeNames={'#ttl': 'ttl'},
            ExpressionAttributeValues={
                ':status': 'error',
                ':error': error_message[:500],  # Truncate long errors
                ':updated': now,
                ':ttl': ttl
            }
        )

    except Exception as e:
        logger.error(f"Error marking bronze error for {filename}: {e}")


def extract_date_from_filename(filename: str) -> Optional[str]:
    """
    Extract date from GDELT filename.

    Format: YYYYMMDDHHMMSS.gkg.csv.zip -> YYYY-MM-DD
    Example: 20230930150000.gkg.csv.zip -> 2023-09-30

    Returns None if filename format is invalid.
    """
    try:
        # Extract first 8 characters (YYYYMMDD)
        date_str = filename[:8]

        # Parse and reformat to YYYY-MM-DD
        year = date_str[:4]
        month = date_str[4:6]
        day = date_str[6:8]

        return f"{year}-{month}-{day}"
    except Exception as e:
        logger.warning(f"Could not extract date from filename {filename}: {e}")
        return None


def queue_dates_for_silver(processed_dates: set):
    """
    Queue unique dates to silver SQS for event-driven silver processing.

    Checks DynamoDB to avoid queuing dates that are already processed or in progress.
    This creates event-driven architecture: Bronze completion → Silver processing
    """
    tracking_table = dynamodb.Table(TRACKING_TABLE)

    dates_queued = 0
    dates_skipped = 0

    for date_str in sorted(processed_dates):
        try:
            # Check if silver processing already complete for this date
            silver_key = f"SILVER_{date_str}"
            response = tracking_table.get_item(Key={'file_name': silver_key})

            if 'Item' in response:
                item = response['Item']
                silver_status = item.get('silver_status')

                if silver_status == 'success':
                    logger.info(f"Skipping silver queue for {date_str}: already processed")
                    dates_skipped += 1
                    continue
                elif silver_status == 'in_progress':
                    logger.info(f"Skipping silver queue for {date_str}: already in progress")
                    dates_skipped += 1
                    continue

            # Queue date to silver SQS
            sqs.send_message(
                QueueUrl=SILVER_QUEUE_URL,
                MessageBody=date_str
            )

            logger.info(f"✓ Queued {date_str} for silver processing")
            dates_queued += 1

        except Exception as e:
            logger.error(f"Error queuing {date_str} for silver: {e}")

    if dates_queued > 0:
        logger.info(f"📨 Queued {dates_queued} date(s) for silver processing (skipped {dates_skipped} already processed)")


# For local testing
if __name__ == "__main__":
    # Test with sample event
    test_event = {
        "Records": [
            {
                "body": "http://data.gdeltproject.org/gdeltv2/20230930000000.gkg.csv.zip",
                "messageId": "test-message-1",
                "receiptHandle": "test-receipt-1"
            }
        ]
    }

    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))
