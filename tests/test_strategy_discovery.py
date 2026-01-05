"""Property-based tests for strategy discovery mechanism.

Feature: strategy-stock-screener, Property 15: Strategy Plugin Discovery
Validates: Requirements 5.2
"""

import tempfile
import shutil
from pathlib import Path
from hypothesis import given, strategies as st, settings
import pytest

from screener.strategies.discovery import (
    discover_strategies,
    get_strategy,
    list_available_strategies
)
from screener.strategies.base import StrategyModule
from screener.core.models import StockData, StrategyAnalysis


# Helper function to create a valid strategy module file
def create_strategy_file(directory: Path, strategy_name: str, class_name: str) -> Path:
    """
    Create a valid strategy module file in the given directory.
    
    Args:
        directory: Directory to create the file in
        strategy_name: Name to return from the strategy's name property
        class_name: Name of the strategy class
        
    Returns:
        Path to the created file
    """
    file_path = directory / f"{strategy_name.lower().replace(' ', '_')}_strategy.py"
    
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
        return {{"min_price": 10, "max_price": 100}}
    
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
    num_strategies=st.integers(min_value=1, max_value=5),
)
def test_discover_strategies_finds_all_valid_modules(num_strategies):
    """
    Feature: strategy-stock-screener, Property 15: Strategy Plugin Discovery
    
    For any valid strategy module file placed in the strategies directory,
    the system should automatically discover and register it.
    """
    # Create a temporary directory for test strategies
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create multiple strategy files
        created_strategies = []
        for i in range(num_strategies):
            strategy_name = f"Test Strategy {i}"
            class_name = f"TestStrategy{i}"
            create_strategy_file(temp_path, strategy_name, class_name)
            created_strategies.append(strategy_name)
        
        # Discover strategies
        discovered = discover_strategies(str(temp_path))
        
        # All created strategies should be discovered
        assert len(discovered) == num_strategies, \
            f"Expected {num_strategies} strategies, found {len(discovered)}"
        
        # Each created strategy should be in the discovered set
        for strategy_name in created_strategies:
            assert strategy_name in discovered, \
                f"Strategy '{strategy_name}' should be discovered"
            
            # Verify it's a StrategyModule instance
            assert isinstance(discovered[strategy_name], StrategyModule), \
                f"Discovered strategy should be a StrategyModule instance"


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
def test_discovered_strategy_has_correct_name(strategy_name):
    """
    Feature: strategy-stock-screener, Property 15: Strategy Plugin Discovery
    
    For any discovered strategy, its name property should match the registered name.
    """
    # Create a temporary directory for test strategies
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create a strategy file
        class_name = "TestStrategy"
        create_strategy_file(temp_path, strategy_name, class_name)
        
        # Discover strategies
        discovered = discover_strategies(str(temp_path))
        
        # Strategy should be discovered with correct name
        assert strategy_name in discovered, \
            f"Strategy '{strategy_name}' should be discovered"
        
        # The name property should match
        assert discovered[strategy_name].name == strategy_name, \
            f"Strategy name property should be '{strategy_name}'"


def test_discover_strategies_ignores_invalid_files():
    """
    Feature: strategy-stock-screener, Property 15: Strategy Plugin Discovery
    
    For any invalid or non-strategy files in the directory,
    discovery should skip them without failing.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create a valid strategy
        create_strategy_file(temp_path, "Valid Strategy", "ValidStrategy")
        
        # Create an invalid Python file (no strategy class)
        invalid_file = temp_path / "invalid_strategy.py"
        invalid_file.write_text("# This file has no strategy class\nprint('hello')")
        
        # Create a non-Python file
        non_python = temp_path / "readme_strategy.txt"
        non_python.write_text("This is not a Python file")
        
        # Discover strategies - should only find the valid one
        discovered = discover_strategies(str(temp_path))
        
        # Should find exactly one valid strategy
        assert len(discovered) == 1, \
            f"Should discover exactly 1 valid strategy, found {len(discovered)}"
        assert "Valid Strategy" in discovered


def test_get_strategy_returns_correct_strategy():
    """
    Feature: strategy-stock-screener, Property 15: Strategy Plugin Discovery
    
    For any registered strategy name, get_strategy should return that strategy.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create multiple strategies
        create_strategy_file(temp_path, "Strategy A", "StrategyA")
        create_strategy_file(temp_path, "Strategy B", "StrategyB")
        
        # Get specific strategy
        strategy_a = get_strategy("Strategy A", str(temp_path))
        
        # Should return the correct strategy
        assert strategy_a.name == "Strategy A"
        assert isinstance(strategy_a, StrategyModule)


def test_get_strategy_raises_error_for_unknown_strategy():
    """
    Feature: strategy-stock-screener, Property 15: Strategy Plugin Discovery
    
    For any unregistered strategy name, get_strategy should raise KeyError.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create one strategy
        create_strategy_file(temp_path, "Known Strategy", "KnownStrategy")
        
        # Try to get unknown strategy
        with pytest.raises(KeyError) as exc_info:
            get_strategy("Unknown Strategy", str(temp_path))
        
        # Error message should be helpful
        assert "Unknown Strategy" in str(exc_info.value)
        assert "not found" in str(exc_info.value).lower()


def test_list_available_strategies_returns_all_names():
    """
    Feature: strategy-stock-screener, Property 15: Strategy Plugin Discovery
    
    For any set of discovered strategies, list_available_strategies
    should return all strategy names.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create multiple strategies
        expected_names = ["Strategy X", "Strategy Y", "Strategy Z"]
        for i, name in enumerate(expected_names):
            create_strategy_file(temp_path, name, f"Strategy{chr(88+i)}")
        
        # List available strategies
        available = list_available_strategies(str(temp_path))
        
        # Should return all strategy names
        assert len(available) == len(expected_names)
        for name in expected_names:
            assert name in available


@settings(max_examples=100)
@given(
    num_strategies=st.integers(min_value=0, max_value=10),
)
def test_discover_strategies_count_matches_files(num_strategies):
    """
    Feature: strategy-stock-screener, Property 15: Strategy Plugin Discovery
    
    For any number of valid strategy files, the number of discovered
    strategies should match the number of files.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create strategy files
        for i in range(num_strategies):
            create_strategy_file(temp_path, f"Strategy {i}", f"Strategy{i}")
        
        # Discover strategies
        discovered = discover_strategies(str(temp_path))
        
        # Count should match
        assert len(discovered) == num_strategies, \
            f"Expected {num_strategies} strategies, found {len(discovered)}"
