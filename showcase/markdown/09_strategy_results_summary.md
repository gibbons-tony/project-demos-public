```python
%run ./00_setup_and_config

```


```python
# NOTEBOOK 09: VISUALIZATION AND REPORTING (MULTI-MODEL)
# ============================================================================
# Databricks notebook source
# MAGIC %md
# MAGIC # Final Report and Dashboard - All Commodities and Model Versions
# MAGIC 
# MAGIC Creates comprehensive reports and visualizations for each commodity and model version
# MAGIC plus cross-model and cross-commodity comparisons.

# COMMAND ----------


# COMMAND ----------

import pandas as pd
import numpy as np
import pickle
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

# COMMAND ----------

# MAGIC %md
# MAGIC ## Generate Individual Commodity and Model Reports

# COMMAND ----------

# Store summaries for cross-commodity and cross-model comparison
all_summaries = []

# Loop through all commodities
for CURRENT_COMMODITY in COMMODITY_CONFIGS.keys():
    print("\n" + "=" * 80)
    print(f"GENERATING REPORTS: {CURRENT_COMMODITY.upper()}")
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
        # Load All Results
        # ----------------------------------------------------------------------
        print(f"\nLoading results...")
        
        try:
            with open(MODEL_DATA_PATHS['results_detailed'], 'rb') as f:
                results_detailed = pickle.load(f)
            
            with open(MODEL_DATA_PATHS['statistical_results'], 'rb') as f:
                stat_results = pickle.load(f)
            
            with open(MODEL_DATA_PATHS['feature_analysis'], 'rb') as f:
                feature_results = pickle.load(f)
            
            with open(MODEL_DATA_PATHS['sensitivity_results'], 'rb') as f:
                sensitivity_results = pickle.load(f)
            
            results_df = spark.table(MODEL_DATA_PATHS['results']).toPandas()
            
            print(f"✓ Loaded all analysis results")
            
        except FileNotFoundError as e:
            print(f"⚠️  Missing file for {CURRENT_COMMODITY} - {MODEL_VERSION}")
            print(f"   {e}")
            continue
        except Exception as e:
            print(f"⚠️  Error loading data: {e}")
            continue
        
        # ----------------------------------------------------------------------
        # Executive Summary
        # ----------------------------------------------------------------------
        print(f"\nGenerating executive summary...")
        
        # Best performers
        best_overall = results_df.loc[results_df['net_earnings'].idxmax()]
        
        baseline_results = results_df[results_df['type'] == 'baseline']
        prediction_results = results_df[results_df['type'] == 'prediction']
        
        best_baseline = baseline_results.loc[baseline_results['net_earnings'].idxmax()] if len(baseline_results) > 0 else None
        best_prediction = prediction_results.loc[prediction_results['net_earnings'].idxmax()] if len(prediction_results) > 0 else None
        
        # Calculate advantage
        if best_baseline is not None and best_prediction is not None:
            earnings_diff = best_prediction['net_earnings'] - best_baseline['net_earnings']
            pct_diff = (earnings_diff / abs(best_baseline['net_earnings'])) * 100 if best_baseline['net_earnings'] != 0 else 0
        else:
            earnings_diff = 0
            pct_diff = 0
        
        # Summary statistics
        summary = {
            'commodity': CURRENT_COMMODITY,
            'model_version': MODEL_VERSION,
            'source_type': 'SYNTHETIC' if MODEL_VERSION.startswith('synthetic_') else 'REAL',
            'best_overall_strategy': best_overall['strategy'],
            'best_overall_earnings': best_overall['net_earnings'],
            'best_baseline_strategy': best_baseline['strategy'] if best_baseline is not None else None,
            'best_baseline_earnings': best_baseline['net_earnings'] if best_baseline is not None else None,
            'best_prediction_strategy': best_prediction['strategy'] if best_prediction is not None else None,
            'best_prediction_earnings': best_prediction['net_earnings'] if best_prediction is not None else None,
            'prediction_advantage_dollars': earnings_diff,
            'prediction_advantage_pct': pct_diff,
            'n_strategies_tested': len(results_df),
            'statistical_significance': stat_results.get('comparisons', pd.DataFrame()).get('significant', pd.Series()).any() if 'comparisons' in stat_results else False
        }
        
        all_summaries.append(summary)
        
        print(f"✓ Executive summary created")
        
        # ----------------------------------------------------------------------
        # Create Summary Report
        # ----------------------------------------------------------------------
        print(f"\nCreating summary report...")
        
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append(f"TRADING STRATEGY ANALYSIS REPORT")
        report_lines.append(f"Commodity: {CURRENT_COMMODITY.upper()}")
        report_lines.append(f"Model: {MODEL_VERSION}")
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("=" * 80)
        report_lines.append("")
        
        report_lines.append("EXECUTIVE SUMMARY")
        report_lines.append("-" * 80)
        report_lines.append(f"Best Overall Strategy: {best_overall['strategy']}")
        report_lines.append(f"  Net Earnings: ${best_overall['net_earnings']:,.2f}")
        report_lines.append(f"  Total Revenue: ${best_overall['total_revenue']:,.2f}")
        report_lines.append(f"  Total Costs: ${best_overall['total_costs']:,.2f}")
        report_lines.append(f"  Number of Trades: {best_overall['n_trades']}")
        report_lines.append("")
        
        if best_baseline is not None:
            report_lines.append(f"Best Baseline Strategy: {best_baseline['strategy']}")
            report_lines.append(f"  Net Earnings: ${best_baseline['net_earnings']:,.2f}")
            report_lines.append("")
        
        if best_prediction is not None:
            report_lines.append(f"Best Prediction Strategy: {best_prediction['strategy']}")
            report_lines.append(f"  Net Earnings: ${best_prediction['net_earnings']:,.2f}")
            report_lines.append(f"  Advantage over Baseline: ${earnings_diff:+,.2f} ({pct_diff:+.1f}%)")
            report_lines.append("")
        
        report_lines.append("STRATEGY COMPARISON")
        report_lines.append("-" * 80)
        for _, row in results_df.sort_values('net_earnings', ascending=False).iterrows():
            report_lines.append(f"{row['strategy']:30s} {row['type']:10s} ${row['net_earnings']:>12,.2f}")
        report_lines.append("")
        
        if 'comparisons' in stat_results and stat_results['comparisons'] is not None and len(stat_results['comparisons']) > 0:
            report_lines.append("STATISTICAL SIGNIFICANCE")
            report_lines.append("-" * 80)
            for _, row in stat_results['comparisons'].iterrows():
                sig_marker = "***" if row['p_value'] < 0.001 else "**" if row['p_value'] < 0.01 else "*" if row['p_value'] < 0.05 else "ns"
                report_lines.append(f"{row['strategy']:30s} p={row['p_value']:.4f} {sig_marker:3s} d={row['cohens_d']:+.3f}")
            report_lines.append("")
        
        if 'feature_importance' in feature_results:
            report_lines.append("FEATURE IMPORTANCE")
            report_lines.append("-" * 80)
            for _, row in feature_results['feature_importance'].iterrows():
                report_lines.append(f"{row['feature']:30s} {row['importance']:.3f}")
            report_lines.append("")
        
        report_lines.append("=" * 80)
        
        report_text = "\n".join(report_lines)
        
        # Save report
        report_path = f'{VOLUME_PATH}/report_{CURRENT_COMMODITY}_{MODEL_VERSION}.txt'
        with open(report_path, 'w') as f:
            f.write(report_text)
        
        print(f"✓ Saved: {report_path}")
        
        # ----------------------------------------------------------------------
        # Create Dashboard Visualization
        # ----------------------------------------------------------------------
        print(f"\nCreating dashboard visualization...")
        
        fig = plt.figure(figsize=(20, 12))
        gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
        
        # 1. Strategy Earnings Comparison
        ax1 = fig.add_subplot(gs[0, :2])
        results_sorted = results_df.sort_values('net_earnings', ascending=False)
        colors = ['orangered' if t == 'prediction' else 'steelblue' for t in results_sorted['type']]
        ax1.barh(results_sorted['strategy'], results_sorted['net_earnings'], color=colors, alpha=0.7)
        ax1.set_xlabel('Net Earnings ($)')
        ax1.set_title(f'Strategy Performance - {CURRENT_COMMODITY.upper()} - {MODEL_VERSION}', fontweight='bold')
        ax1.grid(True, alpha=0.3, axis='x')
        
        # 2. Feature Importance
        if 'feature_importance' in feature_results:
            ax2 = fig.add_subplot(gs[0, 2])
            feat_imp = feature_results['feature_importance'].head(6)
            ax2.barh(feat_imp['feature'], feat_imp['importance'], color='forestgreen', alpha=0.7)
            ax2.set_xlabel('Importance')
            ax2.set_title('Top Features', fontweight='bold')
            ax2.grid(True, alpha=0.3, axis='x')
        
        # 3. Transaction Cost Sensitivity
        if 'transaction_sensitivity' in sensitivity_results:
            ax3 = fig.add_subplot(gs[1, 0])
            trans_sens = sensitivity_results['transaction_sensitivity']
            ax3.plot(trans_sens['cost_multiplier'], trans_sens['prediction_earnings'], 
                    marker='o', label='Prediction', color='orangered')
            ax3.plot(trans_sens['cost_multiplier'], trans_sens['baseline_earnings'], 
                    marker='s', label='Baseline', color='steelblue')
            ax3.set_xlabel('Cost Multiplier')
            ax3.set_ylabel('Net Earnings ($)')
            ax3.set_title('Transaction Cost Sensitivity', fontweight='bold')
            ax3.legend()
            ax3.grid(True, alpha=0.3)
            ax3.axvline(x=1.0, color='black', linestyle='--', alpha=0.5)
        
        # 4. Storage Cost Sensitivity
        if 'storage_sensitivity' in sensitivity_results:
            ax4 = fig.add_subplot(gs[1, 1])
            stor_sens = sensitivity_results['storage_sensitivity']
            ax4.plot(stor_sens['cost_multiplier'], stor_sens['prediction_earnings'], 
                    marker='o', label='Prediction', color='orangered')
            ax4.plot(stor_sens['cost_multiplier'], stor_sens['baseline_earnings'], 
                    marker='s', label='Baseline', color='steelblue')
            ax4.set_xlabel('Cost Multiplier')
            ax4.set_ylabel('Net Earnings ($)')
            ax4.set_title('Storage Cost Sensitivity', fontweight='bold')
            ax4.legend()
            ax4.grid(True, alpha=0.3)
            ax4.axvline(x=1.0, color='black', linestyle='--', alpha=0.5)
        
        # 5. Statistical Comparison
        if 'comparisons' in stat_results and stat_results['comparisons'] is not None and len(stat_results['comparisons']) > 0:
            ax5 = fig.add_subplot(gs[1, 2])
            comp = stat_results['comparisons']
            colors_sig = ['green' if s else 'gray' for s in comp['significant']]
            ax5.barh(comp['strategy'], comp['total_earnings_diff'], color=colors_sig, alpha=0.7)
            ax5.axvline(x=0, color='black', linestyle='-', linewidth=1)
            ax5.set_xlabel('Earnings Advantage ($)')
            ax5.set_title('vs Best Baseline', fontweight='bold')
            ax5.grid(True, alpha=0.3, axis='x')
        
        # 6. Summary Stats Table
        ax6 = fig.add_subplot(gs[2, :])
        ax6.axis('off')
        
        summary_text = f"""
        SUMMARY STATISTICS
        
        Best Overall: {best_overall['strategy']} (${best_overall['net_earnings']:,.2f})
        Best Baseline: {best_baseline['strategy'] if best_baseline is not None else 'N/A'}
        Best Prediction: {best_prediction['strategy'] if best_prediction is not None else 'N/A'}
        
        Prediction Advantage: ${earnings_diff:+,.2f} ({pct_diff:+.1f}%)
        Statistical Significance: {'YES' if summary['statistical_significance'] else 'NO'}
        """
        
        ax6.text(0.1, 0.5, summary_text, fontsize=12, verticalalignment='center', 
                family='monospace')
        
        plt.suptitle(f'Trading Strategy Analysis Dashboard\n{CURRENT_COMMODITY.upper()} - {MODEL_VERSION}', 
                    fontsize=16, fontweight='bold', y=0.98)
        
        dashboard_path = f'{VOLUME_PATH}/dashboard_{CURRENT_COMMODITY}_{MODEL_VERSION}.png'
        plt.savefig(dashboard_path, dpi=300, bbox_inches='tight')
        print(f"✓ Saved: {dashboard_path}")
        plt.close()
        
        print(f"\n✓ Report complete for {MODEL_VERSION}")
    
    print(f"\n{'=' * 80}")
    print(f"✓ {CURRENT_COMMODITY.upper()} COMPLETE")
    print(f"{'=' * 80}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Cross-Model and Cross-Commodity Summary

# COMMAND ----------

print("\n" + "=" * 80)
print("GENERATING CROSS-MODEL AND CROSS-COMMODITY SUMMARY")
print("=" * 80)

if len(all_summaries) > 0:
    summary_df = pd.DataFrame(all_summaries)
    
    print(f"\nTotal combinations analyzed: {len(summary_df)}")
    print(f"  Commodities: {summary_df['commodity'].nunique()}")
    print(f"  Model versions: {summary_df['model_version'].nunique()}")
    
    # Save summary
    summary_csv = f'{VOLUME_PATH}/all_models_summary.csv'
    summary_df.to_csv(summary_csv, index=False)
    print(f"\n✓ Saved: {summary_csv}")
    
    # Display key findings
    print("\nTOP PERFORMERS:")
    print("-" * 80)
    top_10 = summary_df.nlargest(10, 'best_prediction_earnings')
    for _, row in top_10.iterrows():
        print(f"{row['commodity']:10s} {row['model_version']:25s} ${row['best_prediction_earnings']:>12,.2f}  ({row['prediction_advantage_pct']:+6.1f}%)")
    
    print("\n✓ All reports and visualizations complete")
else:
    print("\n⚠️  No summaries generated")

# COMMAND ----------

print("\n" + "=" * 80)
print("VISUALIZATION AND REPORTING COMPLETE")
print("=" * 80)
print(f"\nAll reports and dashboards saved to: {VOLUME_PATH}")
print("\n✓ Block 08 complete")
```
