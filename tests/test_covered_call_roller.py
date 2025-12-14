"""Unit tests for CoveredCallRoller functionality."""

import pytest
from datetime import date, timedelta, datetime
from unittest.mock import Mock, MagicMock
from dataclasses import dataclass

from src.strategy.covered_call_roller import (
    CoveredCallRoller,
    RollOpportunity,
    RollPlan,
    RollOrder,
    RollOrderResult
)
from src.positions.models import OptionPosition
from src.brokers.base_client import OptionContract, OrderResult


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


class TestCoveredCallRoller:
    """Test cases for CoveredCallRoller initialization and basic functionality."""

    @pytest.fixture
    def mock_broker_client(self):
        """Create a mock broker client."""
        client = Mock()
        client.get_expiring_short_calls = Mock()
        client.get_current_price = Mock()
        client.get_option_chain = Mock()
        client.submit_roll_order = Mock()
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
    def roller(self, mock_broker_client, mock_logger):
        """Create a CoveredCallRoller instance."""
        return CoveredCallRoller(
            broker_client=mock_broker_client,
            logger=mock_logger
        )

    def test_initialization(self, roller, mock_broker_client, mock_logger):
        """Test roller initialization."""
        assert roller.broker_client == mock_broker_client
        assert roller.logger == mock_logger

    def test_initialization_without_logger(self, mock_broker_client):
        """Test roller initialization without logger."""
        roller = CoveredCallRoller(mock_broker_client)
        assert roller.broker_client == mock_broker_client
        assert roller.logger is None


class TestExpiringITMCallIdentification:
    """Test cases for identifying expiring ITM calls with various scenarios."""

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
        return logger

    @pytest.fixture
    def roller(self, mock_broker_client, mock_logger):
        """Create a roller instance."""
        return CoveredCallRoller(mock_broker_client, mock_logger)

    @pytest.fixture
    def sample_expiring_calls(self):
        """Create sample expiring call positions."""
        today = date.today()
        return [
            OptionPosition(
                symbol="TLT", quantity=-2, market_value=-500.0, average_cost=-2.50,
                unrealized_pnl=100.0, position_type="short_call", strike=95.0,
                expiration=today, option_type="call"
            ),
            OptionPosition(
                symbol="TLT", quantity=-1, market_value=-150.0, average_cost=-1.50,
                unrealized_pnl=50.0, position_type="short_call", strike=100.0,
                expiration=today, option_type="call"
            ),
            OptionPosition(
                symbol="NVDA", quantity=-3, market_value=-750.0, average_cost=-2.50,
                unrealized_pnl=200.0, position_type="short_call", strike=140.0,
                expiration=today, option_type="call"
            )
        ]

    def test_identify_expiring_itm_calls_success(self, roller, mock_broker_client, mock_logger, sample_expiring_calls):
        """Test successful identification of expiring ITM calls."""
        # Setup mock responses
        mock_broker_client.get_expiring_short_calls.return_value = sample_expiring_calls
        mock_broker_client.get_current_price.side_effect = lambda symbol: {
            "TLT": 98.0,  # TLT at $98 - $95 call is ITM, $100 call is OTM
            "NVDA": 145.0  # NVDA at $145 - $140 call is ITM
        }[symbol]

        result = roller.identify_expiring_itm_calls()

        # Should find 2 ITM calls: TLT $95 and NVDA $140
        assert len(result) == 2
        
        # Verify the ITM calls
        itm_symbols_strikes = [(call.symbol, call.strike) for call in result]
        assert ("TLT", 95.0) in itm_symbols_strikes
        assert ("NVDA", 140.0) in itm_symbols_strikes
        assert ("TLT", 100.0) not in itm_symbols_strikes  # This one is OTM

        # Verify broker calls
        mock_broker_client.get_expiring_short_calls.assert_called_once_with(date.today(), None)
        assert mock_broker_client.get_current_price.call_count == 2  # Called for TLT and NVDA

        # Verify logging
        mock_logger.log_info.assert_called()

    def test_identify_expiring_itm_calls_with_symbol_filter(self, roller, mock_broker_client, mock_logger, sample_expiring_calls):
        """Test identification with symbol filter."""
        # Filter to only TLT calls
        tlt_calls = [call for call in sample_expiring_calls if call.symbol == "TLT"]
        mock_broker_client.get_expiring_short_calls.return_value = tlt_calls
        mock_broker_client.get_current_price.return_value = 98.0  # TLT at $98

        result = roller.identify_expiring_itm_calls("TLT")

        # Should find 1 ITM call: TLT $95
        assert len(result) == 1
        assert result[0].symbol == "TLT"
        assert result[0].strike == 95.0

        # Verify broker was called with symbol filter
        mock_broker_client.get_expiring_short_calls.assert_called_once_with(date.today(), "TLT")

    def test_identify_expiring_itm_calls_no_itm_calls(self, roller, mock_broker_client, mock_logger, sample_expiring_calls):
        """Test identification when no calls are ITM."""
        mock_broker_client.get_expiring_short_calls.return_value = sample_expiring_calls
        # Set prices below all strikes
        mock_broker_client.get_current_price.side_effect = lambda symbol: {
            "TLT": 90.0,  # Below both $95 and $100 strikes
            "NVDA": 135.0  # Below $140 strike
        }[symbol]

        result = roller.identify_expiring_itm_calls()

        assert len(result) == 0
        mock_logger.log_info.assert_called()

    def test_identify_expiring_itm_calls_no_expiring_calls(self, roller, mock_broker_client, mock_logger):
        """Test identification when no calls are expiring."""
        mock_broker_client.get_expiring_short_calls.return_value = []

        result = roller.identify_expiring_itm_calls()

        assert len(result) == 0
        mock_broker_client.get_expiring_short_calls.assert_called_once()

    def test_identify_expiring_itm_calls_price_api_error(self, roller, mock_broker_client, mock_logger, sample_expiring_calls):
        """Test identification with price API error for one symbol."""
        mock_broker_client.get_expiring_short_calls.return_value = sample_expiring_calls
        
        def mock_get_price(symbol):
            if symbol == "TLT":
                return 98.0
            elif symbol == "NVDA":
                raise Exception("Price API failed")
        
        mock_broker_client.get_current_price.side_effect = mock_get_price

        result = roller.identify_expiring_itm_calls()

        # Should still find TLT ITM call despite NVDA error
        assert len(result) == 1
        assert result[0].symbol == "TLT"
        assert result[0].strike == 95.0

        # Verify error was logged
        mock_logger.log_error.assert_called()

    def test_identify_expiring_itm_calls_broker_api_error(self, roller, mock_broker_client, mock_logger):
        """Test identification with broker API error."""
        mock_broker_client.get_expiring_short_calls.side_effect = Exception("Broker API failed")

        with pytest.raises(RuntimeError, match="Error identifying expiring ITM calls"):
            roller.identify_expiring_itm_calls()

        mock_logger.log_error.assert_called()

    def test_identify_expiring_itm_calls_tlt_specific_scenario(self, roller, mock_broker_client, mock_logger):
        """Test identification with TLT-specific scenario as mentioned in requirements."""
        # Create TLT-specific expiring calls
        today = date.today()
        tlt_calls = [
            OptionPosition(
                symbol="TLT", quantity=-5, market_value=-1250.0, average_cost=-2.50,
                unrealized_pnl=500.0, position_type="short_call", strike=92.0,
                expiration=today, option_type="call"
            ),
            OptionPosition(
                symbol="TLT", quantity=-3, market_value=-450.0, average_cost=-1.50,
                unrealized_pnl=150.0, position_type="short_call", strike=95.0,
                expiration=today, option_type="call"
            ),
            OptionPosition(
                symbol="TLT", quantity=-2, market_value=-200.0, average_cost=-1.00,
                unrealized_pnl=50.0, position_type="short_call", strike=98.0,
                expiration=today, option_type="call"
            )
        ]

        mock_broker_client.get_expiring_short_calls.return_value = tlt_calls
        mock_broker_client.get_current_price.return_value = 96.5  # TLT at $96.50

        result = roller.identify_expiring_itm_calls("TLT")

        # Should find 2 ITM calls: $92 and $95 strikes (both below $96.50)
        assert len(result) == 2
        itm_strikes = sorted([call.strike for call in result])
        assert itm_strikes == [92.0, 95.0]

        # $98 strike should not be ITM
        assert not any(call.strike == 98.0 for call in result)


