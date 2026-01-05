"""Property-based tests for preset round-trip consistency."""

import pytest
import tempfile
from pathlib import Path
from hypothesis import given, strategies as st, settings
from screener.config import ConfigManager


# Strategy for generating filter dictionaries
filter_strategy = st.fixed_dictionaries({
    'min_market_cap': st.floats(min_value=1e6, max_value=1e12, allow_nan=False, allow_infinity=False),
    'min_volume': st.integers(min_value=100000, max_value=100000000),
    'price_min': st.floats(min_value=1.0, max_value=500.0, allow_nan=False, allow_infinity=False),
    'price_max': st.floats(min_value=1.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    'rsi_min': st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    'rsi_max': st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    'beta_min': st.floats(min_value=0.0, max_value=3.0, allow_nan=False, allow_infinity=False),
    'beta_max': st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False),
})


@settings(max_examples=100)
@given(
    preset_name=st.text(min_size=1, max_size=50, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
    strategy_name=st.sampled_from(['PCS', 'CoveredCall', 'IronCondor', 'Collar']),
    filters=filter_strategy
)
def test_preset_roundtrip_consistency(preset_name, strategy_name, filters):
    """
    Feature: strategy-stock-screener, Property 23: Preset Round-Trip Consistency
    
    For any parameter configuration, saving as a named preset then loading that preset
    should return equivalent parameters.
    
    Validates: Requirements 7.2, 7.3
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        presets_path = Path(tmpdir) / "presets.json"
        
        config = ConfigManager(str(config_path), str(presets_path))
        
        # Save preset
        config.save_preset(preset_name, strategy_name, filters)
        
        # Load preset
        loaded_filters = config.load_preset(preset_name, strategy_name)
        
        # Verify round-trip consistency
        assert loaded_filters is not None, f"Preset '{preset_name}' for strategy '{strategy_name}' should exist"
        assert loaded_filters == filters, f"Loaded filters should match saved filters"


@settings(max_examples=100)
@given(
    preset_name=st.text(min_size=1, max_size=50, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
    strategy_name=st.sampled_from(['PCS', 'CoveredCall', 'IronCondor', 'Collar']),
    filters=filter_strategy
)
def test_preset_persistence_across_instances(preset_name, strategy_name, filters):
    """
    Test that presets persist across ConfigManager instances.
    
    Validates: Requirements 7.2, 7.3
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        presets_path = Path(tmpdir) / "presets.json"
        
        # Save preset with first instance
        config1 = ConfigManager(str(config_path), str(presets_path))
        config1.save_preset(preset_name, strategy_name, filters)
        
        # Load preset with second instance
        config2 = ConfigManager(str(config_path), str(presets_path))
        loaded_filters = config2.load_preset(preset_name, strategy_name)
        
        # Verify persistence
        assert loaded_filters is not None
        assert loaded_filters == filters


@settings(max_examples=100)
@given(
    filters=filter_strategy
)
def test_preset_with_special_characters_in_name(filters):
    """
    Test that presets work with various valid preset names.
    
    Validates: Requirements 7.2, 7.3
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        presets_path = Path(tmpdir) / "presets.json"
        
        config = ConfigManager(str(config_path), str(presets_path))
        
        # Test with various preset names
        test_names = ["aggressive", "conservative-v2", "test_preset", "preset.1"]
        
        for preset_name in test_names:
            config.save_preset(preset_name, "PCS", filters)
            loaded = config.load_preset(preset_name, "PCS")
            assert loaded == filters, f"Round-trip failed for preset name: {preset_name}"
