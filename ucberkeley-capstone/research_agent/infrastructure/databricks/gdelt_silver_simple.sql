CREATE TABLE IF NOT EXISTS commodity.silver.gdelt_wide (
  article_date DATE,
  -- Theme group aggregations (SUPPLY, LOGISTICS, TRADE, MARKET, POLICY, CORE, OTHER)
  group_SUPPLY_count BIGINT,
  group_SUPPLY_tone_avg DOUBLE,
  group_SUPPLY_tone_positive DOUBLE,
  group_SUPPLY_tone_negative DOUBLE,
  group_SUPPLY_tone_polarity DOUBLE,

  group_LOGISTICS_count BIGINT,
  group_LOGISTICS_tone_avg DOUBLE,
  group_LOGISTICS_tone_positive DOUBLE,
  group_LOGISTICS_tone_negative DOUBLE,
  group_LOGISTICS_tone_polarity DOUBLE,

  group_TRADE_count BIGINT,
  group_TRADE_tone_avg DOUBLE,
  group_TRADE_tone_positive DOUBLE,
  group_TRADE_tone_negative DOUBLE,
  group_TRADE_tone_polarity DOUBLE,

  group_MARKET_count BIGINT,
  group_MARKET_tone_avg DOUBLE,
  group_MARKET_tone_positive DOUBLE,
  group_MARKET_tone_negative DOUBLE,
  group_MARKET_tone_polarity DOUBLE,

  group_POLICY_count BIGINT,
  group_POLICY_tone_avg DOUBLE,
  group_POLICY_tone_positive DOUBLE,
  group_POLICY_tone_negative DOUBLE,
  group_POLICY_tone_polarity DOUBLE,

  group_CORE_count BIGINT,
  group_CORE_tone_avg DOUBLE,
  group_CORE_tone_positive DOUBLE,
  group_CORE_tone_negative DOUBLE,
  group_CORE_tone_polarity DOUBLE,

  group_OTHER_count BIGINT,
  group_OTHER_tone_avg DOUBLE,
  group_OTHER_tone_positive DOUBLE,
  group_OTHER_tone_negative DOUBLE,
  group_OTHER_tone_polarity DOUBLE,

  -- Individual theme columns (theme_THEMENAME_count, theme_THEMENAME_tone_avg, etc.)
  -- Note: Actual columns will vary based on themes present in the data
  -- Parquet schema inference will handle this automatically
  commodity STRING
)
USING PARQUET
PARTITIONED BY (commodity)
LOCATION 's3://groundtruth-capstone/processed/gdelt/silver/gdelt_wide/';