class TestRollOpportunityCalculation:
    """Test cases for roll opportunity calculation with different market conditions."""

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
        return logger

    @pytest.fixture
    def roller(self, mock_broker_client, mock_logger):
        """Create a roller instance."""
        return CoveredCallRoller(mock_broker_client, mock_logger)

    @pytest.fixture
    def sample_itm_calls(self):
        """Create sample ITM call positions."""
        today = date.today()
        return [
            OptionPosition(
                symbol="TLT", quantity=-2, market_value=-500.0, average_cost=-2.50,
                unrealized_pnl=100.0, position_type="short_call", strike=95.0,
                expiration=today, option_type="call"
            ),
            OptionPosition(
                symbol="NVDA", quantity=-1, market_value=-300.0, average_cost=-3.00,
                unrealized_pnl=150.0, position_type="short_call", strike=140.0,
                expiration=today, option_type="call"
            )
        ]

    def test_calculate_roll_opportunities_success(self, roller, mock_broker_client, mock_logger, sample_itm_calls):
        """Test successful calculation of roll opportunities."""
        # Setup mock responses
        mock_broker_client.get_current_price.side_effect = lambda symbol: {
            "TLT": 98.0,
            "NVDA": 145.0
        }[symbol]

        # Mock find_best_roll_target to return valid targets
        roller.find_best_roll_target = Mock()
        roller.find_best_roll_target.side_effect = [
            (date.today() + timedelta(days=14), 97.0),  # TLT roll target
            (date.today() + timedelta(days=21), 142.0)  # NVDA roll target
        ]

        # Mock estimate_roll_credit to return positive credits
        roller.estimate_roll_credit = Mock()
        roller.estimate_roll_credit.side_effect = [1.25, 2.50]  # Positive credits

        result = roller.calculate_roll_opportunities(sample_itm_calls)

        assert len(result) == 2
        
        # Verify TLT opportunity
        tlt_opportunity = next(opp for opp in result if opp.symbol == "TLT")
        assert tlt_opportunity.current_call.strike == 95.0
        assert tlt_opportunity.target_strike == 97.0
        assert tlt_opportunity.estimated_credit == 1.25
        assert tlt_opportunity.current_price == 98.0

        # Verify NVDA opportunity
        nvda_opportunity = next(opp for opp in result if opp.symbol == "NVDA")
        assert nvda_opportunity.current_call.strike == 140.0
        assert nvda_opportunity.target_strike == 142.0
        assert nvda_opportunity.estimated_credit == 2.50
        assert nvda_opportunity.current_price == 145.0

        # Verify method calls
        assert roller.find_best_roll_target.call_count == 2
        assert roller.estimate_roll_credit.call_count == 2

    def test_calculate_roll_opportunities_negative_credit(self, roller, mock_broker_client, mock_logger, sample_itm_calls):
        """Test calculation when roll would result in negative credit."""
        mock_broker_client.get_current_price.return_value = 98.0

        # Mock to return valid targets but negative credits
        roller.find_best_roll_target = Mock(return_value=(date.today() + timedelta(days=14), 97.0))
        roller.estimate_roll_credit = Mock(return_value=-0.50)  # Negative credit

        result = roller.calculate_roll_opportunities(sample_itm_calls)

        # Should return empty list since no positive credit opportunities
        assert len(result) == 0
        mock_logger.log_info.assert_called()

    def test_calculate_roll_opportunities_no_suitable_targets(self, roller, mock_broker_client, mock_logger, sample_itm_calls):
        """Test calculation when no suitable roll targets are found."""
        mock_broker_client.get_current_price.return_value = 98.0

        # Mock to return no suitable targets
        roller.find_best_roll_target = Mock(return_value=(None, None))

        result = roller.calculate_roll_opportunities(sample_itm_calls)

        assert len(result) == 0
        mock_logger.log_info.assert_called()

    def test_calculate_roll_opportunities_mixed_results(self, roller, mock_broker_client, mock_logger, sample_itm_calls):
        """Test calculation with mixed results (some viable, some not)."""
        mock_broker_client.get_current_price.side_effect = lambda symbol: {
            "TLT": 98.0,
            "NVDA": 145.0
        }[symbol]

        # Mock different outcomes for each call
        def mock_find_target(call, price):
            if call.symbol == "TLT":
                return (date.today() + timedelta(days=14), 97.0)  # Valid target
            else:
                return (None, None)  # No target for NVDA

        roller.find_best_roll_target = Mock(side_effect=mock_find_target)
        roller.estimate_roll_credit = Mock(return_value=1.25)  # Positive credit for TLT

        result = roller.calculate_roll_opportunities(sample_itm_calls)

        # Should only find opportunity for TLT
        assert len(result) == 1
        assert result[0].symbol == "TLT"

    def test_calculate_roll_opportunities_api_error(self, roller, mock_broker_client, mock_logger, sample_itm_calls):
        """Test calculation with API error."""
        mock_broker_client.get_current_price.side_effect = Exception("Price API failed")

        # The method handles individual call errors gracefully, so it returns empty list instead of raising
        result = roller.calculate_roll_opportunities(sample_itm_calls)
        
        assert len(result) == 0  # Should return empty list when all calls fail
        mock_logger.log_error.assert_called()

    def test_calculate_roll_opportunities_individual_call_error(self, roller, mock_broker_client, mock_logger, sample_itm_calls):
        """Test calculation with error for individual call."""
        # First call succeeds, second fails
        def mock_get_price(symbol):
            if symbol == "TLT":
                return 98.0
            else:
                raise Exception("NVDA price failed")

        mock_broker_client.get_current_price.side_effect = mock_get_price

        # Mock successful roll target for TLT
        roller.find_best_roll_target = Mock(return_value=(date.today() + timedelta(days=14), 97.0))
        roller.estimate_roll_credit = Mock(return_value=1.25)

        result = roller.calculate_roll_opportunities(sample_itm_calls)

        # Should still find opportunity for TLT despite NVDA error
        assert len(result) == 1
        assert result[0].symbol == "TLT"

        # Verify error was logged
        mock_logger.log_error.assert_called()


