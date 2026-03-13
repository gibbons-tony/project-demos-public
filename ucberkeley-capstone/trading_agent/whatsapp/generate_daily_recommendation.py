"""
WhatsApp Daily Recommendation Generator

Generates trading recommendations for WhatsApp delivery using:
- Expected Value strategy (proven best for Coffee: +3.4% vs baseline)
- Availability-first model selection (handles sparse forecast data)
- Real-time market data from Databricks Unity Catalog

Usage:
    python generate_daily_recommendation.py --commodity Coffee
    python generate_daily_recommendation.py --commodity Coffee --output-json recommendations.json
"""

import argparse
import os
import sys
from pathlib import Path
from datetime import datetime, date, timedelta
import pandas as pd
import numpy as np
import json
from typing import Dict, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from databricks import sql
from data_access.forecast_loader import (
    get_available_models,
    load_forecast_distributions,
    transform_to_prediction_matrices
)


def get_latest_market_price(connection, commodity: str) -> Tuple[float, date]:
    """
    Get the most recent closing price for a commodity.

    Returns:
        (price, date) tuple
    """
    cursor = connection.cursor()
    cursor.execute(f"""
        SELECT close, date
        FROM commodity.bronze.market_data
        WHERE commodity = '{commodity}'
        ORDER BY date DESC
        LIMIT 1
    """)

    row = cursor.fetchone()
    cursor.close()

    if row:
        return float(row[0]), row[1]
    else:
        raise ValueError(f"No market data found for {commodity}")


def get_best_model_from_forecast_metadata(
    connection,
    commodity: str,
    metric: str = 'mae_14d'
) -> Optional[str]:
    """
    Get best performing model based on forecast accuracy metrics.

    Args:
        connection: Databricks SQL connection
        commodity: 'Coffee' or 'Sugar'
        metric: Metric to optimize (default: 'mae_14d')
                Options: mae_1d, mae_7d, mae_14d, rmse_14d, crps_14d

    Returns:
        model_version string of best model, or None if no data
    """
    cursor = connection.cursor()

    # Query for best model based on average performance
    # Lower is better for MAE, RMSE, CRPS
    query = f"""
        SELECT model_version, AVG({metric}) as avg_metric
        FROM commodity.forecast.forecast_metadata
        WHERE commodity = '{commodity}'
          AND {metric} IS NOT NULL
          AND model_success = TRUE
        GROUP BY model_version
        ORDER BY avg_metric ASC
        LIMIT 1
    """

    try:
        cursor.execute(query)
        row = cursor.fetchone()
        cursor.close()

        if row:
            print(f"Best model by {metric}: {row[0]} (avg {metric}={row[1]:.4f})")
            return row[0]
        else:
            print(f"No forecast metadata available for {commodity}")
            return None

    except Exception as e:
        print(f"Error querying forecast_metadata: {e}")
        cursor.close()
        return None


