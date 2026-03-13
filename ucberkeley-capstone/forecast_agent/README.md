# Forecast Agent

Machine learning system for coffee price forecasting with 14-day horizon. Generates probabilistic forecasts (2,000 Monte Carlo paths) and point predictions with uncertainty quantification.

---

## 🚀 NEW: ml_lib Pipeline (Dec 2024)

**Modern PySpark-based forecasting framework** with gold table integration and intelligent model selection.

### Quick Start (3 Steps)

```python
# 1. Load gold table (90% fewer rows than silver!)
from forecast_agent.ml_lib.cross_validation.data_loader import GoldDataLoader

loader = GoldDataLoader()  # Defaults to commodity.gold.unified_data
df = loader.load(commodity='Coffee')

# 2. Optional: Use raw table with custom imputation
from forecast_agent.ml_lib.transformers import create_production_imputer

loader_raw = GoldDataLoader(table_name='commodity.gold.unified_data_raw')
df_raw = loader_raw.load(commodity='Coffee')

imputer = create_production_imputer()
df_imputed = imputer.transform(df_raw)
df_imputed.cache()  # CRITICAL for 2-3x speedup!
df_imputed.count()

# 3. Fit models (cross-validation framework)
# from forecast_agent.ml_lib.cross_validation import TimeSeriesForecastCV
# cv = TimeSeriesForecastCV(n_folds=5, horizon=14)
# results = cv.fit(df_imputed)
```

### Key Features

✅ **Gold Tables** - 90% row reduction vs silver (7k vs 75k rows)
✅ **ImputationTransformer** - Flexible NULL handling (4 strategies)
✅ **forecast_testing Schema** - Isolated testing before production
✅ **Fit Many, Publish Few** - Test 200+ configs, publish top ~15 (93% compute savings!)

### Documentation

- **Quick Start**: [ml_lib/QUICKSTART.md](ml_lib/QUICKSTART.md) - 3-step workflow, table selection guide
- **Validation**: [ml_lib/VALIDATION_WORKFLOW.md](ml_lib/VALIDATION_WORKFLOW.md) - 5-phase validation plan
- **Selection**: [ml_lib/MODEL_SELECTION_STRATEGY.md](ml_lib/MODEL_SELECTION_STRATEGY.md) - Fit many, publish few
- **Migration**: [../research_agent/docs/GOLD_MIGRATION_GUIDE.md](../research_agent/docs/GOLD_MIGRATION_GUIDE.md) - Silver → Gold migration
- **Data Contracts**: [../docs/DATA_CONTRACTS.md](../docs/DATA_CONTRACTS.md) - Schema details

### Data Sources (Gold Tables - Recommended)

| Table | Use Case | Rows | NULLs | Imputation Required |
|-------|----------|------|-------|---------------------|
| `commodity.gold.unified_data` | Production, stable pipelines | 7,612 | None (forward-filled) | ❌ No |
| `commodity.gold.unified_data_raw` | Experimentation, new models | 7,612 | ~30% market data, ~73% GDELT | ✅ Yes (ImputationTransformer) |
| `commodity.silver.unified_data` | Legacy (deprecated Q1 2025) | 75,000 | None | ❌ No |

**Choose gold.unified_data** if: Production models, proven data, no imputation needed
**Choose gold.unified_data_raw** if: New models, custom imputation, experimenting

### Testing Schema (forecast_testing)

Isolate experimentation from production:

```python
# Test in forecast_testing (safe)
save_results(schema='commodity.forecast_testing', results)

# After validation → promote to production
promote_to_production(selected_models, from_schema='forecast_testing')
```

**Tables**:
- `commodity.forecast_testing.distributions`
- `commodity.forecast_testing.point_forecasts`
- `commodity.forecast_testing.model_metadata`
- `commodity.forecast_testing.validation_results` (tracks test outcomes)

**Setup**: `python setup_testing_schema.py`

### Model Selection Strategy

**Problem**: Fitting 200 configs and publishing all → trading agent tests 200 forecasts (explosion!)

**Solution**: **Fit Many, Publish Few**

1. **Experiment**: Fit 200+ configs in `forecast_testing`
2. **Evaluate**: Measure DA, MAE, stability
3. **Select**: Choose top ~15 diverse models (SQL-based selection)
4. **Backfill**: Only backfill selected 15 (93% compute savings!)
5. **Publish**: Promote to `commodity.forecast` (production)

**Benefits**:
- Compute: 4,800 hours → 360 hours (93% reduction)
- Trading agent: Test 15 curated forecasts (not 200)
- Production: Clean, interpretable ensemble
- Experimentation: Freedom without production impact

