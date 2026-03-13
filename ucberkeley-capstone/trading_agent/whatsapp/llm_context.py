"""
LLM Context Builder for WhatsApp Trading Bot

Provides structured context for Claude AI to answer questions about:
- Forecast models and their performance
- Forecast scenarios and Monte Carlo simulations
- Trading strategy calculations
- Market trends and pricing data
"""

import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any, Tuple
import numpy as np
import requests


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

    # Prepare request URL
    clean_host = host.replace('https://', '').replace('http://', '')
    url = f"https://{clean_host}/api/2.0/sql/statements/"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "statement": sql_query,
        "warehouse_id": warehouse_id,
        "wait_timeout": "30s"
    }

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

        state = status_data.get('status', {}).get('state')

        if state == 'SUCCEEDED':
            # Extract data
            manifest = status_data.get('manifest', {})
            chunks = manifest.get('chunks', [])

            if not chunks:
                return []

            # Fetch first chunk
            chunk_index = chunks[0].get('chunk_index', 0)
            chunk_url = f"{status_url}/result/chunks/{chunk_index}"
            chunk_response = requests.get(chunk_url, headers=headers)
            chunk_response.raise_for_status()
            chunk_data = chunk_response.json()

            return chunk_data.get('data_array', [])

        elif state in ['FAILED', 'CANCELED', 'CLOSED']:
            error = status_data.get('status', {}).get('error', {})
            raise Exception(f"Query {state}: {error}")

        time.sleep(1)

    raise Exception(f"Query timed out after {timeout}s")


# ==============================================================================
# CORE CONTEXT BUILDERS
# ==============================================================================

def get_forecast_model_context(commodity: str, model_name: str) -> Dict:
    """
    Query forecast_metadata table for model details.

    Args:
        commodity: Commodity name (Coffee, Sugar, etc.)
        model_name: Model version name (arima_111_v1, etc.)

    Returns:
        Dictionary with model info, performance metrics, and selection rationale
    """
    # Query model metadata
    query = f"""
    SELECT
        model_version,
        mae_14d,
        rmse_14d,
        crps_14d,
        coverage_95pct
    FROM commodity.forecast.forecast_metadata
    WHERE commodity = '{commodity}'
      AND is_actuals = FALSE
      AND has_data_leakage = FALSE
      AND model_success = TRUE
    ORDER BY mae_14d ASC
    LIMIT 10
    """

    rows = execute_databricks_query(query)

    if not rows:
        return {
            'model_info': {'name': model_name, 'type': 'Unknown'},
            'performance': {},
            'selection_rationale': {'why_chosen': 'No data available'}
        }

    # Find selected model
    selected = None
    alternatives = []

    for i, row in enumerate(rows):
        model_data = {
            'name': row[0],
            'mae_14d': float(row[1]) if row[1] is not None else None,
            'rmse_14d': float(row[2]) if row[2] is not None else None,
            'crps_14d': float(row[3]) if row[3] is not None else None,
            'coverage_95pct': float(row[4]) if row[4] is not None else None,
            'rank': i + 1
        }

        if row[0] == model_name:
            selected = model_data
        else:
            alternatives.append((row[0], float(row[1]) if row[1] else 999))

    # If model not found, use best model
    if not selected:
        selected = {
            'name': rows[0][0],
            'mae_14d': float(rows[0][1]) if rows[0][1] else None,
            'rmse_14d': float(rows[0][2]) if rows[0][2] else None,
            'crps_14d': float(rows[0][3]) if rows[0][3] else None,
            'coverage_95pct': float(rows[0][4]) if rows[0][4] else None,
            'rank': 1
        }

    # Extract model type from name
    model_type = 'ARIMA'
    if 'sarimax' in selected['name'].lower():
        model_type = 'SARIMAX'
    elif 'random_walk' in selected['name'].lower():
        model_type = 'Random Walk'
    elif 'prophet' in selected['name'].lower():
        model_type = 'Prophet'

    return {
        'model_info': {
            'name': selected['name'],
            'type': model_type,
            'features': ['Historical prices', 'Seasonal patterns'] if 'weather' not in selected['name'] else ['Historical prices', 'Seasonal patterns', 'Weather data']
        },
        'performance': {
            'mae_14d': selected['mae_14d'],
            'rmse_14d': selected['rmse_14d'],
            'crps_14d': selected['crps_14d'],
            'coverage_95pct': selected['coverage_95pct']
        },
        'selection_rationale': {
            'why_chosen': f"Lowest MAE ({selected['mae_14d']:.2f}) among {len(rows)} tested models",
            'rank': selected['rank'],
            'alternatives': alternatives[:3]
        }
    }


