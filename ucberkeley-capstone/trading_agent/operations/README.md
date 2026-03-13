# Operations Module - Daily Trading Recommendations

This module provides operational tools for generating daily trading recommendations using the latest forecasts.

---

## Quick Start

### Single Model
```bash
cd trading_agent
source ../venv/bin/activate
python operations/daily_recommendations.py --commodity coffee --model sarimax_auto_weather_v1
```

### All Models
```bash
python operations/daily_recommendations.py --commodity coffee --all-models
```

---

## What It Does

1. **Queries Unity Catalog** for the latest prediction
   - Finds most recent `forecast_start_date` for specified model
   - Loads prediction matrix (2000 paths × 14 days)

2. **Loads Current State**
   - Inventory level (placeholder: 35.5 tons)
   - Days since harvest (placeholder: 45 days)
   - Current price (from `commodity.prices.daily`)
   - Price history (last 100 days)

3. **Generates Recommendations** for all 9 strategies:
   - **Baselines (4):** ImmediateSale, EqualBatch, PriceThreshold, MovingAverage
   - **Prediction-based (5):** Consensus, ExpectedValue, RiskAdjusted, PriceThresholdPredictive, MovingAveragePredictive

4. **Displays Actionable Guidance**
   - SELL or HOLD for each strategy
   - Quantity to sell (in tons)
   - Reasoning behind decision
   - Summary statistics

---

## Example Output

```
================================================================================
DAILY TRADING RECOMMENDATIONS
================================================================================
Date: 2025-11-10 14:30:15
Commodity: COFFEE
================================================================================

Connecting to Databricks...
✓ Connected

Loading current state...
✓ Current state loaded
  Inventory: 35.5 tons
  Current Price: $105.50
  Days Since Harvest: 45

Processing model: sarimax_auto_weather_v1

================================================================================
MODEL: sarimax_auto_weather_v1
================================================================================
Latest Prediction:
  Forecast Date: 2025-11-10
  Generated: 2025-11-10 06:00:00
  Simulation Paths: 2000
  Forecast Horizon: 14 days

Recommendations:
Strategy                   Action  Quantity (tons)  Reasoning                         Uses Predictions
Immediate Sale             SELL    8.9              sale_frequency_reached           No
Equal Batches              SELL    12.5             scheduled_batch_sale             No
Price Threshold            SELL    8.9              price_5.2%_above_threshold       No
Moving Average             HOLD    0.0              price_below_30d_ma               No
Consensus                  HOLD    0.0              strong_consensus_72%_conf8%      Yes
Expected Value             SELL    12.5             ev_peaks_day_3_net_benefit_125   Yes
Risk-Adjusted              HOLD    0.0              high_confidence_low_uncertainty  Yes
Price Threshold Predictive SELL    8.9              both_indicators_suggest_sell     Yes
Moving Average Predictive  HOLD    0.0              ma+prediction_both_hold          Yes

📊 Summary: 5/9 strategies recommend SELL
   Total recommended: 50.7 tons (142.8% of inventory)

================================================================================
RECOMMENDATIONS COMPLETE
================================================================================
```

---

## Command-Line Options

| Option | Description | Example |
|--------|-------------|---------|
| `--commodity` | Commodity to analyze (required) | `--commodity coffee` |
| `--model` | Specific model to use | `--model sarimax_auto_weather_v1` |
| `--all-models` | Process all available models | `--all-models` |
| `--output-json` | Save structured data as JSON file | `--output-json recommendations.json` |

**Note:** Must specify either `--model` or `--all-models`

---

## How It Works

### 1. Strategy Decision Logic

Each strategy has a `decide()` method:

```python
def decide(self, day, inventory, current_price, price_history, predictions=None):
    """
    Make trading decision for current day.

    Returns:
        {'action': 'SELL' | 'HOLD',
         'amount': float (tons),
         'reason': str}
    """
```

