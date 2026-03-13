"""
Complete Analysis Flow - Run Everything End-to-End

Purpose:
    Single script to run the complete trading agent analysis pipeline:
    1. Generate forecast manifests (discover available models)
    2. Load forecast predictions from database
    3. (Optional) Optimize strategy parameters
    4. Run backtests for all strategies and models
    5. Run statistical tests to validate profitability
    6. Generate summary report

Usage:
    # Full flow with optimization
    python production/scripts/run_complete_analysis_flow.py --optimize

    # Quick flow without optimization (use existing params)
    python production/scripts/run_complete_analysis_flow.py

    # Single commodity
    python production/scripts/run_complete_analysis_flow.py --commodity coffee

    # Skip statistical tests (just backtest)
    python production/scripts/run_complete_analysis_flow.py --skip-stats

Returns:
    Exit code 0 on success, 1 on failure
    Generates comprehensive summary report
"""

import sys
import os
import json
import argparse
from datetime import datetime
from pathlib import Path

# Add trading_agent to path for local execution
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    trading_agent_dir = os.path.dirname(os.path.dirname(script_dir))
    sys.path.insert(0, trading_agent_dir)
except NameError:
    # Running in Databricks
    sys.path.insert(0, '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent')

from pyspark.sql import SparkSession
from production.config import COMMODITY_CONFIGS, VOLUME_PATH, OUTPUT_SCHEMA


def print_section(title):
    """Print formatted section header"""
    print("\n" + "=" * 100)
    print(f"{title:^100}")
    print("=" * 100 + "\n")


def run_step(step_name, func, *args, **kwargs):
    """
    Run a step and track success/failure

    Args:
        step_name: Human-readable step name
        func: Function to execute
        *args, **kwargs: Arguments to pass to function

    Returns:
        Tuple of (success, result, error_msg)
    """
    print_section(f"STEP: {step_name}")
    start_time = datetime.now()

    try:
        result = func(*args, **kwargs)
        duration = (datetime.now() - start_time).total_seconds()
        print(f"\n✓ {step_name} completed successfully ({duration:.1f}s)")
        return True, result, None
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        print(f"\n✗ {step_name} failed ({duration:.1f}s)")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False, None, str(e)


def step_generate_manifests(spark, commodities):
    """Step 1: Generate forecast manifests"""
    from production.scripts.generate_forecast_manifest import generate_manifest_for_commodity

    volume_path = Path(VOLUME_PATH)
    manifests = {}

    for commodity in commodities:
        print(f"\nGenerating manifest for {commodity.upper()}...")
        manifest = generate_manifest_for_commodity(spark, commodity, str(volume_path))
        manifests[commodity] = manifest

        if manifest and 'models' in manifest:
            print(f"  ✓ Found {len(manifest['models'])} models")
            excellent = sum(1 for m in manifest['models'].values() if m.get('quality') == 'EXCELLENT')
            good = sum(1 for m in manifest['models'].values() if m.get('quality') == 'GOOD')
            print(f"    - EXCELLENT: {excellent}, GOOD: {good}")
        else:
            print(f"  ⚠️  No models found for {commodity}")

    return manifests


def step_load_predictions(spark, commodities):
    """Step 2: Load forecast predictions from database"""
    from production.scripts.load_forecast_predictions import run_forecast_predictions

    print(f"\nLoading predictions for commodities: {', '.join(commodities)}")

    # Call run_forecast_predictions which handles all commodities
    result = run_forecast_predictions(commodities=commodities)

    return result


