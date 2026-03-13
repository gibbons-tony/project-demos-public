"""
Production Scripts

Automated scripts for running trading agent workflow components.

Scripts:
- generate_synthetic_predictions.py: Generate synthetic predictions at multiple accuracy levels (ONE-TIME testing)
- load_forecast_predictions.py: Load and transform real forecast predictions from table (PERIODIC use)

Note: Notebooks 06-10 (statistical validation, feature importance, sensitivity analysis,
      results summary, paired scenario analysis) use OLD approach (paired t-tests).
      NEW approach uses theoretical maximum benchmark (see diagnostics/run_diagnostic_theoretical_max.py).
      Modern analysis suite to be designed.
"""

__version__ = '1.0.0'
__author__ = 'Trading Agent Team'
__date__ = '2025-11-24'
