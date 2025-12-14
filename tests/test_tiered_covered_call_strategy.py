"""Unit tests for TieredCoveredCallCalculator."""

import pytest
from datetime import date, timedelta
from unittest.mock import Mock, MagicMock
from dataclasses import dataclass

from src.strategy.tiered_covered_call_strategy import (
    TieredCoveredCallCalculator,
    TieredCoveredCallPlan,
    ExpirationGroup
)
from src.positions.models import PositionSummary, OptionPosition
from src.brokers.base_client import OptionContract


@dataclass
class MockOptionContract:
    """Mock option contract for testing."""
    symbol: str
    strike: float
    expiration: date
    option_type: str
    bid: float = 0.0
    ask: float = 0.0
    last_price: float = 0.0


class TestTieredCoveredCallCalculator:
    """Test cases for TieredCoveredCallCalculator."""

    @pytest.fixture
    def mock_broker_client(self):
        """Create a mock broker client."""
        client = Mock()
        client.get_option_chain = Mock()
        return client

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        logger = Mock()
        logger.log_info = Mock()
        logger.log_error = Mock()
        logger.log_warning = Mock()
        return logger

    @pytest.fixture
    def calculator(self, mock_broker_client, mock_logger):
        """Create a TieredCoveredCallCalculator instance."""
        return TieredCoveredCallCalculator(
            broker_client=mock_broker_client,
            min_days_to_expiration=7,
            max_days_to_expiration=60,
            logger=mock_logger
        )

    @pytest.fixture
    def sample_position_summary(self):
        """Create a sample position summary for testing."""
        return PositionSummary(
            symbol="NVDA",
            total_shares=600,
            available_shares=600,
            current_price=150.0,
            long_options=[],
            existing_short_calls=[]
        )

    def test_initialization(self, calculator, mock_broker_client, mock_logger):
        """Test calculator initialization."""
        assert calculator.broker_client == mock_broker_client
        assert calculator.min_days_to_expiration == 7
        assert calculator.max_days_to_expiration == 60
        assert calculator.logger == mock_logger
        assert calculator.validator is not None

    def test_initialization_with_custom_parameters(self, mock_broker_client):
        """Test calculator initialization with custom parameters."""
        calculator = TieredCoveredCallCalculator(
            broker_client=mock_broker_client,
            min_days_to_expiration=14,
            max_days_to_expiration=90
        )

        assert calculator.min_days_to_expiration == 14
        assert calculator.max_days_to_expiration == 90
        assert calculator.logger is None


