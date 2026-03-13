# P2: Add BRL/USD Forex Data via Lambda

**Priority**: P2 (Important but not blocking current work)
**Impact**: HIGH - Brazil produces 40% of global coffee
**Effort**: 2-3 hours
**Status**: Planned

---

## Why This Matters

### Current Gap:
- **24 forex pairs available** in unified_data
- **7/8 top coffee producers** covered (60% of production)
- **❌ BRL/USD missing** = 40% of production not represented!

### Business Impact:
When Brazilian Real (BRL) weakens:
- Brazilian coffee exports become cheaper
- Global coffee prices tend to drop
- Colombian/Vietnamese producers become less competitive

**Example:** BRL depreciation in 2020-2021 partially offset the July 2021 frost price spike by making Brazilian coffee more competitive.

---

## Implementation Plan

### Option 1: Extend Existing Forex Lambda (Recommended)

**Current Setup:**
- Lambdas already fetch 24 forex pairs
- Source likely: Alpha Vantage, OpenExchangeRates, or ECB API
- Data flows: Lambda → S3 → Databricks bronze.macro → silver.unified_data

**Tasks:**
1. **Identify forex lambda** (`grep -r "forex\|exchange" ../research_agent/lambdas/`)
2. **Add BRL to forex pair list** (1 line change: `'BRL': 'USD'`)
3. **Redeploy lambda** (`aws lambda update-function-code`)
4. **Backfill historical BRL/USD** (2015-2025, ~3,800 days)
5. **Update unified_data** to include brl_usd column
6. **Update TFT models** to use brl_usd in feature list

**Estimated Time:** 2-3 hours

---

### Option 2: Quick Fix - Fetch from Free API

If lambda approach is complex, quick alternative:

```python
# Quick BRL/USD backfill using exchangerate-api.com (free tier)
import requests
import pandas as pd
from datetime import datetime, timedelta

def fetch_brl_usd_history():
    """Fetch BRL/USD from 2015-2025 using free API."""
    # Free API: https://exchangerate-api.com or https://fixer.io

    base_url = "https://api.exchangerate-api.com/v4/history/USD"
    dates = pd.date_range('2015-01-01', '2025-11-12', freq='D')

    brl_rates = []
    for date in dates:
        response = requests.get(f"{base_url}/{date.strftime('%Y/%m/%d')}")
        data = response.json()
        brl_rates.append({
            'date': date,
            'brl_usd': data['rates']['BRL']
        })

    return pd.DataFrame(brl_rates)

# Load to Databricks
df = fetch_brl_usd_history()
# Write to commodity.bronze.macro or create new table
```

**Estimated Time:** 1 hour

---

## Alternative Data Sources

