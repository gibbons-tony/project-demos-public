# Spark-Parallelized Forecast Backfill

This guide explains how to use the Spark-based backfill for massive speedup.

## Performance Comparison

| Method | Time for 2,872 dates | Parallelism | Cost |
|--------|---------------------|-------------|------|
| **Local (current)** | 10-20 hours | Serial (1 core) | Low |
| **Spark (new)** | 20-60 minutes | Parallel (100s of cores) | Medium |

## Setup in Databricks

### 1. Upload forecast_agent to Databricks

**Option A: Via Databricks CLI**
```bash
databricks workspace import-dir \
  /Users/connorwatson/Documents/Data\ Science/DS210/ucberkeley-capstone/forecast_agent \
  /Workspace/forecast_agent
```

**Option B: Via UI**
1. Go to Databricks workspace
2. Right-click on Workspace → Import
3. Upload the `forecast_agent` folder

### 2. Create a Databricks Notebook

1. Create new notebook: `Backfill_Spark`
2. Copy contents of `backfill_spark.py` into the notebook
3. The file is already formatted as a Databricks notebook with `# COMMAND ----------` separators

### 3. Create a Cluster

**Recommended settings for 2,872 date backfill:**

```
Cluster Mode: Standard
Databricks Runtime: 14.3 LTS ML (or latest)
Worker Type: i3.xlarge (4 cores, 30.5 GB)
Workers: 16-32 (autoscaling)
Driver Type: i3.xlarge

Total cores: 64-128
Estimated runtime: 20-40 minutes
```

**For smaller backfills (<500 dates):**
```
Workers: 4-8
Total cores: 16-32
Estimated runtime: 10-20 minutes
```

### 4. Install Dependencies

The notebook automatically installs required packages:
```python
%pip install scikit-learn xgboost statsmodels
```

## Usage

### Run in Databricks Notebook

```python
# Execute all cells in the notebook, then run:

result = spark_backfill(
    commodity="Coffee",
    models=["xgboost"],
    train_frequency="semiannually",
    start_date="2018-01-01",
    end_date="2025-11-16",
    num_partitions=200  # Adjust based on cluster size
)

display(result)
```

### Run Multiple Models in Parallel

```python
# Backfill all baseline models
result = spark_backfill(
    commodity="Coffee",
    models=["naive", "random_walk", "xgboost", "sarimax_auto_weather"],
    train_frequency="semiannually",
    num_partitions=200
)
```

### Sugar Backfill

```python
result = spark_backfill(
    commodity="Sugar",
    models=["xgboost"],
    train_frequency="semiannually",
    num_partitions=200
)
```

## How It Works

### Architecture

```
┌─────────────────────────────────────────────────────┐
│ Spark Driver                                        │
│                                                     │
│ 1. Generate list of (forecast_date, train_date)   │
│ 2. Create DataFrame with tasks                     │
│ 3. Repartition across workers                      │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│ Spark Workers (Parallel Execution)                  │
│                                                     │
│ Worker 1: Forecasts 1-100                          │
│ Worker 2: Forecasts 101-200                        │
│ Worker 3: Forecasts 201-300                        │
│ ...                                                 │
│ Worker N: Forecasts 2701-2872                      │
│                                                     │
│ Each worker:                                        │
│   - Loads training data from Delta                  │
│   - Loads pretrained model from database            │
│   - Generates 2000 Monte Carlo paths               │
│   - Returns DataFrame with results                  │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│ Delta Table Write                                   │
│                                                     │
│ All results written in bulk                         │
│ commodity.forecast.distributions                    │
└─────────────────────────────────────────────────────┘
```

### Key Optimizations

1. **Parallel execution**: Each forecast date runs independently on different workers
2. **Pretrained models**: No training, just inference (fast!)
3. **Bulk Delta writes**: Single write operation instead of many INSERTs
4. **Auto-resume**: Skips dates that already have forecasts
5. **Fault tolerance**: Spark handles worker failures automatically

## Tuning Parameters

### num_partitions

Controls parallelism level:
- **Rule of thumb**: 2-4x your total number of cores
- Too few: Workers sit idle
- Too many: Overhead from task scheduling

```python
# Example calculations
16 workers × 4 cores = 64 total cores
num_partitions = 200  # ~3x cores (good)

32 workers × 4 cores = 128 total cores
num_partitions = 400  # ~3x cores (good)
```

### Cluster Size

For **Coffee XGBoost (2,872 dates)**:
- 8 workers (32 cores): ~60-90 minutes
- 16 workers (64 cores): ~30-45 minutes
- 32 workers (128 cores): ~15-25 minutes

Diminishing returns above 32 workers due to:
- Database read bottlenecks
- Network overhead
- Task scheduling overhead

## Monitoring Progress

### In Databricks Notebook

The function prints progress:
```
Processing model: xgboost
Training windows: 16
Total forecast dates: 2872
Already exist: 500
Need to generate: 2372

🚀 Launching Spark jobs across 200 partitions...
💾 Writing forecasts to Delta table...

✅ Complete!
   Rows written: 4,744,000
   Expected: 4,744,000
   Forecasts: 2372
```

### Spark UI

1. Click "Spark UI" tab in notebook
2. View "Stages" to see parallel task execution
3. Monitor memory usage and task duration

## Cost Optimization

### Auto-termination

Set cluster to auto-terminate after 30 minutes of inactivity:
```
Cluster → Edit → Advanced Options → Auto Termination
```

### Spot Instances

For non-urgent backfills, use spot instances:
```
Cluster → Edit → Worker Type → Use Spot Instances
Savings: 60-90% vs on-demand
Risk: Workers may be preempted (Spark handles this)
```

### Right-sizing

Don't over-provision:
- Start with 8 workers
- Monitor CPU/memory usage
- Scale up if underutilized
- Scale down if over-provisioned

## Troubleshooting

### "Model not found" errors

Ensure all models are trained:
```bash
# Local: Train models first
python train_models.py --commodity Coffee --models xgboost --train-frequency semiannually
```

### Out of Memory

Reduce `num_partitions` or increase worker memory:
```python
num_partitions = 100  # Fewer tasks = more memory per task
```

### Slow execution

- Check if workers are busy (Spark UI)
- Increase `num_partitions` if workers idle
- Increase cluster size if all workers busy

## Next Steps

1. **Upload to Databricks**: Copy `backfill_spark.py` to Databricks workspace
2. **Create cluster**: Use recommended settings above
3. **Run backfill**: Execute notebook
4. **Verify results**: Check `commodity.forecast.distributions` table
5. **Schedule**: Set up as Databricks Job for regular backfills

## Comparison with Local Backfill

| Feature | Local | Spark |
|---------|-------|-------|
| Speed | Slow (serial) | Fast (parallel) |
| Setup | Simple | Medium (cluster config) |
| Cost | Low | Medium |
| Scalability | Poor | Excellent |
| Fault tolerance | Manual retries | Automatic |
| Best for | One-time, small | Production, large |

Use **local** for:
- Quick tests
- Small date ranges (<100 dates)
- Development

Use **Spark** for:
- Production backfills
- Large date ranges (1000+ dates)
- Time-sensitive updates
