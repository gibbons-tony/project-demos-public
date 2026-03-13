# Data Pipeline Status

Last Updated: 2025-11-07

## Databricks Infrastructure

**Workspace**: `https://dbc-5e4780f4-fcec.cloud.databricks.com`
**SQL Warehouse**: `d88ad009595327fd`
**Catalog**: `commodity`

**Credentials**: All credentials stored in `.env` files (gitignored, not in repo)

---

## Data Layers

### Bronze Layer (Raw Data)

| Table | Status | Row Count | Date Range | Notes |
|-------|--------|-----------|------------|-------|
| `market` | ✅ Ready | 343,694 | 2015-2025 | Commodity prices (Coffee, Sugar, etc.) |
| `weather` (v1) | ✅ Ready | 246,030 | 2015-2025 | OLD coordinates (state capitals) |
| `weather_v2` | 🔄 Creating | TBD | 2015-2025 | NEW corrected coordinates |
| `vix` | ✅ Ready | ~10 years | 2015-2025 | Volatility index |
| `cftc` | ✅ Ready | Multiple years | 2015-2025 | CFTC commitment of traders |
| `macro` | ✅ Ready | Multiple years | 2015-2025 | Macroeconomic indicators |
| `gdelt` | ⚠️ Sparse | 114,221 | 2021, 2023, 2025 | Only 32 days of data |

### Silver Layer (Curated)

| Table | Status | Row Count | Notes |
|-------|--------|-----------|-------|
| `unified_data` | ✅ Ready | 199,794 | Joins bronze tables, currently uses weather v1 |

### Forecast Layer

| Table | Status | Row Count | Notes |
|-------|--------|-----------|-------|
| `distributions` | ✅ Ready | 1,664,830 | Monte Carlo paths (2K-4K per forecast) |
| `forecast_metadata` | ✅ Ready | 44 | Metadata for 44 forecast windows |
| `forecast_actuals` | ✅ Ready | 600 | Realized prices for backtesting |
| `point_forecasts` | ✅ Ready | 0 | 14-day point forecasts with confidence intervals |

---

## Forecast API

**Location**: `trading_agent/FORECAST_API_GUIDE.md`
**Status**: ✅ All queries validated (2025-11-07)
**Test Results**: 7/7 tests passed

**Available Data**:
- Coffee: 1.2M paths across 42 forecast dates
- Sugar: 420K paths across 42 forecast dates
- Date Range: July 2018 - November 2025

**Models Available**: 10 models (Prophet, ARIMA, Random Walk, XGBoost, SARIMAX, etc.)

---

## Data Quality

**Last Validation**: 2025-11-07

**Results**: 20/20 tests passed
- ✅ No nulls in critical columns
- ✅ Data freshness: 7 days
- ✅ All forecast tables populated
- ✅ Distribution integrity validated

---

## Known Issues

1. **GDELT Sparse Coverage**: Only 32 days across 3 years (see WARNINGS.md)
2. **Weather v2 Migration**: In progress, bronze table being created
3. **unified_data**: Still uses weather v1, needs update after weather_v2 completes

---

## Upcoming Changes

1. Weather v2 bronze table creation (in progress)
2. unified_data update to use weather_v2
3. Model retraining with corrected weather coordinates
4. Databricks jobs setup for automated pipeline

---

## For Trading Agent

**Ready to Use**:
- ✅ `commodity.forecast.distributions` - Monte Carlo paths
- ✅ `commodity.forecast.forecast_actuals` - Backtest data
- ✅ `commodity.forecast.forecast_metadata` - Forecast metadata
- ✅ Forecast API Guide - All queries working

**Credentials**: Contact Research Agent team for Databricks credentials

**API Examples**: See `trading_agent/FORECAST_API_GUIDE.md`
