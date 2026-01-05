"""Property-based tests for strategy loading in ScreeningEngine.

Feature: strategy-stock-screener, Property 16: Strategy Loading Correctness
Validates: Requirements 5.3
"""

import tempfile
from pathlib import Path
from hypothesis import given, strategies as st, settings
import pytest
import pandas as pd

from screener.core.engine import ScreeningEngine
from screener.strategies.base import StrategyModule
from screener.core.models import StockData, StrategyAnalysis


# Helper function to create a valid strategy module file
def create_strategy_file(
    directory: Path,
    strategy_name: str,
    class_name: str,
    default_filters: dict = None
) -> Path:
    """
    Create a valid strategy module file in the given directory.
    
    Args:
        directory: Directory to create the file in
        strategy_name: Name to return from the strategy's name property
        class_name: Name of the strategy class
        default_filters: Optional default filters for the strategy
        
    Returns:
        Path to the created file
    """
    if default_filters is None:
        default_filters = {"min_price": 10, "max_price": 100}
    
    file_path = directory / f"{strategy_name.lower().replace(' ', '_')}_strategy.py"
    
    # Convert default_filters dict to string representation
    filters_str = repr(default_filters)
    
    content = f'''"""Test strategy module."""

from screener.strategies.base import StrategyModule
from screener.core.models import StockData, StrategyAnalysis


class {class_name}(StrategyModule):
    """Test strategy implementation."""
    
    @property
    def name(self) -> str:
        return "{strategy_name}"
    
    @property
    def default_filters(self):
        return {filters_str}
    
    def get_finviz_filters(self, params):
        return {{"price_min": params.get("min_price", 10)}}
    
    def score_stock(self, stock_data: StockData) -> float:
        return 50.0
    
    def analyze_stock(self, stock_data: StockData) -> StrategyAnalysis:
        return StrategyAnalysis(
            ticker=stock_data.ticker,
            strategy_score=50.0,
            support_levels=[],
            recommended_strikes={{}},
            estimated_premium=0.0,
            probability_of_profit=0.0,
            max_risk=0.0,
            return_on_risk=0.0,
            price_chart_data={{}},
            iv_history_data={{}},
            trade_recommendation="Hold",
            risk_assessment="Medium",
            notes=[]
        )
'''
    
    file_path.write_text(content)
    return file_path


@settings(max_examples=100)
@given(
    strategy_name=st.text(
        alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'),  # Uppercase, lowercase, digits
            min_codepoint=32,  # Start from space
            max_codepoint=126  # ASCII printable range
        ),
        min_size=1,
        max_size=50
    ).filter(lambda x: x.strip() and '/' not in x and '\\' not in x),
)
def test_load_strategy_returns_correct_strategy(strategy_name):
    """
    Feature: strategy-stock-screener, Property 16: Strategy Loading Correctness
    
    For any registered strategy, selecting it should load its specific
    default filters and analysis functions.
    """
    # Create a temporary directory for test strategies
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create a strategy file with specific default filters
        expected_filters = {
            "min_market_cap": 1000000,
            "min_volume": 500000,
            "price_min": 20,
            "price_max": 150
        }
        class_name = "TestStrategy"
        create_strategy_file(temp_path, strategy_name, class_name, expected_filters)
        
        # Create screening engine
        engine = ScreeningEngine()
        
        # Load the strategy using the custom directory
        from screener.strategies.discovery import get_strategy
        strategy = get_strategy(strategy_name, str(temp_path))
        
        # Verify the loaded strategy has correct name
        assert strategy.name == strategy_name, \
            f"Loaded strategy name should be '{strategy_name}', got '{strategy.name}'"
        
        # Verify the loaded strategy has correct default filters
        assert strategy.default_filters == expected_filters, \
            f"Loaded strategy should have filters {expected_filters}, got {strategy.default_filters}"
        
        # Verify it's a StrategyModule instance
        assert isinstance(strategy, StrategyModule), \
            "Loaded strategy should be a StrategyModule instance"


