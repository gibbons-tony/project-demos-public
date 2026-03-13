-- Create GDELT Bronze external table pointing to S3 Parquet
CREATE TABLE IF NOT EXISTS commodity.bronze.gdelt_bronze (
  article_date DATE,
  source_url STRING,
  themes STRING,
  locations STRING,
  all_names STRING,
  tone_avg DOUBLE,
  tone_positive DOUBLE,
  tone_negative DOUBLE,
  tone_polarity DOUBLE,
  has_coffee BOOLEAN,
  has_sugar BOOLEAN
)
USING PARQUET
LOCATION 's3://groundtruth-capstone/processed/gdelt/bronze/gdelt/';