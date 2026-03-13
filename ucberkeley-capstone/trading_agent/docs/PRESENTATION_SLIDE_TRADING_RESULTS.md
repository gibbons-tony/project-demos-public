# Trading Strategy Results - Presentation Slide

**Purpose:** Slide proposal for presenting trading agent results
**Created:** 2024-12-04
**Updated:** 2024-12-04
**Status:** ⚠️ TEMPLATE - All numbers are PLACEHOLDERS until real backtest data is available

**IMPORTANT:**
- All dollar amounts ($50K, $61K, etc.) are PLACEHOLDER examples
- All percentages (18-22%, +1-2%, etc.) are PLACEHOLDER examples
- All p-values are PLACEHOLDER examples
- Replace with actual backtest results before presentation
- See ACADEMIC_REFERENCES_BIBLIOGRAPHY.md for verified citations

---

## Slide Title

**"Research-Based Trading Algorithms: Proven Value"**
**Subtitle:** "Forecast Integration: Needs Accuracy Improvement"

---

## Layout: 3-Column Structure

### Column 1: What We Tested (10 Strategies)

**📚 Baseline Algorithms (4)**
*Based on academic research:*

- **Immediate Sale** (naive baseline)
- **Equal Batches** (practitioner heuristic)
- **Price Threshold** [Marshall et al. 2008]
- **Moving Average** [Marshall et al. 2008]

**🔮 Forecast-Enhanced (6)**
*Integrating predictions:*

- **Consensus** [Clemen 1989]
- **Expected Value** [Williams & Wright 1991]
- **Risk-Adjusted** [Markowitz 1952]
- **Threshold + Forecasts** [Marshall 2008 extended]
- **Moving Avg + Forecasts** [Marshall 2008 extended]
- **MPC Optimization** [Secomandi 2010]

**See docs/ACADEMIC_REFERENCES_BIBLIOGRAPHY.md for complete verified citations**

---

### Column 2: Results (Horizontal Bar Chart)

**⚠️ PLACEHOLDER DATA - Replace with actual backtest results**

**Visual: Horizontal bars showing net earnings**

```
Immediate Sale    ████ $50K (baseline) [PLACEHOLDER]
                        ↓ +22% ✓ [PLACEHOLDER]
Price Threshold   █████████ $61K [PLACEHOLDER]
Moving Average    ██████████ $62K [PLACEHOLDER]
Equal Batches     █████████ $61K [PLACEHOLDER]
                        ↓ +1.5% (ns) [PLACEHOLDER]
MA + Forecasts    ██████████ $63K [PLACEHOLDER]
Consensus         ██████████ $63K [PLACEHOLDER]
Expected Value    ██████████ $62K [PLACEHOLDER]
Risk-Adjusted     ██████████ $63K [PLACEHOLDER]

Legend:
✓ = p < 0.001 (statistically significant)
ns = p > 0.05 (not significant)
```

**⚠️ All numbers above are PLACEHOLDER examples for layout purposes only**

---

### Column 3: Key Findings

**⚠️ PLACEHOLDER PERCENTAGES - Replace with actual results**

**✅ Algorithms Drive Value**
- Smart strategies beat naive by [18-22%] [PLACEHOLDER]
- Highly significant (p < 0.001) [PLACEHOLDER]
- **Production-ready NOW** [If results confirm]

**⚠️ Forecasts: Limited Impact**
- Add only [+1-2%] over baseline algorithms [PLACEHOLDER]
- Not statistically significant (p > 0.05) [PLACEHOLDER]
- Current forecast accuracy is limiting factor [If confirmed]

**🎯 Opportunity: Better Forecasts**
- Sensitivity analysis shows: [PLACEHOLDER]
  - 90% accuracy → [+8%] projected gain [PLACEHOLDER]
  - vs current [+2%] at 75% accuracy [PLACEHOLDER]
- Forecast improvement = [4x ROI increase] [PLACEHOLDER]

---

