```python
%run ./00_setup_and_config
```


```python
%run ./03_strategy_implementations
```


```python
# NOTEBOOK 04: BACKTESTING ENGINE (UPDATED)
# ============================================================================
# Databricks notebook source
# MAGIC %md
# MAGIC # Backtesting Engine - Updated for Harvest Cycles
# MAGIC 
# MAGIC Now handles:
# MAGIC - Gradual inventory accumulation during harvest windows
# MAGIC - Multiple harvest cycles across simulation period
# MAGIC - 365-day max holding from harvest window start
# MAGIC - Force liquidation before new harvest begins
# MAGIC - Percentage-based costs (storage and transaction scale with price)

# COMMAND ----------


# COMMAND ----------

import pandas as pd
import numpy as np
import pickle

# COMMAND ----------

class BacktestEngine:
    """
    Backtesting engine for commodity trading strategies.
    Tracks net earnings from selling commodity inventory with harvest cycle awareness.
    Uses percentage-based costs that scale with commodity price.
    """
    
    def __init__(self, prices, prediction_matrices, producer_config):
        """
        Initialize backtest engine with harvest schedule.
        
        Args:
            prices: DataFrame with columns ['date', 'price']
            prediction_matrices: dict mapping dates to N×H prediction arrays
            producer_config: dict with commodity configuration including harvest_windows
        """
        self.prices = prices.copy().sort_values('date').reset_index(drop=True)
        self.prediction_matrices = prediction_matrices
        self.config = producer_config
        
        # Create harvest schedule from config
        self.harvest_schedule = self._create_harvest_schedule()
        
        # Detect prediction structure
        if len(prediction_matrices) > 0:
            sample_matrix = list(prediction_matrices.values())[0]
            self.n_runs = sample_matrix.shape[0]
            self.n_horizons = sample_matrix.shape[1]
            print(f"Backtest engine initialized:")
            print(f"  Commodity: {self.config['commodity']}")
            print(f"  Price days: {len(self.prices)}")
            print(f"  Prediction matrices: {len(self.prediction_matrices)}")
            print(f"  Matrix structure: {self.n_runs} runs × {self.n_horizons} horizons")
            print(f"  Harvest windows: {self.config['harvest_windows']}")
            print(f"  Annual harvest volume: {self.config['harvest_volume']} tons")
            print(f"  Storage cost: {self.config.get('storage_cost_pct_per_day', 'N/A')}% per day")
            print(f"  Transaction cost: {self.config.get('transaction_cost_pct', 'N/A')}% per sale")
            
            # Report harvest schedule stats
            harvest_days = sum(1 for d in self.harvest_schedule.values() if d['is_harvest_day'])
            harvest_starts = sum(1 for d in self.harvest_schedule.values() if d['is_harvest_window_start'])
            print(f"  Harvest days in simulation: {harvest_days}")
            print(f"  Harvest cycles in simulation: {harvest_starts}")
    
    def _create_harvest_schedule(self):
        """
        Create a harvest schedule showing when inventory accumulates.
        Returns dict mapping date -> harvest info
        """
        harvest_schedule = {}
        
        # Get harvest windows from config (list of (start_month, end_month) tuples)
        harvest_windows = self.config['harvest_windows']
        annual_volume = self.config['harvest_volume']
        
        # For each date in prices, determine if it's in a harvest window
        for idx, row in self.prices.iterrows():
            date = row['date']
            month = date.month
            year = date.year
            
            # Check if this date falls in any harvest window
            is_harvest = False
            for start_month, end_month in harvest_windows:
                if start_month <= end_month:
                    # Window within same year (e.g., May-September)
                    if start_month <= month <= end_month:
                        is_harvest = True
                        break
                else:
                    # Window crosses year boundary (e.g., October-December wraps to Jan-Feb)
                    if month >= start_month or month <= end_month:
                        is_harvest = True
                        break
            
            if is_harvest:
                # Calculate which harvest year this belongs to
                # For simplicity, use year if window is in same calendar year,
                # otherwise use year of the start month
                for start_month, end_month in harvest_windows:
                    if start_month <= end_month:
                        if start_month <= month <= end_month:
                            harvest_year = year
                            break
                    else:
                        if month >= start_month:
                            harvest_year = year
                        else:
                            harvest_year = year - 1
                        break
                
                # Determine if this is the first day of the harvest window
                is_window_start = False
                if idx > 0:
                    prev_date = self.prices.loc[idx - 1, 'date']
                    prev_month = prev_date.month
                    prev_was_harvest = False
                    for start_month, end_month in harvest_windows:
                        if start_month <= end_month:
                            if start_month <= prev_month <= end_month:
                                prev_was_harvest = True
                                break
                        else:
                            if prev_month >= start_month or prev_month <= end_month:
                                prev_was_harvest = True
                                break
                    # Window starts if previous day wasn't harvest but today is
                    is_window_start = not prev_was_harvest
                else:
                    # First day of simulation - check if it's start of window
                    is_window_start = (month == harvest_windows[0][0])
                
                # Calculate daily increment
                # Distribute annual volume evenly across all harvest days in the year
                # Count how many harvest days there are in a typical year
                days_in_window = 0
                for start_month, end_month in harvest_windows:
                    if start_month <= end_month:
                        # Simple case: May (5) to Sep (9) = 5 months
                        days_in_window += (end_month - start_month + 1) * 30  # Approximate
                    else:
                        # Cross-year case: Oct (10) to Feb (2) = Oct-Dec + Jan-Feb
                        days_in_window += (12 - start_month + 1 + end_month) * 30
                
                # Daily increment = annual volume / number of days in harvest
                daily_increment = annual_volume / days_in_window if days_in_window > 0 else 0
                
                harvest_schedule[date] = {
                    'is_harvest_day': True,
                    'is_harvest_window_start': is_window_start,
                    'daily_increment': daily_increment,
                    'harvest_year': harvest_year
                }
            else:
                harvest_schedule[date] = {
                    'is_harvest_day': False,
                    'is_harvest_window_start': False,
                    'daily_increment': 0.0,
                    'harvest_year': None
                }
        
        return harvest_schedule
    
    def run(self, strategy):
        """Run backtest for a strategy with harvest cycle tracking"""
        strategy.reset()
        
        # Start with ZERO inventory - will accumulate during harvest
        self.inventory = 0
        self.trades = []
        self.daily_state = []
        self.total_storage_costs = 0
        
        for idx in range(len(self.prices)):
            current_date = self.prices.loc[idx, 'date']
            current_price = self.prices.loc[idx, 'price']
            
            # Get harvest schedule for this date
            schedule = self.harvest_schedule.get(current_date, {
                'is_harvest_window_start': False,
                'is_harvest_day': False,
                'daily_increment': 0.0,
                'harvest_year': None
            })
            
            # CRITICAL: Before new harvest starts, force-liquidate old inventory
            if schedule['is_harvest_window_start'] and self.inventory > 0:
                liquidation = strategy.force_liquidate_before_new_harvest(self.inventory)
                if liquidation and liquidation['action'] == 'SELL':
                    amount = liquidation['amount']
                    self._execute_trade(idx, current_date, current_price, amount, 
                                      liquidation['reason'])
            
            # Check if harvest window is starting (reset 365-day clock)
            if schedule['is_harvest_window_start']:
                strategy.set_harvest_start(idx)
            
            # Add daily harvest increment if in harvest window
            if schedule['is_harvest_day']:
                daily_increment = schedule['daily_increment']
                self.inventory += daily_increment
            else:
                daily_increment = 0.0
            
            # Get predictions and price history
            predictions = self.prediction_matrices.get(current_date, None)
            price_history = self.prices.loc[:idx]
            
            # Get strategy decision
            decision = strategy.decide(idx, self.inventory, current_price, price_history, predictions)
            
            # Execute trades
            if decision['action'] == 'SELL' and decision.get('amount', 0) > 0:
                amount = min(decision['amount'], self.inventory)
                if amount >= self.config.get('min_inventory_to_trade', 0):
                    self._execute_trade(idx, current_date, current_price, amount, decision.get('reason', ''))
            
            # Accumulate storage costs for remaining inventory (percentage-based)
            # Storage cost = inventory × current_price × (storage_cost_pct_per_day / 100)
            storage_cost_pct = self.config.get('storage_cost_pct_per_day', 
                                              self.config.get('storage_cost_per_ton_per_day', 0))
            
            # Convert price from cents/lb to $/ton (cents/lb × 20 = $/ton)
            price_per_ton = current_price * 20
            
            # Check if using percentage-based or legacy fixed cost
            if 'storage_cost_pct_per_day' in self.config:
                daily_storage_cost = self.inventory * price_per_ton * (storage_cost_pct / 100)
            else:
                # Legacy: fixed dollar amount per ton per day
                daily_storage_cost = self.inventory * storage_cost_pct
            
            self.total_storage_costs += daily_storage_cost
            
            # Track daily state (including harvest activity)
            self.daily_state.append({
                'date': current_date,
                'day': idx,
                'price': current_price,
                'inventory': self.inventory,
                'harvest_added': daily_increment,  # Track daily harvest additions
                'is_harvest_window': schedule['is_harvest_day'],  # Track harvest status
                'harvest_year': schedule.get('harvest_year'),  # Track which harvest year
                'daily_storage_cost': daily_storage_cost,
                'cumulative_storage_cost': self.total_storage_costs
            })
        
        # Force liquidation at end if inventory remains
        if self.inventory > 0:
            final_date = self.prices.iloc[-1]['date']
            final_price = self.prices.iloc[-1]['price']
            self._execute_trade(len(self.prices)-1, final_date, final_price, 
                              self.inventory, 'end_of_simulation_forced_liquidation')
        
        # Calculate summary metrics
        total_revenue = sum(t['revenue'] for t in self.trades)
        total_transaction_costs = sum(t['transaction_cost'] for t in self.trades)
        net_earnings = total_revenue - total_transaction_costs - self.total_storage_costs
        
        return {
            'strategy_name': strategy.name,
            'trades': self.trades,
            'daily_state': pd.DataFrame(self.daily_state),
            'total_revenue': total_revenue,
            'total_transaction_costs': total_transaction_costs,
            'total_storage_costs': self.total_storage_costs,
            'net_earnings': net_earnings,
            'harvest_schedule': self.harvest_schedule  # Include for analysis
        }
    
    def _execute_trade(self, day, date, price, amount, reason):
        """Execute a trade and update state with percentage-based transaction costs"""
        # Convert price from cents/lb to $/ton (cents/lb × 20 = $/ton)
        price_per_ton = price * 20
        
        revenue = amount * price_per_ton
        
        # Transaction cost = amount × price × (transaction_cost_pct / 100)
        transaction_cost_pct = self.config.get('transaction_cost_pct',
                                              self.config.get('transaction_cost_per_ton', 0))
        
        # Check if using percentage-based or legacy fixed cost
        if 'transaction_cost_pct' in self.config:
            transaction_cost = amount * price_per_ton * (transaction_cost_pct / 100)
        else:
            # Legacy: fixed dollar amount per ton
            transaction_cost = amount * transaction_cost_pct
        
        net_revenue = revenue - transaction_cost
        
        self.inventory -= amount
        
        self.trades.append({
            'day': day,
            'date': date,
            'price': price,
            'amount': amount,
            'revenue': revenue,
            'transaction_cost': transaction_cost,
            'net_revenue': net_revenue,
            'reason': reason
        })

# COMMAND ----------

def calculate_metrics(results):
    """
    Calculate comprehensive performance metrics including risk-adjusted measures.
    """
    
    trades = results['trades']
    daily_state = results['daily_state']
    
    # Core financial metrics
    total_revenue = results['total_revenue']
    total_transaction_costs = results['total_transaction_costs']
    total_storage_costs = results['total_storage_costs']
    net_earnings = results['net_earnings']
    
    # Trading pattern metrics
    n_trades = len(trades)
    
    if n_trades > 0:
        total_volume = sum(t['amount'] for t in trades)
        avg_sale_price = total_revenue / total_volume if total_volume > 0 else 0
        
        # Days to liquidate
        first_trade_day = trades[0]['day']
        last_trade_day = trades[-1]['day']
        days_to_liquidate = last_trade_day - first_trade_day
        
        # Average days between trades
        if n_trades > 1:
            trade_days = [t['day'] for t in trades]
            days_between_trades = np.mean(np.diff(trade_days))
        else:
            days_between_trades = 0
        
        # First and last sale prices
        first_sale_price = trades[0]['price']
        last_sale_price = trades[-1]['price']
        
    else:
        avg_sale_price = 0
        days_to_liquidate = 0
        days_between_trades = 0
        first_sale_price = 0
        last_sale_price = 0
    
    # Calculate portfolio values over time for risk metrics
    trades_by_day = {t['day']: t for t in trades}
    accumulated_net_proceeds = 0
    portfolio_values = []
    
    for idx, row in daily_state.iterrows():
        day = row['day']
        inventory = row['inventory']
        price = row['price']
        
        # Add net proceeds from any sales today
        if day in trades_by_day:
            trade = trades_by_day[day]
            accumulated_net_proceeds += (trade['revenue'] - trade['transaction_cost'])
        
        # Subtract daily storage costs
        accumulated_net_proceeds -= row['daily_storage_cost']
        
        # Portfolio = net proceeds + remaining inventory market value
        inventory_value = inventory * price
        portfolio_value = accumulated_net_proceeds + inventory_value
        portfolio_values.append(portfolio_value)
    
    portfolio_values = np.array(portfolio_values)
    
    # Calculate risk-return metrics
    if len(portfolio_values) > 1:
        # Daily changes
        daily_changes = np.diff(portfolio_values)
        
        # Total return (from first to last portfolio value)
        initial_value = portfolio_values[0]
        final_value = portfolio_values[-1]
        total_return = (final_value - initial_value) / abs(initial_value) if initial_value != 0 else 0
        
        # Annualized return (assuming ~252 trading days per year)
        n_days = len(portfolio_values)
        annualized_return = (1 + total_return) ** (252 / n_days) - 1 if n_days > 0 else 0
        
        # Volatility (std of daily changes, annualized)
        volatility = np.std(daily_changes) * np.sqrt(252)
        
        # Sharpe ratio (assuming risk-free rate = 0 for simplicity)
        sharpe_ratio = annualized_return / volatility if volatility > 0 else 0
    else:
        total_return = 0
        annualized_return = 0
        volatility = 0
        sharpe_ratio = 0
    
    return {
        'strategy': results['strategy_name'],
        'net_earnings': net_earnings,
        'total_revenue': total_revenue,
        'total_costs': total_transaction_costs + total_storage_costs,
        'transaction_costs': total_transaction_costs,
        'storage_costs': total_storage_costs,
        'avg_sale_price': avg_sale_price,
        'first_sale_price': first_sale_price,
        'last_sale_price': last_sale_price,
        'n_trades': n_trades,
        'days_to_liquidate': days_to_liquidate,
        'avg_days_between_trades': days_between_trades,
        # Risk-return metrics
        'total_return': total_return,
        'annualized_return': annualized_return,
        'volatility': volatility,
        'sharpe_ratio': sharpe_ratio
    }

# COMMAND ----------

print("=" * 80)
print("BACKTESTING ENGINE - MULTI-COMMODITY ANALYSIS")
print("=" * 80)
print("✓ BacktestEngine class ready (with harvest cycle support)")
print("✓ calculate_metrics function ready")
print("\nEngine features:")
print("  - Harvest-aware: tracks inventory accumulation during harvest windows")
print("  - Multi-cycle: handles multiple harvest seasons across simulation")
print("  - Age tracking: enforces 365-day max holding from harvest start")
print("  - Pre-harvest liquidation: forces sale of old inventory before new harvest")
print("  - Percentage-based costs: storage and transaction costs scale with price")
print("  - Data-driven: adapts to actual prediction matrix structure")
print("  - Tracks: net earnings, trades, daily inventory state, harvest events")
print("  - Handles: transaction costs, storage costs, forced liquidation")
print("\nNEW: Inventory starts at zero and accumulates during harvest windows")
print("NEW: Each harvest window resets the 365-day holding period")
print("NEW: Old inventory is liquidated before new harvest begins")
print("NEW: Costs are percentage-based and scale automatically with commodity value")
```
