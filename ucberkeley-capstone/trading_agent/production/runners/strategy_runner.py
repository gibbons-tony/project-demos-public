"""
Strategy Runner Module
Initializes strategies and executes backtests
"""

import pandas as pd
from typing import Dict, List, Tuple, Any

# Import production infrastructure
from production.strategies import (
    ImmediateSaleStrategy,
    EqualBatchStrategy,
    PriceThresholdStrategy,
    MovingAverageStrategy,
    PriceThresholdPredictive,
    MovingAveragePredictive,
    ExpectedValueStrategy,
    ConsensusStrategy,
    RiskAdjustedStrategy,
    RollingHorizonMPC
)
from production.core.backtest_engine import (
    BacktestEngine,
    calculate_metrics,
    calculate_metrics_by_year,
    calculate_metrics_by_quarter,
    calculate_metrics_by_month
)


class StrategyRunner:
    """Runs all 10 trading strategies through backtest engine"""

    def __init__(
        self,
        prices: pd.DataFrame,
        prediction_matrices: Dict[Any, Any],
        commodity_config: Dict[str, Any],
        baseline_params: Dict[str, Any],
        prediction_params: Dict[str, Any]
    ):
        """
        Initialize strategy runner

        Args:
            prices: Price DataFrame with columns ['date', 'price']
            prediction_matrices: Dict mapping {timestamp: numpy_array}
            commodity_config: Commodity-specific configuration
            baseline_params: Baseline strategy parameters
            prediction_params: Prediction strategy parameters
        """
        self.prices = prices
        self.prediction_matrices = prediction_matrices
        self.commodity_config = commodity_config
        self.baseline_params = baseline_params
        self.prediction_params = prediction_params

        # Initialize backtest engine
        self.engine = BacktestEngine(
            prices=prices,
            prediction_matrices=prediction_matrices,
            producer_config=commodity_config  # BacktestEngine expects 'producer_config' parameter name
        )

    def initialize_strategies(self) -> Tuple[List, List]:
        """
        Initialize all 10 strategies with COMPLETE optimized parameter dicts.

        Uses parameter unpacking (**params) to pass ALL optimized parameters
        from Optuna through to strategy constructors. Cost parameters
        (storage_cost_pct_per_day, transaction_cost_pct) are injected from
        commodity config for prediction strategies.

        Returns:
            Tuple of (baseline_strategies, prediction_strategies)
        """

        # Helper to add cost parameters from commodity config
        def add_costs(params: dict) -> dict:
            """
            Add commodity-level cost parameters to prediction strategy params.

            Costs come from COMMODITY_CONFIGS. Only add if not already present
            to avoid duplicate keyword argument errors when using default params.
            """
            p = params.copy()
            if 'storage_cost_pct_per_day' not in p:
                p['storage_cost_pct_per_day'] = self.commodity_config['storage_cost_pct_per_day']
            if 'transaction_cost_pct' not in p:
                p['transaction_cost_pct'] = self.commodity_config['transaction_cost_pct']
            return p

        # Baseline strategies - unpack ALL optimized parameters
        # Uses .get() with empty dict fallback for graceful degradation to __init__ defaults
        baselines = [
            ImmediateSaleStrategy(**self.baseline_params.get('immediate_sale', {})),
            EqualBatchStrategy(**self.baseline_params.get('equal_batch', {})),
            PriceThresholdStrategy(**self.baseline_params.get('price_threshold', {})),
            MovingAverageStrategy(**self.baseline_params.get('moving_average', {}))
        ]

        # Prediction strategies - unpack ALL optimized parameters + add costs
        # ALL 107 Optuna-optimized parameters now flow through correctly
        prediction_strategies = [
            ConsensusStrategy(**add_costs(self.prediction_params.get('consensus', {}))),
            ExpectedValueStrategy(**add_costs(self.prediction_params.get('expected_value', {}))),
            RiskAdjustedStrategy(**add_costs(self.prediction_params.get('risk_adjusted', {}))),
            # Matched pairs - use COMPLETE parameter dicts (18-19 params each!)
            PriceThresholdPredictive(**add_costs(self.prediction_params.get('price_threshold_predictive', {}))),
            MovingAveragePredictive(**add_costs(self.prediction_params.get('moving_average_predictive', {}))),
            # Advanced optimization strategy (10th strategy)
            RollingHorizonMPC(**add_costs(self.prediction_params.get('rolling_horizon_mpc', {})))
        ]

        return baselines, prediction_strategies

    def run_all_strategies(
        self,
        commodity: str,
        model_version: str,
        verbose: bool = True
    ) -> Tuple[Dict[str, Any], pd.DataFrame]:
        """
        Run backtest for all strategies

        Args:
            commodity: Commodity name for logging
            model_version: Model version for logging
            verbose: Print progress messages

        Returns:
            Tuple of (results_dict, metrics_df)
            - results_dict: {strategy_name: backtest_results}
            - metrics_df: DataFrame with all strategy metrics
        """
        baselines, prediction_strategies = self.initialize_strategies()
        all_strategies = baselines + prediction_strategies

        if verbose:
            print("\n" + "=" * 80)
            print(f"RUNNING BACKTESTS - {commodity.upper()} - {model_version}")
            print("=" * 80)
            print(f"\n✓ {len(baselines)} baseline strategies")
            print(f"✓ {len(prediction_strategies)} prediction-based strategies")
            print(f"Total: {len(all_strategies)} strategies to test")

        results_dict = {}
        metrics_list = []
        metrics_by_year_dict = {}  # Store year-by-year metrics
        metrics_by_quarter_dict = {}  # Store quarter-by-quarter metrics
        metrics_by_month_dict = {}  # Store month-by-month metrics

        for i, strategy in enumerate(all_strategies, 1):
            if verbose:
                print(f"\n[{i}/{len(all_strategies)}] Running: {strategy.name}...")

            # Run backtest
            results = self.engine.run(strategy)

            # Calculate overall metrics
            metrics = calculate_metrics(results)

            # Calculate multi-granularity metrics
            year_metrics = calculate_metrics_by_year(results)
            quarter_metrics = calculate_metrics_by_quarter(results)
            month_metrics = calculate_metrics_by_month(results)

            # Store results
            results_dict[strategy.name] = results
            metrics_list.append(metrics)
            metrics_by_year_dict[strategy.name] = year_metrics
            metrics_by_quarter_dict[strategy.name] = quarter_metrics
            metrics_by_month_dict[strategy.name] = month_metrics

            if verbose:
                print(f"  Total Revenue:  ${metrics['total_revenue']:,.2f}")
                print(f"  Net Earnings:   ${metrics['net_earnings']:,.2f}")
                print(f"  Avg Sale Price: ${metrics['avg_sale_price']:.2f}")
                print(f"  Total Costs:    ${metrics['total_costs']:,.2f}")
                print(f"  Trades:         {metrics['n_trades']}")

        if verbose:
            print("\n" + "=" * 80)
            print("BACKTESTS COMPLETE")
            print("=" * 80)

        # Create metrics DataFrame
        metrics_df = pd.DataFrame(metrics_list)

        # Add metadata
        baseline_names = [s.name for s in baselines]
        metrics_df['type'] = metrics_df['strategy'].apply(
            lambda x: 'Baseline' if x in baseline_names else 'Prediction'
        )
        metrics_df['commodity'] = commodity
        metrics_df['model_version'] = model_version

        # Sort by net earnings
        metrics_df = metrics_df.sort_values('net_earnings', ascending=False)

        # Create year-by-year DataFrame (flattened from nested dict)
        year_metrics_list = []
        for strategy_name, year_dict in metrics_by_year_dict.items():
            for year, metrics in year_dict.items():
                year_metrics_list.append(metrics)

        metrics_by_year_df = pd.DataFrame(year_metrics_list) if year_metrics_list else pd.DataFrame()

        if not metrics_by_year_df.empty:
            # Add metadata
            metrics_by_year_df['type'] = metrics_by_year_df['strategy'].apply(
                lambda x: 'Baseline' if x in baseline_names else 'Prediction'
            )
            metrics_by_year_df['commodity'] = commodity
            metrics_by_year_df['model_version'] = model_version

        # Create quarter-by-quarter DataFrame
        quarter_metrics_list = []
        for strategy_name, quarter_dict in metrics_by_quarter_dict.items():
            for quarter_key, metrics in quarter_dict.items():
                quarter_metrics_list.append(metrics)

        metrics_by_quarter_df = pd.DataFrame(quarter_metrics_list) if quarter_metrics_list else pd.DataFrame()

        if not metrics_by_quarter_df.empty:
            # Add metadata
            metrics_by_quarter_df['type'] = metrics_by_quarter_df['strategy'].apply(
                lambda x: 'Baseline' if x in baseline_names else 'Prediction'
            )
            metrics_by_quarter_df['commodity'] = commodity
            metrics_by_quarter_df['model_version'] = model_version

        # Create month-by-month DataFrame
        month_metrics_list = []
        for strategy_name, month_dict in metrics_by_month_dict.items():
            for month_key, metrics in month_dict.items():
                month_metrics_list.append(metrics)

        metrics_by_month_df = pd.DataFrame(month_metrics_list) if month_metrics_list else pd.DataFrame()

        if not metrics_by_month_df.empty:
            # Add metadata
            metrics_by_month_df['type'] = metrics_by_month_df['strategy'].apply(
                lambda x: 'Baseline' if x in baseline_names else 'Prediction'
            )
            metrics_by_month_df['commodity'] = commodity
            metrics_by_month_df['model_version'] = model_version

        return results_dict, metrics_df, metrics_by_year_df, metrics_by_quarter_df, metrics_by_month_df

    def analyze_best_performers(
        self,
        metrics_df: pd.DataFrame,
        commodity: str,
        model_version: str,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Identify and analyze best performing strategies

        Args:
            metrics_df: Metrics DataFrame from run_all_strategies
            commodity: Commodity name
            model_version: Model version
            verbose: Print summary

        Returns:
            Dictionary with best performer analysis
        """
        best_baseline = metrics_df[metrics_df['type'] == 'Baseline'].iloc[0]
        best_prediction = metrics_df[metrics_df['type'] == 'Prediction'].iloc[0]
        best_overall = metrics_df.iloc[0]

        # Calculate advantage
        earnings_diff = best_prediction['net_earnings'] - best_baseline['net_earnings']
        pct_diff = (earnings_diff / abs(best_baseline['net_earnings'])) * 100 \
            if best_baseline['net_earnings'] != 0 else 0

        analysis = {
            'best_baseline': best_baseline.to_dict(),
            'best_prediction': best_prediction.to_dict(),
            'best_overall': best_overall.to_dict(),
            'earnings_diff': earnings_diff,
            'pct_diff': pct_diff,
            'commodity': commodity,
            'model_version': model_version
        }

        if verbose:
            print("\n" + "=" * 80)
            print(f"RESULTS SUMMARY - {commodity.upper()} - {model_version}")
            print("=" * 80)
            print(f"\n🏆 Best Overall: {best_overall['strategy']}")
            print(f"   Net Earnings: ${best_overall['net_earnings']:,.2f}")
            print(f"\n📊 Best Baseline: {best_baseline['strategy']}")
            print(f"   Net Earnings: ${best_baseline['net_earnings']:,.2f}")
            print(f"\n🎯 Best Prediction: {best_prediction['strategy']}")
            print(f"   Net Earnings: ${best_prediction['net_earnings']:,.2f}")
            print(f"\n📈 Prediction Advantage: ${earnings_diff:+,.2f} ({pct_diff:+.1f}%)")

        return analysis

    def analyze_risk_adjusted_scenarios(
        self,
        results_dict: Dict[str, Any],
        verbose: bool = True
    ) -> Dict[str, int]:
        """
        Analyze scenario distribution for Risk-Adjusted strategy

        Args:
            results_dict: Results from run_all_strategies
            verbose: Print analysis

        Returns:
            Dictionary with scenario counts
        """
        if 'Risk-Adjusted' not in results_dict:
            return {}

        risk_adj_results = results_dict['Risk-Adjusted']
        trades = risk_adj_results['trades']

        if verbose:
            print("\nAnalyzing Risk-Adjusted Strategy Scenarios...")

        # DEBUG: Print actual trade reasons
        if verbose:
            print("\nDEBUG - All Risk-Adjusted Trade Reasons:")
            reason_counts = {}
            for trade in trades:
                reason = trade.get('reason', 'UNKNOWN')
                reason_counts[reason] = reason_counts.get(reason, 0) + 1

            for reason, count in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True):
                print(f"  {count:2d}× {reason}")
            print()

        # Extract scenario counts from trade reasons
        scenario_counts = {
            'very_low_risk_8pct': 0,
            'low_risk_12pct': 0,
            'medium_risk_18pct': 0,
            'med_high_risk_25pct': 0,
            'high_risk_30pct': 0,
            'very_high_risk_40pct': 0,
            'other': 0
        }

        for trade in trades:
            reason = trade.get('reason', '')
            if 'very_low_risk' in reason or ('cv' in reason and 'defer' in reason):
                scenario_counts['very_low_risk_8pct'] += 1
            elif 'low_risk' in reason and 'ret' in reason:
                scenario_counts['low_risk_12pct'] += 1
            elif 'medium_risk' in reason and 'baseline' in reason:
                scenario_counts['medium_risk_18pct'] += 1
            elif 'med_high_risk' in reason or 'weak_trend' in reason:
                scenario_counts['med_high_risk_25pct'] += 1
            elif 'high_risk' in reason and 'reduce_exposure' in reason:
                scenario_counts['high_risk_30pct'] += 1
            elif 'very_high_risk' in reason or 'exit_fast' in reason:
                scenario_counts['very_high_risk_40pct'] += 1
            else:
                scenario_counts['other'] += 1

        if verbose:
            print("Risk-Adjusted Strategy - Scenario Distribution:")
            print(f"  Very Low Risk (8% batch):       {scenario_counts['very_low_risk_8pct']} trades")
            print(f"  Low Risk (12% batch):           {scenario_counts['low_risk_12pct']} trades")
            print(f"  Medium Risk (18% batch):        {scenario_counts['medium_risk_18pct']} trades")
            print(f"  Med-High Risk (25% batch):      {scenario_counts['med_high_risk_25pct']} trades")
            print(f"  High Risk (30% batch):          {scenario_counts['high_risk_30pct']} trades")
            print(f"  Very High Risk (40% batch):     {scenario_counts['very_high_risk_40pct']} trades")
            print(f"  Other (deadline/fallback):      {scenario_counts['other']} trades")

        return scenario_counts

    def analyze_forced_liquidations(
        self,
        results_dict: Dict[str, Any],
        commodity_config: Dict[str, Any],
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Analyze forced liquidation events

        Args:
            results_dict: Results from run_all_strategies
            commodity_config: Commodity configuration for harvest volume
            verbose: Print analysis

        Returns:
            Dictionary with forced liquidation analysis
        """
        if 'Risk-Adjusted' not in results_dict:
            return {}

        if verbose:
            print(f"\nAnalyzing forced liquidations...")

        forced = [
            t for t in results_dict['Risk-Adjusted']['trades']
            if 'liquidate' in t['reason'].lower() or 'forced' in t['reason'].lower()
        ]

        analysis = {
            'n_events': len(forced),
            'total_tons': 0,
            'avg_tons_per_event': 0,
            'pct_of_harvest': 0
        }

        if len(forced) > 0:
            total = sum(t['amount'] for t in forced)
            analysis['total_tons'] = total
            analysis['avg_tons_per_event'] = total / len(forced)

            # Calculate % of total harvest
            total_harvest = commodity_config['harvest_volume']
            analysis['pct_of_harvest'] = (total / total_harvest) * 100

            if verbose:
                print(f"\nForced liquidation events for Risk-Adjusted strategy:")
                for t in forced:
                    print(f"  {str(t['date'])[:10]}: {t['amount']:6.2f} tons - {t['reason']}")

                print(f"\nTotal: {total:.2f} tons across {len(forced)} events")
                print(f"Average: {total/len(forced):.2f} tons per liquidation")
                print(f"% of total harvest: {analysis['pct_of_harvest']:.1f}%")
        else:
            if verbose:
                print("No forced liquidations detected")

        return analysis
