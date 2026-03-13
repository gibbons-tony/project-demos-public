# Academic References - Complete Bibliography

**Purpose:** Complete bibliographic information for all academic papers referenced in trading strategies
**Created:** 2024-12-04
**Status:** ✅ VERIFIED - All citations confirmed via web search

---

## Complete Citations (APA Style)

### 1. Portfolio Theory and Risk Management

**Markowitz, H. (1952).** Portfolio selection. *Journal of Finance*, 7(1), 77-91.
**DOI:** 10.1111/j.1540-6261.1952.tb01525.x
**Citations:** 5,254+
**Used for:** Risk-Adjusted strategy
**Notes:** Nobel Prize-winning paper (1990). Foundation of mean-variance optimization and modern portfolio theory. PERFECT fit for Risk-Adjusted strategy which explicitly implements risk-return tradeoff using coefficient of variation.

---

### 2. Commodity Storage and Optimal Timing

**Williams, J. C., & Wright, B. D. (1991).** *Storage and commodity markets.* Cambridge University Press.
**ISBN:** 9780521326162
**Publisher:** Cambridge University Press, March 29, 1991
**Pages:** 502
**Used for:** Expected Value strategy, Rolling Horizon MPC strategy (alternative)
**Notes:** Comprehensive treatment of commodity storage decisions with uncertainty. Addresses how storage capability affects prices and optimal timing. Economic Journal described it as "of major significance in the analysis of commodity markets" and "required reading for all students of agricultural economics."

---

### 3. Commodity Futures and Quantitative Trading

**Marshall, B. R., Cahan, R. H., & Cahan, J. M. (2008).** Can commodity futures be profitably traded with quantitative market timing strategies? *Journal of Banking & Finance*, 32(9), 1810-1819.
**DOI:** (Available through ScienceDirect)
**Used for:** Price Threshold strategy, Moving Average strategy, and their predictive variants
**Notes:** Most comprehensive examination of quantitative trading rules in commodity futures markets. Tests 15 major commodity futures series. Most appropriate citation for commodity-specific quantitative MA strategies. Note: Authors report that 14 out of 15 commodities fail to generate statistically significant profits after adjustment for data-snooping bias.

---

### 4. Forecast Combination and Ensemble Methods

**Clemen, R. T. (1989).** Combining forecasts: A review and annotated bibliography. *International Journal of Forecasting*, 5(4), 559-583.
**DOI:** 10.1016/0169-2070(89)90012-5
**Citations:** 2,165+
**Used for:** Consensus strategy
**Notes:** Comprehensive review with 200+ item annotated bibliography. Key finding: "Forecast accuracy can be substantially improved through combination of multiple individual forecasts." Also notes that "simple combination methods often work reasonably well relative to more complex combinations." Ideal citation for ensemble/consensus forecast combination methodology.

---

### 5. Technical Trading Indicators

**Wilder, J. Welles (1978).** *New concepts in technical trading systems.* Trend Research.
**Pages:** 142
**Used for:** Price Threshold strategy, Moving Average strategy (for RSI and ADX indicators)
**Notes:** Original source for Relative Strength Index (RSI), Average Directional Index (ADX), Parabolic SAR, Average True Range (ATR), and other foundational technical indicators. Considered one of the most innovative books ever written on technical analysis. Wilder's formulas are built into almost every modern charting package. Still among bestsellers 40+ years after publication without updates.

---

### 6. Technical Trading Rules (Academic Validation)

**Brock, W., Lakonishok, J., & LeBaron, B. (1992).** Simple technical trading rules and the stochastic properties of stock returns. *Journal of Finance*, 47(5), 1731-1764.
**DOI:** 10.1111/j.1540-6261.1992.tb04681.x
**Citations:** 2,200+
**Used for:** Moving Average strategy (optional - provides academic validation)
**Notes:** Highly cited empirical study of technical trading rules using Dow Jones Index from 1897 to 1986. Tests moving average and trading range break rules. Provides strong support for technical strategies - returns not consistent with random walk, AR(1), GARCH-M, or Exponential GARCH models. Stock-focused but validates general approach.

