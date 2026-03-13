#!/bin/bash
# Deploy gdelt-bronze-transform Lambda function
# Converts JSONL files to Bronze Parquet format incrementally

set -e  # Exit on error

# Configuration
FUNCTION_NAME="gdelt-bronze-transform"
REGION="us-west-2"
ROLE_NAME="groundtruth-lambda-execution-role"
ROLE_ARN="arn:aws:iam::534150427458:role/${ROLE_NAME}"
LAYER_ARN="arn:aws:lambda:us-west-2:336392948345:layer:AWSSDKPandas-Python311:24"
FUNCTION_DIR="functions/gdelt-bronze-transform"

echo "========================================"
echo "Deploying: ${FUNCTION_NAME}"
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
        --memory-size 1024 \
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
        --memory-size 1024 \
        --timeout 900 \
        --layers "$LAYER_ARN" \
        --region "$REGION"

    echo "Waiting for function to be active..."
    aws lambda wait function-active --function-name "$FUNCTION_NAME" --region "$REGION"

    # Attach DynamoDB policy for tracking
    echo "Checking DynamoDB policy..."
    POLICY_NAME="groundtruth-dynamodb-access"

    if ! aws iam get-policy --policy-arn "arn:aws:iam::534150427458:policy/${POLICY_NAME}" 2>/dev/null; then
        echo "Creating DynamoDB policy..."
        cat > /tmp/dynamodb-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:Query",
        "dynamodb:Scan",
        "dynamodb:UpdateItem"
      ],
      "Resource": "arn:aws:dynamodb:us-west-2:534150427458:table/groundtruth-*"
    }
  ]
}
EOF

        aws iam create-policy \
            --policy-name "$POLICY_NAME" \
            --policy-document file:///tmp/dynamodb-policy.json \
            --region "$REGION"
    fi

    # Attach policy to role
    aws iam attach-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-arn "arn:aws:iam::534150427458:policy/${POLICY_NAME}" \
        --region "$REGION" 2>/dev/null || echo "Policy already attached"
fi

# Cleanup
rm lambda.zip
cd - > /dev/null

echo ""
echo "✓ ${FUNCTION_NAME} deployed successfully"
echo ""
echo "Test with:"
echo "aws lambda invoke --function-name ${FUNCTION_NAME} \\"
echo "  --cli-binary-format raw-in-base64-out \\"
echo "  --payload '{\"mode\":\"incremental\",\"limit\":10}' \\"
echo "  --region ${REGION} response.json && cat response.json | python3 -m json.tool"