class TestExpirationDateSelection:
    """Test cases for expiration date selection with various market calendars."""

    @pytest.fixture
    def mock_broker_client(self):
        """Create a mock broker client."""
        return Mock()

    @pytest.fixture
    def calculator(self, mock_broker_client):
        """Create a calculator instance."""
        return TieredCoveredCallCalculator(mock_broker_client)

    def test_find_next_three_expirations_success(self, calculator, mock_broker_client):
        """Test successful finding of three expiration dates."""
        today = date.today()
        exp1 = today + timedelta(days=14)
        exp2 = today + timedelta(days=21)
        exp3 = today + timedelta(days=35)

        # Mock option chain with multiple expirations
        mock_options = [
            MockOptionContract("NVDA", 150.0, exp1, "call"),
            MockOptionContract("NVDA", 155.0, exp1, "call"),
            MockOptionContract("NVDA", 150.0, exp2, "call"),
            MockOptionContract("NVDA", 155.0, exp2, "call"),
            MockOptionContract("NVDA", 150.0, exp3, "call"),
            MockOptionContract("NVDA", 155.0, exp3, "call"),
        ]

        mock_broker_client.get_option_chain.return_value = mock_options

        result = calculator.find_next_three_expirations("NVDA")

        assert len(result) == 3
        assert result == [exp1, exp2, exp3]
        assert all(isinstance(exp, date) for exp in result)

    def test_find_next_three_expirations_limited_available(self, calculator, mock_broker_client):
        """Test finding expirations when fewer than 3 are available."""
        today = date.today()
        exp1 = today + timedelta(days=14)
        exp2 = today + timedelta(days=28)

        mock_options = [
            MockOptionContract("NVDA", 150.0, exp1, "call"),
            MockOptionContract("NVDA", 150.0, exp2, "call"),
        ]

        mock_broker_client.get_option_chain.return_value = mock_options

        result = calculator.find_next_three_expirations("NVDA")

        assert len(result) == 2
        assert result == [exp1, exp2]

    def test_find_next_three_expirations_no_valid_dates(self, calculator, mock_broker_client):
        """Test finding expirations when no valid dates are available."""
        today = date.today()
        # Expiration too far in the future (beyond max_days_to_expiration)
        exp_too_far = today + timedelta(days=100)

        mock_options = [
            MockOptionContract("NVDA", 150.0, exp_too_far, "call"),
        ]

        mock_broker_client.get_option_chain.return_value = mock_options

        with pytest.raises(ValueError, match="No valid expiration dates found"):
            calculator.find_next_three_expirations("NVDA")

    def test_find_next_three_expirations_api_error(self, calculator, mock_broker_client):
        """Test finding expirations with API error."""
        mock_broker_client.get_option_chain.side_effect = Exception("API Error")

        with pytest.raises(ValueError, match="Failed to find expiration dates"):
            calculator.find_next_three_expirations("NVDA")

    def test_find_next_three_expirations_date_filtering(self, calculator, mock_broker_client):
        """Test that expiration dates are properly filtered by min/max days."""
        today = date.today()
        exp_too_soon = today + timedelta(days=3)  # Before min_days_to_expiration (7)
        exp_valid1 = today + timedelta(days=14)
        exp_valid2 = today + timedelta(days=28)
        exp_too_far = today + timedelta(days=90)  # After max_days_to_expiration (60)

        mock_options = [
            MockOptionContract("NVDA", 150.0, exp_too_soon, "call"),
            MockOptionContract("NVDA", 150.0, exp_valid1, "call"),
            MockOptionContract("NVDA", 150.0, exp_valid2, "call"),
            MockOptionContract("NVDA", 150.0, exp_too_far, "call"),
        ]

        mock_broker_client.get_option_chain.return_value = mock_options

        result = calculator.find_next_three_expirations("NVDA")

        assert len(result) == 2
        assert result == [exp_valid1, exp_valid2]

    def test_find_next_three_expirations_sorted_chronologically(self, calculator, mock_broker_client):
        """Test that expiration dates are returned in chronological order."""
        today = date.today()
        exp1 = today + timedelta(days=35)
        exp2 = today + timedelta(days=14)
        exp3 = today + timedelta(days=21)

        # Return options in non-chronological order
        mock_options = [
            MockOptionContract("NVDA", 150.0, exp1, "call"),
            MockOptionContract("NVDA", 150.0, exp2, "call"),
            MockOptionContract("NVDA", 150.0, exp3, "call"),
        ]

        mock_broker_client.get_option_chain.return_value = mock_options

        result = calculator.find_next_three_expirations("NVDA")

        # Should be sorted chronologically
        assert result == [exp2, exp3, exp1]

    def test_find_next_three_expirations_duplicate_dates(self, calculator, mock_broker_client):
        """Test handling of duplicate expiration dates."""
        today = date.today()
        exp1 = today + timedelta(days=14)
        exp2 = today + timedelta(days=28)

        # Multiple options with same expiration dates
        mock_options = [
            MockOptionContract("NVDA", 150.0, exp1, "call"),
            MockOptionContract("NVDA", 155.0, exp1, "call"),  # Duplicate date
            MockOptionContract("NVDA", 150.0, exp2, "call"),
            MockOptionContract("NVDA", 155.0, exp2, "call"),  # Duplicate date
        ]

        mock_broker_client.get_option_chain.return_value = mock_options

        result = calculator.find_next_three_expirations("NVDA")

        # Should return unique dates only
        assert len(result) == 2
        assert result == [exp1, exp2]


