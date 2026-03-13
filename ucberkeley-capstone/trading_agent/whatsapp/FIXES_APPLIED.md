# WhatsApp Lambda - Fixes Applied

## Date: 2025-11-18

## Summary
Fixed critical issues preventing the Lambda from connecting to Databricks and returning accurate trading recommendations.

---

## Issues Fixed

### 1. **URL Construction Bug** 🔴 CRITICAL
**Problem**: URL was being constructed as `https://https://dbc-...` (double protocol prefix)

**Root Cause**:
```python
host = os.environ['DATABRICKS_HOST']  # Already contains 'https://'
url = f"https://{host}/api/2.0/sql/statements/"  # Adding it again!
```

**Fix**: Strip protocol prefix before constructing URL
```python
clean_host = host.replace('https://', '').replace('http://', '')
url = f"https://{clean_host}/api/2.0/sql/statements/"
```

**Files Changed**: `lambda_handler_real.py:43-44, 68, 91`

---

### 2. **Price Unit Conversion** 🔴 CRITICAL
**Problem**: Market and forecast data stored in cents, but code treated it as dollars

**Evidence**:
- Market data: `393.05` cents = $3.93/kg (not $393/kg!)
- Forecast range was showing $381-$419 instead of $3.81-$4.20

**Fix**: Added price conversion constant and applied to both market and forecast data
```python
PRICE_CENTS_TO_DOLLARS = 0.01

# Market data conversion
price_cents = float(rows[0][0])
price_dollars = price_cents * PRICE_CENTS_TO_DOLLARS

# Forecast data conversion
path = [float(row[i]) * PRICE_CENTS_TO_DOLLARS for i in range(2, 16)]
```

**Impact**: Without this fix, recommendations would be completely wrong (prices 100x too high)

**Files Changed**: `lambda_handler_real.py:20, 139-140, 348`

---

### 3. **SQL Injection Protection** 🟡 HIGH
**Problem**: User input (commodity) directly interpolated into SQL queries

**Fix**: Added input validation whitelist
```python
ALLOWED_COMMODITIES = {'Coffee', 'Sugar', 'Cocoa', 'Wheat'}

if commodity not in ALLOWED_COMMODITIES:
    raise ValueError(f"Invalid commodity: {commodity}")
```

**Files Changed**: `lambda_handler_real.py:17, 123, 155, 206, 299`

---

### 4. **Missing NumPy Dependency** 🟡 HIGH
**Problem**: `numpy` was commented out in requirements.txt but imported in code

**Fix**: Uncommented numpy in requirements
```python
numpy==1.26.4  # Now active
```

**Files Changed**: `requirements_lambda.txt:9`

---

### 5. **Type Conversion Error** 🟡 MEDIUM
**Problem**: Metric value from Databricks returned as string, code tried to format as float

**Error**:
```
ValueError: Unknown format code 'f' for object of type 'str'
```

**Fix**: Explicit type conversion
```python
metric_value = float(metric_rows[0][1]) if metric_rows[0][1] is not None else None
if metric_value is not None:
    print(f"Best model by {metric}: {best_model} (avg={metric_value:.4f})")
```

**Files Changed**: `lambda_handler_real.py:251-255`

---

### 6. **Improved Error Handling & Logging** ✅ ENHANCEMENT
**Added**:
- Progress indicators ([1/4], [2/4], etc.)
- Detailed logging at each step
- Better error messages with context
- Graceful fallback to mock data
- Input validation with clear error messages

**Example Output**:
```
[1/4] Fetching current market data...
✓ Current price: $3.93 (as of 2025-10-31)

[2/4] Calculating 7-day trend...
✓ 7-day trend: -6.6%

[3/4] Fetching forecast data...
✓ Using model: sarimax_auto_weather_v1
✓ Forecast date: 2025-10-25
✓ Paths loaded: 2000

[4/4] Calculating Expected Value recommendation...
✓ Decision: SELL
✓ Expected gain: $0.00
```

**Files Changed**: `lambda_handler_real.py:535-582, 143, 174, 347-355`

---

## Test Results

### Coffee ✅
```
Price: $3.93/kg
7-Day Trend: 📉 -6.6%
Forecast Range: $3.81 - $4.20
Model: sarimax_auto_weather_v1
Recommendation: SELL NOW
Status: Using REAL Databricks data
```

### Sugar ✅
```
Price: $0.14/kg
7-Day Trend: 📉 -4.5%
Status: Market data from Databricks, no recent forecasts (falls back to mock)
```

---

## Deployment Notes

### Before Deploying

1. **Update Lambda timeout** (if using AWS):
   ```bash
   aws lambda update-function-configuration \
     --function-name trading-recommendations-whatsapp \
     --timeout 60
   ```
   Current: 30s (too short for Databricks queries)
   Recommended: 60s

2. **Redeploy with new code**:
   ```bash
   cd trading_agent/whatsapp
   ./deploy_lambda.sh
   ```

