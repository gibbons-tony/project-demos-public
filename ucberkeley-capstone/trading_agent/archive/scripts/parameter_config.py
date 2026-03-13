"""
Parameter Configuration Utilities

Helper functions for loading and using optimal parameters from grid search results.

Usage:
    from parameter_config import load_optimal_parameters, apply_to_notebook_params

    # Load optimal parameters
    optimal = load_optimal_parameters('optimal_parameters.json')

    # Convert to notebook format
    baseline_params, prediction_params = apply_to_notebook_params(optimal)
"""

import json
from typing import Dict, Tuple, Any
from pathlib import Path


def load_optimal_parameters(filepath: str) -> Dict[str, Any]:
    """
    Load optimal parameters from JSON file.

    Args:
        filepath: Path to optimal_parameters.json

    Returns:
        dict: Optimal parameters structure
    """
    with open(filepath, 'r') as f:
        return json.load(f)


def apply_to_notebook_params(optimal_params: Dict[str, Any]) -> Tuple[Dict, Dict]:
    """
    Convert optimal parameters to notebook BASELINE_PARAMS and PREDICTION_PARAMS format.

    Args:
        optimal_params: Dict from load_optimal_parameters()

    Returns:
        tuple: (BASELINE_PARAMS, PREDICTION_PARAMS) dicts
    """
    params = optimal_params['parameters']

    # Build BASELINE_PARAMS
    baseline_params = {}

    if 'equal_batch' in params:
        baseline_params['equal_batch'] = params['equal_batch']['params']

    if 'price_threshold' in params:
        baseline_params['price_threshold'] = {
            'threshold_pct': params['price_threshold']['params']['threshold_pct']
            # Note: batch_fraction and max_days_without_sale passed directly to strategy init
        }

    if 'moving_average' in params:
        baseline_params['moving_average'] = {
            'ma_period': params['moving_average']['params']['ma_period']
            # Note: batch_fraction and max_days_without_sale passed directly to strategy init
        }

    # Build PREDICTION_PARAMS
    prediction_params = {}

    if 'consensus' in params:
        prediction_params['consensus'] = params['consensus']['params']

    if 'expected_value' in params:
        prediction_params['expected_value'] = params['expected_value']['params']

    if 'risk_adjusted' in params:
        prediction_params['risk_adjusted'] = params['risk_adjusted']['params']

    return baseline_params, prediction_params


def get_matched_pair_params(optimal_params: Dict[str, Any]) -> Dict[str, Dict]:
    """
    Extract matched pair parameters for predictive strategies.

    Args:
        optimal_params: Dict from load_optimal_parameters()

    Returns:
        dict: Parameters for each predictive strategy
    """
    params = optimal_params['parameters']
    matched_pair_params = {}

    # Price threshold predictive
    if 'price_threshold' in params:
        matched_pair_params['price_threshold_predictive'] = {
            'threshold_pct': params['price_threshold']['params']['threshold_pct'],
            'batch_fraction': params['price_threshold']['params']['batch_fraction'],
            'max_days_without_sale': params['price_threshold']['params']['max_days_without_sale']
        }

    # Moving average predictive
    if 'moving_average' in params:
        matched_pair_params['moving_average_predictive'] = {
            'ma_period': params['moving_average']['params']['ma_period'],
            'batch_fraction': params['moving_average']['params']['batch_fraction'],
            'max_days_without_sale': params['moving_average']['params']['max_days_without_sale']
        }

    return matched_pair_params


