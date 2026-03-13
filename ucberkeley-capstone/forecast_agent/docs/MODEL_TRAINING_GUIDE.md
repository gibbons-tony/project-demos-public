# Model Training Guide for Databricks

**Purpose:** Step-by-step guide to train forecast models on Databricks using the train-once/inference-many pattern.

**Last Updated:** 2025-11-22

---

## Quick Start

**Train all models (96 total):**
```bash
cd forecast_agent
python /tmp/submit_full_training.py  # Uses script from this guide
```

**Expected duration:** 15-30 minutes
**Output:** Models saved to `commodity.forecast.trained_models` table

---

## Prerequisites

### 1. Environment Setup

Ensure you have credentials in `../infra/.env`:
```bash
DATABRICKS_HOST=https://dbc-xxxxxx.cloud.databricks.com
DATABRICKS_TOKEN=dapi...
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/...
```

Load credentials:
```bash
cd forecast_agent
set -a && source ../infra/.env && set +a
```

### 2. ML Cluster

**Existing Cluster ID:** `1121-061338-wj2kqadu`

**Specifications:**
- Runtime: ML 14.3.x-cpu-ml-scala2.12
- Node Type: i3.xlarge (single-node)
- Libraries: pmdarima (already installed)

**Why use existing cluster:**
- Faster startup (no cluster creation delay)
- Libraries already installed
- Cost-effective (no redundant cluster creation)

### 3. Ground Truth Package

The `ground_truth` Python package must be built and uploaded to DBFS.

**Build wheel:**
```bash
cd forecast_agent
rm -rf build dist ground_truth.egg-info
python setup.py bdist_wheel
```

**Upload to DBFS:**
```bash
databricks fs cp dist/ground_truth-0.1.0-py3-none-any.whl \
  dbfs:/FileStore/packages/ground_truth-0.1.0-py3-none-any.whl --overwrite
```

**Verify upload:**
```bash
databricks fs ls dbfs:/FileStore/packages/
```

---

## Training Architecture

### Train-Once/Inference-Many Pattern

Instead of training 2,800+ models (one per date), we:

1. **Train periodically** - 16 semiannual training windows (2018-2025)
2. **Reuse models** - Each trained model generates forecasts for multiple dates
3. **Save to database** - Models persisted in `commodity.forecast.trained_models`

**Result:** 96 models instead of 2,800+ (97% reduction)

### Training Configuration

```python
COMMODITIES = ['Coffee', 'Sugar']
MODEL_KEYS = ['naive', 'xgboost', 'sarimax_auto_weather']
TRAIN_FREQUENCY = 'semiannually'  # Every 6 months
START_DATE = '2018-01-01'
END_DATE = '2025-11-17'
MODEL_VERSION = 'v1.0'
```

**Total models:** 2 commodities × 3 models × 16 windows = **96 models**

---

## Incremental Testing Approach

**Critical:** Test components individually before running full training.

### Test 1: Verify Package Imports

**Purpose:** Ensure ground_truth wheel can be imported on Databricks

**Test script** (`/tmp/test1_import_wheel.py`):
```python
#!/usr/bin/env python3
print("TEST 1: Import ground_truth wheel package")

from ground_truth.models.naive import naive_forecast_with_metadata
from ground_truth.models.xgboost_model import xgboost_forecast_with_metadata
from ground_truth.models.sarimax import sarimax_forecast_with_metadata

print("✅ TEST 1 PASSED - All imports work!")
```

**Submit:**
```bash
python /tmp/submit_test_simple.py /tmp/test1_import_wheel.py "Test1-Imports"
```

### Test 2: Single Model Training

**Purpose:** Verify model training logic works

**Test script** (`/tmp/test2_train.py`):
```python
#!/usr/bin/env python3
print("TEST 2: Train single naive model")

from ground_truth.models.naive import naive_forecast_with_metadata
import pandas as pd
import numpy as np

# Create test data
dates = pd.date_range('2024-01-01', periods=100, freq='D')
data = pd.DataFrame({
    'close': 100 + np.random.randn(100).cumsum()
}, index=dates)

# Train model
result = naive_forecast_with_metadata(
    df_pandas=data,
    commodity='Coffee',
    target='close',
    horizon=14
)

print(f"✅ TEST 2 PASSED - Model trained: {result['fitted_model']['model_type']}")
```

