#!/bin/bash
# Deploy GDELT Bronze → Silver Step Functions State Machine

set -e

REGION="us-west-2"
ACCOUNT_ID="534150427458"
STATE_MACHINE_NAME="gdelt-bronze-silver-pipeline"
ROLE_NAME="gdelt-stepfunctions-role"

echo "========================================"
echo "Deploying GDELT Pipeline State Machine"
echo "========================================"
echo ""

# Create IAM role for Step Functions if it doesn't exist
echo "Checking Step Functions IAM role..."
if ! aws iam get-role --role-name "$ROLE_NAME" --region "$REGION" 2>/dev/null; then
    echo "Creating Step Functions IAM role..."

    # Trust policy
    cat > /tmp/stepfunctions-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "states.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    aws iam create-role \
        --role-name "$ROLE_NAME" \
        --assume-role-policy-document file:///tmp/stepfunctions-trust-policy.json \
        --region "$REGION"

    # Execution policy
    cat > /tmp/stepfunctions-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:InvokeFunction"
      ],
      "Resource": [
        "arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:gdelt-bronze-transform",
        "arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:gdelt-silver-transform"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:${REGION}:${ACCOUNT_ID}:*"
    }
  ]
}
EOF

    aws iam put-role-policy \
        --role-name "$ROLE_NAME" \
        --policy-name "StepFunctionsExecutionPolicy" \
        --policy-document file:///tmp/stepfunctions-policy.json \
        --region "$REGION"

    echo "Waiting 10 seconds for IAM role to propagate..."
    sleep 10
else
    echo "IAM role already exists"
fi

ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
echo "Using role: $ROLE_ARN"
echo ""

# Check if state machine exists
echo "Checking if state machine exists..."
if aws stepfunctions describe-state-machine \
    --state-machine-arn "arn:aws:states:${REGION}:${ACCOUNT_ID}:stateMachine:${STATE_MACHINE_NAME}" \
    --region "$REGION" 2>/dev/null; then

    echo "Updating existing state machine..."
    aws stepfunctions update-state-machine \
        --state-machine-arn "arn:aws:states:${REGION}:${ACCOUNT_ID}:stateMachine:${STATE_MACHINE_NAME}" \
        --definition file://gdelt_bronze_silver_pipeline.json \
        --region "$REGION"
else
    echo "Creating new state machine..."
    aws stepfunctions create-state-machine \
        --name "$STATE_MACHINE_NAME" \
        --definition file://gdelt_bronze_silver_pipeline.json \
        --role-arn "$ROLE_ARN" \
        --region "$REGION"
fi

echo ""
echo "✓ State machine deployed successfully"
echo ""
echo "State Machine ARN:"
echo "arn:aws:states:${REGION}:${ACCOUNT_ID}:stateMachine:${STATE_MACHINE_NAME}"
echo ""
echo "=========================================="
echo "Usage Examples"
echo "=========================================="
echo ""
echo "1. Process small batch (10 files, testing):"
echo "aws stepfunctions start-execution \\"
echo "  --state-machine-arn arn:aws:states:${REGION}:${ACCOUNT_ID}:stateMachine:${STATE_MACHINE_NAME} \\"
echo "  --input '{\"offset\":0,\"limit\":10,\"processed_so_far\":0,\"total_records\":0,\"silver_start_date\":\"2021-01-01\",\"silver_end_date\":\"2021-01-31\"}' \\"
echo "  --region ${REGION}"
echo ""
echo "2. Process all remaining files (21,267 files):"
echo "aws stepfunctions start-execution \\"
echo "  --state-machine-arn arn:aws:states:${REGION}:${ACCOUNT_ID}:stateMachine:${STATE_MACHINE_NAME} \\"
echo "  --name backfill-full-bronze-\$(date +%s) \\"
echo "  --input '{\"offset\":0,\"limit\":100,\"processed_so_far\":0,\"total_records\":0,\"silver_start_date\":\"2021-01-01\",\"silver_end_date\":\"2025-12-31\"}' \\"
echo "  --region ${REGION}"
echo ""
echo "3. Monitor execution:"
echo "aws stepfunctions list-executions \\"
echo "  --state-machine-arn arn:aws:states:${REGION}:${ACCOUNT_ID}:stateMachine:${STATE_MACHINE_NAME} \\"
echo "  --max-results 5 \\"
echo "  --region ${REGION}"