def get_forecast_scenario_context(
    commodity: str,
    forecast_date: str,
    model_name: str
) -> Dict:
    """
    Explain how forecast scenarios work using actual data.

    Args:
        commodity: Commodity name
        forecast_date: Forecast start date (YYYY-MM-DD)
        model_name: Model version name

    Returns:
        Dictionary with scenario generation details and interpretation
    """
    # Query forecast distributions for percentiles
    query = f"""
    SELECT
        PERCENTILE(day_7, 0.10) as p10_d7,
        PERCENTILE(day_7, 0.50) as p50_d7,
        PERCENTILE(day_7, 0.90) as p90_d7,
        PERCENTILE(day_14, 0.10) as p10_d14,
        PERCENTILE(day_14, 0.50) as p50_d14,
        PERCENTILE(day_14, 0.90) as p90_d14,
        AVG(day_7) as mean_d7,
        STDDEV(day_7) as std_d7,
        COUNT(*) as num_paths
    FROM commodity.forecast.distributions
    WHERE commodity = '{commodity}'
      AND forecast_start_date = '{forecast_date}'
      AND model_version = '{model_name}'
      AND is_actuals = FALSE
      AND has_data_leakage = FALSE
    """

    rows = execute_databricks_query(query)

    if not rows or not rows[0][0]:
        return {
            'generation': {
                'method': 'Monte Carlo Simulation',
                'num_paths': 2000,
                'horizon_days': 14
            },
            'forecast_metadata': {'forecast_date': forecast_date},
            'interpretation': {'price_range': {}}
        }

    row = rows[0]
    p10_d7, p50_d7, p90_d7 = row[0], row[1], row[2]
    p10_d14, p50_d14, p90_d14 = row[3], row[4], row[5]
    mean_d7, std_d7, num_paths = row[6], row[7], int(row[8])

    # Calculate coefficient of variation for volatility assessment
    cv = (std_d7 / mean_d7) if mean_d7 and mean_d7 > 0 else 0
    volatility = 'Low' if cv < 0.05 else 'Moderate' if cv < 0.10 else 'High'

    # Count rising vs falling scenarios
    rising_pct = 50  # Simplified - would need actual calculation
    falling_pct = 50

    return {
        'generation': {
            'method': 'Monte Carlo Simulation',
            'num_paths': num_paths,
            'horizon_days': 14,
            'how_it_works': [
                '1. Model predicts expected trend',
                '2. Adds realistic price volatility',
                '3. Simulates 2000 possible outcomes'
            ]
        },
        'forecast_metadata': {
            'forecast_date': forecast_date,
            'data_cutoff': forecast_date,
            'next_update': 'Daily at 6 AM UTC'
        },
        'interpretation': {
            'price_range': {
                'day_7': {'p10': p10_d7, 'p50': p50_d7, 'p90': p90_d7},
                'day_14': {'p10': p10_d14, 'p50': p50_d14, 'p90': p90_d14}
            },
            'confidence_80pct': f"Day 7 prices between ${p10_d7:.2f}-${p90_d7:.2f}/ton",
            'volatility': f"{volatility} (CV: {cv:.2f})"
        },
        'scenario_distribution': {
            'rising_scenarios_pct': rising_pct,
            'falling_scenarios_pct': falling_pct,
            'volatility': volatility
        }
    }


