"""Property-based tests for history log maintenance.

Feature: strategy-stock-screener, Property 22: History Log Maintenance
Validates: Requirements 6.5
"""

import tempfile
import shutil
from datetime import datetime, timedelta
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
    })


def valid_stock_dataframe_strategy():
    """Generate valid stock DataFrames."""
    return st.builds(
        lambda rows: pd.DataFrame(rows),
        st.lists(
            st.fixed_dictionaries({
                'ticker': st.text(min_size=1, max_size=5, alphabet=st.characters(whitelist_categories=('Lu',))),
                'price': st.floats(min_value=1, max_value=1000, allow_nan=False, allow_infinity=False),
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
)
def test_save_results_adds_history_entry(strategy_name, filters, stocks):
    """
    Feature: strategy-stock-screener, Property 22: History Log Maintenance
    
    For any screening operation, an entry should be added to the history log
    containing timestamp, strategy name, filter parameters, and result count.
    """
    # Create temporary directory for this test
    temp_storage_dir = tempfile.mkdtemp()
    
    try:
        storage = StorageManager(results_dir=temp_storage_dir)
        
        # Create and save screening results
        results = ScreenerResults(
            timestamp=datetime.now(),
            strategy=strategy_name,
            filters=filters,
            stocks=stocks,
            metadata={}
        )
        
        result_id = storage.save_results(results, strategy_name)
        
        # Get history
        history = storage.get_history()
        
        # Verify history contains at least one entry
        assert len(history) > 0, "History should contain at least one entry"
        
        # Verify the most recent entry matches our save
        latest_entry = history[0]
        assert latest_entry['id'] == result_id, "Latest entry ID should match result ID"
        assert latest_entry['strategy'] == strategy_name, "Latest entry strategy should match"
        assert latest_entry['num_results'] == len(stocks), "Latest entry result count should match"
        assert 'timestamp' in latest_entry, "History entry should contain timestamp"
        assert 'filters_summary' in latest_entry, "History entry should contain filters summary"
        
    finally:
        # Clean up temporary directory
        shutil.rmtree(temp_storage_dir)


@settings(max_examples=100)
@given(
    num_saves=st.integers(min_value=1, max_value=10),
    strategy_name=st.sampled_from(['pcs', 'covered_call', 'iron_condor', 'collar']),
    filters=valid_filters_strategy(),
)
def test_history_maintains_multiple_entries(num_saves, strategy_name, filters):
    """
    Feature: strategy-stock-screener, Property 22: History Log Maintenance
    
    For any number of screening operations, the history log should maintain
    all entries.
    """
    # Create temporary directory for this test
    temp_storage_dir = tempfile.mkdtemp()
    
    try:
        storage = StorageManager(results_dir=temp_storage_dir)
        
        # Save multiple results
        for i in range(num_saves):
            stocks = pd.DataFrame({'ticker': [f'STOCK{i}'], 'price': [100.0]})
            results = ScreenerResults(
                timestamp=datetime.now() + timedelta(seconds=i),
                strategy=strategy_name,
                filters=filters,
                stocks=stocks,
                metadata={}
            )
            storage.save_results(results, strategy_name)
        
        # Get history
        history = storage.get_history()
        
        # Verify history contains all entries
        assert len(history) == num_saves, \
            f"History should contain {num_saves} entries, got {len(history)}"
        
    finally:
        # Clean up temporary directory
        shutil.rmtree(temp_storage_dir)


@settings(max_examples=100)
@given(
    limit=st.integers(min_value=1, max_value=20),
    strategy_name=st.sampled_from(['pcs', 'covered_call', 'iron_condor', 'collar']),
    filters=valid_filters_strategy(),
)
def test_history_respects_limit(limit, strategy_name, filters):
    """
    Feature: strategy-stock-screener, Property 22: History Log Maintenance
    
    For any limit parameter, get_history should return at most that many entries.
    """
    # Create temporary directory for this test
    temp_storage_dir = tempfile.mkdtemp()
    
    try:
        storage = StorageManager(results_dir=temp_storage_dir)
        
        # Save more results than the limit
        num_saves = limit + 5
        for i in range(num_saves):
            stocks = pd.DataFrame({'ticker': [f'STOCK{i}'], 'price': [100.0]})
            results = ScreenerResults(
                timestamp=datetime.now() + timedelta(seconds=i),
                strategy=strategy_name,
                filters=filters,
                stocks=stocks,
                metadata={}
            )
            storage.save_results(results, strategy_name)
        
        # Get history with limit
        history = storage.get_history(limit=limit)
        
        # Verify history respects limit
        assert len(history) <= limit, \
            f"History should contain at most {limit} entries, got {len(history)}"
        
    finally:
        # Clean up temporary directory
        shutil.rmtree(temp_storage_dir)


@settings(max_examples=100)
@given(
    strategy_name=st.sampled_from(['pcs', 'covered_call', 'iron_condor', 'collar']),
    filters=valid_filters_strategy(),
)
def test_history_sorted_by_timestamp_descending(strategy_name, filters):
    """
    Feature: strategy-stock-screener, Property 22: History Log Maintenance
    
    For any history log, entries should be sorted by timestamp in descending
    order (most recent first).
    """
    # Create temporary directory for this test
    temp_storage_dir = tempfile.mkdtemp()
    
    try:
        storage = StorageManager(results_dir=temp_storage_dir)
        
        # Save multiple results with different timestamps
        timestamps = []
        for i in range(5):
            timestamp = datetime.now() + timedelta(seconds=i)
            timestamps.append(timestamp)
            stocks = pd.DataFrame({'ticker': [f'STOCK{i}'], 'price': [100.0]})
            results = ScreenerResults(
                timestamp=timestamp,
                strategy=strategy_name,
                filters=filters,
                stocks=stocks,
                metadata={}
            )
            storage.save_results(results, strategy_name)
        
        # Get history
        history = storage.get_history()
        
        # Verify history is sorted by timestamp descending
        for i in range(len(history) - 1):
            current_ts = datetime.fromisoformat(history[i]['timestamp'])
            next_ts = datetime.fromisoformat(history[i + 1]['timestamp'])
            assert current_ts >= next_ts, \
                "History should be sorted by timestamp descending (most recent first)"
        
    finally:
        # Clean up temporary directory
        shutil.rmtree(temp_storage_dir)
