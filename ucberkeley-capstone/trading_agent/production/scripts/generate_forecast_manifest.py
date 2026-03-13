"""
Generate forecast manifest by querying commodity.forecast.distributions table
This creates the manifest file that data_loader expects
"""
import sys
import os
import json
from datetime import datetime, timedelta
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

def generate_manifest_for_commodity(spark, commodity, volume_path):
    """Generate forecast manifest by querying distributions table"""
    
    print(f"\n{'='*80}")
    print(f"GENERATING FORECAST MANIFEST FOR {commodity.upper()}")
    print(f"{'='*80}")
    
    # Get all model versions for this commodity
    # Note: commodity column is capitalized in table ('Coffee', 'Sugar')
    commodity_capitalized = commodity.capitalize()
    models_df = spark.sql(f"""
        SELECT DISTINCT model_version
        FROM commodity.forecast.distributions
        WHERE commodity = '{commodity_capitalized}'
            AND is_actuals = false
        ORDER BY model_version
    """)
    
    model_versions = [row.model_version for row in models_df.collect()]
    print(f"\nFound {len(model_versions)} models: {model_versions}")
    
    manifest = {
        'commodity': commodity,
        'generated_at': datetime.now().isoformat(),
        'models': {}
    }
    
    for model_version in model_versions:
        print(f"\nProcessing {model_version}...")
        
        # Get forecast date coverage (using forecast_start_date not prediction_date)
        coverage_df = spark.sql(f"""
            SELECT
                MIN(forecast_start_date) as first_pred,
                MAX(forecast_start_date) as last_pred,
                COUNT(DISTINCT forecast_start_date) as n_dates,
                COUNT(DISTINCT YEAR(forecast_start_date)) as n_years
            FROM commodity.forecast.distributions
            WHERE commodity = '{commodity_capitalized}'
                AND model_version = '{model_version}'
                AND is_actuals = false
        """)
        
        row = coverage_df.first()
        
        if row and row.n_dates > 0:
            # Calculate years span
            first_date = datetime.strptime(str(row.first_pred), '%Y-%m-%d')
            last_date = datetime.strptime(str(row.last_pred), '%Y-%m-%d')
            years_span = (last_date - first_date).days / 365.25
            expected_days = (last_date - first_date).days + 1
            coverage_pct = (row.n_dates / expected_days) * 100
            
            # Determine quality
            if coverage_pct >= 90 and years_span >= 5:
                quality = 'EXCELLENT'
                meets_criteria = True
            elif coverage_pct >= 70 and years_span >= 3:
                quality = 'GOOD'
                meets_criteria = True
            elif coverage_pct >= 50:
                quality = 'MARGINAL'
                meets_criteria = False
            else:
                quality = 'SPARSE'
                meets_criteria = False
            
            manifest['models'][model_version] = {
                'type': 'synthetic' if 'synthetic' in model_version else 'real',
                'date_range': {
                    'start': str(row.first_pred),
                    'end': str(row.last_pred)
                },
                'years_span': round(years_span, 2),
                'expected_days': expected_days,
                'prediction_dates': row.n_dates,
                'coverage_pct': round(coverage_pct, 2),
                'years_available': row.n_years,
                'meets_criteria': meets_criteria,
                'quality': quality,
                'validation_thresholds': {
                    'min_coverage_pct': 70,
                    'min_years_span': 3
                },
                'n_paths': 'N/A',  # Would need to query distributions to count
                'pickle_file': f'prediction_matrices_{commodity.lower()}_{model_version}.pkl'
            }
            
            print(f"  ✓ {str(row.first_pred)} to {str(row.last_pred)}")
            print(f"    {row.n_dates} dates, {round(coverage_pct, 1)}% coverage, {quality}")
        else:
            print(f"  ⚠️  No predictions found")
    
    # Ensure volume directory exists
    os.makedirs(volume_path, exist_ok=True)
    
    # Write manifest
    manifest_path = os.path.join(volume_path, f'forecast_manifest_{commodity}.json')
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\n{'='*80}")
    print(f"✅ MANIFEST CREATED: {manifest_path}")
    print(f"   Models included: {len(manifest['models'])}")
    print(f"{'='*80}")
    
    return manifest_path

def main():
    spark = SparkSession.builder.getOrCreate()
    
    # Get config
    sys.path.insert(0, '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent')
    from production.config import VOLUME_PATH, COMMODITY_CONFIGS
    
    # Generate for all commodities
    commodities = list(COMMODITY_CONFIGS.keys())
    
    for commodity in commodities:
        try:
            manifest_path = generate_manifest_for_commodity(spark, commodity, VOLUME_PATH)
        except Exception as e:
            print(f"\n❌ ERROR processing {commodity}: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*80}")
    print("MANIFEST GENERATION COMPLETE")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
