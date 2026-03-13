# Databricks Migration Guide

## Overview

This guide provides step-by-step instructions for migrating from the current Databricks workspace (with broken PrivateLink configuration) to a fresh Databricks account.

**Why migrate?**
- Current workspace has unfixable PrivateLink redirect issue (`/etc/hosts` redirects to non-working private IPs)
- Unity Catalog queries hang indefinitely on compute clusters
- Cannot be fixed without Databricks Support access
- Clean account = no broken Private Access Settings

**What needs to be migrated:**
1. S3 bucket registration and permissions
2. Unity Catalog structure (catalog, schemas, tables)
3. IAM roles and trust relationships
4. Cluster configurations
5. Notebooks (via git repo)

**What does NOT need migration:**
- Data in S3 (already exists in `s3://groundtruth-capstone/`)
- Lambda functions (independent from Databricks)
- Python code (in git repo)

---

## Prerequisites Checklist

Before starting migration:

- [ ] Weather backfill v2 completed (check: `s3://groundtruth-capstone/landing/weather_v2/`)
- [ ] AWS CLI configured with appropriate permissions
- [ ] Access to AWS IAM console
- [ ] New Databricks account created
- [ ] Databricks CLI configured for new workspace
- [ ] Git repo cloned locally with latest code

---

## Part 1: AWS IAM Configuration

### Step 1.1: Create IAM Role for Databricks Cross-Account Access

**Purpose**: Allows Databricks to access your AWS account

```bash
# Create trust policy document
cat > databricks-cross-account-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::414351767826:role/unity-catalog-prod-UCMasterRole-14S5ZJVKOTYTL"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "<YOUR_EXTERNAL_ID_FROM_DATABRICKS>"
        }
      }
    }
  ]
}
EOF

# Create role
aws iam create-role \
  --role-name databricks-cross-account-role \
  --assume-role-policy-document file://databricks-cross-account-trust-policy.json

# Attach AWS managed policy
aws iam attach-role-policy \
  --role-name databricks-cross-account-role \
  --policy-arn arn:aws:iam::aws:policy/AWSDataExchangeFullAccess
```

**Note**: Get `<YOUR_EXTERNAL_ID_FROM_DATABRICKS>` from the Databricks account setup wizard.

### Step 1.2: Create IAM Role for S3 Access (Unity Catalog)

**Purpose**: Allows Unity Catalog to access S3 buckets

```bash
# Create trust policy for Databricks Unity Catalog
cat > databricks-s3-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::414351767826:role/unity-catalog-prod-UCMasterRole-14S5ZJVKOTYTL"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "<YOUR_EXTERNAL_ID_FROM_DATABRICKS>"
        }
      }
    }
  ]
}
EOF

# Create role
aws iam create-role \
  --role-name databricks-s3-access-role \
  --assume-role-policy-document file://databricks-s3-trust-policy.json

# Attach S3 full access policy
aws iam attach-role-policy \
  --role-name databricks-s3-access-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess

# Get role ARN (save this for Unity Catalog setup)
aws iam get-role \
  --role-name databricks-s3-access-role \
  --query 'Role.Arn' \
  --output text
```

**Expected Output**: `arn:aws:iam::534150427458:role/databricks-s3-access-role`

### Step 1.3: Create Instance Profile for S3 Ingestion Cluster (Optional)

**Purpose**: For clusters that need direct S3 access outside Unity Catalog (e.g., Auto Loader)

```bash
# Create trust policy for EC2
cat > ec2-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role
aws iam create-role \
  --role-name databricks-s3-ingest-role \
  --assume-role-policy-document file://ec2-trust-policy.json

# Attach S3 full access
aws iam attach-role-policy \
  --role-name databricks-s3-ingest-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess

# Create instance profile
aws iam create-instance-profile \
  --instance-profile-name databricks-s3-ingest-profile

# Add role to instance profile
aws iam add-role-to-instance-profile \
  --instance-profile-name databricks-s3-ingest-profile \
  --role-name databricks-s3-ingest-role

# Get instance profile ARN (save for Databricks workspace setup)
aws iam get-instance-profile \
  --instance-profile-name databricks-s3-ingest-profile \
  --query 'InstanceProfile.Arn' \
  --output text
```

