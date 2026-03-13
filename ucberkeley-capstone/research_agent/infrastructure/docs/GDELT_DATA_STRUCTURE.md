# GDELT Data Structure Reference

**Last Updated**: 2025-11-24

This document explains the structure of GDELT news data in our Databricks tables.

---

## Table Locations

| Layer | Table | Description |
|-------|-------|-------------|
| Bronze | `commodity.bronze.gdelt` | Raw GDELT data (narrow format) |
| Silver | `commodity.silver.gdelt_wide` | Aggregated wide format (sparse, trading days only) |
| **Silver** | **`commodity.silver.gdelt_wide_fillforward`** | **Continuous daily data (recommended for forecasting)** |

---

## Schema Overview

**Grain**: `(article_date, commodity)`
- **article_date**: Date of news articles
- **commodity**: `coffee` or `sugar`

**Total Columns**: 114 (2 metadata + 112 data columns)

---

## Column Categories

### 1. Metadata Columns (2)
- `article_date` - Date (YYYY-MM-DD)
- `commodity` - String (coffee | sugar)

### 2. Count Columns (22)
Article counts by category/theme. **Set to 0 for missing dates** in fillforward table.

#### Group Counts (8 columns)
Organizational categories for news classification:

- `group_ALL_count` - **Total articles** (all categories combined)
- `group_CORE_count` - Core commodity market news
- `group_LOGISTICS_count` - Supply chain, transportation, storage
- `group_MARKET_count` - Trading, prices, futures markets
- `group_OTHER_count` - Miscellaneous/uncategorized
- `group_POLICY_count` - Government policy, regulations, tariffs
- `group_SUPPLY_count` - Production, harvest, weather impacts
- `group_TRADE_count` - Import/export, international trade

#### Theme Counts (14 columns)
GDELT-specific topic classifications:

- `theme_AGRICULTURE_count` - Agricultural topics
- `theme_ALLIANCE_count` - International alliances, agreements
- `theme_DELAY_count` - Delays, disruptions
- `theme_ECON_DEBT_count` - Economic debt issues
- `theme_ECON_INFLATION_count` - Inflation concerns
- `theme_ECON_STOCKMARKET_count` - Stock market related
- `theme_ELECTION_count` - Political elections
- `theme_EPU_POLICY_count` - Economic policy uncertainty
- `theme_EPU_POLICY_GOVERNMENT_count` - Government policy uncertainty
- `theme_GENERAL_GOVERNMENT_count` - General government news
- `theme_LEGISLATION_count` - Laws, legislation
- `theme_NATURAL_DISASTER_count` - Weather, natural disasters
- `theme_TAX_DISEASE_count` - Taxation and disease outbreaks
- `theme_WB_698_TRADE_count` - World Bank trade indicators

### 3. Tone Columns (88)
Sentiment metrics. **Forward-filled from previous date** in fillforward table.

Each group/theme has 4 tone metrics:
- `*_tone_avg` - Average tone (-100 to +100, negative = bad news)
- `*_tone_positive` - Positive sentiment score (0 to 100)
- `*_tone_negative` - Negative sentiment score (0 to 100)
- `*_tone_polarity` - Sentiment polarity/strength

#### Group Tone Metrics (32 columns)
Example for `group_ALL`:
- `group_ALL_tone_avg`
- `group_ALL_tone_positive`
- `group_ALL_tone_negative`
- `group_ALL_tone_polarity`

*(Same pattern for CORE, LOGISTICS, MARKET, OTHER, POLICY, SUPPLY, TRADE)*

#### Theme Tone Metrics (56 columns)
Example for `theme_AGRICULTURE`:
- `theme_AGRICULTURE_tone_avg`
- `theme_AGRICULTURE_tone_positive`
- `theme_AGRICULTURE_tone_negative`
- `theme_AGRICULTURE_tone_polarity`

*(Same pattern for all 14 themes)*

---

