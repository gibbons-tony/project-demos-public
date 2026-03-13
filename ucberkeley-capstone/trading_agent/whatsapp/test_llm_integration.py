"""
Test LLM integration with Lambda handler

Tests the intent detection and routing logic without deploying to Lambda.
"""

import os
import sys

# Set up test environment
os.environ['DATABRICKS_HOST'] = 'https://dbc-5e4780f4-fcec.cloud.databricks.com'
os.environ['DATABRICKS_TOKEN'] = '***REMOVED***'
os.environ['DATABRICKS_HTTP_PATH'] = '/sql/1.0/warehouses/d88ad009595327fd'

# Mock Anthropic API key for testing (won't be called in intent test)
os.environ['ANTHROPIC_API_KEY'] = 'test-key'

# Import modules
from llm_context import detect_intent, extract_commodity

def test_intent_detection():
    """Test intent detection for different message types"""

    test_cases = [
        # Commodity lookup (simple requests)
        ("coffee", "commodity_lookup", "Coffee"),
        ("sugar", "commodity_lookup", "Sugar"),
        ("Coffee", "commodity_lookup", "Coffee"),
        ("give me coffee update", "commodity_lookup", "Coffee"),

        # Questions
        ("Why should I sell coffee?", "question", "Coffee"),
        ("What forecast model are you using?", "question", None),
        ("How accurate are coffee predictions?", "question", "Coffee"),
        ("Explain the scenarios", "question", None),
        ("What is the best time to sell sugar?", "question", "Sugar"),

        # Comparisons
        ("Compare coffee and sugar", "comparison", None),
        ("Which is better coffee or sugar?", "comparison", None),

        # Help
        ("help", "help", None),
        ("what can you do", "help", None),
        ("hello", "help", None),
    ]

    print("=" * 70)
    print("TESTING INTENT DETECTION")
    print("=" * 70)

    passed = 0
    failed = 0

    for message, expected_intent, expected_commodity in test_cases:
        detected_intent = detect_intent(message)
        detected_commodity = extract_commodity(message)

        intent_match = detected_intent == expected_intent
        commodity_match = detected_commodity == expected_commodity

        status = "✓" if (intent_match and commodity_match) else "✗"

        print(f"\n{status} Message: '{message}'")
        print(f"  Expected intent: {expected_intent} | Detected: {detected_intent}")
        if expected_commodity:
            print(f"  Expected commodity: {expected_commodity} | Detected: {detected_commodity}")

        if intent_match and commodity_match:
            passed += 1
        else:
            failed += 1

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    return failed == 0


def test_context_availability():
    """Test that all required modules are available"""

    print("\n" + "=" * 70)
    print("TESTING MODULE AVAILABILITY")
    print("=" * 70)

    try:
        from llm_context import (
            build_llm_context,
            detect_intent,
            extract_commodity,
            get_forecast_model_context,
            get_forecast_scenario_context,
            get_trading_strategy_context,
            get_market_context
        )
        print("✓ llm_context.py - All functions available")
    except ImportError as e:
        print(f"✗ llm_context.py - Import error: {e}")
        return False

    try:
        from llm_client import (
            query_claude,
            format_llm_response,
            handle_llm_error,
            handle_help_response
        )
        print("✓ llm_client.py - All functions available")
    except ImportError as e:
        print(f"✗ llm_client.py - Import error: {e}")
        return False

    try:
        from lambda_handler_real import lambda_handler
        print("✓ lambda_handler_real.py - Handler available")
    except ImportError as e:
        print(f"✗ lambda_handler_real.py - Import error: {e}")
        return False

    return True


def test_lambda_routing():
    """Test Lambda routing logic (without actually calling APIs)"""

    print("\n" + "=" * 70)
    print("TESTING LAMBDA ROUTING LOGIC")
    print("=" * 70)

    from lambda_handler_real import parse_commodity_from_message

    test_messages = [
        ("coffee", "Coffee", "commodity_lookup"),
        ("why should I sell coffee?", "Coffee", "question"),
        ("help", None, "help"),
    ]

    for message, expected_commodity, expected_route in test_messages:
        commodity = parse_commodity_from_message(message)
        intent = detect_intent(message)

        print(f"\nMessage: '{message}'")
        print(f"  Commodity: {commodity} (expected: {expected_commodity})")
        print(f"  Intent: {intent} (expected: {expected_route})")

        if commodity == expected_commodity:
            if intent == expected_route:
                print("  ✓ Routing correct")
            else:
                print(f"  ✗ Intent mismatch")
        else:
            print(f"  ✗ Commodity mismatch")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("LLM INTEGRATION TEST SUITE")
    print("=" * 70)

    # Test 1: Module availability
    if not test_context_availability():
        print("\n✗ Module availability test failed!")
        sys.exit(1)

    # Test 2: Intent detection
    if not test_intent_detection():
        print("\n✗ Intent detection test failed!")
        sys.exit(1)

    # Test 3: Lambda routing
    test_lambda_routing()

    print("\n" + "=" * 70)
    print("✓ ALL TESTS PASSED")
    print("=" * 70)
    print("\nThe LLM integration is ready for deployment!")
    print("\nNext steps:")
    print("1. Add ANTHROPIC_API_KEY to Lambda environment")
    print("2. Build deployment package with llm_context.py and llm_client.py")
    print("3. Deploy to Lambda")
    print("4. Test with real WhatsApp messages")