def step_optimize_parameters(spark, commodities, manifests):
    """
    Step 3: Optimize strategy parameters (optional)

    Uses manifest from Step 1 to determine which models to optimize.
    Runs optimization separately for each (commodity, model_version) combination.

    Args:
        spark: SparkSession
        commodities: List of commodity names
        manifests: Dict of manifest results from Step 1 (contains available models)

    Returns:
        Dict of optimization results keyed by (commodity, model_version)
    """
    from production.optimization.run_parameter_optimization import run_optimization

    results = {}

    for commodity in commodities:
        print(f"\n{'='*80}")
        print(f"OPTIMIZING PARAMETERS FOR {commodity.upper()}")
        print(f"{'='*80}")

        # Load manifest to get available models
        manifest_path = manifests.get(commodity)
        if not manifest_path:
            print(f"  ⚠️  No manifest found for {commodity}, skipping optimization")
            continue

        try:
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
        except Exception as e:
            print(f"  ✗ Failed to load manifest: {e}")
            continue

        models = manifest.get('models', {})
        if not models:
            print(f"  ⚠️  No models in manifest for {commodity}")
            continue

        print(f"\nFound {len(models)} models to optimize:")
        for model_name, model_info in models.items():
            quality = model_info.get('quality', 'UNKNOWN')
            meets_criteria = model_info.get('meets_criteria', False)
            status = '✓' if meets_criteria else '⚠️'
            print(f"  {status} {model_name}: {quality}")

        # Optimize each model separately
        commodity_results = {}
        for model_version in models.keys():
            print(f"\n  Optimizing {model_version}...")
            try:
                result = run_optimization(
                    spark=spark,
                    commodity=commodity,
                    model_version=model_version,
                    n_trials=100  # Reduced for faster execution
                )
                commodity_results[model_version] = result
                print(f"    ✓ {model_version} optimization complete")
            except Exception as e:
                print(f"    ✗ {model_version} optimization failed: {e}")
                commodity_results[model_version] = {'error': str(e)}

        results[commodity] = commodity_results

    return results


def step_run_backtests(spark, commodities, use_optimized_params=True):
    """Step 4: Run backtests for all strategies and models"""
    from production.runners.multi_commodity_runner import MultiCommodityRunner

    # Filter commodities
    commodity_configs = {k: v for k, v in COMMODITY_CONFIGS.items() if k in commodities}

    print(f"\nRunning backtests for: {list(commodity_configs.keys())}")
    print(f"Using optimized params: {use_optimized_params}")

    runner = MultiCommodityRunner(
        spark=spark,
        commodity_configs=commodity_configs,
        volume_path=VOLUME_PATH,
        output_schema=OUTPUT_SCHEMA,
        use_optimized_params=use_optimized_params,
        run_statistical_tests=False  # We'll run these separately
    )

    results = runner.run_all_commodities(verbose=True)

    # Get summary statistics
    summary = runner.get_summary()

    print(f"\n✓ Backtests completed")
    print(f"  Total combinations: {summary['total_combinations']}")
    print(f"  Commodities: {', '.join(summary['commodities'])}")
    for commodity in summary['commodities']:
        print(f"    - {commodity}: {summary[f'{commodity}_models']} models")

    return results


def step_run_statistical_tests(spark, commodities):
    """Step 5: Run multi-granularity statistical tests"""
    from production.analysis.multi_granularity_stats import (
        run_multi_commodity_granular_analysis,
        print_granular_summary
    )

    print_section("5. Multi-Granularity Statistical Tests")
    print("Testing strategy performance at year/quarter/month granularities")
    print(f"Commodities: {', '.join(commodities)}")

    # Run analysis for all commodities and models
    results = run_multi_commodity_granular_analysis(
        spark=spark,
        commodities=commodities,
        schema=OUTPUT_SCHEMA,
        verbose=True
    )

    # Print summary
    print_granular_summary(results)

    # Check for filtering validation: verify years match manifest ranges
    print(f"\n{'=' * 80}")
    print("FILTERING VALIDATION")
    print(f"{'=' * 80}")

    for commodity in commodities:
        # Load manifest to check expected date ranges
        manifest_path = f'{VOLUME_PATH}/forecast_manifest_{commodity}.json'
        try:
            import json
            import os
            if os.path.exists(manifest_path):
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)

                print(f"\n{commodity.upper()}:")
                for model, model_results in results[commodity].items():
                    if model in manifest['models']:
                        expected_years = manifest['models'][model]['years_available']
                        year_result = model_results.get('year', {})

                        if year_result.get('status') == 'success':
                            actual_years = [int(y) for y in year_result['periods']]
                            years_match = sorted(actual_years) == sorted(expected_years)

                            if years_match:
                                print(f"  ✓ {model}: Years match manifest {expected_years}")
                            else:
                                print(f"  ✗ {model}: Year mismatch!")
                                print(f"      Expected: {expected_years}")
                                print(f"      Actual: {actual_years}")
                        else:
                            print(f"  ⚠️  {model}: No year data ({year_result.get('status')})")
        except Exception as e:
            print(f"  ⚠️  Could not validate filtering: {e}")

    return results


