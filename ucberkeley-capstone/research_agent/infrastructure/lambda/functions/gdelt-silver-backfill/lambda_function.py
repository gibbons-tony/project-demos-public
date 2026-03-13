"""
Lambda function for Silver Backfill - SQS-based date processing.

Processes Bronze → Silver transformation one DATE at a time via SQS queue.
Each SQS message contains a single date to process.

Architecture:
- SQS Queue: groundtruth-gdelt-silver-backfill-queue
- Message format: {"date": "2021-01-01"}
- DynamoDB tracking: SILVER_{date} entries for progress tracking
- S3 write: Overwrite partitions to prevent duplicates
"""

import json
import boto3
import pandas as pd
import numpy as np
import awswrangler as wr
from datetime import datetime, timedelta
from typing import Dict, List
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS Clients
dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')

# Configuration
BRONZE_PATH = 's3://groundtruth-capstone/processed/gdelt/bronze/gdelt/'
SILVER_PATH = 's3://groundtruth-capstone/processed/gdelt/silver/gdelt_wide/'
TRACKING_TABLE = 'groundtruth-capstone-file-tracking'

# Theme to Group Mapping (matches notebook exactly - 43 themes)
THEME_TO_GROUP = {
    # SUPPLY - Production/harvest disruptions (7 themes)
    'NATURAL_DISASTER': 'SUPPLY',
    'CLIMATE_CHANGE': 'SUPPLY',
    'TAX_DISEASE': 'SUPPLY',
    'TAX_PLANTDISEASE': 'SUPPLY',
    'TAX_PESTS': 'SUPPLY',
    'STRIKE': 'SUPPLY',
    'ECON_UNIONS': 'SUPPLY',

    # LOGISTICS - Transportation/distribution (6 themes)
    'CRISIS_LOGISTICS': 'LOGISTICS',
    'CRISISLEX_C04_LOGISTICS_TRANSPORT': 'LOGISTICS',
    'BLOCKADE': 'LOGISTICS',
    'DELAY': 'LOGISTICS',
    'CLOSURE': 'LOGISTICS',
    'BORDER': 'LOGISTICS',

    # TRADE - International commerce (6 themes)
    'ECON_FREETRADE': 'TRADE',
    'ECON_TRADE_DISPUTE': 'TRADE',
    'TAX_TARIFFS': 'TRADE',
    'ECON_SUBSIDIES': 'TRADE',
    'ECON_CURRENCY_EXCHANGE_RATE': 'TRADE',
    'WB_698_TRADE': 'TRADE',

    # MARKET - Financial/macro (9 themes)
    'ECON_STOCKMARKET': 'MARKET',
    'ECON_EARNINGSREPORT': 'MARKET',
    'ECON_INTEREST_RATES': 'MARKET',
    'ECON_DEBT': 'MARKET',
    'ECON_INFLATION': 'MARKET',
    'ECON_COST_OF_LIVING': 'MARKET',
    'ENERGY': 'MARKET',
    'OIL': 'MARKET',
    'ECON_BITCOIN': 'MARKET',

    # POLICY - Government/political (11 themes)
    'LEGISLATION': 'POLICY',
    'GOV_REFORM': 'POLICY',
    'GENERAL_GOVERNMENT': 'POLICY',
    'STATE_OF_EMERGENCY': 'POLICY',
    'ELECTION': 'POLICY',
    'CORRUPTION': 'POLICY',
    'NEGOTIATIONS': 'POLICY',
    'ALLIANCE': 'POLICY',
    'CEASEFIRE': 'POLICY',
    'EPU_POLICY': 'POLICY',
    'EPU_POLICY_GOVERNMENT': 'POLICY',

    # CORE - Direct commodity topics (4 themes)
    'AGRICULTURE': 'CORE',
    'FOOD_STAPLE': 'CORE',
    'FOOD_SECURITY': 'CORE',
    'WB_2044_RURAL_WATER': 'CORE',
}


