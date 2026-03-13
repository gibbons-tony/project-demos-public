# Research Agent

Data infrastructure for commodity price forecasting - automated data collection, processing, and feature engineering.

## Purpose

Maintains the data pipeline from raw sources to production-ready tables for ML models:
- **Bronze Layer**: Raw data from APIs (market, weather, VIX, FX, GDELT)
- **Silver Layer**: Legacy unified table (exploded regions)
- **Gold Layer**: Production ML-ready tables (array-based, 90% smaller)

## Quick Start

### For Forecast Models (Consumers)

**Current data source**: `commodity.gold.unified_data`
- 7k rows (Coffee + Sugar, daily from 2015)
- Array-based weather/GDELT features
- All features forward-filled (production-stable)

```sql
-- Load in Databricks
SELECT * FROM commodity.gold.unified_data
WHERE commodity = 'Coffee' AND is_trading_day = 1
ORDER BY date DESC LIMIT 100;
```

**See [docs/GOLD_MIGRATION_GUIDE.md](docs/GOLD_MIGRATION_GUIDE.md) for:**
- Which table to use (production vs experimental)
- Migration examples (SARIMAX, XGBoost, regional models)
- NULL handling and imputation strategies
- Array feature usage patterns

### For Data Engineers (Maintainers)

**See [docs/BUILD_INSTRUCTIONS.md](docs/BUILD_INSTRUCTIONS.md) for:**
- How to rebuild gold tables
- DRY architecture (production derives from raw)
- Validation procedures
- Troubleshooting common issues

## Architecture

### Data Flow

```
AWS Lambda (6 functions, daily 2AM UTC)
  ↓
S3 Landing Zone
  ↓
Databricks Bronze Tables (commodity.bronze.*)
  ↓
Gold Tables (commodity.gold.*)
  └── unified_data (production, forward-filled)
  └── unified_data_raw (experimental, NULLs preserved)
```

**Key Architecture Docs:**
- **[docs/UNIFIED_DATA_ARCHITECTURE.md](docs/UNIFIED_DATA_ARCHITECTURE.md)** - Data joining strategy and unified table design
- **[docs/GOLD_MIGRATION_GUIDE.md](docs/GOLD_MIGRATION_GUIDE.md)** - Gold layer usage guide
- **[docs/DATABRICKS_MIGRATION_GUIDE.md](docs/DATABRICKS_MIGRATION_GUIDE.md)** - Databricks setup and migration
- **[docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)** - Complete data source documentation
- **[docs/GDELT_PROCESSING.md](docs/GDELT_PROCESSING.md)** - GDELT sentiment processing guide

### Infrastructure

**Lambda Functions** (see `infrastructure/lambda/functions/`):
1. `market-data-fetcher` - Coffee/Sugar futures prices
2. `weather-data-fetcher` - Regional weather (65 locations)
3. `vix-data-fetcher` - VIX volatility index
4. `fx-calculator-fetcher` - Exchange rates (24 currencies)
5. `cftc-data-fetcher` - Commitment of Traders reports
6. GDELT pipeline (4 functions) - News sentiment

**Scheduling**: EventBridge rules run daily at 2AM UTC

**See [infrastructure/README.md](infrastructure/README.md) for deployment and monitoring.**

## Directory Structure

```
research_agent/
├── docs/                        # Detailed documentation
│   ├── BUILD_INSTRUCTIONS.md    # How to build gold tables
│   ├── GOLD_MIGRATION_GUIDE.md  # Migration guide for forecast models
│   └── DATABRICKS_MIGRATION_GUIDE.md  # Databricks setup
├── infrastructure/              # AWS Lambda + EventBridge
│   ├── lambda/functions/        # 6 data collection functions
│   ├── eventbridge/             # Daily scheduling (2AM UTC)
│   └── databricks/              # Table creation scripts
├── sql/                         # Gold layer SQL
│   ├── create_gold_unified_data.sql      # Production (forward-filled)
│   └── create_gold_unified_data_raw.sql  # Experimental (NULLs preserved)
├── tests/                       # Testing and validation
│   ├── validation/              # One-time validation scripts
│   ├── health_checks/           # Periodic health checks (planned)
│   └── monitoring/              # Continuous monitoring (planned)
├── notebooks/                   # Data exploration
└── config/                      # Configuration files
```

## Gold Layer Tables (Current Production)

### `commodity.gold.unified_data` (Production)

**Use for**: Production models, stable pipelines
- All features forward-filled (no NULLs except pre-2021 GDELT)
- 7,612 rows (Coffee + Sugar, 2015-2024)
- Weather/GDELT as arrays (65 regions, variable article counts)

