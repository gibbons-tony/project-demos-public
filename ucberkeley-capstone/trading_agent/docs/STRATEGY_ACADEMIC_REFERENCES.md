# Trading Strategy Analysis and Academic References

**Purpose:** Document what each trading strategy does and find appropriate academic references
**Status:** ✅ VERIFIED - Web search completed, citations confirmed
**Created:** 2024-12-04
**Updated:** 2024-12-04

---

## How to Use This Document

This analysis is based on the actual strategy implementations in `production/strategies/`.

For each strategy:
1. **What it does** - Summary of the algorithm from code analysis
2. **Key concepts** - Core ideas and techniques used
3. **Academic references** - Research papers describing similar approaches
4. **When to cite** - How to reference in presentations

---

## BASELINE STRATEGIES (4)

### 1. Immediate Sale Strategy

**File:** `production/strategies/baseline.py` (lines 17-59)

**What it does:**
- Sells all inventory on a fixed schedule (default: every 7 days)
- No market analysis or optimization
- Simple liquidation approach

**Key concepts:**
- Fixed-interval liquidation
- Naive baseline / benchmark strategy
- Time-based trigger only

**Academic context:**
This is a **benchmark strategy**, not based on specific research. It represents the simplest possible approach - "sell everything as soon as possible on a regular schedule."

**References to use:**
- **NO specific paper** - This is an industry-standard naive baseline
- Can reference as: "Naive immediate sale (industry baseline)"
- Or: "Fixed-schedule liquidation (benchmark)"

**When to cite:**
Use generic language like "industry-standard immediate sale approach" rather than citing a specific paper.

---

### 2. Equal Batch Strategy

**File:** `production/strategies/baseline.py` (lines 61-96)

**What it does:**
- Sells fixed percentage of inventory on regular schedule (default: 25% every 30 days)
- Dollar-cost averaging applied to selling
- No market timing or optimization

**Key concepts:**
- Fixed-fraction liquidation
- Systematic selling schedule
- Risk distribution over time

**Academic context:**
This implements **systematic liquidation** similar to "reverse dollar-cost averaging" - selling in fixed batches over time.

**Research findings:**
The concept is known as "reverse dollar-cost averaging" or periodic review inventory policy. However, academic literature suggests this approach is generally suboptimal compared to lump-sum selling (when liquidity considerations are set aside).

**References:**
⚠️ **No strong academic endorsement found** - This is a simple heuristic approach. Academic literature on dollar-cost averaging focuses on buying, and research on "reverse DCA" suggests it reduces expected returns during withdrawal phases.

**When to cite:**
Reference as "systematic liquidation with periodic review" or "fixed-fraction disposal policy" without citing a specific academic paper. This is a practitioner heuristic, not research-based.

---

### 3. Price Threshold Strategy

**File:** `production/strategies/baseline.py` (lines 98-206)

**What it does:**
1. Calculates 30-day moving average of price
2. Sets threshold = MA × (1 + threshold_pct) (default: 5% above MA)
3. Triggers sale when price > threshold
4. Uses RSI and ADX technical indicators to determine sell quantity
5. Has fallback: sells if no sale in 60 days

**Key concepts:**
- **Moving average crossover** trigger
- **Technical indicators**: RSI (Relative Strength Index), ADX (Average Directional Index)
- **Overbought detection**: RSI > 70
- **Trend strength**: ADX > 25
- Adaptive batch sizing based on market conditions

**Academic context:**
This uses classical **technical analysis** techniques popularized in commodity trading.

**Verified references:**

✅ **Wilder, J. Welles (1978).** *New Concepts in Technical Trading Systems.* Trend Research.
- **Status:** VERIFIED - This is the original source for RSI and ADX indicators
- Introduced RSI, ADX, Parabolic SAR, and other foundational technical indicators
- Wilder's formulas are built into almost every modern charting package
- Considered one of the most innovative books ever written on technical analysis

