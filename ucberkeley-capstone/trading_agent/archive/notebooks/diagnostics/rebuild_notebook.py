#!/usr/bin/env python3
"""Rebuild diagnostic_16 notebook with proper Jupyter formatting"""

import json

def create_code_cell(source):
    """Create a code cell"""
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source if isinstance(source, list) else [source]
    }

def create_markdown_cell(source):
    """Create a markdown cell"""
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": source if isinstance(source, list) else [source]
    }

# Create notebook
nb = {
    "cells": [],
    "metadata": {},
    "nbformat": 4,
    "nbformat_minor": 0
}

# Cell 0: Title
nb["cells"].append(create_markdown_cell([
    "# Diagnostic 16: Optuna Hyperparameter Optimization - ALL 9 Strategies\n",
    "\n",
    "**Purpose:** Intelligently optimize parameters for ALL trading strategies using Optuna with Spark parallelization\n",
    "\n",
    "**Strategies:**\n",
    "1. ImmediateSaleStrategy\n",
    "2. EqualBatchStrategy\n",
    "3. PriceThresholdStrategy\n",
    "4. MovingAverageStrategy\n",
    "5. PriceThresholdPredictive\n",
    "6. MovingAveragePredictive\n",
    "7. ExpectedValueStrategy\n",
    "8. ConsensusStrategy\n",
    "9. RiskAdjustedStrategy\n",
    "\n",
    "**Optimization Approach:**\n",
    "- **Algorithm:** Tree-structured Parzen Estimator (TPE) via Optuna\n",
    "- **Parallelization:** 8 Spark workers per strategy\n",
    "- **Trials:** 200 per strategy (~1,800 total)\n",
    "- **Speedup:** ~99.6% reduction vs brute force grid search (1,800 vs 520,000 evaluations)\n",
    "\n",
    "**Key Configuration:**\n",
    "- Small farmer costs: 0.005% storage/day, 0.01% transaction\n",
    "- Intelligent sampling of continuous parameter spaces\n",
    "- All strategies imported from all_strategies_pct.py\n",
    "\n",
    "**Expected Results:**\n",
    "- Near-optimal parameters with 200 trials (vs 186k for exhaustive search)\n",
    "- Clear ranking with realistic costs\n",
    "- Matched pairs showing prediction value-add\n",
    "- Convergence visualization via Optuna studies"
]))

# Cell 1: Setup
nb["cells"].append(create_code_cell("%run ../00_setup_and_config"))

# Cell 2: Imports
nb["cells"].append(create_code_cell([
    "import sys\n",
    "import os\n",
    "import pandas as pd\n",
    "import numpy as np\n",
    "import pickle\n",
    "from datetime import datetime\n",
    "import optuna\n",
    "from optuna.samplers import TPESampler\n",
    "import importlib.util\n",
    "\n",
    "print(\"=\"*80)\n",
    "print(\"DIAGNOSTIC 16: OPTUNA HYPERPARAMETER OPTIMIZATION - ALL 9 STRATEGIES\")\n",
    "print(\"=\"*80)\n",
    "print(\"\\nUsing Optuna TPE with Spark parallelization for intelligent search\")\n",
    "print(\"Expected: ~200 trials per strategy vs 500k+ grid combinations\")"
]))

# Continue with remaining cells...
print(f"Building notebook with {len(nb['cells'])} cells so far...")

# Save
output_path = 'diagnostic_16_comprehensive_grid_search.ipynb'
with open(output_path, 'w') as f:
    json.dump(nb, f, indent=2)

print(f"✓ Saved {output_path}")
print(f"  Total cells: {len(nb['cells'])}")
