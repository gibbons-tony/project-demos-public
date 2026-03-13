"""
Rigorous Statistical Testing for Trading Strategies

Implements finance best practices for testing strategy performance:
- Non-parametric tests for small samples (binomial, Wilcoxon)
- Daily returns with HAC standard errors (Newey-West)
- Monthly returns analysis
- Proper effect sizes and confidence intervals

Based on finance literature:
- Harvey & Liu (2015): Requires t-stat > 3.0 for significance
- White (2000): Reality check for data snooping
- Hansen (2005): Superior predictive ability test

Key principle: Use non-overlapping returns, account for autocorrelation
"""

import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, Tuple, List, Optional, Any
from statsmodels.stats.sandwich_covariance import cov_hac
from statsmodels.regression.linear_model import OLS
import pickle


class RigorousStatisticalAnalyzer:
    """
    Finance-grade statistical testing for trading strategies

    Implements multiple complementary approaches:
    1. Annual returns: Non-parametric tests (small sample)
    2. Daily returns: HAC-adjusted tests (large sample, autocorrelated)
    3. Monthly returns: Middle ground (moderate sample, low autocorrelation)
    """

    def __init__(self, spark=None):
        """
        Initialize analyzer

        Args:
            spark: Spark session for loading Delta tables
        """
        self.spark = spark

    # ========================================================================
    # DATA LOADING
    # ========================================================================

    def load_year_by_year_results(
        self,
        commodity: str,
        model_version: str
    ) -> pd.DataFrame:
        """
        Load annual results from Delta table

        Args:
            commodity: Commodity name
            model_version: Model version

        Returns:
            DataFrame with yearly results
        """
        table_name = f"commodity.trading_agent.results_{commodity}_by_year_{model_version}"
        df = self.spark.sql(f"SELECT * FROM {table_name}").toPandas()
        return df

    def load_detailed_results(
        self,
        commodity: str,
        model_version: str,
        pickle_path: str = None
    ) -> Dict[str, Any]:
        """
        Load detailed daily results from pickle

        Args:
            commodity: Commodity name
            model_version: Model version
            pickle_path: Optional path to pickle file

        Returns:
            Dictionary with detailed results including daily_state
        """
        if pickle_path is None:
            pickle_path = f"/Volumes/commodity/trading_agent/files/results_detailed_{commodity}_{model_version}.pkl"

        with open(pickle_path, 'rb') as f:
            return pickle.load(f)

    # ========================================================================
    # ANNUAL RETURNS: NON-PARAMETRIC TESTS (Best for n=11)
    # ========================================================================

    def test_annual_nonparametric(
        self,
        strategy_values: np.ndarray,
        baseline_values: np.ndarray,
        strategy_name: str,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Non-parametric tests on annual returns (designed for small samples)

        Tests:
        1. Binomial sign test: Is win rate > 50%?
        2. Wilcoxon signed-rank test: Are differences significant?

        Args:
            strategy_values: Annual net earnings for strategy (n years)
            baseline_values: Annual net earnings for baseline (n years)
            strategy_name: Name of strategy
            verbose: Print results

        Returns:
            Dictionary with test results
        """
        differences = strategy_values - baseline_values
        n_years = len(differences)

        # Binomial sign test
        n_positive = np.sum(differences > 0)
        n_negative = np.sum(differences < 0)
        n_ties = np.sum(differences == 0)

        # One-sided binomial test: P(X >= n_positive | p=0.5)
        binomial_result = stats.binomtest(n_positive, n_years, 0.5, alternative='greater')
        binomial_p = binomial_result.pvalue

        # Wilcoxon signed-rank test (more powerful, uses magnitude)
        if n_ties < n_years:  # Need at least one non-zero difference
            wilcoxon_stat, wilcoxon_p = stats.wilcoxon(
                differences[differences != 0],
                alternative='greater'
            )
        else:
            wilcoxon_stat, wilcoxon_p = np.nan, 1.0

        # Effect size: Cohen's d
        mean_diff = np.mean(differences)
        std_diff = np.std(differences, ddof=1)
        cohens_d = mean_diff / std_diff if std_diff > 0 else 0

        # Median and quartiles
        median_diff = np.median(differences)
        q1_diff = np.percentile(differences, 25)
        q3_diff = np.percentile(differences, 75)

        # Confidence interval (bootstrap)
        ci_lower, ci_upper = self._bootstrap_ci(differences)

        # Interpretation
        effect_interp = self._interpret_cohens_d(cohens_d)

        if verbose:
            print(f"\n{strategy_name} vs Baseline (Annual Returns):")
            print(f"  Sample size: {n_years} years")
            print(f"  Win rate: {n_positive}/{n_years} ({n_positive/n_years:.1%})")
            print(f"  Mean annual advantage: ${mean_diff:,.0f}")
            print(f"  Median annual advantage: ${median_diff:,.0f}")
            print(f"  IQR: [${q1_diff:,.0f}, ${q3_diff:,.0f}]")
            print(f"\n  Binomial sign test:")
            print(f"    H0: Win rate = 50% (no better than coin flip)")
            print(f"    p-value: {binomial_p:.6f} {'✓ SIGNIFICANT' if binomial_p < 0.05 else '✗'}")
            print(f"\n  Wilcoxon signed-rank test:")
            print(f"    p-value: {wilcoxon_p:.6f} {'✓ SIGNIFICANT' if wilcoxon_p < 0.05 else '✗'}")
            print(f"\n  Effect size: Cohen's d = {cohens_d:.3f} ({effect_interp})")
            print(f"  95% CI: [${ci_lower:,.0f}, ${ci_upper:,.0f}]")

        return {
            'strategy': strategy_name,
            'test_type': 'annual_nonparametric',
            'n_years': n_years,
            'n_positive': n_positive,
            'n_negative': n_negative,
            'win_rate': n_positive / n_years,
            'mean_difference': mean_diff,
            'median_difference': median_diff,
            'q1_difference': q1_diff,
            'q3_difference': q3_diff,
            'binomial_p_value': binomial_p,
            'binomial_significant_05': binomial_p < 0.05,
            'binomial_significant_01': binomial_p < 0.01,
            'wilcoxon_statistic': wilcoxon_stat,
            'wilcoxon_p_value': wilcoxon_p,
            'wilcoxon_significant_05': wilcoxon_p < 0.05,
            'cohens_d': cohens_d,
            'effect_interpretation': effect_interp,
            'ci_95_lower': ci_lower,
            'ci_95_upper': ci_upper
        }

    # ========================================================================
    # DAILY RETURNS: HAC-ADJUSTED TESTS (Uses all data)
    # ========================================================================

    def calculate_daily_returns(
        self,
        daily_state_strategy: pd.DataFrame,
        daily_state_baseline: pd.DataFrame,
        trades_strategy: List[Dict],
        trades_baseline: List[Dict]
    ) -> pd.DataFrame:
        """
        Calculate daily returns (not cumulative values)

        Daily return = (Net_value_today - Net_value_yesterday) / Net_value_yesterday

        This reduces autocorrelation compared to levels.

        Args:
            daily_state_strategy: Daily state for strategy
            daily_state_baseline: Daily state for baseline
            trades_strategy: Trades for strategy
            trades_baseline: Trades for baseline

        Returns:
            DataFrame with daily returns for both strategies
        """
        # Calculate daily net values (same as before)
        strategy_daily = daily_state_strategy.copy()
        baseline_daily = daily_state_baseline.copy()

        strategy_daily['date'] = pd.to_datetime(strategy_daily['date'])
        baseline_daily['date'] = pd.to_datetime(baseline_daily['date'])

        # Calculate cumulative revenues from trades
        strategy_trades_df = pd.DataFrame(trades_strategy)
        baseline_trades_df = pd.DataFrame(trades_baseline)

        if len(strategy_trades_df) > 0:
            strategy_trades_df['date'] = pd.to_datetime(strategy_trades_df['date'])
            strategy_trades_df = strategy_trades_df.sort_values('date')
            strategy_trades_df['cumulative_revenue'] = strategy_trades_df['revenue'].cumsum()
            strategy_trades_df['cumulative_trans_cost'] = strategy_trades_df['transaction_cost'].cumsum()

        if len(baseline_trades_df) > 0:
            baseline_trades_df['date'] = pd.to_datetime(baseline_trades_df['date'])
            baseline_trades_df = baseline_trades_df.sort_values('date')
            baseline_trades_df['cumulative_revenue'] = baseline_trades_df['revenue'].cumsum()
            baseline_trades_df['cumulative_trans_cost'] = baseline_trades_df['transaction_cost'].cumsum()

        # Merge and calculate net values
        daily_comparison = []

        for idx, row in strategy_daily.iterrows():
            date = row['date']

            baseline_row = baseline_daily[baseline_daily['date'] == date]
            if len(baseline_row) == 0:
                continue
            baseline_row = baseline_row.iloc[0]

            # Strategy net value
            strategy_inventory_value = row['inventory'] * row['price'] * 20
            strategy_cumulative_storage = row['cumulative_storage_cost']

            strategy_trades_to_date = strategy_trades_df[strategy_trades_df['date'] <= date]
            strategy_cumulative_revenue = strategy_trades_to_date['cumulative_revenue'].iloc[-1] if len(strategy_trades_to_date) > 0 else 0
            strategy_cumulative_trans = strategy_trades_to_date['cumulative_trans_cost'].iloc[-1] if len(strategy_trades_to_date) > 0 else 0

            strategy_net_value = (strategy_inventory_value + strategy_cumulative_revenue -
                                 strategy_cumulative_storage - strategy_cumulative_trans)

            # Baseline net value
            baseline_inventory_value = baseline_row['inventory'] * baseline_row['price'] * 20
            baseline_cumulative_storage = baseline_row['cumulative_storage_cost']

            baseline_trades_to_date = baseline_trades_df[baseline_trades_df['date'] <= date]
            baseline_cumulative_revenue = baseline_trades_to_date['cumulative_revenue'].iloc[-1] if len(baseline_trades_to_date) > 0 else 0
            baseline_cumulative_trans = baseline_trades_to_date['cumulative_trans_cost'].iloc[-1] if len(baseline_trades_to_date) > 0 else 0

            baseline_net_value = (baseline_inventory_value + baseline_cumulative_revenue -
                                 baseline_cumulative_storage - baseline_cumulative_trans)

            daily_comparison.append({
                'date': date,
                'strategy_net_value': strategy_net_value,
                'baseline_net_value': baseline_net_value
            })

        df = pd.DataFrame(daily_comparison)
        df = df.sort_values('date').reset_index(drop=True)

        # Calculate returns (percent change)
        df['strategy_return'] = df['strategy_net_value'].pct_change()
        df['baseline_return'] = df['baseline_net_value'].pct_change()
        df['excess_return'] = df['strategy_return'] - df['baseline_return']

        # Drop first row (NaN from pct_change)
        df = df.iloc[1:].reset_index(drop=True)

        return df

    def test_daily_returns_hac(
        self,
        daily_returns_df: pd.DataFrame,
        strategy_name: str,
        max_lags: int = 30,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Test daily excess returns with HAC standard errors (Newey-West)

        Accounts for autocorrelation in daily returns without throwing away data.

        Args:
            daily_returns_df: DataFrame with excess_return column
            strategy_name: Name of strategy
            max_lags: Maximum lags for HAC covariance (default 30 days ≈ 1 month)
            verbose: Print results

        Returns:
            Dictionary with test results
        """
        excess_returns = daily_returns_df['excess_return'].dropna().values
        n_days = len(excess_returns)

        # Mean excess return
        mean_excess = np.mean(excess_returns)

        # OLS regression: excess_return ~ 1 (just testing if mean != 0)
        y = excess_returns
        X = np.ones((len(y), 1))  # Intercept only

        model = OLS(y, X).fit()

        # HAC standard errors (Newey-West)
        hac_cov = cov_hac(model, nlags=max_lags)
        hac_se = np.sqrt(hac_cov[0, 0])

        # t-statistic with HAC standard errors
        t_stat_hac = mean_excess / hac_se

        # p-value (two-tailed)
        df = n_days - 1
        p_value_hac = 2 * (1 - stats.t.cdf(abs(t_stat_hac), df))

        # Confidence interval with HAC SE
        t_critical = stats.t.ppf(0.975, df)
        ci_lower_hac = mean_excess - t_critical * hac_se
        ci_upper_hac = mean_excess + t_critical * hac_se

        # Compare to naive (non-HAC) standard error
        naive_se = np.std(excess_returns, ddof=1) / np.sqrt(n_days)
        t_stat_naive = mean_excess / naive_se
        p_value_naive = 2 * (1 - stats.t.cdf(abs(t_stat_naive), df))

        # Annualized metrics (assuming 252 trading days/year)
        annualized_excess = mean_excess * 252
        sharpe_ratio = mean_excess / np.std(excess_returns) * np.sqrt(252) if np.std(excess_returns) > 0 else 0

        if verbose:
            print(f"\n{strategy_name} vs Baseline (Daily Returns with HAC):")
            print(f"  Sample size: {n_days:,} days")
            print(f"  Mean daily excess return: {mean_excess:.6f} ({mean_excess*100:.4f}%)")
            print(f"  Annualized excess return: {annualized_excess:.4f} ({annualized_excess*100:.2f}%)")
            print(f"  Sharpe ratio (annualized): {sharpe_ratio:.3f}")
            print(f"\n  HAC-adjusted test (accounts for autocorrelation):")
            print(f"    t-statistic: {t_stat_hac:.3f}")
            print(f"    p-value: {p_value_hac:.6f} {'✓ SIGNIFICANT' if p_value_hac < 0.05 else '✗'}")
            print(f"    95% CI: [{ci_lower_hac:.6f}, {ci_upper_hac:.6f}]")
            print(f"\n  Naive test (ignores autocorrelation - for comparison):")
            print(f"    t-statistic: {t_stat_naive:.3f}")
            print(f"    p-value: {p_value_naive:.6f}")
            print(f"\n  Interpretation:")
            if p_value_hac < 0.05:
                print(f"    ✓ Statistically significant with proper autocorrelation adjustment")
            else:
                print(f"    ✗ Not significant even with {n_days:,} observations")
                print(f"      (Autocorrelation reduces effective sample size)")

        return {
            'strategy': strategy_name,
            'test_type': 'daily_returns_hac',
            'n_days': n_days,
            'mean_daily_excess_return': mean_excess,
            'annualized_excess_return': annualized_excess,
            'sharpe_ratio': sharpe_ratio,
            't_statistic_hac': t_stat_hac,
            'p_value_hac': p_value_hac,
            'significant_05_hac': p_value_hac < 0.05,
            'ci_95_lower_hac': ci_lower_hac,
            'ci_95_upper_hac': ci_upper_hac,
            'hac_standard_error': hac_se,
            't_statistic_naive': t_stat_naive,
            'p_value_naive': p_value_naive,
            'naive_standard_error': naive_se
        }

    # ========================================================================
    # MONTHLY RETURNS: MIDDLE GROUND
    # ========================================================================

    def calculate_monthly_returns(
        self,
        daily_returns_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Aggregate daily returns to monthly (non-overlapping periods)

        Args:
            daily_returns_df: DataFrame with daily returns

        Returns:
            DataFrame with monthly returns
        """
        df = daily_returns_df.copy()
        df['year_month'] = df['date'].dt.to_period('M')

        # Calculate end-of-month values
        monthly = df.groupby('year_month').agg({
            'strategy_net_value': 'last',
            'baseline_net_value': 'last',
            'date': 'last'
        }).reset_index()

        # Calculate monthly returns
        monthly['strategy_return'] = monthly['strategy_net_value'].pct_change()
        monthly['baseline_return'] = monthly['baseline_net_value'].pct_change()
        monthly['excess_return'] = monthly['strategy_return'] - monthly['baseline_return']

        # Drop first row (NaN)
        monthly = monthly.iloc[1:].reset_index(drop=True)

        return monthly

    def test_monthly_returns(
        self,
        monthly_returns_df: pd.DataFrame,
        strategy_name: str,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Test monthly excess returns (standard t-test, minimal autocorrelation)

        Args:
            monthly_returns_df: DataFrame with monthly excess returns
            strategy_name: Name of strategy
            verbose: Print results

        Returns:
            Dictionary with test results
        """
        excess_returns = monthly_returns_df['excess_return'].dropna().values
        n_months = len(excess_returns)

        # One-sample t-test: Is mean excess return > 0?
        mean_excess = np.mean(excess_returns)
        t_stat, p_value = stats.ttest_1samp(excess_returns, 0, alternative='greater')

        # Confidence interval
        se = stats.sem(excess_returns)
        df = n_months - 1
        t_critical = stats.t.ppf(0.975, df)
        ci_lower = mean_excess - t_critical * se
        ci_upper = mean_excess + t_critical * se

        # Win rate
        n_positive = np.sum(excess_returns > 0)
        win_rate = n_positive / n_months

        # Annualized
        annualized_excess = mean_excess * 12
        sharpe_ratio = mean_excess / np.std(excess_returns) * np.sqrt(12) if np.std(excess_returns) > 0 else 0

        if verbose:
            print(f"\n{strategy_name} vs Baseline (Monthly Returns):")
            print(f"  Sample size: {n_months} months")
            print(f"  Mean monthly excess return: {mean_excess:.6f} ({mean_excess*100:.4f}%)")
            print(f"  Annualized excess return: {annualized_excess:.4f} ({annualized_excess*100:.2f}%)")
            print(f"  Monthly win rate: {n_positive}/{n_months} ({win_rate:.1%})")
            print(f"  Sharpe ratio (annualized): {sharpe_ratio:.3f}")
            print(f"\n  One-sample t-test:")
            print(f"    t-statistic: {t_stat:.3f} (df={df})")
            print(f"    p-value: {p_value:.6f} {'✓ SIGNIFICANT' if p_value < 0.05 else '✗'}")
            print(f"    95% CI: [{ci_lower:.6f}, {ci_upper:.6f}]")

        return {
            'strategy': strategy_name,
            'test_type': 'monthly_returns',
            'n_months': n_months,
            'mean_monthly_excess_return': mean_excess,
            'annualized_excess_return': annualized_excess,
            'sharpe_ratio': sharpe_ratio,
            'win_rate': win_rate,
            't_statistic': t_stat,
            'p_value': p_value,
            'significant_05': p_value < 0.05,
            'ci_95_lower': ci_lower,
            'ci_95_upper': ci_upper
        }

    # ========================================================================
    # COMPREHENSIVE ANALYSIS
    # ========================================================================

    def analyze_strategy_comprehensive(
        self,
        commodity: str,
        model_version: str,
        strategy_name: str,
        baseline_name: str = 'Immediate Sale',
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Run rigorous statistical tests on a strategy using high-granularity data

        1. Daily: HAC-adjusted t-test on returns (n~3,780)
        2. Monthly: Standard t-test on returns (n~132)

        Args:
            commodity: Commodity name
            model_version: Model version
            strategy_name: Name of strategy to test
            baseline_name: Name of baseline strategy
            verbose: Print results

        Returns:
            Dictionary with all test results
        """
        if verbose:
            print("=" * 80)
            print(f"RIGOROUS STATISTICAL ANALYSIS")
            print(f"Commodity: {commodity.upper()} | Model: {model_version}")
            print(f"Strategy: {strategy_name}")
            print(f"Baseline: {baseline_name}")
            print("=" * 80)

        results = {}

        # ====================================================================
        # 1. DAILY RETURNS (HAC-adjusted)
        # ====================================================================

        if verbose:
            print("\n" + "=" * 80)
            print("1. DAILY RETURNS (HAC-Adjusted Test)")
            print("   Sample: ~3,780 days")
            print("   Method: Newey-West HAC standard errors")
            print("=" * 80)

        try:
            detailed_results = self.load_detailed_results(commodity, model_version)

            if strategy_name in detailed_results and baseline_name in detailed_results:
                strategy_data = detailed_results[strategy_name]
                baseline_data = detailed_results[baseline_name]

                daily_returns_df = self.calculate_daily_returns(
                    strategy_data['daily_state'],
                    baseline_data['daily_state'],
                    strategy_data['trades'],
                    baseline_data['trades']
                )

                results['daily'] = self.test_daily_returns_hac(
                    daily_returns_df, strategy_name, verbose=verbose
                )

                # ============================================================
                # 2. MONTHLY RETURNS
                # ============================================================

                if verbose:
                    print("\n" + "=" * 80)
                    print("2. MONTHLY RETURNS (Standard t-test)")
                    print("   Sample: ~132 months")
                    print("   Method: Standard t-test (minimal autocorrelation)")
                    print("=" * 80)

                monthly_returns_df = self.calculate_monthly_returns(daily_returns_df)

                results['monthly'] = self.test_monthly_returns(
                    monthly_returns_df, strategy_name, verbose=verbose
                )
            else:
                results['daily'] = None
                results['monthly'] = None
                if verbose:
                    print("  ⚠️  Strategy or baseline not found in detailed results")

        except Exception as e:
            results['daily'] = None
            results['monthly'] = None
            if verbose:
                print(f"  ⚠️  Could not load detailed results: {e}")

        # ====================================================================
        # SUMMARY
        # ====================================================================

        if verbose:
            print("\n" + "=" * 80)
            print("SUMMARY: STATISTICAL SIGNIFICANCE")
            print("=" * 80)

            sig_count = 0
            total_tests = 0

            if results.get('daily'):
                print(f"\nDaily (n={results['daily']['n_days']:,} days):")
                print(f"  HAC t-test: {'✓ SIGNIFICANT (p<0.05)' if results['daily']['significant_05_hac'] else '✗ Not significant'}")
                print(f"  p-value: {results['daily']['p_value_hac']:.6f}")
                print(f"  Annualized excess return: {results['daily']['annualized_excess_return']*100:.2f}%")
                print(f"  Sharpe ratio: {results['daily']['sharpe_ratio']:.3f}")
                if results['daily']['significant_05_hac']:
                    sig_count += 1
                total_tests += 1

            if results.get('monthly'):
                print(f"\nMonthly (n={results['monthly']['n_months']} months):")
                print(f"  t-test: {'✓ SIGNIFICANT (p<0.05)' if results['monthly']['significant_05'] else '✗ Not significant'}")
                print(f"  p-value: {results['monthly']['p_value']:.6f}")
                print(f"  Annualized excess return: {results['monthly']['annualized_excess_return']*100:.2f}%")
                print(f"  Win rate: {results['monthly']['win_rate']:.1%}")
                if results['monthly']['significant_05']:
                    sig_count += 1
                total_tests += 1

            print(f"\n{'='*80}")
            if sig_count == total_tests and total_tests > 0:
                print(f"✓ STATISTICALLY SIGNIFICANT: Both tests show p<0.05")
            elif sig_count > 0:
                print(f"~ MIXED EVIDENCE: {sig_count}/{total_tests} tests significant")
            else:
                print(f"✗ NOT SIGNIFICANT: Strategy does not beat baseline (p≥0.05)")
            print("=" * 80)

        return results

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _bootstrap_ci(
        self,
        data: np.ndarray,
        n_bootstrap: int = 10000,
        alpha: float = 0.05
    ) -> Tuple[float, float]:
        """
        Bootstrap confidence interval for mean

        Args:
            data: Data array
            n_bootstrap: Number of bootstrap samples
            alpha: Significance level (default 0.05 for 95% CI)

        Returns:
            (lower, upper) confidence interval
        """
        bootstrap_means = []
        n = len(data)

        for _ in range(n_bootstrap):
            sample = np.random.choice(data, size=n, replace=True)
            bootstrap_means.append(np.mean(sample))

        lower = np.percentile(bootstrap_means, alpha/2 * 100)
        upper = np.percentile(bootstrap_means, (1 - alpha/2) * 100)

        return lower, upper

    def _interpret_cohens_d(self, d: float) -> str:
        """Interpret Cohen's d effect size"""
        abs_d = abs(d)
        if abs_d >= 0.8:
            return 'large'
        elif abs_d >= 0.5:
            return 'medium'
        elif abs_d >= 0.2:
            return 'small'
        else:
            return 'negligible'


def run_comprehensive_analysis(
    commodity: str,
    model_version: str,
    strategy_name: str,
    baseline_name: str = 'Immediate Sale',
    spark = None,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Convenience function for running comprehensive analysis

    Args:
        commodity: Commodity name
        model_version: Model version
        strategy_name: Strategy to test
        baseline_name: Baseline strategy
        spark: Spark session
        verbose: Print results

    Returns:
        Dictionary with all test results
    """
    analyzer = RigorousStatisticalAnalyzer(spark=spark)
    return analyzer.analyze_strategy_comprehensive(
        commodity, model_version, strategy_name, baseline_name, verbose
    )
