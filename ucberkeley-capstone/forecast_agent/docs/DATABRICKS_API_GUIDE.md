# Databricks API Development Guide

This document captures key learnings from API-driven Databricks development for autonomous job execution and debugging.

## Quick Reference: Error Retrieval Pattern

**Most Common Mistake**: Trying to get errors from parent run ID instead of task run IDs.

**Working Pattern**:
```python
# Step 1: Get parent run to extract task run IDs
parent_url = f"{host}/api/2.1/jobs/runs/get?run_id={parent_run_id}"
parent_result = get(parent_url)
tasks = parent_result.get('tasks', [])

# Step 2: Get errors from EACH TASK run ID (NOT parent!)
for task in tasks:
    task_run_id = task.get('run_id')  # ← Use THIS, not parent_run_id!

    error_url = f"{host}/api/2.1/jobs/runs/get-output?run_id={task_run_id}"
    error_result = get(error_url)

    if 'error' in error_result:
        print(error_result['error'])  # Full Python traceback!
```

**Why This Matters**: For multi-task jobs, calling `/jobs/runs/get-output` on the parent run ID returns `400 Bad Request`. You must use individual task run IDs.

## Environment Setup

### Credentials

Load credentials from `../infra/.env`:

```bash
set -a && source ../infra/.env && set +a
```

Required environment variables:
- `DATABRICKS_HOST` - Workspace URL (e.g., `https://dbc-xxxxxx.cloud.databricks.com`)
- `DATABRICKS_TOKEN` - Personal access token
- `DATABRICKS_HTTP_PATH` - SQL warehouse HTTP path

**Security**: Never hardcode credentials in code. Always use environment variables.

## API Version Gotchas

### Workspace Import API

The workspace import endpoint uses API v2.0, NOT v2.1:

```python
# ❌ WRONG - Returns 404
url = f"{host}/api/2.1/workspace/import"

# ✅ CORRECT
url = f"{host}/api/2.0/workspace/import"
```

### Jobs API

Most jobs endpoints use API v2.1:

```python
# Submit job
POST /api/2.1/jobs/runs/submit

# Get run status
GET /api/2.1/jobs/runs/get?run_id={run_id}

# Get run output
GET /api/2.1/jobs/runs/get-output?run_id={run_id}
```

## Multi-Task Job Error Retrieval

### The Problem

For jobs with multiple tasks, calling `/jobs/runs/get-output` on the **parent run ID** returns an error:

```
400 Bad Request: "Retrieving the output of runs with multiple tasks is not supported.
Please retrieve the output of each individual task run instead."
```

### The Solution

Retrieve error logs from **individual task run IDs**:

```python
# Step 1: Get parent run status to find task run IDs
status_url = f"{host}/api/2.1/jobs/runs/get?run_id={parent_run_id}"
req = urllib.request.Request(status_url)
req.add_header('Authorization', f'Bearer {token}')

with urllib.request.urlopen(req) as response:
    result = json.loads(response.read().decode())
    tasks = result.get('tasks', [])

    for task in tasks:
        task_key = task.get('task_key')
        task_run_id = task.get('run_id')  # ← Individual task run ID

        # Step 2: Get output for each task
        task_output_url = f"{host}/api/2.1/jobs/runs/get-output?run_id={task_run_id}"
        task_req = urllib.request.Request(task_output_url)
        task_req.add_header('Authorization', f'Bearer {token}')

        with urllib.request.urlopen(task_req) as task_response:
            task_result = json.loads(task_response.read().decode())

            if 'error' in task_result:
                print(f"Task {task_key} error: {task_result['error']}")
```

## Package Installation in Databricks Notebooks

### databricks-sql-connector Requirement

When using `from databricks import sql` in a Databricks notebook, you **must** install `databricks-sql-connector`:

```python
# ❌ WRONG - ImportError: cannot import name 'sql' from 'databricks'
# MAGIC %pip install xgboost statsmodels pmdarima

# ✅ CORRECT
# MAGIC %pip install databricks-sql-connector xgboost statsmodels pmdarima
```

**Why**: The `databricks` module in Databricks runtime does not include the `sql` submodule by default. The `databricks-sql-connector` package provides the SQL connection interface.

### Package Installation Pattern

Always use `%pip install` magic command at the top of notebooks:

```python
# COMMAND ----------

# MAGIC %pip install databricks-sql-connector xgboost statsmodels pmdarima

# COMMAND ----------

# Now safe to import
from databricks import sql
```

## Autonomous Job Execution Pattern

### Complete Workflow

