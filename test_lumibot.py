#!/usr/bin/env python3
"""
Test script to verify Lumibot integration with Tradier.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("=" * 70)
print("LUMIBOT + TRADIER INTEGRATION TEST")
print("=" * 70)
print()

# Check if Lumibot is installed
try:
    import lumibot

    print("✓ Lumibot is installed")
    print(f"  Version: {lumibot.__version__ if hasattr(lumibot, '__version__') else 'unknown'}")
except ImportError:
    print("✗ Lumibot is NOT installed")
    print("  Run: pip install lumibot")
    exit(1)

# Check if Tradier broker is available
try:
    from lumibot.brokers import Tradier

    print("✓ Lumibot Tradier broker is available")
except ImportError:
    print("✗ Lumibot Tradier broker is NOT available")
    exit(1)

# Check environment variables
api_token = os.getenv("TRADIER_API_TOKEN")
account_id = os.getenv("TRADIER_ACCOUNT_ID")

print()
print("Environment Variables:")
if api_token:
    print(f"✓ TRADIER_API_TOKEN is set ({api_token[:10]}...)")
else:
    print("✗ TRADIER_API_TOKEN is NOT set")

if account_id:
    print(f"✓ TRADIER_ACCOUNT_ID is set ({account_id})")
else:
    print("✗ TRADIER_ACCOUNT_ID is NOT set")

if not api_token or not account_id:
    print()
    print("Please set credentials in .env file:")
    print("  TRADIER_API_TOKEN=your_token")
    print("  TRADIER_ACCOUNT_ID=your_account_id")
    exit(1)

# Test Lumibot Tradier broker initialization
print()
print("Testing Lumibot Tradier Broker:")
try:
    broker = Tradier(access_token=api_token, account_number=account_id, paper=True)  # Use sandbox
    print("✓ Lumibot Tradier broker initialized successfully")
    print(f"  Broker class: {broker.__class__.__name__}")
    print(f"  Broker module: {broker.__class__.__module__}")
except Exception as e:
    print(f"✗ Failed to initialize broker: {str(e)}")
    exit(1)

# Test authentication
print()
print("Testing Authentication:")
try:
    # Lumibot broker is authenticated if it can check market status
    is_open = broker.is_market_open()
    print(f"✓ Authentication successful!")
    print(f"  Market is: {'OPEN' if is_open else 'CLOSED'}")
except Exception as e:
    print(f"✗ Authentication failed: {str(e)}")
    exit(1)

# Market status already tested above during authentication

# Test getting a quote
print()
print("Testing Market Data:")
try:
    from lumibot.entities import Asset

    asset = Asset(symbol="AAPL", asset_type="stock")
    price = broker.get_last_price(asset)
    if price:
        print(f"✓ Market data retrieval successful")
        print(f"  AAPL price: ${price:.2f}")
    else:
        print("✗ Could not retrieve price")
except Exception as e:
    print(f"✗ Market data retrieval failed: {str(e)}")

# Test our custom client
print()
print("Testing Custom LumibotTradierClient:")
try:
    from src.tradier.lumibot_client import LumibotTradierClient
    from src.logging.bot_logger import BotLogger
    from src.config.models import LoggingConfig

    # Create logger
    logging_config = LoggingConfig(level="INFO", file_path="logs/test.log")
    logger = BotLogger(logging_config)

    # Create client
    client = LumibotTradierClient(
        api_token=api_token,
        account_id=account_id,
        base_url="https://sandbox.tradier.com",
        logger=logger,
    )

    print("✓ LumibotTradierClient initialized")

    # Test authentication
    if client.authenticate():
        print("✓ LumibotTradierClient authentication successful")

        # Get framework info
        info = client.get_framework_info()
        print(f"  Framework: {info['framework']}")
        print(f"  Broker: {info['broker']}")
        print(f"  Broker Class: {info['broker_class']}")
    else:
        print("✗ LumibotTradierClient authentication failed")

except Exception as e:
    print(f"✗ LumibotTradierClient test failed: {str(e)}")
    import traceback

    traceback.print_exc()

print()
print("=" * 70)
print("TEST COMPLETE")
print("=" * 70)
print()
print("If all tests passed, Lumibot is properly integrated!")
print("You can now run: python main.py --dry-run --once")
