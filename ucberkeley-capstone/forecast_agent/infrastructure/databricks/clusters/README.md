# Databricks Cluster Configuration

**Purpose**: Code-based, repeatable setup for deploying forecast_agent to Databricks clusters.

---

## Two Approaches

### Option 1: Wheel Package Installation (Recommended)

**Cleanest approach** - Install forecast_agent as a proper Python package on the cluster.

**Pros**:
- ✅ Imports work normally: `from forecast_agent.ml_lib.transformers import create_production_imputer`
- ✅ Package versioning and dependencies managed
- ✅ No manual module loading in notebooks
- ✅ Works across all notebooks automatically

**Cons**:
- Requires cluster restart to activate
- Slightly more setup time

**Steps**:
```bash
cd forecast_agent
python infrastructure/databricks/clusters/deploy_package.py
```

---

### Option 2: Source File Upload (Lightweight Alternative)

**Lightweight approach** - Upload .py files and use importlib pattern (like DS261).

**Pros**:
- ✅ No cluster restart needed
- ✅ Instant deployment
- ✅ Good for rapid iteration

**Cons**:
- Requires importlib boilerplate in each notebook

**Steps**:
```bash
cd forecast_agent
python infrastructure/databricks/clusters/upload_source_files.py
```

---

## Recommendation

**Use Option 1 (deploy_package.py)** - Production-ready, clean imports

**Use Option 2 (upload_source_files.py)** - Quick experiments, rapid iteration

---

**Last Updated**: December 5, 2024