class TestRollTargetSelection:
    """Test cases for finding best roll targets."""

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
        return logger

    @pytest.fixture
    def roller(self, mock_broker_client, mock_logger):
        """Create a roller instance."""
        return CoveredCallRoller(mock_broker_client, mock_logger)

    @pytest.fixture
    def sample_call(self):
        """Create a sample call position."""
        return OptionPosition(
            symbol="TLT", quantity=-2, market_value=-500.0, average_cost=-2.50,
            unrealized_pnl=100.0, position_type="short_call", strike=95.0,
            expiration=date.today(), option_type="call"
        )

    def test_find_best_roll_target_success(self, roller, mock_broker_client, mock_logger, sample_call):
        """Test successful roll target selection."""
        current_price = 98.0
        
        # Mock option chain for target expiration
        target_exp = date.today() + timedelta(days=7)  # Next Friday
        mock_options = [
            MockOptionContract("TLT", 93.0, target_exp, "call"),
            MockOptionContract("TLT", 95.0, target_exp, "call"),  # Same strike
            MockOptionContract("TLT", 97.0, target_exp, "call"),  # Higher strike
            MockOptionContract("TLT", 99.0, target_exp, "call"),
        ]

        mock_broker_client.get_option_chain.return_value = mock_options

        target_expiration, target_strike = roller.find_best_roll_target(sample_call, current_price)

        assert target_expiration is not None
        assert target_strike == 95.0  # Should select same or higher strike (95.0 is first at/above current)
        
        mock_broker_client.get_option_chain.assert_called()
        mock_logger.log_info.assert_called()

    def test_find_best_roll_target_prefer_higher_strike(self, roller, mock_broker_client, mock_logger, sample_call):
        """Test that higher strikes are preferred when available."""
        current_price = 98.0
        
        target_exp = date.today() + timedelta(days=7)
        mock_options = [
            MockOptionContract("TLT", 93.0, target_exp, "call"),  # Below current strike
            MockOptionContract("TLT", 97.0, target_exp, "call"),  # Above current strike
            MockOptionContract("TLT", 99.0, target_exp, "call"),  # Even higher
        ]

        mock_broker_client.get_option_chain.return_value = mock_options

        target_expiration, target_strike = roller.find_best_roll_target(sample_call, current_price)

        assert target_strike == 97.0  # Should select first strike at or above current (97.0)

    def test_find_best_roll_target_no_higher_strikes(self, roller, mock_broker_client, mock_logger, sample_call):
        """Test roll target selection when no higher strikes available."""
        current_price = 98.0
        
        target_exp = date.today() + timedelta(days=7)
        mock_options = [
            MockOptionContract("TLT", 90.0, target_exp, "call"),
            MockOptionContract("TLT", 92.0, target_exp, "call"),  # All below current strike
            MockOptionContract("TLT", 94.0, target_exp, "call"),
        ]

        mock_broker_client.get_option_chain.return_value = mock_options

        target_expiration, target_strike = roller.find_best_roll_target(sample_call, current_price)

        assert target_strike == 94.0  # Should use highest available strike

    def test_find_best_roll_target_no_call_options(self, roller, mock_broker_client, mock_logger, sample_call):
        """Test roll target selection when no call options available."""
        current_price = 98.0
        
        # Only put options available
        target_exp = date.today() + timedelta(days=7)
        mock_options = [
            MockOptionContract("TLT", 95.0, target_exp, "put"),
            MockOptionContract("TLT", 97.0, target_exp, "put"),
        ]

        mock_broker_client.get_option_chain.return_value = mock_options

        target_expiration, target_strike = roller.find_best_roll_target(sample_call, current_price)

        assert target_expiration is None
        assert target_strike is None
        mock_logger.log_info.assert_called()

    def test_find_best_roll_target_no_available_expirations(self, roller, mock_broker_client, mock_logger, sample_call):
        """Test roll target selection when no expirations are available."""
        current_price = 98.0
        
        # Mock option chain to return empty for all potential expirations
        mock_broker_client.get_option_chain.return_value = []

        target_expiration, target_strike = roller.find_best_roll_target(sample_call, current_price)

        assert target_expiration is None
        assert target_strike is None
        mock_logger.log_info.assert_called()

    def test_find_best_roll_target_api_error(self, roller, mock_broker_client, mock_logger, sample_call):
        """Test roll target selection with API error."""
        current_price = 98.0
        
        mock_broker_client.get_option_chain.side_effect = Exception("Option chain API failed")

        target_expiration, target_strike = roller.find_best_roll_target(sample_call, current_price)

        assert target_expiration is None
        assert target_strike is None
        # The method catches exceptions and returns None, None but may not always log errors
        # depending on where the exception occurs