---

## Part 2: Databricks Workspace Setup

### Step 2.1: Create Databricks Workspace

**In Databricks Account Console:**

1. Go to **Workspaces** > **Create Workspace**
2. Configure:
   - **Workspace Name**: `groundtruth-capstone`
   - **AWS Region**: `us-west-2` (Oregon)
   - **Deployment Name**: `groundtruth-capstone`
3. **Network Configuration**:
   - Choose: **Public network** (DO NOT enable PrivateLink)
   - This avoids the broken Private Access Settings issue
4. **Storage Configuration**:
   - Root S3 Bucket: Let Databricks create (or use existing non-DBFS bucket)
5. **Cross-Account IAM Role**:
   - Enter ARN from Step 1.1: `arn:aws:iam::534150427458:role/databricks-cross-account-role`
6. Click **Create Workspace**

### Step 2.2: Enable Unity Catalog

**In Databricks Account Console:**

1. Go to **Data** > **Unity Catalog** > **Create Metastore**
2. Configure:
   - **Metastore Name**: `commodity_metastore`
   - **Region**: `us-west-2`
   - **S3 Bucket**: `s3://groundtruth-capstone-metastore/` (create new bucket first)
   - **IAM Role ARN**: (from Step 1.2) `arn:aws:iam::534150427458:role/databricks-s3-access-role`
3. Click **Create**
4. **Assign metastore to workspace**: Select `groundtruth-capstone` workspace

### Step 2.3: Register Instance Profile (Optional - for S3 Ingestion Cluster)

**In Databricks Workspace Admin Console:**

1. Go to **Settings** > **Compute** > **Instance Profiles**
2. Click **Add Instance Profile**
3. Enter ARN from Step 1.3: `arn:aws:iam::534150427458:instance-profile/databricks-s3-ingest-profile`
4. Click **Add**

---

## Part 3: Unity Catalog Configuration

### Step 3.1: Create Storage Credential

**Method 1: Via SQL Warehouse (Recommended)**

1. Open SQL Editor in new workspace
2. Run:

```sql
CREATE STORAGE CREDENTIAL IF NOT EXISTS s3_groundtruth_capstone
USING AWS_IAM_ROLE
WITH (
  role_arn = 'arn:aws:iam::534150427458:role/databricks-s3-access-role'
)
COMMENT 'Storage credential for groundtruth-capstone S3 buckets';

-- Verify
DESCRIBE STORAGE CREDENTIAL s3_groundtruth_capstone;
```

**Method 2: Via Python Script**

```bash
cd research_agent/infrastructure/databricks
export DATABRICKS_HOST="https://<NEW_WORKSPACE_ID>.cloud.databricks.com"
export DATABRICKS_TOKEN="<NEW_TOKEN>"
export DATABRICKS_HTTP_PATH="/sql/1.0/warehouses/<WAREHOUSE_ID>"
python setup_unity_catalog_credentials.py
```

### Step 3.2: Create External Locations

**Run in SQL Editor:**