### Test 3: Database Write

**Purpose:** Verify database schema and write operations

**Test script** (`/tmp/test3_db.py`):
```python
#!/usr/bin/env python3
print("TEST 3: Save model to database")

from ground_truth.models.naive import naive_train
import pandas as pd
import json

# Train model
dates = pd.date_range('2024-01-01', periods=100, freq='D')
data = pd.DataFrame({'close': 100 + np.random.randn(100).cumsum()}, index=dates)
fitted_model = naive_train(data, target='close')

# Serialize
fitted_model_json = json.dumps({
    'model_type': fitted_model.get('model_type'),
    'last_value': float(fitted_model.get('last_value')),
    'daily_vol': float(fitted_model.get('daily_vol')),
    'last_date': str(fitted_model.get('last_date')),
    'target': fitted_model.get('target')
}).replace("'", "''")

# Insert (NOTE: Column is training_cutoff_date, not training_window_end)
spark.sql(f'''
    INSERT INTO commodity.forecast.trained_models
    (commodity, model_name, model_version, training_cutoff_date,
     year, month, fitted_model_json, created_at)
    VALUES ('Coffee', 'naive', 'test_v0.1', '2024-01-01', 2024, 1,
            '{fitted_model_json}', CURRENT_TIMESTAMP())
''')

# Verify and cleanup
result = spark.sql("SELECT COUNT(*) as cnt FROM commodity.forecast.trained_models WHERE model_version = 'test_v0.1'").toPandas()
print(f"✅ TEST 3 PASSED - {result['cnt'].iloc[0]} test models saved")
spark.sql("DELETE FROM commodity.forecast.trained_models WHERE model_version = 'test_v0.1'")
```

**Key learnings from Test 3:**
- Database column is `training_cutoff_date` (not `training_window_end`)
- Must escape single quotes in JSON: `.replace("'", "''")`
- Use Spark SQL (not databricks.sql connector) in notebooks

---

## Full Training Submission

### Training Script

The main training script (`forecast_agent/databricks_train_simple.py`):
- Loads data from `commodity.silver.unified_data`
- Trains models using train-once pattern
- Saves fitted models to `commodity.forecast.trained_models`

**Key fixes from initial attempts:**
1. Removed unused imports (`ground_truth.features.weather`, `ground_truth.features.sentiment`)
2. Fixed database schema (use `training_cutoff_date`)
3. Ground truth package installed as cluster library (not pip install at runtime)

### Submission Script

Create `/tmp/submit_full_training.py`:

```python
#!/usr/bin/env python3
import urllib.request
import json
import os
import base64
from datetime import datetime

# Load environment
env_file = '/Users/connorwatson/Documents/Data Science/DS210-capstone/ucberkeley-capstone/infra/.env'
with open(env_file) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ[key] = value

HOST = os.environ['DATABRICKS_HOST']
TOKEN = os.environ['DATABRICKS_TOKEN']
ML_CLUSTER_ID = '1121-061338-wj2kqadu'
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

# Upload training script
script_path = '/Users/connorwatson/Documents/Data Science/DS210-capstone/ucberkeley-capstone/forecast_agent/databricks_train_simple.py'
with open(script_path, 'r') as f:
    content = f.read()

notebook_path = f"/Users/ground.truth.datascience@gmail.com/train_all_models_{timestamp}"

upload_req = urllib.request.Request(
    f"{HOST}/api/2.0/workspace/import",
    data=json.dumps({
        "path": notebook_path,
        "content": base64.b64encode(content.encode()).decode(),
        "language": "PYTHON",
        "overwrite": True,
        "format": "SOURCE"
    }).encode(),
    headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'}
)

with urllib.request.urlopen(upload_req) as response:
    print("✅ Uploaded training script")

# Submit job
job_config = {
    "run_name": f"Train All Models (Coffee+Sugar) - {timestamp}",
    "tasks": [{
        "task_key": "train_all",
        "notebook_task": {
            "notebook_path": notebook_path,
            "source": "WORKSPACE"
        },
        "existing_cluster_id": ML_CLUSTER_ID,
        "libraries": [
            {"whl": "dbfs:/FileStore/packages/ground_truth-0.1.0-py3-none-any.whl"}
        ],
        "timeout_seconds": 3600
    }]
}

job_req = urllib.request.Request(
    f"{HOST}/api/2.1/jobs/runs/submit",
    data=json.dumps(job_config).encode(),
    headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'}
)

with urllib.request.urlopen(job_req) as response:
    result = json.loads(response.read().decode())
    run_id = result['run_id']
    print(f"✅ Submitted: {run_id}")
    print(f"Monitor: {HOST}/#job/{run_id}")

    with open('/tmp/full_training_run_id.txt', 'w') as f:
        f.write(str(run_id))
```

