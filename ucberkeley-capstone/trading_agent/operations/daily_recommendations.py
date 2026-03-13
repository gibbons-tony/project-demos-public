"""
Daily Trading Recommendations

Generates actionable trading recommendations using latest predictions.
Run this daily when new forecasts are available.

Usage:
    python daily_recommendations.py --commodity coffee --model sarimax_auto_weather_v1
    python daily_recommendations.py --commodity sugar --all-models
    python daily_recommendations.py --commodity coffee --model sarimax_auto_weather_v1 --output-json recommendations.json
"""

import sys
import os
from databricks import sql
from dotenv import load_dotenv
import pandas as pd
import numpy as np
from datetime import datetime
import argparse
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import strategies
from production.strategies.baseline import (
    ImmediateSaleStrategy,
    EqualBatchStrategy,
    PriceThresholdStrategy,
    MovingAverageStrategy
)
from production.strategies.prediction import (
    ConsensusStrategy,
    ExpectedValueStrategy,
    RiskAdjustedStrategy,
    PriceThresholdPredictive,
    MovingAveragePredictive
)

# Import data access
from data_access.forecast_loader import (
    get_available_models,
    load_forecast_distributions,
    transform_to_prediction_matrices
)

# Load environment variables
load_dotenv()


def get_latest_prediction(commodity, model_version, connection):
    """
    Get the most recent prediction for operational use.

    Returns:
        tuple: (prediction_matrix, forecast_date, generation_timestamp)
    """
    # Query for latest forecast_start_date for this model
    cursor = connection.cursor()
    cursor.execute("""
        SELECT MAX(forecast_start_date) as latest_date
        FROM commodity.forecast.distributions
        WHERE commodity = %s
          AND model_version = %s
          AND is_actuals = FALSE
    """, (commodity.capitalize(), model_version))

    result = cursor.fetchone()
    if result is None or result[0] is None:
        raise ValueError(f"No predictions found for {commodity} - {model_version}")

    latest_date = result[0]

    # Load just this date's predictions
    df = load_forecast_distributions(
        commodity=commodity.capitalize(),
        model_version=model_version,
        connection=connection,
        start_date=latest_date,
        end_date=latest_date
    )

    if len(df) == 0:
        raise ValueError(f"No data for latest date {latest_date}")

    # Transform to prediction matrix
    matrices = transform_to_prediction_matrices(df)

    if len(matrices) == 0:
        raise ValueError(f"Could not transform predictions")

    # Get the single matrix
    forecast_date = list(matrices.keys())[0]
    prediction_matrix = matrices[forecast_date]

    # Get generation timestamp
    generation_ts = df['generation_timestamp'].max()

    cursor.close()

    return prediction_matrix, forecast_date, generation_ts


def get_exchange_rates(connection, currency_pairs=None):
    """
    Get latest exchange rates from Databricks.

    Args:
        connection: Databricks SQL connection
        currency_pairs: Optional list of specific currency pairs to fetch.
                       If None, fetches all available pairs.

    Returns:
        dict: {currency_pair: rate}
    """
    cursor = connection.cursor()

    if currency_pairs is None:
        # Query all available currency pairs with their latest rates
        cursor.execute("""
            WITH ranked_rates AS (
                SELECT
                    currency_pair,
                    rate,
                    date,
                    ROW_NUMBER() OVER (PARTITION BY currency_pair ORDER BY date DESC) as rn
                FROM commodity.bronze.fx_rates
            )
            SELECT currency_pair, rate
            FROM ranked_rates
            WHERE rn = 1
        """)

        rates = {}
        for row in cursor.fetchall():
            rates[row[0]] = row[1]

    else:
        # Query specific currency pairs
        rates = {}
        for pair in currency_pairs:
            cursor.execute("""
                SELECT rate
                FROM commodity.bronze.fx_rates
                WHERE currency_pair = %s
                ORDER BY date DESC
                LIMIT 1
            """, (pair,))

            result = cursor.fetchone()
            if result:
                rates[pair] = result[0]

    cursor.close()
    return rates