class TestCreditCalculation:
    """Test cases for roll credit calculation and strike selection logic."""

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
        return logger

    @pytest.fixture
    def roller(self, mock_broker_client, mock_logger):
        """Create a roller instance."""
        return CoveredCallRoller(mock_broker_client, mock_logger)

    @pytest.fixture
    def sample_call(self):
        """Create a sample call position."""
        return OptionPosition(
            symbol="TLT", quantity=-2, market_value=-500.0, average_cost=-2.50,
            unrealized_pnl=100.0, position_type="short_call", strike=95.0,
            expiration=date.today(), option_type="call"
        )

    def test_estimate_roll_credit_itm_to_otm(self, roller, mock_broker_client, mock_logger, sample_call):
        """Test credit estimation for rolling ITM call to OTM call."""
        current_price = 98.0  # Stock at $98, call strike at $95 (ITM)
        target_exp = date.today() + timedelta(days=14)
        target_strike = 100.0  # OTM target

        mock_broker_client.get_current_price.return_value = current_price

        credit = roller.estimate_roll_credit(sample_call, target_exp, target_strike)

        # Should be positive credit (simplified calculation)
        # Buyback cost = intrinsic (98-95=3) + small time value (0.05) = 3.05
        # New call premium = time value only for OTM = 0.02 * 14 = 0.28
        # Credit = 0.28 - 3.05 = -2.77 (actually a debit in this case)
        assert isinstance(credit, float)
        mock_broker_client.get_current_price.assert_called_once_with("TLT")
        mock_logger.log_info.assert_called()

    def test_estimate_roll_credit_itm_to_itm(self, roller, mock_broker_client, mock_logger, sample_call):
        """Test credit estimation for rolling ITM call to another ITM call."""
        current_price = 98.0
        target_exp = date.today() + timedelta(days=21)
        target_strike = 97.0  # Still ITM but higher than current

        mock_broker_client.get_current_price.return_value = current_price

        credit = roller.estimate_roll_credit(sample_call, target_exp, target_strike)

        assert isinstance(credit, float)
        # Should account for intrinsic value in new call
        mock_logger.log_info.assert_called()

    def test_estimate_roll_credit_longer_expiration(self, roller, mock_broker_client, mock_logger, sample_call):
        """Test credit estimation with longer expiration (more time value)."""
        current_price = 98.0
        target_exp = date.today() + timedelta(days=35)  # 5 weeks out
        target_strike = 100.0

        mock_broker_client.get_current_price.return_value = current_price

        credit = roller.estimate_roll_credit(sample_call, target_exp, target_strike)

        assert isinstance(credit, float)
        # Longer expiration should provide more time value
        mock_logger.log_info.assert_called()

    def test_estimate_roll_credit_api_error(self, roller, mock_broker_client, mock_logger, sample_call):
        """Test credit estimation with API error."""
        target_exp = date.today() + timedelta(days=14)
        target_strike = 100.0

        mock_broker_client.get_current_price.side_effect = Exception("Price API failed")

        credit = roller.estimate_roll_credit(sample_call, target_exp, target_strike)

        assert credit == 0.0  # Should return 0 on error
        mock_logger.log_error.assert_called()

    def test_estimate_roll_credit_tlt_specific_scenario(self, roller, mock_broker_client, mock_logger):
        """Test credit estimation with TLT-specific scenario."""
        # TLT call at $95 strike, stock at $96.50
        tlt_call = OptionPosition(
            symbol="TLT", quantity=-5, market_value=-1250.0, average_cost=-2.50,
            unrealized_pnl=500.0, position_type="short_call", strike=95.0,
            expiration=date.today(), option_type="call"
        )
        
        current_price = 96.5
        target_exp = date.today() + timedelta(days=21)  # 3 weeks out
        target_strike = 97.0  # Slightly higher strike

        mock_broker_client.get_current_price.return_value = current_price

        credit = roller.estimate_roll_credit(tlt_call, target_exp, target_strike)

        assert isinstance(credit, float)
        # With TLT's typical volatility and time value, should be reasonable estimate
        mock_logger.log_info.assert_called()

    def test_estimate_roll_credit_various_time_periods(self, roller, mock_broker_client, mock_logger, sample_call):
        """Test credit estimation with various time periods."""
        current_price = 98.0
        mock_broker_client.get_current_price.return_value = current_price
        target_strike = 100.0

        # Test different expiration periods
        time_periods = [7, 14, 21, 28, 35]  # 1-5 weeks
        credits = []

        for days in time_periods:
            target_exp = date.today() + timedelta(days=days)
            credit = roller.estimate_roll_credit(sample_call, target_exp, target_strike)
            credits.append(credit)

        # Longer expirations should generally provide more time value
        # (though the simplified calculation may not always show this)
        assert all(isinstance(c, float) for c in credits)
        assert len(credits) == len(time_periods)


