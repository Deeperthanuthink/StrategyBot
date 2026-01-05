"""Property-based tests for results persistence.

Feature: strategy-stock-screener, Property 18: Results Persistence
Validates: Requirements 6.1
"""

import tempfile
import shutil
from pathlib import Path
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
def test_save_results_creates_files(strategy_name, filters, stocks, metadata):
    """
    Feature: strategy-stock-screener, Property 18: Results Persistence
    
    For any completed screening operation, the results should be saved to local
    storage with a timestamp.
    """
    # Create temporary directory for this test
    temp_storage_dir = tempfile.mkdtemp()
    
    try:
        storage = StorageManager(results_dir=temp_storage_dir)
        
        # Create screening results
        results = ScreenerResults(
            timestamp=datetime.now(),
            strategy=strategy_name,
            filters=filters,
            stocks=stocks,
            metadata=metadata
        )
        
        # Save results
        result_id = storage.save_results(results, strategy_name)
        
        # Verify result ID is returned
        assert result_id is not None
        assert isinstance(result_id, str)
        assert len(result_id) > 0
        
        # Verify JSON file exists
        json_path = Path(temp_storage_dir) / f"{result_id}.json"
        assert json_path.exists(), f"JSON file should exist at {json_path}"
        
        # Verify CSV file exists
        csv_path = Path(temp_storage_dir) / f"{result_id}.csv"
        assert csv_path.exists(), f"CSV file should exist at {csv_path}"
        
        # Verify history file exists
        history_path = Path(temp_storage_dir) / "screener_history.json"
        assert history_path.exists(), "History file should exist"
    finally:
        # Clean up temporary directory
        shutil.rmtree(temp_storage_dir)


@settings(max_examples=100)
@given(
    strategy_name=st.sampled_from(['pcs', 'covered_call', 'iron_condor', 'collar']),
    filters=valid_filters_strategy(),
    stocks=valid_stock_dataframe_strategy(),
)
def test_save_results_includes_timestamp(strategy_name, filters, stocks):
    """
    Feature: strategy-stock-screener, Property 18: Results Persistence
    
    For any saved screening results, the result ID should include a timestamp.
    """
    # Create temporary directory for this test
    temp_storage_dir = tempfile.mkdtemp()
    
    try:
        storage = StorageManager(results_dir=temp_storage_dir)
        
        # Create screening results with specific timestamp
        timestamp = datetime(2025, 1, 4, 14, 30, 45)
        results = ScreenerResults(
            timestamp=timestamp,
            strategy=strategy_name,
            filters=filters,
            stocks=stocks,
            metadata={}
        )
        
        # Save results
        result_id = storage.save_results(results, strategy_name)
        
        # Verify result ID contains timestamp
        assert "2025-01-04" in result_id, "Result ID should contain date"
        assert strategy_name in result_id, "Result ID should contain strategy name"
    finally:
        # Clean up temporary directory
        shutil.rmtree(temp_storage_dir)
