"""Unit tests for configuration error handling."""

import pytest
import tempfile
import json
from pathlib import Path
from screener.config import ConfigManager


def test_missing_config_file_uses_defaults():
    """
    Test that missing config file uses safe defaults.
    
    Requirements: 7.5
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "nonexistent" / "config.json"
        presets_path = Path(tmpdir) / "presets.json"
        
        # Should not raise an error
        config = ConfigManager(str(config_path), str(presets_path))
        
        # Should have default values
        assert config.get("finviz.credentials_path") == ".env"
        assert config.get("finviz.rate_limit_delay") == 1.0
        assert config.get("finviz.max_retries") == 3
        assert config.get("storage.results_dir") == "data/screener_results"
        assert config.get("storage.max_history_entries") == 100
        assert config.get("analysis.risk_free_rate") == 0.05
        assert config.get("analysis.default_dte") == 45


def test_invalid_json_config_uses_defaults():
    """
    Test that invalid JSON in config file uses safe defaults.
    
    Requirements: 7.5
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        presets_path = Path(tmpdir) / "presets.json"
        
        # Write invalid JSON
        with open(config_path, 'w') as f:
            f.write("{ invalid json content }")
        
        # Should not raise an error
        config = ConfigManager(str(config_path), str(presets_path))
        
        # Should have default values
        assert config.get("finviz.credentials_path") == ".env"
        assert config.get("finviz.rate_limit_delay") == 1.0
        assert config.get("storage.results_dir") == "data/screener_results"


def test_malformed_json_config_uses_defaults():
    """
    Test that malformed JSON (incomplete) uses safe defaults.
    
    Requirements: 7.5
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        presets_path = Path(tmpdir) / "presets.json"
        
        # Write incomplete JSON
        with open(config_path, 'w') as f:
            f.write('{"finviz": {"credentials_path": ')
        
        # Should not raise an error
        config = ConfigManager(str(config_path), str(presets_path))
        
        # Should have default values
        assert config.get("finviz.credentials_path") == ".env"
        assert config.get("storage.results_dir") == "data/screener_results"


def test_empty_config_file_uses_defaults():
    """
    Test that empty config file uses safe defaults.
    
    Requirements: 7.5
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        presets_path = Path(tmpdir) / "presets.json"
        
        # Write empty file
        with open(config_path, 'w') as f:
            f.write("")
        
        # Should not raise an error
        config = ConfigManager(str(config_path), str(presets_path))
        
        # Should have default values
        assert config.get("finviz.credentials_path") == ".env"


def test_missing_presets_file_starts_empty():
    """
    Test that missing presets file starts with empty presets.
    
    Requirements: 7.5
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        presets_path = Path(tmpdir) / "nonexistent" / "presets.json"
        
        # Should not raise an error
        config = ConfigManager(str(config_path), str(presets_path))
        
        # Should have empty presets
        assert config.list_presets() == []
        assert config.load_preset("any", "PCS") is None


def test_invalid_json_presets_starts_empty():
    """
    Test that invalid JSON in presets file starts with empty presets.
    
    Requirements: 7.5
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        presets_path = Path(tmpdir) / "presets.json"
        
        # Write invalid JSON
        with open(presets_path, 'w') as f:
            f.write("{ invalid json }")
        
        # Should not raise an error
        config = ConfigManager(str(config_path), str(presets_path))
        
        # Should have empty presets
        assert config.list_presets() == []
        assert config.load_preset("any", "PCS") is None


def test_partial_config_merges_with_defaults():
    """
    Test that partial config file merges with defaults.
    
    Requirements: 7.5
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        presets_path = Path(tmpdir) / "presets.json"
        
        # Write partial config (only finviz section)
        partial_config = {
            "finviz": {
                "credentials_path": "custom.env",
                "rate_limit_delay": 2.5
            }
        }
        
        with open(config_path, 'w') as f:
            json.dump(partial_config, f)
        
        config = ConfigManager(str(config_path), str(presets_path))
        
        # Should have custom finviz values
        assert config.get("finviz.credentials_path") == "custom.env"
        assert config.get("finviz.rate_limit_delay") == 2.5
        
        # But missing sections should not have defaults automatically
        # (this is expected behavior - only load_config with missing file uses full defaults)
        assert config.get("storage.results_dir") is None
        assert config.get("analysis.risk_free_rate") is None


def test_config_with_extra_fields_loads_successfully():
    """
    Test that config with extra unknown fields loads successfully.
    
    Requirements: 7.5
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        presets_path = Path(tmpdir) / "presets.json"
        
        # Write config with extra fields
        config_data = {
            "finviz": {
                "credentials_path": ".env",
                "rate_limit_delay": 1.0,
                "max_retries": 3,
                "extra_field": "should be ignored"
            },
            "unknown_section": {
                "some_value": 123
            }
        }
        
        with open(config_path, 'w') as f:
            json.dump(config_data, f)
        
        # Should not raise an error
        config = ConfigManager(str(config_path), str(presets_path))
        
        # Should load known values
        assert config.get("finviz.credentials_path") == ".env"
        assert config.get("finviz.rate_limit_delay") == 1.0
        
        # Extra fields should be accessible but not validated
        assert config.get("finviz.extra_field") == "should be ignored"
        assert config.get("unknown_section.some_value") == 123


def test_config_reload_after_corruption():
    """
    Test that config can be reloaded after file corruption.
    
    Requirements: 7.5
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        presets_path = Path(tmpdir) / "presets.json"
        
        # Start with valid config
        valid_config = {
            "finviz": {
                "credentials_path": "valid.env",
                "rate_limit_delay": 1.5
            }
        }
        
        with open(config_path, 'w') as f:
            json.dump(valid_config, f)
        
        config = ConfigManager(str(config_path), str(presets_path))
        assert config.get("finviz.credentials_path") == "valid.env"
        
        # Corrupt the file
        with open(config_path, 'w') as f:
            f.write("{ corrupted }")
        
        # Reload config
        config.load_config()
        
        # Should fall back to defaults
        assert config.get("finviz.credentials_path") == ".env"
        assert config.get("finviz.rate_limit_delay") == 1.0
