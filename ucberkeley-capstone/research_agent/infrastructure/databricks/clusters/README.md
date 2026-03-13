# Unity Catalog Cluster Setup

**Purpose**: Automated creation and management of Unity Catalog-enabled compute clusters.

---

## Quick Start

### Create the Cluster

```bash
python research_agent/infrastructure/databricks/clusters/create_unity_catalog_cluster.py
```

This creates `unity-catalog-cluster` configured for:
- ✅ Unity Catalog SQL queries (commodity.bronze/silver/gold tables)
- ✅ Running SQL files directly in SQL Editor
- ✅ Interactive data analysis and exploration

**Time**: ~3-5 minutes to start

---

## What Gets Created

**Cluster Name**: `unity-catalog-cluster`

**Configuration**:
- **Node Type**: i3.xlarge (4 vCPUs, 30GB RAM, NVMe SSD)
- **Workers**: 1-2 (autoscaling)
- **Access Mode**: SINGLE_USER (required for Unity Catalog)
- **Spot Instances**: Yes (70% cost savings)
- **Auto-termination**: 30 minutes of inactivity

**Cost**: ~$0.20-$0.30/hour (~$13/month typical usage)

---

## How to Use

### Option 1: SQL Editor (Recommended for SQL Files)

1. In Databricks, go to **SQL Editor**
2. Select cluster: `unity-catalog-cluster`
3. Open your SQL file (e.g., `research_agent/sql/create_gold_unified_data.sql`)
4. Click **Run**

**Example SQL files**:
- `research_agent/sql/create_gold_unified_data.sql` - Creates gold.unified_data table
- `research_agent/sql/create_unified_data.sql` - Creates silver.unified_data table

### Option 2: Notebooks (For Python + SQL)

1. Open your notebook in Databricks
2. Click the cluster dropdown at top
3. Select `unity-catalog-cluster`
4. Run your code

**Example**:
```python
spark.sql("USE CATALOG commodity")

# Query gold table
df = spark.sql("""
    SELECT date, commodity, close, size(weather_data) as num_regions
    FROM commodity.gold.unified_data
    WHERE commodity = 'Coffee'
    LIMIT 10
""")
display(df)
```

---

## Files in This Directory

| File | Purpose |
|------|---------|
| `create_unity_catalog_cluster.py` | Creates/starts the cluster |
| `list_databricks_clusters.py` | Lists all clusters + Unity Catalog status |
| `databricks_unity_catalog_cluster.json` | Cluster configuration |
| `UNITY_CATALOG_CLUSTER_RATIONALE.md` | **Why** we chose this config (sizing, cost analysis) |

---

## Configuration Rationale

See [UNITY_CATALOG_CLUSTER_RATIONALE.md](UNITY_CATALOG_CLUSTER_RATIONALE.md) for detailed explanations:

- **Why i3.xlarge?** 30GB RAM + fast NVMe SSD balances performance vs cost for our SQL workload
- **Why 1-2 workers?** Our data volume (~7k rows in gold, ~75k in silver) doesn't justify more parallelism
- **Why spot instances?** 70% cost savings with fallback protection
- **Cost comparison**: $13/month (our config) vs $40/month (on-demand) vs $26/month (larger instances)

---

## Troubleshooting

### "Unity Catalog is not enabled on this cluster"

**Problem**: You're using the wrong cluster (e.g., "SQL Job Runner")

**Solution**: Switch to `unity-catalog-cluster` in the cluster dropdown

### "Cluster not found"

**Problem**: Cluster hasn't been created yet

**Solution**: Run the creation script:
```bash
python research_agent/infrastructure/databricks/clusters/create_unity_catalog_cluster.py
```

### "Schema does not exist: gold"

**Problem**: The gold schema hasn't been created

**Solution**: The SQL file now includes `CREATE SCHEMA IF NOT EXISTS commodity.gold` - just re-run it

---

## Listing All Clusters

To see all available clusters and their Unity Catalog compatibility:

```bash
python research_agent/infrastructure/databricks/clusters/list_databricks_clusters.py
```

Output shows:
- Cluster name and state (RUNNING/TERMINATED)
- Access mode (SINGLE_USER required for UC)
- Unity Catalog status (ENABLED/DISABLED)
- Recommendations for which cluster to use

---

## When NOT to Use This Cluster

❌ **Large backfills (>100 forecasts)**: Use dedicated Spark cluster with 4+ workers (see forecast_agent/docs/SPARK_BACKFILL_GUIDE.md)

❌ **S3 ingestion (Auto Loader)**: This cluster can't access S3 via instance profile. Use dedicated ingestion cluster if needed.

❌ **Shared team access**: SINGLE_USER mode means only one user can attach notebooks at a time. Create separate clusters for each user.

---

## References

- Parent guide: [research_agent/infrastructure/databricks/README.md](../README.md)
- Unity Catalog docs: https://docs.databricks.com/data-governance/unity-catalog/
- AWS EC2 i3 instance pricing: https://aws.amazon.com/ec2/instance-types/i3/

---

**Last Updated**: 2025-12-06
**Owner**: Research Agent Team
