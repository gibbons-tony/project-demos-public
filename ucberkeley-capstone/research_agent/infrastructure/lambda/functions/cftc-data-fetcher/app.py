import pandas as pd
import requests
import zipfile
import io
import time
from datetime import datetime, timezone
import boto3
import os
from botocore.exceptions import ClientError

# --- Configuration (Set these variables in your Lambda Environment Variables) ---
BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', 'groundtruth-capstone')
S3_KEY_PREFIX = os.environ.get('S3_KEY_PREFIX', 'landing/cftc_data/')
TARGET_FILE_NAME = 'cftc_coffee_sugar_positioning'
# The CFTC reports data up to the current year.
# This script iterates from this START_YEAR up to the current year.
START_YEAR = 2000

# Initialize S3 client outside the main handler for better performance
s3_client = boto3.client('s3')


# --- Helper Logic ---

def fetch_and_filter_cftc(year: int, last_date_in_db: str | None = None) -> pd.DataFrame:
    """
    Fetches, unzips, and filters CFTC data for a single specified year,
    and returns only records newer than the provided last_date_in_db.
    """
    print(f"  - Processing Year {year}...")

    try:
        url = f"https://www.cftc.gov/files/dea/history/deacot{year}.zip"
        response = requests.get(url, timeout=30)

        # 1. Download and Unzip the latest yearly file
        z = zipfile.ZipFile(io.BytesIO(response.content))
        txt_files = [f for f in z.namelist() if f.endswith('.txt')]

        if not txt_files:
            print(f"    ! No txt files found in {year} zip.")
            return pd.DataFrame()

        df = pd.read_csv(z.open(txt_files[0]), low_memory=False)

        market_col = 'Market and Exchange Names'
        date_col = 'As of Date in Form YYYY-MM-DD'

        if market_col not in df.columns:
            print(f"    ! Column '{market_col}' not found in {year}.")
            return pd.DataFrame()

        # Standard filtering for Coffee and Sugar
        relevant = df[df[market_col].str.contains('COFFEE|SUGAR', case=False, na=False)].copy()

        if len(relevant) > 0:
            # Prepare dates for filtering
            relevant[date_col] = pd.to_datetime(relevant[date_col], format='%Y-%m-%d')

            # --- CRITICAL INCREMENTAL FILTERING STEP ---
            if last_date_in_db:
                last_dt = pd.to_datetime(last_date_in_db, format='%Y-%m-%d')
                initial_count = len(relevant)

                # Keep only records that are strictly newer than the last date in the database
                relevant = relevant[relevant[date_col] > last_dt]

                if len(relevant) < initial_count:
                    print(
                        f"    * Filtered {initial_count - len(relevant)} old records. {len(relevant)} new records remain.")
                elif len(relevant) == initial_count:
                    print(f"    * No new records found after {last_date_in_db}.")
            # ------------------------------------------

            # Select final columns
            cols_to_keep = [
                market_col, date_col, 'Open Interest (All)',
                'Noncommercial Positions-Long (All)', 'Noncommercial Positions-Short (All)',
                'Commercial Positions-Long (All)', 'Commercial Positions-Short (All)',
                '% of OI-Noncommercial-Long (All)', '% of OI-Noncommercial-Short (All)'
            ]

            available = [col for col in cols_to_keep if col in relevant.columns]
            relevant = relevant[available]

            print(f"    ✓ Found {len(relevant)} new records for {year}")
            return relevant
        else:
            print(f"    ! No coffee/sugar data in {year} file")
            return pd.DataFrame()

    except Exception as e:
        print(f"    ! Error processing year {year}: {str(e)}")
        return pd.DataFrame()
    finally:
        # Pause briefly to be polite to the CFTC server
        time.sleep(0.5)


# --- Data Pull Functions ---

def get_historical_backfill():
    """Fetches all data from START_YEAR up to the PREVIOUS year."""
    print("Getting historical CFTC positioning (2020 - Last Year)...")
    current_year = datetime.now().year
    all_data = []

    # Iterate up to the year BEFORE the current year
    for year in range(START_YEAR, current_year):
        df = fetch_and_filter_cftc(year)
        if not df.empty:
            all_data.append(df)

    if all_data:
        result = pd.concat(all_data, ignore_index=True)
        print(f"  ✓ {len(result):,} historical records retrieved.")
        return result
    else:
        print("  ! No historical CFTC data retrieved.")
        return pd.DataFrame()


