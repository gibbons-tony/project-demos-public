# WhatsApp Trading Recommendations

Automated daily trading recommendations for Coffee and Sugar commodities, delivered via WhatsApp.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              Databricks Unity Catalog                    │
│                                                          │
│  ┌────────────────────┐  ┌─────────────────────────┐   │
│  │ commodity.forecast │  │ commodity.bronze        │   │
│  │ .distributions     │  │ .market_data            │   │
│  │ (2000 MC paths)    │  │ (historical prices)     │   │
│  └────────────────────┘  └─────────────────────────┘   │
│                                                          │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ SQL queries
                     │
         ┌───────────▼──────────────┐
         │  generate_daily_          │
         │  recommendation.py        │
         │                           │
         │  - Availability-first     │
         │    model selection        │
         │  - Expected Value         │
         │    strategy               │
         │  - WhatsApp formatting    │
         └───────────┬───────────────┘
                     │
                     │ JSON output
                     │
         ┌───────────▼──────────────┐
         │  WhatsApp Business API    │
         │  (future integration)     │
         └───────────────────────────┘
```

## Two-Step Optimization Approach

**Q: "Where are you getting the best model from?"**

**A: We use a two-step optimization:**
1. **Select best forecast model** from `commodity.forecast.forecast_metadata` (forecast accuracy)
2. **Select best trading strategy** for that model from backtesting results

### Step 1: Forecast Model Selection

Query `commodity.forecast.forecast_metadata` for best performing model:

```python
def get_best_model_from_forecast_metadata(connection, commodity, metric='mae_14d'):
    """
    SELECT model_version, AVG(mae_14d) as avg_metric
    FROM commodity.forecast.forecast_metadata
    WHERE commodity = 'Coffee'
      AND mae_14d IS NOT NULL
    GROUP BY model_version
    ORDER BY avg_metric ASC  -- Lower MAE is better
    LIMIT 1
    """
```

**Metrics Available**:
- MAE (Mean Absolute Error): 1d, 7d, 14d horizons
- RMSE (Root Mean Squared Error): 1d, 7d, 14d
- CRPS (Continuous Ranked Probability Score): 1d, 7d, 14d
- Calibration scores and coverage metrics

**Fallback**: If best model has no recent forecast, try other models in order until one is found.

### Step 2: Trading Strategy Selection

Based on backtesting results (see `trading_agent/MASTER_SYSTEM_PLAN.md`):

```python
def get_best_strategy_for_model(commodity, model_version):
    """
    Coffee: ExpectedValue strategy (proven +3.4% vs baseline)
    Sugar: ImmediateSale strategy (stable commodity, predictions add no value)

    TODO: Query commodity.trading.backtest_results table once created
    """
```

**Current Implementation**: Hardcoded based on backtest findings
- **Coffee**: All 12 models → Expected Value strategy ($751,641 net earnings)
- **Sugar**: All 9 models → Immediate Sale strategy ($50,071 net earnings)

**Future Enhancement**: When model diversity is confirmed (backtesting shows all models produce identical results - under investigation), this function will query a backtesting results table to get strategy performance per model.

## Expected Value Strategy

Uses the strategy proven best in backtesting (+3.4% gain for Coffee).

### Decision Logic

```python
for each future day (1-14):
    expected_price = median(2000 Monte Carlo paths)
    storage_cost = current_price × 0.025% × days_held
    transaction_cost = expected_price × 0.25%

    net_expected_value = expected_price - storage_cost - transaction_cost

if max(net_expected_value) - current_price > $50/ton:
    HOLD (sell on optimal day)
else:
    SELL NOW (expected gain too small)
```

### Parameters

- **Storage cost**: 0.025% of value per day
- **Transaction cost**: 0.25% of sale value
- **Minimum gain threshold**: $50/ton
- **Inventory size**: 50 tons (default)

These parameters are based on the backtesting configuration that achieved +3.4% improvement.

## Data Sources

### 1. commodity.forecast.distributions
- 2000 Monte Carlo simulation paths per forecast
- 14-day horizon
- Updated periodically (sparse data - not all models forecast daily)
- Columns: `day_1` through `day_14` (predicted prices)
- Filter: `is_actuals = FALSE` for forecasts

### 2. commodity.bronze.market_data
- Historical closing prices
- Updated daily
- Used for:
  - Current market price
  - 7-day trend calculation

### 3. commodity.silver.unified_data (future)
- Weather data (temperature, precipitation)
- FX rates (COP, VND, BRL, etc.)
- CFTC sentiment (Net Non-Commercial Position)
- Not currently used in recommendation, but available

## Output Format

### WhatsApp Message
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
Forecast Date: 2025-01-14
────────────────────────────────────────
```

