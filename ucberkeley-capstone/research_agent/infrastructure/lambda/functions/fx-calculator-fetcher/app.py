import os
import io
import time
import json
import requests
import pandas as pd
import boto3
import datetime as dt
from botocore.exceptions import ClientError
from fredapi import Fred

# --- Configuration ---
# FRED_API_KEY and S3_BUCKET_NAME are supplied via environment variables from template.yaml
# We set a hardcoded start date for historical data fetching
HISTORICAL_START_DATE = '2015-01-01'
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')

def get_worldbank_exchange_rate(country_code, currency_name):
    """
    Get exchange rate from World Bank for currencies not available in FRED.
    Returns annual data forward-filled to daily frequency.

    Parameters:
        country_code: ISO 3-letter country code (e.g., 'VNM' for Vietnam)
        currency_name: Currency abbreviation (e.g., 'vnd')
    """
    print(f"  - Getting {currency_name.upper()}/USD...")
    try:
        url = f'https://api.worldbank.org/v2/country/{country_code}/indicator/PA.NUS.FCRF?format=json&per_page=500&date=2015:2025'
        response = requests.get(url, timeout=15)
        data = response.json()

        if len(data) > 1 and data[1]:
            records = []
            for item in data[1]:
                if item['value'] is not None:
                    year = int(item['date'])
                    date = pd.Timestamp(f'{year}-06-30')
                    records.append({'date': date, f'{currency_name}_usd': item['value']})

            if records:
                df = pd.DataFrame(records)
                df = df.set_index('date').resample('D').ffill().reset_index()
                print(f"    ✓ {currency_name.upper()}: {len(df)} records")
                return df
    except Exception as e:
        print(f"    ! {currency_name.upper()}: {str(e)[:50]}")

    return pd.DataFrame()

def get_daily_macro(start_date):
    """
    COMPREHENSIVE macro data - 40 currencies covering 98%+ of production,
    starting from the provided start_date.
    """

    print(f"Starting comprehensive macro indicators and FX rates collection from {start_date}...")
    key = os.getenv('FRED_API_KEY')
    if not key:
        print("  ! No FRED API key")
        return pd.DataFrame()

    fred = Fred(api_key=key)

    # FRED-available currencies
    fred_series = {
        'DEXBZUS': 'brl_usd',      # Brazil
        'DEXINUS': 'inr_usd',      # India
        'DEXCHUS': 'cny_usd',      # China
        'DEXTHUS': 'thb_usd',      # Thailand
        'DEXMXUS': 'mxn_usd',      # Mexico
        'DEXUSAL': 'aud_usd',      # Australia
        'DEXUSEU': 'eur_usd',      # Euro (France, Germany, Poland, Netherlands, Belgium, Spain, Austria)
        'DEXSFUS': 'zar_usd',      # South Africa
        'DEXJPUS': 'jpy_usd',      # Japan
        'DEXSZUS': 'chf_usd',      # Switzerland (general indicator)
        'DEXKOUS': 'krw_usd',      # South Korea (general indicator)
        'DEXUSUK': 'gbp_usd',      # UK
        'DCOILWTICO': 'oil_wti',   # Oil
        'DTWEXBGS': 'usd_index',   # USD Index
        'DGS10': 'us_10yr_rate'    # 10Y Treasury
    }

    dfs = []

    # Fetch FRED series
    print("Fetching FRED data...")
    for code, name in fred_series.items():
        try:
            # Use the dynamic start_date for FRED calls
            data = fred.get_series(code, observation_start=start_date)
            df = pd.DataFrame({'date': data.index, name: data.values})
            dfs.append(df)
            print(f"  - {name}: {len(data):,} records")
            time.sleep(0.3)
        except Exception as e:
            print(f"  ! {name}: {str(e)[:50]}")

    # World Bank currencies
    worldbank_currencies = [
        # Coffee producers
        ('VNM', 'vnd'),      # Vietnam
        ('COL', 'cop'),      # Colombia
        ('IDN', 'idr'),      # Indonesia
        ('ETH', 'etb'),      # Ethiopia
        ('HND', 'hnl'),      # Honduras
        ('UGA', 'ugx'),      # Uganda
        ('PER', 'pen'),      # Peru
        ('CAF', 'xaf'),      # CAR
        ('GTM', 'gtq'),      # Guatemala
        ('GIN', 'gnf'),      # Guinea
        ('NIC', 'nio'),      # Nicaragua
        ('CRI', 'crc'),      # Costa Rica
        ('TZA', 'tzs'),      # Tanzania
        ('KEN', 'kes'),      # Kenya
        ('LAO', 'lak'),      # Laos

        # Sugar producers (not in FRED)
        ('PAK', 'pkr'),      # Pakistan
        ('PHL', 'php'),      # Philippines
        ('EGY', 'egp'),      # Egypt
        ('CUB', 'cup'),      # Cuba
        ('ARG', 'ars'),      # Argentina
        ('RUS', 'rub'),      # Russia
        ('TUR', 'try'),      # Turkey
        ('UKR', 'uah'),      # Ukraine
        ('IRN', 'irr'),      # Iran
        ('BLR', 'byn'),      # Belarus
    ]

    print("\nFetching World Bank FX (annual, forward-filled)...")
    for country_code, currency in worldbank_currencies:
        wb_df = get_worldbank_exchange_rate(country_code, currency)
        if not wb_df.empty:
            dfs.append(wb_df)

    # Notes on special cases
    print("\n  Note: XOF (Ivory Coast) pegged to EUR at 655.957:1 - using EUR")
    print("  Note: PLN (Poland) can use EUR proxy or World Bank data")

    # Merge all dataframes
    if dfs:
        result = dfs[0]
        for df in dfs[1:]:
            result = pd.merge(result, df, on='date', how='outer')
        print(f"\n  ✓ {len(result):,} daily records with {len(result.columns)-1} data series")
        return result

    return pd.DataFrame()