---

### 7. Model Predictive Control and Commodity Storage

**Secomandi, N. (2010).** Optimal commodity trading with a capacitated storage asset. *Management Science*, 56(3), 449-467.
**DOI:** 10.1287/mnsc.1090.1049
**Author affiliation:** Tepper School of Business, Carnegie Mellon University, Pittsburgh, Pennsylvania
**Used for:** Rolling Horizon MPC strategy
**Notes:** Addresses the warehouse problem with both space and injection/withdrawal capacity limits - foundational problem in merchant management of storage assets for commodities (energy sources, natural resources). Shows that optimal inventory-trading policy of risk-neutral merchant is characterized by two stage and spot-price dependent basestock targets. Under certain assumptions, these targets are monotone in spot price and partition the inventory/spot-price space into three regions: buy and inject, do nothing, or withdraw and sell. Computational analysis based on natural gas data shows mismanaging the trading-operations interface can yield significant value losses. **This is the closest match to the MPC strategy's approach** with finite horizon, terminal boundary conditions, and optimal storage decisions.

---

## Strategy-to-Citation Mapping

| Strategy | Primary Citation(s) | Citation Quality |
|----------|-------------------|------------------|
| 1. Immediate Sale | None (naive baseline) | N/A - No citation needed |
| 2. Equal Batches | None found | ⚠️ Practitioner heuristic only |
| 3. Price Threshold | Marshall et al. (2008) + Wilder (1978) | ✅ VERIFIED - Excellent fit |
| 4. Moving Average | Marshall et al. (2008) + Wilder (1978) | ✅ VERIFIED - Excellent fit |
| 5. Threshold Predictive | Marshall (2008) + Williams & Wright (1991) | ✅ VERIFIED - Cite components |
| 6. MA Predictive | Marshall (2008) + Williams & Wright (1991) | ✅ VERIFIED - Cite components |
| 7. Expected Value | Williams & Wright (1991) | ✅ VERIFIED - Perfect fit |
| 8. Consensus | Clemen (1989) | ✅ VERIFIED - Excellent fit |
| 9. Risk-Adjusted | **Markowitz (1952)** | ✅ VERIFIED - PERFECT fit ⭐ |
| 10. Rolling Horizon MPC | **Secomandi (2010)** or Williams & Wright (1991) | ✅ VERIFIED - Multiple options |

---

## BibTeX Format

For LaTeX users, here are the citations in BibTeX format:

```bibtex
@article{Markowitz1952,
  author = {Markowitz, Harry},
  title = {Portfolio Selection},
  journal = {Journal of Finance},
  volume = {7},
  number = {1},
  pages = {77--91},
  year = {1952},
  doi = {10.1111/j.1540-6261.1952.tb01525.x}
}

@book{Williams1991,
  author = {Williams, Jeffrey C. and Wright, Brian D.},
  title = {Storage and Commodity Markets},
  publisher = {Cambridge University Press},
  year = {1991},
  isbn = {9780521326162}
}

@article{Marshall2008,
  author = {Marshall, Ben R. and Cahan, Rochester H. and Cahan, Jared M.},
  title = {Can Commodity Futures be Profitably Traded with Quantitative Market Timing Strategies?},
  journal = {Journal of Banking \& Finance},
  volume = {32},
  number = {9},
  pages = {1810--1819},
  year = {2008}
}

@article{Clemen1989,
  author = {Clemen, Robert T.},
  title = {Combining Forecasts: A Review and Annotated Bibliography},
  journal = {International Journal of Forecasting},
  volume = {5},
  number = {4},
  pages = {559--583},
  year = {1989},
  doi = {10.1016/0169-2070(89)90012-5}
}

@book{Wilder1978,
  author = {Wilder, J. Welles},
  title = {New Concepts in Technical Trading Systems},
  publisher = {Trend Research},
  year = {1978}
}

@article{Brock1992,
  author = {Brock, William and Lakonishok, Josef and LeBaron, Blake},
  title = {Simple Technical Trading Rules and the Stochastic Properties of Stock Returns},
  journal = {Journal of Finance},
  volume = {47},
  number = {5},
  pages = {1731--1764},
  year = {1992},
  doi = {10.1111/j.1540-6261.1992.tb04681.x}
}

@article{Secomandi2010,
  author = {Secomandi, Nicola},
  title = {Optimal Commodity Trading with a Capacitated Storage Asset},
  journal = {Management Science},
  volume = {56},
  number = {3},
  pages = {449--467},
  year = {2010},
  doi = {10.1287/mnsc.1090.1049}
}
```

