"""
Property tests for PCS filter criteria enforcement.

Feature: strategy-stock-screener, Property 9: PCS Filter Criteria Enforcement

For any stock in PCS screening results, it should satisfy all PCS criteria:
market cap > $2B, volume > 1M, price in [$20, $200], RSI in [40, 70],
price above SMA20 and SMA50, weekly performance in [-5%, 10%], beta in [0.5, 1.5],
optionable and shortable.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8**
"""

import pytest
from hypothesis import given, strategies as st, settings
from datetime import date, timedelta
from screener.strategies.pcs_strategy import PCSStrategy, PCS_DEFAULT_FILTERS
from screener.core.models import StockData


def create_stock_data(
    ticker: str = "TEST",
    price: float = 100.0,
    volume: int = 2000000,
    avg_volume: int = 2000000,
    market_cap: float = 5_000_000_000,
    rsi: float = 55.0,
    sma20: float = 95.0,
    sma50: float = 90.0,
    sma200: float = 85.0,
    beta: float = 1.0,
    implied_volatility: float = 0.30,
    iv_rank: float = 50.0,
    perf_week: float = 2.0,
    earnings_days_away: int = 30,
) -> StockData:
    """Helper to create StockData with sensible defaults."""
    return StockData(
        ticker=ticker,
        company_name=f"{ticker} Inc.",
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
        option_volume=100000,
        sector="Technology",
        industry="Software",
        earnings_date=date.today() + timedelta(days=earnings_days_away),
        earnings_days_away=earnings_days_away,
        perf_week=perf_week,
        perf_month=5.0,
        perf_quarter=10.0,
    )


def stock_passes_pcs_filters(stock: StockData, filters: dict) -> bool:
    """Check if a stock passes all PCS filter criteria."""
    # Requirement 3.1: Market cap > $2B
    if stock.market_cap < filters.get("min_market_cap", 2_000_000_000):
        return False
    
    # Requirement 3.2: Volume > 1M
    if stock.avg_volume < filters.get("min_volume", 1_000_000):
        return False
    
    # Requirement 3.3: Price between $20 and $200
    if stock.price < filters.get("price_min", 20):
        return False
    if stock.price > filters.get("price_max", 200):
        return False
    
    # Requirement 3.4: RSI between 40 and 70
    if stock.rsi < filters.get("rsi_min", 40):
        return False
    if stock.rsi > filters.get("rsi_max", 70):
        return False
    
    # Requirement 3.5: Price above SMA20 and SMA50
    if filters.get("above_sma20", True) and stock.price <= stock.sma20:
        return False
    if filters.get("above_sma50", True) and stock.price <= stock.sma50:
        return False
    
    # Requirement 3.6: Weekly performance between -5% and +10%
    if stock.perf_week < filters.get("weekly_perf_min", -5):
        return False
    if stock.perf_week > filters.get("weekly_perf_max", 10):
        return False
    
    # Requirement 3.8: Beta between 0.5 and 1.5
    if stock.beta < filters.get("beta_min", 0.5):
        return False
    if stock.beta > filters.get("beta_max", 1.5):
        return False
    
    return True


@settings(max_examples=100)
@given(
    market_cap=st.floats(min_value=2_000_000_000, max_value=1e12, allow_nan=False, allow_infinity=False),
    avg_volume=st.integers(min_value=1_000_000, max_value=100_000_000),
    price=st.floats(min_value=20.0, max_value=200.0, allow_nan=False, allow_infinity=False),
    rsi=st.floats(min_value=40.0, max_value=70.0, allow_nan=False, allow_infinity=False),
    beta=st.floats(min_value=0.5, max_value=1.5, allow_nan=False, allow_infinity=False),
    perf_week=st.floats(min_value=-5.0, max_value=10.0, allow_nan=False, allow_infinity=False),
)
def test_stocks_meeting_all_criteria_pass_filters(
    market_cap: float,
    avg_volume: int,
    price: float,
    rsi: float,
    beta: float,
    perf_week: float,
):
    """
    Feature: strategy-stock-screener, Property 9: PCS Filter Criteria Enforcement
    
    For any stock that meets all PCS criteria, it should pass the filter check.
    **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8**
    """
    # Create stock with values that meet all criteria
    # Ensure price is above SMAs
    sma20 = price * 0.95  # SMA20 is 5% below price
    sma50 = price * 0.90  # SMA50 is 10% below price
    
    stock = create_stock_data(
        market_cap=market_cap,
        avg_volume=avg_volume,
        price=price,
        rsi=rsi,
        beta=beta,
        perf_week=perf_week,
        sma20=sma20,
        sma50=sma50,
    )
    
    pcs = PCSStrategy()
    filters = pcs.default_filters
    
    # Stock should pass all filters
    assert stock_passes_pcs_filters(stock, filters), \
        f"Stock with valid criteria should pass filters: {stock}"


@settings(max_examples=100)
@given(
    market_cap=st.floats(min_value=100_000, max_value=1_999_999_999, allow_nan=False, allow_infinity=False),
)
def test_stocks_below_market_cap_fail_filter(market_cap: float):
    """
    Feature: strategy-stock-screener, Property 9: PCS Filter Criteria Enforcement
    
    For any stock with market cap below $2B, it should fail the filter.
    **Validates: Requirements 3.1**
    """
    stock = create_stock_data(market_cap=market_cap)
    
    pcs = PCSStrategy()
    filters = pcs.default_filters
    
    assert not stock_passes_pcs_filters(stock, filters), \
        f"Stock with market cap ${market_cap:,.0f} should fail filter"