@settings(max_examples=100)
@given(
    num_strategies=st.integers(min_value=1, max_value=5),
)
def test_get_available_strategies_returns_all_registered(num_strategies):
    """
    Feature: strategy-stock-screener, Property 16: Strategy Loading Correctness
    
    For any set of registered strategies, get_available_strategies should
    return all strategy names.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create multiple strategy files
        created_strategies = []
        for i in range(num_strategies):
            strategy_name = f"Test Strategy {i}"
            class_name = f"TestStrategy{i}"
            create_strategy_file(temp_path, strategy_name, class_name)
            created_strategies.append(strategy_name)
        
        # Discover strategies directly from the temp directory
        from screener.strategies.discovery import discover_strategies
        discovered = discover_strategies(str(temp_path))
        available = list(discovered.keys())
        
        # All created strategies should be available
        assert len(available) == num_strategies, \
            f"Expected {num_strategies} strategies, found {len(available)}"
        
        for strategy_name in created_strategies:
            assert strategy_name in available, \
                f"Strategy '{strategy_name}' should be in available strategies"


def test_load_strategy_raises_error_for_unknown_strategy():
    """
    Feature: strategy-stock-screener, Property 16: Strategy Loading Correctness
    
    For any unregistered strategy name, load_strategy should raise KeyError.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create one strategy
        create_strategy_file(temp_path, "Known Strategy", "KnownStrategy")
        
        # Create screening engine
        engine = ScreeningEngine()
        
        # Try to load unknown strategy
        with pytest.raises(KeyError) as exc_info:
            from screener.strategies.discovery import get_strategy
            get_strategy("Unknown Strategy", str(temp_path))
        
        # Error message should be helpful
        assert "Unknown Strategy" in str(exc_info.value)
        assert "not found" in str(exc_info.value).lower()


@settings(max_examples=100)
@given(
    min_price=st.floats(min_value=1.0, max_value=50.0),
    max_price=st.floats(min_value=51.0, max_value=500.0),
    min_volume=st.integers(min_value=100000, max_value=10000000),
)
def test_loaded_strategy_preserves_filter_values(min_price, max_price, min_volume):
    """
    Feature: strategy-stock-screener, Property 16: Strategy Loading Correctness
    
    For any strategy with specific filter values, loading that strategy
    should preserve all filter values exactly.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create a strategy with specific filter values
        strategy_name = "Price Volume Strategy"
        expected_filters = {
            "min_price": min_price,
            "max_price": max_price,
            "min_volume": min_volume,
        }
        create_strategy_file(temp_path, strategy_name, "PriceVolumeStrategy", expected_filters)
        
        # Load the strategy
        from screener.strategies.discovery import get_strategy
        strategy = get_strategy(strategy_name, str(temp_path))
        
        # Verify all filter values are preserved
        loaded_filters = strategy.default_filters
        assert loaded_filters["min_price"] == min_price, \
            f"min_price should be {min_price}, got {loaded_filters['min_price']}"
        assert loaded_filters["max_price"] == max_price, \
            f"max_price should be {max_price}, got {loaded_filters['max_price']}"
        assert loaded_filters["min_volume"] == min_volume, \
            f"min_volume should be {min_volume}, got {loaded_filters['min_volume']}"


def test_loaded_strategy_has_required_methods():
    """
    Feature: strategy-stock-screener, Property 16: Strategy Loading Correctness
    
    For any loaded strategy, it should implement all required StrategyModule methods.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create a strategy
        strategy_name = "Complete Strategy"
        create_strategy_file(temp_path, strategy_name, "CompleteStrategy")
        
        # Load the strategy
        from screener.strategies.discovery import get_strategy
        strategy = get_strategy(strategy_name, str(temp_path))
        
        # Verify all required methods exist and are callable
        assert hasattr(strategy, 'name'), "Strategy should have 'name' property"
        assert hasattr(strategy, 'default_filters'), "Strategy should have 'default_filters' property"
        assert hasattr(strategy, 'get_finviz_filters'), "Strategy should have 'get_finviz_filters' method"
        assert hasattr(strategy, 'score_stock'), "Strategy should have 'score_stock' method"
        assert hasattr(strategy, 'analyze_stock'), "Strategy should have 'analyze_stock' method"
        
        # Verify methods are callable
        assert callable(strategy.get_finviz_filters), "get_finviz_filters should be callable"
        assert callable(strategy.score_stock), "score_stock should be callable"
        assert callable(strategy.analyze_stock), "analyze_stock should be callable"