def get_current_state(commodity, connection):
    """
    Get current state for operational decision-making.

    In production, this would query your inventory management system.
    For now, uses placeholder values.

    Returns:
        dict with: inventory, days_since_harvest, current_price, price_history, exchange_rates
    """
    # Get latest price
    cursor = connection.cursor()

    # TODO: Replace with actual price query from your system
    # For now, using placeholder
    cursor.execute("""
        SELECT date, price
        FROM commodity.prices.daily
        WHERE commodity = %s
        ORDER BY date DESC
        LIMIT 100
    """, (commodity.capitalize(),))

    rows = cursor.fetchall()
    if len(rows) == 0:
        # Fallback to mock data
        print("  ⚠️  No price data found, using mock data")
        price_history = pd.DataFrame({
            'date': pd.date_range(end=datetime.now(), periods=100, freq='D'),
            'price': 100 + np.cumsum(np.random.randn(100) * 0.5)
        })
        current_price = price_history['price'].iloc[-1]
    else:
        price_history = pd.DataFrame(rows, columns=['date', 'price'])
        price_history = price_history.sort_values('date')
        current_price = price_history['price'].iloc[-1]

    cursor.close()

    # TODO: Get actual inventory from your system
    # For now, placeholder
    inventory = 35.5  # tons
    days_since_harvest = 45

    # Get all available exchange rates
    exchange_rates = get_exchange_rates(connection)

    return {
        'inventory': inventory,
        'days_since_harvest': days_since_harvest,
        'current_price': current_price,
        'price_history': price_history,
        'current_date': datetime.now(),
        'exchange_rates': exchange_rates
    }


def initialize_strategies(commodity_config):
    """
    Initialize all trading strategies with commodity-specific parameters.

    Returns:
        list of (strategy_name, strategy_object, needs_predictions)
    """
    strategies = []

    # Baseline strategies (don't use predictions)
    strategies.append((
        'Immediate Sale',
        ImmediateSaleStrategy(min_batch_size=5.0, sale_frequency_days=7),
        False
    ))

    strategies.append((
        'Equal Batches',
        EqualBatchStrategy(batch_size=0.25, frequency_days=30),
        False
    ))

    strategies.append((
        'Price Threshold',
        PriceThresholdStrategy(
            threshold_pct=0.05,
            batch_fraction=0.25,
            max_days_without_sale=60
        ),
        False
    ))

    strategies.append((
        'Moving Average',
        MovingAverageStrategy(
            ma_period=30,
            batch_fraction=0.25,
            max_days_without_sale=60
        ),
        False
    ))

    # Prediction-based strategies
    strategies.append((
        'Consensus',
        ConsensusStrategy(
            consensus_threshold=0.70,
            min_return=0.03,
            evaluation_day=14
        ),
        True
    ))

    strategies.append((
        'Expected Value',
        ExpectedValueStrategy(
            storage_cost_pct_per_day=commodity_config['storage_cost_pct_per_day'],
            transaction_cost_pct=commodity_config['transaction_cost_pct'],
            min_ev_improvement=50,
            baseline_batch=0.15,
            baseline_frequency=10
        ),
        True
    ))

    strategies.append((
        'Risk-Adjusted',
        RiskAdjustedStrategy(
            min_return=0.05,
            max_uncertainty=0.08,
            consensus_threshold=0.65,
            evaluation_day=14
        ),
        True
    ))

    strategies.append((
        'Price Threshold Predictive',
        PriceThresholdPredictive(
            threshold_pct=0.05,
            batch_fraction=0.25,
            max_days_without_sale=60,
            storage_cost_pct_per_day=commodity_config['storage_cost_pct_per_day'],
            transaction_cost_pct=commodity_config['transaction_cost_pct']
        ),
        True
    ))

    strategies.append((
        'Moving Average Predictive',
        MovingAveragePredictive(
            ma_period=30,
            batch_fraction=0.25,
            max_days_without_sale=60,
            storage_cost_pct_per_day=commodity_config['storage_cost_pct_per_day'],
            transaction_cost_pct=commodity_config['transaction_cost_pct']
        ),
        True
    ))

    return strategies


