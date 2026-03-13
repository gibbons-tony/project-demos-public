"""
AWS Lambda Function to Load GDELT CSV URLs to SQS for Bronze Processing
Scans GDELT master file list, checks DynamoDB for missing/incomplete files,
and loads CSV URLs (not S3 paths!) to SQS for direct CSV→Bronze processing

Used by Step Function for daily incremental updates
"""

import json
import boto3
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
sqs = boto3.client('sqs', region_name='us-west-2')

# Configuration
TRACKING_TABLE = 'groundtruth-capstone-file-tracking'
QUEUE_URL = 'https://sqs.us-west-2.amazonaws.com/534150427458/groundtruth-gdelt-backfill-queue'
MASTER_LIST_URL = 'http://data.gdeltproject.org/gdeltv2/masterfilelist.txt'
INCREMENTAL_LOOKBACK_DAYS = 90


def lambda_handler(event, context):
    """
    Main Lambda handler - scans GDELT master list and loads CSV URLs to SQS

    Event parameters:
    - mode: 'incremental' (default) or 'full' - determines date range
    - lookback_days: Number of days to look back (default: 90 for incremental)

    Returns:
    {
        'files_loaded': int - Number of CSV URLs loaded to SQS,
        'files_already_processed': int - Number of files with bronze_status='success',
        'total_files_checked': int - Total files in master list (in date range)
    }
    """
    mode = event.get('mode', 'incremental')
    lookback_days = event.get('lookback_days', INCREMENTAL_LOOKBACK_DAYS)

    logger.info(f"Starting GDELT CSV SQS loader - mode: {mode}, lookback: {lookback_days} days")

    try:
        # Step 1: Fetch master file list with date filtering
        if mode == 'incremental':
            start_date = datetime.utcnow() - timedelta(days=lookback_days)
        else:
            start_date = datetime(2021, 1, 1)  # Full mode: from 2021

        gkg_files = fetch_master_file_list(start_date)
        logger.info(f"Found {len(gkg_files):,} GKG files in master list (from {start_date.strftime('%Y-%m-%d')})")

        # Step 2: Get existing DynamoDB entries to check bronze status
        logger.info("Checking DynamoDB for files needing bronze processing...")
        files_to_process, files_already_done = identify_files_needing_processing(gkg_files)

        logger.info(f"Files needing bronze processing: {len(files_to_process):,}")
        logger.info(f"Files already processed: {len(files_already_done):,}")

        # Step 3: Load CSV URLs to SQS
        if files_to_process:
            logger.info(f"Loading {len(files_to_process):,} CSV URLs to SQS...")
            loaded_count = load_csv_urls_to_sqs(files_to_process)
            logger.info(f"Loaded {loaded_count:,} CSV URLs to queue")
        else:
            logger.info("No files need processing - all up to date!")
            loaded_count = 0

        result = {
            'files_loaded': loaded_count,
            'files_already_processed': len(files_already_done),
            'total_files_checked': len(gkg_files)
        }

        logger.info(f"Loader complete: {result}")

        return {
            'statusCode': 200,
            'body': json.dumps(result),
            **result  # Include at top level for Step Function
        }

    except Exception as e:
        logger.error(f"Error in CSV SQS loader: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def fetch_master_file_list(start_date: datetime) -> List[Tuple[str, str]]:
    """
    Fetch GDELT master file list and filter for GKG files from start_date onwards.

    Returns:
        List of tuples: [(filename, csv_url), ...]
        Example: [('20230101000000.gkg.csv.zip', 'http://data.gdeltproject.org/gdeltv2/20230101000000.gkg.csv.zip'), ...]
    """
    logger.info(f"Fetching GDELT master file list from {MASTER_LIST_URL}")

    try:
        response = requests.get(MASTER_LIST_URL, timeout=60)
        response.raise_for_status()

        gkg_files = []
        start_timestamp = int(start_date.timestamp())

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
                timestamp_str = filename[:14]
                file_date = datetime.strptime(timestamp_str, '%Y%m%d%H%M%S')
                file_timestamp = int(file_date.timestamp())

                # Only include files from start_date onwards
                if file_timestamp >= start_timestamp:
                    gkg_files.append((filename, url))

            except (ValueError, IndexError):
                continue

        logger.info(f"Found {len(gkg_files):,} GKG files from {start_date.strftime('%Y-%m-%d')}")
        return gkg_files

    except Exception as e:
        logger.error(f"Error fetching master file list: {e}")
        raise


def identify_files_needing_processing(gkg_files: List[Tuple[str, str]]) -> Tuple[List[Tuple[str, str]], List[str]]:
    """
    Check DynamoDB to identify which files need bronze processing.

    Args:
        gkg_files: List of (filename, csv_url) tuples from master list

    Returns:
        Tuple of:
        - files_to_process: List of (filename, csv_url) tuples needing processing
        - files_already_done: List of filenames with bronze_status='success'
    """
    table = dynamodb.Table(TRACKING_TABLE)

    files_to_process = []
    files_already_done = []

    # Batch get items from DynamoDB (more efficient than individual get_item calls)
    # Process in batches of 100 (DynamoDB batch_get_item limit)
    for i in range(0, len(gkg_files), 100):
        batch = gkg_files[i:i+100]

        # Prepare batch get request
        keys = [{'file_name': filename} for filename, _ in batch]

        try:
            response = dynamodb.batch_get_item(
                RequestItems={
                    TRACKING_TABLE: {
                        'Keys': keys,
                        'ProjectionExpression': 'file_name, bronze_status'
                    }
                }
            )

            # Extract bronze status for files in DynamoDB
            dynamodb_items = {item['file_name']: item.get('bronze_status') for item in response['Responses'].get(TRACKING_TABLE, [])}

            # Check each file in the batch
            for filename, csv_url in batch:
                bronze_status = dynamodb_items.get(filename)

                if bronze_status == 'success':
                    # Already processed to bronze successfully
                    files_already_done.append(filename)
                else:
                    # Needs processing (bronze_status is None, 'error', '404', or 'in_progress')
                    files_to_process.append((filename, csv_url))

        except Exception as e:
            logger.error(f"Error checking batch in DynamoDB: {e}")
            # On error, assume files need processing
            files_to_process.extend(batch)

    return files_to_process, files_already_done


def load_csv_urls_to_sqs(files_to_process: List[Tuple[str, str]]) -> int:
    """
    Load CSV URLs to SQS queue in batches.

    Args:
        files_to_process: List of (filename, csv_url) tuples

    Returns:
        Number of URLs successfully loaded to queue
    """
    loaded_count = 0
    batch_size = 10  # SQS batch limit

    for i in range(0, len(files_to_process), batch_size):
        batch = files_to_process[i:i+batch_size]

        # Prepare SQS batch entries with CSV URLs (not S3 paths!)
        entries = [
            {
                'Id': str(j),
                'MessageBody': csv_url  # Direct CSV URL from GDELT
            }
            for j, (filename, csv_url) in enumerate(batch)
        ]

        try:
            response = sqs.send_message_batch(
                QueueUrl=QUEUE_URL,
                Entries=entries
            )

            # Count successful sends
            loaded_count += len(batch)

            # Log failed messages (if any)
            if 'Failed' in response and response['Failed']:
                failed_count = len(response['Failed'])
                logger.warning(f"Failed to send {failed_count} messages in batch")
                for failed in response['Failed']:
                    logger.warning(f"Failed message: {failed}")
                loaded_count -= failed_count

            # Progress logging every 1000 files
            if loaded_count % 1000 == 0 and loaded_count > 0:
                logger.info(f"Loaded {loaded_count:,}/{len(files_to_process):,} URLs to SQS...")

        except Exception as e:
            logger.error(f"Error sending batch to SQS: {e}")
            raise

    return loaded_count


# For local testing
if __name__ == "__main__":
    test_event = {
        'mode': 'incremental',
        'lookback_days': 90
    }

    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))
