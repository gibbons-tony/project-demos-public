#!/bin/bash
# Deploy gdelt-jsonl-bronze-transform Lambda function (BACKFILL MODE)
# Processes existing JSONL files → Bronze Parquet format
# This is the BACKFILL Lambda for processing 168,704 existing JSONL files

set -e  # Exit on error

# Configuration
FUNCTION_NAME="gdelt-jsonl-bronze-transform"
REGION="us-west-2"
ROLE_NAME="groundtruth-lambda-execution-role"
ROLE_ARN="arn:aws:iam::534150427458:role/${ROLE_NAME}"
LAYER_ARN="arn:aws:lambda:us-west-2:336392948345:layer:AWSSDKPandas-Python311:24"
FUNCTION_DIR="functions/gdelt-bronze-transform"

echo "========================================"
echo "Deploying BACKFILL Bronze Lambda: ${FUNCTION_NAME}"
echo "Purpose: Process existing JSONL → Bronze Parquet"
echo "========================================"

# Create deployment package
cd "$FUNCTION_DIR"
echo "Creating deployment package..."
zip -q lambda.zip lambda_function.py

# Check if function exists
if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" 2>/dev/null; then
    echo "Function exists, updating code..."

    aws lambda update-function-code \
        --function-name "$FUNCTION_NAME" \
        --zip-file fileb://lambda.zip \
        --region "$REGION"

    echo "Waiting for update to complete..."
    aws lambda wait function-updated --function-name "$FUNCTION_NAME" --region "$REGION"

    echo "Updating configuration..."
    aws lambda update-function-configuration \
        --function-name "$FUNCTION_NAME" \
        --runtime python3.11 \
        --handler lambda_function.lambda_handler \
        --memory-size 2048 \
        --timeout 900 \
        --layers "$LAYER_ARN" \
        --region "$REGION"

    echo "Waiting for configuration update..."
    aws lambda wait function-updated --function-name "$FUNCTION_NAME" --region "$REGION"

else
    echo "Creating new function..."

    aws lambda create-function \
        --function-name "$FUNCTION_NAME" \
        --runtime python3.11 \
        --handler lambda_function.lambda_handler \
        --role "$ROLE_ARN" \
        --zip-file fileb://lambda.zip \
        --memory-size 2048 \
        --timeout 900 \
        --layers "$LAYER_ARN" \
        --region "$REGION"

    echo "Waiting for function to be active..."
    aws lambda wait function-active --function-name "$FUNCTION_NAME" --region "$REGION"
fi

# Cleanup
rm lambda.zip
cd - > /dev/null

echo ""
echo "✓ ${FUNCTION_NAME} deployed successfully"
echo ""
echo "Next steps:"
echo "1. Update SQS trigger to point to this function:"
echo "   - Queue: groundtruth-gdelt-backfill-queue"
echo "   - Current trigger UUID: cce42542-5271-4e13-bcbe-42f515cbab3d"
echo ""
echo "Test with single file:"
echo "aws lambda invoke --function-name ${FUNCTION_NAME} \\"
echo "  --cli-binary-format raw-in-base64-out \\"
echo "  --payload '{\"Records\":[{\"body\":\"landing/gdelt/filtered/20210101000000.gkg.jsonl\"}]}' \\"
echo "  --region ${REGION} response.json && cat response.json | python3 -m json.tool"