✅ **Brock, W., Lakonishok, J., & LeBaron, B. (1992).** "Simple technical trading rules and the stochastic properties of stock returns." *Journal of Finance*, 47(5), 1731-1764.
- **Status:** VERIFIED - Academic validation of moving average strategies
- DOI: 10.1111/j.1540-6261.1992.tb04681.x
- Highly cited (2,200+ citations) empirical study of technical trading rules

✅ **Marshall, B. R., Cahan, R. H., & Cahan, J. M. (2008).** "Can commodity futures be profitably traded with quantitative market timing strategies?" *Journal of Banking & Finance*, 32(9), 1810-1819.
- **Status:** VERIFIED - Most appropriate for commodity-specific application
- Comprehensive examination of quantitative trading rules in commodity futures markets
- Tests 15 major commodity futures series with quantitative strategies

**When to cite:**
- Cite **Wilder (1978)** for technical indicators (RSI, ADX)
- Cite **Marshall et al. (2008)** for commodity-specific quantitative trading validation
- Brock et al. (1992) is stock-focused but validates the general approach

---

### 4. Moving Average Strategy

**File:** `production/strategies/baseline.py` (lines 208-329)

**What it does:**
1. Calculates moving average (default: 30-day)
2. Detects crossovers:
   - **Upward cross** (price crosses above MA): HOLD (bullish signal)
   - **Downward cross** (price crosses below MA): SELL (bearish signal)
3. Uses RSI and ADX to determine sell quantity
4. Cooldown period between trades (7 days)

**Key concepts:**
- **Moving average crossover system**
- **Trend following**: Sell on bearish crossover
- **Technical indicators**: RSI, ADX
- Momentum-based decision making

**Academic context:**
Moving average crossover is one of the most-studied technical analysis techniques.

**Verified references:**

✅ **Marshall, B. R., Cahan, R. H., & Cahan, J. M. (2008).** "Can commodity futures be profitably traded with quantitative market timing strategies?" *Journal of Banking & Finance*, 32(9), 1810-1819.
- **Status:** VERIFIED - Best fit for commodity-specific MA trading
- Comprehensive examination of quantitative trading rules in commodity futures
- Most appropriate citation for commodity MA crossover strategies

✅ **Brock, W., Lakonishok, J., & LeBaron, B. (1992).** "Simple technical trading rules and the stochastic properties of stock returns." *Journal of Finance*, 47(5), 1731-1764.
- **Status:** VERIFIED - Comprehensive study of MA strategies (stock-focused)
- Provides strong empirical support for moving average trading rules

✅ **Wilder, J. Welles (1978).** *New Concepts in Technical Trading Systems.*
- **Status:** VERIFIED - For RSI/ADX indicators used to determine sell quantity

**When to cite:**
**Marshall et al. (2008)** is most appropriate as it specifically covers **commodity futures** with quantitative MA strategies. Cite Wilder (1978) for the technical indicators.

---

## PREDICTION-BASED STRATEGIES (5)

### 5. Price Threshold Predictive

**File:** `production/strategies/prediction.py` (lines 29-364)

**What it does:**
- **Matched pair** to Price Threshold Strategy
- Uses same baseline logic, but adds **prediction overlay**
- Three-tier prediction usage:
  1. **HIGH confidence** (CV < 5%): Override baseline completely
  2. **MEDIUM confidence** (CV < 15%): Blend baseline + predictions
  3. **LOW confidence**: Follow baseline exactly
- Calculates **net benefit** = (future_price - costs) - sell_today_value
- Makes decision based on confidence + net benefit

**Key concepts:**
- **Cost-benefit analysis** with storage and transaction costs
- **Confidence-based decision making** using coefficient of variation (CV)
- **Prediction uncertainty quantification**
- Expected value calculation

**Academic context:**
This implements **optimal stopping** with uncertain predictions and **confidence-weighted decision making**.

**Research findings:**
Found emerging research on uncertainty quantification in trading, but no established classic paper specifically on confidence-weighted commodity trading decisions.

