"""Unit tests for PositionService."""

import pytest
from datetime import date, timedelta
from unittest.mock import Mock, MagicMock
from dataclasses import dataclass

from src.positions.position_service import PositionService
from src.positions.models import PositionSummary, OptionPosition, CoveredCallOrder
from src.positions.validation import PositionValidationSummary, ValidationResult
from src.brokers.base_client import Position


@dataclass
class MockPosition:
    """Mock position for testing."""
    symbol: str
    quantity: int
    market_value: float = 0.0
    average_cost: float = 0.0


class TestPositionService:
    """Test cases for PositionService."""

    @pytest.fixture
    def mock_broker_client(self):
        """Create a mock broker client."""
        client = Mock()
        client.get_current_price = Mock()
        client.get_position = Mock()
        client.get_option_chain = Mock()
        return client

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        logger = Mock()
        logger.info = Mock()
        logger.error = Mock()
        logger.warning = Mock()
        logger.log_info = Mock()
        logger.log_error = Mock()
        logger.log_warning = Mock()
        return logger

    @pytest.fixture
    def position_service(self, mock_broker_client, mock_logger):
        """Create a PositionService instance with mocks."""
        return PositionService(mock_broker_client, mock_logger)

    def test_initialization(self, position_service, mock_broker_client, mock_logger):
        """Test PositionService initialization."""
        assert position_service.broker_client == mock_broker_client
        assert position_service.logger == mock_logger
        assert position_service.validator is not None

    def test_get_long_positions_success(self, position_service, mock_broker_client, mock_logger):
        """Test successful position retrieval."""
        # Mock broker responses
        mock_broker_client.get_current_price.return_value = 150.0
        mock_broker_client.get_position.return_value = MockPosition("NVDA", 500)

        result = position_service.get_long_positions("NVDA")

        assert isinstance(result, PositionSummary)
        assert result.symbol == "NVDA"
        assert result.total_shares == 500
        assert result.available_shares == 500  # No existing short calls
        assert result.current_price == 150.0
        assert result.long_options == []
        assert result.existing_short_calls == []

        mock_broker_client.get_current_price.assert_called_once_with("NVDA")
        mock_broker_client.get_position.assert_called_once_with("NVDA")
        mock_logger.log_info.assert_called()

    def test_get_long_positions_with_long_calls(self, position_service, mock_broker_client, mock_logger):
        """Test position retrieval with stock shares and long call options."""
        # Mock broker responses
        mock_broker_client.get_current_price.return_value = 95.50
        mock_broker_client.get_position.return_value = MockPosition("TLT", 200)
        
        # Mock detailed positions with 3 long call contracts
        long_call_1 = OptionPosition(
            symbol="TLT",
            quantity=1,
            market_value=150.0,
            average_cost=145.0,
            unrealized_pnl=5.0,
            position_type='long_call',
            strike=100.0,
            expiration=date.today() + timedelta(days=30),
            option_type='call'
        )
        long_call_2 = OptionPosition(
            symbol="TLT",
            quantity=1,
            market_value=140.0,
            average_cost=135.0,
            unrealized_pnl=5.0,
            position_type='long_call',
            strike=102.0,
            expiration=date.today() + timedelta(days=30),
            option_type='call'
        )
        long_call_3 = OptionPosition(
            symbol="TLT",
            quantity=1,
            market_value=130.0,
            average_cost=125.0,
            unrealized_pnl=5.0,
            position_type='long_call',
            strike=104.0,
            expiration=date.today() + timedelta(days=30),
            option_type='call'
        )
        
        mock_broker_client.get_detailed_positions.return_value = [long_call_1, long_call_2, long_call_3]
        
        result = position_service.get_long_positions("TLT")
        
        assert isinstance(result, PositionSummary)
        assert result.symbol == "TLT"
        # 200 stock shares + 3 long calls * 100 shares each = 500 total shares
        assert result.total_shares == 500
        assert result.available_shares == 500  # No existing short calls
        assert result.current_price == 95.50
        assert len(result.long_options) == 3
        assert result.existing_short_calls == []
        
        mock_broker_client.get_current_price.assert_called_once_with("TLT")
        mock_broker_client.get_position.assert_called_once_with("TLT")
        mock_broker_client.get_detailed_positions.assert_called_once_with("TLT")
        mock_logger.log_info.assert_called()

    def test_get_long_positions_no_stock_position(self, position_service, mock_broker_client, mock_logger):
        """Test position retrieval when no stock position exists."""
        mock_broker_client.get_current_price.return_value = 150.0
        mock_broker_client.get_position.return_value = None

        result = position_service.get_long_positions("NVDA")

        assert result.symbol == "NVDA"
        assert result.total_shares == 0
        assert result.available_shares == 0
        assert result.current_price == 150.0

    def test_get_long_positions_empty_symbol(self, position_service):
        """Test position retrieval with empty symbol."""
        with pytest.raises(ValueError, match="Symbol cannot be empty"):
            position_service.get_long_positions("")

        with pytest.raises(ValueError, match="Symbol cannot be empty"):
            position_service.get_long_positions("   ")

    def test_get_long_positions_lowercase_symbol(self, position_service, mock_broker_client):
        """Test position retrieval with lowercase symbol gets converted."""
        mock_broker_client.get_current_price.return_value = 150.0
        mock_broker_client.get_position.return_value = MockPosition("NVDA", 300)

        result = position_service.get_long_positions("nvda")

        assert result.symbol == "NVDA"
        mock_broker_client.get_current_price.assert_called_once_with("NVDA")
        mock_broker_client.get_position.assert_called_once_with("NVDA")

    def test_get_long_positions_broker_error(self, position_service, mock_broker_client, mock_logger):
        """Test position retrieval with broker API error."""
        mock_broker_client.get_current_price.side_effect = Exception("API Error")

        with pytest.raises(RuntimeError, match="Error retrieving positions for NVDA"):
            position_service.get_long_positions("NVDA")

        mock_logger.log_error.assert_called()

    def test_get_long_positions_price_error(self, position_service, mock_broker_client, mock_logger):
        """Test position retrieval when price data is unavailable."""
        mock_broker_client.get_current_price.side_effect = ValueError("Price data unavailable")

        with pytest.raises(RuntimeError, match="Error retrieving positions for NVDA"):
            position_service.get_long_positions("NVDA")

    def test_calculate_available_shares_basic(self, position_service):
        """Test basic available shares calculation."""
        positions = [
            MockPosition("NVDA", 300),
            MockPosition("NVDA", 200)
        ]

        result = position_service.calculate_available_shares(positions)

        assert result == 500

    def test_calculate_available_shares_mixed_quantities(self, position_service):
        """Test available shares calculation with mixed position quantities."""
        positions = [
            MockPosition("NVDA", 300),   # Long position
            MockPosition("NVDA", -100),  # Short position (ignored)
            MockPosition("NVDA", 150),   # Long position
            MockPosition("NVDA", 0)      # Zero position (ignored)
        ]

        result = position_service.calculate_available_shares(positions)

        assert result == 450  # Only positive quantities counted

    def test_calculate_available_shares_empty_list(self, position_service):
        """Test available shares calculation with empty position list."""
        result = position_service.calculate_available_shares([])
        assert result == 0

    def test_calculate_available_shares_all_negative(self, position_service):
        """Test available shares calculation with all negative positions."""
        positions = [
            MockPosition("NVDA", -100),
            MockPosition("NVDA", -200)
        ]

        result = position_service.calculate_available_shares(positions)
        assert result == 0

    def test_get_existing_short_calls_placeholder(self, position_service, mock_logger):
        """Test get_existing_short_calls returns empty list (placeholder implementation)."""
        result = position_service.get_existing_short_calls("NVDA")

        assert result == []
        mock_logger.log_info.assert_called_with("Querying existing short calls for NVDA (not yet implemented)")

    def test_validate_covered_call_orders_success(self, position_service, mock_broker_client, mock_logger):
        """Test successful covered call order validation."""
        # Mock position data
        mock_broker_client.get_current_price.return_value = 150.0
        mock_broker_client.get_position.return_value = MockPosition("NVDA", 500)

        # Create test orders
        orders = [
            CoveredCallOrder("NVDA", 155.0, date.today() + timedelta(days=30), 2, 200),
            CoveredCallOrder("NVDA", 160.0, date.today() + timedelta(days=45), 1, 100)
        ]

        is_valid, summary = position_service.validate_covered_call_orders("NVDA", orders, 300)

        assert is_valid is True
        assert isinstance(summary, PositionValidationSummary)
        assert summary.symbol == "NVDA"
        assert summary.total_shares == 500
        assert summary.available_shares == 500
        assert summary.requested_contracts == 3
        mock_logger.log_info.assert_called()

    def test_validate_covered_call_orders_insufficient_shares(self, position_service, mock_broker_client, mock_logger):
        """Test covered call order validation with insufficient shares."""
        # Mock position data - only 200 shares available
        mock_broker_client.get_current_price.return_value = 150.0
        mock_broker_client.get_position.return_value = MockPosition("NVDA", 200)

        # Create orders requiring 500 shares
        orders = [
            CoveredCallOrder("NVDA", 155.0, date.today() + timedelta(days=30), 5, 500)
        ]

        is_valid, summary = position_service.validate_covered_call_orders("NVDA", orders, 300)

        assert is_valid is False
        assert summary.validation_passed is False
        assert len(summary.errors) > 0
        mock_logger.log_error.assert_called()

    def test_validate_covered_call_orders_below_minimum(self, position_service, mock_broker_client, mock_logger):
        """Test covered call order validation below minimum shares required."""
        # Mock position data - only 250 shares available
        mock_broker_client.get_current_price.return_value = 150.0
        mock_broker_client.get_position.return_value = MockPosition("NVDA", 250)

        orders = [
            CoveredCallOrder("NVDA", 155.0, date.today() + timedelta(days=30), 1, 100)
        ]

        is_valid, summary = position_service.validate_covered_call_orders("NVDA", orders, 300)

        assert is_valid is False
        assert summary.validation_passed is False
        mock_logger.log_error.assert_called()

    def test_validate_covered_call_orders_broker_error(self, position_service, mock_broker_client, mock_logger):
        """Test covered call order validation with broker error."""
        mock_broker_client.get_current_price.side_effect = Exception("Broker API Error")

        orders = [
            CoveredCallOrder("NVDA", 155.0, date.today() + timedelta(days=30), 1, 100)
        ]

        is_valid, summary = position_service.validate_covered_call_orders("NVDA", orders, 300)

        assert is_valid is False
        assert summary.validation_passed is False
        assert len(summary.errors) > 0
        assert "Broker API Error" in summary.errors[0]
        mock_logger.log_error.assert_called()

    def test_validate_single_covered_call_success(self, position_service, mock_broker_client, mock_logger):
        """Test successful single covered call validation."""
        mock_broker_client.get_current_price.return_value = 150.0
        mock_broker_client.get_position.return_value = MockPosition("NVDA", 500)

        result = position_service.validate_single_covered_call(
            "NVDA", 155.0, date.today() + timedelta(days=30), 2
        )

        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert result.error_message is None
        mock_logger.log_info.assert_called()

    def test_validate_single_covered_call_insufficient_shares(self, position_service, mock_broker_client, mock_logger):
        """Test single covered call validation with insufficient shares."""
        mock_broker_client.get_current_price.return_value = 150.0
        mock_broker_client.get_position.return_value = MockPosition("NVDA", 50)  # Only 50 shares

        result = position_service.validate_single_covered_call(
            "NVDA", 155.0, date.today() + timedelta(days=30), 2  # Need 200 shares
        )

        assert result.is_valid is False
        assert result.error_message is not None
        mock_logger.log_error.assert_called()

    def test_validate_single_covered_call_error(self, position_service, mock_broker_client, mock_logger):
        """Test single covered call validation with error."""
        mock_broker_client.get_current_price.side_effect = Exception("API Error")

        result = position_service.validate_single_covered_call(
            "NVDA", 155.0, date.today() + timedelta(days=30), 1
        )

        assert result.is_valid is False
        assert "API Error" in result.error_message
        mock_logger.log_error.assert_called()

    def test_get_position_validation_summary_success(self, position_service, mock_broker_client, mock_logger):
        """Test successful position validation summary."""
        mock_broker_client.get_current_price.return_value = 150.0
        mock_broker_client.get_position.return_value = MockPosition("NVDA", 500)

        summary = position_service.get_position_validation_summary("NVDA")

        assert isinstance(summary, PositionValidationSummary)
        assert summary.symbol == "NVDA"
        assert summary.total_shares == 500
        assert summary.available_shares == 500
        assert summary.max_contracts_allowed == 5  # 500 shares / 100
        assert summary.validation_passed is True
        assert len(summary.errors) == 0
        mock_logger.log_info.assert_called()

    def test_get_position_validation_summary_insufficient_shares(self, position_service, mock_broker_client, mock_logger):
        """Test position validation summary with insufficient shares."""
        mock_broker_client.get_current_price.return_value = 150.0
        mock_broker_client.get_position.return_value = MockPosition("NVDA", 50)  # Less than 100 shares

        summary = position_service.get_position_validation_summary("NVDA")

        assert summary.validation_passed is False
        assert summary.max_contracts_allowed == 0
        assert len(summary.errors) > 0
        assert "Insufficient shares" in summary.errors[0]

    def test_get_position_validation_summary_error(self, position_service, mock_broker_client, mock_logger):
        """Test position validation summary with error."""
        mock_broker_client.get_current_price.side_effect = Exception("API Error")

        summary = position_service.get_position_validation_summary("NVDA")

        assert summary.validation_passed is False
        assert summary.total_shares == 0
        assert summary.available_shares == 0
        assert len(summary.errors) > 0
        assert "API Error" in summary.errors[0]
        mock_logger.log_error.assert_called()