## Bottom Section: Forecast Sensitivity Chart

**⚠️ PLACEHOLDER CHART - Replace with actual sensitivity analysis data**

**Title:** "How Forecast Accuracy Affects Strategy Value"

```
Net Earnings [ALL VALUES PLACEHOLDER]
      ↑
  70K │                              ●────● 100% accuracy [PLACEHOLDER]
      │                          ●──●
  65K │                      ●──●
      │                  ●──●
  60K │              ●──●              Current (~75%) [PLACEHOLDER]
      │          ●──●                        ↓ +$2K [PLACEHOLDER]
  55K │      ●──●                         (marginal)
      │═══════════════════════════════ Baseline (no forecasts)
  50K │
      └─────────────────────────────────────────→ Forecast Accuracy
         60%     70%     80%     90%    100%

         Minimum    Break-    Current   Target    Theoretical
         Viable     Even                          Maximum
```

**Key Message:** Better forecasts unlock [4x] more value than current accuracy provides [PLACEHOLDER]

**NOTE:** Run sensitivity analysis with synthetic predictions at 60%, 70%, 80%, 90%, 100% accuracy levels to generate real data for this chart.

---

## Speaker Notes / Talking Points

### Setup (10 seconds)
"We tested 10 trading strategies—4 from academic research, 6 integrating our price forecasts—across 7 years of coffee trading data."

### Finding 1: Algorithms Work (15 seconds)
"The big win is algorithm design. Research-based strategies like price threshold and moving average beat naive 'sell immediately' by 18-22%. This is highly significant with p-values under 0.001, meaning we can deploy these algorithms to production right now with confidence."

### Finding 2: Forecasts Don't Add Much Yet (15 seconds)
"Forecast integration? Disappointing but instructive. Adding predictions only improves results by 1-2%, which is NOT statistically significant. This tells us our algorithm framework works, but current forecast accuracy is the limiting factor, not the strategy logic."

### Future Opportunity (10 seconds)
"The opportunity: sensitivity analysis shows if we improve forecast accuracy from 75% to 90%, we could unlock an additional 5-8% gain—4 times the current forecast value. The algorithms are ready; forecast quality is our next lever."

---

## Data Points to Extract from Backtests

When you run updated notebooks/production system, extract these metrics:

| Metric | Description | Source |
|--------|-------------|--------|
| **Baseline (Immediate Sale)** | Naive strategy earnings | Strategy results |
| **Best Baseline Algorithm** | Price Threshold or Moving Avg | Max of baseline strategies |
| **% Improvement (algorithms)** | (Best Baseline - Immediate) / Immediate | Calculation |
| **p-value (algorithms)** | Statistical significance | Notebook 06 |
| **Best Forecast Strategy** | Risk-Adjusted or Consensus | Max of forecast strategies |
| **% Improvement (forecasts)** | (Best Forecast - Best Baseline) / Best Baseline | Calculation |
| **p-value (forecasts)** | Statistical significance | Notebook 06 |
| **Sensitivity: 60%-100%** | Earnings at each accuracy level | Multi-accuracy backtest with v8 synthetic predictions |

---

## How to Get Real Data

### Step 1: Generate Synthetic Predictions at All Accuracy Levels
```bash
# Run in Databricks
01_synthetic_predictions_v8.ipynb
```

**Outputs:**
- `synthetic_acc100`, `synthetic_acc90`, `synthetic_acc80`, `synthetic_acc70`, `synthetic_acc60`
- Saved to `commodity.forecast.distributions`

### Step 2: Run Backtests

**Option A: Update Notebook 05**
```python
# In 05_strategy_comparison.ipynb
# Add imports to use production strategies
import sys
sys.path.append('/Workspace/Repos/Project_Git/ucberkeley-capstone/trading_agent')

from production.strategies import (
    ImmediateSaleStrategy,
    EqualBatchStrategy,
    PriceThresholdStrategy,
    MovingAverageStrategy,
    ConsensusStrategy,
    ExpectedValueStrategy,
    RiskAdjustedStrategy,
    PriceThresholdPredictive,
    MovingAveragePredictive,
    RollingHorizonMPC
)

# Run for each accuracy level
for accuracy in [100, 90, 80, 70, 60]:
    model_version = f'synthetic_acc{accuracy}'
    # Load predictions and run backtests
```

