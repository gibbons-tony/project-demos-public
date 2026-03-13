# Forecast Agent - Forecasting Patterns

**Owner:** Connor

---

## Before Working

Read [README.md](README.md) → [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) first

---

## Critical Rules

**1. Data Sources - Use Gold Tables ONLY**
```python
# CORRECT
from ml_lib.cross_validation.data_loader import GoldDataLoader
loader = GoldDataLoader()
df = loader.load(commodity='Coffee')

# WRONG - NEVER query bronze or silver directly
df = spark.table('commodity.bronze.market')      # Has gaps!
df = spark.table('commodity.silver.unified_data') # Deprecated!
```

**Why:** Gold tables have continuous daily coverage (no gaps), 90% fewer rows, forward-filled data

**2. Prefer PySpark Over Pandas**
- **Always think:** "Can I parallelize this with Spark instead of pandas/numpy?"
- Identify parallelization opportunities using PySpark
- When using pandas/numpy, consider if Spark would be more efficient
- When using Spark, seek efficient implementations:
  - **Cache** intermediate results that are reused (`df.cache()`)
  - **Broadcast** small lookup tables for joins (`F.broadcast(small_df)`)
  - Use window functions instead of collect()
  - Avoid multiple actions on uncached DataFrames

```python
# GOOD - PySpark (parallelized)
df_spark.groupBy('commodity').agg(F.mean('close'))

# GOOD - Broadcast small table for efficient join
from pyspark.sql.functions import broadcast
df_large.join(broadcast(df_small), 'id')

# GOOD - Cache reused DataFrames
df_filtered = df.filter(F.col('commodity') == 'Coffee')
df_filtered.cache()
df_filtered.count()  # Materialize cache
result1 = df_filtered.agg(...)  # Reuses cache
result2 = df_filtered.groupBy(...)  # Reuses cache

# AVOID - Pandas (single-threaded on driver)
df_pandas = df_spark.toPandas()  # Pulls all data to driver!
df_pandas.groupby('commodity')['close'].mean()
```

**3. Always Cache After Imputation**
```python
df_imputed = imputer.transform(df_raw)
df_imputed.cache()  # CRITICAL for 2-3x speedup!
df_imputed.count()   # Materialize
```

**4. Package Deployment**
After code changes:
```bash
python infrastructure/databricks/clusters/deploy_package.py
```

**5. Testing**
```bash
pytest tests/
```

---

## Key Patterns

- **Train-once/inference-many** - See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **GoldDataLoader** - Standard data access
- **"Fit many, publish few"** - See [ml_lib/MODEL_SELECTION_STRATEGY.md](ml_lib/MODEL_SELECTION_STRATEGY.md)
