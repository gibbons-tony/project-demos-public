"""
Daily-Level Statistical Analysis

Uses daily_state data (~4,000 observations) to test if strategies significantly
outperform immediate sale baseline.

For each day, compares cumulative net value:
- Strategy: Current inventory value - cumulative storage costs - transaction costs from sales
- Baseline: What immediate sale would have earned (all sold at harvest, minus transaction costs)

Uses blocked bootstrap to account for temporal autocorrelation.
"""

import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, List, Tuple, Any
import pickle


class DailyLevelAnalyzer:
    """Analyzes backtest results using daily granularity"""

    def __init__(self, spark=None):
        self.spark = spark

    def load_detailed_results(self, commodity: str, model_version: str, pickle_path: str = None) -> Dict:
        """Load detailed results from pickle file"""
        if pickle_path is None:
            pickle_path = f"/Volumes/commodity/trading_agent/results/results_detailed_{commodity}_{model_version}.pkl"

        with open(pickle_path, 'rb') as f:
            return pickle.load(f)

    def create_daily_comparison(
        self,
        strategy_daily_state: pd.DataFrame,
        strategy_trades: List[Dict],
        baseline_daily_state: pd.DataFrame,
        baseline_trades: List[Dict]
    ) -> pd.DataFrame:
        """
        Create day-by-day comparison of cumulative net value

        For each day:
        - Strategy value = (current_inventory * today_price) - cumulative_storage - cumulative_transaction_costs
        - Baseline value = total_revenue_from_immediate_sales - cumulative_storage - cumulative_transaction_costs

        Args:
            strategy_daily_state: Daily state DataFrame for prediction strategy
            strategy_trades: List of trades for prediction strategy
            baseline_daily_state: Daily state for Immediate Sale
            baseline_trades: List of trades for Immediate Sale

        Returns:
            DataFrame with daily value comparison
        """
        # Ensure date is datetime
        strategy_daily = strategy_daily_state.copy()
        baseline_daily = baseline_daily_state.copy()

        strategy_daily['date'] = pd.to_datetime(strategy_daily['date'])
        baseline_daily['date'] = pd.to_datetime(baseline_daily['date'])

        # Calculate cumulative transaction costs for each strategy
        strategy_trades_df = pd.DataFrame(strategy_trades)
        baseline_trades_df = pd.DataFrame(baseline_trades)

        if len(strategy_trades_df) > 0:
            strategy_trades_df['date'] = pd.to_datetime(strategy_trades_df['date'])
            strategy_trades_df = strategy_trades_df.sort_values('date')
            strategy_trades_df['cumulative_transaction_cost'] = strategy_trades_df['transaction_cost'].cumsum()
            strategy_trades_df['cumulative_revenue'] = strategy_trades_df['revenue'].cumsum()

        if len(baseline_trades_df) > 0:
            baseline_trades_df['date'] = pd.to_datetime(baseline_trades_df['date'])
            baseline_trades_df = baseline_trades_df.sort_values('date')
            baseline_trades_df['cumulative_transaction_cost'] = baseline_trades_df['transaction_cost'].cumsum()
            baseline_trades_df['cumulative_revenue'] = baseline_trades_df['revenue'].cumsum()

        # Merge trade info with daily state
        comparison_data = []

        for idx, row in strategy_daily.iterrows():
            date = row['date']

            # Find corresponding baseline day
            baseline_row = baseline_daily[baseline_daily['date'] == date]
            if len(baseline_row) == 0:
                continue
            baseline_row = baseline_row.iloc[0]

            # Strategy cumulative value
            strategy_inventory_value = row['inventory'] * row['price'] * 20  # Convert to $/ton
            strategy_cumulative_storage = row['cumulative_storage_cost']

            # Get cumulative transaction costs and revenue up to this date
            strategy_trades_to_date = strategy_trades_df[strategy_trades_df['date'] <= date]
            strategy_cumulative_trans_cost = strategy_trades_to_date['cumulative_transaction_cost'].iloc[-1] if len(strategy_trades_to_date) > 0 else 0
            strategy_cumulative_revenue = strategy_trades_to_date['cumulative_revenue'].iloc[-1] if len(strategy_trades_to_date) > 0 else 0

            strategy_net_value = (strategy_inventory_value + strategy_cumulative_revenue -
                                 strategy_cumulative_storage - strategy_cumulative_trans_cost)

            # Baseline cumulative value
            baseline_inventory_value = baseline_row['inventory'] * baseline_row['price'] * 20
            baseline_cumulative_storage = baseline_row['cumulative_storage_cost']

            baseline_trades_to_date = baseline_trades_df[baseline_trades_df['date'] <= date]
            baseline_cumulative_trans_cost = baseline_trades_to_date['cumulative_transaction_cost'].iloc[-1] if len(baseline_trades_to_date) > 0 else 0
            baseline_cumulative_revenue = baseline_trades_to_date['cumulative_revenue'].iloc[-1] if len(baseline_trades_to_date) > 0 else 0

            baseline_net_value = (baseline_inventory_value + baseline_cumulative_revenue -
                                 baseline_cumulative_storage - baseline_cumulative_trans_cost)

            comparison_data.append({
                'date': date,
                'year': date.year,
                'strategy_net_value': strategy_net_value,
                'baseline_net_value': baseline_net_value,
                'daily_difference': strategy_net_value - baseline_net_value,
                'strategy_inventory': row['inventory'],
                'baseline_inventory': baseline_row['inventory']
            })

        return pd.DataFrame(comparison_data)

    def blocked_bootstrap_test(
        self,
        differences: np.ndarray,
        dates: pd.Series,
        n_bootstrap: int = 10000,
        block_size_days: int = 30
    ) -> Tuple[float, float, float]:
        """
        Blocked bootstrap test for time series data

        Resamples blocks of consecutive days to preserve temporal correlation structure.

        Args:
            differences: Array of daily differences
            dates: Series of dates corresponding to differences
            n_bootstrap: Number of bootstrap samples
            block_size_days: Size of blocks to resample (days)

        Returns:
            (mean_difference, p_value, ci_lower, ci_upper)
        """
        n_obs = len(differences)
        observed_mean = np.mean(differences)

        # Create blocks
        n_blocks = int(np.ceil(n_obs / block_size_days))
        bootstrap_means = []

        for _ in range(n_bootstrap):
            # Resample blocks with replacement
            sampled_blocks = np.random.choice(n_blocks, size=n_blocks, replace=True)

            # Reconstruct time series from sampled blocks
            resampled_data = []
            for block_idx in sampled_blocks:
                start_idx = block_idx * block_size_days
                end_idx = min((block_idx + 1) * block_size_days, n_obs)
                resampled_data.extend(differences[start_idx:end_idx])

            bootstrap_means.append(np.mean(resampled_data[:n_obs]))  # Trim to original length

        bootstrap_means = np.array(bootstrap_means)

        # Calculate p-value (two-tailed test against zero)
        p_value = np.mean(np.abs(bootstrap_means) >= np.abs(observed_mean))

        # 95% confidence interval
        ci_lower = np.percentile(bootstrap_means, 2.5)
        ci_upper = np.percentile(bootstrap_means, 97.5)

        return observed_mean, p_value, ci_lower, ci_upper

    def test_strategy_vs_baseline(
        self,
        comparison_df: pd.DataFrame,
        strategy_name: str,
        n_bootstrap: int = 10000,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Test if strategy significantly outperforms baseline using daily data

        Args:
            comparison_df: DataFrame from create_daily_comparison()
            strategy_name: Name of strategy
            n_bootstrap: Number of bootstrap samples
            verbose: Print results

        Returns:
            Dictionary with test results
        """
        differences = comparison_df['daily_difference'].values
        dates = comparison_df['date']
        years = comparison_df['year'].values

        n_days = len(differences)
        n_years = len(np.unique(years))

        # Blocked bootstrap test
        mean_diff, p_value, ci_lower, ci_upper = self.blocked_bootstrap_test(
            differences, dates, n_bootstrap=n_bootstrap
        )

        # Calculate year-level statistics for comparison
        year_means = comparison_df.groupby('year')['daily_difference'].mean()
        n_positive_years = sum(year_means > 0)

        # Effect size (using between-year std)
        cohens_d = mean_diff / year_means.std() if year_means.std() > 0 else 0

        # Interpretation
        significant_05 = p_value < 0.05

        effect_interp = 'negligible'
        abs_d = abs(cohens_d)
        if abs_d >= 0.8:
            effect_interp = 'large'
        elif abs_d >= 0.5:
            effect_interp = 'medium'
        elif abs_d >= 0.2:
            effect_interp = 'small'

        # Daily success rate
        n_positive_days = sum(differences > 0)
        daily_success_rate = n_positive_days / n_days

        if verbose:
            print(f"\n{strategy_name} vs Immediate Sale (Daily-Level Analysis):")
            print(f"  Sample: {n_days:,} days across {n_years} years")
            print(f"  Mean daily advantage: ${mean_diff:,.2f}")
            print(f"  Blocked bootstrap p-value: {p_value:.4f} {'✓' if significant_05 else '✗'}")
            print(f"  95% CI: [${ci_lower:,.2f}, ${ci_upper:,.2f}]")
            print(f"  Cohen's d: {cohens_d:.3f} ({effect_interp})")
            print(f"  Days with advantage: {n_positive_days:,}/{n_days:,} ({daily_success_rate:.1%})")
            print(f"  Years with positive mean: {n_positive_years}/{n_years}")

        return {
            'strategy': strategy_name,
            'n_days': n_days,
            'n_years': n_years,
            'mean_difference': mean_diff,
            'p_value': p_value,
            'significant_05': significant_05,
            'ci_95_lower': ci_lower,
            'ci_95_upper': ci_upper,
            'cohens_d': cohens_d,
            'effect_interpretation': effect_interp,
            'n_positive_days': n_positive_days,
            'daily_success_rate': daily_success_rate,
            'n_positive_years': n_positive_years
        }

    def analyze_all_prediction_strategies(
        self,
        commodity: str,
        model_version: str,
        pickle_path: str = None,
        n_bootstrap: int = 10000,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Analyze all prediction strategies vs immediate sale at daily level

        Args:
            commodity: Commodity name
            model_version: Model version
            pickle_path: Path to pickle file
            n_bootstrap: Number of bootstrap samples
            verbose: Print results

        Returns:
            Dictionary with results for all strategies
        """
        if verbose:
            print("=" * 80)
            print(f"DAILY-LEVEL ANALYSIS: {commodity.upper()} - {model_version}")
            print("=" * 80)

        # Load detailed results
        detailed_results = self.load_detailed_results(commodity, model_version, pickle_path)

        # Get baseline (Immediate Sale) data
        baseline_data = detailed_results['Immediate Sale']
        baseline_daily_state = baseline_data['daily_state']
        baseline_trades = baseline_data['trades']

        # Identify prediction strategies
        all_strategies = list(detailed_results.keys())
        prediction_keywords = ['Predictive', 'Consensus', 'Expected Value', 'Risk-Adjusted', 'MPC']
        prediction_strategies = [s for s in all_strategies if any(kw in s for kw in prediction_keywords)]

        if verbose:
            print(f"\nFound {len(prediction_strategies)} prediction strategies")
            print(f"Daily observations per strategy: ~{len(baseline_daily_state):,}")

        results = {}

        for strategy in prediction_strategies:
            strategy_data = detailed_results[strategy]
            strategy_daily_state = strategy_data['daily_state']
            strategy_trades = strategy_data['trades']

            # Create daily comparison
            comparison_df = self.create_daily_comparison(
                strategy_daily_state, strategy_trades,
                baseline_daily_state, baseline_trades
            )

            # Run statistical test
            test_results = self.test_strategy_vs_baseline(
                comparison_df, strategy, n_bootstrap, verbose
            )

            results[strategy] = test_results

        # Find best significant strategy
        significant_strategies = {k: v for k, v in results.items() if v['significant_05']}

        if significant_strategies:
            best_strategy_name = max(significant_strategies.keys(),
                                    key=lambda k: significant_strategies[k]['mean_difference'])
            best = significant_strategies[best_strategy_name]

            if verbose:
                print("\n" + "=" * 80)
                print("🏆 BEST SIGNIFICANT STRATEGY (Daily-Level)")
                print("=" * 80)
                print(f"Strategy: {best['strategy']}")
                print(f"Mean daily advantage: ${best['mean_difference']:,.2f}")
                print(f"p-value: {best['p_value']:.4f}")
                print(f"Effect size: {best['cohens_d']:.3f} ({best['effect_interpretation']})")
                print(f"Daily success rate: {best['daily_success_rate']:.1%}")
        else:
            best = None
            if verbose:
                print("\n" + "=" * 80)
                print("⚠️  NO STATISTICALLY SIGNIFICANT STRATEGIES FOUND")
                print("=" * 80)

        return {
            'commodity': commodity,
            'model_version': model_version,
            'n_strategies': len(prediction_strategies),
            'strategy_results': results,
            'best_significant': best,
            'has_significant_results': len(significant_strategies) > 0
        }


def run_daily_level_analysis(
    commodity: str,
    model_version: str,
    pickle_path: str = None,
    n_bootstrap: int = 10000,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Run daily-level statistical analysis

    Args:
        commodity: Commodity name
        model_version: Model version
        pickle_path: Path to detailed results pickle
        n_bootstrap: Number of bootstrap samples
        verbose: Print output

    Returns:
        Analysis results
    """
    analyzer = DailyLevelAnalyzer()
    return analyzer.analyze_all_prediction_strategies(
        commodity, model_version, pickle_path, n_bootstrap, verbose
    )
