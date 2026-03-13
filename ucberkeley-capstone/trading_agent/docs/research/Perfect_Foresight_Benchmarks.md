

# **Optimizing Agricultural Inventory Liquidation: Theoretical Frameworks and Algorithmic Solutions**

## **1\. Introduction: The Dual Challenge of Benchmarking and Execution**

The agricultural sector operates at the intersection of biological certainty and market volatility. While the production cycle follows a predictable cadence, the marketing cycle is governed by stochastic price processes that defy simple forecasting. Farmers and commodity producers face a recurrent optimization problem: inventory accumulates during harvest windows, and this stock must be liquidated to maximize profit subject to complex cost structures involving transaction fees and duration-dependent holding costs.

This report addresses this challenge through two distinct but complementary lenses:

1. **The "Oracle" Benchmark (Perfect Foresight):** Establishing the theoretical maximum profit achievable if all future price movements were known. This serves as the rigorous standard for backtesting and quantifying the opportunity cost of uncertainty.  
2. **The "Farmer" Reality (Limited Foresight):** Optimizing decisions when reliable price visibility is restricted to a short window (e.g., 14 days). This section details the algorithms required to bridge the gap between short-term data and long-term value.

---

## **Part I: The Perfect Foresight Benchmark (The Oracle)**

To evaluate any marketing strategy, one must first establish the "ceiling" of possibility. The "Oracle" solution acts as a boundary condition, answering the question: "If we had known exactly when the market would peak and bottom, how much value could our storage infrastructure have captured?"

### **2\. Theoretical Foundations of the Warehouse Problem**

#### **2.1 Historical Evolution: From Cahn to Convexity**

The "Warehouse Problem" was formally introduced by A.S. Cahn in 1948\.1 It poses a fundamental question: Given a warehouse with fixed capacity and an initial stock subject to price variations, what is the optimal pattern of storage and sales? While Bellman (1957) applied Dynamic Programming (DP) to solve this, the "curse of dimensionality" often plagues DP in continuous state spaces.

In the context of inventory that *accumulates* over time, we are modeling a "production-inventory" system where inflow ($H\_t$) is exogenous and outflow ($x\_t$) is discretionary.

#### **2.2 The Deterministic "Oracle" Paradigm**

To find the theoretical maximum, we treat the historical price series not as a random variable, but as a deterministic input vector $P \=$. This transforms the stochastic control problem into a deterministic convex optimization problem.2 This allows for the calculation of "Regret"—the difference between the Oracle's optimal return and the actual strategy's return.

### **3\. Mathematical Formulation: The Linear Programming Paradigm**

Linear Programming (LP) is the gold standard for the perfect foresight problem due to its scalability and ability to handle continuous flow constraints.

#### **3.1 The Objective Function**

The objective is to maximize Total Profit ($Z$), defined as Net Revenue minus Storage Costs. Unlike standard models with fixed costs, we model costs as percentages:

* **Transaction Cost ($c\_{trans}$):** % of gross revenue.  
* **Storage Cost ($c\_{hold}$):** % of inventory value per day.

Total Objective:

$$\\text{Maximize } Z \= \\sum\_{t=1}^{T} \\left\[ P\_t (1 \- c\_{trans}) x\_t \- c\_{hold} P\_t s\_t \\right\]$$

#### **3.2 Constraints**

1. Flow Balance: Inventory at end of day $t$ equals yesterday's inventory plus harvest minus sales.

   $$s\_t \= s\_{t-1} \+ H\_t \- x\_t \\quad \\forall t \= 1, \\dots, T$$  
2. **Non-Negativity:** $x\_t \\ge 0, s\_t \\ge 0$.  
3. **Capacity:** $s\_t \\le S\_{max}$.  
4. **Terminal Condition:** $s\_T \= 0$ (Force full liquidation by end of backtest).

#### **3.3 The Percentage Storage Nuance**

The term $c\_{hold} P\_t s\_t$ introduces a critical dynamic: **High prices increase storage costs.** Holding inventory during a price spike is effectively taxed at a higher rate. This creates a "soft capacity constraint" that incentivizes the algorithm to liquidate aggressively *during* price peaks rather than holding through them.3

### **4\. Geometric Algorithms: The Convex Hull Approach**

While LP provides the numerical solution, Geometric Algorithms offer the intuition. Ideally, inventory should be held only when the price appreciation exceeds the cost of carry.