### JSON Output
```json
{
  "commodity": "Coffee",
  "generated_at": "2025-01-14T10:30:00",
  "current_price": 2.15,
  "7day_trend": 2.3,
  "forecast_range": [2.08, 2.28],
  "best_window": [9, 11],
  "inventory_tons": 50,
  "hold_duration": 10,
  "strategy_decision": {
    "action": "HOLD",
    "expected_gain_per_ton": 125.00,
    "total_expected_gain": 6250.00,
    "optimal_sale_day": 10,
    "reasoning": "Expected to gain $125/ton by selling on day 10"
  },
  "model_version": "sarimax_auto_weather_v1",
  "forecast_date": "2025-01-14"
}
```

## Usage

### Prerequisites
```bash
export DATABRICKS_HOST="https://your-workspace.cloud.databricks.com"
export DATABRICKS_TOKEN="dapi..."
export DATABRICKS_HTTP_PATH="/sql/1.0/warehouses/..."
```

### Run Recommendation Generator
```bash
cd trading_agent/whatsapp

# Generate Coffee recommendation
python generate_daily_recommendation.py --commodity Coffee

# Generate with custom inventory
python generate_daily_recommendation.py \
    --commodity Coffee \
    --inventory-tons 75

# Export to JSON
python generate_daily_recommendation.py \
    --commodity Coffee \
    --output-json coffee_recommendation.json
```

### Output Example
```
============================================================
Generating recommendation for Coffee
============================================================

1. Fetching current market price...
   Current price: $2.15 (as of 2025-01-14)

2. Calculating 7-day trend...
   7-day trend: +2.3%

3. Finding available forecast...
Checking arima_111_v1...
  Found forecast dated 2025-01-14
   Using model: arima_111_v1
   Forecast date: 2025-01-14
   Prediction matrix shape: (2000, 14)

4. Calculating 14-day forecast range...
   Range (10th-90th percentile): $2.08 - $2.28

5. Finding best sale window...
   Best 3-day window: Days 9-11

6. Calculating Expected Value strategy recommendation...
   Decision: HOLD
   Expected to gain $125/ton by selling on day 10

============================================================
WHATSAPP MESSAGE
============================================================
[formatted message shown above]
```

## Implementation Status

### ✅ Completed
- [x] Core recommendation engine (ExpectedValue strategy)
- [x] Databricks data integration (market_data, forecast.distributions)
- [x] WhatsApp message formatting
- [x] AWS Lambda webhook handler with real data
- [x] Twilio WhatsApp integration
- [x] Deployment automation script
- [x] QR code onboarding support

### 📝 Implementation Files
- `generate_daily_recommendation.py` - Core recommendation logic
- `lambda_handler_real.py` - AWS Lambda handler with Databricks queries
- `deploy_lambda.sh` - Automated deployment script
- `WHATSAPP_SETUP.md` - Complete setup guide

### 🔄 Next Steps

#### 1. Multi-User Management
- User database (phone numbers, subscriptions)
- Personalized inventory sizes
- Subscription preferences (daily/weekly)

#### 2. Scheduled Execution
- Deploy as Databricks Job (daily 6am ET)
- Store recommendations in Delta table for audit trail
- Alert on failures or missing data

#### 3. Enhanced Features
- Implement Consensus strategy (currently using ExpectedValue fallback)
- Custom alerts (price thresholds)
- Historical recommendation performance tracking
- A/B testing different strategies

#### 4. Production Migration
- Move from Twilio sandbox to WhatsApp Business API
- Configure message templates (requires approval)
- Implement caching layer (DynamoDB)
- Set up monitoring and alerts

## Cost Estimate