```sql
-- Landing zone for raw data
CREATE EXTERNAL LOCATION IF NOT EXISTS groundtruth_landing
URL 's3://groundtruth-capstone/landing/'
WITH (STORAGE CREDENTIAL s3_groundtruth_capstone)
COMMENT 'Landing zone for raw data from Lambda functions';

-- Delta Lake bronze layer
CREATE EXTERNAL LOCATION IF NOT EXISTS groundtruth_bronze
URL 's3://groundtruth-capstone/delta/bronze/'
WITH (STORAGE CREDENTIAL s3_groundtruth_capstone)
COMMENT 'Bronze layer Delta tables';

-- Delta Lake silver layer
CREATE EXTERNAL LOCATION IF NOT EXISTS groundtruth_silver
URL 's3://groundtruth-capstone/delta/silver/'
WITH (STORAGE CREDENTIAL s3_groundtruth_capstone)
COMMENT 'Silver layer Delta tables (curated/transformed)';

-- Forecast layer
CREATE EXTERNAL LOCATION IF NOT EXISTS groundtruth_forecast
URL 's3://groundtruth-capstone/delta/forecast/'
WITH (STORAGE CREDENTIAL s3_groundtruth_capstone)
COMMENT 'Forecast layer Delta tables';

-- Config files
CREATE EXTERNAL LOCATION IF NOT EXISTS groundtruth_config
URL 's3://groundtruth-capstone/config/'
WITH (STORAGE CREDENTIAL s3_groundtruth_capstone)
COMMENT 'Configuration files (region coordinates, etc.)';

-- Weather v2 landing (corrected coordinates)
CREATE EXTERNAL LOCATION IF NOT EXISTS groundtruth_weather_v2
URL 's3://groundtruth-capstone/landing/weather_v2/'
WITH (STORAGE CREDENTIAL s3_groundtruth_capstone)
COMMENT 'Weather v2 data with corrected growing region coordinates';

-- Verify all locations
SHOW EXTERNAL LOCATIONS;
```

### Step 3.3: Grant Permissions

```sql
-- Grant READ FILES permission to all users
GRANT READ FILES ON EXTERNAL LOCATION groundtruth_landing TO `account users`;
GRANT READ FILES ON EXTERNAL LOCATION groundtruth_bronze TO `account users`;
GRANT READ FILES ON EXTERNAL LOCATION groundtruth_silver TO `account users`;
GRANT READ FILES ON EXTERNAL LOCATION groundtruth_forecast TO `account users`;
GRANT READ FILES ON EXTERNAL LOCATION groundtruth_config TO `account users`;
GRANT READ FILES ON EXTERNAL LOCATION groundtruth_weather_v2 TO `account users`;
```

### Step 3.4: Create Unity Catalog Structure

```sql
-- Create catalog
CREATE CATALOG IF NOT EXISTS commodity
COMMENT 'Commodity forecasting platform data';

-- Use the catalog
USE CATALOG commodity;

-- Create schemas
CREATE SCHEMA IF NOT EXISTS bronze
COMMENT 'Raw data ingested from landing zone';

CREATE SCHEMA IF NOT EXISTS silver
COMMENT 'Curated, cleaned, and unified data';

CREATE SCHEMA IF NOT EXISTS forecast
COMMENT 'Forecast outputs (point forecasts and distributions)';

-- Verify structure
SHOW SCHEMAS IN commodity;
```

### Step 3.5: Create Delta Tables

**Bronze Layer Tables:**

