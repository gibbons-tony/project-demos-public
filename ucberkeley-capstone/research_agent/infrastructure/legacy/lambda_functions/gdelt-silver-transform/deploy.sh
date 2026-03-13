#!/bin/bash
#
# Deploy GDELT Silver Transform Lambda Function
#

set -e

FUNCTION_NAME="gdelt-silver-transform"
ROLE_ARN="arn:aws:iam::534150427458:role/groundtruth-lambda-execution-role"
REGION="us-west-2"

echo "========================================================================"
echo "Deploying Lambda: ${FUNCTION_NAME}"
echo "========================================================================"

# Create deployment package
echo ""
echo "Step 1: Creating deployment package..."

# Clean previous builds
rm -rf package
rm -f function.zip

# Create package directory
mkdir -p package

# Install dependencies (use Docker for Lambda-compatible builds)
echo "Installing dependencies..."
pip3 install -r requirements.txt -t package/ --platform manylinux2014_x86_64 --only-binary=:all:

# Copy Lambda function
cp lambda_function.py package/

# Create ZIP
cd package
zip -r ../function.zip . -q
cd ..

echo "✓ Package created: $(du -h function.zip | cut -f1)"

# Upload to S3 (Lambda deployment packages > 50MB must be uploaded to S3)
echo ""
echo "Step 2: Uploading to S3..."
S3_BUCKET="groundtruth-capstone"
S3_KEY="lambda-deployments/${FUNCTION_NAME}/function.zip"

aws s3 cp function.zip "s3://${S3_BUCKET}/${S3_KEY}"
echo "✓ Uploaded to s3://${S3_BUCKET}/${S3_KEY}"

# Create or update Lambda function
echo ""
echo "Step 3: Deploying Lambda function..."

if aws lambda get-function --function-name ${FUNCTION_NAME} --region ${REGION} 2>/dev/null; then
    echo "Updating existing function..."
    aws lambda update-function-code \
        --function-name ${FUNCTION_NAME} \
        --s3-bucket ${S3_BUCKET} \
        --s3-key ${S3_KEY} \
        --region ${REGION}

    # Wait for update to complete
    aws lambda wait function-updated \
        --function-name ${FUNCTION_NAME} \
        --region ${REGION}

    # Update configuration
    aws lambda update-function-configuration \
        --function-name ${FUNCTION_NAME} \
        --timeout 900 \
        --memory-size 3008 \
        --region ${REGION} \
        --ephemeral-storage '{"Size": 2048}'

    echo "✓ Function updated"
else
    echo "Creating new function..."
    aws lambda create-function \
        --function-name ${FUNCTION_NAME} \
        --runtime python3.11 \
        --role ${ROLE_ARN} \
        --handler lambda_function.lambda_handler \
        --code S3Bucket=${S3_BUCKET},S3Key=${S3_KEY} \
        --timeout 900 \
        --memory-size 3008 \
        --region ${REGION} \
        --ephemeral-storage '{"Size": 2048}' \
        --environment 'Variables={PYTHONPATH=/var/task/package}'

    echo "✓ Function created"
fi

# Cleanup
rm -rf package
rm -f function.zip

echo ""
echo "========================================================================"
echo "✅ DEPLOYMENT COMPLETE"
echo "========================================================================"
echo ""
echo "Function: ${FUNCTION_NAME}"
echo "Region: ${REGION}"
echo "Memory: 3008 MB"
echo "Timeout: 900 seconds (15 minutes)"
echo "Ephemeral Storage: 2048 MB"
echo ""
echo "To test:"
echo "  aws lambda invoke --function-name ${FUNCTION_NAME} \\"
echo "    --payload '{\"start_date\":\"2024-01-01\",\"end_date\":\"2024-01-07\"}' \\"
echo "    --region ${REGION} response.json"
echo ""
