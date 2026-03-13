"""
AWS Lambda Function for GDELT Daily Discovery
Checks master list vs DynamoDB and queues unprocessed files for Bronze processing

Triggered by EventBridge daily schedule (2 AM UTC)
"""

import boto3
import json
import requests
from datetime import datetime
from typing import Set
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
sqs = boto3.client('sqs', region_name='us-west-2')

# Configuration
MAIN_TRACKING_TABLE = 'groundtruth-capstone-file-tracking'
QUEUE_URL = 'https://sqs.us-west-2.amazonaws.com/534150427458/groundtruth-gdelt-backfill-queue'
GDELT_BASE_URL = 'http://data.gdeltproject.org/gdeltv2/'
GDELT_MASTER_LIST_URL = 'http://data.gdeltproject.org/gdeltv2/masterfilelist.txt'

# Date range for processing
START_DATE = '2021-01-01'
END_DATE = '2030-12-31'


def lambda_handler(event, context):
    """
    Main Lambda handler - runs daily to discover and queue new GDELT files

    Returns:
        - files_queued: Number of files sent to SQS
        - files_already_processed: Number of files already in bronze
        - total_checked: Total files in date range
    """
    logger.info("Starting GDELT daily discovery")

    try:
        # Step 1: Get GKG files from master list
        logger.info("Downloading fresh GDELT master list...")
        master_list_files = get_master_list_gkg_files(START_DATE, END_DATE)
        logger.info(f"Found {len(master_list_files):,} GKG files in master list")

        # Step 2: Get files already processed to bronze
        logger.info("Checking DynamoDB for already processed files...")
        bronze_processed = get_bronze_processed_files()
        logger.info(f"Found {len(bronze_processed):,} files already processed to bronze")

        # Step 3: Find files that need processing
        files_to_process = sorted(master_list_files - bronze_processed)
        logger.info(f"Need to process: {len(files_to_process):,} files")

        # Step 4: Populate SQS queue with CSV URLs
        if files_to_process:
            sent_count = populate_sqs_with_csv_urls(files_to_process)
        else:
            sent_count = 0
            logger.info("No new files to process - all up to date!")

        # Summary
        result = {
            'files_queued': sent_count,
            'files_already_processed': len(bronze_processed),
            'total_in_master_list': len(master_list_files),
            'start_date': START_DATE,
            'end_date': END_DATE,
            'timestamp': datetime.utcnow().isoformat()
        }

        logger.info(f"Discovery complete: {json.dumps(result)}")

        return {
            'statusCode': 200,
            'body': json.dumps(result)
        }

    except Exception as e:
        logger.error(f"Error in discovery process: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def get_master_list_gkg_files(start_date: str, end_date: str) -> Set[str]:
    """
    Download fresh GDELT master list and extract GKG CSV filenames in date range.
    Returns set of filenames like: '20230930000000.gkg.csv.zip'

    OPTIMIZATION: Streams response line-by-line to avoid loading entire file into memory.
    """
    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')

    gkg_files = set()
    lines_processed = 0

    try:
        # Stream the master list line by line instead of loading all into memory
        logger.info(f"Streaming master list from {GDELT_MASTER_LIST_URL}")

        with requests.get(GDELT_MASTER_LIST_URL, timeout=120, stream=True) as response:
            response.raise_for_status()

            # Process line by line
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue

                lines_processed += 1

                # Log progress every 100k lines
                if lines_processed % 100000 == 0:
                    logger.info(f"Processed {lines_processed:,} lines, found {len(gkg_files):,} GKG files in range")

                parts = line.split()
                if len(parts) < 3:
                    continue

                url = parts[2]

                # Only GKG files (not export or mentions)
                if '.gkg.csv.zip' not in url:
                    continue

                filename = url.split('/')[-1]

                # Extract date from filename (YYYYMMDDHHMMSS.gkg.csv.zip)
                try:
                    date_str = filename[:8]  # YYYYMMDD
                    file_dt = datetime.strptime(date_str, '%Y%m%d')

                    if start_dt <= file_dt <= end_dt:
                        gkg_files.add(filename)
                except:
                    continue

        logger.info(f"Completed: processed {lines_processed:,} total lines, found {len(gkg_files):,} GKG files in date range")

    except Exception as e:
        logger.error(f"Error streaming GDELT master list: {e}")
        raise

    return gkg_files


def get_bronze_processed_files() -> Set[str]:
    """
    Get all files already processed to bronze from MAIN tracking table.
    Filters for bronze_status='success' to get CSV files (.zip) that are complete.
    Returns set of filenames.
    """
    table = dynamodb.Table(MAIN_TRACKING_TABLE)

    processed = set()

    # Scan with filter for bronze_status = 'success'
    response = table.scan(
        FilterExpression='bronze_status = :status',
        ExpressionAttributeValues={':status': 'success'},
        ProjectionExpression='file_name'
    )
    processed.update(item['file_name'] for item in response.get('Items', []))

    while 'LastEvaluatedKey' in response:
        response = table.scan(
            FilterExpression='bronze_status = :status',
            ExpressionAttributeValues={':status': 'success'},
            ProjectionExpression='file_name',
            ExclusiveStartKey=response['LastEvaluatedKey']
        )
        processed.update(item['file_name'] for item in response.get('Items', []))

        if len(processed) % 10000 == 0:
            logger.info(f"Scanned {len(processed):,} processed files so far...")

    return processed


def populate_sqs_with_csv_urls(csv_filenames: list) -> int:
    """
    Send CSV URLs to SQS queue for bronze processing.
    Converts filenames like '20230930000000.gkg.csv.zip' to full GDELT URLs.
    """
    logger.info(f"Populating SQS queue with {len(csv_filenames):,} CSV URLs...")

    if not csv_filenames:
        return 0

    sent_count = 0
    batch_size = 10

    for i in range(0, len(csv_filenames), batch_size):
        batch = csv_filenames[i:i + batch_size]

        # Generate full CSV URLs
        entries = [
            {
                'Id': str(j),
                'MessageBody': f"{GDELT_BASE_URL}{filename}"
            }
            for j, filename in enumerate(batch)
        ]

        try:
            response = sqs.send_message_batch(
                QueueUrl=QUEUE_URL,
                Entries=entries
            )
            sent_count += len(batch)

            if sent_count % 1000 == 0:
                logger.info(f"Sent {sent_count:,}/{len(csv_filenames):,} ({sent_count*100//len(csv_filenames)}%)")

            if 'Failed' in response and response['Failed']:
                logger.warning(f"{len(response['Failed'])} messages failed in batch")

        except Exception as e:
            logger.error(f"Error sending batch: {e}")
            raise

    logger.info(f"Successfully sent {sent_count:,} CSV URLs to queue")
    return sent_count


# For local testing
if __name__ == "__main__":
    result = lambda_handler({}, None)
    print(json.dumps(result, indent=2))