**Option B: Production System** (once AWS unlocked)
```bash
python production/run_backtest_workflow.py --mode full --commodity coffee
# Automatically discovers and runs all synthetic accuracy levels
```

### Step 3: Get Statistical Significance
```bash
# Run in Databricks
06_statistical_validation.ipynb
```

**Outputs:**
- p-values for each strategy comparison
- Cohen's d (effect sizes)
- Bootstrap confidence intervals

### Step 4: Create Sensitivity Analysis
```python
# New analysis or add to 08_sensitivity_analysis.ipynb

import pandas as pd
import matplotlib.pyplot as plt

accuracy_results = []

for accuracy in [100, 90, 80, 70, 60]:
    model_version = f'synthetic_acc{accuracy}'
    results_df = spark.table(f'commodity.trading_agent.results_coffee_{model_version}').toPandas()

    for strategy in results_df['strategy'].unique():
        row = results_df[results_df['strategy'] == strategy].iloc[0]
        accuracy_results.append({
            'accuracy': accuracy,
            'strategy': strategy,
            'net_earnings': row['net_earnings'],
            'type': row['type']
        })

sensitivity_df = pd.DataFrame(accuracy_results)

# Plot: Strategy Performance vs Forecast Accuracy
fig, ax = plt.subplots(figsize=(12, 6))

for strategy in sensitivity_df['strategy'].unique():
    strategy_data = sensitivity_df[sensitivity_df['strategy'] == strategy]
    ax.plot(strategy_data['accuracy'], strategy_data['net_earnings'],
            marker='o', label=strategy, linewidth=2)

ax.set_xlabel('Forecast Accuracy (%)', fontsize=12)
ax.set_ylabel('Net Earnings ($)', fontsize=12)
ax.set_title('Strategy Performance vs Forecast Accuracy', fontsize=14, fontweight='bold')
ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
ax.grid(alpha=0.3)
plt.tight_layout()
plt.show()
```

---

## Visual Design Recommendations

### Color Coding
- 🟢 **Green**: Significant results (p < 0.001) - Algorithm improvements
- 🟡 **Yellow**: Not significant (p > 0.05) - Forecast improvements
- ⚪ **Gray**: Baseline reference (Immediate Sale)

### Emphasis
- Make the **18-22% algorithm improvement** large and GREEN
- Make the **+1-2% forecast improvement** smaller and YELLOW with "(p > 0.05)"
- Bold the key message: **"Algorithms work; forecasts need improvement"**

### Chart Style
- **Horizontal bars** (easier to label strategy names)
- **Clear significance markers** (✓ for significant, "ns" for not significant)
- **Sensitivity chart** shows upward slope = opportunity for forecast improvement

---

## Key Story Elements

### The Honest Narrative

1. **What We Built**: Comprehensive trading strategy framework based on academic research
2. **What Works**: Smart algorithms deliver significant, production-ready value
3. **What Doesn't (Yet)**: Forecast integration shows promise but needs accuracy improvement
4. **The Opportunity**: Clear path to 4x ROI increase through forecast quality improvement

### Why This Story Works

- **Honest**: Doesn't oversell forecast value when data doesn't support it
- **Positive**: Shows algorithms are production-ready NOW
- **Future-focused**: Identifies clear improvement path (forecasts)
- **Data-driven**: Statistical significance gives credibility
- **Complete**: Shows breadth of testing (10 strategies × 6 accuracy levels × 7 years)

---

## Alternative Slide Layouts

### Option 1: Waterfall Chart (Executive Audience)

**Single powerful visual showing value decomposition:**

