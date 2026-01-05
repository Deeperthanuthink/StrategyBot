"""Property-based tests for strategy interface validation.

Feature: strategy-stock-screener, Property 17: Strategy Interface Validation
Validates: Requirements 5.5
"""

from datetime import date
from hypothesis import given, strategies as st, settings
import pytest

from screener.strategies.base import StrategyModule
from screener.core.models import StockData, StrategyAnalysis


# Create a concrete test strategy for validation
class ValidTestStrategy(StrategyModule):
    """A valid strategy implementation for testing."""
    
    @property
    def name(self) -> str:
        return "Valid Test Strategy"
    
    @property
    def default_filters(self):
        return {"min_price": 10, "max_price": 100}
    
    def get_finviz_filters(self, params):
        return {"price_min": params.get("min_price", 10)}
    
    def score_stock(self, stock_data: StockData) -> float:
        return 50.0
    
    def analyze_stock(self, stock_data: StockData) -> StrategyAnalysis:
        return StrategyAnalysis(
            ticker=stock_data.ticker,
            strategy_score=50.0,
            support_levels=[],
            recommended_strikes={},
            estimated_premium=0.0,
            probability_of_profit=0.0,
            max_risk=0.0,
            return_on_risk=0.0,
            price_chart_data={},
            iv_history_data={},
            trade_recommendation="Hold",
            risk_assessment="Medium",
            notes=[]
        )


# Create an incomplete strategy missing required methods
class IncompleteStrategy(StrategyModule):
    """An incomplete strategy missing required methods."""
    
    @property
    def name(self) -> str:
        return "Incomplete Strategy"
    
    @property
    def default_filters(self):
        return {}
    
    # Missing get_finviz_filters, score_stock, and analyze_stock


def create_valid_stock_data(ticker="AAPL"):
    """Helper to create valid stock data for testing."""
    return StockData(
        ticker=ticker,
        company_name="Test Company",
        price=150.0,
        volume=1000000,
        avg_volume=1000000,
        market_cap=2_000_000_000,
        rsi=50.0,
        sma20=150.0,
        sma50=145.0,
        sma200=140.0,
        beta=1.0,
        implied_volatility=0.3,
        iv_rank=50.0,
        option_volume=10000,
        sector="Technology",
        industry="Consumer Electronics",
        earnings_date=None,
        earnings_days_away=30,
        perf_week=1.5,
        perf_month=3.0,
        perf_quarter=5.0,
    )


def test_valid_strategy_has_all_required_methods():
    """
    Feature: strategy-stock-screener, Property 17: Strategy Interface Validation
    
    For any loaded strategy module, it should implement all required interface methods.
    """
    strategy = ValidTestStrategy()
    
    # Check that all required methods exist and are callable
    assert hasattr(strategy, 'name'), "Strategy should have 'name' property"
    assert hasattr(strategy, 'default_filters'), "Strategy should have 'default_filters' property"
    assert hasattr(strategy, 'get_finviz_filters'), "Strategy should have 'get_finviz_filters' method"
    assert hasattr(strategy, 'score_stock'), "Strategy should have 'score_stock' method"
    assert hasattr(strategy, 'analyze_stock'), "Strategy should have 'analyze_stock' method"
    
    # Verify they are callable (except properties)
    assert callable(strategy.get_finviz_filters), "get_finviz_filters should be callable"
    assert callable(strategy.score_stock), "score_stock should be callable"
    assert callable(strategy.analyze_stock), "analyze_stock should be callable"


def test_incomplete_strategy_cannot_be_instantiated():
    """
    Feature: strategy-stock-screener, Property 17: Strategy Interface Validation
    
    For any strategy module missing required methods, instantiation should fail.
    """
    # Attempting to instantiate an incomplete strategy should raise TypeError
    with pytest.raises(TypeError) as exc_info:
        IncompleteStrategy()
    
    # Error should mention abstract methods
    assert "abstract" in str(exc_info.value).lower()


@settings(max_examples=100)
@given(
    strategy_name=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
)
def test_strategy_name_property_returns_string(strategy_name):
    """
    Feature: strategy-stock-screener, Property 17: Strategy Interface Validation
    
    For any valid strategy, the name property should return a non-empty string.
    """
    # Create a dynamic strategy with the given name
    class DynamicStrategy(StrategyModule):
        @property
        def name(self):
            return strategy_name
        
        @property
        def default_filters(self):
            return {}
        
        def get_finviz_filters(self, params):
            return {}
        
        def score_stock(self, stock_data: StockData) -> float:
            return 50.0
        
        def analyze_stock(self, stock_data: StockData) -> StrategyAnalysis:
            return StrategyAnalysis(
                ticker=stock_data.ticker,
                strategy_score=50.0,
                support_levels=[],
                recommended_strikes={},
                estimated_premium=0.0,
                probability_of_profit=0.0,
                max_risk=0.0,
                return_on_risk=0.0,
                price_chart_data={},
                iv_history_data={},
                trade_recommendation="Hold",
                risk_assessment="Medium",
                notes=[]
            )
    
    strategy = DynamicStrategy()
    
    # Name should be a string
    assert isinstance(strategy.name, str), "Strategy name should be a string"
    # Name should not be empty
    assert len(strategy.name.strip()) > 0, "Strategy name should not be empty"
    # Name should match what we set
    assert strategy.name == strategy_name