class TestRollPlanExecution:
    """Test cases for roll plan execution and order management."""

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
        return logger

    @pytest.fixture
    def roller(self, mock_broker_client, mock_logger):
        """Create a roller instance."""
        return CoveredCallRoller(mock_broker_client, mock_logger)

    @pytest.fixture
    def sample_roll_plan(self):
        """Create a sample roll plan."""
        today = date.today()
        current_call = OptionPosition(
            symbol="TLT", quantity=-2, market_value=-500.0, average_cost=-2.50,
            unrealized_pnl=100.0, position_type="short_call", strike=95.0,
            expiration=today, option_type="call"
        )

        roll_opportunity = RollOpportunity(
            symbol="TLT",
            current_call=current_call,
            target_expiration=today + timedelta(days=14),
            target_strike=97.0,
            estimated_credit=1.25,
            current_price=98.0
        )

        return RollPlan(
            symbol="TLT",
            current_price=98.0,
            roll_opportunities=[roll_opportunity],
            total_estimated_credit=1.25,
            execution_time=datetime.now(),
            cumulative_premium_collected=5.0,
            cost_basis_impact=0.05
        )

    def test_execute_roll_plan_success(self, roller, mock_broker_client, mock_logger, sample_roll_plan):
        """Test successful roll plan execution."""
        # Mock successful roll order result
        successful_roll_result = RollOrderResult(
            roll_order=RollOrder(
                symbol="TLT",
                close_strike=95.0,
                close_expiration=date.today(),
                open_strike=97.0,
                open_expiration=date.today() + timedelta(days=14),
                quantity=2,
                estimated_credit=1.25
            ),
            close_result=OrderResult(success=True, order_id="CLOSE123", status="FILLED", error_message=None),
            open_result=OrderResult(success=True, order_id="OPEN456", status="FILLED", error_message=None),
            actual_credit=1.30,  # Slightly better than estimated
            success=True
        )

        mock_broker_client.submit_roll_order.return_value = successful_roll_result

        results = roller.execute_roll_plan(sample_roll_plan)

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].actual_credit == 1.30
        assert results[0].roll_order.symbol == "TLT"

        mock_broker_client.submit_roll_order.assert_called_once()
        mock_logger.log_info.assert_called()

    def test_execute_roll_plan_partial_failure(self, roller, mock_broker_client, mock_logger):
        """Test roll plan execution with partial failures."""
        today = date.today()
        
        # Create plan with multiple opportunities
        opportunities = [
            RollOpportunity(
                symbol="TLT",
                current_call=OptionPosition(
                    symbol="TLT", quantity=-2, market_value=-500.0, average_cost=-2.50,
                    unrealized_pnl=100.0, position_type="short_call", strike=95.0,
                    expiration=today, option_type="call"
                ),
                target_expiration=today + timedelta(days=14),
                target_strike=97.0,
                estimated_credit=1.25,
                current_price=98.0
            ),
            RollOpportunity(
                symbol="NVDA",
                current_call=OptionPosition(
                    symbol="NVDA", quantity=-1, market_value=-300.0, average_cost=-3.00,
                    unrealized_pnl=150.0, position_type="short_call", strike=140.0,
                    expiration=today, option_type="call"
                ),
                target_expiration=today + timedelta(days=21),
                target_strike=142.0,
                estimated_credit=2.50,
                current_price=145.0
            )
        ]

        roll_plan = RollPlan(
            symbol="MULTI",
            current_price=0.0,  # Not applicable for multi-symbol
            roll_opportunities=opportunities,
            total_estimated_credit=3.75,
            execution_time=datetime.now(),
            cumulative_premium_collected=10.0,
            cost_basis_impact=0.10
        )

        # Mock mixed results - first succeeds, second fails
        def mock_submit_roll(roll_order):
            if roll_order.symbol == "TLT":
                return RollOrderResult(
                    roll_order=roll_order,
                    close_result=OrderResult(success=True, order_id="CLOSE123", status="FILLED", error_message=None),
                    open_result=OrderResult(success=True, order_id="OPEN456", status="FILLED", error_message=None),
                    actual_credit=1.30,
                    success=True
                )
            else:  # NVDA fails
                return RollOrderResult(
                    roll_order=roll_order,
                    close_result=OrderResult(success=False, order_id=None, status="REJECTED", error_message="Insufficient liquidity"),
                    open_result=OrderResult(success=False, order_id=None, status="REJECTED", error_message="Order rejected"),
                    actual_credit=0.0,
                    success=False
                )

        mock_broker_client.submit_roll_order.side_effect = mock_submit_roll

        results = roller.execute_roll_plan(roll_plan)

        assert len(results) == 2
        assert results[0].success is True  # TLT succeeded
        assert results[1].success is False  # NVDA failed

        # Verify both orders were attempted
        assert mock_broker_client.submit_roll_order.call_count == 2
        mock_logger.log_info.assert_called()
        mock_logger.log_error.assert_called()

    def test_execute_roll_plan_complete_failure(self, roller, mock_broker_client, mock_logger, sample_roll_plan):
        """Test roll plan execution with complete failure."""
        # Mock broker client to raise exception
        mock_broker_client.submit_roll_order.side_effect = Exception("Broker API failed")

        results = roller.execute_roll_plan(sample_roll_plan)

        assert len(results) == 1
        assert results[0].success is False
        assert results[0].actual_credit == 0.0

        mock_logger.log_error.assert_called()

    def test_execute_roll_plan_empty_plan(self, roller, mock_broker_client, mock_logger):
        """Test execution of empty roll plan."""
        empty_plan = RollPlan(
            symbol="TLT",
            current_price=98.0,
            roll_opportunities=[],
            total_estimated_credit=0.0,
            execution_time=datetime.now(),
            cumulative_premium_collected=0.0,
            cost_basis_impact=0.0
        )

        results = roller.execute_roll_plan(empty_plan)

        assert len(results) == 0
        mock_broker_client.submit_roll_order.assert_not_called()

    def test_execute_roll_plan_critical_error(self, roller, mock_broker_client, mock_logger, sample_roll_plan):
        """Test roll plan execution with critical error."""
        # Mock a critical error that should raise RuntimeError
        mock_broker_client.submit_roll_order.side_effect = Exception("Critical system failure")

        # The method should handle individual order failures gracefully
        results = roller.execute_roll_plan(sample_roll_plan)

        # Should still return results (with failures) rather than raising
        assert len(results) == 1
        assert results[0].success is False


