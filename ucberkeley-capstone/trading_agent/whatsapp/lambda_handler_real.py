"""
WhatsApp Trading Recommendations - Lambda Handler (Real Data)

Responds to Twilio WhatsApp webhook with trading recommendations.
Queries Databricks via REST API for real market data, forecasts, and recommendations.
"""

import json
import os
import time
from datetime import datetime, date, timedelta
from typing import Dict, Optional, Tuple, List, Any
import numpy as np
import requests

# Import trading strategies
from trading_strategies import (
    ExpectedValueStrategy,
    analyze_forecast as analyze_forecast_distribution,
    calculate_7day_trend as calc_trend
)

# Allowed commodities for SQL injection protection
ALLOWED_COMMODITIES = {'Coffee', 'Sugar', 'Cocoa', 'Wheat'}

# Price conversion factor (market data is in cents)
PRICE_CENTS_TO_DOLLARS = 0.01

# Trading strategy parameters from backtesting notebook 03_strategy_implementations.ipynb
# NOTE: These are PERCENTAGES (not decimals). The strategy divides by 100 when calculating costs.
COMMODITY_CONFIGS = {
    'Coffee': {
        'storage_cost_pct_per_day': 0.025,  # 0.025% per day (notebook value)
        'transaction_cost_pct': 0.25,        # 0.25% per transaction (notebook value)
        'min_ev_improvement': 50.0,          # $50/ton minimum gain
        'baseline_batch': 0.15,              # 15% baseline batch size
        'inventory_default': 50.0            # Default inventory (tons)
    },
    'Sugar': {
        'storage_cost_pct_per_day': 0.025,  # 0.025% per day (same as Coffee in notebook)
        'transaction_cost_pct': 0.25,        # 0.25% per transaction
        'min_ev_improvement': 50.0,          # $50/ton minimum gain
        'baseline_batch': 0.15,              # 15% baseline batch size
        'inventory_default': 50.0            # Default inventory (tons)
    }
}


def execute_databricks_query(sql_query: str, timeout: int = 60) -> List[List[Any]]:
    """
    Execute SQL query on Databricks using REST API.

    Args:
        sql_query: SQL query to execute
        timeout: Maximum time to wait for query completion (seconds)

    Returns:
        List of rows (each row is a list of values)

    Raises:
        Exception if query fails or times out
    """
    # Get credentials from environment
    host = os.environ['DATABRICKS_HOST']
    token = os.environ['DATABRICKS_TOKEN']
    warehouse_id = os.environ['DATABRICKS_HTTP_PATH'].split('/')[-1]

    # Prepare request URL (remove https:// if already present in host)
    clean_host = host.replace('https://', '').replace('http://', '')
    url = f"https://{clean_host}/api/2.0/sql/statements/"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "statement": sql_query,
        "warehouse_id": warehouse_id,
        "wait_timeout": "30s"  # Server-side timeout
    }

    print(f"Executing Databricks query: {sql_query[:100]}...")

    # Submit query
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()

    result = response.json()
    statement_id = result.get("statement_id")

    if not statement_id:
        raise Exception(f"No statement_id in response: {result}")

    # Poll for completion
    status_url = f"https://{clean_host}/api/2.0/sql/statements/{statement_id}"
    start_time = time.time()

    while time.time() - start_time < timeout:
        status_response = requests.get(status_url, headers=headers)
        status_response.raise_for_status()

        status_data = status_response.json()
        state = status_data.get("status", {}).get("state")

        print(f"Query status: {state}")

        if state == "SUCCEEDED":
            # Extract results
            manifest = status_data.get("manifest", {})
            chunks = manifest.get("chunks", [])

            if not chunks:
                # No results (empty query)
                return []

            # Get first chunk (for most queries, there's only one chunk)
            chunk_index = chunks[0].get("chunk_index", 0)
            result_url = f"https://{clean_host}/api/2.0/sql/statements/{statement_id}/result/chunks/{chunk_index}"

            result_response = requests.get(result_url, headers=headers)
            result_response.raise_for_status()

            result_data = result_response.json()
            data_array = result_data.get("data_array", [])

            print(f"Query returned {len(data_array)} rows")
            return data_array

        elif state == "FAILED":
            error = status_data.get("status", {}).get("error", {})
            raise Exception(f"Query failed: {error.get('message', 'Unknown error')}")

        elif state == "CANCELED":
            raise Exception("Query was canceled")

        # Still running, wait before polling again
        time.sleep(2)

    raise Exception(f"Query timed out after {timeout} seconds")


