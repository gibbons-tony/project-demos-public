"""
Model Runner - Orchestrates Multi-Model Analysis

This module implements the nested loop structure:
    for commodity in ['coffee', 'sugar']:
        for model in get_available_models(commodity):
            run_analysis(commodity, model)

Total iterations: 15 (10 Coffee models + 5 Sugar models)
"""

import sys
import os
from typing import Dict, Optional
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_access.forecast_loader import (
    get_available_models,
    get_available_commodities,
    load_forecast_distributions,
    transform_to_prediction_matrices,
    get_data_summary,
    print_data_summary
)


def run_analysis_for_model(
    commodity: str,
    model_version: str,
    connection,
    commodity_config: Dict,
    prices,
    backtest_function,
    output_dir: str,
    verbose: bool = True
) -> Optional[Dict]:
    """
    Run complete backtest analysis for a single (commodity, model) combination.

    Args:
        commodity: str - Commodity name (e.g., 'coffee', 'sugar')
        model_version: str - Model identifier (e.g., 'sarimax_auto_weather_v1')
        connection: Databricks SQL connection
        commodity_config: dict - Commodity configuration (harvest, costs, etc.)
        prices: DataFrame - Price history for backtesting
        backtest_function: callable - Function that runs the backtest
        output_dir: str - Directory for output files
        verbose: bool - Print progress messages

    Returns:
        Dict with analysis results, or None if failed

    Structure of returned dict:
        {
            'commodity': 'coffee',
            'model_version': 'sarimax_auto_weather_v1',
            'data_summary': {...},
            'prediction_matrices': {...},
            'backtest_results': {...},
            'execution_time': 123.45
        }
    """
    if verbose:
        print(f"\n{'='*80}")
        print(f"ANALYZING: {commodity.upper()} - {model_version}")
        print(f"{'='*80}\n")

    start_time = datetime.now()

    try:
        # Step 1: Load forecast distributions from Unity Catalog
        if verbose:
            print(f"1. Loading forecast data from Unity Catalog...")

        df = load_forecast_distributions(
            commodity=commodity.capitalize(),
            model_version=model_version,
            connection=connection
        )

        if len(df) == 0:
            print(f"   ⚠️  No data found for {commodity} - {model_version}")
            return None

        if verbose:
            print(f"   ✓ Loaded {len(df):,} rows")

        # Step 2: Get data summary
        if verbose:
            print(f"\n2. Getting data summary...")

        summary = get_data_summary(commodity.capitalize(), model_version, connection)
        if verbose:
            print_data_summary(summary)

        # Step 3: Transform to prediction matrices
        if verbose:
            print(f"3. Transforming to prediction matrices...")

        prediction_matrices = transform_to_prediction_matrices(df)

        if verbose:
            print(f"   ✓ Created {len(prediction_matrices):,} prediction matrices")

        # Step 4: Run backtest
        if verbose:
            print(f"\n4. Running backtest analysis...")

        backtest_results = backtest_function(
            commodity=commodity,
            model_version=model_version,
            commodity_config=commodity_config,
            prices=prices,
            prediction_matrices=prediction_matrices,
            output_dir=output_dir
        )

        if verbose:
            print(f"   ✓ Backtest complete")

        # Calculate execution time
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()

        if verbose:
            print(f"\n{'='*80}")
            print(f"✅ COMPLETED: {commodity.upper()} - {model_version}")
            print(f"   Execution time: {execution_time:.1f} seconds")
            print(f"{'='*80}\n")

        # Return results
        return {
            'commodity': commodity,
            'model_version': model_version,
            'data_summary': summary,
            'prediction_matrices': prediction_matrices,
            'backtest_results': backtest_results,
            'execution_time': execution_time,
            'timestamp': end_time
        }

    except Exception as e:
        print(f"\n{'='*80}")
        print(f"❌ ERROR: {commodity.upper()} - {model_version}")
        print(f"   {type(e).__name__}: {e}")
        print(f"{'='*80}\n")

        import traceback
        if verbose:
            traceback.print_exc()

        return None


