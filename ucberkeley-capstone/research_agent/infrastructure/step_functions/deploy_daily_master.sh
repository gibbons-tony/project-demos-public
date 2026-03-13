#!/bin/bash
# Deploy Daily Master Pipeline State Machine

set -e

REGION="us-west-2"
ACCOUNT_ID="534150427458"
STATE_MACHINE_NAME="gdelt-daily-master-pipeline"
ROLE_NAME="gdelt-stepfunctions-role"
SCHEDULE_NAME="gdelt-daily-pipeline-schedule"

echo "========================================"
echo "Deploying Daily Master Pipeline"
echo "========================================"
echo ""

# Get IAM role ARN (should already exist from previous deployment)
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
echo "Using IAM role: $ROLE_ARN"
echo ""

# Update the role to include permissions for nested state machine execution
echo "Updating IAM policy for nested state machine execution..."
cat > /tmp/stepfunctions-policy-daily.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:InvokeFunction"
      ],
      "Resource": [
        "arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:gdelt-processor",
        "arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:gdelt-bronze-transform",
        "arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:gdelt-silver-transform"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "states:StartExecution",
        "states:DescribeExecution",
        "states:StopExecution"
      ],
      "Resource": [
        "arn:aws:states:${REGION}:${ACCOUNT_ID}:stateMachine:gdelt-bronze-silver-pipeline",
        "arn:aws:states:${REGION}:${ACCOUNT_ID}:execution:gdelt-bronze-silver-pipeline:*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "events:PutTargets",
        "events:PutRule",
        "events:DescribeRule"
      ],
      "Resource": [
        "arn:aws:events:${REGION}:${ACCOUNT_ID}:rule/StepFunctionsGetEventsForStepFunctionsExecutionRule"
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
    --policy-document file:///tmp/stepfunctions-policy-daily.json \
    --region "$REGION"

echo "IAM policy updated"
echo ""

# Check if state machine exists
echo "Checking if state machine exists..."
if aws stepfunctions describe-state-machine \
    --state-machine-arn "arn:aws:states:${REGION}:${ACCOUNT_ID}:stateMachine:${STATE_MACHINE_NAME}" \
    --region "$REGION" 2>/dev/null; then

    echo "Updating existing state machine..."
    aws stepfunctions update-state-machine \
        --state-machine-arn "arn:aws:states:${REGION}:${ACCOUNT_ID}:stateMachine:${STATE_MACHINE_NAME}" \
        --definition file://gdelt_daily_master_pipeline.json \
        --region "$REGION"
else
    echo "Creating new state machine..."
    aws stepfunctions create-state-machine \
        --name "$STATE_MACHINE_NAME" \
        --definition file://gdelt_daily_master_pipeline.json \
        --role-arn "$ROLE_ARN" \
        --region "$REGION"
fi

echo ""
echo "✓ State machine deployed successfully"
echo ""

# Create EventBridge schedule (daily at 2am UTC)
echo "Setting up EventBridge daily schedule..."

# Create IAM role for EventBridge to invoke Step Functions if it doesn't exist
EVENTBRIDGE_ROLE_NAME="eventbridge-stepfunctions-role"
EVENTBRIDGE_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${EVENTBRIDGE_ROLE_NAME}"

if ! aws iam get-role --role-name "$EVENTBRIDGE_ROLE_NAME" --region "$REGION" 2>/dev/null; then
    echo "Creating EventBridge IAM role..."

    cat > /tmp/eventbridge-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "events.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    aws iam create-role \
        --role-name "$EVENTBRIDGE_ROLE_NAME" \
        --assume-role-policy-document file:///tmp/eventbridge-trust-policy.json \
        --region "$REGION"

    cat > /tmp/eventbridge-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "states:StartExecution"
      ],
      "Resource": [
        "arn:aws:states:${REGION}:${ACCOUNT_ID}:stateMachine:${STATE_MACHINE_NAME}"
      ]
    }
  ]
}
EOF

    aws iam put-role-policy \
        --role-name "$EVENTBRIDGE_ROLE_NAME" \
        --policy-name "InvokeStepFunctions" \
        --policy-document file:///tmp/eventbridge-policy.json \
        --region "$REGION"

    echo "Waiting 10 seconds for IAM role to propagate..."
    sleep 10
fi

# Create or update EventBridge rule
echo "Creating/updating EventBridge schedule rule..."
aws events put-rule \
    --name "$SCHEDULE_NAME" \
    --schedule-expression "cron(0 2 * * ? *)" \
    --state ENABLED \
    --description "Trigger GDELT daily pipeline at 2am UTC" \
    --region "$REGION"

# Add Step Functions as target
echo "Adding Step Functions target to schedule..."
aws events put-targets \
    --rule "$SCHEDULE_NAME" \
    --targets "Id"="1","Arn"="arn:aws:states:${REGION}:${ACCOUNT_ID}:stateMachine:${STATE_MACHINE_NAME}","RoleArn"="${EVENTBRIDGE_ROLE_ARN}" \
    --region "$REGION"

echo ""
echo "✓ EventBridge schedule configured"
echo ""
echo "=========================================="
echo "Deployment Complete"
echo "=========================================="
echo ""
echo "State Machine ARN:"
echo "arn:aws:states:${REGION}:${ACCOUNT_ID}:stateMachine:${STATE_MACHINE_NAME}"
echo ""
echo "Schedule: Daily at 2:00 AM UTC (cron: 0 2 * * ? *)"
echo ""
echo "==========================================="
echo "Manual Test Execution"
echo "==========================================="
echo ""
echo "Test the pipeline manually:"
echo "aws stepfunctions start-execution \\"
echo "  --state-machine-arn arn:aws:states:${REGION}:${ACCOUNT_ID}:stateMachine:${STATE_MACHINE_NAME} \\"
echo "  --name manual-test-\$(date +%s) \\"
echo "  --region ${REGION}"
echo ""
echo "Monitor executions:"
echo "aws stepfunctions list-executions \\"
echo "  --state-machine-arn arn:aws:states:${REGION}:${ACCOUNT_ID}:stateMachine:${STATE_MACHINE_NAME} \\"
echo "  --max-results 5 \\"
echo "  --region ${REGION}"
echo ""
echo "Disable schedule (if needed):"
echo "aws events disable-rule --name ${SCHEDULE_NAME} --region ${REGION}"
echo ""
echo "Re-enable schedule:"
echo "aws events enable-rule --name ${SCHEDULE_NAME} --region ${REGION}"