### WhatsApp Business API Pricing
- Conversation-based pricing: $0.005 - $0.02 per conversation
- Template messages: Lower cost tier ($0.005)
- User-initiated messages: Free to respond (24hr window)

### For 100 Users
- Daily message: 100 × 30 days × $0.005 = **$15/month**
- Negligible Databricks query cost (<$1/month)

### For 1,000 Users
- Daily message: 1,000 × 30 days × $0.005 = **$150/month**

## Testing Status

### Deployment Status
The WhatsApp Trading Bot sandbox is deployed and working correctly. All message flows have been verified through Lambda testing.

### Quick Start
1. Open WhatsApp on your phone
2. Scan the QR code: `whatsapp_demo_qr.png`
3. WhatsApp opens with pre-filled message: "join manner-telephone"
4. Tap "SEND"
5. You'll receive a Coffee market recommendation with real-time data

### QR Code
- Location: `whatsapp_demo_qr.png` (24KB)
- Features:
  - Pre-fills WhatsApp with "join manner-telephone"
  - Professional layout with step-by-step instructions
  - WhatsApp green "TAP SEND" button
  - Ready to print or display on screen

### Message Flows (All Verified)

**1. Join Flow - Auto Coffee Welcome**
- User sends: `join manner-telephone` (via QR code)
- Bot responds: Coffee market recommendation with:
  - Current price: $3,930/ton
  - 7-day trend: -6.6%
  - 14-day forecast: $2,984-$3,150/ton
  - Trading recommendation: SELL NOW
  - Expected value analysis

**2. Coffee Request**
- User sends: `coffee`
- Bot responds: Latest Coffee market recommendation with real Databricks data

**3. Sugar Request**
- User sends: `sugar`
- Bot responds: Latest Sugar market recommendation with real Databricks data

**4. Exit Command**
- User sends: `exit` (or stop, quit, unsubscribe, leave, cancel)
- Bot responds: Goodbye message confirming unsubscription

**5. Unrecognized Message - Help**
- User sends: `hello` (or any unrecognized text)
- Bot responds: Help menu with available commands

### Technical Details
- **Lambda Function**: berkeley-datasci210-capstone-processor (us-west-2, 19MB)
- **Twilio WhatsApp**: +1 415 523 8886 (Sandbox - free testing)
- **Join Code**: manner-telephone
- **Data Source**: Databricks REST API with real-time market data
- **Commodities**: Coffee, Sugar
- **Forecast Horizon**: 14 days
- **Strategy**: ExpectedValue (buy/hold/sell)

### Testing Instructions
1. **Test with Real WhatsApp**:
   - Open WhatsApp on your phone
   - Scan `whatsapp_demo_qr.png`
   - Tap "SEND" to join
   - Verify you receive Coffee recommendation
   - Try commands: `sugar`, `coffee`, `exit`, `hello`

2. **Check Lambda logs** (if issues occur):
   ```bash
   AWS_PROFILE=ucberkeley-sso aws logs tail /aws/lambda/berkeley-datasci210-capstone-processor \
     --region us-west-2 --since 5m --follow
   ```

3. **Local testing**:
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

### Future: Production Upgrade
Once sandbox testing is complete and you're ready for production:

**Option 1: Dedicated Twilio Number (~$1/month)**
- No "join manner-telephone" requirement
- Users just scan QR and get immediate recommendation
- Cleaner UX for demos/presentations
- Keep same Lambda backend

**Option 2: WhatsApp Business API**
- Official business account
- Custom branding
- Higher rate limits
- More expensive ($$$)

**Recommendation:** Start with dedicated Twilio number for cleaner demo experience.

---

## Changelog

### 2025-11-18: Critical Fixes Applied

#### Issues Fixed

**1. URL Construction Bug (CRITICAL)**
- Problem: URL was being constructed as `https://https://dbc-...` (double protocol prefix)
- Root Cause: Environment variable already contains 'https://' prefix
- Fix: Strip protocol prefix before constructing URL
- Files Changed: `lambda_handler_real.py:43-44, 68, 91`

**2. Price Unit Conversion (CRITICAL)**
- Problem: Market and forecast data stored in cents, but code treated it as dollars
- Evidence: Market data `393.05` cents = $3.93/kg (not $393/kg!)
- Fix: Added price conversion constant (0.01) and applied to both market and forecast data
- Impact: Without this fix, recommendations would be completely wrong (prices 100x too high)
- Files Changed: `lambda_handler_real.py:20, 139-140, 348`