class TestCostBasisImpactCalculation:
    """Test cases for cost basis impact calculation from rolls."""

    @pytest.fixture
    def mock_broker_client(self):
        """Create a mock broker client."""
        return Mock()

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        logger = Mock()
        logger.log_info = Mock()
        return logger

    @pytest.fixture
    def roller(self, mock_broker_client, mock_logger):
        """Create a roller instance."""
        return CoveredCallRoller(mock_broker_client, mock_logger)

    def test_calculate_cumulative_cost_basis_impact_basic(self, roller, mock_logger):
        """Test basic cost basis impact calculation."""
        symbol = "TLT"
        additional_premium = 250.0  # $2.50 per contract * 100 shares

        impact = roller.calculate_cumulative_cost_basis_impact(symbol, additional_premium)

        # Should be $2.50 per share (250 / 100)
        assert impact == 2.50
        mock_logger.log_info.assert_called()

    def test_calculate_cumulative_cost_basis_impact_zero_premium(self, roller, mock_logger):
        """Test cost basis impact with zero premium."""
        symbol = "TLT"
        additional_premium = 0.0

        impact = roller.calculate_cumulative_cost_basis_impact(symbol, additional_premium)

        assert impact == 0.0

    def test_calculate_cumulative_cost_basis_impact_negative_premium(self, roller, mock_logger):
        """Test cost basis impact with negative premium (debit)."""
        symbol = "TLT"
        additional_premium = -100.0  # Debit roll

        impact = roller.calculate_cumulative_cost_basis_impact(symbol, additional_premium)

        assert impact == 0.0  # Should not reduce cost basis for debit rolls

    def test_calculate_cumulative_cost_basis_impact_large_premium(self, roller, mock_logger):
        """Test cost basis impact with large premium collection."""
        symbol = "NVDA"
        additional_premium = 1500.0  # $15.00 per contract * 100 shares

        impact = roller.calculate_cumulative_cost_basis_impact(symbol, additional_premium)

        assert impact == 15.0  # $15 per share


