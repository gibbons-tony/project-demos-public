

# **Optimization of Agricultural Inventory Liquidation Under Limited Foresight: Bridging Finite Horizons and Infinite Realities**

## **1\. Introduction: The Information Asymmetry in Inventory Management**

The fundamental challenge in the optimization of agricultural inventory liquidation lies in the temporal disconnect between the decision horizon and the realization of value. In the "Farmer’s Problem," an agent is tasked with liquidating a fixed harvest over a prolonged selling season—spanning potentially 180 days or more—while possessing reliable market information for only a fraction of that time. This scenario, defined as **Limited Foresight**, typically restricts the reliable forecast window to a short horizon, such as 14 days ($H=14$), beyond which price uncertainty renders deterministic planning perilously inaccurate.

While the theoretical baseline of "Perfect Foresight" (the Oracle) allows for the global maximization of revenue by perfectly timing sales at global price peaks, the Limited Foresight agent operates in a regime of "Receding Horizon Control." The agent must optimize decisions for the immediate window $\[t, t+H\]$ while managing the profound uncertainty of the interval $(t+H, T\]$. Without specific correction mechanisms, optimization solvers operating on finite horizons exhibit a structural pathology known as the **End-of-Horizon (EoH) Effect** or "myopic liquidation." By implicitly assuming that the world—or at least the value of the asset—ceases to exist at $t+H$, these solvers systematically undervalue inventory retention, precipitating premature liquidation at distressed prices to capture whatever revenue is available before the horizon closes.1

This report provides an exhaustive analysis of the methodologies required to correct this myopia. We explore the implementation of **Rolling Horizon Optimization (RHO)** and **Model Predictive Control (MPC)** as the structural frameworks for decision-making. We then delve into the rigorous derivation of **Terminal Value Functions ($V\_T$)** using **Shadow Pricing**, **Approximate Dynamic Programming (ADP)**, and **Online Algorithms**. The objective is to engineer a local decision policy that, despite seeing only 14 days ahead, approximates the strategic patience and performance of the infinite-horizon optimal solution.

---

## **2\. The Limited Foresight Scenario: Structural Dynamics**

### **2.1 The Rolling Horizon Mechanism**

The Limited Foresight scenario is best modeled using a Rolling Horizon Optimization (RHO) framework. Unlike a static two-stage stochastic program where decisions are fixed for long periods, RHO is dynamic and iterative. At decision epoch $t$, the agent observes the current state of the system—specifically the inventory level $x\_t$ and the current price $p\_t$—and generates a forecast for the horizon $\\mathcal{H} \= \\{t, t+1, \\dots, t+H-1\\}$.3 The agent solves an optimization problem to maximize revenue over this finite window, implements the first decision $u\_t$, and then "rolls" the horizon forward to $t+1$.1

The defining characteristic of this approach is the discrepancy between the *planning horizon* ($H=14$) and the *execution horizon* ($T=180$). While the rolling mechanism allows the agent to incorporate new information continuously, it suffers from "short-sightedness." Standard RHO implementations often neglect the opportunity cost of selling inventory today versus holding it for the unseen future ($t \> H$). As detailed in recent studies on energy storage and production planning, finite horizons necessitate techniques to explicitly account for the impact of decisions beyond the chosen horizon, otherwise, the system behaves as if the asset has zero value at the boundary constraint.1

### **2.2 The End-of-Horizon (EoH) Effect and Myopic Liquidation**

The most critical failure mode in limited foresight inventory problems is the End-of-Horizon effect. Formally, a standard optimization formulation for period $t$ maximizes the objective function $J\_t$:

$$J\_t \= \\sum\_{k=0}^{H-1} p\_{t+k} \\cdot u\_{t+k} \+ \\Phi(x\_{t+H})$$  
where $u\_{t+k}$ represents the sales quantity and $\\Phi(x\_{t+H})$ represents the terminal value of the remaining inventory. In a naive implementation, $\\Phi(x)$ is often set to zero or a static salvage value. Consequently, the solver perceives any inventory held past day 14 as having no value. The rational mathematical response is to liquidate all stock within the 14-day window, regardless of whether current prices are historically low.6

This results in a "sawtooth" inventory profile where the agent repeatedly builds up and dumps inventory (if production continues) or, in the farmer's liquidation case, sells aggressively in the first few periods of the season. Research indicates that this behavior is not merely sub-optimal but can destroy significant value compared to infinite-horizon policies. For instance, in maritime inventory routing, failing to account for EoH effects leads to empty customer inventories at the end of the planning period, transferring shortages and high costs to subsequent cycles.8 Similarly, in building energy management, a 24-hour horizon without terminal correction leads to avoidable inefficiencies because the thermal mass (inventory) is depleted overnight, requiring expensive reheating the next morning.2

