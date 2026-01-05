"""Configuration management for the stock screener."""

import json
import logging
from pathlib import Path
from typing import Any, Optional, List

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Exception raised for parameter validation errors."""
    pass


class ConfigManager:
    """Manages application configuration with support for dot notation access."""
    
    # Parameter validation rules
    PARAMETER_RANGES = {
        'min_market_cap': (0, 1e13),
        'max_market_cap': (0, 1e13),
        'min_volume': (0, 1e10),
        'max_volume': (0, 1e10),
        'price_min': (0, 10000),
        'price_max': (0, 10000),
        'rsi_min': (0, 100),
        'rsi_max': (0, 100),
        'beta_min': (0, 10),
        'beta_max': (0, 10),
        'iv_rank_min': (0, 100),
        'iv_rank_max': (0, 100),
        'weekly_perf_min': (-100, 100),
        'weekly_perf_max': (-100, 100),
        'earnings_buffer_days': (0, 365),
    }
    
    def __init__(self, config_path: str = "config/screener_config.json",
                 presets_path: str = "config/user_presets.json",
                 strategies_dir: str = "config/strategies"):
        """
        Initialize the ConfigManager.
        
        Args:
            config_path: Path to the configuration JSON file
            presets_path: Path to the user presets JSON file
            strategies_dir: Path to the directory containing strategy configs
        """
        self.config_path = Path(config_path)
        self.presets_path = Path(presets_path)
        self.strategies_dir = Path(strategies_dir)
        self.config: dict = {}
        self.presets: dict = {}
        self.strategy_configs: dict = {}
        self.load_config()
        self._load_presets()
    
    def load_config(self) -> dict:
        """
        Load configuration from JSON file.
        
        Returns:
            The loaded configuration dictionary
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            json.JSONDecodeError: If config file is invalid JSON
        """
        if not self.config_path.exists():
            logger.warning(f"Config file not found at {self.config_path}, using defaults")
            self.config = self._get_default_config()
            return self.config
        
        try:
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
            logger.info(f"Configuration loaded from {self.config_path}")
            return self.config
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            self.config = self._get_default_config()
            return self.config
    
    def _get_default_config(self) -> dict:
        """
        Get default configuration values.
        
        Returns:
            Dictionary with default configuration
        """
        return {
            "finviz": {
                "credentials_path": ".env",
                "rate_limit_delay": 1.0,
                "max_retries": 3
            },
            "storage": {
                "results_dir": "data/screener_results",
                "max_history_entries": 100
            },
            "analysis": {
                "risk_free_rate": 0.05,
                "default_dte": 45
            }
        }
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.
        
        Args:
            key_path: Dot-separated path to the config value (e.g., "finviz.rate_limit_delay")
            default: Default value to return if key doesn't exist
            
        Returns:
            The configuration value or default if not found
            
        Example:
            >>> config.get("finviz.rate_limit_delay")
            1.0
            >>> config.get("finviz.timeout", 30)
            30
        """
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def set(self, key_path: str, value: Any) -> None:
        """
        Set a configuration value using dot notation.
        
        Args:
            key_path: Dot-separated path to the config value (e.g., "finviz.rate_limit_delay")
            value: Value to set
            
        Example:
            >>> config.set("finviz.rate_limit_delay", 2.0)
            >>> config.get("finviz.rate_limit_delay")
            2.0
        """
        keys = key_path.split('.')
        current = self.config
        
        # Navigate to the parent of the target key
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Set the final key
        current[keys[-1]] = value
    
    def save(self) -> None:
        """
        Save the current configuration to the JSON file.
        
        Raises:
            IOError: If unable to write to config file
        """
        try:
            # Ensure parent directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            
            logger.info(f"Configuration saved to {self.config_path}")
        except IOError as e:
            logger.error(f"Failed to save configuration: {e}")
            raise
    
    def _load_presets(self) -> dict:
        """
        Load presets from JSON file.
        
        Returns:
            The loaded presets dictionary
        """
        if not self.presets_path.exists():
            logger.info(f"Presets file not found at {self.presets_path}, starting with empty presets")
            self.presets = {}
            return self.presets
        
        try:
            with open(self.presets_path, 'r') as f:
                self.presets = json.load(f)
            logger.info(f"Presets loaded from {self.presets_path}")
            return self.presets
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in presets file: {e}")
            self.presets = {}
            return self.presets
    
    def validate_parameters(self, filters: dict) -> List[str]:
        """
        Validate filter parameters are within acceptable ranges.
        
        Args:
            filters: Dictionary of filter parameters to validate
            
        Returns:
            List of validation error messages (empty if all valid)
            
        Example:
            >>> errors = config.validate_parameters({"rsi_min": 150})
            >>> print(errors)
            ["Parameter 'rsi_min' value 150 is outside valid range [0, 100]"]
        """
        errors = []
        
        for param_name, value in filters.items():
            if param_name in self.PARAMETER_RANGES:
                min_val, max_val = self.PARAMETER_RANGES[param_name]
                
                # Check if value is numeric (but not boolean)
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    errors.append(
                        f"Parameter '{param_name}' must be numeric, got {type(value).__name__}"
                    )
                    continue
                
                # Check if value is within range
                if value < min_val or value > max_val:
                    errors.append(
                        f"Parameter '{param_name}' value {value} is outside valid range [{min_val}, {max_val}]"
                    )
        
        return errors
    
    def save_preset(self, name: str, strategy: str, filters: dict) -> None:
        """
        Save a named preset for a strategy.
        
        Args:
            name: Name of the preset
            strategy: Strategy name (e.g., "PCS", "CoveredCall")
            filters: Dictionary of filter parameters
            
        Raises:
            ValidationError: If filter parameters are invalid
            
        Example:
            >>> config.save_preset("aggressive", "PCS", {"min_iv_rank": 60, "min_volume": 2000000})
        """
        # Validate parameters before saving
        validation_errors = self.validate_parameters(filters)
        if validation_errors:
            error_msg = "Invalid filter parameters:\n" + "\n".join(validation_errors)
            raise ValidationError(error_msg)
        
        if strategy not in self.presets:
            self.presets[strategy] = {}
        
        self.presets[strategy][name] = filters
        
        # Save to file
        try:
            self.presets_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.presets_path, 'w') as f:
                json.dump(self.presets, f, indent=2)
            logger.info(f"Preset '{name}' saved for strategy '{strategy}'")
        except IOError as e:
            logger.error(f"Failed to save preset: {e}")
            raise
    
    def load_preset(self, name: str, strategy: str) -> Optional[dict]:
        """
        Load a named preset for a strategy.
        
        Args:
            name: Name of the preset
            strategy: Strategy name
            
        Returns:
            Dictionary of filter parameters, or None if preset doesn't exist
            
        Example:
            >>> filters = config.load_preset("aggressive", "PCS")
            >>> print(filters)
            {"min_iv_rank": 60, "min_volume": 2000000}
        """
        if strategy not in self.presets:
            return None
        
        return self.presets[strategy].get(name)
    
    def list_presets(self, strategy: Optional[str] = None) -> list[str]:
        """
        List available presets, optionally filtered by strategy.
        
        Args:
            strategy: Optional strategy name to filter by
            
        Returns:
            List of preset names
            
        Example:
            >>> config.list_presets("PCS")
            ["aggressive", "conservative", "balanced"]
            >>> config.list_presets()
            ["PCS:aggressive", "PCS:conservative", "CoveredCall:income"]
        """
        if strategy:
            if strategy not in self.presets:
                return []
            return list(self.presets[strategy].keys())
        
        # Return all presets with strategy prefix
        all_presets = []
        for strat, presets in self.presets.items():
            for preset_name in presets.keys():
                all_presets.append(f"{strat}:{preset_name}")
        
        return all_presets
    
    def load_strategy_config(self, strategy_name: str) -> Optional[dict]:
        """
        Load strategy-specific configuration from file.
        
        Args:
            strategy_name: Name of the strategy (e.g., "PCS", "CoveredCall")
            
        Returns:
            Strategy configuration dictionary, or None if not found
            
        Example:
            >>> config = manager.load_strategy_config("PCS")
            >>> print(config["default_filters"])
            {"min_market_cap": 2000000000, ...}
        """
        # Check if already loaded
        if strategy_name in self.strategy_configs:
            return self.strategy_configs[strategy_name]
        
        # Construct path to strategy config file
        # Support both exact name and lowercase with _config suffix
        possible_paths = [
            self.strategies_dir / f"{strategy_name.lower()}_config.json",
            self.strategies_dir / f"{strategy_name}_config.json",
            self.strategies_dir / f"{strategy_name.lower()}.json",
        ]
        
        for config_file in possible_paths:
            if config_file.exists():
                try:
                    with open(config_file, 'r') as f:
                        strategy_config = json.load(f)
                    
                    # Cache the loaded config
                    self.strategy_configs[strategy_name] = strategy_config
                    logger.info(f"Strategy config loaded for '{strategy_name}' from {config_file}")
                    return strategy_config
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in strategy config {config_file}: {e}")
                    return None
                except IOError as e:
                    logger.error(f"Error reading strategy config {config_file}: {e}")
                    return None
        
        logger.warning(f"No strategy config found for '{strategy_name}'")
        return None
    
    def get_strategy_defaults(self, strategy_name: str) -> dict:
        """
        Get default filters for a strategy from its config file.
        
        Args:
            strategy_name: Name of the strategy
            
        Returns:
            Dictionary of default filter parameters, or empty dict if not found
            
        Example:
            >>> defaults = manager.get_strategy_defaults("PCS")
            >>> print(defaults["min_market_cap"])
            2000000000
        """
        strategy_config = self.load_strategy_config(strategy_name)
        if strategy_config:
            return strategy_config.get("default_filters", {})
        return {}
    
    def get_strategy_scoring_weights(self, strategy_name: str) -> dict:
        """
        Get scoring weights for a strategy from its config file.
        
        Args:
            strategy_name: Name of the strategy
            
        Returns:
            Dictionary of scoring weights, or empty dict if not found
            
        Example:
            >>> weights = manager.get_strategy_scoring_weights("PCS")
            >>> print(weights["iv_rank"])
            30
        """
        strategy_config = self.load_strategy_config(strategy_name)
        if strategy_config:
            return strategy_config.get("scoring_weights", {})
        return {}
    
    def get_strategy_analysis_settings(self, strategy_name: str) -> dict:
        """
        Get analysis settings for a strategy from its config file.
        
        Args:
            strategy_name: Name of the strategy
            
        Returns:
            Dictionary of analysis settings, or empty dict if not found
            
        Example:
            >>> settings = manager.get_strategy_analysis_settings("PCS")
            >>> print(settings["default_dte"])
            45
        """
        strategy_config = self.load_strategy_config(strategy_name)
        if strategy_config:
            return strategy_config.get("analysis_settings", {})
        return {}
    
    def list_available_strategies(self) -> list[str]:
        """
        List all strategies that have configuration files.
        
        Returns:
            List of strategy names
            
        Example:
            >>> strategies = manager.list_available_strategies()
            >>> print(strategies)
            ["PCS", "CoveredCall", "IronCondor"]
        """
        if not self.strategies_dir.exists():
            return []
        
        strategies = []
        for config_file in self.strategies_dir.glob("*_config.json"):
            # Extract strategy name from filename (remove _config.json)
            strategy_name = config_file.stem.replace("_config", "").upper()
            strategies.append(strategy_name)
        
        return sorted(strategies)
