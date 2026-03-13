# Research Agent - Data Pipeline Patterns

**Ownership:** Shared among all team members

---

## Before Working

Read [README.md](README.md) → [docs/UNIFIED_DATA_ARCHITECTURE.md](docs/UNIFIED_DATA_ARCHITECTURE.md) first

---

## Critical Rules

**1. Testing Organization**
```
tests/
├── validation/       # One-time validation after major changes
├── health_checks/    # Periodic health checks
└── data_quality/     # Bronze/silver/gold layer checks
```

**2. Update Documentation When Needed**
- Adding data source → Update [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)
- Changing gold schema → Update [docs/UNIFIED_DATA_ARCHITECTURE.md](docs/UNIFIED_DATA_ARCHITECTURE.md)
- Building gold tables → See [docs/BUILD_INSTRUCTIONS.md](docs/BUILD_INSTRUCTIONS.md)

**3. Lambda Deployment**
```bash
cd infrastructure/lambda/functions/market-data-fetcher
./deploy.sh
```

**4. Validate Before Rebuilding Gold**
```bash
# Check bronze quality first
python tests/data_quality/bronze/check_databricks_tables.py
# Then rebuild gold tables
```

---

## Key Patterns

- **Lambda RUN_MODE** - HISTORICAL (backfill) vs INCREMENTAL (daily)
- **Array-based gold** - Weather/GDELT as arrays (90% row reduction)
- **Data flow** - S3 → Bronze → Gold → Forecasts
