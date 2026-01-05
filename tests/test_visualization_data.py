"""Property-based tests for visualization data generation.

Feature: strategy-stock-screener, Property 13: Visualization Data Generation
Validates: Requirements 4.5
"""

import numpy as np
import pandas as pd
from hypothesis import given, strategies as st, settings
import pytest

from screener.analysis.engine import (
    generate_price_chart_data,
    generate_iv_history_chart_data
)


@settings(max_examples=100)
@given(
    price_history_size=st.integers(min_value=20, max_value=252),
    current_price=st.floats(min_value=10, max_value=500, allow_nan=False, allow_infinity=False),
    num_support_levels=st.integers(min_value=0, max_value=10),
)
def test_price_chart_data_generation(price_history_size, current_price, num_support_levels):
    """
    Feature: strategy-stock-screener, Property 13: Visualization Data Generation
    
    For any completed analysis, the result should include chart data for price history
    with support levels.
    """
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
    
    # Generate support levels
    support_levels = [current_price * (1 - i * 0.05) for i in range(num_support_levels)]
    
    # Generate chart data
    chart_data = generate_price_chart_data(price_history, support_levels)
    
    # Verify chart data completeness
    assert chart_data is not None, "Chart data should be generated"
    assert isinstance(chart_data, dict), "Chart data should be a dictionary"
    
    # Required fields
    required_fields = ['dates', 'prices', 'lows', 'highs', 'support_levels']
    for field in required_fields:
        assert field in chart_data, f"Chart data should include '{field}'"
    
    # Verify data consistency
    assert len(chart_data['dates']) == price_history_size, \
        "Dates should match price history size"
    assert len(chart_data['prices']) == price_history_size, \
        "Prices should match price history size"
    assert len(chart_data['lows']) == price_history_size, \
        "Lows should match price history size"
    assert len(chart_data['highs']) == price_history_size, \
        "Highs should match price history size"
    
    # Verify support levels are included
    assert chart_data['support_levels'] == support_levels, \
        "Support levels should be included in chart data"
    
    # Verify moving averages are included
    assert 'sma20' in chart_data, "Chart data should include SMA20"
    assert 'sma50' in chart_data, "Chart data should include SMA50"
    assert 'sma200' in chart_data, "Chart data should include SMA200"
    
    assert len(chart_data['sma20']) == price_history_size, \
        "SMA20 should match price history size"
    assert len(chart_data['sma50']) == price_history_size, \
        "SMA50 should match price history size"
    assert len(chart_data['sma200']) == price_history_size, \
        "SMA200 should match price history size"


@settings(max_examples=100)
@given(
    iv_history_size=st.integers(min_value=10, max_value=252),
    current_iv=st.floats(min_value=0.1, max_value=2.0, allow_nan=False, allow_infinity=False),
)
def test_iv_history_chart_data_generation(iv_history_size, current_iv):
    """
    Feature: strategy-stock-screener, Property 13: Visualization Data Generation
    
    For any completed analysis, the result should include chart data for IV history.
    """
    # Generate IV history
    iv_low = current_iv * 0.7
    iv_high = current_iv * 1.3
    iv_history = pd.Series(np.random.uniform(iv_low, iv_high, iv_history_size))
    
    # Generate chart data
    chart_data = generate_iv_history_chart_data(iv_history, current_iv)
    
    # Verify chart data completeness
    assert chart_data is not None, "IV chart data should be generated"
    assert isinstance(chart_data, dict), "IV chart data should be a dictionary"
    
    # Required fields
    required_fields = ['dates', 'iv_values', 'current_iv', 'iv_low', 'iv_high', 'iv_mean']
    for field in required_fields:
        assert field in chart_data, f"IV chart data should include '{field}'"
    
    # Verify data consistency
    assert len(chart_data['dates']) == iv_history_size, \
        "Dates should match IV history size"
    assert len(chart_data['iv_values']) == iv_history_size, \
        "IV values should match IV history size"
    
    # Verify current IV
    assert chart_data['current_iv'] == current_iv, \
        "Current IV should be included"
    
    # Verify statistics
    assert chart_data['iv_low'] == iv_history.min(), \
        "IV low should match minimum of history"
    assert chart_data['iv_high'] == iv_history.max(), \
        "IV high should match maximum of history"
    assert abs(chart_data['iv_mean'] - iv_history.mean()) < 0.01, \
        "IV mean should match average of history"


