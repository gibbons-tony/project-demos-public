# Unity Catalog Cluster Configuration Rationale

**Cluster Name:** `unity-catalog-cluster`
**Created:** 2025-12-06
**Purpose:** Unity Catalog SQL workloads (table creation, queries, data transformation)

---

## Configuration Summary

```json
{
  "cluster_name": "unity-catalog-cluster",
  "spark_version": "13.3.x-scala2.12",
  "node_type_id": "i3.xlarge",
  "autoscale": {
    "min_workers": 1,
    "max_workers": 2
  },
  "data_security_mode": "SINGLE_USER",
  "autotermination_minutes": 30,
  "aws_attributes": {
    "availability": "SPOT_WITH_FALLBACK",
    "spot_bid_price_percent": 100
  }
}
```

---

## Design Decisions

### 1. Node Type: i3.xlarge

**Specs:**
- 4 vCPUs
- 30.5 GB RAM
- 950 GB NVMe SSD storage

**Why i3.xlarge?**
- ✅ **Sufficient memory for SQL operations:** Our largest table (`commodity.gold.unified_data`) has ~7k rows with nested arrays. 30GB RAM easily handles this.
- ✅ **Local SSD for shuffle operations:** i3 instances have fast NVMe SSDs which accelerate Spark shuffles during JOINs and aggregations.
- ✅ **Cost-effective:** At ~$0.31/hour on-demand ($0.10/hour spot), it's the smallest instance that comfortably handles our workload.
- ❌ **Not using**: r5 (memory-optimized) or m5 (general purpose) because i3's local storage is more valuable for our SQL-heavy workload than extra RAM.

**Alternative considered:**
- `i3.2xlarge` (8 vCPUs, 61GB RAM) - **Too expensive** for our small data volume (~75k rows in silver, ~7k in gold)

### 2. Autoscaling: 1-2 Workers

**Why autoscale instead of fixed workers?**
- ✅ **Cost savings during idle:** With 1 minimum worker, the cluster costs less when not actively processing queries.
- ✅ **Burst capacity:** Scales to 2 workers for complex queries (e.g., `create_gold_unified_data.sql` with multiple CTEs and window functions).
- ✅ **Auto-termination synergy:** Cluster terminates after 30 minutes of inactivity, so we're rarely paying for max capacity.

**Why not more workers?**
- Our data volume doesn't justify parallelism beyond 2 workers
- SQL queries complete in seconds to minutes even on 1 worker
- Large backfills use separate Spark clusters (see forecast_agent/docs/SPARK_BACKFILL_GUIDE.md)

### 3. Data Security Mode: SINGLE_USER

**Why SINGLE_USER?**
- ✅ **Required for Unity Catalog:** Unity Catalog requires either `SINGLE_USER` or `USER_ISOLATION` mode for security.
- ✅ **Simplest authentication:** No need for complex ACLs when running ad-hoc SQL queries.
- ❌ **Limitation:** Only one user can attach notebooks to the cluster at a time.

**Alternative:**
- `USER_ISOLATION` mode would allow multi-user access, but adds complexity we don't need.

### 4. Spot Instances: SPOT_WITH_FALLBACK

**Why spot instances?**
- ✅ **70% cost savings:** Spot instances cost ~$0.10/hour vs $0.31/hour on-demand
- ✅ **Fallback protection:** `SPOT_WITH_FALLBACK` automatically switches to on-demand if spot capacity is unavailable
- ✅ **Low interruption risk:** SQL queries typically complete in <5 minutes, minimizing spot interruption impact

**Trade-off:**
- Spot instances can be interrupted, but `first_on_demand: 1` ensures the driver node is always stable

### 5. Auto-Termination: 30 Minutes

**Why 30 minutes?**
- ✅ **Balance convenience vs cost:** Long enough for interactive SQL work without accidentally leaving cluster running overnight
- ✅ **Fast restart:** Cluster starts in 3-5 minutes, so termination doesn't significantly slow workflow

**Alternative:**
- 120 minutes (default) - **Too expensive** if user forgets to terminate manually

### 6. Spark Version: 13.3.x LTS

**Why 13.3.x?**
- ✅ **Unity Catalog compatibility:** Fully supports Unity Catalog features
- ✅ **Long-term support:** LTS version receives bug fixes and security patches
- ✅ **Stability:** Well-tested for production workloads

---

## Cost Analysis

### Hourly Cost (Spot Instances)
- **Driver:** 1x i3.xlarge spot = $0.10/hour
- **Workers:** 1-2x i3.xlarge spot = $0.10-$0.20/hour
- **Total:** $0.20-$0.30/hour

### Monthly Cost (Typical Usage)
Assuming 2 hours/day of active use (auto-terminates when idle):
- **Daily:** 2 hours × $0.30 = $0.60/day
- **Monthly:** $0.60 × 22 workdays = **~$13.20/month**

### Comparison to Alternatives
| Cluster Config | Hourly Cost | Monthly Cost (44 hrs) |
|----------------|-------------|-----------------------|
| **i3.xlarge (1-2 workers, spot)** | $0.20-$0.30 | **$13.20** |
| i3.xlarge (2 workers, on-demand) | $0.93 | $40.92 |
| i3.2xlarge (1-2 workers, spot) | $0.40-$0.60 | $26.40 |
| SQL Warehouse (Serverless) | ~$0.70/DBU | Variable |

**Winner:** Our configuration is **3x cheaper** than on-demand and **2x cheaper** than larger instances.

---

## When NOT to Use This Cluster

❌ **Large backfills (>100 forecasts):** Use dedicated Spark cluster with 4+ workers
❌ **S3 ingestion (Auto Loader):** Use `s3-ingestion-cluster` (no Unity Catalog, has instance profile)
❌ **Shared team access:** Create separate clusters for each user (SINGLE_USER limitation)

---

## Recreation Instructions

If the cluster is accidentally deleted or needs to be recreated:

```bash
# From project root
python research_agent/infrastructure/databricks/create_unity_catalog_cluster.py
```

This script:
1. Checks if `unity-catalog-cluster` already exists
2. Creates new cluster if missing
3. Starts existing cluster if terminated
4. Waits for cluster to reach RUNNING state

**Configuration source:** `research_agent/infrastructure/databricks/databricks_unity_catalog_cluster.json`

---

## References

- Cluster creation script: `research_agent/infrastructure/databricks/create_unity_catalog_cluster.py`
- Configuration file: `research_agent/infrastructure/databricks/databricks_unity_catalog_cluster.json`
- Usage guide: `research_agent/infrastructure/databricks/CLUSTER_GUIDE.md`
- AWS EC2 pricing: https://aws.amazon.com/ec2/instance-types/i3/
- Databricks Unity Catalog docs: https://docs.databricks.com/data-governance/unity-catalog/index.html

---

**Document Owner:** Research Agent Team
**Last Updated:** 2025-12-06
**Reviewed By:** N/A
