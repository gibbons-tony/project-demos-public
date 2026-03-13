#!/usr/bin/env python3
"""
Local test for LP optimizer - verifies it works without Databricks access
"""
import numpy as np
import pandas as pd
from strategies.lp_optimizer import solve_optimal_liquidation_lp

def test_lp_optimizer():
    """Test LP optimizer with simple synthetic data."""

    print("\n" + "="*80)
    print("TESTING LP OPTIMIZER (Local)")
    print("="*80 + "\n")

    # Create simple test data
    n_days = 30
    dates = pd.date_range('2024-01-01', periods=n_days, freq='D')

    # Price pattern: starts at 100, peaks at 150 on day 15, ends at 110
    prices_cents = 100 + 50 * np.sin(np.linspace(0, np.pi, n_days))

    prices_df = pd.DataFrame({
        'date': dates,
        'price': prices_cents
    })

    # Harvest: Add 10 tons on days 0-9 (total 100 tons)
    harvest_amounts = np.zeros(n_days)
    harvest_amounts[0:10] = 10.0

    harvest_schedule = pd.DataFrame({
        'date': dates,
        'daily_increment': harvest_amounts
    })

    print("Test scenario:")
    print(f"  Days: {n_days}")
    print(f"  Total harvest: {harvest_amounts.sum():.1f} tons (days 0-9)")
    print(f"  Price range: {prices_cents.min():.1f} to {prices_cents.max():.1f} cents/lb")
    print(f"  Price peak: Day {np.argmax(prices_cents)}")

    # Costs
    storage_cost_pct = 0.3  # 0.3% per day
    transaction_cost_pct = 2.0  # 2% per transaction

    print(f"\nCosts:")
    print(f"  Storage: {storage_cost_pct}% per day")
    print(f"  Transaction: {transaction_cost_pct}% per sale")

    # Solve
    print(f"\nSolving LP...")
    try:
        result = solve_optimal_liquidation_lp(
            prices_df=prices_df,
            harvest_schedule=harvest_schedule,
            storage_cost_pct_per_day=storage_cost_pct,
            transaction_cost_pct=transaction_cost_pct
        )

        print(f"\n✅ LP SOLVER SUCCESS")
        print(f"\nResults:")
        print(f"  Max net earnings: ${result['max_net_earnings']:,.2f}")
        print(f"  Total revenue: ${result['total_revenue']:,.2f}")
        print(f"  Transaction costs: ${result['total_transaction_costs']:,.2f}")
        print(f"  Storage costs: ${result['total_storage_costs']:,.2f}")
        print(f"  Number of trades: {len(result['trades'])}")

        # Show trades
        print(f"\nTrade schedule:")
        for trade in result['trades']:
            print(f"  Day {trade['day']:2d} ({trade['date'].date()}): "
                  f"Sell {trade['amount']:6.1f} tons @ {trade['price']:6.2f} cents/lb "
                  f"= ${trade['revenue']:8,.0f}")

        # Validation checks
        print(f"\nValidation checks:")
        total_sold = sum(t['amount'] for t in result['trades'])
        total_harvested = harvest_amounts.sum()
        print(f"  Total sold: {total_sold:.1f} tons")
        print(f"  Total harvested: {total_harvested:.1f} tons")
        print(f"  Match: {'✓' if abs(total_sold - total_harvested) < 0.1 else '✗'}")

        # Check that we sold near price peak
        peak_day = np.argmax(prices_cents)
        sold_near_peak = sum(t['amount'] for t in result['trades']
                             if abs(t['day'] - peak_day) <= 3)
        pct_near_peak = 100 * sold_near_peak / total_sold
        print(f"  Sold near peak (±3 days): {pct_near_peak:.1f}%")
        print(f"  Strategy: {'Good' if pct_near_peak > 50 else 'Check logic'}")

        return True

    except Exception as e:
        print(f"\n❌ LP SOLVER FAILED")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_lp_optimizer()

    print(f"\n" + "="*80)
    if success:
        print("✅ LOCAL LP OPTIMIZER TEST PASSED")
    else:
        print("❌ LOCAL LP OPTIMIZER TEST FAILED")
    print("="*80 + "\n")

    exit(0 if success else 1)
