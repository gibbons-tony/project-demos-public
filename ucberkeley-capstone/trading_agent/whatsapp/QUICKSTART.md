# WhatsApp Trading Recommendations - Quick Start Guide

Get your WhatsApp demo running in **~15 minutes**.

## What You'll Build

A WhatsApp bot that sends AI-powered trading recommendations:
- Scan QR code → Send one message → Receive prediction
- Real data from Databricks (prices, forecasts, trends)
- Expected Value strategy (+3.4% proven from backtesting)

## Prerequisites

- AWS CLI configured
- Databricks credentials in `~/.databrickscfg`
- Python 3.11+
- Twilio account (free sandbox works)

## Step 1: Deploy Lambda (5 min)

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

## Step 2: Set Up Twilio (5 min)

### 2.1 Create Account
1. Go to https://www.twilio.com/try-twilio
2. Sign up (free trial, no credit card needed)
3. Verify your phone number

### 2.2 Join WhatsApp Sandbox
1. In Twilio Console → **Messaging** → **Try it out** → **Send a WhatsApp message**
2. You'll see:
   - WhatsApp number: `+1 415 523 8886` (US number)
   - Join code: e.g., `join yellow-donkey`
   - QR code

3. Join the sandbox:
   - **Option A**: Scan QR code with your phone
   - **Option B**: Send WhatsApp to `+1 415 523 8886` with message: `join yellow-donkey`

4. Wait for confirmation message

## Step 3: Configure Webhook (2 min)

1. In Twilio Console → **Messaging** → **Settings** → **WhatsApp sandbox settings**
2. Scroll to "Sandbox Configuration"
3. Under "WHEN A MESSAGE COMES IN":
   - Paste your webhook URL from Step 1
   - Method: **POST**
4. Click **Save**

## Step 4: Generate QR Code for Demo (3 min)

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

## Step 5: Test It! (1 min)

### Test Yourself
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

### Test with Others
1. Share `whatsapp_qr_code.png` with demo participants
2. They scan → Send join message → Send "coffee"
3. They receive predictions with real data

## Demo Flow

### For Participants

**Initial Setup (First Time):**
1. Scan QR code
2. WhatsApp opens with message: `join yellow-donkey`
3. Tap **Send**
4. Receive confirmation

**Get Recommendations (Anytime):**
- Send: `coffee` → Coffee recommendation
- Send: `sugar` → Sugar recommendation

## Troubleshooting

### Lambda returns mock data instead of real data

Check environment variables:
```bash
aws lambda get-function-configuration \
  --function-name trading-recommendations-whatsapp \
  --query 'Environment.Variables'
```

Should show DATABRICKS_HOST, DATABRICKS_TOKEN, DATABRICKS_HTTP_PATH.

**Fix:**
```bash
./deploy_lambda.sh  # Re-run deployment
```

### No forecast data available

Check Databricks has recent forecasts:
```sql
SELECT model_version, forecast_start_date, COUNT(*) as paths
FROM commodity.forecast.distributions
WHERE commodity = 'Coffee'
  AND is_actuals = FALSE
  AND forecast_start_date >= CURRENT_DATE - INTERVAL 7 DAYS
GROUP BY model_version, forecast_start_date
ORDER BY forecast_start_date DESC;
```

If empty, run forecast generation first:
```bash
cd forecast_agent
# Run your forecast models
```

### WhatsApp not receiving messages

1. **Check webhook URL** in Twilio console
2. **Test Lambda directly**:
   ```bash
   aws lambda invoke \
     --function-name trading-recommendations-whatsapp \
     --payload '{"body":"Body=coffee"}' \
     /tmp/test.json

   cat /tmp/test.json
   ```
3. **Check CloudWatch Logs**:
   ```bash
   aws logs tail /aws/lambda/trading-recommendations-whatsapp \
     --region us-west-2 \
     --since 5m \
     --follow
   ```

### Twilio sandbox expired

Sandbox codes expire after a period. To reset:
1. Twilio Console → WhatsApp sandbox
2. Get new join code
3. Re-generate QR code with new join code

## What's Happening Behind the Scenes

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

## Next Steps

### For Demo
- Share `whatsapp_qr_code.png` with your audience
- Show real-time predictions with live data
- Demonstrate both Coffee and Sugar recommendations

### For Production
See `WHATSAPP_SETUP.md` for:
- WhatsApp Business API (move from sandbox)
- User management (store preferences)
- Scheduled recommendations (daily 6am)
- Caching layer (reduce Databricks queries)
- Monitoring and alerts

## Files Created

- `deploy_lambda.sh` - Automated Lambda deployment
- `lambda_handler_real.py` - Lambda function with Databricks queries
- `generate_qr_code.py` - QR code generator for easy onboarding
- `whatsapp_qr_code.png` - Shareable QR code image
- `WHATSAPP_SETUP.md` - Detailed setup and troubleshooting
- `README.md` - Architecture and documentation

## Cost Estimate

**Demo (~100 messages):**
- AWS Lambda: ~$0.20
- Databricks queries: ~$0.50
- Twilio sandbox: FREE
- **Total: < $1**

**Production (1000 users, daily messages):**
- AWS Lambda: ~$5/month
- Databricks: ~$10/month
- WhatsApp Business API: ~$150/month
- **Total: ~$165/month**

## Support

Check logs:
```bash
# Lambda logs
aws logs tail /aws/lambda/trading-recommendations-whatsapp --follow

# Test webhook directly
curl -X POST https://your-api-id.execute-api.us-west-2.amazonaws.com/prod/webhook \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "Body=coffee&From=whatsapp%3A%2B15555551234"
```

For issues, see `WHATSAPP_SETUP.md` troubleshooting section.