#### **4.1 Adjusted Prices**

To adapt geometric solutions to percentage-based costs, we transform the price series into "Adjusted Prices" $\\hat{P}\_t$:

$$\\hat{P}\_t \= \\frac{P\_t (1 \- c\_{trans})}{(1 \+ c\_{hold})^t}$$

This discounts future prices by the compounding storage cost.

#### **4.2 The Greatest Convex Minorant (GCM)**

The optimal selling strategy involves finding the **Greatest Convex Minorant** of the cumulative adjusted price curve. Visually, this is akin to stretching a string over the peaks of the price chart.

* **Rule:** Sell exactly when the Adjusted Price touches the "string" (the convex hull).  
* **implication:** Optimality is driven by local maxima in the *storage-adjusted* domain. If the adjusted price is falling, the storage cost is eating profit faster than the market price is rising—indicating a sell signal.4

---

## **Part II: Optimization Under Limited Foresight (The Farmer)**

In reality, a farmer does not see the full price vector $P$. They operate with **Limited Foresight**, typically possessing a reliable forecast for only a short horizon $H$ (e.g., 14 days) within a much longer selling season $T$ (e.g., 180 days).

### **5\. Structural Dynamics of Limited Foresight**

#### **5.1 The Rolling Horizon Mechanism**

This scenario is modeled using **Rolling Horizon Optimization (RHO)**. At day $t$, the agent sees prices for $\[t, t+14\]$. It solves the optimization for this window, executes the decision for day $t$, and then "rolls" the window forward to $t+1$.

#### **5.2 The End-of-Horizon (EoH) Effect**

The critical pathology of limited foresight is the **End-of-Horizon Effect** (or "myopic liquidation"). A naive solver sees the world ending at day $t+14$. To maximize revenue, it will force inventory to zero by day 14, causing premature liquidation at potentially distressed prices.

* **Symptom:** A "sawtooth" inventory profile where stock is dumped at the end of every forecast window.5

### **6\. Resolving Myopia: Terminal Value Engineering**

To prevent myopic liquidation, we must assign a value to the inventory remaining at day $t+14$. The optimization objective becomes:

$$J\_t \= \\sum\_{k=0}^{14} \\text{Revenue}\_{t+k} \+ V\_{term}(s\_{t+14})$$

#### **6.1 Heuristic Approaches**

* **Salvage Value:** Valuing remaining stock at cost. This is often too low, leading to early selling.  
* **Average Price:** Valuing stock at the historical average price. This prevents selling when current prices are below average.7

#### **6.2 Shadow Pricing (Dual Variables)**

A rigorous method uses the **Shadow Price** ($\\lambda$) from the LP solution. The shadow price represents the marginal value of an additional unit of inventory.

* **Method:** Extract the dual variable of the inventory constraint from yesterday's solution. Use this $\\lambda$ to price the terminal inventory for today's optimization.  
* **Smoothing:** Shadow prices can be volatile. Exponential smoothing ($\\bar{\\lambda}\_t \= \\alpha \\lambda\_t \+ (1-\\alpha)\\bar{\\lambda}\_{t-1}$) stabilizes the signal, effectively "learning" the long-term value of holding grain.8

#### **6.3 Approximate Dynamic Programming (ADP)**

ADP attempts to learn the true value function $V(s\_t)$ of the infinite horizon problem. By simulating the 14-day policy repeatedly over historical data, we can train a function approximator (e.g., a neural network or regression model) to predict the future value of inventory based on current price and stock levels. This learned function becomes the $V\_{term}$.9

### **7\. Online Algorithms and Competitive Ratios**

When forecasts are unreliable, **Online Algorithms** provide safety nets.

* **Reservation Price Policy:** Sell only if $P\_t \\ge P^\*(s\_t)$. The threshold $P^\*$ increases as inventory decreases (scarcity) and decreases as the season end approaches (urgency).  
* **Threat-Based Algorithms:** Calculate the minimum sales required to guarantee a specific "Competitive Ratio" against a worst-case future price drop.10

---

## **Part III: Implementation and Benchmarking**

### **8\. Computational Strategy**

We recommend a Python-based stack using **CVXPY** for rigorous convex optimization.

#### **8.1 The "Perfect" Backtest Code (LP)**

This solves the global optimization for the entire history at once.

