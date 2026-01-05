"""Property-based tests for historical results retrieval.

Feature: strategy-stock-screener, Property 19: Historical Results Retrieval
Validates: Requirements 6.2
"""

import tempfile
import shutil
from datetime import datetime
from hypothesis import given, strategies as st, settings
import pytest
import pandas as pd

from screener.core.models import ScreenerResults
from screener.storage import StorageManager


def valid_filters_strategy():
    """Generate valid filter dictionaries."""
    return st.fixed_dictionaries({
        'min_market_cap': st.floats(min_value=0, max_value=1e12, allow_nan=False, allow_infinity=False),
        'min_volume': st.integers(min_value=0, max_value=1_000_000_000),
        'price_min': st.floats(min_value=1, max_value=1000, allow_nan=False, allow_infinity=False),
        'price_max': st.floats(min_value=1, max_value=1000, allow_nan=False, allow_infinity=False),
    })


def valid_stock_dataframe_strategy():
    """Generate valid stock DataFrames."""
    return st.builds(
        lambda rows: pd.DataFrame(rows),
        st.lists(
            st.fixed_dictionaries({
                'ticker': st.text(min_size=1, max_size=5, alphabet=st.characters(whitelist_categories=('Lu',))),
                'price': st.floats(min_value=1, max_value=1000, allow_nan=False, allow_infinity=False),
                'volume': st.integers(min_value=0, max_value=1_000_000_000),
                'score': st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
            }),
            min_size=0,
            max_size=10
        )
    )


@settings(max_examples=100)
@given(
    strategy_name=st.sampled_from(['pcs', 'covered_call', 'iron_condor', 'collar']),
    filters=valid_filters_strategy(),
    stocks=valid_stock_dataframe_strategy(),
    metadata=st.dictionaries(
        st.text(min_size=1, max_size=20),
        st.one_of(st.text(max_size=50), st.integers(), st.floats(allow_nan=False, allow_infinity=False)),
        max_size=5
    )
)
def test_load_results_retrieves_saved_data(strategy_name, filters, stocks, metadata):
    """
    Feature: strategy-stock-screener, Property 19: Historical Results Retrieval
    
    For any saved screening session, requesting it by ID should return the
    complete saved results.
    """
    # Create temporary directory for this test
    temp_storage_dir = tempfile.mkdtemp()
    
    try:
        storage = StorageManager(results_dir=temp_storage_dir)
        
        # Create and save screening results
        original_results = ScreenerResults(
            timestamp=datetime.now(),
            strategy=strategy_name,
            filters=filters,
            stocks=stocks,
            metadata=metadata
        )
        
        result_id = storage.save_results(original_results, strategy_name)
        
        # Load results by ID
        loaded_results = storage.load_results(result_id)
        
        # Verify loaded results match original
        assert loaded_results.strategy == original_results.strategy
        assert loaded_results.filters == original_results.filters
        assert loaded_results.metadata == original_results.metadata
        
        # Verify DataFrame contents match
        assert len(loaded_results.stocks) == len(original_results.stocks)
        if len(original_results.stocks) > 0:
            assert list(loaded_results.stocks.columns) == list(original_results.stocks.columns)
            
    finally:
        # Clean up temporary directory
        shutil.rmtree(temp_storage_dir)


@settings(max_examples=100)
@given(
    result_id=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), blacklist_characters='/')),
)
def test_load_nonexistent_results_raises_error(result_id):
    """
    Feature: strategy-stock-screener, Property 19: Historical Results Retrieval
    
    For any non-existent result ID, attempting to load should raise FileNotFoundError.
    """
    # Create temporary directory for this test
    temp_storage_dir = tempfile.mkdtemp()
    
    try:
        storage = StorageManager(results_dir=temp_storage_dir)
        
        # Attempt to load non-existent results
        with pytest.raises(FileNotFoundError):
            storage.load_results(result_id)
            
    finally:
        # Clean up temporary directory
        shutil.rmtree(temp_storage_dir)


@settings(max_examples=100)
@given(
    strategy_name=st.sampled_from(['pcs', 'covered_call', 'iron_condor', 'collar']),
    filters=valid_filters_strategy(),
    stocks=valid_stock_dataframe_strategy(),
)
def test_load_results_preserves_timestamp(strategy_name, filters, stocks):
    """
    Feature: strategy-stock-screener, Property 19: Historical Results Retrieval
    
    For any saved screening session, the loaded results should preserve the
    original timestamp.
    """
    # Create temporary directory for this test
    temp_storage_dir = tempfile.mkdtemp()
    
    try:
        storage = StorageManager(results_dir=temp_storage_dir)
        
        # Create screening results with specific timestamp
        original_timestamp = datetime(2025, 1, 4, 15, 30, 45)
        original_results = ScreenerResults(
            timestamp=original_timestamp,
            strategy=strategy_name,
            filters=filters,
            stocks=stocks,
            metadata={}
        )
        
        result_id = storage.save_results(original_results, strategy_name)
        
        # Load results
        loaded_results = storage.load_results(result_id)
        
        # Verify timestamp is preserved
        assert loaded_results.timestamp == original_timestamp
        
    finally:
        # Clean up temporary directory
        shutil.rmtree(temp_storage_dir)