## Data Gaps & Forward Fill Strategy

### Bronze/Silver Tables (`gdelt_wide`)
- **Coverage**: Only dates with actual GDELT data (sparse)
- **Gaps**: Weekends, holidays, days with no news
- **Total rows**: ~2,051 (as of Nov 2025)

### Fillforward Table (`gdelt_wide_fillforward`) ⭐
- **Coverage**: Every calendar day (2021-01-01 to current)
- **Gaps**: None (continuous time series)
- **Total rows**: ~3,576 (1,788 dates × 2 commodities)
- **Strategy**:
  - **Count columns**: Set to 0 (no news on that date)
  - **Tone columns**: Forward-filled from previous date with data

---

## Common Use Cases

### 1. Overall Sentiment Analysis
Use `group_ALL_*` columns for aggregate sentiment:

```sql
SELECT article_date, commodity,
       group_ALL_count,           -- Total article volume
       group_ALL_tone_avg,        -- Overall sentiment
       group_ALL_tone_polarity    -- Sentiment strength
FROM commodity.silver.gdelt_wide_fillforward
WHERE commodity = 'coffee'
  AND article_date >= '2024-01-01'
ORDER BY article_date
```

### 2. Supply Chain Disruption Detection
Use `group_LOGISTICS_*` and `group_SUPPLY_*`:

```sql
SELECT article_date, commodity,
       group_LOGISTICS_count,
       group_LOGISTICS_tone_avg,
       group_SUPPLY_tone_negative  -- High = bad news about supply
FROM commodity.silver.gdelt_wide_fillforward
WHERE group_LOGISTICS_count > 0 OR group_SUPPLY_count > 0
ORDER BY article_date DESC
```

### 3. Weather Event Impact
Use `theme_NATURAL_DISASTER_*`:

```sql
SELECT article_date, commodity,
       theme_NATURAL_DISASTER_count,
       theme_NATURAL_DISASTER_tone_avg
FROM commodity.silver.gdelt_wide_fillforward
WHERE theme_NATURAL_DISASTER_count > 5  -- Significant coverage
ORDER BY article_date DESC
```

### 4. Policy/Government Analysis
Use `group_POLICY_*` and `theme_EPU_*`:

```sql
SELECT article_date, commodity,
       group_POLICY_count,
       theme_EPU_POLICY_tone_avg,
       theme_LEGISLATION_count
FROM commodity.silver.gdelt_wide_fillforward
WHERE commodity = 'sugar'
  AND (group_POLICY_count > 0 OR theme_EPU_POLICY_count > 0)
ORDER BY article_date DESC
```

---

## Interpretation Guide

### Tone Scores
- **tone_avg**: -100 to +100
  - Positive values = optimistic news
  - Negative values = pessimistic news
  - Magnitude matters: -5 vs -50 very different

- **tone_positive**: 0 to 100
  - Percentage of positive language

- **tone_negative**: 0 to 100
  - Percentage of negative language
  - High values = bearish sentiment

- **tone_polarity**: Absolute difference between positive and negative
  - High = strong directional sentiment
  - Low = mixed/neutral sentiment

### Count Interpretation
- **High counts**: Major news event or sustained coverage
- **Zero counts**: No relevant news (or missing data in sparse table)
- **Trend changes**: Emerging story or fading interest

---

## Best Practices for Forecasting

1. **Always use `gdelt_wide_fillforward`** for time series models
   - No gaps = no missing timesteps
   - Forward-filled tones maintain context

2. **Start with `group_ALL_*`** for baseline sentiment
   - Captures overall market mood
   - Less noisy than individual themes

3. **Add specific themes** based on hypothesis
   - Weather models: `theme_NATURAL_DISASTER_*`
   - Policy models: `group_POLICY_*`, `theme_EPU_*`
   - Supply models: `group_SUPPLY_*`, `theme_AGRICULTURE_*`