@settings(max_examples=100)
@given(
    price_history_size=st.integers(min_value=20, max_value=252),
    iv_history_size=st.integers(min_value=10, max_value=252),
    current_price=st.floats(min_value=10, max_value=500, allow_nan=False, allow_infinity=False),
    current_iv=st.floats(min_value=0.1, max_value=2.0, allow_nan=False, allow_infinity=False),
)
def test_complete_visualization_data_generation(
    price_history_size, iv_history_size, current_price, current_iv
):
    """
    Feature: strategy-stock-screener, Property 13: Visualization Data Generation
    
    For any completed analysis, both price chart data and IV history chart data
    should be generated successfully.
    """
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
    
    # Generate IV history
    iv_low = current_iv * 0.7
    iv_high = current_iv * 1.3
    iv_history = pd.Series(np.random.uniform(iv_low, iv_high, iv_history_size))
    
    # Generate support levels
    support_levels = [current_price * 0.95, current_price * 0.90, current_price * 0.85]
    
    # Generate both chart data types
    price_chart = generate_price_chart_data(price_history, support_levels)
    iv_chart = generate_iv_history_chart_data(iv_history, current_iv)
    
    # Verify both are generated successfully
    assert price_chart is not None and isinstance(price_chart, dict), \
        "Price chart data should be generated"
    assert iv_chart is not None and isinstance(iv_chart, dict), \
        "IV chart data should be generated"
    
    # Verify both have required structure
    assert 'dates' in price_chart and 'prices' in price_chart, \
        "Price chart should have dates and prices"
    assert 'dates' in iv_chart and 'iv_values' in iv_chart, \
        "IV chart should have dates and IV values"
    
    # Verify support levels are in price chart
    assert 'support_levels' in price_chart, \
        "Price chart should include support levels"
    assert price_chart['support_levels'] == support_levels, \
        "Support levels should match input"


def test_empty_price_history_handled_gracefully():
    """
    Feature: strategy-stock-screener, Property 13: Visualization Data Generation
    
    For empty price history, chart data generation should handle it gracefully
    and return valid structure.
    """
    empty_df = pd.DataFrame()
    support_levels = [100.0, 95.0, 90.0]
    
    chart_data = generate_price_chart_data(empty_df, support_levels)
    
    # Should return valid structure even with empty data
    assert chart_data is not None, "Chart data should be generated even for empty history"
    assert isinstance(chart_data, dict), "Chart data should be a dictionary"
    assert 'dates' in chart_data and len(chart_data['dates']) == 0, \
        "Empty history should result in empty dates"
    assert 'support_levels' in chart_data, "Support levels should still be included"
    assert chart_data['support_levels'] == support_levels, \
        "Support levels should match input"


def test_empty_iv_history_handled_gracefully():
    """
    Feature: strategy-stock-screener, Property 13: Visualization Data Generation
    
    For empty IV history, chart data generation should handle it gracefully
    and return valid structure.
    """
    empty_series = pd.Series([])
    current_iv = 0.5
    
    chart_data = generate_iv_history_chart_data(empty_series, current_iv)
    
    # Should return valid structure even with empty data
    assert chart_data is not None, "IV chart data should be generated even for empty history"
    assert isinstance(chart_data, dict), "IV chart data should be a dictionary"
    assert 'dates' in chart_data and len(chart_data['dates']) == 0, \
        "Empty history should result in empty dates"
    assert chart_data['current_iv'] == current_iv, \
        "Current IV should still be included"