**Baseline strategies** (don't use predictions):
- Check price thresholds, moving averages, scheduled sales
- Make decisions based on current price and history

**Prediction-based strategies** (use predictions):
- Analyze prediction matrix (2000 paths × 14 days)
- Calculate consensus, expected value, risk metrics
- Incorporate predictions into decision logic

### 2. Latest Prediction Query

```python
def get_latest_prediction(commodity, model_version, connection):
    # Query: SELECT MAX(forecast_start_date) WHERE ...
    # Returns: prediction_matrix (np.ndarray), forecast_date, generation_timestamp
```

Queries Unity Catalog for the most recent prediction available for the specified model.

### 3. Current State Loading

```python
def get_current_state(commodity, connection):
    # Returns: {inventory, days_since_harvest, current_price, price_history}
```

**Current implementation:** Uses placeholders for inventory and days_since_harvest

**Production TODO:** Integrate with actual inventory management system

### 4. Recommendation Generation

```python
# For each strategy:
decision = strategy.decide(
    day=days_since_harvest,
    inventory=current_inventory,
    current_price=price,
    price_history=history_df,
    predictions=prediction_matrix  # Only for prediction-based strategies
)
```

---

## Integration Points

### TODO: Inventory System Integration

Replace placeholder values in `get_current_state()`:

```python
def get_current_state(commodity, connection):
    # Current: Placeholder
    inventory = 35.5
    days_since_harvest = 45

    # TODO: Query actual inventory system
    # inventory = query_inventory_db(commodity)
    # days_since_harvest = calculate_from_harvest_date(commodity)

    return {...}
```

### TODO: Price Data Source

Currently queries `commodity.prices.daily` table. Verify this is the correct source.

```python
cursor.execute("""
    SELECT date, price
    FROM commodity.prices.daily
    WHERE commodity = %s
    ORDER BY date DESC
    LIMIT 100
""", (commodity.capitalize(),))
```

---

## Deployment Options

### Option 1: Databricks Job (Recommended)

Schedule as daily job in Databricks:

```python
# Databricks job configuration
{
    "name": "Daily Coffee Recommendations",
    "job_clusters": [...],
    "python_wheel_task": {
        "package_name": "trading_agent",
        "entry_point": "daily_recommendations",
        "parameters": ["--commodity", "coffee", "--all-models"]
    },
    "schedule": {
        "quartz_cron_expression": "0 0 7 * * ?",  # 7 AM daily
        "timezone_id": "America/New_York"
    }
}
```

### Option 2: Command-Line (Ad-hoc)

Run manually when needed:

```bash
python operations/daily_recommendations.py --commodity coffee --model sarimax_auto_weather_v1
```

### Option 3: API Endpoint

Wrap in Flask/FastAPI for web service:

```python
@app.get("/recommendations/{commodity}/{model}")
def get_recommendations(commodity: str, model: str):
    # Call daily_recommendations logic
    # Return JSON
```

---

## Output Interpretation

### Action Types

| Action | Meaning | Typical Quantity |
|--------|---------|------------------|
| `SELL` | Sell inventory today | 5-50% of inventory |
| `HOLD` | Do not sell, wait | 0 tons |

### Reasoning Codes

Common reason strings returned by strategies:

**Baseline reasons:**
- `sale_frequency_reached` - Time for scheduled sale
- `price_X%_above_threshold` - Price exceeds threshold
- `price_below_ma` - Price below moving average
- `no_inventory` - No inventory to sell

**Prediction-based reasons:**
- `strong_consensus_72%_conf8%` - 72% of paths predict increase, 8% uncertainty
- `ev_peaks_day_3_net_benefit_125` - Expected value peaks on day 3, $125 benefit
- `weak_consensus_55%_or_high_unc15%` - Low consensus or high uncertainty
- `bearish_consensus_38%_ret-2%` - 38% bullish (bearish signal)
- `both_indicators_suggest_sell` - Multiple indicators agree

### Confidence Indicators

Higher numbers indicate stronger signal:
- Consensus %: 70%+ is strong, 50-60% is weak
- Uncertainty: <5% is low, >15% is high
- Net benefit: >$100 is significant

---

## JSON Output Format

When using `--output-json`, the script generates structured data suitable for messaging services (WhatsApp, SMS, etc.).

### Example Usage

```bash
python operations/daily_recommendations.py \
  --commodity coffee \
  --model sarimax_auto_weather_v1 \
  --output-json recommendations.json
```

### Output Structure

```json
{
  "generated_at": "2025-11-10T14:30:15.123456",
  "commodity": "coffee",
  "models_processed": 1,
  "recommendations": [
    {
      "timestamp": "2025-11-10T14:30:15.123456",
      "commodity": "coffee",
      "model": {
        "name": "sarimax_auto_weather_v1",
        "forecast_date": "2025-11-10",
        "generation_timestamp": "2025-11-10 06:00:00",
        "simulation_paths": 2000,
        "forecast_horizon_days": 14
      },
      "market": {
        "current_price_usd": 105.50,
        "trend_7d_pct": 3.2,
        "trend_direction": "↑",
        "exchange_rates": {
          "COP/USD": 3876.50,
          "VND/USD": 23450.00,
          "BRL/USD": 5.12,
          "INR/USD": 83.25,
          "THB/USD": 34.80,
          "IDR/USD": 15678.00,
          "ETB/USD": 56.50,
          "...": "..."
        },
        "local_prices": {
          "COP": 408967.50,
          "VND": 2473975.00,
          "BRL": 539.76,
          "INR": 8783.87,
          "THB": 3671.40,
          "IDR": 1654026.00,
          "ETB": 5960.75,
          "...": "..."
        }
      },
      "forecast": {
        "horizon_days": 14,
        "price_range_usd": {
          "min": 98.20,
          "max": 112.80,
          "median": 106.40
        },
        "best_window": {
          "days": [8, 9, 10],
          "expected_price_usd": 109.50
        },
        "daily_forecast": {
          "day_1": {"median": 105.80, "p25": 103.20, "p75": 108.40},
          "day_2": {"median": 106.10, "p25": 103.50, "p75": 108.90}
        }
      },
      "inventory": {
        "stock_tons": 35.5,
        "days_held": 45
      },
      "recommendation": {
        "action": "HOLD",
        "quantity_tons": 0.0,
        "confidence": {
          "strategies_agreeing": 4,
          "total_strategies": 5
        },
        "financial_impact": {
          "usd": {
            "sell_now_value": 3745.25,
            "wait_value": 3887.25,
            "potential_gain": 142.00,
            "potential_gain_pct": 3.79
          },
          "local_currency": {
            "sell_now_value": {
              "COP": 14516593.75,
              "VND": 87825612.50,
              "BRL": 19175.68,
              "INR": 311858.56,
              "...": "..."
            },
            "wait_value": {
              "COP": 15067043.75,
              "VND": 91146062.50,
              "BRL": 19901.28,
              "INR": 323594.06,
              "...": "..."
            },
            "potential_gain": {
              "COP": 550450.00,
              "VND": 3320450.00,
              "BRL": 725.60,
              "INR": 11735.50,
              "...": "..."
            }
          }
        }
      },
      "all_strategies": [...]
    }
  ]
}
```

### Currency Support

The system automatically fetches **all available exchange rates** from `commodity.bronze.fx_rates`, including:

**Major commodity producers:**
- **COP** (Colombian Peso) - Coffee
- **VND** (Vietnamese Dong) - Coffee
- **BRL** (Brazilian Real) - Coffee, Sugar
- **INR** (Indian Rupee) - Sugar
- **THB** (Thai Baht) - Sugar
- **IDR** (Indonesian Rupiah) - Coffee
- **ETB** (Ethiopian Birr) - Coffee
- **HNL** (Honduran Lempira) - Coffee
- **UGX** (Ugandan Shilling) - Coffee
- **MXN** (Mexican Peso) - Coffee
- And many more...

**Major economies:**
- EUR, GBP, JPY, CNY, AUD, CHF, KRW, ZAR

All prices and financial impact are automatically calculated in all available currencies.

### WhatsApp Integration

This JSON format is designed for messaging services to send personalized recommendations to commodity producers.

#### Step-by-Step Implementation Guide

**1. Generate the daily recommendations:**
```bash
python operations/daily_recommendations.py \
  --commodity coffee \
  --model sarimax_auto_weather_v1 \
  --output-json recommendations.json
```

**2. In your messaging service, load the JSON:**
```python
import json

with open('recommendations.json', 'r') as f:
    data = json.load(f)

# Get the first model's recommendations
rec = data['recommendations'][0]
```

**3. Look up the user's region and determine their currency:**

The JSON contains all available currencies. Your messaging service should:
- Store user profile with their region (e.g., "Antioquia, Colombia")
- Map region to currency code (e.g., Colombia → COP)
- Extract the appropriate currency from the JSON

```python
# Example user profile lookup
user = get_user_profile(phone_number)  # Your user database
region = user['region']  # e.g., "Antioquia, Colombia"

# Map region to currency
REGION_TO_CURRENCY = {
    'Colombia': 'COP',
    'Vietnam': 'VND',
    'Brazil': 'BRL',
    'India': 'INR',
    'Thailand': 'THB',
    'Indonesia': 'IDR',
    'Ethiopia': 'ETB',
    'Honduras': 'HNL',
    'Uganda': 'UGX',
    'Mexico': 'MXN',
    # ... add more as needed
}

currency = REGION_TO_CURRENCY.get(user['country'], 'USD')
```

**4. Extract prices in the user's local currency:**

```python
# Check if the currency is available in the data
if currency in rec['market']['local_prices']:
    current_price_local = rec['market']['local_prices'][currency]
    exchange_rate = rec['market']['exchange_rates'][f'{currency}/USD']

    # Get financial impact in local currency
    sell_now = rec['recommendation']['financial_impact']['local_currency']['sell_now_value'][currency]
    wait_value = rec['recommendation']['financial_impact']['local_currency']['wait_value'][currency]
    potential_gain = rec['recommendation']['financial_impact']['local_currency']['potential_gain'][currency]
else:
    # Fallback to USD if currency not available
    current_price_local = rec['market']['current_price_usd']
    currency = 'USD'
    sell_now = rec['recommendation']['financial_impact']['usd']['sell_now_value']
    wait_value = rec['recommendation']['financial_impact']['usd']['wait_value']
    potential_gain = rec['recommendation']['financial_impact']['usd']['potential_gain']
```

**5. Format values with appropriate number formatting:**

```python
# Format numbers for readability
def format_currency(amount, currency):
    """Format currency based on typical conventions."""
    if currency == 'COP':
        # Colombian Peso: usually shown without decimals
        return f"{amount:,.0f}"
    elif currency == 'VND':
        # Vietnamese Dong: usually shown without decimals
        return f"{amount:,.0f}"
    elif currency == 'USD':
        # USD: show 2 decimals
        return f"{amount:,.2f}"
    else:
        # Default: 2 decimals
        return f"{amount:,.2f}"

# Example usage
current_price_formatted = format_currency(current_price_local, currency)
sell_now_formatted = format_currency(sell_now, currency)
wait_formatted = format_currency(wait_value, currency)
gain_formatted = format_currency(potential_gain, currency)
```

**6. Construct the WhatsApp message:**

```python
# Extract data from JSON
action = rec['recommendation']['action']
trend_pct = rec['market']['trend_7d_pct']
trend_dir = rec['market']['trend_direction']
best_window = rec['forecast']['best_window']['days']
stock = rec['inventory']['stock_tons']
days_held = rec['inventory']['days_held']
gain_pct = rec['recommendation']['financial_impact']['usd']['potential_gain_pct']

# Currency symbol lookup
CURRENCY_SYMBOLS = {
    'USD': '$', 'COP': '$', 'BRL': 'R$', 'EUR': '€',
    'GBP': '£', 'JPY': '¥', 'INR': '₹', 'MXN': '$',
    'VND': '₫', 'THB': '฿', 'IDR': 'Rp'
}
symbol = CURRENCY_SYMBOLS.get(currency, currency)

# Build the message
message = f"""━━━━━━━━━━━━━━━━━━━━━━
🌱 COFFEE MARKET UPDATE
━━━━━━━━━━━━━━━━━━━━━━
📅 {rec['timestamp'][:10]}
📍 Your Region: {user['region']}

CURRENT MARKET
💵 Today: {symbol}{current_price_formatted}/ton
📊 7-day trend: {trend_dir} {trend_pct:+.1f}%

FORECAST (14 days)
🔮 Expected: {symbol}{format_currency(rec['forecast']['price_range_usd']['min'] * exchange_rate, currency)}-{format_currency(rec['forecast']['price_range_usd']['max'] * exchange_rate, currency)}/ton
🎯 Best sale window: Days {best_window[0]}-{best_window[-1]}

YOUR INVENTORY
📦 Stock: {stock:.1f} tons
⏰ Held: {days_held} days

━━━━━━━━━━━━━━━━━━━━━━
🎯 RECOMMENDATION
━━━━━━━━━━━━━━━━━━━━━━
{'✅ HOLD' if action == 'HOLD' else '💰 SELL'} - Wait for better prices

Wait for forecast window: {symbol}{wait_formatted}
Sell today: {symbol}{sell_now_formatted}
Potential gain: {symbol}{gain_formatted} ({gain_pct:+.1f}%)

Next update: Tomorrow 6 AM
"""
```

**7. Send via WhatsApp API:**

```python
# Using Twilio
from twilio.rest import Client

client = Client(account_sid, auth_token)
message = client.messages.create(
    body=message,
    from_='whatsapp:+14155238886',  # Twilio sandbox or your number
    to=f'whatsapp:{user["phone_number"]}'
)

# Or using MessageBird, Vonage, etc.
```

#### Key Data Mapping Reference

| WhatsApp Field | JSON Path |
|----------------|-----------|
| Current price (local) | `market.local_prices[CURRENCY]` |
| 7-day trend | `market.trend_7d_pct` |
| Trend direction | `market.trend_direction` |
| Forecast range (local) | `forecast.price_range_usd.min/max` × `exchange_rates[CURRENCY/USD]` |
| Best window days | `forecast.best_window.days` |
| Stock (tons) | `inventory.stock_tons` |
| Days held | `inventory.days_held` |
| Action (HOLD/SELL) | `recommendation.action` |
| Sell now value (local) | `recommendation.financial_impact.local_currency.sell_now_value[CURRENCY]` |
| Wait value (local) | `recommendation.financial_impact.local_currency.wait_value[CURRENCY]` |
| Potential gain (local) | `recommendation.financial_impact.local_currency.potential_gain[CURRENCY]` |
| Potential gain % | `recommendation.financial_impact.usd.potential_gain_pct` |
| User region | User profile (not in JSON - your database) |

#### Complete Example

```python
def send_coffee_recommendation(phone_number, recommendations_file):
    """
    Send personalized WhatsApp recommendation to a farmer.

    Args:
        phone_number: User's WhatsApp number
        recommendations_file: Path to recommendations.json
    """
    # Load recommendations
    with open(recommendations_file) as f:
        data = json.load(f)
    rec = data['recommendations'][0]

    # Get user profile
    user = get_user_profile(phone_number)
    currency = get_user_currency(user['country'])

    # Check if currency available, fallback to USD
    if currency not in rec['market']['local_prices']:
        currency = 'USD'
        exchange_rate = 1.0
    else:
        exchange_rate = rec['market']['exchange_rates'][f'{currency}/USD']

    # Extract and format values
    if currency == 'USD':
        current_price = rec['market']['current_price_usd']
        sell_now = rec['recommendation']['financial_impact']['usd']['sell_now_value']
        wait_val = rec['recommendation']['financial_impact']['usd']['wait_value']
        gain = rec['recommendation']['financial_impact']['usd']['potential_gain']
    else:
        current_price = rec['market']['local_prices'][currency]
        sell_now = rec['recommendation']['financial_impact']['local_currency']['sell_now_value'][currency]
        wait_val = rec['recommendation']['financial_impact']['local_currency']['wait_value'][currency]
        gain = rec['recommendation']['financial_impact']['local_currency']['potential_gain'][currency]

    # Build message (see template above)
    message = build_whatsapp_message(rec, user, currency, ...)

    # Send
    send_whatsapp(phone_number, message)
```

#### Important Notes

1. **Currency Availability**: Always check if the user's currency exists in `local_prices` before accessing it. Fallback to USD if not available.

2. **Region Storage**: The JSON does NOT include user region - this must come from your user profile database.

3. **Exchange Rate Updates**: Exchange rates are pulled fresh from Databricks each time the script runs, ensuring up-to-date conversions.

4. **Number Formatting**: Different currencies have different conventions (e.g., VND and COP typically don't show decimals).

5. **Forecast Values**: Forecast prices are in USD by default. To convert to local currency, multiply by the exchange rate: `forecast_price_usd × exchange_rate`

6. **Percentage Gain**: `potential_gain_pct` is the same in all currencies (it's a ratio), so use the USD value.

---

## Use Cases

### 1. Daily Decision Support

**When:** New forecast becomes available (typically morning)

**Workflow:**
1. Run script with `--all-models`
2. Review recommendations across models
3. Check for consensus (multiple strategies agree)
4. Make informed trading decision

### 2. Model Comparison

**When:** Evaluating which model to trust

**Workflow:**
1. Run for multiple models
2. Compare recommendations
3. Identify which models are most aggressive/conservative
4. Cross-reference with backtest performance

### 3. Strategy Validation

**When:** Testing if strategies work as expected

**Workflow:**
1. Run with current live data
2. Compare baseline vs prediction-based
3. Verify matched pairs behave correctly
4. Validate reasoning aligns with strategy logic

### 4. Operational Monitoring

**When:** Regular health check

**Workflow:**
1. Schedule daily runs
2. Log recommendations
3. Track actual decisions vs recommendations
4. Measure strategy accuracy over time

---

## Troubleshooting

### No predictions found

```
Error: No predictions found for coffee - sarimax_auto_weather_v1
```

**Solution:** Check that predictions exist in Unity Catalog
```sql
SELECT MAX(forecast_start_date), COUNT(*)
FROM commodity.forecast.distributions
WHERE commodity = 'Coffee' AND model_version = 'sarimax_auto_weather_v1'
```

### No price data found

```
⚠️  No price data found, using mock data
```

**Solution:** Verify `commodity.prices.daily` table exists and is populated

### Strategy errors

```
Strategy: Consensus | Action: ERROR | Reasoning: 'NoneType' object has no attribute 'shape'
```

**Solution:** Check that prediction matrix is valid numpy array with shape (n_paths, 14)

---

## Future Enhancements

### 1. Inventory State Persistence

Store state between runs to track actual inventory:

```python
# Save state after each run
state_tracker.save(commodity, date, {
    'inventory': inventory_after_sales,
    'sales_made': total_sold,
    'days_since_harvest': days + 1
})

# Load state at next run
state = state_tracker.load(commodity)
```

### 2. Recommendation History

Track recommendations over time:

```python
# Log each recommendation
recommendation_log.append({
    'date': today,
    'model': model,
    'strategy': strategy_name,
    'recommendation': decision,
    'actual_action': actual_action_taken
})

# Analyze accuracy
accuracy = compare_recommendations_vs_actuals(log)
```

### 3. Consensus Aggregation

Aggregate recommendations across models:

```python
# Find consensus across all models
consensus = aggregate_recommendations(all_model_recommendations)

print("🎯 CONSENSUS RECOMMENDATION:")
print(f"   Action: {consensus['action']}")
print(f"   Confidence: {consensus['agreement_pct']}%")
print(f"   Models agreeing: {consensus['n_models']}/{total_models}")
```

### 4. Email/Slack Notifications

Send daily reports:

```python
# Format as email
email = format_recommendations_email(recommendations)
send_email(to="trader@company.com", subject="Daily Recommendations", body=email)

# Or Slack
slack_message = format_recommendations_slack(recommendations)
send_slack(channel="#trading", message=slack_message)
```

---

## Related Documentation

- **Backtest Analysis:** `../production/runners/multi_commodity_runner.py`
- **Multi-Model Analysis:** `../docs/MULTI_MODEL_ANALYSIS.md`
- **Strategy Implementations:** `../production/strategies/`
- **Data Access:** `../data_access/forecast_loader.py`
