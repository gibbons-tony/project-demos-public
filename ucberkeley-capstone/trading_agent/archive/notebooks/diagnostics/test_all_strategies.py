"""
Quick validation test for all 9 percentage-based strategies.
Tests that each strategy can be instantiated and run a basic decision.
"""

import numpy as np
import pandas as pd
import sys
sys.path.insert(0, '/Users/markgibbons/capstone/ucberkeley-capstone/trading_agent/commodity_prediction_analysis/diagnostics')

from all_strategies_pct import (
    ImmediateSaleStrategy,
    EqualBatchStrategy,
    PriceThresholdStrategy,
    MovingAverageStrategy,
    PriceThresholdPredictive,
    MovingAveragePredictive,
    ExpectedValueStrategy,
    ConsensusStrategy,
    RiskAdjustedStrategy
)

def test_strategy(strategy_class, name, use_predictions=False):
    """Test that a strategy can make a decision"""
    print(f"\nTesting {name}...")

    # Create strategy instance with appropriate params
    if strategy_class in [ImmediateSaleStrategy, EqualBatchStrategy]:
        strategy = strategy_class()
    elif strategy_class in [PriceThresholdStrategy, MovingAverageStrategy]:
        # Baselines don't use storage/transaction costs
        strategy = strategy_class()
    elif strategy_class in [PriceThresholdPredictive, MovingAveragePredictive]:
        # Matched pairs need both baseline and prediction params
        strategy = strategy_class(
            storage_cost_pct_per_day=0.025,
            transaction_cost_pct=0.25
        )
    else:
        # Prediction strategies need costs
        strategy = strategy_class(
            storage_cost_pct_per_day=0.025,
            transaction_cost_pct=0.25
        )

    # Create test data
    inventory = 10.0  # tons
    current_price = 150.0  # cents/lb

    # Create price history as DataFrame (required by ADX calculation)
    price_history = pd.DataFrame({
        'price': [145, 148, 150, 152, 150, 151, 149, 150, 152, 151,
                  150, 149, 151, 152, 150]  # 15 days for ADX calculation
    })

    # Create predictions if needed
    predictions = None
    if use_predictions:
        # 100 prediction paths, 30 days ahead
        # Simulate 2% price increase over 14 days
        predictions = np.random.normal(
            loc=current_price * 1.02,  # 2% higher
            scale=current_price * 0.03,  # 3% std dev
            size=(100, 30)
        )

    # Make decision
    day = 10
    decision = strategy.decide(day, inventory, current_price, price_history, predictions)

    # Validate decision structure
    assert 'action' in decision, f"{name}: Missing 'action' key"
    assert 'amount' in decision, f"{name}: Missing 'amount' key"
    assert 'reason' in decision, f"{name}: Missing 'reason' key"
    assert decision['action'] in ['SELL', 'HOLD'], f"{name}: Invalid action: {decision['action']}"
    assert decision['amount'] >= 0, f"{name}: Negative amount: {decision['amount']}"

    print(f"  ✓ {name} working correctly")
    print(f"    Action: {decision['action']}, Amount: {decision['amount']:.2f} tons, Reason: {decision['reason']}")

    return True

def main():
    print("=" * 70)
    print("TESTING ALL 9 PERCENTAGE-BASED STRATEGIES")
    print("=" * 70)

    strategies = [
        # Baselines (no predictions)
        (ImmediateSaleStrategy, "ImmediateSaleStrategy", False),
        (EqualBatchStrategy, "EqualBatchStrategy", False),
        (PriceThresholdStrategy, "PriceThresholdStrategy", False),
        (MovingAverageStrategy, "MovingAverageStrategy", False),

        # Matched pairs (with predictions)
        (PriceThresholdPredictive, "PriceThresholdPredictive", True),
        (MovingAveragePredictive, "MovingAveragePredictive", True),

        # Standalone predictions
        (ExpectedValueStrategy, "ExpectedValueStrategy", True),
        (ConsensusStrategy, "ConsensusStrategy", True),
        (RiskAdjustedStrategy, "RiskAdjustedStrategy", True),
    ]

    passed = 0
    failed = 0

    for strategy_class, name, use_predictions in strategies:
        try:
            test_strategy(strategy_class, name, use_predictions)
            passed += 1
        except Exception as e:
            print(f"  ✗ {name} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
