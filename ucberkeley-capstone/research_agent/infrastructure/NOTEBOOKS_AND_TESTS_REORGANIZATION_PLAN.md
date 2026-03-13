# Notebooks and Tests Reorganization Plan

**Date**: 2025-12-05
**Purpose**: Consolidate scattered notebooks, tests, and validation scripts into a clean nested structure

---

## 🎯 Current State (The Mess)

### Notebooks (2 folders, 2 files)
```
research_agent/
├── notebooks/                         ← EMPTY (1 empty SQL notebook from Oct 28)
│   └── Data Exploration.dbquery.ipynb
└── databricks_notebooks/              ← ACTIVE (1 Python notebook from Nov 1)
    └── Pipeline_Health_Dashboard.py
```

### Tests/Validation (5 DIFFERENT locations!)
```
research_agent/
├── infrastructure/
│   ├── tests/                         ← Main test folder (25 files, mixed)
│   │   ├── test_*.py (5 files)       - Unit tests for pipeline
│   │   ├── validate_*.py (11 files)  - Validation scripts
│   │   ├── check_*.py (6 files)      - Health checks
│   │   ├── temp/                     - Temporary debug scripts (5 files)
│   │   ├── README.md
│   │   └── GOLD_UNIFIED_DATA_VALIDATION.md
│   │
│   ├── validation/                    ← Separate validation folder
│   │   ├── continuous/
│   │   │   ├── health_checks.py
│   │   │   └── run_health_checks_job.py
│   │   └── one_time/
│   │       └── validate_historical_data.py
│   │
│   ├── databricks/
│   │   └── validate_gold_unified_data.py  ← Duplicate?
│   │
│   └── scripts/
│       ├── test_lambda.py
│       └── clear_test_environment.py
│
├── tests/                             ← YET ANOTHER test folder!
│   ├── validation/
│   │   └── validate_gold_tables.py
│   ├── health_checks/  (empty)
│   ├── monitoring/  (empty)
│   └── README.md
│
└── weather_migration_phase8_validation.py  ← Root level!
```

---

## 🎨 Proposed Clean Structure (By Scope & Purpose)

### Option A: Organize by Layer + Purpose (Recommended)

```
research_agent/
├── notebooks/                         ← Databricks notebooks by purpose
│   ├── exploration/
│   │   └── Data_Exploration.ipynb (cleanup or delete)
│   ├── monitoring/
│   │   └── Pipeline_Health_Dashboard.py
│   └── validation/
│       └── (future: Databricks-native validation notebooks)
│
├── tests/                             ← All test/validation by SCOPE
│   ├── unit/                          ← Unit tests for specific components
│   │   ├── test_pipeline.py
│   │   ├── test_unified_data.py
│   │   ├── test_forecast_schema.py
│   │   └── test_forecast_api_guide.py
│   │
│   ├── integration/                   ← End-to-end pipeline tests
│   │   ├── test_full_pipeline.py
│   │   └── validate_full_pipeline.py
│   │
│   ├── data_quality/                  ← Gold/Silver/Bronze validation
│   │   ├── gold/
│   │   │   ├── validate_gold_unified_data.py
│   │   │   └── validate_gold_databricks.py
│   │   ├── silver/
│   │   │   └── (future silver validation)
│   │   └── bronze/
│   │       └── check_databricks_tables.py
│   │
│   ├── health_checks/                 ← Continuous monitoring
│   │   ├── health_checks.py (from validation/continuous/)
│   │   ├── run_health_checks_job.py
│   │   ├── check_catalog_structure.py
│   │   └── check_gdelt_data.py
│   │
│   ├── domain/                        ← Domain-specific validation
│   │   ├── weather/
│   │   │   ├── validate_region_coordinates.py
│   │   │   ├── validate_weather_pipeline.py
│   │   │   ├── check_sugar_weather.py
│   │   │   └── weather_migration_phase8_validation.py
│   │   ├── market/
│   │   │   └── check_landing_sugar.py
│   │   ├── gdelt/
│   │   │   └── (future GDELT specific tests)
│   │   └── forecast/
│   │       ├── validate_july2021_frost.py
│   │       └── check_forecast_schemas.py
│   │
│   ├── utilities/                     ← Test utilities and helpers
│   │   ├── test_lambda.py
│   │   ├── clear_test_environment.py
│   │   └── (future: test fixtures, mocks)
│   │
│   ├── archived/                      ← One-time or obsolete tests
│   │   ├── one_time/
│   │   │   └── validate_historical_data.py
│   │   └── temp/                      ← Debug scripts (review & delete)
│   │       ├── quick_validate_gold.py
│   │       ├── validate_gdelt_fix.py
│   │       ├── check_commodity_mismatch.py
│   │       ├── check_gdelt_source.py
│   │       └── debug_gdelt_join.py
│   │
│   └── README.md                      ← Master test documentation
│
└── infrastructure/
    ├── databricks/
    │   └── (no more validation scripts here)
    ├── scripts/
    │   └── (no more test scripts here)
    └── validation/
        └── (DELETE - consolidated into tests/)
```