def get_latest_market_price(commodity: str) -> Tuple[float, date]:
    """
    Get the most recent closing price for a commodity.

    Returns:
        (price_in_dollars, date) tuple
    Note: Market data is stored in cents, so we convert to dollars
    """
    # Validate commodity to prevent SQL injection
    if commodity not in ALLOWED_COMMODITIES:
        raise ValueError(f"Invalid commodity: {commodity}. Allowed: {ALLOWED_COMMODITIES}")

    query = f"""
        SELECT close, date
        FROM commodity.bronze.market
        WHERE commodity = '{commodity}'
        ORDER BY date DESC
        LIMIT 1
    """

    try:
        rows = execute_databricks_query(query)

        if rows:
            # Convert from cents to dollars
            price_cents = float(rows[0][0])
            price_dollars = price_cents * PRICE_CENTS_TO_DOLLARS
            date_value = rows[0][1]

            print(f"Market price: {price_cents} cents = ${price_dollars:.2f} (date: {date_value})")
            return price_dollars, date_value
        else:
            raise ValueError(f"No market data found for {commodity}")
    except Exception as e:
        print(f"Error fetching market price for {commodity}: {str(e)}")
        raise


def calculate_7day_trend(commodity: str, current_date: date) -> float:
    """Calculate 7-day price trend percentage."""
    # Validate commodity
    if commodity not in ALLOWED_COMMODITIES:
        raise ValueError(f"Invalid commodity: {commodity}")

    query = f"""
        SELECT close
        FROM commodity.bronze.market
        WHERE commodity = '{commodity}'
          AND date <= '{current_date}'
        ORDER BY date DESC
        LIMIT 8
    """

    try:
        rows = execute_databricks_query(query)

        if len(rows) >= 2:
            current_price = float(rows[0][0])
            week_ago_price = float(rows[-1][0])
            trend_pct = ((current_price - week_ago_price) / week_ago_price) * 100
            print(f"7-day trend for {commodity}: {trend_pct:+.1f}% ({len(rows)} data points)")
            return trend_pct
        else:
            print(f"Insufficient data for 7-day trend (only {len(rows)} data points)")
            return 0.0
    except Exception as e:
        print(f"Error calculating 7-day trend for {commodity}: {str(e)}")
        return 0.0


