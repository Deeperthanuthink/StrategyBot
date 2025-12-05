"""Unit tests for StrategyCalculator."""

import pytest
from datetime import date, timedelta
from src.strategy.strategy_calculator import StrategyCalculator, SpreadParameters
from src.config.models import Config, AlpacaCredentials, LoggingConfig


@pytest.fixture
def sample_config():
    """Create a sample configuration for testing."""
    return Config(
        symbols=["NVDA", "AAPL"],
        strike_offset_percent=5.0,
        spread_width=5.0,
        contract_quantity=1,
        execution_day="Tuesday",
        execution_time_offset_minutes=30,
        expiration_offset_weeks=1,
        alpaca_credentials=AlpacaCredentials(
            api_key="test_key",
            api_secret="test_secret",
            base_url="https://paper-api.alpaca.markets",
        ),
        logging_config=LoggingConfig(level="INFO", file_path="logs/test.log"),
    )


@pytest.fixture
def calculator(sample_config):
    """Create a StrategyCalculator instance for testing."""
    return StrategyCalculator(sample_config)


class TestStrikePriceCalculations:
    """Tests for strike price calculation methods."""

    def test_calculate_short_strike_basic(self, calculator):
        """Test basic short strike calculation."""
        current_price = 100.0
        offset_percent = 5.0

        short_strike = calculator.calculate_short_strike(current_price, offset_percent)

        assert short_strike == 95.0

    def test_calculate_short_strike_various_prices(self, calculator):
        """Test short strike calculation with various market prices."""
        test_cases = [
            (150.0, 5.0, 142.5),
            (50.0, 10.0, 45.0),
            (200.0, 3.0, 194.0),
            (75.5, 5.0, 71.725),
        ]

        for current_price, offset_percent, expected in test_cases:
            result = calculator.calculate_short_strike(current_price, offset_percent)
            assert abs(result - expected) < 0.001

    def test_calculate_short_strike_invalid_price(self, calculator):
        """Test short strike calculation with invalid price."""
        with pytest.raises(ValueError, match="Current price must be positive"):
            calculator.calculate_short_strike(0, 5.0)

        with pytest.raises(ValueError, match="Current price must be positive"):
            calculator.calculate_short_strike(-10, 5.0)

    def test_calculate_short_strike_invalid_offset(self, calculator):
        """Test short strike calculation with invalid offset."""
        with pytest.raises(ValueError, match="Offset percent must be between 0 and 100"):
            calculator.calculate_short_strike(100.0, 0)

        with pytest.raises(ValueError, match="Offset percent must be between 0 and 100"):
            calculator.calculate_short_strike(100.0, 101)

    def test_calculate_long_strike_basic(self, calculator):
        """Test basic long strike calculation."""
        short_strike = 95.0
        spread_width = 5.0

        long_strike = calculator.calculate_long_strike(short_strike, spread_width)

        assert long_strike == 90.0

    def test_calculate_long_strike_various_widths(self, calculator):
        """Test long strike calculation with various spread widths."""
        test_cases = [(100.0, 5.0, 95.0), (142.5, 10.0, 132.5), (50.0, 2.5, 47.5)]

        for short_strike, spread_width, expected in test_cases:
            result = calculator.calculate_long_strike(short_strike, spread_width)
            assert abs(result - expected) < 0.001

    def test_calculate_long_strike_invalid_inputs(self, calculator):
        """Test long strike calculation with invalid inputs."""
        with pytest.raises(ValueError, match="Short strike must be positive"):
            calculator.calculate_long_strike(0, 5.0)

        with pytest.raises(ValueError, match="Spread width must be positive"):
            calculator.calculate_long_strike(100.0, 0)

        with pytest.raises(
            ValueError,
            match="Spread width cannot be greater than or equal to short strike",
        ):
            calculator.calculate_long_strike(10.0, 15.0)


class TestExpirationDateCalculation:
    """Tests for expiration date calculation."""

    def test_calculate_expiration_basic(self, calculator):
        """Test basic expiration date calculation."""
        # Tuesday, Nov 19, 2024
        execution_date = date(2024, 11, 19)
        offset_weeks = 1

        expiration = calculator.calculate_expiration_date(execution_date, offset_weeks)

        # Should be Friday, Nov 29, 2024
        assert expiration == date(2024, 11, 29)
        assert expiration.weekday() == 4  # Friday

    def test_calculate_expiration_from_different_weekdays(self, calculator):
        """Test expiration calculation from different starting weekdays."""
        # Monday, Nov 18, 2024
        monday = date(2024, 11, 18)
        expiration = calculator.calculate_expiration_date(monday, 1)
        assert expiration == date(2024, 11, 29)
        assert expiration.weekday() == 4

        # Wednesday, Nov 20, 2024
        wednesday = date(2024, 11, 20)
        expiration = calculator.calculate_expiration_date(wednesday, 1)
        assert expiration == date(2024, 11, 29)
        assert expiration.weekday() == 4

        # Friday, Nov 22, 2024
        friday = date(2024, 11, 22)
        expiration = calculator.calculate_expiration_date(friday, 1)
        assert expiration == date(2024, 11, 29)
        assert expiration.weekday() == 4

    def test_calculate_expiration_multiple_weeks(self, calculator):
        """Test expiration calculation with multiple week offsets."""
        execution_date = date(2024, 11, 19)

        # 2 weeks
        expiration = calculator.calculate_expiration_date(execution_date, 2)
        assert expiration == date(2024, 12, 6)
        assert expiration.weekday() == 4

        # 3 weeks
        expiration = calculator.calculate_expiration_date(execution_date, 3)
        assert expiration == date(2024, 12, 13)
        assert expiration.weekday() == 4

    def test_calculate_expiration_invalid_offset(self, calculator):
        """Test expiration calculation with invalid offset."""
        execution_date = date(2024, 11, 19)

        with pytest.raises(ValueError, match="Offset weeks must be positive"):
            calculator.calculate_expiration_date(execution_date, 0)

        with pytest.raises(ValueError, match="Offset weeks must be positive"):
            calculator.calculate_expiration_date(execution_date, -1)