```
           Naive          Algorithm         Forecasts        Final
           $50K           Design            Integration      $63K
            │             +$12K             +$1K             │
            ▼              ▲                 ▲               ▼
           ████          ████████            █               ████████

                         92% of gain        8% of gain
                         (Significant)      (Not sig.)
```

**Annotations:**
- "Algorithm Design: Market research + optimization (p < 0.001)"
- "Forecast Integration: Limited by forecast accuracy (p > 0.05)"
- "Future: Better forecasts → 5-8% more gain"

### Option 2: Two-Chart Layout (Academic Audience)

**Top Chart:** Strategy comparison bar chart (as above)

**Bottom Chart:** Paired comparison showing significance
```
Paired Differences (Prediction - Baseline)
      ↑
 $5K  │          ●
      │
 $0   │═══════════════════════ No difference
      │                    ●
-$5K  │    ●           ●
      │
      └───────────────────────→ Strategy Pair
         PT    MA    EV    RA

95% Confidence Intervals
(None cross zero = would be significant)
```

---

## Testing the Narrative

### Questions This Slide Should Answer

1. ✅ "What trading strategies did you test?"
   → 10 strategies: 4 baselines from research, 6 forecast-enhanced

2. ✅ "Do smart algorithms help?"
   → Yes! 18-22% improvement, highly significant

3. ✅ "Do forecasts help?"
   → Marginally (+1-2%), not statistically significant yet

4. ✅ "What's the opportunity?"
   → Improve forecast accuracy 75%→90% = 4x more value

5. ✅ "What's production-ready?"
   → Algorithms are ready now; forecasts need improvement

---

## Next Steps After Creating Slide

1. **Run backtests** with updated production strategies
2. **Extract real numbers** using data extraction code above
3. **Replace placeholders** in slide with actual results
4. **Run statistical validation** to get p-values
5. **Create sensitivity chart** with real accuracy levels
6. **Finalize visual design** using color coding recommendations
7. **Practice presentation** with speaker notes timing

---

## Files Referenced

- `01_synthetic_predictions_v8.ipynb` - Generate accuracy levels
- `05_strategy_comparison.ipynb` - Run backtests
- `06_statistical_validation.ipynb` - Get p-values
- `08_sensitivity_analysis.ipynb` - Accuracy sensitivity
- `production/strategies/` - Latest strategy implementations
- `production/run_backtest_workflow.py` - Automated testing

---

**Last Updated:** 2024-12-04
**Status:** ⚠️ TEMPLATE with PLACEHOLDER data - All numbers must be replaced with actual backtest results
**Next Action:** Run backtests after AWS account unlocked

---

## Academic Citations - VERIFIED REFERENCES

**All academic citations in this document have been updated to use verified references.**

For complete bibliographic information, see:
- **`docs/ACADEMIC_REFERENCES_BIBLIOGRAPHY.md`** - Complete citations in APA and BibTeX format
- **`docs/STRATEGY_ACADEMIC_REFERENCES.md`** - Detailed strategy-by-strategy analysis

### Quick Reference Card:

| Strategy | Citation |
|----------|----------|
| Price Threshold / Moving Average | Marshall, B. R., Cahan, R. H., & Cahan, J. M. (2008). Journal of Banking & Finance, 32(9), 1810-1819. |
| Technical Indicators (RSI, ADX) | Wilder, J. Welles (1978). New Concepts in Technical Trading Systems. |
| Expected Value | Williams, J. C., & Wright, B. D. (1991). Storage and Commodity Markets. Cambridge University Press. |
| Consensus | Clemen, R. T. (1989). International Journal of Forecasting, 5(4), 559-583. |
| Risk-Adjusted | Markowitz, H. (1952). Journal of Finance, 7(1), 77-91. **[Nobel Prize]** |
| Rolling Horizon MPC | Secomandi, N. (2010). Management Science, 56(3), 449-467. |

**All citations verified via web search 2024-12-04.**
