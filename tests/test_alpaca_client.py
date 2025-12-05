"""Unit tests for AlpacaClient."""

import pytest
from datetime import datetime, date
from unittest.mock import Mock, MagicMock, patch
from alpaca_trade_api.rest import APIError

from src.alpaca.alpaca_client import (
    AlpacaClient,
    OptionContract,
    SpreadOrder,
    OrderResult,
    AccountInfo,
)


class TestAlpacaClient:
    """Test cases for AlpacaClient."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        logger = Mock()
        logger.log_info = Mock()
        logger.log_error = Mock()
        logger.log_warning = Mock()
        return logger

    @pytest.fixture
    def client(self, mock_logger):
        """Create an AlpacaClient instance with mock logger."""
        return AlpacaClient(
            api_key="test_key",
            api_secret="test_secret",
            base_url="https://paper-api.alpaca.markets",
            logger=mock_logger,
        )

    def test_initialization(self, client):
        """Test client initialization."""
        assert client.api_key == "test_key"
        assert client.api_secret == "test_secret"
        assert client.base_url == "https://paper-api.alpaca.markets"
        assert client._api is None

    @patch("src.alpaca.alpaca_client.tradeapi.REST")
    def test_authenticate_success(self, mock_rest, client, mock_logger):
        """Test successful authentication."""
        # Mock account response
        mock_account = Mock()
        mock_account.id = "test_account_id"
        mock_account.status = "ACTIVE"

        mock_api = Mock()
        mock_api.get_account.return_value = mock_account
        mock_rest.return_value = mock_api

        result = client.authenticate()

        assert result is True
        assert client._api is not None
        mock_rest.assert_called_once_with(
            key_id="test_key",
            secret_key="test_secret",
            base_url="https://paper-api.alpaca.markets",
            api_version="v2",
        )
        mock_logger.log_info.assert_called_once()

    @patch("src.alpaca.alpaca_client.tradeapi.REST")
    def test_authenticate_api_error(self, mock_rest, client, mock_logger):
        """Test authentication failure with API error."""
        mock_rest.side_effect = APIError({"message": "Invalid credentials"})

        result = client.authenticate()

        assert result is False
        mock_logger.log_error.assert_called_once()

    @patch("src.alpaca.alpaca_client.tradeapi.REST")
    def test_authenticate_unexpected_error(self, mock_rest, client, mock_logger):
        """Test authentication failure with unexpected error."""
        mock_rest.side_effect = Exception("Unexpected error")

        result = client.authenticate()

        assert result is False
        mock_logger.log_error.assert_called_once()

    def test_is_market_open_not_authenticated(self, client):
        """Test is_market_open raises error when not authenticated."""
        with pytest.raises(RuntimeError) as exc_info:
            client.is_market_open()

        assert "not authenticated" in str(exc_info.value)

    def test_is_market_open_success(self, client, mock_logger):
        """Test successful market status check."""
        # Mock API and clock response
        mock_clock = Mock()
        mock_clock.is_open = True
        mock_clock.timestamp = datetime(2025, 11, 25, 10, 0, 0)
        mock_clock.next_open = datetime(2025, 11, 26, 9, 30, 0)

        client._api = Mock()
        client._api.get_clock.return_value = mock_clock

        result = client.is_market_open()

        assert result is True
        client._api.get_clock.assert_called_once()
        mock_logger.log_info.assert_called_once()

    def test_is_market_open_closed(self, client, mock_logger):
        """Test market status check when market is closed."""
        mock_clock = Mock()
        mock_clock.is_open = False
        mock_clock.timestamp = datetime(2025, 11, 25, 20, 0, 0)
        mock_clock.next_open = datetime(2025, 11, 26, 9, 30, 0)

        client._api = Mock()
        client._api.get_clock.return_value = mock_clock

        result = client.is_market_open()

        assert result is False

    def test_is_market_open_api_error(self, client, mock_logger):
        """Test market status check with API error."""
        client._api = Mock()
        client._api.get_clock.side_effect = APIError({"message": "API error"})

        with pytest.raises(APIError):
            client.is_market_open()

        mock_logger.log_error.assert_called_once()

    def test_get_market_open_time_success(self, client, mock_logger):
        """Test successful retrieval of market open time."""
        expected_time = datetime(2025, 11, 26, 9, 30, 0)

        mock_clock = Mock()
        mock_clock.next_open = expected_time

        client._api = Mock()
        client._api.get_clock.return_value = mock_clock

        result = client.get_market_open_time()

        assert result == expected_time
        mock_logger.log_info.assert_called_once()

    def test_get_market_open_time_not_authenticated(self, client):
        """Test get_market_open_time raises error when not authenticated."""
        with pytest.raises(RuntimeError) as exc_info:
            client.get_market_open_time()

        assert "not authenticated" in str(exc_info.value)

    def test_get_current_price_success(self, client, mock_logger):
        """Test successful price retrieval."""
        mock_trade = Mock()
        mock_trade.price = 145.50
        mock_trade.timestamp = datetime(2025, 11, 25, 10, 0, 0)

        client._api = Mock()
        client._api.get_latest_trade.return_value = mock_trade

        result = client.get_current_price("NVDA")

        assert result == 145.50
        client._api.get_latest_trade.assert_called_once_with("NVDA")
        mock_logger.log_info.assert_called_once()

    def test_get_current_price_unavailable(self, client, mock_logger):
        """Test price retrieval when data is unavailable."""
        client._api = Mock()
        client._api.get_latest_trade.return_value = None

        with pytest.raises(ValueError) as exc_info:
            client.get_current_price("INVALID")

        assert "Price data unavailable" in str(exc_info.value)
        mock_logger.log_error.assert_called_once()

    def test_get_current_price_api_error(self, client, mock_logger):
        """Test price retrieval with API error."""
        client._api = Mock()
        client._api.get_latest_trade.side_effect = APIError({"message": "Symbol not found"})

        with pytest.raises(ValueError) as exc_info:
            client.get_current_price("INVALID")

        assert "Price data unavailable" in str(exc_info.value)
        mock_logger.log_error.assert_called_once()

    def test_get_current_price_not_authenticated(self, client):
        """Test get_current_price raises error when not authenticated."""
        with pytest.raises(RuntimeError) as exc_info:
            client.get_current_price("NVDA")

        assert "not authenticated" in str(exc_info.value)

    def test_get_option_chain_success(self, client, mock_logger):
        """Test successful option chain retrieval."""
        expiration = date(2025, 12, 6)

        # Mock option contracts
        mock_contract1 = Mock()
        mock_contract1.symbol = "NVDA251206P00138000"
        mock_contract1.strike_price = 138.0
        mock_contract1.type = "put"

        mock_contract2 = Mock()
        mock_contract2.symbol = "NVDA251206P00133000"
        mock_contract2.strike_price = 133.0
        mock_contract2.type = "put"

        mock_contract3 = Mock()
        mock_contract3.symbol = "NVDA251206C00150000"
        mock_contract3.strike_price = 150.0
        mock_contract3.type = "call"

        client._api = Mock()
        client._api.get_option_contracts.return_value = [
            mock_contract1,
            mock_contract2,
            mock_contract3,
        ]

        result = client.get_option_chain("NVDA", expiration)

        assert len(result) == 2  # Only put options
        assert all(isinstance(opt, OptionContract) for opt in result)
        assert all(opt.option_type == "put" for opt in result)
        assert result[0].strike == 138.0
        assert result[1].strike == 133.0
        mock_logger.log_info.assert_called_once()

    def test_get_option_chain_no_puts_found(self, client, mock_logger):
        """Test option chain retrieval when no put options are found."""
        expiration = date(2025, 12, 6)

        # Mock only call options
        mock_contract = Mock()
        mock_contract.symbol = "NVDA251206C00150000"
        mock_contract.strike_price = 150.0
        mock_contract.type = "call"

        client._api = Mock()
        client._api.get_option_contracts.return_value = [mock_contract]

        with pytest.raises(ValueError) as exc_info:
            client.get_option_chain("NVDA", expiration)

        assert "No put options found" in str(exc_info.value)

    def test_get_option_chain_api_unavailable(self, client, mock_logger):
        """Test option chain retrieval when API method is unavailable."""
        expiration = date(2025, 12, 6)

        client._api = Mock()
        # Simulate AttributeError when method doesn't exist
        client._api.get_option_contracts.side_effect = AttributeError("Method not found")

        with pytest.raises(ValueError) as exc_info:
            client.get_option_chain("NVDA", expiration)

        assert "Option chain unavailable" in str(exc_info.value)
        mock_logger.log_warning.assert_called_once()

    def test_get_option_chain_not_authenticated(self, client):
        """Test get_option_chain raises error when not authenticated."""
        with pytest.raises(RuntimeError) as exc_info:
            client.get_option_chain("NVDA", date(2025, 12, 6))

        assert "not authenticated" in str(exc_info.value)

    def test_submit_spread_order_success(self, client, mock_logger):
        """Test successful spread order submission."""
        spread = SpreadOrder(
            symbol="NVDA",
            short_strike=138.0,
            long_strike=133.0,
            expiration=date(2025, 12, 6),
            quantity=1,
            order_type="limit",
            time_in_force="day",
        )

        mock_order = Mock()
        mock_order.id = "order_123"
        mock_order.status = "accepted"

        client._api = Mock()
        client._api.submit_order.return_value = mock_order

        result = client.submit_spread_order(spread)

        assert result.success is True
        assert result.order_id == "order_123"
        assert result.status == "accepted"
        assert result.error_message is None
        client._api.submit_order.assert_called_once()
        mock_logger.log_info.assert_called_once()

    def test_submit_spread_order_api_error(self, client, mock_logger):
        """Test spread order submission with API error."""
        spread = SpreadOrder(
            symbol="NVDA",
            short_strike=138.0,
            long_strike=133.0,
            expiration=date(2025, 12, 6),
            quantity=1,
        )

        client._api = Mock()
        client._api.submit_order.side_effect = APIError({"message": "Insufficient buying power"})

        result = client.submit_spread_order(spread)

        assert result.success is False
        assert result.order_id is None
        assert result.status == "rejected"
        assert "Insufficient buying power" in result.error_message
        mock_logger.log_error.assert_called_once()

    def test_submit_spread_order_unexpected_error(self, client, mock_logger):
        """Test spread order submission with unexpected error."""
        spread = SpreadOrder(
            symbol="NVDA",
            short_strike=138.0,
            long_strike=133.0,
            expiration=date(2025, 12, 6),
            quantity=1,
        )

        client._api = Mock()
        client._api.submit_order.side_effect = Exception("Network error")

        result = client.submit_spread_order(spread)

        assert result.success is False
        assert result.order_id is None
        assert result.status == "error"
        assert "Network error" in result.error_message
        mock_logger.log_error.assert_called_once()

    def test_submit_spread_order_not_authenticated(self, client):
        """Test submit_spread_order raises error when not authenticated."""
        spread = SpreadOrder(
            symbol="NVDA",
            short_strike=138.0,
            long_strike=133.0,
            expiration=date(2025, 12, 6),
            quantity=1,
        )

        with pytest.raises(RuntimeError) as exc_info:
            client.submit_spread_order(spread)

        assert "not authenticated" in str(exc_info.value)

    def test_get_account_info_success(self, client, mock_logger):
        """Test successful account info retrieval."""
        mock_account = Mock()
        mock_account.account_number = "123456"
        mock_account.buying_power = "50000.00"
        mock_account.cash = "25000.00"
        mock_account.portfolio_value = "75000.00"

        client._api = Mock()
        client._api.get_account.return_value = mock_account

        result = client.get_account_info()

        assert isinstance(result, AccountInfo)
        assert result.account_number == "123456"
        assert result.buying_power == 50000.00
        assert result.cash == 25000.00
        assert result.portfolio_value == 75000.00
        mock_logger.log_info.assert_called_once()

    def test_get_account_info_not_authenticated(self, client):
        """Test get_account_info raises error when not authenticated."""
        with pytest.raises(RuntimeError) as exc_info:
            client.get_account_info()

        assert "not authenticated" in str(exc_info.value)
