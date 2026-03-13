"""
Production Backtest Workflow Orchestrator

Purpose:
    Orchestrates periodic backtesting workflow to evaluate strategy performance
    and identify the best trading approaches for each commodity.

Workflow:
    1. (Optional) Regenerate synthetic predictions
    2. (Optional) Load/reload latest forecast predictions
    3. (Optional) Reoptimize strategy parameters with Optuna
    4. Run backtests for all 10 strategies (multi_commodity_runner)
    5. Generate performance summaries
    6. Identify best strategies per commodity

Frequency:
    Run PERIODICALLY (monthly/quarterly) to re-evaluate strategies
    NOT daily - this is for strategic analysis, not operational recommendations

Usage:
    # Standard workflow (use existing predictions and params)
    python production/run_backtest_workflow.py --mode full

    # Force reload forecasts from database
    python production/run_backtest_workflow.py --mode full --reload-forecasts

    # Regenerate synthetic predictions
    python production/run_backtest_workflow.py --mode full --regenerate-synthetic

    # Reoptimize parameters (runs Optuna optimization)
    python production/run_backtest_workflow.py --mode full --reoptimize

    # Full rebuild (all optional steps)
    python production/run_backtest_workflow.py --mode full --reload-forecasts --regenerate-synthetic --reoptimize

    # Single commodity
    python production/run_backtest_workflow.py --mode full --commodity coffee

    # Skip prediction loading (use existing)
    python production/run_backtest_workflow.py --mode backtest-only

    # Quick test with synthetic predictions only
    python production/run_backtest_workflow.py --mode synthetic-test

Returns:
    Exit code 0 on success, 1 on failure
    Generates summary reports and identifies best strategies
"""

import sys
import os
import json
import argparse
from datetime import datetime
import subprocess

# Add repo path for Databricks jobs (fixed path, not using __file__)
sys.path.insert(0, '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent')

from production.config import COMMODITY_CONFIGS


