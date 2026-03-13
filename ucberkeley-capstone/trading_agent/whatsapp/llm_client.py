"""
LLM Client for WhatsApp Trading Bot

Handles Claude AI API calls for conversational Q&A about trading recommendations.
"""

import os
import json
import time
from typing import Dict, Optional

# Import Anthropic SDK
try:
    import anthropic
except ImportError:
    # Will be available in Lambda after deployment
    anthropic = None

# Import formatting functions from llm_context
from llm_context import (
    format_market_data,
    format_forecast_data,
    format_model_info,
    format_scenario_info,
    format_recommendation,
    format_strategy_info
)


def query_claude(
    user_question: str,
    context: dict,
    max_tokens: int = 500,
    temperature: float = 0.3
) -> str:
    """
    Call Claude with structured context and get response.

    Args:
        user_question: User's question from WhatsApp
        context: Output from build_llm_context()
        max_tokens: Response length limit (500 = ~2 WhatsApp messages)
        temperature: 0.3 = more deterministic, less creative

    Returns:
        Claude's response text

    Raises:
        Exception if API call fails
    """
    if anthropic is None:
        raise Exception("anthropic package not available")

    # Get API key from environment
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise Exception("ANTHROPIC_API_KEY not set")

    # Initialize client
    client = anthropic.Anthropic(api_key=api_key)

    # Build system prompt
    system_prompt = """You are an expert commodity trading advisor with access to:
- Real-time market prices from Databricks
- Probabilistic forecasts from ML models (2000 Monte Carlo paths)
- Trading strategy recommendations based on Expected Value optimization

Your role:
1. Answer questions clearly and concisely (WhatsApp format - brief!)
2. Explain forecast models and scenarios when asked
3. Provide transparent reasoning for recommendations
4. Acknowledge uncertainty and limitations
5. Use data to support your answers

Guidelines:
- Keep responses under 500 characters for WhatsApp readability
- Use bullet points for clarity
- Cite specific numbers from the data
- If you don't have the data, say so explicitly
- Explain technical concepts in simple terms
- Focus on actionable insights"""

    # Build user prompt with context
    market_data = context.get('market_data', {})
    forecast = context.get('forecast', {})
    model_info = context.get('model_info', {})
    scenario_info = context.get('scenario_info', {})
    recommendation = context.get('recommendation', {})
    strategy_info = context.get('strategy_info', {})

    user_prompt = f"""User Question: {user_question}

MARKET DATA:
{format_market_data(market_data)}

FORECAST:
{format_forecast_data(forecast)}

MODEL INFORMATION:
{format_model_info(model_info)}

SCENARIO DETAILS:
{format_scenario_info(scenario_info)}

TRADING RECOMMENDATION:
{format_recommendation(recommendation)}

STRATEGY EXPLANATION:
{format_strategy_info(strategy_info)}

Please answer the user's question based on this data. Be concise and specific."""

    print(f"Calling Claude API with {len(user_prompt)} chars context...")

    # Call Claude
    start_time = time.time()

    message = client.messages.create(
        model="claude-3-5-haiku-20241022",  # Fast and cheap
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_prompt,
        messages=[{
            "role": "user",
            "content": user_prompt
        }]
    )

    response_time = time.time() - start_time
    token_count = message.usage.input_tokens + message.usage.output_tokens

    print(f"Claude response: {token_count} tokens in {response_time:.2f}s")

    return message.content[0].text


def format_llm_response(
    claude_response: str,
    commodity: str = None
) -> Dict:
    """
    Format Claude's response for WhatsApp with emoji and structure.

    Args:
        claude_response: Claude's answer
        commodity: Optional commodity name for icon

    Returns:
        Lambda response dict with TwiML body
    """
    # Add commodity icon
    icons = {
        'coffee': '☕',
        'wheat': '🌾',
        'rice': '🍚',
        'corn': '🌽',
        'sugar': '🍬',
        'cocoa': '🍫',
        'cotton': '👕'
    }

    icon = icons.get(commodity.lower() if commodity else None, '📊')

    # Format message
    message = f"""{icon} *COMMODITY ADVISOR*

{claude_response}

_Powered by Claude AI + Real-time Data_"""

    # Create TwiML response (without importing twilio library)
    twiml_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{message}</Message>
</Response>"""

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'text/xml'},
        'body': twiml_body
    }


def handle_llm_error(error: Exception) -> Dict:
    """
    Handle LLM errors gracefully.

    Args:
        error: Exception that occurred

    Returns:
        Lambda response dict with error message
    """
    error_message = f"""⚠️ *TEMPORARY ISSUE*

I'm having trouble processing your request right now.

Error: {str(error)[:100]}

Please try:
• Asking a simpler question
• Requesting a commodity summary (just type "coffee")
• Waiting a moment and trying again

_Our team has been notified_"""

    # Create TwiML response
    twiml_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{error_message}</Message>
</Response>"""

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'text/xml'},
        'body': twiml_body
    }


def handle_help_response() -> Dict:
    """
    Return help message.

    Returns:
        Lambda response dict with help text
    """
    help_text = """📱 *HOW TO USE*

*Get Recommendations:*
Just type a commodity name:
• coffee
• sugar
• wheat

*Ask Questions:*
• Why should I sell?
• What forecast model are you using?
• How accurate are predictions?
• Explain the scenarios

*Get Help:*
• help - Show this message

_Trading recommendations updated daily at 6 AM UTC_"""

    # Create TwiML response
    twiml_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{help_text}</Message>
</Response>"""

    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'text/xml'},
        'body': twiml_body
    }
