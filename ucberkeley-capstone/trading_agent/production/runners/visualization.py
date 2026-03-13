"""
Visualization Module
Generates all charts for backtest results

Aligned with Phase 3 consolidation structure:
- performance/: Net earnings, revenue charts
- timelines/: Trading timeline, inventory drawdown
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import numpy as np
from typing import Dict, List, Any
from pathlib import Path


class VisualizationGenerator:
    """Generates all backtest visualization charts"""

    def __init__(self, volume_path: str = "/Volumes/commodity/trading_agent/files"):
        """
        Initialize visualization generator

        Args:
            volume_path: Base path for saving charts
        """
        self.volume_path = volume_path

    def generate_all_charts(
        self,
        commodity: str,
        model_version: str,
        results_df: pd.DataFrame,
        results_dict: Dict[str, Any],
        prices: pd.DataFrame,
        baseline_strategies: List[str],
        output_organized: bool = False
    ) -> Dict[str, str]:
        """
        Generate all 5 visualization types

        Args:
            commodity: Commodity name
            model_version: Model version
            results_df: Metrics DataFrame
            results_dict: Full results dictionary
            prices: Price history DataFrame
            baseline_strategies: List of baseline strategy names
            output_organized: If True, organize into Phase 3 subdirectories

        Returns:
            Dictionary mapping chart_type to file_path
        """
        print("\nGenerating visualizations...")

        chart_paths = {}

        # Determine output directory structure
        if output_organized:
            base_path = Path(self.volume_path)
            perf_dir = base_path / "performance"
            timeline_dir = base_path / "timelines"
            perf_dir.mkdir(parents=True, exist_ok=True)
            timeline_dir.mkdir(parents=True, exist_ok=True)
        else:
            # Legacy flat structure
            base_path = self.volume_path

        # 1. Net earnings bar chart
        chart_paths['net_earnings'] = self.generate_net_earnings_chart(
            results_df, commodity, model_version,
            str(perf_dir if output_organized else base_path)
        )

        # 2. Trading timeline
        chart_paths['trading_timeline'] = self.generate_trading_timeline(
            results_dict, prices, commodity, model_version,
            str(timeline_dir if output_organized else base_path)
        )

        # 3. Total revenue (without costs)
        chart_paths['total_revenue'] = self.generate_total_revenue_chart(
            results_dict, baseline_strategies, commodity, model_version,
            str(perf_dir if output_organized else base_path)
        )

        # 4. Cumulative net revenue (with costs)
        chart_paths['cumulative_returns'] = self.generate_cumulative_returns_chart(
            results_dict, baseline_strategies, commodity, model_version,
            str(perf_dir if output_organized else base_path)
        )

        # 5. Inventory drawdown
        chart_paths['inventory_drawdown'] = self.generate_inventory_drawdown_chart(
            results_dict, baseline_strategies, commodity, model_version,
            str(timeline_dir if output_organized else base_path)
        )

        print(f"  ✓ Generated {len(chart_paths)} charts")
        return chart_paths

    def generate_net_earnings_chart(
        self,
        results_df: pd.DataFrame,
        commodity: str,
        model_version: str,
        output_dir: str
    ) -> str:
        """Generate net earnings bar chart"""
        fig, ax = plt.subplots(figsize=(14, 8))

        baseline_data = results_df[results_df['type'] == 'Baseline'].sort_values(
            'net_earnings', ascending=True
        )
        prediction_data = results_df[results_df['type'] == 'Prediction'].sort_values(
            'net_earnings', ascending=True
        )

        y_baseline = range(len(baseline_data))
        y_prediction = range(len(baseline_data), len(baseline_data) + len(prediction_data))

        ax.barh(y_baseline, baseline_data['net_earnings'],
                color='steelblue', alpha=0.7, label='Baseline')
        ax.barh(y_prediction, prediction_data['net_earnings'],
                color='orangered', alpha=0.7, label='Prediction')

        all_strategies_sorted = pd.concat([baseline_data, prediction_data])
        ax.set_yticks(range(len(all_strategies_sorted)))
        ax.set_yticklabels(all_strategies_sorted['strategy'])
        ax.set_xlabel('Net Earnings ($)', fontsize=12)
        ax.set_title(
            f'Net Earnings by Strategy - {commodity.upper()} - {model_version}',
            fontsize=14, fontweight='bold'
        )
        ax.legend()
        ax.grid(True, alpha=0.3, axis='x')

        # Add value labels
        for i, (idx, row) in enumerate(all_strategies_sorted.iterrows()):
            ax.text(row['net_earnings'], i, f"  ${row['net_earnings']:,.0f}",
                   va='center', fontsize=9)

        plt.tight_layout()
        chart_path = f"{output_dir}/net_earnings_{commodity}_{model_version}.png"
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        print(f"  ✓ Saved: {chart_path}")
        plt.close()

        return chart_path

    def generate_trading_timeline(
        self,
        results_dict: Dict[str, Any],
        prices: pd.DataFrame,
        commodity: str,
        model_version: str,
        output_dir: str
    ) -> str:
        """Generate trading timeline scatter plot"""
        fig, ax = plt.subplots(figsize=(16, 8))

        # Plot price history as background
        ax.plot(prices['date'], prices['price'], color='gray', linewidth=1.5,
                alpha=0.5, label='Price History', zorder=1)

        # Color map for strategies
        strategy_names = list(results_dict.keys())
        colors = plt.cm.tab10(np.linspace(0, 1, len(strategy_names)))
        strategy_colors = dict(zip(strategy_names, colors))

        # Plot trades for each strategy
        for name, results in results_dict.items():
            trades = results['trades']
            if len(trades) > 0:
                trade_dates = [t['date'] for t in trades]
                trade_prices = [t['price'] for t in trades]
                trade_amounts = [t['amount'] for t in trades]

                # Marker size proportional to trade amount
                sizes = [amt * 10 for amt in trade_amounts]

                ax.scatter(trade_dates, trade_prices, s=sizes, alpha=0.6,
                          color=strategy_colors[name], label=name,
                          edgecolors='black', linewidth=0.5, zorder=2)

        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Price ($/ton)', fontsize=12)
        ax.set_title(
            f'Trading Timeline - {commodity.upper()} - {model_version}',
            fontsize=14, fontweight='bold'
        )
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        chart_path = f"{output_dir}/trading_timeline_{commodity}_{model_version}.png"
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        print(f"  ✓ Saved: {chart_path}")
        plt.close()

        return chart_path

    def generate_total_revenue_chart(
        self,
        results_dict: Dict[str, Any],
        baseline_strategies: List[str],
        commodity: str,
        model_version: str,
        output_dir: str
    ) -> str:
        """Generate cumulative total revenue chart (without costs)"""
        fig, ax = plt.subplots(figsize=(16, 8))

        # Calculate and plot cumulative revenue for each strategy
        for name, results in results_dict.items():
            daily_state = results['daily_state']
            trades_by_day = {t['day']: t for t in results['trades']}

            # Build up cumulative revenue day by day
            cumulative_revenue = []
            dates = []
            running_revenue = 0

            for idx, row in daily_state.iterrows():
                day = row['day']
                date = row['date']

                # Add any sales revenue from today
                if day in trades_by_day:
                    trade = trades_by_day[day]
                    running_revenue += trade['revenue']

                cumulative_revenue.append(running_revenue)
                dates.append(date)

            # Plot
            is_pred = name not in baseline_strategies
            ax.plot(dates, cumulative_revenue, label=name,
                   linestyle='-' if is_pred else '--',
                   linewidth=2 if is_pred else 1.5,
                   alpha=0.9 if is_pred else 0.6)

        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Cumulative Total Revenue ($)', fontsize=12)
        ax.set_title(
            f'Cumulative Total Revenue Over Time (Without Costs) - {commodity.upper()} - {model_version}',
            fontsize=14, fontweight='bold'
        )
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.8)

        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

        plt.tight_layout()
        chart_path = f"{output_dir}/total_revenue_no_costs_{commodity}_{model_version}.png"
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        print(f"  ✓ Saved: {chart_path}")
        plt.close()

        return chart_path

    def generate_cumulative_returns_chart(
        self,
        results_dict: Dict[str, Any],
        baseline_strategies: List[str],
        commodity: str,
        model_version: str,
        output_dir: str
    ) -> str:
        """Generate cumulative net revenue chart (with costs)"""
        fig, ax = plt.subplots(figsize=(16, 8))

        # Calculate and plot cumulative net revenue for each strategy
        for name, results in results_dict.items():
            daily_state = results['daily_state']
            trades_by_day = {t['day']: t for t in results['trades']}

            # Build up cumulative values day by day
            cumulative_net_revenue = []
            dates = []
            running_revenue = 0
            running_transaction_costs = 0
            running_storage_costs = 0

            for idx, row in daily_state.iterrows():
                day = row['day']
                date = row['date']

                # Add any sales revenue/costs from today
                if day in trades_by_day:
                    trade = trades_by_day[day]
                    running_revenue += trade['revenue']
                    running_transaction_costs += trade['transaction_cost']

                # Add today's storage cost
                running_storage_costs += row['daily_storage_cost']

                # Net earnings to date
                net_revenue = running_revenue - running_transaction_costs - running_storage_costs
                cumulative_net_revenue.append(net_revenue)
                dates.append(date)

            # Plot
            is_pred = name not in baseline_strategies
            ax.plot(dates, cumulative_net_revenue, label=name,
                   linestyle='-' if is_pred else '--',
                   linewidth=2 if is_pred else 1.5,
                   alpha=0.9 if is_pred else 0.6)

        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Cumulative Net Revenue ($)', fontsize=12)
        ax.set_title(
            f'Cumulative Net Revenue Over Time - {commodity.upper()} - {model_version}',
            fontsize=14, fontweight='bold'
        )
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.8)

        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

        plt.tight_layout()
        chart_path = f"{output_dir}/cumulative_returns_{commodity}_{model_version}.png"
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        print(f"  ✓ Saved: {chart_path}")
        plt.close()

        return chart_path

    def generate_inventory_drawdown_chart(
        self,
        results_dict: Dict[str, Any],
        baseline_strategies: List[str],
        commodity: str,
        model_version: str,
        output_dir: str
    ) -> str:
        """Generate inventory drawdown chart"""
        fig, ax = plt.subplots(figsize=(16, 8))

        # Plot inventory levels over time for each strategy
        for name, results in results_dict.items():
            daily_state = results['daily_state']

            dates = daily_state['date'].tolist()
            inventory = daily_state['inventory'].tolist()

            # Plot
            is_pred = name not in baseline_strategies
            ax.plot(dates, inventory, label=name,
                   linestyle='-' if is_pred else '--',
                   linewidth=2 if is_pred else 1.5,
                   alpha=0.9 if is_pred else 0.6)

        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Inventory (tons)', fontsize=12)
        ax.set_title(
            f'Inventory Drawdown Over Time - {commodity.upper()} - {model_version}',
            fontsize=14, fontweight='bold'
        )
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.8)

        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

        plt.tight_layout()
        chart_path = f"{output_dir}/inventory_drawdown_{commodity}_{model_version}.png"
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        print(f"  ✓ Saved: {chart_path}")
        plt.close()

        return chart_path

    def generate_cross_commodity_comparison(
        self,
        comparison_df: pd.DataFrame,
        output_dir: str
    ) -> Dict[str, str]:
        """
        Generate cross-commodity/model comparison charts

        Args:
            comparison_df: Summary DataFrame with all commodity-model pairs
            output_dir: Directory to save charts

        Returns:
            Dictionary mapping chart_type to file_path
        """
        print("\nGenerating cross-commodity/model comparison charts...")

        chart_paths = {}

        # Chart 1: Prediction advantage by model and commodity
        chart_paths['advantage'] = self._plot_prediction_advantage(
            comparison_df, output_dir
        )

        # Chart 2: Best strategy earnings by model and commodity
        chart_paths['earnings'] = self._plot_best_earnings(
            comparison_df, output_dir
        )

        return chart_paths

    def _plot_prediction_advantage(
        self,
        comparison_df: pd.DataFrame,
        output_dir: str
    ) -> str:
        """Plot prediction advantage across commodities and models"""
        fig, ax = plt.subplots(figsize=(16, 8))

        commodities = comparison_df['Commodity'].unique()
        models = comparison_df['Model Version'].unique()

        x = np.arange(len(commodities))
        width = 0.8 / len(models)

        for i, model in enumerate(models):
            model_data = comparison_df[comparison_df['Model Version'] == model]
            advantages = [
                model_data[model_data['Commodity'] == c]['Prediction Advantage ($)'].values[0]
                if len(model_data[model_data['Commodity'] == c]) > 0 else 0
                for c in commodities
            ]

            ax.bar(x + i * width, advantages, width, label=model, alpha=0.8)

        ax.set_xlabel('Commodity', fontsize=12)
        ax.set_ylabel('Prediction Advantage ($)', fontsize=12)
        ax.set_title('Prediction Strategy Advantage by Model and Commodity',
                     fontsize=14, fontweight='bold')
        ax.set_xticks(x + width * (len(models) - 1) / 2)
        ax.set_xticklabels(commodities)
        ax.legend(loc='best', fontsize=9)
        ax.grid(True, alpha=0.3, axis='y')
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.8)

        plt.tight_layout()
        chart_path = f"{output_dir}/cross_model_commodity_advantage.png"
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        print(f"✓ Saved: {chart_path}")
        plt.close()

        return chart_path

    def _plot_best_earnings(
        self,
        comparison_df: pd.DataFrame,
        output_dir: str
    ) -> str:
        """Plot best strategy earnings across commodities and models"""
        fig, ax = plt.subplots(figsize=(16, 8))

        commodities = comparison_df['Commodity'].unique()
        models = comparison_df['Model Version'].unique()

        x = np.arange(len(commodities))
        width = 0.8 / len(models)

        for i, model in enumerate(models):
            model_data = comparison_df[comparison_df['Model Version'] == model]
            baseline_earnings = [
                model_data[model_data['Commodity'] == c]['Best Baseline Earnings'].values[0]
                if len(model_data[model_data['Commodity'] == c]) > 0 else 0
                for c in commodities
            ]
            prediction_earnings = [
                model_data[model_data['Commodity'] == c]['Best Prediction Earnings'].values[0]
                if len(model_data[model_data['Commodity'] == c]) > 0 else 0
                for c in commodities
            ]

            x_offset = x + i * width
            ax.bar(x_offset - width/4, baseline_earnings, width/2,
                   label=f'{model} - Baseline' if i == 0 else '',
                   color='steelblue', alpha=0.7)
            ax.bar(x_offset + width/4, prediction_earnings, width/2,
                   label=f'{model} - Prediction' if i == 0 else '',
                   color='orangered', alpha=0.7)

        ax.set_xlabel('Commodity', fontsize=12)
        ax.set_ylabel('Net Earnings ($)', fontsize=12)
        ax.set_title('Best Strategy Earnings by Model and Commodity',
                     fontsize=14, fontweight='bold')
        ax.set_xticks(x + width * (len(models) - 1) / 2)
        ax.set_xticklabels(commodities)
        ax.legend(loc='best', fontsize=9)
        ax.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()
        chart_path = f"{output_dir}/cross_model_commodity_earnings.png"
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        print(f"✓ Saved: {chart_path}")
        plt.close()

        return chart_path