3. **Verify environment variables** are set:
   - `DATABRICKS_HOST` (without extra https://)
   - `DATABRICKS_TOKEN`
   - `DATABRICKS_HTTP_PATH`

### Testing

**Local test**:
```bash
cd trading_agent/whatsapp
python3 -c "
import os
os.environ['DATABRICKS_HOST'] = 'https://your-workspace.databricks.com'
os.environ['DATABRICKS_TOKEN'] = 'dapi...'
os.environ['DATABRICKS_HTTP_PATH'] = '/sql/1.0/warehouses/...'

from lambda_handler_real import lambda_handler
result = lambda_handler({
    'body': 'Body=coffee',
    'httpMethod': 'POST'
}, None)
print(result['body'][:500])
"
```

**AWS Lambda test**:
```bash
aws lambda invoke \
  --function-name trading-recommendations-whatsapp \
  --region us-west-2 \
  --payload '{"body":"Body=coffee","httpMethod":"POST"}' \
  --cli-binary-format raw-in-base64-out \
  /tmp/test-response.json

cat /tmp/test-response.json
```

---

## Known Issues / Limitations

### 1. Forecast Data Availability
- **Sugar**: No recent forecasts in commodity.forecast.distributions
- **Impact**: Falls back to mock data for Sugar
- **Solution**: Ensure forecast models are running for all commodities

### 2. Forecast Age
- Current setting: `max_age_days=30`
- Coffee has forecasts from 2025-10-25 (7 days old) - works fine
- Consider reducing to 7 days for fresher forecasts

### 3. Variable Path Counts
- Code expects 2000 paths
- Coffee data has 2000 paths ✓
- But found models with 4000 paths in testing
- **Fixed**: Code now handles variable path counts dynamically

---

## Performance

### Typical Response Time
- Market data query: 2-3 seconds
- Trend calculation: 2-3 seconds
- Forecast metadata: 2-3 seconds
- Forecast data load: 3-5 seconds
- **Total**: 10-15 seconds

### Optimization Opportunities
1. **Cache recommendations** (DynamoDB, 1-hour TTL) → Save ~$0.02/query
2. **Combine SQL queries** → Reduce to 2 queries instead of 5
3. **Lambda layer for NumPy** → Reduce package size by 30MB
4. **Use Databricks SQL Endpoint connection pooling** → Faster subsequent queries

---

## Security Checklist

- [x] SQL injection protection (whitelist validation)
- [x] Input sanitization (commodity names)
- [x] Error messages don't leak sensitive info
- [ ] Twilio webhook signature validation (TODO)
- [ ] Rate limiting (API Gateway throttling) (TODO)
- [ ] Move secrets to AWS Secrets Manager (TODO)

---

## Next Steps

1. **Immediate**:
   - Deploy updated code to AWS Lambda
   - Test end-to-end with Twilio webhook
   - Monitor CloudWatch logs for errors

2. **Short-term**:
   - Add Twilio webhook signature validation
   - Implement caching layer (DynamoDB)
   - Set up CloudWatch alarms

3. **Medium-term**:
   - Generate forecasts for Sugar
   - Optimize query performance
   - Add user management (custom inventory sizes)

---

### 7. **Updated WhatsApp Message Format** ✅ ENHANCEMENT
**Problem**: Message format didn't match specification in `Whatsapp demo.pdf`

**Changes**:
- Header now shows commodity emoji and name (☕ COFFEE MARKET UPDATE)
- Added date at top
- Changed from $/kg to $/ton pricing
- Updated section headers (CURRENT MARKET, FORECAST (14 days), YOUR INVENTORY)
- Changed recommendation format to match spec
- Removed technical details (model version, strategy)
- Added "Next update: Tomorrow 6 AM" footer

**Before**:
```
────────────────────────────────────────
📊 *Current Market*
Price: $3.93/kg
7-Day Trend: 📉 -6.6%
...
_Model: sarimax_auto_weather_v1_
```

**After**:
```
☕ *COFFEE MARKET UPDATE*

_Nov 18, 2025_

*CURRENT MARKET*
📊 Today: $3,930/ton
↓ 7-day trend: -6.6%
...
_Next update: Tomorrow 6 AM_
```

**Files Changed**: `lambda_handler_real.py:456-555`, `lambda_handler.py:14-95`

---

## Files Modified

1. `lambda_handler_real.py` - Main fixes (URL, prices, validation, logging, message format)
2. `lambda_handler.py` - Updated mock message format
3. `requirements_lambda.txt` - Uncommented numpy
4. `FIXES_APPLIED.md` - This document

## Lines Changed
- **lambda_handler_real.py**: ~120 lines modified, ~40 lines added
- **lambda_handler.py**: ~85 lines modified
- **requirements_lambda.txt**: 1 line uncommented

---

## Verification Commands

```bash
# Check market data
curl -X POST "https://dbc-XXX.cloud.databricks.com/api/2.0/sql/statements/" \
  -H "Authorization: Bearer dapi..." \
  -d '{"statement":"SELECT * FROM commodity.bronze.market WHERE commodity='\''Coffee'\'' ORDER BY date DESC LIMIT 1","warehouse_id":"..."}'

# Check forecast availability
curl -X POST "https://dbc-XXX.cloud.databricks.com/api/2.0/sql/statements/" \
  -H "Authorization: Bearer dapi..." \
  -d '{"statement":"SELECT model_version, COUNT(*) FROM commodity.forecast.distributions WHERE commodity='\''Coffee'\'' AND is_actuals=FALSE GROUP BY model_version","warehouse_id":"..."}'

# Test Lambda
aws lambda invoke --function-name trading-recommendations-whatsapp \
  --payload '{"body":"Body=coffee"}' response.json && cat response.json
```

---

## Contact

For issues or questions about these fixes, check:
- CloudWatch Logs: `/aws/lambda/trading-recommendations-whatsapp`
- Databricks workspace: https://dbc-5e4780f4-fcec.cloud.databricks.com
- This repository: `trading_agent/whatsapp/`