def analyze_forecast(prediction_matrix, current_price):
    """
    Analyze forecast to extract key insights for messaging.

    Returns:
        dict with: price_range, best_window, expected_prices_by_day
    """
    # Calculate statistics across all paths for each day
    median_by_day = np.median(prediction_matrix, axis=0)
    p25_by_day = np.percentile(prediction_matrix, 25, axis=0)
    p75_by_day = np.percentile(prediction_matrix, 75, axis=0)

    # Overall forecast range (across all 14 days)
    forecast_min = np.percentile(prediction_matrix, 10)  # 10th percentile
    forecast_max = np.percentile(prediction_matrix, 90)  # 90th percentile

    # Find best sale window (highest median prices, look for 3-day windows)
    best_window_start = 0
    best_window_avg = 0

    for start_day in range(len(median_by_day) - 2):
        window_avg = np.mean(median_by_day[start_day:start_day + 3])
        if window_avg > best_window_avg:
            best_window_avg = window_avg
            best_window_start = start_day

    best_window_days = list(range(best_window_start + 1, best_window_start + 4))  # 1-indexed

    return {
        'price_range': {
            'min': forecast_min,
            'max': forecast_max,
            'median': np.median(prediction_matrix)
        },
        'best_window': {
            'days': best_window_days,
            'expected_price': best_window_avg
        },
        'daily_forecast': {
            f'day_{i+1}': {
                'median': median_by_day[i],
                'p25': p25_by_day[i],
                'p75': p75_by_day[i]
            }
            for i in range(len(median_by_day))
        }
    }


def calculate_financial_impact(state, forecast_analysis, recommendation):
    """
    Calculate financial impact of recommendation vs alternatives.

    Returns:
        dict with: sell_now_value, wait_value, potential_gain (in USD and local currencies)
    """
    inventory = state['inventory']
    current_price = state['current_price']
    exchange_rates = state.get('exchange_rates', {})

    # Value if sell today (USD)
    sell_now_value_usd = inventory * current_price

    # Value if wait for best window (from forecast) (USD)
    best_window_price = forecast_analysis['best_window']['expected_price']
    wait_value_usd = inventory * best_window_price

    # Potential gain/loss (USD)
    potential_gain_usd = wait_value_usd - sell_now_value_usd
    potential_gain_pct = (potential_gain_usd / sell_now_value_usd) * 100

    # Convert to local currencies
    sell_now_local = {}
    wait_value_local = {}
    potential_gain_local = {}

    for pair, rate in exchange_rates.items():
        currency_code = pair.split('/')[0]
        sell_now_local[currency_code] = sell_now_value_usd * rate
        wait_value_local[currency_code] = wait_value_usd * rate
        potential_gain_local[currency_code] = potential_gain_usd * rate

    return {
        'sell_now_value': sell_now_value_usd,
        'wait_value': wait_value_usd,
        'potential_gain': potential_gain_usd,
        'potential_gain_pct': potential_gain_pct,
        'sell_now_value_local': sell_now_local,
        'wait_value_local': wait_value_local,
        'potential_gain_local': potential_gain_local
    }


