"""
Production Runners Module
Modular backtest execution system - replicates notebook 05 workflow

**Architecture:**
- DataLoader: Load prices and prediction matrices
- StrategyRunner: Execute all 10 strategies (4 baseline + 6 prediction)
- VisualizationGenerator: Generate all 5 chart types
- ResultSaver: Persist to Delta tables and pickle files
- MultiCommodityRunner: Main orchestrator

**Usage:**
```python
from production.runners.multi_commodity_runner import MultiCommodityRunner
from production.config import COMMODITY_CONFIGS, BASELINE_PARAMS, PREDICTION_PARAMS

runner = MultiCommodityRunner(
    spark=spark,
    commodity_configs=COMMODITY_CONFIGS,
    baseline_params=BASELINE_PARAMS,
    prediction_params=PREDICTION_PARAMS
)

results = runner.run_all_commodities()
```

**Module Contents:**
"""

from .data_loader import DataLoader
from .strategy_runner import StrategyRunner
from .visualization import VisualizationGenerator
from .result_saver import ResultSaver
from .multi_commodity_runner import MultiCommodityRunner

__all__ = [
    'DataLoader',
    'StrategyRunner',
    'VisualizationGenerator',
    'ResultSaver',
    'MultiCommodityRunner'
]

__version__ = '1.0.0'
__author__ = 'Trading Agent Team'
__date__ = '2025-11-24'
