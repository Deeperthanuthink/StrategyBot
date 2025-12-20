"""Tradier API client for market data and order execution."""

from datetime import datetime, date
from typing import List, Optional
from dataclasses import dataclass
import requests
import json

from src.logging.bot_logger import BotLogger


@dataclass
class OptionContract:
    """Represents an option contract."""

    symbol: str
    strike: float
    expiration: date
    option_type: str  # 'put' or 'call'


@dataclass
class SpreadOrder:
    """Represents a put credit spread order."""

    symbol: str
    short_strike: float
    long_strike: float
    expiration: date
    quantity: int
    order_type: str = "limit"
    time_in_force: str = "gtc"


@dataclass
class OrderResult:
    """Result of an order submission."""

    success: bool
    order_id: Optional[str]
    status: Optional[str]
    error_message: Optional[str]


@dataclass
class AccountInfo:
    """Account information from Tradier."""

    account_number: str
    buying_power: float
    cash: float
    portfolio_value: float


class TradierClient:
    """Client for interacting with Tradier API."""

    def __init__(
        self,
        api_token: str,
        account_id: str,
        base_url: str,
        logger: Optional[BotLogger] = None,
    ):
        """Initialize Tradier client.

        Args:
            api_token: Tradier API access token
            account_id: Tradier account ID
            base_url: Tradier API base URL (sandbox or production)
            logger: Optional logger instance
        """
        self.api_token = api_token
        self.account_id = account_id
        self.base_url = base_url.rstrip("/")
        self.logger = logger
        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": f"Bearer {api_token}", "Accept": "application/json"}
        )

    def authenticate(self) -> bool:
        """Authenticate with Tradier API and verify credentials.

        Returns:
            True if authentication successful, False otherwise
        """
        try:
            # Verify credentials by fetching account profile
            response = self.session.get(f"{self.base_url}/v1/user/profile")

            if response.status_code == 200:
                profile = response.json()

                if self.logger:
                    self.logger.log_info(
                        "Successfully authenticated with Tradier API",
                        {"account_id": self.account_id},
                    )

                return True
            else:
                error_msg = (
                    f"Tradier API authentication failed: {response.status_code} - {response.text}"
                )
                if self.logger:
                    self.logger.log_error(
                        error_msg,
                        None,
                        {
                            "base_url": self.base_url,
                            "status_code": response.status_code,
                        },
                    )
                return False

        except Exception as e:
            error_msg = f"Unexpected error during authentication: {str(e)}"
            if self.logger:
                self.logger.log_error(
                    error_msg,
                    e,
                    {"base_url": self.base_url, "error_type": type(e).__name__},
                )
            return False

    def is_market_open(self) -> bool:
        """Check if the market is currently open.

        Returns:
            True if market is open, False otherwise
        """
        try:
            response = self.session.get(f"{self.base_url}/v1/markets/clock")

            if response.status_code == 200:
                clock_data = response.json()
                clock = clock_data.get("clock", {})
                is_open = clock.get("state") == "open"

                if self.logger:
                    self.logger.log_info(
                        f"Market status checked: {'OPEN' if is_open else 'CLOSED'}",
                        {
                            "state": clock.get("state"),
                            "timestamp": clock.get("timestamp"),
                        },
                    )

                return is_open
            else:
                if self.logger:
                    self.logger.log_warning(
                        f"Failed to check market status: {response.status_code}"
                    )
                return False

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
            response = self.session.get(f"{self.base_url}/v1/markets/clock")

            if response.status_code == 200:
                clock_data = response.json()
                clock = clock_data.get("clock", {})
                next_open_str = clock.get("next_open")

                if next_open_str:
                    next_open = datetime.fromisoformat(next_open_str.replace("Z", "+00:00"))

                    if self.logger:
                        self.logger.log_info(
                            "Retrieved market open time",
                            {"next_open": next_open.isoformat()},
                        )

                    return next_open
                else:
                    raise ValueError("Next open time not available in response")
            else:
                raise ValueError(f"Failed to get market clock: {response.status_code}")

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
            response = self.session.get(
                f"{self.base_url}/v1/markets/quotes", params={"symbols": symbol}
            )

            if response.status_code == 200:
                data = response.json()
                quotes = data.get("quotes", {}).get("quote", {})

                # Handle both single quote (dict) and multiple quotes (list)
                if isinstance(quotes, list):
                    quote = quotes[0] if quotes else {}
                else:
                    quote = quotes

                last_price = quote.get("last")

                if last_price is None:
                    raise ValueError(f"Price data unavailable for symbol {symbol}")

                price = float(last_price)

                if self.logger:
                    self.logger.log_info(
                        f"Retrieved current price for {symbol}",
                        {"symbol": symbol, "price": price},
                    )

                return price
            else:
                raise ValueError(f"Failed to get price for {symbol}: {response.status_code}")

        except ValueError:
            raise
        except Exception as e:
            error_msg = f"Unexpected error getting price for {symbol}: {str(e)}"
            if self.logger:
                self.logger.log_error(
                    error_msg, e, {"symbol": symbol, "error_type": type(e).__name__}
                )
            raise

    def get_option_expirations(self, symbol: str) -> List[date]:
        """Get available option expiration dates for a symbol.

        Args:
            symbol: Stock symbol (e.g., 'TLT')

        Returns:
            List of expiration dates sorted chronologically

        Raises:
            ValueError: If API request fails or no expirations available
        """
        try:
            response = self.session.get(
                f"{self.base_url}/v1/markets/options/expirations",
                params={"symbol": symbol}
            )

            if response.status_code != 200:
                error_msg = f"Tradier API error: {response.status_code} - {response.text}"
                if self.logger:
                    self.logger.log_error(
                        f"Failed to get option expirations for {symbol}",
                        None,
                        {
                            "symbol": symbol,
                            "status_code": response.status_code,
                            "response": response.text
                        }
                    )
                raise ValueError(error_msg)

            data = response.json()
            expirations_data = data.get("expirations")

            if not expirations_data:
                error_msg = f"No option expirations available for {symbol}"
                if self.logger:
                    self.logger.log_error(
                        error_msg,
                        None,
                        {"symbol": symbol, "response": data}
                    )
                raise ValueError(error_msg)

            date_strings = expirations_data.get("date", [])

            if not date_strings:
                error_msg = f"No option expirations available for {symbol}"
                if self.logger:
                    self.logger.log_error(
                        error_msg,
                        None,
                        {"symbol": symbol, "response": data}
                    )
                raise ValueError(error_msg)

            # Convert date strings to date objects
            expiration_dates = []
            for date_str in date_strings:
                try:
                    expiration_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    expiration_dates.append(expiration_date)
                except ValueError as e:
                    if self.logger:
                        self.logger.log_warning(
                            f"Failed to parse expiration date: {date_str}",
                            {"symbol": symbol, "date_str": date_str, "error": str(e)}
                        )
                    continue

            # Sort dates chronologically
            expiration_dates.sort()

            if self.logger:
                self.logger.log_info(
                    f"Retrieved {len(expiration_dates)} option expirations for {symbol}",
                    {
                        "symbol": symbol,
                        "count": len(expiration_dates),
                        "first_expiration": expiration_dates[0].isoformat() if expiration_dates else None,
                        "last_expiration": expiration_dates[-1].isoformat() if expiration_dates else None
                    }
                )

            return expiration_dates

        except ValueError:
            raise
        except Exception as e:
            error_msg = f"Unexpected error getting option expirations for {symbol}: {str(e)}"
            if self.logger:
                self.logger.log_error(
                    error_msg,
                    e,
                    {"symbol": symbol, "error_type": type(e).__name__}
                )
            raise ValueError(error_msg) from e

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
            # Format expiration date as string
            expiration_str = expiration.strftime("%Y-%m-%d")

            # Get options chain from Tradier
            response = self.session.get(
                f"{self.base_url}/v1/markets/options/chains",
                params={"symbol": symbol, "expiration": expiration_str},
            )

            if response.status_code != 200:
                raise ValueError(f"Failed to get option chain: {response.status_code}")

            data = response.json()
            options_data = data.get("options", {})

            if not options_data:
                raise ValueError(f"No options data available for {symbol}")

            options_list = options_data.get("option", [])

            # Ensure it's a list
            if isinstance(options_list, dict):
                options_list = [options_list]

            # Filter for put options only
            put_options = []
            for option in options_list:
                option_type = option.get("option_type", "").lower()
                strike = option.get("strike")
                option_symbol = option.get("symbol")

                if option_type == "put" and strike:
                    contract = OptionContract(
                        symbol=option_symbol,
                        strike=float(strike),
                        expiration=expiration,
                        option_type="put",
                    )
                    put_options.append(contract)

            if not put_options:
                raise ValueError(f"No put options found for {symbol} expiring {expiration_str}")

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
        """Submit a put credit spread order to Tradier.

        Args:
            spread: SpreadOrder object with order details

        Returns:
            OrderResult with order ID and status
        """
        try:
            # Format expiration date
            expiration_str = spread.expiration.strftime("%y%m%d")

            # Construct option symbols using OCC format
            # Format: SYMBOL + YYMMDD + C/P + Strike (8 digits with 3 decimals)
            short_strike_str = f"{int(spread.short_strike * 1000):08d}"
            long_strike_str = f"{int(spread.long_strike * 1000):08d}"

            short_symbol = f"{spread.symbol}{expiration_str}P{short_strike_str}"
            long_symbol = f"{spread.symbol}{expiration_str}P{long_strike_str}"

            # Create multileg order for put credit spread
            # Sell short put (higher strike) and buy long put (lower strike)
            order_data = {
                "class": "multileg",
                "symbol": spread.symbol,
                "type": "credit",
                "duration": spread.time_in_force,
                "option_symbol[0]": short_symbol,
                "side[0]": "sell_to_open",
                "quantity[0]": spread.quantity,
                "option_symbol[1]": long_symbol,
                "side[1]": "buy_to_open",
                "quantity[1]": spread.quantity,
            }

            # Submit the order
            response = self.session.post(
                f"{self.base_url}/v1/accounts/{self.account_id}/orders", data=order_data
            )

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
                            "status_code": response.status_code,
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

    def get_account_info(self) -> AccountInfo:
        """Get account information from Tradier.

        Returns:
            AccountInfo object with account details
        """
        try:
            response = self.session.get(f"{self.base_url}/v1/accounts/{self.account_id}/balances")

            if response.status_code == 200:
                data = response.json()
                balances = data.get("balances", {})

                info = AccountInfo(
                    account_number=self.account_id,
                    buying_power=float(balances.get("option_buying_power", 0)),
                    cash=float(balances.get("cash_available", 0)),
                    portfolio_value=float(balances.get("total_equity", 0)),
                )

                if self.logger:
                    self.logger.log_info(
                        "Retrieved account information",
                        {
                            "buying_power": info.buying_power,
                            "portfolio_value": info.portfolio_value,
                        },
                    )

                return info
            else:
                raise ValueError(f"Failed to get account info: {response.status_code}")

        except Exception as e:
            error_msg = f"Unexpected error getting account info: {str(e)}"
            if self.logger:
                self.logger.log_error(error_msg, e, {"error_type": type(e).__name__})
            raise