@settings(max_examples=100)
@given(
    filters=st.dictionaries(
        keys=st.text(min_size=1, max_size=20),
        values=st.one_of(st.integers(), st.floats(allow_nan=False, allow_infinity=False), st.text()),
        min_size=0,
        max_size=10
    )
)
def test_default_filters_returns_dict(filters):
    """
    Feature: strategy-stock-screener, Property 17: Strategy Interface Validation
    
    For any valid strategy, default_filters should return a dictionary.
    """
    class DynamicStrategy(StrategyModule):
        @property
        def name(self):
            return "Test"
        
        @property
        def default_filters(self):
            return filters
        
        def get_finviz_filters(self, params):
            return {}
        
        def score_stock(self, stock_data: StockData) -> float:
            return 50.0
        
        def analyze_stock(self, stock_data: StockData) -> StrategyAnalysis:
            return StrategyAnalysis(
                ticker="TEST",
                strategy_score=50.0,
                support_levels=[],
                recommended_strikes={},
                estimated_premium=0.0,
                probability_of_profit=0.0,
                max_risk=0.0,
                return_on_risk=0.0,
                price_chart_data={},
                iv_history_data={},
                trade_recommendation="Hold",
                risk_assessment="Medium",
                notes=[]
            )
    
    strategy = DynamicStrategy()
    
    # default_filters should return a dict
    result = strategy.default_filters
    assert isinstance(result, dict), "default_filters should return a dictionary"


@settings(max_examples=100)
@given(
    score=st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
)
def test_score_stock_returns_float_in_range(score):
    """
    Feature: strategy-stock-screener, Property 17: Strategy Interface Validation
    
    For any valid strategy and stock data, score_stock should return a float between 0-100.
    """
    class DynamicStrategy(StrategyModule):
        @property
        def name(self):
            return "Test"
        
        @property
        def default_filters(self):
            return {}
        
        def get_finviz_filters(self, params):
            return {}
        
        def score_stock(self, stock_data: StockData) -> float:
            return score
        
        def analyze_stock(self, stock_data: StockData) -> StrategyAnalysis:
            return StrategyAnalysis(
                ticker=stock_data.ticker,
                strategy_score=score,
                support_levels=[],
                recommended_strikes={},
                estimated_premium=0.0,
                probability_of_profit=0.0,
                max_risk=0.0,
                return_on_risk=0.0,
                price_chart_data={},
                iv_history_data={},
                trade_recommendation="Hold",
                risk_assessment="Medium",
                notes=[]
            )
    
    strategy = DynamicStrategy()
    stock_data = create_valid_stock_data()
    
    # score_stock should return a float
    result = strategy.score_stock(stock_data)
    assert isinstance(result, (int, float)), "score_stock should return a numeric value"
    
    # Score should be in valid range
    assert 0 <= result <= 100, f"Score should be between 0-100, got {result}"


def test_analyze_stock_returns_strategy_analysis():
    """
    Feature: strategy-stock-screener, Property 17: Strategy Interface Validation
    
    For any valid strategy and stock data, analyze_stock should return a StrategyAnalysis object.
    """
    strategy = ValidTestStrategy()
    stock_data = create_valid_stock_data()
    
    # analyze_stock should return StrategyAnalysis
    result = strategy.analyze_stock(stock_data)
    assert isinstance(result, StrategyAnalysis), \
        "analyze_stock should return a StrategyAnalysis object"
    
    # Result should have the correct ticker
    assert result.ticker == stock_data.ticker, \
        "StrategyAnalysis ticker should match input stock ticker"


def test_get_finviz_filters_returns_dict():
    """
    Feature: strategy-stock-screener, Property 17: Strategy Interface Validation
    
    For any valid strategy and parameters, get_finviz_filters should return a dictionary.
    """
    strategy = ValidTestStrategy()
    params = {"min_price": 20, "max_price": 200}
    
    # get_finviz_filters should return a dict
    result = strategy.get_finviz_filters(params)
    assert isinstance(result, dict), \
        "get_finviz_filters should return a dictionary"


@settings(max_examples=100)
@given(
    ticker=st.text(min_size=1, max_size=5).filter(lambda x: x.strip()),
)
def test_strategy_methods_accept_stock_data(ticker):
    """
    Feature: strategy-stock-screener, Property 17: Strategy Interface Validation
    
    For any valid strategy, score_stock and analyze_stock should accept StockData objects.
    """
    strategy = ValidTestStrategy()
    stock_data = create_valid_stock_data(ticker=ticker)
    
    # Both methods should accept StockData without error
    score = strategy.score_stock(stock_data)
    analysis = strategy.analyze_stock(stock_data)
    
    # Results should be valid
    assert isinstance(score, (int, float)), "score_stock should return numeric value"
    assert isinstance(analysis, StrategyAnalysis), "analyze_stock should return StrategyAnalysis"
    assert analysis.ticker == ticker, "Analysis should preserve ticker"