def print_update_instructions(optimal_params: Dict[str, Any]):
    """
    Print instructions for updating notebook with optimal parameters.

    Args:
        optimal_params: Dict from load_optimal_parameters()
    """
    baseline_params, prediction_params = apply_to_notebook_params(optimal_params)
    matched_pair_params = get_matched_pair_params(optimal_params)

    print("=" * 80)
    print("PARAMETER UPDATE INSTRUCTIONS")
    print("=" * 80)

    print("\n1. Update BASELINE_PARAMS (lines ~66-79):")
    print("-" * 40)
    print("BASELINE_PARAMS = {")
    for key, value in baseline_params.items():
        print(f"    '{key}': {{")
        for param, val in value.items():
            print(f"        '{param}': {val},")
        print("    },")
    print("}")

    print("\n2. Update PREDICTION_PARAMS (lines ~81-98):")
    print("-" * 40)
    print("PREDICTION_PARAMS = {")
    for key, value in prediction_params.items():
        print(f"    '{key}': {{")
        for param, val in value.items():
            if isinstance(val, float):
                print(f"        '{param}': {val},")
            else:
                print(f"        '{param}': {val},")
        print("    },")
    print("}")

    print("\n3. Update strategy instantiation (lines ~3484-3492):")
    print("-" * 40)

    if 'price_threshold_predictive' in matched_pair_params:
        pt_params = matched_pair_params['price_threshold_predictive']
        print("PriceThresholdPredictive(")
        print(f"    threshold_pct={pt_params['threshold_pct']},")
        print(f"    batch_fraction={pt_params['batch_fraction']},")
        print(f"    max_days_without_sale={pt_params['max_days_without_sale']}")
        print("),")

    if 'moving_average_predictive' in matched_pair_params:
        ma_params = matched_pair_params['moving_average_predictive']
        print("MovingAveragePredictive(")
        print(f"    ma_period={ma_params['ma_period']},")
        print(f"    batch_fraction={ma_params['batch_fraction']},")
        print(f"    max_days_without_sale={ma_params['max_days_without_sale']}")
        print(")")

    print("\n" + "=" * 80)
    print("Expected Improvement")
    print("=" * 80)

    params = optimal_params['parameters']
    for strategy, data in params.items():
        if 'net_revenue' in data and data['net_revenue'] > 0:
            print(f"{strategy:30s}: ${data['net_revenue']:>12,.2f}")


def compare_to_current(optimal_params: Dict[str, Any],
                      current_baseline_params: Dict,
                      current_prediction_params: Dict) -> Dict[str, Dict]:
    """
    Compare optimal parameters to current values.

    Args:
        optimal_params: Dict from load_optimal_parameters()
        current_baseline_params: Current BASELINE_PARAMS from notebook
        current_prediction_params: Current PREDICTION_PARAMS from notebook

    Returns:
        dict: Comparison results
    """
    opt_baseline, opt_prediction = apply_to_notebook_params(optimal_params)

    comparison = {
        'baseline': {},
        'prediction': {}
    }

    # Compare baseline params
    for strategy in opt_baseline:
        if strategy in current_baseline_params:
            comparison['baseline'][strategy] = {
                'current': current_baseline_params[strategy],
                'optimal': opt_baseline[strategy],
                'changed': opt_baseline[strategy] != current_baseline_params[strategy]
            }

    # Compare prediction params
    for strategy in opt_prediction:
        if strategy in current_prediction_params:
            comparison['prediction'][strategy] = {
                'current': current_prediction_params[strategy],
                'optimal': opt_prediction[strategy],
                'changed': opt_prediction[strategy] != current_prediction_params[strategy]
            }

    return comparison


def print_comparison(comparison: Dict[str, Dict]):
    """
    Print parameter comparison.

    Args:
        comparison: Dict from compare_to_current()
    """
    print("=" * 80)
    print("PARAMETER COMPARISON: Current vs Optimal")
    print("=" * 80)

    for category in ['baseline', 'prediction']:
        if comparison[category]:
            print(f"\n{category.upper()} STRATEGIES:")
            print("-" * 40)

            for strategy, data in comparison[category].items():
                print(f"\n{strategy}:")

                if data['changed']:
                    print("  ⚠️  PARAMETERS CHANGED")

                    current = data['current']
                    optimal = data['optimal']

                    for param in optimal:
                        curr_val = current.get(param, 'N/A')
                        opt_val = optimal[param]

                        if curr_val != opt_val:
                            print(f"    {param}:")
                            print(f"      Current: {curr_val}")
                            print(f"      Optimal: {opt_val} {'✓' if opt_val != curr_val else ''}")
                        else:
                            print(f"    {param}: {opt_val} (unchanged)")
                else:
                    print("  ✓ Parameters are already optimal")


# Example usage
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Load and display optimal parameters')
    parser.add_argument('filepath', help='Path to optimal_parameters.json')
    parser.add_argument('--compare', action='store_true',
                       help='Compare to current notebook parameters')

    args = parser.parse_args()

    # Load optimal parameters
    optimal = load_optimal_parameters(args.filepath)

    print(f"\nLoaded optimal parameters:")
    print(f"  Generated: {optimal['generated_at']}")
    print(f"  Commodity: {optimal['commodity']}")
    print(f"  Model: {optimal['model']}")
    print(f"  Strategies optimized: {len(optimal['parameters'])}")

    # Print update instructions
    print_update_instructions(optimal)

    # Compare if requested
    if args.compare:
        # Load current params from notebook (would need to import them)
        print("\n⚠️  Comparison requires current notebook parameters")
        print("   Run this script within Databricks notebook context or")
        print("   manually specify current parameters")
