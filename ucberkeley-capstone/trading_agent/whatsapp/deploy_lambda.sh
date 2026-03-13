#!/bin/bash
# Deploy WhatsApp Lambda Function to AWS (with real Databricks data)
#
# This script packages and deploys the Lambda function for Twilio WhatsApp webhook

set -e

echo "=========================================="
echo "WhatsApp Lambda Deployment"
echo "=========================================="
echo ""

# Configuration
FUNCTION_NAME="trading-recommendations-whatsapp"
REGION="us-west-2"
RUNTIME="python3.11"
HANDLER="lambda_handler_real.lambda_handler"
TIMEOUT=30
MEMORY=512

# Check AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "Error: AWS CLI not found. Please install: https://aws.amazon.com/cli/"
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo "Error: AWS credentials not configured. Run 'aws configure'"
    exit 1
fi

# Get Databricks credentials (if available)
if [ -f ~/.databrickscfg ]; then
    echo "Reading Databricks credentials from ~/.databrickscfg..."
    DATABRICKS_HOST=$(grep -A 2 "\[DEFAULT\]" ~/.databrickscfg | grep "^host" | cut -d'=' -f2 | tr -d ' ')
    DATABRICKS_TOKEN=$(grep -A 2 "\[DEFAULT\]" ~/.databrickscfg | grep "^token" | cut -d'=' -f2 | tr -d ' ')

    # Try to get warehouse path from databrickscfg
    DATABRICKS_HTTP_PATH=$(grep -A 2 "\[DEFAULT\]" ~/.databrickscfg | grep "^http_path" | cut -d'=' -f2 | tr -d ' ')

    if [ -z "$DATABRICKS_HTTP_PATH" ]; then
        echo "  Warning: http_path not found in ~/.databrickscfg"
        echo "  Will need to set DATABRICKS_HTTP_PATH manually"
    fi
else
    echo "Warning: ~/.databrickscfg not found"
    echo "Lambda will use mock data unless you manually set environment variables"
fi

echo "1. Creating deployment package with dependencies..."
echo ""

# Create temporary build directory
BUILD_DIR="/tmp/lambda-whatsapp-build"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Copy Lambda function and dependencies
cp lambda_handler_real.py "$BUILD_DIR/"
cp trading_strategies.py "$BUILD_DIR/"

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install -q -r requirements_lambda.txt -t "$BUILD_DIR/" --platform manylinux2014_x86_64 --only-binary=:all: 2>&1 | grep -v "Requirement already satisfied" || true

# Create ZIP package
cd "$BUILD_DIR"
zip -q -r lambda_function.zip .

PACKAGE_SIZE=$(du -h lambda_function.zip | cut -f1)
echo "✓ Package created: $BUILD_DIR/lambda_function.zip ($PACKAGE_SIZE)"
echo ""

echo "2. Creating IAM execution role (if needed)..."
echo ""

ROLE_NAME="trading-whatsapp-lambda-role"
ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text 2>/dev/null || echo "")

if [ -z "$ROLE_ARN" ]; then
    echo "Creating new IAM role..."

    # Create trust policy
    TRUST_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
)

    # Create role
    ROLE_ARN=$(aws iam create-role \
        --role-name "$ROLE_NAME" \
        --assume-role-policy-document "$TRUST_POLICY" \
        --query 'Role.Arn' \
        --output text)

    # Attach basic execution policy
    aws iam attach-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"

    echo "✓ Created IAM role: $ROLE_ARN"
    echo "  Waiting 10 seconds for role to propagate..."
    sleep 10
else
    echo "✓ Using existing IAM role: $ROLE_ARN"
fi

echo ""

echo "3. Creating/updating Lambda function..."
echo ""

# Check if function exists
if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" &> /dev/null; then
    echo "Function exists, updating code..."

    aws lambda update-function-code \
        --function-name "$FUNCTION_NAME" \
        --zip-file "fileb://$BUILD_DIR/lambda_function.zip" \
        --region "$REGION" \
        --output text > /dev/null

    echo "✓ Lambda function code updated"

    # Update configuration if needed
    if [ -n "$DATABRICKS_HOST" ]; then
        echo "Updating environment variables..."
        aws lambda update-function-configuration \
            --function-name "$FUNCTION_NAME" \
            --region "$REGION" \
            --timeout "$TIMEOUT" \
            --memory-size "$MEMORY" \
            --environment "Variables={DATABRICKS_HOST=$DATABRICKS_HOST,DATABRICKS_TOKEN=$DATABRICKS_TOKEN,DATABRICKS_HTTP_PATH=$DATABRICKS_HTTP_PATH}" \
            --output text > /dev/null
        echo "✓ Environment variables updated"
    fi
else
    echo "Creating new Lambda function..."

    # Build environment variables
    if [ -n "$DATABRICKS_HOST" ]; then
        if [ -n "$DATABRICKS_HTTP_PATH" ]; then
            ENV_VARS="Variables={DATABRICKS_HOST=$DATABRICKS_HOST,DATABRICKS_TOKEN=$DATABRICKS_TOKEN,DATABRICKS_HTTP_PATH=$DATABRICKS_HTTP_PATH}"
        else
            # http_path missing - set placeholder, user must update manually
            ENV_VARS="Variables={DATABRICKS_HOST=$DATABRICKS_HOST,DATABRICKS_TOKEN=$DATABRICKS_TOKEN,DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/REPLACE_ME}"
        fi
    else
        ENV_VARS="Variables={}"
    fi

    aws lambda create-function \
        --function-name "$FUNCTION_NAME" \
        --runtime "$RUNTIME" \
        --role "$ROLE_ARN" \
        --handler "$HANDLER" \
        --timeout "$TIMEOUT" \
        --memory-size "$MEMORY" \
        --zip-file "fileb://$BUILD_DIR/lambda_function.zip" \
        --environment "$ENV_VARS" \
        --region "$REGION" \
        --output text > /dev/null

    echo "✓ Lambda function created"
