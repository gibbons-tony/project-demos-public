# Research Agent Tests

Comprehensive test suite for the research agent data pipeline, organized by scope and purpose.

---

## 📁 Directory Structure

```
tests/
├── unit/                  # Unit tests for specific components
├── integration/           # End-to-end pipeline tests
├── data_quality/          # Data validation by layer
│   ├── gold/             # Gold layer validation
│   ├── silver/           # Silver layer validation (future)
│   └── bronze/           # Bronze layer checks
├── health_checks/         # Continuous monitoring scripts
├── domain/                # Domain-specific tests
│   ├── weather/          # Weather data validation
│   ├── market/           # Market data validation
│   ├── gdelt/            # GDELT data validation (future)
│   └── forecast/         # Forecast-specific tests
├── utilities/             # Test helpers and utilities
└── archived/              # One-time or obsolete tests
    ├── one_time/         # Historical validation
    └── temp/             # Debug scripts (review & clean)
```

---

## 🚀 Running Tests

### Unit Tests (pytest)
```bash
# Run all unit tests
pytest tests/unit/

# Run specific test
pytest tests/unit/test_pipeline.py
pytest tests/unit/test_unified_data.py
pytest tests/unit/test_forecast_schema.py
```

### Integration Tests
```bash
# Full end-to-end pipeline
python tests/integration/test_full_pipeline.py
python tests/integration/validate_full_pipeline.py

# Pipeline components
python tests/integration/validate_pipeline.py
```

### Data Quality Validation

**Gold Layer:**
```bash
# Comprehensive gold table validation (standalone Python)
python tests/data_quality/gold/validate_gold_unified_data.py

# Databricks notebook version
python tests/data_quality/gold/validate_gold_unified_data_notebook.py

# Alternative gold validation
python tests/data_quality/gold/validate_gold_databricks.py
python tests/data_quality/gold/validate_gold_tables.py
```

**General:**
```bash
python tests/data_quality/validate_data_quality.py
python tests/data_quality/validate_unified_data_inputs.py
```

**Bronze Layer:**
```bash
python tests/data_quality/bronze/check_databricks_tables.py
```

### Health Checks (Continuous Monitoring)
```bash
# Comprehensive health checks
python tests/health_checks/health_checks.py

# Run as Databricks job
python tests/health_checks/run_health_checks_job.py

# Individual checks
python tests/health_checks/check_catalog_structure.py
python tests/health_checks/check_gdelt_data.py
```

### Domain-Specific Tests

**Weather:**
```bash
# Weather pipeline validation
python tests/domain/weather/validate_weather_pipeline.py

# Region coordinates validation
python tests/domain/weather/validate_region_coordinates.py

# Sugar weather checks
python tests/domain/weather/check_sugar_weather.py

# Weather v2 migration validation
python tests/domain/weather/weather_migration_phase8_validation.py
```

**Market:**
```bash
# Sugar landing data
python tests/domain/market/check_landing_sugar.py
```

**Forecast:**
```bash
# July 2021 frost event validation
python tests/domain/forecast/validate_july2021_frost.py

# Forecast schema checks
python tests/domain/forecast/check_forecast_schemas.py
```

### Utilities
```bash
# Test Lambda functions
python tests/utilities/test_lambda.py

# Clear test environment
python tests/utilities/clear_test_environment.py
```

---

## 📝 Naming Conventions

- **`test_*.py`** - Pytest unit tests (use pytest to run)
- **`validate_*.py`** - Data validation scripts (standalone Python)
- **`check_*.py`** - Health check / infrastructure validation

---

## 🔧 Test Configuration

- **Credentials**: All tests load from `../.env` or environment variables
- **Read-only**: Tests are safe to run in production (no writes)
- **Run after**: Major pipeline changes, data migrations, schema updates

---

## 📊 Quick Reference

| Test Type | Location | Purpose | Run Frequency |
|-----------|----------|---------|---------------|
| Unit | `tests/unit/` | Component validation | On code changes |
| Integration | `tests/integration/` | End-to-end pipeline | Daily/weekly |
| Data Quality | `tests/data_quality/` | Gold/Silver/Bronze validation | After data updates |
| Health Checks | `tests/health_checks/` | Continuous monitoring | Scheduled (hourly/daily) |
| Domain | `tests/domain/` | Domain-specific validation | As needed |

---

## 📌 Related Documentation

- **Gold Layer Validation**: `tests/data_quality/gold/GOLD_UNIFIED_DATA_VALIDATION.md`
- **Pipeline Dependency Graph**: `../infrastructure/GOLD_UNIFIED_DATA_DEPENDENCY_GRAPH.md`
- **Data Sources**: `../docs/DATA_SOURCES.md`

---

## 🗂️ Archived Tests

Tests in `tests/archived/` are either:
- **one_time/**: Historical validation (kept for reference)
- **temp/**: Debug scripts (review & delete if issue resolved)

Review archived tests periodically and delete if no longer needed.

---

**Last Updated**: 2025-12-05
**Maintained By**: Research Agent Team
