"""
Efficiency Analysis

Analyzes how efficiently strategies exploit available information by comparing
actual performance to theoretical maximum.

Key Metrics:
    - Efficiency Ratio = Actual Earnings / Theoretical Max Earnings
    - Decision-by-decision comparison
    - Missed opportunity analysis
"""

from .analyzer import EfficiencyAnalyzer

__all__ = ['EfficiencyAnalyzer']