**Run:**
```bash
python /tmp/submit_full_training.py
```

---

## Monitoring Training

### Real-Time Monitoring

Create `/tmp/monitor_training.py`:

```python
import os
import json
import urllib.request
import time
from datetime import datetime

# Load environment
env_file = '/Users/connorwatson/Documents/Data Science/DS210-capstone/ucberkeley-capstone/infra/.env'
with open(env_file) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ[key] = value

HOST = os.environ['DATABRICKS_HOST']
TOKEN = os.environ['DATABRICKS_TOKEN']

# Get run ID from file
with open('/tmp/full_training_run_id.txt') as f:
    RUN_ID = int(f.read().strip())

print(f'Monitoring training job {RUN_ID}...')

while True:
    req = urllib.request.Request(
        f'{HOST}/api/2.1/jobs/runs/get?run_id={RUN_ID}',
        headers={'Authorization': f'Bearer {TOKEN}'}
    )

    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        state = data.get('state', {})
        lifecycle = state.get('life_cycle_state')
        result = state.get('result_state', 'N/A')

        ts = datetime.now().strftime('%H:%M:%S')
        print(f'[{ts}] {lifecycle} / {result}')

        if result == 'SUCCESS':
            print('\n✅ TRAINING COMPLETED!')
            break
        elif result == 'FAILED':
            print('\n❌ TRAINING FAILED')
            # Get error from task run
            tasks = data.get('tasks', [])
            if tasks:
                task_run_id = tasks[0].get('run_id')
                error_url = f'{HOST}/api/2.1/jobs/runs/get-output?run_id={task_run_id}'
                error_req = urllib.request.Request(error_url, headers={'Authorization': f'Bearer {TOKEN}'})
                try:
                    with urllib.request.urlopen(error_req) as error_response:
                        error_data = json.loads(error_response.read().decode())
                        if 'error' in error_data:
                            print(error_data['error'])
                except:
                    pass
            exit(1)

    time.sleep(30)
```

**Run:**
```bash
python /tmp/monitor_training.py
```

### Error Retrieval Pattern

**IMPORTANT:** For multi-task jobs, retrieve errors from task run IDs (not parent run ID).

**Working pattern:**
```python
# Step 1: Get parent run to find task run IDs
parent_result = get(f'{HOST}/api/2.1/jobs/runs/get?run_id={parent_run_id}')
tasks = parent_result.get('tasks', [])

# Step 2: Get error from TASK run ID
for task in tasks:
    task_run_id = task.get('run_id')  # Use THIS, not parent_run_id!
    error_result = get(f'{HOST}/api/2.1/jobs/runs/get-output?run_id={task_run_id}')

    if 'error' in error_result:
        print(error_result['error'])  # Full Python traceback
```

See `forecast_agent/docs/DATABRICKS_API_GUIDE.md` for details.

---

## Verification

### Check Trained Models