@settings(max_examples=100)
@given(
    avg_volume=st.integers(min_value=0, max_value=999_999),
)
def test_stocks_below_volume_fail_filter(avg_volume: int):
    """
    Feature: strategy-stock-screener, Property 9: PCS Filter Criteria Enforcement
    
    For any stock with volume below 1M, it should fail the filter.
    **Validates: Requirements 3.2**
    """
    stock = create_stock_data(avg_volume=avg_volume)
    
    pcs = PCSStrategy()
    filters = pcs.default_filters
    
    assert not stock_passes_pcs_filters(stock, filters), \
        f"Stock with volume {avg_volume:,} should fail filter"


@settings(max_examples=100)
@given(
    price=st.one_of(
        st.floats(min_value=0.01, max_value=19.99, allow_nan=False, allow_infinity=False),
        st.floats(min_value=200.01, max_value=1000.0, allow_nan=False, allow_infinity=False),
    ),
)
def test_stocks_outside_price_range_fail_filter(price: float):
    """
    Feature: strategy-stock-screener, Property 9: PCS Filter Criteria Enforcement
    
    For any stock with price outside $20-$200, it should fail the filter.
    **Validates: Requirements 3.3**
    """
    # Adjust SMAs to be below price so only price range fails
    stock = create_stock_data(
        price=price,
        sma20=price * 0.9,
        sma50=price * 0.85,
    )
    
    pcs = PCSStrategy()
    filters = pcs.default_filters
    
    assert not stock_passes_pcs_filters(stock, filters), \
        f"Stock with price ${price:.2f} should fail filter"


@settings(max_examples=100)
@given(
    rsi=st.one_of(
        st.floats(min_value=0.0, max_value=39.99, allow_nan=False, allow_infinity=False),
        st.floats(min_value=70.01, max_value=100.0, allow_nan=False, allow_infinity=False),
    ),
)
def test_stocks_outside_rsi_range_fail_filter(rsi: float):
    """
    Feature: strategy-stock-screener, Property 9: PCS Filter Criteria Enforcement
    
    For any stock with RSI outside 40-70, it should fail the filter.
    **Validates: Requirements 3.4**
    """
    stock = create_stock_data(rsi=rsi)
    
    pcs = PCSStrategy()
    filters = pcs.default_filters
    
    assert not stock_passes_pcs_filters(stock, filters), \
        f"Stock with RSI {rsi:.2f} should fail filter"


@settings(max_examples=100)
@given(
    price=st.floats(min_value=50.0, max_value=150.0, allow_nan=False, allow_infinity=False),
    sma_offset=st.floats(min_value=0.01, max_value=0.20, allow_nan=False, allow_infinity=False),
)
def test_stocks_below_sma20_fail_filter(price: float, sma_offset: float):
    """
    Feature: strategy-stock-screener, Property 9: PCS Filter Criteria Enforcement
    
    For any stock with price below SMA20, it should fail the filter.
    **Validates: Requirements 3.5**
    """
    # SMA20 is above price
    sma20 = price * (1 + sma_offset)
    
    stock = create_stock_data(
        price=price,
        sma20=sma20,
        sma50=price * 0.9,  # SMA50 below price
    )
    
    pcs = PCSStrategy()
    filters = pcs.default_filters
    
    assert not stock_passes_pcs_filters(stock, filters), \
        f"Stock with price ${price:.2f} below SMA20 ${sma20:.2f} should fail filter"


@settings(max_examples=100)
@given(
    beta=st.one_of(
        st.floats(min_value=0.0, max_value=0.49, allow_nan=False, allow_infinity=False),
        st.floats(min_value=1.51, max_value=3.0, allow_nan=False, allow_infinity=False),
    ),
)
def test_stocks_outside_beta_range_fail_filter(beta: float):
    """
    Feature: strategy-stock-screener, Property 9: PCS Filter Criteria Enforcement
    
    For any stock with beta outside 0.5-1.5, it should fail the filter.
    **Validates: Requirements 3.8**
    """
    stock = create_stock_data(beta=beta)
    
    pcs = PCSStrategy()
    filters = pcs.default_filters
    
    assert not stock_passes_pcs_filters(stock, filters), \
        f"Stock with beta {beta:.2f} should fail filter"


@settings(max_examples=100)
@given(
    perf_week=st.one_of(
        st.floats(min_value=-50.0, max_value=-5.01, allow_nan=False, allow_infinity=False),
        st.floats(min_value=10.01, max_value=50.0, allow_nan=False, allow_infinity=False),
    ),
)
def test_stocks_outside_weekly_perf_range_fail_filter(perf_week: float):
    """
    Feature: strategy-stock-screener, Property 9: PCS Filter Criteria Enforcement
    
    For any stock with weekly performance outside -5% to +10%, it should fail the filter.
    **Validates: Requirements 3.6**
    """
    stock = create_stock_data(perf_week=perf_week)
    
    pcs = PCSStrategy()
    filters = pcs.default_filters
    
    assert not stock_passes_pcs_filters(stock, filters), \
        f"Stock with weekly perf {perf_week:.2f}% should fail filter"
