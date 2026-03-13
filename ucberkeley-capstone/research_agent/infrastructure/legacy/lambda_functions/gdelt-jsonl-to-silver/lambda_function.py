"""
One-time Lambda to create Silver layer directly from JSONL files.

Combines Bronze transformation (date parsing, tone splitting, commodity flags)
with Silver transformation (theme explosion, aggregation, wide format).

This is a temporary Lambda for fast silver generation. Once Bronze migration
completes, use gdelt-silver-transform instead.
"""

import json
import boto3
import pandas as pd
import awswrangler as wr
from datetime import datetime, timedelta
from typing import Dict, List
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3 = boto3.client('s3')

# Configuration
S3_BUCKET = 'groundtruth-capstone'
S3_JSONL_PREFIX = 'landing/gdelt/filtered/'
SILVER_PATH = 's3://groundtruth-capstone/processed/gdelt/silver/gdelt_wide/'

# Theme to Group Mapping (from gdelt-silver-transform)
THEME_TO_GROUP = {
    # SUPPLY - Production/harvest disruptions
    'NATURAL_DISASTER': 'SUPPLY',
    'CLIMATE_CHANGE': 'SUPPLY',
    'TAX_DISEASE': 'SUPPLY',
    'TAX_PLANTDISEASE': 'SUPPLY',
    'TAX_PESTS': 'SUPPLY',
    'STRIKE': 'SUPPLY',
    'ECON_UNIONS': 'SUPPLY',

    # LOGISTICS - Transportation/distribution
    'CRISIS_LOGISTICS': 'LOGISTICS',
    'BLOCKADE': 'LOGISTICS',
    'DELAY': 'LOGISTICS',
    'CLOSURE': 'LOGISTICS',
    'BORDER': 'LOGISTICS',

    # TRADE - International commerce
    'ECON_FREETRADE': 'TRADE',
    'ECON_TRADE_DISPUTE': 'TRADE',
    'TAX_TARIFFS': 'TRADE',
    'ECON_SUBSIDIES': 'TRADE',
    'ECON_CURRENCY_EXCHANGE_RATE': 'TRADE',

    # MARKET - Financial/macro
    'ECON_STOCKMARKET': 'MARKET',
    'ECON_EARNINGSREPORT': 'MARKET',
    'ECON_INTEREST_RATES': 'MARKET',
    'ECON_DEBT': 'MARKET',
    'ECON_COST_OF_LIVING': 'MARKET',
    'ENERGY': 'MARKET',
    'OIL': 'MARKET',

    # POLICY - Government/political
    'LEGISLATION': 'POLICY',
    'GOV_REFORM': 'POLICY',
    'GENERAL_GOVERNMENT': 'POLICY',
    'STATE_OF_EMERGENCY': 'POLICY',
    'ELECTION': 'POLICY',
    'CORRUPTION': 'POLICY',

    # CORE - Direct commodity topics
    'AGRICULTURE': 'CORE',
    'FOOD_STAPLE': 'CORE',
    'FOOD_SECURITY': 'CORE',
}


def lambda_handler(event, context):
    """
    Process JSONL files directly to Silver wide format.

    Event structure:
    {
        "start_date": "2021-01-01",  # Optional - defaults to all files
        "end_date": "2021-12-31",     # Optional - defaults to all files
        "batch_size": 1000            # Number of files to process per run
    }
    """
    logger.info(f"Event: {json.dumps(event)}")

    # Parse parameters
    start_date_str = event.get('start_date')
    end_date_str = event.get('end_date')
    batch_size = event.get('batch_size', 1000)

    # List all JSONL files
    logger.info(f"Listing JSONL files from {S3_JSONL_PREFIX}")
    all_files = list_s3_files(S3_BUCKET, S3_JSONL_PREFIX)
    logger.info(f"Found {len(all_files):,} total JSONL files")

    # Filter by date range if specified
    if start_date_str or end_date_str:
        all_files = filter_files_by_date(all_files, start_date_str, end_date_str)
        logger.info(f"Filtered to {len(all_files):,} files in date range")

    # Limit batch size
    if len(all_files) > batch_size:
        files_to_process = all_files[:batch_size]
        logger.info(f"Processing first {batch_size} files")
    else:
        files_to_process = all_files

    if not files_to_process:
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'No files to process',
                'total_files': 0
            })
        }

    # Process files in batches to avoid memory issues
    logger.info(f"Processing {len(files_to_process):,} JSONL files...")

    # Read and combine all JSONL data
    all_dataframes = []
    for i, s3_key in enumerate(files_to_process):
        if i % 100 == 0:
            logger.info(f"Reading file {i}/{len(files_to_process)}")

        try:
            response = s3.get_object(Bucket=S3_BUCKET, Key=s3_key)
            df = pd.read_json(response['Body'], lines=True, convert_dates=False)

            if not df.empty:
                all_dataframes.append(df)
        except Exception as e:
            logger.error(f"Error reading {s3_key}: {e}")
            continue

    if not all_dataframes:
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'No data found in files',
                'files_processed': len(files_to_process)
            })
        }

    # Combine all data
    logger.info(f"Combining {len(all_dataframes)} dataframes...")
    df_combined = pd.concat(all_dataframes, ignore_index=True)
    logger.info(f"Combined data: {len(df_combined):,} records")

    # Transform to Bronze schema
    logger.info("Transforming to bronze schema...")
    df_bronze = transform_to_bronze(df_combined)
    logger.info(f"Bronze transformation: {len(df_bronze):,} records")

    # Transform to Silver schema
    logger.info("Exploding themes...")
    df_exploded = explode_themes(df_bronze)
    logger.info(f"Exploded to {len(df_exploded):,} theme records")

    logger.info("Aggregating and pivoting to wide format...")
    df_wide = create_wide_format(df_exploded)
    logger.info(f"Created wide format: {len(df_wide):,} rows × {len(df_wide.columns)} columns")

    # Write to Silver location
    logger.info(f"Writing to {SILVER_PATH}")
    wr.s3.to_parquet(
        df=df_wide,
        path=SILVER_PATH,
        dataset=True,
        mode='append',  # Append since this is one-time processing
        partition_cols=['commodity'],
        compression='snappy'
    )

    logger.info(f"✓ Successfully processed {len(files_to_process):,} files")

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Success',
            'files_processed': len(files_to_process),
            'records_processed': len(df_bronze),
            'wide_rows': len(df_wide),
            'wide_columns': len(df_wide.columns),
            'remaining_files': len(all_files) - len(files_to_process)
        })
    }


