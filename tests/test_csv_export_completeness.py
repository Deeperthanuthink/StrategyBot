"""Property-based tests for CSV export completeness.

Feature: strategy-stock-screener, Property 21: CSV Export Completeness
Validates: Requirements 6.3
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
    })


def valid_stock_dataframe_strategy():
    """Generate valid stock DataFrames with multiple columns."""
    return st.builds(
        lambda rows: pd.DataFrame(rows),
        st.lists(
            st.fixed_dictionaries({
                'ticker': st.text(min_size=1, max_size=5, alphabet=st.characters(whitelist_categories=('Lu',))),
                'price': st.floats(min_value=1, max_value=1000, allow_nan=False, allow_infinity=False),
                'volume': st.integers(min_value=0, max_value=1_000_000_000),
                'score': st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
                'market_cap': st.floats(min_value=1e6, max_value=1e12, allow_nan=False, allow_infinity=False),
                'rsi': st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
            }),
            min_size=1,  # At least one row to test columns
            max_size=10
        )
    )


@settings(max_examples=100)
@given(
    strategy_name=st.sampled_from(['pcs', 'covered_call', 'iron_condor', 'collar']),
    filters=valid_filters_strategy(),
    stocks=valid_stock_dataframe_strategy(),
)
def test_csv_export_contains_all_columns(strategy_name, filters, stocks):
    """
    Feature: strategy-stock-screener, Property 21: CSV Export Completeness
    
    For any screening result set, the exported CSV should contain all stock
    data columns and analysis metrics.
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
            metadata={}
        )
        
        # Export to CSV
        csv_path = Path(temp_storage_dir) / "export_test.csv"
        storage.export_to_csv(results, str(csv_path))
        
        # Verify file exists
        assert csv_path.exists(), "CSV export file should exist"
        
        # Load CSV and verify columns
        imported_df = pd.read_csv(csv_path)
        
        # Verify all original columns are present
        original_columns = set(stocks.columns)
        imported_columns = set(imported_df.columns)
        
        assert original_columns == imported_columns, \
            f"CSV should contain all columns. Missing: {original_columns - imported_columns}"
        
        # Verify row count matches
        assert len(imported_df) == len(stocks), \
            f"CSV should contain all rows. Expected {len(stocks)}, got {len(imported_df)}"
        
    finally:
        # Clean up temporary directory
        shutil.rmtree(temp_storage_dir)


@settings(max_examples=100)
@given(
    strategy_name=st.sampled_from(['pcs', 'covered_call', 'iron_condor', 'collar']),
    filters=valid_filters_strategy(),
    stocks=valid_stock_dataframe_strategy(),
)
def test_csv_export_preserves_data_structure(strategy_name, filters, stocks):
    """
    Feature: strategy-stock-screener, Property 21: CSV Export Completeness
    
    For any screening result set, the exported CSV should preserve the data
    structure (columns and row count).
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
            metadata={}
        )
        
        # Export to CSV
        csv_path = Path(temp_storage_dir) / "export_test.csv"
        storage.export_to_csv(results, str(csv_path))
        
        # Load CSV
        imported_df = pd.read_csv(csv_path)
        
        # Verify structure matches
        assert list(imported_df.columns) == list(stocks.columns), \
            "CSV should have same columns as original"
        assert len(imported_df) == len(stocks), \
            "CSV should have same number of rows as original"
        
        # Verify numeric columns preserve values (within reasonable precision)
        for col in stocks.columns:
            if stocks[col].dtype in ['float64', 'float32', 'int64', 'int32']:
                # For numeric columns, verify values are close
                original_values = stocks[col].values
                imported_values = imported_df[col].values
                
                for i, (orig, imp) in enumerate(zip(original_values, imported_values)):
                    if orig != 0:
                        relative_error = abs((imp - orig) / orig)
                        assert relative_error < 0.001, \
                            f"Column {col} row {i}: relative error {relative_error} too large"
                    else:
                        assert abs(imp - orig) < 1e-6, \
                            f"Column {col} row {i}: absolute error too large for zero value"
        
    finally:
        # Clean up temporary directory
        shutil.rmtree(temp_storage_dir)


@settings(max_examples=100)
@given(
    strategy_name=st.sampled_from(['pcs', 'covered_call', 'iron_condor', 'collar']),
    filters=valid_filters_strategy(),
)
def test_csv_export_handles_empty_dataframe(strategy_name, filters):
    """
    Feature: strategy-stock-screener, Property 21: CSV Export Completeness
    
    For any screening result set with no stocks, the exported CSV should
    still be valid (with headers but no data rows).
    """
    # Create temporary directory for this test
    temp_storage_dir = tempfile.mkdtemp()
    
    try:
        storage = StorageManager(results_dir=temp_storage_dir)
        
        # Create screening results with empty DataFrame
        empty_stocks = pd.DataFrame(columns=['ticker', 'price', 'volume', 'score'])
        results = ScreenerResults(
            timestamp=datetime.now(),
            strategy=strategy_name,
            filters=filters,
            stocks=empty_stocks,
            metadata={}
        )
        
        # Export to CSV
        csv_path = Path(temp_storage_dir) / "export_test.csv"
        storage.export_to_csv(results, str(csv_path))
        
        # Verify file exists
        assert csv_path.exists(), "CSV export file should exist even for empty results"
        
        # Load CSV
        imported_df = pd.read_csv(csv_path)
        
        # Verify it has the correct columns but no rows
        assert list(imported_df.columns) == list(empty_stocks.columns), \
            "CSV should have correct column headers"
        assert len(imported_df) == 0, "CSV should have no data rows"
        
    finally:
        # Clean up temporary directory
        shutil.rmtree(temp_storage_dir)
