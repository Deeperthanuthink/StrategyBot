"""Integration tests for tiered covered calls end-to-end strategy execution."""

import pytest
from datetime import date, timedelta
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass

from src.positions.position_service import PositionService
from src.strategy.tiered_covered_call_strategy import TieredCoveredCallCalculator
from src.positions.models import PositionSummary, OptionPosition, CoveredCallOrder
from src.brokers.base_client import OptionContract


@dataclass
class MockPosition:
    """Mock position for testing."""
    symbol: str
    quantity: int
    market_value: float = 0.0
    average_cost: float = 0.0


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


class TestTieredCoveredCallsIntegration:
    """Integration tests for end-to-end tiered covered calls strategy execution."""

    @pytest.fixture
    def mock_broker_client(self):
        """Create a comprehensive mock broker client."""
        client = Mock()
        client.get_current_price = Mock()
        client.get_position = Mock()
        client.get_option_chain = Mock()
        client.submit_multiple_covered_call_orders = Mock()
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
        """Create a PositionService instance."""
        return PositionService(mock_broker_client, mock_logger)

    @pytest.fixture
    def strategy_calculator(self, mock_broker_client, mock_logger):
        """Create a TieredCoveredCallCalculator instance."""
        return TieredCoveredCallCalculator(mock_broker_client, logger=mock_logger)

    def test_end_to_end_strategy_execution_success(self, position_service, strategy_calculator, mock_broker_client, mock_logger):
        """Test complete end-to-end strategy execution with successful outcome."""
        # Setup mock broker responses
        mock_broker_client.get_current_price.return_value = 150.0
        mock_broker_client.get_position.return_value = MockPosition("NVDA", 600)

        # Setup option chain data for multiple expirations
        today = date.today()
        exp1 = today + timedelta(days=14)
        exp2 = today + timedelta(days=28)
        exp3 = today + timedelta(days=42)

        def mock_get_option_chain(symbol, expiration):
            return [
                MockOptionContract(symbol, 152.5, expiration, "call"),
                MockOptionContract(symbol, 155.0, expiration, "call"),
                MockOptionContract(symbol, 157.5, expiration, "call"),
                MockOptionContract(symbol, 160.0, expiration, "call"),
                MockOptionContract(symbol, 162.5, expiration, "call"),
            ]

        mock_broker_client.get_option_chain.side_effect = mock_get_option_chain

        # Step 1: Get position summary
        position_summary = position_service.get_long_positions("NVDA")

        assert position_summary.symbol == "NVDA"
        assert position_summary.total_shares == 600
        assert position_summary.available_shares == 600
        assert position_summary.current_price == 150.0

        # Step 2: Calculate strategy
        strategy_plan = strategy_calculator.calculate_strategy(position_summary)

        assert strategy_plan.symbol == "NVDA"
        assert strategy_plan.current_price == 150.0
        assert strategy_plan.total_shares == 600
        assert len(strategy_plan.expiration_groups) == 3
        assert strategy_plan.total_contracts == 6  # 600 shares / 100 = 6 contracts
        assert strategy_plan.estimated_premium > 0

        # Verify expiration groups
        for i, group in enumerate(strategy_plan.expiration_groups):
            assert group.num_contracts == 2  # 200 shares per group / 100
            assert group.shares_used == 200
            assert group.strike_price > 150.0  # All strikes should be OTM
            assert group.estimated_premium_per_contract > 0

        # Verify incremental strikes
        strikes = [group.strike_price for group in strategy_plan.expiration_groups]
        assert strikes[0] == 152.5  # First OTM strike
        assert strikes[1] == 155.0  # Next higher strike
        assert strikes[2] == 157.5  # Next higher strike

        # Step 3: Validate orders
        orders = [
            CoveredCallOrder(
                symbol=group.expiration_date.strftime("%Y%m%d"),  # Mock symbol format
                strike=group.strike_price,
                expiration=group.expiration_date,
                quantity=group.num_contracts,
                underlying_shares=group.shares_used
            )
            for group in strategy_plan.expiration_groups
        ]

        is_valid, validation_summary = position_service.validate_covered_call_orders("NVDA", orders)

        assert is_valid is True
        assert validation_summary.validation_passed is True
        assert validation_summary.total_shares == 600
        assert validation_summary.available_shares == 600
        assert validation_summary.requested_contracts == 6

        # Verify logging occurred
        mock_logger.log_info.assert_called()

    def test_end_to_end_with_insufficient_shares(self, position_service, strategy_calculator, mock_broker_client, mock_logger):
        """Test end-to-end execution with insufficient shares scenario."""
        # Setup mock broker responses - insufficient shares
        mock_broker_client.get_current_price.return_value = 150.0
        mock_broker_client.get_position.return_value = MockPosition("NVDA", 250)  # Only 250 shares

        # Step 1: Get position summary
        position_summary = position_service.get_long_positions("NVDA")

        assert position_summary.total_shares == 250
        assert position_summary.available_shares == 250

        # Step 2: Attempt strategy calculation - should fail due to minimum requirements
        with pytest.raises(ValueError, match="Strategy validation failed"):
            strategy_calculator.calculate_strategy(position_summary)

        mock_logger.log_error.assert_called()

    def test_end_to_end_with_existing_short_calls(self, position_service, strategy_calculator, mock_broker_client, mock_logger):
        """Test end-to-end execution accounting for existing short calls."""
        # Setup mock broker responses
        mock_broker_client.get_current_price.return_value = 150.0
        mock_broker_client.get_position.return_value = MockPosition("NVDA", 800)

        # Create position summary with existing short calls
        existing_short_calls = [
            OptionPosition(
                symbol="NVDA", quantity=2, market_value=-1000.0, average_cost=-5.0,
                unrealized_pnl=200.0, position_type="short_call", strike=160.0,
                expiration=date.today() + timedelta(days=30), option_type="call"
            )
        ]

        # Mock the position service to return existing short calls
        with patch.object(position_service, 'get_existing_short_calls', return_value=existing_short_calls):
            # Manually create position summary with reduced available shares
            position_summary = PositionSummary(
                symbol="NVDA",
                total_shares=800,
                available_shares=600,  # 800 - 200 (covered by existing calls)
                current_price=150.0,
                long_options=[],
                existing_short_calls=existing_short_calls
            )

            # Setup option chain
            today = date.today()
            exp1 = today + timedelta(days=14)
            exp2 = today + timedelta(days=28)
            exp3 = today + timedelta(days=42)

            def mock_get_option_chain(symbol, expiration):
                return [
                    MockOptionContract(symbol, 152.5, expiration, "call"),
                    MockOptionContract(symbol, 155.0, expiration, "call"),
                    MockOptionContract(symbol, 157.5, expiration, "call"),
                ]

            mock_broker_client.get_option_chain.side_effect = mock_get_option_chain

            # Calculate strategy with reduced available shares
            strategy_plan = strategy_calculator.calculate_strategy(position_summary)

            assert strategy_plan.total_shares == 600  # Available shares, not total shares
            assert strategy_plan.total_contracts == 6  # Based on available shares
            assert len(strategy_plan.expiration_groups) == 3

    def test_end_to_end_with_api_failures(self, position_service, strategy_calculator, mock_broker_client, mock_logger):
        """Test end-to-end execution with various API failures."""
        # Test price API failure
        mock_broker_client.get_current_price.side_effect = Exception("Price API failed")

        with pytest.raises(RuntimeError, match="Error retrieving positions"):
            position_service.get_long_positions("NVDA")

        mock_logger.error.assert_called()

        # Reset mocks
        mock_broker_client.reset_mock()
        mock_logger.reset_mock()

        # Test option chain API failure
        mock_broker_client.get_current_price.return_value = 150.0
        mock_broker_client.get_position.return_value = MockPosition("NVDA", 600)
        mock_broker_client.get_option_chain.side_effect = Exception("Option chain API failed")

        position_summary = position_service.get_long_positions("NVDA")

        with pytest.raises(ValueError, match="Error calculating tiered covered call strategy"):
            strategy_calculator.calculate_strategy(position_summary)

        mock_logger.log_error.assert_called()

    def test_end_to_end_with_limited_option_liquidity(self, position_service, strategy_calculator, mock_broker_client, mock_logger):
        """Test end-to-end execution with limited option liquidity."""
        # Setup mock broker responses
        mock_broker_client.get_current_price.return_value = 150.0
        mock_broker_client.get_position.return_value = MockPosition("NVDA", 600)

        # Setup limited option chain - only one strike available
        today = date.today()
        exp1 = today + timedelta(days=14)
        exp2 = today + timedelta(days=28)

        def mock_get_option_chain(symbol, expiration):
            if expiration == exp1:
                return [MockOptionContract(symbol, 155.0, expiration, "call")]
            else:
                return [MockOptionContract(symbol, 155.0, expiration, "call")]  # Same strike

        mock_broker_client.get_option_chain.side_effect = mock_get_option_chain

        # Get position summary
        position_summary = position_service.get_long_positions("NVDA")

        # Calculate strategy - should handle limited strikes
        strategy_plan = strategy_calculator.calculate_strategy(position_summary)

        # Should still create a plan, but with same strikes
        assert len(strategy_plan.expiration_groups) >= 2
        strikes = [group.strike_price for group in strategy_plan.expiration_groups]
        # All strikes might be the same due to limited liquidity
        assert all(strike == 155.0 for strike in strikes)

    def test_end_to_end_with_high_priced_stock(self, position_service, strategy_calculator, mock_broker_client, mock_logger):
        """Test end-to-end execution with high-priced stock."""
        # Setup mock broker responses for high-priced stock
        mock_broker_client.get_current_price.return_value = 1500.0  # High price like BRK.A
        mock_broker_client.get_position.return_value = MockPosition("BRK.A", 300)

        # Setup option chain with wide strike intervals
        today = date.today()
        exp1 = today + timedelta(days=14)
        exp2 = today + timedelta(days=28)
        exp3 = today + timedelta(days=42)

        def mock_get_option_chain(symbol, expiration):
            return [
                MockOptionContract(symbol, 1510.0, expiration, "call"),
                MockOptionContract(symbol, 1520.0, expiration, "call"),
                MockOptionContract(symbol, 1530.0, expiration, "call"),
                MockOptionContract(symbol, 1540.0, expiration, "call"),
            ]

        mock_broker_client.get_option_chain.side_effect = mock_get_option_chain

        # Execute end-to-end
        position_summary = position_service.get_long_positions("BRK.A")
        strategy_plan = strategy_calculator.calculate_strategy(position_summary)

        assert strategy_plan.symbol == "BRK.A"
        assert strategy_plan.current_price == 1500.0
        assert strategy_plan.total_contracts == 3  # 300 shares / 100
        assert all(group.strike_price > 1500.0 for group in strategy_plan.expiration_groups)

    def test_end_to_end_with_low_priced_stock(self, position_service, strategy_calculator, mock_broker_client, mock_logger):
        """Test end-to-end execution with low-priced stock."""
        # Setup mock broker responses for low-priced stock
        mock_broker_client.get_current_price.return_value = 5.0  # Low price
        mock_broker_client.get_position.return_value = MockPosition("SIRI", 2000)

        # Setup option chain with narrow strike intervals
        today = date.today()
        exp1 = today + timedelta(days=14)
        exp2 = today + timedelta(days=28)
        exp3 = today + timedelta(days=42)

        def mock_get_option_chain(symbol, expiration):
            return [
                MockOptionContract(symbol, 5.5, expiration, "call"),
                MockOptionContract(symbol, 6.0, expiration, "call"),
                MockOptionContract(symbol, 6.5, expiration, "call"),
                MockOptionContract(symbol, 7.0, expiration, "call"),
            ]

        mock_broker_client.get_option_chain.side_effect = mock_get_option_chain

        # Execute end-to-end
        position_summary = position_service.get_long_positions("SIRI")
        strategy_plan = strategy_calculator.calculate_strategy(position_summary)

        assert strategy_plan.symbol == "SIRI"
        assert strategy_plan.current_price == 5.0
        assert strategy_plan.total_contracts == 20  # 2000 shares / 100
        assert all(group.strike_price > 5.0 for group in strategy_plan.expiration_groups)

    def test_end_to_end_validation_comprehensive(self, position_service, strategy_calculator, mock_broker_client, mock_logger):
        """Test comprehensive validation throughout end-to-end execution."""
        # Setup mock broker responses
        mock_broker_client.get_current_price.return_value = 150.0
        mock_broker_client.get_position.return_value = MockPosition("NVDA", 500)

        # Setup option chain
        today = date.today()
        exp1 = today + timedelta(days=14)
        exp2 = today + timedelta(days=28)
        exp3 = today + timedelta(days=42)

        def mock_get_option_chain(symbol, expiration):
            return [
                MockOptionContract(symbol, 152.5, expiration, "call"),
                MockOptionContract(symbol, 155.0, expiration, "call"),
                MockOptionContract(symbol, 157.5, expiration, "call"),
            ]

        mock_broker_client.get_option_chain.side_effect = mock_get_option_chain

        # Step 1: Position validation
        position_summary = position_service.get_long_positions("NVDA")
        validation_summary = position_service.get_position_validation_summary("NVDA")

        assert validation_summary.validation_passed is True
        assert validation_summary.max_contracts_allowed == 5  # 500 shares / 100

        # Step 2: Strategy calculation with validation
        strategy_plan = strategy_calculator.calculate_strategy(position_summary)

        # Step 3: Individual order validation
        for group in strategy_plan.expiration_groups:
            validation_result = position_service.validate_single_covered_call(
                "NVDA", group.strike_price, group.expiration_date, group.num_contracts
            )
            assert validation_result.is_valid is True

        # Step 4: Comprehensive order validation
        orders = [
            CoveredCallOrder(
                symbol="NVDA",
                strike=group.strike_price,
                expiration=group.expiration_date,
                quantity=group.num_contracts,
                underlying_shares=group.shares_used
            )
            for group in strategy_plan.expiration_groups
        ]

        is_valid, comprehensive_summary = position_service.validate_covered_call_orders("NVDA", orders)

        assert is_valid is True
        assert comprehensive_summary.validation_passed is True
        assert comprehensive_summary.requested_contracts == strategy_plan.total_contracts

    def test_end_to_end_error_recovery(self, position_service, strategy_calculator, mock_broker_client, mock_logger):
        """Test error recovery and graceful degradation in end-to-end execution."""
        # Setup initial successful responses
        mock_broker_client.get_current_price.return_value = 150.0
        mock_broker_client.get_position.return_value = MockPosition("NVDA", 600)

        # Setup option chain that fails for some expirations
        today = date.today()
        exp1 = today + timedelta(days=14)
        exp2 = today + timedelta(days=28)
        exp3 = today + timedelta(days=42)

        def mock_get_option_chain(symbol, expiration):
            if expiration == exp2:
                raise Exception("API timeout for this expiration")
            return [
                MockOptionContract(symbol, 152.5, expiration, "call"),
                MockOptionContract(symbol, 155.0, expiration, "call"),
                MockOptionContract(symbol, 157.5, expiration, "call"),
            ]

        mock_broker_client.get_option_chain.side_effect = mock_get_option_chain

        # Position service should succeed
        position_summary = position_service.get_long_positions("NVDA")
        assert position_summary.symbol == "NVDA"

        # Strategy calculation should fail due to option chain error
        with pytest.raises(ValueError, match="Error calculating tiered covered call strategy"):
            strategy_calculator.calculate_strategy(position_summary)

        # Verify error was logged
        mock_logger.log_error.assert_called()

    def test_end_to_end_performance_with_large_positions(self, position_service, strategy_calculator, mock_broker_client, mock_logger):
        """Test end-to-end execution performance with large positions."""
        # Setup mock broker responses for large position
        mock_broker_client.get_current_price.return_value = 150.0
        mock_broker_client.get_position.return_value = MockPosition("NVDA", 5000)  # Large position

        # Setup option chain
        today = date.today()
        exp1 = today + timedelta(days=14)
        exp2 = today + timedelta(days=28)
        exp3 = today + timedelta(days=42)

        def mock_get_option_chain(symbol, expiration):
            return [
                MockOptionContract(symbol, 152.5, expiration, "call"),
                MockOptionContract(symbol, 155.0, expiration, "call"),
                MockOptionContract(symbol, 157.5, expiration, "call"),
                MockOptionContract(symbol, 160.0, expiration, "call"),
            ]

        mock_broker_client.get_option_chain.side_effect = mock_get_option_chain

        # Execute end-to-end
        position_summary = position_service.get_long_positions("NVDA")
        strategy_plan = strategy_calculator.calculate_strategy(position_summary)

        assert strategy_plan.total_shares == 5000
        assert strategy_plan.total_contracts == 50  # 5000 shares / 100

        # Verify share division handles large quantities correctly
        total_shares_used = sum(group.shares_used for group in strategy_plan.expiration_groups)
        assert total_shares_used == 5000

        # Verify all groups have reasonable contract quantities
        for group in strategy_plan.expiration_groups:
            assert group.num_contracts > 0
            assert group.shares_used == group.num_contracts * 100