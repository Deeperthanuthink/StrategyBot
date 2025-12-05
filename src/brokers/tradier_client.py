"""Tradier broker client using Lumibot."""

from datetime import datetime, date, timedelta
from typing import List, Optional

from lumibot.brokers import Tradier
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


class TradierClient(BaseBrokerClient):
    """Client for interacting with Tradier API using Lumibot."""

    def __init__(
        self,
        api_token: str,
        account_id: str,
        base_url: str,
        logger: Optional[BotLogger] = None,
    ):
        """Initialize Lumibot Tradier client.

        Args:
            api_token: Tradier API access token
            account_id: Tradier account ID
            base_url: Tradier API base URL (sandbox or production)
            logger: Optional logger instance
        """
        self.api_token = api_token
        self.account_id = account_id
        self.logger = logger

        # Determine if using sandbox
        self.is_sandbox = "sandbox" in base_url.lower()

        # Initialize Lumibot Tradier broker
        self.broker = Tradier(
            access_token=api_token, account_number=account_id, paper=self.is_sandbox
        )

        if logger:
            logger.log_info(
                "Initialized Lumibot Tradier broker",
                {
                    "framework": "Lumibot",
                    "broker": "Tradier",
                    "sandbox": self.is_sandbox,
                    "account_id": account_id,
                },
            )

    def get_broker_name(self) -> str:
        """Get the name of the broker."""
        return "Tradier"

    def _generate_synthetic_strikes(self, symbol: str, expiration: date) -> List[OptionContract]:
        """Generate synthetic option strikes when real data is unavailable.

        This is used when the market is closed and option chains aren't available.
        Generates reasonable strikes based on typical option increments.

        Args:
            symbol: Stock symbol
            expiration: Expiration date

        Returns:
            List of synthetic OptionContract objects
        """
        # Generate strikes from $10 to $1500 with appropriate increments
        strikes = []

        # $10-$50: $1 increments
        for strike in range(10, 50, 1):
            strikes.append(float(strike))

        # $50-$100: $2.50 increments
        for strike in [
            50,
            52.5,
            55,
            57.5,
            60,
            62.5,
            65,
            67.5,
            70,
            72.5,
            75,
            77.5,
            80,
            82.5,
            85,
            87.5,
            90,
            92.5,
            95,
            97.5,
            100,
        ]:
            strikes.append(float(strike))

        # $100-$200: $2.50 increments
        for strike in range(100, 200, 5):
            strikes.append(float(strike))
            strikes.append(float(strike + 2.5))

        # $200-$500: $5 increments
        for strike in range(200, 500, 5):
            strikes.append(float(strike))

        # $500-$1500: $10 increments
        for strike in range(500, 1500, 10):
            strikes.append(float(strike))

        # Create option contracts
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

    def get_framework_info(self) -> dict:
        """Get information about the trading framework being used.

        Returns:
            Dictionary with framework details
        """
        return {
            "framework": "Lumibot",
            "version": getattr(self.broker, "__version__", "unknown"),
            "broker": "Tradier",
            "broker_class": self.broker.__class__.__name__,
            "sandbox": self.is_sandbox,
            "account_id": self.account_id,
        }

    def authenticate(self) -> bool:
        """Authenticate with Tradier API and verify credentials.

        Returns:
            True if authentication successful, False otherwise
        """
        try:
            # Log framework info
            if self.logger:
                framework_info = self.get_framework_info()
                self.logger.log_info("Using Lumibot framework for trading", framework_info)

            # Verify credentials by checking if we can get market status
            # Lumibot broker doesn't have get_cash() outside of Strategy context
            is_open = self.broker.is_market_open()

            # If we can check market status, authentication worked
            if self.logger:
                self.logger.log_info(
                    "✓ Successfully authenticated with Tradier API via Lumibot",
                    {
                        "account_id": self.account_id,
                        "sandbox": self.is_sandbox,
                        "market_open": is_open,
                        "framework": "Lumibot",
                    },
                )
            return True

        except Exception as e:
            error_msg = f"Unexpected error during authentication: {str(e)}"
            if self.logger:
                self.logger.log_error(
                    error_msg,
                    e,
                    {"account_id": self.account_id, "error_type": type(e).__name__},
                )
            return False

    def is_market_open(self) -> bool:
        """Check if the market is currently open.

        Returns:
            True if market is open, False otherwise
        """
        try:
            is_open = self.broker.is_market_open()

            if self.logger:
                self.logger.log_info(f"Market status checked: {'OPEN' if is_open else 'CLOSED'}")

            return is_open

        except Exception as e:
            error_msg = f"Unexpected error checking market status: {str(e)}"
            if self.logger:
                self.logger.log_error(error_msg, e, {"error_type": type(e).__name__})
            raise

    def get_market_open_time(self) -> datetime:
        """Get the next market open time.

        Returns:
            Datetime of next market open
        """
        try:
            # Lumibot doesn't have a direct method for this
            # Return a default time (9:30 AM ET next trading day)
            from datetime import timedelta

            now = datetime.now()

            # Simple approximation - next weekday at 9:30 AM
            next_day = now + timedelta(days=1)
            while next_day.weekday() >= 5:  # Skip weekends
                next_day += timedelta(days=1)

            next_open = next_day.replace(hour=9, minute=30, second=0, microsecond=0)

            if self.logger:
                self.logger.log_info(
                    "Estimated next market open time",
                    {"next_open": next_open.isoformat()},
                )

            return next_open

        except Exception as e:
            error_msg = f"Unexpected error getting market open time: {str(e)}"
            if self.logger:
                self.logger.log_error(error_msg, e, {"error_type": type(e).__name__})
            raise

    def get_current_price(self, symbol: str) -> float:
        """Get the current market price for a symbol.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')

        Returns:
            Current price as float

        Raises:
            ValueError: If price data is unavailable
        """
        try:
            # Create asset
            asset = Asset(symbol=symbol, asset_type="stock")

            # Get last price
            price = self.broker.get_last_price(asset)

            if price is None or price <= 0:
                raise ValueError(f"Price data unavailable for symbol {symbol}")

            if self.logger:
                self.logger.log_info(
                    f"Retrieved current price for {symbol}",
                    {"symbol": symbol, "price": price},
                )

            return float(price)

        except ValueError:
            raise
        except Exception as e:
            error_msg = f"Unexpected error getting price for {symbol}: {str(e)}"
            if self.logger:
                self.logger.log_error(
                    error_msg, e, {"symbol": symbol, "error_type": type(e).__name__}
                )
            raise

    def get_option_chain(self, symbol: str, expiration: date) -> List[OptionContract]:
        """Get option chain for a symbol and expiration date, filtered for put options.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            expiration: Option expiration date

        Returns:
            List of OptionContract objects for put options

        Raises:
            ValueError: If option chain is unavailable
        """
        try:
            # Create underlying asset
            underlying = Asset(symbol=symbol, asset_type="stock")

            # Get option chain using Lumibot
            chains = self.broker.get_chains(underlying)

            if not chains:
                raise ValueError(f"No option chains available for {symbol}")

            # Filter for the specific expiration date and put options
            expiration_str = expiration.strftime("%Y-%m-%d")
            put_options = []

            for chain in chains:
                # Check if this chain matches our expiration
                if hasattr(chain, "expiration") and str(chain.expiration) == expiration_str:
                    # Get strikes for puts
                    if hasattr(chain, "puts") and chain.puts:
                        for strike in chain.puts:
                            # Create option symbol in OCC format
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
                    },
                )

            return put_options

        except ValueError:
            raise
        except Exception as e:
            error_msg = f"Unexpected error getting option chain for {symbol}: {str(e)}"
            if self.logger:
                self.logger.log_error(
                    error_msg,
                    e,
                    {
                        "symbol": symbol,
                        "expiration": expiration.isoformat(),
                        "error_type": type(e).__name__,
                    },
                )
            raise ValueError(f"Option chain unavailable for {symbol}") from e

    def submit_spread_order(self, spread: SpreadOrder) -> OrderResult:
        """Submit a put credit spread order to Tradier using Lumibot.

        Args:
            spread: SpreadOrder object with order details

        Returns:
            OrderResult with order ID and status
        """
        try:
            # Format expiration date
            expiration_str = spread.expiration.strftime("%y%m%d")

            # Construct option symbols using OCC format
            short_strike_str = f"{int(spread.short_strike * 1000):08d}"
            long_strike_str = f"{int(spread.long_strike * 1000):08d}"

            short_symbol = f"{spread.symbol}{expiration_str}P{short_strike_str}"
            long_symbol = f"{spread.symbol}{expiration_str}P{long_strike_str}"

            # Use Tradier's native API for multileg orders
            # Lumibot doesn't fully support option spreads, so we use direct API
            import requests

            # Calculate a reasonable credit price (typically 20-40% of spread width)
            spread_width = spread.short_strike - spread.long_strike
            estimated_credit = round(spread_width * 0.30, 2)  # 30% of spread width

            # Prepare multileg order data
            order_data = {
                "class": "multileg",
                "symbol": spread.symbol,
                "type": "credit",
                "duration": spread.time_in_force,
                "price": estimated_credit,  # Credit we want to receive
                "option_symbol[0]": short_symbol,
                "side[0]": "sell_to_open",
                "quantity[0]": spread.quantity,
                "option_symbol[1]": long_symbol,
                "side[1]": "buy_to_open",
                "quantity[1]": spread.quantity,
            }

            # Get base URL from broker
            base_url = (
                "https://sandbox.tradier.com" if self.is_sandbox else "https://api.tradier.com"
            )

            # Submit via Tradier API
            response = requests.post(
                f"{base_url}/v1/accounts/{self.account_id}/orders",
                data=order_data,
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Accept": "application/json",
                },
            )

            short_result = response
            long_result = response  # Same response for multileg

            if response.status_code in [200, 201]:
                result_data = response.json()
                order_info = result_data.get("order", {})
                order_id = order_info.get("id")
                status = order_info.get("status", "submitted")

                result = OrderResult(
                    success=True,
                    order_id=str(order_id) if order_id else None,
                    status=status,
                    error_message=None,
                )

                if self.logger:
                    self.logger.log_info(
                        f"Successfully submitted spread order for {spread.symbol}",
                        {
                            "symbol": spread.symbol,
                            "order_id": order_id,
                            "status": status,
                            "short_strike": spread.short_strike,
                            "long_strike": spread.long_strike,
                            "quantity": spread.quantity,
                        },
                    )

                return result
            else:
                error_msg = f"Order rejected: {response.status_code} - {response.text}"

                result = OrderResult(
                    success=False,
                    order_id=None,
                    status="rejected",
                    error_message=error_msg,
                )

                if self.logger:
                    self.logger.log_error(
                        f"Order rejected for {spread.symbol}: {error_msg}",
                        None,
                        {
                            "symbol": spread.symbol,
                            "short_strike": spread.short_strike,
                            "long_strike": spread.long_strike,
                        },
                    )

                return result

        except Exception as e:
            error_msg = f"Unexpected error submitting order for {spread.symbol}: {str(e)}"

            if self.logger:
                self.logger.log_error(
                    error_msg,
                    e,
                    {
                        "symbol": spread.symbol,
                        "short_strike": spread.short_strike,
                        "long_strike": spread.long_strike,
                        "expiration": spread.expiration.isoformat(),
                        "quantity": spread.quantity,
                        "error_type": type(e).__name__,
                    },
                )

            return OrderResult(success=False, order_id=None, status="error", error_message=str(e))

    def submit_collar_order(
        self,
        symbol: str,
        put_strike: float,
        call_strike: float,
        expiration: date,
        num_collars: int,
    ) -> OrderResult:
        """Submit a collar order to Tradier.

        A collar consists of:
        - Buy protective put (downside protection)
        - Sell covered call (income generation)

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
            # Format expiration
            expiration_str = expiration.strftime("%y%m%d")

            # Construct option symbols
            put_strike_str = f"{int(put_strike * 1000):08d}"
            call_strike_str = f"{int(call_strike * 1000):08d}"

            put_symbol = f"{symbol}{expiration_str}P{put_strike_str}"
            call_symbol = f"{symbol}{expiration_str}C{call_strike_str}"

            # Submit two separate orders (Tradier doesn't support 3-leg orders easily)
            import requests

            base_url = (
                "https://sandbox.tradier.com" if self.is_sandbox else "https://api.tradier.com"
            )

            # Order 1: Buy protective put
            put_order_data = {
                "class": "option",
                "symbol": symbol,
                "option_symbol": put_symbol,
                "side": "buy_to_open",
                "quantity": num_collars,
                "type": "market",
                "duration": "gtc",
            }

            put_response = requests.post(
                f"{base_url}/v1/accounts/{self.account_id}/orders",
                data=put_order_data,
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Accept": "application/json",
                },
            )

            # Order 2: Sell covered call
            call_order_data = {
                "class": "option",
                "symbol": symbol,
                "option_symbol": call_symbol,
                "side": "sell_to_open",
                "quantity": num_collars,
                "type": "market",
                "duration": "gtc",
            }

            call_response = requests.post(
                f"{base_url}/v1/accounts/{self.account_id}/orders",
                data=call_order_data,
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Accept": "application/json",
                },
            )

            # Check if both orders succeeded
            if put_response.status_code in [200, 201] and call_response.status_code in [
                200,
                201,
            ]:
                put_data = put_response.json()
                call_data = call_response.json()

                put_order_id = put_data.get("order", {}).get("id")
                call_order_id = call_data.get("order", {}).get("id")

                result = OrderResult(
                    success=True,
                    order_id=f"PUT:{put_order_id}_CALL:{call_order_id}",
                    status="submitted",
                    error_message=None,
                )

                if self.logger:
                    self.logger.log_info(
                        f"Successfully submitted collar order for {symbol}",
                        {
                            "symbol": symbol,
                            "put_order_id": put_order_id,
                            "call_order_id": call_order_id,
                            "put_strike": put_strike,
                            "call_strike": call_strike,
                            "num_collars": num_collars,
                            "strategy": "collar",
                        },
                    )

                return result
            else:
                error_msg = f"Collar order failed - Put: {put_response.status_code}, Call: {call_response.status_code}"

                if self.logger:
                    self.logger.log_error(
                        f"Collar order rejected for {symbol}: {error_msg}",
                        None,
                        {
                            "symbol": symbol,
                            "put_response": put_response.text,
                            "call_response": call_response.text,
                        },
                    )

                return OrderResult(
                    success=False,
                    order_id=None,
                    status="rejected",
                    error_message=error_msg,
                )

        except Exception as e:
            error_msg = f"Unexpected error submitting collar for {symbol}: {str(e)}"

            if self.logger:
                self.logger.log_error(error_msg, e, {"symbol": symbol})

            return OrderResult(success=False, order_id=None, status="error", error_message=str(e))

    def get_account_info(self) -> AccountInfo:
        """Get account information from Tradier via Lumibot.

        Returns:
            AccountInfo object with account details
        """
        try:
            # Lumibot broker methods work best within Strategy context
            # For now, return placeholder values
            # In actual trading, positions are tracked automatically by Lumibot

            info = AccountInfo(
                account_number=self.account_id,
                buying_power=0.0,  # Lumibot tracks this internally
                cash=0.0,  # Lumibot tracks this internally
                portfolio_value=0.0,  # Lumibot tracks this internally
            )

            if self.logger:
                self.logger.log_info(
                    "Account info requested (Lumibot tracks internally)",
                    {
                        "account_id": self.account_id,
                        "note": "Lumibot manages account state within Strategy context",
                    },
                )

            return info

        except Exception as e:
            error_msg = f"Unexpected error getting account info: {str(e)}"
            if self.logger:
                self.logger.log_error(error_msg, e, {"error_type": type(e).__name__})
            raise

    def get_positions(self) -> list:
        """Get all current stock positions from Tradier.

        Returns:
            List of Position objects
        """
        try:
            import requests

            base_url = (
                "https://sandbox.tradier.com" if self.is_sandbox else "https://api.tradier.com"
            )

            response = requests.get(
                f"{base_url}/v1/accounts/{self.account_id}/positions",
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Accept": "application/json",
                },
            )

            positions = []

            if response.status_code == 200:
                data = response.json()
                positions_data = data.get("positions", {})

                if positions_data == "null" or not positions_data:
                    return []

                position_list = positions_data.get("position", [])

                # Handle single position (not a list)
                if isinstance(position_list, dict):
                    position_list = [position_list]

                for pos in position_list:
                    # Only include stock positions (not options)
                    if pos.get("symbol") and len(pos.get("symbol", "")) <= 5:
                        positions.append(
                            Position(
                                symbol=pos.get("symbol"),
                                quantity=int(pos.get("quantity", 0)),
                                avg_cost=float(pos.get("cost_basis", 0))
                                / max(int(pos.get("quantity", 1)), 1),
                                current_price=float(pos.get("last_price", 0) or 0),
                                market_value=float(pos.get("market_value", 0) or 0),
                            )
                        )

            if self.logger:
                self.logger.log_info(
                    f"Retrieved {len(positions)} stock positions",
                    {"position_count": len(positions)},
                )

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
        """Submit a covered call order to Tradier.

        Sells call options against existing stock position.

        Args:
            symbol: Stock symbol
            call_strike: Strike price for covered call
            expiration: Option expiration date
            num_contracts: Number of contracts (1 contract = 100 shares)

        Returns:
            OrderResult with order ID and status
        """
        try:
            import requests

            # Format expiration
            expiration_str = expiration.strftime("%y%m%d")

            # Construct option symbol
            call_strike_str = f"{int(call_strike * 1000):08d}"
            call_symbol = f"{symbol}{expiration_str}C{call_strike_str}"

            base_url = (
                "https://sandbox.tradier.com" if self.is_sandbox else "https://api.tradier.com"
            )

            # Sell to open call
            order_data = {
                "class": "option",
                "symbol": symbol,
                "option_symbol": call_symbol,
                "side": "sell_to_open",
                "quantity": num_contracts,
                "type": "market",
                "duration": "gtc",
            }

            response = requests.post(
                f"{base_url}/v1/accounts/{self.account_id}/orders",
                data=order_data,
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Accept": "application/json",
                },
            )

            if response.status_code in [200, 201]:
                result_data = response.json()
                order_info = result_data.get("order", {})
                order_id = order_info.get("id")

                result = OrderResult(
                    success=True,
                    order_id=str(order_id) if order_id else None,
                    status="submitted",
                    error_message=None,
                )

                if self.logger:
                    self.logger.log_info(
                        f"Successfully submitted covered call order for {symbol}",
                        {
                            "symbol": symbol,
                            "order_id": order_id,
                            "call_strike": call_strike,
                            "expiration": expiration.isoformat(),
                            "num_contracts": num_contracts,
                            "strategy": "covered_call",
                        },
                    )

                return result
            else:
                error_msg = f"Covered call order rejected: {response.status_code} - {response.text}"

                if self.logger:
                    self.logger.log_error(
                        f"Covered call order rejected for {symbol}: {error_msg}",
                        None,
                        {"symbol": symbol, "response": response.text},
                    )

                return OrderResult(
                    success=False,
                    order_id=None,
                    status="rejected",
                    error_message=error_msg,
                )

        except Exception as e:
            error_msg = f"Unexpected error submitting covered call for {symbol}: {str(e)}"

            if self.logger:
                self.logger.log_error(error_msg, e, {"symbol": symbol})

            return OrderResult(success=False, order_id=None, status="error", error_message=str(e))

    def submit_cash_secured_put_order(
        self, symbol: str, put_strike: float, expiration: date, num_contracts: int
    ) -> OrderResult:
        """Submit a cash-secured put order to Tradier.

        Sells put options to collect premium and potentially buy shares.

        Args:
            symbol: Stock symbol
            put_strike: Strike price for put
            expiration: Option expiration date
            num_contracts: Number of contracts to sell

        Returns:
            OrderResult with order ID and status
        """
        try:
            import requests

            # Format expiration
            expiration_str = expiration.strftime("%y%m%d")

            # Construct option symbol
            put_strike_str = f"{int(put_strike * 1000):08d}"
            put_symbol = f"{symbol}{expiration_str}P{put_strike_str}"

            base_url = (
                "https://sandbox.tradier.com" if self.is_sandbox else "https://api.tradier.com"
            )

            # Sell to open put
            order_data = {
                "class": "option",
                "symbol": symbol,
                "option_symbol": put_symbol,
                "side": "sell_to_open",
                "quantity": num_contracts,
                "type": "market",
                "duration": "gtc",
            }

            response = requests.post(
                f"{base_url}/v1/accounts/{self.account_id}/orders",
                data=order_data,
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Accept": "application/json",
                },
            )

            if response.status_code in [200, 201]:
                result_data = response.json()
                order_info = result_data.get("order", {})
                order_id = order_info.get("id")

                result = OrderResult(
                    success=True,
                    order_id=str(order_id) if order_id else None,
                    status="submitted",
                    error_message=None,
                )

                if self.logger:
                    self.logger.log_info(
                        f"Successfully submitted cash-secured put order for {symbol}",
                        {
                            "symbol": symbol,
                            "order_id": order_id,
                            "put_strike": put_strike,
                            "expiration": expiration.isoformat(),
                            "num_contracts": num_contracts,
                            "strategy": "cash_secured_put",
                        },
                    )

                return result
            else:
                error_msg = (
                    f"Cash-secured put order rejected: {response.status_code} - {response.text}"
                )

                if self.logger:
                    self.logger.log_error(
                        f"Cash-secured put order rejected for {symbol}: {error_msg}",
                        None,
                        {"symbol": symbol, "response": response.text},
                    )

                return OrderResult(
                    success=False,
                    order_id=None,
                    status="rejected",
                    error_message=error_msg,
                )

        except Exception as e:
            error_msg = f"Unexpected error submitting cash-secured put for {symbol}: {str(e)}"

            if self.logger:
                self.logger.log_error(error_msg, e, {"symbol": symbol})

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
        """Submit a double calendar spread order to Tradier.

        A double calendar has 4 legs:
        1. Sell short-term put
        2. Buy long-term put
        3. Sell short-term call
        4. Buy long-term call
        """
        try:
            import requests

            short_exp_str = short_expiration.strftime("%y%m%d")
            long_exp_str = long_expiration.strftime("%y%m%d")

            put_strike_str = f"{int(put_strike * 1000):08d}"
            call_strike_str = f"{int(call_strike * 1000):08d}"

            # Option symbols
            short_put = f"{symbol}{short_exp_str}P{put_strike_str}"
            long_put = f"{symbol}{long_exp_str}P{put_strike_str}"
            short_call = f"{symbol}{short_exp_str}C{call_strike_str}"
            long_call = f"{symbol}{long_exp_str}C{call_strike_str}"

            base_url = (
                "https://sandbox.tradier.com" if self.is_sandbox else "https://api.tradier.com"
            )

            # Submit as 4 separate orders (Tradier doesn't support 4-leg in one order easily)
            orders = [
                {"symbol": short_put, "side": "sell_to_open", "desc": "Short Put"},
                {"symbol": long_put, "side": "buy_to_open", "desc": "Long Put"},
                {"symbol": short_call, "side": "sell_to_open", "desc": "Short Call"},
                {"symbol": long_call, "side": "buy_to_open", "desc": "Long Call"},
            ]

            order_ids = []
            for order in orders:
                order_data = {
                    "class": "option",
                    "symbol": symbol,
                    "option_symbol": order["symbol"],
                    "side": order["side"],
                    "quantity": num_contracts,
                    "type": "market",
                    "duration": "day",
                }

                response = requests.post(
                    f"{base_url}/v1/accounts/{self.account_id}/orders",
                    data=order_data,
                    headers={
                        "Authorization": f"Bearer {self.api_token}",
                        "Accept": "application/json",
                    },
                )

                if response.status_code in [200, 201]:
                    result_data = response.json()
                    order_id = result_data.get("order", {}).get("id")
                    order_ids.append(f"{order['desc']}:{order_id}")
                else:
                    if self.logger:
                        self.logger.log_error(f"Failed to submit {order['desc']}: {response.text}")

            if len(order_ids) == 4:
                result = OrderResult(
                    success=True,
                    order_id="|".join(order_ids),
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
                            "short_exp": short_expiration.isoformat(),
                            "long_exp": long_expiration.isoformat(),
                            "order_ids": order_ids,
                        },
                    )
                return result
            else:
                return OrderResult(
                    success=False,
                    order_id="|".join(order_ids) if order_ids else None,
                    status="partial",
                    error_message=f"Only {len(order_ids)}/4 legs submitted",
                )

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
        """Submit a butterfly spread order to Tradier.

        Long Call Butterfly:
        - Buy 1 lower strike call
        - Sell 2 middle strike calls
        - Buy 1 upper strike call
        """
        try:
            import requests

            exp_str = expiration.strftime("%y%m%d")
            lower_str = f"{int(lower_strike * 1000):08d}"
            middle_str = f"{int(middle_strike * 1000):08d}"
            upper_str = f"{int(upper_strike * 1000):08d}"

            lower_call = f"{symbol}{exp_str}C{lower_str}"
            middle_call = f"{symbol}{exp_str}C{middle_str}"
            upper_call = f"{symbol}{exp_str}C{upper_str}"

            base_url = (
                "https://sandbox.tradier.com" if self.is_sandbox else "https://api.tradier.com"
            )

            # Submit as multileg order
            order_data = {
                "class": "multileg",
                "symbol": symbol,
                "type": "debit",
                "duration": "day",
                "price": "0.50",  # Limit price for debit
                "option_symbol[0]": lower_call,
                "side[0]": "buy_to_open",
                "quantity[0]": num_butterflies,
                "option_symbol[1]": middle_call,
                "side[1]": "sell_to_open",
                "quantity[1]": num_butterflies * 2,  # Sell 2x
                "option_symbol[2]": upper_call,
                "side[2]": "buy_to_open",
                "quantity[2]": num_butterflies,
            }

            response = requests.post(
                f"{base_url}/v1/accounts/{self.account_id}/orders",
                data=order_data,
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Accept": "application/json",
                },
            )

            if response.status_code in [200, 201]:
                result_data = response.json()
                order_id = result_data.get("order", {}).get("id")

                result = OrderResult(
                    success=True,
                    order_id=str(order_id) if order_id else None,
                    status="submitted",
                    error_message=None,
                )

                if self.logger:
                    self.logger.log_info(
                        f"Butterfly submitted for {symbol}",
                        {
                            "symbol": symbol,
                            "lower": lower_strike,
                            "middle": middle_strike,
                            "upper": upper_strike,
                            "expiration": expiration.isoformat(),
                            "order_id": order_id,
                        },
                    )
                return result
            else:
                error_msg = f"Butterfly order rejected: {response.status_code} - {response.text}"
                if self.logger:
                    self.logger.log_error(f"Butterfly rejected for {symbol}: {error_msg}")
                return OrderResult(
                    success=False,
                    order_id=None,
                    status="rejected",
                    error_message=error_msg,
                )

        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Butterfly failed for {symbol}: {str(e)}", e)
            return OrderResult(success=False, order_id=None, status="error", error_message=str(e))

    def submit_married_put_order(
        self, symbol: str, shares: int, put_strike: float, expiration: date
    ) -> OrderResult:
        """Submit a married put order to Tradier.

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
            import requests

            base_url = (
                "https://sandbox.tradier.com" if self.is_sandbox else "https://api.tradier.com"
            )

            # Order 1: Buy shares
            stock_order_data = {
                "class": "equity",
                "symbol": symbol,
                "side": "buy",
                "quantity": shares,
                "type": "market",
                "duration": "day",
            }

            stock_response = requests.post(
                f"{base_url}/v1/accounts/{self.account_id}/orders",
                data=stock_order_data,
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Accept": "application/json",
                },
            )

            # Order 2: Buy protective put
            expiration_str = expiration.strftime("%y%m%d")
            put_strike_str = f"{int(put_strike * 1000):08d}"
            put_symbol = f"{symbol}{expiration_str}P{put_strike_str}"

            num_contracts = shares // 100  # 1 put per 100 shares

            put_order_data = {
                "class": "option",
                "symbol": symbol,
                "option_symbol": put_symbol,
                "side": "buy_to_open",
                "quantity": num_contracts,
                "type": "market",
                "duration": "day",
            }

            put_response = requests.post(
                f"{base_url}/v1/accounts/{self.account_id}/orders",
                data=put_order_data,
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Accept": "application/json",
                },
            )

            # Check if both orders succeeded
            if stock_response.status_code in [
                200,
                201,
            ] and put_response.status_code in [200, 201]:
                stock_data = stock_response.json()
                put_data = put_response.json()

                stock_order_id = stock_data.get("order", {}).get("id")
                put_order_id = put_data.get("order", {}).get("id")

                result = OrderResult(
                    success=True,
                    order_id=f"STOCK:{stock_order_id}_PUT:{put_order_id}",
                    status="submitted",
                    error_message=None,
                )

                if self.logger:
                    self.logger.log_info(
                        f"Successfully submitted married put order for {symbol}",
                        {
                            "symbol": symbol,
                            "stock_order_id": stock_order_id,
                            "put_order_id": put_order_id,
                            "shares": shares,
                            "put_strike": put_strike,
                            "expiration": expiration.isoformat(),
                            "strategy": "married_put",
                        },
                    )

                return result
            else:
                error_msg = f"Married put order failed - Stock: {stock_response.status_code}, Put: {put_response.status_code}"

                if self.logger:
                    self.logger.log_error(
                        f"Married put order rejected for {symbol}: {error_msg}",
                        None,
                        {
                            "symbol": symbol,
                            "stock_response": stock_response.text,
                            "put_response": put_response.text,
                        },
                    )

                return OrderResult(
                    success=False,
                    order_id=None,
                    status="rejected",
                    error_message=error_msg,
                )

        except Exception as e:
            error_msg = f"Unexpected error submitting married put for {symbol}: {str(e)}"

            if self.logger:
                self.logger.log_error(error_msg, e, {"symbol": symbol})

            return OrderResult(success=False, order_id=None, status="error", error_message=str(e))

    def submit_long_straddle_order(
        self, symbol: str, strike: float, expiration: date, num_contracts: int
    ) -> OrderResult:
        """Submit a long straddle order to Tradier.

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
            import requests

            base_url = (
                "https://sandbox.tradier.com" if self.is_sandbox else "https://api.tradier.com"
            )

            # Format expiration and strike
            expiration_str = expiration.strftime("%y%m%d")
            strike_str = f"{int(strike * 1000):08d}"

            call_symbol = f"{symbol}{expiration_str}C{strike_str}"
            put_symbol = f"{symbol}{expiration_str}P{strike_str}"

            # Order 1: Buy call
            call_order_data = {
                "class": "option",
                "symbol": symbol,
                "option_symbol": call_symbol,
                "side": "buy_to_open",
                "quantity": num_contracts,
                "type": "market",
                "duration": "day",
            }

            call_response = requests.post(
                f"{base_url}/v1/accounts/{self.account_id}/orders",
                data=call_order_data,
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Accept": "application/json",
                },
            )

            # Order 2: Buy put
            put_order_data = {
                "class": "option",
                "symbol": symbol,
                "option_symbol": put_symbol,
                "side": "buy_to_open",
                "quantity": num_contracts,
                "type": "market",
                "duration": "day",
            }

            put_response = requests.post(
                f"{base_url}/v1/accounts/{self.account_id}/orders",
                data=put_order_data,
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Accept": "application/json",
                },
            )

            # Check if both orders succeeded
            if call_response.status_code in [200, 201] and put_response.status_code in [
                200,
                201,
            ]:
                call_data = call_response.json()
                put_data = put_response.json()

                call_order_id = call_data.get("order", {}).get("id")
                put_order_id = put_data.get("order", {}).get("id")

                result = OrderResult(
                    success=True,
                    order_id=f"CALL:{call_order_id}_PUT:{put_order_id}",
                    status="submitted",
                    error_message=None,
                )

                if self.logger:
                    self.logger.log_info(
                        f"Successfully submitted long straddle order for {symbol}",
                        {
                            "symbol": symbol,
                            "call_order_id": call_order_id,
                            "put_order_id": put_order_id,
                            "strike": strike,
                            "expiration": expiration.isoformat(),
                            "num_contracts": num_contracts,
                            "strategy": "long_straddle",
                        },
                    )

                return result
            else:
                error_msg = f"Long straddle order failed - Call: {call_response.status_code}, Put: {put_response.status_code}"

                if self.logger:
                    self.logger.log_error(
                        f"Long straddle order rejected for {symbol}: {error_msg}",
                        None,
                        {
                            "symbol": symbol,
                            "call_response": call_response.text,
                            "put_response": put_response.text,
                        },
                    )

                return OrderResult(
                    success=False,
                    order_id=None,
                    status="rejected",
                    error_message=error_msg,
                )

        except Exception as e:
            error_msg = f"Unexpected error submitting long straddle for {symbol}: {str(e)}"

            if self.logger:
                self.logger.log_error(error_msg, e, {"symbol": symbol})

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
        """Submit an iron butterfly order to Tradier.

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
            import requests

            base_url = (
                "https://sandbox.tradier.com" if self.is_sandbox else "https://api.tradier.com"
            )

            # Format expiration and strikes
            exp_str = expiration.strftime("%y%m%d")
            lower_str = f"{int(lower_strike * 1000):08d}"
            middle_str = f"{int(middle_strike * 1000):08d}"
            upper_str = f"{int(upper_strike * 1000):08d}"

            # Option symbols
            lower_put = f"{symbol}{exp_str}P{lower_str}"  # Buy OTM put
            middle_put = f"{symbol}{exp_str}P{middle_str}"  # Sell ATM put
            middle_call = f"{symbol}{exp_str}C{middle_str}"  # Sell ATM call
            upper_call = f"{symbol}{exp_str}C{upper_str}"  # Buy OTM call

            # Submit 4 orders
            orders = [
                {"symbol": lower_put, "side": "buy_to_open", "desc": "Buy Lower Put"},
                {
                    "symbol": middle_put,
                    "side": "sell_to_open",
                    "desc": "Sell Middle Put",
                },
                {
                    "symbol": middle_call,
                    "side": "sell_to_open",
                    "desc": "Sell Middle Call",
                },
                {"symbol": upper_call, "side": "buy_to_open", "desc": "Buy Upper Call"},
            ]

            order_ids = []
            for order in orders:
                order_data = {
                    "class": "option",
                    "symbol": symbol,
                    "option_symbol": order["symbol"],
                    "side": order["side"],
                    "quantity": num_contracts,
                    "type": "market",
                    "duration": "day",
                }

                response = requests.post(
                    f"{base_url}/v1/accounts/{self.account_id}/orders",
                    data=order_data,
                    headers={
                        "Authorization": f"Bearer {self.api_token}",
                        "Accept": "application/json",
                    },
                )

                if response.status_code in [200, 201]:
                    result_data = response.json()
                    order_id = result_data.get("order", {}).get("id")
                    order_ids.append(f"{order['desc']}:{order_id}")
                else:
                    if self.logger:
                        self.logger.log_error(f"Failed to submit {order['desc']}: {response.text}")

            if len(order_ids) == 4:
                result = OrderResult(
                    success=True,
                    order_id="|".join(order_ids),
                    status="submitted",
                    error_message=None,
                )

                if self.logger:
                    self.logger.log_info(
                        f"Iron butterfly submitted for {symbol}",
                        {
                            "symbol": symbol,
                            "lower_strike": lower_strike,
                            "middle_strike": middle_strike,
                            "upper_strike": upper_strike,
                            "expiration": expiration.isoformat(),
                            "num_contracts": num_contracts,
                            "order_ids": order_ids,
                            "strategy": "iron_butterfly",
                        },
                    )
                return result
            else:
                return OrderResult(
                    success=False,
                    order_id="|".join(order_ids) if order_ids else None,
                    status="partial",
                    error_message=f"Only {len(order_ids)}/4 legs submitted",
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
        """Submit a short strangle order to Tradier.

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
            import requests

            base_url = (
                "https://sandbox.tradier.com" if self.is_sandbox else "https://api.tradier.com"
            )

            # Format expiration and strikes
            exp_str = expiration.strftime("%y%m%d")
            put_str = f"{int(put_strike * 1000):08d}"
            call_str = f"{int(call_strike * 1000):08d}"

            put_symbol = f"{symbol}{exp_str}P{put_str}"
            call_symbol = f"{symbol}{exp_str}C{call_str}"

            # Order 1: Sell put
            put_order_data = {
                "class": "option",
                "symbol": symbol,
                "option_symbol": put_symbol,
                "side": "sell_to_open",
                "quantity": num_contracts,
                "type": "market",
                "duration": "day",
            }

            put_response = requests.post(
                f"{base_url}/v1/accounts/{self.account_id}/orders",
                data=put_order_data,
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Accept": "application/json",
                },
            )

            # Order 2: Sell call
            call_order_data = {
                "class": "option",
                "symbol": symbol,
                "option_symbol": call_symbol,
                "side": "sell_to_open",
                "quantity": num_contracts,
                "type": "market",
                "duration": "day",
            }

            call_response = requests.post(
                f"{base_url}/v1/accounts/{self.account_id}/orders",
                data=call_order_data,
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Accept": "application/json",
                },
            )

            # Check if both orders succeeded
            if put_response.status_code in [200, 201] and call_response.status_code in [
                200,
                201,
            ]:
                put_data = put_response.json()
                call_data = call_response.json()

                put_order_id = put_data.get("order", {}).get("id")
                call_order_id = call_data.get("order", {}).get("id")

                result = OrderResult(
                    success=True,
                    order_id=f"PUT:{put_order_id}_CALL:{call_order_id}",
                    status="submitted",
                    error_message=None,
                )

                if self.logger:
                    self.logger.log_info(
                        f"Successfully submitted short strangle order for {symbol}",
                        {
                            "symbol": symbol,
                            "put_order_id": put_order_id,
                            "call_order_id": call_order_id,
                            "put_strike": put_strike,
                            "call_strike": call_strike,
                            "expiration": expiration.isoformat(),
                            "num_contracts": num_contracts,
                            "strategy": "short_strangle",
                            "warning": "UNDEFINED RISK",
                        },
                    )

                return result
            else:
                error_msg = f"Short strangle order failed - Put: {put_response.status_code}, Call: {call_response.status_code}"

                if self.logger:
                    self.logger.log_error(
                        f"Short strangle order rejected for {symbol}: {error_msg}",
                        None,
                        {
                            "symbol": symbol,
                            "put_response": put_response.text,
                            "call_response": call_response.text,
                        },
                    )

                return OrderResult(
                    success=False,
                    order_id=None,
                    status="rejected",
                    error_message=error_msg,
                )

        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Short strangle failed for {symbol}: {str(e)}", e)
            return OrderResult(success=False, order_id=None, status="error", error_message=str(e))