```python
import urllib.request
import json
import os
import base64
import time

class DatabricksJobMonitor:
    def __init__(self, host, token):
        self.host = host.rstrip('/')
        self.token = token
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

    def upload_notebook(self, local_path, workspace_path):
        """Upload notebook to workspace"""
        with open(local_path, 'r') as f:
            content = f.read()

        encoded_content = base64.b64encode(content.encode()).decode()

        data = {
            "path": workspace_path,
            "content": encoded_content,
            "language": "PYTHON",
            "overwrite": True,
            "format": "SOURCE"
        }

        url = f"{self.host}/api/2.0/workspace/import"  # ← Note: v2.0!
        req = urllib.request.Request(url,
                                      data=json.dumps(data).encode(),
                                      headers=self.headers)

        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())

    def submit_job(self, notebook_path, cluster_id, job_name):
        """Submit notebook job"""
        job_config = {
            "run_name": job_name,
            "tasks": [{
                "task_key": "main_task",
                "notebook_task": {
                    "notebook_path": notebook_path,
                    "source": "WORKSPACE"
                },
                "existing_cluster_id": cluster_id,
                "timeout_seconds": 14400,
                "email_notifications": {}
            }]
        }

        url = f"{self.host}/api/2.1/jobs/runs/submit"
        req = urllib.request.Request(url,
                                      data=json.dumps(job_config).encode(),
                                      headers=self.headers)

        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            return result['run_id']

    def monitor_job(self, run_id, poll_interval=60):
        """Monitor job execution with live status updates"""
        while True:
            url = f"{self.host}/api/2.1/jobs/runs/get?run_id={run_id}"
            req = urllib.request.Request(url, headers=self.headers)

            with urllib.request.urlopen(req) as response:
                status = json.loads(response.read().decode())
                state = status.get('state', {})
                life_cycle = state.get('life_cycle_state')
                result_state = state.get('result_state')

                print(f"Status: {life_cycle} / {result_state or 'N/A'}")

                # Check for terminal states
                if life_cycle == 'TERMINATED':
                    if result_state == 'SUCCESS':
                        print("✅ Job completed successfully!")
                        return status
                    else:
                        print(f"❌ Job failed with state: {result_state}")
                        self._print_error_logs(run_id)
                        return status

                elif life_cycle in ['INTERNAL_ERROR', 'SKIPPED']:
                    print(f"❌ Job error: {life_cycle}")
                    self._print_error_logs(run_id)
                    return status

                # Still running
                time.sleep(poll_interval)

    def _print_error_logs(self, parent_run_id):
        """Retrieve error logs from multi-task job"""
        # Get task details
        url = f"{self.host}/api/2.1/jobs/runs/get?run_id={parent_run_id}"
        req = urllib.request.Request(url, headers=self.headers)

        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            tasks = result.get('tasks', [])

            for task in tasks:
                task_run_id = task.get('run_id')

                # Get task output
                output_url = f"{self.host}/api/2.1/jobs/runs/get-output?run_id={task_run_id}"
                output_req = urllib.request.Request(output_url, headers=self.headers)

                try:
                    with urllib.request.urlopen(output_req) as output_response:
                        output_result = json.loads(output_response.read().decode())

                        if 'error' in output_result:
                            print(f"\nError from {task.get('task_key')}:")
                            print(output_result['error'])
                except Exception as e:
                    print(f"Could not fetch output: {e}")

# Usage
host = os.getenv('DATABRICKS_HOST')
token = os.getenv('DATABRICKS_TOKEN')
cluster_id = 'your-cluster-id'

monitor = DatabricksJobMonitor(host, token)

# Step 1: Upload notebook
monitor.upload_notebook(
    'local_notebook.py',
    '/Users/user@domain.com/notebook_name'
)

# Step 2: Submit job
run_id = monitor.submit_job(
    '/Users/user@domain.com/notebook_name',
    cluster_id,
    'My Job Name'
)

# Step 3: Monitor
monitor.monitor_job(run_id, poll_interval=60)
```

## Common Error Patterns

### Error 1: ImportError for databricks.sql

**Symptom**:
```
ImportError: cannot import name 'sql' from 'databricks'
```

**Fix**: Add `databricks-sql-connector` to pip install:
```python
# MAGIC %pip install databricks-sql-connector
```

### Error 2: 404 on Workspace Import

**Symptom**:
```
404 Not Found: {"error":"Bad Target: /api/2.1/workspace/import"}
```

**Fix**: Use API v2.0 instead of v2.1:
```python
url = f"{host}/api/2.0/workspace/import"  # Not v2.1!
```

### Error 3: Can't Get Multi-Task Job Output

**Symptom**:
```
400 Bad Request: Retrieving the output of runs with multiple tasks is not supported
```

**Fix**: Get individual task run IDs first, then fetch output for each task (see "Multi-Task Job Error Retrieval" section above).

## Best Practices

### 1. Session Timeout Handling

Databricks SQL connections timeout after 15 minutes of inactivity. For long-running scripts:

```python
# Reconnect every 50 operations
for i, item in enumerate(items):
    if i % 50 == 0:
        connection.close()
        connection = sql.connect(...)

    # Process item
```

### 2. Polling Intervals

- **Training jobs**: 60-second poll interval
- **Quick status checks**: 10-30 seconds
- **Long-running backfills**: 120+ seconds

### 3. Error Context

Always include:
- Run ID
- Task key (for multi-task jobs)
- Life cycle state
- Result state
- State message
- Elapsed time

### 4. Autonomous Execution Checklist

- [ ] Upload notebook to workspace
- [ ] Submit job with run name including timestamp
- [ ] Save run ID to file for recovery
- [ ] Monitor with appropriate poll interval
- [ ] Retrieve error logs on failure
- [ ] Print URL for manual inspection

## Debugging Tips

### View Job in Databricks UI

```python
job_url = f"{host}/#job/{run_id}/run/1"
print(f"View job at: {job_url}")
```

### Check Cluster Status

```python
cluster_url = f"{host}/api/2.0/clusters/get?cluster_id={cluster_id}"
```

### Verify Notebook Upload

```python
list_url = f"{host}/api/2.0/workspace/list?path=/Users/user@domain.com"
```

## Reference Implementations

**Minimal Example** (`/tmp/get_diagnostic_error.py`):
Simple 30-line script demonstrating the correct pattern for retrieving errors from multi-task jobs using task run IDs.

**Production Implementation** (`run_lstm_databricks.py`):
Complete, production-ready implementation of autonomous job execution with:
- Notebook upload
- Job submission
- Live monitoring with state change tracking
- Error retrieval from multi-task jobs (see `_print_error_logs()` method)
- Comprehensive logging

## Additional Resources

- [Databricks Jobs API Documentation](https://docs.databricks.com/api/workspace/jobs)
- [Workspace API Documentation](https://docs.databricks.com/api/workspace/workspace)
- [databricks-sql-connector PyPI](https://pypi.org/project/databricks-sql-connector/)
