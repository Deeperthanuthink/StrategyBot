"""Main trading bot orchestration."""
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import List, Optional
import time

from src.config.config_manager import ConfigManager
from src.config.models import Config
from src.brokers.broker_factory import BrokerFactory
from src.brokers.base_client import BaseBrokerClient
from src.strategy.strategy_calculator import StrategyCalculator, SpreadParameters
from src.strategy.collar_strategy import CollarCalculator, CollarParameters, CoveredCallCalculator, CoveredCallParameters, WheelCalculator, LadderedCoveredCallCalculator, DoubleCalendarCalculator, ButterflyCalculator, MarriedPutCalculator, LongStraddleCalculator, IronButterflyCalculator, ShortStrangleCalculator
from src.order.order_manager import OrderManager, TradeResult
from src.logging.bot_logger import BotLogger


@dataclass
class ExecutionSummary:
    """Summary of a trading cycle execution."""
    execution_date: datetime
    total_symbols: int
    successful_trades: int
    failed_trades: int
    trade_results: List[TradeResult]


class TradingBot:
    """Main trading bot that orchestrates the entire trading workflow."""
    
    def __init__(self, config_path: str, dry_run: bool = False):
        """Initialize the TradingBot.
        
        Args:
            config_path: Path to the configuration file
            dry_run: If True, no actual orders will be submitted
        """
        self.config_path = config_path
        self.dry_run = dry_run
        self.config: Optional[Config] = None
        self.config_manager: Optional[ConfigManager] = None
        self.logger: Optional[BotLogger] = None
        self.broker_client: Optional[BaseBrokerClient] = None
        self.strategy_calculator: Optional[StrategyCalculator] = None
        self.collar_calculator: Optional[CollarCalculator] = None
        self.order_manager: Optional[OrderManager] = None
        self._initialized = False
    
    def initialize(self) -> bool:
        """Initialize all components of the trading bot.
        
        This method sets up:
        - Configuration manager and loads config
        - Logger
        - Alpaca client and authenticates
        - Strategy calculator
        - Order manager
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Load configuration
            self.config_manager = ConfigManager()
            self.config = self.config_manager.load_config(self.config_path)
            
            # Initialize logger
            self.logger = BotLogger(self.config.logging_config)
            self.logger.log_info(
                "Trading bot initialization started",
                {"config_path": self.config_path, "dry_run": self.dry_run}
            )
            
            # Initialize broker client using factory
            broker_type = self.config.broker_type
            self.logger.log_info(f"Initializing {broker_type} broker via Lumibot")
            
            if broker_type.lower() == 'alpaca':
                credentials = {
                    'api_key': self.config.alpaca_credentials.api_key,
                    'api_secret': self.config.alpaca_credentials.api_secret,
                    'paper': self.config.alpaca_credentials.paper
                }
            else:  # tradier
                credentials = {
                    'api_token': self.config.tradier_credentials.api_token,
                    'account_id': self.config.tradier_credentials.account_id,
                    'base_url': self.config.tradier_credentials.base_url
                }
            
            self.broker_client = BrokerFactory.create_broker(
                broker_type=broker_type,
                credentials=credentials,
                logger=self.logger
            )
            
            # Authenticate with broker
            self.logger.log_info(f"Authenticating with {broker_type} API via Lumibot")
            if not self.broker_client.authenticate():
                self.logger.log_error(f"Failed to authenticate with {broker_type} API")
                return False
            
            # Initialize strategy calculators
            self.strategy_calculator = StrategyCalculator(self.config)
            self.collar_calculator = CollarCalculator(
                put_offset_percent=self.config.collar_put_offset_percent,
                call_offset_percent=self.config.collar_call_offset_percent,
                put_offset_dollars=self.config.collar_put_offset_dollars,
                call_offset_dollars=self.config.collar_call_offset_dollars
            )
            self.covered_call_calculator = CoveredCallCalculator(
                call_offset_percent=self.config.covered_call_offset_percent,
                call_offset_dollars=self.config.covered_call_offset_dollars,
                expiration_days=self.config.covered_call_expiration_days
            )
            self.wheel_calculator = WheelCalculator(
                put_offset_percent=self.config.wheel_put_offset_percent,
                call_offset_percent=self.config.wheel_call_offset_percent,
                put_offset_dollars=self.config.wheel_put_offset_dollars,
                call_offset_dollars=self.config.wheel_call_offset_dollars,
                expiration_days=self.config.wheel_expiration_days
            )
            self.laddered_cc_calculator = LadderedCoveredCallCalculator(
                call_offset_percent=self.config.laddered_call_offset_percent,
                call_offset_dollars=self.config.laddered_call_offset_dollars,
                coverage_ratio=self.config.laddered_coverage_ratio,
                num_legs=self.config.laddered_num_legs
            )
            self.double_calendar_calculator = DoubleCalendarCalculator(
                put_offset_percent=self.config.dc_put_offset_percent,
                call_offset_percent=self.config.dc_call_offset_percent,
                short_days=self.config.dc_short_days,
                long_days=self.config.dc_long_days
            )
            self.butterfly_calculator = ButterflyCalculator(
                wing_width=self.config.bf_wing_width,
                expiration_days=self.config.bf_expiration_days
            )
            self.married_put_calculator = MarriedPutCalculator(
                put_offset_percent=self.config.mp_put_offset_percent,
                put_offset_dollars=self.config.mp_put_offset_dollars,
                expiration_days=self.config.mp_expiration_days,
                shares_per_unit=self.config.mp_shares_per_unit
            )
            self.long_straddle_calculator = LongStraddleCalculator(
                expiration_days=self.config.ls_expiration_days,
                num_contracts=self.config.ls_num_contracts
            )
            self.iron_butterfly_calculator = IronButterflyCalculator(
                wing_width=self.config.ib_wing_width,
                expiration_days=self.config.ib_expiration_days,
                num_contracts=self.config.ib_num_contracts
            )
            self.short_strangle_calculator = ShortStrangleCalculator(
                put_offset_percent=self.config.ss_put_offset_percent,
                call_offset_percent=self.config.ss_call_offset_percent,
                expiration_days=self.config.ss_expiration_days,
                num_contracts=self.config.ss_num_contracts
            )
            strategy_names = {"pcs": "Put Credit Spread", "cs": "Collar", "cc": "Covered Call", "ws": "Wheel Strategy", "lcc": "Laddered Covered Call", "dc": "Double Calendar", "bf": "Butterfly", "mp": "Married Put", "ls": "Long Straddle", "ib": "Iron Butterfly", "ss": "Short Strangle"}
            strategy_name = strategy_names.get(self.config.strategy, "Unknown")
            self.logger.log_info(
                f"Strategy calculators initialized ({strategy_name})",
                {"strategy": self.config.strategy}
            )
            
            # Initialize order manager
            self.order_manager = OrderManager(
                broker_client=self.broker_client,
                logger=self.logger,
                dry_run=self.dry_run
            )
            if self.dry_run:
                self.logger.log_info("Order manager initialized in DRY-RUN mode")
            else:
                self.logger.log_info("Order manager initialized")
            
            self._initialized = True
            self.logger.log_info(
                "Trading bot initialization complete",
                {
                    "symbols": self.config.symbols,
                    "strike_offset": self.config.strike_offset_percent,
                    "spread_width": self.config.spread_width,
                    "contract_quantity": self.config.contract_quantity
                }
            )
            
            return True
            
        except FileNotFoundError as e:
            if self.logger:
                self.logger.log_error(
                    f"Configuration file not found: {str(e)}",
                    e,
                    {
                        "config_path": self.config_path,
                        "error_type": "FileNotFoundError"
                    }
                )
            else:
                print(f"ERROR: Configuration file not found: {str(e)}")
            return False
            
        except ValueError as e:
            if self.logger:
                self.logger.log_error(
                    f"Configuration validation error: {str(e)}",
                    e,
                    {
                        "config_path": self.config_path,
                        "error_type": "ValueError"
                    }
                )
            else:
                print(f"ERROR: Configuration validation error: {str(e)}")
            return False
            
        except Exception as e:
            if self.logger:
                self.logger.log_error(
                    f"Unexpected error during initialization: {str(e)}",
                    e,
                    {
                        "config_path": self.config_path,
                        "error_type": type(e).__name__
                    }
                )
            else:
                print(f"ERROR: Unexpected error during initialization: {str(e)}")
            return False
    
    def execute_trading_cycle(self, market_wait_timeout_minutes: int = 60) -> ExecutionSummary:
        """Execute a complete trading cycle for all configured symbols.
        
        This method:
        1. Verifies the bot is initialized
        2. Checks market status (but proceeds regardless)
        3. Processes each configured symbol
        4. Submits orders (queued if market closed, executed immediately if open)
        5. Collects results into an ExecutionSummary
        
        Args:
            market_wait_timeout_minutes: Not used (kept for backward compatibility)
        
        Returns:
            ExecutionSummary with results of the trading cycle
            
        Raises:
            RuntimeError: If bot is not initialized
        
        Note:
            Orders are submitted with GTC (Good-Til-Canceled) time-in-force,
            allowing them to be placed when market is closed. They will be
            queued and executed when the market opens.
        """
        if not self._initialized:
            raise RuntimeError("Trading bot not initialized. Call initialize() first.")
        
        execution_date = datetime.now()
        self.logger.log_info("Starting trading cycle", {"execution_date": execution_date.isoformat()})
        
        # Check market status but don't block execution
        try:
            is_market_open = self.broker_client.is_market_open()
            if is_market_open:
                self.logger.log_info("Market is currently OPEN - orders will be executed immediately")
            else:
                self.logger.log_warning(
                    "Market is currently CLOSED - orders will be queued and executed when market opens",
                    {"note": "Orders will appear in Alpaca dashboard as pending"}
                )
        except Exception as e:
            self.logger.log_warning(
                f"Could not check market status: {str(e)} - proceeding anyway",
                {"error": str(e)}
            )
        
        # Get list of symbols to process
        symbols = self.config.symbols
        self.logger.log_info(
            f"Processing {len(symbols)} symbols",
            {"symbols": symbols}
        )
        
        # Validate symbols before processing
        valid_symbols = []
        invalid_symbols = []
        
        for symbol in symbols:
            if self._validate_symbol(symbol):
                valid_symbols.append(symbol)
            else:
                invalid_symbols.append(symbol)
        
        if invalid_symbols:
            self.logger.log_warning(
                f"Skipping {len(invalid_symbols)} invalid symbol(s): {', '.join(invalid_symbols)}",
                {"invalid_symbols": invalid_symbols}
            )
        
        if not valid_symbols:
            self.logger.log_error("No valid symbols to process")
            return ExecutionSummary(
                execution_date=execution_date,
                total_symbols=len(symbols),
                successful_trades=0,
                failed_trades=len(symbols),
                trade_results=[]
            )
        
        self.logger.log_info(
            f"Processing {len(valid_symbols)} valid symbol(s)",
            {"valid_symbols": valid_symbols}
        )
        
        # Process each valid symbol and collect results
        trade_results: List[TradeResult] = []
        
        for symbol in valid_symbols:
            try:
                self.logger.log_info(f"Processing symbol: {symbol}")
                
                # Route to appropriate strategy
                if self.config.strategy == 'cs':  # Collar Strategy
                    trade_result = self.process_collar_symbol(symbol)
                elif self.config.strategy == 'cc':  # Covered Call Strategy
                    trade_result = self.process_covered_call_symbol(symbol)
                elif self.config.strategy == 'ws':  # Wheel Strategy
                    trade_result = self.process_wheel_symbol(symbol)
                elif self.config.strategy == 'lcc':  # Laddered Covered Call
                    # This returns multiple results (one per leg)
                    ladder_results = self.process_laddered_cc_symbol(symbol)
                    trade_results.extend(ladder_results)
                    continue  # Skip the single append below
                elif self.config.strategy == 'dc':  # Double Calendar
                    trade_result = self.process_double_calendar_symbol(symbol)
                elif self.config.strategy == 'bf':  # Butterfly
                    trade_result = self.process_butterfly_symbol(symbol)
                elif self.config.strategy == 'mp':  # Married Put
                    trade_result = self.process_married_put_symbol(symbol)
                elif self.config.strategy == 'ls':  # Long Straddle
                    trade_result = self.process_long_straddle_symbol(symbol)
                elif self.config.strategy == 'ib':  # Iron Butterfly
                    trade_result = self.process_iron_butterfly_symbol(symbol)
                elif self.config.strategy == 'ss':  # Short Strangle
                    trade_result = self.process_short_strangle_symbol(symbol)
                else:  # pcs = Put Credit Spread (default)
                    trade_result = self.process_symbol(symbol)
                    
                trade_results.append(trade_result)
                
            except Exception as e:
                # Ensure failure for one symbol doesn't stop processing others
                self.logger.log_error(
                    f"Unexpected error processing symbol {symbol}",
                    e,
                    {
                        "symbol": symbol,
                        "error_type": type(e).__name__,
                        "execution_date": execution_date.isoformat()
                    }
                )
                
                # Create a failed trade result
                failed_result = TradeResult(
                    symbol=symbol,
                    success=False,
                    order_id=None,
                    short_strike=0.0,
                    long_strike=0.0,
                    expiration=date.today(),
                    quantity=0,
                    filled_price=None,
                    error_message=f"Unexpected error: {type(e).__name__}: {str(e)}",
                    timestamp=datetime.now()
                )
                trade_results.append(failed_result)
        
        # Calculate summary statistics
        successful_trades = sum(1 for result in trade_results if result.success)
        failed_trades = len(trade_results) - successful_trades
        
        # Create execution summary
        summary = ExecutionSummary(
            execution_date=execution_date,
            total_symbols=len(symbols),
            successful_trades=successful_trades,
            failed_trades=failed_trades,
            trade_results=trade_results
        )
        
        # Log execution summary
        self._log_execution_summary(summary)
        
        return summary
    
    def _validate_symbol(self, symbol: str) -> bool:
        """Validate if a symbol is valid for trading.
        
        Args:
            symbol: Stock symbol to validate
            
        Returns:
            True if symbol is valid, False otherwise
        """
        # Basic validation: symbol should be uppercase letters only, 1-5 characters
        if not symbol:
            self.logger.log_warning(
                "Empty symbol provided",
                {"symbol": symbol}
            )
            return False
        
        if not isinstance(symbol, str):
            self.logger.log_warning(
                "Symbol must be a string",
                {"symbol": symbol, "type": type(symbol).__name__}
            )
            return False
        
        # Check if symbol contains only uppercase letters
        if not symbol.isupper() or not symbol.isalpha():
            self.logger.log_warning(
                f"Invalid symbol format: {symbol}. Symbol must contain only uppercase letters",
                {"symbol": symbol}
            )
            return False
        
        # Check symbol length (typically 1-5 characters for US stocks)
        if len(symbol) < 1 or len(symbol) > 5:
            self.logger.log_warning(
                f"Invalid symbol length: {symbol}. Symbol must be 1-5 characters",
                {"symbol": symbol, "length": len(symbol)}
            )
            return False
        
        # In dry-run mode or if market is closed, skip price validation
        if self.dry_run:
            self.logger.log_info(
                f"[DRY-RUN MODE] Symbol {symbol} passed basic validation (skipping price check)",
                {"symbol": symbol, "dry_run": True}
            )
            return True
        
        # Try to verify symbol exists by fetching price
        # If this fails (market closed, API issue), accept the symbol anyway
        try:
            price = self.broker_client.get_current_price(symbol)
            if price <= 0:
                self.logger.log_warning(
                    f"Invalid price for symbol {symbol}: ${price}",
                    {"symbol": symbol, "price": price}
                )
                return False
            
            self.logger.log_info(
                f"Symbol {symbol} validated successfully",
                {"symbol": symbol, "price": price}
            )
            return True
            
        except Exception as e:
            # If we can't validate (market closed, API issue), accept the symbol
            self.logger.log_warning(
                f"Could not validate {symbol} (market may be closed): {str(e)}",
                {"symbol": symbol, "error": str(e)}
            )
            self.logger.log_info(
                f"Accepting {symbol} despite validation failure (will attempt to trade)",
                {"symbol": symbol}
            )
            return True  # Accept symbol even if validation fails
    
    def _wait_for_market_open(self, timeout_minutes: int = 60) -> bool:
        """Wait for market to open with timeout.
        
        This method checks if the market is open. If closed, it waits until
        the market opens or the timeout is reached.
        
        Args:
            timeout_minutes: Maximum minutes to wait for market to open
            
        Returns:
            True if market is open, False if timeout reached
        """
        try:
            # Check if market is currently open
            if self.broker_client.is_market_open():
                self.logger.log_info("Market is open, proceeding with trading cycle")
                return True
            
            # Market is closed, get next open time
            self.logger.log_warning("Market is currently closed")
            
            try:
                next_open = self.broker_client.get_market_open_time()
                now = datetime.now(next_open.tzinfo)  # Match timezone
                wait_time = (next_open - now).total_seconds()
                
                self.logger.log_info(
                    f"Market will open at {next_open.isoformat()}",
                    {
                        "next_open": next_open.isoformat(),
                        "wait_seconds": int(wait_time)
                    }
                )
                
                # Check if wait time exceeds timeout
                timeout_seconds = timeout_minutes * 60
                if wait_time > timeout_seconds:
                    self.logger.log_warning(
                        f"Market open time ({wait_time/60:.1f} min) exceeds timeout ({timeout_minutes} min)",
                        {
                            "wait_minutes": wait_time / 60,
                            "timeout_minutes": timeout_minutes
                        }
                    )
                    return False
                
                # Wait until market opens
                if wait_time > 0:
                    self.logger.log_info(
                        f"Waiting {wait_time/60:.1f} minutes for market to open",
                        {"wait_minutes": wait_time / 60}
                    )
                    
                    # Sleep in intervals to allow for interruption
                    sleep_interval = 60  # Check every minute
                    elapsed = 0
                    
                    while elapsed < wait_time:
                        time.sleep(min(sleep_interval, wait_time - elapsed))
                        elapsed += sleep_interval
                        
                        # Check if market opened early
                        if self.broker_client.is_market_open():
                            self.logger.log_info("Market opened, proceeding with trading cycle")
                            return True
                    
                    # Final check after wait
                    if self.broker_client.is_market_open():
                        self.logger.log_info("Market is now open, proceeding with trading cycle")
                        return True
                    else:
                        self.logger.log_warning("Market still closed after waiting")
                        return False
                
            except Exception as e:
                self.logger.log_error(
                    "Failed to get market open time, cannot wait for market",
                    e
                )
                return False
                
        except Exception as e:
            self.logger.log_error(
                "Failed to check market status",
                e
            )
            # If we can't check market status, log error but don't block execution
            # This allows the bot to attempt trading even if market check fails
            self.logger.log_warning("Proceeding with trading cycle despite market check failure")
            return True
    
    def process_symbol(self, symbol: str) -> TradeResult:
        """Process a single symbol through the complete trading workflow.
        
        This method:
        1. Gets current market price
        2. Calculates spread parameters using StrategyCalculator
        3. Retrieves option chain and finds available strikes
        4. Submits order using OrderManager
        
        Args:
            symbol: Stock symbol to process (e.g., 'AAPL')
            
        Returns:
            TradeResult with execution details
        """
        timestamp = datetime.now()
        
        try:
            # Get current market price
            self.logger.log_info(f"Fetching current price for {symbol}")
            current_price = self.broker_client.get_current_price(symbol)
            self.logger.log_info(
                f"Current price for {symbol}: ${current_price:.2f}",
                {"symbol": symbol, "price": current_price}
            )
            
            # Calculate spread parameters
            self.logger.log_info(f"Calculating spread parameters for {symbol}")
            
            # Calculate short strike (below market price)
            short_strike = self.strategy_calculator.calculate_short_strike(
                current_price=current_price,
                offset_percent=self.config.strike_offset_percent,
                offset_dollars=self.config.strike_offset_dollars
            )
            
            # Calculate long strike (below short strike)
            long_strike = self.strategy_calculator.calculate_long_strike(
                short_strike=short_strike,
                spread_width=self.config.spread_width
            )
            
            # Calculate expiration date
            expiration = self.strategy_calculator.calculate_expiration_date(
                execution_date=date.today(),
                offset_weeks=self.config.expiration_offset_weeks
            )
            
            self.logger.log_info(
                f"Calculated strikes for {symbol}",
                {
                    "symbol": symbol,
                    "short_strike": f"${short_strike:.2f}",
                    "long_strike": f"${long_strike:.2f}",
                    "expiration": expiration.isoformat(),
                    "spread_width": f"${short_strike - long_strike:.2f}"
                }
            )
            
            # Retrieve option chain and find available strikes
            self.logger.log_info(f"Retrieving option chain for {symbol}")
            
            # Store original calculated strikes for logging
            original_short_strike = short_strike
            original_long_strike = long_strike
            
            try:
                option_chain = self.broker_client.get_option_chain(symbol, expiration)
                available_strikes = sorted([contract.strike for contract in option_chain])
                
                if not available_strikes:
                    error_msg = "No option strikes available in option chain"
                    self.logger.log_warning(
                        f"Skipping {symbol} - {error_msg}",
                        {"symbol": symbol, "expiration": expiration.isoformat()}
                    )
                    return TradeResult(
                        symbol=symbol,
                        success=False,
                        order_id=None,
                        short_strike=short_strike,
                        long_strike=long_strike,
                        expiration=expiration,
                        quantity=self.config.contract_quantity,
                        filled_price=None,
                        error_message=error_msg,
                        timestamp=timestamp
                    )
                
                self.logger.log_info(
                    f"Retrieved {len(available_strikes)} available strikes for {symbol}",
                    {
                        "symbol": symbol,
                        "strike_count": len(available_strikes),
                        "min_strike": min(available_strikes),
                        "max_strike": max(available_strikes)
                    }
                )
                
                # Find nearest available strikes below target (for put credit spreads)
                try:
                    short_strike = self.strategy_calculator.find_nearest_strike_below(
                        target_strike=short_strike,
                        available_strikes=available_strikes
                    )
                except ValueError as e:
                    error_msg = f"Cannot find suitable short strike: {str(e)}"
                    self.logger.log_warning(
                        f"Skipping {symbol} - {error_msg}",
                        {"symbol": symbol, "target_strike": original_short_strike}
                    )
                    return TradeResult(
                        symbol=symbol,
                        success=False,
                        order_id=None,
                        short_strike=original_short_strike,
                        long_strike=original_long_strike,
                        expiration=expiration,
                        quantity=self.config.contract_quantity,
                        filled_price=None,
                        error_message=error_msg,
                        timestamp=timestamp
                    )
                
                try:
                    long_strike = self.strategy_calculator.find_nearest_strike_below(
                        target_strike=long_strike,
                        available_strikes=available_strikes
                    )
                except ValueError as e:
                    error_msg = f"Cannot find suitable long strike: {str(e)}"
                    self.logger.log_warning(
                        f"Skipping {symbol} - {error_msg}",
                        {"symbol": symbol, "target_strike": original_long_strike}
                    )
                    return TradeResult(
                        symbol=symbol,
                        success=False,
                        order_id=None,
                        short_strike=short_strike,
                        long_strike=original_long_strike,
                        expiration=expiration,
                        quantity=self.config.contract_quantity,
                        filled_price=None,
                        error_message=error_msg,
                        timestamp=timestamp
                    )
                
                # Check if we had to use fallback strikes (different from calculated)
                if abs(short_strike - original_short_strike) > 0.01 or abs(long_strike - original_long_strike) > 0.01:
                    self.logger.log_info(
                        f"Using fallback strikes for {symbol} (calculated strikes not available)",
                        {
                            "symbol": symbol,
                            "calculated_short": f"${original_short_strike:.2f}",
                            "actual_short": f"${short_strike:.2f}",
                            "calculated_long": f"${original_long_strike:.2f}",
                            "actual_long": f"${long_strike:.2f}"
                        }
                    )
                else:
                    self.logger.log_info(
                        f"Using calculated strikes for {symbol} (exact match found)",
                        {
                            "symbol": symbol,
                            "short_strike": f"${short_strike:.2f}",
                            "long_strike": f"${long_strike:.2f}"
                        }
                    )
                
            except ValueError as e:
                # Option chain unavailable - log and skip symbol
                error_msg = f"Option chain unavailable: {str(e)}"
                self.logger.log_warning(
                    f"Skipping {symbol} - {error_msg}",
                    {"symbol": symbol, "error": error_msg}
                )
                
                return TradeResult(
                    symbol=symbol,
                    success=False,
                    order_id=None,
                    short_strike=original_short_strike,
                    long_strike=original_long_strike,
                    expiration=expiration,
                    quantity=self.config.contract_quantity,
                    filled_price=None,
                    error_message=error_msg,
                    timestamp=timestamp
                )
            
            # Validate spread parameters
            actual_spread_width = short_strike - long_strike
            
            # Check if spread width is reasonable (within 50% of configured width)
            configured_width = self.config.spread_width
            if actual_spread_width < configured_width * 0.5:
                error_msg = f"Actual spread width (${actual_spread_width:.2f}) is too narrow compared to configured (${configured_width:.2f})"
                self.logger.log_warning(
                    f"Skipping {symbol} - {error_msg}",
                    {
                        "symbol": symbol,
                        "actual_width": actual_spread_width,
                        "configured_width": configured_width
                    }
                )
                return TradeResult(
                    symbol=symbol,
                    success=False,
                    order_id=None,
                    short_strike=short_strike,
                    long_strike=long_strike,
                    expiration=expiration,
                    quantity=self.config.contract_quantity,
                    filled_price=None,
                    error_message=error_msg,
                    timestamp=timestamp
                )
            
            spread_params = SpreadParameters(
                symbol=symbol,
                short_strike=short_strike,
                long_strike=long_strike,
                expiration=expiration,
                current_price=current_price,
                spread_width=actual_spread_width
            )
            
            try:
                self.strategy_calculator.validate_spread_parameters(spread_params)
            except ValueError as e:
                error_msg = f"Spread validation failed: {str(e)}"
                self.logger.log_error(
                    f"Invalid spread parameters for {symbol}",
                    e,
                    {"symbol": symbol}
                )
                
                return TradeResult(
                    symbol=symbol,
                    success=False,
                    order_id=None,
                    short_strike=short_strike,
                    long_strike=long_strike,
                    expiration=expiration,
                    quantity=self.config.contract_quantity,
                    filled_price=None,
                    error_message=error_msg,
                    timestamp=timestamp
                )
            
            # Submit order using OrderManager
            self.logger.log_info(f"Submitting order for {symbol}")
            trade_result = self.order_manager.submit_order_with_error_handling(
                symbol=symbol,
                short_strike=short_strike,
                long_strike=long_strike,
                expiration=expiration,
                quantity=self.config.contract_quantity,
                max_retries=3
            )
            
            return trade_result
            
        except ValueError as e:
            # Handle price data unavailable or other value errors
            error_msg = f"Data error: {str(e)}"
            self.logger.log_error(
                f"Failed to process {symbol}: {error_msg}",
                e,
                {
                    "symbol": symbol,
                    "error_type": "ValueError",
                    "timestamp": timestamp.isoformat()
                }
            )
            
            return TradeResult(
                symbol=symbol,
                success=False,
                order_id=None,
                short_strike=0.0,
                long_strike=0.0,
                expiration=date.today(),
                quantity=self.config.contract_quantity,
                filled_price=None,
                error_message=error_msg,
                timestamp=timestamp
            )
            
        except Exception as e:
            # Handle any unexpected errors
            error_msg = f"Unexpected error: {type(e).__name__}: {str(e)}"
            self.logger.log_error(
                f"Unexpected error processing {symbol}",
                e,
                {
                    "symbol": symbol,
                    "error_type": type(e).__name__,
                    "timestamp": timestamp.isoformat()
                }
            )
            
            return TradeResult(
                symbol=symbol,
                success=False,
                order_id=None,
                short_strike=0.0,
                long_strike=0.0,
                expiration=date.today(),
                quantity=self.config.contract_quantity,
                filled_price=None,
                error_message=error_msg,
                timestamp=timestamp
            )
    
    def process_collar_symbol(self, symbol: str) -> TradeResult:
        """Process a single symbol using collar strategy.
        
        Collar strategy:
        1. Assumes you own 100 shares of the stock
        2. Buys a protective put (downside protection)
        3. Sells a covered call (income generation)
        
        Args:
            symbol: Stock symbol to process
            
        Returns:
            TradeResult with execution details
        """
        timestamp = datetime.now()
        
        try:
            # Get current market price
            self.logger.log_info(f"Fetching current price for {symbol} (Collar Strategy)")
            current_price = self.broker_client.get_current_price(symbol)
            self.logger.log_info(
                f"Current price for {symbol}: ${current_price:.2f}",
                {"symbol": symbol, "price": current_price, "strategy": "collar"}
            )
            
            # Calculate collar parameters
            self.logger.log_info(f"Calculating collar parameters for {symbol}")
            
            # Calculate target strikes
            put_strike_target = self.collar_calculator.calculate_put_strike(current_price)
            call_strike_target = self.collar_calculator.calculate_call_strike(current_price)
            
            # Calculate expiration
            expiration = self.strategy_calculator.calculate_expiration_date(
                execution_date=date.today(),
                offset_weeks=self.config.expiration_offset_weeks
            )
            
            self.logger.log_info(
                f"Calculated collar targets for {symbol}",
                {
                    "symbol": symbol,
                    "put_target": f"${put_strike_target:.2f}",
                    "call_target": f"${call_strike_target:.2f}",
                    "expiration": expiration.isoformat()
                }
            )
            
            # Get option chain
            self.logger.log_info(f"Retrieving option chain for {symbol}")
            option_chain = self.broker_client.get_option_chain(symbol, expiration)
            available_strikes = sorted(list(set([contract.strike for contract in option_chain])))
            
            self.logger.log_info(
                f"Retrieved {len(available_strikes)} available strikes for {symbol}",
                {"symbol": symbol, "strike_count": len(available_strikes)}
            )
            
            # Find actual strikes
            put_strike = self.collar_calculator.find_nearest_strike_below(
                put_strike_target, available_strikes
            )
            call_strike = self.collar_calculator.find_nearest_strike_above(
                call_strike_target, available_strikes
            )
            
            self.logger.log_info(
                f"Selected collar strikes for {symbol}",
                {
                    "symbol": symbol,
                    "put_strike": f"${put_strike:.2f}",
                    "call_strike": f"${call_strike:.2f}",
                    "protection_range": f"${put_strike:.2f} - ${call_strike:.2f}"
                }
            )
            
            # Calculate number of collars
            num_collars = self.collar_calculator.calculate_num_collars(
                self.config.collar_shares_per_symbol
            )
            
            # Create collar parameters
            collar_params = CollarParameters(
                symbol=symbol,
                current_price=current_price,
                shares_owned=self.config.collar_shares_per_symbol,
                put_strike=put_strike,
                put_expiration=expiration,
                call_strike=call_strike,
                call_expiration=expiration,
                num_collars=num_collars
            )
            
            # Validate collar parameters
            self.collar_calculator.validate_collar_parameters(collar_params)
            
            # Submit collar order
            self.logger.log_info(f"Submitting collar order for {symbol}")
            trade_result = self.order_manager.submit_collar_order(
                symbol=symbol,
                put_strike=put_strike,
                call_strike=call_strike,
                expiration=expiration,
                num_collars=num_collars
            )
            
            return trade_result
            
        except Exception as e:
            error_msg = f"Unexpected error: {type(e).__name__}: {str(e)}"
            self.logger.log_error(
                f"Unexpected error processing collar for {symbol}",
                e,
                {
                    "symbol": symbol,
                    "error_type": type(e).__name__,
                    "timestamp": timestamp.isoformat()
                }
            )
            
            return TradeResult(
                symbol=symbol,
                success=False,
                order_id=None,
                short_strike=0.0,
                long_strike=0.0,
                expiration=date.today(),
                quantity=0,
                filled_price=None,
                error_message=error_msg,
                timestamp=timestamp
            )

    def process_covered_call_symbol(self, symbol: str) -> TradeResult:
        """Process a single symbol using covered call strategy.
        
        Covered call strategy:
        1. Checks that you own 100+ shares of the stock
        2. Sells a call option above current price for income
        
        Args:
            symbol: Stock symbol to process
            
        Returns:
            TradeResult with execution details
        """
        timestamp = datetime.now()
        
        try:
            # Check position first
            position = self.broker_client.get_position(symbol)
            if not position or position.quantity < 100:
                shares = position.quantity if position else 0
                error_msg = f"Insufficient shares: need 100, have {shares}"
                self.logger.log_warning(
                    f"Cannot sell covered call for {symbol}: {error_msg}",
                    {"symbol": symbol, "shares_owned": shares}
                )
                return TradeResult(
                    symbol=symbol,
                    success=False,
                    order_id=None,
                    short_strike=0.0,
                    long_strike=0.0,
                    expiration=date.today(),
                    quantity=0,
                    filled_price=None,
                    error_message=error_msg,
                    timestamp=timestamp
                )
            
            shares_owned = position.quantity
            num_contracts = self.covered_call_calculator.calculate_num_contracts(shares_owned)
            
            # Get current market price
            self.logger.log_info(f"Fetching current price for {symbol} (Covered Call Strategy)")
            current_price = self.broker_client.get_current_price(symbol)
            self.logger.log_info(
                f"Current price for {symbol}: ${current_price:.2f}",
                {"symbol": symbol, "price": current_price, "strategy": "covered_call"}
            )
            
            # Calculate call strike target
            call_strike_target = self.covered_call_calculator.calculate_call_strike(current_price)
            
            # Calculate expiration (~10 days out)
            expiration = self.covered_call_calculator.calculate_expiration()
            
            self.logger.log_info(
                f"Calculated covered call targets for {symbol}",
                {
                    "symbol": symbol,
                    "call_target": f"${call_strike_target:.2f}",
                    "expiration": expiration.isoformat(),
                    "shares_owned": shares_owned,
                    "num_contracts": num_contracts
                }
            )
            
            # Get option chain
            self.logger.log_info(f"Retrieving option chain for {symbol}")
            option_chain = self.broker_client.get_option_chain(symbol, expiration)
            available_strikes = sorted(list(set([contract.strike for contract in option_chain])))
            
            # Find actual strike
            call_strike = self.covered_call_calculator.find_nearest_strike_above(
                call_strike_target, available_strikes
            )
            
            self.logger.log_info(
                f"Selected covered call strike for {symbol}",
                {
                    "symbol": symbol,
                    "call_strike": f"${call_strike:.2f}",
                    "expiration": expiration.isoformat()
                }
            )
            
            # Submit covered call order
            self.logger.log_info(f"Submitting covered call order for {symbol}")
            order_result = self.broker_client.submit_covered_call_order(
                symbol=symbol,
                call_strike=call_strike,
                expiration=expiration,
                num_contracts=num_contracts
            )
            
            if order_result.success:
                return TradeResult(
                    symbol=symbol,
                    success=True,
                    order_id=order_result.order_id,
                    short_strike=call_strike,
                    long_strike=0.0,
                    expiration=expiration,
                    quantity=num_contracts,
                    filled_price=None,
                    error_message=None,
                    timestamp=timestamp
                )
            else:
                return TradeResult(
                    symbol=symbol,
                    success=False,
                    order_id=None,
                    short_strike=call_strike,
                    long_strike=0.0,
                    expiration=expiration,
                    quantity=num_contracts,
                    filled_price=None,
                    error_message=order_result.error_message,
                    timestamp=timestamp
                )
            
        except Exception as e:
            error_msg = f"Unexpected error: {type(e).__name__}: {str(e)}"
            self.logger.log_error(
                f"Unexpected error processing covered call for {symbol}",
                e,
                {
                    "symbol": symbol,
                    "error_type": type(e).__name__,
                    "timestamp": timestamp.isoformat()
                }
            )
            
            return TradeResult(
                symbol=symbol,
                success=False,
                order_id=None,
                short_strike=0.0,
                long_strike=0.0,
                expiration=date.today(),
                quantity=0,
                filled_price=None,
                error_message=error_msg,
                timestamp=timestamp
            )

    def process_wheel_symbol(self, symbol: str) -> TradeResult:
        """Process a single symbol using the Wheel strategy.
        
        The Wheel Strategy automatically determines the phase:
        - If you DON'T own 100+ shares → Sell cash-secured put
        - If you DO own 100+ shares → Sell covered call
        
        Args:
            symbol: Stock symbol to process
            
        Returns:
            TradeResult with execution details
        """
        timestamp = datetime.now()
        
        try:
            # Check current position to determine phase
            position = self.broker_client.get_position(symbol)
            shares_owned = position.quantity if position else 0
            
            phase = self.wheel_calculator.determine_phase(shares_owned)
            
            self.logger.log_info(
                f"Wheel strategy for {symbol}: Phase = {'Covered Call' if phase == 'cc' else 'Cash-Secured Put'}",
                {"symbol": symbol, "shares_owned": shares_owned, "phase": phase}
            )
            
            # Get current market price
            current_price = self.broker_client.get_current_price(symbol)
            self.logger.log_info(
                f"Current price for {symbol}: ${current_price:.2f}",
                {"symbol": symbol, "price": current_price, "strategy": "wheel"}
            )
            
            # Calculate expiration
            expiration = self.wheel_calculator.calculate_expiration()
            
            # Get option chain
            option_chain = self.broker_client.get_option_chain(symbol, expiration)
            available_strikes = sorted(list(set([contract.strike for contract in option_chain])))
            
            if phase == 'cc':
                # Covered Call phase - sell calls
                call_strike_target = self.wheel_calculator.calculate_call_strike(current_price)
                call_strike = self.wheel_calculator.find_nearest_strike_above(
                    call_strike_target, available_strikes
                )
                num_contracts = self.wheel_calculator.calculate_num_contracts(shares_owned)
                
                self.logger.log_info(
                    f"Wheel CC: Selling {num_contracts} call(s) at ${call_strike:.2f}",
                    {"symbol": symbol, "call_strike": call_strike, "expiration": expiration.isoformat()}
                )
                
                order_result = self.broker_client.submit_covered_call_order(
                    symbol=symbol,
                    call_strike=call_strike,
                    expiration=expiration,
                    num_contracts=num_contracts
                )
                
                return TradeResult(
                    symbol=symbol,
                    success=order_result.success,
                    order_id=order_result.order_id,
                    short_strike=call_strike,
                    long_strike=0.0,
                    expiration=expiration,
                    quantity=num_contracts,
                    filled_price=None,
                    error_message=order_result.error_message,
                    timestamp=timestamp
                )
            else:
                # Cash-Secured Put phase - sell puts
                put_strike_target = self.wheel_calculator.calculate_put_strike(current_price)
                put_strike = self.wheel_calculator.find_nearest_strike_below(
                    put_strike_target, available_strikes
                )
                num_contracts = 1  # Default to 1 contract for CSP
                
                self.logger.log_info(
                    f"Wheel CSP: Selling {num_contracts} put(s) at ${put_strike:.2f}",
                    {"symbol": symbol, "put_strike": put_strike, "expiration": expiration.isoformat()}
                )
                
                order_result = self.broker_client.submit_cash_secured_put_order(
                    symbol=symbol,
                    put_strike=put_strike,
                    expiration=expiration,
                    num_contracts=num_contracts
                )
                
                return TradeResult(
                    symbol=symbol,
                    success=order_result.success,
                    order_id=order_result.order_id,
                    short_strike=put_strike,
                    long_strike=0.0,
                    expiration=expiration,
                    quantity=num_contracts,
                    filled_price=None,
                    error_message=order_result.error_message,
                    timestamp=timestamp
                )
            
        except Exception as e:
            error_msg = f"Unexpected error: {type(e).__name__}: {str(e)}"
            self.logger.log_error(
                f"Unexpected error processing wheel for {symbol}",
                e,
                {"symbol": symbol, "error_type": type(e).__name__, "timestamp": timestamp.isoformat()}
            )
            
            return TradeResult(
                symbol=symbol,
                success=False,
                order_id=None,
                short_strike=0.0,
                long_strike=0.0,
                expiration=date.today(),
                quantity=0,
                filled_price=None,
                error_message=error_msg,
                timestamp=timestamp
            )

    def process_laddered_cc_symbol(self, symbol: str) -> List[TradeResult]:
        """Process a single symbol using Laddered Covered Call strategy.
        
        Sells covered calls on 2/3 of holdings across 5 expiration dates.
        Each leg = 20% of the covered portion.
        
        Args:
            symbol: Stock symbol to process
            
        Returns:
            List of TradeResult (one per leg)
        """
        timestamp = datetime.now()
        results = []
        
        try:
            # Check current position
            position = self.broker_client.get_position(symbol)
            if not position or position.quantity < 100:
                shares = position.quantity if position else 0
                error_msg = f"Insufficient shares: need 100+, have {shares}"
                self.logger.log_warning(
                    f"Cannot execute laddered CC for {symbol}: {error_msg}",
                    {"symbol": symbol, "shares_owned": shares}
                )
                return [TradeResult(
                    symbol=symbol,
                    success=False,
                    order_id=None,
                    short_strike=0.0,
                    long_strike=0.0,
                    expiration=date.today(),
                    quantity=0,
                    filled_price=None,
                    error_message=error_msg,
                    timestamp=timestamp
                )]
            
            shares_owned = position.quantity
            
            # Get current price
            current_price = self.broker_client.get_current_price(symbol)
            self.logger.log_info(
                f"Laddered CC for {symbol}: ${current_price:.2f}, {shares_owned} shares",
                {"symbol": symbol, "price": current_price, "shares": shares_owned}
            )
            
            # Calculate ladder
            ladder = self.laddered_cc_calculator.calculate_ladder(shares_owned, current_price)
            call_strike_target = self.laddered_cc_calculator.calculate_call_strike(current_price)
            
            total_contracts = sum(leg['contracts'] for leg in ladder)
            self.logger.log_info(
                f"Laddered CC: {total_contracts} contracts across {len(ladder)} legs",
                {"symbol": symbol, "ladder": ladder}
            )
            
            # Process each leg
            for leg in ladder:
                exp = leg['expiration']
                num_contracts = leg['contracts']
                leg_num = leg['leg']
                
                try:
                    # Get option chain for this expiration
                    option_chain = self.broker_client.get_option_chain(symbol, exp)
                    available_strikes = sorted(list(set([c.strike for c in option_chain])))
                    
                    # Find actual strike
                    call_strike = self.laddered_cc_calculator.find_nearest_strike_above(
                        call_strike_target, available_strikes
                    )
                    
                    self.logger.log_info(
                        f"Leg {leg_num}: {num_contracts} call(s) @ ${call_strike:.2f}, exp {exp}",
                        {"symbol": symbol, "leg": leg_num, "strike": call_strike, "exp": exp.isoformat()}
                    )
                    
                    # Submit order
                    order_result = self.broker_client.submit_covered_call_order(
                        symbol=symbol,
                        call_strike=call_strike,
                        expiration=exp,
                        num_contracts=num_contracts
                    )
                    
                    results.append(TradeResult(
                        symbol=f"{symbol}_L{leg_num}",
                        success=order_result.success,
                        order_id=order_result.order_id,
                        short_strike=call_strike,
                        long_strike=0.0,
                        expiration=exp,
                        quantity=num_contracts,
                        filled_price=None,
                        error_message=order_result.error_message,
                        timestamp=timestamp
                    ))
                    
                except Exception as leg_error:
                    self.logger.log_error(f"Leg {leg_num} failed: {str(leg_error)}", leg_error)
                    results.append(TradeResult(
                        symbol=f"{symbol}_L{leg_num}",
                        success=False,
                        order_id=None,
                        short_strike=call_strike_target,
                        long_strike=0.0,
                        expiration=exp,
                        quantity=num_contracts,
                        filled_price=None,
                        error_message=str(leg_error),
                        timestamp=timestamp
                    ))
            
            return results
            
        except Exception as e:
            error_msg = f"Unexpected error: {type(e).__name__}: {str(e)}"
            self.logger.log_error(f"Laddered CC failed for {symbol}", e)
            return [TradeResult(
                symbol=symbol,
                success=False,
                order_id=None,
                short_strike=0.0,
                long_strike=0.0,
                expiration=date.today(),
                quantity=0,
                filled_price=None,
                error_message=error_msg,
                timestamp=timestamp
            )]

    def process_double_calendar_symbol(self, symbol: str) -> TradeResult:
        """Process a double calendar spread on a symbol.
        
        Double Calendar:
        - Sell short-term put + Buy long-term put (lower strike)
        - Sell short-term call + Buy long-term call (higher strike)
        
        Args:
            symbol: Stock symbol (typically QQQ)
            
        Returns:
            TradeResult with execution details
        """
        timestamp = datetime.now()
        
        try:
            # Get current price
            current_price = self.broker_client.get_current_price(symbol)
            self.logger.log_info(
                f"Double Calendar for {symbol}: ${current_price:.2f}",
                {"symbol": symbol, "price": current_price, "strategy": "double_calendar"}
            )
            
            # Calculate strikes
            put_strike_target = self.double_calendar_calculator.calculate_put_strike(current_price)
            call_strike_target = self.double_calendar_calculator.calculate_call_strike(current_price)
            
            # Calculate expirations
            short_exp = self.double_calendar_calculator.calculate_short_expiration()
            long_exp = self.double_calendar_calculator.calculate_long_expiration()
            
            self.logger.log_info(
                f"DC targets: Put ${put_strike_target:.2f}, Call ${call_strike_target:.2f}",
                {
                    "symbol": symbol,
                    "put_target": put_strike_target,
                    "call_target": call_strike_target,
                    "short_exp": short_exp.isoformat(),
                    "long_exp": long_exp.isoformat()
                }
            )
            
            # Get option chains for both expirations
            short_chain = self.broker_client.get_option_chain(symbol, short_exp)
            long_chain = self.broker_client.get_option_chain(symbol, long_exp)
            
            short_strikes = sorted(list(set([c.strike for c in short_chain])))
            long_strikes = sorted(list(set([c.strike for c in long_chain])))
            
            # Find actual strikes (use strikes available in both chains)
            common_strikes = sorted(list(set(short_strikes) & set(long_strikes)))
            if not common_strikes:
                common_strikes = short_strikes  # Fallback
            
            put_strike = self.double_calendar_calculator.find_nearest_strike_below(
                put_strike_target, common_strikes
            )
            call_strike = self.double_calendar_calculator.find_nearest_strike_above(
                call_strike_target, common_strikes
            )
            
            self.logger.log_info(
                f"DC strikes: Put ${put_strike:.2f}, Call ${call_strike:.2f}",
                {"symbol": symbol, "put_strike": put_strike, "call_strike": call_strike}
            )
            
            # Submit double calendar order
            num_contracts = self.config.contract_quantity
            order_result = self.broker_client.submit_double_calendar_order(
                symbol=symbol,
                put_strike=put_strike,
                call_strike=call_strike,
                short_expiration=short_exp,
                long_expiration=long_exp,
                num_contracts=num_contracts
            )
            
            return TradeResult(
                symbol=symbol,
                success=order_result.success,
                order_id=order_result.order_id,
                short_strike=put_strike,
                long_strike=call_strike,
                expiration=short_exp,
                quantity=num_contracts,
                filled_price=None,
                error_message=order_result.error_message,
                timestamp=timestamp
            )
            
        except Exception as e:
            error_msg = f"Unexpected error: {type(e).__name__}: {str(e)}"
            self.logger.log_error(f"Double calendar failed for {symbol}", e)
            return TradeResult(
                symbol=symbol,
                success=False,
                order_id=None,
                short_strike=0.0,
                long_strike=0.0,
                expiration=date.today(),
                quantity=0,
                filled_price=None,
                error_message=error_msg,
                timestamp=timestamp
            )

    def process_butterfly_symbol(self, symbol: str) -> TradeResult:
        """Process a butterfly spread on a symbol.
        
        Long Call Butterfly:
        - Buy 1 lower strike call
        - Sell 2 middle strike calls (ATM)
        - Buy 1 upper strike call
        
        Args:
            symbol: Stock symbol (typically QQQ)
            
        Returns:
            TradeResult with execution details
        """
        timestamp = datetime.now()
        
        try:
            # Get current price
            current_price = self.broker_client.get_current_price(symbol)
            self.logger.log_info(
                f"Butterfly for {symbol}: ${current_price:.2f}",
                {"symbol": symbol, "price": current_price, "strategy": "butterfly"}
            )
            
            # Calculate expiration
            expiration = self.butterfly_calculator.calculate_expiration()
            
            # Get option chain
            option_chain = self.broker_client.get_option_chain(symbol, expiration)
            available_strikes = sorted(list(set([c.strike for c in option_chain])))
            
            # Calculate strikes
            lower, middle, upper = self.butterfly_calculator.calculate_strikes(
                current_price, available_strikes
            )
            
            wing_width = middle - lower
            
            self.logger.log_info(
                f"Butterfly strikes: ${lower:.2f} / ${middle:.2f} / ${upper:.2f}",
                {
                    "symbol": symbol,
                    "lower": lower,
                    "middle": middle,
                    "upper": upper,
                    "wing_width": wing_width,
                    "expiration": expiration.isoformat()
                }
            )
            
            # Submit butterfly order
            num_butterflies = self.config.contract_quantity
            order_result = self.broker_client.submit_butterfly_order(
                symbol=symbol,
                lower_strike=lower,
                middle_strike=middle,
                upper_strike=upper,
                expiration=expiration,
                num_butterflies=num_butterflies
            )
            
            return TradeResult(
                symbol=symbol,
                success=order_result.success,
                order_id=order_result.order_id,
                short_strike=middle,  # Middle is the "short" (sell 2)
                long_strike=lower,    # Lower is one of the "longs"
                expiration=expiration,
                quantity=num_butterflies,
                filled_price=None,
                error_message=order_result.error_message,
                timestamp=timestamp
            )
            
        except Exception as e:
            error_msg = f"Unexpected error: {type(e).__name__}: {str(e)}"
            self.logger.log_error(f"Butterfly failed for {symbol}", e)
            return TradeResult(
                symbol=symbol,
                success=False,
                order_id=None,
                short_strike=0.0,
                long_strike=0.0,
                expiration=date.today(),
                quantity=0,
                filled_price=None,
                error_message=error_msg,
                timestamp=timestamp
            )

    def process_married_put_symbol(self, symbol: str) -> TradeResult:
        """Process a single symbol using Married Put strategy.
        
        Married Put strategy:
        1. Buy 100 shares of stock
        2. Buy 1 protective put option
        
        This provides downside protection while maintaining unlimited upside.
        
        Args:
            symbol: Stock symbol to process
            
        Returns:
            TradeResult with execution details
        """
        timestamp = datetime.now()
        
        try:
            # Get current market price
            self.logger.log_info(f"Fetching current price for {symbol} (Married Put Strategy)")
            current_price = self.broker_client.get_current_price(symbol)
            self.logger.log_info(
                f"Current price for {symbol}: ${current_price:.2f}",
                {"symbol": symbol, "price": current_price, "strategy": "married_put"}
            )
            
            # Calculate put strike target
            put_strike_target = self.married_put_calculator.calculate_put_strike(current_price)
            
            # Calculate expiration
            expiration = self.married_put_calculator.calculate_expiration()
            
            # Get shares to buy
            shares_to_buy = self.config.mp_shares_per_unit
            
            self.logger.log_info(
                f"Married Put targets for {symbol}",
                {
                    "symbol": symbol,
                    "shares_to_buy": shares_to_buy,
                    "put_target": f"${put_strike_target:.2f}",
                    "expiration": expiration.isoformat(),
                    "estimated_cost": f"${current_price * shares_to_buy:,.2f}"
                }
            )
            
            # Get option chain
            self.logger.log_info(f"Retrieving option chain for {symbol}")
            option_chain = self.broker_client.get_option_chain(symbol, expiration)
            available_strikes = sorted(list(set([contract.strike for contract in option_chain])))
            
            self.logger.log_info(
                f"Retrieved {len(available_strikes)} available strikes for {symbol}",
                {"symbol": symbol, "strike_count": len(available_strikes)}
            )
            
            # Find actual put strike
            put_strike = self.married_put_calculator.find_nearest_strike_below(
                put_strike_target, available_strikes
            )
            
            self.logger.log_info(
                f"Selected married put strike for {symbol}",
                {
                    "symbol": symbol,
                    "put_strike": f"${put_strike:.2f}",
                    "expiration": expiration.isoformat(),
                    "protection_level": f"${put_strike:.2f} ({((current_price - put_strike) / current_price * 100):.1f}% below)"
                }
            )
            
            # Submit married put order
            self.logger.log_info(f"Submitting married put order for {symbol}")
            order_result = self.broker_client.submit_married_put_order(
                symbol=symbol,
                shares=shares_to_buy,
                put_strike=put_strike,
                expiration=expiration
            )
            
            if order_result.success:
                return TradeResult(
                    symbol=symbol,
                    success=True,
                    order_id=order_result.order_id,
                    short_strike=0.0,  # No short position in married put
                    long_strike=put_strike,  # Long put for protection
                    expiration=expiration,
                    quantity=shares_to_buy,
                    filled_price=None,
                    error_message=None,
                    timestamp=timestamp
                )
            else:
                return TradeResult(
                    symbol=symbol,
                    success=False,
                    order_id=None,
                    short_strike=0.0,
                    long_strike=put_strike,
                    expiration=expiration,
                    quantity=shares_to_buy,
                    filled_price=None,
                    error_message=order_result.error_message,
                    timestamp=timestamp
                )
            
        except Exception as e:
            error_msg = f"Unexpected error: {type(e).__name__}: {str(e)}"
            self.logger.log_error(
                f"Unexpected error processing married put for {symbol}",
                e,
                {
                    "symbol": symbol,
                    "error_type": type(e).__name__,
                    "timestamp": timestamp.isoformat()
                }
            )
            
            return TradeResult(
                symbol=symbol,
                success=False,
                order_id=None,
                short_strike=0.0,
                long_strike=0.0,
                expiration=date.today(),
                quantity=0,
                filled_price=None,
                error_message=error_msg,
                timestamp=timestamp
            )

    def process_long_straddle_symbol(self, symbol: str) -> TradeResult:
        """Process a single symbol using Long Straddle strategy.
        
        Long Straddle strategy:
        1. Buy 1 ATM call option
        2. Buy 1 ATM put option (same strike as call)
        
        Profits from significant price movement in either direction.
        Best used when expecting high volatility but unsure of direction.
        
        Args:
            symbol: Stock symbol to process
            
        Returns:
            TradeResult with execution details
        """
        timestamp = datetime.now()
        
        try:
            # Get current market price
            self.logger.log_info(f"Fetching current price for {symbol} (Long Straddle Strategy)")
            current_price = self.broker_client.get_current_price(symbol)
            self.logger.log_info(
                f"Current price for {symbol}: ${current_price:.2f}",
                {"symbol": symbol, "price": current_price, "strategy": "long_straddle"}
            )
            
            # Calculate expiration
            expiration = self.long_straddle_calculator.calculate_expiration()
            
            # Get number of contracts
            num_contracts = self.config.ls_num_contracts
            
            self.logger.log_info(
                f"Long Straddle targets for {symbol}",
                {
                    "symbol": symbol,
                    "target_strike": f"${current_price:.2f} (ATM)",
                    "expiration": expiration.isoformat(),
                    "num_contracts": num_contracts
                }
            )
            
            # Get option chain
            self.logger.log_info(f"Retrieving option chain for {symbol}")
            option_chain = self.broker_client.get_option_chain(symbol, expiration)
            available_strikes = sorted(list(set([contract.strike for contract in option_chain])))
            
            self.logger.log_info(
                f"Retrieved {len(available_strikes)} available strikes for {symbol}",
                {"symbol": symbol, "strike_count": len(available_strikes)}
            )
            
            # Find ATM strike (closest to current price)
            strike = self.long_straddle_calculator.calculate_strike(current_price, available_strikes)
            
            self.logger.log_info(
                f"Selected long straddle strike for {symbol}",
                {
                    "symbol": symbol,
                    "strike": f"${strike:.2f}",
                    "expiration": expiration.isoformat(),
                    "distance_from_atm": f"${abs(strike - current_price):.2f}"
                }
            )
            
            # Submit long straddle order
            self.logger.log_info(f"Submitting long straddle order for {symbol}")
            order_result = self.broker_client.submit_long_straddle_order(
                symbol=symbol,
                strike=strike,
                expiration=expiration,
                num_contracts=num_contracts
            )
            
            if order_result.success:
                return TradeResult(
                    symbol=symbol,
                    success=True,
                    order_id=order_result.order_id,
                    short_strike=0.0,  # No short position in long straddle
                    long_strike=strike,  # Both call and put at this strike
                    expiration=expiration,
                    quantity=num_contracts,
                    filled_price=None,
                    error_message=None,
                    timestamp=timestamp
                )
            else:
                return TradeResult(
                    symbol=symbol,
                    success=False,
                    order_id=None,
                    short_strike=0.0,
                    long_strike=strike,
                    expiration=expiration,
                    quantity=num_contracts,
                    filled_price=None,
                    error_message=order_result.error_message,
                    timestamp=timestamp
                )
            
        except Exception as e:
            error_msg = f"Unexpected error: {type(e).__name__}: {str(e)}"
            self.logger.log_error(
                f"Unexpected error processing long straddle for {symbol}",
                e,
                {
                    "symbol": symbol,
                    "error_type": type(e).__name__,
                    "timestamp": timestamp.isoformat()
                }
            )
            
            return TradeResult(
                symbol=symbol,
                success=False,
                order_id=None,
                short_strike=0.0,
                long_strike=0.0,
                expiration=date.today(),
                quantity=0,
                filled_price=None,
                error_message=error_msg,
                timestamp=timestamp
            )

    def process_iron_butterfly_symbol(self, symbol: str) -> TradeResult:
        """Process a single symbol using Iron Butterfly strategy.
        
        Iron Butterfly strategy:
        1. Sell 1 ATM call (middle strike)
        2. Sell 1 ATM put (middle strike)
        3. Buy 1 OTM call (upper wing - protection)
        4. Buy 1 OTM put (lower wing - protection)
        
        Profits when stock stays near the middle strike. Collects premium
        from selling the ATM straddle, with wings providing protection.
        
        Args:
            symbol: Stock symbol to process
            
        Returns:
            TradeResult with execution details
        """
        timestamp = datetime.now()
        
        try:
            # Get current market price
            self.logger.log_info(f"Fetching current price for {symbol} (Iron Butterfly Strategy)")
            current_price = self.broker_client.get_current_price(symbol)
            self.logger.log_info(
                f"Current price for {symbol}: ${current_price:.2f}",
                {"symbol": symbol, "price": current_price, "strategy": "iron_butterfly"}
            )
            
            # Calculate expiration
            expiration = self.iron_butterfly_calculator.calculate_expiration()
            
            # Get number of contracts
            num_contracts = self.config.ib_num_contracts
            
            self.logger.log_info(
                f"Iron Butterfly targets for {symbol}",
                {
                    "symbol": symbol,
                    "target_middle": f"${current_price:.2f} (ATM)",
                    "wing_width": f"${self.config.ib_wing_width:.2f}",
                    "expiration": expiration.isoformat(),
                    "num_contracts": num_contracts
                }
            )
            
            # Get option chain
            self.logger.log_info(f"Retrieving option chain for {symbol}")
            option_chain = self.broker_client.get_option_chain(symbol, expiration)
            available_strikes = sorted(list(set([contract.strike for contract in option_chain])))
            
            self.logger.log_info(
                f"Retrieved {len(available_strikes)} available strikes for {symbol}",
                {"symbol": symbol, "strike_count": len(available_strikes)}
            )
            
            # Calculate strikes (lower, middle, upper)
            lower_strike, middle_strike, upper_strike = self.iron_butterfly_calculator.calculate_strikes(
                current_price, available_strikes
            )
            
            wing_width = middle_strike - lower_strike
            
            self.logger.log_info(
                f"Selected iron butterfly strikes for {symbol}",
                {
                    "symbol": symbol,
                    "lower_strike": f"${lower_strike:.2f}",
                    "middle_strike": f"${middle_strike:.2f}",
                    "upper_strike": f"${upper_strike:.2f}",
                    "wing_width": f"${wing_width:.2f}",
                    "expiration": expiration.isoformat()
                }
            )
            
            # Submit iron butterfly order
            self.logger.log_info(f"Submitting iron butterfly order for {symbol}")
            order_result = self.broker_client.submit_iron_butterfly_order(
                symbol=symbol,
                lower_strike=lower_strike,
                middle_strike=middle_strike,
                upper_strike=upper_strike,
                expiration=expiration,
                num_contracts=num_contracts
            )
            
            if order_result.success:
                return TradeResult(
                    symbol=symbol,
                    success=True,
                    order_id=order_result.order_id,
                    short_strike=middle_strike,  # ATM strike where we sell
                    long_strike=lower_strike,    # One of the wings
                    expiration=expiration,
                    quantity=num_contracts,
                    filled_price=None,
                    error_message=None,
                    timestamp=timestamp
                )
            else:
                return TradeResult(
                    symbol=symbol,
                    success=False,
                    order_id=None,
                    short_strike=middle_strike,
                    long_strike=lower_strike,
                    expiration=expiration,
                    quantity=num_contracts,
                    filled_price=None,
                    error_message=order_result.error_message,
                    timestamp=timestamp
                )
            
        except Exception as e:
            error_msg = f"Unexpected error: {type(e).__name__}: {str(e)}"
            self.logger.log_error(
                f"Unexpected error processing iron butterfly for {symbol}",
                e,
                {
                    "symbol": symbol,
                    "error_type": type(e).__name__,
                    "timestamp": timestamp.isoformat()
                }
            )
            
            return TradeResult(
                symbol=symbol,
                success=False,
                order_id=None,
                short_strike=0.0,
                long_strike=0.0,
                expiration=date.today(),
                quantity=0,
                filled_price=None,
                error_message=error_msg,
                timestamp=timestamp
            )

    def process_short_strangle_symbol(self, symbol: str) -> TradeResult:
        """Process a single symbol using Short Strangle strategy.
        
        Short Strangle strategy:
        1. Sell 1 OTM put (below current price)
        2. Sell 1 OTM call (above current price)
        
        Collects premium, profits when stock stays between strikes.
        WARNING: This strategy has UNDEFINED RISK on both sides!
        
        Args:
            symbol: Stock symbol to process
            
        Returns:
            TradeResult with execution details
        """
        timestamp = datetime.now()
        
        try:
            # Get current market price
            self.logger.log_info(f"Fetching current price for {symbol} (Short Strangle Strategy)")
            current_price = self.broker_client.get_current_price(symbol)
            self.logger.log_info(
                f"Current price for {symbol}: ${current_price:.2f}",
                {"symbol": symbol, "price": current_price, "strategy": "short_strangle"}
            )
            
            # Calculate expiration
            expiration = self.short_strangle_calculator.calculate_expiration()
            
            # Get number of contracts
            num_contracts = self.config.ss_num_contracts
            
            # Calculate target strikes
            put_strike_target = self.short_strangle_calculator.calculate_put_strike(current_price)
            call_strike_target = self.short_strangle_calculator.calculate_call_strike(current_price)
            
            self.logger.log_info(
                f"Short Strangle targets for {symbol}",
                {
                    "symbol": symbol,
                    "put_target": f"${put_strike_target:.2f}",
                    "call_target": f"${call_strike_target:.2f}",
                    "expiration": expiration.isoformat(),
                    "num_contracts": num_contracts,
                    "warning": "UNDEFINED RISK STRATEGY"
                }
            )
            
            # Get option chain
            self.logger.log_info(f"Retrieving option chain for {symbol}")
            option_chain = self.broker_client.get_option_chain(symbol, expiration)
            available_strikes = sorted(list(set([contract.strike for contract in option_chain])))
            
            self.logger.log_info(
                f"Retrieved {len(available_strikes)} available strikes for {symbol}",
                {"symbol": symbol, "strike_count": len(available_strikes)}
            )
            
            # Find actual strikes
            put_strike = self.short_strangle_calculator.find_nearest_strike_below(
                put_strike_target, available_strikes
            )
            call_strike = self.short_strangle_calculator.find_nearest_strike_above(
                call_strike_target, available_strikes
            )
            
            profit_range = call_strike - put_strike
            
            self.logger.log_info(
                f"Selected short strangle strikes for {symbol}",
                {
                    "symbol": symbol,
                    "put_strike": f"${put_strike:.2f}",
                    "call_strike": f"${call_strike:.2f}",
                    "profit_range": f"${profit_range:.2f}",
                    "expiration": expiration.isoformat()
                }
            )
            
            # Submit short strangle order
            self.logger.log_info(f"Submitting short strangle order for {symbol}")
            order_result = self.broker_client.submit_short_strangle_order(
                symbol=symbol,
                put_strike=put_strike,
                call_strike=call_strike,
                expiration=expiration,
                num_contracts=num_contracts
            )
            
            if order_result.success:
                return TradeResult(
                    symbol=symbol,
                    success=True,
                    order_id=order_result.order_id,
                    short_strike=call_strike,  # Call strike (one of the shorts)
                    long_strike=put_strike,    # Put strike (other short)
                    expiration=expiration,
                    quantity=num_contracts,
                    filled_price=None,
                    error_message=None,
                    timestamp=timestamp
                )
            else:
                return TradeResult(
                    symbol=symbol,
                    success=False,
                    order_id=None,
                    short_strike=call_strike,
                    long_strike=put_strike,
                    expiration=expiration,
                    quantity=num_contracts,
                    filled_price=None,
                    error_message=order_result.error_message,
                    timestamp=timestamp
                )
            
        except Exception as e:
            error_msg = f"Unexpected error: {type(e).__name__}: {str(e)}"
            self.logger.log_error(
                f"Unexpected error processing short strangle for {symbol}",
                e,
                {
                    "symbol": symbol,
                    "error_type": type(e).__name__,
                    "timestamp": timestamp.isoformat()
                }
            )
            
            return TradeResult(
                symbol=symbol,
                success=False,
                order_id=None,
                short_strike=0.0,
                long_strike=0.0,
                expiration=date.today(),
                quantity=0,
                filled_price=None,
                error_message=error_msg,
                timestamp=timestamp
            )

    def _log_execution_summary(self, summary: ExecutionSummary):
        """Log execution summary with success/failure counts and detailed report.
        
        This method generates a comprehensive report of the trading cycle,
        including overall statistics and individual trade results.
        
        Args:
            summary: ExecutionSummary to log
        """
        # Log overall summary
        summary_dict = {
            'execution_date': summary.execution_date.isoformat(),
            'total_symbols': summary.total_symbols,
            'successful_trades': summary.successful_trades,
            'failed_trades': summary.failed_trades
        }
        
        self.logger.log_execution_summary(summary_dict)
        
        # Generate detailed report of all trade results
        self.logger.log_info("=" * 60)
        self.logger.log_info("DETAILED TRADE RESULTS")
        self.logger.log_info("=" * 60)
        
        for trade_result in summary.trade_results:
            status = "SUCCESS" if trade_result.success else "FAILED"
            
            trade_info = {
                "symbol": trade_result.symbol,
                "status": status,
                "short_strike": f"${trade_result.short_strike:.2f}",
                "long_strike": f"${trade_result.long_strike:.2f}",
                "expiration": trade_result.expiration.isoformat(),
                "quantity": trade_result.quantity
            }
            
            if trade_result.success:
                if trade_result.order_id:
                    trade_info["order_id"] = trade_result.order_id
                if trade_result.filled_price:
                    trade_info["filled_price"] = f"${trade_result.filled_price:.2f}"
                
                self.logger.log_info(
                    f"✓ {trade_result.symbol}: Order submitted successfully",
                    trade_info
                )
            else:
                trade_info["error"] = trade_result.error_message
                self.logger.log_error(
                    f"✗ {trade_result.symbol}: Order failed",
                    context=trade_info
                )
        
        self.logger.log_info("=" * 60)
        
        # Log summary statistics
        success_rate = (summary.successful_trades / summary.total_symbols * 100) if summary.total_symbols > 0 else 0
        
        self.logger.log_info(
            f"Trading cycle complete: {summary.successful_trades}/{summary.total_symbols} successful ({success_rate:.1f}%)",
            {
                "execution_date": summary.execution_date.isoformat(),
                "success_rate": f"{success_rate:.1f}%"
            }
        )
        
        # Ensure graceful handling of partial failures
        if summary.failed_trades > 0:
            self.logger.log_warning(
                f"{summary.failed_trades} trade(s) failed during this cycle",
                {
                    "failed_count": summary.failed_trades,
                    "total_count": summary.total_symbols
                }
            )
            
            # Log failed symbols for easy reference
            failed_symbols = [
                result.symbol for result in summary.trade_results 
                if not result.success
            ]
            self.logger.log_warning(
                f"Failed symbols: {', '.join(failed_symbols)}",
                {"failed_symbols": failed_symbols}
            )

    def shutdown(self):
        """Perform graceful shutdown and cleanup.
        
        This method:
        1. Closes broker connections
        2. Flushes log buffers
        3. Cleans up resources
        """
        if self.logger:
            self.logger.log_info("Initiating trading bot shutdown")
        
        try:
            # Close broker connections
            if self.broker_client:
                broker_name = self.broker_client.get_broker_name()
                self.logger.log_info(f"Closing {broker_name} broker connections")
                # Lumibot brokers handle cleanup internally
                self.broker_client = None
            
            # Flush log buffers
            if self.logger:
                self.logger.log_info("Flushing log buffers")
                for handler in self.logger.logger.handlers:
                    handler.flush()
            
            # Mark as not initialized
            self._initialized = False
            
            if self.logger:
                self.logger.log_info("Trading bot shutdown complete")
            
        except Exception as e:
            if self.logger:
                self.logger.log_error(
                    "Error during shutdown",
                    e,
                    {
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                )
            else:
                print(f"ERROR during shutdown: {type(e).__name__}: {str(e)}")