---

## 📋 File-by-File Categorization

### Notebooks (2 files)

| Current Location | File | Last Modified | Purpose | Action |
|-----------------|------|---------------|---------|--------|
| research_agent/notebooks/ | Data Exploration.dbquery.ipynb | Oct 28 | EMPTY SQL notebook | ❓ Delete or move to notebooks/exploration/ |
| research_agent/databricks_notebooks/ | Pipeline_Health_Dashboard.py | Nov 1 | Active monitoring dashboard | ✅ Move to notebooks/monitoring/ |

### Tests - Unit Tests (5 files)

| Current Location | File | Purpose | New Location |
|-----------------|------|---------|--------------|
| infrastructure/tests/ | test_pipeline.py | Unit test for pipeline | tests/unit/ |
| infrastructure/tests/ | test_unified_data.py | Unit test for unified data | tests/unit/ |
| infrastructure/tests/ | test_forecast_schema.py | Forecast schema validation | tests/unit/ |
| infrastructure/tests/ | test_forecast_api_guide.py | API guide testing | tests/unit/ |
| infrastructure/tests/ | test_full_pipeline.py | End-to-end pipeline test | tests/integration/ |

### Tests - Data Quality Validation (11 files)

| Current Location | File | Purpose | New Location |
|-----------------|------|---------|--------------|
| infrastructure/tests/ | validate_gold_unified_data.py | Gold table validation | tests/data_quality/gold/ |
| infrastructure/databricks/ | validate_gold_unified_data.py | **DUPLICATE?** | ⚠️ Check if duplicate, consolidate |
| infrastructure/tests/ | validate_gold_databricks.py | Gold Databricks validation | tests/data_quality/gold/ |
| research_agent/tests/validation/ | validate_gold_tables.py | Another gold validation | ⚠️ Consolidate with above |
| infrastructure/tests/ | validate_data_quality.py | General data quality | tests/data_quality/ |
| infrastructure/tests/ | validate_full_pipeline.py | Full pipeline validation | tests/integration/ |
| infrastructure/tests/ | validate_pipeline.py | Pipeline validation | tests/integration/ |
| infrastructure/tests/ | validate_unified_data_inputs.py | Unified data inputs | tests/data_quality/ |
| infrastructure/tests/ | validate_weather_pipeline.py | Weather pipeline | tests/domain/weather/ |
| infrastructure/tests/ | validate_region_coordinates.py | Region coordinates | tests/domain/weather/ |
| research_agent/ (root!) | weather_migration_phase8_validation.py | Weather migration validation | tests/domain/weather/ or archive |

### Tests - Health Checks (6 files)

| Current Location | File | Purpose | New Location |
|-----------------|------|---------|--------------|
| infrastructure/tests/ | check_catalog_structure.py | Catalog structure check | tests/health_checks/ |
| infrastructure/tests/ | check_databricks_tables.py | Databricks tables check | tests/data_quality/bronze/ |
| infrastructure/tests/ | check_forecast_schemas.py | Forecast schema check | tests/domain/forecast/ |
| infrastructure/tests/ | check_gdelt_data.py | GDELT data check | tests/health_checks/ |
| infrastructure/tests/ | check_landing_sugar.py | Sugar landing check | tests/domain/market/ |
| infrastructure/tests/ | check_sugar_weather.py | Sugar weather check | tests/domain/weather/ |

### Tests - Continuous Monitoring (2 files)

| Current Location | File | Purpose | New Location |
|-----------------|------|---------|--------------|
| infrastructure/validation/continuous/ | health_checks.py | Continuous health checks | tests/health_checks/ |
| infrastructure/validation/continuous/ | run_health_checks_job.py | Job runner | tests/health_checks/ |

### Tests - One-Time/Historical (1 file)

| Current Location | File | Purpose | New Location |
|-----------------|------|---------|--------------|
| infrastructure/validation/one_time/ | validate_historical_data.py | Historical validation | tests/archived/one_time/ |

### Tests - Temp/Debug Scripts (5 files - REVIEW & DELETE)

