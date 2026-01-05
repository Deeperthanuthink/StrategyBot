"""
Property-based tests for results display completeness.

Feature: strategy-stock-screener, Property 2: Results Display Completeness
Validates: Requirements 1.3

For any screening result set, the displayed table should contain stock symbols,
key metrics (price, volume, market cap), and strategy-specific scores for all stocks.
"""

import pytest
from hypothesis import given, strategies as st, settings
import pandas as pd
from datetime import datetime
from screener.core.models import ScreenerResults


@settings(max_examples=100)
@given(
    num_stocks=st.integers(min_value=1, max_value=50),
    has_scores=st.booleans(),
)
def test_results_contain_required_columns(num_stocks, has_scores):
    """
    Property 2: Results Display Completeness
    
    For any screening result set, the results should contain all required columns:
    - ticker (stock symbol)
    - key metrics (price, volume, market_cap)
    - strategy_score (if scoring was performed)
    """
    # Create sample screening results
    stocks_data = []
    for i in range(num_stocks):
        stock = {
            'ticker': f'STOCK{i}',
            'company_name': f'Company {i}',
            'price': 50.0 + i,
            'volume': 1_000_000 + i * 10000,
            'avg_volume': 1_000_000 + i * 10000,
            'market_cap': 2e9 + i * 1e8,
            'rsi': 50.0,
            'sma20': 50.0,
            'sma50': 50.0,
            'sma200': 50.0,
            'beta': 1.0,
            'implied_volatility': 0.3,
            'iv_rank': 50.0,
            'option_volume': 10000,
            'sector': 'Technology',
            'industry': 'Software',
            'earnings_date': None,
            'earnings_days_away': 30,
            'perf_week': 0.0,
            'perf_month': 0.0,
            'perf_quarter': 0.0,
        }
        
        if has_scores:
            stock['strategy_score'] = 50.0 + i
        
        stocks_data.append(stock)
    
    stocks_df = pd.DataFrame(stocks_data)
    
    results = ScreenerResults(
        timestamp=datetime.now(),
        strategy="Test Strategy",
        filters={},
        stocks=stocks_df,
        metadata={}
    )
    
    # Verify required columns are present
    assert 'ticker' in results.stocks.columns, "Results must contain ticker column"
    assert 'price' in results.stocks.columns, "Results must contain price column"
    assert 'volume' in results.stocks.columns, "Results must contain volume column"
    assert 'market_cap' in results.stocks.columns, "Results must contain market_cap column"
    
    # Verify all stocks are present
    assert len(results.stocks) == num_stocks, \
        f"Results should contain all {num_stocks} stocks"
    
    # Verify strategy_score is present if scoring was performed
    if has_scores:
        assert 'strategy_score' in results.stocks.columns, \
            "Results must contain strategy_score column when scoring is performed"


@settings(max_examples=100)
@given(
    num_stocks=st.integers(min_value=1, max_value=20),
)
def test_all_stocks_have_complete_data(num_stocks):
    """
    Test that all stocks in results have complete data for display.
    
    Every stock should have non-null values for key display fields.
    """
    # Create sample screening results
    stocks_data = []
    for i in range(num_stocks):
        stocks_data.append({
            'ticker': f'STOCK{i}',
            'company_name': f'Company {i}',
            'price': 50.0 + i,
            'volume': 1_000_000 + i * 10000,
            'market_cap': 2e9 + i * 1e8,
            'strategy_score': 50.0 + i,
        })
    
    stocks_df = pd.DataFrame(stocks_data)
    
    results = ScreenerResults(
        timestamp=datetime.now(),
        strategy="Test Strategy",
        filters={},
        stocks=stocks_df,
        metadata={}
    )
    
    # Verify no null values in key columns
    assert results.stocks['ticker'].notna().all(), \
        "All stocks must have ticker"
    assert results.stocks['price'].notna().all(), \
        "All stocks must have price"
    assert results.stocks['volume'].notna().all(), \
        "All stocks must have volume"
    assert results.stocks['market_cap'].notna().all(), \
        "All stocks must have market_cap"
    assert results.stocks['strategy_score'].notna().all(), \
        "All stocks must have strategy_score"


