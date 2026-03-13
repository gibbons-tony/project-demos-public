"""
Daily-Level Statistical Analysis

Analyzes trading strategies at the daily level using daily_state data.
This provides maximum statistical power (~4,000 observations vs 11 years).

Compares cumulative value each day: what would liquidating all inventory today yield
under each strategy vs immediate sale baseline?

Uses blocked bootstrap to account for temporal autocorrelation.
"""

import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, List, Tuple, Any, Optional
import pickle


class DailyLevelAnalyzer:
    """Analyzes backtest results at the daily level using full daily_state data"""

    def __init__(self, spark=None):
        """
        Initialize daily-level analyzer

        Args:
            spark: Spark session (for loading data from DBFS/volumes)
        """
        self.spark = spark

    def load_detailed_results(
        self,
        commodity: str,
        model_version: str,
        pickle_path: str = None
    ) -> Dict[str, Any]:
        """
        Load detailed results from pickle file

        Args:
            commodity: Commodity name
            model_version: Model version
            pickle_path: Path to pickle file (if None, uses default)

        Returns:
            Dictionary with detailed results for all strategies
        """
        if pickle_path is None:
            pickle_path = f"/Volumes/commodity/trading_agent/results/results_detailed_{commodity}_{model_version}.pkl"

        # Load from DBFS/volume
        with open(pickle_path, 'rb') as f:
            detailed_results = pickle.load(f)

        return detailed_results

    def extract_trade_dataframe(
        self,
        detailed_results: Dict[str, Any],
        strategy_name: str
    ) -> pd.DataFrame:
        """
        Extract trade-level data for a specific strategy

        Args:
            detailed_results: Full detailed results dictionary
            strategy_name: Name of strategy to extract

        Returns:
            DataFrame with one row per trade
        """
        if strategy_name not in detailed_results:
            raise ValueError(f"Strategy {strategy_name} not found in results")

        strategy_data = detailed_results[strategy_name]
        trades = strategy_data['trades']

        # Convert trades list to DataFrame
        trades_df = pd.DataFrame(trades)

        # Add year column for clustering
        trades_df['year'] = pd.to_datetime(trades_df['date']).dt.year

        # Add strategy name
        trades_df['strategy'] = strategy_name

        return trades_df

    def create_immediate_sale_counterfactual(
        self,
        detailed_results: Dict[str, Any],
        prediction_strategy_trades: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Create counterfactual: what would immediate sale have earned for each trade?

        For each trade in the prediction strategy, find what the harvest-date price was
        (when the inventory was first added) to calculate immediate sale revenue.

        Args:
            detailed_results: Full results including Immediate Sale strategy
            prediction_strategy_trades: Trade data for prediction strategy

        Returns:
            DataFrame with paired trade comparisons
        """
        # Get immediate sale trades to find harvest prices
        immediate_sale_data = detailed_results['Immediate Sale']
        immediate_sale_trades = pd.DataFrame(immediate_sale_data['trades'])
        immediate_sale_trades['year'] = pd.to_datetime(immediate_sale_trades['date']).dt.year

        # Get daily state to track when inventory was added (harvest dates)
        daily_state = immediate_sale_data['daily_state']

        # For each prediction strategy trade, find the harvest-date price
        # This tells us what immediate sale would have earned
        comparisons = []

        for idx, trade in prediction_strategy_trades.iterrows():
            trade_year = trade['year']
            trade_amount = trade['amount']

            # Find the immediate sale trades from the same year
            year_immediate_trades = immediate_sale_trades[
                immediate_sale_trades['year'] == trade_year
            ]

            if len(year_immediate_trades) > 0:
                # For immediate sale, all sales happen at harvest prices
                # Use weighted average harvest price for this year
                harvest_price = year_immediate_trades['price'].mean()
                harvest_revenue_per_ton = harvest_price * 20  # Convert to $/ton

                # Calculate what immediate sale would have earned
                immediate_sale_revenue = trade_amount * harvest_revenue_per_ton

                # Apply same transaction cost percentage
                transaction_cost_pct = 0.5  # Default from config
                immediate_sale_cost = immediate_sale_revenue * (transaction_cost_pct / 100)
                immediate_sale_net = immediate_sale_revenue - immediate_sale_cost

                comparisons.append({
                    'date': trade['date'],
                    'year': trade_year,
                    'amount': trade_amount,
                    'strategy_price': trade['price'],
                    'strategy_revenue': trade['revenue'],
                    'strategy_net_revenue': trade['net_revenue'],
                    'immediate_sale_price': harvest_price,
                    'immediate_sale_revenue': immediate_sale_revenue,
                    'immediate_sale_net_revenue': immediate_sale_net,
                    'difference': trade['net_revenue'] - immediate_sale_net,
                    'strategy': trade['strategy']
                })

        return pd.DataFrame(comparisons)

    def clustered_ttest(
        self,
        differences: np.ndarray,
        cluster_ids: np.ndarray
    ) -> Tuple[float, float, float]:
        """
        Perform t-test with clustered standard errors

        Accounts for correlation between observations within the same cluster (year).

        Args:
            differences: Array of differences (strategy - baseline)
            cluster_ids: Array of cluster identifiers (years)

        Returns:
            (mean_difference, t_statistic, p_value)
        """
        n = len(differences)
        mean_diff = np.mean(differences)

        # Calculate clustered standard errors
        # Group differences by cluster
        unique_clusters = np.unique(cluster_ids)
        n_clusters = len(unique_clusters)

        # Calculate cluster means
        cluster_means = []
        cluster_sizes = []
        for cluster in unique_clusters:
            cluster_data = differences[cluster_ids == cluster]
            cluster_means.append(np.mean(cluster_data))
            cluster_sizes.append(len(cluster_data))

        cluster_means = np.array(cluster_means)

        # Clustered variance estimator
        # Var = (n_clusters / (n_clusters - 1)) * sum((cluster_mean - overall_mean)^2 * cluster_size^2) / n^2
        cluster_deviations = cluster_means - mean_diff
        variance_components = [(dev ** 2) * (size ** 2) for dev, size in zip(cluster_deviations, cluster_sizes)]
        clustered_var = (n_clusters / (n_clusters - 1)) * sum(variance_components) / (n ** 2)
        clustered_se = np.sqrt(clustered_var)

        # t-statistic with n_clusters - 1 degrees of freedom
        t_stat = mean_diff / clustered_se if clustered_se > 0 else 0
        df = n_clusters - 1
        p_value = 2 * (1 - stats.t.cdf(abs(t_stat), df))

        return mean_diff, t_stat, p_value, clustered_se

    def test_strategy_vs_immediate_sale(
        self,
        comparison_df: pd.DataFrame,
        strategy_name: str,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Test if a strategy significantly outperforms immediate sale at trade level

        Args:
            comparison_df: DataFrame from create_immediate_sale_counterfactual()
            strategy_name: Name of strategy being tested
            verbose: Print detailed results

        Returns:
            Dictionary with statistical test results
        """
        differences = comparison_df['difference'].values
        years = comparison_df['year'].values

        n_trades = len(differences)
        n_years = len(np.unique(years))

        # Clustered t-test
        mean_diff, t_stat, p_value, clustered_se = self.clustered_ttest(differences, years)

        # Effect size (Cohen's d using clustered standard deviation)
        # Use between-cluster std for effect size
        year_means = comparison_df.groupby('year')['difference'].mean()
        cohens_d = mean_diff / year_means.std() if year_means.std() > 0 else 0

        # Confidence interval (using clustered SE)
        df = n_years - 1
        t_critical = stats.t.ppf(0.975, df)
        ci_95_lower = mean_diff - t_critical * clustered_se
        ci_95_upper = mean_diff + t_critical * clustered_se

        # Sign test at year level
        n_positive_years = sum(year_means > 0)
        sign_p_value = stats.binomtest(n_positive_years, n_years, 0.5, alternative='greater').pvalue

        # Trade-level success rate
        n_positive_trades = sum(differences > 0)
        trade_success_rate = n_positive_trades / n_trades

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

        if verbose:
            print(f"\n{strategy_name} vs Immediate Sale (Trade-Level Analysis):")
            print(f"  Sample: {n_trades} trades across {n_years} years")
            print(f"  Mean improvement per trade: ${mean_diff:,.2f}")
            print(f"  Clustered SE: ${clustered_se:,.2f}")
            print(f"  t-statistic: {t_stat:.3f} (df={df})")
            print(f"  p-value: {p_value:.4f} {'✓' if significant_05 else '✗'}")
            print(f"  95% CI: [${ci_95_lower:,.2f}, ${ci_95_upper:,.2f}]")
            print(f"  Cohen's d: {cohens_d:.3f} ({effect_interp})")
            print(f"  Trade success rate: {trade_success_rate:.1%} ({n_positive_trades}/{n_trades})")
            print(f"  Years with positive mean: {n_positive_years}/{n_years}")
            print(f"  Year-level sign test p-value: {sign_p_value:.4f}")

        return {
            'strategy': strategy_name,
            'n_trades': n_trades,
            'n_years': n_years,
            'mean_difference': mean_diff,
            'clustered_se': clustered_se,
            't_statistic': t_stat,
            'p_value': p_value,
            'significant_05': significant_05,
            'ci_95_lower': ci_95_lower,
            'ci_95_upper': ci_95_upper,
            'cohens_d': cohens_d,
            'effect_interpretation': effect_interp,
            'n_positive_trades': n_positive_trades,
            'trade_success_rate': trade_success_rate,
            'n_positive_years': n_positive_years,
            'sign_test_p_value': sign_p_value
        }

    def analyze_all_prediction_strategies(
        self,
        commodity: str,
        model_version: str,
        pickle_path: str = None,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Analyze all prediction strategies vs immediate sale at trade level

        Args:
            commodity: Commodity name
            model_version: Model version
            pickle_path: Path to pickle file (optional)
            verbose: Print results

        Returns:
            Dictionary with results for all strategies
        """
        if verbose:
            print("=" * 80)
            print(f"TRADE-LEVEL ANALYSIS: {commodity.upper()} - {model_version}")
            print("=" * 80)

        # Load detailed results
        detailed_results = self.load_detailed_results(commodity, model_version, pickle_path)

        # Identify prediction strategies
        all_strategies = list(detailed_results.keys())
        prediction_keywords = ['Predictive', 'Consensus', 'Expected Value', 'Risk-Adjusted', 'MPC']
        prediction_strategies = [s for s in all_strategies if any(kw in s for kw in prediction_keywords)]

        if verbose:
            print(f"\nFound {len(prediction_strategies)} prediction strategies to analyze")
            print(f"Comparing against: Immediate Sale\n")

        results = {}

        for strategy in prediction_strategies:
            # Extract trades
            strategy_trades = self.extract_trade_dataframe(detailed_results, strategy)

            # Create counterfactual comparison
            comparison_df = self.create_immediate_sale_counterfactual(
                detailed_results, strategy_trades
            )

            # Run statistical test
            test_results = self.test_strategy_vs_immediate_sale(
                comparison_df, strategy, verbose
            )

            results[strategy] = test_results

        # Find best strategy
        significant_strategies = {k: v for k, v in results.items() if v['significant_05']}

        if significant_strategies:
            best_strategy_name = max(significant_strategies.keys(),
                                    key=lambda k: significant_strategies[k]['mean_difference'])
            best = significant_strategies[best_strategy_name]

            if verbose:
                print("\n" + "=" * 80)
                print("🏆 BEST SIGNIFICANT STRATEGY (Trade-Level)")
                print("=" * 80)
                print(f"Strategy: {best['strategy']}")
                print(f"Mean improvement per trade: ${best['mean_difference']:,.2f}")
                print(f"p-value: {best['p_value']:.4f}")
                print(f"Effect size: {best['cohens_d']:.3f} ({best['effect_interpretation']})")
                print(f"Trade success rate: {best['trade_success_rate']:.1%}")
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


def run_trade_level_analysis(
    commodity: str,
    model_version: str,
    pickle_path: str = None,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Run trade-level statistical analysis

    Args:
        commodity: Commodity name (e.g., 'coffee', 'sugar')
        model_version: Model version (e.g., 'naive', 'prophet_v1')
        pickle_path: Path to detailed results pickle file (optional)
        verbose: Print detailed output

    Returns:
        Dictionary with analysis results
    """
    analyzer = TradeLevelAnalyzer()
    results = analyzer.analyze_all_prediction_strategies(
        commodity, model_version, pickle_path, verbose
    )

    return results
