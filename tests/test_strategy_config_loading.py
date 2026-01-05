"""Unit tests for strategy configuration loading."""

import pytest
import tempfile
import json
from pathlib import Path
from screener.config import ConfigManager


def test_load_strategy_config_success():
    """Test loading a valid strategy config file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        presets_path = Path(tmpdir) / "presets.json"
        strategies_dir = Path(tmpdir) / "strategies"
        strategies_dir.mkdir()
        
        # Create a strategy config
        strategy_config = {
            "name": "Put Credit Spread",
            "default_filters": {
                "min_market_cap": 2000000000,
                "min_volume": 1000000
            },
            "scoring_weights": {
                "iv_rank": 30,
                "liquidity": 20
            }
        }
        
        strategy_file = strategies_dir / "pcs_config.json"
        with open(strategy_file, 'w') as f:
            json.dump(strategy_config, f)
        
        config = ConfigManager(str(config_path), str(presets_path), str(strategies_dir))
        
        # Load strategy config
        loaded = config.load_strategy_config("PCS")
        
        assert loaded is not None
        assert loaded["name"] == "Put Credit Spread"
        assert loaded["default_filters"]["min_market_cap"] == 2000000000


def test_load_strategy_config_not_found():
    """Test loading a non-existent strategy config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        presets_path = Path(tmpdir) / "presets.json"
        strategies_dir = Path(tmpdir) / "strategies"
        strategies_dir.mkdir()
        
        config = ConfigManager(str(config_path), str(presets_path), str(strategies_dir))
        
        # Try to load non-existent strategy
        loaded = config.load_strategy_config("NonExistent")
        
        assert loaded is None


def test_load_strategy_config_invalid_json():
    """Test loading a strategy config with invalid JSON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        presets_path = Path(tmpdir) / "presets.json"
        strategies_dir = Path(tmpdir) / "strategies"
        strategies_dir.mkdir()
        
        # Create invalid JSON file
        strategy_file = strategies_dir / "pcs_config.json"
        with open(strategy_file, 'w') as f:
            f.write("{ invalid json }")
        
        config = ConfigManager(str(config_path), str(presets_path), str(strategies_dir))
        
        # Should return None for invalid JSON
        loaded = config.load_strategy_config("PCS")
        
        assert loaded is None


def test_get_strategy_defaults():
    """Test retrieving default filters from strategy config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        presets_path = Path(tmpdir) / "presets.json"
        strategies_dir = Path(tmpdir) / "strategies"
        strategies_dir.mkdir()
        
        # Create a strategy config
        strategy_config = {
            "name": "Put Credit Spread",
            "default_filters": {
                "min_market_cap": 2000000000,
                "min_volume": 1000000,
                "price_min": 20
            }
        }
        
        strategy_file = strategies_dir / "pcs_config.json"
        with open(strategy_file, 'w') as f:
            json.dump(strategy_config, f)
        
        config = ConfigManager(str(config_path), str(presets_path), str(strategies_dir))
        
        # Get defaults
        defaults = config.get_strategy_defaults("PCS")
        
        assert defaults["min_market_cap"] == 2000000000
        assert defaults["min_volume"] == 1000000
        assert defaults["price_min"] == 20


def test_get_strategy_defaults_missing_strategy():
    """Test retrieving defaults for non-existent strategy."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        presets_path = Path(tmpdir) / "presets.json"
        strategies_dir = Path(tmpdir) / "strategies"
        strategies_dir.mkdir()
        
        config = ConfigManager(str(config_path), str(presets_path), str(strategies_dir))
        
        # Should return empty dict
        defaults = config.get_strategy_defaults("NonExistent")
        
        assert defaults == {}


def test_get_strategy_scoring_weights():
    """Test retrieving scoring weights from strategy config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        presets_path = Path(tmpdir) / "presets.json"
        strategies_dir = Path(tmpdir) / "strategies"
        strategies_dir.mkdir()
        
        # Create a strategy config
        strategy_config = {
            "name": "Put Credit Spread",
            "scoring_weights": {
                "iv_rank": 30,
                "technical_strength": 25,
                "liquidity": 20,
                "stability": 25
            }
        }
        
        strategy_file = strategies_dir / "pcs_config.json"
        with open(strategy_file, 'w') as f:
            json.dump(strategy_config, f)
        
        config = ConfigManager(str(config_path), str(presets_path), str(strategies_dir))
        
        # Get scoring weights
        weights = config.get_strategy_scoring_weights("PCS")
        
        assert weights["iv_rank"] == 30
        assert weights["technical_strength"] == 25
        assert weights["liquidity"] == 20
        assert weights["stability"] == 25


