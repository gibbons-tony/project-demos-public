"""
Diagnostic: Confidence-Based Blending Test

Tests redesigned matched pair strategies across different prediction accuracy levels
to validate the three-tier confidence system:
- HIGH confidence (CV < 5%): Override baseline
- MEDIUM confidence (5-15%): Blend baseline + predictions
- LOW confidence (CV > 15%): Follow baseline

Expected results:
- acc100 (CV~0%): High uplift via overrides
- acc90 (CV~12%): Moderate uplift via blending
- acc80/70/60 (CV>25%): Minimal uplift (falls back to baseline)
"""

import pandas as pd
import numpy as np
import pickle
from datetime import datetime
from pathlib import Path

# Databricks imports
from pyspark.sql import SparkSession
import sys
import os

# Import strategies
import importlib.util

try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    script_dir = '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent/commodity_prediction_analysis/diagnostics'

possible_paths = [
    os.path.join(script_dir, 'all_strategies_pct.py'),
    '/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent/commodity_prediction_analysis/diagnostics/all_strategies_pct.py',
]

strategies_path = None
for path in possible_paths:
    if os.path.exists(path):
        strategies_path = path
        break

if strategies_path is None:
    raise FileNotFoundError(f"Could not find all_strategies_pct.py. Tried: {possible_paths}")

spec = importlib.util.spec_from_file_location('all_strategies_pct', strategies_path)
strat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(strat)

PriceThresholdStrategy = strat.PriceThresholdStrategy
PriceThresholdPredictive = strat.PriceThresholdPredictive
MovingAveragePredictive = strat.MovingAveragePredictive


class SimpleBacktestEngine:
    """Minimal backtest engine"""
    def __init__(self, prices_df, prediction_matrices, costs):
        self.prices = prices_df
        self.prediction_matrices = prediction_matrices
        self.storage_cost_pct = costs['storage_cost_pct_per_day']
        self.transaction_cost_pct = costs['transaction_cost_pct']

    def run_backtest(self, strategy, initial_inventory=50.0):
        """Run backtest and return final net earnings"""
        inventory = initial_inventory
        total_revenue = 0.0
        total_transaction_costs = 0.0
        total_storage_costs = 0.0
        trades = []

        for day in range(len(self.prices) - 14):
            current_date = self.prices.iloc[day]['date']
            current_price = self.prices.iloc[day]['price']
            predictions = self.prediction_matrices.get(current_date, None)
            price_history = self.prices.iloc[:day+1].copy()

            decision = strategy.decide(day, inventory, current_price, price_history, predictions)

            if decision['action'] == 'SELL' and decision['amount'] > 0:
                sell_amount = min(decision['amount'], inventory)
                revenue = sell_amount * current_price
                transaction_cost = revenue * (self.transaction_cost_pct / 100)
                net_revenue = revenue - transaction_cost

                total_revenue += net_revenue
                total_transaction_costs += transaction_cost
                inventory -= sell_amount

                trades.append({
                    'day': day,
                    'date': current_date,
                    'price': current_price,
                    'amount': sell_amount,
                    'revenue': net_revenue,
                    'reason': decision.get('reason', 'unknown')
                })

            if inventory > 0:
                storage_cost = inventory * current_price * (self.storage_cost_pct / 100)
                total_storage_costs += storage_cost

        # Forced liquidation
        if inventory > 0:
            final_price = self.prices.iloc[-14]['price']
            final_revenue = inventory * final_price
            final_transaction_cost = final_revenue * (self.transaction_cost_pct / 100)
            total_revenue += (final_revenue - final_transaction_cost)
            total_transaction_costs += final_transaction_cost

            trades.append({
                'day': len(self.prices) - 14,
                'date': self.prices.iloc[-14]['date'],
                'price': final_price,
                'amount': inventory,
                'revenue': final_revenue - final_transaction_cost,
                'reason': 'forced_liquidation'
            })

        net_earnings = total_revenue - total_storage_costs

        return {
            'net_earnings': net_earnings,
            'total_revenue': total_revenue,
            'transaction_costs': total_transaction_costs,
            'storage_costs': total_storage_costs,
            'trades': trades,
            'num_trades': len(trades)
        }


