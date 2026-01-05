"""Property-based tests for parameter range validation."""

import pytest
import tempfile
from pathlib import Path
from hypothesis import given, strategies as st, settings, assume
from screener.config import ConfigManager, ValidationError


@settings(max_examples=100)
@given(
    param_name=st.sampled_from([
        'min_market_cap', 'max_market_cap', 'min_volume', 'max_volume',
        'price_min', 'price_max', 'rsi_min', 'rsi_max',
        'beta_min', 'beta_max', 'iv_rank_min', 'iv_rank_max',
        'weekly_perf_min', 'weekly_perf_max', 'earnings_buffer_days'
    ]),
    value=st.floats(min_value=-1e15, max_value=1e15, allow_nan=False, allow_infinity=False)
)
def test_parameter_range_validation(param_name, value):
    """
    Feature: strategy-stock-screener, Property 25: Parameter Range Validation
    
    For any numeric parameter, values outside the valid range should be rejected
    with a clear error message.
    
    Validates: Requirements 7.6, 8.3
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        presets_path = Path(tmpdir) / "presets.json"
        
        config = ConfigManager(str(config_path), str(presets_path))
        
        # Get the valid range for this parameter
        min_val, max_val = config.PARAMETER_RANGES[param_name]
        
        filters = {param_name: value}
        
        # Validate
        errors = config.validate_parameters(filters)
        
        # Check if value is within range
        if min_val <= value <= max_val:
            # Should have no errors
            assert len(errors) == 0, \
                f"Valid value {value} for '{param_name}' should not produce errors"
        else:
            # Should have an error
            assert len(errors) > 0, \
                f"Invalid value {value} for '{param_name}' should produce an error"
            
            # Error message should mention the parameter name and range
            error_msg = errors[0]
            assert param_name in error_msg, \
                f"Error message should mention parameter name '{param_name}'"
            assert str(min_val) in error_msg or str(max_val) in error_msg, \
                f"Error message should mention valid range"


@settings(max_examples=100)
@given(
    param_name=st.sampled_from([
        'min_market_cap', 'rsi_min', 'beta_min', 'price_min'
    ]),
    value=st.one_of(
        st.text(min_size=1, max_size=20),
        st.booleans(),
        st.none(),
        st.lists(st.integers()),
    )
)
def test_non_numeric_parameter_rejection(param_name, value):
    """
    Test that non-numeric values are rejected with clear error messages.
    
    Validates: Requirements 7.6, 8.3
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        presets_path = Path(tmpdir) / "presets.json"
        
        config = ConfigManager(str(config_path), str(presets_path))
        
        filters = {param_name: value}
        
        # Validate
        errors = config.validate_parameters(filters)
        
        # Should have an error about non-numeric type
        assert len(errors) > 0, \
            f"Non-numeric value {value} for '{param_name}' should produce an error"
        
        error_msg = errors[0]
        assert param_name in error_msg, \
            f"Error message should mention parameter name '{param_name}'"
        assert "numeric" in error_msg.lower(), \
            f"Error message should mention that value must be numeric"


@settings(max_examples=100)
@given(
    strategy_name=st.sampled_from(['PCS', 'CoveredCall', 'IronCondor', 'Collar']),
    preset_name=st.text(min_size=1, max_size=30, alphabet=st.characters(blacklist_categories=('Cs', 'Cc'))),
    invalid_value=st.floats(min_value=200, max_value=1000, allow_nan=False, allow_infinity=False)
)
def test_save_preset_with_invalid_parameters_raises_error(strategy_name, preset_name, invalid_value):
    """
    Test that saving a preset with invalid parameters raises ValidationError.
    
    Validates: Requirements 7.6, 8.3
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        presets_path = Path(tmpdir) / "presets.json"
        
        config = ConfigManager(str(config_path), str(presets_path))
        
        # Create filters with an out-of-range RSI value (valid range is 0-100)
        filters = {
            'rsi_min': invalid_value,  # Invalid: > 100
            'min_volume': 1000000
        }
        
        # Should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            config.save_preset(preset_name, strategy_name, filters)
        
        # Error message should be clear
        error_msg = str(exc_info.value)
        assert 'rsi_min' in error_msg, \
            f"Error message should mention the invalid parameter 'rsi_min'"


@settings(max_examples=100)
@given(
    filters=st.fixed_dictionaries({
        'min_market_cap': st.floats(min_value=1e6, max_value=1e12, allow_nan=False, allow_infinity=False),
        'min_volume': st.integers(min_value=100000, max_value=100000000),
        'rsi_min': st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
        'rsi_max': st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
    })
)
def test_valid_parameters_pass_validation(filters):
    """
    Test that valid parameters pass validation without errors.
    
    Validates: Requirements 7.6, 8.3
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        presets_path = Path(tmpdir) / "presets.json"
        
        config = ConfigManager(str(config_path), str(presets_path))
        
        # Validate
        errors = config.validate_parameters(filters)
        
        # Should have no errors
        assert len(errors) == 0, \
            f"Valid parameters should not produce validation errors: {errors}"


@settings(max_examples=100)
@given(
    filters=st.dictionaries(
        keys=st.sampled_from(['min_market_cap', 'rsi_min', 'beta_min', 'price_min']),
        values=st.floats(min_value=-1e10, max_value=1e10, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=4
    )
)
def test_multiple_parameter_validation_errors(filters):
    """
    Test that validation returns errors for all invalid parameters.
    
    Validates: Requirements 7.6, 8.3
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        presets_path = Path(tmpdir) / "presets.json"
        
        config = ConfigManager(str(config_path), str(presets_path))
        
        # Count how many parameters are out of range
        expected_errors = 0
        for param_name, value in filters.items():
            min_val, max_val = config.PARAMETER_RANGES[param_name]
            if value < min_val or value > max_val:
                expected_errors += 1
        
        # Validate
        errors = config.validate_parameters(filters)
        
        # Should have the expected number of errors
        assert len(errors) == expected_errors, \
            f"Expected {expected_errors} validation errors, got {len(errors)}"