def get_trading_strategy_context(
    recommendation: Dict,
    prediction_matrix: np.ndarray,
    current_price: float,
    storage_cost_pct_per_day: float = 0.025
) -> Dict:
    """
    Explain trading decision with step-by-step calculation.

    Args:
        recommendation: Output from ExpectedValueStrategy.decide()
        prediction_matrix: 2000 x 14 numpy array (forecasts)
        current_price: Current market price ($/ton)
        storage_cost_pct_per_day: Storage cost as % of price per day

    Returns:
        Dictionary with strategy explanation and calculations
    """
    # Calculate expected prices for key days
    day_0_value = current_price
    day_7_expected = np.mean(prediction_matrix[:, 6]) if prediction_matrix.shape[1] > 6 else current_price
    day_14_expected = np.mean(prediction_matrix[:, 13]) if prediction_matrix.shape[1] > 13 else current_price

    # Calculate storage costs
    storage_cost_per_day = current_price * (storage_cost_pct_per_day / 100)
    cost_7d = 7 * storage_cost_per_day
    cost_14d = 14 * storage_cost_per_day

    # Net values after storage costs
    net_value_d0 = day_0_value
    net_value_d7 = day_7_expected - cost_7d
    net_value_d14 = day_14_expected - cost_14d

    # Get optimal day from recommendation
    optimal_day = recommendation.get('optimal_sell_day', 0)
    expected_gain = recommendation.get('expected_gain_per_ton', 0)
    action = recommendation.get('action', 'HOLD')

    # Determine confidence based on clarity of decision
    if abs(expected_gain) > 10:
        confidence = 'High'
    elif abs(expected_gain) > 5:
        confidence = 'Moderate'
    else:
        confidence = 'Low'

    # Risk assessment
    if action == 'SELL':
        risk = 'Low - avoiding storage costs'
    else:
        risk = 'Moderate - holding for potential gains'

    return {
        'strategy': {
            'name': 'ExpectedValueStrategy',
            'approach': 'Maximize expected profit after storage costs'
        },
        'calculation': {
            'current_price': current_price,
            'storage_cost_per_day': storage_cost_per_day,
            'expected_price_day_0': day_0_value,
            'expected_price_day_7': day_7_expected,
            'expected_price_day_14': day_14_expected,
            'net_value_day_0': net_value_d0,
            'net_value_day_7': net_value_d7,
            'net_value_day_14': net_value_d14,
            'optimal_day': optimal_day,
            'expected_gain_per_ton': expected_gain
        },
        'reasoning': {
            'decision': action,
            'why': recommendation.get('reason', 'Optimizing expected value'),
            'confidence': confidence,
            'risk_assessment': risk
        },
        'assumptions': {
            'storage_cost': f"{storage_cost_pct_per_day}% per day",
            'no_spoilage': True,
            'liquid_market': True,
            'no_transaction_costs': True
        }
    }


def get_market_context(commodity: str) -> Dict:
    """
    Get current market state and trends.

    Args:
        commodity: Commodity name

    Returns:
        Dictionary with price trends (GDELT sentiment excluded for now)
    """
    # Query recent market data (last 30 days)
    query = f"""
    SELECT date, price
    FROM commodity.bronze.market
    WHERE commodity = '{commodity}'
    ORDER BY date DESC
    LIMIT 30
    """

    rows = execute_databricks_query(query)

    if not rows or len(rows) == 0:
        return {
            'price_trends': {
                'current': 0,
                '7d_change_pct': 0,
                '30d_change_pct': 0
            },
            'news_sentiment': {
                'status': 'unavailable',
                'reason': 'GDELT backfill in progress (99.9% incomplete)'
            }
        }

    # Extract prices (convert from cents to dollars)
    prices = [float(row[1]) * 0.01 for row in rows]
    dates = [row[0] for row in rows]

    current_price = prices[0]

    # Calculate 7-day change
    if len(prices) >= 7:
        price_7d_ago = prices[6]
        change_7d_pct = ((current_price - price_7d_ago) / price_7d_ago) * 100 if price_7d_ago > 0 else 0
    else:
        change_7d_pct = 0

    # Calculate 30-day change
    if len(prices) >= 30:
        price_30d_ago = prices[29]
        change_30d_pct = ((current_price - price_30d_ago) / price_30d_ago) * 100 if price_30d_ago > 0 else 0
    else:
        change_30d_pct = 0

    # Calculate 30-day high/low
    high_30d = max(prices)
    low_30d = min(prices)

    return {
        'price_trends': {
            'current': current_price,
            '7d_change_pct': change_7d_pct,
            '30d_change_pct': change_30d_pct,
            'ytd_change_pct': 0,  # Would need full year data
            '30d_high': high_30d,
            '30d_low': low_30d
        },
        'news_sentiment': {
            'status': 'unavailable',
            'reason': 'GDELT backfill in progress (99.9% incomplete)'
        },
        'fundamental_factors': {
            'supply_status': 'Unknown (no data)',
            'demand_status': 'Unknown (no data)'
        }
    }


