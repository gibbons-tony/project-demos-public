"""
Simple script to check prediction_date ranges for coffee models
"""
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

models = ['xgboost_weather_v1', 'synthetic_acc100', 'synthetic_acc90', 'synthetic_acc60', 'sarimax_auto_weather_v1']

print("=" * 100)
print("PREDICTION DATE RANGES FOR COFFEE MODELS")
print("=" * 100)

results = {}
for model in models:
    df = spark.sql(f"""
        SELECT
            MIN(prediction_date) as first_pred,
            MAX(prediction_date) as last_pred,
            COUNT(DISTINCT prediction_date) as n_dates
        FROM commodity.forecast.distributions
        WHERE model_version = '{model}'
            AND commodity = 'coffee'
            AND is_actuals = false
    """)
    
    row = df.first()
    results[model] = row
    
    print(f"\n{model}:")
    if row and row.n_dates > 0:
        print(f"  First: {row.first_pred}")
        print(f"  Last: {row.last_pred}")
        print(f"  Dates: {row.n_dates}")
    else:
        print(f"  NO PREDICTIONS")

print("\n" + "=" * 100)
print("COMPARISON")
print("=" * 100)

first_dates = {m: r.first_pred for m, r in results.items() if r and r.n_dates > 0}
last_dates = {m: r.last_pred for m, r in results.items() if r and r.n_dates > 0}

if len(set(first_dates.values())) == 1 and len(set(last_dates.values())) == 1:
    print("\n✅ ALL MODELS HAVE IDENTICAL RANGES")
    print(f"   Range: {list(first_dates.values())[0]} to {list(last_dates.values())[0]}")
else:
    print("\n⚠️  MODELS HAVE DIFFERENT RANGES")
    for m in sorted(first_dates.keys()):
        print(f"  {m}: {first_dates[m]} to {last_dates[m]}")

print("\n" + "=" * 100)
