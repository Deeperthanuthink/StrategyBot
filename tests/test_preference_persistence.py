"""
Property-based tests for preference persistence.

Feature: strategy-stock-screener, Property 4: Preference Persistence Round-Trip
Validates: Requirements 1.5

For any set of screening parameters, saving preferences then loading them
should return equivalent parameter values.
"""

import pytest
from hypothesis import given, strategies as st, settings
import tempfile
import os
from pathlib import Path
from screener.config.manager import ConfigManager


@settings(max_examples=100)
@given(
    min_market_cap=st.floats(min_value=1e9, max_value=1e12),
    min_volume=st.integers(min_value=100_000, max_value=10_000_000),
    price_min=st.floats(min_value=10, max_value=100),
    price_max=st.floats(min_value=100, max_value=1000),
    rsi_min=st.integers(min_value=0, max_value=50),
    rsi_max=st.integers(min_value=50, max_value=100),
)
def test_preference_round_trip(
    min_market_cap, min_volume, price_min, price_max, rsi_min, rsi_max
):
    """
    Property 4: Preference Persistence Round-Trip
    
    For any set of screening parameters, saving preferences then loading them
    should return equivalent parameter values.
    """
    # Create a temporary config file
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test_config.json"
        
        # Create config manager
        config_manager = ConfigManager(config_path=str(config_path))
        
        # Create test preferences
        test_prefs = {
            'min_market_cap': min_market_cap,
            'min_volume': min_volume,
            'price_min': price_min,
            'price_max': price_max,
            'rsi_min': rsi_min,
            'rsi_max': rsi_max,
        }
        
        # Save preferences
        strategy_name = "TestStrategy"
        config_manager.set(f"preferences.{strategy_name}", test_prefs)
        config_manager.save()
        
        # Load preferences
        loaded_prefs = config_manager.get(f"preferences.{strategy_name}")
        
        # Verify round-trip consistency
        assert loaded_prefs is not None, "Loaded preferences should not be None"
        assert loaded_prefs == test_prefs, \
            "Loaded preferences should match saved preferences"
        
        # Verify each individual value
        assert loaded_prefs['min_market_cap'] == min_market_cap
        assert loaded_prefs['min_volume'] == min_volume
        assert loaded_prefs['price_min'] == price_min
        assert loaded_prefs['price_max'] == price_max
        assert loaded_prefs['rsi_min'] == rsi_min
        assert loaded_prefs['rsi_max'] == rsi_max


@settings(max_examples=100)
@given(
    above_sma20=st.booleans(),
    above_sma50=st.booleans(),
    optionable=st.booleans(),
    shortable=st.booleans(),
)
def test_boolean_preference_round_trip(
    above_sma20, above_sma50, optionable, shortable
):
    """
    Test that boolean preferences are preserved in round-trip.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test_config.json"
        config_manager = ConfigManager(config_path=str(config_path))
        
        # Create test preferences with boolean values
        test_prefs = {
            'above_sma20': above_sma20,
            'above_sma50': above_sma50,
            'optionable': optionable,
            'shortable': shortable,
        }
        
        # Save and load
        strategy_name = "TestStrategy"
        config_manager.set(f"preferences.{strategy_name}", test_prefs)
        config_manager.save()
        
        loaded_prefs = config_manager.get(f"preferences.{strategy_name}")
        
        # Verify boolean values are preserved
        assert loaded_prefs['above_sma20'] == above_sma20
        assert loaded_prefs['above_sma50'] == above_sma50
        assert loaded_prefs['optionable'] == optionable
        assert loaded_prefs['shortable'] == shortable


def test_multiple_strategies_preferences():
    """
    Test that preferences for multiple strategies can be saved independently.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test_config.json"
        config_manager = ConfigManager(config_path=str(config_path))
        
        # Create preferences for different strategies
        pcs_prefs = {
            'min_market_cap': 2e9,
            'min_volume': 1_000_000,
            'price_min': 20,
            'price_max': 200,
        }
        
        covered_call_prefs = {
            'min_market_cap': 5e9,
            'min_volume': 2_000_000,
            'price_min': 50,
            'price_max': 500,
        }
        
        # Save preferences for both strategies
        config_manager.set("preferences.PCS", pcs_prefs)
        config_manager.set("preferences.CoveredCall", covered_call_prefs)
        config_manager.save()
        
        # Load preferences for each strategy
        loaded_pcs = config_manager.get("preferences.PCS")
        loaded_cc = config_manager.get("preferences.CoveredCall")
        
        # Verify both are preserved independently
        assert loaded_pcs == pcs_prefs
        assert loaded_cc == covered_call_prefs
        assert loaded_pcs != loaded_cc


def test_preference_persistence_across_sessions():
    """
    Test that preferences persist across multiple config manager instances.
    
    This simulates closing and reopening the application.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test_config.json"
        
        # First session: save preferences
        config_manager1 = ConfigManager(config_path=str(config_path))
        test_prefs = {
            'min_market_cap': 3e9,
            'min_volume': 1_500_000,
            'rsi_min': 45,
            'rsi_max': 65,
        }
        config_manager1.set("preferences.TestStrategy", test_prefs)
        config_manager1.save()
        
        # Second session: load preferences
        config_manager2 = ConfigManager(config_path=str(config_path))
        loaded_prefs = config_manager2.get("preferences.TestStrategy")
        
        # Verify preferences persisted
        assert loaded_prefs == test_prefs


def test_empty_preferences_handling():
    """
    Test that empty preferences are handled correctly.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test_config.json"
        config_manager = ConfigManager(config_path=str(config_path))
        
        # Try to load preferences that don't exist
        loaded_prefs = config_manager.get("preferences.NonExistentStrategy")
        
        # Should return None for non-existent preferences
        assert loaded_prefs is None


def test_preference_overwrite():
    """
    Test that saving new preferences overwrites old ones.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test_config.json"
        config_manager = ConfigManager(config_path=str(config_path))
        
        # Save initial preferences
        initial_prefs = {'min_market_cap': 2e9, 'min_volume': 1_000_000}
        config_manager.set("preferences.TestStrategy", initial_prefs)
        config_manager.save()
        
        # Save new preferences (overwrite)
        new_prefs = {'min_market_cap': 5e9, 'min_volume': 2_000_000}
        config_manager.set("preferences.TestStrategy", new_prefs)
        config_manager.save()
        
        # Load preferences
        loaded_prefs = config_manager.get("preferences.TestStrategy")
        
        # Should have new values, not old ones
        assert loaded_prefs == new_prefs
        assert loaded_prefs != initial_prefs


@settings(max_examples=100)
@given(
    num_filters=st.integers(min_value=1, max_value=10),
)
def test_variable_number_of_filters(num_filters):
    """
    Test that preferences with varying numbers of filters are handled correctly.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test_config.json"
        config_manager = ConfigManager(config_path=str(config_path))
        
        # Create preferences with variable number of filters
        test_prefs = {}
        for i in range(num_filters):
            test_prefs[f'filter_{i}'] = i * 100
        
        # Save and load
        config_manager.set("preferences.TestStrategy", test_prefs)
        config_manager.save()
        
        loaded_prefs = config_manager.get("preferences.TestStrategy")
        
        # Verify all filters are preserved
        assert len(loaded_prefs) == num_filters
        assert loaded_prefs == test_prefs
