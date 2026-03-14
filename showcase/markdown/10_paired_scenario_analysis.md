```python
# NOTEBOOK 09: THREE-SCENARIO FOCUSED ANALYSIS (MULTI-COMMODITY)
# ============================================================================
# Databricks notebook source
# MAGIC %md
# MAGIC # Block 09: Moving Average vs Predictions vs Immediate Sale Analysis
# MAGIC 
# MAGIC This analysis focuses on three key scenarios for each commodity:
# MAGIC 1. Moving Average Baseline (no predictions)
# MAGIC 2. Moving Average with Predictions
# MAGIC 3. Immediate Sale (simple equal batches)
# MAGIC 
# MAGIC Key Question: **Do predictions add value to the moving average strategy?**

# COMMAND ----------

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from datetime import datetime
import pickle
import warnings
warnings.filterwarnings('ignore')

# Set style
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")

print("="*80)
print("BLOCK 09: THREE-SCENARIO COMPARATIVE ANALYSIS")
print("="*80)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

# Commodities to analyze
COMMODITIES = ['coffee', 'sugar']
BASE_PATH = '/Volumes/commodity/silver/trading_agent_volume'

# Store results across all commodities
all_commodity_summaries = []

# Color scheme for consistency
COLORS = {'Immediate Sale': '#3498db', 'MA Baseline': '#e74c3c', 'MA + Predictions': '#2ecc71'}

# COMMAND ----------

# MAGIC %md
# MAGIC ## Analysis Functions

# COMMAND ----------

def bootstrap_metric(strategy_name, detailed_results, metric='net_earnings', n_bootstrap=1000, seed=42):
    """
    Calculate bootstrap confidence intervals for a strategy's performance metric.
    
    This resamples trades with replacement to estimate the distribution of outcomes.
    """
    np.random.seed(seed)
    
    # Get the detailed results for this strategy
    # detailed_results is a dict with strategy names as keys
    if strategy_name not in detailed_results:
        return None, None, None
    
    strat_data = detailed_results[strategy_name]
    
    if 'trades' not in strat_data or len(strat_data['trades']) == 0:
        return None, None, None
    
    trades_df = pd.DataFrame(strat_data['trades'])
    
    if len(trades_df) == 0:
        return None, None, None
    
    # Bootstrap resampling
    bootstrap_samples = []
    for _ in range(n_bootstrap):
        # Resample trades with replacement
        sample_trades = trades_df.sample(n=len(trades_df), replace=True)
        
        # Calculate metric for this bootstrap sample
        if metric == 'net_earnings':
            # Recalculate net earnings from the resampled trades
            # Trade structure: 'revenue', 'transaction_cost', 'net_revenue'
            # Note: storage costs are tracked separately in the simulation
            gross_revenue = sample_trades['revenue'].sum()
            transaction_costs = sample_trades['transaction_cost'].sum()
            # We can't recalculate storage costs from trades alone, so use net_revenue
            sample_metric = sample_trades['net_revenue'].sum()
        elif metric == 'total_revenue':
            # Total revenue before any costs
            sample_metric = sample_trades['revenue'].sum()
        elif metric == 'avg_sale_price':
            # Trade structure: 'price' (in cents/lb), 'amount' (in tons)
            sample_metric = (sample_trades['amount'] * sample_trades['price']).sum() / sample_trades['amount'].sum()
        else:
            sample_metric = sample_trades[metric].mean()
        
        bootstrap_samples.append(sample_metric)
    
    # Calculate confidence intervals
    ci_lower = np.percentile(bootstrap_samples, 2.5)
    ci_upper = np.percentile(bootstrap_samples, 97.5)
    mean_estimate = np.mean(bootstrap_samples)
    
    return mean_estimate, ci_lower, ci_upper

# COMMAND ----------

# MAGIC %md
# MAGIC ## Loop Through Each Commodity

# COMMAND ----------

for COMMODITY in COMMODITIES:
    print("\n" + "="*80)
    print(f"ANALYZING: {COMMODITY.upper()}")
    print("="*80)
    
    try:
        # ====================================================================
        # 1. Load Results from Prior Runs
        # ====================================================================
        print(f"\n📊 Loading results for {COMMODITY.upper()}...")
        
        # Load main results
        results_path = f'{BASE_PATH}/results_{COMMODITY}.csv'
        results_df = pd.read_csv(results_path)
        
        # Load detailed results (contains transaction-level data)
        detailed_path = f'{BASE_PATH}/results_detailed_{COMMODITY}.pkl'
        with open(detailed_path, 'rb') as f:
            detailed_results = pickle.load(f)
        
        print(f"✓ Loaded {len(results_df)} strategy results")
        print(f"✓ Loaded detailed results for {len(detailed_results)} strategies")
    
    except FileNotFoundError as e:
        print(f"⚠️  Could not load results for {COMMODITY}: {e}")
        print(f"   Skipping {COMMODITY}...")
        continue
    
    # ====================================================================
    # 2. Extract the Three Scenarios
    # ====================================================================
    print(f"\n{'─'*80}")
    print("EXTRACTING THREE SCENARIOS")
    print(f"{'─'*80}")
    
    # First, show all available strategies
    print(f"\nAvailable strategies in {COMMODITY} results:")
    for i, strat in enumerate(results_df['strategy'].unique(), 1):
        earnings = results_df[results_df['strategy'] == strat]['net_earnings'].values[0]
        print(f"  {i}. {strat} (${earnings:,.0f})")
    
    # Define the three scenarios with EXACT strategy names from the notebook
    # Based on notebook code:
    # - ImmediateSaleStrategy() → "Immediate Sale"
    # - MovingAverageStrategy() → "Moving Average"
    # - MovingAveragePredictive() → "Moving Average Predictive"
    
    SCENARIO_NAMES = {
        'Immediate Sale': 'Immediate Sale',
        'MA Baseline': 'Moving Average',
        'MA + Predictions': 'Moving Average Predictive'
    }
    
    print(f"\nSearching for three key scenarios...")
    
    # Extract relevant strategies
    three_scenarios = []
    
    for label, exact_name in SCENARIO_NAMES.items():
        # Find exact match
        match = results_df[results_df['strategy'] == exact_name]
        
        if len(match) > 0:
            best = match.iloc[0]
            three_scenarios.append({
                'label': label,
                'strategy_name': best['strategy'],
                'data': best.to_dict()
            })
            print(f"✓ Found {label}: {best['strategy']}")
        else:
            print(f"⚠️  No match found for {label} (expected: '{exact_name}')")
    
    if len(three_scenarios) < 3:
        print(f"\n⚠️  Only found {len(three_scenarios)}/3 scenarios for {COMMODITY}")
        print(f"   Available strategies don't match expected patterns.")
        print(f"   Please check strategy names above and update SCENARIO_PATTERNS.")
        print(f"   Skipping {COMMODITY}...")
        continue
    
    # Create comparison dataframe
    comparison_df = pd.DataFrame([s['data'] for s in three_scenarios])
    comparison_df['label'] = [s['label'] for s in three_scenarios]
    
    print(f"\n✓ Extracted {len(comparison_df)} scenarios for analysis")
    
    # ====================================================================
    # 3. Statistical Testing: Do Predictions Add Value?
    # ====================================================================
    print(f"\n{'─'*80}")
    print("STATISTICAL ANALYSIS: PREDICTIONS VALUE-ADD")
    print(f"{'─'*80}")
    
    # Extract MA baseline and MA prediction results
    ma_baseline = comparison_df[comparison_df['label'] == 'MA Baseline'].iloc[0]
    ma_prediction = comparison_df[comparison_df['label'] == 'MA + Predictions'].iloc[0]
    immediate_sale = comparison_df[comparison_df['label'] == 'Immediate Sale'].iloc[0]
    
    # Calculate key differences
    earnings_diff = ma_prediction['net_earnings'] - ma_baseline['net_earnings']
    earnings_pct = (earnings_diff / ma_baseline['net_earnings']) * 100
    
    revenue_diff = ma_prediction['total_revenue'] - ma_baseline['total_revenue']
    revenue_pct = (revenue_diff / ma_baseline['total_revenue']) * 100
    
    price_diff = ma_prediction['avg_sale_price'] - ma_baseline['avg_sale_price']
    price_pct = (price_diff / ma_baseline['avg_sale_price']) * 100
    
    print(f"\n1. NET EARNINGS COMPARISON (After Costs)")
    print(f"   MA Baseline:      ${ma_baseline['net_earnings']:,.2f}")
    print(f"   MA + Predictions: ${ma_prediction['net_earnings']:,.2f}")
    print(f"   Difference:       ${earnings_diff:,.2f} ({earnings_pct:+.2f}%)")
    print(f"   Status:           {'✓ PREDICTIONS ADD VALUE' if earnings_diff > 0 else '✗ PREDICTIONS REDUCE VALUE'}")
    
    print(f"\n2. TOTAL REVENUE COMPARISON (Before Costs)")
    print(f"   MA Baseline:      ${ma_baseline['total_revenue']:,.2f}")
    print(f"   MA + Predictions: ${ma_prediction['total_revenue']:,.2f}")
    print(f"   Difference:       ${revenue_diff:,.2f} ({revenue_pct:+.2f}%)")
    print(f"   Status:           {'✓ PREDICTIONS ADD VALUE' if revenue_diff > 0 else '✗ PREDICTIONS REDUCE VALUE'}")
    
    # Identify if there's a disconnect
    if (earnings_diff > 0 and revenue_diff < 0) or (earnings_diff < 0 and revenue_diff > 0):
        print(f"\n   ⚠️  IMPORTANT: Net and gross revenue show OPPOSITE results!")
        print(f"      This suggests cost assumptions are driving the difference.")
    
    print(f"\n3. AVERAGE PRICE COMPARISON")
    print(f"   MA Baseline:      ${ma_baseline['avg_sale_price']:.2f}")
    print(f"   MA + Predictions: ${ma_prediction['avg_sale_price']:.2f}")
    print(f"   Difference:       ${price_diff:.2f} ({price_pct:+.2f}%)")
    
    print(f"\n4. COST ANALYSIS")
    print(f"   MA Baseline:")
    print(f"      Storage costs:     ${ma_baseline['storage_costs']:,.2f}")
    print(f"      Transaction costs: ${ma_baseline['transaction_costs']:,.2f}")
    print(f"      Total costs:       ${ma_baseline['total_costs']:,.2f}")
    print(f"   MA + Predictions:")
    print(f"      Storage costs:     ${ma_prediction['storage_costs']:,.2f}")
    print(f"      Transaction costs: ${ma_prediction['transaction_costs']:,.2f}")
    print(f"      Total costs:       ${ma_prediction['total_costs']:,.2f}")
    print(f"   Cost difference:      ${ma_prediction['total_costs'] - ma_baseline['total_costs']:+,.2f}")
    
    print(f"\n5. TRADING BEHAVIOR")
    print(f"   MA Baseline trades:      {ma_baseline['n_trades']:.0f}")
    print(f"   MA + Predictions trades: {ma_prediction['n_trades']:.0f}")
    print(f"   Immediate Sale trades:       {immediate_sale['n_trades']:.0f}")
    
    # Calculate metrics vs batch sale baseline
    immediate_sale_earnings_diff = ma_prediction['net_earnings'] - immediate_sale['net_earnings']
    immediate_sale_earnings_pct = (immediate_sale_earnings_diff / immediate_sale['net_earnings']) * 100
    
    print(f"\n6. COMPARISON TO IMMEDIATE SALE (Simplest Strategy)")
    print(f"   Immediate Sale:       ${immediate_sale['net_earnings']:,.2f}")
    print(f"   MA Baseline:      ${ma_baseline['net_earnings']:,.2f} ({(ma_baseline['net_earnings']/immediate_sale['net_earnings']-1)*100:+.1f}%)")
    print(f"   MA + Predictions: ${ma_prediction['net_earnings']:,.2f} ({batch_earnings_pct:+.1f}%)")
    
    # ====================================================================
    # 4. Bootstrap Confidence Intervals
    # ====================================================================
    print(f"\n{'─'*80}")
    print("BOOTSTRAP CONFIDENCE INTERVALS (95%)")
    print(f"{'─'*80}")
    print("Resampling trades 1,000 times to assess outcome uncertainty...\n")
    
    # Calculate bootstrap CIs for all three scenarios (both net earnings and total revenue)
    ci_results = {}
    for scenario in three_scenarios:
        label = scenario['label']
        strategy_name = scenario['strategy_name']
        
        # Net earnings
        mean_earnings, ci_low_earnings, ci_high_earnings = bootstrap_metric(strategy_name, detailed_results, 'net_earnings')
        
        # Total revenue
        mean_revenue, ci_low_revenue, ci_high_revenue = bootstrap_metric(strategy_name, detailed_results, 'total_revenue')
        
        if mean_earnings is not None:
            ci_results[label] = {
                'mean_earnings': mean_earnings,
                'ci_low_earnings': ci_low_earnings,
                'ci_high_earnings': ci_high_earnings,
                'ci_width_earnings': ci_high_earnings - ci_low_earnings,
                'mean_revenue': mean_revenue,
                'ci_low_revenue': ci_low_revenue,
                'ci_high_revenue': ci_high_revenue,
                'ci_width_revenue': ci_high_revenue - ci_low_revenue
            }
            
            print(f"{label}:")
            print(f"  Net Earnings:  ${mean_earnings:,.2f}  [${ci_low_earnings:,.2f}, ${ci_high_earnings:,.2f}]")
            print(f"  Total Revenue: ${mean_revenue:,.2f}  [${ci_low_revenue:,.2f}, ${ci_high_revenue:,.2f}]")
            print(f"  CI Width: ${ci_high_earnings - ci_low_earnings:,.2f} (net) / ${ci_high_revenue - ci_low_revenue:,.2f} (gross)\n")
    
    # Check if CIs overlap
    ci_overlap_net = None
    ci_overlap_revenue = None
    if 'MA Baseline' in ci_results and 'MA + Predictions' in ci_results:
        baseline_ci = ci_results['MA Baseline']
        prediction_ci = ci_results['MA + Predictions']
        
        # Check net earnings overlap
        ci_overlap_net = not (baseline_ci['ci_high_earnings'] < prediction_ci['ci_low_earnings'] or 
                              prediction_ci['ci_high_earnings'] < baseline_ci['ci_low_earnings'])
        
        # Check total revenue overlap
        ci_overlap_revenue = not (baseline_ci['ci_high_revenue'] < prediction_ci['ci_low_revenue'] or 
                                  prediction_ci['ci_high_revenue'] < baseline_ci['ci_low_revenue'])
        
        print("CONFIDENCE INTERVAL OVERLAP ANALYSIS:")
        print("\n  Net Earnings:")
        if ci_overlap_net:
            print("     ⚠️  Confidence intervals OVERLAP")
            print("     → Difference may not be statistically significant")
        else:
            print("     ✓ Confidence intervals DO NOT overlap")
            print("     → Difference is likely statistically significant")
        
        print("\n  Total Revenue:")
        if ci_overlap_revenue:
            print("     ⚠️  Confidence intervals OVERLAP")
            print("     → Difference may not be statistically significant")
        else:
            print("     ✓ Confidence intervals DO NOT overlap")
            print("     → Difference is likely statistically significant")
    
    # ====================================================================
    # 5. Trade-by-Trade Analysis
    # ====================================================================
    print(f"\n{'─'*80}")
    print("TRADE-BY-TRADE COMPARISON")
    print(f"{'─'*80}")
    
    # Extract trade details for MA baseline and MA prediction
    trades_analysis = {}
    
    for scenario in three_scenarios:
        label = scenario['label']
        strategy_name = scenario['strategy_name']
        
        # Get from detailed results dictionary
        if strategy_name in detailed_results:
            result = detailed_results[strategy_name]
            if 'trades' in result and len(result['trades']) > 0:
                trades_df = pd.DataFrame(result['trades'])
                trades_analysis[label] = trades_df
    
    # Compare trade distributions
    t_stat, p_value, cohens_d = None, None, None
    if 'MA Baseline' in trades_analysis and 'MA + Predictions' in trades_analysis:
        baseline_trades = trades_analysis['MA Baseline']
        prediction_trades = trades_analysis['MA + Predictions']
        
        # Calculate days held if we have the data
        if 'day' in baseline_trades.columns:
            # Estimate days held from cumulative days (rough approximation)
            baseline_trades['days_held'] = baseline_trades['day'].diff().fillna(0)
            prediction_trades['days_held'] = prediction_trades['day'].diff().fillna(0)
        
        print(f"\nTRADE STATISTICS:")
        print(f"\nMA Baseline:")
        print(f"  Total trades: {len(baseline_trades)}")
        print(f"  Avg sale price: ${baseline_trades['price'].mean():.2f}")
        print(f"  Std sale price: ${baseline_trades['price'].std():.2f}")
        print(f"  Avg quantity: {baseline_trades['amount'].mean():.2f} tons")
        if 'days_held' in baseline_trades.columns:
            print(f"  Avg days between trades: {baseline_trades['days_held'].mean():.1f}")
        
        print(f"\nMA + Predictions:")
        print(f"  Total trades: {len(prediction_trades)}")
        print(f"  Avg sale price: ${prediction_trades['price'].mean():.2f}")
        print(f"  Std sale price: ${prediction_trades['price'].std():.2f}")
        print(f"  Avg quantity: {prediction_trades['amount'].mean():.2f} tons")
        if 'days_held' in prediction_trades.columns:
            print(f"  Avg days between trades: {prediction_trades['days_held'].mean():.1f}")
        
        # Statistical test on sale prices
        t_stat, p_value = stats.ttest_ind(prediction_trades['price'], 
                                           baseline_trades['price'])
        
        print(f"\nT-TEST ON SALE PRICES:")
        print(f"  t-statistic: {t_stat:.4f}")
        print(f"  p-value: {p_value:.4f}")
        print(f"  Result: {'✓ Significantly different' if p_value < 0.05 else '✗ Not significantly different'} (α=0.05)")
        
        # Effect size (Cohen's d)
        pooled_std = np.sqrt((baseline_trades['price'].std()**2 + 
                             prediction_trades['price'].std()**2) / 2)
        cohens_d = (prediction_trades['price'].mean() - 
                    baseline_trades['price'].mean()) / pooled_std
        
        print(f"  Cohen's d: {cohens_d:.4f}")
        
        # Interpret effect size
        if abs(cohens_d) < 0.2:
            effect = "negligible"
        elif abs(cohens_d) < 0.5:
            effect = "small"
        elif abs(cohens_d) < 0.8:
            effect = "medium"
        else:
            effect = "large"
        
        print(f"  Effect size: {effect}")
    
    # ====================================================================
    # 6. Visualization: Comprehensive Dashboard
    # ====================================================================
    print(f"\n{'─'*80}")
    print("GENERATING VISUALIZATIONS")
    print(f"{'─'*80}")
    
    # Create comprehensive figure
    fig = plt.figure(figsize=(20, 12))
    fig.suptitle(f'{COMMODITY.title()} - Three-Scenario Trading Strategy Comparison', 
                 fontsize=20, fontweight='bold', y=0.995)
    
    # ====================================================================
    # PLOT 1: Earnings Comparison
    # ====================================================================
    ax1 = plt.subplot(2, 4, 1)
    
    scenarios_sorted = comparison_df.sort_values('net_earnings', ascending=True)
    bars = ax1.barh(range(len(scenarios_sorted)), scenarios_sorted['net_earnings'], 
                    color=[COLORS[label] for label in scenarios_sorted['label']])
    
    # Add value labels
    for i, (idx, row) in enumerate(scenarios_sorted.iterrows()):
        ax1.text(row['net_earnings'], i, f" ${row['net_earnings']:,.0f}", 
                va='center', fontsize=10, fontweight='bold')
    
    ax1.set_yticks(range(len(scenarios_sorted)))
    ax1.set_yticklabels(scenarios_sorted['label'], fontsize=11)
    ax1.set_xlabel('Net Earnings ($)', fontsize=11, fontweight='bold')
    ax1.set_title('Net Earnings Comparison', fontsize=13, fontweight='bold', pad=10)
    ax1.grid(axis='x', alpha=0.3)
    
    # ====================================================================
    # PLOT 2: Net Earnings vs Total Revenue Comparison
    # ====================================================================
    ax2 = plt.subplot(2, 4, 2)
    
    x = np.arange(len(comparison_df))
    width = 0.35
    
    bars1 = ax2.bar(x - width/2, comparison_df['net_earnings'], width,
                    label='Net Earnings', color='steelblue', alpha=0.8)
    bars2 = ax2.bar(x + width/2, comparison_df['total_revenue'], width,
                    label='Total Revenue', color='orange', alpha=0.8)
    
    # Add value labels
    for i, (idx, row) in enumerate(comparison_df.iterrows()):
        ax2.text(i - width/2, row['net_earnings'], f"${row['net_earnings']/1000:.0f}k",
                ha='center', va='bottom', fontsize=8, fontweight='bold')
        ax2.text(i + width/2, row['total_revenue'], f"${row['total_revenue']/1000:.0f}k",
                ha='center', va='bottom', fontsize=8, fontweight='bold')
    
    ax2.set_xticks(x)
    ax2.set_xticklabels(comparison_df['label'], fontsize=11, rotation=15, ha='right')
    ax2.set_ylabel('Dollar Amount ($)', fontsize=11, fontweight='bold')
    ax2.set_title('Net vs Gross Revenue', fontsize=13, fontweight='bold', pad=10)
    ax2.legend(fontsize=10)
    ax2.grid(axis='y', alpha=0.3)
    
    # ====================================================================
    # PLOT 3: Average Sale Price
    # ====================================================================
    ax3 = plt.subplot(2, 4, 3)
    
    bars = ax3.bar(range(len(comparison_df)), comparison_df['avg_sale_price'],
                   color=[COLORS[label] for label in comparison_df['label']])
    
    # Add value labels
    for i, (idx, row) in enumerate(comparison_df.iterrows()):
        ax3.text(i, row['avg_sale_price'], f"${row['avg_sale_price']:.0f}", 
                ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    ax3.set_xticks(range(len(comparison_df)))
    ax3.set_xticklabels(comparison_df['label'], fontsize=11, rotation=15, ha='right')
    ax3.set_ylabel('Average Sale Price ($)', fontsize=11, fontweight='bold')
    ax3.set_title('Average Sale Price', fontsize=13, fontweight='bold', pad=10)
    ax3.grid(axis='y', alpha=0.3)
    
    # ====================================================================
    # PLOT 4: Number of Trades
    # ====================================================================
    ax4 = plt.subplot(2, 4, 4)
    
    bars = ax4.bar(range(len(comparison_df)), comparison_df['n_trades'],
                   color=[COLORS[label] for label in comparison_df['label']])
    
    # Add value labels
    for i, (idx, row) in enumerate(comparison_df.iterrows()):
        ax4.text(i, row['n_trades'], f"{row['n_trades']:.0f}", 
                ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    ax4.set_xticks(range(len(comparison_df)))
    ax4.set_xticklabels(comparison_df['label'], fontsize=11, rotation=15, ha='right')
    ax4.set_ylabel('Number of Trades', fontsize=11, fontweight='bold')
    ax4.set_title('Trading Activity', fontsize=13, fontweight='bold', pad=10)
    ax4.grid(axis='y', alpha=0.3)
    
    # ====================================================================
    # PLOT 5: Sale Price Distribution (if trade data available)
    # ====================================================================
    ax5 = plt.subplot(2, 4, 5)
    
    if len(trades_analysis) > 0:
        for label, trades_df in trades_analysis.items():
            if len(trades_df) > 0:
                ax5.hist(trades_df['price'], bins=20, alpha=0.6, 
                        label=label, color=COLORS[label], edgecolor='black')
        
        ax5.set_xlabel('Sale Price (cents/lb)', fontsize=11, fontweight='bold')
        ax5.set_ylabel('Frequency', fontsize=11, fontweight='bold')
        ax5.set_title('Sale Price Distribution', fontsize=13, fontweight='bold', pad=10)
        ax5.legend(fontsize=10)
        ax5.grid(axis='y', alpha=0.3)
    else:
        ax5.text(0.5, 0.5, 'Trade-level data\nnot available', 
                ha='center', va='center', transform=ax5.transAxes, fontsize=12)
        ax5.set_title('Sale Price Distribution', fontsize=13, fontweight='bold', pad=10)
    
    # ====================================================================
    # PLOT 6: Days Between Trades Distribution
    # ====================================================================
    ax6 = plt.subplot(2, 4, 6)
    
    if len(trades_analysis) > 0:
        has_data = False
        for label, trades_df in trades_analysis.items():
            if len(trades_df) > 0 and 'day' in trades_df.columns:
                # Calculate days between consecutive trades
                days_between = trades_df['day'].diff().dropna()
                if len(days_between) > 0:
                    ax6.hist(days_between, bins=20, alpha=0.6, 
                            label=label, color=COLORS[label], edgecolor='black')
                    has_data = True
        
        if has_data:
            ax6.set_xlabel('Days Between Trades', fontsize=11, fontweight='bold')
            ax6.set_ylabel('Frequency', fontsize=11, fontweight='bold')
            ax6.set_title('Trading Frequency Distribution', fontsize=13, fontweight='bold', pad=10)
            ax6.legend(fontsize=10)
            ax6.grid(axis='y', alpha=0.3)
        else:
            ax6.text(0.5, 0.5, 'Trade timing data\nnot available', 
                    ha='center', va='center', transform=ax6.transAxes, fontsize=12)
            ax6.set_title('Trading Frequency Distribution', fontsize=13, fontweight='bold', pad=10)
    else:
        ax6.text(0.5, 0.5, 'Trade-level data\nnot available', 
                ha='center', va='center', transform=ax6.transAxes, fontsize=12)
        ax6.set_title('Trading Frequency Distribution', fontsize=13, fontweight='bold', pad=10)
    
    # ====================================================================
    # PLOT 7: Cumulative Earnings (if trade data available)
    # ====================================================================
    ax7 = plt.subplot(2, 4, 7)
    
    if len(trades_analysis) > 0:
        for label, trades_df in trades_analysis.items():
            if len(trades_df) > 0 and 'date' in trades_df.columns:
                # Sort by date and calculate cumulative net revenue
                trades_sorted = trades_df.sort_values('date').copy()
                trades_sorted['cumulative_net'] = trades_sorted['net_revenue'].cumsum()
                
                ax7.plot(range(len(trades_sorted)), trades_sorted['cumulative_net'], 
                        marker='o', markersize=4, label=label, color=COLORS[label], linewidth=2)
        
        ax7.set_xlabel('Trade Number', fontsize=11, fontweight='bold')
        ax7.set_ylabel('Cumulative Net Earnings ($)', fontsize=11, fontweight='bold')
        ax7.set_title('Cumulative Earnings Over Time', fontsize=13, fontweight='bold', pad=10)
        ax7.legend(fontsize=10)
        ax7.grid(alpha=0.3)
    else:
        ax7.text(0.5, 0.5, 'Trade-level data\nnot available', 
                ha='center', va='center', transform=ax7.transAxes, fontsize=12)
        ax7.set_title('Cumulative Earnings Over Time', fontsize=13, fontweight='bold', pad=10)
    
    # ====================================================================
    # PLOT 8: Summary Statistics Table
    # ====================================================================
    ax8 = plt.subplot(2, 4, 8)
    ax8.axis('off')
    
    # Prepare summary data
    summary_data = []
    for _, row in comparison_df.iterrows():
        summary_data.append([
            row['label'],
            f"${row['total_revenue']:,.0f}",
            f"${row['net_earnings']:,.0f}",
            f"${row['avg_sale_price']:.0f}",
            f"{row['n_trades']:.0f}",
            f"${row['storage_costs']:,.0f}"
        ])
    
    # Create table
    table = ax8.table(cellText=summary_data,
                     colLabels=['Strategy', 'Gross\nRevenue', 'Net\nEarnings', 
                               'Avg\nPrice', 'Trades', 'Storage\nCosts'],
                     cellLoc='center',
                     loc='center',
                     colWidths=[0.20, 0.18, 0.18, 0.12, 0.10, 0.18])
    
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 2.5)
    
    # Style the header
    for i in range(6):
        cell = table[(0, i)]
        cell.set_facecolor('#2c3e50')
        cell.set_text_props(weight='bold', color='white', fontsize=9)
    
    # Style the rows
    for i in range(1, len(summary_data) + 1):
        for j in range(6):
            cell = table[(i, j)]
            if i % 2 == 0:
                cell.set_facecolor('#ecf0f1')
            # Highlight best values
            if j == 1:  # Gross revenue column
                if summary_data[i-1][1] == max([row[1] for row in summary_data]):
                    cell.set_facecolor('#d5f4e6')
                    cell.set_text_props(weight='bold')
            elif j == 2:  # Net earnings column
                if summary_data[i-1][2] == max([row[2] for row in summary_data]):
                    cell.set_facecolor('#d5f4e6')
                    cell.set_text_props(weight='bold')
    
    ax8.set_title('Summary Statistics', fontsize=13, fontweight='bold', pad=20)
    
    plt.tight_layout(rect=[0, 0, 1, 0.99])
    
    # Save figure
    output_path = f'{BASE_PATH}/three_scenario_analysis_{COMMODITY}.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"\n✓ Saved comprehensive dashboard: {output_path}")
    
    # Display in notebook
    plt.show()
    plt.close()
    
    # ====================================================================
    # 7. Detailed Statistical Report
    # ====================================================================
    print(f"\n{'─'*80}")
    print("FINAL STATISTICAL REPORT")
    print(f"{'─'*80}")
    
    print(f"\nCOMMODITY: {COMMODITY.upper()}")
    print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    print(f"\n{'─'*80}")
    print("SCENARIO PERFORMANCE SUMMARY")
    print(f"{'─'*80}")
    
    for _, row in comparison_df.sort_values('net_earnings', ascending=False).iterrows():
        print(f"\n{row['label']}:")
        print(f"  Strategy: {row['strategy']}")
        print(f"  Net Earnings: ${row['net_earnings']:,.2f}")
        print(f"  Average Sale Price: ${row['avg_sale_price']:.2f}")
        print(f"  Number of Trades: {row['n_trades']:.0f}")
        print(f"  Total Storage Costs: ${row['storage_costs']:,.0f}")
        print(f"  Total Transaction Costs: ${row['transaction_costs']:,.0f}")
    
    print(f"\n{'─'*80}")
    print("KEY FINDINGS: DO PREDICTIONS ADD VALUE?")
    print(f"{'─'*80}")
    
    # Calculate key metrics
    ma_baseline_earnings = ma_baseline['net_earnings']
    ma_prediction_earnings = ma_prediction['net_earnings']
    earnings_advantage = ma_prediction_earnings - ma_baseline_earnings
    pct_advantage = (earnings_advantage / ma_baseline_earnings) * 100
    
    ma_baseline_revenue = ma_baseline['total_revenue']
    ma_prediction_revenue = ma_prediction['total_revenue']
    revenue_advantage = ma_prediction_revenue - ma_baseline_revenue
    revenue_pct_advantage = (revenue_advantage / ma_baseline_revenue) * 100
    
    print(f"\n1. NET EARNINGS IMPROVEMENT (After Costs)")
    print(f"   Moving Average Baseline: ${ma_baseline_earnings:,.2f}")
    print(f"   Moving Average + Predictions: ${ma_prediction_earnings:,.2f}")
    print(f"   Absolute Difference: ${earnings_advantage:,.2f}")
    print(f"   Percentage Improvement: {pct_advantage:+.2f}%")
    
    if earnings_advantage > 0:
        print(f"   ✓ VERDICT: Predictions ADD value on net earnings")
        print(f"     Predictions improve net earnings by {pct_advantage:.1f}%")
    else:
        print(f"   ✗ VERDICT: Predictions DO NOT add value on net earnings")
        print(f"     Predictions reduce net earnings by {abs(pct_advantage):.1f}%")
    
    print(f"\n2. TOTAL REVENUE IMPROVEMENT (Before Costs)")
    print(f"   Moving Average Baseline: ${ma_baseline_revenue:,.2f}")
    print(f"   Moving Average + Predictions: ${ma_prediction_revenue:,.2f}")
    print(f"   Absolute Difference: ${revenue_advantage:,.2f}")
    print(f"   Percentage Improvement: {revenue_pct_advantage:+.2f}%")
    
    if revenue_advantage > 0:
        print(f"   ✓ VERDICT: Predictions ADD value on total revenue")
        print(f"     Predictions improve total revenue by {revenue_pct_advantage:.1f}%")
    else:
        print(f"   ✗ VERDICT: Predictions DO NOT add value on total revenue")
        print(f"     Predictions reduce total revenue by {abs(revenue_pct_advantage):.1f}%")
    
    # Check for disconnect between metrics
    if (earnings_advantage > 0 and revenue_advantage < 0) or (earnings_advantage < 0 and revenue_advantage > 0):
        print(f"\n   ⚠️  CRITICAL INSIGHT: Net and gross show OPPOSITE results!")
        print(f"      This means cost assumptions are driving the difference.")
        if revenue_advantage > 0 and earnings_advantage < 0:
            print(f"      → Predictions generate MORE revenue but HIGHER costs")
            cost_diff = ma_prediction['total_costs'] - ma_baseline['total_costs']
            print(f"      → Extra costs: ${cost_diff:,.2f} (storage: ${ma_prediction['storage_costs'] - ma_baseline['storage_costs']:,.2f})")
        elif revenue_advantage < 0 and earnings_advantage > 0:
            print(f"      → Predictions generate LESS revenue but LOWER costs")
            cost_diff = ma_baseline['total_costs'] - ma_prediction['total_costs']
            print(f"      → Cost savings: ${cost_diff:,.2f}")
    
    print(f"\n3. STATISTICAL SIGNIFICANCE")
    if 'MA Baseline' in ci_results and 'MA + Predictions' in ci_results:
        baseline_ci = ci_results['MA Baseline']
        prediction_ci = ci_results['MA + Predictions']
        
        print(f"   Net Earnings:")
        if ci_overlap_net:
            print(f"      ⚠️  95% Confidence intervals overlap")
            print(f"         Baseline CI: [${baseline_ci['ci_low_earnings']:,.0f}, ${baseline_ci['ci_high_earnings']:,.0f}]")
            print(f"         Prediction CI: [${prediction_ci['ci_low_earnings']:,.0f}, ${prediction_ci['ci_high_earnings']:,.0f}]")
            print(f"         → Difference may not be statistically significant")
        else:
            print(f"      ✓ 95% Confidence intervals DO NOT overlap")
            print(f"         Baseline CI: [${baseline_ci['ci_low_earnings']:,.0f}, ${baseline_ci['ci_high_earnings']:,.0f}]")
            print(f"         Prediction CI: [${prediction_ci['ci_low_earnings']:,.0f}, ${prediction_ci['ci_high_earnings']:,.0f}]")
            print(f"         → Difference is statistically significant")
        
        print(f"\n   Total Revenue:")
        if ci_overlap_revenue:
            print(f"      ⚠️  95% Confidence intervals overlap")
            print(f"         Baseline CI: [${baseline_ci['ci_low_revenue']:,.0f}, ${baseline_ci['ci_high_revenue']:,.0f}]")
            print(f"         Prediction CI: [${prediction_ci['ci_low_revenue']:,.0f}, ${prediction_ci['ci_high_revenue']:,.0f}]")
            print(f"         → Difference may not be statistically significant")
        else:
            print(f"      ✓ 95% Confidence intervals DO NOT overlap")
            print(f"         Baseline CI: [${baseline_ci['ci_low_revenue']:,.0f}, ${baseline_ci['ci_high_revenue']:,.0f}]")
            print(f"         Prediction CI: [${prediction_ci['ci_low_revenue']:,.0f}, ${prediction_ci['ci_high_revenue']:,.0f}]")
            print(f"         → Difference is statistically significant")
    
    print(f"\n4. TRADING BEHAVIOR")
    print(f"   MA Baseline: {ma_baseline['n_trades']:.0f} trades")
    print(f"   MA + Predictions: {ma_prediction['n_trades']:.0f} trades")
    trade_diff = ma_prediction['n_trades'] - ma_baseline['n_trades']
    print(f"   Difference: {trade_diff:+.0f} trades")
    
    if trade_diff > 0:
        print(f"   → Predictions lead to MORE trading activity")
    elif trade_diff < 0:
        print(f"   → Predictions lead to LESS trading activity")
    else:
        print(f"   → No change in trading frequency")
    
    print(f"\n5. COMPARISON TO IMMEDIATE SALE")
    immediate_sale_earnings = immediate_sale['net_earnings']
    immediate_sale_revenue = immediate_sale['total_revenue']
    ma_baseline_vs_imm_net = ((ma_baseline_earnings / immediate_sale_earnings) - 1) * 100
    ma_prediction_vs_imm_net = ((ma_prediction_earnings / immediate_sale_earnings) - 1) * 100
    ma_baseline_vs_imm_rev = ((ma_baseline_revenue / immediate_sale_revenue) - 1) * 100
    ma_prediction_vs_imm_rev = ((ma_prediction_revenue / immediate_sale_revenue) - 1) * 100
    
    print(f"   Net Earnings:")
    print(f"      Immediate Sale: ${immediate_sale_earnings:,.2f}")
    print(f"      MA Baseline: {ma_baseline_vs_imm_net:+.1f}%")
    print(f"      MA + Predictions: {ma_prediction_vs_imm_net:+.1f}%")
    
    print(f"   Total Revenue:")
    print(f"      Immediate Sale: ${immediate_sale_revenue:,.2f}")
    print(f"      MA Baseline: {ma_baseline_vs_imm_rev:+.1f}%")
    print(f"      MA + Predictions: {ma_prediction_vs_imm_rev:+.1f}%")
    
    print(f"\n{'─'*80}")
    print("RECOMMENDATION")
    print(f"{'─'*80}")
    
    # Generate recommendation based on all analysis
    # Consider both net earnings and total revenue
    if (earnings_advantage > 0 and pct_advantage > 5) or (revenue_advantage > 0 and revenue_pct_advantage > 5):
        if not ci_overlap_net:
            recommendation = "STRONG: Use predictions"
            print("\n✓ STRONG RECOMMENDATION: Use predictions")
            print("  Rationale:")
            if earnings_advantage > 0 and pct_advantage > 5:
                print(f"  • Predictions significantly improve net earnings ({pct_advantage:.1f}%)")
            if revenue_advantage > 0 and revenue_pct_advantage > 5:
                print(f"  • Predictions significantly improve total revenue ({revenue_pct_advantage:.1f}%)")
            print("  • Difference is statistically significant")
            print("  • Added complexity is justified by performance gain")
        else:
            recommendation = "WEAK: Use predictions"
            print("\n⚠️  WEAK RECOMMENDATION: Use predictions")
            print("  Rationale:")
            if earnings_advantage > 0:
                print(f"  • Predictions show improved net earnings ({pct_advantage:.1f}%)")
            if revenue_advantage > 0:
                print(f"  • Predictions show improved total revenue ({revenue_pct_advantage:.1f}%)")
            print("  • However, confidence intervals overlap")
            print("  • Consider gathering more data for conclusive results")
    elif (earnings_advantage > 0 and pct_advantage > 0) or (revenue_advantage > 0 and revenue_pct_advantage > 0):
        recommendation = "CONDITIONAL: Consider predictions"
        print("\n⚠️  CONDITIONAL RECOMMENDATION: Consider predictions")
        print("  Rationale:")
        if earnings_advantage > 0:
            print(f"  • Predictions show modest improvement in net earnings ({pct_advantage:.1f}%)")
        if revenue_advantage > 0:
            print(f"  • Predictions show modest improvement in total revenue ({revenue_pct_advantage:.1f}%)")
        if earnings_advantage < 0 and revenue_advantage > 0:
            print(f"  • ⚠️  Net earnings DECREASE but total revenue INCREASES")
            print(f"  • This suggests cost assumptions may be too conservative")
        print("  • Benefit may not justify added complexity")
        print("  • Stick with baseline MA unless marginal gains matter")
    else:
        recommendation = "DO NOT use predictions"
        print("\n✗ RECOMMENDATION: Do NOT use predictions")
        print("  Rationale:")
        print("  • Predictions reduce earnings")
        print("  • Baseline moving average performs better")
        print("  • Added complexity is not justified")
    
    print(f"\n{'='*80}")
    print(f"ANALYSIS COMPLETE - {COMMODITY.upper()}")
    print(f"{'='*80}\n")
    
    # ====================================================================
    # 8. Save Analysis Results
    # ====================================================================
    
    # Save the three-scenario comparison
    comparison_output = {
        'commodity': COMMODITY,
        'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'scenarios': comparison_df.to_dict('records'),
        'ma_baseline_earnings': ma_baseline_earnings,
        'ma_prediction_earnings': ma_prediction_earnings,
        'earnings_advantage': earnings_advantage,
        'pct_advantage': pct_advantage,
        'ma_baseline_revenue': ma_baseline_revenue,
        'ma_prediction_revenue': ma_prediction_revenue,
        'revenue_advantage': revenue_advantage,
        'revenue_pct_advantage': revenue_pct_advantage,
        'confidence_intervals': ci_results if len(ci_results) > 0 else None,
        'ci_overlap_net': ci_overlap_net,
        'ci_overlap_revenue': ci_overlap_revenue,
        't_statistic': t_stat,
        'p_value': p_value,
        'cohens_d': cohens_d,
        'recommendation': recommendation
    }
    
    # Save as pickle
    pkl_path = f'{BASE_PATH}/three_scenario_analysis_{COMMODITY}.pkl'
    with open(pkl_path, 'wb') as f:
        pickle.dump(comparison_output, f)
    print(f"✓ Saved analysis results: {pkl_path}")
    
    # Save as CSV for easy viewing
    csv_path = f'{BASE_PATH}/three_scenario_comparison_{COMMODITY}.csv'
    comparison_df.to_csv(csv_path, index=False)
    print(f"✓ Saved comparison table: {csv_path}")
    
    # Save detailed report as text
    report_path = f'{BASE_PATH}/three_scenario_report_{COMMODITY}.txt'
    with open(report_path, 'w') as f:
        f.write("="*80 + "\n")
        f.write("THREE-SCENARIO TRADING STRATEGY ANALYSIS\n")
        f.write("="*80 + "\n\n")
        f.write(f"Commodity: {COMMODITY.upper()}\n")
        f.write(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("SCENARIOS ANALYZED:\n")
        f.write("-" * 80 + "\n")
        for _, row in comparison_df.iterrows():
            f.write(f"\n{row['label']}:\n")
            f.write(f"  Net Earnings: ${row['net_earnings']:,.2f}\n")
            f.write(f"  Avg Sale Price: ${row['avg_sale_price']:.2f}\n")
            f.write(f"  Trades: {row['n_trades']:.0f}\n")
        
        f.write("\n" + "="*80 + "\n")
        f.write("KEY FINDING: DO PREDICTIONS ADD VALUE?\n")
        f.write("="*80 + "\n\n")
        f.write(f"Earnings Advantage: ${earnings_advantage:,.2f} ({pct_advantage:+.2f}%)\n")
        
        if earnings_advantage > 0:
            f.write("\n✓ VERDICT: Predictions ADD value\n")
        else:
            f.write("\n✗ VERDICT: Predictions DO NOT add value\n")
        
        f.write(f"\nRecommendation: {recommendation}\n")
        
        f.write("\n" + "="*80 + "\n")
    
    print(f"✓ Saved detailed report: {report_path}")
    
    # Add to cross-commodity summary
    all_commodity_summaries.append({
        'commodity': COMMODITY,
        'ma_baseline_earnings': ma_baseline_earnings,
        'ma_prediction_earnings': ma_prediction_earnings,
        'immediate_sale_earnings': immediate_sale_earnings,
        'earnings_advantage': earnings_advantage,
        'pct_advantage': pct_advantage,
        'ma_baseline_revenue': ma_baseline_revenue,
        'ma_prediction_revenue': ma_prediction_revenue,
        'immediate_sale_revenue': immediate_sale_revenue,
        'revenue_advantage': revenue_advantage,
        'revenue_pct_advantage': revenue_pct_advantage,
        'ci_overlap_net': ci_overlap_net,
        'ci_overlap_revenue': ci_overlap_revenue,
        'p_value': p_value,
        'cohens_d': cohens_d,
        'recommendation': recommendation
    })

# COMMAND ----------

# MAGIC %md
# MAGIC ## Cross-Commodity Comparison

# COMMAND ----------

if len(all_commodity_summaries) > 0:
    print("\n" + "="*80)
    print("CROSS-COMMODITY COMPARISON")
    print("="*80)
    
    cross_df = pd.DataFrame(all_commodity_summaries)
    
    print("\nSummary across all commodities:")
    print("\nCommodity Performance:")
    for _, row in cross_df.iterrows():
        print(f"\n{row['commodity'].upper()}:")
        print(f"  MA Baseline:     ${row['ma_baseline_earnings']:,.2f}")
        print(f"  MA + Predictions: ${row['ma_prediction_earnings']:,.2f}")
        print(f"  Advantage:        ${row['earnings_advantage']:,.2f} ({row['pct_advantage']:+.1f}%)")
        print(f"  Recommendation:   {row['recommendation']}")
    
    # Save cross-commodity comparison
    cross_csv_path = f"{BASE_PATH}/cross_commodity_three_scenario_summary.csv"
    cross_df.to_csv(cross_csv_path, index=False)
    print(f"\n✓ Saved: {cross_csv_path}")
    
    # Create cross-commodity visualization
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    fig.suptitle('Cross-Commodity Comparison: Prediction Value-Add', 
                 fontsize=16, fontweight='bold')
    
    # Plot 1: Earnings comparison
    ax1 = axes[0]
    x = np.arange(len(cross_df))
    width = 0.35
    
    ax1.bar(x - width/2, cross_df['ma_baseline_earnings'], width, 
            label='MA Baseline', color='#e74c3c', alpha=0.8)
    ax1.bar(x + width/2, cross_df['ma_prediction_earnings'], width, 
            label='MA + Predictions', color='#2ecc71', alpha=0.8)
    
    ax1.set_xlabel('Commodity', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Net Earnings ($)', fontsize=12, fontweight='bold')
    ax1.set_title('Earnings Comparison by Commodity', fontsize=13, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels([c.title() for c in cross_df['commodity']])
    ax1.legend()
    ax1.grid(axis='y', alpha=0.3)
    
    # Plot 2: Percentage advantage
    ax2 = axes[1]
    colors = ['#2ecc71' if x > 0 else '#e74c3c' for x in cross_df['pct_advantage']]
    bars = ax2.bar(cross_df['commodity'], cross_df['pct_advantage'], color=colors, alpha=0.8)
    
    # Add value labels
    for i, (bar, val) in enumerate(zip(bars, cross_df['pct_advantage'])):
        ax2.text(bar.get_x() + bar.get_width()/2, val, f'{val:+.1f}%', 
                ha='center', va='bottom' if val > 0 else 'top', fontsize=11, fontweight='bold')
    
    ax2.axhline(0, color='black', linewidth=1)
    ax2.set_xlabel('Commodity', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Prediction Advantage (%)', fontsize=12, fontweight='bold')
    ax2.set_title('Percentage Improvement with Predictions', fontsize=13, fontweight='bold')
    ax2.set_xticklabels([c.title() for c in cross_df['commodity']])
    ax2.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    
    cross_viz_path = f'{BASE_PATH}/cross_commodity_comparison.png'
    plt.savefig(cross_viz_path, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"✓ Saved: {cross_viz_path}")
    
    plt.show()
    plt.close()
    
    print("\n" + "="*80)
    print("ALL COMMODITIES ANALYZED")
    print("="*80)
    print(f"Commodities processed: {', '.join([s['commodity'].title() for s in all_commodity_summaries])}")
else:
    print("\n⚠️  WARNING: No commodities were successfully processed!")
    print("   Check for errors above.")

print("\n" + "="*80)
print("BLOCK 09 COMPLETE")
print("="*80)
print(f"\nAll analysis outputs saved to: {BASE_PATH}/")
print("  • Individual commodity dashboards (PNG)")
print("  • Comparison tables (CSV)")
print("  • Detailed analysis (PKL)")
print("  • Text reports (TXT)")
print("  • Cross-commodity comparison (PNG, CSV)")
```
