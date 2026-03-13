# Root Cause Analysis: Performance Drop from +14.35% to +0.99%

**Date:** 2025-12-11
**Issue:** RollingHorizonMPC strategy performance dropped from +14.35% to +0.99% improvement over baseline
**Impact:** -13.36 percentage point discrepancy between documented and current results

---

## Executive Summary

The +14.35% improvement documented on **Dec 8, 2025** was based on OLD backtest calculations that included unrealized gains from inventory appreciation. On **Dec 10, 2025**, the net_earnings calculation was fundamentally changed to only count REALIZED revenue from sales, causing MPC performance to drop to +0.99%. The new calculation is MORE CONSERVATIVE and arguably more accurate, but represents a different metric than the original documentation.

---

## Timeline of Events

### Dec 8, 2025 - Documentation Written
- **File:** `docs/PRESENTATION_SLIDE_TRADING_RESULTS_REAL_DATA.md`
- **Last Modified:** 2025-12-08 15:20:03
- **Result Documented:** RollingHorizonMPC +14.35% improvement (naive model)
- **Calculation Method:** Portfolio value approach (cash + inventory × current_price)

### Dec 10, 2025 - Three Critical Commits

#### Commit d0e8e97 (20:13) - Net Earnings Calculation Changed
```
Calculate net_earnings from inventory changes and storage costs

- Use available columns: inventory, price, cumulative_storage_cost
- Calculate sales from inventory decreases
- Compute revenue = quantity_sold * price
- Net earnings = cumulative_revenue - cumulative_storage_cost
```

**OLD METHOD (production/analysis/statistical_tests.py):**
```python
daily_df['portfolio_value'] = daily_df['cash'] + (daily_df['inventory'] * daily_df['price'])
initial_capital = daily_df.iloc[0]['cash'] if len(daily_df) > 0 else 0
daily_df['net_earnings'] = daily_df['portfolio_value'] - initial_capital
```

**NEW METHOD:**
```python
daily_df['inventory_change'] = daily_df['inventory'].diff().fillna(0)
daily_df['quantity_sold'] = -daily_df['inventory_change'].clip(upper=0)
daily_df['revenue'] = daily_df['quantity_sold'] * daily_df['price']
daily_df['cumulative_revenue'] = daily_df['revenue'].cumsum()
daily_df['net_earnings'] = daily_df['cumulative_revenue'] - daily_df['cumulative_storage_cost']
```

#### Commit 7896982 (20:16) - Financial Tracking Added
```
Add financial tracking to daily_state in backtest engine

- Track cumulative_revenue and cumulative_transaction_costs throughout simulation
- Calculate cash position (revenue - transaction_costs - storage_costs) for each day
- Add cumulative_revenue, cumulative_transaction_costs, and cash fields to daily_state
```

#### Commit 539d76a (21:18) - Manifest Date Filtering
```
Fix backtest to filter data by manifest date ranges

Expected result: Model comparisons will now show ~15% MPC improvement
instead of the incorrect 7% caused by including invalid years.
```

**Irony:** This commit expected to INCREASE MPC performance to 15%, but the new net_earnings calculation actually DECREASED it to 0.99%.

### Dec 11, 2025 - Tables Regenerated
- **Time:** 2025-12-11 06:42 AM
- **Result:** All coffee results tables regenerated with new calculation
- **Naive MPC Performance:** +0.99% (excluding 2025 incomplete year)

---

## Root Cause: Net Earnings Calculation Change

### Old Calculation (Portfolio Value Approach)
**Formula:** `net_earnings = (cash + inventory × current_price) - initial_capital`

**Characteristics:**
- Includes **unrealized gains** from inventory appreciation
- If coffee price increases from $100 to $150, holding 10 tons shows $500 gain
- Favors strategies that hold inventory during price increases
- Reflects total asset value (mark-to-market accounting)

**Why MPC Showed +14.35%:**
- MPC strategy holds inventory longer waiting for optimal sale prices
- During price increases, unrealized inventory value accumulates
- Even if not sold, inventory appreciation counted as "earnings"

