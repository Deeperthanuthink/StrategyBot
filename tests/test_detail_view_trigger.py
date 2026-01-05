"""
Property-based tests for stock detail view trigger.

Feature: strategy-stock-screener, Property 3: Stock Detail View Trigger
Validates: Requirements 1.4

For any stock in the screening results, selecting that stock should trigger
display of detailed analysis including support levels, probability of profit,
and premium estimates.
"""

import pytest
from hypothesis import given, strategies as st, settings
import pandas as pd
from datetime import datetime
from screener.core.models import StockData, StrategyAnalysis
from screener.strategies.pcs_strategy import PCSStrategy


@settings(max_examples=100)
@given(
    ticker=st.text(min_size=1, max_size=5, alphabet=st.characters(whitelist_categories=('Lu',))),
    price=st.floats(min_value=20, max_value=500),
    iv_rank=st.floats(min_value=0, max_value=100),
)
def test_stock_selection_triggers_analysis(ticker, price, iv_rank):
    """
    Property 3: Stock Detail View Trigger
    
    For any stock, selecting it should trigger detailed analysis that includes:
    - Support levels
    - Probability of profit
    - Premium estimates
    - Recommended strikes
    """
    # Create a stock data object
    stock_data = StockData(
        ticker=ticker,
        company_name=f"{ticker} Inc.",
        price=price,
        volume=1_000_000,
        avg_volume=1_000_000,
        market_cap=2e9,
        rsi=50.0,
        sma20=price * 0.98,
        sma50=price * 0.95,
        sma200=price * 0.90,
        beta=1.0,
        implied_volatility=0.3,
        iv_rank=iv_rank,
        option_volume=10000,
        sector='Technology',
        industry='Software',
        earnings_date=None,
        earnings_days_away=30,
        perf_week=0.0,
        perf_month=0.0,
        perf_quarter=0.0,
    )
    
    # Use PCS strategy to analyze the stock
    strategy = PCSStrategy()
    
    # Trigger analysis (simulates selecting the stock)
    analysis = strategy.analyze_stock(stock_data)
    
    # Verify analysis contains all required components
    assert isinstance(analysis, StrategyAnalysis), \
        "Analysis should return a StrategyAnalysis object"
    
    assert analysis.ticker == ticker, \
        "Analysis should be for the selected stock"
    
    assert len(analysis.support_levels) > 0, \
        "Analysis should include support levels"
    
    assert 0 <= analysis.probability_of_profit <= 100, \
        "Analysis should include valid probability of profit"
    
    assert analysis.estimated_premium >= 0, \
        "Analysis should include premium estimate"
    
    assert 'short' in analysis.recommended_strikes, \
        "Analysis should include short strike recommendation"
    
    assert 'long' in analysis.recommended_strikes, \
        "Analysis should include long strike recommendation"
    
    assert analysis.max_risk >= 0, \
        "Analysis should include max risk calculation"
    
    assert analysis.return_on_risk >= 0, \
        "Analysis should include return on risk calculation"


@settings(max_examples=100)
@given(
    num_stocks=st.integers(min_value=1, max_value=10),
    selected_index=st.integers(min_value=0, max_value=9),
)
def test_different_stocks_produce_different_analyses(num_stocks, selected_index):
    """
    Test that selecting different stocks produces different analyses.
    
    This ensures that the detail view is responsive to stock selection.
    """
    # Ensure selected_index is within bounds
    if selected_index >= num_stocks:
        selected_index = num_stocks - 1
    
    # Create multiple stocks
    stocks = []
    for i in range(num_stocks):
        stock = StockData(
            ticker=f'STOCK{i}',
            company_name=f'Company {i}',
            price=50.0 + i * 10,
            volume=1_000_000,
            avg_volume=1_000_000,
            market_cap=2e9,
            rsi=50.0,
            sma20=50.0,
            sma50=50.0,
            sma200=50.0,
            beta=1.0,
            implied_volatility=0.3,
            iv_rank=50.0 + i,
            option_volume=10000,
            sector='Technology',
            industry='Software',
            earnings_date=None,
            earnings_days_away=30,
            perf_week=0.0,
            perf_month=0.0,
            perf_quarter=0.0,
        )
        stocks.append(stock)
    
    # Analyze the selected stock
    strategy = PCSStrategy()
    selected_stock = stocks[selected_index]
    analysis = strategy.analyze_stock(selected_stock)
    
    # Verify the analysis is for the correct stock
    assert analysis.ticker == selected_stock.ticker, \
        "Analysis should be for the selected stock"
    
    # If there are multiple stocks, verify that different stocks produce different analyses
    if num_stocks > 1:
        # Analyze a different stock
        other_index = (selected_index + 1) % num_stocks
        other_stock = stocks[other_index]
        other_analysis = strategy.analyze_stock(other_stock)
        
        # The analyses should be different
        assert analysis.ticker != other_analysis.ticker, \
            "Different stocks should have different tickers in analysis"


