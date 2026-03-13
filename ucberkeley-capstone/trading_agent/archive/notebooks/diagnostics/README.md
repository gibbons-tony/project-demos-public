# Diagnostics Folder - Clean Structure

**Last Updated:** 2025-11-24
**Status:** Cleaned and organized

---

## 📁 Directory Structure

```
diagnostics/
├── 📘 Core Strategy Implementation
│   ├── all_strategies_pct.py (54K)          ← All 9 trading strategies
│   ├── cost_config_small_farmer.py (1.4K)   ← Cost configurations
│   └── test_all_strategies.py (4.2K)        ← Quick smoke tests
│
├── 📊 Active Diagnostic Notebooks
│   ├── diagnostic_16_optuna_with_params.ipynb (20K)    ← Grid search optimization
│   │                                                    └─► SAVES: diagnostic_16_best_params.pkl
│   ├── diagnostic_17_paradox_analysis.ipynb (28K)      ← Trade-by-trade analysis
│   │                                                    └─► LOADS: diagnostic_16_best_params.pkl
│   └── diagnostic_100_algorithm_validation.py (13K)     ← 100% accuracy test
│
└── 📖 Documentation
    ├── MASTER_DIAGNOSTIC_PLAN.md (17K)              ← ⭐ START HERE - Complete workflow guide
    ├── ACCURACY_LEVEL_TESTING_GUIDE.md (8.9K)      ← 100% accuracy testing details
    ├── FILE_CLEANUP_ASSESSMENT.md (6.9K)           ← What was cleaned and why
    │
    └── Utility Guides
        ├── DATABRICKS_QUERY_GUIDE.md (2.6K)        ← Quick reference
        ├── DATABRICKS_OUTPUT_ACCESS_GUIDE.md (8.8K) ← How to access outputs
        ├── HOW_TO_GET_NOTEBOOK_RESULTS.md (3.8K)   ← Download results guide
        └── rebuild_notebook.py (3.1K)              ← Utility script
```

---

## 🚀 Quick Start

### 1. Read the Documentation
```bash
# Start with the master plan (single source of truth)
cat MASTER_DIAGNOSTIC_PLAN.md
```

### 2. Understand the Workflow

```
v8 Predictions (Main folder)
      ↓
diagnostic_16 (Grid search) → Saves: diagnostic_16_best_params.pkl
      ↓
diagnostic_17 (Analysis) → Loads: diagnostic_16_best_params.pkl
      ↓
diagnostic_100 (100% test) → Validates algorithms work
```

### 3. Run Diagnostics

**Step 1:** Test algorithm validity (CRITICAL)
```bash
python diagnostic_100_algorithm_validation.py
```

**Step 2:** Optimize parameters (Databricks)
- Run `diagnostic_16_optuna_with_params.ipynb`
- Wait for output: `diagnostic_16_best_params.pkl`

**Step 3:** Analyze paradox (Databricks)
- Run `diagnostic_17_paradox_analysis.ipynb`
- Requires: `diagnostic_16_best_params.pkl` from Step 2

---

## 📝 Key Files Explained

### Strategy Implementation
**`all_strategies_pct.py`**
- Contains all 9 trading strategies
- 4 Baselines: Immediate Sale, Equal Batches, Price Threshold, Moving Average
- 5 Prediction-based: Expected Value, Consensus, Risk-Adjusted, PT Predictive, MA Predictive
- Percentage-based decision framework (scale-invariant)
- Used by: All diagnostic notebooks

### Diagnostic Workflows
**`diagnostic_16_optuna_with_params.ipynb`**
- Optimizes parameters for all 9 strategies using Optuna
- 200 trials per strategy
- **OUTPUT:** `diagnostic_16_best_params.pkl` (dictionary of optimized params)
- Runtime: 30-60 minutes

**`diagnostic_17_paradox_analysis.ipynb`**
- Investigates why predictions might hurt performance
- Uses optimized parameters from diagnostic_16
- **INPUT:** `diagnostic_16_best_params.pkl` (REQUIRED!)
- Trade-by-trade comparison, cost breakdown, hypothesis testing
- Runtime: 5-10 minutes