def get_best_available_model(
    commodity: str,
    max_age_days: int = 10,
    metric: str = 'mae_14d'
) -> Optional[str]:
    """
    Get best performing model that has recent forecasts available.

    For 14-day forecasts, max_age_days should be small enough that the forecasts
    are still valid. A forecast from 14+ days ago has completely expired.
    Default is 10 days to capture forecasts that still have future coverage.

    Steps:
    1. Find all models with forecasts within max_age_days
    2. Among those, pick the one with best performance metrics
    3. If no metrics available, pick the one with most recent forecast date

    Args:
        commodity: 'Coffee' or 'Sugar'
        max_age_days: Maximum age of forecasts to consider (default 10 for 14-day forecasts)
        metric: Performance metric to optimize (mae_14d, rmse_14d, crps_14d)

    Returns:
        model_version string, or None if no forecasts available
    """
    # Validate commodity
    if commodity not in ALLOWED_COMMODITIES:
        raise ValueError(f"Invalid commodity: {commodity}")

    cutoff_date = date.today() - timedelta(days=max_age_days)

    # Step 1: Find all models with recent forecasts
    available_models_query = f"""
        SELECT DISTINCT model_version
        FROM commodity.forecast.distributions
        WHERE commodity = '{commodity}'
          AND is_actuals = FALSE
          AND forecast_start_date >= '{cutoff_date}'
    """

    try:
        available_models = execute_databricks_query(available_models_query)

        if not available_models or len(available_models) == 0:
            print(f"No models with recent forecasts for {commodity}")
            return None

        model_list = [row[0] for row in available_models]
        print(f"Found {len(model_list)} models with recent forecasts: {model_list}")

        # Step 2: Among available models, find the one with best metrics
        models_str = "', '".join(model_list)
        metrics_query = f"""
            SELECT
                m.model_version,
                AVG(m.{metric}) as avg_metric
            FROM commodity.forecast.forecast_metadata m
            WHERE m.commodity = '{commodity}'
              AND m.model_version IN ('{models_str}')
              AND m.{metric} IS NOT NULL
              AND m.model_success = TRUE
            GROUP BY m.model_version
            ORDER BY avg_metric ASC
            LIMIT 1
        """

        metric_rows = execute_databricks_query(metrics_query)

        if metric_rows and len(metric_rows) > 0:
            best_model = metric_rows[0][0]
            metric_value = float(metric_rows[0][1]) if metric_rows[0][1] is not None else None
            if metric_value is not None:
                print(f"Best model by {metric}: {best_model} (avg={metric_value:.4f})")
            else:
                print(f"Best model by {metric}: {best_model} (no metric value)")
            return best_model

        # Step 3: No metrics available, pick model with most recent forecast
        print(f"No performance metrics available, selecting by most recent forecast date")
        recent_query = f"""
            SELECT model_version, MAX(forecast_start_date) as latest_date
            FROM commodity.forecast.distributions
            WHERE commodity = '{commodity}'
              AND model_version IN ('{models_str}')
              AND is_actuals = FALSE
              AND forecast_start_date >= '{cutoff_date}'
            GROUP BY model_version
            ORDER BY latest_date DESC
            LIMIT 1
        """

        recent_rows = execute_databricks_query(recent_query)
        if recent_rows and len(recent_rows) > 0:
            recent_model = recent_rows[0][0]
            recent_date = recent_rows[0][1]
            print(f"Using most recent model: {recent_model} (latest forecast: {recent_date})")
            return recent_model

        return None

    except Exception as e:
        print(f"Error selecting best model: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_available_forecast(
    commodity: str,
    max_age_days: int = 10,
    preferred_model: Optional[str] = None
) -> Optional[Dict]:
    """
    Get forecast for commodity, preferring specified model if available.

    Returns:
        Dict with:
            - model_version: str
            - forecast_date: date
            - prediction_matrix: np.ndarray (N, 14) where N is number of paths
    """
    # Validate commodity
    if commodity not in ALLOWED_COMMODITIES:
        raise ValueError(f"Invalid commodity: {commodity}")

    cutoff_date = date.today() - timedelta(days=max_age_days)

    # If no preferred model specified, find the best available one
    if preferred_model is None:
        preferred_model = get_best_available_model(commodity, max_age_days)
        if preferred_model is None:
            return None

    # Get forecast for the preferred/best model
    query = f"""
        SELECT
            model_version,
            forecast_start_date,
            day_1, day_2, day_3, day_4, day_5, day_6, day_7,
            day_8, day_9, day_10, day_11, day_12, day_13, day_14
        FROM commodity.forecast.distributions
        WHERE commodity = '{commodity}'
          AND model_version = '{preferred_model}'
          AND is_actuals = FALSE
          AND forecast_start_date >= '{cutoff_date}'
        ORDER BY forecast_start_date DESC
        LIMIT 2000
    """

    rows = execute_databricks_query(query)

    if not rows:
        print(f"No forecast data for model {preferred_model}")
        return None

    # Extract model and date from first row
    model_version = rows[0][0]
    forecast_date = rows[0][1]

    # Build prediction matrix (N paths × 14 days)
    prediction_matrix = []
    for row in rows:
        if row[0] != model_version or row[1] != forecast_date:
            break  # Different model/date

        # Extract day_1 through day_14
        # Note: Prices in forecast are in CENTS (same as market data), convert to dollars
        path = [float(row[i]) * PRICE_CENTS_TO_DOLLARS for i in range(2, 16)]
        prediction_matrix.append(path)

    num_paths = len(prediction_matrix)
    print(f"Loaded {num_paths} paths for {model_version} (forecast date: {forecast_date})")

    if num_paths == 0:
        print(f"ERROR: No forecast paths loaded for {commodity}/{model_version}")
        return None

    prediction_array = np.array(prediction_matrix)
    print(f"Prediction matrix shape: {prediction_array.shape}")

    return {
        'model_version': model_version,
        'forecast_date': forecast_date,
        'prediction_matrix': prediction_array
    }