| Current Location | File | Purpose | Action |
|-----------------|------|---------|--------|
| infrastructure/tests/temp/ | quick_validate_gold.py | Quick gold validation | ⚠️ If still needed → tests/data_quality/gold/, else DELETE |
| infrastructure/tests/temp/ | validate_gdelt_fix.py | GDELT fix validation | ❓ If issue fixed → DELETE |
| infrastructure/tests/temp/ | check_commodity_mismatch.py | Commodity mismatch debug | ❓ If issue fixed → DELETE |
| infrastructure/tests/temp/ | check_gdelt_source.py | GDELT source debug | ❓ If issue fixed → DELETE |
| infrastructure/tests/temp/ | debug_gdelt_join.py | GDELT join debug | ❓ If issue fixed → DELETE |

### Tests - Utilities (2 files)

| Current Location | File | Purpose | New Location |
|-----------------|------|---------|--------------|
| infrastructure/scripts/ | test_lambda.py | Lambda testing utility | tests/utilities/ |
| infrastructure/scripts/ | clear_test_environment.py | Test env cleanup | tests/utilities/ |

### Domain-Specific (2 files)

| Current Location | File | Purpose | New Location |
|-----------------|------|---------|--------------|
| infrastructure/tests/ | validate_july2021_frost.py | July 2021 frost event validation | tests/domain/forecast/ |
| infrastructure/tests/ | check_forecast_schemas.py | Forecast schema check | tests/domain/forecast/ |

---

## 🚀 Migration Plan

### Phase 1: Create New Structure (Low Risk)

```bash
cd research_agent

# Create new test structure
mkdir -p tests/unit
mkdir -p tests/integration
mkdir -p tests/data_quality/{gold,silver,bronze}
mkdir -p tests/health_checks
mkdir -p tests/domain/{weather,market,gdelt,forecast}
mkdir -p tests/utilities
mkdir -p tests/archived/{one_time,temp}

# Create new notebook structure
mkdir -p notebooks/{exploration,monitoring,validation}
```

### Phase 2: Move Notebooks (Zero Risk)

```bash
# Move active monitoring notebook
mv databricks_notebooks/Pipeline_Health_Dashboard.py \
   notebooks/monitoring/

# Handle empty notebook (DECIDE: move or delete)
# Option A: Delete
rm notebooks/Data\ Exploration.dbquery.ipynb
# Option B: Move
mv notebooks/Data\ Exploration.dbquery.ipynb \
   notebooks/exploration/

# Remove old folders
rmdir databricks_notebooks/
# rmdir notebooks/ (only if we deleted the empty notebook)
```

### Phase 3: Consolidate Duplicate Validation Scripts (CRITICAL)

```bash
# Check if these are duplicates
diff infrastructure/tests/validate_gold_unified_data.py \
     infrastructure/databricks/validate_gold_unified_data.py

diff infrastructure/tests/validate_gold_databricks.py \
     tests/validation/validate_gold_tables.py

# If duplicates → keep BEST version (likely infrastructure/tests/)
# If different → understand purpose, then consolidate
```

### Phase 4: Move Tests by Category

```bash
# Unit tests
mv infrastructure/tests/test_pipeline.py tests/unit/
mv infrastructure/tests/test_unified_data.py tests/unit/
mv infrastructure/tests/test_forecast_schema.py tests/unit/
mv infrastructure/tests/test_forecast_api_guide.py tests/unit/

# Integration tests
mv infrastructure/tests/test_full_pipeline.py tests/integration/
mv infrastructure/tests/validate_full_pipeline.py tests/integration/
mv infrastructure/tests/validate_pipeline.py tests/integration/

# Data quality - Gold
mv infrastructure/tests/validate_gold_unified_data.py tests/data_quality/gold/
mv infrastructure/tests/validate_gold_databricks.py tests/data_quality/gold/
# (After consolidating duplicates)

# Data quality - Bronze
mv infrastructure/tests/check_databricks_tables.py tests/data_quality/bronze/

# Health checks
mv infrastructure/tests/check_catalog_structure.py tests/health_checks/
mv infrastructure/tests/check_gdelt_data.py tests/health_checks/
mv infrastructure/validation/continuous/health_checks.py tests/health_checks/
mv infrastructure/validation/continuous/run_health_checks_job.py tests/health_checks/

# Domain - Weather
mv infrastructure/tests/validate_weather_pipeline.py tests/domain/weather/
mv infrastructure/tests/validate_region_coordinates.py tests/domain/weather/
mv infrastructure/tests/check_sugar_weather.py tests/domain/weather/
mv weather_migration_phase8_validation.py tests/domain/weather/

# Domain - Market
mv infrastructure/tests/check_landing_sugar.py tests/domain/market/

# Domain - Forecast
mv infrastructure/tests/validate_july2021_frost.py tests/domain/forecast/
mv infrastructure/tests/check_forecast_schemas.py tests/domain/forecast/

# Utilities
mv infrastructure/scripts/test_lambda.py tests/utilities/
mv infrastructure/scripts/clear_test_environment.py tests/utilities/

# Archived - One-time
mv infrastructure/validation/one_time/validate_historical_data.py tests/archived/one_time/

# Archived - Temp (REVIEW FIRST)
mv infrastructure/tests/temp/*.py tests/archived/temp/
```

