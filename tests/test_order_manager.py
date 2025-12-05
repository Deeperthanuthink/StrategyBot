"""Unit tests for OrderManager."""

import pytest
from datetime import datetime, date
from unittest.mock import Mock, patch
import time

from src.order.order_manager import OrderManager, TradeResult
from src.alpaca.alpaca_client import SpreadOrder, OrderResult


class TestOrderManager:
    """Test cases for OrderManager."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        logger = Mock()
        logger.log_info = Mock()
        logger.log_error = Mock()
        logger.log_warning = Mock()
        logger.log_debug = Mock()
        logger.log_trade = Mock()
        return logger

    @pytest.fixture
    def mock_alpaca_client(self):
        """Create a mock Alpaca client."""
        client = Mock()
        client.submit_spread_order = Mock()
        return client

    @pytest.fixture
    def order_manager(self, mock_alpaca_client, mock_logger):
        """Create an OrderManager instance with mocks."""
        return OrderManager(alpaca_client=mock_alpaca_client, logger=mock_logger)

    def test_initialization(self, order_manager, mock_alpaca_client, mock_logger):
        """Test OrderManager initialization."""
        assert order_manager.alpaca_client == mock_alpaca_client
        assert order_manager.logger == mock_logger

    def test_create_spread_order(self, order_manager, mock_logger):
        """Test creating a spread order."""
        symbol = "NVDA"
        short_strike = 138.0
        long_strike = 133.0
        expiration = date(2025, 12, 6)
        quantity = 1

        order = order_manager.create_spread_order(
            symbol=symbol,
            short_strike=short_strike,
            long_strike=long_strike,
            expiration=expiration,
            quantity=quantity,
        )

        assert isinstance(order, SpreadOrder)
        assert order.symbol == symbol
        assert order.short_strike == short_strike
        assert order.long_strike == long_strike
        assert order.expiration == expiration
        assert order.quantity == quantity
        assert order.order_type == "limit"
        assert order.time_in_force == "day"
        mock_logger.log_debug.assert_called_once()

    def test_validate_order_success(self, order_manager, mock_logger):
        """Test successful order validation."""
        order = SpreadOrder(
            symbol="NVDA",
            short_strike=138.0,
            long_strike=133.0,
            expiration=date(2025, 12, 6),
            quantity=1,
        )

        is_valid, error_msg = order_manager.validate_order(order)

        assert is_valid is True
        assert error_msg is None
        mock_logger.log_debug.assert_called_once()

    def test_validate_order_empty_symbol(self, order_manager):
        """Test order validation with empty symbol."""
        order = SpreadOrder(
            symbol="",
            short_strike=138.0,
            long_strike=133.0,
            expiration=date(2025, 12, 6),
            quantity=1,
        )

        is_valid, error_msg = order_manager.validate_order(order)

        assert is_valid is False
        assert "Symbol cannot be empty" in error_msg

    def test_validate_order_lowercase_symbol(self, order_manager):
        """Test order validation with lowercase symbol."""
        order = SpreadOrder(
            symbol="nvda",
            short_strike=138.0,
            long_strike=133.0,
            expiration=date(2025, 12, 6),
            quantity=1,
        )

        is_valid, error_msg = order_manager.validate_order(order)

        assert is_valid is False
        assert "must be uppercase" in error_msg

    def test_validate_order_negative_short_strike(self, order_manager):
        """Test order validation with negative short strike."""
        order = SpreadOrder(
            symbol="NVDA",
            short_strike=-10.0,
            long_strike=133.0,
            expiration=date(2025, 12, 6),
            quantity=1,
        )

        is_valid, error_msg = order_manager.validate_order(order)

        assert is_valid is False
        assert "Short strike must be positive" in error_msg

    def test_validate_order_invalid_strike_ordering(self, order_manager):
        """Test order validation with invalid strike ordering for put credit spread."""
        order = SpreadOrder(
            symbol="NVDA",
            short_strike=133.0,  # Should be higher than long strike
            long_strike=138.0,
            expiration=date(2025, 12, 6),
            quantity=1,
        )

        is_valid, error_msg = order_manager.validate_order(order)

        assert is_valid is False
        assert "Short strike" in error_msg
        assert "must be higher than long strike" in error_msg

    def test_validate_order_negative_quantity(self, order_manager):
        """Test order validation with negative quantity."""
        order = SpreadOrder(
            symbol="NVDA",
            short_strike=138.0,
            long_strike=133.0,
            expiration=date(2025, 12, 6),
            quantity=-1,
        )

        is_valid, error_msg = order_manager.validate_order(order)

        assert is_valid is False
        assert "Quantity must be positive" in error_msg

    def test_validate_order_past_expiration(self, order_manager):
        """Test order validation with past expiration date."""
        order = SpreadOrder(
            symbol="NVDA",
            short_strike=138.0,
            long_strike=133.0,
            expiration=date(2020, 1, 1),  # Past date
            quantity=1,
        )

        is_valid, error_msg = order_manager.validate_order(order)

        assert is_valid is False
        assert "must be in the future" in error_msg

    def test_retry_order_validation_failure(self, order_manager, mock_logger):
        """Test retry_order with validation failure."""
        order = SpreadOrder(
            symbol="",  # Invalid empty symbol
            short_strike=138.0,
            long_strike=133.0,
            expiration=date(2025, 12, 6),
            quantity=1,
        )

        result = order_manager.retry_order(order, max_retries=3)

        assert result.success is False
        assert result.status == "validation_failed"
        assert "Symbol cannot be empty" in result.error_message
        mock_logger.log_error.assert_called_once()

    def test_retry_order_success_first_attempt(
        self, order_manager, mock_alpaca_client, mock_logger
    ):
        """Test retry_order succeeds on first attempt."""
        order = SpreadOrder(
            symbol="NVDA",
            short_strike=138.0,
            long_strike=133.0,
            expiration=date(2025, 12, 6),
            quantity=1,
        )

        # Mock successful order submission
        mock_alpaca_client.submit_spread_order.return_value = OrderResult(
            success=True, order_id="order_123", status="accepted", error_message=None
        )

        result = order_manager.retry_order(order, max_retries=3)

        assert result.success is True
        assert result.order_id == "order_123"
        assert result.status == "accepted"
        mock_alpaca_client.submit_spread_order.assert_called_once_with(order)

    @patch("time.sleep")
    def test_retry_order_success_after_retries(
        self, mock_sleep, order_manager, mock_alpaca_client, mock_logger
    ):
        """Test retry_order succeeds after retries."""
        order = SpreadOrder(
            symbol="NVDA",
            short_strike=138.0,
            long_strike=133.0,
            expiration=date(2025, 12, 6),
            quantity=1,
        )

        # Mock first two attempts fail, third succeeds
        mock_alpaca_client.submit_spread_order.side_effect = [
            OrderResult(
                success=False,
                order_id=None,
                status="error",
                error_message="Network timeout",
            ),
            OrderResult(
                success=False,
                order_id=None,
                status="error",
                error_message="Network timeout",
            ),
            OrderResult(
                success=True,
                order_id="order_123",
                status="accepted",
                error_message=None,
            ),
        ]

        result = order_manager.retry_order(order, max_retries=3)

        assert result.success is True
        assert result.order_id == "order_123"
        assert mock_alpaca_client.submit_spread_order.call_count == 3
        # Verify exponential backoff: 1s, 2s
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)

    @patch("time.sleep")
    def test_retry_order_max_retries_exceeded(
        self, mock_sleep, order_manager, mock_alpaca_client, mock_logger
    ):
        """Test retry_order fails after max retries."""
        order = SpreadOrder(
            symbol="NVDA",
            short_strike=138.0,
            long_strike=133.0,
            expiration=date(2025, 12, 6),
            quantity=1,
        )

        # Mock all attempts fail
        mock_alpaca_client.submit_spread_order.return_value = OrderResult(
            success=False,
            order_id=None,
            status="error",
            error_message="Network timeout",
        )

        result = order_manager.retry_order(order, max_retries=3)

        assert result.success is False
        assert result.status == "max_retries_exceeded"
        assert "Failed after 3 attempts" in result.error_message
        assert mock_alpaca_client.submit_spread_order.call_count == 3
        # Verify exponential backoff: 1s, 2s, 4s (but only 2 sleeps since last attempt doesn't sleep)
        assert mock_sleep.call_count == 2

    def test_retry_order_non_retryable_error(self, order_manager, mock_alpaca_client, mock_logger):
        """Test retry_order stops on non-retryable error."""
        order = SpreadOrder(
            symbol="NVDA",
            short_strike=138.0,
            long_strike=133.0,
            expiration=date(2025, 12, 6),
            quantity=1,
        )

        # Mock non-retryable error (insufficient buying power)
        mock_alpaca_client.submit_spread_order.return_value = OrderResult(
            success=False,
            order_id=None,
            status="rejected",
            error_message="Insufficient buying power",
        )

        result = order_manager.retry_order(order, max_retries=3)

        assert result.success is False
        assert "Insufficient buying power" in result.error_message
        # Should only try once since error is non-retryable
        mock_alpaca_client.submit_spread_order.assert_called_once()

    @patch("time.sleep")
    def test_retry_order_exception_handling(
        self, mock_sleep, order_manager, mock_alpaca_client, mock_logger
    ):
        """Test retry_order handles exceptions."""
        order = SpreadOrder(
            symbol="NVDA",
            short_strike=138.0,
            long_strike=133.0,
            expiration=date(2025, 12, 6),
            quantity=1,
        )

        # Mock exception on all attempts
        mock_alpaca_client.submit_spread_order.side_effect = Exception("Connection error")

        result = order_manager.retry_order(order, max_retries=3)

        assert result.success is False
        assert result.status == "max_retries_exceeded"
        assert "Connection error" in result.error_message
        assert mock_alpaca_client.submit_spread_order.call_count == 3

    def test_is_retryable_error_network_errors(self, order_manager):
        """Test _is_retryable_error identifies retryable errors."""
        # Network/timeout errors should be retryable
        assert order_manager._is_retryable_error("Network timeout") is True
        assert order_manager._is_retryable_error("Connection error") is True
        assert order_manager._is_retryable_error("Temporary error") is True
        assert order_manager._is_retryable_error(None) is True

    def test_is_retryable_error_non_retryable(self, order_manager):
        """Test _is_retryable_error identifies non-retryable errors."""
        # These errors should not be retried
        assert order_manager._is_retryable_error("Insufficient buying power") is False
        assert order_manager._is_retryable_error("Invalid strike price") is False
        assert order_manager._is_retryable_error("Invalid symbol") is False
        assert order_manager._is_retryable_error("Symbol not found") is False
        assert order_manager._is_retryable_error("Unauthorized access") is False
        assert order_manager._is_retryable_error("Order rejected") is False

    def test_submit_order_with_error_handling_success(
        self, order_manager, mock_alpaca_client, mock_logger
    ):
        """Test submit_order_with_error_handling with successful order."""
        mock_alpaca_client.submit_spread_order.return_value = OrderResult(
            success=True, order_id="order_123", status="accepted", error_message=None
        )

        result = order_manager.submit_order_with_error_handling(
            symbol="NVDA",
            short_strike=138.0,
            long_strike=133.0,
            expiration=date(2025, 12, 6),
            quantity=1,
            max_retries=3,
        )

        assert isinstance(result, TradeResult)
        assert result.success is True
        assert result.symbol == "NVDA"
        assert result.order_id == "order_123"
        assert result.short_strike == 138.0
        assert result.long_strike == 133.0
        assert result.error_message is None
        mock_logger.log_trade.assert_called_once()

    def test_submit_order_with_error_handling_failure(
        self, order_manager, mock_alpaca_client, mock_logger
    ):
        """Test submit_order_with_error_handling with order failure."""
        mock_alpaca_client.submit_spread_order.return_value = OrderResult(
            success=False,
            order_id=None,
            status="rejected",
            error_message="Insufficient buying power",
        )

        result = order_manager.submit_order_with_error_handling(
            symbol="NVDA",
            short_strike=138.0,
            long_strike=133.0,
            expiration=date(2025, 12, 6),
            quantity=1,
            max_retries=3,
        )

        assert isinstance(result, TradeResult)
        assert result.success is False
        assert result.symbol == "NVDA"
        assert result.order_id is None
        assert "Insufficient buying power" in result.error_message
        mock_logger.log_trade.assert_called_once()

    @patch("time.sleep")
    def test_submit_order_with_error_handling_value_error(
        self, mock_sleep, order_manager, mock_alpaca_client, mock_logger
    ):
        """Test submit_order_with_error_handling handles ValueError."""
        # Simulate ValueError during order creation/submission
        mock_alpaca_client.submit_spread_order.side_effect = ValueError("Invalid strike price")

        result = order_manager.submit_order_with_error_handling(
            symbol="NVDA",
            short_strike=138.0,
            long_strike=133.0,
            expiration=date(2025, 12, 6),
            quantity=1,
            max_retries=3,
        )

        assert isinstance(result, TradeResult)
        assert result.success is False
        # The error goes through retry logic, so check for the actual error message
        assert "Invalid strike price" in result.error_message
        mock_logger.log_error.assert_called()

    @patch("time.sleep")
    def test_submit_order_with_error_handling_connection_error(
        self, mock_sleep, order_manager, mock_alpaca_client, mock_logger
    ):
        """Test submit_order_with_error_handling handles ConnectionError."""
        mock_alpaca_client.submit_spread_order.side_effect = ConnectionError("Network unreachable")

        result = order_manager.submit_order_with_error_handling(
            symbol="NVDA",
            short_strike=138.0,
            long_strike=133.0,
            expiration=date(2025, 12, 6),
            quantity=1,
            max_retries=3,
        )

        assert isinstance(result, TradeResult)
        assert result.success is False
        # The error goes through retry logic, so check for the actual error message
        assert "Network unreachable" in result.error_message
        mock_logger.log_error.assert_called()

    @patch("time.sleep")
    def test_submit_order_with_error_handling_timeout_error(
        self, mock_sleep, order_manager, mock_alpaca_client, mock_logger
    ):
        """Test submit_order_with_error_handling handles TimeoutError."""
        mock_alpaca_client.submit_spread_order.side_effect = TimeoutError("Request timeout")

        result = order_manager.submit_order_with_error_handling(
            symbol="NVDA",
            short_strike=138.0,
            long_strike=133.0,
            expiration=date(2025, 12, 6),
            quantity=1,
            max_retries=3,
        )

        assert isinstance(result, TradeResult)
        assert result.success is False
        # The error goes through retry logic, so check for the actual error message
        assert "Request timeout" in result.error_message
        mock_logger.log_error.assert_called()

    def test_submit_order_with_error_handling_unexpected_error(
        self, order_manager, mock_alpaca_client, mock_logger
    ):
        """Test submit_order_with_error_handling handles unexpected errors."""
        mock_alpaca_client.submit_spread_order.side_effect = RuntimeError("Unexpected error")

        result = order_manager.submit_order_with_error_handling(
            symbol="NVDA",
            short_strike=138.0,
            long_strike=133.0,
            expiration=date(2025, 12, 6),
            quantity=1,
            max_retries=3,
        )

        assert isinstance(result, TradeResult)
        assert result.success is False
        assert "Unexpected error" in result.error_message
        mock_logger.log_error.assert_called()

    def test_log_trade_result(self, order_manager, mock_logger):
        """Test _log_trade_result logs correctly."""
        trade_result = TradeResult(
            symbol="NVDA",
            success=True,
            order_id="order_123",
            short_strike=138.0,
            long_strike=133.0,
            expiration=date(2025, 12, 6),
            quantity=1,
            filled_price=0.50,
            error_message=None,
            timestamp=datetime(2025, 11, 25, 10, 0, 0),
        )

        order_manager._log_trade_result(trade_result)

        mock_logger.log_trade.assert_called_once()
        call_args = mock_logger.log_trade.call_args[0][0]
        assert call_args["symbol"] == "NVDA"
        assert call_args["success"] is True
        assert call_args["order_id"] == "order_123"