def test_get_strategy_analysis_settings():
    """Test retrieving analysis settings from strategy config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        presets_path = Path(tmpdir) / "presets.json"
        strategies_dir = Path(tmpdir) / "strategies"
        strategies_dir.mkdir()
        
        # Create a strategy config
        strategy_config = {
            "name": "Put Credit Spread",
            "analysis_settings": {
                "default_dte": 45,
                "spread_width": 5,
                "ideal_beta_min": 0.7
            }
        }
        
        strategy_file = strategies_dir / "pcs_config.json"
        with open(strategy_file, 'w') as f:
            json.dump(strategy_config, f)
        
        config = ConfigManager(str(config_path), str(presets_path), str(strategies_dir))
        
        # Get analysis settings
        settings = config.get_strategy_analysis_settings("PCS")
        
        assert settings["default_dte"] == 45
        assert settings["spread_width"] == 5
        assert settings["ideal_beta_min"] == 0.7


def test_list_available_strategies():
    """Test listing all available strategies."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        presets_path = Path(tmpdir) / "presets.json"
        strategies_dir = Path(tmpdir) / "strategies"
        strategies_dir.mkdir()
        
        # Create multiple strategy configs
        for strategy_name in ["pcs", "covered_call", "iron_condor"]:
            strategy_file = strategies_dir / f"{strategy_name}_config.json"
            with open(strategy_file, 'w') as f:
                json.dump({"name": strategy_name}, f)
        
        config = ConfigManager(str(config_path), str(presets_path), str(strategies_dir))
        
        # List strategies
        strategies = config.list_available_strategies()
        
        assert "PCS" in strategies
        assert "COVERED_CALL" in strategies
        assert "IRON_CONDOR" in strategies
        assert len(strategies) == 3


def test_list_available_strategies_empty_dir():
    """Test listing strategies when directory is empty."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        presets_path = Path(tmpdir) / "presets.json"
        strategies_dir = Path(tmpdir) / "strategies"
        strategies_dir.mkdir()
        
        config = ConfigManager(str(config_path), str(presets_path), str(strategies_dir))
        
        # Should return empty list
        strategies = config.list_available_strategies()
        
        assert strategies == []


def test_strategy_config_caching():
    """Test that strategy configs are cached after first load."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.json"
        presets_path = Path(tmpdir) / "presets.json"
        strategies_dir = Path(tmpdir) / "strategies"
        strategies_dir.mkdir()
        
        # Create a strategy config
        strategy_config = {
            "name": "Put Credit Spread",
            "default_filters": {"min_market_cap": 2000000000}
        }
        
        strategy_file = strategies_dir / "pcs_config.json"
        with open(strategy_file, 'w') as f:
            json.dump(strategy_config, f)
        
        config = ConfigManager(str(config_path), str(presets_path), str(strategies_dir))
        
        # Load strategy config
        loaded1 = config.load_strategy_config("PCS")
        
        # Modify the file
        strategy_config["default_filters"]["min_market_cap"] = 5000000000
        with open(strategy_file, 'w') as f:
            json.dump(strategy_config, f)
        
        # Load again - should return cached version
        loaded2 = config.load_strategy_config("PCS")
        
        # Should still have old value (cached)
        assert loaded2["default_filters"]["min_market_cap"] == 2000000000


def test_real_pcs_config_loads():
    """Test that the actual PCS config file loads correctly."""
    # This test uses the real config file
    config = ConfigManager()
    
    # Load PCS config
    pcs_config = config.load_strategy_config("PCS")
    
    # Verify it loaded
    assert pcs_config is not None
    assert "default_filters" in pcs_config
    assert "scoring_weights" in pcs_config
    assert "analysis_settings" in pcs_config
    
    # Verify some key values
    defaults = pcs_config["default_filters"]
    assert defaults["min_market_cap"] == 2000000000
    assert defaults["min_volume"] == 1000000
    assert defaults["price_min"] == 20
    assert defaults["price_max"] == 200
    
    weights = pcs_config["scoring_weights"]
    assert weights["iv_rank"] == 30
    assert weights["technical_strength"] == 25
    
    settings = pcs_config["analysis_settings"]
    assert settings["default_dte"] == 45