```sql
USE CATALOG commodity;
USE SCHEMA bronze;

-- Weather table (will be populated from landing/weather_v2)
CREATE TABLE IF NOT EXISTS weather (
  date DATE,
  commodity STRING,
  region STRING,
  temp_c DOUBLE,
  humidity_pct DOUBLE,
  precipitation_mm DOUBLE,
  year INT,
  month INT,
  day INT
)
USING DELTA
PARTITIONED BY (year, month, day)
LOCATION 's3://groundtruth-capstone/delta/bronze/weather/'
COMMENT 'Weather data for commodity-growing regions';

-- Market data table
CREATE TABLE IF NOT EXISTS market_data (
  date DATE,
  commodity STRING,
  open DOUBLE,
  high DOUBLE,
  low DOUBLE,
  close DOUBLE,
  volume BIGINT,
  year INT,
  month INT,
  day INT
)
USING DELTA
PARTITIONED BY (year, month, day)
LOCATION 's3://groundtruth-capstone/delta/bronze/market_data/'
COMMENT 'Commodity price data from Yahoo Finance';

-- VIX table
CREATE TABLE IF NOT EXISTS vix (
  date DATE,
  open DOUBLE,
  high DOUBLE,
  low DOUBLE,
  close DOUBLE,
  year INT,
  month INT,
  day INT
)
USING DELTA
PARTITIONED BY (year, month, day)
LOCATION 's3://groundtruth-capstone/delta/bronze/vix/'
COMMENT 'VIX volatility index';

-- FX rates table
CREATE TABLE IF NOT EXISTS fx_rates (
  date DATE,
  currency_pair STRING,
  rate DOUBLE,
  year INT,
  month INT,
  day INT
)
USING DELTA
PARTITIONED BY (year, month, day)
LOCATION 's3://groundtruth-capstone/delta/bronze/fx_rates/'
COMMENT 'Foreign exchange rates (COP/USD, VND/USD, etc.)';

-- CFTC positions table
CREATE TABLE IF NOT EXISTS cftc_positions (
  report_date DATE,
  commodity STRING,
  contract_type STRING,
  commercial_long BIGINT,
  commercial_short BIGINT,
  noncommercial_long BIGINT,
  noncommercial_short BIGINT,
  year INT,
  month INT
)
USING DELTA
PARTITIONED BY (year, month)
LOCATION 's3://groundtruth-capstone/delta/bronze/cftc_positions/'
COMMENT 'CFTC Commitments of Traders data';
```

**Silver Layer Table:**

```sql
USE SCHEMA silver;

-- Unified data table (SINGLE SOURCE OF TRUTH)
CREATE TABLE IF NOT EXISTS unified_data (
  date DATE,
  commodity STRING,
  region STRING,
  -- Market data (global level)
  close DOUBLE,
  volume BIGINT,
  -- VIX (global level)
  vix_close DOUBLE,
  -- FX rates (country level)
  fx_rate DOUBLE,
  currency_pair STRING,
  -- Weather data (region level)
  temp_c DOUBLE,
  humidity_pct DOUBLE,
  precipitation_mm DOUBLE,
  year INT,
  month INT,
  day INT
)
USING DELTA
PARTITIONED BY (commodity, year, month)
LOCATION 's3://groundtruth-capstone/delta/silver/unified_data/'
COMMENT 'Unified dataset combining all data sources at region-date-commodity level';
```

**Forecast Layer Tables:**

```sql
USE SCHEMA forecast;

-- Point forecasts table
CREATE TABLE IF NOT EXISTS point_forecasts (
  forecast_date DATE,
  prediction_date DATE,
  commodity STRING,
  model_version STRING,
  predicted_close DOUBLE,
  lower_bound DOUBLE,
  upper_bound DOUBLE,
  confidence_level DOUBLE,
  -- Metadata
  training_cutoff_date DATE,
  model_hyperparameters STRING,
  forecast_created_at TIMESTAMP,
  year INT,
  month INT
)
USING DELTA
PARTITIONED BY (model_version, year, month)
LOCATION 's3://groundtruth-capstone/delta/forecast/point_forecasts/'
COMMENT '14-day ahead point forecasts from all models';

-- Distributions table
CREATE TABLE IF NOT EXISTS distributions (
  forecast_date DATE,
  prediction_date DATE,
  commodity STRING,
  model_version STRING,
  path_id INT,
  simulated_close DOUBLE,
  -- Metadata
  forecast_created_at TIMESTAMP,
  year INT,
  month INT
)
USING DELTA
PARTITIONED BY (model_version, year, month)
LOCATION 's3://groundtruth-capstone/delta/forecast/distributions/'
COMMENT '2000 Monte Carlo paths for each forecast (risk analysis)';

-- Actuals table (for forecast evaluation)
CREATE TABLE IF NOT EXISTS actuals (
  date DATE,
  commodity STRING,
  actual_close DOUBLE,
  year INT,
  month INT
)
USING DELTA
PARTITIONED BY (year, month)
LOCATION 's3://groundtruth-capstone/delta/forecast/actuals/'
COMMENT 'Actual prices for forecast evaluation';
```