class TestStrikeRounding:
    """Tests for finding nearest available strike."""

    def test_find_nearest_strike_exact_match(self, calculator):
        """Test finding strike when exact match exists."""
        available_strikes = [90.0, 95.0, 100.0, 105.0, 110.0]
        target_strike = 100.0

        nearest = calculator.find_nearest_strike(target_strike, available_strikes)

        assert nearest == 100.0

    def test_find_nearest_strike_round_down(self, calculator):
        """Test finding strike that rounds down."""
        available_strikes = [90.0, 95.0, 100.0, 105.0, 110.0]
        target_strike = 97.0

        nearest = calculator.find_nearest_strike(target_strike, available_strikes)

        assert nearest == 95.0

    def test_find_nearest_strike_round_up(self, calculator):
        """Test finding strike that rounds up."""
        available_strikes = [90.0, 95.0, 100.0, 105.0, 110.0]
        target_strike = 103.0

        nearest = calculator.find_nearest_strike(target_strike, available_strikes)

        assert nearest == 105.0

    def test_find_nearest_strike_midpoint(self, calculator):
        """Test finding strike at exact midpoint."""
        available_strikes = [90.0, 95.0, 100.0, 105.0, 110.0]
        target_strike = 97.5

        nearest = calculator.find_nearest_strike(target_strike, available_strikes)

        # Should pick one of the two equidistant strikes
        assert nearest in [95.0, 100.0]

    def test_find_nearest_strike_empty_list(self, calculator):
        """Test finding strike with empty list."""
        with pytest.raises(ValueError, match="No available strikes provided"):
            calculator.find_nearest_strike(100.0, [])

    def test_find_nearest_strike_invalid_target(self, calculator):
        """Test finding strike with invalid target."""
        available_strikes = [90.0, 95.0, 100.0]

        with pytest.raises(ValueError, match="Target strike must be positive"):
            calculator.find_nearest_strike(0, available_strikes)


class TestSpreadValidation:
    """Tests for spread parameter validation."""

    def test_validate_spread_valid(self, calculator):
        """Test validation of valid spread parameters."""
        spread = SpreadParameters(
            symbol="NVDA",
            short_strike=95.0,
            long_strike=90.0,
            expiration=date.today() + timedelta(days=7),
            current_price=100.0,
            spread_width=5.0,
        )

        result = calculator.validate_spread_parameters(spread)

        assert result is True

    def test_validate_spread_invalid_strike_order(self, calculator):
        """Test validation with invalid strike ordering."""
        spread = SpreadParameters(
            symbol="NVDA",
            short_strike=90.0,
            long_strike=95.0,
            expiration=date.today() + timedelta(days=7),
            current_price=100.0,
            spread_width=5.0,
        )

        with pytest.raises(ValueError, match="Short strike must be greater than long strike"):
            calculator.validate_spread_parameters(spread)

    def test_validate_spread_negative_strikes(self, calculator):
        """Test validation with negative strikes."""
        spread = SpreadParameters(
            symbol="NVDA",
            short_strike=-95.0,
            long_strike=-90.0,
            expiration=date.today() + timedelta(days=7),
            current_price=100.0,
            spread_width=5.0,
        )

        with pytest.raises(ValueError, match="Short strike must be positive"):
            calculator.validate_spread_parameters(spread)

    def test_validate_spread_width_mismatch(self, calculator):
        """Test validation with mismatched spread width."""
        spread = SpreadParameters(
            symbol="NVDA",
            short_strike=95.0,
            long_strike=90.0,
            expiration=date.today() + timedelta(days=7),
            current_price=100.0,
            spread_width=10.0,  # Actual width is 5.0
        )

        with pytest.raises(
            ValueError,
            match="Actual spread width doesn't match configured spread width",
        ):
            calculator.validate_spread_parameters(spread)

    def test_validate_spread_past_expiration(self, calculator):
        """Test validation with past expiration date."""
        spread = SpreadParameters(
            symbol="NVDA",
            short_strike=95.0,
            long_strike=90.0,
            expiration=date.today() - timedelta(days=1),
            current_price=100.0,
            spread_width=5.0,
        )

        with pytest.raises(ValueError, match="Expiration date cannot be in the past"):
            calculator.validate_spread_parameters(spread)