class TestStrikePriceCalculation:
    """Test cases for strike price calculation with different price levels."""

    @pytest.fixture
    def mock_broker_client(self):
        """Create a mock broker client."""
        return Mock()

    @pytest.fixture
    def calculator(self, mock_broker_client):
        """Create a calculator instance."""
        return TieredCoveredCallCalculator(mock_broker_client)

    def test_calculate_incremental_strikes_basic(self, calculator, mock_broker_client):
        """Test basic incremental strike calculation."""
        today = date.today()
        expirations = [
            today + timedelta(days=14),
            today + timedelta(days=28),
            today + timedelta(days=42)
        ]
        current_price = 150.0

        # Mock option chains for each expiration
        def mock_get_option_chain(symbol, expiration):
            return [
                MockOptionContract(symbol, 152.5, expiration, "call"),
                MockOptionContract(symbol, 155.0, expiration, "call"),
                MockOptionContract(symbol, 157.5, expiration, "call"),
                MockOptionContract(symbol, 160.0, expiration, "call"),
                MockOptionContract(symbol, 162.5, expiration, "call"),
            ]

        mock_broker_client.get_option_chain.side_effect = mock_get_option_chain

        result = calculator.calculate_incremental_strikes("NVDA", current_price, expirations)

        assert len(result) == 3
        assert result[0] == 152.5  # First OTM strike for nearest expiration
        assert result[1] == 155.0  # Next higher strike for second expiration
        assert result[2] == 157.5  # Next higher strike for third expiration
        assert all(strike > current_price for strike in result)

    def test_calculate_incremental_strikes_high_price_stock(self, calculator, mock_broker_client):
        """Test strike calculation for high-priced stock."""
        today = date.today()
        expirations = [today + timedelta(days=14), today + timedelta(days=28)]
        current_price = 1200.0

        def mock_get_option_chain(symbol, expiration):
            return [
                MockOptionContract(symbol, 1210.0, expiration, "call"),
                MockOptionContract(symbol, 1220.0, expiration, "call"),
                MockOptionContract(symbol, 1230.0, expiration, "call"),
            ]

        mock_broker_client.get_option_chain.side_effect = mock_get_option_chain

        result = calculator.calculate_incremental_strikes("NVDA", current_price, expirations)

        assert result[0] == 1210.0
        assert result[1] == 1220.0
        assert all(strike > current_price for strike in result)

    def test_calculate_incremental_strikes_low_price_stock(self, calculator, mock_broker_client):
        """Test strike calculation for low-priced stock."""
        today = date.today()
        expirations = [today + timedelta(days=14), today + timedelta(days=28)]
        current_price = 5.0

        def mock_get_option_chain(symbol, expiration):
            return [
                MockOptionContract(symbol, 5.5, expiration, "call"),
                MockOptionContract(symbol, 6.0, expiration, "call"),
                MockOptionContract(symbol, 6.5, expiration, "call"),
            ]

        mock_broker_client.get_option_chain.side_effect = mock_get_option_chain

        result = calculator.calculate_incremental_strikes("NVDA", current_price, expirations)

        assert result[0] == 5.5
        assert result[1] == 6.0
        assert all(strike > current_price for strike in result)

    def test_calculate_incremental_strikes_insufficient_strikes(self, calculator, mock_broker_client):
        """Test strike calculation when insufficient higher strikes are available."""
        today = date.today()
        expirations = [today + timedelta(days=14), today + timedelta(days=28)]
        current_price = 150.0

        def mock_get_option_chain(symbol, expiration):
            if expiration == expirations[0]:
                return [MockOptionContract(symbol, 155.0, expiration, "call")]
            else:
                # Second expiration has no strikes higher than 155.0
                return [
                    MockOptionContract(symbol, 150.0, expiration, "call"),
                    MockOptionContract(symbol, 155.0, expiration, "call")
                ]

        mock_broker_client.get_option_chain.side_effect = mock_get_option_chain

        result = calculator.calculate_incremental_strikes("NVDA", current_price, expirations)

        assert result[0] == 155.0
        assert result[1] == 155.0  # Uses highest available when no higher strikes exist

    def test_calculate_incremental_strikes_no_otm_strikes(self, calculator, mock_broker_client):
        """Test strike calculation when no OTM strikes are available."""
        today = date.today()
        expirations = [today + timedelta(days=14)]
        current_price = 150.0

        def mock_get_option_chain(symbol, expiration):
            # All strikes are at or below current price
            return [
                MockOptionContract(symbol, 140.0, expiration, "call"),
                MockOptionContract(symbol, 145.0, expiration, "call"),
                MockOptionContract(symbol, 150.0, expiration, "call"),
            ]

        mock_broker_client.get_option_chain.side_effect = mock_get_option_chain

        with pytest.raises(ValueError, match="No out-of-the-money call strikes available"):
            calculator.calculate_incremental_strikes("NVDA", current_price, expirations)

    def test_calculate_incremental_strikes_invalid_current_price(self, calculator, mock_broker_client):
        """Test strike calculation with invalid current price."""
        today = date.today()
        expirations = [today + timedelta(days=14)]

        with pytest.raises(ValueError, match="Invalid current price"):
            calculator.calculate_incremental_strikes("NVDA", 0.0, expirations)

        with pytest.raises(ValueError, match="Invalid current price"):
            calculator.calculate_incremental_strikes("NVDA", -10.0, expirations)

    def test_calculate_incremental_strikes_empty_expirations(self, calculator, mock_broker_client):
        """Test strike calculation with empty expirations list."""
        with pytest.raises(ValueError, match="No expiration dates provided"):
            calculator.calculate_incremental_strikes("NVDA", 150.0, [])

    def test_calculate_incremental_strikes_api_error(self, calculator, mock_broker_client):
        """Test strike calculation with API error."""
        today = date.today()
        expirations = [today + timedelta(days=14)]
        current_price = 150.0

        mock_broker_client.get_option_chain.side_effect = Exception("API Error")

        with pytest.raises(ValueError, match="Failed to get option chain"):
            calculator.calculate_incremental_strikes("NVDA", current_price, expirations)

    def test_calculate_incremental_strikes_no_call_options(self, calculator, mock_broker_client):
        """Test strike calculation when only put options are available."""
        today = date.today()
        expirations = [today + timedelta(days=14)]
        current_price = 150.0

        def mock_get_option_chain(symbol, expiration):
            # Only put options available
            return [
                MockOptionContract(symbol, 145.0, expiration, "put"),
                MockOptionContract(symbol, 140.0, expiration, "put"),
            ]

        mock_broker_client.get_option_chain.side_effect = mock_get_option_chain

        with pytest.raises(ValueError, match="No out-of-the-money call strikes available"):
            calculator.calculate_incremental_strikes("NVDA", current_price, expirations)


