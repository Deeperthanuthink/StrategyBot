"""Unit tests for ConfigManager."""

import json
import os
import tempfile
import pytest
from src.config import ConfigManager, Config, AlpacaCredentials, LoggingConfig


class TestConfigManager:
    """Test cases for ConfigManager."""

    def test_load_valid_config(self):
        """Test loading a valid configuration file."""
        config_data = {
            "symbols": ["NVDA", "GOOGL", "AAPL"],
            "strike_offset_percent": 5.0,
            "spread_width": 5.0,
            "contract_quantity": 2,
            "execution_day": "Tuesday",
            "execution_time_offset_minutes": 30,
            "expiration_offset_weeks": 1,
            "alpaca": {
                "api_key": "test_key",
                "api_secret": "test_secret",
                "base_url": "https://paper-api.alpaca.markets",
            },
            "logging": {"level": "INFO", "file_path": "logs/test.log"},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name

        try:
            manager = ConfigManager()
            config = manager.load_config(config_path)

            assert config.symbols == ["NVDA", "GOOGL", "AAPL"]
            assert config.strike_offset_percent == 5.0
            assert config.spread_width == 5.0
            assert config.contract_quantity == 2
            assert config.execution_day == "Tuesday"
            assert config.execution_time_offset_minutes == 30
            assert config.expiration_offset_weeks == 1
            assert config.alpaca_credentials.api_key == "test_key"
            assert config.alpaca_credentials.api_secret == "test_secret"
            assert config.logging_config.level == "INFO"
        finally:
            os.unlink(config_path)

    def test_load_config_missing_file(self):
        """Test loading configuration from non-existent file."""
        manager = ConfigManager()

        with pytest.raises(FileNotFoundError) as exc_info:
            manager.load_config("nonexistent_config.json")

        assert "Configuration file not found" in str(exc_info.value)

    def test_load_config_invalid_json(self):
        """Test loading configuration with invalid JSON format."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{ invalid json }")
            config_path = f.name

        try:
            manager = ConfigManager()

            with pytest.raises(json.JSONDecodeError) as exc_info:
                manager.load_config(config_path)

            assert "Invalid JSON format" in str(exc_info.value)
        finally:
            os.unlink(config_path)

    def test_environment_variable_substitution(self):
        """Test environment variable substitution in configuration."""
        os.environ["TEST_API_KEY"] = "env_test_key"
        os.environ["TEST_API_SECRET"] = "env_test_secret"

        config_data = {
            "symbols": ["NVDA"],
            "strike_offset_percent": 5.0,
            "spread_width": 5.0,
            "contract_quantity": 1,
            "execution_day": "Tuesday",
            "execution_time_offset_minutes": 30,
            "expiration_offset_weeks": 1,
            "alpaca": {
                "api_key": "${TEST_API_KEY}",
                "api_secret": "${TEST_API_SECRET}",
                "base_url": "https://paper-api.alpaca.markets",
            },
            "logging": {"level": "INFO", "file_path": "logs/test.log"},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name

        try:
            manager = ConfigManager()
            config = manager.load_config(config_path)

            assert config.alpaca_credentials.api_key == "env_test_key"
            assert config.alpaca_credentials.api_secret == "env_test_secret"
        finally:
            os.unlink(config_path)
            del os.environ["TEST_API_KEY"]
            del os.environ["TEST_API_SECRET"]

    def test_default_value_application(self):
        """Test that default values are applied for missing fields."""
        config_data = {
            "symbols": ["NVDA"],
            "alpaca": {"api_key": "test_key", "api_secret": "test_secret"},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name

        try:
            manager = ConfigManager()
            config = manager.load_config(config_path)

            # Check default values
            assert config.strike_offset_percent == 5.0
            assert config.spread_width == 5.0
            assert config.contract_quantity == 1
            assert config.execution_day == "Tuesday"
            assert config.execution_time_offset_minutes == 30
            assert config.expiration_offset_weeks == 1
            assert config.alpaca_credentials.base_url == "https://paper-api.alpaca.markets"
            assert config.logging_config.level == "INFO"
            assert config.logging_config.file_path == "logs/trading_bot.log"
        finally:
            os.unlink(config_path)

    def test_invalid_symbol_format(self):
        """Test validation of invalid symbol format."""
        config_data = {
            "symbols": ["nvda"],  # lowercase - invalid
            "strike_offset_percent": 5.0,
            "spread_width": 5.0,
            "contract_quantity": 1,
            "execution_day": "Tuesday",
            "execution_time_offset_minutes": 30,
            "expiration_offset_weeks": 1,
            "alpaca": {
                "api_key": "test_key",
                "api_secret": "test_secret",
                "base_url": "https://paper-api.alpaca.markets",
            },
            "logging": {"level": "INFO", "file_path": "logs/test.log"},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name

        try:
            manager = ConfigManager()

            with pytest.raises(ValueError) as exc_info:
                manager.load_config(config_path)

            assert "must be uppercase" in str(exc_info.value)
        finally:
            os.unlink(config_path)

    def test_invalid_numeric_ranges(self):
        """Test validation of invalid numeric ranges."""
        # Test negative strike offset
        config_data = {
            "symbols": ["NVDA"],
            "strike_offset_percent": -5.0,  # negative - invalid
            "spread_width": 5.0,
            "contract_quantity": 1,
            "execution_day": "Tuesday",
            "execution_time_offset_minutes": 30,
            "expiration_offset_weeks": 1,
            "alpaca": {
                "api_key": "test_key",
                "api_secret": "test_secret",
                "base_url": "https://paper-api.alpaca.markets",
            },
            "logging": {"level": "INFO", "file_path": "logs/test.log"},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name

        try:
            manager = ConfigManager()

            with pytest.raises(ValueError) as exc_info:
                manager.load_config(config_path)

            assert "must be positive" in str(exc_info.value)
        finally:
            os.unlink(config_path)

    def test_getter_methods(self):
        """Test all getter methods return correct values."""
        config_data = {
            "symbols": ["NVDA", "GOOGL"],
            "strike_offset_percent": 7.5,
            "spread_width": 10.0,
            "contract_quantity": 3,
            "execution_day": "Wednesday",
            "execution_time_offset_minutes": 45,
            "expiration_offset_weeks": 2,
            "alpaca": {
                "api_key": "test_key",
                "api_secret": "test_secret",
                "base_url": "https://paper-api.alpaca.markets",
            },
            "logging": {"level": "DEBUG", "file_path": "logs/test.log"},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_path = f.name

        try:
            manager = ConfigManager()
            manager.load_config(config_path)

            assert manager.get_symbols() == ["NVDA", "GOOGL"]
            assert manager.get_strike_offset_percent() == 7.5
            assert manager.get_spread_width() == 10.0
            assert manager.get_contract_quantity() == 3
            assert manager.get_execution_day() == "Wednesday"
            assert manager.get_execution_time_offset_minutes() == 45
            assert manager.get_expiration_offset_weeks() == 2

            credentials = manager.get_alpaca_credentials()
            assert credentials.api_key == "test_key"
            assert credentials.api_secret == "test_secret"

            logging_config = manager.get_logging_config()
            assert logging_config.level == "DEBUG"
            assert logging_config.file_path == "logs/test.log"
        finally:
            os.unlink(config_path)

    def test_getter_methods_before_load(self):
        """Test that getter methods raise error before config is loaded."""
        manager = ConfigManager()

        with pytest.raises(RuntimeError) as exc_info:
            manager.get_symbols()

        assert "Configuration not loaded" in str(exc_info.value)
