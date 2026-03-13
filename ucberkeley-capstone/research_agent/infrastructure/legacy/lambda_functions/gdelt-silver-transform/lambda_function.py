"""
Lambda function to create Silver (wide format) table from Bronze parquet data.

Processes data using pandas and AWS Data Wrangler, creating pivoted theme aggregations.
"""

import json
import boto3
import pandas as pd
import awswrangler as wr
from datetime import datetime, timedelta
from typing import Dict, List

# Configuration
BRONZE_PATH = 's3://groundtruth-capstone/processed/gdelt/bronze/gdelt/'
SILVER_PATH = 's3://groundtruth-capstone/processed/gdelt/silver/gdelt_wide/'
TRACKING_TABLE = 'groundtruth-capstone-file-tracking'

# Theme to Group Mapping
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
    Process Bronze data to create Silver wide format table.

    Event structure:
    {
        "start_date": "2024-01-01",  # Optional - defaults to yesterday
        "end_date": "2024-01-31",     # Optional - defaults to yesterday
        "batch_size_days": 7           # Optional - process N days at a time
    }
    """
    print(f"Event: {json.dumps(event)}")

    # Parse parameters
    end_date_str = event.get('end_date', (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d'))
    start_date_str = event.get('start_date', end_date_str)
    batch_size = event.get('batch_size_days', 7)

    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

    print(f"Processing date range: {start_date} to {end_date}")
    print(f"Batch size: {batch_size} days")

    # Read Bronze data for date range
    print(f"Reading Bronze data from {BRONZE_PATH}")
    df_bronze = wr.s3.read_parquet(
        path=BRONZE_PATH,
        dataset=True
    )

    # Transform raw bronze data (date parsing, tone splitting, commodity flagging)
    print("Transforming bronze data...")
    df_transformed = transform_bronze_data(df_bronze)

    # Filter by date range
    df_transformed = df_transformed[
        (df_transformed['article_date'] >= start_date) &
        (df_transformed['article_date'] <= end_date)
    ]

    record_count = len(df_transformed)
    print(f"Loaded {record_count:,} records from Bronze table")

    if record_count == 0:
        print("No data to process")
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'No data to process',
                'records_processed': 0
            })
        }

    # Explode themes and create commodity rows
    print("Exploding themes...")
    df_exploded = explode_themes(df_transformed)
    print(f"Exploded to {len(df_exploded):,} theme records")

    # Aggregate and pivot
    print("Aggregating and pivoting to wide format...")
    df_wide = create_wide_format(df_exploded)
    print(f"Created wide format: {len(df_wide):,} rows × {len(df_wide.columns)} columns")

    # Write to S3 (overwrite partitions to prevent duplicates)
    print(f"Writing to {SILVER_PATH}")
    wr.s3.to_parquet(
        df=df_wide,
        path=SILVER_PATH,
        dataset=True,
        mode='overwrite_partitions',  # Changed from 'append' to prevent duplicates
        partition_cols=['commodity'],
        compression='snappy'
    )

    print(f"✓ Successfully processed {record_count:,} records")

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Success',
            'records_processed': record_count,
            'wide_rows': len(df_wide),
            'wide_columns': len(df_wide.columns),
            'date_range': f"{start_date} to {end_date}"
        })
    }


def transform_bronze_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform raw bronze data: parse dates, split tone, flag commodities.
    All processing logic moved from bronze layer to silver layer.
    """
    # Parse article_date from date field (format: yyyyMMddHHmmss string)
    df['article_date'] = pd.to_datetime(
        df['date'].str[:8],  # Extract YYYYMMDD
        format='%Y%m%d',
        errors='coerce'
    ).dt.date

    # Parse tone fields (comma-separated: avg,positive,negative,polarity)
    tone_split = df['tone'].str.split(',', expand=True)
    df['tone_avg'] = pd.to_numeric(tone_split[0], errors='coerce')
    df['tone_positive'] = pd.to_numeric(tone_split[1], errors='coerce')
    df['tone_negative'] = pd.to_numeric(tone_split[2], errors='coerce')
    df['tone_polarity'] = pd.to_numeric(tone_split[3], errors='coerce')

    # Flag commodities based on all_names
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

    # Drop rows with invalid dates
    df = df.dropna(subset=['article_date'])

    return df


def explode_themes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Explode themes column and create separate rows for coffee and sugar.
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
    """
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
    # CRITICAL: Use int/float (not 'int64'/'float64') to force numpy types
    for col in df_wide.columns:
        if col not in ['article_date', 'commodity']:
            if '_count' in col:
                # Count columns: convert NaN to 0, then force numpy int64
                df_wide[col] = df_wide[col].fillna(0).astype(int)
            else:
                # Tone columns: convert NaN to 0.0, then force float64
                df_wide[col] = df_wide[col].fillna(0.0).astype(float)

    return df_wide


def pivot_metrics(df: pd.DataFrame, pivot_col: str, prefix: str) -> pd.DataFrame:
    """
    Pivot aggregated data to create wide format with metric columns.
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
