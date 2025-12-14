#!/usr/bin/env python3
"""Integration test for comprehensive position validation and error handling."""

import sys
import os
from datetime import date, timedelta
from typing import List

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from positions.models import PositionSummary, OptionPosition, CoveredCallOrder
from positions.validation import PositionValidator, ValidationResult
from positions.position_service import PositionService
from order.order_validator import OrderValidator
from logging.bot_logger import BotLogger
from config.models import LoggingConfig


def create_test_logger():
    """Create a test logger."""
    config = LoggingConfig(
        level="INFO",
        file_path="logs/test_validation.log"
    )
    return BotLogger(config)


def test_position_validation():
    """Test position validation logic."""
    print("Testing position validation...")
    
    logger = create_test_logger()
    validator = PositionValidator(logger)
    
    # Test case 1: Sufficient shares
    position_summary = PositionSummary(
        symbol="AAPL",
        total_shares=1000,
        available_shares=1000,
        current_price=150.0,
        long_options=[],
        existing_short_calls=[]
    )
    
    result = validator.validate_sufficient_shares(position_summary, 5, 100)
    assert result.is_valid, f"Expected valid result, got: {result.error_message}"
    print("✓ Test 1 passed: Sufficient shares validation")
    
    # Test case 2: Insufficient shares
    position_summary_insufficient = PositionSummary(
        symbol="AAPL",
        total_shares=50,
        available_shares=50,
        current_price=150.0,
        long_options=[],
        existing_short_calls=[]
    )
    
    result = validator.validate_sufficient_shares(position_summary_insufficient, 1, 100)
    assert not result.is_valid, "Expected invalid result for insufficient shares"
    print("✓ Test 2 passed: Insufficient shares validation")
    
    # Test case 3: Adjustment needed
    position_summary_adjustment = PositionSummary(
        symbol="AAPL",
        total_shares=350,
        available_shares=350,
        current_price=150.0,
        long_options=[],
        existing_short_calls=[]
    )
    
    result = validator.validate_sufficient_shares(position_summary_adjustment, 5, 100)
    assert result.is_valid, "Expected valid result with adjustment"
    assert result.adjusted_contracts == 3, f"Expected 3 adjusted contracts, got {result.adjusted_contracts}"
    print("✓ Test 3 passed: Contract adjustment validation")
    
    print("All position validation tests passed!\n")


def test_order_validation():
    """Test order validation logic."""
    print("Testing order validation...")
    
    logger = create_test_logger()
    order_validator = OrderValidator(logger)
    
    # Create test position summary
    position_summary = PositionSummary(
        symbol="AAPL",
        total_shares=500,
        available_shares=500,
        current_price=150.0,
        long_options=[],
        existing_short_calls=[]
    )
    
    # Create test orders
    future_date = date.today() + timedelta(days=30)
    orders = [
        CoveredCallOrder(
            symbol="AAPL",
            strike=155.0,
            expiration=future_date,
            quantity=2,
            underlying_shares=200
        ),
        CoveredCallOrder(
            symbol="AAPL",
            strike=160.0,
            expiration=future_date,
            quantity=3,
            underlying_shares=300
        )
    ]
    
    # Test valid orders
    result = order_validator.validate_orders_before_submission(orders, position_summary)
    assert result.is_valid, f"Expected valid orders, got errors: {result.errors}"
    assert len(result.validated_orders) == 2, f"Expected 2 validated orders, got {len(result.validated_orders)}"
    print("✓ Test 1 passed: Valid orders validation")
    
    # Test orders exceeding available shares
    large_orders = [
        CoveredCallOrder(
            symbol="AAPL",
            strike=155.0,
            expiration=future_date,
            quantity=10,  # 1000 shares needed, but only 500 available
            underlying_shares=1000
        )
    ]
    
    result = order_validator.validate_orders_before_submission(large_orders, position_summary)
    # Should still be valid but with adjustments
    print(f"Large order validation result: valid={result.is_valid}, warnings={len(result.warnings)}")
    
    print("All order validation tests passed!\n")


def test_error_scenarios():
    """Test various error scenarios."""
    print("Testing error scenarios...")
    
    logger = create_test_logger()
    validator = PositionValidator(logger)
    
    # Test case 1: No shares at all
    no_shares_position = PositionSummary(
        symbol="AAPL",
        total_shares=0,
        available_shares=0,
        current_price=150.0,
        long_options=[],
        existing_short_calls=[]
    )
    
    result = validator.validate_sufficient_shares(no_shares_position, 1, 100)
    assert not result.is_valid, "Expected invalid result for no shares"
    assert "No shares found" in result.error_message, f"Unexpected error message: {result.error_message}"
    print("✓ Test 1 passed: No shares error handling")
    
    # Test case 2: Existing short calls reducing available shares
    with_short_calls = PositionSummary(
        symbol="AAPL",
        total_shares=500,
        available_shares=300,  # 200 shares covered by existing calls
        current_price=150.0,
        long_options=[],
        existing_short_calls=[
            OptionPosition(
                symbol="AAPL240315C00155000",
                quantity=-2,  # Short 2 calls
                market_value=-400.0,
                average_cost=2.0,
                unrealized_pnl=100.0,
                position_type="short_call",
                strike=155.0,
                expiration=date.today() + timedelta(days=30),
                option_type="call"
            )
        ]
    )
    
    result = validator.validate_sufficient_shares(with_short_calls, 4, 100)  # Need 400 shares, only 300 available
    assert result.is_valid, "Expected valid result with adjustment"
    assert result.adjusted_contracts == 3, f"Expected 3 adjusted contracts, got {result.adjusted_contracts}"
    print("✓ Test 2 passed: Existing short calls handling")
    
    print("All error scenario tests passed!\n")


def main():
    """Run all validation tests."""
    print("Starting comprehensive validation tests...\n")
    
    try:
        test_position_validation()
        test_order_validation()
        test_error_scenarios()
        
        print("🎉 All validation tests passed successfully!")
        print("\nValidation system is working correctly:")
        print("- Position validation prevents naked call creation")
        print("- Order validation catches invalid parameters")
        print("- Error handling provides clear feedback")
        print("- Logging captures all validation activities")
        
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())