fi

echo ""

echo "4. Creating API Gateway (if needed)..."
echo ""

# Get or create REST API
API_ID=$(aws apigateway get-rest-apis --region "$REGION" --query "items[?name=='trading-whatsapp-api'].id" --output text)

if [ -z "$API_ID" ]; then
    echo "Creating new REST API..."

    API_ID=$(aws apigateway create-rest-api \
        --name "trading-whatsapp-api" \
        --description "API for Twilio WhatsApp webhook" \
        --region "$REGION" \
        --query 'id' \
        --output text)

    echo "✓ Created API: $API_ID"

    # Get root resource
    ROOT_RESOURCE_ID=$(aws apigateway get-resources \
        --rest-api-id "$API_ID" \
        --region "$REGION" \
        --query 'items[0].id' \
        --output text)

    # Create /webhook resource
    RESOURCE_ID=$(aws apigateway create-resource \
        --rest-api-id "$API_ID" \
        --parent-id "$ROOT_RESOURCE_ID" \
        --path-part "webhook" \
        --region "$REGION" \
        --query 'id' \
        --output text)

    # Create POST method
    aws apigateway put-method \
        --rest-api-id "$API_ID" \
        --resource-id "$RESOURCE_ID" \
        --http-method POST \
        --authorization-type NONE \
        --region "$REGION" \
        --output text > /dev/null

    # Get Lambda ARN
    LAMBDA_ARN=$(aws lambda get-function \
        --function-name "$FUNCTION_NAME" \
        --region "$REGION" \
        --query 'Configuration.FunctionArn' \
        --output text)

    # Create Lambda integration
    aws apigateway put-integration \
        --rest-api-id "$API_ID" \
        --resource-id "$RESOURCE_ID" \
        --http-method POST \
        --type AWS_PROXY \
        --integration-http-method POST \
        --uri "arn:aws:apigateway:$REGION:lambda:path/2015-03-31/functions/$LAMBDA_ARN/invocations" \
        --region "$REGION" \
        --output text > /dev/null

    # Add Lambda permission for API Gateway
    ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text)
    aws lambda add-permission \
        --function-name "$FUNCTION_NAME" \
        --statement-id "apigateway-invoke-$(date +%s)" \
        --action lambda:InvokeFunction \
        --principal apigateway.amazonaws.com \
        --source-arn "arn:aws:execute-api:$REGION:$ACCOUNT_ID:$API_ID/*/*/webhook" \
        --region "$REGION" \
        --output text > /dev/null

    # Deploy API
    aws apigateway create-deployment \
        --rest-api-id "$API_ID" \
        --stage-name "prod" \
        --region "$REGION" \
        --output text > /dev/null

    echo "✓ API Gateway configured and deployed"
else
    echo "✓ Using existing API: $API_ID"
fi

echo ""

# Get webhook URL
WEBHOOK_URL="https://$API_ID.execute-api.$REGION.amazonaws.com/prod/webhook"

echo "=========================================="
echo "✓ Deployment Complete"
echo "=========================================="
echo ""
echo "Webhook URL:"
echo "  $WEBHOOK_URL"
echo ""

if [ -n "$DATABRICKS_HOST" ]; then
    echo "Databricks connection:"
    echo "  ✓ Host: $DATABRICKS_HOST"
    echo "  ✓ Token: ${DATABRICKS_TOKEN:0:10}..."
    if [ -n "$DATABRICKS_HTTP_PATH" ]; then
        echo "  ✓ Warehouse: $DATABRICKS_HTTP_PATH"
    else
        echo "  ⚠ Warehouse path not set - you'll need to add DATABRICKS_HTTP_PATH manually"
    fi
    echo ""
    echo "Lambda will query real data from Databricks"
else
    echo "⚠ Databricks not configured - Lambda will use mock data"
    echo ""
    echo "To enable real data, set environment variables:"
    echo "  aws lambda update-function-configuration \\"
    echo "    --function-name $FUNCTION_NAME \\"
    echo "    --environment 'Variables={DATABRICKS_HOST=...,DATABRICKS_TOKEN=...,DATABRICKS_HTTP_PATH=...}'"
fi

echo ""
echo "Next steps:"
echo "  1. Copy the webhook URL above"
echo "  2. Follow WHATSAPP_SETUP.md to configure Twilio"
echo "  3. Test by scanning QR code and sending 'coffee' or 'sugar'"
echo ""

# Test the Lambda function
echo "Testing Lambda function..."
echo ""

TEST_EVENT=$(cat <<EOF
{
  "body": "From=whatsapp%3A%2B15555551234&Body=coffee&MessageSid=SM123",
  "httpMethod": "POST",
  "headers": {
    "Content-Type": "application/x-www-form-urlencoded"
  }
}
EOF
)

RESPONSE=$(aws lambda invoke \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --payload "$TEST_EVENT" \
    --cli-binary-format raw-in-base64-out \
    /tmp/lambda-test-output.json 2>&1)

if [ $? -eq 0 ]; then
    echo "✓ Lambda test successful"
    echo ""
    echo "Sample response:"
    cat /tmp/lambda-test-output.json | python3 -c "import sys, json; data = json.load(sys.stdin); print(data['body'][:400] + '...' if len(data.get('body', '')) > 400 else data.get('body', ''))"
else
    echo "⚠ Lambda test failed:"
    echo "$RESPONSE"
fi

echo ""
