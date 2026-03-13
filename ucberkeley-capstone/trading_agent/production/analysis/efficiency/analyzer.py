"""
Efficiency Analyzer

Compares actual strategy performance to theoretical maximum to measure efficiency.

Key Questions:
    1. How efficiently are we exploiting available predictions?
    2. Where are we leaving money on the table?
    3. Which strategies get closest to optimal?

Metrics:
    - Efficiency Ratio: (Actual / Theoretical Max) × 100%
    - Opportunity Gap: Theoretical Max - Actual
    - Decision Quality: Day-by-day comparison
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional


class EfficiencyAnalyzer:
    """
    Analyzes strategy efficiency by comparing actual results to theoretical maximum.

    Attributes:
        theoretical_max_result (Dict): Result from TheoreticalMaxCalculator
        actual_results (pd.DataFrame): Actual strategy results with metrics
    """

    def __init__(self, theoretical_max_result: Dict):
        """
        Initialize analyzer with theoretical maximum benchmark.

        Args:
            theoretical_max_result: Dict from TheoreticalMaxCalculator.calculate_optimal_policy()
                Must contain:
                - total_net_earnings: float
                - optimal_decisions: List[Dict]
                - total_revenue: float
                - total_transaction_costs: float
                - total_storage_costs: float
        """
        self.theoretical_max_result = theoretical_max_result
        self.theoretical_max_earnings = theoretical_max_result['total_net_earnings']

    def calculate_efficiency_ratios(
        self,
        actual_results: pd.DataFrame,
        earnings_column: str = 'net_earnings',
        strategy_column: str = 'strategy'
    ) -> pd.DataFrame:
        """
        Calculate efficiency ratios for all strategies.

        Args:
            actual_results: DataFrame with actual strategy performance
            earnings_column: Column name for net earnings (default: 'net_earnings')
            strategy_column: Column name for strategy name (default: 'strategy')

        Returns:
            pd.DataFrame with columns:
                - strategy: str
                - actual_earnings: float
                - theoretical_max: float
                - efficiency_pct: float (0-100)
                - opportunity_gap: float (dollars left on table)
                - efficiency_category: str (EXCELLENT/GOOD/MODERATE/POOR)
        """
        efficiency_results = []

        for idx, row in actual_results.iterrows():
            strategy = row[strategy_column]
            actual_earnings = row[earnings_column]

            efficiency_pct = (actual_earnings / self.theoretical_max_earnings) * 100
            opportunity_gap = self.theoretical_max_earnings - actual_earnings

            # Categorize efficiency
            if efficiency_pct >= 80:
                category = 'EXCELLENT'
            elif efficiency_pct >= 70:
                category = 'GOOD'
            elif efficiency_pct >= 60:
                category = 'MODERATE'
            else:
                category = 'POOR'

            efficiency_results.append({
                'strategy': strategy,
                'actual_earnings': actual_earnings,
                'theoretical_max': self.theoretical_max_earnings,
                'efficiency_pct': efficiency_pct,
                'opportunity_gap': opportunity_gap,
                'efficiency_category': category
            })

        return pd.DataFrame(efficiency_results).sort_values('efficiency_pct', ascending=False)

    def compare_decisions(
        self,
        actual_decisions: pd.DataFrame,
        strategy_name: str
    ) -> pd.DataFrame:
        """
        Compare actual strategy decisions to optimal decisions day-by-day.

        Args:
            actual_decisions: DataFrame with columns ['date', 'amount_sold', 'price', 'inventory_after']
            strategy_name: Name of the strategy being compared

        Returns:
            pd.DataFrame with day-by-day comparison
        """
        optimal_df = pd.DataFrame(self.theoretical_max_result['optimal_decisions'])

        # Merge on date
        comparison = optimal_df.merge(
            actual_decisions,
            on='date',
            how='left',
            suffixes=('_optimal', '_actual')
        )

        # Calculate differences
        comparison['amount_diff'] = comparison['amount_sold_optimal'] - comparison['amount_sold_actual']
        comparison['inventory_diff'] = comparison['inventory_after_optimal'] - comparison['inventory_after_actual']

        # Flag suboptimal decisions
        comparison['is_suboptimal'] = comparison['amount_diff'].abs() > 0.1  # Threshold: 0.1 tons

        # Add strategy name
        comparison['strategy'] = strategy_name

        return comparison[[
            'day', 'date', 'strategy',
            'amount_sold_optimal', 'amount_sold_actual', 'amount_diff',
            'inventory_after_optimal', 'inventory_after_actual', 'inventory_diff',
            'is_suboptimal'
        ]]

    def get_summary_report(
        self,
        efficiency_df: pd.DataFrame
    ) -> Dict:
        """
        Generate summary report of efficiency analysis.

        Args:
            efficiency_df: DataFrame from calculate_efficiency_ratios()

        Returns:
            Dict with summary statistics and insights
        """
        best_strategy = efficiency_df.iloc[0]
        worst_strategy = efficiency_df.iloc[-1]

        # Category distribution
        category_counts = efficiency_df['efficiency_category'].value_counts()

        summary = {
            'theoretical_max_earnings': self.theoretical_max_earnings,
            'n_strategies_evaluated': len(efficiency_df),

            # Best strategy
            'best_strategy': best_strategy['strategy'],
            'best_efficiency_pct': best_strategy['efficiency_pct'],
            'best_actual_earnings': best_strategy['actual_earnings'],
            'best_opportunity_gap': best_strategy['opportunity_gap'],

            # Worst strategy
            'worst_strategy': worst_strategy['strategy'],
            'worst_efficiency_pct': worst_strategy['efficiency_pct'],
            'worst_actual_earnings': worst_strategy['actual_earnings'],

            # Distribution
            'avg_efficiency_pct': efficiency_df['efficiency_pct'].mean(),
            'median_efficiency_pct': efficiency_df['efficiency_pct'].median(),
            'std_efficiency_pct': efficiency_df['efficiency_pct'].std(),

            # Category breakdown
            'n_excellent': category_counts.get('EXCELLENT', 0),
            'n_good': category_counts.get('GOOD', 0),
            'n_moderate': category_counts.get('MODERATE', 0),
            'n_poor': category_counts.get('POOR', 0),

            # Insights
            'total_opportunity_gap': efficiency_df['opportunity_gap'].sum(),
            'avg_opportunity_gap': efficiency_df['opportunity_gap'].mean()
        }

        return summary

    def get_interpretation(
        self,
        summary: Dict
    ) -> str:
        """
        Generate human-readable interpretation of efficiency analysis.

        Args:
            summary: Dict from get_summary_report()

        Returns:
            str with interpretation and recommendations
        """
        lines = []

        lines.append("=" * 80)
        lines.append("EFFICIENCY ANALYSIS INTERPRETATION")
        lines.append("=" * 80)

        # Overall assessment
        if summary['best_efficiency_pct'] >= 80:
            lines.append("\n✅ EXCELLENT: Best strategy achieves >80% efficiency")
            lines.append(f"   Our algorithms are effectively exploiting available predictions.")
        elif summary['best_efficiency_pct'] >= 70:
            lines.append("\n✓ GOOD: Best strategy achieves >70% efficiency")
            lines.append(f"   Room for optimization, but reasonable performance.")
        elif summary['best_efficiency_pct'] >= 60:
            lines.append("\n⚠️ MODERATE: Best strategy only achieves 60-70% efficiency")
            lines.append(f"   Significant room for improvement in decision logic.")
        else:
            lines.append("\n❌ POOR: Best strategy achieves <60% efficiency")
            lines.append(f"   Fundamental issues with strategy decision logic.")

        # Best strategy details
        lines.append(f"\nBest Strategy: {summary['best_strategy']}")
        lines.append(f"  Efficiency: {summary['best_efficiency_pct']:.1f}%")
        lines.append(f"  Actual Earnings: ${summary['best_actual_earnings']:,.2f}")
        lines.append(f"  Opportunity Gap: ${summary['best_opportunity_gap']:,.2f} left on table")

        # Category distribution
        lines.append(f"\nStrategy Distribution:")
        lines.append(f"  EXCELLENT (≥80%): {summary['n_excellent']}")
        lines.append(f"  GOOD (70-80%): {summary['n_good']}")
        lines.append(f"  MODERATE (60-70%): {summary['n_moderate']}")
        lines.append(f"  POOR (<60%): {summary['n_poor']}")

        # Average performance
        lines.append(f"\nAverage Efficiency: {summary['avg_efficiency_pct']:.1f}%")
        lines.append(f"Total Opportunity Gap (all strategies): ${summary['total_opportunity_gap']:,.2f}")

        # Recommendations
        lines.append("\n" + "=" * 80)
        lines.append("RECOMMENDATIONS")
        lines.append("=" * 80)

        if summary['best_efficiency_pct'] >= 80:
            lines.append("\n1. Current strategies are performing well")
            lines.append("2. Focus on production deployment and monitoring")
            lines.append("3. Consider marginal optimizations for the remaining gap")
        elif summary['best_efficiency_pct'] >= 70:
            lines.append("\n1. Investigate decision patterns in best strategy")
            lines.append("2. Analyze where opportunity gap occurs (early/late in cycle)")
            lines.append("3. Consider parameter tuning to improve efficiency")
        else:
            lines.append("\n1. URGENT: Review strategy decision logic")
            lines.append("2. Analyze optimal policy for patterns")
            lines.append("3. Consider redesigning strategies to better exploit predictions")
            lines.append("4. May need to revisit prediction quality/calibration")

        return "\n".join(lines)

    def identify_critical_decisions(
        self,
        comparison_df: pd.DataFrame,
        top_n: int = 10
    ) -> pd.DataFrame:
        """
        Identify the most critical suboptimal decisions.

        Args:
            comparison_df: DataFrame from compare_decisions()
            top_n: Number of top decisions to return (default: 10)

        Returns:
            pd.DataFrame with most impactful suboptimal decisions
        """
        # Filter to suboptimal decisions
        suboptimal = comparison_df[comparison_df['is_suboptimal']].copy()

        # Calculate impact (absolute difference in amount sold)
        suboptimal['impact'] = suboptimal['amount_diff'].abs()

        # Sort by impact
        critical = suboptimal.sort_values('impact', ascending=False).head(top_n)

        return critical[[
            'day', 'date', 'strategy',
            'amount_sold_optimal', 'amount_sold_actual',
            'amount_diff', 'impact'
        ]]