def test_analysis_includes_visualization_data():
    """
    Test that analysis includes data for price and IV charts.
    
    Requirements: 1.4, 4.5
    """
    stock_data = StockData(
        ticker='AAPL',
        company_name='Apple Inc.',
        price=150.0,
        volume=50_000_000,
        avg_volume=50_000_000,
        market_cap=2.5e12,
        rsi=55.0,
        sma20=148.0,
        sma50=145.0,
        sma200=140.0,
        beta=1.2,
        implied_volatility=0.25,
        iv_rank=60.0,
        option_volume=100000,
        sector='Technology',
        industry='Consumer Electronics',
        earnings_date=None,
        earnings_days_away=45,
        perf_week=2.0,
        perf_month=5.0,
        perf_quarter=10.0,
    )
    
    strategy = PCSStrategy()
    analysis = strategy.analyze_stock(stock_data)
    
    # Verify visualization data is present
    assert analysis.price_chart_data is not None, \
        "Analysis should include price chart data"
    
    assert analysis.iv_history_data is not None, \
        "Analysis should include IV history chart data"
    
    assert isinstance(analysis.price_chart_data, dict), \
        "Price chart data should be a dictionary"
    
    assert isinstance(analysis.iv_history_data, dict), \
        "IV history data should be a dictionary"


def test_analysis_includes_trade_recommendation():
    """
    Test that analysis includes a trade recommendation.
    """
    stock_data = StockData(
        ticker='MSFT',
        company_name='Microsoft Corporation',
        price=350.0,
        volume=30_000_000,
        avg_volume=30_000_000,
        market_cap=2.8e12,
        rsi=60.0,
        sma20=345.0,
        sma50=340.0,
        sma200=330.0,
        beta=1.1,
        implied_volatility=0.22,
        iv_rank=70.0,
        option_volume=80000,
        sector='Technology',
        industry='Software',
        earnings_date=None,
        earnings_days_away=60,
        perf_week=1.5,
        perf_month=4.0,
        perf_quarter=8.0,
    )
    
    strategy = PCSStrategy()
    analysis = strategy.analyze_stock(stock_data)
    
    # Verify trade recommendation is present
    assert analysis.trade_recommendation is not None, \
        "Analysis should include trade recommendation"
    
    assert isinstance(analysis.trade_recommendation, str), \
        "Trade recommendation should be a string"
    
    assert analysis.trade_recommendation in ['Strong Buy', 'Buy', 'Hold', 'Avoid'], \
        "Trade recommendation should be one of the valid values"
    
    # Verify risk assessment is present
    assert analysis.risk_assessment is not None, \
        "Analysis should include risk assessment"
    
    assert isinstance(analysis.risk_assessment, str), \
        "Risk assessment should be a string"


def test_analysis_includes_notes():
    """
    Test that analysis includes explanatory notes.
    """
    stock_data = StockData(
        ticker='GOOGL',
        company_name='Alphabet Inc.',
        price=140.0,
        volume=25_000_000,
        avg_volume=25_000_000,
        market_cap=1.8e12,
        rsi=52.0,
        sma20=138.0,
        sma50=135.0,
        sma200=130.0,
        beta=1.05,
        implied_volatility=0.28,
        iv_rank=55.0,
        option_volume=70000,
        sector='Technology',
        industry='Internet',
        earnings_date=None,
        earnings_days_away=50,
        perf_week=1.0,
        perf_month=3.0,
        perf_quarter=7.0,
    )
    
    strategy = PCSStrategy()
    analysis = strategy.analyze_stock(stock_data)
    
    # Verify notes are present
    assert analysis.notes is not None, \
        "Analysis should include notes"
    
    assert isinstance(analysis.notes, list), \
        "Notes should be a list"
    
    assert len(analysis.notes) > 0, \
        "Analysis should include at least one note"
    
    # Verify notes are strings
    for note in analysis.notes:
        assert isinstance(note, str), \
            "Each note should be a string"
        assert len(note) > 0, \
            "Notes should not be empty"