def write_dataframe_to_s3(df):
    """
    Converts a pandas DataFrame to CSV and uploads it to the configured S3 bucket.
    """
    if df.empty:
        print("DataFrame is empty. Skipping S3 upload.")
        return

    if not S3_BUCKET_NAME:
        print("S3_BUCKET_NAME environment variable is not set. Cannot upload.")
        return

    # Initialize S3 client
    s3 = boto3.client('s3')

    # Create the filename with timestamp for uniqueness
    timestamp = dt.datetime.now().strftime('%Y%m%d_%H%M%S')
    output_filename = f"daily_macro_data_{timestamp}.csv"

    # Write to an in-memory CSV buffer
    csv_buffer = io.StringIO()
    # Write DataFrame index (date) as the first column
    df.to_csv(csv_buffer, index=True)

    try:
        # Upload the in-memory content to the 'macro_data' prefix
        s3.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=f"landing/macro_data/{output_filename}",
            Body=csv_buffer.getvalue(),
            ContentType='text/csv'
        )
        print(f"Successfully uploaded {len(df)} records to s3://{S3_BUCKET_NAME}/macro_data/{output_filename}")

    except ClientError as e:
        print(f"Failed to upload to S3: {e}. Check IAM permissions and bucket name.")
    except Exception as e:
        print(f"An unexpected error occurred during S3 upload: {e}")


def lambda_handler(event, context):
    """
    Main entry point for the AWS Lambda function.
    Determines the fetch mode and start date based on the RUN_MODE environment variable.
    """
    # Essential check for required environment variable
    if not os.environ.get('FRED_API_KEY'):
        print("FATAL: FRED_API_KEY environment variable is missing.")
        return {'statusCode': 500, 'body': json.dumps({'message': 'Missing API Key'})}

    # 1. Determine the RUN_MODE and set the actual start date
    # Default to 'INCREMENTAL' if RUN_MODE is not set, as scheduled runs should be incremental
    run_mode = os.environ.get('RUN_MODE', 'INCREMENTAL').upper()

    if run_mode == 'HISTORICAL':
        # For one-time historical pull
        fetch_start_date = HISTORICAL_START_DATE
        print(f"Running in HISTORICAL mode. Fetching data from: {fetch_start_date}")

    elif run_mode == 'INCREMENTAL':
        # For daily scheduled pulls, fetch the last 7 days to cover data lags and weekends.
        n_days_ago = dt.date.today() - dt.timedelta(days=7)
        fetch_start_date = n_days_ago.strftime('%Y-%m-%d')
        print(f"Running in INCREMENTAL mode. Fetching data from the last 7 days, starting: {fetch_start_date}")
    else:
        # Fallback for unrecognized mode
        n_days_ago = dt.date.today() - dt.timedelta(days=7)
        fetch_start_date = n_days_ago.strftime('%Y-%m-%d')
        print(f"RUN_MODE '{run_mode}' unrecognized. Defaulting to incremental starting: {fetch_start_date}")

    try:
        # 2. Fetch and process the data using the calculated start date
        macro_df = get_daily_macro(fetch_start_date)

        # 3. Upload the processed data to S3
        write_dataframe_to_s3(macro_df)

        return {
            'statusCode': 200,
            'body': json.dumps({'message': f'{run_mode} data collection finished. Uploaded {len(macro_df)} records.'})
        }
    except Exception as e:
        print(f"Unhandled error in lambda_handler: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': f'Processing failed: {str(e)}'})
        }
