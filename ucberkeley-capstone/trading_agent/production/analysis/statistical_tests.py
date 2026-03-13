"""
Statistical Validation for Trading Strategies

Provides statistical tests to determine if strategy improvements are significant
or could be due to random chance.

Key tests:
- Paired t-test: Does strategy beat baseline across years?
- Sign test: Non-parametric robustness check
- Bootstrap CI: Confidence intervals for differences
- Effect sizes: Cohen's d for practical significance
"""

import pandas as pd
import numpy as np
from scipy import stats
from statsmodels.stats.multitest import multipletests
from statsmodels.regression.linear_model import OLS
from statsmodels.stats.sandwich_covariance import cov_cluster
from typing import Dict, Tuple, List, Optional, Any
import pickle
import os
import json


class StatisticalAnalyzer:
    """
    Runs statistical validation on backtest results

    Answers the key question: "Is this improvement statistically significant
    or could it be random chance?"
    """

    def __init__(self, spark=None):
        """
        Initialize statistical analyzer

        Args:
            spark: Spark session (required for loading Delta tables)
        """
        self.spark = spark

    def load_forecast_manifest(self, commodity: str) -> Optional[Dict]:
        """
        Load forecast manifest to determine valid time periods for a commodity

        Args:
            commodity: Commodity name (e.g., 'coffee')

        Returns:
            Dict with manifest data or None if not found
        """
        manifest_path = f"/dbfs/production/files/forecast_manifest_{commodity}.json"

        try:
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            return manifest
        except FileNotFoundError:
            print(f"⚠️  Warning: Forecast manifest not found at {manifest_path}")
            return None
        except Exception as e:
            print(f"⚠️  Warning: Could not load manifest: {e}")
            return None

    def load_year_by_year_results(
        self,
        commodity: str,
        model_version: str
    ) -> pd.DataFrame:
        """
        Load year-by-year results from Delta table, filtering to valid years only

        Valid years are determined by the forecast manifest (years_available field),
        which tells us which years have valid forecast data for the model.

        Args:
            commodity: Commodity name (e.g., 'coffee')
            model_version: Model version (e.g., 'naive')

        Returns:
            DataFrame with columns [year, strategy, net_earnings, ...]
            Filtered to valid years only
        """
        if self.spark is None:
            raise ValueError("Spark session required to load results")

        table_name = f"commodity.trading_agent.results_{commodity}_by_year_{model_version}"

        try:
            # Load forecast manifest to get valid years for this model
            manifest = self.load_forecast_manifest(commodity)

            if manifest and 'models' in manifest and model_version in manifest['models']:
                # Use years_available from manifest (intelligent time period detection)
                valid_years = manifest['models'][model_version]['years_available']
                print(f"✓ Using forecast manifest for valid years: {valid_years}")
                print(f"  Date range: {manifest['models'][model_version]['date_range']}")
                print(f"  Coverage: {manifest['models'][model_version]['coverage_pct']:.1f}%")
            else:
                # Fallback: compute valid years from data
                print(f"⚠️  Forecast manifest not available for {model_version}, computing valid years from data...")
                df_spark = self.spark.table(table_name)
                from pyspark.sql.functions import min as spark_min
                valid_years_df = df_spark.groupBy('year').agg(
                    spark_min('net_earnings').alias('min_earnings')
                ).filter('min_earnings > 0')
                valid_years = sorted([row.year for row in valid_years_df.collect()])
                print(f"  Computed valid years: {valid_years}")

            # Load data and filter to valid years
            df_spark = self.spark.table(table_name)
            df = df_spark.filter(df_spark.year.isin(valid_years)).toPandas()

            total_rows = self.spark.table(table_name).count()
            print(f"✓ Loaded {len(df)} year-strategy combinations from {table_name}")
            print(f"  Valid years: {sorted(valid_years)} ({len(valid_years)} years)")
            print(f"  Filtered out {total_rows - len(df)} invalid rows")

            return df
        except Exception as e:
            raise ValueError(f"Could not load results table {table_name}: {e}")

    def load_detailed_results(
        self,
        commodity: str,
        model_version: str
    ) -> Optional[Dict[str, Any]]:
        """
        Load detailed results from pickle file (contains daily_state DataFrames)

        Args:
            commodity: Commodity name (e.g., 'coffee')
            model_version: Model version (e.g., 'naive')

        Returns:
            Dict mapping {strategy_name: results_dict} where results_dict contains:
                - 'daily_state': DataFrame with daily data
                - 'trades': List of trades
                - 'net_earnings': Total earnings
                - etc.
            Returns None if pickle file not found
        """
        # Try multiple possible file locations
        possible_paths = [
            f"/dbfs/production/files/results_detailed_{commodity}_{model_version}.pkl",  # Production location
            f"/dbfs/volumes/commodity/trading_agent/results/results_detailed_{commodity}_{model_version}.pkl",
            f"/Volumes/commodity/trading_agent/results/results_detailed_{commodity}_{model_version}.pkl",
            f"/dbfs/FileStore/trading_agent/results_detailed_{commodity}_{model_version}.pkl"
        ]

        for file_path in possible_paths:
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'rb') as f:
                        results_dict = pickle.load(f)
                    print(f"✓ Loaded detailed results from {file_path}")
                    print(f"  Contains {len(results_dict)} strategies")
                    return results_dict
                except Exception as e:
                    print(f"⚠️  Error loading {file_path}: {e}")
                    continue

        print(f"⚠️  No pickle file found for {commodity}/{model_version}")
        print(f"    Tried: {possible_paths}")
        return None

    def run_multi_granularity_analysis(
        self,
        commodity: str,
        model_version: str,
        strategy_name: str,
        baseline_name: str,
        granularities: List[str] = ['year', 'quarter', 'month'],
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Run analysis at multiple time granularities and compare

        This addresses the small sample size problem (n=5 years) by also
        analyzing at finer granularities (monthly: n=60, quarterly: n=20)
        with proper clustered standard errors.

        Args:
            commodity: Commodity name
            model_version: Model version
            strategy_name: Strategy to test
            baseline_name: Baseline to compare against
            granularities: List of granularities to test
            verbose: Print results

        Returns:
            Dict with results at each granularity
        """
        if verbose:
            print(f"\n{'=' * 80}")
            print(f"MULTI-GRANULARITY ANALYSIS: {strategy_name} vs {baseline_name}")
            print(f"{'=' * 80}")

        # Load detailed results from pickle
        results_dict = self.load_detailed_results(commodity, model_version)

        if results_dict is None:
            print(f"❌ Could not load detailed results for multi-granularity analysis")
            print(f"   Pickle files not available - multi-granularity analysis skipped")
            return {'error': 'Pickle files not found'}

        # Convert pickle data to DataFrame format for aggregation
        # Each strategy has a 'daily_state' DataFrame
        all_daily_data = []

        for strategy, strategy_results in results_dict.items():
            if 'daily_state' in strategy_results and strategy_results['daily_state'] is not None:
                daily_df = strategy_results['daily_state'].copy()
                if not daily_df.empty:
                    daily_df['strategy'] = strategy

                    # Check for required columns
                    required_cols = ['date', 'inventory', 'price', 'cumulative_storage_cost']
                    missing_cols = [col for col in required_cols if col not in daily_df.columns]

                    if missing_cols:
                        print(f"⚠️  Strategy '{strategy}' missing columns: {missing_cols}")
                        print(f"   Available columns: {list(daily_df.columns)}")
                        print(f"   Skipping this strategy for multi-granularity analysis")
                        continue

                    # Calculate sales from inventory changes (decrease = sale)
                    daily_df = daily_df.sort_values('date').reset_index(drop=True)
                    daily_df['inventory_change'] = daily_df['inventory'].diff().fillna(0)
                    daily_df['quantity_sold'] = -daily_df['inventory_change'].clip(upper=0)  # Negative change = sale

                    # Calculate revenue from sales (quantity sold * price on sale day)
                    daily_df['revenue'] = daily_df['quantity_sold'] * daily_df['price']
                    daily_df['cumulative_revenue'] = daily_df['revenue'].cumsum()

                    # Net earnings = cumulative revenue - cumulative storage costs
                    daily_df['net_earnings'] = daily_df['cumulative_revenue'] - daily_df['cumulative_storage_cost']

                    all_daily_data.append(daily_df)

        if not all_daily_data:
            print(f"❌ No daily_state data found in pickle file")
            return {'error': 'No daily_state data in pickle'}

        # Combine all strategies
        detailed_df = pd.concat(all_daily_data, ignore_index=True)
        print(f"  Converted {len(detailed_df)} daily observations across {len(results_dict)} strategies")

        results = {}

        for gran in granularities:
            if verbose:
                print(f"\n{'-' * 80}")
                print(f"GRANULARITY: {gran.upper()}")
                print(f"{'-' * 80}")

            # Aggregate to this granularity
            period_df = aggregate_results_by_period(detailed_df, granularity=gran)

            if gran == 'year':
                # Use standard paired t-test for annual
                test_result = test_strategy_vs_baseline(
                    strategy_name=strategy_name,
                    baseline_name=baseline_name,
                    year_df=period_df.rename(columns={'period': 'year'}),
                    verbose=verbose
                )
            else:
                # Use clustered SE for finer granularities
                test_result = test_with_clustered_se(
                    strategy_name=strategy_name,
                    baseline_name=baseline_name,
                    period_df=period_df,
                    cluster_var='year',
                    verbose=verbose
                )

            results[gran] = test_result

        # Compare across granularities
        if verbose:
            print(f"\n{'=' * 80}")
            print("COMPARISON ACROSS GRANULARITIES")
            print(f"{'=' * 80}")
            print(f"\n{'Granularity':<12} {'n':<6} {'Mean Diff':<15} {'p-value':<10} {'Significant'}")
            print(f"{'-' * 60}")

            for gran in granularities:
                res = results[gran]
                if 'error' not in res:
                    n = res.get('n_years', res.get('n_periods', 'N/A'))
                    diff = res['mean_difference']
                    p = res['p_value']
                    sig = "✓" if p < 0.05 else "✗"
                    print(f"{gran:<12} {n:<6} ${diff:>12,.0f} {p:>9.4f}  {sig}")

        return {
            'strategy': strategy_name,
            'baseline': baseline_name,
            'results_by_granularity': results,
            'interpretation': self._interpret_multi_granularity(results)
        }

    def _interpret_multi_granularity(self, results: Dict[str, Any]) -> str:
        """Interpret multi-granularity results"""
        significant_at = []

        for gran, res in results.items():
            if 'error' not in res and res.get('p_value', 1.0) < 0.05:
                significant_at.append(gran)

        if len(significant_at) == 0:
            return "No significant difference at any granularity"
        elif len(significant_at) == len(results):
            return f"Significant at ALL granularities ({', '.join(significant_at)}) - robust result"
        else:
            return f"Significant at: {', '.join(significant_at)}"

    def run_full_analysis(
        self,
        commodity: str,
        model_version: str,
        primary_baseline: str = "Immediate Sale",
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Run complete statistical analysis for a commodity-model combination

        Args:
            commodity: Commodity name
            model_version: Model version
            primary_baseline: Baseline strategy to compare against
            verbose: Print detailed results

        Returns:
            Dict with all statistical test results
        """
        if verbose:
            print("\n" + "=" * 80)
            print(f"STATISTICAL ANALYSIS: {commodity.upper()} - {model_version}")
            print("=" * 80)

        # Load data
        year_df = self.load_year_by_year_results(commodity, model_version)

        # Validate data quality BEFORE running tests
        if verbose:
            print(f"\n{'=' * 80}")
            print("DATA VALIDATION")
            print("=" * 80)

        validation = validate_backtest_data(year_df)

        if verbose:
            for check_name, passed in validation['checks'].items():
                status = "✓" if passed else "✗"
                print(f"  {status} {check_name}")

            if validation['warnings']:
                print(f"\n⚠️  Warnings:")
                for warning in validation['warnings']:
                    print(f"     - {warning}")

            if not validation['passed']:
                print(f"\n⚠️  Data validation failed - results may be unreliable!")
            else:
                print(f"\n✓ Data validation passed")

        # Get all strategies
        strategies = year_df['strategy'].unique().tolist()

        # Identify prediction strategies
        prediction_strategies = [
            s for s in strategies if any([
                'Predictive' in s,
                s in ['Consensus', 'Expected Value', 'Risk-Adjusted', 'RollingHorizonMPC']
            ])
        ]

        baseline_strategies = [s for s in strategies if s not in prediction_strategies]

        if verbose:
            print(f"\n✓ Found {len(strategies)} strategies:")
            print(f"  • {len(baseline_strategies)} baselines: {baseline_strategies}")
            print(f"  • {len(prediction_strategies)} prediction-based: {prediction_strategies}")
            print(f"\nPrimary baseline: {primary_baseline}")

        results = {
            'commodity': commodity,
            'model_version': model_version,
            'primary_baseline': primary_baseline,
            'n_strategies': len(strategies),
            'n_years': len(year_df['year'].unique()),
            'years': sorted(year_df['year'].unique().tolist()),
            'strategy_vs_baseline_tests': [],
            'matched_pair_tests': [],
            'best_prediction_analysis': None
        }

        # Test each prediction strategy vs primary baseline
        if verbose:
            print(f"\n{'=' * 80}")
            print(f"PREDICTION STRATEGIES vs {primary_baseline.upper()}")
            print("=" * 80)

        for strategy in prediction_strategies:
            test_result = test_strategy_vs_baseline(
                strategy_name=strategy,
                baseline_name=primary_baseline,
                year_df=year_df,
                verbose=verbose
            )
            results['strategy_vs_baseline_tests'].append(test_result)

        # Test matched pairs (forecast integration benefit)
        matched_pairs = [
            ('Price Threshold Predictive', 'Price Threshold'),
            ('Moving Average Predictive', 'Moving Average')
        ]

        if verbose:
            print(f"\n{'=' * 80}")
            print("MATCHED PAIR TESTS (Forecast Integration Benefit)")
            print("=" * 80)

        for pred_strategy, base_strategy in matched_pairs:
            if pred_strategy in strategies and base_strategy in strategies:
                test_result = test_strategy_vs_baseline(
                    strategy_name=pred_strategy,
                    baseline_name=base_strategy,
                    year_df=year_df,
                    verbose=verbose
                )
                results['matched_pair_tests'].append(test_result)

        # Apply multiple testing correction (critical for rigor)
        if verbose:
            print(f"\n{'=' * 80}")
            print("MULTIPLE TESTING CORRECTION")
            print("=" * 80)

        mtest_correction = apply_multiple_testing_correction(
            results['strategy_vs_baseline_tests'],
            method='holm',
            alpha=0.05
        )
        results['multiple_testing_correction'] = mtest_correction

        if verbose:
            print(f"  Method: {mtest_correction['method'].upper()}")
            print(f"  Family-wise error rate (α): {mtest_correction['alpha']}")
            print(f"  Number of tests: {mtest_correction['n_tests']}")
            print(f"  Significant (raw): {mtest_correction['n_significant_raw']}")
            print(f"  Significant (adjusted): {mtest_correction['n_significant_adjusted']}")
            if mtest_correction['n_lost_significance'] > 0:
                print(f"  ⚠️  {mtest_correction['n_lost_significance']} tests lost significance after correction")
            else:
                print(f"  ✓ All significant tests remain significant after correction")

            print(f"\n  Corrected Results:")
            for res in mtest_correction['corrected_results']:
                status = "✓" if res['significant_adjusted'] else "✗"
                lost = " (LOST)" if res['lost_significance'] else ""
                print(f"    {status} {res['strategy']}: p_raw={res['p_value_raw']:.4f} → "
                      f"p_adj={res['p_value_adjusted']:.4f}{lost}")

        # Identify best prediction strategy and analyze it
        if results['strategy_vs_baseline_tests']:
            best_pred = max(
                results['strategy_vs_baseline_tests'],
                key=lambda x: x.get('mean_difference', float('-inf'))
            )
            results['best_prediction_analysis'] = best_pred

            if verbose:
                print(f"\n{'=' * 80}")
                print("BEST PREDICTION STRATEGY")
                print("=" * 80)
                self._print_detailed_analysis(best_pred)

            # Run multi-granularity analysis on best strategy
            # This tests at quarterly (n=44) and monthly (n=132) levels
            # to leverage more observations while accounting for within-year correlation
            try:
                multi_gran_results = self.run_multi_granularity_analysis(
                    commodity=commodity,
                    model_version=model_version,
                    strategy_name=best_pred['strategy'],
                    baseline_name=primary_baseline,
                    granularities=['year', 'quarter', 'month'],
                    verbose=verbose
                )
                results['multi_granularity_analysis'] = multi_gran_results
            except Exception as e:
                if verbose:
                    print(f"\n⚠️  Multi-granularity analysis failed: {str(e)}")
                    import traceback
                    traceback.print_exc()
                results['multi_granularity_analysis'] = {'error': str(e)}

        return results

    def _print_detailed_analysis(self, test_result: Dict) -> None:
        """Print detailed analysis of a test result"""
        print(f"\n🏆 {test_result['strategy']} vs {test_result['baseline']}")
        print(f"\nSample Size: {test_result['n_years']} years ({test_result['years'][0]}-{test_result['years'][-1]})")

        print(f"\nDescriptive Statistics:")
        print(f"  Mean earnings ({test_result['strategy']}): ${test_result['mean_strategy']:,.0f}")
        print(f"  Mean earnings ({test_result['baseline']}): ${test_result['mean_baseline']:,.0f}")
        print(f"  Mean difference: ${test_result['mean_difference']:,.0f}")
        print(f"  Std of differences: ${test_result['std_difference']:,.0f}")

        print(f"\nPaired t-test:")
        print(f"  t-statistic: {test_result['t_statistic']:.4f}")
        print(f"  p-value: {test_result['p_value']:.4f}", end="")
        if test_result['significant_05']:
            print(" ✓ SIGNIFICANT at α=0.05")
        elif test_result['p_value'] < 0.10:
            print(" ⚠️  Marginally significant (p<0.10)")
        else:
            print(" ✗ Not significant")

        print(f"\nEffect Size:")
        print(f"  Cohen's d: {test_result['cohens_d']:.4f} ({test_result['effect_interpretation']})")

        print(f"\n95% Confidence Interval:")
        print(f"  [{test_result['ci_95_lower']:,.0f}, {test_result['ci_95_upper']:,.0f}]")
        if test_result['ci_includes_zero']:
            print("  ⚠️  Includes zero (cannot rule out no effect)")
        else:
            print("  ✓ Does not include zero")

        print(f"\nSign Test (Non-Parametric):")
        print(f"  Years positive: {test_result['n_years_positive']}/{test_result['n_years']}")
        print(f"  Years negative: {test_result['n_years_negative']}/{test_result['n_years']}")
        print(f"  p-value: {test_result['sign_test_p_value']:.4f}", end="")
        if test_result['sign_test_significant']:
            print(" ✓ SIGNIFICANT")
        else:
            print(" ✗ Not significant")

        print(f"\nPermutation Test (Random Chance):")
        print(f"  {test_result['permutation_explanation']}")
        print(f"  p-value: {test_result['permutation_p_value']:.4f}", end="")
        if test_result['permutation_significant']:
            print(" ✓ SIGNIFICANT (NOT random chance)")
        else:
            print(" ✗ Could be random chance")

        print(f"\nAssumption Checks:")
        print(f"  Normality (Shapiro-Wilk): {test_result['normality_interpretation']}")
        if test_result['normality_shapiro_p'] is not None:
            print(f"    p-value: {test_result['normality_shapiro_p']:.4f}")
        print(f"    Skewness: {test_result['normality_skewness']:.3f}")
        print(f"    Kurtosis: {test_result['normality_kurtosis']:.3f}")
        print(f"  Recommendation: {test_result['normality_recommendation']}")

    def save_results(
        self,
        results: Dict[str, Any],
        save_to_delta: bool = True
    ) -> Optional[str]:
        """
        Save statistical test results to Delta table

        Args:
            results: Output from run_full_analysis()
            save_to_delta: If True, save to Delta table

        Returns:
            Table name if saved, None otherwise
        """
        if not save_to_delta or self.spark is None:
            return None

        commodity = results['commodity']
        model_version = results['model_version']

        # Flatten all test results to DataFrame
        all_tests = []

        # Strategy vs baseline tests
        for test in results['strategy_vs_baseline_tests']:
            test_copy = test.copy()
            test_copy['test_type'] = 'strategy_vs_baseline'
            test_copy['years_list'] = str(test_copy['years'])  # Convert list to string for Delta
            all_tests.append(test_copy)

        # Matched pair tests
        for test in results['matched_pair_tests']:
            test_copy = test.copy()
            test_copy['test_type'] = 'matched_pair'
            test_copy['years_list'] = str(test_copy['years'])
            all_tests.append(test_copy)

        if not all_tests:
            print("⚠️  No test results to save")
            return None

        stats_df = pd.DataFrame(all_tests)

        # Add metadata
        stats_df['commodity'] = commodity
        stats_df['model_version'] = model_version
        stats_df['analysis_timestamp'] = pd.Timestamp.now()

        # Remove list column (converted to string above)
        if 'years' in stats_df.columns:
            stats_df = stats_df.drop(columns=['years'])

        # Save to Delta
        table_name = f"commodity.trading_agent.statistical_tests_{commodity}_{model_version}"

        try:
            self.spark.createDataFrame(stats_df).write \
                .mode("overwrite") \
                .option("overwriteSchema", "true") \
                .saveAsTable(table_name)

            print(f"\n✓ Saved statistical tests to: {table_name}")
            return table_name

        except Exception as e:
            print(f"\n❌ Error saving to Delta: {e}")
            return None


def aggregate_results_by_period(
    detailed_df: pd.DataFrame,
    granularity: str = 'year'
) -> pd.DataFrame:
    """
    Aggregate trading results by different time periods

    Args:
        detailed_df: DataFrame with columns [date, strategy, net_earnings, ...]
        granularity: 'year', 'quarter', or 'month'

    Returns:
        DataFrame aggregated by period with columns [period, year, strategy, net_earnings]
    """
    df = detailed_df.copy()

    # Ensure date column is datetime
    if 'date' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['date']):
        df['date'] = pd.to_datetime(df['date'])

    # Create period column
    if granularity == 'year':
        df['period'] = df['date'].dt.year
        df['year'] = df['date'].dt.year
    elif granularity == 'quarter':
        df['period'] = df['date'].dt.to_period('Q').astype(str)
        df['year'] = df['date'].dt.year
    elif granularity == 'month':
        df['period'] = df['date'].dt.to_period('M').astype(str)
        df['year'] = df['date'].dt.year
    else:
        raise ValueError(f"Unknown granularity: {granularity}")

    # Aggregate by period and strategy
    # For net_earnings (cumulative), take the last value in the period
    # which represents the total earnings up to that point
    agg_df = df.sort_values('date').groupby(['period', 'year', 'strategy']).agg({
        'net_earnings': 'last'  # Take final value for the period
    }).reset_index()

    return agg_df


