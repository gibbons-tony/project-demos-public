# GDELT Sentiment Data Processing

**Status**: 🚧 **WORK IN PROGRESS** - Open to modification and suggestions

**Owner**: Research Agent (Stuart & Francisco)
**Input**: `commodity.bronze.bronze_gkg` (GDELT Global Knowledge Graph)
**Output**: Sentiment features in `commodity.silver.unified_data`

---

## Overview

This document explains how we process GDELT sentiment data for commodity forecasting. Since we're **aggregating raw embeddings** rather than using them directly, we need to document these decisions for transparency and future iteration.

---

## What is GDELT GKG?

**GDELT (Global Database of Events, Language, and Tone)**:
- Monitors world news in 100+ languages
- Updates every 15 minutes
- Provides sentiment analysis for global events
- Free, publicly available

**GKG (Global Knowledge Graph)**:
- Article-level metadata
- Contains `V2TONE` (7-dimensional sentiment embedding)
- Contains `THEMES` (article topics/keywords)

---

## V2TONE Structure (Raw Embedding)

`V2TONE` is a **comma-separated string** with 7 dimensions per article:

| Index | Dimension | Range | Description |
|-------|-----------|-------|-------------|
| 0 | **Tone** | -100 to +100 | Overall sentiment (negative to positive) |
| 1 | **Positive Score** | 0 to 100 | Percentage of positive words |
| 2 | **Negative Score** | 0 to 100 | Percentage of negative words |
| 3 | **Polarity** | 0 to 100 | Absolute difference (positive - negative) |
| 4 | **Activity Density** | 0 to 100 | Action/verb intensity |
| 5 | **Self/Group Density** | 0 to 100 | First-person reference density |
| 6 | **Word Count** | Integer | Total words in article |

**Example**: `"-2.5,3.2,5.7,2.5,10.2,4.1,850"` means:
- Slightly negative tone (-2.5)
- 3.2% positive words
- 5.7% negative words (more negative than positive)
- Polarity of 2.5
- 850 words total

---

## Our Processing Approach: Bag-of-Articles Aggregation

### What We Do

We **aggregate multiple articles per day** into **single daily features** using simple statistics:

```sql
-- 1. Parse V2TONE dimensions (article-level)
SELECT
  DATE(SQLDATE) as date,
  CAST(SPLIT(V2TONE, ',')[0] AS DOUBLE) as tone,
  CAST(SPLIT(V2TONE, ',')[1] AS DOUBLE) as positive_score,
  CAST(SPLIT(V2TONE, ',')[2] AS DOUBLE) as negative_score,
  CAST(SPLIT(V2TONE, ',')[3] AS DOUBLE) as polarity,
  ...
FROM commodity.bronze.bronze_gkg
WHERE THEMES LIKE '%COFFEE%' OR THEMES LIKE '%SUGAR%'

-- 2. Aggregate by day (bag-of-articles)
SELECT
  date,
  commodity,
  AVG(tone) as gdelt_tone,                -- Mean sentiment
  AVG(positive_score) as gdelt_positive,  -- Mean positivity
  AVG(negative_score) as gdelt_negative,  -- Mean negativity
  AVG(polarity) as gdelt_polarity,        -- Mean polarity
  STDDEV(tone) as gdelt_tone_volatility,  -- Disagreement/uncertainty
  COUNT(*) as gdelt_article_count,        -- News volume
  SUM(word_count) as gdelt_total_words    -- Coverage depth
FROM article_level_data
GROUP BY date, commodity
```

### Result: 7 Daily Features per Commodity

| Feature | Type | Interpretation |
|---------|------|----------------|
| `gdelt_tone` | FLOAT | Average daily sentiment (-100 to +100) |
| `gdelt_positive` | FLOAT | Average positive score |
| `gdelt_negative` | FLOAT | Average negative score |
| `gdelt_polarity` | FLOAT | Average polarity |
| `gdelt_tone_volatility` | FLOAT | Std dev of tone (disagreement) |
| `gdelt_article_count` | INT | Number of articles (attention) |
| `gdelt_total_words` | INT | Total word count (coverage) |

---

## Why This Approach?

### Pros ✅

1. **Simple & Interpretable**: Daily averages are easy to understand
2. **Reduces Dimensionality**: 100s of articles → 7 features per day
3. **Standard Practice**: Similar to "bag-of-words" in NLP
4. **Compatible with SARIMAX**: Time series models need single values per timestep
5. **Captures Key Signals**:
   - Mean tone = overall sentiment
   - Volatility = disagreement/uncertainty
   - Article count = attention spikes

### Cons ❌

1. **Loses Temporal Detail**: Can't see intraday sentiment shifts
2. **Averages Out Extremes**: One very negative article gets diluted by many neutral ones
3. **No Article Weighting**: Major news outlets weighted same as minor blogs
4. **Loses Article Relationships**: Can't model sentiment cascades or reply chains

---

## Alternative Approaches (Future Consideration)

### 1. Weighted Aggregation

**Weight articles by source importance or word count**:
```sql
AVG(tone * word_count) / SUM(word_count) as weighted_tone
```

**Pros**: Important/long articles have more influence
**Cons**: Assumes longer = more important (not always true)

---

### 2. Preserve Full Article Embeddings