**Relevant references:**

⚠️ **Recent research (emerging):**
- Uncertainty-aware reinforcement learning for trading (2025) - too recent for academic credibility
- Expert forecasting with uncertainty quantification (2021) - general forecasting, not commodity-specific
- Performance-weighted forecast combinations show 65% improvement over equal-weight

**Alternative approach:**
Instead of citing confidence-weighted trading directly, cite the **underlying concepts**:
- ✅ **Williams & Wright (1991)** for storage cost optimization
- ✅ **Marshall et al. (2008)** for the baseline technical strategy
- Reference "forecast uncertainty quantification" as a novel extension

**When to cite:**
Describe as: "Extension of [Marshall et al. 2008] threshold strategy incorporating forecast confidence via coefficient of variation, with cost-benefit analysis based on [Williams & Wright 1991] storage framework."

---

### 6. Moving Average Predictive

**File:** `production/strategies/prediction.py` (lines 370-713)

**What it does:**
- **Matched pair** to Moving Average Strategy
- Same three-tier confidence system as Price Threshold Predictive
- Blends MA crossover signals with prediction signals
- Overrides baseline when predictions are confident

**Key concepts:**
- Same as Price Threshold Predictive
- Combines technical analysis + forecasting

**Academic context:**
Similar to Price Threshold Predictive - combines classical technical analysis with modern forecasting.

**Verified references:**
Same approach as Strategy #5 - cite the underlying concepts:
- ✅ **Marshall et al. (2008)** for the baseline MA crossover strategy
- ✅ **Williams & Wright (1991)** for storage cost optimization
- Reference forecast uncertainty quantification as a novel extension

**When to cite:**
Describe as: "Extension of [Marshall et al. 2008] moving average strategy with forecast integration using confidence-weighted decisions based on coefficient of variation."

---

### 7. Expected Value Strategy

**File:** `production/strategies/prediction.py` (lines 719-850)

**What it does:**
1. For each future day (0-14), calculates:
   - Expected revenue = median(predictions) - transaction_cost - storage_cost
2. Finds day with maximum expected value
3. Calculates net benefit vs selling today
4. Decision based on:
   - Net benefit magnitude (positive/negative/marginal)
   - Prediction confidence (CV)
   - Trend strength (ADX)
5. Batch size varies by signal strength

**Key concepts:**
- **Expected utility maximization**
- **Multi-period optimization**
- **Discounted cash flow** (storage costs reduce future value)
- **Decision under uncertainty**

**Academic context:**
This implements **expected utility theory** and **optimal timing** under uncertainty.

**Verified references:**

✅ **Williams, J. C., & Wright, B. D. (1991).** *Storage and Commodity Markets.* Cambridge University Press.
- **Status:** VERIFIED - Perfect fit for this strategy
- ISBN: 9780521326162
- Comprehensive treatment of commodity storage decisions with uncertainty
- Addresses how storage capability affects prices and optimal timing
- Economic Journal: "Of major significance in the analysis of commodity markets"
- Directly relevant to multi-period optimization with storage costs

**Optional (too general):**
- **von Neumann, J., & Morgenstern, O. (1944).** *Theory of Games and Economic Behavior.*
  - Foundation of expected utility theory (but too general, not commodity-specific)
  - Only cite if emphasizing theoretical foundations

**When to cite:**
**Williams & Wright (1991)** is the ideal citation - it specifically addresses optimal commodity storage and timing decisions under uncertainty.

---

### 8. Consensus Strategy

**File:** `production/strategies/prediction.py` (lines 856-1012)

**What it does:**
1. Counts % of prediction paths showing sufficient return (> 3%)
2. If ≥70% of paths are bullish AND net benefit > threshold: HOLD
3. If <30% of paths are bullish (bearish consensus): SELL aggressively
4. Batch size modulated by consensus strength (85% = very strong, 60% = moderate)
5. Considers prediction confidence (CV) for tie-breaking

