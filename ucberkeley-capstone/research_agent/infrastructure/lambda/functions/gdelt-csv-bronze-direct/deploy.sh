#!/bin/bash

# Deploy CSV→Bronze Lambda to gdelt-bronze-transform function
# This replaces the old JSONL→Bronze code with new CSV→Bronze direct code

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
FUNCTION_NAME="gdelt-bronze-transform"
DEPLOYMENT_ZIP="$SCRIPT_DIR/deployment.zip"

echo "============================================================"
echo "Deploying CSV→Bronze Direct Lambda"
echo "============================================================"
echo ""
echo "Function: $FUNCTION_NAME"
echo "Package:  $DEPLOYMENT_ZIP"
echo ""

# Check if deployment.zip exists
if [ ! -f "$DEPLOYMENT_ZIP" ]; then
    echo "ERROR: deployment.zip not found!"
    echo "Please run: ./build.sh first"
    exit 1
fi

# Get file size
FILE_SIZE=$(du -h "$DEPLOYMENT_ZIP" | cut -f1)
echo "Package size: $FILE_SIZE"
echo ""

# Update Lambda function code
echo "Updating Lambda function code..."
aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file "fileb://$DEPLOYMENT_ZIP" \
    --region us-west-2 \
    --output json > /tmp/lambda_update_response.json

echo ""
echo "✓ Lambda function updated successfully!"
echo ""

# Show results
echo "Function details:"
cat /tmp/lambda_update_response.json | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f\"  Function ARN:  {data['FunctionArn']}\")
print(f\"  Last Modified: {data['LastModified']}\")
print(f\"  Code Size:     {data['CodeSize'] / (1024*1024):.1f} MB\")
print(f\"  Runtime:       {data['Runtime']}\")
print(f\"  Handler:       {data['Handler']}\")
"

echo ""
echo "============================================================"
echo "Deployment complete!"
echo "============================================================"
