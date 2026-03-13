"""
Silver Discovery Lambda - Find dates needing silver processing.

Scans DynamoDB to find bronze files that don't have corresponding silver status.
Compiles unique dates and queues them to silver SQS queue (avoiding duplicates).

Trigger: Manual or EventBridge schedule
Output: Queues dates to groundtruth-gdelt-silver-backfill-queue
"""

import json
import boto3
from datetime import datetime
from typing import Set, Dict
from collections import defaultdict
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS Clients
dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
sqs = boto3.client('sqs', region_name='us-west-2')

# Configuration
TRACKING_TABLE = 'groundtruth-capstone-file-tracking'
SILVER_QUEUE_URL = 'https://sqs.us-west-2.amazonaws.com/534150427458/groundtruth-gdelt-silver-backfill-queue'


def lambda_handler(event, context):
    """
    Main Lambda handler - discovers dates needing silver processing.

    Logic:
    1. Scan DynamoDB for all entries
    2. For each bronze file with success status, extract date
    3. Check if corresponding SILVER_{date} entry exists with success status
    4. If not, add date to queue list
    5. Check SQS queue for dates already queued (to avoid duplicates)
    6. Queue unique dates that need processing
    """
    logger.info(f"Event: {json.dumps(event)}")

    start_time = datetime.utcnow()
    logger.info(f"Starting silver discovery at {start_time.isoformat()}")

    try:
        # Step 1: Scan DynamoDB for bronze and silver status
        logger.info("Scanning DynamoDB for bronze and silver status...")
        bronze_dates, silver_dates, dates_needing_reprocess = scan_dynamodb_status()

        logger.info(f"Found {len(bronze_dates)} unique dates with bronze data")
        logger.info(f"Found {len(silver_dates)} dates with silver status")
        logger.info(f"Found {len(dates_needing_reprocess)} dates needing re-processing (partial/old)")

        # Step 1b: Delete old SILVER entries for dates needing re-processing
        if dates_needing_reprocess:
            logger.info(f"Deleting {len(dates_needing_reprocess)} old/partial SILVER entries...")
            delete_silver_entries(dates_needing_reprocess)

        # Step 2: Find dates needing silver processing
        # Include both new dates and dates needing re-processing
        dates_needing_silver = (bronze_dates - silver_dates) | dates_needing_reprocess
        logger.info(f"Identified {len(dates_needing_silver)} dates needing silver processing")

        if not dates_needing_silver:
            logger.info("No dates need silver processing - all caught up!")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'All dates processed',
                    'bronze_dates': len(bronze_dates),
                    'silver_dates': len(silver_dates),
                    'dates_queued': 0
                })
            }

        # Step 3: Check SQS queue for dates already queued
        logger.info("Checking SQS queue for already-queued dates...")
        queued_dates = get_dates_in_queue()
        logger.info(f"Found {len(queued_dates)} dates already in queue")

        # Step 4: Filter out dates already in queue
        dates_to_queue = dates_needing_silver - queued_dates
        logger.info(f"{len(dates_to_queue)} dates need to be queued")

        # Step 5: Queue dates
        if dates_to_queue:
            queued_count = queue_dates_for_silver(sorted(dates_to_queue))
            logger.info(f"✓ Queued {queued_count} dates for silver processing")
        else:
            queued_count = 0
            logger.info("All needed dates are already in queue")

        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        logger.info(f"Silver discovery completed in {duration:.1f} seconds")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Discovery complete',
                'bronze_dates': len(bronze_dates),
                'silver_dates': len(silver_dates),
                'dates_needing_reprocess': len(dates_needing_reprocess),
                'dates_needing_silver': len(dates_needing_silver),
                'dates_already_queued': len(queued_dates),
                'dates_queued': queued_count,
                'duration_seconds': duration
            })
        }

    except Exception as e:
        logger.error(f"Error in silver discovery: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def scan_dynamodb_status() -> tuple[Set[str], Set[str], Set[str]]:
    """
    Scan DynamoDB to find:
    1. All dates with successful bronze processing
    2. All dates with complete silver status
    3. All dates with silver entries needing re-processing (missing completeness or partial)

    Returns (bronze_dates, silver_dates, dates_needing_reprocess)
    """
    table = dynamodb.Table(TRACKING_TABLE)

    bronze_dates = set()
    silver_dates = set()
    dates_needing_reprocess = set()

    # Count of bronze files per date
    bronze_count_by_date = defaultdict(int)

    # Scan all items
    scan_kwargs = {}
    items_scanned = 0

    while True:
        response = table.scan(**scan_kwargs)
        items = response.get('Items', [])
        items_scanned += len(items)

        for item in items:
            file_name = item.get('file_name', '')

            # Check for SILVER_{date} entries
            if file_name.startswith('SILVER_'):
                date_str = file_name[7:]  # Remove "SILVER_" prefix
                silver_status = item.get('silver_status')

                # Check if this entry needs re-processing
                if silver_status == 'success':
                    # Check if bronze completeness fields exist
                    has_completeness = 'bronze_completeness_status' in item

                    if not has_completeness:
                        # Old entry without completeness tracking - needs re-processing
                        logger.info(f"Found old silver entry without completeness: {date_str}")
                        dates_needing_reprocess.add(date_str)
                    elif item.get('bronze_completeness_status') == 'partial':
                        # Partial bronze data - needs re-processing
                        logger.info(f"Found partial silver entry: {date_str}")
                        dates_needing_reprocess.add(date_str)
                    else:
                        # Complete and has completeness tracking
                        silver_dates.add(date_str)

                elif silver_status == 'in_progress':
                    # Currently processing, don't queue duplicates
                    silver_dates.add(date_str)

            # Check for bronze file entries with success status
            elif file_name.endswith('.parquet') or file_name.endswith('.gkg.csv.zip'):
                bronze_status = item.get('bronze_status')

                if bronze_status == 'success':
                    # Extract date from filename (YYYYMMDDHHMMSS.gkg.csv.zip)
                    try:
                        date_prefix = file_name[:8]  # YYYYMMDD
                        year = date_prefix[:4]
                        month = date_prefix[4:6]
                        day = date_prefix[6:8]
                        date_str = f"{year}-{month}-{day}"

                        bronze_dates.add(date_str)
                        bronze_count_by_date[date_str] += 1
                    except Exception as e:
                        logger.warning(f"Could not extract date from {file_name}: {e}")

        # Check if there are more items
        if 'LastEvaluatedKey' not in response:
            break

        scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']

        # Log progress every 10k items
        if items_scanned % 10000 == 0:
            logger.info(f"Scanned {items_scanned:,} items... (found {len(bronze_dates)} bronze dates, {len(silver_dates)} silver dates)")

    logger.info(f"Total items scanned: {items_scanned:,}")
    logger.info(f"Sample bronze file counts: {dict(list(bronze_count_by_date.items())[:5])}")
    logger.info(f"Dates needing re-processing: {len(dates_needing_reprocess)}")

    return bronze_dates, silver_dates, dates_needing_reprocess


def delete_silver_entries(dates: Set[str]):
    """
    Delete SILVER_{date} entries from DynamoDB for dates needing re-processing.
    This allows them to be re-queued and re-processed with updated logic.
    """
    table = dynamodb.Table(TRACKING_TABLE)
    deleted_count = 0

    for date_str in dates:
        tracking_key = f"SILVER_{date_str}"
        try:
            table.delete_item(Key={'file_name': tracking_key})
            deleted_count += 1
            logger.info(f"Deleted old SILVER entry: {tracking_key}")
        except Exception as e:
            logger.error(f"Failed to delete {tracking_key}: {e}")

    logger.info(f"Deleted {deleted_count} old SILVER entries")


def get_dates_in_queue() -> Set[str]:
    """
    Check SQS queue for dates already queued (to avoid duplicates).

    Note: This uses ReceiveMessage which only samples the queue,
    so it's not 100% accurate but helps reduce duplicates.
    """
    queued_dates = set()

    try:
        # Get queue attributes to check message count
        attrs = sqs.get_queue_attributes(
            QueueUrl=SILVER_QUEUE_URL,
            AttributeNames=['ApproximateNumberOfMessages', 'ApproximateNumberOfMessagesNotVisible']
        )

        available = int(attrs['Attributes'].get('ApproximateNumberOfMessages', 0))
        in_flight = int(attrs['Attributes'].get('ApproximateNumberOfMessagesNotVisible', 0))

        logger.info(f"Queue has {available} available, {in_flight} in-flight messages")

        # Sample up to 10 messages to see what's queued
        # (We won't delete them, just peek)
        if available > 0:
            response = sqs.receive_message(
                QueueUrl=SILVER_QUEUE_URL,
                MaxNumberOfMessages=min(10, available),
                VisibilityTimeout=30,  # Short timeout so they return quickly
                WaitTimeSeconds=1
            )

            if 'Messages' in response:
                for msg in response['Messages']:
                    try:
                        body = json.loads(msg['Body'])
                        date_str = body.get('date')
                        if date_str:
                            queued_dates.add(date_str)
                    except Exception as e:
                        logger.warning(f"Error parsing queue message: {e}")

                logger.info(f"Sampled {len(response['Messages'])} messages from queue")

    except Exception as e:
        logger.warning(f"Error checking queue: {e}")

    return queued_dates


def queue_dates_for_silver(dates: list) -> int:
    """
    Queue dates to silver SQS queue.

    Returns count of successfully queued dates.
    """
    queued_count = 0
    failed_count = 0

    # Queue in batches of 10 (SQS batch limit)
    batch_size = 10

    for i in range(0, len(dates), batch_size):
        batch = dates[i:i+batch_size]

        entries = [
            {
                'Id': str(idx),
                'MessageBody': json.dumps({'date': date_str})
            }
            for idx, date_str in enumerate(batch)
        ]

        try:
            response = sqs.send_message_batch(
                QueueUrl=SILVER_QUEUE_URL,
                Entries=entries
            )

            # Check for successes and failures
            if 'Successful' in response:
                queued_count += len(response['Successful'])

            if 'Failed' in response:
                failed_count += len(response['Failed'])
                for failure in response['Failed']:
                    logger.error(f"Failed to queue message {failure['Id']}: {failure['Message']}")

        except Exception as e:
            logger.error(f"Error queueing batch {i//batch_size + 1}: {e}")
            failed_count += len(batch)

    if failed_count > 0:
        logger.warning(f"Failed to queue {failed_count} dates")

    return queued_count