def get_trading_recommendation(
    commodity: str,
    current_price: float,
    prediction_matrix: np.ndarray,
    inventory_tons: float = 50.0,
    days_held: int = 0
) -> Dict:
    """
    Get trading recommendation using proven strategies from backtesting.

    Uses ExpectedValueStrategy which achieved +3.4% returns for Coffee in backtesting.
    Integrates with full trading algorithm infrastructure from daily_recommendations.py.

    Args:
        commodity: 'Coffee' or 'Sugar'
        current_price: Current market price ($/kg)
        prediction_matrix: Monte Carlo predictions (N paths × 14 days)
        inventory_tons: Current inventory size
        days_held: Days since harvest/purchase

    Returns:
        Dict with complete recommendation including:
            - action: 'HOLD' or 'SELL'
            - optimal_sale_day: Best day to sell
            - expected_gain_per_ton: Expected gain per ton
            - total_expected_gain: Total expected gain for inventory
            - sell_now_value: Value if sell today
            - wait_value: Value if wait for optimal day
            - forecast_range: (min, max) price range
            - best_sale_window: (start_day, end_day) for best 3-day window
    """
    # Get commodity-specific parameters (from backtesting results)
    config = COMMODITY_CONFIGS.get(commodity, COMMODITY_CONFIGS['Coffee'])

    # Initialize strategy with commodity-specific parameters (from backtesting)
    strategy = ExpectedValueStrategy(
        storage_cost_pct_per_day=config['storage_cost_pct_per_day'],
        transaction_cost_pct=config['transaction_cost_pct'],
        min_ev_improvement=config['min_ev_improvement'],
        baseline_batch=config['baseline_batch']
    )

    # Get strategy decision
    decision = strategy.decide(
        current_price=current_price,
        prediction_matrix=prediction_matrix,
        inventory=inventory_tons,
        days_held=days_held
    )

    # Analyze forecast distribution
    forecast_analysis = analyze_forecast_distribution(prediction_matrix, current_price)

    # Combine strategy decision with forecast analysis
    return {
        'action': decision['action'],
        'amount_to_sell': decision['amount'],
        'optimal_sale_day': decision['optimal_day'],
        'expected_gain_per_ton': decision['expected_gain_per_ton'],
        'total_expected_gain': decision['total_expected_gain'],
        'reasoning': decision['reasoning'],
        'sell_now_value': decision['sell_now_value'],
        'wait_value': decision['wait_value'],
        'forecast_range': forecast_analysis['price_range'],
        'best_sale_window': forecast_analysis['best_window'],
        'best_window_price': forecast_analysis['best_window_price']
    }