4. **Lag sentiment features** by 1-7 days
   - News impact may not be immediate
   - Test different lag windows

5. **Normalize by article count**
   - `tone_avg * log(1 + count)` weighs by coverage volume
   - Avoids single-article noise

---

## Data Quality Notes

- **Language Bias**: GDELT over-represents English-language news
- **Sentiment Noise**: Tone scores can be noisy day-to-day
- **Coverage Gaps**: Some days have zero relevant articles (counts = 0)
- **Forward-Fill Caveat**: Tone metrics in fillforward table are stale on gap days
- **Timezone**: GDELT uses UTC; dates may not align perfectly with market close

---

## Source & Processing

**Raw Data**: GDELT Project GKG (Global Knowledge Graph) files
- Source: http://data.gdeltproject.org/gdeltv2/masterfilelist.txt
- Format: Tab-separated values (TSV)
- Frequency: 15-minute updates (aggregated to daily)

**Processing Pipeline**:
1. **Bronze**: Raw GDELT data filtered for coffee/sugar keywords
2. **Silver**: Wide-format aggregation (1 row per date-commodity)
3. **Fillforward**: Gap-filled continuous time series

**Update Schedule**:
- Bronze discovery: Daily at 2 AM UTC
- Silver processing: Daily at 3 AM UTC
- Fillforward refresh: Daily at 4 AM UTC

---

## How to Query the Data

### SQL Editor (Databricks UI)

1. Navigate to: https://dbc-5e4780f4-fcec.cloud.databricks.com
2. Click "SQL Editor"
3. Select warehouse: `Serverless Starter Warehouse` (ID: `d88ad009595327fd`)
4. Run your query:
   ```sql
   SELECT * FROM commodity.silver.gdelt_wide_fillforward
   WHERE commodity = 'coffee' AND article_date >= '2024-01-01'
   LIMIT 10
   ```

### Python REST API

```python
import requests
import os

def query_databricks(sql):
    """Execute SQL query against Databricks SQL warehouse."""
    response = requests.post(
        "https://dbc-5e4780f4-fcec.cloud.databricks.com/api/2.0/sql/statements/",
        headers={
            "Authorization": f"Bearer {os.environ['DATABRICKS_TOKEN']}",
            "Content-Type": "application/json"
        },
        json={
            "warehouse_id": "d88ad009595327fd",
            "statement": sql,
            "wait_timeout": "50s"
        }
    )
    result = response.json()
    return result.get('result', {}).get('data_array', [])

# Example usage
data = query_databricks("""
    SELECT article_date, commodity, group_ALL_count, group_ALL_tone_avg
    FROM commodity.silver.gdelt_wide_fillforward
    WHERE commodity = 'coffee' AND article_date >= '2024-11-01'
    ORDER BY article_date
""")
```

### Performance Tips

1. **Always filter on partitions**: `WHERE commodity = 'X' AND article_date >= 'YYYY-MM-DD'`
2. **Use LIMIT for exploration**: Add `LIMIT 100` when testing queries
3. **Refresh if data missing**: `REFRESH TABLE commodity.silver.gdelt_wide_fillforward`
4. **Avoid SELECT ***: Specify only needed columns for better performance

### Common Issues

- **"Table not found"** → Use full name with catalog: `commodity.silver.gdelt_wide_fillforward`
- **Slow query** → Add partition filters (commodity, article_date)
- **No results** → Verify data exists: `SELECT COUNT(*) FROM commodity.silver.gdelt_wide_fillforward`
- **Stale data** → Run `REFRESH TABLE` to update metadata

---

## Related Documentation

- **Lambda Pipeline**: `GDELT_LAMBDA_REFERENCE_GUIDE.md`
- **Data Sources Overview**: `../DATA_SOURCES.md`
- **Unified Architecture**: `../UNIFIED_DATA_ARCHITECTURE.md`

---

**Questions?** See `research_agent/README.md` for navigation to other docs.
