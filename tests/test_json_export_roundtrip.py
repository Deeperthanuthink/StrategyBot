"""Property-based tests for JSON export round-trip consistency.

Feature: strategy-stock-screener, Property 20: Export Round-Trip Consistency
Validates: Requirements 6.4
"""

import tempfile
import shutil
import json
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
def test_json_export_roundtrip_preserves_data(strategy_name, filters, stocks, metadata):
    """
    Feature: strategy-stock-screener, Property 20: Export Round-Trip Consistency
    
    For any screening result set, exporting to JSON then importing should
    produce equivalent data.
    """
    # Create temporary directory for this test
    temp_storage_dir = tempfile.mkdtemp()
    
    try:
        storage = StorageManager(results_dir=temp_storage_dir)
        
        # Create screening results
        original_results = ScreenerResults(
            timestamp=datetime.now(),
            strategy=strategy_name,
            filters=filters,
            stocks=stocks,
            metadata=metadata
        )
        
        # Export to JSON
        json_path = Path(temp_storage_dir) / "export_test.json"
        storage.export_to_json(original_results, str(json_path))
        
        # Verify file exists
        assert json_path.exists(), "JSON export file should exist"
        
        # Import from JSON
        with open(json_path, 'r') as f:
            imported_data = json.load(f)
        
        # Reconstruct ScreenerResults from imported data
        imported_results = ScreenerResults(
            timestamp=datetime.fromisoformat(imported_data['timestamp']),
            strategy=imported_data['strategy'],
            filters=imported_data['filters'],
            stocks=pd.DataFrame(imported_data['stocks']),
            metadata=imported_data.get('metadata', {})
        )
        
        # Verify data matches
        assert imported_results.strategy == original_results.strategy
        assert imported_results.filters == original_results.filters
        assert imported_results.metadata == original_results.metadata
        
        # Verify DataFrame contents match
        assert len(imported_results.stocks) == len(original_results.stocks)
        if len(original_results.stocks) > 0:
            assert list(imported_results.stocks.columns) == list(original_results.stocks.columns)
            
    finally:
        # Clean up temporary directory
        shutil.rmtree(temp_storage_dir)


@settings(max_examples=100)
@given(
    strategy_name=st.sampled_from(['pcs', 'covered_call', 'iron_condor', 'collar']),
    filters=valid_filters_strategy(),
    stocks=valid_stock_dataframe_strategy(),
)
def test_json_export_contains_all_fields(strategy_name, filters, stocks):
    """
    Feature: strategy-stock-screener, Property 20: Export Round-Trip Consistency
    
    For any screening result set, the exported JSON should contain all required
    fields: timestamp, strategy, filters, stocks, metadata.
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
            metadata={'test_key': 'test_value'}
        )
        
        # Export to JSON
        json_path = Path(temp_storage_dir) / "export_test.json"
        storage.export_to_json(results, str(json_path))
        
        # Load and verify JSON structure
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # Verify all required fields are present
        assert 'timestamp' in data, "JSON should contain timestamp"
        assert 'strategy' in data, "JSON should contain strategy"
        assert 'filters' in data, "JSON should contain filters"
        assert 'stocks' in data, "JSON should contain stocks"
        assert 'metadata' in data, "JSON should contain metadata"
        
        # Verify field values
        assert data['strategy'] == strategy_name
        assert data['filters'] == filters
        assert isinstance(data['stocks'], list)
        
    finally:
        # Clean up temporary directory
        shutil.rmtree(temp_storage_dir)