See [ml_lib/MODEL_SELECTION_STRATEGY.md](ml_lib/MODEL_SELECTION_STRATEGY.md) for detailed selection criteria.

---

## Project Structure

```
forecast_agent/
├── README.md                         # This file
├── ml_lib/                           # Modern PySpark forecasting framework
│   ├── transformers/                 # ImputationTransformer, feature engineering
│   ├── cross_validation/             # TimeSeriesForecastCV, data loaders
│   ├── models/                       # Model implementations
│   ├── QUICKSTART.md                 # 3-step workflow guide
│   ├── VALIDATION_WORKFLOW.md        # 5-phase validation
│   └── MODEL_SELECTION_STRATEGY.md   # Fit many, publish few
│
├── docs/                             # Architecture documentation
│   ├── FORECASTING_EVOLUTION.md      # V1 → V2 → V3 progression
│   ├── ARCHITECTURE.md               # Train-once/inference-many pattern
│   └── SPARK_BACKFILL_GUIDE.md       # Parallel processing
│
├── infrastructure/                   # Deployment automation
│   └── databricks/
│       ├── clusters/                 # Cluster config, package deployment
│       └── sql/                      # Schema definitions
│
├── notebooks/                        # Databricks notebooks
├── tests/                            # Unit tests
├── deprecated/                       # Legacy ground_truth pipeline (archived)
└── setup.py                          # Package configuration
```

## Output Tables

All tables in `commodity.forecast` schema:

**`distributions`**
- 2,000 Monte Carlo paths per forecast
- Columns: day_1 through day_14, path_id (0-1999)

**`point_forecasts`**
- 14-day forecasts with prediction intervals
- Columns: day_1 through day_14, actual_close

**`model_metadata`**
- Model performance metrics (MAE, RMSE, Dir Day0)

**Testing Schema** (`commodity.forecast_testing`):
- Parallel structure for safe experimentation
- Setup: `python setup_testing_schema.py`

## Key Metrics

- **MAE** (Mean Absolute Error): Average prediction error in dollars
- **RMSE** (Root Mean Squared Error): Penalizes large errors
- **Dir Day0**: Directional accuracy from day 0 (primary trading metric)
  - Measures: Is day i > day 0? (trading signal quality)

## Environment Setup

### Databricks Credentials
Load credentials from `../infra/.env`:
```bash
cd forecast_agent
set -a && source ../infra/.env && set +a
```

Required environment variables:
- `DATABRICKS_HOST` - Databricks workspace URL
- `DATABRICKS_TOKEN` - Personal access token

### Deploy Package to Databricks
```bash
# Build wheel, upload to DBFS, install on cluster
python infrastructure/databricks/clusters/deploy_package.py
```

## Legacy Code

**⚠️ The previous ground_truth pipeline is deprecated** (Dec 6, 2024)

All legacy code has been moved to `deprecated/` folder. For historical context and the evolution from V1 → V2 → V3, see:

- **[docs/FORECASTING_EVOLUTION.md](docs/FORECASTING_EVOLUTION.md)** - Complete progression history, lessons learned, presentation highlights
- **[deprecated/README.md](deprecated/README.md)** - Legacy code inventory

**Key Evolution**:
- V1: Retrain-per-forecast (24-48 hours)
- V2: Train-once/inference-many (1-2 hours, 180x speedup)
- V3: ml_lib + "fit many, publish few" (93% compute savings, 90% fewer rows)

## Documentation

**Current (ml_lib)**:
- **[ml_lib/QUICKSTART.md](ml_lib/QUICKSTART.md)** - 3-step workflow, table selection guide
- **[ml_lib/VALIDATION_WORKFLOW.md](ml_lib/VALIDATION_WORKFLOW.md)** - 5-phase validation plan
- **[ml_lib/MODEL_SELECTION_STRATEGY.md](ml_lib/MODEL_SELECTION_STRATEGY.md)** - Selection criteria

**Architecture**:
- **[docs/FORECASTING_EVOLUTION.md](docs/FORECASTING_EVOLUTION.md)** - V1 → V2 → V3 progression
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Train-once/inference-many pattern
- **[infrastructure/databricks/clusters/README.md](infrastructure/databricks/clusters/README.md)** - Deployment guide

**Data**:
- **[../research_agent/docs/GOLD_MIGRATION_GUIDE.md](../research_agent/docs/GOLD_MIGRATION_GUIDE.md)** - Silver → Gold migration
- **[../docs/DATA_CONTRACTS.md](../docs/DATA_CONTRACTS.md)** - Schema details