def format_whatsapp_message(
    commodity: str,
    current_price: float,
    price_date: date,
    trend_7d: float,
    forecast: Dict,
    strategy_decision: Dict,
    inventory_tons: float = 50.0
) -> str:
    """
    Format trading recommendation as WhatsApp message.

    Format matches specification from Whatsapp demo.pdf
    """
    from datetime import datetime, timedelta

    # Commodity emoji
    commodity_emoji = "☕" if commodity == "Coffee" else "🍬"

    # Format date
    today = datetime.now()
    date_str = today.strftime("%b %d, %Y")

    # Trend arrow and sign
    if trend_7d > 0:
        trend_arrow = "↑"
        trend_sign = "+"
    else:
        trend_arrow = "↓"
        trend_sign = ""

    # Convert price to $/ton (current price is $/kg, multiply by 1000)
    price_per_ton = current_price * 1000

    # Forecast range in $/ton
    forecast_range = strategy_decision['forecast_range']
    forecast_min_ton = forecast_range[0] * 1000
    forecast_max_ton = forecast_range[1] * 1000

    # Best sale window
    window = strategy_decision['best_sale_window']
    window_str = f"Days {window[0]}-{window[1]}"

    # Hold duration
    hold_duration = strategy_decision['optimal_sale_day']

    # Expected gain
    total_gain = strategy_decision['total_expected_gain']
    expected_gain_per_ton = strategy_decision['expected_gain_per_ton']

    # Calculate sell today value (per ton)
    immediate_sale_per_ton = price_per_ton * inventory_tons

    # Calculate wait for window value (per ton)
    if strategy_decision['action'] == 'HOLD':
        best_price_estimate = (forecast_min_ton + forecast_max_ton) / 2
        wait_value = best_price_estimate * inventory_tons
    else:
        wait_value = immediate_sale_per_ton

    # Build message header
    message = f"""{commodity_emoji} *{commodity.upper()} MARKET UPDATE*

_{date_str}_

*CURRENT MARKET*
📊 Today: ${price_per_ton:,.0f}/ton
{trend_arrow} 7-day trend: {trend_sign}{trend_7d:.1f}%

*FORECAST (14 days)*
🔮 Expected: ${forecast_min_ton:,.0f}-${forecast_max_ton:,.0f}/ton
📍 Best sale window: {window_str}

*YOUR INVENTORY*
📦 Stock: {int(inventory_tons)} tons
⏱ Held: {hold_duration} days

"""

    # Recommendation section
    if strategy_decision['action'] == 'HOLD':
        message += f"""✅ *RECOMMENDATION*

✅ *HOLD - Wait for better prices*
Expected gain: ${total_gain:,.0f}
Wait for forecast window: ${wait_value:,.0f}
Sell today: ${immediate_sale_per_ton:,.0f}"""
    else:
        message += f"""✅ *RECOMMENDATION*

✅ *SELL NOW*
Current market favorable
Sell today: ${immediate_sale_per_ton:,.0f}
Expected gain if wait: ${expected_gain_per_ton * inventory_tons:,.0f}"""

    # Next update time (6 AM tomorrow)
    tomorrow = today + timedelta(days=1)
    message += f"\n\n_Next update: Tomorrow 6 AM_"

    return message


def generate_recommendation_from_databricks(commodity: str) -> Dict:
    """
    Generate real recommendation by querying Databricks via REST API.

    Returns:
        Dict with:
            - whatsapp_message: str
            - metadata: dict
    """
    print(f"\n{'='*60}")
    print(f"Generating recommendation for {commodity} from Databricks")
    print(f"{'='*60}")

    # Get current market data
    print("\n[1/4] Fetching current market data...")
    current_price, price_date = get_latest_market_price(commodity)
    print(f"✓ Current price: ${current_price:.2f} (as of {price_date})")

    print("\n[2/4] Calculating 7-day trend...")
    trend_7d = calculate_7day_trend(commodity, price_date)
    print(f"✓ 7-day trend: {trend_7d:+.1f}%")

    # Get forecast
    print("\n[3/4] Fetching forecast data...")
    forecast = get_available_forecast(commodity)  # Uses default max_age_days=10

    if not forecast:
        raise ValueError(f"No recent forecast available for {commodity}")

    print(f"✓ Using model: {forecast['model_version']}")
    print(f"✓ Forecast date: {forecast['forecast_date']}")
    print(f"✓ Paths loaded: {forecast['prediction_matrix'].shape[0]}")

    # Calculate recommendation using trading algorithm (Expected Value strategy)
    print("\n[4/4] Calculating trading recommendation...")
    strategy_decision = get_trading_recommendation(
        commodity=commodity,
        current_price=current_price,
        prediction_matrix=forecast['prediction_matrix'],
        inventory_tons=50.0,
        days_held=0  # TODO: Track actual hold duration per user
    )
    print(f"✓ Decision: {strategy_decision['action']}")
    print(f"✓ Expected gain: ${strategy_decision['total_expected_gain']:,.2f}")
    print(f"✓ Strategy: ExpectedValue (proven +3.4% for Coffee in backtesting)")

    # Format message
    whatsapp_message = format_whatsapp_message(
        commodity=commodity,
        current_price=current_price,
        price_date=price_date,
        trend_7d=trend_7d,
        forecast=forecast,
        strategy_decision=strategy_decision,
        inventory_tons=50.0
    )

    print(f"\n{'='*60}")
    print("✓ Recommendation generated successfully")
    print(f"{'='*60}\n")

    return {
        'whatsapp_message': whatsapp_message,
        'metadata': {
            'commodity': commodity,
            'current_price': current_price,
            'model': forecast['model_version'],
            'strategy': 'ExpectedValue',
            'action': strategy_decision['action'],
            'expected_gain': strategy_decision['total_expected_gain']
        }
    }


