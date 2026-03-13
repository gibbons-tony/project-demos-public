#!/bin/bash
# Complete EventBridge Schedule Setup for ALL Lambda Functions
# Creates daily schedules at 2 AM UTC for data pipeline

set -e

# Configuration
NEW_ACCOUNT_ID="534150427458"
NEW_REGION="us-west-2"
SCHEDULE_EXPRESSION="cron(0 2 * * ? *)"  # 2 AM UTC daily

echo "======================================"
echo "EventBridge Schedule Setup - ALL Functions"
echo "======================================"
echo ""
echo "Schedule: $SCHEDULE_EXPRESSION (2 AM UTC daily)"
echo "Region: $NEW_REGION"
echo ""

# Function configurations: name | rule-name | description
FUNCTIONS=(
    "market-data-fetcher|groundtruth-market-data-daily|Fetch Yahoo Finance commodity prices daily at 2 AM UTC"
    "weather-data-fetcher|groundtruth-weather-data-daily|Fetch OpenWeather data daily at 2 AM UTC"
    "vix-data-fetcher|groundtruth-vix-data-daily|Fetch VIX volatility data daily at 2 AM UTC"
    "fx-calculator-fetcher|groundtruth-fx-data-daily|Fetch FRED FX rates daily at 2 AM UTC"
    "cftc-data-fetcher|groundtruth-cftc-data-daily|Fetch CFTC positioning data daily at 2 AM UTC"
)

# Process each function
for func_config in "${FUNCTIONS[@]}"; do
    IFS='|' read -r FUNCTION_NAME RULE_NAME DESCRIPTION <<< "$func_config"

    echo "======================================"
    echo "Setting up: $FUNCTION_NAME"
    echo "======================================"
    echo ""

    # Get function ARN
    FUNCTION_ARN=$(aws lambda get-function \
        --function-name $FUNCTION_NAME \
        --region $NEW_REGION \
        --query 'Configuration.FunctionArn' \
        --output text)

    echo "Function ARN: $FUNCTION_ARN"

    # Create EventBridge rule
    echo "Creating EventBridge rule..."
    aws events put-rule \
        --name $RULE_NAME \
        --schedule-expression "$SCHEDULE_EXPRESSION" \
        --state ENABLED \
        --description "$DESCRIPTION" \
        --region $NEW_REGION

    echo "✓ Rule created: $RULE_NAME"

    # Add Lambda as target
    echo "Adding Lambda function as target..."
    aws events put-targets \
        --rule $RULE_NAME \
        --targets "Id=1,Arn=$FUNCTION_ARN" \
        --region $NEW_REGION

    echo "✓ Target added"

    # Grant EventBridge permission to invoke Lambda
    echo "Granting EventBridge permission..."
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
done

echo "======================================"
echo "All EventBridge Schedules Complete!"
echo "======================================"
echo ""
echo "✅ Scheduled Functions (6 total):"
echo "   1. market-data-fetcher    → 2 AM UTC daily"
echo "   2. weather-data-fetcher   → 2 AM UTC daily"
echo "   3. vix-data-fetcher       → 2 AM UTC daily"
echo "   4. fx-calculator-fetcher  → 2 AM UTC daily"
echo "   5. cftc-data-fetcher      → 2 AM UTC daily"
echo "   6. gdelt-processor        → 2 AM UTC daily (already configured)"
echo ""
echo "View schedules:"
echo "  https://console.aws.amazon.com/events/home?region=$NEW_REGION#/eventbus/default"
echo ""
echo "Test manually:"
echo "  aws lambda invoke --function-name market-data-fetcher --region $NEW_REGION response.json"
echo ""