def get_last_processed_date_from_s3() -> str | None:
    """
    Attempts to find the latest 'As of Date' from the most recent CFTC file
    in the S3 Bronze storage location to enable incremental loading.

    Returns:
        str | None: The max date string (YYYY-MM-DD) found in S3, or None if no files exist.
    """
    if not BUCKET_NAME:
        print("  ! BUCKET_NAME missing. Cannot determine last processed date.")
        return None

    s3 = boto3.client('s3')

    try:
        # 1. List objects, ordered by last modified (latest file first)
        response = s3.list_objects_v2(
            Bucket=BUCKET_NAME,
            Prefix=S3_KEY_PREFIX,
            MaxKeys=1,  # Only need the most recently uploaded file
        )

        if 'Contents' not in response or not response['Contents']:
            print("  ! No files found in S3 CFTC prefix. Starting from clean slate.")
            return None

        latest_key = response['Contents'][0]['Key']
        print(f"  * Latest file in S3: {latest_key}")

        # 2. Download and read the latest file to find the max date
        obj = s3.get_object(Bucket=BUCKET_NAME, Key=latest_key)

        # Assuming the latest S3 file is a CSV and contains the 'As of Date' column
        df = pd.read_csv(io.BytesIO(obj['Body'].read()), low_memory=False)
        date_col = 'As of Date in Form YYYY-MM-DD'

        if date_col in df.columns:
            # Find the maximum date in that file
            df[date_col] = pd.to_datetime(df[date_col], format='%Y-%m-%d', errors='coerce')
            max_date = df[date_col].max()
            last_date_str = max_date.strftime('%Y-%m-%d')
            print(f"  * Determined last processed date: {last_date_str}")
            return last_date_str

    except ClientError as e:
        print(f"  ! S3 Client Error during date retrieval: {e}")
    except Exception as e:
        print(f"  ! Error finding last date in S3: {e}")

    return None  # Fallback


def get_current_year_update():
    """
    Fetches the current year's file, finds the last processed date from S3,
    and passes it to the fetcher for incremental loading.
    """
    current_year = datetime.now().year
    print(f"Getting current year CFTC positioning ({current_year})...")

    # STEP 1: Find the max date already in the bronze layer
    last_date = get_last_processed_date_from_s3()

    # STEP 2: Pass the found date to the fetch function
    df = fetch_and_filter_cftc(current_year, last_date)

    if not df.empty:
        print(f"  ✓ {len(df):,} new records retrieved.")
    else:
        print("  ! No new CFTC data retrieved.")

    return df


# --- S3 Upload Function ---

def upload_dataframe_to_s3(df, bucket, key):
    """Uploads a pandas DataFrame as a CSV file to S3."""
    print(f"\n-> Starting upload to s3://{bucket}/{key}")

    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)

    try:
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=csv_buffer.getvalue(),
            ContentType='text/csv'
        )
        print(f"✓ Upload successful.")
        return True
    except Exception as e:
        print(f"Error uploading to S3: {e}")
        return False


# --- AWS Lambda Handler ---

def lambda_handler(event, context):
    """Main handler function for AWS Lambda."""

    print(f"--- Lambda execution started at {datetime.now(timezone.utc)} ---")

    # 1. Fetch data from both historical and current year sources
    #historical_data = get_historical_backfill()
    current_data = get_current_year_update()

    # 2. Combine the data
    # all_data = pd.concat([historical_data, current_data], ignore_index=True)
    all_data = current_data
    if all_data.empty:
        return {
            'statusCode': 200,
            'body': 'CFTC data fetch completed, but no relevant data was found.'
        }

    # Drop duplicates that may occur due to file overlaps, keeping the latest one
    market_col = 'Market and Exchange Names'
    date_col = 'As of Date in Form YYYY-MM-DD'
    all_data = all_data.drop_duplicates(subset=[market_col, date_col], keep='last')

    print(f"\nTotal unique records ready for upload: {len(all_data):,}")

    # 3. Define S3 upload path
    current_date = datetime.now(timezone.utc).strftime("%Y%m%d")
    s3_key = f"{S3_KEY_PREFIX}{TARGET_FILE_NAME}_{current_date}.csv"

    # 4. Upload to S3
    success = upload_dataframe_to_s3(all_data, BUCKET_NAME, s3_key)

    if success:
        return {
            'statusCode': 200,
            'body': f'Successfully uploaded {len(all_data)} unique records to s3://{BUCKET_NAME}/{s3_key}'
        }
    else:
        return {
            'statusCode': 500,
            'body': 'Failed to upload data to S3.'
        }