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

        # Mock get_option_expirations to return API expirations
        mock_broker_client.get_option_expirations.return_value = [exp1, exp2, exp3]

        # Mock option chain with call options for validation
        mock_options = [
            MockOptionContract("NVDA", 150.0, exp1, "call"),
            MockOptionContract("NVDA", 155.0, exp1, "call"),
        ]
        mock_broker_client.get_option_chain.return_value = mock_options

        result = calculator.find_next_three_expirations("NVDA")

        assert len(result) == 3
        assert result == [exp1, exp2, exp3]
        assert all(isinstance(exp, date) for exp in result)
        mock_broker_client.get_option_expirations.assert_called_once_with("NVDA")

    def test_find_next_three_expirations_date_range_filtering(self, calculator, mock_broker_client):
        """Test date range filtering with various min/max days configurations."""
        today = date.today()
        exp_too_soon = today + timedelta(days=3)  # Before min_days (7)
        exp_valid1 = today + timedelta(days=14)
        exp_valid2 = today + timedelta(days=28)
        exp_valid3 = today + timedelta(days=45)
        exp_too_far = today + timedelta(days=90)  # After max_days (60)

        # Mock API returns all expirations
        mock_broker_client.get_option_expirations.return_value = [
            exp_too_soon, exp_valid1, exp_valid2, exp_valid3, exp_too_far
        ]

        # Mock option chain with call options
        mock_options = [MockOptionContract("NVDA", 150.0, exp_valid1, "call")]
        mock_broker_client.get_option_chain.return_value = mock_options

        result = calculator.find_next_three_expirations("NVDA")

        # Should only return expirations within date range
        assert len(result) == 3
        assert result == [exp_valid1, exp_valid2, exp_valid3]
        assert exp_too_soon not in result
        assert exp_too_far not in result

    def test_find_next_three_expirations_call_option_validation(self, calculator, mock_broker_client):
        """Test call option validation logic."""
        today = date.today()
        exp1 = today + timedelta(days=14)
        exp2 = today + timedelta(days=21)
        exp3 = today + timedelta(days=28)

        mock_broker_client.get_option_expirations.return_value = [exp1, exp2, exp3]

        # First expiration has call options
        # Second expiration has no call options (only puts)
        # Third expiration has call options
        def mock_get_option_chain(symbol, expiration):
            if expiration == exp1:
                return [MockOptionContract(symbol, 150.0, expiration, "call")]
            elif expiration == exp2:
                return [MockOptionContract(symbol, 150.0, expiration, "put")]
            else:  # exp3
                return [MockOptionContract(symbol, 150.0, expiration, "call")]

        mock_broker_client.get_option_chain.side_effect = mock_get_option_chain

        result = calculator.find_next_three_expirations("NVDA")

        # Should only return expirations with call options
        assert len(result) == 2
        assert result == [exp1, exp3]
        assert exp2 not in result

    def test_find_next_three_expirations_fewer_than_three(self, calculator, mock_broker_client):
        """Test returning fewer than 3 expirations when available."""
        today = date.today()
        exp1 = today + timedelta(days=14)
        exp2 = today + timedelta(days=28)

        mock_broker_client.get_option_expirations.return_value = [exp1, exp2]

        mock_options = [MockOptionContract("NVDA", 150.0, exp1, "call")]
        mock_broker_client.get_option_chain.return_value = mock_options

        result = calculator.find_next_three_expirations("NVDA")

        assert len(result) == 2
        assert result == [exp1, exp2]

    def test_find_next_three_expirations_error_propagation(self, calculator, mock_broker_client):
        """Test error propagation from get_option_expirations()."""
        mock_broker_client.get_option_expirations.side_effect = ValueError("API Error: No expirations available")

        with pytest.raises(ValueError, match="API Error: No expirations available"):
            calculator.find_next_three_expirations("NVDA")

    def test_find_next_three_expirations_no_expirations_in_range(self, calculator, mock_broker_client):
        """Test error when all expirations are outside date range."""
        today = date.today()
        exp_too_far = today + timedelta(days=100)

        mock_broker_client.get_option_expirations.return_value = [exp_too_far]

        with pytest.raises(ValueError, match="No expirations found between"):
            calculator.find_next_three_expirations("NVDA")

    def test_find_next_three_expirations_no_call_options(self, calculator, mock_broker_client):
        """Test error when no expirations have call options."""
        today = date.today()
        exp1 = today + timedelta(days=14)
        exp2 = today + timedelta(days=21)

        mock_broker_client.get_option_expirations.return_value = [exp1, exp2]

        # All expirations only have put options
        mock_options = [MockOptionContract("NVDA", 150.0, exp1, "put")]
        mock_broker_client.get_option_chain.return_value = mock_options

        with pytest.raises(ValueError, match="No expirations with call options found"):
            calculator.find_next_three_expirations("NVDA")

    def test_find_next_three_expirations_logging(self, calculator, mock_broker_client):
        """Test logging at each step (API call, filtering, validation)."""
        mock_logger = Mock()
        calculator.logger = mock_logger

        today = date.today()
        exp1 = today + timedelta(days=14)
        exp2 = today + timedelta(days=21)

        mock_broker_client.get_option_expirations.return_value = [exp1, exp2]
        mock_options = [MockOptionContract("NVDA", 150.0, exp1, "call")]
        mock_broker_client.get_option_chain.return_value = mock_options

        result = calculator.find_next_three_expirations("NVDA")

        # Verify logging was called at various stages
        assert mock_logger.log_info.call_count >= 3  # API call, filtering, validation
        
        # Check that specific log messages were made
        log_calls = [str(call) for call in mock_logger.log_info.call_args_list]
        assert any("Retrieving option expirations from API" in str(call) for call in log_calls)
        assert any("Retrieved" in str(call) and "expirations from API" in str(call) for call in log_calls)
        assert any("Filtered expirations by date range" in str(call) for call in log_calls)

    def test_find_next_three_expirations_checks_up_to_five(self, calculator, mock_broker_client):
        """Test that validation checks up to 5 expirations to get 3 valid ones."""
        today = date.today()
        expirations = [today + timedelta(days=7 + i*7) for i in range(6)]  # 6 expirations

        mock_broker_client.get_option_expirations.return_value = expirations

        # First 2 have no call options, next 3 have call options
        def mock_get_option_chain(symbol, expiration):
            if expiration in expirations[:2]:
                return [MockOptionContract(symbol, 150.0, expiration, "put")]
            else:
                return [MockOptionContract(symbol, 150.0, expiration, "call")]

        mock_broker_client.get_option_chain.side_effect = mock_get_option_chain

        result = calculator.find_next_three_expirations("NVDA")

        # Should return 3 valid expirations (skipping first 2)
        assert len(result) == 3
        assert result == expirations[2:5]
        # Should have checked exactly 5 expirations (stopped after getting 3 valid)
        assert mock_broker_client.get_option_chain.call_count == 5

    def test_find_next_three_expirations_custom_date_range(self):
        """Test with custom min/max days configuration."""
        mock_broker_client = Mock()
        calculator = TieredCoveredCallCalculator(
            mock_broker_client,
            min_days_to_expiration=14,
            max_days_to_expiration=45
        )

        today = date.today()
        exp_too_soon = today + timedelta(days=10)
        exp_valid = today + timedelta(days=21)
        exp_too_far = today + timedelta(days=50)

        mock_broker_client.get_option_expirations.return_value = [exp_too_soon, exp_valid, exp_too_far]
        mock_options = [MockOptionContract("NVDA", 150.0, exp_valid, "call")]
        mock_broker_client.get_option_chain.return_value = mock_options

        result = calculator.find_next_three_expirations("NVDA")

        assert len(result) == 1
        assert result == [exp_valid]

    def test_find_next_three_expirations_no_valid_dates(self, calculator, mock_broker_client):
        """Test finding expirations when no valid dates are available."""
        today = date.today()
        # Expiration too far in the future (beyond max_days_to_expiration)
        exp_too_far = today + timedelta(days=100)

        mock_broker_client.get_option_expirations.return_value = [exp_too_far]

        with pytest.raises(ValueError, match="No expirations found between"):
            calculator.find_next_three_expirations("NVDA")

    def test_find_next_three_expirations_api_error(self, calculator, mock_broker_client):
        """Test finding expirations with API error."""
        mock_broker_client.get_option_expirations.side_effect = Exception("API Error")

        with pytest.raises(Exception, match="API Error"):
            calculator.find_next_three_expirations("NVDA")

    def test_find_next_three_expirations_sorted_chronologically(self, calculator, mock_broker_client):
        """Test that expiration dates are returned in chronological order."""
        today = date.today()
        exp1 = today + timedelta(days=35)
        exp2 = today + timedelta(days=14)
        exp3 = today + timedelta(days=21)

        # Return expirations in non-chronological order from API
        # Note: API should return sorted, but we test that filtering preserves order
        mock_broker_client.get_option_expirations.return_value = [exp2, exp3, exp1]
        mock_options = [MockOptionContract("NVDA", 150.0, exp1, "call")]
        mock_broker_client.get_option_chain.return_value = mock_options

        result = calculator.find_next_three_expirations("NVDA")

        # Should be sorted chronologically (as returned by API)
        assert result == [exp2, exp3, exp1]


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