---

## Part 4: Cluster Configuration

### Step 4.1: Create Unity Catalog Cluster

**Via Databricks CLI:**

```bash
cd research_agent/infrastructure/databricks
databricks clusters create --json-file databricks_unity_catalog_cluster.json
```

**Cluster Config** (`databricks_unity_catalog_cluster.json`):
```json
{
  "cluster_name": "unity-catalog-cluster",
  "spark_version": "13.3.x-scala2.12",
  "node_type_id": "i3.xlarge",
  "driver_node_type_id": "i3.xlarge",
  "num_workers": 1,
  "autotermination_minutes": 60,
  "data_security_mode": "SINGLE_USER",
  "spark_conf": {
    "spark.databricks.unityCatalog.enabled": "true"
  },
  "custom_tags": {
    "purpose": "unity-catalog-queries",
    "project": "capstone"
  }
}
```

**Purpose**:
- Query Unity Catalog tables
- Run forecast models
- Trading agent data access

### Step 4.2: Create S3 Ingestion Cluster (Optional)

**Cluster Config** (`databricks_s3_ingestion_cluster.json`):
```json
{
  "cluster_name": "s3-ingestion-cluster",
  "spark_version": "13.3.x-scala2.12",
  "node_type_id": "i3.xlarge",
  "driver_node_type_id": "i3.xlarge",
  "num_workers": 2,
  "autotermination_minutes": 60,
  "aws_attributes": {
    "instance_profile_arn": "arn:aws:iam::534150427458:instance-profile/databricks-s3-ingest-profile"
  },
  "spark_conf": {
    "spark.databricks.delta.preview.enabled": "true"
  },
  "custom_tags": {
    "purpose": "s3-auto-loader",
    "project": "capstone"
  }
}
```

**Purpose**:
- Auto Loader jobs (landing -> bronze)
- Direct S3 processing without Unity Catalog overhead

**Note**: Only create this if needed. Unity Catalog cluster can handle most workloads.

---

## Part 5: Data Migration

### Step 5.1: Verify S3 Data Exists

```bash
# Check landing zones
aws s3 ls s3://groundtruth-capstone/landing/market_data/ --recursive | head -10
aws s3 ls s3://groundtruth-capstone/landing/weather_v2/ --recursive | head -10

# Check existing Delta tables (if any)
aws s3 ls s3://groundtruth-capstone/delta/bronze/weather/ --recursive | head -10
aws s3 ls s3://groundtruth-capstone/delta/silver/unified_data/ --recursive | head -10
```

**Expected**: Data already exists in S3, no copying needed.

### Step 5.2: Test Unity Catalog S3 Access

**Run in new workspace SQL Editor:**

```sql
-- Test reading from landing zone
SELECT * FROM json.`s3://groundtruth-capstone/landing/market_data/year=2024/month=11/day=01/*.jsonl` LIMIT 5;

-- Test reading config files
SELECT * FROM json.`s3://groundtruth-capstone/config/region_coordinates.json` LIMIT 5;

-- Test reading weather_v2
SELECT * FROM json.`s3://groundtruth-capstone/landing/weather_v2/year=2024/month=11/day=01/*.jsonl` LIMIT 5;
```

**Expected**: Data loads successfully from S3.

### Step 5.3: Load Weather v2 Data into Bronze Table

**Run in notebook on Unity Catalog cluster:**

```python
from pyspark.sql import functions as F

# Read weather_v2 from landing zone
df_weather = spark.read.json("s3://groundtruth-capstone/landing/weather_v2/")