def get_available_forecast(
    connection,
    commodity: str,
    max_age_days: int = 7,
    preferred_model: Optional[str] = None
) -> Optional[Dict]:
    """
    Get forecast for the best available model.

    Two-step optimization:
    1. If preferred_model specified, try to get forecast from that model first
    2. Otherwise, fall back to availability-first search across all models

    Args:
        connection: Databricks SQL connection
        commodity: 'Coffee' or 'Sugar'
        max_age_days: Maximum age of forecast to consider (default 7 days)
        preferred_model: Model to try first (e.g., from forecast_metadata)

    Returns:
        Dict with:
            - model_version: str
            - forecast_start_date: date
            - data_cutoff_date: date
            - prediction_matrix: np.ndarray of shape (2000, 14)
            - actuals: np.ndarray of shape (14,) or None if not available
    """
    # Calculate cutoff date
    cutoff_date = date.today() - timedelta(days=max_age_days)

    # Get all available models for this commodity
    models = get_available_models(commodity, connection)

    if not models:
        print(f"No forecast models available for {commodity}")
        return None

    # If preferred model specified, try it first
    if preferred_model and preferred_model in models:
        models_to_try = [preferred_model] + [m for m in models if m != preferred_model]
        print(f"Trying preferred model: {preferred_model}")
    else:
        models_to_try = models

    # Try each model until we find one with recent forecasts
    for model_version in models_to_try:
        if model_version != preferred_model:
            print(f"Checking {model_version}...")

        # Query most recent forecast for this model
        cursor = connection.cursor()
        cursor.execute(f"""
            SELECT MAX(forecast_start_date) as latest_forecast
            FROM commodity.forecast.distributions
            WHERE commodity = '{commodity}'
              AND model_version = '{model_version}'
              AND is_actuals = FALSE
              AND forecast_start_date >= '{cutoff_date}'
        """)

        row = cursor.fetchone()
        cursor.close()

        if row and row[0]:
            latest_forecast_date = row[0]
            print(f"  ✓ Found forecast dated {latest_forecast_date}")

            # Load this forecast
            df = load_forecast_distributions(
                commodity=commodity,
                model_version=model_version,
                connection=connection,
                start_date=str(latest_forecast_date),
                end_date=str(latest_forecast_date)
            )

            if len(df) > 0:
                # Get data_cutoff_date from the forecast
                data_cutoff_date = df[df['is_actuals'] == False]['data_cutoff_date'].iloc[0]

                # Transform to prediction matrix
                matrices = transform_to_prediction_matrices(df)

                if latest_forecast_date in matrices:
                    prediction_matrix = matrices[latest_forecast_date]

                    # Extract actuals if available
                    actuals_df = df[df['is_actuals'] == True]
                    if len(actuals_df) > 0:
                        day_cols = [f'day_{i}' for i in range(1, 15)]
                        actuals = actuals_df[day_cols].values[0]
                    else:
                        actuals = None

                    return {
                        'model_version': model_version,
                        'forecast_start_date': latest_forecast_date,
                        'data_cutoff_date': data_cutoff_date,
                        'prediction_matrix': prediction_matrix,
                        'actuals': actuals
                    }
        else:
            print(f"  ✗ No recent forecast")

    print(f"No recent forecasts found for {commodity} (checked {len(models_to_try)} models)")
    return None


def calculate_7day_trend(connection, commodity: str, as_of_date: date) -> float:
    """
    Calculate 7-day price trend as percentage change.

    Returns:
        Percentage change over last 7 days (e.g., 2.5 for +2.5%)
    """
    cursor = connection.cursor()
    cursor.execute(f"""
        SELECT close, date
        FROM commodity.bronze.market_data
        WHERE commodity = '{commodity}'
          AND date <= '{as_of_date}'
        ORDER BY date DESC
        LIMIT 8
    """)

    rows = cursor.fetchall()
    cursor.close()

    if len(rows) < 8:
        return 0.0

    # Most recent is rows[0], 7 days ago is rows[7]
    current_price = float(rows[0][0])
    week_ago_price = float(rows[7][0])

    pct_change = ((current_price - week_ago_price) / week_ago_price) * 100
    return round(pct_change, 1)


def calculate_14day_forecast_range(prediction_matrix: np.ndarray) -> Tuple[float, float]:
    """
    Calculate 14-day forecast range from Monte Carlo paths.

    Args:
        prediction_matrix: np.ndarray of shape (2000, 14)

    Returns:
        (lower_bound, upper_bound) tuple using 10th and 90th percentiles
    """
    # Use day 14 predictions (last column)
    day_14_predictions = prediction_matrix[:, -1]

    # Calculate percentiles
    lower = np.percentile(day_14_predictions, 10)
    upper = np.percentile(day_14_predictions, 90)

    return (round(lower, 2), round(upper, 2))


def find_best_sale_window(prediction_matrix: np.ndarray) -> Tuple[int, int]:
    """
    Find best 3-day window to sell based on median forecasts.

    Args:
        prediction_matrix: np.ndarray of shape (2000, 14)

    Returns:
        (start_day, end_day) tuple (1-indexed, inclusive)
    """
    # Calculate median forecast for each day
    median_forecasts = np.median(prediction_matrix, axis=0)

    # Find 3-day window with highest average
    window_size = 3
    best_avg = -np.inf
    best_start = 1

    for start_idx in range(len(median_forecasts) - window_size + 1):
        window_avg = np.mean(median_forecasts[start_idx:start_idx + window_size])
        if window_avg > best_avg:
            best_avg = window_avg
            best_start = start_idx + 1  # Convert to 1-indexed

    return (best_start, best_start + window_size - 1)


