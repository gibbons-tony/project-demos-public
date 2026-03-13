# WhatsApp Trading Bot Setup Guide

Complete guide to deploy the WhatsApp trading recommendations bot with real Databricks data integration.

## Table of Contents

1. [Quick Start (15 minutes)](#quick-start-15-minutes)
2. [Architecture Overview](#architecture-overview)
3. [Prerequisites](#prerequisites)
4. [Detailed Setup](#detailed-setup)
5. [Configuration](#configuration)
6. [Testing](#testing)
7. [Demo Setup](#demo-setup)
8. [Troubleshooting](#troubleshooting)
9. [Production Deployment](#production-deployment)
10. [Cost Estimates](#cost-estimates)

---

## Quick Start (15 minutes)

Get your WhatsApp demo running quickly with these streamlined steps.

### What You'll Build

A WhatsApp bot that sends AI-powered trading recommendations:
- Scan QR code → Send one message → Receive prediction
- Real data from Databricks (prices, forecasts, trends)
- Expected Value strategy (+3.4% proven from backtesting)

### Quick Prerequisites

- AWS CLI configured
- Databricks credentials in `~/.databrickscfg`
- Python 3.11+
- Twilio account (free sandbox works)

### Quick Step 1: Deploy Lambda (5 min)

```bash
cd trading_agent/whatsapp

# Deploy Lambda with Databricks integration
./deploy_lambda.sh
```

**Output:**
```
✓ Lambda function created
✓ API Gateway configured
✓ Lambda test successful

Webhook URL:
  https://abc123xyz.execute-api.us-west-2.amazonaws.com/prod/webhook

Databricks connection:
  ✓ Host: https://your-workspace.cloud.databricks.com
  ✓ Token: dapi...
  ✓ Warehouse: /sql/1.0/warehouses/...

Lambda will query real data from Databricks
```

**Save the webhook URL** - you'll need it in step 3.

### Quick Step 2: Set Up Twilio (5 min)

#### 2.1 Create Account
1. Go to https://www.twilio.com/try-twilio
2. Sign up (free trial, no credit card needed)
3. Verify your phone number

#### 2.2 Join WhatsApp Sandbox
1. In Twilio Console → **Messaging** → **Try it out** → **Send a WhatsApp message**
2. You'll see:
   - WhatsApp number: `+1 415 523 8886` (US number)
   - Join code: e.g., `join yellow-donkey`
   - QR code

3. Join the sandbox:
   - **Option A**: Scan QR code with your phone
   - **Option B**: Send WhatsApp to `+1 415 523 8886` with message: `join yellow-donkey`

4. Wait for confirmation message

### Quick Step 3: Configure Webhook (2 min)

1. In Twilio Console → **Messaging** → **Settings** → **WhatsApp sandbox settings**
2. Scroll to "Sandbox Configuration"
3. Under "WHEN A MESSAGE COMES IN":
   - Paste your webhook URL from Step 1
   - Method: **POST**
4. Click **Save**

### Quick Step 4: Generate QR Code for Demo (3 min)

Install QR code library:
```bash
pip3 install qrcode pillow
```

Generate QR code:
```bash
./generate_qr_code.py \
  --twilio-number "+14155238886" \
  --join-code "yellow-donkey" \
  --commodity coffee
```

**Output:**
```
✓ QR code saved to: whatsapp_qr_code.png

WhatsApp Link:
  https://wa.me/14155238886?text=join%20yellow-donkey
```

This creates a QR code that:
- Opens WhatsApp with pre-filled join message
- User taps "Send" once to join
- Then can send "coffee" or "sugar" for recommendations

### Quick Step 5: Test It! (1 min)

Send WhatsApp message to Twilio number:
```
coffee
```

**Expected Response:**
```
────────────────────────────────────────
📊 Current Market
Price: $2.15/kg
7-Day Trend: 📈 +2.3%

🔮 14-Day Forecast
Range: $2.08 - $2.28
Best Sale Window: Days 9-11

📦 Inventory
Stock: 50 tons
Hold Duration: 10 days

💡 Recommendation
✋ HOLD
Expected Gain: $6,250
Sell on: Day 10

Model: sarimax_auto_weather_v1
Strategy: Expected Value (+3.4% proven)
Forecast Date: 2025-01-18
────────────────────────────────────────
```

---

## Architecture Overview

```
User WhatsApp → Twilio → API Gateway → Lambda → Databricks → Response
                                          ↓
                                    commodity.bronze.market_data
                                    commodity.forecast.distributions
                                    commodity.forecast.forecast_metadata
```

### Data Flow

```
User sends "coffee"
  ↓
Twilio forwards to Lambda webhook
  ↓
Lambda queries Databricks:
  - commodity.bronze.market_data (current price, 7-day trend)
  - commodity.forecast.distributions (2000 MC paths × 14 days)
  ↓
Lambda calculates Expected Value strategy:
  - Evaluate selling on each future day (1-14)
  - Account for storage costs (0.025%/day)
  - Account for transaction costs (0.25%)
  - Recommend HOLD if expected gain > $50/ton
  ↓
Lambda formats WhatsApp message
  ↓
Twilio sends to user's WhatsApp
```

---

## Prerequisites

### Required Software
1. **AWS CLI** configured with credentials
   ```bash
   aws configure
   # or verify: aws sts get-caller-identity
   ```

2. **Python 3.11+** installed locally
   ```bash
   python3 --version
   ```

3. **Databricks workspace** with Unity Catalog
   - Access to `commodity.bronze.market_data`
   - Access to `commodity.forecast.distributions`
   - SQL Warehouse running

4. **Twilio account** (free trial works)
   - Sign up at https://www.twilio.com/try-twilio
   - No credit card required for sandbox

### Databricks Configuration

Verify `~/.databrickscfg` contains your credentials:

```bash
cat ~/.databrickscfg
```

Should contain:
```ini
[DEFAULT]
host = https://your-workspace.cloud.databricks.com
token = dapi...
http_path = /sql/1.0/warehouses/...
```

If `http_path` is missing, add it manually:
1. Databricks UI → SQL Warehouses
2. Select your warehouse → Connection details
3. Copy "Server hostname" and "HTTP path"

---

## Detailed Setup

### Part 1: Deploy Lambda Function

#### Step 1: Prepare Databricks Credentials

The deployment script reads credentials from `~/.databrickscfg`. Verify all three values are present:

```bash
grep -E 'host|token|http_path' ~/.databrickscfg
```

Should show:
```
host = https://...
token = dapi...
http_path = /sql/1.0/warehouses/...
```

#### Step 2: Run Deployment Script

```bash
cd trading_agent/whatsapp
chmod +x deploy_lambda.sh
./deploy_lambda.sh
```

The script will:
- ✓ Read Databricks credentials from `~/.databrickscfg`
- ✓ Install dependencies (`databricks-sql-connector`, `numpy`)
- ✓ Package Lambda function (3-15MB)
- ✓ Create/update Lambda function in AWS
- ✓ Set environment variables for Databricks connection
- ✓ Create API Gateway endpoint
- ✓ Test the function

**Save the webhook URL** from the output:
```
Webhook URL:
  https://xxxxx.execute-api.us-west-2.amazonaws.com/prod/webhook
```

#### Step 3: Verify Lambda Configuration

Check environment variables are set:

```bash
aws lambda get-function-configuration \
  --function-name trading-recommendations-whatsapp \
  --region us-west-2 \
  --query 'Environment.Variables'
```

Should show:
```json
{
  "DATABRICKS_HOST": "https://...",
  "DATABRICKS_TOKEN": "dapi...",
  "DATABRICKS_HTTP_PATH": "/sql/1.0/warehouses/..."
}
```

#### Step 4: Test Lambda Function Directly

Test with Coffee recommendation:

```bash
aws lambda invoke \
  --function-name trading-recommendations-whatsapp \
  --region us-west-2 \
  --payload '{"body":"Body=coffee","httpMethod":"POST"}' \
  --cli-binary-format raw-in-base64-out \
  /tmp/test-coffee.json

cat /tmp/test-coffee.json
```

Should return TwiML response with real market data and forecast.

Test with Sugar:

```bash
aws lambda invoke \
  --function-name trading-recommendations-whatsapp \
  --region us-west-2 \
  --payload '{"body":"Body=sugar","httpMethod":"POST"}' \
  --cli-binary-format raw-in-base64-out \
  /tmp/test-sugar.json

cat /tmp/test-sugar.json
```

### Part 2: Configure Twilio WhatsApp

#### Step 1: Create Twilio Account

1. Go to https://www.twilio.com/try-twilio
2. Sign up for free trial (no credit card required for sandbox)
3. Verify your phone number
4. Complete onboarding questions

#### Step 2: Enable WhatsApp Sandbox

1. In Twilio Console → **Messaging** → **Try it out** → **Send a WhatsApp message**
2. You'll see a QR code and join code like `join <word>-<word>`
3. Join the sandbox:
   - **Option A**: Scan QR code with your phone
   - **Option B**: Send WhatsApp to `+1 415 523 8886` (US number)
     - Message: `join yellow-donkey` (use your specific code)
4. You should receive confirmation message

**Note:** The join code is unique to your account and changes periodically.

#### Step 3: Configure Webhook

1. In Twilio Console → **Messaging** → **Settings** → **WhatsApp sandbox settings**
2. Scroll to "Sandbox Configuration"
3. Under "WHEN A MESSAGE COMES IN":
   - Paste your Lambda webhook URL
   - Method: `POST`
4. Click "Save"

Example webhook URL:
```
https://abc123xyz.execute-api.us-west-2.amazonaws.com/prod/webhook
```

#### Step 4: Test End-to-End

1. Send WhatsApp message to Twilio number: `coffee`
2. Should receive trading recommendation with:
   - Current market price (from `commodity.bronze.market_data`)
   - 7-day trend
   - 14-day forecast range (from `commodity.forecast.distributions`)
   - HOLD/SELL recommendation
   - Model version used

3. Send WhatsApp message: `sugar`
4. Should receive Sugar recommendation

---

## Configuration

### Environment Variables

Lambda function uses these environment variables (set automatically by `deploy_lambda.sh`):

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABRICKS_HOST` | Databricks workspace URL | `https://dbc-12345.cloud.databricks.com` |
| `DATABRICKS_TOKEN` | Personal access token | `dapi...` |
| `DATABRICKS_HTTP_PATH` | SQL Warehouse path | `/sql/1.0/warehouses/abc123` |

### Update Environment Variables Manually

If needed, update variables manually:

```bash
aws lambda update-function-configuration \
  --function-name trading-recommendations-whatsapp \
  --region us-west-2 \
  --environment "Variables={DATABRICKS_HOST=https://...,DATABRICKS_TOKEN=dapi...,DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/...}"
```

### Lambda Function Configuration

Default settings:
- **Memory**: 512 MB
- **Timeout**: 60 seconds
- **Runtime**: Python 3.11
- **Architecture**: x86_64

Adjust if needed:

```bash
# Increase memory to 1024 MB
aws lambda update-function-configuration \
  --function-name trading-recommendations-whatsapp \
  --memory-size 1024

# Increase timeout to 120 seconds
aws lambda update-function-configuration \
  --function-name trading-recommendations-whatsapp \
  --timeout 120
```

---

## Testing

### Test Lambda Directly

Bypass Twilio and test Lambda function:

```bash
# Test Coffee
aws lambda invoke \
  --function-name trading-recommendations-whatsapp \
  --payload '{"body":"Body=coffee"}' \
  /tmp/test.json

cat /tmp/test.json
```

### Test API Gateway Endpoint

Test the webhook URL directly:

```bash
curl -X POST https://your-api-id.execute-api.us-west-2.amazonaws.com/prod/webhook \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "Body=coffee&From=whatsapp%3A%2B15555551234"
```

Should return TwiML XML response.

### Test WhatsApp End-to-End

1. Send WhatsApp message to Twilio number
2. Message body: `coffee` or `sugar`
3. Verify response contains:
   - Current price
   - Trend
   - Forecast range
   - Recommendation (HOLD/SELL)
   - Model version

### Monitor Logs

Watch CloudWatch Logs in real-time:

```bash
aws logs tail /aws/lambda/trading-recommendations-whatsapp \
  --region us-west-2 \
  --since 5m \
  --follow
```

---

## Demo Setup

### Generate QR Code for Easy Onboarding

Install dependencies:
```bash
pip3 install qrcode pillow
```

Generate QR code:
```bash
./generate_qr_code.py \
  --twilio-number "+14155238886" \
  --join-code "yellow-donkey" \
  --commodity coffee
```

**Output:**
```
✓ QR code saved to: whatsapp_qr_code.png

WhatsApp Link:
  https://wa.me/14155238886?text=join%20yellow-donkey
```

### Share with Demo Participants

#### For Participants (First Time Setup)

1. Scan QR code
2. WhatsApp opens with message: `join yellow-donkey`
3. Tap **Send**
4. Receive confirmation
5. Now send: `coffee` or `sugar`

#### Manual Join Instructions

```
1. Open WhatsApp
2. Send message to: +1 415 523 8886
3. Send: join <your-code>  (e.g., "join yellow-donkey")
4. Wait for confirmation
5. Send: coffee
```

### Demo Flow

**Get Recommendations (Anytime):**
- Send: `coffee` → Coffee recommendation
- Send: `sugar` → Sugar recommendation

---

## Troubleshooting

### Lambda returns mock data instead of real data

**Symptoms:**
- Recommendations show generic/fake data
- No model version in response
- Prices don't match current market

**Check:** Lambda environment variables

```bash
aws lambda get-function-configuration \
  --function-name trading-recommendations-whatsapp \
  --query 'Environment.Variables'
```

**Fix:** Re-run deployment script

```bash
./deploy_lambda.sh
```

Or update variables manually:

```bash
aws lambda update-function-configuration \
  --function-name trading-recommendations-whatsapp \
  --environment "Variables={DATABRICKS_HOST=https://...,DATABRICKS_TOKEN=dapi...,DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/...}"
```

### Lambda timeout or errors

**Symptoms:**
- WhatsApp message not received
- Delayed responses (>30 seconds)
- Error messages

**Check:** CloudWatch Logs

```bash
aws logs tail /aws/lambda/trading-recommendations-whatsapp \
  --region us-west-2 \
  --since 5m \
  --follow
```

**Common Issues:**
- **Databricks SQL warehouse stopped** → Start it in Databricks UI
- **Network timeout** → Increase Lambda timeout to 60s+
- **Missing data in tables** → Check `forecast.distributions` has recent data

**Fix timeout:**

```bash
aws lambda update-function-configuration \
  --function-name trading-recommendations-whatsapp \
  --timeout 120
```

### No forecast data available

**Symptoms:**
- Response says "No forecast data available"
- Mock data returned instead of real forecast

**Check:** Databricks tables

```sql
-- Check latest forecast
SELECT model_version, forecast_start_date, COUNT(*) as path_count
FROM commodity.forecast.distributions
WHERE commodity = 'Coffee'
  AND is_actuals = FALSE
GROUP BY model_version, forecast_start_date
ORDER BY forecast_start_date DESC
LIMIT 5;

-- Check market data
SELECT date, close
FROM commodity.bronze.market_data
WHERE commodity = 'Coffee'
ORDER BY date DESC
LIMIT 5;
```

**Fix:** Run forecast models first

```bash
cd forecast_agent
# Run forecast generation
python -m ground_truth.models.sarimax_auto_weather_v1
```

### WhatsApp not receiving messages

**Symptoms:**
- Send message to Twilio number
- No response received

**Check 1:** Webhook URL in Twilio console

1. Go to Twilio Console → WhatsApp sandbox settings
2. Verify "WHEN A MESSAGE COMES IN" has your API Gateway URL
3. Method should be POST
4. Save and try again

**Check 2:** Test Lambda directly

```bash
aws lambda invoke \
  --function-name trading-recommendations-whatsapp \
  --payload '{"body":"Body=coffee"}' \
  /tmp/test.json

cat /tmp/test.json
```

**Check 3:** CloudWatch Logs

```bash
aws logs tail /aws/lambda/trading-recommendations-whatsapp \
  --region us-west-2 \
  --since 5m \
  --follow
```

**Check 4:** API Gateway endpoint

```bash
curl -X POST https://your-api-id.execute-api.us-west-2.amazonaws.com/prod/webhook \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "Body=coffee&From=whatsapp%3A%2B15555551234"
```

### Twilio sandbox expired

**Symptoms:**
- Join code no longer works
- Existing users can't send messages

**Fix:**
1. Twilio Console → WhatsApp sandbox
2. Get new join code
3. Re-generate QR code with new join code:
   ```bash
   ./generate_qr_code.py \
     --twilio-number "+14155238886" \
     --join-code "new-join-code" \
     --commodity coffee
   ```
4. Share new QR code with participants

### API Gateway permissions issues

**Symptoms:**
- 403 Forbidden
- API Gateway returns error

**Fix:** Ensure Lambda has API Gateway trigger

```bash
# Check Lambda triggers
aws lambda get-function \
  --function-name trading-recommendations-whatsapp \
  --query 'Configuration.FunctionArn'
```

The deployment script should handle this automatically. If issues persist, re-run:

```bash
./deploy_lambda.sh
```

---

## Production Deployment

### 1. Move from Sandbox to Production WhatsApp

**Sandbox Limitations:**
- Limited to pre-approved phone numbers
- Join code required for each user
- Sandbox can expire

**Production WhatsApp Business API Requirements:**
- Facebook Business Manager account
- WhatsApp Business API approval (1-2 weeks)
- Message template approval
- Domain verification
- Phone number verification

**Cost:** $0.005 per conversation (first 1000 free monthly)

**Steps:**
1. Apply for WhatsApp Business API access through Twilio
2. Create message templates for approval
3. Verify business domain
4. Update webhook URL in production settings
5. Remove sandbox join code requirements

### 2. Scale Lambda for Production

**Recommended Configuration:**

```bash
# Increase memory to 1024 MB
aws lambda update-function-configuration \
  --function-name trading-recommendations-whatsapp \
  --memory-size 1024

# Increase timeout to 60 seconds
aws lambda update-function-configuration \
  --function-name trading-recommendations-whatsapp \
  --timeout 60

# Configure reserved concurrency
aws lambda put-function-concurrency \
  --function-name trading-recommendations-whatsapp \
  --reserved-concurrent-executions 10

# Enable X-Ray tracing
aws lambda update-function-configuration \
  --function-name trading-recommendations-whatsapp \
  --tracing-config Mode=Active
```

### 3. Add Caching Layer

**Problem:** Each request queries Databricks (~0.1 DBU, 5-10s latency)

**Solution:** Cache daily recommendations in DynamoDB

**Implementation:**

```python
# Cache structure in DynamoDB
{
  "commodity": "Coffee",
  "date": "2025-01-18",
  "recommendation": {...},
  "ttl": 1737244800  # 6-24 hours
}
```

**Benefits:**
- Reduces Databricks queries by ~95%
- Faster responses (<1s)
- Lower costs

**Cost:** DynamoDB on-demand pricing (~$0.25/month for demo)

### 4. User Management

**Store user preferences in DynamoDB:**

```python
{
  "phone": "+1234567890",
  "commodity": "Coffee",
  "inventory_tons": 75,
  "notifications": "daily",  # or "weekly", "none"
  "timezone": "America/New_York",
  "language": "en",
  "created_at": "2025-01-18T10:00:00Z"
}
```

**Features to Add:**
- User registration flow
- Preference updates via WhatsApp
- Daily scheduled recommendations
- Alert thresholds (price movements, forecast changes)

### 5. Monitoring and Alerts

**CloudWatch Alarms:**

```bash
# Lambda errors > 5% in 5 minutes
aws cloudwatch put-metric-alarm \
  --alarm-name trading-bot-high-error-rate \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold

# Lambda duration > 25 seconds
aws cloudwatch put-metric-alarm \
  --alarm-name trading-bot-high-duration \
  --metric-name Duration \
  --namespace AWS/Lambda \
  --statistic Average \
  --period 300 \
  --threshold 25000 \
  --comparison-operator GreaterThanThreshold

# API Gateway 5xx errors
aws cloudwatch put-metric-alarm \
  --alarm-name trading-bot-api-errors \
  --metric-name 5XXError \
  --namespace AWS/ApiGateway \
  --statistic Sum \
  --period 300 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold
```

**Metrics to Track:**
- Lambda invocations per day
- Average response time
- Error rate
- Databricks query time
- User engagement (messages per user)
- Recommendation accuracy (if users report outcomes)

### 6. Scheduled Recommendations

**Use AWS EventBridge to send daily recommendations:**

```bash
# Create EventBridge rule for daily 6am EST
aws events put-rule \
  --name trading-daily-recommendations \
  --schedule-expression "cron(0 11 * * ? *)"  # 6am EST = 11am UTC

# Add Lambda as target
aws events put-targets \
  --rule trading-daily-recommendations \
  --targets "Id"="1","Arn"="arn:aws:lambda:us-west-2:ACCOUNT:function:trading-recommendations-whatsapp"
```

**Lambda modification needed:**
- Check if invocation is from EventBridge vs API Gateway
- Query DynamoDB for users with `notifications: "daily"`
- Send recommendations via Twilio API (not TwiML response)

### 7. A/B Testing

**Test different recommendation strategies:**

```python
# Assign users to cohorts
cohorts = {
  "control": "ExpectedValue",
  "treatment_a": "Consensus",
  "treatment_b": "RiskAdjusted"
}

# Track performance by cohort
metrics = {
  "cohort": "treatment_a",
  "recommendations": 50,
  "actions_taken": 12,
  "reported_profit": 3500
}
```

---

## Cost Estimates

### Demo Usage (~100 messages)

| Service | Usage | Cost |
|---------|-------|------|
| AWS Lambda | 100 invocations × 512MB × 10s | ~$0.20 |
| Databricks | 100 queries × 0.1 DBU × $0.22/DBU | ~$0.50 |
| Twilio Sandbox | 100 messages | **FREE** |
| **Total** | | **< $1** |

### Production Usage (1000 users, daily messages)

| Service | Usage | Cost |
|---------|-------|------|
| AWS Lambda | 30K invocations/month | ~$5/month |
| Databricks | 1K queries/month (with caching) | ~$10/month |
| WhatsApp Business API | 30K conversations/month | ~$150/month |
| DynamoDB | 30K reads, 1K writes | ~$0.25/month |
| **Total** | | **~$165/month** |

**Notes:**
- Caching reduces Databricks costs by 95%
- First 1000 WhatsApp conversations free monthly
- Lambda costs scale linearly with usage
- Databricks costs depend on query complexity

---

## Data Sources

The Lambda queries these Databricks tables:

### commodity.bronze.market_data

- **Purpose**: Current prices and historical data
- **Grain**: `(date, commodity, region)`
- **Update Frequency**: Daily
- **Usage**: Calculate current price and 7-day trend

**Query Example:**
```sql
SELECT date, close
FROM commodity.bronze.market_data
WHERE commodity = 'Coffee'
ORDER BY date DESC
LIMIT 7;
```

### commodity.forecast.distributions

- **Purpose**: Monte Carlo simulation paths
- **Grain**: `(forecast_start_date, commodity, region, simulation_id)`
- **Columns**: `day_1` through `day_14`
- **Paths**: 2000 simulations per forecast
- **Filter**: `is_actuals = FALSE`
- **Update Frequency**: Daily or as forecasts run

**Query Example:**
```sql
SELECT day_1, day_2, ..., day_14
FROM commodity.forecast.distributions
WHERE commodity = 'Coffee'
  AND forecast_start_date = (
    SELECT MAX(forecast_start_date)
    FROM commodity.forecast.distributions
    WHERE commodity = 'Coffee' AND is_actuals = FALSE
  )
  AND is_actuals = FALSE;
```

### commodity.forecast.forecast_metadata

- **Purpose**: Model performance metrics
- **Metrics**: MAE, RMSE, CRPS
- **Usage**: Select best performing model
- **Update Frequency**: Each forecast run

**Query Example:**
```sql
SELECT model_version, crps
FROM commodity.forecast.forecast_metadata
WHERE commodity = 'Coffee'
ORDER BY crps ASC
LIMIT 1;
```

---

## Files Created

- `deploy_lambda.sh` - Automated Lambda deployment script
- `lambda_handler_real.py` - Lambda function with Databricks queries
- `generate_qr_code.py` - QR code generator for easy onboarding
- `whatsapp_qr_code.png` - Shareable QR code image
- `SETUP_GUIDE.md` - This comprehensive setup guide
- `README.md` - Architecture and documentation

---

## Next Steps

### For Demo
- Share `whatsapp_qr_code.png` with your audience
- Show real-time predictions with live data
- Demonstrate both Coffee and Sugar recommendations

### For Production
- Move from sandbox to WhatsApp Business API
- Add caching layer (DynamoDB)
- Implement user management
- Set up monitoring and alerts
- Add scheduled daily recommendations

### For Enhancement
1. **Add more commodities**: Extend to Cocoa, Wheat, etc.
2. **Implement Consensus strategy**: Currently using ExpectedValue for all
3. **Add proactive alerts**: Notify on significant price movements
4. **A/B test strategies**: Compare recommendation performance
5. **Add LLM integration**: Natural language queries and explanations

---

## Support

### Check Logs

```bash
# Lambda logs
aws logs tail /aws/lambda/trading-recommendations-whatsapp \
  --region us-west-2 \
  --follow

# Test webhook directly
curl -X POST https://your-api-id.execute-api.us-west-2.amazonaws.com/prod/webhook \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "Body=coffee&From=whatsapp%3A%2B15555551234"
```

### Verify Databricks Data

```sql
-- Check forecast freshness
SELECT model_version, forecast_start_date, COUNT(*) as paths
FROM commodity.forecast.distributions
WHERE commodity = 'Coffee'
  AND is_actuals = FALSE
  AND forecast_start_date >= CURRENT_DATE - INTERVAL 7 DAYS
GROUP BY model_version, forecast_start_date
ORDER BY forecast_start_date DESC;

-- Check market data
SELECT date, close
FROM commodity.bronze.market_data
WHERE commodity = 'Coffee'
ORDER BY date DESC
LIMIT 10;
```

### Test Lambda Function

```bash
# Direct test
aws lambda invoke \
  --function-name trading-recommendations-whatsapp \
  --payload '{"body":"Body=coffee"}' \
  /tmp/test.json

cat /tmp/test.json
```

---

**Last Updated:** 2025-01-18
**Maintained By:** Trading Agent Team