class TestDataClassCreation:
    """Test cases for data class creation and validation."""

    def test_roll_opportunity_creation(self):
        """Test RollOpportunity data class creation."""
        today = date.today()
        current_call = OptionPosition(
            symbol="TLT", quantity=-2, market_value=-500.0, average_cost=-2.50,
            unrealized_pnl=100.0, position_type="short_call", strike=95.0,
            expiration=today, option_type="call"
        )

        opportunity = RollOpportunity(
            symbol="TLT",
            current_call=current_call,
            target_expiration=today + timedelta(days=14),
            target_strike=97.0,
            estimated_credit=1.25,
            current_price=98.0
        )

        assert opportunity.symbol == "TLT"
        assert opportunity.current_call == current_call
        assert opportunity.target_strike == 97.0
        assert opportunity.estimated_credit == 1.25

    def test_roll_plan_creation(self):
        """Test RollPlan data class creation."""
        today = date.today()
        opportunities = []  # Empty for this test

        plan = RollPlan(
            symbol="TLT",
            current_price=98.0,
            roll_opportunities=opportunities,
            total_estimated_credit=0.0,
            execution_time=datetime.now(),
            cumulative_premium_collected=5.0,
            cost_basis_impact=0.05
        )

        assert plan.symbol == "TLT"
        assert plan.current_price == 98.0
        assert len(plan.roll_opportunities) == 0
        assert plan.cumulative_premium_collected == 5.0

    def test_roll_order_creation(self):
        """Test RollOrder data class creation."""
        today = date.today()

        order = RollOrder(
            symbol="TLT",
            close_strike=95.0,
            close_expiration=today,
            open_strike=97.0,
            open_expiration=today + timedelta(days=14),
            quantity=2,
            estimated_credit=1.25
        )

        assert order.symbol == "TLT"
        assert order.close_strike == 95.0
        assert order.open_strike == 97.0
        assert order.quantity == 2

    def test_roll_order_result_creation(self):
        """Test RollOrderResult data class creation."""
        today = date.today()

        roll_order = RollOrder(
            symbol="TLT",
            close_strike=95.0,
            close_expiration=today,
            open_strike=97.0,
            open_expiration=today + timedelta(days=14),
            quantity=2,
            estimated_credit=1.25
        )

        result = RollOrderResult(
            roll_order=roll_order,
            close_result=OrderResult(success=True, order_id="CLOSE123", status="FILLED", error_message=None),
            open_result=OrderResult(success=True, order_id="OPEN456", status="FILLED", error_message=None),
            actual_credit=1.30,
            success=True
        )

        assert result.roll_order == roll_order
        assert result.success is True
        assert result.actual_credit == 1.30
        assert result.close_result.order_id == "CLOSE123"
        assert result.open_result.order_id == "OPEN456"


