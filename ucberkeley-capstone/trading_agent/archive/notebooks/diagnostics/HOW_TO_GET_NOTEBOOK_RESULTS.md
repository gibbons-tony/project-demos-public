# How to Get Notebook Execution Results

## Problem
When notebooks are executed in Databricks, the outputs are not preserved when exporting via:
- `databricks workspace export --format JUPYTER` → outputs array is empty
- `databricks workspace export --format HTML` → HTML contains JavaScript, not actual outputs

## Solutions

### Option 1: User Shares Results Manually
User copies key outputs from Databricks and pastes them in Slack/chat

### Option 2: User Commits Executed Notebook
User executes notebook in Databricks, then uses Databricks Repos to commit the executed version with outputs to git

### Option 3: Results Stored in Files
Diagnostic notebooks save results to pickle/CSV files that can be downloaded:
```python
# In diagnostic notebook:
results = {
    'summary': summary_dict,
    'details': details_list
}
with open('/tmp/diagnostic_08_results.pkl', 'wb') as f:
    pickle.dump(results, f)

# Then download:
dbutils.fs.cp('/tmp/diagnostic_08_results.pkl', '/Volumes/commodity/trading_agent/files/diagnostic_08_results.pkl')
```

### Option 4: Query Results from Spark Tables
If diagnostic writes results to a Spark table, query it:
```python
results = spark.table('commodity.trading_agent.diagnostic_08_results').toPandas()
```

### Option 5: Use Databricks REST API
Use REST API to get notebook run results (requires run_id from Jobs API)

## Recommended Approach
For diagnostics, use **Option 3**: Save results to files in /Volumes/ that can be accessed

## Template for Future Diagnostics

```python
# At end of diagnostic notebook:
import pickle
from datetime import datetime

results = {
    'timestamp': datetime.now().isoformat(),
    'test_name': 'diagnostic_08',
    'summary': {
        'pass': True,
        'message': 'Predictions are being passed correctly'
    },
    'details': {
        'fallback_count': 0,
        'prediction_based_count': 100
    }
}

# Save to volume
output_path = '/Volumes/commodity/trading_agent/files/diagnostic_08_results.pkl'
with open(output_path.replace('/Volumes', '/dbfs/Volumes'), 'wb') as f:
    pickle.dump(results, f)

print(f"Results saved to: {output_path}")
print(f"Download with: dbutils.fs.cp('{output_path}', 'file:/tmp/diagnostic_08_results.pkl')")
```

## WORKING SOLUTION (Tested 2025-11-22)

### ✅ Download the Data Files Directly

**What worked:**
```bash
# 1. Download the pickle file that the diagnostic reads
databricks fs cp \
  dbfs:/Volumes/commodity/trading_agent/files/results_detailed_coffee_synthetic_acc90.pkl \
  /tmp/results_detailed.pkl

# 2. Analyze it with Python (use venv python for pandas support)
/Users/markgibbons/capstone/ucberkeley-capstone/venv/bin/python << 'EOF'
import pickle

with open('/tmp/results_detailed.pkl', 'rb') as f:
    all_results = pickle.load(f)

# Now analyze all_results dictionary
for strategy_name, result in all_results.items():
    trades = result['trades']
    # Count reasons, etc.
EOF
```

**Why this works:**
- Diagnostic notebooks load data from pickle files (results_detailed, prediction_matrices, etc.)
- These pickle files ARE accessible via `databricks fs cp`
- We can download and analyze them directly without needing notebook outputs

**Key paths:**
```
/Volumes/commodity/trading_agent/files/results_detailed_coffee_synthetic_acc90.pkl
/Volumes/commodity/trading_agent/files/prediction_matrices_coffee_synthetic_acc90.pkl
/Volumes/commodity/trading_agent/files/cross_model_commodity_summary.csv
```

**Python environment:**
- Use venv python: `/Users/markgibbons/capstone/ucberkeley-capstone/venv/bin/python`
- This has pandas and other required packages installed
- Regular python3 doesn't have pandas

## Current Situation (2025-11-22)
- ✅ Successfully retrieved diagnostic_08 results
- ✅ Method: Download pickle file directly with `databricks fs cp`
- ✅ Analyzed with venv python
- ✅ Found: 0% trades without predictions (predictions ARE being passed)
