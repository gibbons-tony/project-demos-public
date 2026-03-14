# Diagnostic 16: Optuna Optimization - ALL 9 Strategies

**Pure in-memory, no SQLite**


```
%run ../00_setup_and_config
```


```
%pip install optuna --quiet
```


```
import sys, os, pandas as pd, numpy as np, pickle
from datetime import datetime
import optuna
from optuna.samplers import TPESampler
import importlib.util

print('='*80)
print('OPTUNA OPTIMIZATION - ALL 9 STRATEGIES')
print('='*80)
```

## Load Strategies


```
if 'all_strategies_pct' in sys.modules:
    del sys.modules['all_strategies_pct']

spec = importlib.util.spec_from_file_location('all_strategies_pct', 'all_strategies_pct.py')
strat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(strat)

ImmediateSaleStrategy = strat.ImmediateSaleStrategy
EqualBatchStrategy = strat.EqualBatchStrategy
PriceThresholdStrategy = strat.PriceThresholdStrategy
MovingAverageStrategy = strat.MovingAverageStrategy
PriceThresholdPredictive = strat.PriceThresholdPredictive
MovingAveragePredictive = strat.MovingAveragePredictive
ExpectedValueStrategy = strat.ExpectedValueStrategy
ConsensusStrategy = strat.ConsensusStrategy
RiskAdjustedStrategy = strat.RiskAdjustedStrategy

print('✓ Loaded ALL 9 strategies')
```

## Load Data


```
COMMODITY = 'coffee'
MODEL_VERSION = 'synthetic_acc90'

DATA_PATHS = get_data_paths(COMMODITY, MODEL_VERSION)
COMMODITY_CONFIG = COMMODITY_CONFIGS[COMMODITY]

COMMODITY_CONFIG['storage_cost_pct_per_day'] = 0.005
COMMODITY_CONFIG['transaction_cost_pct'] = 0.01

prices = spark.table(get_data_paths(COMMODITY)['prices_prepared']).toPandas()
prices['date'] = pd.to_datetime(prices['date'])

with open(DATA_PATHS['prediction_matrices'], 'rb') as f:
    prediction_matrices = pickle.load(f)
prediction_matrices = {pd.to_datetime(k): v for k, v in prediction_matrices.items()}

print(f'✓ Loaded {len(prices)} prices, {len(prediction_matrices)} matrices')
```

## Backtest Engine


```
class Engine:
    def __init__(self, prices_df, pred_matrices, config):
        self.prices = prices_df
        self.pred = pred_matrices
        self.config = config
    
    def run_backtest(self, strategy, inv=50.0):
        inventory, trades, rev, trans, stor = inv, [], 0, 0, 0
        strategy.reset()
        strategy.set_harvest_start(0)
        
        for day in range(len(self.prices)):
            date = self.prices.iloc[day]['date']
            price = self.prices.iloc[day]['price']
            hist = self.prices.iloc[:day+1].copy()
            pred = self.pred.get(date)
            
            dec = strategy.decide(day=day, inventory=inventory, current_price=price, price_history=hist, predictions=pred)
            
            if dec['action'] == 'SELL' and dec['amount'] > 0:
                amt = min(dec['amount'], inventory)
                r = amt * price * 20
                t = r * self.config['transaction_cost_pct'] / 100
                rev += r
                trans += t
                inventory -= amt
            
            if inventory > 0:
                stor += inventory * self.prices.iloc[:day+1]['price'].mean() * 20 * self.config['storage_cost_pct_per_day'] / 100
        
        return {'net_earnings': rev - trans - stor, 'total_revenue': rev, 'num_trades': len(trades), 'storage_costs': stor, 'final_inventory': inventory}

engine = Engine(prices, prediction_matrices, COMMODITY_CONFIG)
print('✓ Engine ready')
```

## Search Spaces - ALL 9 Strategies