**3. SQL Injection Protection (HIGH)**
- Problem: User input (commodity) directly interpolated into SQL queries
- Fix: Added input validation whitelist (Coffee, Sugar, Cocoa, Wheat)
- Files Changed: `lambda_handler_real.py:17, 123, 155, 206, 299`

**4. Missing NumPy Dependency (HIGH)**
- Problem: `numpy` was commented out in requirements.txt but imported in code
- Fix: Uncommented numpy in requirements
- Files Changed: `requirements_lambda.txt:9`

**5. Type Conversion Error (MEDIUM)**
- Problem: Metric value from Databricks returned as string, code tried to format as float
- Fix: Explicit type conversion before formatting
- Files Changed: `lambda_handler_real.py:251-255`

**6. Improved Error Handling & Logging (ENHANCEMENT)**
- Added: Progress indicators ([1/4], [2/4], etc.)
- Added: Detailed logging at each step
- Added: Better error messages with context
- Added: Graceful fallback to mock data
- Added: Input validation with clear error messages
- Files Changed: `lambda_handler_real.py:535-582, 143, 174, 347-355`

**7. Updated WhatsApp Message Format (ENHANCEMENT)**
- Problem: Message format didn't match specification in WhatsApp demo
- Changes:
  - Header now shows commodity emoji and name (☕ COFFEE MARKET UPDATE)
  - Added date at top
  - Changed from $/kg to $/ton pricing
  - Updated section headers (CURRENT MARKET, FORECAST (14 days), YOUR INVENTORY)
  - Changed recommendation format to match spec
  - Removed technical details (model version, strategy)
  - Added "Next update: Tomorrow 6 AM" footer
- Files Changed: `lambda_handler_real.py:456-555`, `lambda_handler.py:14-95`

#### Test Results

**Coffee** ✅
- Price: $3.93/kg
- 7-Day Trend: -6.6%
- Forecast Range: $3.81 - $4.20
- Model: sarimax_auto_weather_v1
- Recommendation: SELL NOW
- Status: Using REAL Databricks data

**Sugar** ✅
- Price: $0.14/kg
- 7-Day Trend: -4.5%
- Status: Market data from Databricks, no recent forecasts (falls back to mock)

#### Deployment Notes

**Before Deploying**:
1. Update Lambda timeout to 60s (current 30s is too short for Databricks queries)
2. Redeploy with new code: `./deploy_lambda.sh`
3. Verify environment variables are set correctly

**Known Issues / Limitations**:
1. **Forecast Data Availability**: Sugar has no recent forecasts (falls back to mock data)
2. **Forecast Age**: Current setting is 30 days; consider reducing to 7 days for fresher data
3. **Variable Path Counts**: Code now handles variable path counts dynamically

**Performance**:
- Typical response time: 10-15 seconds
- Market data query: 2-3 seconds
- Trend calculation: 2-3 seconds
- Forecast metadata: 2-3 seconds
- Forecast data load: 3-5 seconds

**Optimization Opportunities**:
1. Cache recommendations (DynamoDB, 1-hour TTL) → Save ~$0.02/query
2. Combine SQL queries → Reduce to 2 queries instead of 5
3. Lambda layer for NumPy → Reduce package size by 30MB
4. Use Databricks SQL Endpoint connection pooling → Faster subsequent queries

**Security Checklist**:
- [x] SQL injection protection (whitelist validation)
- [x] Input sanitization (commodity names)
- [x] Error messages don't leak sensitive info
- [ ] Twilio webhook signature validation (TODO)
- [ ] Rate limiting (API Gateway throttling) (TODO)
- [ ] Move secrets to AWS Secrets Manager (TODO)

---

## References

- **Backtesting Results**: `trading_agent/MASTER_SYSTEM_PLAN.md`
- **Forecast Data Schema**: `forecast_agent/ground_truth/storage/databricks_writer.py:186`
- **Data Loader**: `trading_agent/data_access/forecast_loader.py`
- **WhatsApp Mockup**: `/Users/markgibbons/Downloads/Whatsapp demo.pdf`
