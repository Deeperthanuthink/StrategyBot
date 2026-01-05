"""Property-based tests for Finviz data completeness.

Feature: strategy-stock-screener, Property 7: Downloaded Data Completeness
Validates: Requirements 2.3
"""

from hypothesis import given, strategies as st, settings
import pytest
import pandas as pd
from datetime import date

from screener.finviz import FinvizClient, FinvizCredentials


def create_mock_finviz_row():
    """Create a mock Finviz data row with all required fields."""
    return {
        'Ticker': 'AAPL',
        'Company': 'Apple Inc.',
        'Price': '150.00',
        'Volume': '50000000',
        'Avg Volume': '60000000',
        'Market Cap': '2.5T',
        'RSI (14)': '55.5',
        'SMA20': '148.50',
        'SMA50': '145.00',
        'SMA200': '140.00',
        'Beta': '1.2',
        'Volatility': '0.35',
        'IV Rank': '60.0',
        'Option Volume': '500000',
        'Sector': 'Technology',
        'Industry': 'Consumer Electronics',
        'Earnings': 'Jan 25',
        'Perf Week': '2.5%',
        'Perf Month': '5.0%',
        'Perf Quarter': '10.0%',
    }


@settings(max_examples=100)
@given(
    ticker=st.text(alphabet=st.characters(whitelist_categories=('Lu',)), min_size=1, max_size=5),
    company=st.text(min_size=1, max_size=100).filter(lambda x: x.strip()),
    price=st.floats(min_value=0.01, max_value=10000, allow_nan=False, allow_infinity=False),
    volume=st.integers(min_value=0, max_value=1_000_000_000),
    market_cap_suffix=st.sampled_from(['M', 'B', 'T']),
    market_cap_value=st.floats(min_value=1, max_value=999, allow_nan=False, allow_infinity=False),
)
def test_parsed_data_contains_all_required_fields(
    ticker, company, price, volume, market_cap_suffix, market_cap_value
):
    """
    Feature: strategy-stock-screener, Property 7: Downloaded Data Completeness
    
    For any Finviz result set, the parsed data should include all required fields:
    price, volume, technical indicators (RSI, SMAs), and fundamental metrics
    (market cap, sector, earnings date).
    """
    credentials = FinvizCredentials(email="test@example.com", password="testpass123")
    client = FinvizClient(credentials=credentials)
    
    # Create a mock row with the generated values
    row_data = {
        'Ticker': ticker,
        'Company': company,
        'Price': str(price),
        'Volume': str(volume),
        'Avg Volume': str(volume),
        'Market Cap': f"{market_cap_value:.1f}{market_cap_suffix}",
        'RSI (14)': '55.5',
        'SMA20': str(price * 0.99),
        'SMA50': str(price * 0.97),
        'SMA200': str(price * 0.95),
        'Beta': '1.2',
        'Volatility': '0.35',
        'IV Rank': '60.0',
        'Option Volume': '500000',
        'Sector': 'Technology',
        'Industry': 'Consumer Electronics',
        'Earnings': 'Jan 25',
        'Perf Week': '2.5%',
        'Perf Month': '5.0%',
        'Perf Quarter': '10.0%',
    }
    
    row = pd.Series(row_data)
    
    # Parse the row
    stock = client._parse_single_stock(row)
    
    # Verify all required fields are present
    assert stock.ticker is not None
    assert stock.company_name is not None
    assert stock.price > 0
    assert stock.volume >= 0
    assert stock.avg_volume >= 0
    assert stock.market_cap > 0
    
    # Technical indicators
    assert 0 <= stock.rsi <= 100
    assert stock.sma20 >= 0
    assert stock.sma50 >= 0
    assert stock.sma200 >= 0
    assert stock.beta >= 0
    
    # Options data
    assert 0 <= stock.implied_volatility <= 10
    assert 0 <= stock.iv_rank <= 100
    assert stock.option_volume >= 0
    
    # Fundamental data
    assert stock.sector is not None
    assert stock.industry is not None
    assert stock.earnings_days_away >= 0
    
    # Performance metrics
    assert isinstance(stock.perf_week, float)
    assert isinstance(stock.perf_month, float)
    assert isinstance(stock.perf_quarter, float)