### **2.3 Model Predictive Control (MPC) and Feedback**

Model Predictive Control (MPC) refines RHO by explicitly framing the problem as a feedback control loop. While RHO is a scheduling technique, MPC focuses on system stability and state tracking. In the inventory context, "Economic MPC" is the relevant paradigm, where the objective is economic profit rather than setpoint tracking.9

The standard MPC loop involves:

1. **Measurement:** acquiring the current inventory $x\_t$ and market price $p\_t$.  
2. **Prediction:** estimating future prices $\\hat{p}\_{t+k}$ for $k \\in \[0, H\]$.  
3. **Optimization:** solving the open-loop control problem to find the optimal sales sequence $u^\*\_{t \\dots t+H}$.  
4. **Action:** applying $u^\*\_t$ to the system.  
5. **Feedback:** updating the model state based on realized sales and demand, correcting for any "plant-model mismatch" (e.g., if actual demand differed from the plan).2

The literature emphasizes that MPC's performance is critically dependent on the terminal ingredients: the terminal cost/reward function and the terminal constraint set. Without these, MPC cannot guarantee recursive feasibility or stability. A common error is using a "hard" terminal constraint (e.g., $x\_{t+H} \= 0$), which enforces liquidation. Instead, "soft" terminal penalties or value functions are required to reflect the *continuation value* of the inventory.10

---

## **3\. Engineering the Terminal Value Function**

To prevent myopic liquidation, the optimization problem must be augmented with a Terminal Value Function, $V\_T(x\_{t+H})$, which serves as a proxy for the revenue potential of the remaining inventory over the interval $(t+H, T\]$. This section explores the derivation of this function through heuristic, dual-theoretic, and dynamic programming lenses.

### **3.1 Heuristic Approaches: Salvage and Cost Recovery**

The simplest methods for constructing $V\_T$ rely on static heuristics. While computationally inexpensive, they often fail to capture the dynamic opportunity cost of holding inventory.

* **Salvage Value:** Assigning a fixed price $s$ to terminal inventory, such that $V\_T(x) \= s \\cdot x$. If $s$ is set to the production cost, the solver merely avoids selling at a loss. However, if market prices are consistently above production costs, this undervalues the stock, leading to early sales.12  
* **Average Revenue:** Setting $V\_T(x) \= \\bar{p} \\cdot x$, where $\\bar{p}$ is the historical average price. This prevents selling when $p\_t \< \\bar{p}$ (assuming the solver prefers the guaranteed terminal value). However, this assumes prices revert to the mean within the horizon, which may not hold in trending markets.14  
* **Zero-Inventory Logic:** Some approaches explicitly set the terminal inventory target to zero, assuming the planning horizon covers the relevant cycle. In a 14-day window within a 180-day season, this is catastrophic, effectively decoupling the decision from the true season length.7

### **3.2 Shadow Pricing: The Messenger from the Future**

A more rigorous approach utilizes the **Shadow Price** (or Dual Variable) of the inventory constraint from the optimization itself. In Linear Programming (LP) and convex optimization, the dual variable associated with a resource constraint represents the marginal value of relaxing that constraint—i.e., the value of having one additional unit of inventory.15

#### **3.2.1 Derivation from the Dual**

Consider the inventory balance constraint at the end of the planning horizon ($t+H$). The optimization problem includes a constraint $x\_{t+H} \\ge 0$ (or a safety stock level). The Lagrange multiplier (dual variable) $\\lambda\_{t+H}$ corresponding to this constraint reflects the sensitivity of the optimal objective value to the available inventory.

$$\\lambda\_t \= \\frac{\\partial J^\*}{\\partial x\_t}$$

In a rolling horizon context, the dual variable $\\lambda\_{t+H}$ extracted from the solution at time $t$ can be used to inform the terminal value for the optimization at time $t+1$. Specifically, we can set the terminal value function for the next iteration to be linear in inventory with a slope determined by the shadow price:

$$V\_T(x) \= \\bar{\\lambda} \\cdot x$$

This creates a feedback loop where the "value" of inventory is learned from the optimization's own assessment of scarcity.17

#### **3.2.2 Instability and Smoothing**

A major challenge with raw shadow prices is their volatility. If the solver hits a constraint (e.g., running out of stock), the dual variable can spike to the value of the "Stockout Penalty" or the market price cap. Conversely, if inventory is abundant, the shadow price may drop to zero. This "bang-bang" behavior can cause system nervousness, where the sales strategy oscillates wildly.19  
To mitigate this, smoothing techniques are employed. The effective terminal price $\\bar{\\lambda}\_t$ is updated via exponential smoothing:

$$\\bar{\\lambda}\_t \= (1 \- \\alpha) \\bar{\\lambda}\_{t-1} \+ \\alpha \\lambda\_{current}$$

This stabilizes the signal, providing a consistent "market price" for internal inventory valuation that reflects the long-term trend rather than transient horizon effects.20

### **3.3 Infinite Horizon Approximation via Discount Factors**

An alternative to explicit terminal valuation is the manipulation of the **Discount Factor** ($\\gamma$) to approximate an infinite horizon. A discount factor $\\gamma \< 1$ implies an "Effective Planning Horizon" $T\_{eff} \\approx \\frac{1}{1-\\gamma}$. Even if the solver only sees 14 days explicitly, a discount factor close to 1 (e.g., 0.995) mathematically weights the future heavily, implicitly assuming the process continues.4

There is a direct theoretical equivalence between the discount factor and **Storage Costs**. A high storage cost $h$ makes holding inventory expensive, which is mathematically isomorphic to a high discount rate (low $\\gamma$) that reduces the present value of future sales. Research in consumer choice modeling and inventory control demonstrates that the functional relationship between purchase incidence (sales) and inventory depends on this ratio.22 Therefore, the "Terminal Value" can effectively be engineered by tuning the discount factor or storage cost parameter within the 14-day model. If the storage cost is set artificially low (or the discount factor high), the solver perceives "holding" as a low-cost strategy, naturally pushing inventory toward the terminal state without a distinct penalty function.24

| Terminal Strategy | Mechanism | Pros | Cons |
| :---- | :---- | :---- | :---- |
| **Naive Liquidation** | $\\Phi(x)=0$ | Simple implementation | Catastrophic value destruction |
| **Salvage Value** | $\\Phi(x)=c \\cdot x$ | Prevents loss | Ignores profit potential |
| **Shadow Pricing** | $\\Phi(x)=\\lambda \\cdot x$ | Dynamic, market-aware | Can be unstable/oscillatory |
| **Discounting** | $\\gamma \\to 1$ | Implicit horizon extension | Sensitive to parameter tuning |
| **ADP (VFA)** | $\\Phi(x) \\approx V(x)$ | Theoretically optimal | High computational cost (training) |

Table 1: Comparison of Terminal Value strategies for resolving the End-of-Horizon effect.4

---

## **4\. Approximate Dynamic Programming (ADP)**

While MPC uses local optimization, Approximate Dynamic Programming (ADP) attempts to learn the true value function $V\_t(S\_t)$ of the infinite horizon problem to use as the terminal correction. This effectively breaks the "Curse of Dimensionality" associated with exact Dynamic Programming.26

### **4.1 Value Function Approximation (VFA)**

In the context of the farmer's problem, the state variable $S\_t$ typically includes the current inventory $x\_t$ and the current price $p\_t$. Exact DP is intractable because $x\_t$ is continuous and $p\_t$ is stochastic. ADP replaces the exact value function with an approximation $\\bar{V}\_t(S\_t)$, often parametrized as a linear model, a piecewise linear function, or a neural network.28

For the inventory liquidation problem, a common approximation form is:

$$\\bar{V}\_t(x\_t) \= \\theta\_{t,0} \+ \\theta\_{t,1} x\_t \+ \\theta\_{t,2} x\_t^2$$

Here, $\\theta\_{t,1}$ captures the marginal value (shadow price) and $\\theta\_{t,2}$ captures the diminishing returns of holding excess inventory (saturation). These parameters are learned iteratively. The system simulates the 14-day policy, observes the realized downstream value, and updates $\\theta$ using stochastic gradient descent methods.27

### **4.2 The Post-Decision State Variable**

A critical innovation in ADP for inventory problems is the use of the Post-Decision State ($S^x\_t$). The standard Bellman equation requires computing the expectation of the future value $\\mathbb{E}$, which is computationally expensive inside an optimization loop.  
By defining the state $S^x\_t$ as the inventory after the decision $u\_t$ is made but before the new price $p\_{t+1}$ is revealed, the maximization step becomes deterministic:

$$\\max\_{u\_t} \\left( R(S\_t, u\_t) \+ \\bar{V}\_{t}^{x}(S^x\_t) \\right)$$

This allows the use of standard deterministic solvers (like LP or MILP) for the daily decision, with the "future" encapsulated entirely in the deterministic function $\\bar{V}^x$.27

### **4.3 Double-Loop Learning Algorithms**

Implementing ADP requires a "Double-Loop" architecture:

1. **Outer Loop (Simulation):** The agent plays through the entire 180-day season multiple times.  
2. **Inner Loop (Optimization):** At each step $t$, the agent solves the 14-day limited foresight problem augmented with the current VFA $\\bar{V}\_t(x\_{t+14})$.  
3. Update Step: At the end of each simulation run (or step), the actual value realized from day $t$ onwards is compared to the VFA prediction. The error is used to update the parameters $\\theta$.3  
   This iterative process eventually converges to a value function that accurately predicts the "Long Run" value of inventory, effectively allowing the 14-day solver to "see" the end of the season through the lens of the learned proxy function.32

---

## **5\. Online Algorithms and Threshold Policies**

In scenarios where forecasts are unreliable or the computational burden of MPC/ADP is too high, **Online Algorithms** offer a robust alternative. These approaches make no assumptions about future price distributions, instead optimizing for the "Competitive Ratio"—minimizing the gap between the algorithm's performance and that of an omniscient adversary (Oracle) in the worst-case scenario.33

### **5.1 The Reservation Price Policy**

The most effective online strategy for inventory liquidation is the **Reservation Price** (or Threshold) policy. The agent sets a price floor $p^\*(x\_t, t)$ and sells only if the current market price $p\_t \\ge p^\*$.

* **Inventory Dependence:** As inventory $x\_t$ decreases, the scarcity value increases, raising the reservation price. This prevents "selling cheap" early in the season.  
* **Time Dependence:** As the deadline $T$ approaches, the reservation price must decrease to ensure liquidation. This is the explicit handling of the End-of-Horizon effect—rather than a binary "sell/hold" cliff, the threshold glides down smoothly.35

Analytically, the reservation price can be derived from the ADP value function: $p^\* \\approx \\frac{\\partial V}{\\partial x}$. However, online algorithms provide closed-form formulas for $p^\*$ based on the range of possible prices $\[P\_{min}, P\_{max}\]$ and the remaining time, guaranteeing a performance ratio of at least $O(\\log(P\_{max}/P\_{min}))$.37

### **5.2 Threat-Based Algorithms**

A specific class of online algorithms relevant to the farmer is the **Threat-Based** approach. The algorithm calculates the minimum sales quantity required today to ensure that, even if prices drop to $P\_{min}$ for the remainder of the season, the total revenue will satisfy a specific competitive ratio.

* **Mechanism:** The agent calculates a "threat" scenario (worst-case future). If the current inventory is too high to be liquidated safely in the threat scenario, the agent is forced to sell a portion $u\_t$ immediately, regardless of the current price.  
* **Integration with Limited Foresight:** The 14-day forecast can be used to set the bounds $P\_{min}$ and $P\_{max}$ dynamically. Instead of assuming a global worst case, the threat is calculated based on the *forecasted* worst case, allowing the algorithm to be less conservative when the near-term outlook is positive.34

### **5.3 Inventory Balancing**

Another relevant strategy is Inventory Balancing, derived from the "Online Knapsack" problem. Here, the goal is to allocate limited capacity (inventory) to items (sales opportunities) arriving over time. The "value density" of a sale is the price $p\_t$. The algorithm accepts a trade (sells) if the price exceeds a threshold that is exponential in the fraction of inventory already sold.

$$\\psi(z) \= L \\left( \\frac{U}{L} \\right)^z$$

where $z$ is the fraction of inventory sold, $L$ is the lower price bound, and $U$ is the upper price bound. This simple rule guarantees near-optimal revenue without requiring any complex lookahead or optimization solvers, acting as a powerful heuristic safety net for the MPC controller.39

---

## **6\. Comparative Analysis: Limited Foresight vs. Oracle**

To quantify the impact of these methodologies, we compare the "Limited Foresight" scenario against the "Perfect Foresight" baseline. The Oracle baseline represents the theoretical upper bound, achievable only if the farmer knows the entire price trajectory ($p\_1, \\dots, p\_{180}$) at day 1\.

### **6.1 Baseline: Perfect Foresight (The Oracle)**

The Oracle solves a single, global linear program:

$$\\max \\sum\_{t=1}^{T} p\_t u\_t \\quad \\text{s.t.} \\quad \\sum u\_t \\le X\_{total}$$

* **Behavior:** The Oracle waits patiently for the global price maximums. It holds inventory through minor fluctuations and executes massive sales only at the peaks.  
* **Inventory Profile:** Step function. Inventory remains constant for long periods, then drops sharply.  
* **Efficiency:** 100% (Benchmark).41

### **6.2 Scenario A: Naive Limited Foresight (14-Day)**

* **Behavior:** The agent sees a price peak within the 14-day window and liquidates heavily, unaware that a higher peak exists on day 45\. Due to the EoH effect, it clears inventory at day 14 to secure "terminal value" (which is zero).  
* **Inventory Profile:** "Sawtooth" or rapid depletion. The agent is consistently "stockout" during late-season spikes because it oversold early.  
* **Efficiency:** Typically 60-75% of Oracle. The loss stems from two sources: (1) missed long-term opportunities (Blindness) and (2) distressed selling at the horizon boundary (Myopia).2