def run_command(command, description, timeout=3600):
    """
    Run a command and capture output

    Args:
        command: List of command arguments
        description: Human-readable description
        timeout: Timeout in seconds

    Returns:
        Tuple of (success, output, error)
    """
    print(f"\n{'=' * 80}")
    print(f"STEP: {description}")
    print(f"{'=' * 80}")
    print(f"Command: {' '.join(command)}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)

        if result.returncode == 0:
            print(f"\n✓ {description} completed successfully")
            return True, result.stdout, result.stderr
        else:
            print(f"\n✗ {description} failed with exit code {result.returncode}")
            return False, result.stdout, result.stderr

    except subprocess.TimeoutExpired:
        print(f"\n✗ {description} timed out after {timeout} seconds")
        return False, "", f"Timeout after {timeout}s"
    except Exception as e:
        print(f"\n✗ {description} failed with exception: {e}")
        return False, "", str(e)


def parse_json_summary(output):
    """
    Extract JSON summary from command output

    Args:
        output: Command stdout

    Returns:
        dict or None
    """
    try:
        # Find JSON block in output
        lines = output.split('\n')
        json_start = None
        for i, line in enumerate(lines):
            if 'JSON SUMMARY' in line or line.strip().startswith('{'):
                json_start = i
                break

        if json_start is None:
            return None

        # Extract JSON lines
        json_lines = []
        in_json = False
        brace_count = 0

        for line in lines[json_start:]:
            if line.strip().startswith('{'):
                in_json = True

            if in_json:
                json_lines.append(line)
                brace_count += line.count('{') - line.count('}')

                if brace_count == 0 and len(json_lines) > 0:
                    break

        if not json_lines:
            return None

        json_str = '\n'.join(json_lines)
        return json.loads(json_str)

    except Exception as e:
        print(f"⚠️  Could not parse JSON summary: {e}")
        return None


def run_full_workflow(commodities=None, skip_predictions=False, reload_forecasts=False,
                     regenerate_synthetic=False, reoptimize=False):
    """
    Run complete backtest workflow

    Args:
        commodities: List of commodities or None for all
        skip_predictions: Skip prediction loading step
        reload_forecasts: Force reload forecasts from database
        regenerate_synthetic: Regenerate synthetic predictions
        reoptimize: Re-run Optuna parameter optimization

    Returns:
        dict: Workflow summary
    """
    start_time = datetime.now()
    print("=" * 80)
    print("PERIODIC BACKTEST WORKFLOW")
    print("=" * 80)
    print(f"Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: Periodic backtesting (strategy evaluation)")
    print(f"Commodities: {commodities if commodities else 'ALL'}")
    print(f"Reload forecasts: {reload_forecasts}")
    print(f"Regenerate synthetic: {regenerate_synthetic}")
    print(f"Reoptimize params: {reoptimize}")
    print("=" * 80)

    workflow_results = {
        'start_time': start_time.isoformat(),
        'mode': 'full_backtest',
        'steps': []
    }

    # Determine Python executable
    python_cmd = sys.executable

    # ----------------------------------------------------------------------
    # STEP 1: Regenerate Synthetic Predictions (Optional)
    # ----------------------------------------------------------------------
    if regenerate_synthetic:
        cmd = [python_cmd, 'production/scripts/generate_synthetic_predictions.py']
        if commodities:
            for commodity in commodities:
                cmd_commodity = cmd + ['--commodity', commodity]
                success, stdout, stderr = run_command(
                    cmd_commodity,
                    f"Regenerate Synthetic Predictions ({commodity})",
                    timeout=900
                )

                step_result = {
                    'step': f'regenerate_synthetic_{commodity}',
                    'success': success,
                    'summary': parse_json_summary(stdout)
                }
                workflow_results['steps'].append(step_result)

                if not success:
                    print(f"\n⚠️  Failed to regenerate synthetic predictions for {commodity}, but continuing...")
        else:
            # Run for all commodities
            for commodity in COMMODITY_CONFIGS.keys():
                cmd_commodity = cmd + ['--commodity', commodity]
                success, stdout, stderr = run_command(
                    cmd_commodity,
                    f"Regenerate Synthetic Predictions ({commodity})",
                    timeout=900
                )

                step_result = {
                    'step': f'regenerate_synthetic_{commodity}',
                    'success': success,
                    'summary': parse_json_summary(stdout)
                }
                workflow_results['steps'].append(step_result)
    else:
        print("\nℹ️  Using existing synthetic predictions")

    # ----------------------------------------------------------------------
    # STEP 2: Load Latest Predictions (Optional)
    # ----------------------------------------------------------------------
    if not skip_predictions or reload_forecasts:
        cmd = [python_cmd, 'production/scripts/load_forecast_predictions.py']
        if commodities:
            cmd.extend(['--commodities', ','.join(commodities)])
        if reload_forecasts:
            cmd.append('--force')  # Force reload from database

        success, stdout, stderr = run_command(
            cmd,
            "Load Latest Forecast Predictions",
            timeout=1800
        )

        step_result = {
            'step': 'load_predictions',
            'success': success,
            'summary': parse_json_summary(stdout)
        }
        workflow_results['steps'].append(step_result)

        if not success:
            print("\n✗ Workflow failed at prediction loading step")
            return workflow_results
    else:
        print("\nℹ️  Skipping prediction loading (using existing data)")

    # ----------------------------------------------------------------------
    # STEP 3: Reoptimize Parameters (Optional)
    # ----------------------------------------------------------------------
    if reoptimize:
        print("\n" + "=" * 80)
        print("STEP: Reoptimize Strategy Parameters")
        print("=" * 80)
        print("Running Optuna optimization to find best parameters...")

        # Run optimizer
        cmd = [python_cmd, 'analysis/optimization/run_parameter_optimization.py']
        if commodities:
            cmd.extend(['--commodity', commodities[0] if len(commodities) == 1 else 'coffee'])

        success, stdout, stderr = run_command(
            cmd,
            "Run Optuna Parameter Optimization",
            timeout=7200  # 2 hours max
        )

        step_result = {
            'step': 'reoptimize_params',
            'success': success,
            'summary': parse_json_summary(stdout)
        }
        workflow_results['steps'].append(step_result)

        if not success:
            print("\n⚠️  Parameter optimization failed")
            print("   Checking if previous optimized parameters exist for fallback...")

            # Check if previous params exist - if so, use them and continue
            from production.parameter_manager import ParameterManager
            pm = ParameterManager(
                commodity=commodities[0] if commodities else 'coffee',
                model_version='arima_v1',
                verbose=True
            )

            # Try to load previous params
            previous_params = pm.load_optimized_params(version='previous')
            if previous_params:
                print("   ✓ Found previous optimized parameters - using those instead")
                print("   Workflow will continue with fallback parameters")
            else:
                print("   ✗ No previous parameters available")
                print("   Workflow will use default hardcoded parameters")
                # Don't fail the workflow - just continue with defaults
    else:
        print("\nℹ️  Using existing optimized parameters (or defaults if unavailable)")

    # ----------------------------------------------------------------------
    # STEP 4: Run Backtests (Multi-Commodity Runner)
    # ----------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("STEP: Run Strategy Backtests")
    print("=" * 80)
    print("Using production/runners/multi_commodity_runner.py")
    print("This will backtest all 10 strategies across all commodity-model combinations")

    # Import and run multi_commodity_runner
    try:
        from pyspark.sql import SparkSession
        from production.runners.multi_commodity_runner import MultiCommodityRunner
        from production.config import (
            COMMODITY_CONFIGS,
            VOLUME_PATH,
            OUTPUT_SCHEMA
        )
        from production.parameter_manager import get_params_for_backtest

        # Initialize Spark
        spark = SparkSession.builder.appName("BacktestWorkflow").getOrCreate()
        print("✓ Spark session initialized")

        # Filter commodities if specified
        commodity_configs = COMMODITY_CONFIGS
        if commodities:
            commodity_configs = {k: v for k, v in COMMODITY_CONFIGS.items() if k in commodities}

        print(f"\nRunning backtests for: {list(commodity_configs.keys())}")

        # Initialize runner with parameter_manager
        runner = MultiCommodityRunner(
            spark=spark,
            commodity_configs=commodity_configs,
            baseline_params=None,  # Will be loaded per commodity-model pair
            prediction_params=None,  # Will be loaded per commodity-model pair
            volume_path=VOLUME_PATH,
            output_schema=OUTPUT_SCHEMA,
            use_optimized_params=True  # Enable automatic optimized parameter loading
        )

        # Run backtests
        results = runner.run_all_commodities()

        print(f"\n✓ Backtests completed")
        print(f"  Commodities processed: {len(results['commodities'])}")
        print(f"  Total combinations: {results['total_combinations']}")
        print(f"  Successful: {results['successful_combinations']}")
        print(f"  Failed: {results['failed_combinations']}")

        step_result = {
            'step': 'run_backtests',
            'success': results['failed_combinations'] == 0,
            'summary': results
        }
        workflow_results['steps'].append(step_result)

        if results['failed_combinations'] > 0:
            print("\n⚠️  Some backtests failed, but continuing...")

    except Exception as e:
        print(f"\n✗ Backtest step failed: {e}")
        import traceback
        traceback.print_exc()

        step_result = {
            'step': 'run_backtests',
            'success': False,
            'error': str(e)
        }
        workflow_results['steps'].append(step_result)
        return workflow_results

    # ----------------------------------------------------------------------
    # STEP 5: Identify Best Forecast Model (Statistical Comparison)
    # ----------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("STEP: Identify Best Forecast Model")
    print("=" * 80)

    try:
        # Run model comparison for each commodity
        from scipy import stats as scipy_stats
        from pyspark.sql.functions import min as spark_min
        import pandas as pd

        best_models = {}

        for commodity in commodity_configs.keys():
            print(f"\nAnalyzing {commodity}...")

            # Load manifest
            manifest_path = os.path.join(VOLUME_PATH, f'forecast_manifest_{commodity}.json')
            try:
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
                manifest_models = list(manifest['models'].keys())
            except:
                print(f"  ⚠️  No manifest found for {commodity}, skipping")
                continue

            print(f"  Models in manifest: {manifest_models}")

            # Compare models
            model_results = {}
            for model in manifest_models:
                table = f"{OUTPUT_SCHEMA}.results_{commodity}_by_year_{model}"

                try:
                    df = spark.table(table).toPandas()

                    # Find valid years
                    df_spark = spark.table(table)
                    year_validity = df_spark.groupBy('year').agg(
                        spark_min('net_earnings').alias('min_earnings')
                    ).filter('min_earnings > 0').select('year').toPandas()

                    valid_years = sorted(year_validity['year'].astype(int).tolist())
                    df_filtered = df[df['year'].isin(valid_years)]

                    # Get MPC vs Baseline
                    mpc_data = df_filtered[df_filtered['strategy'] == 'RollingHorizonMPC']['net_earnings'].values
                    baseline_data = df_filtered[df_filtered['strategy'] == 'Immediate Sale']['net_earnings'].values

                    if len(mpc_data) > 0 and len(baseline_data) > 0:
                        annual_improvements = ((mpc_data - baseline_data) / baseline_data) * 100
                        avg_improvement = annual_improvements.mean()

                        model_results[model] = {
                            'avg_improvement': float(avg_improvement),
                            'n_years': len(valid_years)
                        }

                        print(f"    {model}: {avg_improvement:+.2f}% (n={len(valid_years)})")

                except Exception as e:
                    print(f"    {model}: ERROR - {e}")

            # Select winner
            if model_results:
                winner = max(model_results.items(), key=lambda x: x[1]['avg_improvement'])
                winner_model = winner[0]
                winner_improvement = winner[1]['avg_improvement']

                best_models[commodity] = {
                    'model': winner_model,
                    'avg_improvement': winner_improvement,
                    'n_years': winner[1]['n_years'],
                    'all_models': model_results
                }

                print(f"\n  🏆 Winner: {winner_model} ({winner_improvement:+.2f}%)")

        workflow_results['best_models'] = best_models

        print(f"\n✓ Identified best models for {len(best_models)} commodities")

    except Exception as e:
        print(f"\n⚠️  Model comparison failed: {e}")
        import traceback
        traceback.print_exc()
        workflow_results['best_models'] = {}

    # ----------------------------------------------------------------------
    # STEP 6: Identify Best Strategies (per model)
    # ----------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("STEP: Identify Best Strategies")
    print("=" * 80)

    try:
        best_strategies = {}

        for commodity_result in results['commodity_results']:
            commodity = commodity_result['commodity']
            model_version = commodity_result['model_version']

            if commodity_result['status'] == 'success':
                metrics = commodity_result['metrics']

                # Find best strategy by net earnings
                best_strategy = metrics.sort_values('net_earnings', ascending=False).iloc[0]

                best_strategies[f"{commodity}_{model_version}"] = {
                    'commodity': commodity,
                    'model_version': model_version,
                    'strategy': best_strategy['strategy'],
                    'net_earnings': float(best_strategy['net_earnings']),
                    'sharpe_ratio': float(best_strategy.get('sharpe_ratio', 0)),
                    'n_trades': int(best_strategy['n_trades'])
                }

                print(f"\n{commodity.upper()} - {model_version}:")
                print(f"  Best Strategy: {best_strategy['strategy']}")
                print(f"  Net Earnings: ${best_strategy['net_earnings']:,.2f}")
                print(f"  Sharpe Ratio: {best_strategy.get('sharpe_ratio', 0):.2f}")

        workflow_results['best_strategies'] = best_strategies

        print(f"\n✓ Identified best strategies for {len(best_strategies)} combinations")

    except Exception as e:
        print(f"\n⚠️  Could not identify best strategies: {e}")
        workflow_results['best_strategies'] = {}

    # ----------------------------------------------------------------------
    # Final Summary
    # ----------------------------------------------------------------------
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    workflow_results['end_time'] = end_time.isoformat()
    workflow_results['duration_seconds'] = duration
    workflow_results['status'] = 'success' if all(s.get('success', False) for s in workflow_results['steps']) else 'partial'

    print("\n" + "=" * 80)
    print("WORKFLOW COMPLETE")
    print("=" * 80)
    print(f"Completed: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
    print(f"Status: {workflow_results['status'].upper()}")

    # Print best strategies summary
    if workflow_results.get('best_strategies'):
        print("\n" + "-" * 80)
        print("BEST STRATEGIES IDENTIFIED")
        print("-" * 80)
        for combo, info in workflow_results['best_strategies'].items():
            print(f"{info['commodity'].upper()} - {info['model_version']}: {info['strategy']} (${info['net_earnings']:,.2f})")

    return workflow_results


def run_synthetic_test():
    """
    Quick test using synthetic predictions only

    Returns:
        dict: Test results
    """
    print("=" * 80)
    print("SYNTHETIC PREDICTION TEST")
    print("=" * 80)
    print("This is a quick test using synthetic predictions at 100% accuracy")
    print("Use this to validate that the workflow functions correctly")
    print("=" * 80)

    start_time = datetime.now()

    # Run synthetic predictions for one commodity at 100% accuracy
    python_cmd = sys.executable
    cmd = [
        python_cmd,
        'production/scripts/generate_synthetic_predictions.py',
        '--commodity', 'coffee',
        '--accuracies', '1.0'
    ]

    success, stdout, stderr = run_command(
        cmd,
        "Generate Synthetic Predictions (100% accuracy)",
        timeout=900
    )

    if not success:
        print("\n✗ Synthetic prediction test failed")
        return {'status': 'failed', 'step': 'synthetic_predictions'}

    # Now run backtest with synthetic data
    print("\n⚠️  Note: Backtest integration with synthetic predictions requires")
    print("   updating multi_commodity_runner to accept synthetic model versions")

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    return {
        'status': 'success',
        'duration_seconds': duration,
        'note': 'Synthetic predictions generated. Manual backtest required.'
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Orchestrate periodic backtesting workflow'
    )
    parser.add_argument(
        '--mode',
        type=str,
        choices=['full', 'backtest-only', 'synthetic-test'],
        default='full',
        help='Workflow mode: full (load + backtest), backtest-only (skip loading), synthetic-test (quick validation)'
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
        '--reload-forecasts',
        action='store_true',
        default=False,
        help='Force reload forecasts from database (default: use existing if available)'
    )
    parser.add_argument(
        '--regenerate-synthetic',
        action='store_true',
        default=False,
        help='Regenerate synthetic predictions (default: use existing)'
    )
    parser.add_argument(
        '--reoptimize',
        action='store_true',
        default=False,
        help='Re-run Optuna parameter optimization (default: use existing optimized params)'
    )

    args = parser.parse_args()

    # Parse commodities
    commodities = None
    if args.commodities:
        commodities = [c.strip() for c in args.commodities.split(',')]
    elif args.commodity:
        commodities = [args.commodity]

    # Run appropriate workflow
    if args.mode == 'synthetic-test':
        result = run_synthetic_test()
    elif args.mode == 'backtest-only':
        result = run_full_workflow(
            commodities=commodities,
            skip_predictions=True,
            reload_forecasts=args.reload_forecasts,
            regenerate_synthetic=args.regenerate_synthetic,
            reoptimize=args.reoptimize
        )
    else:  # full
        result = run_full_workflow(
            commodities=commodities,
            skip_predictions=False,
            reload_forecasts=args.reload_forecasts,
            regenerate_synthetic=args.regenerate_synthetic,
            reoptimize=args.reoptimize
        )

    # Print final JSON summary
    print("\n" + "=" * 80)
    print("JSON SUMMARY (for automation)")
    print("=" * 80)
    print(json.dumps(result, indent=2))

    # Exit with appropriate code
    # Accept both 'success' and 'partial' as successful outcomes
    # 'partial' means workflow completed but some steps had warnings
    sys.exit(0 if result.get('status') in ['success', 'partial'] else 1)
