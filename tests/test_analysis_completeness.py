"""Property-based tests for analysis engine completeness.

Feature: strategy-stock-screener, Property 12: Analysis Completeness
Validates: Requirements 4.1, 4.2, 4.3, 4.4
"""

import numpy as np
import pandas as pd
from hypothesis import given, strategies as st, settings, assume
import pytest

from screener.analysis.engine import (
    calculate_iv_rank,
    identify_support_levels,
    estimate_pop_for_pcs,
    estimate_pcs_premium
)


@settings(max_examples=100)
@given(
    current_iv=st.floats(min_value=0.01, max_value=5.0, allow_nan=False, allow_infinity=False),
    iv_history_size=st.integers(min_value=10, max_value=252),  # 10 days to 1 year
)
def test_iv_rank_calculation_completeness(current_iv, iv_history_size):
    """
    Feature: strategy-stock-screener, Property 12: Analysis Completeness
    
    For any analyzed stock, the analysis result should include IV rank.
    IV rank should be between 0 and 100.
    """
    # Generate random IV history
    iv_low = current_iv * np.random.uniform(0.5, 0.9)
    iv_high = current_iv * np.random.uniform(1.1, 2.0)
    iv_history = pd.Series(np.random.uniform(iv_low, iv_high, iv_history_size))
    
    # Calculate IV rank
    iv_rank = calculate_iv_rank(current_iv, iv_history)
    
    # Verify completeness: IV rank should be present and valid
    assert iv_rank is not None, "IV rank should be calculated"
    assert isinstance(iv_rank, (int, float)), "IV rank should be numeric"
    assert 0 <= iv_rank <= 100, f"IV rank should be between 0 and 100, got {iv_rank}"


@settings(max_examples=100)
@given(
    price_history_size=st.integers(min_value=20, max_value=252),
    current_price=st.floats(min_value=10, max_value=500, allow_nan=False, allow_infinity=False),
)
def test_support_levels_identification_completeness(price_history_size, current_price):
    """
    Feature: strategy-stock-screener, Property 12: Analysis Completeness
    
    For any analyzed stock, the analysis result should include support levels.
    Support levels should be a list of numeric values.
    """
    # Generate price history with SMAs
    prices = current_price * (1 + np.random.uniform(-0.2, 0.2, price_history_size))
    lows = prices * np.random.uniform(0.95, 1.0, price_history_size)
    highs = prices * np.random.uniform(1.0, 1.05, price_history_size)
    
    price_history = pd.DataFrame({
        'close': prices,
        'low': lows,
        'high': highs,
        'sma20': prices * 0.98,
        'sma50': prices * 0.96,
        'sma200': prices * 0.94,
    })
    
    # Identify support levels
    support_levels = identify_support_levels(price_history)
    
    # Verify completeness: support levels should be present
    assert support_levels is not None, "Support levels should be calculated"
    assert isinstance(support_levels, list), "Support levels should be a list"
    
    # All support levels should be numeric and positive
    for level in support_levels:
        assert isinstance(level, (int, float)), f"Support level should be numeric, got {type(level)}"
        assert level > 0, f"Support level should be positive, got {level}"
    
    # Support levels should be sorted in descending order
    if len(support_levels) > 1:
        for i in range(len(support_levels) - 1):
            assert support_levels[i] >= support_levels[i + 1], \
                "Support levels should be sorted in descending order"


@settings(max_examples=100)
@given(
    current_price=st.floats(min_value=20, max_value=500, allow_nan=False, allow_infinity=False),
    strike_offset=st.floats(min_value=0.05, max_value=0.20),  # 5-20% below current price
    days_to_expiration=st.integers(min_value=1, max_value=90),
    implied_volatility=st.floats(min_value=0.1, max_value=2.0, allow_nan=False, allow_infinity=False),
)
def test_probability_of_profit_completeness(current_price, strike_offset, days_to_expiration, implied_volatility):
    """
    Feature: strategy-stock-screener, Property 12: Analysis Completeness
    
    For any analyzed stock, the analysis result should include probability of profit.
    POP should be between 0 and 100.
    """
    short_strike = current_price * (1 - strike_offset)
    
    # Calculate POP
    pop = estimate_pop_for_pcs(current_price, short_strike, days_to_expiration, implied_volatility)
    
    # Verify completeness: POP should be present and valid
    assert pop is not None, "Probability of profit should be calculated"
    assert isinstance(pop, (int, float)), "POP should be numeric"
    assert 0 <= pop <= 100, f"POP should be between 0 and 100, got {pop}"


