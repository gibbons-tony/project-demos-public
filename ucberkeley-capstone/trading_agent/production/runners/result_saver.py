"""
Result Saver Module
Handles persistence of backtest results to Delta tables and pickle files
"""

import pandas as pd
import pickle
from typing import Dict, Any, Optional
from pathlib import Path


class ResultSaver:
    """Saves backtest results to Delta and pickle formats"""

    def __init__(self, spark=None):
        """
        Initialize result saver

        Args:
            spark: Spark session (required for Delta table operations)
        """
        self.spark = spark

    def save_results(
        self,
        commodity: str,
        model_version: str,
        metrics_df: pd.DataFrame,
        results_dict: Dict[str, Any],
        data_paths: Dict[str, str],
        metrics_by_year_df: Optional[pd.DataFrame] = None,
        metrics_by_quarter_df: Optional[pd.DataFrame] = None,
        metrics_by_month_df: Optional[pd.DataFrame] = None,
        verbose: bool = True
    ) -> Dict[str, str]:
        """
        Save all results to Delta and pickle

        Args:
            commodity: Commodity name
            model_version: Model version
            metrics_df: Overall metrics DataFrame
            results_dict: Full results dictionary
            data_paths: Data paths from config
            metrics_by_year_df: Year-by-year metrics DataFrame (optional)
            metrics_by_quarter_df: Quarter-by-quarter metrics DataFrame (optional)
            metrics_by_month_df: Month-by-month metrics DataFrame (optional)
            verbose: Print save messages

        Returns:
            Dictionary mapping result_type to save_path
        """
        if verbose:
            print("\nSaving results...")

        saved_paths = {}

        # 1. Save overall metrics to Delta table
        saved_paths['delta_metrics'] = self._save_metrics_to_delta(
            metrics_df, data_paths['results'], verbose
        )

        # 2. Save year-by-year metrics to Delta table (if provided)
        if metrics_by_year_df is not None and not metrics_by_year_df.empty:
            # Use same table name with _by_year suffix
            year_table_name = data_paths['results'].replace(
                f"results_{commodity}",
                f"results_{commodity}_by_year"
            )
            saved_paths['delta_metrics_by_year'] = self._save_metrics_to_delta(
                metrics_by_year_df, year_table_name, verbose
            )

        # 3. Save quarter-by-quarter metrics to Delta table (if provided)
        if metrics_by_quarter_df is not None and not metrics_by_quarter_df.empty:
            # Use same table name with _by_quarter suffix
            quarter_table_name = data_paths['results'].replace(
                f"results_{commodity}",
                f"results_{commodity}_by_quarter"
            )
            saved_paths['delta_metrics_by_quarter'] = self._save_metrics_to_delta(
                metrics_by_quarter_df, quarter_table_name, verbose
            )

        # 4. Save month-by-month metrics to Delta table (if provided)
        if metrics_by_month_df is not None and not metrics_by_month_df.empty:
            # Use same table name with _by_month suffix
            month_table_name = data_paths['results'].replace(
                f"results_{commodity}",
                f"results_{commodity}_by_month"
            )
            saved_paths['delta_metrics_by_month'] = self._save_metrics_to_delta(
                metrics_by_month_df, month_table_name, verbose
            )

        # 5. Save detailed results to pickle
        saved_paths['pickle_detailed'] = self._save_detailed_to_pickle(
            results_dict, data_paths['results_detailed'], verbose
        )

        return saved_paths

    def _save_metrics_to_delta(
        self,
        metrics_df: pd.DataFrame,
        table_name: str,
        verbose: bool
    ) -> str:
        """
        Save metrics DataFrame to Delta table

        Args:
            metrics_df: Metrics DataFrame
            table_name: Unity Catalog table name
            verbose: Print messages

        Returns:
            Table name
        """
        if self.spark is None:
            raise ValueError("Spark session required to save to Delta table")

        # Convert to Spark DataFrame and save
        self.spark.createDataFrame(metrics_df) \
            .write \
            .format("delta") \
            .mode("overwrite") \
            .saveAsTable(table_name)

        if verbose:
            print(f"  ✓ Saved to Delta: {table_name}")

        return table_name

    def _save_detailed_to_pickle(
        self,
        results_dict: Dict[str, Any],
        file_path: str,
        verbose: bool
    ) -> str:
        """
        Save detailed results dictionary to pickle

        Args:
            results_dict: Full results dictionary
            file_path: Path to pickle file
            verbose: Print messages

        Returns:
            File path
        """
        # Ensure directory exists
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, 'wb') as f:
            pickle.dump(results_dict, f)

        if verbose:
            print(f"  ✓ Saved: {file_path}")

        return file_path

    def save_cross_commodity_results(
        self,
        comparison_df: pd.DataFrame,
        detailed_df: pd.DataFrame,
        volume_path: str,
        verbose: bool = True
    ) -> Dict[str, str]:
        """
        Save cross-commodity/model comparison results

        Args:
            comparison_df: Summary comparison DataFrame
            detailed_df: Detailed results (all strategies)
            volume_path: Base path for files
            verbose: Print messages

        Returns:
            Dictionary mapping result_type to file_path
        """
        if verbose:
            print("\nSaving cross-commodity/model results...")

        saved_paths = {}

        # Save summary comparison
        summary_path = f"{volume_path}/cross_model_commodity_summary.csv"
        comparison_df.to_csv(summary_path, index=False)
        saved_paths['summary'] = summary_path

        if verbose:
            print(f"  ✓ Saved summary: {summary_path}")

        # Save detailed results (all strategies)
        detailed_path = f"{volume_path}/detailed_strategy_results.csv"
        detailed_df.to_csv(detailed_path, index=False)
        saved_paths['detailed'] = detailed_path

        if verbose:
            print(f"  ✓ Saved detailed: {detailed_path}")
            print(f"     Total rows: {len(detailed_df)} (all strategies)")

        return saved_paths

    def load_results(
        self,
        commodity: str,
        model_version: str,
        data_paths: Dict[str, str],
        load_detailed: bool = True
    ) -> Dict[str, Any]:
        """
        Load previously saved results

        Args:
            commodity: Commodity name
            model_version: Model version
            data_paths: Data paths from config
            load_detailed: If True, load detailed pickle results

        Returns:
            Dictionary with loaded results
        """
        loaded = {}

        # Load metrics from Delta
        if self.spark:
            loaded['metrics_df'] = self.spark.table(data_paths['results']).toPandas()
            print(f"✓ Loaded metrics from Delta: {data_paths['results']}")

        # Load detailed results from pickle
        if load_detailed:
            try:
                with open(data_paths['results_detailed'], 'rb') as f:
                    loaded['results_dict'] = pickle.load(f)
                print(f"✓ Loaded detailed results: {data_paths['results_detailed']}")
            except FileNotFoundError:
                print(f"⚠️  Detailed results not found: {data_paths['results_detailed']}")

        return loaded

    def create_consolidated_summary(
        self,
        all_commodity_results: Dict[str, Dict[str, Any]],
        verbose: bool = True
    ) -> pd.DataFrame:
        """
        Create consolidated summary across all commodity-model pairs

        Args:
            all_commodity_results: Nested dictionary {commodity: {model: results}}
            verbose: Print summary

        Returns:
            Summary DataFrame with all combinations
        """
        comparison_data = []

        for commodity_name, model_data in all_commodity_results.items():
            for model_version, results in model_data.items():
                comparison_data.append({
                    'Commodity': commodity_name.upper(),
                    'Model Version': model_version,
                    'Best Overall Strategy': results['best_overall']['strategy'],
                    'Best Overall Earnings': results['best_overall']['net_earnings'],
                    'Best Baseline Strategy': results['best_baseline']['strategy'],
                    'Best Baseline Earnings': results['best_baseline']['net_earnings'],
                    'Best Prediction Strategy': results['best_prediction']['strategy'],
                    'Best Prediction Earnings': results['best_prediction']['net_earnings'],
                    'Prediction Advantage ($)': results['earnings_diff'],
                    'Prediction Advantage (%)': results['pct_diff']
                })

        comparison_df = pd.DataFrame(comparison_data)

        if verbose:
            print("\n📊 Summary by Commodity and Model:")
            print(comparison_df.to_string())

            # Find best combo
            if len(comparison_df) > 0:
                best_combo = comparison_df.loc[comparison_df['Prediction Advantage ($)'].idxmax()]
                print("\n" + "=" * 80)
                print("KEY FINDINGS")
                print("=" * 80)
                print(f"\n💡 Best commodity/model for prediction-based strategies:")
                print(f"   {best_combo['Commodity']} - {best_combo['Model Version']}")
                print(f"   Advantage: ${best_combo['Prediction Advantage ($)']:,.2f}")
                print(f"   ({best_combo['Prediction Advantage (%)']:.1f}% improvement)")

        return comparison_df

    def create_detailed_results_df(
        self,
        all_commodity_results: Dict[str, Dict[str, Any]]
    ) -> pd.DataFrame:
        """
        Create detailed DataFrame with ALL strategy results

        Args:
            all_commodity_results: Nested dictionary {commodity: {model: results}}

        Returns:
            DataFrame with all strategies across all commodity-model pairs
        """
        detailed_results = []

        for commodity_name, model_data in all_commodity_results.items():
            for model_version, results in model_data.items():
                results_df = results['results_df'].copy()
                results_df['Commodity'] = commodity_name.upper()
                results_df['Model Version'] = model_version
                detailed_results.append(results_df)

        detailed_df = pd.concat(detailed_results, ignore_index=True)
        detailed_df = detailed_df.sort_values(
            ['Commodity', 'Model Version', 'net_earnings'],
            ascending=[True, True, False]
        )

        return detailed_df

    def validate_results(
        self,
        metrics_df: pd.DataFrame,
        results_dict: Dict[str, Any]
    ) -> bool:
        """
        Validate results for consistency and completeness

        Args:
            metrics_df: Metrics DataFrame
            results_dict: Results dictionary

        Returns:
            True if validation passes
        """
        issues = []

        # Check metrics DataFrame
        required_cols = [
            'strategy', 'net_earnings', 'total_revenue', 'total_costs',
            'n_trades', 'type', 'commodity', 'model_version'
        ]
        missing_cols = set(required_cols) - set(metrics_df.columns)
        if missing_cols:
            issues.append(f"Metrics missing columns: {missing_cols}")

        # Check results_dict keys match metrics strategies
        metric_strategies = set(metrics_df['strategy'].unique())
        result_strategies = set(results_dict.keys())
        if metric_strategies != result_strategies:
            issues.append(
                f"Strategy mismatch: "
                f"metrics={metric_strategies}, results={result_strategies}"
            )

        # Check for null values in critical columns
        for col in ['net_earnings', 'total_revenue', 'n_trades']:
            if metrics_df[col].isna().any():
                issues.append(f"Null values found in {col}")

        # Report issues
        if issues:
            print("\n⚠️  Validation issues found:")
            for issue in issues:
                print(f"  - {issue}")
            return False

        print("✓ Results validation passed")
        return True
