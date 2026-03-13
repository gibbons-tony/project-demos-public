#!/bin/bash
# EventBridge Schedule Setup for GDELT Processor
# Creates daily schedule at 2 AM UTC to trigger GDELT data ingestion

set -e

# Configuration
NEW_ACCOUNT_ID="534150427458"
NEW_REGION="us-west-2"
FUNCTION_NAME="gdelt-processor"
RULE_NAME="groundtruth-gdelt-daily-update"
SCHEDULE_EXPRESSION="cron(0 2 * * ? *)"  # 2 AM UTC daily

echo "======================================"
echo "EventBridge Schedule Setup"
echo "======================================"
echo ""
echo "Function: $FUNCTION_NAME"
echo "Schedule: $SCHEDULE_EXPRESSION (2 AM UTC daily)"
echo "Region: $NEW_REGION"
echo ""

# Get function ARN
FUNCTION_ARN=$(aws lambda get-function \
    --function-name $FUNCTION_NAME \
    --region $NEW_REGION \
    --query 'Configuration.FunctionArn' \
    --output text)

echo "Function ARN: $FUNCTION_ARN"
echo ""

# Create EventBridge rule
echo "Creating EventBridge rule..."
aws events put-rule \
    --name $RULE_NAME \
    --schedule-expression "$SCHEDULE_EXPRESSION" \
    --state ENABLED \
    --description "Trigger GDELT incremental update daily at 2 AM UTC" \
    --region $NEW_REGION

echo "✓ Rule created"
echo ""

# Add Lambda as target
echo "Adding Lambda function as target..."
aws events put-targets \
    --rule $RULE_NAME \
    --targets "Id=1,Arn=$FUNCTION_ARN,Input={\"mode\":\"incremental\"}" \
    --region $NEW_REGION

echo "✓ Target added"
echo ""

# Grant EventBridge permission to invoke Lambda
echo "Granting EventBridge permission to invoke Lambda..."
STATEMENT_ID="AllowEventBridgeInvoke-$RULE_NAME"

# Remove existing permission if it exists
aws lambda remove-permission \
    --function-name $FUNCTION_NAME \
    --statement-id $STATEMENT_ID \
    --region $NEW_REGION 2>/dev/null || true

# Add permission
aws lambda add-permission \
    --function-name $FUNCTION_NAME \
    --statement-id $STATEMENT_ID \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --source-arn "arn:aws:events:$NEW_REGION:$NEW_ACCOUNT_ID:rule/$RULE_NAME" \
    --region $NEW_REGION

echo "✓ Permission granted"
echo ""

echo "======================================"
echo "EventBridge Schedule Setup Complete!"
echo "======================================"
echo ""
echo "The GDELT processor will now run daily at 2 AM UTC"
echo "View schedule: https://console.aws.amazon.com/events/home?region=$NEW_REGION#/eventbus/default/rules/$RULE_NAME"
echo ""
echo "To test manually:"
echo "  aws lambda invoke --function-name $FUNCTION_NAME --payload '{\"mode\":\"incremental\"}' --region $NEW_REGION response.json"
echo ""