def generate_summary_report(flow_results):
    """Generate comprehensive summary report"""
    print_section("COMPLETE ANALYSIS FLOW - SUMMARY REPORT")

    print(f"Execution Time: {flow_results['end_time']}")
    print(f"Total Duration: {flow_results['duration_seconds']:.1f}s ({flow_results['duration_seconds']/60:.1f} minutes)")
    print(f"\nCommodities Processed: {', '.join(flow_results['commodities'])}")

    # Step summaries
    print("\n" + "-" * 100)
    print("STEP RESULTS:")
    print("-" * 100)

    for step_name, step_result in flow_results['steps'].items():
        status = "✓" if step_result['success'] else "✗"
        print(f"{status} {step_name}: {step_result['duration']:.1f}s")
        if not step_result['success']:
            print(f"    Error: {step_result.get('error', 'Unknown error')}")

    # Statistical test summary
    if flow_results['steps']['statistical_tests']['success']:
        print("\n" + "-" * 100)
        print("STATISTICAL VALIDATION RESULTS:")
        print("-" * 100)

        stats_results = flow_results['steps']['statistical_tests']['result']
        for commodity, models in stats_results.items():
            print(f"\n{commodity.upper()}:")
            for model, result in models.items():
                if 'error' in result:
                    print(f"  ✗ {model}: {result['error']}")
                elif result.get('significant_strategies'):
                    sig_count = len(result['significant_strategies'])
                    print(f"  ✓ {model}: {sig_count} strategies beat baseline (p<0.05)")
                    for strategy in result['significant_strategies'][:3]:  # Show top 3
                        print(f"      - {strategy['strategy']}: +${strategy['avg_excess_return']:.2f}/day (p={strategy['p_value']:.4f})")
                else:
                    print(f"  ⚠️  {model}: No significant improvements")

    # Overall status
    print("\n" + "=" * 100)
    all_success = all(step['success'] for step in flow_results['steps'].values())
    if all_success:
        print("✓ COMPLETE ANALYSIS FLOW: SUCCESS")
    else:
        print("⚠️  COMPLETE ANALYSIS FLOW: PARTIAL SUCCESS (some steps failed)")
    print("=" * 100)

    return all_success