def generate_recommendations(state, prediction_matrix, commodity_config):
    """
    Generate recommendations for all strategies.

    Returns:
        tuple: (recommendations_df, structured_data)
            structured_data contains all info needed for WhatsApp message
    """
    strategies = initialize_strategies(commodity_config)

    # Prepare parameters for decide() method
    day = state['days_since_harvest']
    inventory = state['inventory']
    current_price = state['current_price']
    price_history = state['price_history']

    recommendations = []

    for strategy_name, strategy_obj, needs_predictions in strategies:
        try:
            # Set harvest start (strategies need this)
            strategy_obj.set_harvest_start(day=0)

            # Get decision
            if needs_predictions:
                decision = strategy_obj.decide(
                    day=day,
                    inventory=inventory,
                    current_price=current_price,
                    price_history=price_history,
                    predictions=prediction_matrix
                )
            else:
                decision = strategy_obj.decide(
                    day=day,
                    inventory=inventory,
                    current_price=current_price,
                    price_history=price_history,
                    predictions=None
                )

            recommendations.append({
                'Strategy': strategy_name,
                'Action': decision['action'],
                'Quantity (tons)': decision['amount'],
                'Reasoning': decision['reason'],
                'Uses Predictions': 'Yes' if needs_predictions else 'No'
            })

        except Exception as e:
            recommendations.append({
                'Strategy': strategy_name,
                'Action': 'ERROR',
                'Quantity (tons)': 0,
                'Reasoning': str(e),
                'Uses Predictions': 'Yes' if needs_predictions else 'No'
            })

    recommendations_df = pd.DataFrame(recommendations)

    # Analyze forecast for structured output
    forecast_analysis = analyze_forecast(prediction_matrix, current_price)

    # Calculate 7-day price trend
    prices_7d = price_history['price'].tail(7)
    trend_7d_pct = ((prices_7d.iloc[-1] - prices_7d.iloc[0]) / prices_7d.iloc[0]) * 100
    trend_direction = '↑' if trend_7d_pct > 0 else '↓'

    # Determine primary recommendation (consensus from prediction-based strategies)
    prediction_strategies = recommendations_df[recommendations_df['Uses Predictions'] == 'Yes']
    sell_count = (prediction_strategies['Action'] == 'SELL').sum()
    hold_count = (prediction_strategies['Action'] == 'HOLD').sum()

    primary_action = 'SELL' if sell_count > hold_count else 'HOLD'

    # Get recommended quantity (average from SELL recommendations)
    if primary_action == 'SELL':
        sell_recs = prediction_strategies[prediction_strategies['Action'] == 'SELL']
        recommended_quantity = sell_recs['Quantity (tons)'].mean() if len(sell_recs) > 0 else 0
    else:
        recommended_quantity = 0

    # Calculate financial impact
    financial_impact = calculate_financial_impact(state, forecast_analysis, {
        'action': primary_action,
        'quantity': recommended_quantity
    })

    # Get exchange rates from state
    exchange_rates = state.get('exchange_rates', {})

    # Calculate local currency prices if exchange rates available
    local_prices = {}
    for pair, rate in exchange_rates.items():
        # Extract currency code (e.g., "COP" from "COP/USD")
        currency_code = pair.split('/')[0]
        local_prices[currency_code] = current_price * rate

    # Structure data for WhatsApp message
    structured_data = {
        'timestamp': datetime.now().isoformat(),
        'commodity': commodity_config['commodity'],
        'market': {
            'current_price_usd': current_price,
            'trend_7d_pct': trend_7d_pct,
            'trend_direction': trend_direction,
            'exchange_rates': exchange_rates,
            'local_prices': local_prices
        },
        'forecast': {
            'horizon_days': 14,
            'price_range_usd': {
                'min': forecast_analysis['price_range']['min'],
                'max': forecast_analysis['price_range']['max']
            },
            'best_window': {
                'days': forecast_analysis['best_window']['days'],
                'expected_price_usd': forecast_analysis['best_window']['expected_price']
            },
            'daily_forecast': forecast_analysis['daily_forecast']
        },
        'inventory': {
            'stock_tons': inventory,
            'days_held': day
        },
        'recommendation': {
            'action': primary_action,
            'quantity_tons': recommended_quantity,
            'confidence': {
                'strategies_agreeing': sell_count if primary_action == 'SELL' else hold_count,
                'total_strategies': len(prediction_strategies)
            },
            'financial_impact': {
                'usd': {
                    'sell_now_value': financial_impact['sell_now_value'],
                    'wait_value': financial_impact['wait_value'],
                    'potential_gain': financial_impact['potential_gain'],
                    'potential_gain_pct': financial_impact['potential_gain_pct']
                },
                'local_currency': {
                    'sell_now_value': financial_impact['sell_now_value_local'],
                    'wait_value': financial_impact['wait_value_local'],
                    'potential_gain': financial_impact['potential_gain_local']
                }
            }
        },
        'all_strategies': recommendations_df.to_dict('records')
    }

    return recommendations_df, structured_data


class NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder for NumPy types."""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def main():
    parser = argparse.ArgumentParser(description='Generate daily trading recommendations')
    parser.add_argument('--commodity', required=True, choices=['coffee', 'sugar'],
                       help='Commodity to analyze')
    parser.add_argument('--model', help='Specific model to use (e.g., sarimax_auto_weather_v1)')
    parser.add_argument('--all-models', action='store_true',
                       help='Generate recommendations for all available models')
    parser.add_argument('--output-json', help='Output structured data as JSON to specified file path')

    args = parser.parse_args()

    if not args.model and not args.all_models:
        print("Error: Must specify either --model or --all-models")
        sys.exit(1)

    # Commodity configuration
    COMMODITY_CONFIGS = {
        'coffee': {
            'commodity': 'coffee',
            'harvest_volume': 50,
            'harvest_windows': [(5, 9)],
            'storage_cost_pct_per_day': 0.025,
            'transaction_cost_pct': 0.25
        },
        'sugar': {
            'commodity': 'sugar',
            'harvest_volume': 50,
            'harvest_windows': [(4, 9)],
            'storage_cost_pct_per_day': 0.020,
            'transaction_cost_pct': 0.25
        }
    }

    commodity_config = COMMODITY_CONFIGS[args.commodity]

    # Connect to Databricks
    print("=" * 80)
    print("DAILY TRADING RECOMMENDATIONS")
    print("=" * 80)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Commodity: {args.commodity.upper()}")
    print("=" * 80)
    print()

    print("Connecting to Databricks...")
    connection = sql.connect(
        server_hostname=os.getenv("DATABRICKS_HOST", "").replace("https://", ""),
        http_path=os.getenv("DATABRICKS_HTTP_PATH"),
        access_token=os.getenv("DATABRICKS_TOKEN")
    )
    print("✓ Connected\n")

    # Get current state
    print("Loading current state...")
    state = get_current_state(args.commodity, connection)
    print(f"✓ Current state loaded")
    print(f"  Inventory: {state['inventory']} tons")
    print(f"  Current Price: ${state['current_price']:.2f}")
    print(f"  Days Since Harvest: {state['days_since_harvest']}")
    print()

    # Determine which models to process
    if args.all_models:
        models = get_available_models(args.commodity.capitalize(), connection)
        print(f"Processing {len(models)} models...")
    else:
        models = [args.model]
        print(f"Processing model: {args.model}")

    print()

    # Storage for JSON output (if requested)
    all_structured_data = []

    # Generate recommendations for each model
    for model in models:
        print("=" * 80)
        print(f"MODEL: {model}")
        print("=" * 80)

        try:
            # Get latest prediction
            prediction, forecast_date, generation_ts = get_latest_prediction(
                args.commodity, model, connection
            )

            print(f"Latest Prediction:")
            print(f"  Forecast Date: {forecast_date}")
            print(f"  Generated: {generation_ts}")
            print(f"  Simulation Paths: {prediction.shape[0]}")
            print(f"  Forecast Horizon: {prediction.shape[1]} days")
            print()

            # Generate recommendations
            recommendations_df, structured_data = generate_recommendations(state, prediction, commodity_config)

            # Add model info to structured data
            structured_data['model'] = {
                'name': model,
                'forecast_date': str(forecast_date),
                'generation_timestamp': str(generation_ts),
                'simulation_paths': int(prediction.shape[0]),
                'forecast_horizon_days': int(prediction.shape[1])
            }

            # Store for JSON output
            if args.output_json:
                all_structured_data.append(structured_data)

            # Display
            print("Recommendations:")
            print(recommendations_df.to_string(index=False))
            print()

            # Highlight key recommendations
            sell_recs = recommendations_df[recommendations_df['Action'] == 'SELL']
            if len(sell_recs) > 0:
                total_sell = sell_recs['Quantity (tons)'].sum()
                print(f"📊 Summary: {len(sell_recs)}/{len(recommendations_df)} strategies recommend SELL")
                print(f"   Total recommended: {total_sell:.1f} tons ({total_sell/state['inventory']*100:.1f}% of inventory)")
            else:
                print(f"📊 Summary: All strategies recommend HOLD")

            print()

        except Exception as e:
            print(f"❌ Error processing {model}: {e}")
            print()
            continue

    connection.close()

    # Save JSON output if requested
    if args.output_json and len(all_structured_data) > 0:
        print()
        print(f"Saving structured data to {args.output_json}...")

        # Prepare output
        output = {
            'generated_at': datetime.now().isoformat(),
            'commodity': args.commodity,
            'models_processed': len(all_structured_data),
            'recommendations': all_structured_data
        }

        # Write to file
        with open(args.output_json, 'w') as f:
            json.dump(output, f, indent=2, cls=NumpyEncoder)

        print(f"✓ Structured data saved ({len(all_structured_data)} models)")
        print()

    print("=" * 80)
    print("RECOMMENDATIONS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