### **6.3 Scenario B: Limited Foresight with Terminal Correction (MPC/ADP)**

* **Behavior:** The agent optimizes within the 14-day window but carries a high "Shadow Price" on its inventory. Even if the 14-day forecast shows a small peak, the Terminal Value function $V\_T(x)$ (derived from ADP or Shadow Pricing) suggests that holding the inventory is more valuable than selling at the current moderate price.  
* **Inventory Profile:** Smoothed trajectory. The agent sells incrementally when prices exceed the shadow price. It holds sufficient stock to capture the 14-day peaks but preserves a strategic reserve for the post-horizon future.  
* **Efficiency:** 85-95% of Oracle. The gap narrows significantly because the Terminal Value effectively "extends" the horizon, acting as a compressed representation of the future price trajectory.4

| Metric | Perfect Foresight (Oracle) | Limited (Naive 14-Day) | Limited (Corrected \- Shadow/ADP) |
| :---- | :---- | :---- | :---- |
| **Information Set** | Full ($t=1 \\to 180$) | Partial ($t \\to t+14$) | Partial \+ Proxy ($V\_T$) |
| **Liquidation Logic** | Global Peak Timing | Horizon Constraint Clearing | Marginal Value Thresholding |
| **End-of-Horizon Effect** | None | Severe (Dump at $t+14$) | Mitigated (Smooth transition) |
| **Computational Cost** | Low (Single LP) | Medium (Daily MILP) | High (Learning/Dual Tracking) |
| **Typical Performance** | 100% | \~65% | \~90% |

Table 2: Comparative performance and characteristics of inventory liquidation strategies.1

---

## **7\. Strategic Recommendations and Implementation Roadmap**

For the practical implementation of the farmer's inventory problem under limited foresight, the research suggests a hybrid architecture that combines the tactical precision of MPC with the strategic robustness of ADP and Online Algorithms.

### **7.1 The "Shadow-Corrected" MPC Architecture**

The recommended solver structure is a **Receding Horizon Controller with Dual-Variable Learning**.

1. **Initialization:** Start with a conservative heuristic for Terminal Value (e.g., $V\_T(x) \= \\text{Cost} \\times 1.2$).  
2. **Daily Optimization:** Solve the 14-day MPC problem.  
   * *Constraint:* Soften the terminal inventory constraint. Instead of $x\_{t+14} \\ge 0$, use a penalty for low inventory if demand is expected, or simply let the $V\_T$ term drive retention.  
3. **Dual Extraction:** Extract the shadow price $\\lambda\_{t+14}$ from the solver.  
4. **Smoothing:** Update the terminal value slope for tomorrow's run: $v\_{new} \= \\beta v\_{old} \+ (1-\\beta)\\lambda$.  
5. **Safety Net:** Overlay an **Online Threshold Rule**. If the MPC suggests selling $u\_t$, check if $p\_t$ is above the "Inventory Balancing" reservation price. If not, constrain $u\_t$ to zero. This protects against solver errors due to bad forecasts.20

### **7.2 Handling the End of the Season**

As the true season end ($T=180$) enters the 14-day prediction window (i.e., at $t=166$), the logic must switch. The Terminal Value function should decay to the actual salvage value (or zero). The "Effective Horizon" logic of discount factors must be relaxed so that the solver naturally liquidates the remaining stock. This "Shrinking Horizon" phase transforms the problem from an infinite-horizon approximation back to a standard finite-horizon termination.5

### **7.3 Conclusion**

The "Limited Foresight" problem is not merely a forecasting challenge but a valuation challenge. The naive 14-day solver fails not because it cannot see the future, but because it values the future at zero. By engineering a **Terminal Value Function**—whether through Shadow Pricing, ADP learning, or Online thresholds—we provide the solver with a "monetary" reason to hold inventory. This effectively bridges the gap between the myopic present and the strategic future, allowing the farmer to navigate the 180-day season with near-optimal efficiency despite the blinders of the 14-day forecast. The integration of **Economic MPC** with **Shadow Price Smoothing** represents the state-of-the-art solution for this class of inventory problems, balancing computational feasibility with economic performance.

#### **Works cited**

