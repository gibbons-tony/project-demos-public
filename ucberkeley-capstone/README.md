# Ground Truth - Commodity Forecasting System

**Team**: Connor Watson, Stuart Holland, Francisco Munoz, Tony Gibbons

AI-driven forecasting for coffee & sugar futures to help Colombian traders optimize harvest sales.

**Key Insight**: Traders care about `Coffee Price (USD) × COP/USD Rate`, not just USD futures.

---

## For AI Assistants

**🤖 START HERE**: [CLAUDE.md](CLAUDE.md)

This is your primary entry point containing:
- Credential setup (AWS & Databricks)
- Development best practices
- Navigation to all key docs
- Current project state
- Quick reference for common tasks

**Documentation Strategy**: See [docs/DOCUMENTATION_STRATEGY.md](docs/DOCUMENTATION_STRATEGY.md) for our hierarchical documentation organization

---

## Quick Start

```bash
# Project structure
ucberkeley-capstone/
├── README.md              # Human entry point
├── CLAUDE.md              # 🤖 AI agent entry point
├── docs/                  # Core reference documentation
│   ├── DOCUMENTATION_STRATEGY.md  # How we organize docs
│   ├── DATA_CONTRACTS.md  # Database schemas (single source of truth)
│   ├── ARCHITECTURE.md    # System architecture
│   ├── SECURITY.md        # Credential management
│   └── EVALUATION_STRATEGY.md
├── research_agent/        # Data pipeline (Francisco)
├── forecast_agent/        # Time series forecasting (Connor)
├── trading_agent/         # Risk/trading signals (Tony)
└── data/                  # Local snapshots (gitignored)
```

---

## Three-Agent System

```
Research → Forecast → Trading
(Francisco)  (Connor)   (Tony)
```

**Research Agent**: Creates `commodity.silver.unified_data`
- Lambda functions for data ingestion
- Bronze/Silver layers in Databricks
- See [research_agent/README.md](research_agent/README.md)

**Forecast Agent**: Generates forecasts + distributions
- Time series models (SARIMAX, Prophet, XGBoost, ARIMA)
- Walk-forward evaluation framework
- See [forecast_agent/README.md](forecast_agent/README.md)

**Trading Agent**: Risk management + signals
- VaR, CVaR metrics
- Position sizing recommendations
- See [trading_agent/README.md](trading_agent/README.md)

---

## Data Contracts

### Input: `commodity.silver.unified_data`
- Grain: (date, commodity, region)
- ~75k rows, 37 columns
- Market data + weather + macro + exchange rates

### Outputs:
- `commodity.forecast.point_forecasts` - 14-day forecasts with confidence intervals
- `commodity.forecast.distributions` - 2,000 Monte Carlo paths for risk analysis
- `commodity.forecast.forecast_metadata` - Model metadata and evaluation metrics

See [docs/DATA_CONTRACTS.md](docs/DATA_CONTRACTS.md) for complete schemas.

---

## Current State

**Production Tables** (Databricks):
- ✅ **commodity.landing.*** - Raw incremental data (6 tables)
- ✅ **commodity.bronze.*** - Deduplicated views (6 views)
- ✅ **commodity.silver.unified_data** - Joined dataset (~75k rows)
- ✅ **commodity.forecast.distributions** - 22,000 rows (9 models, Coffee)
- ✅ **commodity.forecast.point_forecasts** - Point forecasts with confidence intervals

**Infrastructure**:
- Lambda Functions deployed in us-west-2
- EventBridge daily triggers
- Databricks Unity Catalog

---

## Tech Stack

- **Platform**: Databricks (PySpark)
- **Storage**: Delta Lake
- **Modeling**: statsmodels, Prophet, XGBoost
- **Infrastructure**: AWS Lambda, EventBridge
- **Local Testing**: Parquet snapshots

---

## Documentation

**Core Reference**:
- [CLAUDE.md](CLAUDE.md) - AI agent entry point
- [docs/DOCUMENTATION_STRATEGY.md](docs/DOCUMENTATION_STRATEGY.md) - How we organize docs
- [docs/DATA_CONTRACTS.md](docs/DATA_CONTRACTS.md) - Database schemas
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - System architecture
- [docs/SECURITY.md](docs/SECURITY.md) - Credential management

**Agent-Specific**:
- [research_agent/README.md](research_agent/README.md)
- [forecast_agent/README.md](forecast_agent/README.md)
- [trading_agent/README.md](trading_agent/README.md)

**Note**: All documentation follows a hierarchical web-graph structure. See [docs/DOCUMENTATION_STRATEGY.md](docs/DOCUMENTATION_STRATEGY.md) for details.

---

**Last Updated**: 2025-01-11
