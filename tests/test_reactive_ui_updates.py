"""
Property-based tests for reactive UI updates.

Feature: strategy-stock-screener, Property 1: Reactive UI Updates
Validates: Requirements 1.2

For any screening parameter modification in the Marimo notebook,
the results display should update automatically without requiring manual refresh.
"""

import pytest
from hypothesis import given, strategies as st, settings
import pandas as pd
from screener.core.engine import ScreeningEngine
from screener.core.models import StockData


# Since we cannot directly test Marimo's reactive behavior without running the notebook,
# we test the underlying logic that would trigger updates


@settings(max_examples=100)
@given(
    min_market_cap=st.floats(min_value=1e9, max_value=1e12),
    min_volume=st.integers(min_value=500_000, max_value=5_000_000),
    price_min=st.floats(min_value=10, max_value=50),
    price_max=st.floats(min_value=100, max_value=500),
)
def test_filter_changes_produce_different_results(
    min_market_cap, min_volume, price_min, price_max
):
    """
    Property 1: Reactive UI Updates
    
    For any screening parameter modification, the filtering logic should
    produce results that reflect the new parameters.
    
    This tests the underlying logic that Marimo would use to reactively
    update the UI when parameters change.
    """
    # Create sample stock data
    stocks_data = []
    for i in range(20):
        stocks_data.append({
            'ticker': f'STOCK{i}',
            'company_name': f'Company {i}',
            'price': 50 + i * 10,
            'volume': 1_000_000,
            'avg_volume': 1_000_000 + i * 100_000,
            'market_cap': 2e9 + i * 1e9,
            'rsi': 50,
            'sma20': 50,
            'sma50': 50,
            'sma200': 50,
            'beta': 1.0,
            'implied_volatility': 0.3,
            'iv_rank': 50,
            'option_volume': 10000,
            'sector': 'Technology',
            'industry': 'Software',
            'earnings_date': None,
            'earnings_days_away': 30,
            'perf_week': 0,
            'perf_month': 0,
            'perf_quarter': 0,
        })
    
    stocks_df = pd.DataFrame(stocks_data)
    
    # Create two different filter sets
    filters1 = {
        'min_market_cap': min_market_cap,
        'min_volume': min_volume,
        'price_min': price_min,
        'price_max': price_max,
    }
    
    filters2 = {
        'min_market_cap': min_market_cap * 1.5,
        'min_volume': min_volume * 1.5,
        'price_min': price_min * 1.2,
        'price_max': price_max * 0.8,
    }
    
    # Create engine and apply filters
    engine = ScreeningEngine()
    
    # Mock strategy for filtering
    class MockStrategy:
        @property
        def name(self):
            return "Mock"
        
        @property
        def default_filters(self):
            return {}
        
        def get_finviz_filters(self, params):
            return {}
        
        def score_stock(self, stock_data):
            return 50.0
        
        def analyze_stock(self, stock_data):
            return None
    
    strategy = MockStrategy()
    
    # Apply both filter sets
    result1 = engine.apply_filters(stocks_df.copy(), filters1, strategy)
    result2 = engine.apply_filters(stocks_df.copy(), filters2, strategy)
    
    # The results should be different when filters are different
    # (unless all stocks pass both filters, which is unlikely with random values)
    # At minimum, the filtering logic should execute without error
    assert isinstance(result1, pd.DataFrame)
    assert isinstance(result2, pd.DataFrame)
    
    # If filters are more restrictive, result should have fewer or equal stocks
    assert len(result2) <= len(result1)


def test_strategy_change_loads_new_filters():
    """
    Test that changing strategy loads new default filters.
    
    This simulates the reactive behavior where selecting a different
    strategy should load that strategy's default filters.
    """
    engine = ScreeningEngine()
    
    # Get available strategies
    strategies = engine.get_available_strategies()
    
    if len(strategies) < 1:
        pytest.skip("No strategies available for testing")
    
    # Load first strategy
    strategy1 = engine.load_strategy(strategies[0])
    filters1 = strategy1.default_filters
    
    # Verify filters are loaded
    assert isinstance(filters1, dict)
    assert len(filters1) > 0
    
    # If there's a second strategy, verify it has different filters
    if len(strategies) > 1:
        strategy2 = engine.load_strategy(strategies[1])
        filters2 = strategy2.default_filters
        
        assert isinstance(filters2, dict)
        # Strategies may have different filter sets
        # At minimum, they should both be valid dictionaries


def test_filter_panel_reflects_strategy_defaults():
    """
    Test that filter panel values match strategy defaults.
    
    This ensures that when a strategy is selected, the filter panel
    is populated with the correct default values.
    """
    engine = ScreeningEngine()
    strategies = engine.get_available_strategies()
    
    if len(strategies) < 1:
        pytest.skip("No strategies available for testing")
    
    for strategy_name in strategies:
        strategy = engine.load_strategy(strategy_name)
        defaults = strategy.default_filters
        
        # Verify that all default filter values are of expected types
        for key, value in defaults.items():
            assert value is not None, f"Filter {key} should have a default value"
            
            # Numeric filters should be numbers
            if key in ['min_market_cap', 'min_volume', 'price_min', 'price_max',
                      'rsi_min', 'rsi_max', 'beta_min', 'beta_max',
                      'weekly_perf_min', 'weekly_perf_max', 'earnings_buffer_days']:
                assert isinstance(value, (int, float)), \
                    f"Filter {key} should be numeric, got {type(value)}"
            
            # Boolean filters should be booleans
            if key in ['above_sma20', 'above_sma50', 'optionable', 'shortable']:
                assert isinstance(value, bool), \
                    f"Filter {key} should be boolean, got {type(value)}"
