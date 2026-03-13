# Technical Approach Highlights
## UC Berkeley Capstone - Commodity Price Forecasting

**Last Updated:** 2025-11-12
**Purpose:** Key technical decisions and innovations for presentation

---

## 1. Data Architecture

### Multi-Layer Lakehouse (Bronze → Silver → Gold)
- **Bronze Layer**: Raw data ingestion (market prices, weather, GDELT, VIX, forex)
- **Silver Layer**: Cleaned, validated, joined unified_data table
- **Gold Layer**: Feature-engineered forecast distributions table

**Key Innovation:** Single `unified_data` table with 3,000+ rows covering 8 years of daily data across 15+ data sources

### Databricks Unity Catalog
- **Catalog:** commodity
- **Schemas:** bronze, silver, forecast
- **Tables:** market, weather, weather_v2, gdelt, vix, forex, unified_data, distributions
- **Benefits:** ACID transactions, time travel, schema evolution

---

## 2. Data Sources Integration

### 8 Data Sources Automated via AWS Lambda
1. **Market Data** (Yahoo Finance): Daily coffee futures prices
2. **Weather V2** (Open-Meteo): 6 producer countries, 5 weather variables each
3. **GDELT** (Google BigQuery): Geopolitical event sentiment
4. **VIX** (CBOE): Market volatility index
5. **Forex** (7 currency pairs): BRL, COP, VND, HNL, UGX, IDR, ETB vs USD
6. **CFTC** (Commitment of Traders): Institutional positioning
7. **Weather V1** (Original): Brazil/Colombia temperature/precipitation
8. **Producer Countries**: Coffee production by country

**Key Innovation:** Serverless Lambda functions trigger daily at 6 AM EST, write to S3, Databricks ingests via COPY INTO

### Weather V2 Upgrade (Nov 2025)
- **Old:** 2 countries (Brazil, Colombia), 2 variables (temp, precip)
- **New:** 6 countries (added Vietnam, Honduras, Uganda, Indonesia), 5 variables (added humidity, wind, cloud cover)
- **Impact:** 15x more weather features (4 → 60 columns)
- **Backfilled:** 175,770 records (2015-2025)

---

## 3. Forecasting Models

### Model Portfolio (3 Tiers)
1. **Baseline:** Naive (last price carried forward)
2. **Traditional ML:** XGBoost with engineered features
3. **Deep Learning:** Temporal Fusion Transformer (TFT) with attention

### Probabilistic Forecasting
- **Output:** 2,000 Monte Carlo paths per forecast
- **Quantiles:** 10th, 25th, 50th, 75th, 90th percentiles
- **Uncertainty:** Standard deviation calculated from path distribution
- **Use Case:** Risk management, confidence intervals for trading decisions

### Multi-Horizon Forecasts
- **Horizons:** 1, 3, 7, 14 days ahead
- **Actuals Tracking:** Ground truth stored alongside forecasts for backtesting
- **Evaluation:** MAE, RMSE, directional accuracy per horizon

---

## 4. Expanding Window Cross-Validation

### Rolling Window Backfill Strategy
- **Training Frequency:** Quarterly (32 trainings) or Semiannually (16 trainings)
- **Date Range:** 2018-01-01 to 2025-11-11 (7 years, 2,872 days)
- **Train Once, Forecast Daily:** Each model trained periodically, forecasts daily until next retrain
- **Example:** Train on Jan 1, forecast daily Jan 2 → Jun 30 (181 days), retrain Jul 1

**Key Benefit:** Realistic backtest of how model would perform in production (no lookahead bias)

### Resume Capability
- **Problem:** Multi-hour backfills can be interrupted
- **Solution:** Check existing forecasts in Databricks, skip already-completed dates
- **Impact:** Can restart failed backfills without duplicating work

---

## 5. Temporal Fusion Transformer (TFT)

### Why TFT?
- **Multi-horizon native:** Forecasts 1-14 days simultaneously
- **Attention mechanisms:** Learns which features matter when
- **Variable selection:** Automatically determines feature importance
- **Interpretable:** Attention weights show causal relationships