def build_llm_context(
    message: str,
    commodity: str,
    market_data: Dict,
    forecast_data: Dict,
    recommendation: Dict,
    prediction_matrix: np.ndarray,
    model_name: str
) -> Dict:
    """
    Assemble complete context for Claude API call.

    Args:
        message: User's question
        commodity: Commodity name
        market_data: Current market state (from existing handler)
        forecast_data: Forecast summary (from existing handler)
        recommendation: Trading recommendation (from existing handler)
        prediction_matrix: 2000 x 14 numpy array
        model_name: Model version name

    Returns:
        Complete context dictionary for Claude
    """
    # Get enriched context
    model_info = get_forecast_model_context(commodity, model_name)

    # Get forecast scenario context
    forecast_date = forecast_data.get('forecast_date', datetime.now().strftime('%Y-%m-%d'))
    scenario_info = get_forecast_scenario_context(commodity, forecast_date, model_name)

    # Get strategy context
    current_price = market_data.get('current_price', 0)
    storage_cost_pct = 0.025  # From COMMODITY_CONFIGS
    strategy_info = get_trading_strategy_context(
        recommendation,
        prediction_matrix,
        current_price,
        storage_cost_pct
    )

    # Get market context
    market_context = get_market_context(commodity)

    return {
        'user_message': message,
        'timestamp': datetime.now().isoformat(),
        'commodity': commodity,

        # Existing data
        'market_data': market_data,
        'forecast': forecast_data,
        'recommendation': recommendation,

        # New explanatory context
        'model_info': model_info,
        'scenario_info': scenario_info,
        'strategy_info': strategy_info,
        'market_context': market_context
    }


# ==============================================================================
# INTENT DETECTION & COMMODITY EXTRACTION
# ==============================================================================

def detect_intent(message: str) -> str:
    """
    Classify message type.

    Args:
        message: User's message

    Returns:
        'commodity_lookup' | 'question' | 'comparison' | 'help'
    """
    message_lower = message.lower().strip()

    # Simple commodity lookup
    commodities = ['coffee', 'wheat', 'rice', 'corn', 'sugar', 'cocoa', 'cotton']
    if message_lower in commodities:
        return 'commodity_lookup'

    # Question indicators
    question_words = ['why', 'what', 'how', 'when', 'explain', 'tell me', 'should i', 'can you']
    if any(word in message_lower for word in question_words):
        return 'question'

    # Comparison
    if 'compare' in message_lower or ' vs ' in message_lower:
        return 'comparison'

    # Help
    if message_lower in ['help', 'info', 'commands', '?']:
        return 'help'

    # Default to question for complex messages
    if len(message.split()) > 3:
        return 'question'

    return 'help'


def extract_commodity(message: str) -> Optional[str]:
    """
    Extract commodity name from message.

    Args:
        message: User's message

    Returns:
        Commodity name (capitalized) or None
    """
    message_lower = message.lower()

    commodities = {
        'coffee': 'Coffee',
        'wheat': 'Wheat',
        'rice': 'Rice',
        'corn': 'Corn',
        'sugar': 'Sugar',
        'cocoa': 'Cocoa',
        'cotton': 'Cotton'
    }

    for key, value in commodities.items():
        if key in message_lower:
            return value

    # Default to Coffee if no commodity mentioned (most common)
    return 'Coffee'


# ==============================================================================
# FORMAT FUNCTIONS FOR CLAUDE PROMPTS
# ==============================================================================

def format_market_data(market_data: Dict) -> str:
    """Format market data for Claude prompt."""
    current = market_data.get('current_price', 0)
    change_7d = market_data.get('7d_change_pct', 0)
    change_30d = market_data.get('30d_change_pct', 0)
    high_30d = market_data.get('30d_high', 0)
    low_30d = market_data.get('30d_low', 0)

    return f"""Current Price: ${current:.2f}/ton
7-day change: {change_7d:+.1f}%
30-day change: {change_30d:+.1f}%
30-day range: ${low_30d:.2f} - ${high_30d:.2f}"""


