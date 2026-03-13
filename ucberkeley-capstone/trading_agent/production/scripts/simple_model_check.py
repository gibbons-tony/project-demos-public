"""Simple check of which models are in predictions tables"""

from pyspark.sql import SparkSession

spark = SparkSession.builder.appName("CheckModels").getOrCreate()

print("=" * 80)
print("CHECKING WHICH MODELS ARE IN PREDICTIONS TABLES")
print("=" * 80)

# Coffee synthetic
print("\n1. Coffee Synthetic (predictions_coffee):")
try:
    df = spark.sql("SELECT DISTINCT model_version FROM commodity.trading_agent.predictions_coffee ORDER BY model_version")
    models = [row.model_version for row in df.collect()]
    print(f"   {len(models)} models: {models}")
except Exception as e:
    print(f"   Error: {e}")

# Coffee real
print("\n2. Coffee Real (forecast.distributions):")
try:
    df = spark.sql("SELECT DISTINCT model_version FROM commodity.forecast.distributions WHERE commodity = 'Coffee' AND is_actuals = false ORDER BY model_version")
    models = [row.model_version for row in df.collect()]
    print(f"   {len(models)} models: {models}")
except Exception as e:
    print(f"   Error: {e}")

# Sugar synthetic
print("\n3. Sugar Synthetic (predictions_sugar):")
try:
    df = spark.sql("SELECT DISTINCT model_version FROM commodity.trading_agent.predictions_sugar ORDER BY model_version")
    models = [row.model_version for row in df.collect()]
    print(f"   {len(models)} models: {models}")
except Exception as e:
    print(f"   Error: {e}")

# Sugar real
print("\n4. Sugar Real (forecast.distributions):")
try:
    df = spark.sql("SELECT DISTINCT model_version FROM commodity.forecast.distributions WHERE commodity = 'Sugar' AND is_actuals = false ORDER BY model_version")
    models = [row.model_version for row in df.collect()]
    print(f"   {len(models)} models: {models}")
except Exception as e:
    print(f"   Error: {e}")

print("\n" + "=" * 80)