### New Calculation (Realized Revenue Approach)
**Formula:** `net_earnings = cumulative_revenue_from_sales - cumulative_storage_costs`

**Characteristics:**
- Only counts **realized revenue** when inventory is actually sold
- Holding inventory during price increase = $0 revenue until sale
- Subtracts storage costs for holding inventory
- More conservative, cash-flow focused metric

**Why MPC Shows Only +0.99%:**
- MPC holds inventory longer, accumulating more storage costs
- Revenue only realized when inventory is eventually sold
- Storage costs reduce net earnings significantly
- No credit for inventory appreciation until actual sale

---

## Impact Analysis

### Statistical Comparison

| Metric | Old Method (Dec 8) | New Method (Dec 11) | Change |
|--------|-------------------|---------------------|--------|
| Naive MPC | +14.35% | +0.99% | -13.36 pp |
| Accounting | Mark-to-market | Cash flow | Different basis |
| Unrealized gains | Included | Excluded | Methodology |

### Why This Matters

1. **Different Business Questions:**
   - Old: "What's my portfolio worth if I sold everything today?"
   - New: "How much actual cash have I generated from sales?"

2. **MPC Strategy Characteristics:**
   - Holds inventory longer to wait for optimal prices
   - Old method: Rewarded for price timing (even unrealized)
   - New method: Penalized for storage costs while waiting

3. **Baseline Strategy (Immediate Sale):**
   - Sells immediately, minimizing storage costs
   - Old method: Loses unrealized gains from not holding
   - New method: Avoids storage costs, shows better relative performance

---

## Verification: Can We Reproduce Dec 8 Results?

### Option 1: Revert Calculation to Portfolio Value Method
**File:** `production/analysis/statistical_tests.py`
**Location:** Lines 228-237

**Required change:**
```python
# Revert to portfolio value calculation
daily_df['portfolio_value'] = daily_df['cash'] + (daily_df['inventory'] * daily_df['price'])
initial_capital = daily_df.iloc[0]['cash'] if len(daily_df) > 0 else 0
daily_df['net_earnings'] = daily_df['portfolio_value'] - initial_capital
```

**Impact:**
- Will reproduce ~14-15% improvement for naive MPC
- Matches documented results
- But: Changes accounting methodology back to mark-to-market

### Option 2: Check for Old Result Tables
**Tables to check:**
- Look for any tables with Dec 5 or earlier timestamps
- Baseline tables exist from Dec 5: `results_coffee_baseline_year`
- May have snapshot of old calculation results

**Command:**
```sql
DESCRIBE DETAIL commodity.trading_agent.results_coffee_by_year_naive;
-- Check lastModified timestamp
```

### Option 3: Accept New Calculation and Update Documentation
**Rationale:**
- New calculation is more conservative and arguably more accurate
- Reflects actual cash generation, not paper gains
- Better aligns with real-world profitability metrics

**Required action:**
- Update `docs/PRESENTATION_SLIDE_TRADING_RESULTS_REAL_DATA.md`
- Change +14.35% to +0.99%
- Add footnote explaining calculation methodology change
- Document both metrics (portfolio value vs realized revenue)

---

## Git Reversion Feasibility

### Files Modified on Dec 10
1. `production/analysis/statistical_tests.py` (d0e8e97)
2. `production/core/backtest_engine.py` (7896982)
3. `production/runners/data_loader.py` (539d76a)

### Reversion Impact
**Reverting d0e8e97 alone:**
- Restores old net_earnings calculation
- Should reproduce ~14-15% improvement
- Loses new financial tracking features

**Reverting all three commits:**
- Fully restores Dec 8 state
- Loses manifest filtering (may cause other issues)
- Loses financial tracking infrastructure

**Git commands:**
```bash
# Option A: Revert just the calculation change
git revert d0e8e97 --no-commit
git commit -m "Revert net_earnings to portfolio value method"

# Option B: Revert all three commits (not recommended)
git revert 539d76a 7896982 d0e8e97 --no-commit
git commit -m "Revert Dec 10 backtest changes"
```

