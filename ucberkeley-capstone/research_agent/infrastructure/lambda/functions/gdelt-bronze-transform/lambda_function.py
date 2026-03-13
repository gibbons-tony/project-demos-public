"""
Lambda function to convert GDELT data to Bronze Parquet format - Dual-mode support.

**Backfill Mode (current):** Processes JSONL → Bronze Parquet
- Reads filtered JSONL files from S3
- Converts to Parquet with schema transformations
- Writes to Bronze layer
- Tracks progress in DynamoDB with comprehensive error logging

**Incremental Mode (future):** Will process CSV → Bronze Parquet directly
- Download CSV from GDELT
- Filter and convert directly to Parquet
- Skip JSONL intermediate step

Uses unified DynamoDB tracking table to avoid reprocessing and enable retry/recovery.
"""

import json
import boto3
import pandas as pd
import awswrangler as wr
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
import re

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# Configuration
S3_BUCKET = 'groundtruth-capstone'
S3_JSONL_PREFIX = 'landing/gdelt/filtered/'
S3_BRONZE_PATH = 's3://groundtruth-capstone/processed/gdelt/bronze/gdelt/'
TRACKING_TABLE = 'groundtruth-capstone-file-tracking'  # Unified tracking table


def lambda_handler(event, context):
    """
    Main Lambda handler - converts JSONL to Bronze Parquet from SQS queue.

    Event structure (SQS):
    {
        "Records": [
            {
                "body": "landing/gdelt/filtered/20210101.jsonl",
                "receiptHandle": "..."
            }
        ]
    }
    """
    logger.info(f"Event: {json.dumps(event)}")

    try:
        # Check if this is an SQS event
        if 'Records' not in event:
            # Fallback to direct invocation for testing
            return handle_direct_invocation(event, context)

        # Process SQS messages
        processed_count = 0
        total_records = 0
        failed_messages = []

        for record in event['Records']:
            s3_key = record['body']

            try:
                # Extract full filename from S3 key (unique identifier)
                filename = extract_filename(s3_key)
                logger.info(f"Processing {s3_key} (filename: {filename})")

                # Check if should process using unified tracking
                should_process, skip_reason = should_process_file(filename)
                if not should_process:
                    logger.info(f"Skipping {filename} - {skip_reason}")
                    continue

                # Process the file
                records = process_jsonl_file(s3_key, filename)
                processed_count += 1
                total_records += records

                # Mark as processed with success status
                mark_bronze_success(filename, records)

                logger.info(f"✓ Processed {filename}: {records} records")

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error processing {s3_key}: {error_msg}", exc_info=True)

                # Try to extract filename for error tracking
                try:
                    filename = extract_filename(s3_key)
                    mark_bronze_error(filename, error_msg)
                except:
                    pass  # If can't extract filename, just log

                failed_messages.append({
                    'file': s3_key,
                    'error': error_msg
                })
                # Let SQS retry by raising exception
                raise

        result = {
            'processed_files': processed_count,
            'total_records': total_records,
            'failed_messages': failed_messages
        }

        logger.info(f"Batch complete: {result}")

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