### Free APIs (5,000+ requests/month):
1. **ExchangeRate-API** (https://exchangerate-api.com) - FREE, no key required
2. **Fixer.io** (free tier) - Historical data available
3. **Open Exchange Rates** (1,000 requests/month free)

### Premium APIs (if budget available):
1. **Alpha Vantage** - $50/month, reliable
2. **Polygon.io** - Real-time forex
3. **ECB API** - European Central Bank, free but limited pairs

---

## Integration Steps

### Step 1: Identify Current Forex Source

```bash
# Find forex lambda
cd ../research_agent/lambdas
grep -r "forex\|exchange\|currency" .

# Check existing forex table
DATABRICKS_HOST="..." python -c "
from databricks import sql
cursor = connection.cursor()
cursor.execute('SELECT * FROM commodity.bronze.macro WHERE currency_pair LIKE \'%USD\' LIMIT 1')
print(cursor.fetchall())
"
```

### Step 2: Add BRL to Lambda

```python
# In forex lambda (likely forex-data-fetcher or similar)
FOREX_PAIRS = [
    'COP_USD', 'VND_USD', 'IDR_USD', 'ETB_USD',
    'HNL_USD', 'UGX_USD', 'PEN_USD',
    'BRL_USD',  # ← ADD THIS LINE
    # ... other 17 pairs
]
```

### Step 3: Backfill Historical Data

```python
# Run backfill for 2015-2025 (one-time)
python backfill_brl_usd.py --start-date 2015-01-01 --end-date 2025-11-12
```

### Step 4: Update unified_data SQL

```sql
-- In research_agent/sql/create_unified_data.sql
-- Add to forex section:
LEFT JOIN (
    SELECT date, close as brl_usd
    FROM commodity.bronze.macro
    WHERE currency_pair = 'BRL_USD'
) brl ON unified.date = brl.date
```

### Step 5: Update TFT Models

```python
# In forecast_agent/ground_truth/config/model_registry.py
# Update tft_full and tft_forex to include 'brl_usd'
'exog_features': [
    'cop_usd', 'vnd_usd', 'idr_usd', 'brl_usd',  # ← Add here
    # ... rest of features
]
```

---

## Expected Impact

### Model Performance:
- **Baseline (no BRL)**: TFT learns from 7/8 producers (60% coverage)
- **With BRL**: TFT learns from 8/8 producers (100% coverage)
- **Expected MAE improvement**: 5-15% (BRL is highly correlated with coffee prices)

### Attention Weights:
After adding BRL, check TFT attention to see:
- Does model learn BRL is most important forex?
- How does BRL relate to temperature shocks (e.g., July 2021 frost)?
- Leading/lagging relationship with coffee prices

---

## Testing Strategy

### Before/After Comparison:
1. **Train TFT without BRL** (current state)
2. **Add BRL data**
3. **Train TFT with BRL**
4. **Compare MAE on July 2021 frost event**
   - Hypothesis: Model with BRL should better predict post-frost prices

### Key Dates to Validate:
- **July 2021 frost**: Price spike + BRL depreciation
- **2020 COVID crash**: BRL crashed → Coffee prices volatile
- **2015-2016 BRL crisis**: BRL lost 50% → Coffee exports surged

---

## Next Steps (P2 - After Current Backfill)

1. **Find forex lambda** in research_agent codebase
2. **Add BRL to pair list**
3. **Backfill 2015-2025** (~3,800 daily values)
4. **Update unified_data** SQL and rebuild
5. **Update TFT models** to include brl_usd
6. **Re-backfill TFT forecasts** (quarterly or semiannually)
7. **Compare performance** vs non-BRL version

---

## Files to Modify

1. `research_agent/lambdas/*/forex_fetcher.py` (or similar) - Add BRL
2. `research_agent/sql/create_unified_data.sql` - Add brl_usd column
3. `forecast_agent/ground_truth/config/model_registry.py` - Update TFT features
4. Create `research_agent/infrastructure/backfill_brl_usd.py` - One-time backfill

---

## Priority Justification

**Why P2 (not P1)?**
- Current models work without BRL (7/8 producers = 60% coverage)
- Naive backfill is running, want to complete baseline first
- TFT implementation is ready to use as-is

**Why not P3?**
- BRL represents 40% of production (largest gap)
- Strong economic theory: BRL movements → coffee price changes
- Relatively easy to implement (2-3 hours)

**When to do it:**
- After naive backfill completes
- After TFT quick test validates model works
- Before full TFT backfill with all features

---

## Cost Estimate

- **Free API option**: $0
- **Lambda compute**: ~$0.01 (one-time backfill)
- **S3 storage**: ~$0.001/month (3,800 records)
- **Databricks compute**: ~$0.10 (rebuild unified_data)

**Total**: < $1

---

## Success Criteria

✅ BRL/USD data available in unified_data (2015-2025)
✅ TFT models can use brl_usd as feature
✅ Attention weights show BRL importance
✅ MAE improves by 5-15% on validation set
✅ July 2021 frost predictions improve

---

**Status**: Ready to implement after naive backfill completes
**Owner**: TBD
**ETA**: 2-3 hours once prioritized