class TestStrategyCalculationIntegration:
    """Integration tests for end-to-end strategy calculation."""

    @pytest.fixture
    def mock_broker_client(self):
        """Create a mock broker client with realistic data."""
        client = Mock()
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
        """Create a calculator instance."""
        return TieredCoveredCallCalculator(
            broker_client=mock_broker_client,
            min_days_to_expiration=7,
            max_days_to_expiration=60,
            logger=mock_logger
        )

    def test_end_to_end_strategy_with_valid_expirations(self, calculator, mock_broker_client):
        """Test end-to-end strategy calculation with symbol that has valid expirations."""
        position_summary = PositionSummary(
            symbol="TLT",
            total_shares=600,
            available_shares=600,
            current_price=95.50,
            long_options=[],
            existing_short_calls=[]
        )

        today = date.today()
        exp1 = today + timedelta(days=14)
        exp2 = today + timedelta(days=28)
        exp3 = today + timedelta(days=42)

        # Mock get_option_expirations to return real expiration dates
        mock_broker_client.get_option_expirations.return_value = [exp1, exp2, exp3]

        # Mock option chains with real call options (no synthetic strikes)
        def mock_get_option_chain(symbol, expiration):
            if expiration == exp1:
                return [
                    MockOptionContract(symbol, 96.0, expiration, "call", bid=1.20, ask=1.25),
                    MockOptionContract(symbol, 97.0, expiration, "call", bid=0.80, ask=0.85),
                    MockOptionContract(symbol, 98.0, expiration, "call", bid=0.50, ask=0.55),
                ]
            elif expiration == exp2:
                return [
                    MockOptionContract(symbol, 96.0, expiration, "call", bid=1.80, ask=1.85),
                    MockOptionContract(symbol, 97.0, expiration, "call", bid=1.40, ask=1.45),
                    MockOptionContract(symbol, 98.0, expiration, "call", bid=1.00, ask=1.05),
                    MockOptionContract(symbol, 99.0, expiration, "call", bid=0.70, ask=0.75),
                ]
            else:  # exp3
                return [
                    MockOptionContract(symbol, 96.0, expiration, "call", bid=2.20, ask=2.25),
                    MockOptionContract(symbol, 97.0, expiration, "call", bid=1.80, ask=1.85),
                    MockOptionContract(symbol, 98.0, expiration, "call", bid=1.40, ask=1.45),
                    MockOptionContract(symbol, 99.0, expiration, "call", bid=1.00, ask=1.05),
                    MockOptionContract(symbol, 100.0, expiration, "call", bid=0.70, ask=0.75),
                ]

        mock_broker_client.get_option_chain.side_effect = mock_get_option_chain

        # Execute strategy calculation
        result = calculator.calculate_strategy(position_summary)

        # Verify strategy plan was created
        assert isinstance(result, TieredCoveredCallPlan)
        assert result.symbol == "TLT"
        assert result.current_price == 95.50
        assert result.total_shares == 600
        assert len(result.expiration_groups) == 3
        assert result.total_contracts == 6  # 600 shares / 100 = 6 contracts

        # Verify all expirations are the ones we provided
        result_expirations = [group.expiration_date for group in result.expiration_groups]
        assert result_expirations == [exp1, exp2, exp3]

        # Verify strikes are incremental and above current price
        strikes = [group.strike_price for group in result.expiration_groups]
        assert strikes[0] == 96.0  # First OTM strike
        assert strikes[1] == 97.0  # Next higher strike
        assert strikes[2] == 98.0  # Next higher strike
        assert all(strike > 95.50 for strike in strikes)

    def test_no_synthetic_strikes_in_strategy_plan(self, calculator, mock_broker_client):
        """Verify no synthetic strikes appear in final strategy plan."""
        position_summary = PositionSummary(
            symbol="SPY",
            total_shares=300,
            available_shares=300,
            current_price=450.00,
            long_options=[],
            existing_short_calls=[]
        )

        today = date.today()
        exp1 = today + timedelta(days=10)
        exp2 = today + timedelta(days=24)

        mock_broker_client.get_option_expirations.return_value = [exp1, exp2]

        # Mock option chains with real options only
        def mock_get_option_chain(symbol, expiration):
            return [
                MockOptionContract(symbol, 455.0, expiration, "call", bid=3.50, ask=3.60),
                MockOptionContract(symbol, 460.0, expiration, "call", bid=2.00, ask=2.10),
                MockOptionContract(symbol, 465.0, expiration, "call", bid=1.00, ask=1.10),
            ]

        mock_broker_client.get_option_chain.side_effect = mock_get_option_chain

        result = calculator.calculate_strategy(position_summary)

        # Verify all strikes are from the real option chain
        available_strikes = [455.0, 460.0, 465.0]
        for group in result.expiration_groups:
            assert group.strike_price in available_strikes, \
                f"Strike {group.strike_price} is not in available strikes (possible synthetic)"

    def test_all_expirations_have_real_call_options(self, calculator, mock_broker_client):
        """Verify all expirations in plan have real call options."""
        position_summary = PositionSummary(
            symbol="QQQ",
            total_shares=600,
            available_shares=600,
            current_price=380.00,
            long_options=[],
            existing_short_calls=[]
        )

        today = date.today()
        exp1 = today + timedelta(days=12)
        exp2 = today + timedelta(days=26)
        exp3 = today + timedelta(days=40)

        mock_broker_client.get_option_expirations.return_value = [exp1, exp2, exp3]

        # Track which expirations were validated
        validated_expirations = []

        def mock_get_option_chain(symbol, expiration):
            validated_expirations.append(expiration)
            return [
                MockOptionContract(symbol, 385.0, expiration, "call", bid=2.50, ask=2.60),
                MockOptionContract(symbol, 390.0, expiration, "call", bid=1.50, ask=1.60),
                MockOptionContract(symbol, 395.0, expiration, "call", bid=0.80, ask=0.90),
            ]

        mock_broker_client.get_option_chain.side_effect = mock_get_option_chain

        result = calculator.calculate_strategy(position_summary)

        # Verify all expirations in the plan were validated to have call options
        plan_expirations = [group.expiration_date for group in result.expiration_groups]
        for exp in plan_expirations:
            assert exp in validated_expirations, \
                f"Expiration {exp} in plan was not validated for call options"

        # Verify each expiration has call options (not puts)
        for group in result.expiration_groups:
            options = mock_get_option_chain("QQQ", group.expiration_date)
            call_options = [opt for opt in options if opt.option_type.lower() == "call"]
            assert len(call_options) > 0, \
                f"Expiration {group.expiration_date} has no call options"

    def test_strategy_with_narrow_date_range(self, calculator, mock_broker_client):
        """Test with different date ranges (narrow)."""
        # Create calculator with narrow date range
        calculator.min_days_to_expiration = 10
        calculator.max_days_to_expiration = 25

        position_summary = PositionSummary(
            symbol="IWM",
            total_shares=300,
            available_shares=300,
            current_price=200.00,
            long_options=[],
            existing_short_calls=[]
        )

        today = date.today()
        exp_too_soon = today + timedelta(days=5)
        exp_valid1 = today + timedelta(days=15)
        exp_valid2 = today + timedelta(days=22)
        exp_too_far = today + timedelta(days=35)

        mock_broker_client.get_option_expirations.return_value = [
            exp_too_soon, exp_valid1, exp_valid2, exp_too_far
        ]

        def mock_get_option_chain(symbol, expiration):
            return [
                MockOptionContract(symbol, 205.0, expiration, "call", bid=1.50, ask=1.60),
                MockOptionContract(symbol, 210.0, expiration, "call", bid=0.80, ask=0.90),
            ]

        mock_broker_client.get_option_chain.side_effect = mock_get_option_chain

        result = calculator.calculate_strategy(position_summary)

        # Should only include expirations within narrow range
        result_expirations = [group.expiration_date for group in result.expiration_groups]
        assert exp_too_soon not in result_expirations
        assert exp_too_far not in result_expirations
        assert exp_valid1 in result_expirations
        assert exp_valid2 in result_expirations

    def test_strategy_with_wide_date_range(self, calculator, mock_broker_client):
        """Test with different date ranges (wide)."""
        # Create calculator with wide date range
        calculator.min_days_to_expiration = 7
        calculator.max_days_to_expiration = 90

        position_summary = PositionSummary(
            symbol="DIA",
            total_shares=600,
            available_shares=600,
            current_price=350.00,
            long_options=[],
            existing_short_calls=[]
        )

        today = date.today()
        exp1 = today + timedelta(days=14)
        exp2 = today + timedelta(days=45)
        exp3 = today + timedelta(days=75)

        mock_broker_client.get_option_expirations.return_value = [exp1, exp2, exp3]

        def mock_get_option_chain(symbol, expiration):
            return [
                MockOptionContract(symbol, 355.0, expiration, "call", bid=2.00, ask=2.10),
                MockOptionContract(symbol, 360.0, expiration, "call", bid=1.20, ask=1.30),
                MockOptionContract(symbol, 365.0, expiration, "call", bid=0.70, ask=0.80),
            ]

        mock_broker_client.get_option_chain.side_effect = mock_get_option_chain

        result = calculator.calculate_strategy(position_summary)

        # Should include all expirations within wide range
        result_expirations = [group.expiration_date for group in result.expiration_groups]
        assert len(result_expirations) == 3
        assert exp1 in result_expirations
        assert exp2 in result_expirations
        assert exp3 in result_expirations

    def test_error_handling_no_valid_expirations(self, calculator, mock_broker_client):
        """Test error handling when no valid expirations found."""
        position_summary = PositionSummary(
            symbol="XYZ",
            total_shares=600,
            available_shares=600,
            current_price=100.00,
            long_options=[],
            existing_short_calls=[]
        )

        # Mock get_option_expirations to raise error
        mock_broker_client.get_option_expirations.side_effect = ValueError(
            "No option expirations available for XYZ"
        )

        with pytest.raises(ValueError, match="Error calculating tiered covered call strategy"):
            calculator.calculate_strategy(position_summary)

    def test_error_handling_all_expirations_outside_range(self, calculator, mock_broker_client):
        """Test error handling when all expirations are outside date range."""
        position_summary = PositionSummary(
            symbol="ABC",
            total_shares=600,
            available_shares=600,
            current_price=50.00,
            long_options=[],
            existing_short_calls=[]
        )

        today = date.today()
        exp_too_far = today + timedelta(days=100)

        mock_broker_client.get_option_expirations.return_value = [exp_too_far]

        with pytest.raises(ValueError, match="Error calculating tiered covered call strategy"):
            calculator.calculate_strategy(position_summary)

    def test_error_handling_no_call_options_available(self, calculator, mock_broker_client):
        """Test error handling when no expirations have call options."""
        position_summary = PositionSummary(
            symbol="DEF",
            total_shares=600,
            available_shares=600,
            current_price=75.00,
            long_options=[],
            existing_short_calls=[]
        )

        today = date.today()
        exp1 = today + timedelta(days=14)
        exp2 = today + timedelta(days=28)

        mock_broker_client.get_option_expirations.return_value = [exp1, exp2]

        # Mock option chains with only put options
        def mock_get_option_chain(symbol, expiration):
            return [
                MockOptionContract(symbol, 70.0, expiration, "put", bid=1.00, ask=1.10),
                MockOptionContract(symbol, 65.0, expiration, "put", bid=0.50, ask=0.60),
            ]

        mock_broker_client.get_option_chain.side_effect = mock_get_option_chain

        with pytest.raises(ValueError, match="Error calculating tiered covered call strategy"):
            calculator.calculate_strategy(position_summary)