**`diagnostic_100_algorithm_validation.py`**
- Tests strategies with 100% accurate predictions (perfect foresight)
- If predictions don't beat baselines with 100% accuracy → algorithms broken
- Independent test (doesn't need diagnostic_16 params)
- Runtime: 3-5 minutes

---

## 📚 Documentation

### Primary Documentation
**`MASTER_DIAGNOSTIC_PLAN.md`** ⭐
- Complete diagnostic workflow
- File dependencies clearly explained
- Troubleshooting guide
- Expected results by accuracy level
- **Use this as your single source of truth**

**`ACCURACY_LEVEL_TESTING_GUIDE.md`**
- Details on testing across accuracy spectrum (60%, 70%, 80%, 90%, 100%)
- Why 100% accuracy test is critical
- Monotonicity validation
- Troubleshooting by accuracy level

**`FILE_CLEANUP_ASSESSMENT.md`**
- Documents cleanup performed on 2025-11-24
- Explains what was deleted and why
- Before/after comparison

### Utility Guides
- `DATABRICKS_QUERY_GUIDE.md` - Quick reference for common queries
- `DATABRICKS_OUTPUT_ACCESS_GUIDE.md` - How to access Databricks outputs
- `HOW_TO_GET_NOTEBOOK_RESULTS.md` - Download results from Databricks

---

## 🎯 Success Criteria

### Critical Test (Must Pass)
- [ ] **100% accuracy (diagnostic_100):** Predictions beat baseline by >10%
  - If fails: Algorithms broken - fix before continuing

### Validation Tests (Should Pass)
- [ ] **90% accuracy (diagnostic_16+17):** Predictions beat baseline by >$30k
- [ ] **Monotonicity (main notebooks):** 60% < 70% < 80% < 90% < 100%

---

## 🗂️ File Count

**Total files:** 13
- **Python implementations:** 3 (strategies, config, tests)
- **Diagnostic notebooks:** 3 (diagnostic_16, diagnostic_17, diagnostic_100)
- **Documentation:** 7 (including this README)

**Cleaned up:** 10 obsolete files removed (Nov 24, 2025)
- Duplicates, obsolete strategy versions, outdated docs

---

## 🔗 Related Documentation

### In Parent Folder
- `../DATABRICKS_ACCESS_NOTES.md` - Databricks patterns and access
- `../00_setup_and_config.ipynb` - Configuration and paths
- `../01_synthetic_predictions_v8.ipynb` - Prediction generation

### Main Project
- `../../README.md` - Trading agent overview
- `/docs/DOCUMENTATION_STRATEGY.md` - Project doc structure

---

## ⚠️ Important Notes

### File Dependencies
**CRITICAL:** `diagnostic_17` requires `diagnostic_16` to run first!

```
diagnostic_16_optuna_with_params.ipynb
    ↓ (saves)
diagnostic_16_best_params.pkl  ← KEY ARTIFACT
    ↓ (loads)
diagnostic_17_paradox_analysis.ipynb
```

If you try to run diagnostic_17 without running diagnostic_16 first, you'll get:
```
FileNotFoundError: diagnostic_16_best_params.pkl not found!
Please run diagnostic_16_optuna_complete.ipynb first
```

### Accuracy Levels
All diagnostics use synthetic predictions generated by v8:
- `synthetic_acc100` - 100% accurate (0% MAPE)
- `synthetic_acc90` - 90% accurate (10% MAPE)
- `synthetic_acc80` - 80% accurate (20% MAPE)
- `synthetic_acc70` - 70% accurate (30% MAPE)
- `synthetic_acc60` - 60% accurate (40% MAPE)

---

## 📞 Support

**Questions?** Check `MASTER_DIAGNOSTIC_PLAN.md` first

**Issues?** See troubleshooting section in master plan

**Need to add new diagnostics?**
1. Create file: `diagnostic_XX_description.ipynb`
2. Update `MASTER_DIAGNOSTIC_PLAN.md`
3. Document dependencies clearly
4. Update this README

---

**Ready to start?** Read `MASTER_DIAGNOSTIC_PLAN.md` for complete workflow! 🚀
