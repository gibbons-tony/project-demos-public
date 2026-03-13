from datetime import datetime, timezone, timedelta
import io
import json
import os
import requests
import boto3
import pandas as pd
import yfinance as yf

# Historical backfill start date
HISTORICAL_START_DATE = '2015-01-01'

def lambda_handler(event, context):
    """Sample pure Lambda function

    Parameters
    ----------
    event: dict, required
        API Gateway Lambda Proxy Input Format

        Event doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html#api-gateway-simple-proxy-for-lambda-input-format

    context: object, required
        Lambda Context runtime methods and attributes

        Context doc: https://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html

    Returns
    ------
    API Gateway Lambda Proxy Output Format: dict

        Return doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html
    """

    # --- 1. Determine RUN_MODE and set date range ---
    run_mode = os.environ.get('RUN_MODE', 'INCREMENTAL').upper()
    dt_now = datetime.now(timezone.utc)

    if run_mode == 'HISTORICAL':
        # One-time historical pull from 2015 to present
        START_DATE = HISTORICAL_START_DATE
        END_DATE = dt_now.strftime("%Y-%m-%d")
        print(f"Running in HISTORICAL mode. Fetching data from: {START_DATE} to {END_DATE}")
    else:
        # Incremental mode: fetch yesterday's data (weekdays only)
        if dt_now.weekday() in [1, 2, 3, 4, 5]:
            START_DATE = (dt_now - timedelta(days=1)).strftime('%Y-%m-%d')
            END_DATE = dt_now.strftime("%Y-%m-%d")
            print(f"Running in INCREMENTAL mode. Fetching data for: {START_DATE}")
        else:
            # Weekend - no data to fetch
            print("Weekend detected. No market data to fetch.")
            return {
                'statusCode': 200,
                'body': json.dumps('Weekend - no market data available')
            }

    s3_bucket_name = os.environ.get('S3_BUCKET_NAME', 'groundtruth-capstone')
    prices = None
    # --- 2. Retrieve data from the external API ---
    try:
        print("Getting daily futures prices...")

        coffee = yf.download("KC=F", start=START_DATE, end=END_DATE, progress=False, auto_adjust=True)
        coffee = coffee.reset_index()
        # Flatten MultiIndex columns if present
        if isinstance(coffee.columns, pd.MultiIndex):
            coffee.columns = ['_'.join(col).strip('_') if isinstance(col, tuple) else col for col in
                              coffee.columns.values]

        # Remove ticker suffix from column names (e.g., 'Close_KC=F' -> 'Close')
        coffee.columns = [col.split('_')[0] if '_' in str(col) and '=' in str(col) else col for col in coffee.columns]
        coffee['commodity'] = 'Coffee'

        sugar = yf.download("SB=F", start=START_DATE, end=END_DATE, progress=False, auto_adjust=True)
        sugar = sugar.reset_index()
        # Flatten MultiIndex columns if present
        if isinstance(sugar.columns, pd.MultiIndex):
            sugar.columns = ['_'.join(col).strip('_') if isinstance(col, tuple) else col for col in
                             sugar.columns.values]

        # Remove ticker suffix from column names (e.g., 'Close_SB=F' -> 'Close')
        sugar.columns = [col.split('_')[0] if '_' in str(col) and '=' in str(col) else col for col in sugar.columns]
        sugar['commodity'] = 'Sugar'

        # Combine properly in long format with commodity as a column
        prices = pd.concat([coffee, sugar], ignore_index=True)

        # Rename Date column if it exists
        if 'Date' in prices.columns:
            prices.rename(columns={'Date': 'date'}, inplace=True)

        # Ensure column names are lowercase for consistency
        prices.columns = [col.lower() if isinstance(col, str) else col for col in prices.columns]

        print(f"  ✓ {len(prices):,} daily price records")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from API: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps(f"Error fetching data: {e}")
        }

    # --- 3. Generate a unique S3 object key (filename) ---
    if run_mode == 'HISTORICAL':
        # For historical backfill, save to history subfolder
        s3_prefix = "landing/market_data/history"
        s3_object_key = f"{s3_prefix}/historical-{START_DATE}-to-{END_DATE}.csv"
    else:
        # For incremental, save to main folder with date
        s3_prefix = "landing/market_data"
        s3_object_key = f"{s3_prefix}/{START_DATE}-market-api-data.csv"

    # --- 5. Upload data to S3 ---
    s3 = boto3.client('s3')
    with io.StringIO() as csv_buffer:
        try:
            prices.to_csv(csv_buffer, index=False)
            s3.put_object(
                Bucket=s3_bucket_name,
                Key=s3_object_key,
                Body=csv_buffer.getvalue(),
                ContentType='application/csv'
            )

            print(f"Successfully uploaded data to s3://{s3_bucket_name}/{s3_object_key}")
            return {
                'statusCode': 200,
                'body': json.dumps('Data successfully retrieved and saved to S3!')
            }
        except Exception as e:
            print(f"Error uploading data to S3: {e}")
            return {
                'statusCode': 500,
                'body': json.dumps(f"Error uploading to S3: {e}")
            }