1. Market-based scheduling of energy storage systems: Optimality guarantees \- DTU Research Database, accessed November 25, 2025, [https://orbit.dtu.dk/files/399533245/PhD\_Thesis\_Elea\_Prat.pdf](https://orbit.dtu.dk/files/399533245/PhD_Thesis_Elea_Prat.pdf)  
2. Dynamic horizon selection methodology for model predictive control in buildings, accessed November 25, 2025, [https://www.researchgate.net/publication/362789906\_Dynamic\_horizon\_selection\_methodology\_for\_model\_predictive\_control\_in\_buildings](https://www.researchgate.net/publication/362789906_Dynamic_horizon_selection_methodology_for_model_predictive_control_in_buildings)  
3. Enhancing Rolling Horizon Production Planning Through Stochastic Optimization Evaluated by Means of Simulation \- arXiv, accessed November 25, 2025, [https://arxiv.org/html/2402.14506v1](https://arxiv.org/html/2402.14506v1)  
4. Uniform turnpike theorems for finite Markov decision processes \- Cornell University, accessed November 25, 2025, [https://people.orie.cornell.edu/melewis/pubs/turnpike.pdf](https://people.orie.cornell.edu/melewis/pubs/turnpike.pdf)  
5. The benefit of receding horizon control \- Edinburgh Research Explorer, accessed November 25, 2025, [https://www.research.ed.ac.uk/files/103525579/elsarticle\_template.pdf](https://www.research.ed.ac.uk/files/103525579/elsarticle_template.pdf)  
6. Algorithmic Approaches to Inventory Management Optimization \- MDPI, accessed November 25, 2025, [https://www.mdpi.com/2227-9717/9/1/102](https://www.mdpi.com/2227-9717/9/1/102)  
7. A comparison of methods for lot-sizing in a rolling horizon environment \- ResearchGate, accessed November 25, 2025, [https://www.researchgate.net/publication/220059752\_A\_comparison\_of\_methods\_for\_lot-sizing\_in\_a\_rolling\_horizon\_environment](https://www.researchgate.net/publication/220059752_A_comparison_of_methods_for_lot-sizing_in_a_rolling_horizon_environment)  
8. Long‐term effects of short planning horizons for inventory routing problems \- Sci-Hub, accessed November 25, 2025, [https://2024.sci-hub.box/8653/09f4e8dd089a3ba1c86c7c68fef33fee/benahmed2021.pdf](https://2024.sci-hub.box/8653/09f4e8dd089a3ba1c86c7c68fef33fee/benahmed2021.pdf)  
9. Feedback-Based Deterministic Optimization Is a Robust Approach for Supply Chain Management under Demand Uncertainty \- ACS Publications, accessed November 25, 2025, [https://pubs.acs.org/doi/10.1021/acs.iecr.2c00099](https://pubs.acs.org/doi/10.1021/acs.iecr.2c00099)  
10. Mixed-Integer Model Predictive Control with Applications to Building Energy Systems \- The Robert Mehrabian College of Engineering \- UC Santa Barbara, accessed November 25, 2025, [https://sites.engineering.ucsb.edu/\~jbraw/jbrweb-archives/theses/risbeck.pdf](https://sites.engineering.ucsb.edu/~jbraw/jbrweb-archives/theses/risbeck.pdf)  
11. Bi-level Model Predictive Control for Energy-aware Integrated Product Pricing and Production Scheduling \- arXiv, accessed November 25, 2025, [https://arxiv.org/html/2507.14385v1](https://arxiv.org/html/2507.14385v1)  
12. Inventory control for a perishable product with non-stationary demand and service level constraints \- Optimization Online, accessed November 25, 2025, [https://optimization-online.org/wp-content/uploads/2013/08/4010.pdf](https://optimization-online.org/wp-content/uploads/2013/08/4010.pdf)  
13. Analysis of Supply Contracts with Commitments and Flexibility \- Deep Blue Repositories, accessed November 25, 2025, [https://deepblue.lib.umich.edu/bitstream/handle/2027.42/60455/20300\_ftp.pdf?sequence=1](https://deepblue.lib.umich.edu/bitstream/handle/2027.42/60455/20300_ftp.pdf?sequence=1)  
14. An Approximate Dynamic Programming Approach for a Product Distribution Problem, accessed November 25, 2025, [https://people.orie.cornell.edu/huseyin/publications/spatially\_distr\_inv.pdf](https://people.orie.cornell.edu/huseyin/publications/spatially_distr_inv.pdf)  
15. 1\. An introduction to dynamic optimization, accessed November 25, 2025, [http://econdse.org/wp-content/uploads/2012/10/002\_2012\_Intro-to-Optimal-control](http://econdse.org/wp-content/uploads/2012/10/002_2012_Intro-to-Optimal-control)  
16. Shadow price \- Wikipedia, accessed November 25, 2025, [https://en.wikipedia.org/wiki/Shadow\_price](https://en.wikipedia.org/wiki/Shadow_price)  
17. Investment Behavior, Observable Expectations, and Internal Funds \- Federal Reserve Board, accessed November 25, 2025, [https://www.federalreserve.gov/pubs/feds/1999/199927/199927pap.pdf](https://www.federalreserve.gov/pubs/feds/1999/199927/199927pap.pdf)  
18. Terminal value: A crucial and yet often forgotten element in timber harvest scheduling and timberland valuation \- Southern Research Station, accessed November 25, 2025, [https://www.srs.fs.usda.gov/pubs/ja/2024/ja\_2024\_henderson\_001.pdf](https://www.srs.fs.usda.gov/pubs/ja/2024/ja_2024_henderson_001.pdf)  
19. An Optimal Inventory Pricing and Ordering Strategy Subject to Stock and Price Dependent Demand \- NAUN, accessed November 25, 2025, [https://www.naun.org/main/NAUN/ijmmas/2021/a442001-022(2021).pdf](https://www.naun.org/main/NAUN/ijmmas/2021/a442001-022\(2021\).pdf)  
20. Rolling horizon data driven robust optimization for supply chain planning \- ResearchGate, accessed November 25, 2025, [https://www.researchgate.net/publication/395924899\_Rolling\_horizon\_data\_driven\_robust\_optimization\_for\_supply\_chain\_planning](https://www.researchgate.net/publication/395924899_Rolling_horizon_data_driven_robust_optimization_for_supply_chain_planning)  
21. The Steady-State Model: SSQPM \- Bank of Canada, accessed November 25, 2025, [https://www.bankofcanada.ca/wp-content/uploads/2010/01/tr72.pdf](https://www.bankofcanada.ca/wp-content/uploads/2010/01/tr72.pdf)  
22. Identification and Estimation of Forward-looking Behavior: The Case of Consumer Stockpiling \- Wharton Marketing, accessed November 25, 2025, [https://marketing.wharton.upenn.edu/wp-content/uploads/2015/04/02-22-2017-Ching-Osborne-Paper-Part-1.pdf](https://marketing.wharton.upenn.edu/wp-content/uploads/2015/04/02-22-2017-Ching-Osborne-Paper-Part-1.pdf)  
23. Identification and Estimation of Forward-Looking Behavior: The Case of Consumer Stockpiling | Marketing Science \- PubsOnLine, accessed November 25, 2025, [https://pubsonline.informs.org/doi/10.1287/mksc.2019.1193](https://pubsonline.informs.org/doi/10.1287/mksc.2019.1193)  
24. Chapter 19 Inventory Theory, accessed November 25, 2025, [https://www.ime.unicamp.br/\~andreani/MS515/capitulo12.pdf](https://www.ime.unicamp.br/~andreani/MS515/capitulo12.pdf)  
25. An Approximate Dynamic Programming Approach to Benchmark Practice-Based Heuristics for Natural Gas Storage Valuation | Operations Research \- PubsOnLine, accessed November 25, 2025, [https://pubsonline.informs.org/doi/10.1287/opre.1090.0768](https://pubsonline.informs.org/doi/10.1287/opre.1090.0768)  
26. Production and inventory control in complex production systems using approximate dynamic programming. \- ThinkIR, accessed November 25, 2025, [https://ir.library.louisville.edu/cgi/viewcontent.cgi?article=3374\&context=etd](https://ir.library.louisville.edu/cgi/viewcontent.cgi?article=3374&context=etd)  
27. Understanding approximate dynamic programming \- Telnyx, accessed November 25, 2025, [https://telnyx.com/learn-ai/approximate-dynamic-programming](https://telnyx.com/learn-ai/approximate-dynamic-programming)  
28. Designing Lookahead Policies for Sequential Decision Problems in Transportation and Logistics \- IEEE Xplore, accessed November 25, 2025, [https://ieeexplore.ieee.org/iel7/8784355/9680328/09702124.pdf](https://ieeexplore.ieee.org/iel7/8784355/9680328/09702124.pdf)  
29. APPROXIMATE DYNAMIC PROGRAMMING ALGORITHMS FOR PRODUCTION-PLANNING PROBLEMS \- SOAR, accessed November 25, 2025, [https://soar.wichita.edu/server/api/core/bitstreams/dd7c0e48-7f2e-42f0-8cbc-c2aa1256ae45/content](https://soar.wichita.edu/server/api/core/bitstreams/dd7c0e48-7f2e-42f0-8cbc-c2aa1256ae45/content)  
30. Perspectives of approximate dynamic programming \- CASTLE, accessed November 25, 2025, [https://castle.princeton.edu/adp/Papers/Powell%20-%20Perspectives%20of%20approximate%20dynamic%20programming.pdf](https://castle.princeton.edu/adp/Papers/Powell%20-%20Perspectives%20of%20approximate%20dynamic%20programming.pdf)  
31. Finite-Horizon Approximate Linear Programs for Capacity Allocation over a Rolling Horizon \- Dan Zhang, accessed November 25, 2025, [https://danzhang.com/papers/RollingHorizonRM\_Final.pdf](https://danzhang.com/papers/RollingHorizonRM_Final.pdf)  
32. Separating value functions across time-scales \- Proceedings of Machine Learning Research, accessed November 25, 2025, [http://proceedings.mlr.press/v97/romoff19a/romoff19a.pdf](http://proceedings.mlr.press/v97/romoff19a/romoff19a.pdf)  
33. Differentiable Game Mechanics | Request PDF \- ResearchGate, accessed November 25, 2025, [https://www.researchgate.net/publication/333982053\_Differentiable\_Game\_Mechanics](https://www.researchgate.net/publication/333982053_Differentiable_Game_Mechanics)  
34. BibTeX bibliography pomacs.bib \- Index of files in /, accessed November 25, 2025, [http://ftp.math.utah.edu/pub/tex/bib/pomacs.html](http://ftp.math.utah.edu/pub/tex/bib/pomacs.html)  
35. The Disposal of Excess Stock: A Classification of Literature and Some Directions for Further Research Authors: Keith A. Willoug, accessed November 25, 2025, [https://www.edwards.usask.ca/faculty/Keith%20Willoughby/files/Excess%20stock%20disposal.pdf](https://www.edwards.usask.ca/faculty/Keith%20Willoughby/files/Excess%20stock%20disposal.pdf)  
36. Avellaneda and Stoikov MM paper implementation | by Siddharth Kumar \- Medium, accessed November 25, 2025, [https://medium.com/@degensugarboo/avellaneda-and-stoikov-mm-paper-implementation-b7011b5a7532](https://medium.com/@degensugarboo/avellaneda-and-stoikov-mm-paper-implementation-b7011b5a7532)  
37. Competitive Online Optimization under Inventory Constraints | Request PDF \- ResearchGate, accessed November 25, 2025, [https://www.researchgate.net/publication/340218797\_Competitive\_Online\_Optimization\_under\_Inventory\_Constraints](https://www.researchgate.net/publication/340218797_Competitive_Online_Optimization_under_Inventory_Constraints)  
38. Experimental Analysis of an Online Trading Algorithm | Request PDF \- ResearchGate, accessed November 25, 2025, [https://www.researchgate.net/publication/220082105\_Experimental\_Analysis\_of\_an\_Online\_Trading\_Algorithm](https://www.researchgate.net/publication/220082105_Experimental_Analysis_of_an_Online_Trading_Algorithm)  
39. 1 Introduction \- arXiv, accessed November 25, 2025, [https://arxiv.org/html/2511.16044v1](https://arxiv.org/html/2511.16044v1)  
40. Algorithms for Online Matching, Assortment, and Pricing with Tight Weight-dependent Competitive Ratios, accessed November 25, 2025, [https://business.columbia.edu/sites/default/files-efs/pubfiles/26019/Matching.pdf](https://business.columbia.edu/sites/default/files-efs/pubfiles/26019/Matching.pdf)  
41. Efficient option pricing with transaction costs, accessed November 25, 2025, [https://ora.ox.ac.uk/objects/uuid:a253f57f-149d-4d3d-8d47-77dd858cfbf1/files/m9b484c1fd01a7cc22f3f90a3f4c7e619](https://ora.ox.ac.uk/objects/uuid:a253f57f-149d-4d3d-8d47-77dd858cfbf1/files/m9b484c1fd01a7cc22f3f90a3f4c7e619)  
42. Budget Constrained Bidding in Keyword Auctions and Online Knapsack Problems | Request PDF \- ResearchGate, accessed November 25, 2025, [https://www.researchgate.net/publication/284004591\_Budget\_Constrained\_Bidding\_in\_Keyword\_Auctions\_and\_Online\_Knapsack\_Problems](https://www.researchgate.net/publication/284004591_Budget_Constrained_Bidding_in_Keyword_Auctions_and_Online_Knapsack_Problems)  
43. Models and Algorithms for Real-Time Production Scheduling \- University of Wisconsin–Madison, accessed November 25, 2025, [https://asset.library.wisc.edu/1711.dl/6QQKIQBJFHFUV8M/R/file-2f235.pdf](https://asset.library.wisc.edu/1711.dl/6QQKIQBJFHFUV8M/R/file-2f235.pdf)  
44. Rolling horizon inventory problem \- Gurobi Support, accessed November 25, 2025, [https://support.gurobi.com/hc/en-us/community/posts/8592396785297-Rolling-horizon-inventory-problem](https://support.gurobi.com/hc/en-us/community/posts/8592396785297-Rolling-horizon-inventory-problem)