---

## Data Reversion Feasibility

### Current Table State
- All results tables regenerated Dec 11, 2025 06:42 AM
- Based on new calculation methodology
- Includes manifest filtering

### Reversion Options

#### Option 1: Regenerate with Old Code
```bash
# 1. Revert calculation code
git revert d0e8e97

# 2. Re-run complete analysis
databricks jobs submit --json @jobs/test_complete_analysis.json

# 3. Tables will be regenerated with old calculation
# Expected result: ~14-15% improvement
```

#### Option 2: Check for Backup Tables
```python
# Look for archived tables (if any exist)
SHOW TABLES IN commodity.trading_agent LIKE '*archive*';
SHOW TABLES IN commodity.trading_agent LIKE '*backup*';
SHOW TABLES IN commodity.trading_agent LIKE '*old*';
```

#### Option 3: Use Git History
```bash
# Checkout old version of backtest code
git checkout d0e8e97~1  # One commit before the change

# Run backtest with old code
# Generate new tables with _old_method suffix

# Compare results
```

---

## Recommendations

### Short Term (Today)
1. **Verify findings:** Run backtest with reverted calculation to confirm ~14-15% result
2. **Document discrepancy:** Add this root cause analysis to docs/
3. **Decide on metric:** Choose portfolio value OR realized revenue approach

### Medium Term (This Week)
1. **If reverting:**
   - Git revert d0e8e97
   - Regenerate all result tables
   - Verify documentation matches results

2. **If keeping new calculation:**
   - Update documentation to reflect +0.99% result
   - Add methodology note explaining accounting change
   - Consider tracking BOTH metrics going forward

### Long Term (For Presentation)
1. **Present both metrics:**
   - Portfolio value improvement: +14.35%
   - Realized revenue improvement: +0.99%
   - Explain the difference and business implications

2. **Add financial analysis:**
   - Storage costs as % of revenue
   - Inventory turnover rates by strategy
   - Trade frequency vs holding period analysis

---

## Key Questions for Decision

1. **Which metric matters more for your use case?**
   - Portfolio value (mark-to-market) shows total asset value
   - Realized revenue shows actual cash generation

2. **What does the business need to know?**
   - If selling the business: Portfolio value matters (includes inventory)
   - If evaluating profitability: Realized revenue matters (actual cash)

3. **Presentation strategy:**
   - Show +14.35% (requires reverting calculation)
   - Show +0.99% with better explanation
   - Show both with clear methodology documentation

---

## Technical Details

### Affected Files
```
production/analysis/statistical_tests.py         # Net earnings calculation
production/core/backtest_engine.py               # Financial tracking
production/runners/data_loader.py                # Manifest filtering
docs/PRESENTATION_SLIDE_TRADING_RESULTS_REAL_DATA.md  # Documentation
```

### Affected Tables (All regenerated Dec 11)
```
commodity.trading_agent.results_coffee_naive
commodity.trading_agent.results_coffee_by_year_naive
commodity.trading_agent.results_coffee_by_quarter_naive
commodity.trading_agent.results_coffee_by_month_naive
commodity.trading_agent.results_coffee_sarimax_auto_weather
commodity.trading_agent.results_coffee_xgboost
```

### Key Commits
```
d0e8e97  Calculate net_earnings from inventory changes (Dec 10, 20:13)
7896982  Add financial tracking to daily_state (Dec 10, 20:16)
539d76a  Fix backtest to filter by manifest dates (Dec 10, 21:18)
```

---

## Conclusion

The discrepancy is NOT a bug but a **fundamental methodology change** in how net_earnings is calculated. The old method (portfolio value) showed +14.35% because it included unrealized gains from inventory appreciation. The new method (realized revenue) shows +0.99% because it only counts actual sales and subtracts storage costs.

**The MPC strategy performance depends entirely on which accounting method you use.**

Both methods are valid - they answer different business questions. The decision now is which metric to use for documentation and presentation.