# Transform to bronze schema
df_bronze = df_weather.select(
    F.col("date").cast("date"),
    F.col("commodity"),
    F.col("region"),
    F.col("temperature_2m_mean").alias("temp_c"),
    F.col("relative_humidity_2m_mean").alias("humidity_pct"),
    F.col("precipitation_sum").alias("precipitation_mm"),
    F.year("date").alias("year"),
    F.month("date").alias("month"),
    F.dayofmonth("date").alias("day")
)

# Write to Delta table (replace mode for migration)
df_bronze.write.format("delta").mode("overwrite").saveAsTable("commodity.bronze.weather")

print(f"✅ Loaded {df_bronze.count()} weather records into commodity.bronze.weather")
```

### Step 5.4: Rebuild Silver Layer (unified_data)

**If unified_data pipeline exists, re-run it. Otherwise:**

```python
# Load all bronze tables
df_weather = spark.table("commodity.bronze.weather")
df_market = spark.table("commodity.bronze.market_data")
df_vix = spark.table("commodity.bronze.vix")
df_fx = spark.table("commodity.bronze.fx_rates")

# Join logic (simplified - actual pipeline may differ)
df_unified = (
    df_market
    .join(df_vix, on="date", how="left")
    .join(df_fx, on="date", how="left")
    .join(df_weather, on=["date", "commodity", "region"], how="left")
)

# Write to silver layer
df_unified.write.format("delta").mode("overwrite").saveAsTable("commodity.silver.unified_data")

print(f"✅ Created unified_data with {df_unified.count()} rows")
```

---

## Part 6: Validation

### Step 6.1: Verify Unity Catalog Structure

```sql
-- Check catalogs
SHOW CATALOGS;

-- Check schemas
USE CATALOG commodity;
SHOW SCHEMAS;

-- Check tables in each schema
USE SCHEMA bronze;
SHOW TABLES;

USE SCHEMA silver;
SHOW TABLES;

USE SCHEMA forecast;
SHOW TABLES;
```

**Expected**: All schemas and tables exist.

### Step 6.2: Verify Table Counts

```sql
SELECT 'bronze.weather' as table_name, COUNT(*) as row_count FROM commodity.bronze.weather
UNION ALL
SELECT 'bronze.market_data', COUNT(*) FROM commodity.bronze.market_data
UNION ALL
SELECT 'bronze.vix', COUNT(*) FROM commodity.bronze.vix
UNION ALL
SELECT 'silver.unified_data', COUNT(*) FROM commodity.silver.unified_data;
```

**Expected**: Reasonable row counts (millions of weather rows, hundreds of thousands for unified_data).

### Step 6.3: Test Unity Catalog Queries from Notebook

**Attach notebook to `unity-catalog-cluster` and run:**

```python
# Test 1: USE CATALOG (this was hanging in old workspace)
spark.sql("USE CATALOG commodity")
print("✅ USE CATALOG works!")

# Test 2: Query table
df = spark.sql("SELECT COUNT(*) as count FROM commodity.bronze.weather")
df.show()
print("✅ Queries work!")

# Test 3: Load unified_data for forecast models
df_unified = spark.table("commodity.silver.unified_data")
print(f"✅ Loaded unified_data: {df_unified.count()} rows")
df_unified.printSchema()
```

**Expected**: All queries complete without hanging.

### Step 6.4: Test July 2021 Frost Event

**Verify corrected weather captures known frost:**

```python
from pyspark.sql import functions as F

# Query July 2021 Brazil frost event
df_frost = spark.sql("""
    SELECT date, region, temp_c, commodity
    FROM commodity.bronze.weather
    WHERE commodity = 'Coffee'
      AND region IN ('Minas Gerais', 'Sao Paulo', 'Parana')
      AND date BETWEEN '2021-07-18' AND '2021-07-22'
    ORDER BY date, region
""")

df_frost.show(50, truncate=False)