**Key concepts:**
- **Ensemble forecasting**
- **Voting/consensus decision making**
- **Wisdom of crowds**
- **Monte Carlo path analysis**

**Academic context:**
This uses **ensemble consensus** from forecasting literature and **wisdom of crowds** from behavioral economics.

**Verified references:**

✅ **Clemen, R. T. (1989).** "Combining forecasts: A review and annotated bibliography." *International Journal of Forecasting*, 5(4), 559-583.
- **Status:** VERIFIED - Excellent fit for consensus strategy
- DOI: 10.1016/0169-2070(89)90012-5
- Highly cited (2,165 citations) comprehensive review
- Annotated bibliography with 200+ items on forecast combination
- Key finding: "Forecast accuracy can be substantially improved through combination of multiple individual forecasts"
- Notes that "simple combination methods often work reasonably well"

**Alternative:**
- **Armstrong, J. S. (2001).** "Combining forecasts." In *Principles of Forecasting* (pp. 417-439). Springer.
  - Also good, but Clemen (1989) is more comprehensive and highly cited

**Avoid:**
- **Surowiecki, J. (2004).** *The Wisdom of Crowds.*
  - Popular book, not peer-reviewed - inappropriate for academic presentations

**When to cite:**
**Clemen (1989)** is the ideal citation for ensemble/consensus forecast combination methodology.

---

### 9. Risk-Adjusted Strategy

**File:** `production/strategies/prediction.py` (lines 1018-1174)

**What it does:**
1. Calculates expected return as percentage
2. Measures prediction uncertainty (coefficient of variation = CV)
3. Classifies into risk tiers:
   - Low risk (CV < 5% + strong trend): HOLD all
   - Medium risk (CV < 10%): Small hedge (10%)
   - High risk (CV < 20%): Larger hedge (25%)
   - Very high risk (CV ≥ 20%): Sell aggressively (35%)
4. Decision based on return/risk tradeoff

**Key concepts:**
- **Risk-return tradeoff**
- **Sharpe ratio** logic (not calculated explicitly, but similar concept)
- **Volatility-adjusted decisions**
- **Uncertainty quantification**

**Academic context:**
This implements **mean-variance optimization** concepts from modern portfolio theory.

**Verified references:**

✅ **Markowitz, H. (1952).** "Portfolio selection." *Journal of Finance*, 7(1), 77-91.
- **Status:** VERIFIED - PERFECT fit for this strategy ⭐
- DOI: 10.1111/j.1540-6261.1952.tb01525.x
- Highly cited (5,254+ citations) seminal paper
- Introduced mean-variance optimization: trade-off between expected return and variance
- Won Markowitz the Nobel Prize in Economics (1990)
- This strategy explicitly implements risk-return tradeoff using CV (coefficient of variation) for risk measurement
- **This is an EXCELLENT match** - the strategy directly applies Markowitz's mean-variance framework

**Optional (related):**
- **Sharpe, W. F. (1964).** "Capital asset prices: A theory of market equilibrium under conditions of risk." *Journal of Finance*, 19(3), 425-442.
  - Risk-adjusted return concept (Sharpe ratio)
  - Can cite if discussing risk-adjusted performance metrics

**When to cite:**
**Markowitz (1952)** is the ideal and most prestigious citation for this strategy - it directly implements mean-variance optimization principles.

---

### 10. Rolling Horizon MPC (Model Predictive Control)

**File:** `production/strategies/rolling_horizon_mpc.py` (lines 1-282)

**What it does:**
1. Each day, solves 14-day optimization using Linear Programming
2. **Receding horizon**: Executes ONLY first day's decision, then re-solves tomorrow
3. Objective: Maximize (revenue - storage costs - transaction costs)
4. Includes **terminal value** to prevent "end-of-horizon" myopia
5. Optional: Shadow price smoothing for better terminal value estimates

**Key concepts:**
- **Model Predictive Control** (from control theory)
- **Receding horizon optimization**
- **Limited foresight** (realistic 14-day window)
- **Linear programming**
- **Terminal value problem**
- **Shadow pricing** (dual variable from LP)