def test_with_clustered_se(
    strategy_name: str,
    baseline_name: str,
    period_df: pd.DataFrame,
    cluster_var: str = 'year',
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Test strategy vs baseline with clustered standard errors

    Accounts for within-cluster correlation (e.g., months within same year
    are correlated). Uses robust covariance matrix.

    Args:
        strategy_name: Strategy to test
        baseline_name: Baseline to compare against
        period_df: DataFrame with [period, year, strategy, net_earnings]
        cluster_var: Variable to cluster by (typically 'year')
        verbose: Print results

    Returns:
        Dict with test results including clustered SE
    """
    # Get strategy and baseline earnings
    strategy_earnings = period_df[period_df['strategy'] == strategy_name].sort_values('period')
    baseline_earnings = period_df[period_df['strategy'] == baseline_name].sort_values('period')

    # Find common periods
    common_periods = set(strategy_earnings['period']).intersection(set(baseline_earnings['period']))

    if len(common_periods) < 3:
        return {
            'error': f'Insufficient overlapping periods: {len(common_periods)}',
            'strategy': strategy_name,
            'baseline': baseline_name,
            'n_periods': len(common_periods)
        }

    # Filter to common periods and align
    strategy_data = strategy_earnings[strategy_earnings['period'].isin(common_periods)].set_index('period')
    baseline_data = baseline_earnings[baseline_earnings['period'].isin(common_periods)].set_index('period')

    # Create regression dataset
    reg_df = pd.DataFrame({
        'earnings': pd.concat([strategy_data['net_earnings'], baseline_data['net_earnings']]),
        'is_strategy': [1] * len(strategy_data) + [0] * len(baseline_data),
        cluster_var: pd.concat([strategy_data[cluster_var], baseline_data[cluster_var]])
    })

    # Run OLS regression: earnings ~ is_strategy
    # Coefficient on is_strategy = mean difference
    model = OLS(reg_df['earnings'],
                pd.DataFrame({'const': 1, 'strategy': reg_df['is_strategy']}))

    # Fit with clustered standard errors
    results = model.fit(cov_type='cluster',
                       cov_kwds={'groups': reg_df[cluster_var].values})

    # Extract results
    coef = results.params['strategy']
    se_clustered = results.bse['strategy']
    t_stat = results.tvalues['strategy']
    p_value = results.pvalues['strategy']
    ci = results.conf_int(alpha=0.05).loc['strategy']

    # Compute naive SE for comparison
    differences = strategy_data['net_earnings'].values - baseline_data['net_earnings'].values
    se_naive = np.std(differences, ddof=1) / np.sqrt(len(differences))

    # Number of clusters
    n_clusters = reg_df[cluster_var].nunique()

    result = {
        'strategy': strategy_name,
        'baseline': baseline_name,
        'n_periods': len(common_periods),
        'n_clusters': n_clusters,
        'periods': sorted(common_periods),

        # Point estimate
        'mean_difference': float(coef),

        # Standard errors
        'se_clustered': float(se_clustered),
        'se_naive': float(se_naive),
        'se_inflation_factor': float(se_clustered / se_naive) if se_naive > 0 else np.nan,

        # Test statistics
        't_statistic': float(t_stat),
        'p_value': float(p_value),
        'significant_05': bool(p_value < 0.05),

        # Confidence interval (clustered)
        'ci_95_lower': float(ci[0]),
        'ci_95_upper': float(ci[1]),
        'ci_includes_zero': bool(ci[0] <= 0 <= ci[1])
    }

    if verbose:
        print(f"\n{strategy_name} vs {baseline_name}:")
        print(f"  n={len(common_periods)} periods, {n_clusters} clusters ({cluster_var})")
        print(f"  Δ=${coef:,.0f}, SE_clustered=${se_clustered:,.0f}, p={p_value:.4f}", end="")
        if p_value < 0.05:
            print(" ✓")
        else:
            print(" ✗")
        print(f"  SE inflation: {se_clustered/se_naive:.2f}x (clustering effect)")

    return result


def test_strategy_vs_baseline(
    strategy_name: str,
    baseline_name: str,
    year_df: pd.DataFrame,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Test if strategy significantly beats baseline using paired t-test

    This is a paired test because we compare the SAME years for both strategies,
    controlling for year-to-year market variation.

    Args:
        strategy_name: Strategy to test (e.g., "Rolling Horizon MPC")
        baseline_name: Baseline to compare against (e.g., "Immediate Sale")
        year_df: DataFrame with columns [year, strategy, net_earnings]
        verbose: Print results

    Returns:
        Dict with comprehensive statistical test results
    """
    # Get year-by-year earnings for each strategy
    strategy_years = year_df[year_df['strategy'] == strategy_name].set_index('year')['net_earnings']
    baseline_years = year_df[year_df['strategy'] == baseline_name].set_index('year')['net_earnings']

    # Find overlapping years
    common_years = strategy_years.index.intersection(baseline_years.index)

    if len(common_years) < 3:
        result = {
            'error': f'Insufficient overlapping years: {len(common_years)}',
            'strategy': strategy_name,
            'baseline': baseline_name,
            'n_years': len(common_years)
        }
        if verbose:
            print(f"\n⚠️  {strategy_name} vs {baseline_name}: Only {len(common_years)} overlapping years (need ≥3)")
        return result

    # Align data by year (preserves pairing)
    strategy_values = strategy_years.loc[common_years].values
    baseline_values = baseline_years.loc[common_years].values
    differences = strategy_values - baseline_values

    # Calculate percentage improvements (year by year and mean)
    pct_improvements = ((strategy_values - baseline_values) / np.abs(baseline_values)) * 100
    mean_pct_improvement = float(np.mean(pct_improvements))

    # Year-by-year breakdown
    year_by_year = []
    for year, strat_val, base_val, diff, pct in zip(
        sorted(common_years),
        strategy_years.loc[sorted(common_years)].values,
        baseline_years.loc[sorted(common_years)].values,
        strategy_years.loc[sorted(common_years)].values - baseline_years.loc[sorted(common_years)].values,
        pct_improvements[np.argsort(common_years)]
    ):
        year_by_year.append({
            'year': int(year),
            'strategy_earnings': float(strat_val),
            'baseline_earnings': float(base_val),
            'difference': float(diff),
            'pct_improvement': float(pct)
        })

    # Check normality assumption for t-test
    normality = check_normality_assumptions(differences)

    # Paired t-test
    t_stat, p_value = stats.ttest_rel(strategy_values, baseline_values)

    # Effect size (Cohen's d for paired data)
    mean_diff = np.mean(differences)
    std_diff = np.std(differences, ddof=1)
    cohens_d = mean_diff / std_diff if std_diff > 0 else 0

    # 95% Confidence interval for mean difference
    ci = stats.t.interval(
        confidence=0.95,
        df=len(differences) - 1,
        loc=mean_diff,
        scale=stats.sem(differences)
    )

    # Sign test (non-parametric alternative)
    n_positive = np.sum(differences > 0)
    n_total = len(differences)
    # Binomial test: H0 = 50% probability of being positive
    # Use binomtest (binom_test was deprecated)
    sign_p_value = stats.binomtest(n_positive, n_total, 0.5, alternative='greater').pvalue

    # Bootstrap confidence interval for robustness
    boot_ci = bootstrap_confidence_interval(strategy_values, baseline_values, n_bootstrap=10000)

    # Permutation test (easy-to-explain random chance test)
    perm_result = permutation_test(strategy_values, baseline_values, n_permutations=10000)

    result = {
        'strategy': strategy_name,
        'baseline': baseline_name,
        'n_years': len(common_years),
        'years': sorted(common_years.tolist()),

        # Descriptive statistics
        'mean_strategy': float(np.mean(strategy_values)),
        'mean_baseline': float(np.mean(baseline_values)),
        'mean_difference': float(mean_diff),
        'std_difference': float(std_diff),

        # Percentage improvements
        'mean_pct_improvement': mean_pct_improvement,
        'year_by_year': year_by_year,

        # Paired t-test
        't_statistic': float(t_stat),
        'p_value': float(p_value),
        'significant_05': bool(p_value < 0.05),
        'significant_01': bool(p_value < 0.01),

        # Effect size
        'cohens_d': float(cohens_d),
        'effect_interpretation': _interpret_cohens_d(cohens_d),

        # Parametric confidence interval
        'ci_95_lower': float(ci[0]),
        'ci_95_upper': float(ci[1]),
        'ci_includes_zero': bool(ci[0] <= 0 <= ci[1]),

        # Bootstrap confidence interval
        'bootstrap_ci_95_lower': float(boot_ci[0]),
        'bootstrap_ci_95_upper': float(boot_ci[1]),

        # Sign test
        'n_years_positive': int(n_positive),
        'n_years_negative': int(n_total - n_positive),
        'sign_test_p_value': float(sign_p_value),
        'sign_test_significant': bool(sign_p_value < 0.05),

        # Permutation test (easy-to-explain random chance test)
        'permutation_p_value': perm_result['p_value'],
        'permutation_n_extreme': perm_result['n_extreme'],
        'permutation_explanation': perm_result['explanation'],
        'permutation_significant': bool(perm_result['p_value'] < 0.05),

        # Normality assumption check
        'normality_shapiro_p': normality['shapiro_p_value'],
        'normality_is_normal': normality['is_normal'],
        'normality_skewness': normality['skewness'],
        'normality_kurtosis': normality['kurtosis'],
        'normality_interpretation': normality['interpretation'],
        'normality_recommendation': normality['recommendation']
    }

    if verbose:
        print(f"\n{strategy_name} vs {baseline_name}:")
        print(f"  n={len(common_years)} years ({min(common_years)}-{max(common_years)})")
        print(f"  Mean improvement: ${mean_diff:,.0f} ({mean_pct_improvement:+.2f}%)")
        print(f"  p-value: {p_value:.4f}", end="")
        if p_value < 0.05:
            print(" ✓ SIGNIFICANT")
        elif p_value < 0.10:
            print(" ⚠️ MARGINAL")
        else:
            print(" ✗ NOT SIGNIFICANT")

        # Year-by-year breakdown
        print(f"\n  Year-by-year:")
        print(f"    {'Year':<6} {'Strategy':<12} {'Baseline':<12} {'Difference':<12} {'% Improvement':<15}")
        print(f"    {'-' * 57}")
        for yby in year_by_year:
            print(f"    {yby['year']:<6} "
                  f"${yby['strategy_earnings']:>10,.0f} "
                  f"${yby['baseline_earnings']:>10,.0f} "
                  f"${yby['difference']:>10,.0f} "
                  f"{yby['pct_improvement']:>13.2f}%")

    return result


def permutation_test(
    strategy_earnings: np.ndarray,
    baseline_earnings: np.ndarray,
    n_permutations: int = 10000
) -> Dict[str, Any]:
    """
    Permutation test: Could we get these results by random chance?

    EASY TO EXPLAIN: "If strategy labels were meaningless, shuffling them
    randomly shouldn't matter. We shuffled 10,000 times - how many random
    shuffles beat the real result?"

    This directly tests the null hypothesis that strategy assignment is random.

    Args:
        strategy_earnings: Array of strategy earnings by year
        baseline_earnings: Array of baseline earnings by year
        n_permutations: Number of random shuffles

    Returns:
        Dict with permutation test results
    """
    # Observed difference
    observed_diff = np.mean(strategy_earnings) - np.mean(baseline_earnings)

    # Combine all values
    all_values = np.concatenate([strategy_earnings, baseline_earnings])
    n_strategy = len(strategy_earnings)

    # Generate null distribution by random shuffling
    random_diffs = []
    for _ in range(n_permutations):
        # Shuffle and split
        shuffled = np.random.permutation(all_values)
        fake_strategy = shuffled[:n_strategy]
        fake_baseline = shuffled[n_strategy:]
        random_diffs.append(np.mean(fake_strategy) - np.mean(fake_baseline))

    random_diffs = np.array(random_diffs)

    # Two-tailed p-value: how many random shuffles matched or beat observed?
    p_value = np.mean(np.abs(random_diffs) >= np.abs(observed_diff))

    # Count extreme values
    n_extreme = np.sum(np.abs(random_diffs) >= np.abs(observed_diff))

    return {
        'observed_difference': float(observed_diff),
        'p_value': float(p_value),
        'n_permutations': n_permutations,
        'n_extreme': int(n_extreme),
        'random_diffs': random_diffs,  # For visualization
        'explanation': f'Out of {n_permutations} random shuffles, only {n_extreme} '
                      f'matched or beat observed result ({p_value*100:.2f}%)'
    }


def check_normality_assumptions(differences: np.ndarray) -> Dict[str, Any]:
    """
    Check if paired differences satisfy normality assumption for t-test

    Uses Shapiro-Wilk test (best for n<50) and reports:
    - Normality test result
    - Skewness and kurtosis
    - Recommendation on which test to trust

    Args:
        differences: Array of paired differences (strategy - baseline)

    Returns:
        Dict with normality test results and interpretation
    """
    n = len(differences)

    # Shapiro-Wilk test (H0: data is normally distributed)
    if n >= 3:
        shapiro_stat, shapiro_p = stats.shapiro(differences)
    else:
        shapiro_stat, shapiro_p = np.nan, np.nan

    # Descriptive statistics
    skewness = stats.skew(differences)
    kurtosis = stats.kurtosis(differences)  # Excess kurtosis (normal = 0)

    # Interpretation
    is_normal = shapiro_p > 0.05 if not np.isnan(shapiro_p) else None

    if is_normal is None:
        interpretation = "Sample too small for normality test (n<3)"
        recommendation = "Use non-parametric tests only"
    elif is_normal:
        interpretation = "Differences appear normally distributed"
        recommendation = "t-test is appropriate"
    else:
        interpretation = f"Differences may not be normal (Shapiro-Wilk p={shapiro_p:.4f})"
        if abs(skewness) > 1 or abs(kurtosis) > 1:
            recommendation = "Trust non-parametric tests (sign test, permutation) over t-test"
        else:
            recommendation = "t-test likely robust despite slight non-normality"

    return {
        'n': n,
        'shapiro_statistic': float(shapiro_stat) if not np.isnan(shapiro_stat) else None,
        'shapiro_p_value': float(shapiro_p) if not np.isnan(shapiro_p) else None,
        'is_normal': is_normal,
        'skewness': float(skewness),
        'kurtosis': float(kurtosis),
        'interpretation': interpretation,
        'recommendation': recommendation
    }


def apply_multiple_testing_correction(
    test_results: List[Dict[str, Any]],
    method: str = 'holm',
    alpha: float = 0.05
) -> Dict[str, Any]:
    """
    Apply multiple testing correction to family of hypothesis tests

    CRITICAL for avoiding Type I errors when testing multiple strategies.

    Methods available:
    - 'bonferroni': Most conservative, controls FWER
    - 'holm': Less conservative than Bonferroni, still controls FWER (recommended)
    - 'fdr_bh': Benjamini-Hochberg, controls FDR (false discovery rate)

    Args:
        test_results: List of test result dicts (each must have 'p_value' key)
        method: Correction method
        alpha: Family-wise error rate

    Returns:
        Dict with corrected p-values and significance decisions
    """
    # Extract p-values
    p_values = np.array([r.get('p_value', 1.0) for r in test_results])
    strategy_names = [r.get('strategy', f'Test {i}') for i, r in enumerate(test_results)]

    if len(p_values) == 0:
        return {
            'method': method,
            'alpha': alpha,
            'n_tests': 0,
            'corrected_results': []
        }

    # Apply correction
    reject, p_adjusted, alphacSidak, alphacBonf = multipletests(
        p_values,
        alpha=alpha,
        method=method
    )

    # Build corrected results
    corrected_results = []
    for i, (name, p_raw, p_adj, sig) in enumerate(zip(strategy_names, p_values, p_adjusted, reject)):
        corrected_results.append({
            'strategy': name,
            'p_value_raw': float(p_raw),
            'p_value_adjusted': float(p_adj),
            'significant_raw': bool(p_raw < alpha),
            'significant_adjusted': bool(sig),
            'lost_significance': bool(p_raw < alpha and not sig)
        })

    # Summary statistics
    n_significant_raw = sum(p_values < alpha)
    n_significant_adjusted = sum(reject)
    n_lost = sum((p_values < alpha) & (~reject))

    return {
        'method': method,
        'alpha': alpha,
        'n_tests': len(p_values),
        'n_significant_raw': int(n_significant_raw),
        'n_significant_adjusted': int(n_significant_adjusted),
        'n_lost_significance': int(n_lost),
        'corrected_results': corrected_results,
        'interpretation': f"After {method} correction: {n_significant_adjusted}/{len(p_values)} "
                         f"tests remain significant (lost {n_lost} due to multiple testing)"
    }


def validate_backtest_data(year_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Data validation checks before running statistical tests

    Checks for:
    - Missing values
    - Duplicate year-strategy combinations
    - Complete coverage (all strategies in all years)
    - Reasonable earnings values
    - Outlier years

    Args:
        year_df: DataFrame with columns [year, strategy, net_earnings]

    Returns:
        Dict with validation results and warnings
    """
    validation = {
        'passed': True,
        'warnings': [],
        'checks': {}
    }

    # Check for nulls
    null_count = year_df['net_earnings'].isna().sum()
    validation['checks']['no_nulls'] = null_count == 0
    if null_count > 0:
        validation['warnings'].append(f'{null_count} null values in net_earnings')
        validation['passed'] = False

    # Check for duplicates
    duplicates = year_df.duplicated(subset=['year', 'strategy']).sum()
    validation['checks']['no_duplicates'] = duplicates == 0
    if duplicates > 0:
        validation['warnings'].append(f'{duplicates} duplicate year-strategy combinations')
        validation['passed'] = False

    # Check complete coverage (all strategies in all years)
    years = year_df['year'].unique()
    strategies = year_df['strategy'].unique()
    expected_combinations = len(years) * len(strategies)
    actual_combinations = len(year_df)
    validation['checks']['complete_coverage'] = expected_combinations == actual_combinations
    if expected_combinations != actual_combinations:
        missing = expected_combinations - actual_combinations
        validation['warnings'].append(
            f'Incomplete coverage: {missing} missing year-strategy combinations '
            f'(expected {expected_combinations}, got {actual_combinations})'
        )

    # Check for reasonable values (not $1B from coffee or negative $1M)
    min_earnings = year_df['net_earnings'].min()
    max_earnings = year_df['net_earnings'].max()
    validation['checks']['reasonable_min'] = min_earnings > -1_000_000
    validation['checks']['reasonable_max'] = max_earnings < 10_000_000

    if min_earnings <= -1_000_000:
        validation['warnings'].append(f'Extreme negative earnings: ${min_earnings:,.0f}')
    if max_earnings >= 10_000_000:
        validation['warnings'].append(f'Extreme positive earnings: ${max_earnings:,.0f}')

    # Detect outlier years (years with unusual average earnings)
    avg_by_year = year_df.groupby('year')['net_earnings'].mean()
    if len(avg_by_year) >= 3:
        z_scores = (avg_by_year - avg_by_year.mean()) / avg_by_year.std()
        outliers = avg_by_year[np.abs(z_scores) > 2]
        validation['checks']['no_outlier_years'] = len(outliers) == 0
        validation['outlier_years'] = outliers.index.tolist() if len(outliers) > 0 else []

        if len(outliers) > 0:
            validation['warnings'].append(
                f'{len(outliers)} outlier years detected: {outliers.index.tolist()}'
            )

    return validation


def bootstrap_confidence_interval(
    strategy_earnings: np.ndarray,
    baseline_earnings: np.ndarray,
    n_bootstrap: int = 10000,
    confidence: float = 0.95
) -> Tuple[float, float]:
    """
    Bootstrap confidence interval for difference in means

    Non-parametric alternative to t-test confidence interval.
    Doesn't assume normal distribution of differences.

    Args:
        strategy_earnings: Array of strategy earnings by year
        baseline_earnings: Array of baseline earnings by year (same length)
        n_bootstrap: Number of bootstrap samples
        confidence: Confidence level (0.95 = 95%)

    Returns:
        (lower_bound, upper_bound)
    """
    n = len(strategy_earnings)
    differences = []

    for _ in range(n_bootstrap):
        # Resample with replacement (preserves pairing)
        indices = np.random.choice(n, size=n, replace=True)
        boot_diff = np.mean(strategy_earnings[indices] - baseline_earnings[indices])
        differences.append(boot_diff)

    alpha = 1 - confidence
    lower = np.percentile(differences, alpha/2 * 100)
    upper = np.percentile(differences, (1 - alpha/2) * 100)

    return (lower, upper)


def run_full_statistical_analysis(
    spark,
    commodity: str,
    model_version: str,
    primary_baseline: str = "Immediate Sale",
    verbose: bool = True,
    save_to_delta: bool = True
) -> Dict[str, Any]:
    """
    Convenience function: Run complete statistical analysis

    Args:
        spark: Spark session
        commodity: Commodity name
        model_version: Model version
        primary_baseline: Baseline strategy name
        verbose: Print detailed results
        save_to_delta: Save results to Delta table

    Returns:
        Dict with all statistical test results
    """
    analyzer = StatisticalAnalyzer(spark=spark)
    results = analyzer.run_full_analysis(
        commodity=commodity,
        model_version=model_version,
        primary_baseline=primary_baseline,
        verbose=verbose
    )

    if save_to_delta:
        analyzer.save_results(results, save_to_delta=True)

    return results


def _interpret_cohens_d(d: float) -> str:
    """
    Interpret Cohen's d effect size

    Standard interpretation:
    - |d| < 0.2: negligible
    - 0.2 ≤ |d| < 0.5: small
    - 0.5 ≤ |d| < 0.8: medium
    - |d| ≥ 0.8: large
    """
    abs_d = abs(d)
    if abs_d < 0.2:
        return "negligible"
    elif abs_d < 0.5:
        return "small"
    elif abs_d < 0.8:
        return "medium"
    else:
        return "large"