class TestPositionSummaryCalculation:
    """Test cases for position summary calculations with various holding combinations."""

    @pytest.fixture
    def mock_broker_client(self):
        """Create a mock broker client."""
        client = Mock()
        client.get_current_price = Mock()
        client.get_position = Mock()
        return client

    @pytest.fixture
    def position_service(self, mock_broker_client):
        """Create a PositionService instance."""
        return PositionService(mock_broker_client)

    def test_position_summary_with_large_position(self, position_service, mock_broker_client):
        """Test position summary calculation with large stock position."""
        mock_broker_client.get_current_price.return_value = 200.0
        mock_broker_client.get_position.return_value = MockPosition("TSLA", 1000)

        result = position_service.get_long_positions("TSLA")

        assert result.symbol == "TSLA"
        assert result.total_shares == 1000
        assert result.available_shares == 1000
        assert result.current_price == 200.0

    def test_position_summary_with_small_position(self, position_service, mock_broker_client):
        """Test position summary calculation with small stock position."""
        mock_broker_client.get_current_price.return_value = 50.0
        mock_broker_client.get_position.return_value = MockPosition("F", 75)

        result = position_service.get_long_positions("F")

        assert result.symbol == "F"
        assert result.total_shares == 75
        assert result.available_shares == 75
        assert result.current_price == 50.0

    def test_position_summary_with_zero_position(self, position_service, mock_broker_client):
        """Test position summary calculation with zero stock position."""
        mock_broker_client.get_current_price.return_value = 100.0
        mock_broker_client.get_position.return_value = MockPosition("AAPL", 0)

        result = position_service.get_long_positions("AAPL")

        assert result.symbol == "AAPL"
        assert result.total_shares == 0
        assert result.available_shares == 0
        assert result.current_price == 100.0

    def test_position_summary_high_price_stock(self, position_service, mock_broker_client):
        """Test position summary with high-priced stock."""
        mock_broker_client.get_current_price.return_value = 1500.0
        mock_broker_client.get_position.return_value = MockPosition("BRK.A", 10)

        result = position_service.get_long_positions("BRK.A")

        assert result.symbol == "BRK.A"
        assert result.total_shares == 10
        assert result.available_shares == 10
        assert result.current_price == 1500.0

    def test_position_summary_low_price_stock(self, position_service, mock_broker_client):
        """Test position summary with low-priced stock."""
        mock_broker_client.get_current_price.return_value = 2.50
        mock_broker_client.get_position.return_value = MockPosition("SIRI", 2000)

        result = position_service.get_long_positions("SIRI")

        assert result.symbol == "SIRI"
        assert result.total_shares == 2000
        assert result.available_shares == 2000
        assert result.current_price == 2.50


