"""Configuration manager for loading and validating configuration."""
import json
import os
import re
from typing import List
from .models import Config, AlpacaCredentials, TradierCredentials, LoggingConfig


class ConfigManager:
    """Manages loading and validation of configuration."""
    
    def __init__(self):
        """Initialize the ConfigManager."""
        self._config: Config = None
    
    def load_config(self, config_path: str) -> Config:
        """Load configuration from a JSON file.
        
        Args:
            config_path: Path to the configuration file
            
        Returns:
            Config object with loaded configuration
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid
            json.JSONDecodeError: If JSON is malformed
        """
        if not os.path.exists(config_path):
            raise FileNotFoundError(
                f"Configuration file not found: {config_path}\n"
                f"Please create a configuration file at this location."
            )
        
        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"Invalid JSON format in configuration file: {e.msg}",
                e.doc,
                e.pos
            )
        
        # Substitute environment variables
        config_data = self._substitute_env_vars(config_data)
        
        # Get broker type
        broker_type = config_data.get('broker_type', 'tradier')
        
        # Parse broker-specific credentials (support both nested and flat structure)
        alpaca_credentials = None
        tradier_credentials = None
        brokers = config_data.get('brokers', {})
        
        if broker_type.lower() == 'alpaca':
            # Try nested first, then flat
            alpaca_data = brokers.get('alpaca', {}) or config_data.get('alpaca', {})
            alpaca_credentials = AlpacaCredentials(
                api_key=alpaca_data.get('api_key', ''),
                api_secret=alpaca_data.get('api_secret', ''),
                paper=alpaca_data.get('paper', True)
            )
        elif broker_type.lower() == 'tradier':
            # Try nested first, then flat
            tradier_data = brokers.get('tradier', {}) or config_data.get('tradier', {})
            tradier_credentials = TradierCredentials(
                api_token=tradier_data.get('api_token', ''),
                account_id=tradier_data.get('account_id', ''),
                base_url=tradier_data.get('base_url', 'https://sandbox.tradier.com')
            )
        
        logging_data = config_data.get('logging', {})
        logging_config = LoggingConfig(
            level=logging_data.get('level', 'INFO'),
            file_path=logging_data.get('file_path', 'logs/trading_bot.log')
        )
        
        # Get nested strategy configs
        strategies = config_data.get('strategies', {})
        pcs_config = strategies.get('pcs', {})
        cs_config = strategies.get('cs', {})
        cc_config = strategies.get('cc', {})
        ws_config = strategies.get('ws', {})
        lcc_config = strategies.get('lcc', {})
        dc_config = strategies.get('dc', {})
        bf_config = strategies.get('bf', {})
        mp_config = strategies.get('mp', {})
        ls_config = strategies.get('ls', {})
        ib_config = strategies.get('ib', {})
        ss_config = strategies.get('ss', {})
        
        # Create main config with type conversion error handling
        try:
            config = Config(
                symbols=config_data.get('symbols', []),
                strategy=config_data.get('strategy', 'pcs'),
                # PCS settings
                strike_offset_percent=float(pcs_config.get('strike_offset_percent', 5.0)),
                strike_offset_dollars=float(pcs_config.get('strike_offset_dollars', 0.0)),
                spread_width=float(pcs_config.get('spread_width', 5.0)),
                # General settings
                contract_quantity=int(config_data.get('contract_quantity', 1)),
                run_immediately=config_data.get('run_immediately', False),
                execution_day=config_data.get('execution_day', 'Tuesday'),
                execution_time_offset_minutes=int(config_data.get('execution_time_offset_minutes', 30)),
                expiration_offset_weeks=int(config_data.get('expiration_offset_weeks', 1)),
                broker_type=broker_type,
                alpaca_credentials=alpaca_credentials,
                tradier_credentials=tradier_credentials,
                logging_config=logging_config,
                # Collar settings
                collar_put_offset_percent=float(cs_config.get('put_offset_percent', 5.0)),
                collar_call_offset_percent=float(cs_config.get('call_offset_percent', 5.0)),
                collar_put_offset_dollars=float(cs_config.get('put_offset_dollars', 0.0)),
                collar_call_offset_dollars=float(cs_config.get('call_offset_dollars', 0.0)),
                collar_shares_per_symbol=int(cs_config.get('shares_per_symbol', 100)),
                # Covered Call settings
                covered_call_offset_percent=float(cc_config.get('offset_percent', 5.0)),
                covered_call_offset_dollars=float(cc_config.get('offset_dollars', 0.0)),
                covered_call_expiration_days=int(cc_config.get('expiration_days', 10)),
                # Wheel settings
                wheel_put_offset_percent=float(ws_config.get('put_offset_percent', 5.0)),
                wheel_call_offset_percent=float(ws_config.get('call_offset_percent', 5.0)),
                wheel_put_offset_dollars=float(ws_config.get('put_offset_dollars', 0.0)),
                wheel_call_offset_dollars=float(ws_config.get('call_offset_dollars', 0.0)),
                wheel_expiration_days=int(ws_config.get('expiration_days', 30)),
                # Laddered CC settings
                laddered_call_offset_percent=float(lcc_config.get('call_offset_percent', 5.0)),
                laddered_call_offset_dollars=float(lcc_config.get('call_offset_dollars', 0.0)),
                laddered_coverage_ratio=float(lcc_config.get('coverage_ratio', 0.667)),
                laddered_num_legs=int(lcc_config.get('num_legs', 5)),
                # Double Calendar settings
                dc_put_offset_percent=float(dc_config.get('put_offset_percent', 2.0)),
                dc_call_offset_percent=float(dc_config.get('call_offset_percent', 2.0)),
                dc_short_days=int(dc_config.get('short_days', 2)),
                dc_long_days=int(dc_config.get('long_days', 4)),
                dc_symbol=dc_config.get('symbol', 'QQQ'),
                # Butterfly settings
                bf_wing_width=float(bf_config.get('wing_width', 5.0)),
                bf_expiration_days=int(bf_config.get('expiration_days', 7)),
                bf_symbol=bf_config.get('symbol', 'QQQ'),
                # Married Put settings
                mp_put_offset_percent=float(mp_config.get('put_offset_percent', 5.0)),
                mp_put_offset_dollars=float(mp_config.get('put_offset_dollars', 0.0)),
                mp_expiration_days=int(mp_config.get('expiration_days', 30)),
                mp_shares_per_unit=int(mp_config.get('shares_per_unit', 100)),
                # Long Straddle settings
                ls_expiration_days=int(ls_config.get('expiration_days', 30)),
                ls_num_contracts=int(ls_config.get('num_contracts', 1)),
                # Iron Butterfly settings
                ib_wing_width=float(ib_config.get('wing_width', 5.0)),
                ib_expiration_days=int(ib_config.get('expiration_days', 30)),
                ib_num_contracts=int(ib_config.get('num_contracts', 1)),
                # Short Strangle settings
                ss_put_offset_percent=float(ss_config.get('put_offset_percent', 5.0)),
                ss_call_offset_percent=float(ss_config.get('call_offset_percent', 5.0)),
                ss_expiration_days=int(ss_config.get('expiration_days', 30)),
                ss_num_contracts=int(ss_config.get('num_contracts', 1))
            )
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"Invalid configuration value type: {e}\n"
                f"Please check that numeric values are numbers and other values are correct types."
            )
        
        # Validate configuration
        if not self.validate_config(config):
            raise ValueError("Configuration validation failed")
        
        self._config = config
        return config
    
    def _substitute_env_vars(self, data):
        """Recursively substitute environment variables in configuration data.
        
        Environment variables should be in the format ${VAR_NAME}.
        
        Args:
            data: Configuration data (dict, list, or string)
            
        Returns:
            Data with environment variables substituted
        """
        if isinstance(data, dict):
            return {key: self._substitute_env_vars(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._substitute_env_vars(item) for item in data]
        elif isinstance(data, str):
            # Find all ${VAR_NAME} patterns
            pattern = r'\$\{([^}]+)\}'
            matches = re.findall(pattern, data)
            result = data
            for var_name in matches:
                env_value = os.environ.get(var_name, '')
                result = result.replace(f'${{{var_name}}}', env_value)
            return result
        else:
            return data
    
    def validate_config(self, config: Config) -> bool:
        """Validate the configuration.
        
        Args:
            config: Config object to validate
            
        Returns:
            True if valid
            
        Raises:
            ValueError: If validation fails with error message
        """
        is_valid, error_message = config.validate()
        if not is_valid:
            raise ValueError(f"Configuration validation error: {error_message}")
        return True
    
    def get_symbols(self) -> List[str]:
        """Get the list of symbols to trade.
        
        Returns:
            List of symbol strings
        """
        if self._config is None:
            raise RuntimeError("Configuration not loaded. Call load_config first.")
        return self._config.symbols
    
    def get_strike_offset_percent(self) -> float:
        """Get the strike price offset percentage.
        
        Returns:
            Strike offset percentage
        """
        if self._config is None:
            raise RuntimeError("Configuration not loaded. Call load_config first.")
        return self._config.strike_offset_percent
    
    def get_spread_width(self) -> float:
        """Get the spread width in dollars.
        
        Returns:
            Spread width
        """
        if self._config is None:
            raise RuntimeError("Configuration not loaded. Call load_config first.")
        return self._config.spread_width
    
    def get_contract_quantity(self) -> int:
        """Get the number of contracts per trade.
        
        Returns:
            Contract quantity
        """
        if self._config is None:
            raise RuntimeError("Configuration not loaded. Call load_config first.")
        return self._config.contract_quantity
    
    def get_execution_day(self) -> str:
        """Get the day of week for execution.
        
        Returns:
            Execution day name
        """
        if self._config is None:
            raise RuntimeError("Configuration not loaded. Call load_config first.")
        return self._config.execution_day
    
    def get_execution_time_offset_minutes(self) -> int:
        """Get the execution time offset in minutes after market open.
        
        Returns:
            Execution time offset in minutes
        """
        if self._config is None:
            raise RuntimeError("Configuration not loaded. Call load_config first.")
        return self._config.execution_time_offset_minutes
    
    def get_expiration_offset_weeks(self) -> int:
        """Get the expiration offset in weeks.
        
        Returns:
            Expiration offset weeks
        """
        if self._config is None:
            raise RuntimeError("Configuration not loaded. Call load_config first.")
        return self._config.expiration_offset_weeks
    
    def get_tradier_credentials(self) -> TradierCredentials:
        """Get Tradier API credentials.
        
        Returns:
            TradierCredentials object
        """
        if self._config is None:
            raise RuntimeError("Configuration not loaded. Call load_config first.")
        return self._config.tradier_credentials
    
    def get_logging_config(self) -> LoggingConfig:
        """Get logging configuration.
        
        Returns:
            LoggingConfig object
        """
        if self._config is None:
            raise RuntimeError("Configuration not loaded. Call load_config first.")
        return self._config.logging_config