Python

import cvxpy as cp  
import numpy as np

def solve\_oracle\_inventory(prices, harvest, trans\_cost\_pct, hold\_cost\_pct):  
    """  
    Solves for the global maximum profit with perfect foresight.  
    prices: array of daily prices  
    harvest: array of daily harvest inflow  
    """  
    T \= len(prices)  
    sales \= cp.Variable(T, nonneg=True)  
    inventory \= cp.Variable(T+1, nonneg=True)  
      
    constraints \= \[inventory \== 0, inventory \== 0\]  
    profit\_terms \=  
      
    for t in range(T):  
        \# Flow Balance  
        constraints.append(inventory\[t+1\] \== inventory\[t\] \+ harvest\[t\] \- sales\[t\])  
          
        \# Net Revenue (Revenue \- Transaction Cost)  
        net\_rev \= prices\[t\] \* (1 \- trans\_cost\_pct) \* sales\[t\]  
          
        \# Holding Cost (Based on value of ending inventory)  
        hold\_cost \= prices\[t\] \* hold\_cost\_pct \* inventory\[t+1\]  
          
        profit\_terms.append(net\_rev \- hold\_cost)  
          
    prob \= cp.Problem(cp.Maximize(cp.sum(profit\_terms)), constraints)  
    prob.solve(solver=cp.ECOS)  
      
    return sales.value, inventory.value, prob.value

#### **8.2 The "Limited" Backtest Code (Rolling Loop)**

This simulates the farmer's reality, solving a small LP every day.

Python

def solve\_rolling\_farmer(prices, harvest, horizon=14, term\_decay=0.95):  
    """  
    Simulates daily decisions with 14-day lookahead.  
    """  
    T \= len(prices)  
    realized\_sales \= np.zeros(T)  
    current\_inventory \= 0.0  
      
    for t in range(T):  
        \# Define window end  
        end\_t \= min(t \+ horizon, T)  
        window\_len \= end\_t \- t  
          
        \# Local Optimization Variables  
        local\_sales \= cp.Variable(window\_len, nonneg=True)  
        local\_inv \= cp.Variable(window\_len \+ 1, nonneg=True)  
          
        cons \= \[local\_inv \== current\_inventory\]  
        obj\_terms \=  
          
        for k in range(window\_len):  
            idx \= t \+ k  
            \# Flow constraint  
            \# Note: harvest is known for the window (or estimated)  
            inflow \= harvest\[idx\]   
            cons.append(local\_inv\[k+1\] \== local\_inv\[k\] \+ inflow \- local\_sales\[k\])  
              
            \# Objective  
            rev \= prices\[idx\] \* (1 \- trans\_cost) \* local\_sales\[k\]  
            cost \= prices\[idx\] \* hold\_cost \* local\_inv\[k+1\]  
            obj\_terms.append(rev \- cost)  
              
        \# TERMINAL VALUE CORRECTION  
        \# Valuing remaining inventory at the end of the 14 days  
        \# using a heuristic (e.g., current price discounted) to prevent dumping.  
        terminal\_val \= local\_inv\[window\_len\] \* prices\[end\_t-1\] \* term\_decay  
        obj\_terms.append(terminal\_val)  
          
        \# Solve Local Problem  
        prob \= cp.Problem(cp.Maximize(cp.sum(obj\_terms)), cons)  
        prob.solve(solver=cp.ECOS)  
          
        \# Execute ONLY the first decision (Receding Horizon)  
        decision\_today \= local\_sales.value  
        realized\_sales\[t\] \= decision\_today  
          
        \# Update state for next loop  
        current\_inventory \= current\_inventory \+ harvest\[t\] \- decision\_today  
          
    return realized\_sales

### **9\. Conclusion**

By combining these two models, the user can construct a rigorous "Regret Analysis" framework:

1. **Calculate the Ceiling:** Run the Oracle model to find the absolute maximum profit ($Z\_{opt}$).  
2. **Simulate Reality:** Run the Rolling Horizon model to find the realizable profit ($Z\_{real}$).  
3. **Analyze the Gap:** The difference $Z\_{opt} \- Z\_{real}$ quantifies the cost of limited information.

If the gap is large, the focus should be on improving the **Terminal Value Function** (better long-term valuation). If the gap is small, the strategy is efficient, and further gains can only come from reducing physical costs (transaction/storage fees). This dual approach transforms inventory management from speculative guesswork into a quantitative science.

