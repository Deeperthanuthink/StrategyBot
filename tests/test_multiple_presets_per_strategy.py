"""Property-based tests for multiple presets per strategy."""

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
})


@settings(max_examples=100)
@given(
    strategy_name=st.sampled_from(['PCS', 'CoveredCall', 'IronCondor', 'Collar']),
    presets=st.lists(
        st.tuples(
            st.text(min_size=1, max_size=30, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
            filter_strategy
        ),
        min_size=2,
        max_size=5,
        unique_by=lambda x: x[0]  # Ensure unique preset names
    )
)
def test_multiple_presets_per_strategy(strategy_name, presets):
    """
    Feature: strategy-stock-screener, Property 24: Multiple Presets Per Strategy
    
    For any strategy, multiple distinct presets should be storable and independently
    retrievable without interference.
    
    Validates: Requirements 7.4
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        presets_path = Path(tmpdir) / "presets.json"
        
        config = ConfigManager(str(config_path), str(presets_path))
        
        # Save all presets
        for preset_name, filters in presets:
            config.save_preset(preset_name, strategy_name, filters)
        
        # Verify all presets can be retrieved independently
        for preset_name, expected_filters in presets:
            loaded_filters = config.load_preset(preset_name, strategy_name)
            assert loaded_filters is not None, f"Preset '{preset_name}' should exist"
            assert loaded_filters == expected_filters, \
                f"Preset '{preset_name}' should return correct filters without interference"
        
        # Verify list_presets returns all preset names
        preset_names = config.list_presets(strategy_name)
        expected_names = [name for name, _ in presets]
        assert set(preset_names) == set(expected_names), \
            f"list_presets should return all saved preset names"


@settings(max_examples=100)
@given(
    presets_by_strategy=st.fixed_dictionaries({
        'PCS': st.lists(
            st.tuples(st.text(min_size=1, max_size=20, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))), filter_strategy),
            min_size=1, max_size=3, unique_by=lambda x: x[0]
        ),
        'CoveredCall': st.lists(
            st.tuples(st.text(min_size=1, max_size=20, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))), filter_strategy),
            min_size=1, max_size=3, unique_by=lambda x: x[0]
        ),
    })
)
def test_presets_isolated_across_strategies(presets_by_strategy):
    """
    Test that presets for different strategies don't interfere with each other.
    
    Validates: Requirements 7.4
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        presets_path = Path(tmpdir) / "presets.json"
        
        config = ConfigManager(str(config_path), str(presets_path))
        
        # Save presets for all strategies
        for strategy_name, presets in presets_by_strategy.items():
            for preset_name, filters in presets:
                config.save_preset(preset_name, strategy_name, filters)
        
        # Verify each strategy's presets are isolated
        for strategy_name, presets in presets_by_strategy.items():
            for preset_name, expected_filters in presets:
                loaded_filters = config.load_preset(preset_name, strategy_name)
                assert loaded_filters == expected_filters, \
                    f"Preset '{preset_name}' for '{strategy_name}' should not be affected by other strategies"
            
            # Verify list_presets only returns presets for this strategy
            preset_names = config.list_presets(strategy_name)
            expected_names = [name for name, _ in presets]
            assert set(preset_names) == set(expected_names), \
                f"list_presets('{strategy_name}') should only return presets for that strategy"


@settings(max_examples=100)
@given(
    strategy_name=st.sampled_from(['PCS', 'CoveredCall', 'IronCondor', 'Collar']),
    preset_name=st.text(min_size=1, max_size=30, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
    filters1=filter_strategy,
    filters2=filter_strategy
)
def test_preset_overwrite(strategy_name, preset_name, filters1, filters2):
    """
    Test that saving a preset with the same name overwrites the previous one.
    
    Validates: Requirements 7.4
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        presets_path = Path(tmpdir) / "presets.json"
        
        config = ConfigManager(str(config_path), str(presets_path))
        
        # Save first version
        config.save_preset(preset_name, strategy_name, filters1)
        
        # Save second version with same name
        config.save_preset(preset_name, strategy_name, filters2)
        
        # Verify only the second version is stored
        loaded_filters = config.load_preset(preset_name, strategy_name)
        assert loaded_filters == filters2, \
            f"Preset should be overwritten with latest save"
        
        # Verify only one preset with this name exists
        preset_names = config.list_presets(strategy_name)
        assert preset_names.count(preset_name) == 1, \
            f"Only one preset with name '{preset_name}' should exist"