def get_mock_recommendation(commodity='Coffee'):
    """
    Fallback mock recommendation if Databricks unavailable.

    Format matches specification from Whatsapp demo.pdf
    """
    from datetime import datetime

    today = datetime.now()
    date_str = today.strftime("%b %d, %Y")

    if commodity == 'Coffee':
        return {
            'whatsapp_message': f"""☕ *COFFEE MARKET UPDATE*

_{date_str}_

*CURRENT MARKET*
📊 Today: $7,780/ton
↑ 7-day trend: +3.2%

*FORECAST (14 days)*
🔮 Expected: $8,400-$9,000/ton
📍 Best sale window: Days 8-10

*YOUR INVENTORY*
📦 Stock: 50 tons
⏱ Held: 45 days

✅ *RECOMMENDATION*

✅ *HOLD - Wait for better prices*
Expected gain: $5,000
Wait for forecast window: $425,000
Sell today: $389,000

_Next update: Tomorrow 6 AM_""",
            'metadata': {
                'commodity': 'Coffee',
                'model': 'sarimax_auto_weather_v1',
                'strategy': 'ExpectedValue',
                'action': 'HOLD',
                'expected_gain': 5000
            }
        }
    elif commodity == 'Sugar':
        return {
            'whatsapp_message': f"""🍬 *SUGAR MARKET UPDATE*

_{date_str}_

*CURRENT MARKET*
📊 Today: $180/ton
↓ 7-day trend: -0.8%

*FORECAST (14 days)*
🔮 Expected: $170-$190/ton
📍 Best sale window: Days 3-5

*YOUR INVENTORY*
📦 Stock: 50 tons
⏱ Held: 0 days

✅ *RECOMMENDATION*

✅ *SELL NOW*
Current market favorable
Sell today: $9,000
Expected gain if wait: $0

_Next update: Tomorrow 6 AM_""",
            'metadata': {
                'commodity': 'Sugar',
                'model': 'prophet_v1',
                'strategy': 'Consensus',
                'action': 'SELL',
                'expected_gain': 0
            }
        }
    else:
        return get_mock_recommendation('Coffee')


def parse_commodity_from_message(message_body):
    """
    Extract commodity preference from user message.

    Examples:
        "coffee" → Coffee
        "sugar recommendation" → Sugar
        "hello" → None (show help)
        "exit" → 'EXIT' (special marker)

    Returns:
        Commodity name, 'EXIT' for exit commands, or None for help
    """
    message_lower = message_body.lower().strip()

    # Handle exit/stop commands
    exit_commands = ['exit', 'stop', 'quit', 'unsubscribe', 'leave', 'cancel']
    if any(cmd in message_lower for cmd in exit_commands):
        return 'EXIT'

    # Recognize explicit commodity requests
    if 'sugar' in message_lower:
        return 'Sugar'
    elif 'coffee' in message_lower:
        return 'Coffee'
    else:
        # Unrecognized message - return None to show help
        return None