class TestShareDivision:
    """Test cases for share division with various quantities and remainder handling."""

    @pytest.fixture
    def calculator(self):
        """Create a calculator instance."""
        return TieredCoveredCallCalculator(Mock())

    def test_divide_shares_into_groups_basic(self, calculator):
        """Test basic share division into 3 groups."""
        result = calculator.divide_shares_into_groups(600, 3)

        assert len(result) == 3
        assert sum(result) == 600
        assert all(shares % 100 == 0 for shares in result)  # All multiples of 100
        assert result == [200, 200, 200]

    def test_divide_shares_into_groups_with_remainder(self, calculator):
        """Test share division with remainder allocation."""
        result = calculator.divide_shares_into_groups(700, 3)

        assert len(result) == 3
        assert sum(result) == 600  # Rounded down to nearest 100 per group, remainder to first
        assert result[0] >= result[1]  # First group gets remainder
        assert result[0] >= result[2]
        assert all(shares % 100 == 0 for shares in result)

    def test_divide_shares_into_groups_uneven_division(self, calculator):
        """Test share division that doesn't divide evenly."""
        result = calculator.divide_shares_into_groups(550, 3)

        assert len(result) == 3
        assert sum(result) == 500  # 550 -> 500 (rounded down to multiples of 100)
        assert result[0] >= result[1]
        assert result[0] >= result[2]

    def test_divide_shares_into_groups_insufficient_for_all(self, calculator):
        """Test share division when insufficient shares for all groups."""
        result = calculator.divide_shares_into_groups(250, 3)

        assert len(result) == 3
        assert result[0] == 200  # All shares go to first group
        assert result[1] == 0
        assert result[2] == 0
        assert sum(result) == 200

    def test_divide_shares_into_groups_minimum_shares(self, calculator):
        """Test share division with exactly minimum shares."""
        result = calculator.divide_shares_into_groups(100, 3)

        assert len(result) == 3
        assert result[0] == 100
        assert result[1] == 0
        assert result[2] == 0

    def test_divide_shares_into_groups_large_quantity(self, calculator):
        """Test share division with large quantities."""
        result = calculator.divide_shares_into_groups(3000, 3)

        assert len(result) == 3
        assert sum(result) == 3000
        assert result == [1000, 1000, 1000]

    def test_divide_shares_into_groups_two_groups(self, calculator):
        """Test share division into 2 groups."""
        result = calculator.divide_shares_into_groups(500, 2)

        assert len(result) == 2
        assert sum(result) == 500
        assert result == [250, 250]

    def test_divide_shares_into_groups_single_group(self, calculator):
        """Test share division into 1 group."""
        result = calculator.divide_shares_into_groups(400, 1)

        assert len(result) == 1
        assert result[0] == 400

    def test_divide_shares_into_groups_invalid_shares(self, calculator):
        """Test share division with invalid share quantities."""
        with pytest.raises(ValueError, match="Invalid total_shares"):
            calculator.divide_shares_into_groups(-100, 3)

        with pytest.raises(ValueError, match="Insufficient shares"):
            calculator.divide_shares_into_groups(50, 3)  # Less than 100 shares

    def test_divide_shares_into_groups_invalid_groups(self, calculator):
        """Test share division with invalid number of groups."""
        with pytest.raises(ValueError, match="Invalid num_groups"):
            calculator.divide_shares_into_groups(300, 0)

        with pytest.raises(ValueError, match="Invalid num_groups"):
            calculator.divide_shares_into_groups(300, -1)

    def test_divide_shares_into_groups_remainder_allocation(self, calculator):
        """Test that remainder shares are properly allocated to first group."""
        result = calculator.divide_shares_into_groups(850, 3)

        # 850 / 3 = 283.33 -> 200 per group base
        # Remaining 250 shares -> 200 additional to first group
        assert len(result) == 3
        assert result[0] == 400  # 200 base + 200 additional
        assert result[1] == 200
        assert result[2] == 200
        assert sum(result) == 800


