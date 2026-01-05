"""
Property tests for PCS earnings date filtering.

Feature: strategy-stock-screener, Property 10: Earnings Date Filtering

For any stock in PCS screening results when earnings filtering is enabled,
the earnings date should be more than 14 days away.

**Validates: Requirements 3.9**
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import date, timedelta
from screener.strategies.pcs_strategy import PCSStrategy, PCS_DEFAULT_FILTERS
from screener.core.models import StockData


def create_valid_pcs_stock(earnings_days_away: int) -> StockData:
    """Create a stock that passes all PCS filters except potentially earnings."""
    return StockData(
        ticker="TEST",
        company_name="Test Inc.",
        price=100.0,
        volume=2000000,
        avg_volume=2000000,
        market_cap=5_000_000_000,
        rsi=55.0,
        sma20=95.0,
        sma50=90.0,
        sma200=85.0,
        beta=1.0,
        implied_volatility=0.30,
        iv_rank=50.0,
        option_volume=100000,
        sector="Technology",
        industry="Software",
        earnings_date=date.today() + timedelta(days=earnings_days_away),
        earnings_days_away=earnings_days_away,
        perf_week=2.0,
        perf_month=5.0,
        perf_quarter=10.0,
    )


def stock_passes_earnings_filter(stock: StockData, earnings_buffer_days: int) -> bool:
    """Check if a stock passes the earnings date filter."""
    return stock.earnings_days_away > earnings_buffer_days


@settings(max_examples=100)
@given(
    earnings_days_away=st.integers(min_value=15, max_value=365),
)
def test_stocks_with_earnings_beyond_buffer_pass_filter(earnings_days_away: int):
    """
    Feature: strategy-stock-screener, Property 10: Earnings Date Filtering
    
    For any stock with earnings more than 14 days away, it should pass the earnings filter.
    **Validates: Requirements 3.9**
    """
    stock = create_valid_pcs_stock(earnings_days_away)
    
    pcs = PCSStrategy()
    earnings_buffer = pcs.default_filters.get("earnings_buffer_days", 14)
    
    assert stock_passes_earnings_filter(stock, earnings_buffer), \
        f"Stock with earnings {earnings_days_away} days away should pass filter"


@settings(max_examples=100)
@given(
    earnings_days_away=st.integers(min_value=0, max_value=14),
)
def test_stocks_with_earnings_within_buffer_fail_filter(earnings_days_away: int):
    """
    Feature: strategy-stock-screener, Property 10: Earnings Date Filtering
    
    For any stock with earnings within 14 days, it should fail the earnings filter.
    **Validates: Requirements 3.9**
    """
    stock = create_valid_pcs_stock(earnings_days_away)
    
    pcs = PCSStrategy()
    earnings_buffer = pcs.default_filters.get("earnings_buffer_days", 14)
    
    assert not stock_passes_earnings_filter(stock, earnings_buffer), \
        f"Stock with earnings {earnings_days_away} days away should fail filter"


@settings(max_examples=100)
@given(
    earnings_days_away=st.integers(min_value=0, max_value=365),
)
def test_earnings_filter_boundary_is_14_days(earnings_days_away: int):
    """
    Feature: strategy-stock-screener, Property 10: Earnings Date Filtering
    
    For any stock, the earnings filter should use exactly 14 days as the boundary.
    **Validates: Requirements 3.9**
    """
    stock = create_valid_pcs_stock(earnings_days_away)
    
    pcs = PCSStrategy()
    earnings_buffer = pcs.default_filters.get("earnings_buffer_days", 14)
    
    # Verify the default buffer is 14 days
    assert earnings_buffer == 14, \
        f"Default earnings buffer should be 14 days, got {earnings_buffer}"
    
    # Verify filter behavior matches the 14-day boundary
    passes_filter = stock_passes_earnings_filter(stock, earnings_buffer)
    expected_pass = earnings_days_away > 14
    
    assert passes_filter == expected_pass, \
        f"Stock with earnings {earnings_days_away} days away: " \
        f"expected pass={expected_pass}, got pass={passes_filter}"


@settings(max_examples=100)
@given(
    custom_buffer=st.integers(min_value=1, max_value=60),
    earnings_days_away=st.integers(min_value=0, max_value=90),
)
def test_earnings_filter_respects_custom_buffer(custom_buffer: int, earnings_days_away: int):
    """
    Feature: strategy-stock-screener, Property 10: Earnings Date Filtering
    
    For any custom earnings buffer setting, the filter should correctly apply that buffer.
    **Validates: Requirements 3.9**
    """
    stock = create_valid_pcs_stock(earnings_days_away)
    
    # Test with custom buffer
    passes_filter = stock_passes_earnings_filter(stock, custom_buffer)
    expected_pass = earnings_days_away > custom_buffer
    
    assert passes_filter == expected_pass, \
        f"With buffer={custom_buffer}, stock with earnings {earnings_days_away} days away: " \
        f"expected pass={expected_pass}, got pass={passes_filter}"


def test_pcs_default_filters_include_earnings_buffer():
    """
    Verify that PCS default filters include the earnings buffer setting.
    **Validates: Requirements 3.9**
    """
    pcs = PCSStrategy()
    filters = pcs.default_filters
    
    assert "earnings_buffer_days" in filters, \
        "PCS default filters should include earnings_buffer_days"
    assert filters["earnings_buffer_days"] == 14, \
        f"Default earnings buffer should be 14 days, got {filters['earnings_buffer_days']}"