def handle_direct_invocation(event, context):
    """
    Handle direct Lambda invocation (non-SQS) for testing or manual runs.

    Event structure:
    {
        "s3_key": "landing/gdelt/filtered/20210101.jsonl"
    }
    """
    logger.info("Direct invocation (non-SQS)")

    s3_key = event.get('s3_key')
    if not s3_key:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Missing s3_key parameter'})
        }

    file_name = s3_key.split('/')[-1]

    try:
        # Check if already processed
        if is_file_processed(file_name):
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Already processed',
                    'file': file_name
                })
            }

        # Process the file
        records = process_jsonl_file(s3_key, file_name)
        mark_file_processed(file_name)

        return {
            'statusCode': 200,
            'body': json.dumps({
                'processed_files': 1,
                'total_records': records,
                'file': file_name
            })
        }

    except Exception as e:
        logger.error(f"Error processing {file_name}: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def list_s3_files(bucket: str, prefix: str) -> List[str]:
    """List all files with given prefix in S3 bucket."""
    files = []
    paginator = s3.get_paginator('list_objects_v2')

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        if 'Contents' in page:
            for obj in page['Contents']:
                key = obj['Key']
                if key.endswith('.jsonl'):
                    files.append(key)

    return files


def process_jsonl_file(s3_key: str, file_name: str) -> int:
    """
    Read JSONL file from S3, transform to Bronze schema, write as Parquet.
    Returns number of records processed.

    **Comprehensive error tracking:**
    - Marks bronze_status='in_progress' at start
    - Updates to 'success' with record count on completion
    - Updates to 'error' with error message on failure
    """
    logger.info(f"Processing {file_name}")

    # Mark as in progress BEFORE processing starts
    mark_bronze_in_progress(file_name)

    # Read JSONL from S3 using pandas directly to prevent date auto-conversion
    # awswrangler converts large ints to timestamps before we can process them
    s3_client = boto3.client('s3')
    response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
    df = pd.read_json(response['Body'], lines=True, convert_dates=False)

    if df.empty:
        logger.warning(f"No data in {file_name}")
        return 0

    # Transform to Bronze schema
    df_bronze = transform_to_bronze(df)

    # Write to Bronze location as Parquet
    wr.s3.to_parquet(
        df=df_bronze,
        path=S3_BRONZE_PATH,
        dataset=True,
        mode='append',
        compression='snappy'
    )

    record_count = len(df_bronze)
    logger.info(f"✓ Wrote {record_count} records to Bronze for {file_name}")

    return record_count


def transform_to_bronze(df: pd.DataFrame) -> pd.DataFrame:
    """
    Simple JSONL to Parquet conversion - keep all columns as-is.
    Bronze layer is for raw data storage, transformations happen in Silver.
    """
    logger.info(f"Transform input: {len(df)} rows, columns: {list(df.columns)}")

    # Keep all columns from JSONL exactly as they are
    # Just ensure consistent string types for text fields
    df_bronze = df.copy()

    # Convert all columns to strings (raw data preservation)
    for col in df_bronze.columns:
        df_bronze[col] = df_bronze[col].astype(str)

    logger.info(f"Bronze output: {len(df_bronze)} rows, {len(df_bronze.columns)} columns")

    return df_bronze


def extract_filename(s3_key: str) -> str:
    """
    Extract original CSV filename from S3 key for DynamoDB lookup.

    Examples:
      landing/gdelt/filtered/20210101000000.gkg.csv.jsonl -> 20210101000000.gkg.csv.zip
      20210101000000.gkg.csv.zip -> 20210101000000.gkg.csv.zip

    The JSONL files are intermediate format. DynamoDB is keyed by the original
    CSV filename (*.gkg.csv.zip) from the backfill process.
    """
    # Extract filename from path
    filename = s3_key.split('/')[-1]
    if not filename:
        raise ValueError(f"Could not extract filename from: {s3_key}")

    # Convert JSONL filename back to original CSV filename
    # 20210101000000.gkg.csv.jsonl -> 20210101000000.gkg.csv.zip
    if filename.endswith('.gkg.csv.jsonl'):
        filename = filename.replace('.gkg.csv.jsonl', '.gkg.csv.zip')

    return filename


def should_process_file(filename: str) -> tuple[bool, Optional[str]]:
    """
    Check if file should be processed based on unified tracking table.

    **Backfill Mode (current):**
    Bronze processing requires:
    1. JSONL must exist and be ready (jsonl_status = 'success')
    2. Bronze processing not yet complete (bronze_status != 'success')

    **Future Incremental Mode:**
    Will check: csv_status = 'success' AND bronze_status != 'success'

    Args:
        filename: Full filename (e.g., '20210101000000.gkg.csv.zip')

    Returns:
        (should_process, skip_reason)
        - (True, None): Process the file
        - (False, reason): Skip with reason
    """
    try:
        table = dynamodb.Table(TRACKING_TABLE)
        response = table.get_item(Key={'file_name': filename})

        if 'Item' not in response:
            # No tracking entry - file not in system yet
            return False, "no_tracking_entry"

        item = response['Item']

        # Check if bronze already complete
        if item.get('bronze_status') == 'success':
            return False, "bronze_already_complete"

        # Check if source CSV doesn't exist (404)
        if item.get('csv_status') == '404':
            return False, "source_csv_404"

        # BACKFILL MODE: Check if JSONL exists and is ready
        if item.get('jsonl_status') != 'success':
            # JSONL not ready or failed - cannot process
            return False, "jsonl_not_ready"

        # Check for repeated errors (allow retry on errors)
        if item.get('bronze_status') == 'error':
            logger.warning(f"Retrying after previous error for {filename}: {item.get('bronze_error_message')}")
            return True, None

        # Check if bronze processing is currently in progress (avoid duplicate processing)
        if item.get('bronze_status') == 'in_progress':
            return False, "bronze_in_progress"

        # JSONL ready (jsonl_status='success') AND bronze not complete - safe to process
        return True, None

    except Exception as e:
        logger.error(f"Error checking file status for {filename}: {e}")
        # On error, skip processing (fail safe - don't process without confirming state)
        return False, "dynamodb_error"


def mark_bronze_in_progress(filename: str):
    """Mark bronze processing as in progress in unified tracking table."""
    try:
        table = dynamodb.Table(TRACKING_TABLE)
        now = datetime.utcnow().isoformat()

        table.update_item(
            Key={'file_name': filename},
            UpdateExpression='SET bronze_status = :status, last_updated_at = :updated, #ttl = :ttl',
            ExpressionAttributeNames={'#ttl': 'ttl'},
            ExpressionAttributeValues={
                ':status': 'in_progress',
                ':updated': now,
                ':ttl': int((datetime.utcnow() + timedelta(days=90)).timestamp())
            }
        )
        logger.info(f"⏳ Marked {filename} bronze processing as in_progress")
    except Exception as e:
        logger.error(f"Error marking bronze in_progress for {filename}: {e}")


def mark_bronze_success(filename: str, record_count: int):
    """Mark bronze processing as successful in unified tracking table."""
    try:
        table = dynamodb.Table(TRACKING_TABLE)
        now = datetime.utcnow().isoformat()

        table.update_item(
            Key={'file_name': filename},
            UpdateExpression='SET bronze_parquet_at = :ts, bronze_status = :status, '
                           'last_updated_at = :updated, #ttl = :ttl, record_count = :count',
            ExpressionAttributeNames={'#ttl': 'ttl'},
            ExpressionAttributeValues={
                ':ts': now,
                ':status': 'success',
                ':updated': now,
                ':ttl': int((datetime.utcnow() + timedelta(days=90)).timestamp()),
                ':count': record_count
            }
        )
        logger.info(f"✓ Marked {filename} as bronze complete ({record_count} records)")
    except Exception as e:
        logger.error(f"Error marking bronze success for {filename}: {e}")


def mark_bronze_error(filename: str, error_message: str):
    """Mark bronze processing as failed in unified tracking table."""
    try:
        table = dynamodb.Table(TRACKING_TABLE)
        now = datetime.utcnow().isoformat()

        # Truncate error message to avoid DynamoDB item size limits
        truncated_error = error_message[:500] if error_message else "Unknown error"

        table.update_item(
            Key={'file_name': filename},
            UpdateExpression='SET bronze_status = :status, bronze_error_message = :error, '
                           'last_updated_at = :updated, #ttl = :ttl',
            ExpressionAttributeNames={'#ttl': 'ttl'},
            ExpressionAttributeValues={
                ':status': 'error',
                ':error': truncated_error,
                ':updated': now,
                ':ttl': int((datetime.utcnow() + timedelta(days=90)).timestamp())
            }
        )
        logger.error(f"✗ Marked {filename} as bronze error: {truncated_error}")
    except Exception as e:
        logger.error(f"Error marking bronze failure for {filename}: {e}")


# For local testing
if __name__ == "__main__":
    test_event = {
        "mode": "incremental",
        "offset": 0,
        "limit": 10
    }

    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))