```python
from databricks import sql
import os

# Load credentials
env_file = 'infra/.env'
with open(env_file) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ[key] = value

conn = sql.connect(
    server_hostname=os.environ['DATABRICKS_HOST'].replace('https://', ''),
    http_path=os.environ['DATABRICKS_HTTP_PATH'],
    access_token=os.environ['DATABRICKS_TOKEN']
)

cursor = conn.cursor()

# Count models by commodity and model type
cursor.execute('''
    SELECT
        commodity,
        model_name,
        COUNT(*) as num_models,
        MIN(training_cutoff_date) as first_window,
        MAX(training_cutoff_date) as last_window
    FROM commodity.forecast.trained_models
    WHERE model_version = 'v1.0'
    GROUP BY commodity, model_name
    ORDER BY commodity, model_name
''')

for row in cursor.fetchall():
    commodity, model_name, count, first, last = row
    print(f'{commodity:<12} {model_name:<30} {count:<6} {first} to {last}')

cursor.close()
conn.close()
```

**Expected output:**
```
Coffee       naive                          16     2018-01-01 to 2025-07-01
Coffee       xgboost                        16     2018-01-01 to 2025-07-01
Coffee       sarimax_auto_weather           16     2018-01-01 to 2025-07-01
Sugar        naive                          16     2018-01-01 to 2025-07-01
Sugar        xgboost                        16     2018-01-01 to 2025-07-01
Sugar        sarimax_auto_weather           16     2018-01-01 to 2025-07-01
```

**Note:** You may see duplicates from previous training runs - filter by `model_version` or `created_at` to see only latest.

---

## Common Issues & Solutions

### Issue 1: ModuleNotFoundError: No module named 'ground_truth'

**Cause:** Wheel package not uploaded or not specified in job libraries

**Solution:**
1. Verify wheel uploaded: `databricks fs ls dbfs:/FileStore/packages/`
2. Ensure job config includes library: `{"whl": "dbfs:/FileStore/packages/ground_truth-0.1.0-py3-none-any.whl"}`

### Issue 2: ModuleNotFoundError: No module named 'ground_truth.features.weather'

**Cause:** Training script imports unused modules not in wheel package

**Solution:** Remove unused imports from `databricks_train_simple.py`

### Issue 3: Column 'training_window_end' not found

**Cause:** Database schema uses `training_cutoff_date` (not `training_window_end`)

**Solution:** Update SQL INSERT to use correct column name

### Issue 4: Local NumPy binary incompatibility

**Error:**
```
ValueError: numpy.dtype size changed, may indicate binary incompatibility
```

**Solution:** Always train on Databricks (not locally) to ensure library consistency with inference environment

### Issue 5: INTERNAL_ERROR with vague message

**Cause:** Various issues - need to retrieve actual error logs

**Solution:** Use task run ID pattern (see Error Retrieval Pattern above)

---

## Performance Benchmarks

**Actual Results (2025-11-22):**
- **Models trained:** 96 (across Coffee + Sugar)
- **Duration:** 18 minutes
- **Cluster:** i3.xlarge single-node ML runtime
- **Models per minute:** ~5.3

**Breakdown:**
- Cluster already running (no startup delay)
- Ground truth package pre-uploaded
- Training windows: 16 (semiannual 2018-2025)
- Model types: 3 (naive, xgboost, sarimax)

---

## Next Steps

After training completes:
1. Verify models in database (see Verification section)
2. Run inference backfill using `backfill_rolling_window.py`
3. Populate `commodity.forecast.distributions` and `commodity.forecast.point_forecasts` tables

See `forecast_agent/docs/INFERENCE_BACKFILL_GUIDE.md` (coming soon)

---

## Related Documentation

- **[DATABRICKS_API_GUIDE.md](DATABRICKS_API_GUIDE.md)** - Error retrieval patterns, API quirks
- **[DATABRICKS_CLUSTER_SETUP.md](../DATABRICKS_CLUSTER_SETUP.md)** - ML cluster configuration
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Train-once/inference-many architecture
- **[../BACKFILL_STATUS.md](../BACKFILL_STATUS.md)** - Live status of current backfill

---

**Document Owner:** Claude Code (AI Assistant)
**Last Validated:** 2025-11-22 with Job ID 773612620032262