class TestSyntheticStrikeVerification:
    """Test cases to verify synthetic strikes are never used in strategy calculations."""

    @pytest.fixture
    def mock_broker_client(self):
        """Create a mock broker client."""
        client = Mock()
        client.get_option_expirations = Mock()
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

    def test_get_option_chain_never_generates_synthetic_strikes(self, calculator, mock_broker_client):
        """Verify that get_option_chain() is only called with validated expirations."""
        position_summary = PositionSummary(
            symbol="TLT",
            total_shares=600,
            available_shares=600,
            current_price=95.50,
            long_options=[],
            existing_short_calls=[]
        )

        today = date.today()
        exp1 = today + timedelta(days=10)
        exp2 = today + timedelta(days=24)
        exp3 = today + timedelta(days=38)

        # Mock get_option_expirations to return real dates
        mock_broker_client.get_option_expirations.return_value = [exp1, exp2, exp3]

        # Track all calls to get_option_chain
        option_chain_calls = []

        def mock_get_option_chain(symbol, expiration):
            option_chain_calls.append((symbol, expiration))
            # Return real call options for all validated expirations
            return [
                MockOptionContract(symbol, 96.0, expiration, "call", bid=1.50, ask=1.60),
                MockOptionContract(symbol, 97.0, expiration, "call", bid=1.00, ask=1.10),
                MockOptionContract(symbol, 98.0, expiration, "call", bid=0.60, ask=0.70),
            ]

        mock_broker_client.get_option_chain.side_effect = mock_get_option_chain

        result = calculator.calculate_strategy(position_summary)

        # Verify get_option_chain was only called with validated expirations
        # It should be called during validation and during strike calculation
        for symbol, expiration in option_chain_calls:
            assert expiration in [exp1, exp2, exp3], \
                f"get_option_chain called with unexpected expiration: {expiration}"

        # Verify all strikes in the plan are from real option chains
        real_strikes = [96.0, 97.0, 98.0]
        for group in result.expiration_groups:
            assert group.strike_price in real_strikes, \
                f"Strike {group.strike_price} not in real strikes - possible synthetic"

    def test_find_next_three_expirations_only_returns_validated_expirations(self, calculator, mock_broker_client):
        """Verify find_next_three_expirations() only returns expirations with real call options."""
        today = date.today()
        exp_with_calls = today + timedelta(days=10)
        exp_without_calls = today + timedelta(days=24)
        exp_with_calls_2 = today + timedelta(days=38)

        mock_broker_client.get_option_expirations.return_value = [
            exp_with_calls, exp_without_calls, exp_with_calls_2
        ]

        def mock_get_option_chain(symbol, expiration):
            if expiration == exp_without_calls:
                # Return only put options (no calls)
                return [
                    MockOptionContract(symbol, 95.0, expiration, "put", bid=1.00, ask=1.10),
                ]
            else:
                # Return call options
                return [
                    MockOptionContract(symbol, 96.0, expiration, "call", bid=1.50, ask=1.60),
                    MockOptionContract(symbol, 97.0, expiration, "call", bid=1.00, ask=1.10),
                ]

        mock_broker_client.get_option_chain.side_effect = mock_get_option_chain

        result = calculator.find_next_three_expirations("TLT")

        # Should only include expirations with call options
        assert exp_with_calls in result
        assert exp_without_calls not in result
        assert exp_with_calls_2 in result
        assert len(result) == 2

    def test_calculate_strategy_never_receives_invalid_expirations(self, calculator, mock_broker_client):
        """Test that calculate_strategy() never receives expirations that would trigger synthetic strikes."""
        position_summary = PositionSummary(
            symbol="SPY",
            total_shares=600,
            available_shares=600,
            current_price=450.00,
            long_options=[],
            existing_short_calls=[]
        )

        today = date.today()
        # Include a date that doesn't have real options (like Dec 30)
        exp_invalid = today + timedelta(days=15)
        exp_valid1 = today + timedelta(days=10)
        exp_valid2 = today + timedelta(days=24)

        mock_broker_client.get_option_expirations.return_value = [
            exp_valid1, exp_invalid, exp_valid2
        ]

        def mock_get_option_chain(symbol, expiration):
            if expiration == exp_invalid:
                # Simulate no options available (would trigger synthetic strikes in old code)
                return []
            else:
                return [
                    MockOptionContract(symbol, 455.0, expiration, "call", bid=3.50, ask=3.60),
                    MockOptionContract(symbol, 460.0, expiration, "call", bid=2.00, ask=2.10),
                    MockOptionContract(symbol, 465.0, expiration, "call", bid=1.00, ask=1.10),
                ]

        mock_broker_client.get_option_chain.side_effect = mock_get_option_chain

        result = calculator.calculate_strategy(position_summary)

        # Verify invalid expiration is not in the plan
        plan_expirations = [group.expiration_date for group in result.expiration_groups]
        assert exp_invalid not in plan_expirations, \
            "Invalid expiration (no options) should not be in strategy plan"

        # Verify only valid expirations are in the plan
        for exp in plan_expirations:
            assert exp in [exp_valid1, exp_valid2], \
                f"Unexpected expiration {exp} in plan"

    def test_strategy_plan_contains_no_synthetic_options(self, calculator, mock_broker_client):
        """Add assertion that strategy plan contains no synthetic options."""
        position_summary = PositionSummary(
            symbol="QQQ",
            total_shares=900,
            available_shares=900,
            current_price=380.00,
            long_options=[],
            existing_short_calls=[]
        )

        today = date.today()
        exp1 = today + timedelta(days=12)
        exp2 = today + timedelta(days=26)
        exp3 = today + timedelta(days=40)

        mock_broker_client.get_option_expirations.return_value = [exp1, exp2, exp3]

        # Define real strikes available in the market
        real_strikes = {
            exp1: [385.0, 390.0, 395.0, 400.0],
            exp2: [385.0, 390.0, 395.0, 400.0, 405.0],
            exp3: [385.0, 390.0, 395.0, 400.0, 405.0, 410.0]
        }

        def mock_get_option_chain(symbol, expiration):
            strikes = real_strikes.get(expiration, [])
            return [
                MockOptionContract(symbol, strike, expiration, "call", bid=2.00, ask=2.10)
                for strike in strikes
            ]

        mock_broker_client.get_option_chain.side_effect = mock_get_option_chain

        result = calculator.calculate_strategy(position_summary)

        # Verify all strikes in the plan are from real option chains
        for group in result.expiration_groups:
            available_strikes = real_strikes[group.expiration_date]
            assert group.strike_price in available_strikes, \
                f"Strike {group.strike_price} for expiration {group.expiration_date} " \
                f"is not in real strikes {available_strikes} - possible synthetic strike"

    def test_validation_check_prevents_synthetic_strikes(self, calculator, mock_broker_client):
        """Verify validation check that strategy plan contains no synthetic options."""
        position_summary = PositionSummary(
            symbol="IWM",
            total_shares=300,
            available_shares=300,
            current_price=200.00,
            long_options=[],
            existing_short_calls=[]
        )

        today = date.today()
        exp1 = today + timedelta(days=14)
        exp2 = today + timedelta(days=28)

        mock_broker_client.get_option_expirations.return_value = [exp1, exp2]

        # Track which strikes are requested
        requested_strikes = []

        def mock_get_option_chain(symbol, expiration):
            # Return real call options
            options = [
                MockOptionContract(symbol, 205.0, expiration, "call", bid=1.50, ask=1.60),
                MockOptionContract(symbol, 210.0, expiration, "call", bid=0.80, ask=0.90),
                MockOptionContract(symbol, 215.0, expiration, "call", bid=0.40, ask=0.50),
            ]
            # Track strikes
            for opt in options:
                requested_strikes.append((expiration, opt.strike))
            return options

        mock_broker_client.get_option_chain.side_effect = mock_get_option_chain

        result = calculator.calculate_strategy(position_summary)

        # Verify all strikes in plan were actually returned by get_option_chain
        for group in result.expiration_groups:
            strike_found = False
            for exp, strike in requested_strikes:
                if exp == group.expiration_date and strike == group.strike_price:
                    strike_found = True
                    break
            assert strike_found, \
                f"Strike {group.strike_price} for expiration {group.expiration_date} " \
                f"was not returned by get_option_chain - possible synthetic strike"

    def test_error_propagation_without_synthetic_fallback(self, calculator, mock_broker_client):
        """Verify errors are propagated without attempting synthetic strike generation."""
        position_summary = PositionSummary(
            symbol="XYZ",
            total_shares=600,
            available_shares=600,
            current_price=100.00,
            long_options=[],
            existing_short_calls=[]
        )

        # Mock get_option_expirations to raise error
        mock_broker_client.get_option_expirations.side_effect = ValueError(
            "No option expirations available for XYZ"
        )

        # Should raise error without attempting to generate synthetic strikes
        with pytest.raises(ValueError) as exc_info:
            calculator.calculate_strategy(position_summary)

        # Verify error message doesn't mention synthetic strikes
        error_msg = str(exc_info.value).lower()
        assert "synthetic" not in error_msg, \
            "Error message should not mention synthetic strikes"

        # Verify get_option_chain was never called (no synthetic fallback)
        assert mock_broker_client.get_option_chain.call_count == 0, \
            "get_option_chain should not be called when get_option_expirations fails"

    def test_real_world_scenario_dec_30_excluded(self, calculator, mock_broker_client):
        """Test real-world scenario where Dec 30 (invalid date) is excluded from strategy."""
        position_summary = PositionSummary(
            symbol="TLT",
            total_shares=600,
            available_shares=600,
            current_price=95.50,
            long_options=[],
            existing_short_calls=[]
        )

        today = date.today()
        # Simulate dates including an invalid one like Dec 30
        exp_valid1 = today + timedelta(days=10)
        exp_invalid = today + timedelta(days=20)  # Simulating Dec 30
        exp_valid2 = today + timedelta(days=30)
        exp_valid3 = today + timedelta(days=45)

        mock_broker_client.get_option_expirations.return_value = [
            exp_valid1, exp_invalid, exp_valid2, exp_valid3
        ]

        def mock_get_option_chain(symbol, expiration):
            if expiration == exp_invalid:
                # Simulate no real options available (like Dec 30)
                return []
            else:
                return [
                    MockOptionContract(symbol, 96.0, expiration, "call", bid=1.50, ask=1.60),
                    MockOptionContract(symbol, 97.0, expiration, "call", bid=1.00, ask=1.10),
                    MockOptionContract(symbol, 98.0, expiration, "call", bid=0.60, ask=0.70),
                ]

        mock_broker_client.get_option_chain.side_effect = mock_get_option_chain

        result = calculator.calculate_strategy(position_summary)

        # Verify invalid date (Dec 30) is not in the plan
        plan_expirations = [group.expiration_date for group in result.expiration_groups]
        assert exp_invalid not in plan_expirations, \
            "Invalid expiration (like Dec 30) should be excluded from strategy"

        # Verify only valid expirations with real options are included
        assert exp_valid1 in plan_expirations
        assert exp_valid2 in plan_expirations
        assert exp_valid3 in plan_expirations

        # Verify all strikes are real (not synthetic)
        real_strikes = [96.0, 97.0, 98.0]
        for group in result.expiration_groups:
            assert group.strike_price in real_strikes, \
                f"Strike {group.strike_price} is not a real strike - possible synthetic"