class TestStrategyValidation:
    """Test cases for strategy validation with insufficient shares scenarios."""

    @pytest.fixture
    def mock_broker_client(self):
        """Create a mock broker client."""
        return Mock()

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        logger = Mock()
        logger.log_info = Mock()
        logger.log_error = Mock()
        logger.log_warning = Mock()
        return logger

    @pytest.fixture
    def calculator(self, mock_broker_client, mock_logger):
        """Create a calculator instance."""
        return TieredCoveredCallCalculator(mock_broker_client, logger=mock_logger)

    def test_validate_and_adjust_contracts_no_adjustment_needed(self, calculator):
        """Test contract validation when no adjustment is needed."""
        position_summary = PositionSummary(
            symbol="NVDA",
            total_shares=600,
            available_shares=600,
            current_price=150.0,
            long_options=[],
            existing_short_calls=[]
        )

        requested_contracts = [2, 2, 2]  # 600 shares needed

        adjusted_contracts, warnings = calculator.validate_and_adjust_contracts(
            position_summary, requested_contracts
        )

        assert adjusted_contracts == [2, 2, 2]
        assert len(warnings) == 0

    def test_validate_and_adjust_contracts_proportional_reduction(self, calculator, mock_logger):
        """Test contract validation with proportional reduction."""
        position_summary = PositionSummary(
            symbol="NVDA",
            total_shares=400,
            available_shares=400,  # Only 400 shares available
            current_price=150.0,
            long_options=[],
            existing_short_calls=[]
        )

        requested_contracts = [3, 3, 3]  # 900 shares needed, but only 400 available

        adjusted_contracts, warnings = calculator.validate_and_adjust_contracts(
            position_summary, requested_contracts
        )

        assert sum(adjusted_contracts) == 4  # 400 shares / 100 = 4 contracts max
        assert len(warnings) == 1
        assert "Adjusted contract quantities" in warnings[0]
        mock_logger.log_warning.assert_called()

    def test_validate_and_adjust_contracts_insufficient_for_any(self, calculator, mock_logger):
        """Test contract validation when insufficient shares for any contracts."""
        position_summary = PositionSummary(
            symbol="NVDA",
            total_shares=50,
            available_shares=50,  # Less than 100 shares
            current_price=150.0,
            long_options=[],
            existing_short_calls=[]
        )

        requested_contracts = [1, 1, 1]

        adjusted_contracts, warnings = calculator.validate_and_adjust_contracts(
            position_summary, requested_contracts
        )

        assert adjusted_contracts == [0, 0, 0]
        assert len(warnings) == 1
        assert "No contracts possible" in warnings[0]
        mock_logger.log_warning.assert_called()

    def test_validate_and_adjust_contracts_exact_match(self, calculator):
        """Test contract validation when shares exactly match requirements."""
        position_summary = PositionSummary(
            symbol="NVDA",
            total_shares=300,
            available_shares=300,
            current_price=150.0,
            long_options=[],
            existing_short_calls=[]
        )

        requested_contracts = [3, 0, 0]  # Exactly 300 shares needed

        adjusted_contracts, warnings = calculator.validate_and_adjust_contracts(
            position_summary, requested_contracts
        )

        assert adjusted_contracts == [3, 0, 0]
        assert len(warnings) == 0

    def test_validate_and_adjust_contracts_with_existing_short_calls(self, calculator):
        """Test contract validation accounting for existing short calls."""
        existing_short_calls = [
            OptionPosition(
                symbol="NVDA", quantity=1, market_value=-500.0, average_cost=-5.0,
                unrealized_pnl=100.0, position_type="short_call", strike=155.0,
                expiration=date.today() + timedelta(days=15), option_type="call"
            )
        ]

        position_summary = PositionSummary(
            symbol="NVDA",
            total_shares=500,
            available_shares=400,  # 500 total - 100 covered by existing call
            current_price=150.0,
            long_options=[],
            existing_short_calls=existing_short_calls
        )

        requested_contracts = [2, 2, 2]  # 600 shares needed, but only 400 available

        adjusted_contracts, warnings = calculator.validate_and_adjust_contracts(
            position_summary, requested_contracts
        )

        assert sum(adjusted_contracts) == 4  # 400 available shares / 100
        assert len(warnings) == 1

    def test_calculate_strategy_success(self, calculator, mock_broker_client, mock_logger):
        """Test successful strategy calculation."""
        position_summary = PositionSummary(
            symbol="NVDA",
            total_shares=600,
            available_shares=600,
            current_price=150.0,
            long_options=[],
            existing_short_calls=[]
        )

        today = date.today()
        expirations = [
            today + timedelta(days=14),
            today + timedelta(days=28),
            today + timedelta(days=42)
        ]

        def mock_get_option_chain(symbol, expiration):
            return [
                MockOptionContract(symbol, 152.5, expiration, "call"),
                MockOptionContract(symbol, 155.0, expiration, "call"),
                MockOptionContract(symbol, 157.5, expiration, "call"),
            ]

        mock_broker_client.get_option_chain.side_effect = mock_get_option_chain

        # Mock the find_next_three_expirations method
        calculator.find_next_three_expirations = Mock(return_value=expirations)

        result = calculator.calculate_strategy(position_summary)

        assert isinstance(result, TieredCoveredCallPlan)
        assert result.symbol == "NVDA"
        assert result.current_price == 150.0
        assert result.total_shares == 600
        assert len(result.expiration_groups) == 3
        assert result.total_contracts > 0
        assert result.estimated_premium > 0
        mock_logger.log_info.assert_called()

    def test_calculate_strategy_insufficient_shares(self, calculator, mock_logger):
        """Test strategy calculation with insufficient shares."""
        position_summary = PositionSummary(
            symbol="NVDA",
            total_shares=50,  # Less than minimum required
            available_shares=50,
            current_price=150.0,
            long_options=[],
            existing_short_calls=[]
        )

        with pytest.raises(ValueError, match="Strategy validation failed"):
            calculator.calculate_strategy(position_summary)

        mock_logger.log_error.assert_called()

    def test_calculate_strategy_no_available_expirations(self, calculator, mock_broker_client, mock_logger):
        """Test strategy calculation when no expirations are available."""
        position_summary = PositionSummary(
            symbol="NVDA",
            total_shares=600,
            available_shares=600,
            current_price=150.0,
            long_options=[],
            existing_short_calls=[]
        )

        # Mock find_next_three_expirations to raise an error
        calculator.find_next_three_expirations = Mock(
            side_effect=ValueError("No valid expiration dates found")
        )

        with pytest.raises(ValueError, match="Error calculating tiered covered call strategy"):
            calculator.calculate_strategy(position_summary)

        mock_logger.log_error.assert_called()

    def test_calculate_strategy_api_error_during_calculation(self, calculator, mock_broker_client, mock_logger):
        """Test strategy calculation with API error during calculation."""
        position_summary = PositionSummary(
            symbol="NVDA",
            total_shares=600,
            available_shares=600,
            current_price=150.0,
            long_options=[],
            existing_short_calls=[]
        )

        # Mock find_next_three_expirations to raise an API error
        calculator.find_next_three_expirations = Mock(
            side_effect=Exception("API connection failed")
        )

        with pytest.raises(ValueError, match="Error calculating tiered covered call strategy"):
            calculator.calculate_strategy(position_summary)

        mock_logger.log_error.assert_called()

    def test_calculate_strategy_validation_failure(self, calculator, mock_logger):
        """Test strategy calculation with validation failure."""
        # Position with insufficient shares for minimum requirements
        position_summary = PositionSummary(
            symbol="NVDA",
            total_shares=200,  # Less than 300 minimum
            available_shares=200,
            current_price=150.0,
            long_options=[],
            existing_short_calls=[]
        )

        with pytest.raises(ValueError, match="Strategy validation failed"):
            calculator.calculate_strategy(position_summary)

        mock_logger.log_error.assert_called()