@settings(max_examples=100)
@given(
    current_price=st.floats(min_value=20, max_value=500, allow_nan=False, allow_infinity=False),
    short_strike_offset=st.floats(min_value=0.05, max_value=0.15),  # 5-15% below
    spread_width=st.floats(min_value=2, max_value=10),  # $2-$10 wide
    days_to_expiration=st.integers(min_value=1, max_value=90),
    implied_volatility=st.floats(min_value=0.1, max_value=2.0, allow_nan=False, allow_infinity=False),
)
def test_premium_estimation_completeness(
    current_price, short_strike_offset, spread_width, days_to_expiration, implied_volatility
):
    """
    Feature: strategy-stock-screener, Property 12: Analysis Completeness
    
    For any analyzed stock, the analysis result should include premium estimate.
    Premium estimate should include credit, max_risk, and return_on_risk.
    """
    short_strike = current_price * (1 - short_strike_offset)
    long_strike = short_strike - spread_width
    
    assume(long_strike > 0)  # Ensure valid strike prices
    
    # Calculate premium
    premium_data = estimate_pcs_premium(
        current_price, short_strike, long_strike, days_to_expiration, implied_volatility
    )
    
    # Verify completeness: all required fields should be present
    assert premium_data is not None, "Premium estimate should be calculated"
    assert isinstance(premium_data, dict), "Premium estimate should be a dictionary"
    
    required_fields = ['credit', 'max_risk', 'return_on_risk']
    for field in required_fields:
        assert field in premium_data, f"Premium estimate should include '{field}'"
        assert isinstance(premium_data[field], (int, float)), \
            f"Premium estimate '{field}' should be numeric"
        assert premium_data[field] >= 0, \
            f"Premium estimate '{field}' should be non-negative, got {premium_data[field]}"


@settings(max_examples=100)
@given(
    current_price=st.floats(min_value=20, max_value=500, allow_nan=False, allow_infinity=False),
    short_strike_offset=st.floats(min_value=0.05, max_value=0.15),
    spread_width=st.floats(min_value=2, max_value=10),
    days_to_expiration=st.integers(min_value=1, max_value=90),
    implied_volatility=st.floats(min_value=0.1, max_value=2.0, allow_nan=False, allow_infinity=False),
    iv_history_size=st.integers(min_value=10, max_value=252),
    price_history_size=st.integers(min_value=20, max_value=252),
)
def test_complete_analysis_includes_all_components(
    current_price, short_strike_offset, spread_width, days_to_expiration,
    implied_volatility, iv_history_size, price_history_size
):
    """
    Feature: strategy-stock-screener, Property 12: Analysis Completeness
    
    For any analyzed stock, the complete analysis should include:
    - IV rank (Requirement 4.1)
    - Support levels (Requirement 4.2)
    - Probability of profit (Requirement 4.3)
    - Premium estimate (Requirement 4.4)
    """
    # Setup strikes
    short_strike = current_price * (1 - short_strike_offset)
    long_strike = short_strike - spread_width
    
    assume(long_strike > 0)
    
    # Generate IV history
    iv_low = implied_volatility * 0.7
    iv_high = implied_volatility * 1.3
    iv_history = pd.Series(np.random.uniform(iv_low, iv_high, iv_history_size))
    
    # Generate price history
    prices = current_price * (1 + np.random.uniform(-0.2, 0.2, price_history_size))
    lows = prices * np.random.uniform(0.95, 1.0, price_history_size)
    highs = prices * np.random.uniform(1.0, 1.05, price_history_size)
    
    price_history = pd.DataFrame({
        'close': prices,
        'low': lows,
        'high': highs,
        'sma20': prices * 0.98,
        'sma50': prices * 0.96,
        'sma200': prices * 0.94,
    })
    
    # Perform complete analysis
    iv_rank = calculate_iv_rank(implied_volatility, iv_history)
    support_levels = identify_support_levels(price_history)
    pop = estimate_pop_for_pcs(current_price, short_strike, days_to_expiration, implied_volatility)
    premium = estimate_pcs_premium(
        current_price, short_strike, long_strike, days_to_expiration, implied_volatility
    )
    
    # Verify all components are present and valid
    assert iv_rank is not None and 0 <= iv_rank <= 100, "IV rank should be valid"
    assert support_levels is not None and isinstance(support_levels, list), "Support levels should be valid"
    assert pop is not None and 0 <= pop <= 100, "POP should be valid"
    assert premium is not None and isinstance(premium, dict), "Premium should be valid"
    assert all(k in premium for k in ['credit', 'max_risk', 'return_on_risk']), \
        "Premium should have all required fields"