---

References:

11

#### **Works cited**

1. Technische Universität München Optimal Procurement and Inventory Control in Volatile Commodity Markets, accessed November 25, 2025, [https://d-nb.info/1190818779/34](https://d-nb.info/1190818779/34)  
2. Perfect foresight models \- Stéphane Adjemian, accessed November 25, 2025, [https://stephane-adjemian.fr/dynare/slides/perfect-foresight-models.pdf](https://stephane-adjemian.fr/dynare/slides/perfect-foresight-models.pdf)  
3. The implied convenience yields of precious metals: Safe haven versus industrial usage, accessed November 25, 2025, [http://centerforpbbefr.rutgers.edu/2011PBFEAM/Download/AS/AS-15/2011PBFEAM-092.pdf](http://centerforpbbefr.rutgers.edu/2011PBFEAM/Download/AS/AS-15/2011PBFEAM-092.pdf)  
4. Modular Proximal Optimization for Multidimensional Total-Variation Regularization \- Journal of Machine Learning Research, accessed November 25, 2025, [https://www.jmlr.org/papers/volume19/13-538/13-538.pdf](https://www.jmlr.org/papers/volume19/13-538/13-538.pdf)  
5. Market-based scheduling of energy storage systems: Optimality guarantees \- DTU Research Database, accessed November 25, 2025, [https://orbit.dtu.dk/files/399533245/PhD\_Thesis\_Elea\_Prat.pdf](https://orbit.dtu.dk/files/399533245/PhD_Thesis_Elea_Prat.pdf)  
6. Dynamic horizon selection methodology for model predictive control in buildings, accessed November 25, 2025, [https://www.researchgate.net/publication/362789906\_Dynamic\_horizon\_selection\_methodology\_for\_model\_predictive\_control\_in\_buildings](https://www.researchgate.net/publication/362789906_Dynamic_horizon_selection_methodology_for_model_predictive_control_in_buildings)  
7. An Approximate Dynamic Programming Approach for a Product Distribution Problem, accessed November 25, 2025, [https://people.orie.cornell.edu/huseyin/publications/spatially\_distr\_inv.pdf](https://people.orie.cornell.edu/huseyin/publications/spatially_distr_inv.pdf)  
8. Terminal value: A crucial and yet often forgotten element in timber harvest scheduling and timberland valuation \- Southern Research Station, accessed November 25, 2025, [https://www.srs.fs.usda.gov/pubs/ja/2024/ja\_2024\_henderson\_001.pdf](https://www.srs.fs.usda.gov/pubs/ja/2024/ja_2024_henderson_001.pdf)  
9. Understanding approximate dynamic programming \- Telnyx, accessed November 25, 2025, [https://telnyx.com/learn-ai/approximate-dynamic-programming](https://telnyx.com/learn-ai/approximate-dynamic-programming)  
10. BibTeX bibliography pomacs.bib \- Index of files in /, accessed November 25, 2025, [http://ftp.math.utah.edu/pub/tex/bib/pomacs.html](http://ftp.math.utah.edu/pub/tex/bib/pomacs.html)  
11. A forest of opinions: A multi-model ensemble-HMM voting framework for market regime shift detection and trading \- ResearchGate, accessed November 25, 2025, [https://www.researchgate.net/publication/397111020\_A\_forest\_of\_opinions\_A\_multi-model\_ensemble-HMM\_voting\_framework\_for\_market\_regime\_shift\_detection\_and\_trading](https://www.researchgate.net/publication/397111020_A_forest_of_opinions_A_multi-model_ensemble-HMM_voting_framework_for_market_regime_shift_detection_and_trading)  
12. 1 Introduction \- arXiv, accessed November 25, 2025, [https://arxiv.org/html/2306.11246v3](https://arxiv.org/html/2306.11246v3)  
13. A Computationally Efficient FPTAS for Convex Stochastic Dynamic Programs | SIAM Journal on Optimization \- DSpace@MIT, accessed November 25, 2025, [https://dspace.mit.edu/bitstream/handle/1721.1/116205/13094774x.pdf?sequence=1\&isAllowed=y](https://dspace.mit.edu/bitstream/handle/1721.1/116205/13094774x.pdf?sequence=1&isAllowed=y)