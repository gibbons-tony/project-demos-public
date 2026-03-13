# Archive - Commodity Prediction Analysis

This folder contains archived notebooks and code from the evolution of the commodity prediction analysis system.

---

## Directory Structure

```
archive/
├── notebook_versions/     # Superseded notebook versions
└── monolithic/           # Original monolithic implementations before modularization
```

---

## Contents

### notebook_versions/

**Purpose:** Preserves iteration history of synthetic prediction notebooks

**Files:**
- `01_synthetic_predictions.ipynb` - Base implementation (superseded by v8)
- `01_synthetic_predictions_calibrated.ipynb` - Calibration experiment
- `01_synthetic_predictions_v6.ipynb` - Version 6 iteration
- `01_synthetic_predictions_v7.ipynb` - Version 7 iteration

**Current version:** `01_synthetic_predictions_v8.ipynb` (in parent directory)

**Why archived:**
- Superseded by v8 which fixed critical bugs:
  - Date coverage contamination (2015-2021 had no forecasts)
  - Directional bias in noise generation (should be symmetric)
- See [production/SYNTHETIC_FORECAST_BUGS.md](../production/SYNTHETIC_FORECAST_BUGS.md) for details

### monolithic/

**Purpose:** Preserves original monolithic implementations before refactoring to modular production code

**Files:**
- `trading_prediction_analysis_original_11_11_25.ipynb` (4.6MB)
  - Original all-in-one notebook with complete trading analysis
  - Created: Nov 11-14, 2025
  - Refactored into numbered workflow notebooks (00-10)

- `trading_prediction_analysis.py` (260KB)
  - Python script extraction of monolithic notebook
  - Never used in production
  - Replaced by: production/ modular framework

- `trading_prediction_analysis_multi_model.ipynb` (307KB)
  - Multi-model comparison notebook
  - Replaced by: 05_strategy_comparison.ipynb and 09_strategy_results_summary.ipynb

**Refactoring outcome:**
- Monolithic → 11 focused notebooks (00-10) + production/ framework
- Better modularity, testability, and maintainability
- See [../FILE_INVENTORY.md](../FILE_INVENTORY.md) for current structure

---

## Evolution Timeline

| Date | Milestone |
|------|-----------|
| Nov 11-14, 2025 | Original monolithic notebook created |
| Nov 14-24, 2025 | Refactored to numbered notebooks (00-10) |
| Nov 24, 2025 | Production framework created (production/) |
| Nov 24, 2025 | Synthetic prediction bugs discovered |
| Nov 24, 2025 | v8 created with fixes |
| Dec 8, 2025 | Legacy versions archived |

---

## Archival Policy

**When archived:** Dec 8, 2025 (project cleanup)

**Why archived:**
- Code superseded by current implementations
- Notebooks with known bugs (v1-v7 synthetic predictions)
- Monolithic implementations replaced by modular structure

**When to delete:**
- After 6 months (June 2026) if no active references in code
- After project completion and final presentation
- Safe to delete once git history is sufficient for reference

**Preservation reason:**
- Documents evolution from monolithic → modular architecture
- Shows iteration process (v1 → v8)
- Useful for understanding design decisions and lessons learned
- Historical context for presentation/documentation

---

**Last reviewed:** Dec 8, 2025
**See also:**
- [../FILE_INVENTORY.md](../FILE_INVENTORY.md) - Current notebook inventory
- [../production/SYNTHETIC_FORECAST_BUGS.md](../production/SYNTHETIC_FORECAST_BUGS.md) - Bug details
- [../../archive/REFACTORING_PLAN.md](../../archive/REFACTORING_PLAN.md) - Original refactoring plan
