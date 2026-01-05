"""Property-based tests for StockData validation.

Feature: strategy-stock-screener, Property 8: Data Parsing Validity
Validates: Requirements 2.4
"""

from datetime import date, datetime
from hypothesis import given, strategies as st, settings
import pytest

from screener.core.models import StockData


# Custom strategies for generating valid stock data
def valid_ticker_strategy():
    """Generate valid stock tickers (1-5 uppercase letters)."""
    return st.text(
        alphabet=st.characters(whitelist_categories=('Lu',)),
        min_size=1,
        max_size=5
    )


def valid_company_name_strategy():
    """Generate valid company names."""
    return st.text(min_size=1, max_size=100).filter(lambda x: x.strip())


def valid_sector_strategy():
    """Generate valid sector names."""
    sectors = [
        "Technology", "Healthcare", "Financial", "Consumer Cyclical",
        "Industrials", "Energy", "Utilities", "Real Estate",
        "Consumer Defensive", "Communication Services", "Basic Materials"
    ]
    return st.sampled_from(sectors)


def valid_industry_strategy():
    """Generate valid industry names."""
    return st.text(min_size=1, max_size=100).filter(lambda x: x.strip())


@settings(max_examples=100)
@given(
    ticker=valid_ticker_strategy(),
    company_name=valid_company_name_strategy(),
    price=st.floats(min_value=0.01, max_value=10000, allow_nan=False, allow_infinity=False),
    volume=st.integers(min_value=0, max_value=1_000_000_000),
    avg_volume=st.integers(min_value=0, max_value=1_000_000_000),
    market_cap=st.floats(min_value=1_000_000, max_value=10_000_000_000_000, allow_nan=False, allow_infinity=False),
    rsi=st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
    sma20=st.floats(min_value=0, max_value=10000, allow_nan=False, allow_infinity=False),
    sma50=st.floats(min_value=0, max_value=10000, allow_nan=False, allow_infinity=False),
    sma200=st.floats(min_value=0, max_value=10000, allow_nan=False, allow_infinity=False),
    beta=st.floats(min_value=0, max_value=5, allow_nan=False, allow_infinity=False),
    implied_volatility=st.floats(min_value=0, max_value=10, allow_nan=False, allow_infinity=False),
    iv_rank=st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
    option_volume=st.integers(min_value=0, max_value=100_000_000),
    sector=valid_sector_strategy(),
    industry=valid_industry_strategy(),
    earnings_date=st.one_of(st.none(), st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31))),
    earnings_days_away=st.integers(min_value=0, max_value=365),
    perf_week=st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False),
    perf_month=st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False),
    perf_quarter=st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False),
)
def test_valid_stock_data_passes_validation(
    ticker, company_name, price, volume, avg_volume, market_cap,
    rsi, sma20, sma50, sma200, beta, implied_volatility, iv_rank,
    option_volume, sector, industry, earnings_date, earnings_days_away,
    perf_week, perf_month, perf_quarter
):
    """
    Feature: strategy-stock-screener, Property 8: Data Parsing Validity
    
    For any downloaded Finviz data with valid values, parsing should produce
    a valid StockData object with no validation errors.
    """
    stock = StockData(
        ticker=ticker,
        company_name=company_name,
        price=price,
        volume=volume,
        avg_volume=avg_volume,
        market_cap=market_cap,
        rsi=rsi,
        sma20=sma20,
        sma50=sma50,
        sma200=sma200,
        beta=beta,
        implied_volatility=implied_volatility,
        iv_rank=iv_rank,
        option_volume=option_volume,
        sector=sector,
        industry=industry,
        earnings_date=earnings_date,
        earnings_days_away=earnings_days_away,
        perf_week=perf_week,
        perf_month=perf_month,
        perf_quarter=perf_quarter,
    )
    
    # Valid stock data should pass validation
    errors = stock.validate()
    assert errors == [], f"Valid stock data should have no validation errors, got: {errors}"
    assert stock.is_valid(), "Valid stock data should return True for is_valid()"


@settings(max_examples=100)
@given(
    price=st.floats(max_value=0, allow_nan=False, allow_infinity=False).filter(lambda x: x <= 0),
)
def test_invalid_price_fails_validation(price):
    """
    Feature: strategy-stock-screener, Property 8: Data Parsing Validity
    
    For any stock data with invalid price (non-positive), validation should fail.
    """
    stock = StockData(
        ticker="AAPL",
        company_name="Apple Inc.",
        price=price,
        volume=1000000,
        avg_volume=1000000,
        market_cap=2_000_000_000,
        rsi=50,
        sma20=150,
        sma50=145,
        sma200=140,
        beta=1.0,
        implied_volatility=0.3,
        iv_rank=50,
        option_volume=10000,
        sector="Technology",
        industry="Consumer Electronics",
        earnings_date=None,
        earnings_days_away=30,
        perf_week=1.5,
        perf_month=3.0,
        perf_quarter=5.0,
    )
    
    errors = stock.validate()
    assert len(errors) > 0, "Invalid price should produce validation errors"
    assert any("price" in error.lower() for error in errors), "Error should mention price"
    assert not stock.is_valid(), "Invalid stock data should return False for is_valid()"


@settings(max_examples=100)
@given(
    rsi=st.floats(allow_nan=False, allow_infinity=False).filter(lambda x: x < 0 or x > 100),
)
def test_invalid_rsi_fails_validation(rsi):
    """
    Feature: strategy-stock-screener, Property 8: Data Parsing Validity
    
    For any stock data with RSI outside [0, 100], validation should fail.
    """
    stock = StockData(
        ticker="AAPL",
        company_name="Apple Inc.",
        price=150,
        volume=1000000,
        avg_volume=1000000,
        market_cap=2_000_000_000,
        rsi=rsi,
        sma20=150,
        sma50=145,
        sma200=140,
        beta=1.0,
        implied_volatility=0.3,
        iv_rank=50,
        option_volume=10000,
        sector="Technology",
        industry="Consumer Electronics",
        earnings_date=None,
        earnings_days_away=30,
        perf_week=1.5,
        perf_month=3.0,
        perf_quarter=5.0,
    )
    
    errors = stock.validate()
    assert len(errors) > 0, "Invalid RSI should produce validation errors"
    assert any("rsi" in error.lower() for error in errors), "Error should mention RSI"
    assert not stock.is_valid(), "Invalid stock data should return False for is_valid()"


@settings(max_examples=100)
@given(
    iv_rank=st.floats(allow_nan=False, allow_infinity=False).filter(lambda x: x < 0 or x > 100),
)
def test_invalid_iv_rank_fails_validation(iv_rank):
    """
    Feature: strategy-stock-screener, Property 8: Data Parsing Validity
    
    For any stock data with IV rank outside [0, 100], validation should fail.
    """
    stock = StockData(
        ticker="AAPL",
        company_name="Apple Inc.",
        price=150,
        volume=1000000,
        avg_volume=1000000,
        market_cap=2_000_000_000,
        rsi=50,
        sma20=150,
        sma50=145,
        sma200=140,
        beta=1.0,
        implied_volatility=0.3,
        iv_rank=iv_rank,
        option_volume=10000,
        sector="Technology",
        industry="Consumer Electronics",
        earnings_date=None,
        earnings_days_away=30,
        perf_week=1.5,
        perf_month=3.0,
        perf_quarter=5.0,
    )
    
    errors = stock.validate()
    assert len(errors) > 0, "Invalid IV rank should produce validation errors"
    assert any("iv_rank" in error.lower() for error in errors), "Error should mention iv_rank"
    assert not stock.is_valid(), "Invalid stock data should return False for is_valid()"
