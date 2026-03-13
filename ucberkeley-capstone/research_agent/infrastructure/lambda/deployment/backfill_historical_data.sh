#!/bin/bash
set -e

REGION="us-west-2"

echo "========================================="
echo "HISTORICAL DATA BACKFILL SCRIPT"
echo "========================================="
echo ""

# Step 1: Backfill Market, FX, and VIX data (these all support HISTORICAL mode)
echo "Step 1: Temporarily setting RUN_MODE=HISTORICAL for Market, FX, and VIX functions..."

# Update Market function to HISTORICAL mode
aws lambda update-function-configuration \
  --function-name market-data-fetcher \
  --region $REGION \
  --environment "Variables={RUN_MODE=HISTORICAL,S3_BUCKET_NAME=groundtruth-capstone}" \
  --query '[FunctionName, Environment.Variables.RUN_MODE]' \
  --output text

# Update FX function to HISTORICAL mode
aws lambda update-function-configuration \
  --function-name fx-calculator-fetcher \
  --region $REGION \
  --environment "Variables={RUN_MODE=HISTORICAL,S3_BUCKET_NAME=groundtruth-capstone,FRED_API_KEY=$(aws lambda get-function-configuration --function-name fx-calculator-fetcher --region $REGION --query 'Environment.Variables.FRED_API_KEY' --output text)}" \
  --query '[FunctionName, Environment.Variables.RUN_MODE]' \
  --output text

# Update VIX function to HISTORICAL mode
aws lambda update-function-configuration \
  --function-name vix-data-fetcher \
  --region $REGION \
  --environment "Variables={RUN_MODE=HISTORICAL,S3_BUCKET_NAME=groundtruth-capstone,FRED_API_KEY=$(aws lambda get-function-configuration --function-name vix-data-fetcher --region $REGION --query 'Environment.Variables.FRED_API_KEY' --output text)}" \
  --query '[FunctionName, Environment.Variables.RUN_MODE]' \
  --output text

echo ""
echo "Step 2: Invoking Market, FX, and VIX functions to backfill historical data..."
echo "WARNING: These will take several minutes due to large date ranges!"
echo ""

# Invoke Market function (2015-2025 = 10 years of Coffee/Sugar prices)
echo "Invoking Market function (2015-01-01 to present)..."
aws lambda invoke \
  --function-name market-data-fetcher \
  --region $REGION \
  --cli-read-timeout 600 \
  /tmp/market-historical-response.json

echo "Market Response:"
cat /tmp/market-historical-response.json
echo ""
echo ""

# Invoke FX function (2015-2025 = 10 years of daily FX rates)
echo "Invoking FX function (2015-01-01 to present)..."
aws lambda invoke \
  --function-name fx-calculator-fetcher \
  --region $REGION \
  --cli-read-timeout 600 \
  /tmp/fx-historical-response.json

echo "FX Response:"
cat /tmp/fx-historical-response.json
echo ""
echo ""

# Invoke VIX function (1990-2025 = 35 years of daily VIX data)
echo "Invoking VIX function (1990-01-01 to present)..."
aws lambda invoke \
  --function-name vix-data-fetcher \
  --region $REGION \
  --cli-read-timeout 600 \
  /tmp/vix-historical-response.json

echo "VIX Response:"
cat /tmp/vix-historical-response.json
echo ""
echo ""

# Invoke Weather function (2015-01-01 to present)
# Weather function accepts days_to_fetch parameter, not RUN_MODE
# Calculate days from 2015-01-01 to today (approximately 3,957 days as of 2025-10-31)
echo "Invoking Weather function (2015-01-01 to present)..."
echo "NOTE: This may take 10+ minutes due to API rate limits..."
aws lambda invoke \
  --function-name weather-data-fetcher \
  --region $REGION \
  --payload '{"days_to_fetch": [3957, 0]}' \
  --cli-read-timeout 900 \
  /tmp/weather-historical-response.json

echo "Weather Response:"
cat /tmp/weather-historical-response.json
echo ""
echo ""

# Step 3: Restore INCREMENTAL mode
echo "Step 3: Restoring RUN_MODE=INCREMENTAL for future daily updates..."

aws lambda update-function-configuration \
  --function-name market-data-fetcher \
  --region $REGION \
  --environment "Variables={RUN_MODE=INCREMENTAL,S3_BUCKET_NAME=groundtruth-capstone}" \
  --query '[FunctionName, Environment.Variables.RUN_MODE]' \
  --output text

aws lambda update-function-configuration \
  --function-name fx-calculator-fetcher \
  --region $REGION \
  --environment "Variables={RUN_MODE=INCREMENTAL,S3_BUCKET_NAME=groundtruth-capstone,FRED_API_KEY=$(aws lambda get-function-configuration --function-name fx-calculator-fetcher --region $REGION --query 'Environment.Variables.FRED_API_KEY' --output text)}" \
  --query '[FunctionName, Environment.Variables.RUN_MODE]' \
  --output text

aws lambda update-function-configuration \
  --function-name vix-data-fetcher \
  --region $REGION \
  --environment "Variables={RUN_MODE=INCREMENTAL,S3_BUCKET_NAME=groundtruth-capstone,FRED_API_KEY=$(aws lambda get-function-configuration --function-name vix-data-fetcher --region $REGION --query 'Environment.Variables.FRED_API_KEY' --output text)}" \
  --query '[FunctionName, Environment.Variables.RUN_MODE]' \
  --output text

echo ""
echo "========================================="
echo "Historical backfill complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Check S3 for historical market data: aws s3 ls s3://groundtruth-capstone/landing/market_data/history/ --region us-west-2"
echo "2. Check S3 for historical macro data: aws s3 ls s3://groundtruth-capstone/landing/macro_data/ --region us-west-2"
echo "3. Check S3 for VIX data: aws s3 ls s3://groundtruth-capstone/landing/vix_data/ --region us-west-2"
echo "4. Re-run Databricks table creation SQL to load new historical data"
echo "5. You should now have 2015-2025 data for Coffee, Sugar, FX rates, and VIX!"
