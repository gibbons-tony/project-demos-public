"""
Production Runners Test Suite

Comprehensive test coverage for production backtest runners module

Test Files:
- conftest.py: Shared fixtures and test utilities
- test_data_loader.py: DataLoader module tests
- test_strategy_runner.py: StrategyRunner module tests
- test_visualization.py: VisualizationGenerator module tests
- test_result_saver.py: ResultSaver module tests
- test_integration.py: End-to-end integration tests

Run all tests:
    pytest production/runners/tests/ -v

Run specific module:
    pytest production/runners/tests/test_data_loader.py -v

Run with coverage:
    pytest production/runners/tests/ --cov=production.runners --cov-report=html

Run integration tests only:
    pytest production/runners/tests/test_integration.py -v
"""

__version__ = '1.0.0'
__author__ = 'Trading Agent Team'
__date__ = '2025-11-24'
