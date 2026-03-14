```python
%run ./00_setup_and_config

```


```python
# NOTEBOOK 06: STATISTICAL VALIDATION (MULTI-MODEL)
# ============================================================================
# Databricks notebook source
# MAGIC %md
# MAGIC # Statistical Validation - All Commodities and Model Versions
# MAGIC 
# MAGIC Performs statistical tests comparing prediction vs baseline strategies.
# MAGIC Runs for all configured commodities and model versions.

# COMMAND ----------


# COMMAND ----------

import pandas as pd
import numpy as np
from scipy import stats
import pickle

# COMMAND ----------

# MAGIC %md
# MAGIC ## Process All Commodities and Model Versions

# COMMAND ----------

# Loop through all commodities
for CURRENT_COMMODITY in COMMODITY_CONFIGS.keys():
    print("\n" + "=" * 80)
    print(f"STATISTICAL VALIDATION: {CURRENT_COMMODITY.upper()}")
    print("=" * 80)
    
    # Discover all model versions for this commodity
    print(f"\nDiscovering model versions...")
    
    synthetic_versions = []
    try:
        DATA_PATHS = get_data_paths(CURRENT_COMMODITY)
        synthetic_df = spark.table(DATA_PATHS['predictions']).select("model_version").distinct()
        synthetic_versions = [row.model_version for row in synthetic_df.collect()]
    except:
        pass
    
    real_versions = []
    try:
        real_versions = get_model_versions(CURRENT_COMMODITY)
    except:
        pass
    
    all_model_versions = list(set(synthetic_versions + real_versions))
    
    if len(all_model_versions) == 0:
        print(f"⚠️  No model versions found for {CURRENT_COMMODITY}")
        continue
    
    print(f"✓ Found {len(all_model_versions)} model versions")
    
    # Loop through each model version
    for MODEL_VERSION in all_model_versions:
        print(f"\n{'-' * 80}")
        print(f"MODEL: {MODEL_VERSION}")
        print(f"{'-' * 80}")
        
        MODEL_DATA_PATHS = get_data_paths(CURRENT_COMMODITY, MODEL_VERSION)
        
        # ----------------------------------------------------------------------
        # Load Results
        # ----------------------------------------------------------------------
        print(f"\nLoading results...")
        
        try:
            with open(MODEL_DATA_PATHS['results_detailed'], 'rb') as f:
                results_dict = pickle.load(f)
            
            results_df = spark.table(MODEL_DATA_PATHS['results']).toPandas()
            
            print(f"✓ Loaded results for {len(results_dict)} strategies")
        except Exception as e:
            print(f"⚠️  Could not load results: {e}")
            continue
        
        # ----------------------------------------------------------------------
        # Identify Best Baseline
        # ----------------------------------------------------------------------
        baseline_names = ['Immediate Sale', 'Equal Batches', 'Price Threshold', 'Moving Average']
        baseline_results = results_df[results_df['strategy'].isin(baseline_names)]
        
        if len(baseline_results) == 0:
            print("⚠️  No baseline results found")
            continue
        
        best_baseline = baseline_results.sort_values('net_earnings', ascending=False).iloc[0]['strategy']
        
        print("\nBaseline Comparison:")
        print(f"  Best baseline: {best_baseline}")
        print(f"  Net Earnings: ${baseline_results.loc[baseline_results['strategy'] == best_baseline, 'net_earnings'].iloc[0]:,.2f}")
        
        # ----------------------------------------------------------------------
        # Extract Time Series Data
        # ----------------------------------------------------------------------
        def get_daily_portfolio_values(results, initial_price):
            """Calculate daily portfolio value = remaining inventory value + accumulated net proceeds"""
            daily_state = results['daily_state']
            trades_by_day = {t['day']: t for t in results['trades']}
            
            accumulated_net_proceeds = 0
            portfolio_values = []
            
            for idx, row in daily_state.iterrows():
                day = row['day']
                inventory = row['inventory']
                price = row['price']
                
                if day in trades_by_day:
                    trade = trades_by_day[day]
                    accumulated_net_proceeds += trade['net_revenue']
                
                inventory_value = inventory * price
                portfolio_value = accumulated_net_proceeds + inventory_value
                portfolio_values.append(portfolio_value)
            
            return np.array(portfolio_values)
        
        print("\nExtracting time series data...")
        initial_price = results_dict[list(results_dict.keys())[0]]['daily_state']['price'].iloc[0]
        
        portfolio_values_dict = {}
        for name, results in results_dict.items():
            pv = get_daily_portfolio_values(results, initial_price)
            portfolio_values_dict[name] = pv
        
        print(f"✓ Extracted time series for {len(portfolio_values_dict)} strategies")
        
        # ----------------------------------------------------------------------
        # Statistical Tests - Predictions vs Best Baseline
        # ----------------------------------------------------------------------
        def get_daily_changes(portfolio_values):
            """Get daily changes in portfolio value"""
            changes = np.diff(portfolio_values)
            return changes
        
        print("\nRunning statistical tests...")
        
        baseline_pv = portfolio_values_dict[best_baseline]
        baseline_changes = get_daily_changes(baseline_pv)
        
        prediction_names = ['Consensus', 'Expected Value', 'Risk-Adjusted']
        comparison_results = []
        
        for pred_strat in prediction_names:
            if pred_strat in portfolio_values_dict:
                pred_pv = portfolio_values_dict[pred_strat]
                pred_changes = get_daily_changes(pred_pv)
                
                # Align lengths
                min_len = min(len(baseline_changes), len(pred_changes))
                baseline_changes_aligned = baseline_changes[:min_len]
                pred_changes_aligned = pred_changes[:min_len]
                
                # Paired t-test on daily changes
                diff = pred_changes_aligned - baseline_changes_aligned
                t_stat, p_value = stats.ttest_rel(pred_changes_aligned, baseline_changes_aligned)
                
                # Effect size (Cohen's d)
                cohens_d = np.mean(diff) / np.std(diff) if np.std(diff) > 0 else 0
                
                # Confidence interval
                ci = stats.t.interval(0.95, len(diff)-1, loc=np.mean(diff), scale=stats.sem(diff))
                
                # Mean difference per day (in dollars)
                mean_daily_diff = np.mean(diff)
                
                # Final earnings difference
                pred_earnings = results_df[results_df['strategy'] == pred_strat]['net_earnings'].iloc[0]
                baseline_earnings = results_df[results_df['strategy'] == best_baseline]['net_earnings'].iloc[0]
                earnings_diff = pred_earnings - baseline_earnings
                
                comparison_results.append({
                    'strategy': pred_strat,
                    'baseline': best_baseline,
                    't_statistic': t_stat,
                    'p_value': p_value,
                    'significant': p_value < 0.05,
                    'cohens_d': cohens_d,
                    'mean_daily_diff': mean_daily_diff,
                    'ci_lower': ci[0],
                    'ci_upper': ci[1],
                    'total_earnings_diff': earnings_diff
                })
                
                print(f"\n  {pred_strat} vs {best_baseline}:")
                print(f"    Earnings diff: ${earnings_diff:+,.2f}")
                print(f"    p-value: {p_value:.4f} {'***' if p_value < 0.001 else '**' if p_value < 0.01 else '*' if p_value < 0.05 else 'ns'}")
                print(f"    Significant: {'YES' if p_value < 0.05 else 'NO'}")
                print(f"    Cohen's d: {cohens_d:+.3f}")
        
        if len(comparison_results) > 0:
            comparison_df = pd.DataFrame(comparison_results)
        else:
            comparison_df = pd.DataFrame()
        
        # ----------------------------------------------------------------------
        # Bootstrap Confidence Intervals
        # ----------------------------------------------------------------------
        def bootstrap_earnings(portfolio_values, n_boot=1000):
            """Bootstrap confidence intervals for final net earnings"""
            daily_changes = get_daily_changes(portfolio_values)
            initial_value = portfolio_values[0]
            
            final_values = []
            
            for _ in range(n_boot):
                resampled_changes = np.random.choice(daily_changes, size=len(daily_changes), replace=True)
                final_value = initial_value + np.sum(resampled_changes)
                final_values.append(final_value)
            
            final_values = np.array(final_values)
            
            return {
                'mean': np.mean(final_values),
                'median': np.median(final_values),
                'std': np.std(final_values),
                'ci_lower': np.percentile(final_values, 2.5),
                'ci_upper': np.percentile(final_values, 97.5)
            }
        
        print("\nBootstrapping confidence intervals...")
        
        bootstrap_results = {}
        strategies_to_test = prediction_names + [best_baseline]
        
        for name in strategies_to_test:
            if name in portfolio_values_dict:
                bootstrap_results[name] = bootstrap_earnings(
                    portfolio_values_dict[name], 
                    n_boot=ANALYSIS_CONFIG['bootstrap_iterations']
                )
        
        # Create bootstrap summary table
        bootstrap_df = pd.DataFrame(bootstrap_results).T
        bootstrap_df = bootstrap_df.reset_index().rename(columns={'index': 'strategy'})
        bootstrap_df = bootstrap_df.sort_values('mean', ascending=False)
        
        print(f"✓ Bootstrap complete for {len(bootstrap_results)} strategies")
        
        # ----------------------------------------------------------------------
        # Summary Statistics
        # ----------------------------------------------------------------------
        summary_stats = []
        for name in [best_baseline] + prediction_names:
            if name in results_df['strategy'].values:
                row = results_df[results_df['strategy'] == name].iloc[0]
                stats_dict = {
                    'strategy': name,
                    'type': row['type'],
                    'net_earnings': row['net_earnings'],
                    'avg_sale_price': row['avg_sale_price'],
                    'total_costs': row['total_costs'],
                    'n_trades': row['n_trades']
                }
                
                if name in bootstrap_results:
                    stats_dict['earnings_ci_width'] = bootstrap_results[name]['ci_upper'] - bootstrap_results[name]['ci_lower']
                
                summary_stats.append(stats_dict)
        
        summary_df = pd.DataFrame(summary_stats)
        summary_df = summary_df.sort_values('net_earnings', ascending=False)
        
        # ----------------------------------------------------------------------
        # Save Results
        # ----------------------------------------------------------------------
        print("\nSaving results...")
        
        stat_results = {
            'commodity': CURRENT_COMMODITY,
            'model_version': MODEL_VERSION,
            'comparisons': comparison_df if len(comparison_results) > 0 else None,
            'bootstrap': bootstrap_results,
            'bootstrap_summary': bootstrap_df,
            'summary_stats': summary_df,
            'best_baseline': best_baseline
        }
        
        with open(MODEL_DATA_PATHS['statistical_results'], 'wb') as f:
            pickle.dump(stat_results, f)
        print(f"  ✓ Saved: {MODEL_DATA_PATHS['statistical_results']}")
        
        # Save as CSV for easy viewing
        if len(comparison_results) > 0:
            comparison_df.to_csv(MODEL_DATA_PATHS['statistical_comparisons'], index=False)
            print(f"  ✓ Saved: {MODEL_DATA_PATHS['statistical_comparisons']}")
        
        bootstrap_df.to_csv(MODEL_DATA_PATHS['bootstrap_summary'], index=False)
        summary_df.to_csv(MODEL_DATA_PATHS['summary_stats'], index=False)
        print(f"  ✓ Saved: {MODEL_DATA_PATHS['bootstrap_summary']}")
        print(f"  ✓ Saved: {MODEL_DATA_PATHS['summary_stats']}")
        
        # ----------------------------------------------------------------------
        # Print Key Findings
        # ----------------------------------------------------------------------
        print(f"\n{'='*80}")
        print(f"✓ STATISTICAL VALIDATION COMPLETE - {CURRENT_COMMODITY.upper()} - {MODEL_VERSION}")
        print(f"{'='*80}")
        
        if len(comparison_results) > 0:
            print(f"\nKey findings:")
            print(f"  Best baseline: {best_baseline}")
            
            best_pred_result = comparison_df.loc[comparison_df['total_earnings_diff'].idxmax()]
            print(f"  Best prediction strategy: {best_pred_result['strategy']}")
            print(f"  Earnings advantage: ${best_pred_result['total_earnings_diff']:+,.2f}")
            print(f"  Statistical significance: {'YES (p < 0.05)' if best_pred_result['significant'] else 'NO (p >= 0.05)'}")
            print(f"  Effect size: {best_pred_result['cohens_d']:.3f}")

# COMMAND ----------

print("\n" + "=" * 80)
print("ALL STATISTICAL VALIDATIONS COMPLETE")
print("=" * 80)
print(f"Commodities analyzed: {', '.join([c.upper() for c in COMMODITY_CONFIGS.keys()])}")
print("\n✓ Statistical validation complete for all commodities and models")
```