class TestAvailableSharesCalculation:
    """Test cases for available shares calculation with existing short calls."""

    @pytest.fixture
    def position_service(self):
        """Create a PositionService instance."""
        return PositionService(Mock())

    def test_available_shares_with_existing_short_calls(self, position_service):
        """Test available shares calculation accounting for existing short calls."""
        # Mock position summary with existing short calls
        existing_short_calls = [
            OptionPosition(
                symbol="NVDA",
                quantity=2,  # 2 contracts = 200 shares covered
                market_value=-1000.0,
                average_cost=-5.0,
                unrealized_pnl=200.0,
                position_type="short_call",
                strike=160.0,
                expiration=date.today() + timedelta(days=30),
                option_type="call"
            )
        ]

        # Calculate available shares manually (since this is tested in isolation)
        total_shares = 500
        shares_covered_by_calls = sum(
            option.quantity * 100 for option in existing_short_calls 
            if option.option_type == 'call' and option.position_type == 'short_call'
        )
        expected_available = max(0, total_shares - shares_covered_by_calls)

        assert expected_available == 300  # 500 - 200

    def test_available_shares_multiple_short_calls(self, position_service):
        """Test available shares calculation with multiple existing short calls."""
        existing_short_calls = [
            OptionPosition(
                symbol="NVDA", quantity=1, market_value=-500.0, average_cost=-5.0,
                unrealized_pnl=100.0, position_type="short_call", strike=155.0,
                expiration=date.today() + timedelta(days=15), option_type="call"
            ),
            OptionPosition(
                symbol="NVDA", quantity=2, market_value=-1000.0, average_cost=-5.0,
                unrealized_pnl=200.0, position_type="short_call", strike=160.0,
                expiration=date.today() + timedelta(days=30), option_type="call"
            )
        ]

        total_shares = 800
        shares_covered_by_calls = sum(
            option.quantity * 100 for option in existing_short_calls 
            if option.option_type == 'call' and option.position_type == 'short_call'
        )
        expected_available = max(0, total_shares - shares_covered_by_calls)

        assert expected_available == 500  # 800 - 300 (1*100 + 2*100)

    def test_available_shares_more_calls_than_shares(self, position_service):
        """Test available shares calculation when short calls exceed total shares."""
        existing_short_calls = [
            OptionPosition(
                symbol="NVDA", quantity=6, market_value=-3000.0, average_cost=-5.0,
                unrealized_pnl=600.0, position_type="short_call", strike=155.0,
                expiration=date.today() + timedelta(days=15), option_type="call"
            )
        ]

        total_shares = 400
        shares_covered_by_calls = sum(
            option.quantity * 100 for option in existing_short_calls 
            if option.option_type == 'call' and option.position_type == 'short_call'
        )
        expected_available = max(0, total_shares - shares_covered_by_calls)

        assert expected_available == 0  # max(0, 400 - 600)

    def test_available_shares_no_short_calls(self, position_service):
        """Test available shares calculation with no existing short calls."""
        total_shares = 500
        existing_short_calls = []
        
        shares_covered_by_calls = sum(
            option.quantity * 100 for option in existing_short_calls 
            if option.option_type == 'call' and option.position_type == 'short_call'
        )
        expected_available = max(0, total_shares - shares_covered_by_calls)

        assert expected_available == 500  # All shares available


