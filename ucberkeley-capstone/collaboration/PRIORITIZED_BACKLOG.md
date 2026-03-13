# Prioritized Backlog

Last Updated: 2025-11-18

## Priority 0: Critical Path (Blocking)

### Research Agent

- [ ] **Complete Sugar weather data backfill (PARTIALLY FIXED)**
  - **Status (2025-01-11 22:45)**:
    - Market Data: ✅ Sugar has 5,470 rows (2015-2025) in landing table
    - Weather Data: ❌ Sugar has only 380 rows (10 days) in landing table
    - Unified Data: ❌ Sugar has 380 rows (blocked by missing weather)
  - **Root Cause**: Weather Lambda never ran historical backfill for Sugar regions
  - **Next Steps**:
    1. Check weather Lambda logs / S3 for Sugar data
    2. If failed: Try chunked yearly backfill (2015, 2016, ..., 2025)
    3. Once weather data exists: Run `rebuild_all_layers.py`
    4. Expected final result: ~140,000 Sugar rows in unified_data

### Trading Agent

- (None currently)

---

## Priority 1: High Priority (Core Features)

### Forecast Agent

- [ ] **Build Databricks evaluation dashboard for model performance**
  - Visualize forecast accuracy across 40 historical windows
  - Compare models (SARIMAX, Prophet, XGBoost, ARIMA, Random Walk, TFT)
  - Show MAE/RMSE/MAPE at 1-day, 7-day, 14-day horizons
  - Display prediction interval calibration (95% coverage)

- [ ] **Backfill forecast_metadata with performance metrics from 40 windows**
  - Calculate MAE/RMSE/MAPE for each model × window
  - Track training/inference timing data
  - Store hardware info for reproducibility

- [ ] **Train Temporal Fusion Transformer (TFT) models**
  - Why: State-of-the-art deep learning for multi-horizon forecasting
  - Status: TFT implementation complete, ready to backfill
  - Models: tft_weather, tft_forex, tft_full, tft_ensemble
  - Estimated time: 4-8 hours (semiannual training = 16 trainings)
  - Dependencies: unified_data with weather_v2 + forex
  - Files: `forecast_agent/ground_truth/models/tft_model.py`

### Trading Agent

- [ ] **Integrate forecast API into trading strategy**
  - API Guide: `trading_agent/FORECAST_API_GUIDE.md`
  - All queries validated (2025-11-07)
  - Data available: `commodity.forecast.distributions`

- [ ] **Implement backtesting framework**
  - Data available: `commodity.forecast.forecast_actuals`
  - Use for model validation

---

## Priority 2: Medium Priority (Infrastructure)

### Forecast Agent

- [ ] **Upload point_forecasts for 40 historical windows to Databricks**
  - Currently only distributions table is populated
  - Point forecasts needed for time-series charting
  - ~2,100 rows (42 dates × 5 models × 14 days × 1 mean forecast)

- [ ] **Extend pipeline to Sugar commodity (after data validation)**
  - Validate Sugar data availability in commodity.silver tables
  - Run backfill for Sugar: 40 windows × 5 models × 2,000 paths
  - Update FORECAST_API_GUIDE.md with Sugar examples

- [ ] **Design experiment tracking database**
  - Track model experiments: config, performance, artifacts
  - Enable pruning of poor-performing models from registry
  - Maintain experiment history for presentation/thesis
  - Goal: Show platform's experimentation & scale capabilities

### Research Agent

- [ ] **Add BRL/USD forex data via Lambda**
  - Why: Brazil produces 40% of global coffee, BRL movements highly correlated with coffee prices
  - Impact: HIGH - Expected MAE improvement of 5-15%
  - Current gap: 7/8 top producer currencies available, BRL missing
  - Effort: 2-3 hours
  - Options:
    1. Extend existing forex lambda (add 'BRL': 'USD' to pair list)
    2. Quick fetch from free API (exchangerate-api.com, no key required)
  - Backfill needed: 2015-2025 (~3,800 daily values)
  - Files to modify:
    - `research_agent/lambdas/*/forex_fetcher.py` (or similar)
    - `research_agent/sql/create_unified_data.sql` (add brl_usd column)
    - `forecast_agent/ground_truth/config/model_registry.py` (update TFT features)
  - Cost: < $1 (free API or minimal lambda compute)

- [ ] **Setup Databricks jobs for automated pipeline**
  - Manual via UI (Jobs API requires saved queries)
  - Jobs needed:
    - Daily Bronze Refresh (2 AM)
    - Silver Update (3 AM)
    - Data Quality Validation (4 AM)

- [ ] **Fix GDELT date column type**
  - Currently STRING, should be DATE or TIMESTAMP
  - Low impact (sparse data coverage)

### Trading Agent

- [ ] **Build monitoring dashboard for pipeline data freshness**
  - Track: latest forecast_start_date per model
  - Alert if forecast > 24 hours old
  - Show data quality metrics (null rates, coverage)

---

## Priority 3: Nice to Have (Enhancements)

### Research Agent

- [ ] **Evaluate GDELT inclusion in models**
  - Only 32 days of data across 3 years
  - Determine if adds value or should be excluded
  - See: `collaboration/WARNINGS.md`

- [ ] **Add data freshness monitoring**
  - Alert when data is >7 days stale
  - Integrate with Databricks jobs

### Trading Agent

- (Add nice-to-have tasks here)

---

## Stretch Goals

### Research Agent

- [ ] **Add stock price data integration**
  - Source: Yahoo Finance / Alpha Vantage / other
  - Tickers: Related commodity ETFs, mining companies, etc.
  - Purpose: Additional features for trading models
  - Integration: New bronze table + add to unified_data
  - Estimated time: 3-5 hours
  - Notes:
    - Consider which stock tickers are relevant to commodity trading
    - May need rate-limited API calls
    - Historical data availability varies by source

- [ ] **Add sentiment analysis from news sources**
  - Supplement sparse GDELT data
  - Sources: Financial news APIs, Twitter/X, Reddit
  - NLP pipeline for sentiment scoring

- [ ] **Multi-horizon forecasts**
  - Current: 14-day forecasts
  - Stretch: 30-day, 90-day horizons
  - Evaluate model accuracy at longer horizons

### Trading Agent

- [ ] **Multi-commodity portfolio optimization**
  - Use forecast distributions for correlation analysis
  - Optimize across Coffee, Sugar, and future commodities
  - Risk-adjusted portfolio allocation

- (Add other stretch goals here)

---

## Completed

### Research Agent

- [x] Weather backfill v2 - 10+ years historical data (2015-2025, 175,770 records)
- [x] Weather_v2 bronze table creation (with COPY INTO for S3 ingestion)
- [x] Update unified_data to use weather_v2 (8 weather features per region)
- [x] Validate July 2021 frost event (40.5% price spike confirmed, cold temps detected)
- [x] Implement Temporal Fusion Transformer (TFT) models
  - 5 model variants: tft, tft_weather, tft_forex, tft_full, tft_ensemble
  - Integrated into model registry with forex rates (7/8 producer currencies)
  - Production-ready, dependencies installed
- [x] Full pipeline validation - 20/20 tests passed
- [x] Forecast API Guide validation - 7/7 tests passed
- [x] New Databricks workspace setup (Unity Catalog)
- [x] Remove hardcoded credentials from git
- [x] Create collaboration folder for team coordination

### Trading Agent

- (Track completed tasks here)

---

## Blocked / On Hold

(No blocked items currently)