def get_best_strategy_for_model(
    commodity: str,
    model_version: str,
    connection = None
) -> str:
    """
    Get best PREDICTION-BASED strategy for a specific commodity/model combination.

    IMPORTANT: Must use strategies that leverage predictions, not baselines.

    TODO: Query from commodity.trading.backtest_results table once created.
    For now, uses hardcoded findings from EXECUTION_RESULTS_SUMMARY.md.

    Args:
        commodity: 'Coffee' or 'Sugar'
        model_version: Model identifier (currently unused, all models identical)
        connection: Databricks connection (for future table query)

    Returns:
        Strategy name: 'ExpectedValue', 'Consensus', etc. (prediction-based only)
    """
    # Based on trading_agent/EXECUTION_RESULTS_SUMMARY.md:
    #
    # PREDICTION-BASED STRATEGIES ONLY:
    #
    # Coffee (all 12 real forecast models):
    #   - Best: Expected Value strategy (prediction-based)
    #   - Net earnings: $751,641 (+3.4% vs baseline $727,037)
    #
    # Sugar (all 9 models):
    #   - Best baseline: Immediate Sale - $50,071 (NOT prediction-based)
    #   - Best prediction: Consensus - ~$49,750-$49,886 (uses predictions)
    #   - Note: Predictions underperform baseline by ~$185-$323 (-0.4% to -0.6%)
    #          But we MUST use prediction-based strategy per requirement

    if commodity == 'Coffee':
        strategy = 'ExpectedValue'
        print(f"Best prediction-based strategy for {commodity}: {strategy} (+3.4% vs baseline)")
    elif commodity == 'Sugar':
        strategy = 'Consensus'
        print(f"Best prediction-based strategy for {commodity}: {strategy} (note: baseline performs better)")
    else:
        # Default fallback
        strategy = 'ExpectedValue'
        print(f"Unknown commodity {commodity}, defaulting to {strategy}")

    return strategy


def calculate_expected_value_recommendation(
    current_price: float,
    prediction_matrix: np.ndarray,
    storage_cost_pct_per_day: float = 0.00025,  # 0.025% per day
    transaction_cost_pct: float = 0.0025,  # 0.25% per transaction
    inventory_tons: float = 50.0
) -> Dict:
    """
    Calculate Expected Value strategy recommendation.

    This is the strategy that won in backtesting (+3.4% for Coffee).

    Returns:
        Dict with:
            - action: 'HOLD' or 'SELL'
            - expected_gain_per_ton: float (can be negative)
            - optimal_sale_day: int (1-14) if action is HOLD
            - reasoning: str
    """
    # Calculate median forecasts
    median_forecasts = np.median(prediction_matrix, axis=0)

    # Calculate expected value of selling on each future day
    best_ev = -np.inf
    best_day = 0

    for day in range(14):
        # Expected price on this day
        expected_price = median_forecasts[day]

        # Cumulative storage cost up to this day
        cumulative_storage_cost = current_price * storage_cost_pct_per_day * (day + 1)

        # Transaction cost
        transaction_cost = expected_price * transaction_cost_pct

        # Net expected value
        ev = expected_price - cumulative_storage_cost - transaction_cost

        if ev > best_ev:
            best_ev = ev
            best_day = day + 1  # Convert to 1-indexed

    # Compare with selling immediately
    immediate_sale_value = current_price - (current_price * transaction_cost_pct)

    # Decision threshold: Hold only if expected gain > $50/ton
    expected_gain_per_ton = best_ev - immediate_sale_value
    min_gain_threshold = 50.0

    if expected_gain_per_ton > min_gain_threshold:
        action = 'HOLD'
        reasoning = f"Expected to gain ${expected_gain_per_ton:.0f}/ton by selling on day {best_day}"
        total_expected_gain = expected_gain_per_ton * inventory_tons
    else:
        action = 'SELL'
        reasoning = f"Immediate sale recommended (expected gain ${expected_gain_per_ton:.0f}/ton < ${min_gain_threshold:.0f}/ton threshold)"
        best_day = 0
        total_expected_gain = 0.0

    return {
        'action': action,
        'expected_gain_per_ton': round(expected_gain_per_ton, 2),
        'total_expected_gain': round(total_expected_gain, 2),
        'optimal_sale_day': best_day,
        'reasoning': reasoning
    }