def run_analysis_for_all_models(
    commodity: str,
    connection,
    commodity_config: Dict,
    prices,
    backtest_function,
    output_dir: str,
    verbose: bool = True
) -> Dict[str, Optional[Dict]]:
    """
    Run backtest analysis for all available models of a commodity.

    Args:
        commodity: str - Commodity name (e.g., 'coffee', 'sugar')
        connection: Databricks SQL connection
        commodity_config: dict - Commodity configuration
        prices: DataFrame - Price history
        backtest_function: callable - Function that runs the backtest
        output_dir: str - Directory for output files
        verbose: bool - Print progress messages

    Returns:
        Dict mapping model_version to results dict

    Example:
        >>> results = run_analysis_for_all_models('coffee', conn, config, ...)
        >>> results.keys()
        dict_keys(['arima_111_v1', 'prophet_v1', 'sarimax_auto_weather_v1', ...])
        >>> results['prophet_v1']['backtest_results']
        {...}
    """
    if verbose:
        print(f"\n{'#'*80}")
        print(f"# STARTING ANALYSIS FOR: {commodity.upper()}")
        print(f"{'#'*80}\n")

    # Get all available models for this commodity
    models = get_available_models(commodity.capitalize(), connection)

    if verbose:
        print(f"Found {len(models)} models for {commodity.upper()}:")
        for i, model in enumerate(models, 1):
            print(f"  {i}. {model}")
        print()

    # Run analysis for each model
    results_by_model = {}
    successful = 0
    failed = 0

    for i, model in enumerate(models, 1):
        if verbose:
            print(f"\n[{i}/{len(models)}] Processing {model}...")

        result = run_analysis_for_model(
            commodity=commodity,
            model_version=model,
            connection=connection,
            commodity_config=commodity_config,
            prices=prices,
            backtest_function=backtest_function,
            output_dir=output_dir,
            verbose=verbose
        )

        results_by_model[model] = result

        if result is not None:
            successful += 1
        else:
            failed += 1

    # Summary
    if verbose:
        print(f"\n{'#'*80}")
        print(f"# SUMMARY: {commodity.upper()}")
        print(f"{'#'*80}")
        print(f"Total models: {len(models)}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"{'#'*80}\n")

    return results_by_model


def run_analysis_for_all_commodities(
    commodity_configs: Dict,
    connection,
    prices_dict: Dict,
    backtest_function,
    output_base_dir: str,
    verbose: bool = True
) -> Dict[str, Dict[str, Optional[Dict]]]:
    """
    Run backtest analysis for all commodities and all their models.

    This is the top-level function that orchestrates the complete nested loop.

    Args:
        commodity_configs: dict - Configuration for all commodities
        connection: Databricks SQL connection
        prices_dict: dict - Price history for each commodity
        backtest_function: callable - Function that runs the backtest
        output_base_dir: str - Base directory for output files
        verbose: bool - Print progress messages

    Returns:
        Nested dict: {commodity: {model_version: results}}

    Example:
        >>> all_results = run_analysis_for_all_commodities(configs, conn, ...)
        >>> all_results['coffee']['prophet_v1']['backtest_results']
        {...}
        >>> all_results['sugar']['arima_111_v1']['execution_time']
        123.45
    """
    if verbose:
        print("\n" + "="*80)
        print("MULTI-COMMODITY, MULTI-MODEL ANALYSIS")
        print("="*80)
        print(f"Commodities: {list(commodity_configs.keys())}")
        print(f"Output directory: {output_base_dir}")
        print("="*80 + "\n")

    all_results = {}
    total_start_time = datetime.now()

    # Nested loop: commodity → model
    for commodity_name in commodity_configs.keys():
        # Create output directory for this commodity
        commodity_output_dir = os.path.join(output_base_dir, commodity_name)
        os.makedirs(commodity_output_dir, exist_ok=True)

        # Get configuration and prices for this commodity
        commodity_config = commodity_configs[commodity_name]
        prices = prices_dict.get(commodity_name)

        if prices is None:
            print(f"⚠️  No price data found for {commodity_name.upper()}, skipping...")
            continue

        # Run analysis for all models of this commodity
        results_by_model = run_analysis_for_all_models(
            commodity=commodity_name,
            connection=connection,
            commodity_config=commodity_config,
            prices=prices,
            backtest_function=backtest_function,
            output_dir=commodity_output_dir,
            verbose=verbose
        )

        all_results[commodity_name] = results_by_model

    # Final summary
    total_end_time = datetime.now()
    total_time = (total_end_time - total_start_time).total_seconds()

    if verbose:
        print("\n" + "="*80)
        print("FINAL SUMMARY - ALL COMMODITIES AND MODELS")
        print("="*80)

        total_models = 0
        successful = 0
        failed = 0

        for commodity, models in all_results.items():
            commodity_successful = sum(1 for r in models.values() if r is not None)
            commodity_failed = sum(1 for r in models.values() if r is None)

            print(f"\n{commodity.upper()}:")
            print(f"  Total models: {len(models)}")
            print(f"  Successful: {commodity_successful}")
            print(f"  Failed: {commodity_failed}")

            total_models += len(models)
            successful += commodity_successful
            failed += commodity_failed

        print(f"\n{'='*80}")
        print(f"GRAND TOTAL:")
        print(f"  Total models analyzed: {total_models}")
        print(f"  Successful: {successful}")
        print(f"  Failed: {failed}")
        print(f"  Total execution time: {total_time / 60:.1f} minutes")
        print(f"{'='*80}\n")

    return all_results


def compare_model_performance(all_results: Dict) -> Dict:
    """
    Compare performance metrics across all models and commodities.

    Args:
        all_results: Nested dict from run_analysis_for_all_commodities()

    Returns:
        Dict with comparison dataframes and statistics
    """
    import pandas as pd

    comparison_rows = []

    for commodity, models in all_results.items():
        for model, results in models.items():
            if results is None or results.get('backtest_results') is None:
                continue

            # Extract key metrics from backtest results
            # (Structure depends on what backtest_function returns)
            backtest = results['backtest_results']

            row = {
                'commodity': commodity,
                'model': model,
                'execution_time': results.get('execution_time', 0),
                # Add more metrics as needed based on backtest_results structure
            }

            # Try to extract common metrics if available
            if isinstance(backtest, dict):
                for key in ['net_earnings', 'gross_revenue', 'n_trades', 'avg_sale_price']:
                    if key in backtest:
                        row[key] = backtest[key]

            comparison_rows.append(row)

    comparison_df = pd.DataFrame(comparison_rows)

    return {
        'comparison_table': comparison_df,
        'best_by_commodity': comparison_df.groupby('commodity').first() if len(comparison_df) > 0 else None
    }


def save_results_summary(all_results: Dict, output_path: str):
    """
    Save a summary of all results to a file.

    Args:
        all_results: Results dict from run_analysis_for_all_commodities()
        output_path: Path to save summary file
    """
    with open(output_path, 'w') as f:
        f.write("="*80 + "\n")
        f.write("MULTI-MODEL ANALYSIS SUMMARY\n")
        f.write("="*80 + "\n\n")

        for commodity, models in all_results.items():
            f.write(f"\n{commodity.upper()}:\n")
            f.write("-"*80 + "\n")

            for model, results in models.items():
                if results is None:
                    f.write(f"  {model}: FAILED\n")
                else:
                    exec_time = results.get('execution_time', 0)
                    f.write(f"  {model}: SUCCESS ({exec_time:.1f}s)\n")

    print(f"\n✓ Summary saved to: {output_path}")