```
def get_params(t, s):
    if s == 'immediate_sale':
        return {'min_batch_size': t.suggest_float('min_batch_size', 3.0, 10.0), 'sale_frequency_days': t.suggest_int('sale_frequency_days', 5, 14)}
    
    elif s == 'equal_batch':
        return {'batch_size': t.suggest_float('batch_size', 0.15, 0.30), 'frequency_days': t.suggest_int('frequency_days', 20, 35)}
    
    elif s == 'price_threshold':
        return {'threshold_pct': t.suggest_float('threshold_pct', 0.02, 0.07), 'batch_baseline': t.suggest_float('batch_baseline', 0.20, 0.35), 'batch_overbought_strong': t.suggest_float('batch_overbought_strong', 0.30, 0.40), 'batch_overbought': t.suggest_float('batch_overbought', 0.25, 0.35), 'batch_strong_trend': t.suggest_float('batch_strong_trend', 0.15, 0.25), 'rsi_overbought': t.suggest_int('rsi_overbought', 65, 75), 'rsi_moderate': t.suggest_int('rsi_moderate', 60, 70), 'adx_strong': t.suggest_int('adx_strong', 20, 30), 'cooldown_days': t.suggest_int('cooldown_days', 5, 10), 'max_days_without_sale': t.suggest_int('max_days_without_sale', 45, 75)}
    
    elif s == 'moving_average':
        return {'ma_period': t.suggest_int('ma_period', 20, 35), 'batch_baseline': t.suggest_float('batch_baseline', 0.20, 0.30), 'batch_strong_momentum': t.suggest_float('batch_strong_momentum', 0.15, 0.25), 'batch_overbought': t.suggest_float('batch_overbought', 0.25, 0.35), 'batch_overbought_strong': t.suggest_float('batch_overbought_strong', 0.30, 0.40), 'rsi_overbought': t.suggest_int('rsi_overbought', 65, 75), 'rsi_min': t.suggest_int('rsi_min', 40, 50), 'adx_strong': t.suggest_int('adx_strong', 20, 30), 'adx_weak': t.suggest_int('adx_weak', 15, 25), 'cooldown_days': t.suggest_int('cooldown_days', 5, 10), 'max_days_without_sale': t.suggest_int('max_days_without_sale', 45, 75)}
    
    elif s == 'price_threshold_predictive':
        return {'threshold_pct': t.suggest_float('threshold_pct', 0.02, 0.07), 'batch_baseline': t.suggest_float('batch_baseline', 0.20, 0.35), 'batch_overbought_strong': t.suggest_float('batch_overbought_strong', 0.30, 0.40), 'batch_overbought': t.suggest_float('batch_overbought', 0.25, 0.35), 'batch_strong_trend': t.suggest_float('batch_strong_trend', 0.15, 0.25), 'rsi_overbought': t.suggest_int('rsi_overbought', 65, 75), 'rsi_moderate': t.suggest_int('rsi_moderate', 60, 70), 'adx_strong': t.suggest_int('adx_strong', 20, 30), 'cooldown_days': t.suggest_int('cooldown_days', 5, 10), 'max_days_without_sale': t.suggest_int('max_days_without_sale', 45, 75), 'min_net_benefit_pct': t.suggest_float('min_net_benefit_pct', 0.3, 1.0), 'high_confidence_cv': t.suggest_float('high_confidence_cv', 0.03, 0.08), 'scenario_shift_aggressive': t.suggest_int('scenario_shift_aggressive', 1, 2), 'scenario_shift_conservative': t.suggest_int('scenario_shift_conservative', 1, 2)}
    
    elif s == 'moving_average_predictive':
        return {'ma_period': t.suggest_int('ma_period', 20, 35), 'batch_baseline': t.suggest_float('batch_baseline', 0.20, 0.30), 'batch_strong_momentum': t.suggest_float('batch_strong_momentum', 0.15, 0.25), 'batch_overbought': t.suggest_float('batch_overbought', 0.25, 0.35), 'batch_overbought_strong': t.suggest_float('batch_overbought_strong', 0.30, 0.40), 'rsi_overbought': t.suggest_int('rsi_overbought', 65, 75), 'rsi_min': t.suggest_int('rsi_min', 40, 50), 'adx_strong': t.suggest_int('adx_strong', 20, 30), 'adx_weak': t.suggest_int('adx_weak', 15, 25), 'cooldown_days': t.suggest_int('cooldown_days', 5, 10), 'max_days_without_sale': t.suggest_int('max_days_without_sale', 45, 75), 'min_net_benefit_pct': t.suggest_float('min_net_benefit_pct', 0.3, 1.0), 'high_confidence_cv': t.suggest_float('high_confidence_cv', 0.03, 0.08), 'scenario_shift_aggressive': t.suggest_int('scenario_shift_aggressive', 1, 2), 'scenario_shift_conservative': t.suggest_int('scenario_shift_conservative', 1, 2)}
    
    elif s == 'expected_value':
        return {'min_net_benefit_pct': t.suggest_float('min_net_benefit_pct', 0.3, 1.0), 'negative_threshold_pct': t.suggest_float('negative_threshold_pct', -0.5, -0.1), 'high_confidence_cv': t.suggest_float('high_confidence_cv', 0.03, 0.08), 'medium_confidence_cv': t.suggest_float('medium_confidence_cv', 0.10, 0.15), 'strong_trend_adx': t.suggest_int('strong_trend_adx', 20, 25), 'batch_positive_confident': t.suggest_float('batch_positive_confident', 0.0, 0.05), 'batch_positive_uncertain': t.suggest_float('batch_positive_uncertain', 0.10, 0.20), 'batch_marginal': t.suggest_float('batch_marginal', 0.15, 0.20), 'batch_negative_mild': t.suggest_float('batch_negative_mild', 0.25, 0.30), 'batch_negative_strong': t.suggest_float('batch_negative_strong', 0.35, 0.40), 'cooldown_days': t.suggest_int('cooldown_days', 5, 7), 'baseline_batch': t.suggest_float('baseline_batch', 0.15, 0.20), 'baseline_frequency': t.suggest_int('baseline_frequency', 25, 30)}
    
    elif s == 'consensus':
        return {'consensus_threshold': t.suggest_float('consensus_threshold', 0.60, 0.75), 'very_strong_consensus': t.suggest_float('very_strong_consensus', 0.80, 0.85), 'moderate_consensus': t.suggest_float('moderate_consensus', 0.55, 0.60), 'min_return': t.suggest_float('min_return', 0.02, 0.05), 'min_net_benefit_pct': t.suggest_float('min_net_benefit_pct', 0.3, 0.7), 'high_confidence_cv': t.suggest_float('high_confidence_cv', 0.03, 0.08), 'batch_strong_consensus': t.suggest_float('batch_strong_consensus', 0.0, 0.05), 'batch_moderate': t.suggest_float('batch_moderate', 0.10, 0.20), 'batch_weak': t.suggest_float('batch_weak', 0.25, 0.30), 'batch_bearish': t.suggest_float('batch_bearish', 0.35, 0.40), 'evaluation_day': t.suggest_int('evaluation_day', 10, 14), 'cooldown_days': t.suggest_int('cooldown_days', 5, 7)}
    
    elif s == 'risk_adjusted':
        return {'min_return': t.suggest_float('min_return', 0.02, 0.05), 'min_net_benefit_pct': t.suggest_float('min_net_benefit_pct', 0.3, 0.7), 'max_uncertainty_low': t.suggest_float('max_uncertainty_low', 0.03, 0.08), 'max_uncertainty_medium': t.suggest_float('max_uncertainty_medium', 0.10, 0.20), 'max_uncertainty_high': t.suggest_float('max_uncertainty_high', 0.25, 0.35), 'strong_trend_adx': t.suggest_int('strong_trend_adx', 20, 25), 'batch_low_risk': t.suggest_float('batch_low_risk', 0.0, 0.05), 'batch_medium_risk': t.suggest_float('batch_medium_risk', 0.10, 0.15), 'batch_high_risk': t.suggest_float('batch_high_risk', 0.25, 0.30), 'batch_very_high_risk': t.suggest_float('batch_very_high_risk', 0.35, 0.40), 'evaluation_day': t.suggest_int('evaluation_day', 10, 14), 'cooldown_days': t.suggest_int('cooldown_days', 5, 7)}
    
    raise ValueError(f'Unknown strategy: {s}')

print('✓ ALL search spaces defined')
```

