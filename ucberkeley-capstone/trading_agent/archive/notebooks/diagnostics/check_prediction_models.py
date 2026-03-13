"""
Quick script to check available prediction models in Delta table
"""

from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

print("=" * 80)
print("AVAILABLE PREDICTION MODELS")
print("=" * 80)

# Get distinct model versions
models_df = spark.sql("""
    SELECT
        model_version,
        COUNT(*) as prediction_count,
        MIN(timestamp) as first_prediction,
        MAX(timestamp) as last_prediction
    FROM commodity.trading_agent.predictions_coffee
    GROUP BY model_version
    ORDER BY model_version
""")

print("\nCoffee Predictions:")
models_df.show(truncate=False)

# Get sample predictions for each model to check quality
print("\n" + "=" * 80)
print("SAMPLE PREDICTION STATISTICS")
print("=" * 80)

for model_row in models_df.collect():
    model_version = model_row['model_version']
    print(f"\nModel: {model_version}")
    print("-" * 60)

    # Get coefficient of variation for sample timestamp
    stats_df = spark.sql(f"""
        SELECT
            timestamp,
            day_ahead,
            AVG(predicted_price) as mean_price,
            STDDEV(predicted_price) as std_price,
            STDDEV(predicted_price) / AVG(predicted_price) as cv
        FROM commodity.trading_agent.predictions_coffee
        WHERE model_version = '{model_version}'
        GROUP BY timestamp, day_ahead
        ORDER BY timestamp DESC, day_ahead
        LIMIT 14
    """)

    stats_pd = stats_df.toPandas()
    if len(stats_pd) > 0:
        sample_ts = stats_pd['timestamp'].iloc[0]
        print(f"  Sample timestamp: {sample_ts}")
        print(f"  Average CV across horizons: {stats_pd['cv'].mean():.4f}")
        print(f"  Min CV: {stats_pd['cv'].min():.4f}")
        print(f"  Max CV: {stats_pd['cv'].max():.4f}")
    else:
        print("  No data available")

print("\n" + "=" * 80)
print("DONE")
print("=" * 80)