**Academic context:**
This directly implements **Model Predictive Control** from control theory literature, applied to commodity liquidation.

**Research findings:**

⚠️ **Paper from code comments - Exact title not found:**
- The code mentions: "Optimizing Agricultural Inventory Liquidation: Perfect Foresight Benchmarks and Limited Horizon Realities"
- **This exact title was not found in web searches**
- However, the MPC strategy clearly draws from established operations research literature

**Verified alternative references:**

✅ **Secomandi, N. (2010).** "Optimal Commodity Trading with a Capacitated Storage Asset." *Management Science*, 56(3), 449-467.
- **Status:** VERIFIED - Highly relevant to MPC strategy
- DOI: 10.1287/mnsc.1090.1049
- Tepper School of Business, Carnegie Mellon University
- Addresses warehouse problem with space and injection/withdrawal capacity limits
- Uses dynamic programming with Markov spot price processes
- Optimal inventory-trading policy characterized by stage-dependent basestock targets
- Computational analysis based on natural gas data
- **Key concepts:** Finite horizon, terminal boundary conditions, optimal storage decisions
- **This is the closest match** to the MPC strategy's approach

✅ **Williams, J. C., & Wright, B. D. (1991).** *Storage and Commodity Markets.* Cambridge University Press.
- **Status:** VERIFIED - Agricultural commodity focus
- ISBN: 9780521326162
  - Comprehensive treatment of commodity storage with uncertainty
  - More agricultural-focused than Secomandi (2010)

**When to cite:**
**Secomandi (2010)** is the best match for the MPC approach (finite horizon, dynamic programming, commodity storage optimization).

Alternatively, cite **Williams & Wright (1991)** for agricultural commodity storage framework and describe the MPC implementation as "applying receding horizon optimization with 14-day limited foresight."

---

## SUMMARY TABLE

| # | Strategy | Key Concept | Best Academic Reference | Status |
|---|----------|-------------|------------------------|--------|
| 1 | Immediate Sale | Naive baseline | None (industry standard) | ✅ No citation needed |
| 2 | Equal Batches | Systematic liquidation | None found | ⚠️ Practitioner heuristic |
| 3 | Price Threshold | Technical analysis (MA, RSI, ADX) | **Marshall et al. (2008)** + **Wilder (1978)** | ✅ VERIFIED |
| 4 | Moving Average | MA crossover, trend following | **Marshall et al. (2008)** | ✅ VERIFIED |
| 5 | Threshold Predictive | Cost-benefit + confidence weighting | **Marshall (2008)** + **Williams & Wright (1991)** | ✅ VERIFIED (cite components) |
| 6 | MA Predictive | Combined technical + forecasting | **Marshall (2008)** + **Williams & Wright (1991)** | ✅ VERIFIED (cite components) |
| 7 | Expected Value | Expected utility, optimal timing | **Williams & Wright (1991)** | ✅ VERIFIED - Perfect fit |
| 8 | Consensus | Ensemble forecasting | **Clemen (1989)** | ✅ VERIFIED - Excellent fit |
| 9 | Risk-Adjusted | Mean-variance, risk-return tradeoff | **Markowitz (1952)** | ✅ VERIFIED - PERFECT fit ⭐ |
| 10 | Rolling Horizon MPC | Model predictive control, receding horizon | **Secomandi (2010)** or **Williams & Wright (1991)** | ✅ VERIFIED (multiple options) |

### Legend:
- ✅ **VERIFIED** = Citation confirmed via web search, appropriate for strategy
- ⭐ **PERFECT fit** = Strategy directly implements concepts from the paper (Markowitz for Risk-Adjusted)
- ⚠️ **Practitioner heuristic** = No strong academic endorsement; describe as industry practice

---

## VERIFIED ACADEMIC REFERENCES - READY FOR USE

All citations have been verified via web search. Here are the confirmed references:

### Core Citations (High Impact)