def main():
    parser = argparse.ArgumentParser(
        description='Run complete trading agent analysis flow'
    )
    parser.add_argument(
        '--commodity',
        type=str,
        help='Single commodity to process'
    )
    parser.add_argument(
        '--commodities',
        type=str,
        help='Comma-separated list of commodities'
    )
    parser.add_argument(
        '--optimize',
        action='store_true',
        default=False,
        help='Run parameter optimization (slow but improves results)'
    )
    parser.add_argument(
        '--skip-stats',
        action='store_true',
        default=False,
        help='Skip statistical testing step'
    )

    args = parser.parse_args()

    # Determine commodities to process
    if args.commodities:
        commodities = [c.strip() for c in args.commodities.split(',')]
    elif args.commodity:
        commodities = [args.commodity]
    else:
        commodities = list(COMMODITY_CONFIGS.keys())

    print_section("COMPLETE TRADING AGENT ANALYSIS FLOW")
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Commodities: {', '.join(commodities)}")
    print(f"Optimize Parameters: {args.optimize}")
    print(f"Skip Statistics: {args.skip_stats}")

    # Initialize Spark
    spark = SparkSession.builder.appName("CompleteAnalysisFlow").getOrCreate()

    # Track overall results
    flow_results = {
        'start_time': datetime.now().isoformat(),
        'commodities': commodities,
        'steps': {}
    }

    # Step 1: Generate Manifests
    success, result, error = run_step(
        "1. Generate Forecast Manifests",
        step_generate_manifests,
        spark,
        commodities
    )
    flow_results['steps']['manifests'] = {
        'success': success,
        'result': result,
        'error': error,
        'duration': 0  # Will be updated
    }
    if not success:
        print("\n✗ Flow aborted: Manifest generation failed")
        return False

    # Step 2: Load Predictions
    success, result, error = run_step(
        "2. Load Forecast Predictions",
        step_load_predictions,
        spark,
        commodities
    )
    flow_results['steps']['predictions'] = {
        'success': success,
        'result': result,
        'error': error,
        'duration': 0
    }
    if not success:
        print("\n⚠️  Warning: Prediction loading failed, but continuing...")

    # Step 3: Optimize Parameters (Optional)
    if args.optimize:
        success, result, error = run_step(
            "3. Optimize Strategy Parameters",
            step_optimize_parameters,
            spark,
            commodities,
            flow_results['steps']['manifests']['result'],  # Pass manifests from Step 1
        )
        flow_results['steps']['optimization'] = {
            'success': success,
            'result': result,
            'error': error,
            'duration': 0
        }
        if not success:
            print("\n⚠️  Warning: Optimization failed, will use default parameters")
    else:
        print("\nℹ️  Skipping parameter optimization (use --optimize to enable)")
        flow_results['steps']['optimization'] = {'success': True, 'skipped': True, 'duration': 0}

    # Step 4: Run Backtests
    success, result, error = run_step(
        "4. Run Backtests (All Strategies & Models)",
        step_run_backtests,
        spark,
        commodities,
        use_optimized_params=args.optimize
    )
    flow_results['steps']['backtests'] = {
        'success': success,
        'result': result,
        'error': error,
        'duration': 0
    }
    if not success:
        print("\n✗ Flow aborted: Backtest execution failed")
        return False

    # Step 5: Statistical Tests (Optional)
    if not args.skip_stats:
        success, result, error = run_step(
            "5. Run Statistical Tests (HAC-Adjusted)",
            step_run_statistical_tests,
            spark,
            commodities
        )
        flow_results['steps']['statistical_tests'] = {
            'success': success,
            'result': result,
            'error': error,
            'duration': 0
        }
        if not success:
            print("\n⚠️  Warning: Statistical testing failed")
    else:
        print("\nℹ️  Skipping statistical testing (removed --skip-stats to enable)")
        flow_results['steps']['statistical_tests'] = {'success': True, 'skipped': True, 'duration': 0}

    # Generate Summary Report
    flow_results['end_time'] = datetime.now().isoformat()
    start = datetime.fromisoformat(flow_results['start_time'])
    end = datetime.fromisoformat(flow_results['end_time'])
    flow_results['duration_seconds'] = (end - start).total_seconds()

    overall_success = generate_summary_report(flow_results)

    # Save results to JSON (convert Timestamp keys to strings first)
    def convert_timestamps_to_strings(obj):
        """Recursively convert pandas Timestamp keys to strings for JSON serialization"""
        if isinstance(obj, dict):
            return {
                str(k) if hasattr(k, 'isoformat') else k: convert_timestamps_to_strings(v)
                for k, v in obj.items()
            }
        elif isinstance(obj, list):
            return [convert_timestamps_to_strings(item) for item in obj]
        else:
            return obj

    output_file = Path(VOLUME_PATH) / f"complete_analysis_flow_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(convert_timestamps_to_strings(flow_results), f, indent=2, default=str)
    print(f"\nDetailed results saved to: {output_file}")

    return overall_success


if __name__ == "__main__":
    success = main()
    if not success:
        raise RuntimeError("Complete analysis flow failed - check logs for details")
    # Success - exit normally (no sys.exit() needed for Databricks)
