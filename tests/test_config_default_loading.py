"""Unit tests for default configuration loading."""

import pytest
import tempfile
from pathlib import Path
from screener.config import ConfigManager


def test_default_config_loaded_on_missing_file():
    """
    Test that defaults are loaded when config file doesn't exist.
    
    Requirements: 7.1
    """
    # Use a non-existent path
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "nonexistent" / "config.json"
        
        config = ConfigManager(str(config_path))
        
        # Verify default values are loaded
        assert config.get("finviz.credentials_path") == ".env"
        assert config.get("finviz.rate_limit_delay") == 1.0
        assert config.get("finviz.max_retries") == 3
        assert config.get("storage.results_dir") == "data/screener_results"
        assert config.get("storage.max_history_entries") == 100
        assert config.get("analysis.risk_free_rate") == 0.05
        assert config.get("analysis.default_dte") == 45


def test_default_config_structure():
    """
    Test that default config has the expected structure.
    
    Requirements: 7.1
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        
        config = ConfigManager(str(config_path))
        
        # Verify structure
        assert "finviz" in config.config
        assert "storage" in config.config
        assert "analysis" in config.config
        
        # Verify finviz section
        assert "credentials_path" in config.config["finviz"]
        assert "rate_limit_delay" in config.config["finviz"]
        assert "max_retries" in config.config["finviz"]
        
        # Verify storage section
        assert "results_dir" in config.config["storage"]
        assert "max_history_entries" in config.config["storage"]
        
        # Verify analysis section
        assert "risk_free_rate" in config.config["analysis"]
        assert "default_dte" in config.config["analysis"]


def test_config_loaded_from_existing_file():
    """
    Test that config is loaded from existing file when present.
    
    Requirements: 7.1
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        
        # Create a config file with custom values
        import json
        custom_config = {
            "finviz": {
                "credentials_path": "custom.env",
                "rate_limit_delay": 2.5,
                "max_retries": 5
            },
            "storage": {
                "results_dir": "custom/results",
                "max_history_entries": 200
            },
            "analysis": {
                "risk_free_rate": 0.04,
                "default_dte": 30
            }
        }
        
        with open(config_path, 'w') as f:
            json.dump(custom_config, f)
        
        # Load config
        config = ConfigManager(str(config_path))
        
        # Verify custom values are loaded
        assert config.get("finviz.credentials_path") == "custom.env"
        assert config.get("finviz.rate_limit_delay") == 2.5
        assert config.get("finviz.max_retries") == 5
        assert config.get("storage.results_dir") == "custom/results"
        assert config.get("storage.max_history_entries") == 200
        assert config.get("analysis.risk_free_rate") == 0.04
        assert config.get("analysis.default_dte") == 30
