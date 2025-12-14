"""Data models for configuration."""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class AlpacaCredentials:
    """Alpaca API credentials."""

    api_key: str
    api_secret: str
    paper: bool = True

    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate Alpaca credentials.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.api_key or not self.api_key.strip():
            return False, "API key is required"
        if not self.api_secret or not self.api_secret.strip():
            return False, "API secret is required"
        return True, None


@dataclass
class TradierCredentials:
    """Tradier API credentials."""

    api_token: str
    account_id: str
    base_url: str

    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate Tradier credentials.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.api_token or not self.api_token.strip():
            return False, "API token is required"
        if not self.account_id or not self.account_id.strip():
            return False, "Account ID is required"
        if not self.base_url or not self.base_url.strip():
            return False, "Base URL is required"
        if not self.base_url.startswith(("http://", "https://")):
            return False, "Base URL must start with http:// or https://"
        return True, None


@dataclass
class LoggingConfig:
    """Logging configuration."""

    level: str
    file_path: str

    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate logging configuration.

        Returns:
            Tuple of (is_valid, error_message)
        """
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.level.upper() not in valid_levels:
            return False, f"Log level must be one of {valid_levels}"
        if not self.file_path or not self.file_path.strip():
            return False, "Log file path is required"
        return True, None


@dataclass
class Config:
    """Main configuration for the trading bot."""

    symbols: List[str]
    strategy: str  # "pcs" (put credit spread) or "cs" (collar)
    spread_width: float
    contract_quantity: int
    run_immediately: bool  # If true, ignore execution_day and time, run right away
    execution_day: str
    execution_time_offset_minutes: int
    expiration_offset_weeks: int
    broker_type: str  # "alpaca" or "tradier"
    alpaca_credentials: Optional[AlpacaCredentials]
    tradier_credentials: Optional[TradierCredentials]
    logging_config: LoggingConfig

    # Strike offset - can be percent OR dollars (dollars takes precedence)
    strike_offset_percent: float = 5.0  # Percentage below market price
    strike_offset_dollars: float = 0.0  # Fixed dollar amount below market price

    # Collar-specific settings (optional)
    collar_put_offset_percent: float = 5.0  # How far below price for protective put (%)
    collar_call_offset_percent: float = 5.0  # How far above price for covered call (%)
    collar_put_offset_dollars: float = 0.0  # Fixed dollar amount below price for put
    collar_call_offset_dollars: float = 0.0  # Fixed dollar amount above price for call
    collar_shares_per_symbol: int = 100  # Shares owned per symbol

    # Covered call settings (optional)
    covered_call_offset_percent: float = 5.0  # How far above price for call (%)
    covered_call_offset_dollars: float = 0.0  # Fixed dollar amount above price
    covered_call_expiration_days: int = 10  # Target days until expiration

    # Wheel strategy settings (ws)
    wheel_put_offset_percent: float = 5.0  # How far below price for CSP
    wheel_call_offset_percent: float = 5.0  # How far above price for CC
    wheel_put_offset_dollars: float = 0.0  # Fixed dollar offset for puts
    wheel_call_offset_dollars: float = 0.0  # Fixed dollar offset for calls
    wheel_expiration_days: int = 30  # Target days until expiration

    # Laddered Covered Call settings (lcc)
    laddered_call_offset_percent: float = 5.0  # How far above price for calls
    laddered_call_offset_dollars: float = 0.0  # Fixed dollar offset
    laddered_coverage_ratio: float = 0.667  # 2/3 of holdings
    laddered_num_legs: int = 5  # Number of expiration legs

    # Double Calendar settings (dc)
    dc_put_offset_percent: float = 2.0  # How far below price for put strike
    dc_call_offset_percent: float = 2.0  # How far above price for call strike
    dc_short_days: int = 2  # Days until short leg expiration
    dc_long_days: int = 4  # Days until long leg expiration
    dc_symbol: str = "QQQ"  # Default symbol for double calendar

    # Butterfly settings (bf)
    bf_wing_width: float = 5.0  # Distance between strikes in dollars
    bf_expiration_days: int = 7  # Days until expiration
    bf_symbol: str = "QQQ"  # Default symbol for butterfly

    # Married Put settings (mp)
    mp_put_offset_percent: float = 5.0  # How far below price for put strike
    mp_put_offset_dollars: float = 0.0  # Fixed dollar offset (takes precedence)
    mp_expiration_days: int = 30  # Days until put expiration
    mp_shares_per_unit: int = 100  # Shares to buy per unit

    # Long Straddle settings (ls)
    ls_expiration_days: int = 30  # Days until expiration
    ls_num_contracts: int = 1  # Number of straddles to buy

    # Iron Butterfly settings (ib)
    ib_wing_width: float = 5.0  # Distance from ATM to wing strikes
    ib_expiration_days: int = 30  # Days until expiration
    ib_num_contracts: int = 1  # Number of iron butterflies

    # Short Strangle settings (ss)
    ss_put_offset_percent: float = 5.0  # How far below price for put strike
    ss_call_offset_percent: float = 5.0  # How far above price for call strike
    ss_expiration_days: int = 30  # Days until expiration
    ss_num_contracts: int = 1  # Number of strangles to sell

    # Iron Condor settings (ic)
    ic_put_spread_offset_percent: float = 3.0  # How far below price for put spread
    ic_call_spread_offset_percent: float = 3.0  # How far above price for call spread
    ic_spread_width: float = 5.0  # Width of each spread
    ic_expiration_days: int = 30  # Days until expiration
    ic_num_contracts: int = 1  # Number of iron condors

    # Tiered Covered Calls settings (tcc)
    tcc_min_shares_required: int = 300  # Minimum shares needed to execute strategy
    tcc_max_contracts_per_expiration: int = 10  # Safety limit per expiration
    tcc_min_days_to_expiration: int = 7  # Minimum days to expiration for filtering
    tcc_max_days_to_expiration: int = 60  # Maximum days to expiration for filtering
    tcc_strike_increment_minimum: float = 2.50  # Minimum difference between strikes
    tcc_premium_threshold_per_contract: float = 0.50  # Minimum premium to consider execution
    tcc_roll_enabled: bool = True  # Enable automatic rolling of expiring ITM calls
    tcc_roll_execution_time: str = "15:30"  # Time of day to check for roll opportunities
    tcc_min_roll_credit: float = 0.10  # Minimum credit required to execute a roll
    tcc_max_roll_days_out: int = 45  # Maximum days to expiration for roll targets

    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate the entire configuration.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Validate symbols
        if not self.symbols or len(self.symbols) == 0:
            return False, "At least one symbol is required"

        for symbol in self.symbols:
            if not symbol or not symbol.strip():
                return False, "Symbol cannot be empty"
            if not symbol.isupper():
                return False, f"Symbol '{symbol}' must be uppercase"
            if not symbol.isalpha():
                return False, f"Symbol '{symbol}' must contain only letters"

        # Validate strike offset (either percent or dollars must be valid)
        if self.strike_offset_dollars > 0:
            pass  # Dollar offset is valid
        elif self.strike_offset_percent <= 0:
            return False, "Strike offset percent must be positive"
        elif self.strike_offset_percent > 100:
            return False, "Strike offset percent cannot exceed 100"

        # Validate spread width
        if self.spread_width <= 0:
            return False, "Spread width must be positive"

        # Validate contract quantity
        if self.contract_quantity <= 0:
            return False, "Contract quantity must be positive"
        if not isinstance(self.contract_quantity, int):
            return False, "Contract quantity must be an integer"

        # Validate execution day
        valid_days = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
            "Daily",
        ]
        if self.execution_day not in valid_days:
            return False, f"Execution day must be one of {valid_days}"

        # Validate execution time offset
        if self.execution_time_offset_minutes < 0:
            return False, "Execution time offset minutes cannot be negative"

        # Validate expiration offset weeks
        if self.expiration_offset_weeks <= 0:
            return False, "Expiration offset weeks must be positive"

        # Validate broker type
        valid_brokers = ["alpaca", "tradier"]
        if self.broker_type.lower() not in valid_brokers:
            return False, f"Broker type must be one of {valid_brokers}"

        # Validate broker-specific credentials
        if self.broker_type.lower() == "alpaca":
            if not self.alpaca_credentials:
                return False, "Alpaca credentials required when broker_type is 'alpaca'"
            is_valid, error = self.alpaca_credentials.validate()
            if not is_valid:
                return False, f"Alpaca credentials error: {error}"
        elif self.broker_type.lower() == "tradier":
            if not self.tradier_credentials:
                return (
                    False,
                    "Tradier credentials required when broker_type is 'tradier'",
                )
            is_valid, error = self.tradier_credentials.validate()
            if not is_valid:
                return False, f"Tradier credentials error: {error}"

        is_valid, error = self.logging_config.validate()
        if not is_valid:
            return False, f"Logging config error: {error}"

        # Validate tiered covered calls settings
        if self.tcc_min_shares_required < 100:
            return False, "TCC minimum shares required must be at least 100"
        if self.tcc_max_contracts_per_expiration <= 0:
            return False, "TCC maximum contracts per expiration must be positive"
        if self.tcc_min_days_to_expiration <= 0:
            return False, "TCC minimum days to expiration must be positive"
        if self.tcc_max_days_to_expiration <= self.tcc_min_days_to_expiration:
            return False, "TCC maximum days to expiration must be greater than minimum"
        if self.tcc_strike_increment_minimum <= 0:
            return False, "TCC strike increment minimum must be positive"
        if self.tcc_premium_threshold_per_contract < 0:
            return False, "TCC premium threshold per contract cannot be negative"
        if self.tcc_min_roll_credit < 0:
            return False, "TCC minimum roll credit cannot be negative"
        if self.tcc_max_roll_days_out <= 0:
            return False, "TCC maximum roll days out must be positive"
        # Validate roll execution time format (HH:MM)
        import re
        if not re.match(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', self.tcc_roll_execution_time):
            return False, "TCC roll execution time must be in HH:MM format"

        return True, None