### Phase 5: Move Documentation & Cleanup

```bash
# Move test documentation
mv infrastructure/tests/README.md tests/README.md
mv infrastructure/tests/GOLD_UNIFIED_DATA_VALIDATION.md tests/data_quality/gold/

# Remove empty folders
rmdir infrastructure/tests/temp/
rmdir infrastructure/tests/
rmdir infrastructure/validation/continuous/
rmdir infrastructure/validation/one_time/
rmdir infrastructure/validation/
rmdir tests/validation/  # Old location
rmdir tests/health_checks/  # If was empty
rmdir tests/monitoring/  # If was empty
```

---

## 📝 Documentation Updates

### New tests/README.md

```markdown
# Research Agent Tests

Comprehensive test suite for the research agent data pipeline.

## Structure

- **unit/** - Unit tests for individual components
- **integration/** - End-to-end pipeline tests
- **data_quality/** - Data validation by layer (gold/silver/bronze)
- **health_checks/** - Continuous monitoring scripts
- **domain/** - Domain-specific tests (weather, market, gdelt, forecast)
- **utilities/** - Test helpers and utilities
- **archived/** - One-time or obsolete tests

## Running Tests

### All Unit Tests
```bash
pytest tests/unit/
```

### All Integration Tests
```bash
pytest tests/integration/
```

### Data Quality Validation
```bash
python tests/data_quality/gold/validate_gold_unified_data.py
```

### Health Checks
```bash
python tests/health_checks/health_checks.py
```

## Naming Conventions

- `test_*.py` - Pytest unit tests
- `validate_*.py` - Data validation scripts (can run standalone)
- `check_*.py` - Health check scripts (Databricks or S3)
```

---

## ⚠️ Risks & Mitigation

**Risk 1: Breaking imports**
- **Mitigation**: Most validation scripts are standalone (no imports)
- **Action**: Search for any cross-references before moving

**Risk 2: Duplicate files serving different purposes**
- **Mitigation**: Diff files before consolidating
- **Action**: Phase 3 explicitly checks duplicates

**Risk 3: Active Databricks jobs referencing old paths**
- **Mitigation**: Check Databricks job configurations
- **Action**: Update job paths after moving

**Risk 4: Deleting temp scripts that are still useful**
- **Mitigation**: Review each temp script before deleting
- **Action**: Phase 4 moves to archived/temp first, delete later

---

## 🎯 Benefits

**Clarity:**
- Single `tests/` folder with clear hierarchy
- Purpose-based organization (unit vs integration vs validation)
- Domain-specific tests grouped together

**Discoverability:**
- Easy to find what you need
- Clear what's active vs archived
- Obvious where to add new tests

**Maintainability:**
- No more scattered validation scripts
- Consolidated duplicates
- Clean notebook organization

---

## 📊 Summary

| Action | Count | Details |
|--------|-------|---------|
| **Notebooks** | 2 files | Reorganize into notebooks/{exploration,monitoring} |
| **Tests to move** | ~35 files | Consolidate from 5 locations → 1 clean structure |
| **Duplicates to check** | 2-3 files | validate_gold_unified_data.py, validate_gold_tables.py |
| **Temp scripts to review** | 5 files | Decide: archive or delete |
| **Empty folders to delete** | 7+ folders | Clean up after migration |

**Estimated time**: 30 minutes
**Git commits**: 2-3 (by phase)

---

## 🚦 Next Steps

1. **Review temp scripts** (infrastructure/tests/temp/) - Decide keep vs delete
2. **Check duplicates** - Diff validate_gold_* files
3. **Execute Phase 1-2** - Low risk (new folders + notebooks)
4. **Execute Phase 3** - Critical (consolidate duplicates)
5. **Execute Phase 4-5** - Move tests & cleanup
6. **Update documentation** - New tests/README.md
7. **Git commit** - Atomic commit with clear message

---

**Document Owner**: Research Agent
**Last Updated**: 2025-12-05
**Purpose**: Consolidate scattered tests/notebooks into clean hierarchical structure
