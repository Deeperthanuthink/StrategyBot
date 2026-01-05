"""Property-based tests for Finviz filter application.

Feature: strategy-stock-screener, Property 6: Filter Application Correctness
Validates: Requirements 2.2
"""

from hypothesis import given, strategies as st, settings, assume
import pytest
import pandas as pd

from screener.finviz import FinvizClient, FinvizCredentials, FINVIZ_FILTER_MAP


def filter_key_strategy():
    """Generate valid filter keys from FINVIZ_FILTER_MAP."""
    return st.sampled_from(list(FINVIZ_FILTER_MAP.keys()))


@settings(max_examples=100)
@given(
    filter_keys=st.lists(filter_key_strategy(), min_size=1, max_size=5, unique=True),
)
def test_filter_translation_correctness(filter_keys):
    """
    Feature: strategy-stock-screener, Property 6: Filter Application Correctness
    
    For any configured filter set, the translation to Finviz parameters should
    correctly map internal filter names to Finviz filter codes.
    """
    credentials = FinvizCredentials(email="test@example.com", password="testpass123")
    client = FinvizClient(credentials=credentials)
    
    # Create filter dict with all values set to True (for boolean filters)
    filters = {key: True for key in filter_keys}
    
    # Translate filters
    finviz_filters = client._translate_filters(filters)
    
    # Verify all filters were translated
    for key in filter_keys:
        expected_finviz_key = FINVIZ_FILTER_MAP[key]
        assert expected_finviz_key in finviz_filters or key in finviz_filters, \
            f"Filter {key} should be translated to {expected_finviz_key}"


@settings(max_examples=100)
@given(
    filter_dict=st.dictionaries(
        keys=filter_key_strategy(),
        values=st.booleans(),
        min_size=1,
        max_size=10
    )
)
def test_filter_translation_respects_boolean_values(filter_dict):
    """
    Feature: strategy-stock-screener, Property 6: Filter Application Correctness
    
    For any filter configuration, only filters with truthy values should be
    included in the translated Finviz parameters.
    """
    credentials = FinvizCredentials(email="test@example.com", password="testpass123")
    client = FinvizClient(credentials=credentials)
    
    # Translate filters
    finviz_filters = client._translate_filters(filter_dict)
    
    # Count how many filters should be included (truthy values)
    expected_count = sum(1 for v in filter_dict.values() if v)
    
    # Verify only truthy filters are included
    assert len(finviz_filters) == expected_count, \
        f"Expected {expected_count} filters, got {len(finviz_filters)}"
    
    # Verify all included filters had truthy values
    for key, value in filter_dict.items():
        finviz_key = FINVIZ_FILTER_MAP[key]
        if value:
            assert finviz_key in finviz_filters, \
                f"Truthy filter {key} should be in translated filters"
        else:
            assert finviz_key not in finviz_filters, \
                f"Falsy filter {key} should not be in translated filters"


def test_unmapped_filters_pass_through():
    """
    Test that unmapped filters (already in Finviz format) pass through unchanged.
    """
    credentials = FinvizCredentials(email="test@example.com", password="testpass123")
    client = FinvizClient(credentials=credentials)
    
    # Mix of mapped and unmapped filters
    filters = {
        "optionable": True,  # Mapped
        "custom_finviz_filter": "some_value",  # Unmapped
        "another_custom": True,  # Unmapped
    }
    
    finviz_filters = client._translate_filters(filters)
    
    # Mapped filter should be translated
    assert "sh_opt_option" in finviz_filters
    
    # Unmapped filters should pass through
    assert "custom_finviz_filter" in finviz_filters
    assert finviz_filters["custom_finviz_filter"] == "some_value"
    assert "another_custom" in finviz_filters


def test_empty_filters_returns_empty_dict():
    """
    Test that empty filter dict returns empty translated dict.
    """
    credentials = FinvizCredentials(email="test@example.com", password="testpass123")
    client = FinvizClient(credentials=credentials)
    
    finviz_filters = client._translate_filters({})
    
    assert finviz_filters == {}
    assert len(finviz_filters) == 0


@settings(max_examples=50)
@given(
    num_filters=st.integers(min_value=1, max_value=20),
)
def test_multiple_filters_all_translated(num_filters):
    """
    Feature: strategy-stock-screener, Property 6: Filter Application Correctness
    
    For any number of filters, all should be correctly translated to Finviz format.
    """
    credentials = FinvizCredentials(email="test@example.com", password="testpass123")
    client = FinvizClient(credentials=credentials)
    
    # Select random filters from the map
    all_keys = list(FINVIZ_FILTER_MAP.keys())
    assume(len(all_keys) >= num_filters)
    
    import random
    selected_keys = random.sample(all_keys, min(num_filters, len(all_keys)))
    
    filters = {key: True for key in selected_keys}
    finviz_filters = client._translate_filters(filters)
    
    # All filters should be translated
    assert len(finviz_filters) == len(selected_keys)
    
    # Each filter should map correctly
    for key in selected_keys:
        expected_finviz_key = FINVIZ_FILTER_MAP[key]
        assert expected_finviz_key in finviz_filters