@settings(max_examples=100)
@given(
    num_stocks=st.integers(min_value=1, max_value=50),
)
def test_parse_multiple_stocks_all_complete(num_stocks):
    """
    Feature: strategy-stock-screener, Property 7: Downloaded Data Completeness
    
    For any Finviz result set with multiple stocks, all parsed stocks should
    have complete data.
    """
    credentials = FinvizCredentials(email="test@example.com", password="testpass123")
    client = FinvizClient(credentials=credentials)
    
    # Create a DataFrame with multiple mock stocks
    rows = []
    for i in range(num_stocks):
        row_data = create_mock_finviz_row()
        row_data['Ticker'] = f"TICK{i}"
        row_data['Company'] = f"Company {i}"
        rows.append(row_data)
    
    df = pd.DataFrame(rows)
    
    # Parse all stocks
    stocks = client.parse_stock_data(df)
    
    # Should have parsed all stocks
    assert len(stocks) == num_stocks
    
    # Each stock should have complete data
    for stock in stocks:
        assert stock.ticker is not None
        assert stock.company_name is not None
        assert stock.price > 0
        assert stock.market_cap > 0
        assert 0 <= stock.rsi <= 100
        assert stock.sector is not None
        assert stock.industry is not None


def test_missing_fields_use_safe_defaults():
    """
    Test that missing fields in Finviz data are handled with safe defaults.
    """
    credentials = FinvizCredentials(email="test@example.com", password="testpass123")
    client = FinvizClient(credentials=credentials)
    
    # Create a row with many missing fields
    row_data = {
        'Ticker': 'TEST',
        'Company': 'Test Company',
        'Price': '100.00',
        # Missing most other fields
    }
    
    row = pd.Series(row_data)
    stock = client._parse_single_stock(row)
    
    # Should have safe defaults
    assert stock.ticker == 'TEST'
    assert stock.company_name == 'Test Company'
    assert stock.price == 100.0
    assert stock.volume == 0  # Default
    assert stock.avg_volume == 0  # Default
    assert stock.market_cap > 0  # Default to 1M
    assert stock.rsi == 50.0  # Default
    assert stock.sector == 'Unknown'  # Default
    assert stock.industry == 'Unknown'  # Default
    assert stock.earnings_days_away == 999  # Default (far future)


def test_percentage_values_parsed_correctly():
    """
    Test that percentage values (with % signs) are parsed correctly.
    """
    credentials = FinvizCredentials(email="test@example.com", password="testpass123")
    client = FinvizClient(credentials=credentials)
    
    row_data = create_mock_finviz_row()
    row_data['Perf Week'] = '5.5%'
    row_data['Perf Month'] = '-3.2%'
    row_data['Perf Quarter'] = '12.8%'
    
    row = pd.Series(row_data)
    stock = client._parse_single_stock(row)
    
    # Percentages should be parsed as floats
    assert abs(stock.perf_week - 5.5) < 0.01
    assert abs(stock.perf_month - (-3.2)) < 0.01
    assert abs(stock.perf_quarter - 12.8) < 0.01


def test_market_cap_suffixes_parsed_correctly():
    """
    Test that market cap with M/B/T suffixes are parsed correctly.
    """
    credentials = FinvizCredentials(email="test@example.com", password="testpass123")
    client = FinvizClient(credentials=credentials)
    
    # Test millions
    row_data = create_mock_finviz_row()
    row_data['Market Cap'] = '500M'
    row = pd.Series(row_data)
    stock = client._parse_single_stock(row)
    assert abs(stock.market_cap - 500_000_000) < 1000
    
    # Test billions
    row_data['Market Cap'] = '2.5B'
    row = pd.Series(row_data)
    stock = client._parse_single_stock(row)
    assert abs(stock.market_cap - 2_500_000_000) < 1000
    
    # Test trillions
    row_data['Market Cap'] = '1.2T'
    row = pd.Series(row_data)
    stock = client._parse_single_stock(row)
    assert abs(stock.market_cap - 1_200_000_000_000) < 1000


def test_volume_suffixes_parsed_correctly():
    """
    Test that volume with K/M/B suffixes are parsed correctly.
    """
    credentials = FinvizCredentials(email="test@example.com", password="testpass123")
    client = FinvizClient(credentials=credentials)
    
    row_data = create_mock_finviz_row()
    
    # Test thousands
    row_data['Volume'] = '500K'
    row = pd.Series(row_data)
    stock = client._parse_single_stock(row)
    assert stock.volume == 500_000
    
    # Test millions
    row_data['Volume'] = '50M'
    row = pd.Series(row_data)
    stock = client._parse_single_stock(row)
    assert stock.volume == 50_000_000