def list_s3_files(bucket: str, prefix: str) -> List[str]:
    """List all JSONL files in S3 bucket."""
    files = []
    paginator = s3.get_paginator('list_objects_v2')

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        if 'Contents' in page:
            for obj in page['Contents']:
                key = obj['Key']
                if key.endswith('.jsonl'):
                    files.append(key)

    return files


def filter_files_by_date(files: List[str], start_date_str: str = None, end_date_str: str = None) -> List[str]:
    """Filter files by date range based on filename (YYYYMMDD format)."""
    filtered = []

    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None

    for file_key in files:
        # Extract date from filename: 20210101000000.jsonl -> 20210101
        filename = file_key.split('/')[-1]
        date_str = filename[:8]

        try:
            file_date = datetime.strptime(date_str, '%Y%m%d').date()

            if start_date and file_date < start_date:
                continue
            if end_date and file_date > end_date:
                continue

            filtered.append(file_key)
        except ValueError:
            continue

    return filtered


def transform_to_bronze(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform JSONL schema to Bronze Parquet schema.
    From gdelt-bronze-transform/lambda_function.py
    """
    logger.info(f"Transform input: {len(df)} rows")

    df_bronze = pd.DataFrame()

    # Parse article_date from date field (format: yyyyMMddHHmmss)
    date_str = df['date'].astype(str).str.replace('.0', '', regex=False).str[:8]

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

    logger.info(f"Valid records after bronze transform: {len(df_bronze)}")

    return df_bronze


def explode_themes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Explode themes column and create separate rows for coffee and sugar.
    From gdelt-silver-transform/lambda_function.py
    """
    # Split themes by semicolon
    df['theme_list'] = df['themes'].str.split(';')

    # Explode to one row per theme
    df_exploded = df.explode('theme_list')
    df_exploded = df_exploded[df_exploded['theme_list'].notna() & (df_exploded['theme_list'] != '')]
    df_exploded = df_exploded.rename(columns={'theme_list': 'theme'})

    # Create separate rows for coffee and sugar
    df_coffee = df_exploded[df_exploded['has_coffee']].copy()
    df_coffee['commodity'] = 'coffee'

    df_sugar = df_exploded[df_exploded['has_sugar']].copy()
    df_sugar['commodity'] = 'sugar'

    df_combined = pd.concat([df_coffee, df_sugar], ignore_index=True)

    # Add theme group
    df_combined['theme_group'] = df_combined['theme'].map(THEME_TO_GROUP).fillna('OTHER')

    return df_combined


def create_wide_format(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate by theme and pivot to wide format.
    From gdelt-silver-transform/lambda_function.py
    """
    # Aggregate by individual theme
    theme_agg = df.groupby(['article_date', 'commodity', 'theme']).agg({
        'source_url': 'count',  # count of articles
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

    # Pivot theme groups
    group_wide = pivot_metrics(group_agg, 'theme_group', prefix='group_')

    # Pivot individual themes
    theme_wide = pivot_metrics(theme_agg, 'theme', prefix='theme_')

    # Merge
    df_wide = pd.merge(
        group_wide,
        theme_wide,
        on=['article_date', 'commodity'],
        how='outer'
    )

    # Fill NaN with 0
    df_wide = df_wide.fillna(0)

    return df_wide


def pivot_metrics(df: pd.DataFrame, pivot_col: str, prefix: str) -> pd.DataFrame:
    """
    Pivot aggregated data to create wide format with metric columns.
    From gdelt-silver-transform/lambda_function.py
    """
    result = df.pivot_table(
        index=['article_date', 'commodity'],
        columns=pivot_col,
        values=['count', 'tone_avg', 'tone_positive', 'tone_negative', 'tone_polarity'],
        aggfunc='first'
    )

    # Flatten multi-level columns
    result.columns = [f"{prefix}{col[1]}_{col[0]}" for col in result.columns]
    result = result.reset_index()

    return result


# For local testing
if __name__ == "__main__":
    test_event = {
        "start_date": "2021-01-01",
        "end_date": "2021-01-07",
        "batch_size": 100
    }

    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))