def format_whatsapp_message(recommendation: Dict) -> str:
    """
    Format recommendation as WhatsApp message matching mockup.

    Mockup format:
    ────────────────────────
    Current Market
    Price: $X.XX/kg
    7-Day Trend: ±X.X%

    14-Day Forecast
    Range: $X.XX - $X.XX
    Best Sale Window: Days X-X

    Inventory
    Stock: XX tons
    Hold Duration: XX days

    Recommendation
    [HOLD/SELL]
    Expected Gain: $X,XXX
    ────────────────────────
    """
    msg = "─" * 40 + "\n"
    msg += "📊 *Current Market*\n"
    msg += f"Price: ${recommendation['current_price']:.2f}/kg\n"
    trend_symbol = "📈" if recommendation['7day_trend'] > 0 else "📉"
    msg += f"7-Day Trend: {trend_symbol} {recommendation['7day_trend']:+.1f}%\n"
    msg += "\n"

    msg += "🔮 *14-Day Forecast*\n"
    msg += f"Range: ${recommendation['forecast_range'][0]:.2f} - ${recommendation['forecast_range'][1]:.2f}\n"
    msg += f"Best Sale Window: Days {recommendation['best_window'][0]}-{recommendation['best_window'][1]}\n"
    msg += "\n"

    msg += "📦 *Inventory*\n"
    msg += f"Stock: {recommendation['inventory_tons']:.0f} tons\n"
    msg += f"Hold Duration: {recommendation['hold_duration']} days\n"
    msg += "\n"

    msg += "💡 *Recommendation*\n"
    if recommendation['strategy_decision']['action'] == 'HOLD':
        msg += f"*✋ HOLD*\n"
        msg += f"Expected Gain: ${recommendation['strategy_decision']['total_expected_gain']:,.0f}\n"
        msg += f"Sell on: Day {recommendation['strategy_decision']['optimal_sale_day']}\n"
    else:
        msg += f"*💰 SELL NOW*\n"
        msg += f"Rationale: {recommendation['strategy_decision']['reasoning']}\n"

    msg += "\n"
    msg += f"_Model: {recommendation['model_version']}_\n"
    msg += f"_Forecast Date: {recommendation['forecast_date']}_\n"
    msg += "─" * 40

    return msg


def generate_recommendation(
    connection,
    commodity: str,
    inventory_tons: float = 50.0
) -> Dict:
    """
    Generate complete trading recommendation using two-step optimization:
    1. Select best forecast model based on accuracy metrics
    2. Select best trading strategy for that model based on backtesting results

    Args:
        connection: Databricks SQL connection
        commodity: 'Coffee' or 'Sugar'
        inventory_tons: Inventory size in tons (default 50)

    Returns:
        Dict with all recommendation data
    """
    print(f"\n{'='*60}")
    print(f"Generating recommendation for {commodity}")
    print(f"{'='*60}\n")

    # STEP 1: Select best forecast model from forecast_metadata
    print("STEP 1: Selecting best forecast model...")
    best_model = get_best_model_from_forecast_metadata(
        connection=connection,
        commodity=commodity,
        metric='mae_14d'  # Optimize for 14-day forecast accuracy
    )

    # STEP 2: Get available forecast (prefer best model if available)
    print("\nSTEP 2: Getting forecast data...")
    forecast = get_available_forecast(
        connection=connection,
        commodity=commodity,
        max_age_days=7,
        preferred_model=best_model
    )

    if not forecast:
        raise ValueError(f"No recent forecasts available for {commodity}")

    print(f"   ✓ Using model: {forecast['model_version']}")
    print(f"   ✓ Forecast date: {forecast['forecast_start_date']}")
    print(f"   ✓ Prediction matrix shape: {forecast['prediction_matrix'].shape}")

    # STEP 3: Select best strategy for this model from backtesting results
    print("\nSTEP 3: Selecting best trading strategy...")
    best_strategy = get_best_strategy_for_model(
        commodity=commodity,
        model_version=forecast['model_version'],
        connection=connection
    )

    # Get market data
    print("\nSTEP 4: Fetching market data...")
    current_price, price_date = get_latest_market_price(connection, commodity)
    print(f"   Current price: ${current_price:.2f} (as of {price_date})")

    trend_7d = calculate_7day_trend(connection, commodity, price_date)
    print(f"   7-day trend: {trend_7d:+.1f}%")

    # Calculate forecast metrics
    print("\nSTEP 5: Calculating forecast metrics...")
    forecast_range = calculate_14day_forecast_range(forecast['prediction_matrix'])
    print(f"   Range (10th-90th percentile): ${forecast_range[0]:.2f} - ${forecast_range[1]:.2f}")

    best_window = find_best_sale_window(forecast['prediction_matrix'])
    print(f"   Best 3-day window: Days {best_window[0]}-{best_window[1]}")

    # Execute strategy
    print(f"\nSTEP 6: Executing {best_strategy} strategy...")
    if best_strategy == 'ExpectedValue':
        strategy_decision = calculate_expected_value_recommendation(
            current_price=current_price,
            prediction_matrix=forecast['prediction_matrix'],
            inventory_tons=inventory_tons
        )
    elif best_strategy == 'Consensus':
        # TODO: Implement Consensus strategy from commodity_prediction_analysis notebooks
        # For now, use ExpectedValue as fallback (both are prediction-based)
        print("   ⚠️  Consensus strategy not yet implemented, using ExpectedValue")
        strategy_decision = calculate_expected_value_recommendation(
            current_price=current_price,
            prediction_matrix=forecast['prediction_matrix'],
            inventory_tons=inventory_tons
        )
    else:
        raise ValueError(f"Unknown strategy: {best_strategy}")

    print(f"   Decision: {strategy_decision['action']}")
    print(f"   {strategy_decision['reasoning']}")

    # Calculate hold duration
    if strategy_decision['action'] == 'HOLD':
        hold_duration = strategy_decision['optimal_sale_day']
    else:
        hold_duration = 0

    # Compile full recommendation
    recommendation = {
        'commodity': commodity,
        'generated_at': datetime.now().isoformat(),
        'current_price': current_price,
        'price_date': str(price_date),
        '7day_trend': trend_7d,
        'forecast_range': forecast_range,
        'best_window': best_window,
        'inventory_tons': inventory_tons,
        'hold_duration': hold_duration,
        'strategy_decision': strategy_decision,
        'strategy_used': best_strategy,  # Track which strategy was selected
        'model_version': forecast['model_version'],
        'best_model_from_metadata': best_model,  # Track if preferred model was available
        'forecast_date': str(forecast['forecast_start_date']),
        'data_cutoff_date': str(forecast['data_cutoff_date'])
    }

    return recommendation