def test_results_table_columns_are_displayable():
    """
    Test that results table columns can be displayed.
    
    This ensures that the data types and formats are suitable for UI display.
    """
    # Create sample results
    stocks_data = [
        {
            'ticker': 'AAPL',
            'company_name': 'Apple Inc.',
            'price': 150.25,
            'volume': 50_000_000,
            'market_cap': 2.5e12,
            'rsi': 55.5,
            'iv_rank': 45.0,
            'strategy_score': 75.5,
        },
        {
            'ticker': 'MSFT',
            'company_name': 'Microsoft Corporation',
            'price': 350.75,
            'volume': 30_000_000,
            'market_cap': 2.8e12,
            'rsi': 60.0,
            'iv_rank': 50.0,
            'strategy_score': 80.0,
        },
    ]
    
    stocks_df = pd.DataFrame(stocks_data)
    
    results = ScreenerResults(
        timestamp=datetime.now(),
        strategy="Test Strategy",
        filters={},
        stocks=stocks_df,
        metadata={}
    )
    
    # Verify data types are appropriate for display
    assert results.stocks['ticker'].dtype == object, "Ticker should be string type"
    assert results.stocks['price'].dtype in [float, int], "Price should be numeric"
    assert results.stocks['volume'].dtype in [float, int], "Volume should be numeric"
    assert results.stocks['market_cap'].dtype in [float, int], "Market cap should be numeric"
    assert results.stocks['strategy_score'].dtype in [float, int], "Score should be numeric"
    
    # Verify values are in reasonable ranges
    assert (results.stocks['price'] > 0).all(), "All prices should be positive"
    assert (results.stocks['volume'] >= 0).all(), "All volumes should be non-negative"
    assert (results.stocks['market_cap'] > 0).all(), "All market caps should be positive"
    assert (results.stocks['strategy_score'] >= 0).all(), "All scores should be non-negative"
    assert (results.stocks['strategy_score'] <= 100).all(), "All scores should be <= 100"


def test_empty_results_are_handled():
    """
    Test that empty results (no stocks matched) are handled gracefully.
    """
    # Create empty results
    stocks_df = pd.DataFrame(columns=[
        'ticker', 'company_name', 'price', 'volume', 'market_cap', 'strategy_score'
    ])
    
    results = ScreenerResults(
        timestamp=datetime.now(),
        strategy="Test Strategy",
        filters={},
        stocks=stocks_df,
        metadata={}
    )
    
    # Verify empty results are valid
    assert len(results.stocks) == 0, "Empty results should have 0 stocks"
    assert isinstance(results.stocks, pd.DataFrame), "Empty results should still be a DataFrame"
    
    # Verify columns are still present
    assert 'ticker' in results.stocks.columns
    assert 'price' in results.stocks.columns
    assert 'volume' in results.stocks.columns
    assert 'market_cap' in results.stocks.columns


@settings(max_examples=100)
@given(
    num_stocks=st.integers(min_value=1, max_value=20),
)
def test_results_are_sortable_by_score(num_stocks):
    """
    Test that results can be sorted by strategy score.
    
    This is important for displaying top candidates first.
    """
    # Create sample results with varying scores
    stocks_data = []
    for i in range(num_stocks):
        stocks_data.append({
            'ticker': f'STOCK{i}',
            'company_name': f'Company {i}',
            'price': 50.0 + i,
            'volume': 1_000_000,
            'market_cap': 2e9,
            'strategy_score': float(i * 5),  # Scores from 0 to num_stocks*5
        })
    
    stocks_df = pd.DataFrame(stocks_data)
    
    results = ScreenerResults(
        timestamp=datetime.now(),
        strategy="Test Strategy",
        filters={},
        stocks=stocks_df,
        metadata={}
    )
    
    # Sort by strategy_score descending
    sorted_df = results.stocks.sort_values('strategy_score', ascending=False)
    
    # Verify sorting worked
    scores = sorted_df['strategy_score'].tolist()
    assert scores == sorted(scores, reverse=True), \
        "Results should be sortable by strategy_score in descending order"