# Check minimum temperatures
df_frost.groupBy("region").agg(
    F.min("temp_c").alias("min_temp"),
    F.avg("temp_c").alias("avg_temp")
).show()
```

**Expected**: Minimum temperatures near or below 0°C for this period (frost event).

---

## Part 7: Update Configuration

### Step 7.1: Update Connection Strings

**Files to update:**

1. **`research_agent/infrastructure/unity_catalog_workaround.py`** (if still using SQL connector):
```python
DATABRICKS_HOST = "<NEW_WORKSPACE>.cloud.databricks.com"
DATABRICKS_HTTP_PATH = "/sql/1.0/warehouses/<NEW_WAREHOUSE_ID>"
DATABRICKS_TOKEN = "<NEW_TOKEN>"
```

2. **Team members' local environments:**
```bash
export DATABRICKS_HOST="https://<NEW_WORKSPACE>.cloud.databricks.com"
export DATABRICKS_TOKEN="<NEW_TOKEN>"
```

3. **Lambda functions** (if any call Databricks):
   - Update environment variables in AWS Lambda console

### Step 7.2: Update Databricks CLI Configuration

```bash
databricks configure --token
# Follow prompts with new workspace URL and token
```

### Step 7.3: Test Cluster Creation Script

```bash
cd research_agent/infrastructure/databricks
python create_databricks_clusters.py
```

**Expected**: Clusters create successfully without init script errors.

---

## Part 8: Team Onboarding

### Step 8.1: Invite Team Members

1. Go to **Settings** > **Identity & Access** > **Users**
2. Add team members:
   - Francisco (Research Agent)
   - Connor (Forecast Agent)
   - Mark (Trading Agent)
3. Assign appropriate permissions

### Step 8.2: Share Cluster Access

**Grant cluster access:**
```sql
-- If needed, grant USE SCHEMA permissions
GRANT USAGE ON CATALOG commodity TO `<user>@<domain>.com`;
GRANT USAGE ON SCHEMA commodity.bronze TO `<user>@<domain>.com`;
GRANT USAGE ON SCHEMA commodity.silver TO `<user>@<domain>.com`;
GRANT USAGE ON SCHEMA commodity.forecast TO `<user>@<domain>.com`;
GRANT SELECT ON commodity.silver.unified_data TO `<user>@<domain>.com`;
```

### Step 8.3: Documentation Updates

**Update README files with:**
- New workspace URL
- New SQL Warehouse endpoint
- Cluster names and IDs
- Connection instructions

---

## Part 9: Post-Migration Cleanup

### Step 9.1: Verify Old Workspace Can Be Decommissioned

**Checklist:**
- [ ] All data verified in new workspace
- [ ] All models retrained on new workspace
- [ ] Team members have access to new workspace
- [ ] Notebooks migrated (via git repo)
- [ ] No active jobs running in old workspace

### Step 9.2: Decommission Old Workspace (Optional)

**WARNING**: Only after thorough validation.

1. In Databricks Account Console
2. Go to **Workspaces**
3. Select old workspace
4. Click **Delete Workspace**

### Step 9.3: Clean Up Old IAM Resources (Optional)

**WARNING**: Only if not used elsewhere.

```bash
# List old roles
aws iam list-roles --query 'Roles[?contains(RoleName, `databricks-otxszqwuhb1lbkqvfac5kd`)].[RoleName]' --output table