**Store all article-level data in separate table**:
```
gdelt_articles (date, commodity, article_id, tone_vector[7], source, ...)
```

**Pros**:
- No information loss
- Could use for advanced models (LSTM with attention, Transformers)
- Could weight by source credibility

**Cons**:
- Much larger dataset
- Complex to integrate with time series models
- Would need article-level metadata (source reliability, etc.)

---

### 3. Temporal Aggregation Windows

**Instead of daily averages, use rolling windows**:
```sql
-- 7-day rolling average sentiment
AVG(tone) OVER (
  PARTITION BY commodity
  ORDER BY date
  ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
) as sentiment_7d_avg
```

**Pros**: Smooths noise, captures trends
**Cons**: Lag in signal, overlapping windows

---

### 4. Extreme Value Aggregation

**Focus on outliers instead of averages**:
```sql
MIN(tone) as most_negative_article,  -- Panic signal
MAX(tone) as most_positive_article,  -- Euphoria signal
PERCENTILE(tone, 0.10) as p10_tone,  -- Pessimistic tail
PERCENTILE(tone, 0.90) as p90_tone   -- Optimistic tail
```

**Pros**: Captures sentiment extremes (often more predictive)
**Cons**: More features, noisier signals

---

### 5. Topic-Specific Aggregation

**Separate sentiment by theme/topic**:
```sql
-- Brazil frost sentiment vs general coffee sentiment
CASE
  WHEN THEMES LIKE '%FROST%' THEN 'frost'
  WHEN THEMES LIKE '%DROUGHT%' THEN 'drought'
  WHEN THEMES LIKE '%TRADE%' THEN 'trade'
  ELSE 'general'
END as topic
```

**Pros**: Different topics drive different price reactions
**Cons**: Requires topic classification, much more complex

---

### 6. Time-Weighted Sentiment

**Recent articles weighted more heavily**:
```sql
-- Exponential decay weighting
SUM(tone * EXP(-0.1 * (CURRENT_DATE - date))) /
SUM(EXP(-0.1 * (CURRENT_DATE - date)))
```

**Pros**: Captures "freshness" of sentiment
**Cons**: Harder to backtest consistently

---

## Implementation Status

### Current (Commented in `create_unified_data.sql`)

```sql
-- STEP 1: Parse V2TONE dimensions
gdelt_raw AS (
  SELECT DATE(SQLDATE), commodity,
         CAST(SPLIT(V2TONE, ',')[0] AS DOUBLE) as tone,
         ...
)

-- STEP 2: Daily aggregation (bag-of-articles)
gdelt_sentiment AS (
  SELECT date, commodity,
         AVG(tone), AVG(positive_score), ..., COUNT(*)
  GROUP BY date, commodity
)

-- STEP 3: Forward-fill for non-trading days
gdelt_filled AS (...)
```

### To Enable

1. Uncomment GDELT sections in `research_agent/sql/create_unified_data.sql`
2. Coordinate regeneration of `unified_data` table
3. Validate: Check article counts, sentiment ranges, null handling
4. Test: Train forecast models with/without GDELT features

---

## Open Questions & Feedback Welcome

**We're open to suggestions on**:

1. **Aggregation Method**: Should we weight by word count? Source credibility?
2. **Time Windows**: Daily? 3-day rolling? 7-day rolling?
3. **Extreme Values**: Should we track min/max sentiment alongside mean?
4. **Topic Separation**: Should we separate frost/drought/trade sentiment?
5. **Missing Data**: Forward-fill vs null for days with no articles?
6. **Keyword Filtering**: Are `THEMES LIKE '%COFFEE%'` sufficient or too broad?

**To discuss**:
- Connor: How will forecast models use these features? Any preferred structure?
- Stuart/Francisco: Source quality filtering? De-duplication strategies?
- Team: Should we test multiple aggregation approaches in parallel?

---

## Performance Considerations

**Dataset Size**:
- Raw GDELT: ~millions of articles globally
- Filtered (Coffee/Sugar): ~thousands per day (estimated)
- After aggregation: **2 rows per day** (Coffee + Sugar)

**Processing Cost**:
- Parsing V2TONE: Low (simple string split)
- Keyword filtering: Medium (LIKE on THEMES column)
- Aggregation: Low (GROUP BY date, commodity)
- **Total**: Should add <1 minute to unified_data creation

**Storage Impact**:
- 7 new columns in unified_data
- ~75k rows × 7 columns × 8 bytes = **~4MB** additional storage
- Negligible impact

---

## Next Steps

1. **Validation** (before uncommenting):
   - Query `bronze_gkg` to check article counts
   - Verify V2TONE format consistency
   - Check THEMES keyword coverage

2. **Testing** (after enabling):
   - Compare SARIMAX with/without GDELT features
   - Statistical test: Does sentiment improve accuracy?
   - Feature importance: Which GDELT dimensions matter?

3. **Iteration** (based on results):
   - If valuable: Consider alternative aggregations
   - If noisy: Add smoothing/filtering
   - If topic-specific signals exist: Separate by theme

---

## References

- GDELT Project: https://www.gdeltproject.org/
- GDELT GKG Documentation: http://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf
- V2TONE Specification: See codebook Section 2.5.7

**Document Version**: 1.0
**Last Updated**: 2024-10-28
**Feedback**: Contact Stuart, Francisco, or Connor
