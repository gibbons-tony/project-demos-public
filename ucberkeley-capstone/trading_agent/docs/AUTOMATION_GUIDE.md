# Trading Agent Automation Guide

**Purpose:** Complete guide for automated execution of trading analysis workflows
**Status:** Production patterns proven with diagnostics (16/17/100)
**Last Updated:** 2025-11-24

---

## Overview

This guide documents the proven automation patterns for executing trading analysis workflows on Databricks without manual intervention. The patterns were successfully implemented for diagnostics and are being extended to the main workflow.

---

## Proven Automation Pattern

### Pattern: Script + Jobs API

**Successfully used by:**
- `diagnostics/run_diagnostic_16.py` - Parameter optimization
- `diagnostics/run_diagnostic_17.py` - Trade-by-trade analysis
- `diagnostics/run_diagnostic_100.py` - Algorithm validation

**Key Components:**
1. Python script with `main()` function
2. JSON job definition
3. Databricks Jobs API submission
4. Results saved to `/Volumes/`

### Example: Diagnostic 16

```python
# run_diagnostic_16.py
def main():
    # Load data from Delta tables
    # Run Optuna optimization
    # Save results to volume
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
```

```bash
# Submit job
databricks jobs submit --json @job_diagnostic_16.json

# Monitor
databricks jobs get-run <RUN_ID>

# Download results
databricks fs cp dbfs:/Volumes/.../diagnostic_16_best_params.pkl ./
```

---

## Job Submission

### Job Definition Template

```json
{
  "run_name": "workflow_name",
  "tasks": [{
    "task_key": "main_task",
    "spark_python_task": {
      "python_file": "file:///Workspace/Repos/.../script.py",
      "parameters": ["--commodity", "coffee", "--model", "xgboost"]
    },
    "existing_cluster_id": "1111-041828-yeu2ff2q",
    "libraries": []
  }]
}
```

### Submission Commands

```bash
# Submit single job
databricks jobs submit --json @job_config.json

# Get run status
databricks jobs get-run <RUN_ID>

# Get output
databricks jobs get-run-output <RUN_ID>

# List recent runs
databricks jobs list-runs --limit 10
```

---

## Orchestration Patterns

### Sequential Execution

```python
# run_workflow.py
def run_sequential():
    # Step 1: Generate predictions
    run_id_01 = submit_job('run_01_synthetic_predictions.py')
    wait_for_completion(run_id_01)

    # Step 2: Run backtests
    run_id_05 = submit_job('run_05_strategy_comparison.py')
    wait_for_completion(run_id_05)

    # Step 3: Statistical validation
    run_id_06 = submit_job('run_06_statistical_validation.py')
    wait_for_completion(run_id_06)
```

### Parallel Execution

```python
def run_parallel():
    # Run analysis notebooks in parallel
    run_ids = []
    for script in ['run_06', 'run_07', 'run_08', 'run_09']:
        run_id = submit_job(f'{script}.py')
        run_ids.append(run_id)

    wait_for_all(run_ids)
```

---

## Data Access Patterns

**For complete Databricks data access patterns, connection details, and querying:**
See [DATABRICKS_GUIDE.md](DATABRICKS_GUIDE.md)

**Key automation points:**
- Always query Delta tables (not CSVs)
- Save results to `/Volumes/` (persistent storage)
- Never use `/dbfs/` or workspace storage (ephemeral)

---

## Monitoring and Logging

### Job Monitoring Dashboard

```python
# monitor_jobs.py
from databricks import sdk

w = sdk.WorkspaceClient()

jobs = w.jobs.list_runs(limit=20)
for run in jobs:
    print(f"{run.run_name}: {run.state.life_cycle_state}")
    if run.state.result_state == "FAILED":
        print(f"  Error: {run.state.state_message}")
```

### Logging Structure

```
/Volumes/commodity/trading_agent/logs/
├── run_01_synthetic_predictions_2025-11-24_10-30.log
├── run_05_strategy_comparison_2025-11-24_11-00.log
└── run_06_statistical_validation_2025-11-24_12-00.log
```

**Log contents:**
- Execution start/end timestamps
- Parameters used
- Data loaded (row counts, date ranges)
- Results produced (file paths, metrics)
- Errors/warnings
- Performance stats (runtime, memory)

---

## Notebook to Script Conversion

### Conversion Checklist

1. **Extract logic** from notebook cells
2. **Remove magic commands** (`%run`, `display()`, etc.)
3. **Add proper imports** and path handling
4. **Wrap in `main()` function**
5. **Add error handling** and logging
6. **Test locally** if possible
7. **Commit and push** to git
8. **Update Databricks repo**
9. **Submit test job**
10. **Verify outputs**

### Common Conversions

| Notebook | Script Equivalent |
|----------|-------------------|
| `%run notebook` | `from module import *` |
| `display(df)` | `print(df.head())` |
| `dbutils.fs.cp()` | `with open() as f:` |
| `spark.table()` | Keep as-is |

---

## Current Automation Status

### ✅ Automated (Phase 2 Complete)

**Diagnostics:**
- diagnostic_16: Parameter optimization
- diagnostic_17: Trade-by-trade analysis
- diagnostic_100: Algorithm validation

**Production Modules:**
- `production/strategies/` - All 10 strategies (4 baseline + 6 prediction)
- `production/runners/` - Workflow execution system
- `production/core/` - Backtest engine

### 🔧 In Progress (Phase 2 - 45%)

**Next Steps:**
1. Convert notebook 01 (synthetic predictions) to script
2. Build orchestrator to chain 01 → 05 → 06-10
3. Test end-to-end automated workflow
4. Add monitoring dashboard

### 📋 Pending

**Main Workflow Notebooks:**
- 02_forecast_predictions
- 06_statistical_validation
- 07_feature_importance
- 08_sensitivity_analysis
- 09_strategy_results_summary
- 10_paired_scenario_analysis

---

## Best Practices

**For Databricks-specific best practices (data access, storage, querying):**
See [DATABRICKS_GUIDE.md](DATABRICKS_GUIDE.md)

**Automation-specific best practices:**

### ✅ Do

- Add comprehensive logging
- Handle errors gracefully
- Use absolute paths
- Test scripts before committing
- Parameterize cluster IDs
- Update git repo after changes

### ❌ Don't

- Don't use magic commands in scripts
- Don't skip error handling
- Don't hardcode credentials or cluster IDs

---

## Troubleshooting

### Job Fails Immediately

**Check:**
- Python file path in job definition
- Cluster ID is valid
- Libraries are available
- Databricks repo is updated

### Job Runs But Produces No Output

**Check:**
- Volume path is correct (`/Volumes/` not `/dbfs/`)
- Write permissions on volume
- Script actually writes output (check logs)

### Job Succeeds But Results Missing

**Check:**
- Output file path in logs
- File actually created (`dbfs:/Volumes/...`)
- Correct commodity/model parameters

---

## Reference

**For complete system context:** See [MASTER_SYSTEM_PLAN.md](../MASTER_SYSTEM_PLAN.md) Phase 2

**For file inventory:** See [FILE_INVENTORY.md](../archive/notebooks/FILE_INVENTORY.md)

**For diagnostic details:** See [DIAGNOSTICS.md](DIAGNOSTICS.md)

---

**Document Owner:** System Integration
**Status:** Living Document
**Last Updated:** 2025-11-24