# Do NOT delete yet - verify nothing references these roles
```

---

## Rollback Plan

If migration fails:

1. **Keep old workspace active** until new workspace is fully validated
2. **Revert connection strings** to old workspace
3. **Continue using workaround** (`databricks-sql-connector` library)
4. **Escalate to Databricks Support** for Private Access Settings removal

---

## Migration Checklist

### Pre-Migration
- [ ] Weather backfill v2 completed
- [ ] S3 data backed up (if needed)
- [ ] IAM roles documented
- [ ] Team notified of migration window

### Migration Day
- [ ] Create new Databricks account
- [ ] Configure IAM roles and trust policies
- [ ] Create Unity Catalog metastore
- [ ] Configure external locations
- [ ] Create catalog/schema structure
- [ ] Create Delta tables
- [ ] Load weather v2 data
- [ ] Rebuild silver layer
- [ ] Create clusters
- [ ] Test Unity Catalog queries
- [ ] Verify July 2021 frost event captured

### Post-Migration
- [ ] Update connection strings in code
- [ ] Update team documentation
- [ ] Invite team members
- [ ] Train team on new workspace
- [ ] Monitor for issues (first 48 hours)
- [ ] Decommission old workspace (after 1 week of stability)

---

## Troubleshooting

### Issue: Unity Catalog queries still hang in new workspace

**Cause**: Private Access Settings still enabled (should NOT happen in new account)

**Solution**:
1. Check: Settings > Workspace Admin > Network > Private Access Settings
2. If Private Access Settings exist, contact Databricks Support immediately
3. Request removal of Private Access Settings

### Issue: IAM role trust relationship errors

**Cause**: Wrong external ID or trust policy

**Solution**:
1. Get correct external ID from Databricks account setup wizard
2. Update trust policy:
```bash
aws iam update-assume-role-policy \
  --role-name databricks-s3-access-role \
  --policy-document file://databricks-s3-trust-policy.json
```

### Issue: Cannot read from S3

**Cause**: Storage credential not configured correctly

**Solution**:
1. Verify IAM role exists and has S3 permissions
2. Re-run storage credential creation
3. Test with simple query:
```sql
SELECT * FROM json.`s3://groundtruth-capstone/config/region_coordinates.json` LIMIT 1;
```

### Issue: Tables show 0 rows

**Cause**: Data not loaded or wrong S3 paths

**Solution**:
1. Check S3 locations:
```bash
aws s3 ls s3://groundtruth-capstone/delta/bronze/weather/
```
2. Verify external location URLs match S3 paths
3. Re-run data loading scripts

---

## Success Criteria

Migration is successful when:

1. ✅ Unity Catalog queries work without hanging
2. ✅ `spark.sql("USE CATALOG commodity")` completes instantly
3. ✅ All bronze/silver/forecast tables accessible
4. ✅ Weather v2 data loaded with corrected coordinates
5. ✅ July 2021 frost event visible in data
6. ✅ Team can run forecast models on new workspace
7. ✅ Trading agent can query `commodity.silver.unified_data`
8. ✅ No PrivateLink errors in cluster logs

---

## Contact & Support

**Internal Team:**
- Francisco: Research agent data pipeline
- Connor: Forecast models and validation
- Mark: Trading agent integration

**External Resources:**
- Databricks Documentation: https://docs.databricks.com/
- Unity Catalog Setup: https://docs.databricks.com/data-governance/unity-catalog/
- AWS IAM Roles: https://docs.aws.amazon.com/IAM/latest/UserGuide/

---

## Appendix: Quick Reference

### Key ARNs
```
Cross-Account Role:       arn:aws:iam::534150427458:role/databricks-cross-account-role
S3 Access Role:           arn:aws:iam::534150427458:role/databricks-s3-access-role
Instance Profile:         arn:aws:iam::534150427458:instance-profile/databricks-s3-ingest-profile
S3 Bucket:               s3://groundtruth-capstone/
```

### Unity Catalog Structure
```
commodity (catalog)
├── bronze (schema)
│   ├── weather
│   ├── market_data
│   ├── vix
│   ├── fx_rates
│   └── cftc_positions
├── silver (schema)
│   └── unified_data
└── forecast (schema)
    ├── point_forecasts
    ├── distributions
    └── actuals
```

### Cluster Configs Location
```
research_agent/infrastructure/databricks/
├── databricks_unity_catalog_cluster.json
├── databricks_s3_ingestion_cluster.json
└── create_databricks_clusters.py
```

### Unity Catalog Setup Scripts
```
research_agent/infrastructure/databricks/
├── databricks_unity_catalog_storage_setup.sql
└── setup_unity_catalog_credentials.py
```