def main():
    parser = argparse.ArgumentParser(description='Generate WhatsApp trading recommendation')
    parser.add_argument('--commodity', type=str, required=True, choices=['Coffee', 'Sugar'],
                        help='Commodity to generate recommendation for')
    parser.add_argument('--inventory-tons', type=float, default=50.0,
                        help='Inventory size in tons (default: 50)')
    parser.add_argument('--output-json', type=str, default=None,
                        help='Output JSON file path (optional)')

    args = parser.parse_args()

    # Load Databricks credentials
    DATABRICKS_HOST = os.getenv("DATABRICKS_HOST")
    DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN")
    DATABRICKS_HTTP_PATH = os.getenv("DATABRICKS_HTTP_PATH")

    if not all([DATABRICKS_HOST, DATABRICKS_TOKEN, DATABRICKS_HTTP_PATH]):
        print("ERROR: Missing Databricks credentials in environment variables")
        print("Set DATABRICKS_HOST, DATABRICKS_TOKEN, DATABRICKS_HTTP_PATH")
        sys.exit(1)

    # Connect to Databricks
    print("Connecting to Databricks...")
    connection = sql.connect(
        server_hostname=DATABRICKS_HOST.replace('https://', ''),
        http_path=DATABRICKS_HTTP_PATH,
        access_token=DATABRICKS_TOKEN
    )
    print("✅ Connected\n")

    try:
        # Generate recommendation
        recommendation = generate_recommendation(
            connection=connection,
            commodity=args.commodity,
            inventory_tons=args.inventory_tons
        )

        # Format WhatsApp message
        whatsapp_msg = format_whatsapp_message(recommendation)

        print("\n" + "="*60)
        print("WHATSAPP MESSAGE")
        print("="*60)
        print(whatsapp_msg)
        print()

        # Save to JSON if requested
        if args.output_json:
            # Add formatted message to recommendation
            recommendation['whatsapp_message'] = whatsapp_msg

            with open(args.output_json, 'w') as f:
                json.dump(recommendation, f, indent=2, default=str)

            print(f"✅ Saved to {args.output_json}")

    finally:
        connection.close()


if __name__ == "__main__":
    main()