@settings(max_examples=100)
@given(
    strategy_name=st.text(
        alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'),
            min_codepoint=32,
            max_codepoint=126
        ),
        min_size=1,
        max_size=50
    ).filter(lambda x: x.strip() and '/' not in x and '\\' not in x),
)
def test_loaded_strategy_can_score_stocks(strategy_name):
    """
    Feature: strategy-stock-screener, Property 16: Strategy Loading Correctness
    
    For any loaded strategy, it should be able to score stocks using its
    score_stock method.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create a strategy
        create_strategy_file(temp_path, strategy_name, "ScoringStrategy")
        
        # Load the strategy
        from screener.strategies.discovery import get_strategy
        strategy = get_strategy(strategy_name, str(temp_path))
        
        # Create a sample stock
        stock = StockData(
            ticker="TEST",
            company_name="Test Company",
            price=100.0,
            volume=1000000,
            avg_volume=1000000,
            market_cap=1000000000,
            rsi=50.0,
            sma20=95.0,
            sma50=90.0,
            sma200=85.0,
            beta=1.0,
            implied_volatility=0.3,
            iv_rank=50.0,
            option_volume=10000,
            sector="Technology",
            industry="Software",
            earnings_date=None,
            earnings_days_away=30,
            perf_week=2.0,
            perf_month=5.0,
            perf_quarter=10.0
        )
        
        # Score the stock
        score = strategy.score_stock(stock)
        
        # Verify score is valid (0-100)
        assert isinstance(score, (int, float)), "Score should be numeric"
        assert 0 <= score <= 100, f"Score should be between 0 and 100, got {score}"


@settings(max_examples=100)
@given(
    strategy_name=st.text(
        alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'),
            min_codepoint=32,
            max_codepoint=126
        ),
        min_size=1,
        max_size=50
    ).filter(lambda x: x.strip() and '/' not in x and '\\' not in x),
)
def test_loaded_strategy_can_analyze_stocks(strategy_name):
    """
    Feature: strategy-stock-screener, Property 16: Strategy Loading Correctness
    
    For any loaded strategy, it should be able to analyze stocks using its
    analyze_stock method and return a StrategyAnalysis object.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create a strategy
        create_strategy_file(temp_path, strategy_name, "AnalysisStrategy")
        
        # Load the strategy
        from screener.strategies.discovery import get_strategy
        strategy = get_strategy(strategy_name, str(temp_path))
        
        # Create a sample stock
        stock = StockData(
            ticker="TEST",
            company_name="Test Company",
            price=100.0,
            volume=1000000,
            avg_volume=1000000,
            market_cap=1000000000,
            rsi=50.0,
            sma20=95.0,
            sma50=90.0,
            sma200=85.0,
            beta=1.0,
            implied_volatility=0.3,
            iv_rank=50.0,
            option_volume=10000,
            sector="Technology",
            industry="Software",
            earnings_date=None,
            earnings_days_away=30,
            perf_week=2.0,
            perf_month=5.0,
            perf_quarter=10.0
        )
        
        # Analyze the stock
        analysis = strategy.analyze_stock(stock)
        
        # Verify analysis is a StrategyAnalysis object
        assert isinstance(analysis, StrategyAnalysis), \
            "analyze_stock should return a StrategyAnalysis object"
        
        # Verify analysis has required fields
        assert analysis.ticker == stock.ticker, \
            f"Analysis ticker should be '{stock.ticker}', got '{analysis.ticker}'"
        assert hasattr(analysis, 'strategy_score'), \
            "Analysis should have strategy_score field"
        assert hasattr(analysis, 'support_levels'), \
            "Analysis should have support_levels field"