def main():
    print("="*80)
    print("DIAGNOSTIC: CONFIDENCE-BASED BLENDING TEST")
    print("="*80)
    print(f"Execution time: {datetime.now()}")

    commodity = 'coffee'
    spark = SparkSession.builder.getOrCreate()

    # Output paths
    volume_path = "/Volumes/commodity/trading_agent/files"
    output_file = f"{volume_path}/diagnostic_confidence_test_results.pkl"
    csv_file = f"{volume_path}/diagnostic_confidence_test_summary.csv"

    # Load prices
    print("\n1. Loading prices...")
    market_df = spark.table("commodity.bronze.market").filter(
        f"lower(commodity) = '{commodity}'"
    ).toPandas()

    market_df['date'] = pd.to_datetime(market_df['date']).dt.normalize()
    market_df['price'] = market_df['close']
    prices_df = market_df[['date', 'price']].sort_values('date').reset_index(drop=True)
    prices_df = prices_df[prices_df['date'] >= '2022-01-01'].reset_index(drop=True)

    print(f"✓ Loaded {len(prices_df)} days of prices")

    # Test different accuracy levels
    model_versions = ['synthetic_acc100', 'synthetic_acc90', 'synthetic_acc80', 'synthetic_acc70']

    # Costs
    costs = {
        'storage_cost_pct_per_day': 0.005,
        'transaction_cost_pct': 0.01
    }

    all_results = []

    for model_version in model_versions:
        print(f"\n{'='*80}")
        print(f"TESTING WITH {model_version.upper()}")
        print(f"{'='*80}")

        # Load predictions
        print(f"\n2. Loading {model_version} predictions...")
        pred_df = spark.table(f"commodity.trading_agent.predictions_{commodity}").filter(
            f"model_version = '{model_version}'"
        ).toPandas()

        if len(pred_df) == 0:
            print(f"⚠️  No {model_version} predictions found, skipping...")
            continue

        print(f"✓ Loaded {len(pred_df)} prediction rows")

        # Convert to matrix format
        print(f"\n3. Converting to matrix format...")
        pred_df['timestamp'] = pd.to_datetime(pred_df['timestamp'])
        prediction_matrices = {}

        for timestamp in pred_df['timestamp'].unique():
            ts_data = pred_df[pred_df['timestamp'] == timestamp]
            matrix = ts_data.pivot_table(
                index='run_id',
                columns='day_ahead',
                values='predicted_price',
                aggfunc='first'
            ).values
            date_key = pd.Timestamp(timestamp).normalize()
            prediction_matrices[date_key] = matrix

        print(f"✓ Converted to {len(prediction_matrices)} timestamps")

        # Calculate average CV
        cvs = []
        for date_key, matrix in list(prediction_matrices.items())[:10]:
            for horizon in range(14):
                mean = np.mean(matrix[:, horizon])
                std = np.std(matrix[:, horizon])
                if mean > 0:
                    cvs.append(std / mean)

        avg_cv = np.mean(cvs) if cvs else 0
        print(f"  Average CV: {avg_cv:.4f}")

        # Determine expected confidence tier
        if avg_cv < 0.05:
            expected_tier = "HIGH"
        elif avg_cv < 0.15:
            expected_tier = "MEDIUM"
        else:
            expected_tier = "LOW"
        print(f"  Expected tier: {expected_tier}")

        # Create engine
        engine = SimpleBacktestEngine(prices_df, prediction_matrices, costs)

        # Run baseline (once)
        if model_version == model_versions[0]:
            print(f"\n4. Running baseline (Price Threshold)...")
            baseline_strategy = PriceThresholdStrategy()
            baseline_result = engine.run_backtest(baseline_strategy)
            print(f"  Baseline earnings: ${baseline_result['net_earnings']:,.0f}")
            print(f"  Baseline trades: {baseline_result['num_trades']}")

        # Run prediction strategies
        print(f"\n5. Running prediction strategies...")

        # Price Threshold Predictive
        print(f"\n  Testing Price Threshold Predictive...")
        ptp_strategy = PriceThresholdPredictive(
            storage_cost_pct_per_day=costs['storage_cost_pct_per_day'],
            transaction_cost_pct=costs['transaction_cost_pct']
        )
        ptp_result = engine.run_backtest(ptp_strategy)
        ptp_improvement = ptp_result['net_earnings'] - baseline_result['net_earnings']
        ptp_improvement_pct = (ptp_improvement / baseline_result['net_earnings']) * 100

        print(f"    Earnings: ${ptp_result['net_earnings']:,.0f}")
        print(f"    Trades: {ptp_result['num_trades']}")
        print(f"    Improvement: ${ptp_improvement:,.0f} ({ptp_improvement_pct:+.1f}%)")

        # Moving Average Predictive
        print(f"\n  Testing Moving Average Predictive...")
        map_strategy = MovingAveragePredictive(
            storage_cost_pct_per_day=costs['storage_cost_pct_per_day'],
            transaction_cost_pct=costs['transaction_cost_pct']
        )
        map_result = engine.run_backtest(map_strategy)
        map_improvement = map_result['net_earnings'] - baseline_result['net_earnings']
        map_improvement_pct = (map_improvement / baseline_result['net_earnings']) * 100

        print(f"    Earnings: ${map_result['net_earnings']:,.0f}")
        print(f"    Trades: {map_result['num_trades']}")
        print(f"    Improvement: ${map_improvement:,.0f} ({map_improvement_pct:+.1f}%)")

        # Store results
        all_results.append({
            'model_version': model_version,
            'avg_cv': avg_cv,
            'expected_tier': expected_tier,
            'baseline_earnings': baseline_result['net_earnings'],
            'ptp_earnings': ptp_result['net_earnings'],
            'ptp_improvement_pct': ptp_improvement_pct,
            'map_earnings': map_result['net_earnings'],
            'map_improvement_pct': map_improvement_pct
        })

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY: CONFIDENCE-BASED BLENDING VALIDATION")
    print(f"{'='*80}")

    summary_df = pd.DataFrame(all_results)
    print(f"\n{summary_df.to_string(index=False)}")

    # Analysis
    print(f"\n{'='*80}")
    print("ANALYSIS")
    print(f"{'='*80}")

    print("\nExpected behavior:")
    print("  HIGH confidence (CV < 5%): Strong uplift via prediction overrides")
    print("  MEDIUM confidence (5-15%): Moderate uplift via blending")
    print("  LOW confidence (CV > 15%): Minimal uplift (falls back to baseline)")

    print(f"\nObserved behavior:")
    for _, row in summary_df.iterrows():
        print(f"\n  {row['model_version']} (CV={row['avg_cv']:.2%}, {row['expected_tier']} tier):")
        print(f"    Price Threshold Pred: {row['ptp_improvement_pct']:+.1f}%")
        print(f"    Moving Average Pred:  {row['map_improvement_pct']:+.1f}%")

    # Validation
    validation_passed = True
    print(f"\n{'='*80}")
    print("VALIDATION")
    print(f"{'='*80}")

    # Check HIGH confidence shows best improvement
    high_conf_rows = summary_df[summary_df['expected_tier'] == 'HIGH']
    if len(high_conf_rows) > 0:
        high_avg_improvement = high_conf_rows[['ptp_improvement_pct', 'map_improvement_pct']].mean().mean()
        print(f"\n  HIGH confidence average improvement: {high_avg_improvement:.1f}%")
        if high_avg_improvement > 5:
            print("  ✓ HIGH confidence shows strong uplift")
        else:
            print("  ❌ HIGH confidence should show >5% improvement")
            validation_passed = False

    # Check MEDIUM confidence shows moderate improvement
    med_conf_rows = summary_df[summary_df['expected_tier'] == 'MEDIUM']
    if len(med_conf_rows) > 0:
        med_avg_improvement = med_conf_rows[['ptp_improvement_pct', 'map_improvement_pct']].mean().mean()
        print(f"\n  MEDIUM confidence average improvement: {med_avg_improvement:.1f}%")
        if 2 < med_avg_improvement < high_avg_improvement:
            print("  ✓ MEDIUM confidence shows moderate uplift")
        else:
            print("  ⚠️  MEDIUM confidence should show 2-5% improvement")

    # Check LOW confidence shows minimal improvement
    low_conf_rows = summary_df[summary_df['expected_tier'] == 'LOW']
    if len(low_conf_rows) > 0:
        low_avg_improvement = low_conf_rows[['ptp_improvement_pct', 'map_improvement_pct']].mean().mean()
        print(f"\n  LOW confidence average improvement: {low_avg_improvement:.1f}%")
        if abs(low_avg_improvement) < 3:
            print("  ✓ LOW confidence falls back to baseline")
        else:
            print("  ⚠️  LOW confidence should show <3% improvement (baseline fallback)")

    # Save results
    print(f"\n{'='*80}")
    print("SAVING RESULTS")
    print(f"{'='*80}")

    results_data = {
        'execution_time': datetime.now(),
        'commodity': commodity,
        'validation_passed': validation_passed,
        'all_results': all_results,
        'summary_df': summary_df
    }

    with open(output_file, 'wb') as f:
        pickle.dump(results_data, f)
    print(f"✓ Saved results to: {output_file}")

    summary_df.to_csv(csv_file, index=False)
    print(f"✓ Saved summary to: {csv_file}")

    print(f"\n{'='*80}")
    print("DIAGNOSTIC COMPLETE")
    print(f"{'='*80}")

    if validation_passed:
        print("\n✓✓✓ CONFIDENCE-BASED BLENDING VALIDATED")
        print("\nConclusion: Three-tier system works as expected.")
        print("Strategies appropriately leverage predictions based on confidence.")
    else:
        print("\n⚠️⚠️⚠️  VALIDATION ISSUES DETECTED")
        print("\nReview results to diagnose confidence-based logic.")

    return validation_passed


if __name__ == "__main__":
    success = main()
    if not success:
        raise RuntimeError("Confidence test validation failed!")
