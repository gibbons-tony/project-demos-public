# WhatsApp Trading Recommendations - Setup Guide

Complete guide to deploy the WhatsApp bot with real Databricks data integration.

## Architecture Overview

```
User WhatsApp → Twilio → API Gateway → Lambda → Databricks → Response
                                          ↓
                                    commodity.bronze.market_data
                                    commodity.forecast.distributions
                                    commodity.forecast.forecast_metadata
```

## Prerequisites

1. AWS CLI configured with credentials
2. Databricks workspace with Unity Catalog
3. Twilio account (free trial works)
4. Python 3.11+ installed locally

## Part 1: Deploy Lambda Function

### Step 1: Verify Databricks Credentials

Check that `~/.databrickscfg` contains your credentials:

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

If `http_path` is missing, add it manually. Get the warehouse path from:
1. Databricks UI → SQL Warehouses
2. Select your warehouse → Connection details
3. Copy "Server hostname" and "HTTP path"

### Step 2: Deploy Lambda

```bash
cd trading_agent/whatsapp
chmod +x deploy_lambda.sh
./deploy_lambda.sh
```

The script will:
- ✓ Read Databricks credentials from ~/.databrickscfg
- ✓ Install dependencies (databricks-sql-connector, numpy)
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

### Step 3: Verify Lambda Configuration

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

### Step 4: Test Lambda Function

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

## Part 2: Configure Twilio WhatsApp

### Step 1: Create Twilio Account

1. Go to https://www.twilio.com/try-twilio
2. Sign up for free trial (no credit card required for sandbox)
3. Verify your phone number

### Step 2: Enable WhatsApp Sandbox

1. In Twilio Console → Messaging → Try it out → Send a WhatsApp message
2. You'll see a QR code and join code like `join <word>-<word>`
3. Scan QR code or send WhatsApp to `+1 415 523 8886` (US number)
4. Send the join message (e.g., `join yellow-donkey`)
5. You should receive confirmation

### Step 3: Configure Webhook

1. In Twilio Console → Messaging → Settings → WhatsApp sandbox settings
2. Scroll to "Sandbox Configuration"
3. Under "WHEN A MESSAGE COMES IN":
   - Paste your Lambda webhook URL
   - Method: `POST`
4. Click "Save"

Example webhook URL:
```
https://abc123xyz.execute-api.us-west-2.amazonaws.com/prod/webhook
```

### Step 4: Test End-to-End

1. Send WhatsApp message to Twilio number: `coffee`
2. Should receive trading recommendation with:
   - Current market price (from commodity.bronze.market_data)
   - 7-day trend
   - 14-day forecast range (from commodity.forecast.distributions)
   - HOLD/SELL recommendation
   - Model version used

3. Send WhatsApp message: `sugar`
4. Should receive Sugar recommendation

## Part 3: Demo Setup

### QR Code for Demo

1. In Twilio Console → WhatsApp sandbox settings
2. Copy the QR code image URL
3. Or screenshot the QR code
4. Share this with demo participants

### Join Instructions for Participants

```
1. Scan this QR code with your phone
2. This will open WhatsApp with a pre-filled message
3. Send the message to join
4. Once joined, send "coffee" or "sugar" to get recommendations
```

Alternatively, manual join:
```
1. Open WhatsApp
2. Send message to: +1 415 523 8886
3. Send: join <your-code>  (e.g., "join yellow-donkey")
4. Wait for confirmation
5. Send: coffee
```

## Troubleshooting

### Lambda returns mock data instead of real data

**Check:** Lambda environment variables

```bash
aws lambda get-function-configuration \
  --function-name trading-recommendations-whatsapp \
  --query 'Environment.Variables'
```

**Fix:** Update environment variables

```bash
aws lambda update-function-configuration \
  --function-name trading-recommendations-whatsapp \
  --environment "Variables={DATABRICKS_HOST=https://...,DATABRICKS_TOKEN=dapi...,DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/...}"
```

### Lambda timeout or errors

**Check:** CloudWatch Logs

```bash
aws logs tail /aws/lambda/trading-recommendations-whatsapp \
  --region us-west-2 \
  --since 5m \
  --follow
```

Common issues:
- Databricks SQL warehouse stopped (start it in UI)
- Network timeout (increase Lambda timeout to 60s)
- Missing data in tables (check forecast.distributions has recent data)

### No forecast data available

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

If no data, run forecast models first:
```bash
cd forecast_agent
# Run forecast generation
```

### Twilio webhook not working

**Check:** Webhook URL is correct

1. Go to Twilio Console → WhatsApp sandbox settings
2. Verify "WHEN A MESSAGE COMES IN" has your API Gateway URL
3. Method should be POST
4. Save and try again

**Check:** API Gateway permissions

```bash
# Test API Gateway endpoint directly
curl -X POST https://your-api-id.execute-api.us-west-2.amazonaws.com/prod/webhook \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "Body=coffee&From=whatsapp%3A%2B15555551234"
```

Should return TwiML XML.

## Data Sources

The Lambda queries these Databricks tables:

### commodity.bronze.market_data
- Current prices
- Historical prices for trend calculation
- Updated daily

### commodity.forecast.distributions
- 2000 Monte Carlo simulation paths
- 14-day forecast horizon
- Columns: day_1 through day_14
- Filter: is_actuals = FALSE

### commodity.forecast.forecast_metadata
- Model performance metrics (MAE, RMSE, CRPS)
- Used to select best model
- Updated each forecast run

## Cost Estimate

### AWS Lambda
- Invocations: ~$0.20 per 1M requests
- Duration: 512MB, 5-10s per request
- **Estimate**: <$1/month for demo (< 1000 messages)

### Databricks
- SQL Warehouse queries: $0.22/DBU (Serverless)
- ~0.1 DBU per query
- **Estimate**: <$1/month for demo

### Twilio WhatsApp Sandbox
- **FREE** for sandbox
- Production: $0.005 per conversation (first 1000 free monthly)

**Total demo cost**: ~$2/month

## Production Considerations

### 1. Move from Sandbox to Production WhatsApp

Requires:
- Facebook Business Manager account
- WhatsApp Business API approval
- Message template approval (1-2 weeks)
- Domain verification

Cost: $0.005 per conversation (1000 free monthly)

### 2. Scale Lambda

For production traffic:
- Increase memory: 1024MB
- Increase timeout: 60s
- Configure reserved concurrency
- Enable X-Ray tracing

### 3. Cache Recommendations

Add caching layer:
- Cache daily recommendations in DynamoDB
- TTL: 6-24 hours
- Reduces Databricks queries by ~95%

### 4. User Management

Store user preferences:
```python
{
  "phone": "+1234567890",
  "commodity": "Coffee",
  "inventory_tons": 75,
  "notifications": "daily",
  "timezone": "America/New_York"
}
```

### 5. Monitoring

Set up CloudWatch alarms:
- Lambda errors > 5% in 5min
- Lambda duration > 25s
- API Gateway 5xx errors

## Next Steps

1. **Test with real data**: Verify forecasts are recent
2. **Add more commodities**: Extend to Cocoa, Wheat, etc.
3. **Implement Consensus strategy**: Currently using ExpectedValue for all
4. **Add alerts**: Send proactive alerts on significant price movements
5. **A/B test strategies**: Compare recommendation performance

## Support

For issues:
1. Check CloudWatch Logs: `/aws/lambda/trading-recommendations-whatsapp`
2. Verify Databricks data freshness
3. Test Lambda function directly (bypass Twilio)
4. Check Twilio webhook logs in console
