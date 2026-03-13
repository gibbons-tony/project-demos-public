"""
Production Backtesting Engine

Extracted from 04_backtesting_engine.ipynb with harvest-based inventory
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any


class BacktestEngine:
    """
    Production backtesting engine with harvest-based inventory.

    Key features:
    - Harvest cycles: Inventory accumulates during harvest windows (starts at 0)
    - Price conversion: price_per_ton = price * 20 (cents/lb to $/ton)
    - Percentage-based costs: Storage and transaction scale with commodity value
    - Multi-cycle support: Handles multiple harvest seasons
    - Force liquidation: 365-day max holding, pre-harvest liquidation
    """

    def __init__(self, prices: pd.DataFrame, prediction_matrices: Dict, producer_config: Dict):
        """
        Initialize backtest engine.

        Args:
            prices: DataFrame with columns ['date', 'price']
            prediction_matrices: dict mapping dates to N×H prediction arrays
            producer_config: dict with commodity configuration:
                - commodity: str
                - harvest_volume: float (tons/year)
                - harvest_windows: list of (start_month, end_month) tuples
                - storage_cost_pct_per_day: float
                - transaction_cost_pct: float
                - max_holding_days: int (default 365)
                - min_inventory_to_trade: float (default 1.0)
        """
        self.prices = prices.copy().sort_values('date').reset_index(drop=True)
        self.prediction_matrices = prediction_matrices
        self.config = producer_config

        # Create harvest schedule
        self.harvest_schedule = self._create_harvest_schedule()

        # Detect prediction structure
        if len(prediction_matrices) > 0:
            sample_matrix = list(prediction_matrices.values())[0]
            self.n_runs = sample_matrix.shape[0]
            self.n_horizons = sample_matrix.shape[1]

    def _create_harvest_schedule(self) -> Dict:
        """
        Create harvest schedule showing when inventory accumulates.

        Returns:
            dict mapping date -> harvest info
        """
        harvest_schedule = {}
        harvest_windows = self.config['harvest_windows']
        annual_volume = self.config['harvest_volume']

        # Calculate days in harvest windows (approximate)
        days_in_window = 0
        for start_month, end_month in harvest_windows:
            if start_month <= end_month:
                days_in_window += (end_month - start_month + 1) * 30
            else:
                days_in_window += (12 - start_month + 1 + end_month) * 30

        daily_increment = annual_volume / days_in_window if days_in_window > 0 else 0

        for idx, row in self.prices.iterrows():
            date = row['date']
            month = date.month

            # Check if in harvest window
            is_harvest = False
            for start_month, end_month in harvest_windows:
                if start_month <= end_month:
                    if start_month <= month <= end_month:
                        is_harvest = True
                        break
                else:
                    if month >= start_month or month <= end_month:
                        is_harvest = True
                        break

            # Check if harvest window start
            is_window_start = False
            if idx > 0 and is_harvest:
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
                is_window_start = not prev_was_harvest
            elif idx == 0 and is_harvest:
                is_window_start = (month == harvest_windows[0][0])

            harvest_schedule[date] = {
                'is_harvest_day': is_harvest,
                'is_harvest_window_start': is_window_start,
                'daily_increment': daily_increment if is_harvest else 0.0,
                'harvest_year': date.year if is_harvest else None
            }

        return harvest_schedule

    def run(self, strategy) -> Dict:
        """
        Run backtest for a strategy.

        Args:
            strategy: Trading strategy object with decide() and reset() methods

        Returns:
            dict with:
                - strategy_name: str
                - trades: list of trade dicts
                - daily_state: DataFrame
                - total_revenue: float
                - total_transaction_costs: float
                - total_storage_costs: float
                - net_earnings: float
                - harvest_schedule: dict
        """
        strategy.reset()

        # Start with ZERO inventory (accumulates during harvest)
        self.inventory = 0.0
        self.trades = []
        self.daily_state = []
        self.total_storage_costs = 0.0
        self.cumulative_revenue = 0.0  # Track cumulative revenue for daily_state
        self.cumulative_transaction_costs = 0.0  # Track cumulative transaction costs

        for idx in range(len(self.prices)):
            current_date = self.prices.loc[idx, 'date']
            current_price = self.prices.loc[idx, 'price']

            schedule = self.harvest_schedule.get(current_date, {
                'is_harvest_window_start': False,
                'is_harvest_day': False,
                'daily_increment': 0.0,
                'harvest_year': None
            })

            # Force liquidation before new harvest
            if schedule['is_harvest_window_start'] and self.inventory > 0:
                liquidation = strategy.force_liquidate_before_new_harvest(self.inventory)
                if liquidation and liquidation['action'] == 'SELL':
                    amount = liquidation['amount']
                    self._execute_trade(idx, current_date, current_price, amount,
                                      liquidation['reason'])

            # Reset harvest start day tracking
            if schedule['is_harvest_window_start']:
                strategy.set_harvest_start(idx)

            # Add daily harvest increment
            if schedule['is_harvest_day']:
                self.inventory += schedule['daily_increment']

            # Get strategy decision
            predictions = self.prediction_matrices.get(current_date, None)
            price_history = self.prices.loc[:idx]

            decision = strategy.decide(
                idx, self.inventory, current_price, price_history, predictions
            )

            # Execute trade
            if decision['action'] == 'SELL' and decision.get('amount', 0) > 0:
                amount = min(decision['amount'], self.inventory)
                min_trade = self.config.get('min_inventory_to_trade', 0)
                if amount >= min_trade:
                    self._execute_trade(idx, current_date, current_price, amount,
                                      decision.get('reason', ''))

            # Calculate storage costs (percentage-based, with * 20 multiplier)
            price_per_ton = current_price * 20
            storage_cost_pct = self.config['storage_cost_pct_per_day']
            daily_storage_cost = self.inventory * price_per_ton * (storage_cost_pct / 100)
            self.total_storage_costs += daily_storage_cost

            # Calculate cash position (revenue - costs)
            cash = self.cumulative_revenue - self.cumulative_transaction_costs - self.total_storage_costs

            # Track daily state
            self.daily_state.append({
                'date': current_date,
                'day': idx,
                'price': current_price,
                'inventory': self.inventory,
                'harvest_added': schedule['daily_increment'],
                'is_harvest_window': schedule['is_harvest_day'],
                'harvest_year': schedule['harvest_year'],
                'daily_storage_cost': daily_storage_cost,
                'cumulative_storage_cost': self.total_storage_costs,
                'cumulative_revenue': self.cumulative_revenue,
                'cumulative_transaction_costs': self.cumulative_transaction_costs,
                'cash': cash  # Net cash position
            })

        # Final liquidation
        if self.inventory > 0:
            final_date = self.prices.iloc[-1]['date']
            final_price = self.prices.iloc[-1]['price']
            self._execute_trade(len(self.prices) - 1, final_date, final_price,
                              self.inventory, 'end_of_simulation_forced_liquidation')

        # Calculate summary
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
            'harvest_schedule': self.harvest_schedule
        }

    def run_backtest(self, strategy) -> Dict:
        """
        Compatibility wrapper for run() method.

        The optimizer calls run_backtest() but the production engine uses run().
        This wrapper provides backward compatibility.
        """
        return self.run(strategy)

    def _execute_trade(self, day: int, date, price: float, amount: float, reason: str):
        """
        Execute trade with production formulas.

        CRITICAL: Uses price_per_ton = price * 20 conversion
        """
        # Convert price from cents/lb to $/ton
        price_per_ton = price * 20

        # Calculate revenue
        revenue = amount * price_per_ton

        # Calculate transaction cost (percentage-based)
        transaction_cost_pct = self.config['transaction_cost_pct']
        transaction_cost = amount * price_per_ton * (transaction_cost_pct / 100)

        # Track cumulative totals for daily_state
        self.cumulative_revenue += revenue
        self.cumulative_transaction_costs += transaction_cost

        net_revenue = revenue - transaction_cost

        # Update inventory
        self.inventory -= amount

        # Record trade
        self.trades.append({
            'day': day,
            'date': date,
            'price': price,
            'price_per_ton': price_per_ton,
            'amount': amount,
            'revenue': revenue,
            'transaction_cost': transaction_cost,
            'net_revenue': net_revenue,
            'reason': reason
        })


def calculate_metrics(results: Dict) -> Dict:
    """
    Calculate comprehensive performance metrics.

    Args:
        results: Output from BacktestEngine.run()

    Returns:
        dict with performance metrics
    """
    trades = results['trades']
    daily_state = results['daily_state']

    # Core metrics
    total_revenue = results['total_revenue']
    total_transaction_costs = results['total_transaction_costs']
    total_storage_costs = results['total_storage_costs']
    net_earnings = results['net_earnings']

    # Trading metrics
    n_trades = len(trades)

    if n_trades > 0:
        total_volume = sum(t['amount'] for t in trades)
        avg_sale_price = total_revenue / total_volume if total_volume > 0 else 0

        first_trade_day = trades[0]['day']
        last_trade_day = trades[-1]['day']
        days_to_liquidate = last_trade_day - first_trade_day

        if n_trades > 1:
            trade_days = [t['day'] for t in trades]
            days_between_trades = np.mean(np.diff(trade_days))
        else:
            days_between_trades = 0

        first_sale_price = trades[0]['price']
        last_sale_price = trades[-1]['price']
    else:
        avg_sale_price = 0
        days_to_liquidate = 0
        days_between_trades = 0
        first_sale_price = 0
        last_sale_price = 0

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
        'avg_days_between_trades': days_between_trades
    }


def calculate_metrics_by_year(results: Dict) -> Dict[int, Dict]:
    """
    Calculate performance metrics broken down by year.

    Since different forecast models have different time periods,
    year-by-year comparison enables fair comparison across models.

    Args:
        results: Output from BacktestEngine.run()

    Returns:
        Dict mapping {year: metrics_dict}
    """
    import pandas as pd

    trades = results['trades']
    daily_state = results['daily_state']

    # Group trades by year
    trades_by_year = {}
    for trade in trades:
        year = trade['date'].year
        if year not in trades_by_year:
            trades_by_year[year] = []
        trades_by_year[year].append(trade)

    # Group daily state by year
    daily_by_year = {}
    # Convert DataFrame to list of dicts if it's a DataFrame
    daily_state_records = daily_state.to_dict('records') if isinstance(daily_state, pd.DataFrame) else daily_state
    for state in daily_state_records:
        year = state['date'].year
        if year not in daily_by_year:
            daily_by_year[year] = []
        daily_by_year[year].append(state)

    # Calculate metrics for each year
    metrics_by_year = {}

    for year in sorted(set(list(trades_by_year.keys()) + list(daily_by_year.keys()))):
        year_trades = trades_by_year.get(year, [])
        year_daily = daily_by_year.get(year, [])

        # Calculate year totals
        year_revenue = sum(t['revenue'] for t in year_trades)
        year_transaction_costs = sum(t['transaction_cost'] for t in year_trades)

        # Calculate storage costs for this year
        year_storage_costs = 0.0
        for state in year_daily:
            # Handle both old format (storage_cost) and new format (daily_storage_cost)
            if 'daily_storage_cost' in state:
                year_storage_costs += state['daily_storage_cost']
            elif 'storage_cost' in state:
                year_storage_costs += state['storage_cost']

        year_net_earnings = year_revenue - year_transaction_costs - year_storage_costs

        # Trading metrics
        n_trades = len(year_trades)

        if n_trades > 0:
            total_volume = sum(t['amount'] for t in year_trades)
            avg_sale_price = year_revenue / total_volume if total_volume > 0 else 0

            first_trade_day = year_trades[0]['day']
            last_trade_day = year_trades[-1]['day']
            days_to_liquidate = last_trade_day - first_trade_day

            if n_trades > 1:
                trade_days = [t['day'] for t in year_trades]
                days_between_trades = float(np.mean(np.diff(trade_days)))
            else:
                days_between_trades = 0.0

            first_sale_price = year_trades[0]['price']
            last_sale_price = year_trades[-1]['price']
        else:
            avg_sale_price = 0.0
            days_to_liquidate = 0
            days_between_trades = 0.0
            first_sale_price = 0.0
            last_sale_price = 0.0

        metrics_by_year[year] = {
            'year': year,
            'strategy': results['strategy_name'],
            'net_earnings': year_net_earnings,
            'total_revenue': year_revenue,
            'total_costs': year_transaction_costs + year_storage_costs,
            'transaction_costs': year_transaction_costs,
            'storage_costs': year_storage_costs,
            'avg_sale_price': avg_sale_price,
            'first_sale_price': first_sale_price,
            'last_sale_price': last_sale_price,
            'n_trades': n_trades,
            'days_to_liquidate': days_to_liquidate,
            'avg_days_between_trades': days_between_trades,
            'n_days_in_year': len(year_daily)
        }

    return metrics_by_year


def calculate_metrics_by_quarter(results: Dict) -> Dict[str, Dict]:
    """
    Calculate performance metrics broken down by quarter.

    Args:
        results: Output from BacktestEngine.run()

    Returns:
        Dict mapping {quarter_key: metrics_dict} where quarter_key is "YYYY-QN"
    """
    import pandas as pd

    trades = results['trades']
    daily_state = results['daily_state']

    # Group trades by quarter
    trades_by_quarter = {}
    for trade in trades:
        quarter_key = f"{trade['date'].year}-Q{(trade['date'].month - 1) // 3 + 1}"
        if quarter_key not in trades_by_quarter:
            trades_by_quarter[quarter_key] = []
        trades_by_quarter[quarter_key].append(trade)

    # Group daily state by quarter
    daily_by_quarter = {}
    daily_state_records = daily_state.to_dict('records') if isinstance(daily_state, pd.DataFrame) else daily_state
    for state in daily_state_records:
        quarter_key = f"{state['date'].year}-Q{(state['date'].month - 1) // 3 + 1}"
        if quarter_key not in daily_by_quarter:
            daily_by_quarter[quarter_key] = []
        daily_by_quarter[quarter_key].append(state)

    # Calculate metrics for each quarter
    metrics_by_quarter = {}

    for quarter_key in sorted(set(list(trades_by_quarter.keys()) + list(daily_by_quarter.keys()))):
        quarter_trades = trades_by_quarter.get(quarter_key, [])
        quarter_daily = daily_by_quarter.get(quarter_key, [])

        # Calculate quarter totals
        quarter_revenue = sum(t['revenue'] for t in quarter_trades)
        quarter_transaction_costs = sum(t['transaction_cost'] for t in quarter_trades)

        # Calculate storage costs for this quarter
        quarter_storage_costs = 0.0
        for state in quarter_daily:
            if 'daily_storage_cost' in state:
                quarter_storage_costs += state['daily_storage_cost']
            elif 'storage_cost' in state:
                quarter_storage_costs += state['storage_cost']

        quarter_net_earnings = quarter_revenue - quarter_transaction_costs - quarter_storage_costs

        # Trading metrics
        n_trades = len(quarter_trades)

        if n_trades > 0:
            total_volume = sum(t['amount'] for t in quarter_trades)
            avg_sale_price = quarter_revenue / total_volume if total_volume > 0 else 0
            first_sale_price = quarter_trades[0]['price']
            last_sale_price = quarter_trades[-1]['price']
        else:
            avg_sale_price = 0.0
            first_sale_price = 0.0
            last_sale_price = 0.0

        year, quarter = quarter_key.split('-Q')
        metrics_by_quarter[quarter_key] = {
            'year': int(year),
            'quarter': int(quarter),
            'quarter_key': quarter_key,
            'strategy': results['strategy_name'],
            'net_earnings': quarter_net_earnings,
            'total_revenue': quarter_revenue,
            'total_costs': quarter_transaction_costs + quarter_storage_costs,
            'transaction_costs': quarter_transaction_costs,
            'storage_costs': quarter_storage_costs,
            'avg_sale_price': avg_sale_price,
            'first_sale_price': first_sale_price,
            'last_sale_price': last_sale_price,
            'n_trades': n_trades,
            'n_days_in_quarter': len(quarter_daily)
        }

    return metrics_by_quarter


def calculate_metrics_by_month(results: Dict) -> Dict[str, Dict]:
    """
    Calculate performance metrics broken down by month.

    Args:
        results: Output from BacktestEngine.run()

    Returns:
        Dict mapping {month_key: metrics_dict} where month_key is "YYYY-MM"
    """
    import pandas as pd

    trades = results['trades']
    daily_state = results['daily_state']

    # Group trades by month
    trades_by_month = {}
    for trade in trades:
        month_key = f"{trade['date'].year}-{trade['date'].month:02d}"
        if month_key not in trades_by_month:
            trades_by_month[month_key] = []
        trades_by_month[month_key].append(trade)

    # Group daily state by month
    daily_by_month = {}
    daily_state_records = daily_state.to_dict('records') if isinstance(daily_state, pd.DataFrame) else daily_state
    for state in daily_state_records:
        month_key = f"{state['date'].year}-{state['date'].month:02d}"
        if month_key not in daily_by_month:
            daily_by_month[month_key] = []
        daily_by_month[month_key].append(state)

    # Calculate metrics for each month
    metrics_by_month = {}

    for month_key in sorted(set(list(trades_by_month.keys()) + list(daily_by_month.keys()))):
        month_trades = trades_by_month.get(month_key, [])
        month_daily = daily_by_month.get(month_key, [])

        # Calculate month totals
        month_revenue = sum(t['revenue'] for t in month_trades)
        month_transaction_costs = sum(t['transaction_cost'] for t in month_trades)

        # Calculate storage costs for this month
        month_storage_costs = 0.0
        for state in month_daily:
            if 'daily_storage_cost' in state:
                month_storage_costs += state['daily_storage_cost']
            elif 'storage_cost' in state:
                month_storage_costs += state['storage_cost']

        month_net_earnings = month_revenue - month_transaction_costs - month_storage_costs

        # Trading metrics
        n_trades = len(month_trades)

        if n_trades > 0:
            total_volume = sum(t['amount'] for t in month_trades)
            avg_sale_price = month_revenue / total_volume if total_volume > 0 else 0
            first_sale_price = month_trades[0]['price']
            last_sale_price = month_trades[-1]['price']
        else:
            avg_sale_price = 0.0
            first_sale_price = 0.0
            last_sale_price = 0.0

        year, month = month_key.split('-')
        metrics_by_month[month_key] = {
            'year': int(year),
            'month': int(month),
            'month_key': month_key,
            'strategy': results['strategy_name'],
            'net_earnings': month_net_earnings,
            'total_revenue': month_revenue,
            'total_costs': month_transaction_costs + month_storage_costs,
            'transaction_costs': month_transaction_costs,
            'storage_costs': month_storage_costs,
            'avg_sale_price': avg_sale_price,
            'first_sale_price': first_sale_price,
            'last_sale_price': last_sale_price,
            'n_trades': n_trades,
            'n_days_in_month': len(month_daily)
        }

    return metrics_by_month
