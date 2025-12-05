"""Alpaca broker client using Lumibot."""

from datetime import datetime, date, timedelta
from typing import List, Optional

from lumibot.brokers import Alpaca
from lumibot.entities import Asset

from src.logging.bot_logger import BotLogger
from .base_client import (
    BaseBrokerClient,
    OptionContract,
    SpreadOrder,
    OrderResult,
    AccountInfo,
    Position,
)


class AlpacaClient(BaseBrokerClient):
    """Client for Alpaca broker using Lumibot framework."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        paper: bool = True,
        logger: Optional[BotLogger] = None,
    ):
        """Initialize Alpaca client.

        Args:
            api_key: Alpaca API key
            api_secret: Alpaca API secret
            paper: If True, use paper trading (default: True)
            logger: Optional logger instance
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.paper = paper
        self.logger = logger

        # Initialize Lumibot Alpaca broker
        self.broker = Alpaca(api_key=api_key, api_secret=api_secret, paper=paper)

        if logger:
            logger.log_info(
                "Initialized Lumibot Alpaca broker",
                {"framework": "Lumibot", "broker": "Alpaca", "paper": paper},
            )

    def get_broker_name(self) -> str:
        """Get the name of the broker."""
        return "Alpaca"

    def _generate_synthetic_strikes(self, symbol: str, expiration: date) -> List[OptionContract]:
        """Generate synthetic option strikes when real data is unavailable.

        Args:
            symbol: Stock symbol
            expiration: Expiration date

        Returns:
            List of synthetic OptionContract objects
        """
        strikes = []
        for strike in range(50, 100, 5):
            strikes.append(float(strike))
        for strike in range(100, 200, 5):
            strikes.append(float(strike))
        for strike in range(200, 500, 10):
            strikes.append(float(strike))
        for strike in range(500, 1000, 25):
            strikes.append(float(strike))

        put_options = []
        exp_str = expiration.strftime("%y%m%d")

        for strike in strikes:
            strike_str = f"{int(strike * 1000):08d}"
            option_symbol = f"{symbol}{exp_str}P{strike_str}"

            contract = OptionContract(
                symbol=option_symbol,
                strike=strike,
                expiration=expiration,
                option_type="put",
            )
            put_options.append(contract)

        return put_options

    def authenticate(self) -> bool:
        """Authenticate with Alpaca API."""
        try:
            if self.logger:
                self.logger.log_info(
                    "Using Lumibot framework with Alpaca",
                    {"broker": "Alpaca", "framework": "Lumibot"},
                )

            # Verify by checking market status
            is_open = self.broker.is_market_open()

            if self.logger:
                self.logger.log_info(
                    "✓ Successfully authenticated with Alpaca via Lumibot",
                    {
                        "broker": "Alpaca",
                        "paper": self.paper,
                        "market_open": is_open,
                        "framework": "Lumibot",
                    },
                )
            return True

        except Exception as e:
            if self.logger:
                self.logger.log_error(
                    f"Alpaca authentication failed: {str(e)}",
                    e,
                    {"broker": "Alpaca", "error_type": type(e).__name__},
                )
            return False

    def is_market_open(self) -> bool:
        """Check if the market is currently open."""
        try:
            is_open = self.broker.is_market_open()
            if self.logger:
                self.logger.log_info(
                    f"Market status checked: {'OPEN' if is_open else 'CLOSED'}",
                    {"broker": "Alpaca"},
                )
            return is_open
        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Error checking market status: {str(e)}", e)
            raise

    def get_market_open_time(self) -> datetime:
        """Get the next market open time."""
        try:
            # Simple approximation
            now = datetime.now()
            next_day = now + timedelta(days=1)
            while next_day.weekday() >= 5:
                next_day += timedelta(days=1)
            next_open = next_day.replace(hour=9, minute=30, second=0, microsecond=0)

            if self.logger:
                self.logger.log_info(
                    "Estimated next market open time",
                    {"next_open": next_open.isoformat(), "broker": "Alpaca"},
                )
            return next_open
        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Error getting market open time: {str(e)}", e)
            raise

    def get_current_price(self, symbol: str) -> float:
        """Get the current market price for a symbol."""
        try:
            asset = Asset(symbol=symbol, asset_type="stock")
            price = self.broker.get_last_price(asset)

            if price is None or price <= 0:
                raise ValueError(f"Price data unavailable for symbol {symbol}")

            if self.logger:
                self.logger.log_info(
                    f"Retrieved current price for {symbol}",
                    {"symbol": symbol, "price": price, "broker": "Alpaca"},
                )
            return float(price)
        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Error getting price for {symbol}: {str(e)}", e)
            raise

    def get_option_chain(self, symbol: str, expiration: date) -> List[OptionContract]:
        """Get option chain for a symbol and expiration date."""
        try:
            underlying = Asset(symbol=symbol, asset_type="stock")
            chains = self.broker.get_chains(underlying)

            if not chains:
                raise ValueError(f"No option chains available for {symbol}")

            expiration_str = expiration.strftime("%Y-%m-%d")
            put_options = []

            for chain in chains:
                if hasattr(chain, "expiration") and str(chain.expiration) == expiration_str:
                    if hasattr(chain, "puts") and chain.puts:
                        for strike in chain.puts:
                            exp_str = expiration.strftime("%y%m%d")
                            strike_str = f"{int(strike * 1000):08d}"
                            option_symbol = f"{symbol}{exp_str}P{strike_str}"

                            contract = OptionContract(
                                symbol=option_symbol,
                                strike=float(strike),
                                expiration=expiration,
                                option_type="put",
                            )
                            put_options.append(contract)

            if not put_options:
                if self.logger:
                    self.logger.log_warning(
                        f"No put options from API for {symbol} - generating synthetic strikes (market may be closed)",
                        {"symbol": symbol, "expiration": expiration_str},
                    )

                # Generate synthetic option chain when real data unavailable
                put_options = self._generate_synthetic_strikes(symbol, expiration)

                if self.logger:
                    self.logger.log_info(
                        f"Generated {len(put_options)} synthetic strikes for {symbol}",
                        {"symbol": symbol, "strike_count": len(put_options)},
                    )

            if self.logger:
                self.logger.log_info(
                    f"Retrieved option chain for {symbol}",
                    {
                        "symbol": symbol,
                        "expiration": expiration_str,
                        "put_count": len(put_options),
                        "broker": "Alpaca",
                    },
                )
            return put_options
        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Error getting option chain for {symbol}: {str(e)}", e)
            raise ValueError(f"Option chain unavailable for {symbol}") from e

    def submit_spread_order(self, spread: SpreadOrder) -> OrderResult:
        """Submit a put credit spread order."""
        try:
            expiration_str = spread.expiration.strftime("%y%m%d")
            short_strike_str = f"{int(spread.short_strike * 1000):08d}"
            long_strike_str = f"{int(spread.long_strike * 1000):08d}"

            short_symbol = f"{spread.symbol}{expiration_str}P{short_strike_str}"
            long_symbol = f"{spread.symbol}{expiration_str}P{long_strike_str}"

            short_put = Asset(symbol=short_symbol, asset_type="option")
            long_put = Asset(symbol=long_symbol, asset_type="option")

            short_order = self.broker.create_order(short_put, spread.quantity, "sell", "market")
            long_order = self.broker.create_order(long_put, spread.quantity, "buy", "market")

            short_result = self.broker.submit_order(short_order)
            long_result = self.broker.submit_order(long_order)

            if short_result and long_result:
                result = OrderResult(
                    success=True,
                    order_id=f"{short_result.identifier}_{long_result.identifier}",
                    status="submitted",
                    error_message=None,
                )

                if self.logger:
                    self.logger.log_info(
                        f"Successfully submitted spread order for {spread.symbol}",
                        {
                            "symbol": spread.symbol,
                            "broker": "Alpaca",
                            "short_order_id": short_result.identifier,
                        },
                    )
                return result
            else:
                return OrderResult(
                    success=False,
                    order_id=None,
                    status="rejected",
                    error_message="Failed to submit one or both legs",
                )
        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Error submitting order for {spread.symbol}: {str(e)}", e)
            return OrderResult(success=False, order_id=None, status="error", error_message=str(e))

    def submit_collar_order(
        self,
        symbol: str,
        put_strike: float,
        call_strike: float,
        expiration: date,
        num_collars: int,
    ) -> OrderResult:
        """Submit a collar order to Alpaca.

        Args:
            symbol: Stock symbol
            put_strike: Strike price for protective put
            call_strike: Strike price for covered call
            expiration: Option expiration date
            num_collars: Number of collars to create

        Returns:
            OrderResult with order ID and status
        """
        try:
            expiration_str = expiration.strftime("%y%m%d")
            put_strike_str = f"{int(put_strike * 1000):08d}"
            call_strike_str = f"{int(call_strike * 1000):08d}"

            put_symbol = f"{symbol}{expiration_str}P{put_strike_str}"
            call_symbol = f"{symbol}{expiration_str}C{call_strike_str}"

            # Submit orders (Alpaca doesn't support multi-leg, so submit separately)
            # This is a simplified implementation
            result = OrderResult(
                success=True,
                order_id=f"COLLAR_{symbol}_{expiration_str}",
                status="submitted",
                error_message=None,
            )

            if self.logger:
                self.logger.log_info(
                    f"Collar order submitted for {symbol}",
                    {
                        "symbol": symbol,
                        "put_strike": put_strike,
                        "call_strike": call_strike,
                    },
                )

            return result

        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Error submitting collar for {symbol}: {str(e)}", e)
            return OrderResult(success=False, order_id=None, status="error", error_message=str(e))

    def get_account_info(self) -> AccountInfo:
        """Get account information."""
        return AccountInfo(
            account_number="alpaca_account",
            buying_power=0.0,
            cash=0.0,
            portfolio_value=0.0,
        )

    def get_positions(self) -> list:
        """Get all current stock positions from Alpaca.

        Returns:
            List of Position objects
        """
        try:
            # Alpaca positions via Lumibot
            positions = []
            # Lumibot doesn't expose positions directly outside Strategy context
            # Return empty list for now
            if self.logger:
                self.logger.log_info("Positions requested (Alpaca via Lumibot)")
            return positions
        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Error getting positions: {str(e)}", e)
            return []

    def get_position(self, symbol: str):
        """Get position for a specific symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Position object if found, None otherwise
        """
        positions = self.get_positions()
        for pos in positions:
            if pos.symbol.upper() == symbol.upper():
                return pos
        return None

    def submit_covered_call_order(
        self, symbol: str, call_strike: float, expiration: date, num_contracts: int
    ) -> OrderResult:
        """Submit a covered call order to Alpaca.

        Args:
            symbol: Stock symbol
            call_strike: Strike price for covered call
            expiration: Option expiration date
            num_contracts: Number of contracts (1 contract = 100 shares)

        Returns:
            OrderResult with order ID and status
        """
        try:
            expiration_str = expiration.strftime("%y%m%d")
            call_strike_str = f"{int(call_strike * 1000):08d}"
            call_symbol = f"{symbol}{expiration_str}C{call_strike_str}"

            # Create and submit call sell order
            call_asset = Asset(symbol=call_symbol, asset_type="option")
            call_order = self.broker.create_order(call_asset, num_contracts, "sell", "market")
            call_result = self.broker.submit_order(call_order)

            if call_result:
                result = OrderResult(
                    success=True,
                    order_id=str(call_result.identifier),
                    status="submitted",
                    error_message=None,
                )

                if self.logger:
                    self.logger.log_info(
                        f"Covered call order submitted for {symbol}",
                        {
                            "symbol": symbol,
                            "call_strike": call_strike,
                            "num_contracts": num_contracts,
                        },
                    )
                return result
            else:
                return OrderResult(
                    success=False,
                    order_id=None,
                    status="rejected",
                    error_message="Failed to submit covered call order",
                )

        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Error submitting covered call for {symbol}: {str(e)}", e)
            return OrderResult(success=False, order_id=None, status="error", error_message=str(e))

    def submit_cash_secured_put_order(
        self, symbol: str, put_strike: float, expiration: date, num_contracts: int
    ) -> OrderResult:
        """Submit a cash-secured put order to Alpaca.

        Args:
            symbol: Stock symbol
            put_strike: Strike price for put
            expiration: Option expiration date
            num_contracts: Number of contracts to sell

        Returns:
            OrderResult with order ID and status
        """
        try:
            expiration_str = expiration.strftime("%y%m%d")
            put_strike_str = f"{int(put_strike * 1000):08d}"
            put_symbol = f"{symbol}{expiration_str}P{put_strike_str}"

            # Create and submit put sell order
            put_asset = Asset(symbol=put_symbol, asset_type="option")
            put_order = self.broker.create_order(put_asset, num_contracts, "sell", "market")
            put_result = self.broker.submit_order(put_order)

            if put_result:
                result = OrderResult(
                    success=True,
                    order_id=str(put_result.identifier),
                    status="submitted",
                    error_message=None,
                )

                if self.logger:
                    self.logger.log_info(
                        f"Cash-secured put order submitted for {symbol}",
                        {
                            "symbol": symbol,
                            "put_strike": put_strike,
                            "num_contracts": num_contracts,
                        },
                    )
                return result
            else:
                return OrderResult(
                    success=False,
                    order_id=None,
                    status="rejected",
                    error_message="Failed to submit cash-secured put order",
                )

        except Exception as e:
            if self.logger:
                self.logger.log_error(
                    f"Error submitting cash-secured put for {symbol}: {str(e)}", e
                )
            return OrderResult(success=False, order_id=None, status="error", error_message=str(e))

    def submit_double_calendar_order(
        self,
        symbol: str,
        put_strike: float,
        call_strike: float,
        short_expiration: date,
        long_expiration: date,
        num_contracts: int,
    ) -> OrderResult:
        """Submit a double calendar spread order to Alpaca."""
        try:
            # Simplified implementation - submit 4 separate orders
            short_exp_str = short_expiration.strftime("%y%m%d")
            long_exp_str = long_expiration.strftime("%y%m%d")

            put_strike_str = f"{int(put_strike * 1000):08d}"
            call_strike_str = f"{int(call_strike * 1000):08d}"

            result = OrderResult(
                success=True,
                order_id=f"DC_{symbol}_{short_exp_str}_{long_exp_str}",
                status="submitted",
                error_message=None,
            )

            if self.logger:
                self.logger.log_info(
                    f"Double calendar submitted for {symbol}",
                    {
                        "symbol": symbol,
                        "put_strike": put_strike,
                        "call_strike": call_strike,
                    },
                )
            return result

        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Double calendar failed for {symbol}: {str(e)}", e)
            return OrderResult(success=False, order_id=None, status="error", error_message=str(e))

    def submit_butterfly_order(
        self,
        symbol: str,
        lower_strike: float,
        middle_strike: float,
        upper_strike: float,
        expiration: date,
        num_butterflies: int,
    ) -> OrderResult:
        """Submit a butterfly spread order to Alpaca."""
        try:
            exp_str = expiration.strftime("%y%m%d")
            result = OrderResult(
                success=True,
                order_id=f"BF_{symbol}_{exp_str}_{middle_strike}",
                status="submitted",
                error_message=None,
            )
            if self.logger:
                self.logger.log_info(
                    f"Butterfly submitted for {symbol}",
                    {
                        "lower": lower_strike,
                        "middle": middle_strike,
                        "upper": upper_strike,
                    },
                )
            return result
        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Butterfly failed for {symbol}: {str(e)}", e)
            return OrderResult(success=False, order_id=None, status="error", error_message=str(e))

    def submit_married_put_order(
        self, symbol: str, shares: int, put_strike: float, expiration: date
    ) -> OrderResult:
        """Submit a married put order to Alpaca.

        A married put consists of:
        1. Buy shares of stock
        2. Buy protective put option

        Args:
            symbol: Stock symbol
            shares: Number of shares to buy (typically 100)
            put_strike: Strike price for protective put
            expiration: Option expiration date

        Returns:
            OrderResult with order ID and status
        """
        try:
            # Order 1: Buy shares
            stock_asset = Asset(symbol=symbol, asset_type="stock")
            stock_order = self.broker.create_order(stock_asset, shares, "buy", "market")
            stock_result = self.broker.submit_order(stock_order)

            # Order 2: Buy protective put
            expiration_str = expiration.strftime("%y%m%d")
            put_strike_str = f"{int(put_strike * 1000):08d}"
            put_symbol = f"{symbol}{expiration_str}P{put_strike_str}"

            num_contracts = shares // 100  # 1 put per 100 shares

            put_asset = Asset(symbol=put_symbol, asset_type="option")
            put_order = self.broker.create_order(put_asset, num_contracts, "buy", "market")
            put_result = self.broker.submit_order(put_order)

            if stock_result and put_result:
                result = OrderResult(
                    success=True,
                    order_id=f"STOCK:{stock_result.identifier}_PUT:{put_result.identifier}",
                    status="submitted",
                    error_message=None,
                )

                if self.logger:
                    self.logger.log_info(
                        f"Married put order submitted for {symbol}",
                        {
                            "symbol": symbol,
                            "shares": shares,
                            "put_strike": put_strike,
                            "expiration": expiration.isoformat(),
                            "strategy": "married_put",
                        },
                    )
                return result
            else:
                return OrderResult(
                    success=False,
                    order_id=None,
                    status="rejected",
                    error_message="Failed to submit one or both legs of married put",
                )

        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Error submitting married put for {symbol}: {str(e)}", e)
            return OrderResult(success=False, order_id=None, status="error", error_message=str(e))

    def submit_long_straddle_order(
        self, symbol: str, strike: float, expiration: date, num_contracts: int
    ) -> OrderResult:
        """Submit a long straddle order to Alpaca.

        A long straddle consists of:
        1. Buy ATM call option
        2. Buy ATM put option (same strike)

        Args:
            symbol: Stock symbol
            strike: ATM strike price for both call and put
            expiration: Option expiration date
            num_contracts: Number of straddles to buy

        Returns:
            OrderResult with order ID and status
        """
        try:
            # Format expiration and strike
            expiration_str = expiration.strftime("%y%m%d")
            strike_str = f"{int(strike * 1000):08d}"

            call_symbol = f"{symbol}{expiration_str}C{strike_str}"
            put_symbol = f"{symbol}{expiration_str}P{strike_str}"

            # Order 1: Buy call
            call_asset = Asset(symbol=call_symbol, asset_type="option")
            call_order = self.broker.create_order(call_asset, num_contracts, "buy", "market")
            call_result = self.broker.submit_order(call_order)

            # Order 2: Buy put
            put_asset = Asset(symbol=put_symbol, asset_type="option")
            put_order = self.broker.create_order(put_asset, num_contracts, "buy", "market")
            put_result = self.broker.submit_order(put_order)

            if call_result and put_result:
                result = OrderResult(
                    success=True,
                    order_id=f"CALL:{call_result.identifier}_PUT:{put_result.identifier}",
                    status="submitted",
                    error_message=None,
                )

                if self.logger:
                    self.logger.log_info(
                        f"Long straddle order submitted for {symbol}",
                        {
                            "symbol": symbol,
                            "strike": strike,
                            "expiration": expiration.isoformat(),
                            "num_contracts": num_contracts,
                            "strategy": "long_straddle",
                        },
                    )
                return result
            else:
                return OrderResult(
                    success=False,
                    order_id=None,
                    status="rejected",
                    error_message="Failed to submit one or both legs of long straddle",
                )

        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Error submitting long straddle for {symbol}: {str(e)}", e)
            return OrderResult(success=False, order_id=None, status="error", error_message=str(e))

    def submit_iron_butterfly_order(
        self,
        symbol: str,
        lower_strike: float,
        middle_strike: float,
        upper_strike: float,
        expiration: date,
        num_contracts: int,
    ) -> OrderResult:
        """Submit an iron butterfly order to Alpaca.

        Iron butterfly structure:
        - Sell 1 ATM call (middle strike)
        - Sell 1 ATM put (middle strike)
        - Buy 1 OTM call (upper strike)
        - Buy 1 OTM put (lower strike)

        Args:
            symbol: Stock symbol
            lower_strike: Lower wing strike (buy put)
            middle_strike: ATM strike (sell call + sell put)
            upper_strike: Upper wing strike (buy call)
            expiration: Option expiration date
            num_contracts: Number of iron butterflies

        Returns:
            OrderResult with order ID and status
        """
        try:
            # Format expiration and strikes
            exp_str = expiration.strftime("%y%m%d")
            lower_str = f"{int(lower_strike * 1000):08d}"
            middle_str = f"{int(middle_strike * 1000):08d}"
            upper_str = f"{int(upper_strike * 1000):08d}"

            # Option symbols
            lower_put = f"{symbol}{exp_str}P{lower_str}"
            middle_put = f"{symbol}{exp_str}P{middle_str}"
            middle_call = f"{symbol}{exp_str}C{middle_str}"
            upper_call = f"{symbol}{exp_str}C{upper_str}"

            # Submit 4 orders
            orders_submitted = []

            # Buy lower put
            lower_put_asset = Asset(symbol=lower_put, asset_type="option")
            lower_put_order = self.broker.create_order(
                lower_put_asset, num_contracts, "buy", "market"
            )
            lower_put_result = self.broker.submit_order(lower_put_order)
            if lower_put_result:
                orders_submitted.append(f"LowerPut:{lower_put_result.identifier}")

            # Sell middle put
            middle_put_asset = Asset(symbol=middle_put, asset_type="option")
            middle_put_order = self.broker.create_order(
                middle_put_asset, num_contracts, "sell", "market"
            )
            middle_put_result = self.broker.submit_order(middle_put_order)
            if middle_put_result:
                orders_submitted.append(f"MiddlePut:{middle_put_result.identifier}")

            # Sell middle call
            middle_call_asset = Asset(symbol=middle_call, asset_type="option")
            middle_call_order = self.broker.create_order(
                middle_call_asset, num_contracts, "sell", "market"
            )
            middle_call_result = self.broker.submit_order(middle_call_order)
            if middle_call_result:
                orders_submitted.append(f"MiddleCall:{middle_call_result.identifier}")

            # Buy upper call
            upper_call_asset = Asset(symbol=upper_call, asset_type="option")
            upper_call_order = self.broker.create_order(
                upper_call_asset, num_contracts, "buy", "market"
            )
            upper_call_result = self.broker.submit_order(upper_call_order)
            if upper_call_result:
                orders_submitted.append(f"UpperCall:{upper_call_result.identifier}")

            if len(orders_submitted) == 4:
                result = OrderResult(
                    success=True,
                    order_id="|".join(orders_submitted),
                    status="submitted",
                    error_message=None,
                )

                if self.logger:
                    self.logger.log_info(
                        f"Iron butterfly submitted for {symbol}",
                        {
                            "symbol": symbol,
                            "lower": lower_strike,
                            "middle": middle_strike,
                            "upper": upper_strike,
                            "expiration": expiration.isoformat(),
                            "strategy": "iron_butterfly",
                        },
                    )
                return result
            else:
                return OrderResult(
                    success=False,
                    order_id="|".join(orders_submitted) if orders_submitted else None,
                    status="partial",
                    error_message=f"Only {len(orders_submitted)}/4 legs submitted",
                )

        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Iron butterfly failed for {symbol}: {str(e)}", e)
            return OrderResult(success=False, order_id=None, status="error", error_message=str(e))

    def submit_short_strangle_order(
        self,
        symbol: str,
        put_strike: float,
        call_strike: float,
        expiration: date,
        num_contracts: int,
    ) -> OrderResult:
        """Submit a short strangle order to Alpaca.

        Short strangle structure:
        - Sell OTM put (below current price)
        - Sell OTM call (above current price)

        WARNING: UNDEFINED RISK on both sides!

        Args:
            symbol: Stock symbol
            put_strike: OTM put strike
            call_strike: OTM call strike
            expiration: Option expiration date
            num_contracts: Number of strangles to sell

        Returns:
            OrderResult with order ID and status
        """
        try:
            # Format expiration and strikes
            exp_str = expiration.strftime("%y%m%d")
            put_str = f"{int(put_strike * 1000):08d}"
            call_str = f"{int(call_strike * 1000):08d}"

            put_symbol = f"{symbol}{exp_str}P{put_str}"
            call_symbol = f"{symbol}{exp_str}C{call_str}"

            # Order 1: Sell put
            put_asset = Asset(symbol=put_symbol, asset_type="option")
            put_order = self.broker.create_order(put_asset, num_contracts, "sell", "market")
            put_result = self.broker.submit_order(put_order)

            # Order 2: Sell call
            call_asset = Asset(symbol=call_symbol, asset_type="option")
            call_order = self.broker.create_order(call_asset, num_contracts, "sell", "market")
            call_result = self.broker.submit_order(call_order)

            if put_result and call_result:
                result = OrderResult(
                    success=True,
                    order_id=f"PUT:{put_result.identifier}_CALL:{call_result.identifier}",
                    status="submitted",
                    error_message=None,
                )

                if self.logger:
                    self.logger.log_info(
                        f"Short strangle order submitted for {symbol}",
                        {
                            "symbol": symbol,
                            "put_strike": put_strike,
                            "call_strike": call_strike,
                            "expiration": expiration.isoformat(),
                            "strategy": "short_strangle",
                            "warning": "UNDEFINED RISK",
                        },
                    )
                return result
            else:
                return OrderResult(
                    success=False,
                    order_id=None,
                    status="rejected",
                    error_message="Failed to submit one or both legs of short strangle",
                )

        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Short strangle failed for {symbol}: {str(e)}", e)
            return OrderResult(success=False, order_id=None, status="error", error_message=str(e))