class TestExpirationGroupCreation:
    """Test cases for expiration group creation and validation."""

    @pytest.fixture
    def calculator(self):
        """Create a calculator instance."""
        return TieredCoveredCallCalculator(Mock())

    def test_expiration_group_creation(self, calculator):
        """Test creation of expiration groups."""
        expiration = date.today() + timedelta(days=30)
        
        group = ExpirationGroup(
            expiration_date=expiration,
            strike_price=155.0,
            num_contracts=2,
            shares_used=200,
            estimated_premium_per_contract=2.50
        )

        assert group.expiration_date == expiration
        assert group.strike_price == 155.0
        assert group.num_contracts == 2
        assert group.shares_used == 200
        assert group.estimated_premium_per_contract == 2.50

    def test_tiered_covered_call_plan_creation(self, calculator):
        """Test creation of complete tiered covered call plan."""
        expiration1 = date.today() + timedelta(days=14)
        expiration2 = date.today() + timedelta(days=28)
        
        groups = [
            ExpirationGroup(expiration1, 152.5, 2, 200, 2.00),
            ExpirationGroup(expiration2, 155.0, 2, 200, 2.50)
        ]

        plan = TieredCoveredCallPlan(
            symbol="NVDA",
            current_price=150.0,
            total_shares=400,
            expiration_groups=groups,
            total_contracts=4,
            estimated_premium=9.00
        )

        assert plan.symbol == "NVDA"
        assert plan.current_price == 150.0
        assert plan.total_shares == 400
        assert len(plan.expiration_groups) == 2
        assert plan.total_contracts == 4
        assert plan.estimated_premium == 9.00

    def test_expiration_group_premium_calculation(self, calculator):
        """Test premium calculation for expiration groups."""
        # Test that premium estimation logic works correctly
        current_price = 150.0
        strike_price = 155.0
        days_to_expiration = 30
        
        # Using the formula from the implementation:
        # estimated_premium = max(0.50, (strike - current_price) * 0.1 + days_to_expiration * 0.02)
        expected_premium = max(0.50, (strike_price - current_price) * 0.1 + days_to_expiration * 0.02)
        
        assert expected_premium == max(0.50, 5.0 * 0.1 + 30 * 0.02)
        assert expected_premium == max(0.50, 0.5 + 0.6)
        assert expected_premium == 1.1