## Optimize Function - Pure In-Memory


```
def opt(cls, name, n=200):
    print(f"\n{'='*80}\n{name}: {n} trials\n{'='*80}")
    
    # Pure in-memory study - NO SQLite
    study = optuna.create_study(direction='maximize', sampler=TPESampler(seed=42))
    
    def obj(trial):
        p = get_params(trial, name)
        
        # Add costs for prediction strategies
        if name not in ['immediate_sale', 'equal_batch', 'price_threshold', 'moving_average']:
            p['storage_cost_pct_per_day'] = COMMODITY_CONFIG['storage_cost_pct_per_day']
            p['transaction_cost_pct'] = COMMODITY_CONFIG['transaction_cost_pct']
        
        try:
            s = cls(**p)
            return engine.run_backtest(s)['net_earnings']
        except Exception as e:
            return -1e9
    
    study.optimize(obj, n_trials=n, show_progress_bar=True)
    print(f'✓ Best: ${study.best_value:,.2f}')
    return study.best_params, study

print('✓ Optimize function ready')
```

## Run ALL 9 Strategies


```
results = {}
```

### 1. Immediate Sale


```
p, s = opt(ImmediateSaleStrategy, 'immediate_sale', 200)
results['immediate_sale'] = (p, s.best_value)
```