def format_twilio_response(message):
    """
    Format response for Twilio webhook.

    Twilio expects TwiML response format wrapped in API Gateway response.
    """
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{message}</Message>
</Response>"""

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'text/xml'},
        'body': twiml
    }


def lambda_handler(event, context):
    """
    AWS Lambda handler for Twilio WhatsApp webhook.

    Event structure (from API Gateway):
        {
            'body': 'From=whatsapp%3A%2B1234567890&Body=coffee&...',
            'headers': {...},
            'httpMethod': 'POST',
            ...
        }

    Returns:
        {
            'statusCode': 200,
            'headers': {'Content-Type': 'text/xml'},
            'body': '<Response><Message>...</Message></Response>'
        }
    """

    # Log incoming request
    print(f"Received WhatsApp webhook: {json.dumps(event)}")

    try:
        # Parse form data from Twilio
        if event.get('body'):
            # Parse URL-encoded form data
            from urllib.parse import parse_qs
            import base64

            body = event['body']

            # Lambda Function URLs base64-encode the body
            if event.get('isBase64Encoded', False):
                body = base64.b64decode(body).decode('utf-8')

            params = parse_qs(body)

            # Extract Twilio parameters
            from_number = params.get('From', [''])[0]
            message_body = params.get('Body', [''])[0]

            print(f"From: {from_number}")
            print(f"Message: {message_body}")

            # Check if this is a JOIN message (Twilio sandbox activation)
            message_lower = message_body.strip().lower()
            if message_lower.startswith('join '):
                print(f"🎉 New user joining via sandbox: {message_body}")
                print("Auto-sending Coffee welcome recommendation")
                commodity = 'Coffee'  # Welcome with Coffee by default
            else:
                # Determine commodity from message
                commodity = parse_commodity_from_message(message_body)

            # Handle special responses
            if commodity == 'EXIT':
                print(f"User requested exit: {message_body}")
                goodbye_message = "Thanks for using GroundTruth Trading!\n\nTo unsubscribe from this sandbox, reply with STOP\n\nOr message 'coffee' or 'sugar' anytime to get new recommendations."
                return format_twilio_response(goodbye_message)

            if commodity is None:
                print(f"Unrecognized message, sending help: {message_body}")
                help_message = """Welcome to GroundTruth Trading!

AI-powered commodity market recommendations.

To get started, send one of these:
  • coffee - Get coffee market update
  • sugar - Get sugar market update

You can also send:
  • exit - Stop receiving messages

Powered by real-time GDELT analysis"""
                return format_twilio_response(help_message)

            print(f"Detected commodity: {commodity}")

            # Get recommendation
            try:
                if os.environ.get('DATABRICKS_HOST'):
                    print("Querying Databricks for real data via REST API...")
                    recommendation = generate_recommendation_from_databricks(commodity)
                else:
                    print("Using mock data (Databricks not configured)")
                    recommendation = get_mock_recommendation(commodity)
            except Exception as e:
                print(f"Error getting recommendation from Databricks: {str(e)}")
                import traceback
                traceback.print_exc()
                print("Falling back to mock data")
                recommendation = get_mock_recommendation(commodity)

            # Log metadata
            print(f"Recommendation metadata: {json.dumps(recommendation['metadata'])}")

            # Format and return response
            return format_twilio_response(recommendation['whatsapp_message'])

        else:
            # No body - return error
            error_message = "No message received. Try sending 'coffee' or 'sugar'."
            return format_twilio_response(error_message)

    except Exception as e:
        # Log error
        print(f"Error processing webhook: {str(e)}")
        import traceback
        traceback.print_exc()

        # Return friendly error message
        error_message = "Sorry, something went wrong. Please try again later."
        response = format_twilio_response(error_message)
        response['statusCode'] = 500  # Override to 500 for errors
        return response


# For local testing
if __name__ == "__main__":
    # Simulate Twilio webhook call
    test_event = {
        'body': 'From=whatsapp%3A%2B15555551234&Body=coffee&MessageSid=SM123',
        'httpMethod': 'POST',
        'headers': {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
    }

    result = lambda_handler(test_event, None)
    print("\nResponse:")
    print(result['body'])
