"""Order management with retry logic and error handling."""

from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional
import time

from src.brokers.base_client import BaseBrokerClient, SpreadOrder, OrderResult
from src.logging.bot_logger import BotLogger


@dataclass
class TradeResult:
    """Result of a trade execution."""

    symbol: str
    success: bool
    order_id: Optional[str]
    short_strike: float
    long_strike: float
    expiration: date
    quantity: int
    filled_price: Optional[float]
    error_message: Optional[str]
    timestamp: datetime


class OrderManager:
    """Manages order creation, validation, and execution with retry logic."""

    def __init__(self, broker_client: BaseBrokerClient, logger: BotLogger, dry_run: bool = False):
        """Initialize OrderManager.

        Args:
            broker_client: BaseBrokerClient instance for order execution
            logger: BotLogger instance for logging
            dry_run: If True, simulate order submission without actually placing orders
        """
        self.broker_client = broker_client
        self.logger = logger
        self.dry_run = dry_run

    def create_spread_order(
        self,
        symbol: str,
        short_strike: float,
        long_strike: float,
        expiration: date,
        quantity: int,
    ) -> SpreadOrder:
        """Create a put credit spread order object.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            short_strike: Strike price for the short put (higher strike)
            long_strike: Strike price for the long put (lower strike)
            expiration: Option expiration date
            quantity: Number of contracts

        Returns:
            SpreadOrder object
        """
        order = SpreadOrder(
            symbol=symbol,
            short_strike=short_strike,
            long_strike=long_strike,
            expiration=expiration,
            quantity=quantity,
            order_type="limit",
            time_in_force="gtc",  # Good-Til-Canceled allows orders when market is closed
        )

        self.logger.log_debug(
            f"Created spread order for {symbol}",
            {
                "symbol": symbol,
                "short_strike": short_strike,
                "long_strike": long_strike,
                "expiration": expiration.isoformat(),
                "quantity": quantity,
            },
        )

        return order

    def validate_order(self, order: SpreadOrder) -> tuple[bool, Optional[str]]:
        """Validate order parameters.

        Args:
            order: SpreadOrder to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Validate symbol
        if not order.symbol or not order.symbol.strip():
            return False, "Symbol cannot be empty"

        if not order.symbol.isupper():
            return False, f"Symbol '{order.symbol}' must be uppercase"

        # Validate strikes
        if order.short_strike <= 0:
            return False, "Short strike must be positive"

        if order.long_strike <= 0:
            return False, "Long strike must be positive"

        # For put credit spread, short strike should be higher than long strike
        if order.short_strike <= order.long_strike:
            return (
                False,
                f"Short strike ({order.short_strike}) must be higher than long strike ({order.long_strike}) for put credit spread",
            )

        # Validate spread width is reasonable (not too wide)
        spread_width = order.short_strike - order.long_strike
        if spread_width <= 0:
            return False, "Spread width must be positive"

        # Validate quantity
        if order.quantity <= 0:
            return False, "Quantity must be positive"

        if not isinstance(order.quantity, int):
            return False, "Quantity must be an integer"

        # Validate expiration is in the future
        if order.expiration < date.today():
            return False, f"Expiration date ({order.expiration}) must be in the future"

        self.logger.log_debug(
            f"Order validation passed for {order.symbol}",
            {
                "symbol": order.symbol,
                "short_strike": order.short_strike,
                "long_strike": order.long_strike,
                "spread_width": spread_width,
            },
        )

        return True, None

    def retry_order(self, order: SpreadOrder, max_retries: int = 3) -> OrderResult:
        """Submit order with retry logic and exponential backoff.

        Args:
            order: SpreadOrder to submit
            max_retries: Maximum number of retry attempts (default 3)

        Returns:
            OrderResult with final status
        """
        # Validate order before attempting submission
        is_valid, error_msg = self.validate_order(order)
        if not is_valid:
            self.logger.log_error(
                f"Order validation failed for {order.symbol}: {error_msg}",
                context={"symbol": order.symbol, "error": error_msg},
            )
            return OrderResult(
                success=False,
                order_id=None,
                status="validation_failed",
                error_message=error_msg,
            )

        attempt = 0
        last_error = None

        while attempt < max_retries:
            attempt += 1

            try:
                if self.dry_run:
                    self.logger.log_info(
                        f"[DRY-RUN] Simulating order submission for {order.symbol} (attempt {attempt}/{max_retries})",
                        {
                            "symbol": order.symbol,
                            "attempt": attempt,
                            "max_retries": max_retries,
                            "short_strike": order.short_strike,
                            "long_strike": order.long_strike,
                            "dry_run": True,
                        },
                    )

                    # Simulate successful order in dry-run mode
                    result = OrderResult(
                        success=True,
                        order_id=f"DRY-RUN-{order.symbol}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        status="simulated",
                        error_message=None,
                    )
                else:
                    self.logger.log_info(
                        f"Submitting order for {order.symbol} (attempt {attempt}/{max_retries})",
                        {
                            "symbol": order.symbol,
                            "attempt": attempt,
                            "max_retries": max_retries,
                            "short_strike": order.short_strike,
                            "long_strike": order.long_strike,
                        },
                    )

                    # Submit order through Alpaca client
                    result = self.broker_client.submit_spread_order(order)

                if result.success:
                    self.logger.log_info(
                        f"Order successfully submitted for {order.symbol}",
                        {
                            "symbol": order.symbol,
                            "order_id": result.order_id,
                            "status": result.status,
                            "attempts": attempt,
                        },
                    )
                    return result
                else:
                    # Order failed, log and potentially retry
                    last_error = result.error_message
                    self.logger.log_warning(
                        f"Order submission failed for {order.symbol} (attempt {attempt}/{max_retries}): {result.error_message}",
                        {
                            "symbol": order.symbol,
                            "attempt": attempt,
                            "error": result.error_message,
                        },
                    )

                    # Check if error is retryable
                    if not self._is_retryable_error(result.error_message):
                        self.logger.log_error(
                            f"Non-retryable error for {order.symbol}, aborting retries",
                            context={
                                "symbol": order.symbol,
                                "error": result.error_message,
                            },
                        )
                        return result

                    # If not last attempt, wait with exponential backoff
                    if attempt < max_retries:
                        backoff_time = 2 ** (attempt - 1)  # 1s, 2s, 4s
                        self.logger.log_info(
                            f"Retrying order for {order.symbol} after {backoff_time}s backoff",
                            {"symbol": order.symbol, "backoff_seconds": backoff_time},
                        )
                        time.sleep(backoff_time)

            except Exception as e:
                last_error = str(e)
                self.logger.log_error(
                    f"Unexpected error submitting order for {order.symbol} (attempt {attempt}/{max_retries})",
                    e,
                    {
                        "symbol": order.symbol,
                        "attempt": attempt,
                        "error_type": type(e).__name__,
                    },
                )

                # If not last attempt, wait with exponential backoff
                if attempt < max_retries:
                    backoff_time = 2 ** (attempt - 1)  # 1s, 2s, 4s
                    self.logger.log_info(
                        f"Retrying order for {order.symbol} after {backoff_time}s backoff",
                        {"symbol": order.symbol, "backoff_seconds": backoff_time},
                    )
                    time.sleep(backoff_time)

        # All retries exhausted
        self.logger.log_error(
            f"Order failed for {order.symbol} after {max_retries} attempts",
            context={
                "symbol": order.symbol,
                "max_retries": max_retries,
                "last_error": last_error,
            },
        )

        return OrderResult(
            success=False,
            order_id=None,
            status="max_retries_exceeded",
            error_message=f"Failed after {max_retries} attempts. Last error: {last_error}",
        )

    def _is_retryable_error(self, error_message: Optional[str]) -> bool:
        """Determine if an error is retryable.

        Args:
            error_message: Error message from order submission

        Returns:
            True if error is retryable, False otherwise
        """
        if not error_message:
            return True

        error_lower = error_message.lower()

        # Non-retryable errors
        non_retryable_keywords = [
            "insufficient",  # Insufficient buying power
            "invalid strike",  # Invalid strike price
            "invalid symbol",  # Invalid symbol
            "not found",  # Symbol or option not found
            "unauthorized",  # Authentication issue
            "forbidden",  # Permission issue
            "rejected",  # Order explicitly rejected
        ]

        for keyword in non_retryable_keywords:
            if keyword in error_lower:
                return False

        # Retryable errors (network, timeout, temporary issues)
        return True

    def submit_order_with_error_handling(
        self,
        symbol: str,
        short_strike: float,
        long_strike: float,
        expiration: date,
        quantity: int,
        max_retries: int = 3,
    ) -> TradeResult:
        """Submit order with comprehensive error handling.

        This method wraps the entire order submission process with error handling
        to ensure that failures for one symbol don't stop processing of others.

        Args:
            symbol: Stock symbol
            short_strike: Strike price for the short put
            long_strike: Strike price for the long put
            expiration: Option expiration date
            quantity: Number of contracts
            max_retries: Maximum number of retry attempts

        Returns:
            TradeResult with execution details
        """
        timestamp = datetime.now()

        try:
            # Create the order
            order = self.create_spread_order(
                symbol=symbol,
                short_strike=short_strike,
                long_strike=long_strike,
                expiration=expiration,
                quantity=quantity,
            )

            # Submit with retry logic
            result = self.retry_order(order, max_retries=max_retries)

            # Create trade result
            trade_result = TradeResult(
                symbol=symbol,
                success=result.success,
                order_id=result.order_id,
                short_strike=short_strike,
                long_strike=long_strike,
                expiration=expiration,
                quantity=quantity,
                filled_price=None,  # Would need to query order status for actual fill price
                error_message=result.error_message,
                timestamp=timestamp,
            )

            # Log the trade result
            self._log_trade_result(trade_result)

            return trade_result

        except ValueError as e:
            # Handle validation or data errors
            error_msg = f"Validation error: {str(e)}"
            self.logger.log_error(
                f"Order submission failed for {symbol}: {error_msg}",
                e,
                {
                    "symbol": symbol,
                    "error_type": "ValueError",
                    "short_strike": short_strike,
                    "long_strike": long_strike,
                },
            )

            return TradeResult(
                symbol=symbol,
                success=False,
                order_id=None,
                short_strike=short_strike,
                long_strike=long_strike,
                expiration=expiration,
                quantity=quantity,
                filled_price=None,
                error_message=error_msg,
                timestamp=timestamp,
            )

        except ConnectionError as e:
            # Handle network/connection errors
            error_msg = f"Connection error: {str(e)}"
            self.logger.log_error(
                f"Network error submitting order for {symbol}: {error_msg}",
                e,
                {
                    "symbol": symbol,
                    "error_type": "ConnectionError",
                    "short_strike": short_strike,
                    "long_strike": long_strike,
                },
            )

            return TradeResult(
                symbol=symbol,
                success=False,
                order_id=None,
                short_strike=short_strike,
                long_strike=long_strike,
                expiration=expiration,
                quantity=quantity,
                filled_price=None,
                error_message=error_msg,
                timestamp=timestamp,
            )

        except TimeoutError as e:
            # Handle timeout errors
            error_msg = f"Timeout error: {str(e)}"
            self.logger.log_error(
                f"Timeout submitting order for {symbol}: {error_msg}",
                e,
                {
                    "symbol": symbol,
                    "error_type": "TimeoutError",
                    "short_strike": short_strike,
                    "long_strike": long_strike,
                },
            )

            return TradeResult(
                symbol=symbol,
                success=False,
                order_id=None,
                short_strike=short_strike,
                long_strike=long_strike,
                expiration=expiration,
                quantity=quantity,
                filled_price=None,
                error_message=error_msg,
                timestamp=timestamp,
            )

        except Exception as e:
            # Handle any unexpected errors
            error_msg = f"Unexpected error: {type(e).__name__}: {str(e)}"
            self.logger.log_error(
                f"Unexpected error submitting order for {symbol}: {error_msg}",
                e,
                {
                    "symbol": symbol,
                    "error_type": type(e).__name__,
                    "short_strike": short_strike,
                    "long_strike": long_strike,
                },
            )

            return TradeResult(
                symbol=symbol,
                success=False,
                order_id=None,
                short_strike=short_strike,
                long_strike=long_strike,
                expiration=expiration,
                quantity=quantity,
                filled_price=None,
                error_message=error_msg,
                timestamp=timestamp,
            )

    def _log_trade_result(self, trade_result: TradeResult):
        """Log trade result using the logger's trade logging method.

        Args:
            trade_result: TradeResult to log
        """
        trade_dict = {
            "symbol": trade_result.symbol,
            "success": trade_result.success,
            "order_id": trade_result.order_id,
            "short_strike": trade_result.short_strike,
            "long_strike": trade_result.long_strike,
            "expiration": trade_result.expiration.isoformat(),
            "quantity": trade_result.quantity,
            "filled_price": trade_result.filled_price,
            "error_message": trade_result.error_message,
            "timestamp": trade_result.timestamp.isoformat(),
        }

        self.logger.log_trade(trade_dict)

    def submit_collar_order(
        self,
        symbol: str,
        put_strike: float,
        call_strike: float,
        expiration: date,
        num_collars: int,
    ) -> TradeResult:
        """Submit a collar order with error handling.

        Args:
            symbol: Stock symbol
            put_strike: Strike price for protective put
            call_strike: Strike price for covered call
            expiration: Option expiration date
            num_collars: Number of collars

        Returns:
            TradeResult with execution details
        """
        timestamp = datetime.now()

        try:
            if self.dry_run:
                self.logger.log_info(
                    f"[DRY-RUN] Simulating collar order for {symbol}",
                    {
                        "symbol": symbol,
                        "put_strike": put_strike,
                        "call_strike": call_strike,
                        "num_collars": num_collars,
                        "dry_run": True,
                    },
                )

                result = OrderResult(
                    success=True,
                    order_id=f"DRY-RUN-COLLAR-{symbol}-{timestamp.strftime('%Y%m%d%H%M%S')}",
                    status="simulated",
                    error_message=None,
                )
            else:
                # Submit collar order through broker client
                result = self.broker_client.submit_collar_order(
                    symbol=symbol,
                    put_strike=put_strike,
                    call_strike=call_strike,
                    expiration=expiration,
                    num_collars=num_collars,
                )

            # Create trade result
            trade_result = TradeResult(
                symbol=symbol,
                success=result.success,
                order_id=result.order_id,
                short_strike=put_strike,  # Using put strike as "short"
                long_strike=call_strike,  # Using call strike as "long"
                expiration=expiration,
                quantity=num_collars,
                filled_price=None,
                error_message=result.error_message,
                timestamp=timestamp,
            )

            # Log the trade result
            self._log_trade_result(trade_result)

            return trade_result

        except Exception as e:
            error_msg = f"Unexpected error: {type(e).__name__}: {str(e)}"
            self.logger.log_error(
                f"Collar order submission failed for {symbol}: {error_msg}",
                e,
                {"symbol": symbol},
            )

            return TradeResult(
                symbol=symbol,
                success=False,
                order_id=None,
                short_strike=put_strike,
                long_strike=call_strike,
                expiration=expiration,
                quantity=num_collars,
                filled_price=None,
                error_message=error_msg,
                timestamp=timestamp,
            )
