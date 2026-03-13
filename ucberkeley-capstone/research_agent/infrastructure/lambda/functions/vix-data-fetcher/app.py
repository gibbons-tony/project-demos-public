import os
import io
import json
import pandas as pd
import boto3
import datetime as dt
from botocore.exceptions import ClientError
from fredapi import Fred

# --- Configuration ---
# Set the absolute start date for the one-time historical pull
HISTORICAL_START_DATE = '1990-01-01'  # Using a common VIX start date for full history
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')


def get_daily_volatility(start_date):
    """
    Fetches the daily VIX (VIXCLS) from the FRED API starting from the
    specified start_date.

    Parameters:
        start_date (str): The earliest date for which to fetch data (YYYY-MM-DD).

    Returns:
        pd.DataFrame: A DataFrame with columns ['date', 'vix'].
    """

    print(f"Getting daily volatility (VIX) starting from {start_date}...")

    key = os.getenv('FRED_API_KEY')
    if not key:
        print("  ! FRED_API_KEY environment variable is not set. Cannot fetch FRED data.")
        return pd.DataFrame()

    fred = Fred(api_key=key)

    try:
        # VIXCLS is the CBOE VIX Index (Daily, Close)
        vix = fred.get_series('VIXCLS', observation_start=start_date)

        # Convert the Series to a DataFrame, naming the index 'date'
        df = pd.DataFrame({'date': vix.index, 'vix': vix.values}).dropna()

        print(f"  ✓ {len(df):,} daily VIX records fetched.")
        return df

    except Exception as e:
        print(f"  ! VIX FRED API Error: {str(e)}")
        return pd.DataFrame()


def write_dataframe_to_s3(df, run_mode):
    """
    Converts a pandas DataFrame to CSV and uploads it to the configured S3 bucket.

    Parameters:
        df (pd.DataFrame): The DataFrame to upload.
        run_mode (str): The mode ('HISTORICAL' or 'INCREMENTAL') used for logging and naming.
    """
    if df.empty:
        print("DataFrame is empty. Skipping S3 upload.")
        return

    if not S3_BUCKET_NAME:
        print("S3_BUCKET_NAME environment variable is not set. Cannot upload.")
        return

    # Initialize S3 client
    s3 = boto3.client('s3')

    # Create the filename with timestamp for uniqueness and file type
    timestamp = dt.datetime.now().strftime('%Y%m%d_%H%M%S')

    # Use a descriptive file name prefix
    if run_mode == 'HISTORICAL':
        s3_key = f"landing/vix_data/history/vix_data_{timestamp}.csv"
    else:
        s3_key = f"landing/vix_data/vix_data_{timestamp}.csv"
    output_filename = f"vix_data_{timestamp}.csv"
    # Write to an in-memory CSV buffer
    csv_buffer = io.StringIO()
    # Write DataFrame index (date) as the first column
    df.to_csv(csv_buffer, index=True)

    try:
        # Upload the in-memory content to the 'vix_data' prefix
        s3.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=csv_buffer.getvalue(),
            ContentType='text/csv'
        )
        print(f"Successfully uploaded {len(df)} VIX records to s3://{S3_BUCKET_NAME}/vix_data/{output_filename}")

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
    if not os.getenv('FRED_API_KEY'):
        print("FATAL: FRED_API_KEY environment variable is missing.")
        return {'statusCode': 500, 'body': json.dumps({'message': 'Missing API Key'})}

    # 1. Determine the RUN_MODE and set the actual start date
    # Default to 'INCREMENTAL' if RUN_MODE is not set
    run_mode = os.environ.get('RUN_MODE', 'INCREMENTAL').upper()

    if run_mode == 'HISTORICAL':
        # One-time historical pull
        fetch_start_date = HISTORICAL_START_DATE
        print(f"Running in HISTORICAL mode. Fetching data from: {fetch_start_date}")

    else:  # Defaulting to 'INCREMENTAL'
        # Daily scheduled pulls: fetch the last 7 days for a reliable buffer
        n_days_ago = dt.date.today() - dt.timedelta(days=7)
        fetch_start_date = n_days_ago.strftime('%Y-%m-%d')
        run_mode = 'INCREMENTAL'
        print(f"Running in INCREMENTAL mode. Fetching data from the last 7 days, starting: {fetch_start_date}")

    try:
        # 2. Fetch and process the data
        vix_df = get_daily_volatility(fetch_start_date)

        # 3. Upload the processed data to S3
        write_dataframe_to_s3(vix_df, run_mode)

        return {
            'statusCode': 200,
            'body': json.dumps({'message': f'{run_mode} VIX data collection finished. Uploaded {len(vix_df)} records.'})
        }
    except Exception as e:
        print(f"Unhandled error in lambda_handler: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': f'VIX Processing failed: {str(e)}'})
        }
