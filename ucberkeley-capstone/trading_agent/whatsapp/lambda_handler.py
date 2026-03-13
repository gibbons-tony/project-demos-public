"""
WhatsApp Trading Recommendations - Lambda Handler

Responds to Twilio WhatsApp webhook with trading recommendations.
For demo: Returns mock data immediately.
For production: Can query Databricks for real recommendations.
"""

import json
import os
from datetime import datetime


def get_mock_recommendation(commodity='Coffee'):
    """
    Generate mock recommendation for demo.

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
        # Default to Coffee
        return get_mock_recommendation('Coffee')


def parse_commodity_from_message(message_body):
    """
    Extract commodity preference from user message.

    Examples:
        "coffee" → Coffee
        "sugar recommendation" → Sugar
        "hello" → Coffee (default)
    """
    message_lower = message_body.lower()

    if 'sugar' in message_lower:
        return 'Sugar'
    else:
        # Default to Coffee
        return 'Coffee'


def format_twilio_response(message):
    """
    Format response for Twilio webhook.

    Twilio expects TwiML response format.
    """
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{message}</Message>
</Response>"""

    return twiml


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

            body = event['body']
            params = parse_qs(body)

            # Extract Twilio parameters
            from_number = params.get('From', [''])[0]
            message_body = params.get('Body', [''])[0]

            print(f"From: {from_number}")
            print(f"Message: {message_body}")

            # Determine commodity from message
            commodity = parse_commodity_from_message(message_body)
            print(f"Detected commodity: {commodity}")

            # Get recommendation (mock for demo)
            recommendation = get_mock_recommendation(commodity)

            # Log metadata
            print(f"Recommendation metadata: {json.dumps(recommendation['metadata'])}")

            # Format response
            twiml = format_twilio_response(recommendation['whatsapp_message'])

            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'text/xml'
                },
                'body': twiml
            }

        else:
            # No body - return error
            error_message = "No message received. Try sending 'coffee' or 'sugar'."
            twiml = format_twilio_response(error_message)

            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'text/xml'
                },
                'body': twiml
            }

    except Exception as e:
        # Log error
        print(f"Error processing webhook: {str(e)}")
        import traceback
        traceback.print_exc()

        # Return friendly error message
        error_message = "Sorry, something went wrong. Please try again later."
        twiml = format_twilio_response(error_message)

        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'text/xml'
            },
            'body': twiml
        }


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