### 2. Equal Batch


```
p, s = opt(EqualBatchStrategy, 'equal_batch', 200)
results['equal_batch'] = (p, s.best_value)
```

### 3. Price Threshold


```
p, s = opt(PriceThresholdStrategy, 'price_threshold', 200)
results['price_threshold'] = (p, s.best_value)
```

### 4. Moving Average


```
p, s = opt(MovingAverageStrategy, 'moving_average', 200)
results['moving_average'] = (p, s.best_value)
```

### 5. PT Predictive


```
p, s = opt(PriceThresholdPredictive, 'price_threshold_predictive', 200)
results['price_threshold_predictive'] = (p, s.best_value)
```

### 6. MA Predictive


```
p, s = opt(MovingAveragePredictive, 'moving_average_predictive', 200)
results['moving_average_predictive'] = (p, s.best_value)
```

### 7. Expected Value


```
p, s = opt(ExpectedValueStrategy, 'expected_value', 200)
results['expected_value'] = (p, s.best_value)
```

### 8. Consensus


```
p, s = opt(ConsensusStrategy, 'consensus', 200)
results['consensus'] = (p, s.best_value)
```

### 9. Risk-Adjusted


```
p, s = opt(RiskAdjustedStrategy, 'risk_adjusted', 200)
results['risk_adjusted'] = (p, s.best_value)
```

## Summary


```
print('\n' + '='*80)
print('ALL 9 STRATEGIES COMPLETE')
print('='*80)
for n, (p, v) in sorted(results.items(), key=lambda x: x[1][1], reverse=True):
    print(f'{n:35s}: ${v:,.2f}')
```

## Display Best Parameters


```
print('\n' + '='*80)
print('BEST PARAMETERS FOR EACH STRATEGY')
print('='*80)

for strategy_name, (params, value) in results.items():
    print(f'\n{strategy_name}: ${value:,.2f}')
    print('-' * 40)
    for param, val in sorted(params.items()):
        print(f'  {param:30s}: {val}')
```

## Save Best Parameters for Diagnostic 17


```
# Extract just the parameters (not the values) for diagnostic 17
best_params = {name: params for name, (params, value) in results.items()}

# Add cost parameters to predictive strategies
for strategy in ['price_threshold_predictive', 'moving_average_predictive', 'expected_value', 'consensus', 'risk_adjusted']:
    if strategy in best_params:
        best_params[strategy]['storage_cost_pct_per_day'] = COMMODITY_CONFIG['storage_cost_pct_per_day']
        best_params[strategy]['transaction_cost_pct'] = COMMODITY_CONFIG['transaction_cost_pct']

# Save to pickle file
output_path = 'diagnostic_16_best_params.pkl'
with open(output_path, 'wb') as f:
    pickle.dump(best_params, f)

print(f'\n✓ Saved best parameters to {output_path}')
print(f'  Diagnostic 17 will automatically load these parameters')
```