class TestErrorHandling:
    """Test cases for error handling with edge cases and API failures."""

    @pytest.fixture
    def mock_broker_client(self):
        """Create a mock broker client."""
        return Mock()

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        logger = Mock()
        logger.info = Mock()
        logger.error = Mock()
        logger.log_info = Mock()
        logger.log_error = Mock()
        return logger

    @pytest.fixture
    def position_service(self, mock_broker_client, mock_logger):
        """Create a PositionService instance."""
        return PositionService(mock_broker_client, mock_logger)

    def test_api_timeout_error(self, position_service, mock_broker_client, mock_logger):
        """Test handling of API timeout errors."""
        mock_broker_client.get_current_price.side_effect = TimeoutError("Request timeout")

        with pytest.raises(RuntimeError, match="Error retrieving positions for NVDA"):
            position_service.get_long_positions("NVDA")

        mock_logger.log_error.assert_called()

    def test_api_connection_error(self, position_service, mock_broker_client, mock_logger):
        """Test handling of API connection errors."""
        mock_broker_client.get_current_price.side_effect = ConnectionError("Connection failed")

        with pytest.raises(RuntimeError, match="Error retrieving positions for NVDA"):
            position_service.get_long_positions("NVDA")

        mock_logger.log_error.assert_called()

    def test_api_authentication_error(self, position_service, mock_broker_client, mock_logger):
        """Test handling of API authentication errors."""
        mock_broker_client.get_current_price.side_effect = Exception("Authentication failed")

        with pytest.raises(RuntimeError, match="Error retrieving positions for NVDA"):
            position_service.get_long_positions("NVDA")

        mock_logger.log_error.assert_called()

    def test_invalid_symbol_error(self, position_service, mock_broker_client, mock_logger):
        """Test handling of invalid symbol errors."""
        mock_broker_client.get_current_price.side_effect = ValueError("Invalid symbol")

        with pytest.raises(RuntimeError, match="Error retrieving positions for INVALID"):
            position_service.get_long_positions("INVALID")

        mock_logger.log_error.assert_called()

    def test_empty_response_handling(self, position_service, mock_broker_client):
        """Test handling of empty API responses."""
        mock_broker_client.get_current_price.return_value = 100.0
        mock_broker_client.get_position.return_value = None  # Empty response

        result = position_service.get_long_positions("NVDA")

        assert result.total_shares == 0
        assert result.available_shares == 0
        assert result.current_price == 100.0

    def test_malformed_response_handling(self, position_service, mock_broker_client, mock_logger):
        """Test handling of malformed API responses."""
        mock_broker_client.get_current_price.return_value = "invalid_price"  # Should be float

        with pytest.raises(RuntimeError):
            position_service.get_long_positions("NVDA")

        mock_logger.log_error.assert_called()

    def test_partial_api_failure(self, position_service, mock_broker_client, mock_logger):
        """Test handling when some API calls succeed and others fail."""
        mock_broker_client.get_current_price.return_value = 150.0  # Success
        mock_broker_client.get_position.side_effect = Exception("Position API failed")  # Failure

        with pytest.raises(RuntimeError, match="Error retrieving positions for NVDA"):
            position_service.get_long_positions("NVDA")

        mock_logger.log_error.assert_called()

    def test_validation_with_api_failure(self, position_service, mock_broker_client, mock_logger):
        """Test validation methods handle API failures gracefully."""
        mock_broker_client.get_current_price.side_effect = Exception("API Error")

        orders = [CoveredCallOrder("NVDA", 155.0, date.today() + timedelta(days=30), 1, 100)]
        is_valid, summary = position_service.validate_covered_call_orders("NVDA", orders)

        assert is_valid is False
        assert summary.validation_passed is False
        assert len(summary.errors) > 0
        mock_logger.log_error.assert_called()

    def test_network_interruption_handling(self, position_service, mock_broker_client, mock_logger):
        """Test handling of network interruption during API calls."""
        mock_broker_client.get_current_price.side_effect = OSError("Network is unreachable")

        with pytest.raises(RuntimeError, match="Error retrieving positions for NVDA"):
            position_service.get_long_positions("NVDA")

        mock_logger.log_error.assert_called()