def lambda_handler(event, context):
    """
    Main Lambda handler - processes Bronze → Silver for one date from SQS.

    Event structure (SQS):
    {
        "Records": [
            {
                "body": "{\"date\": \"2021-01-01\"}",
                "receiptHandle": "..."
            }
        ]
    }

    Or direct invocation:
    {
        "date": "2021-01-01"
    }
    """
    logger.info(f"Event: {json.dumps(event)}")

    try:
        # Check if this is an SQS event
        if 'Records' in event:
            # Process SQS messages
            processed_count = 0

            for record in event['Records']:
                message_body = json.loads(record['body'])
                date_str = message_body.get('date')

                if not date_str:
                    logger.error(f"No date in message: {record['body']}")
                    continue

                logger.info(f"Processing date: {date_str}")

                try:
                    result = process_date(date_str)
                    processed_count += 1
                    logger.info(f"✓ Processed {date_str}: {result}")

                except Exception as e:
                    logger.error(f"Error processing {date_str}: {e}", exc_info=True)
                    mark_date_silver_error(date_str, str(e))
                    # Don't raise - let other messages in batch process

            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'SQS batch processed',
                    'dates_processed': processed_count
                })
            }

        else:
            # Direct invocation
            date_str = event.get('date')
            if not date_str:
                raise ValueError("Missing 'date' parameter")

            logger.info(f"Direct invocation for date: {date_str}")
            result = process_date(date_str)

            return {
                'statusCode': 200,
                'body': json.dumps(result)
            }

    except Exception as e:
        logger.error(f"Handler error: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def process_date(date_str: str) -> Dict:
    """
    Process a single date: read bronze data, transform, write to silver.

    Returns dict with processing stats.
    """
    process_date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()

    # Check if already processed
    if should_skip_date(date_str):
        logger.info(f"Skipping {date_str} - already processed")
        return {'status': 'skipped', 'reason': 'already_processed'}

    # Mark as in progress
    mark_date_silver_in_progress(date_str)

    try:
        # Read bronze data for this specific date
        # Note: For large dates (>30 files), this returns pre-aggregated wide format
        logger.info(f"Reading bronze data for {date_str}...")
        df_result, bronze_files_found = read_bronze_for_date(date_str)

        # Check bronze completeness
        bronze_completeness, bronze_expected = check_bronze_completeness(date_str, bronze_files_found)

        if len(df_result) == 0:
            logger.info(f"No bronze data found for {date_str}")
            mark_date_silver_success(date_str, 0, 0, bronze_files_found, bronze_completeness, bronze_expected)
            return {'status': 'no_data', 'date': date_str}

        # Check if this is already wide format (from chunked processing)
        is_wide_format = 'article_date' in df_result.columns and 'commodity' in df_result.columns

        if is_wide_format:
            # Already processed in chunks, just use it
            df_wide = df_result
            record_count = 0  # Can't track individual records for chunked processing
            logger.info(f"Received pre-aggregated wide format: {len(df_wide):,} rows × {len(df_wide.columns)} columns")
        else:
            # Normal processing for small dates
            logger.info(f"Loaded {len(df_result):,} bronze records")

            # Transform
            logger.info("Transforming bronze data...")
            df_transformed = transform_bronze_data(df_result)

            # Filter by exact date
            df_transformed = df_transformed[
                df_transformed['article_date'] == process_date_obj
            ]

            record_count = len(df_transformed)
            logger.info(f"Filtered to {record_count:,} records for {date_str}")

            if record_count == 0:
                mark_date_silver_success(date_str, 0, 0, bronze_files_found, bronze_completeness, bronze_expected)
                return {'status': 'no_data', 'date': date_str}

            # Explode themes
            logger.info("Exploding themes...")
            df_exploded = explode_themes(df_transformed)
            logger.info(f"Exploded to {len(df_exploded):,} theme records")

            # Create wide format
            logger.info("Creating wide format...")
            df_wide = create_wide_format(df_exploded)
            logger.info(f"Created wide format: {len(df_wide):,} rows × {len(df_wide.columns)} columns")

        # Write to silver
        logger.info(f"Writing to {SILVER_PATH}...")
        wr.s3.to_parquet(
            df=df_wide,
            path=SILVER_PATH,
            dataset=True,
            mode='overwrite_partitions',  # Prevent duplicates
            partition_cols=['article_date', 'commodity'],  # Partition by date AND commodity
            compression='snappy'
        )

        # Mark success with bronze completeness tracking
        mark_date_silver_success(date_str, record_count, len(df_wide),
                                bronze_files_found, bronze_completeness, bronze_expected)

        logger.info(f"✓ Successfully processed {date_str}")

        return {
            'status': 'success',
            'date': date_str,
            'bronze_records': record_count,
            'wide_rows': len(df_wide),
            'wide_columns': len(df_wide.columns)
        }

    except Exception as e:
        logger.error(f"Error processing {date_str}: {e}", exc_info=True)
        mark_date_silver_error(date_str, str(e))
        raise


def read_bronze_for_date(date_str: str) -> pd.DataFrame:
    """
    Read bronze parquet data for a specific date.
    Uses file path filtering to read only files for this date.

    Bronze files are named: YYYYMMDDHHMMSS.gkg.parquet
    So we can filter by path prefix.

    For large dates, this reads files in batches to avoid OOM errors.
    """
    # Convert date to YYYYMMDD format
    date_prefix = date_str.replace('-', '')  # "2021-01-01" -> "20210101"

    # List all bronze files for this date
    bucket = 'groundtruth-capstone'
    prefix = f'processed/gdelt/bronze/gdelt/'

    matching_files = []

    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        if 'Contents' not in page:
            continue

        for obj in page['Contents']:
            key = obj['Key']
            # Extract filename from path
            filename = key.split('/')[-1]
            # Check if filename starts with our date
            if filename.startswith(date_prefix) and filename.endswith('.parquet'):
                matching_files.append(f's3://{bucket}/{key}')

    bronze_file_count = len(matching_files)
    logger.info(f"Found {bronze_file_count} bronze files for {date_str}")

    if not matching_files:
        return pd.DataFrame(), 0

    # For large dates (>30 files), process in batches to avoid OOM
    # Lowered from 50 to 30 after finding 49-file dates still cause OOM
    if bronze_file_count > 30:
        logger.info(f"Large date detected ({bronze_file_count} files), processing in batches...")
        df = read_bronze_chunked(matching_files, date_str)
        return df, bronze_file_count

    # Read all matching files for small dates
    df = wr.s3.read_parquet(path=matching_files)

    return df, bronze_file_count


def read_bronze_chunked(file_list: list, date_str: str) -> pd.DataFrame:
    """
    Read bronze files in chunks and return aggregated wide format directly.
    This avoids loading all raw data into memory at once.

    Returns pre-aggregated wide format dataframe.
    """
    CHUNK_SIZE = 25  # Process 25 files at a time
    chunks = [file_list[i:i+CHUNK_SIZE] for i in range(0, len(file_list), CHUNK_SIZE)]

    process_date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    aggregated_dfs = []
    total_records = 0

    for i, chunk in enumerate(chunks):
        logger.info(f"Processing chunk {i+1}/{len(chunks)} ({len(chunk)} files)...")

        # Read chunk
        df_chunk = wr.s3.read_parquet(path=chunk)
        total_records += len(df_chunk)

        # Transform, filter, explode, and aggregate this chunk
        df_chunk = transform_bronze_data(df_chunk)
        df_chunk = df_chunk[df_chunk['article_date'] == process_date_obj]

        if len(df_chunk) == 0:
            continue

        df_chunk = explode_themes(df_chunk)
        df_wide_chunk = create_wide_format(df_chunk)

        aggregated_dfs.append(df_wide_chunk)

        # Clear memory
        del df_chunk
        del df_wide_chunk

    logger.info(f"Processed {total_records:,} total records in {len(chunks)} chunks")

    if not aggregated_dfs:
        return pd.DataFrame()

    # Combine aggregated chunks by summing metrics
    logger.info(f"Combining {len(aggregated_dfs)} aggregated chunks...")
    df_combined = combine_wide_chunks(aggregated_dfs)

    return df_combined


def should_skip_date(date_str: str) -> bool:
    """Check if date is already successfully processed."""
    table = dynamodb.Table(TRACKING_TABLE)
    tracking_key = f"SILVER_{date_str}"

    try:
        response = table.get_item(Key={'file_name': tracking_key})
        if 'Item' in response:
            status = response['Item'].get('silver_status')
            if status == 'success':
                return True
    except Exception as e:
        logger.warning(f"Error checking status for {date_str}: {e}")

    return False


def mark_date_silver_in_progress(date_str: str):
    """Mark a date as silver processing in progress."""
    table = dynamodb.Table(TRACKING_TABLE)
    now = datetime.utcnow().isoformat()
    ttl = int((datetime.utcnow() + timedelta(days=90)).timestamp())

    tracking_key = f"SILVER_{date_str}"

    try:
        table.put_item(
            Item={
                'file_name': tracking_key,
                'silver_date': date_str,
                'silver_status': 'in_progress',
                'silver_started_at': now,
                'last_updated_at': now,
                'ttl': ttl
            }
        )
        logger.info(f"Marked {date_str} as in_progress")
    except Exception as e:
        logger.error(f"Error marking {date_str} as in_progress: {e}")


def check_bronze_completeness(date_str: str, bronze_files_found: int) -> tuple[str, int]:
    """
    Check if all expected bronze files for a date have been processed.

    Returns: (completeness_status, expected_files_count)
        completeness_status: 'complete', 'partial', or 'unknown'
        expected_files_count: number of expected files based on DynamoDB tracking
    """
    table = dynamodb.Table(TRACKING_TABLE)

    # Convert date to YYYYMMDD format for filename matching
    date_prefix = date_str.replace('-', '')

    try:
        # Scan DynamoDB for all files matching this date with bronze_status='success'
        response = table.scan(
            FilterExpression='begins_with(file_name, :prefix) AND bronze_status = :status',
            ExpressionAttributeValues={
                ':prefix': date_prefix,
                ':status': 'success'
            }
        )

        bronze_success_count = len(response.get('Items', []))

        # Handle pagination if needed
        while 'LastEvaluatedKey' in response:
            response = table.scan(
                FilterExpression='begins_with(file_name, :prefix) AND bronze_status = :status',
                ExpressionAttributeValues={
                    ':prefix': date_prefix,
                    ':status': 'success'
                },
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            bronze_success_count += len(response.get('Items', []))

        logger.info(f"DynamoDB check: {bronze_success_count} bronze files with status=success for {date_str}")

        # Compare: if S3 bronze files == DynamoDB success count, assume complete
        # (This assumes all files that made it to S3 are tracked in DynamoDB)
        if bronze_files_found == bronze_success_count:
            return 'complete', bronze_success_count
        elif bronze_files_found < bronze_success_count:
            # Fewer files in S3 than DynamoDB claims - unusual, mark as unknown
            logger.warning(f"S3 has {bronze_files_found} files but DynamoDB shows {bronze_success_count} - marking as unknown")
            return 'unknown', bronze_success_count
        else:
            # More files in S3 than DynamoDB success count - some may still be processing
            logger.warning(f"S3 has {bronze_files_found} files but only {bronze_success_count} marked success in DynamoDB - marking as partial")
            return 'partial', bronze_success_count

    except Exception as e:
        logger.error(f"Error checking bronze completeness: {e}")
        return 'unknown', 0


def mark_date_silver_success(date_str: str, record_count: int, wide_rows: int,
                            bronze_files_found: int, bronze_completeness: str,
                            bronze_expected: int):
    """Mark a date as successfully silver-processed with bronze completeness tracking."""
    table = dynamodb.Table(TRACKING_TABLE)
    now = datetime.utcnow().isoformat()
    ttl = int((datetime.utcnow() + timedelta(days=90)).timestamp())

    tracking_key = f"SILVER_{date_str}"

    try:
        table.update_item(
            Key={'file_name': tracking_key},
            UpdateExpression='SET silver_status = :status, silver_completed_at = :completed, '
                           'silver_record_count = :count, silver_wide_rows = :wide, '
                           'bronze_completeness_status = :completeness, '
                           'bronze_files_found = :found, bronze_files_expected = :expected, '
                           'last_updated_at = :updated, #ttl = :ttl',
            ExpressionAttributeNames={'#ttl': 'ttl'},
            ExpressionAttributeValues={
                ':status': 'success',
                ':completed': now,
                ':count': record_count,
                ':wide': wide_rows,
                ':completeness': bronze_completeness,
                ':found': bronze_files_found,
                ':expected': bronze_expected,
                ':updated': now,
                ':ttl': ttl
            }
        )
        logger.info(f"✓ Marked {date_str} as success ({record_count} records, {wide_rows} wide rows, bronze: {bronze_completeness} - {bronze_files_found}/{bronze_expected} files)")
    except Exception as e:
        logger.error(f"Error marking {date_str} as success: {e}")


def mark_date_silver_error(date_str: str, error_msg: str):
    """Mark a date as failed silver processing."""
    table = dynamodb.Table(TRACKING_TABLE)
    now = datetime.utcnow().isoformat()
    ttl = int((datetime.utcnow() + timedelta(days=90)).timestamp())

    tracking_key = f"SILVER_{date_str}"

    try:
        table.update_item(
            Key={'file_name': tracking_key},
            UpdateExpression='SET silver_status = :status, silver_error = :error, '
                           'last_updated_at = :updated, #ttl = :ttl',
            ExpressionAttributeNames={'#ttl': 'ttl'},
            ExpressionAttributeValues={
                ':status': 'error',
                ':error': error_msg[:500],  # Truncate long errors
                ':updated': now,
                ':ttl': ttl
            }
        )
        logger.error(f"Marked {date_str} as error: {error_msg[:100]}")
    except Exception as e:
        logger.error(f"Error marking {date_str} as failed: {e}")


def transform_bronze_data(df: pd.DataFrame) -> pd.DataFrame:
    """Transform raw bronze data."""
    df['article_date'] = pd.to_datetime(
        df['date'].str[:8],
        format='%Y%m%d',
        errors='coerce'
    ).dt.date

    # Parse tone fields
    tone_split = df['tone'].str.split(',', expand=True)
    df['tone_avg'] = pd.to_numeric(tone_split[0], errors='coerce')
    df['tone_positive'] = pd.to_numeric(tone_split[1], errors='coerce')
    df['tone_negative'] = pd.to_numeric(tone_split[2], errors='coerce')
    df['tone_polarity'] = pd.to_numeric(tone_split[3], errors='coerce')

    # Flag commodities
    all_names_lower = df['all_names'].str.lower()

    df['has_coffee'] = all_names_lower.str.contains(
        'coffee|arabica|robusta',
        regex=True,
        na=False
    )

    df['has_sugar'] = (
        all_names_lower.str.contains('sugarcane|sugar cane', regex=True, na=False) |
        (all_names_lower.str.contains('sugar', regex=False, na=False) &
         ~all_names_lower.str.contains('sugar ray', regex=False, na=False))
    )

    df = df.dropna(subset=['article_date'])
    return df


def explode_themes(df: pd.DataFrame) -> pd.DataFrame:
    """Explode themes and create commodity rows."""
    df['theme_list'] = df['themes'].str.split(';')
    df_exploded = df.explode('theme_list')
    df_exploded = df_exploded[df_exploded['theme_list'].notna() & (df_exploded['theme_list'] != '')]
    df_exploded = df_exploded.rename(columns={'theme_list': 'theme'})

    df_coffee = df_exploded[df_exploded['has_coffee']].copy()
    df_coffee['commodity'] = 'coffee'

    df_sugar = df_exploded[df_exploded['has_sugar']].copy()
    df_sugar['commodity'] = 'sugar'

    df_combined = pd.concat([df_coffee, df_sugar], ignore_index=True)
    df_combined['theme_group'] = df_combined['theme'].map(THEME_TO_GROUP).fillna('OTHER')

    return df_combined


def create_wide_format(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate and pivot to wide format."""
    # Aggregate ALL themes (group_ALL)
    all_agg = df.groupby(['article_date', 'commodity']).agg({
        'source_url': 'count',  # count of articles
        'tone_avg': 'mean',
        'tone_positive': 'mean',
        'tone_negative': 'mean',
        'tone_polarity': 'mean'
    }).reset_index()

    all_agg = all_agg.rename(columns={
        'source_url': 'group_ALL_count',
        'tone_avg': 'group_ALL_tone_avg',
        'tone_positive': 'group_ALL_tone_positive',
        'tone_negative': 'group_ALL_tone_negative',
        'tone_polarity': 'group_ALL_tone_polarity'
    })

    # IMPORTANT: Filter to only themes we're tracking (not all 584 GDELT themes!)
    df_tracked = df[df['theme'].isin(THEME_TO_GROUP.keys())].copy()

    # Aggregate by individual theme (only tracked themes)
    theme_agg = df_tracked.groupby(['article_date', 'commodity', 'theme']).agg({
        'source_url': 'count',
        'tone_avg': 'mean',
        'tone_positive': 'mean',
        'tone_negative': 'mean',
        'tone_polarity': 'mean'
    }).reset_index()
    theme_agg = theme_agg.rename(columns={'source_url': 'count'})

    # Aggregate by theme group
    group_agg = df.groupby(['article_date', 'commodity', 'theme_group']).agg({
        'source_url': 'count',
        'tone_avg': 'mean',
        'tone_positive': 'mean',
        'tone_negative': 'mean',
        'tone_polarity': 'mean'
    }).reset_index()
    group_agg = group_agg.rename(columns={'source_url': 'count'})

    # Pivot
    group_wide = pivot_metrics(group_agg, 'theme_group', prefix='group_')
    theme_wide = pivot_metrics(theme_agg, 'theme', prefix='theme_')

    # Merge ALL with groups
    df_wide = pd.merge(
        all_agg,
        group_wide,
        on=['article_date', 'commodity'],
        how='outer'
    )

    # Merge with individual themes
    df_wide = pd.merge(
        df_wide,
        theme_wide,
        on=['article_date', 'commodity'],
        how='outer'
    )

    # Fill NaN with appropriate values THEN convert types
    # CRITICAL: Use np.int64/np.float64 explicitly to force numpy types (not pandas Int64/Float64)
    for col in df_wide.columns:
        if col not in ['article_date', 'commodity']:
            if '_count' in col:
                # Count columns: convert NaN to 0, then force numpy int64
                df_wide[col] = df_wide[col].fillna(0).astype(np.int64)
            else:
                # Tone columns: convert NaN to 0.0, then force float64
                df_wide[col] = df_wide[col].fillna(0.0).astype(np.float64)

    return df_wide


def combine_wide_chunks(chunk_dfs: list) -> pd.DataFrame:
    """
    Combine multiple wide format dataframes by recalculating weighted averages.

    Each chunk has aggregated metrics (counts and tone averages).
    We need to combine them properly by:
    - Summing counts
    - Recalculating weighted averages based on counts
    """
    if len(chunk_dfs) == 1:
        return chunk_dfs[0]

    # Start with first chunk
    combined = chunk_dfs[0].copy()

    for df_chunk in chunk_dfs[1:]:
        # Merge on article_date and commodity
        combined = combined.merge(
            df_chunk,
            on=['article_date', 'commodity'],
            how='outer',
            suffixes=('', '_new')
        )

        # For each metric column, combine values
        # Get all columns from merged dataframe (excluding base cols and _new suffixes)
        base_cols = ['article_date', 'commodity']
        all_cols = set(combined.columns) - set(base_cols)
        metric_cols = [c for c in all_cols if not c.endswith('_new')]

        for col in metric_cols:
            new_col = f'{col}_new'

            # Check if this column has a _new version (exists in both chunks)
            if new_col in combined.columns:
                if col.endswith('_count'):
                    # Sum counts
                    combined[col] = combined[col].fillna(0) + combined[new_col].fillna(0)
                elif col.endswith('_tone_avg'):
                    # Recalculate weighted average
                    count_col = col.replace('_tone_avg', '_count')
                    count_new_col = f'{count_col}_new'

                    # Check if count columns exist for weighted average calculation
                    if count_new_col in combined.columns:
                        old_count = combined[count_col].fillna(0) - combined[count_new_col].fillna(0)
                        new_count = combined[count_new_col].fillna(0)
                        total_count = combined[count_col].fillna(0)
                    else:
                        # Count column doesn't exist in new chunk, keep old average
                        old_count = combined[count_col].fillna(0)
                        new_count = 0
                        total_count = combined[count_col].fillna(0)

                    old_avg = combined[col].fillna(0)
                    new_avg = combined[new_col].fillna(0)

                    # Weighted average: (old_count * old_avg + new_count * new_avg) / total_count
                    combined[col] = np.where(
                        total_count > 0,
                        (old_count * old_avg + new_count * new_avg) / total_count,
                        0
                    )
                else:
                    # For tone_positive, tone_negative, tone_polarity: sum them
                    combined[col] = combined[col].fillna(0) + combined[new_col].fillna(0)
            # else: column only exists in one chunk, keep as-is

        # Drop _new columns
        new_cols = [c for c in combined.columns if c.endswith('_new')]
        combined = combined.drop(columns=new_cols)

    # CRITICAL FIX: Force data types after combining chunks
    # The arithmetic operations above create pandas Int64/Float64, not numpy int64/float64
    for col in combined.columns:
        if col not in ['article_date', 'commodity']:
            if '_count' in col:
                # Count columns: force numpy int64
                combined[col] = combined[col].astype(np.int64)
            else:
                # Tone columns: force float64
                combined[col] = combined[col].astype(np.float64)

    return combined


def pivot_metrics(df: pd.DataFrame, pivot_col: str, prefix: str) -> pd.DataFrame:
    """Pivot aggregated data to create wide format."""
    result = df.pivot_table(
        index=['article_date', 'commodity'],
        columns=pivot_col,
        values=['count', 'tone_avg', 'tone_positive', 'tone_negative', 'tone_polarity'],
        aggfunc='first'
    )

    result.columns = [f"{prefix}{col[1]}_{col[0]}" for col in result.columns]
    result = result.reset_index()
    return result