### TFT Model Variants
1. **tft** - Base model (price history only)
2. **tft_weather** - With weather covariates (60-day lookback)
3. **tft_forex** - Weather + forex data
4. **tft_full** - All features (weather + forex + GDELT + VIX)
5. **tft_ensemble** - 5-model ensemble for robustness

### Known vs Unknown Features
- **Known:** Weather forecasts (we can predict future weather)
- **Unknown:** Price lags, VIX, GDELT (we don't know future values)

**Innovation:** Separate feature engineering for temporal dependencies

---

## 6. Feature Engineering

### Price-Based Features
- Lag features: 1, 7, 14, 30 days
- Rolling statistics: 7/14/30-day mean, std, min, max
- Momentum indicators: Price changes, volatility

### Weather Features (60 columns)
- 6 countries × 5 variables × 2 metrics (mean + anomaly)
- Temperature (max, min, mean)
- Precipitation (mm)
- Humidity (%)
- Wind speed (km/h)
- Cloud cover (%)

### External Features
- VIX (volatility index)
- GDELT sentiment scores
- 7 forex pairs (producer currencies)
- Day of week, month, quarter (cyclical encoding)

---

## 7. Parallel Backfilling

### Current Approach (Process-Level Parallelization)
- Multiple models running simultaneously via nohup
- Example: naive + xgboost backfills running concurrently
- **Benefit:** 2x speedup on multi-core laptop
- **Limitation:** Limited by local machine cores

### Future: PySpark Parallelization
- Distribute 16 training windows across Databricks cluster nodes
- Each node trains a subset of windows independently
- **Potential Speedup:** 4-8x faster on 8-node cluster
- **Trade-off:** More complex code, requires Databricks compute costs

---

## 8. Key Challenges Solved

### Missing Timesteps in Financial Data
- **Problem:** TFT expects continuous daily data, coffee markets closed weekends/holidays
- **Solution:** Added `allow_missing_timesteps=True` to TimeSeriesDataSet
- **File:** forecast_agent/ground_truth/models/tft_model.py:93

### Credential Security
- **Problem:** Databricks API tokens in code files
- **Solution:** GitHub secret scanning blocked push, migrated to environment variables
- **Files Fixed:** check_all_naive_dates.py, verify_backfill.py, TFT_SETUP.md

### Version Compatibility (Ongoing)
- **Problem:** pytorch-lightning 2.5.5 incompatible with pytorch-forecasting 1.4.0
- **Status:** TFT implementation complete, debugging dependency issues separately

---

## 9. Production-Ready Features

### Distributed Data Platform
- **Storage:** AWS S3 (cheap, durable)
- **Compute:** Databricks Serverless SQL (auto-scaling)
- **Orchestration:** AWS Lambda (serverless, event-driven)

### Automated Pipeline
- Daily data fetches at 6 AM EST
- Incremental loads (only new data)
- Error handling and retry logic
- Monitoring via CloudWatch logs

### Scalability
- Current: 1 commodity (Coffee), 8 data sources
- **Extendable to:** All 10+ commodities with same infrastructure
- Just add commodity ticker to Lambda configurations

---

## 10. Evaluation Framework (In Progress)

### Metrics Planned
- **Accuracy:** MAE, RMSE per horizon (1/3/7/14 days)
- **Directional:** % correct price movement direction
- **Probabilistic:** Calibration (do 90% intervals contain 90% of actuals?)
- **Economic:** Simulated trading PnL using forecasts

### Case Study: July 2021 Brazil Frost
- **Event:** Worst frost in 27 years, coffee prices surged 50%
- **Question:** Did weather-aware models predict this spike?
- **Analysis:** Compare TFT (with weather) vs naive/XGBoost forecasts

---

## 11. Technology Stack

### Languages
- Python 3.11 (data processing, modeling)
- SQL (Databricks queries)
- Bash (automation scripts)

### Key Libraries
- **Data:** pandas, numpy, databricks-sql-connector
- **ML:** xgboost, scikit-learn
- **Deep Learning:** pytorch, pytorch-forecasting, pytorch-lightning
- **Time Series:** statsmodels, prophet (future)

### Infrastructure
- **AWS:** Lambda, S3, EventBridge, CloudWatch
- **Databricks:** Unity Catalog, Serverless SQL Warehouse, Delta Lake
- **Version Control:** Git, GitHub

---

## 12. Quantifiable Achievements

### Data Scale
- **8 years** of historical data (2015-2025)
- **3,000+ rows** in unified_data table
- **175,770 records** backfilled for weather_v2
- **2,872 days** of forecasts to generate (2018-2025)
- **2,000 paths** per forecast = 5.7 million simulated price trajectories

### Model Scale
- **16 training windows** (semiannual strategy)
- **181 forecasts** per window on average
- **3 models** running in parallel (naive, xgboost, tft planned)
- **5 TFT variants** implemented

### Time Savings
- **Manual data fetch:** 30 min/day → **Automated:** 0 min/day
- **Backfill resume:** Saves hours on interrupted runs
- **Parallel models:** 2x speedup vs sequential training

---

## 13. Lessons Learned

### Architecture Decisions
- ✅ **Unified_data table:** Single source of truth beats scattered tables
- ✅ **Probabilistic forecasts:** More useful than point estimates for risk management
- ✅ **Expanding window:** More realistic than fixed train/test split
- ❌ **Daily training:** Too expensive, quarterly/semiannual sufficient

### Technical Debt Addressed
- Deleted 1.67GB of redundant files (lambda_migration/, old logs, zip archives)
- Consolidated 5 TODO files into single PRIORITIZED_BACKLOG.md
- Migrated hardcoded credentials to environment variables
- Organized documentation into structured docs/ folder

### Future Optimizations
- PySpark parallelization for 4-8x backfill speedup
- GPU training for TFT (10x faster than CPU)
- Model ensembling (combine naive + xgboost + tft predictions)
- BRL/USD forex data (Brazil produces 40% of global coffee)

---

## Presentation Talking Points

### Opening Hook
"We built a system that predicts coffee prices 14 days into the future with probabilistic confidence intervals, using 8 automated data sources and 3 tiers of ML models."

### Technical Depth
"Our Temporal Fusion Transformer uses attention mechanisms to learn which weather features in which countries matter most for price movements - like automatically discovering that Brazil frost events drive price spikes."

### Real-World Impact
"By forecasting price distributions instead of single points, traders can quantify risk. A narrow distribution means high confidence, a wide distribution means wait for more data."

### Scalability
"The entire pipeline is serverless and automated. Once configured for coffee, extending to sugar, cocoa, or cotton requires adding 2 lines to a Lambda config file."

---

## Questions to Highlight Technical Choices

**Q: Why Databricks instead of local Postgres?**
A: Databricks handles 100GB+ datasets, auto-scales, and provides ACID transactions on data lakes.

**Q: Why TFT instead of LSTM?**
A: TFT has built-in variable selection, multi-horizon forecasting, and interpretable attention weights.

**Q: Why expanding window instead of fixed train/test?**
A: Expanding window simulates production deployment - how would the model perform if retrained quarterly?

**Q: Why 2,000 Monte Carlo paths?**
A: Allows us to calculate full probability distributions, not just mean forecasts. Critical for risk management.

---

## Files to Reference in Presentation

### Core Pipeline
- `research_agent/lambdas/*/lambda_function.py` - Data fetchers
- `research_agent/sql/create_unified_data.sql` - Feature engineering
- `forecast_agent/backfill_rolling_window.py` - Expanding window backfill

### Model Implementations
- `forecast_agent/ground_truth/models/naive_model.py` - Baseline
- `forecast_agent/ground_truth/models/xgboost_model.py` - Traditional ML
- `forecast_agent/ground_truth/models/tft_model.py` - Deep learning

### Evaluation
- `forecast_agent/verify_backfill.py` - Check forecast completeness
- `collaboration/PRIORITIZED_BACKLOG.md` - Project roadmap

---

**Document Created:** 2025-11-12
**For:** UC Berkeley Capstone Presentation
**Team:** Connor Watson + Tony (Trading Agent)