### `commodity.gold.unified_data_raw` (Experimental)

**Use for**: New models, experimentation, custom imputation
- Only `close` price forward-filled (all other features preserve NULLs)
- Same 7,612 rows as production
- Includes 3 missingness flags: `has_market_data`, `has_weather_data`, `has_gdelt_data`
- Requires imputation in ML pipelines

**Decision tree**: See [docs/GOLD_MIGRATION_GUIDE.md](docs/GOLD_MIGRATION_GUIDE.md)

## Key Features

**Data Coverage**:
- ✅ Market data: Coffee/Sugar futures (OHLCV)
- ✅ Weather: Temp, humidity, precipitation (65 producer regions)
- ✅ Macro: VIX volatility, 24 FX rates
- ✅ GDELT: News sentiment (post-2021, ~27% daily coverage)
- ⏳ CFTC: Commitment of Traders (collected but not integrated)

**Quality Assurance**:
- Deduplication at bronze layer
- Forward-fill for continuous daily coverage
- Validation suite: `tests/validation/validate_gold_tables.py`

## Common Tasks

### Rebuild Gold Tables

```bash
# Option 1: Databricks SQL Editor (recommended)
# 1. Open Databricks SQL Editor
# 2. Run research_agent/sql/create_gold_unified_data_raw.sql
# 3. Run research_agent/sql/create_gold_unified_data.sql

# Option 2: Python programmatic (from IMPLEMENTATION_COMPLETE.md)
python << 'EOF'
from dotenv import load_dotenv
import os
from databricks import sql

load_dotenv('infra/.env')
connection = sql.connect(
    server_hostname=os.environ['DATABRICKS_HOST'].replace('https://', ''),
    http_path=os.environ['DATABRICKS_HTTP_PATH'],
    access_token=os.environ['DATABRICKS_TOKEN']
)
cursor = connection.cursor()

with open('research_agent/sql/create_gold_unified_data_raw.sql') as f:
    cursor.execute(f.read())
    print('✅ unified_data_raw rebuilt')

with open('research_agent/sql/create_gold_unified_data.sql') as f:
    cursor.execute(f.read())
    print('✅ unified_data rebuilt')

cursor.close()
connection.close()
EOF
```

**See [docs/BUILD_INSTRUCTIONS.md](docs/BUILD_INSTRUCTIONS.md) for detailed instructions.**

### Validate Tables

```bash
python research_agent/tests/validation/validate_gold_tables.py

# Runs 6 comprehensive tests:
# - Row counts
# - NULL rates (production vs raw)
# - Missingness flags
# - GDELT capitalization
# - Sample data inspection
```

### Deploy Lambda Functions

```bash
cd research_agent/infrastructure/lambda/functions/market-data-fetcher
./deploy.sh

# Repeat for other functions as needed
```

**See [infrastructure/README.md](infrastructure/README.md) for complete deployment guide.**

## Data Contracts

**Schema definitions**: See `../../docs/DATA_CONTRACTS.md` for:
- Complete table schemas
- Column descriptions and data types
- Example queries for array fields (weather, GDELT)
- Comparison: production vs raw tables

## Related Documentation

**Detailed Documentation** (in `docs/`):
- [docs/UNIFIED_DATA_ARCHITECTURE.md](docs/UNIFIED_DATA_ARCHITECTURE.md) - Data joining strategy
- [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) - All data sources explained
- [docs/GDELT_PROCESSING.md](docs/GDELT_PROCESSING.md) - GDELT sentiment processing
- [docs/BUILD_INSTRUCTIONS.md](docs/BUILD_INSTRUCTIONS.md) - Build and validate gold tables
- [docs/GOLD_MIGRATION_GUIDE.md](docs/GOLD_MIGRATION_GUIDE.md) - Migration guide for forecast models
- [docs/DATABRICKS_MIGRATION_GUIDE.md](docs/DATABRICKS_MIGRATION_GUIDE.md) - Databricks setup and migration

**Infrastructure**:
- [infrastructure/README.md](infrastructure/README.md) - Lambda deployment and monitoring

**Cross-Agent**:
- `../../docs/DATA_CONTRACTS.md` - Schema contracts (shared)
- `../../collaboration/agent_collaboration/unified_data_null_handling/` - Gold tables collaboration docs

## Collaboration

For collaboration with forecast_agent on gold tables implementation:
- See `../../collaboration/agent_collaboration/unified_data_null_handling/IMPLEMENTATION_COMPLETE.md`

---

**Last Updated**: December 5, 2024
**Current Focus**: Gold layer production tables (DRY architecture, NULL handling)
**Next Milestone**: CFTC integration, automated gold table rebuilds