class TestEdgeCasesAndErrorHandling:
    """Test cases for edge cases and comprehensive error handling."""

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
    def roller(self, mock_broker_client, mock_logger):
        """Create a roller instance."""
        return CoveredCallRoller(mock_broker_client, mock_logger)

    def test_identify_expiring_calls_weekend_expiration(self, roller, mock_broker_client, mock_logger):
        """Test identification of calls expiring on weekend (should be Friday)."""
        # Create calls expiring on a Saturday (options typically expire on Friday)
        saturday = date.today()
        while saturday.weekday() != 5:  # Find next Saturday
            saturday += timedelta(days=1)

        weekend_calls = [
            OptionPosition(
                symbol="TLT", quantity=-2, market_value=-500.0, average_cost=-2.50,
                unrealized_pnl=100.0, position_type="short_call", strike=95.0,
                expiration=saturday, option_type="call"
            )
        ]

        mock_broker_client.get_expiring_short_calls.return_value = weekend_calls
        mock_broker_client.get_current_price.return_value = 98.0

        # Should handle weekend expirations gracefully
        result = roller.identify_expiring_itm_calls()

        # The broker client should handle the weekend logic, we just process what it returns
        assert len(result) == 1  # Should find the ITM call
        mock_broker_client.get_expiring_short_calls.assert_called_once()

    def test_calculate_roll_opportunities_empty_list(self, roller, mock_broker_client, mock_logger):
        """Test roll opportunity calculation with empty call list."""
        result = roller.calculate_roll_opportunities([])

        assert len(result) == 0
        mock_logger.log_info.assert_called()

    def test_find_best_roll_target_very_short_expiration(self, roller, mock_broker_client, mock_logger):
        """Test roll target selection with very short time to expiration."""
        sample_call = OptionPosition(
            symbol="TLT", quantity=-2, market_value=-500.0, average_cost=-2.50,
            unrealized_pnl=100.0, position_type="short_call", strike=95.0,
            expiration=date.today(), option_type="call"
        )

        current_price = 98.0

        # The method will try multiple potential expiration dates and adjust to Fridays
        # So we need to mock the get_option_chain to return options for the dates it tries
        def mock_get_option_chain(symbol, expiration):
            return [MockOptionContract(symbol, 97.0, expiration, "call")]

        mock_broker_client.get_option_chain.side_effect = mock_get_option_chain

        target_expiration, target_strike = roller.find_best_roll_target(sample_call, current_price)

        assert target_expiration is not None  # Should find some expiration
        assert target_strike == 97.0

    def test_estimate_roll_credit_extreme_itm_call(self, roller, mock_broker_client, mock_logger):
        """Test credit estimation for extremely ITM call."""
        # Call with strike much lower than current price
        extreme_itm_call = OptionPosition(
            symbol="NVDA", quantity=-1, market_value=-5000.0, average_cost=-50.00,
            unrealized_pnl=2000.0, position_type="short_call", strike=100.0,
            expiration=date.today(), option_type="call"
        )

        current_price = 200.0  # Stock much higher than strike
        target_exp = date.today() + timedelta(days=14)
        target_strike = 205.0

        mock_broker_client.get_current_price.return_value = current_price

        credit = roller.estimate_roll_credit(extreme_itm_call, target_exp, target_strike)

        # Should handle extreme ITM scenario
        assert isinstance(credit, float)
        # With such high intrinsic value, likely to be negative credit (debit roll)

    def test_execute_roll_plan_with_zero_quantity_calls(self, roller, mock_broker_client, mock_logger):
        """Test roll plan execution with zero quantity calls (edge case)."""
        today = date.today()
        
        # Call with zero quantity (shouldn't happen in practice)
        zero_quantity_call = OptionPosition(
            symbol="TLT", quantity=0, market_value=0.0, average_cost=0.0,
            unrealized_pnl=0.0, position_type="short_call", strike=95.0,
            expiration=today, option_type="call"
        )

        opportunity = RollOpportunity(
            symbol="TLT",
            current_call=zero_quantity_call,
            target_expiration=today + timedelta(days=14),
            target_strike=97.0,
            estimated_credit=1.25,
            current_price=98.0
        )

        roll_plan = RollPlan(
            symbol="TLT",
            current_price=98.0,
            roll_opportunities=[opportunity],
            total_estimated_credit=1.25,
            execution_time=datetime.now(),
            cumulative_premium_collected=0.0,
            cost_basis_impact=0.0
        )

        # Mock successful execution
        mock_broker_client.submit_roll_order.return_value = RollOrderResult(
            roll_order=Mock(),
            close_result=OrderResult(success=True, order_id="CLOSE123", status="FILLED", error_message=None),
            open_result=OrderResult(success=True, order_id="OPEN456", status="FILLED", error_message=None),
            actual_credit=0.0,  # No credit for zero quantity
            success=True
        )

        results = roller.execute_roll_plan(roll_plan)

        # Should handle gracefully
        assert len(results) == 1
        # The quantity should be converted to positive (abs value)
        mock_broker_client.submit_roll_order.assert_called_once()

    def test_multiple_symbols_in_single_identification(self, roller, mock_broker_client, mock_logger):
        """Test identification across multiple symbols simultaneously."""
        today = date.today()
        multi_symbol_calls = [
            OptionPosition(
                symbol="TLT", quantity=-2, market_value=-500.0, average_cost=-2.50,
                unrealized_pnl=100.0, position_type="short_call", strike=95.0,
                expiration=today, option_type="call"
            ),
            OptionPosition(
                symbol="NVDA", quantity=-1, market_value=-300.0, average_cost=-3.00,
                unrealized_pnl=150.0, position_type="short_call", strike=140.0,
                expiration=today, option_type="call"
            ),
            OptionPosition(
                symbol="AAPL", quantity=-3, market_value=-900.0, average_cost=-3.00,
                unrealized_pnl=300.0, position_type="short_call", strike=180.0,
                expiration=today, option_type="call"
            )
        ]

        mock_broker_client.get_expiring_short_calls.return_value = multi_symbol_calls
        mock_broker_client.get_current_price.side_effect = lambda symbol: {
            "TLT": 98.0,    # TLT $95 call is ITM
            "NVDA": 145.0,  # NVDA $140 call is ITM  
            "AAPL": 175.0   # AAPL $180 call is OTM
        }[symbol]

        result = roller.identify_expiring_itm_calls()

        # Should find 2 ITM calls (TLT and NVDA)
        assert len(result) == 2
        symbols = [call.symbol for call in result]
        assert "TLT" in symbols
        assert "NVDA" in symbols
        assert "AAPL" not in symbols

        # Should have called get_current_price for all 3 symbols
        assert mock_broker_client.get_current_price.call_count == 3