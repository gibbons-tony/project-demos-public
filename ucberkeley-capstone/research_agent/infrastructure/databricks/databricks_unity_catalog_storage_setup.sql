-- Unity Catalog Storage Credentials and External Locations Setup
--
-- Purpose: Configure Unity Catalog to access S3 buckets for the commodity forecasting platform
--
-- Prerequisites:
--   1. AWS IAM role with S3 access (arn:aws:iam::534150427458:role/databricks-s3-access-role)
--   2. Trust relationship configured between Databricks and AWS
--   3. Admin permissions in Databricks Unity Catalog
--
-- Run this in: Databricks SQL Editor (as admin user)
--
-- After running this:
--   - Unity Catalog clusters can access S3 without instance profiles
--   - No S3 credential conflicts with cluster configurations
--   - Secure, centralized S3 access management

-- ============================================================================
-- STEP 1: Create Storage Credential
-- ============================================================================

-- This allows Unity Catalog to assume an AWS IAM role for S3 access
CREATE STORAGE CREDENTIAL IF NOT EXISTS s3_groundtruth_capstone
USING AWS_IAM_ROLE
WITH (
  role_arn = 'arn:aws:iam::534150427458:role/databricks-s3-access-role'
)
COMMENT 'Storage credential for groundtruth-capstone S3 buckets';

-- Verify creation
DESCRIBE STORAGE CREDENTIAL s3_groundtruth_capstone;

-- ============================================================================
-- STEP 2: Create External Locations for S3 Buckets
-- ============================================================================

-- Main data bucket - landing zone for all raw data
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

-- Verify creation
SHOW EXTERNAL LOCATIONS;

-- ============================================================================
-- STEP 3: Grant Permissions to Users/Groups
-- ============================================================================

-- Grant READ FILES permission on external locations to all users
-- (Adjust as needed for your security requirements)

GRANT READ FILES ON EXTERNAL LOCATION groundtruth_landing TO `account users`;
GRANT READ FILES ON EXTERNAL LOCATION groundtruth_bronze TO `account users`;
GRANT READ FILES ON EXTERNAL LOCATION groundtruth_silver TO `account users`;
GRANT READ FILES ON EXTERNAL LOCATION groundtruth_forecast TO `account users`;
GRANT READ FILES ON EXTERNAL LOCATION groundtruth_config TO `account users`;
GRANT READ FILES ON EXTERNAL LOCATION groundtruth_weather_v2 TO `account users`;

-- Grant WRITE FILES permission to data engineers (adjust group name as needed)
-- GRANT WRITE FILES ON EXTERNAL LOCATION groundtruth_landing TO `data_engineers`;
-- GRANT WRITE FILES ON EXTERNAL LOCATION groundtruth_bronze TO `data_engineers`;
-- GRANT WRITE FILES ON EXTERNAL LOCATION groundtruth_silver TO `data_engineers`;

-- ============================================================================
-- STEP 4: Test S3 Access from Unity Catalog
-- ============================================================================

-- Test reading from landing zone
SELECT * FROM json.`s3://groundtruth-capstone/landing/market_data/year=2024/month=11/day=01/*.json` LIMIT 5;

-- Test reading config files
SELECT * FROM json.`s3://groundtruth-capstone/config/region_coordinates.json` LIMIT 5;

-- ============================================================================
-- STEP 5: Verify Unity Catalog Tables Can Access S3
-- ============================================================================

-- These tables should now work on the Unity Catalog cluster:
SELECT COUNT(*) FROM commodity.bronze.weather;
SELECT COUNT(*) FROM commodity.silver.unified_data;
SELECT COUNT(*) FROM commodity.forecast.point_forecasts;

-- ============================================================================
-- ROLLBACK (if needed)
-- ============================================================================

-- If you need to remove and recreate:
/*
DROP EXTERNAL LOCATION IF EXISTS groundtruth_landing;
DROP EXTERNAL LOCATION IF EXISTS groundtruth_bronze;
DROP EXTERNAL LOCATION IF EXISTS groundtruth_silver;
DROP EXTERNAL LOCATION IF EXISTS groundtruth_forecast;
DROP EXTERNAL LOCATION IF EXISTS groundtruth_config;
DROP EXTERNAL LOCATION IF EXISTS groundtruth_weather_v2;
DROP STORAGE CREDENTIAL IF EXISTS s3_groundtruth_capstone;
*/

-- ============================================================================
-- Summary
-- ============================================================================

/*
What This Does:
1. Creates storage credential using AWS IAM role
2. Maps S3 bucket paths to Unity Catalog external locations
3. Grants permissions for users to read/write files
4. Allows Unity Catalog clusters to access S3 WITHOUT instance profiles

Benefits:
- ✅ No S3 credential conflicts on Unity Catalog clusters
- ✅ Centralized S3 access management
- ✅ Fine-grained permissions (who can read/write which buckets)
- ✅ Compatible with Unity Catalog security model
- ✅ Works seamlessly with Delta tables

Usage:
- Unity Catalog cluster: Access S3 via storage credentials (this setup)
- S3 ingestion cluster: Access S3 via instance profile (for Auto Loader)

Next Steps:
1. Create Unity Catalog cluster using infra/databricks_unity_catalog_cluster.json
2. Attach notebooks to Unity Catalog cluster
3. Test queries on commodity.bronze.* and commodity.silver.* tables
4. Enjoy fast Unity Catalog queries! ✨
*/