def format_forecast_data(forecast: Dict) -> str:
    """Format forecast for Claude prompt."""
    forecast_date = forecast.get('forecast_date', 'Unknown')
    forecast_min = forecast.get('forecast_min', 0)
    forecast_max = forecast.get('forecast_max', 0)
    forecast_mean = forecast.get('forecast_mean', 0)

    return f"""Forecast Date: {forecast_date}
Expected Price Range (14 days): ${forecast_min:.2f} - ${forecast_max:.2f}/ton
Mean Forecast: ${forecast_mean:.2f}/ton
Method: 2000 Monte Carlo simulations"""


def format_model_info(model_info: Dict) -> str:
    """Format model metadata for Claude prompt."""
    name = model_info.get('model_info', {}).get('name', 'Unknown')
    model_type = model_info.get('model_info', {}).get('type', 'Unknown')
    mae = model_info.get('performance', {}).get('mae_14d', 0)
    rmse = model_info.get('performance', {}).get('rmse_14d', 0)
    coverage = model_info.get('performance', {}).get('coverage_95pct', 0)
    why_chosen = model_info.get('selection_rationale', {}).get('why_chosen', 'Unknown')

    return f"""Model: {name}
Type: {model_type}
Accuracy (MAE 14-day): ${mae:.2f}/ton
RMSE: ${rmse:.2f}/ton
95% Confidence Coverage: {coverage:.1f}%
Selection Rationale: {why_chosen}"""


def format_scenario_info(scenario_info: Dict) -> str:
    """Format scenario explanation for Claude prompt."""
    method = scenario_info.get('generation', {}).get('method', 'Unknown')
    num_paths = scenario_info.get('generation', {}).get('num_paths', 2000)
    day_7 = scenario_info.get('interpretation', {}).get('price_range', {}).get('day_7', {})
    volatility = scenario_info.get('interpretation', {}).get('volatility', 'Unknown')

    p10 = day_7.get('p10', 0)
    p50 = day_7.get('p50', 0)
    p90 = day_7.get('p90', 0)

    return f"""Method: {method}
Number of Scenarios: {num_paths}
Day 7 Forecast Range:
  - 10th percentile (downside): ${p10:.2f}/ton
  - 50th percentile (median): ${p50:.2f}/ton
  - 90th percentile (upside): ${p90:.2f}/ton
Volatility: {volatility}"""


def format_recommendation(recommendation: Dict) -> str:
    """Format trading decision for Claude prompt."""
    action = recommendation.get('action', 'HOLD')
    reason = recommendation.get('reason', 'Unknown')
    optimal_day = recommendation.get('optimal_sell_day', 0)
    expected_gain = recommendation.get('expected_gain_per_ton', 0)

    return f"""Decision: {action}
Reason: {reason}
Optimal Sell Day: Day {optimal_day}
Expected Gain: ${expected_gain:.2f}/ton"""


def format_strategy_info(strategy_info: Dict) -> str:
    """Format strategy explanation for Claude prompt."""
    calc = strategy_info.get('calculation', {})
    reasoning = strategy_info.get('reasoning', {})

    current_price = calc.get('current_price', 0)
    storage_cost = calc.get('storage_cost_per_day', 0)
    net_d0 = calc.get('net_value_day_0', 0)
    net_d7 = calc.get('net_value_day_7', 0)
    optimal_day = calc.get('optimal_day', 0)
    gain = calc.get('expected_gain_per_ton', 0)

    decision = reasoning.get('decision', 'HOLD')
    why = reasoning.get('why', 'Unknown')
    confidence = reasoning.get('confidence', 'Unknown')

    return f"""Strategy: ExpectedValueStrategy (maximize profit after costs)

Calculation:
  Current Price: ${current_price:.2f}/ton
  Storage Cost: ${storage_cost:.2f}/ton/day
  Net Value Day 0 (sell now): ${net_d0:.2f}/ton
  Net Value Day 7 (sell later): ${net_d7:.2f}/ton
  Optimal Day: Day {optimal_day}
  Expected Gain: ${gain:.2f}/ton

Decision: {decision}
Reasoning: {why}
Confidence: {confidence}"""