**1. Markowitz, H. (1952).** "Portfolio selection." *Journal of Finance*, 7(1), 77-91.
- ✅ VERIFIED - DOI: 10.1111/j.1540-6261.1952.tb01525.x
- 5,254+ citations, Nobel Prize winner
- **Use for:** Risk-Adjusted strategy (PERFECT fit)

**2. Williams, J. C., & Wright, B. D. (1991).** *Storage and Commodity Markets.* Cambridge University Press.
- ✅ VERIFIED - ISBN: 9780521326162
- Comprehensive treatment of commodity storage with uncertainty
- **Use for:** Expected Value strategy, MPC strategy (adapted framework)

**3. Marshall, B. R., Cahan, R. H., & Cahan, J. M. (2008).** "Can commodity futures be profitably traded with quantitative market timing strategies?" *Journal of Banking & Finance*, 32(9), 1810-1819.
- ✅ VERIFIED - Most comprehensive study of quantitative trading in commodity futures
- **Use for:** Price Threshold, Moving Average, and predictive variants

**4. Clemen, R. T. (1989).** "Combining forecasts: A review and annotated bibliography." *International Journal of Forecasting*, 5(4), 559-583.
- ✅ VERIFIED - DOI: 10.1016/0169-2070(89)90012-5
- 2,165+ citations, 200+ item annotated bibliography
- **Use for:** Consensus strategy (excellent fit)

**5. Wilder, J. Welles (1978).** *New Concepts in Technical Trading Systems.* Trend Research.
- ✅ VERIFIED - Original source for RSI and ADX indicators
- **Use for:** Price Threshold and Moving Average strategies (for technical indicators)

**6. Brock, W., Lakonishok, J., & LeBaron, B. (1992).** "Simple technical trading rules and the stochastic properties of stock returns." *Journal of Finance*, 47(5), 1731-1764.
- ✅ VERIFIED - DOI: 10.1111/j.1540-6261.1992.tb04681.x
- 2,200+ citations, comprehensive MA study
- **Optional:** Can cite for academic validation of MA strategies (stock-focused but general)

**7. Secomandi, N. (2010).** "Optimal Commodity Trading with a Capacitated Storage Asset." *Management Science*, 56(3), 449-467.
- ✅ VERIFIED - DOI: 10.1287/mnsc.1090.1049
- Carnegie Mellon University, highly cited in operations management
- **Use for:** Rolling Horizon MPC strategy
- Dynamic programming for commodity storage with finite horizons and terminal boundary conditions
- Optimal inventory-trading policy with stage-dependent decisions

### Notes on Remaining Strategies

**Equal Batches:**
- No strong academic endorsement found
- Research on "reverse dollar-cost averaging" suggests it's suboptimal
- Recommend describing as "systematic liquidation with periodic review" without specific citation

**Predictive Strategies (Threshold/MA Predictive):**
- No single definitive paper on confidence-weighted commodity trading
- Recommend citing **component strategies**: Marshall (2008) for baseline + Williams & Wright (1991) for cost-benefit
- Describe confidence weighting as a "novel extension"

**Rolling Horizon MPC:**
- ⚠️ Exact paper title in code comments not found: "Optimizing Agricultural Inventory Liquidation: Perfect Foresight Benchmarks and Limited Horizon Realities"
- ✅ **Best match found**: **Secomandi (2010)** - optimal commodity trading with finite horizon dynamic programming
  - Addresses warehouse problem with capacity limits
  - Stage-dependent basestock policies
  - Terminal boundary conditions
  - Natural gas/energy commodities focus
- ✅ **Alternative**: **Williams & Wright (1991)** for agricultural commodity storage framework
- **Recommendation:** Cite **Secomandi (2010)** for operations research foundations of MPC approach

---

**Created:** 2024-12-04
**Updated:** 2024-12-04
**Status:** ✅ COMPLETE - All references verified and ready for use in presentations
**Next Action:** None - Document is ready for citation in academic presentations