---

## Citation Guidelines for Presentations

### Academic Presentations (Use Full Citations)

For academic audiences (thesis defense, research seminars, academic conferences):
- Use **full citations** with journal names, volumes, pages
- Include DOI when available
- Mention citation counts for high-impact papers (Markowitz: 5,254+, Clemen: 2,165+)
- Note Nobel Prize for Markowitz (1952)

### Business/Industry Presentations (Use Author-Year)

For business audiences (stakeholder meetings, industry conferences):
- Use **author-year format**: "Based on Markowitz (1952) portfolio optimization framework"
- Emphasize practical relevance over academic credentials
- Mention institutional affiliation for Secomandi (Carnegie Mellon)
- Focus on "research-based" rather than "peer-reviewed"

### Slides (Minimal Citations)

For presentation slides:
- Use **footnotes** or small text at bottom: "[Marshall et al. 2008, J. Banking & Finance]"
- Place full bibliography on final "References" slide
- Use superscript numbers if multiple citations per slide

---

## How to Describe Strategies Without Direct Citations

Some strategies don't have single perfect academic papers. Here's how to describe them:

### Equal Batches Strategy
❌ Don't say: "Based on Chen (2019)" (fabricated)
✅ Do say: "Systematic liquidation with periodic review - a practitioner heuristic approach"

### Predictive Strategies (Threshold/MA Predictive)
❌ Don't say: "Novel confidence-weighted trading method"
✅ Do say: "Extension of Marshall et al. (2008) technical strategies incorporating forecast confidence via coefficient of variation, with cost-benefit analysis based on Williams & Wright (1991) storage framework"

### Rolling Horizon MPC
❌ Don't say: "Based on internal research document"
✅ Do say: "Receding horizon optimization adapted from Secomandi (2010) commodity storage framework with 14-day limited foresight windows"

---

## Additional Academic Context

### Why Some Strategies Lack Citations

**Equal Batches:**
- Reverse dollar-cost averaging concept exists but academic literature suggests it's suboptimal
- No strong academic endorsement for systematic liquidation in fixed batches
- This is a **heuristic approach** used in practice, not research-based

**Confidence-Weighted Predictive:**
- Emerging area (2021-2025 papers found) but no established classic paper
- Concept is sound but too recent for academic credibility in capstone context
- Better to cite **underlying components** (technical analysis + storage optimization)

**MPC Paper from Code Comments:**
- "Optimizing Agricultural Inventory Liquidation: Perfect Foresight Benchmarks and Limited Horizon Realities"
- **This exact title does not exist** in academic databases
- Likely a working paper title, internal document, or placeholder
- Secomandi (2010) found as best published alternative

---

## Verification Status

All citations verified via web search on 2024-12-04:
- ✅ Markowitz (1952) - Verified via Wiley Online Library
- ✅ Williams & Wright (1991) - Verified via Cambridge University Press
- ✅ Marshall et al. (2008) - Verified via ScienceDirect
- ✅ Clemen (1989) - Verified via International Journal of Forecasting
- ✅ Wilder (1978) - Verified via multiple book retailers and academic sources
- ✅ Brock et al. (1992) - Verified via Journal of Finance
- ✅ Secomandi (2010) - Verified via Management Science (INFORMS)

---

**Document Status:** ✅ COMPLETE - Ready for use in academic presentations
**Last Updated:** 2024-12-04
**Maintained by:** Trading Agent Team

For detailed strategy-by-strategy analysis, see `STRATEGY_ACADEMIC_REFERENCES.md`
