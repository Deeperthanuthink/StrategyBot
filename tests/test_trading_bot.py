"""Integration tests for TradingBot."""

import pytest
import json
import tempfile
import os
from datetime import datetime, date
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from src.bot.trading_bot import TradingBot, ExecutionSummary
from src.order.order_manager import TradeResult
from src.alpaca.alpaca_client import OrderResult, OptionContract


class TestTradingBot:
    """Integration test cases for TradingBot."""

    @pytest.fixture
    def temp_config_file(self):
        """Create a temporary config file for testing."""
        config_data = {
            "symbols": ["NVDA", "AAPL", "GOOGL"],
            "strike_offset_percent": 5.0,
            "spread_width": 5.0,
            "contract_quantity": 1,
            "execution_day": "Tuesday",
            "execution_time_offset_minutes": 30,
            "expiration_offset_weeks": 1,
            "alpaca": {
                "api_key": "test_api_key",
                "api_secret": "test_api_secret",
                "base_url": "https://paper-api.alpaca.markets",
            },
            "logging": {"level": "INFO", "file_path": "logs/test_trading_bot.log"},
        }

        # Create temporary file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            json.dump(config_data, f)
            temp_path = f.name

        yield temp_path

        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    @pytest.fixture
    def trading_bot(self, temp_config_file):
        """Create a TradingBot instance with temp config."""
        return TradingBot(config_path=temp_config_file)

    def test_initialization_success(self, trading_bot):
        """Test successful TradingBot initialization."""
        # Mock Alpaca authentication
        with patch("src.bot.trading_bot.AlpacaClient") as MockAlpacaClient:
            mock_client = Mock()
            mock_client.authenticate.return_value = True
            MockAlpacaClient.return_value = mock_client

            result = trading_bot.initialize()

            assert result is True
            assert trading_bot._initialized is True
            assert trading_bot.config is not None
            assert trading_bot.logger is not None
            assert trading_bot.alpaca_client is not None
            assert trading_bot.strategy_calculator is not None
            assert trading_bot.order_manager is not None

    def test_initialization_auth_failure(self, trading_bot):
        """Test TradingBot initialization with authentication failure."""
        # Mock Alpaca authentication failure
        with patch("src.bot.trading_bot.AlpacaClient") as MockAlpacaClient:
            mock_client = Mock()
            mock_client.authenticate.return_value = False
            MockAlpacaClient.return_value = mock_client

            result = trading_bot.initialize()

            assert result is False
            assert trading_bot._initialized is False

    def test_initialization_missing_config(self):
        """Test TradingBot initialization with missing config file."""
        bot = TradingBot(config_path="nonexistent_config.json")

        result = bot.initialize()

        assert result is False

    def test_execute_trading_cycle_not_initialized(self, trading_bot):
        """Test execute_trading_cycle raises error when not initialized."""
        with pytest.raises(RuntimeError, match="not initialized"):
            trading_bot.execute_trading_cycle()

    @patch("src.bot.trading_bot.AlpacaClient")
    def test_execute_trading_cycle_success(self, MockAlpacaClient, trading_bot):
        """Test full trading cycle with successful trades."""
        # Setup mocks
        mock_client = Mock()
        mock_client.authenticate.return_value = True
        mock_client.is_market_open.return_value = True
        mock_client.get_current_price.side_effect = [
            145.50,
            180.25,
            140.75,
        ]  # Prices for NVDA, AAPL, GOOGL

        # Provide different option chains for different symbols to avoid rounding issues
        def get_option_chain_side_effect(symbol, expiration):
            if symbol == "NVDA":
                return [
                    OptionContract(
                        symbol="TEST",
                        strike=strike,
                        expiration=date(2025, 12, 6),
                        option_type="put",
                    )
                    for strike in [130.0, 133.0, 135.0, 138.0, 140.0, 145.0]
                ]
            elif symbol == "AAPL":
                return [
                    OptionContract(
                        symbol="TEST",
                        strike=strike,
                        expiration=date(2025, 12, 6),
                        option_type="put",
                    )
                    for strike in [165.0, 166.0, 170.0, 171.0, 175.0, 180.0]
                ]
            else:  # GOOGL
                return [
                    OptionContract(
                        symbol="TEST",
                        strike=strike,
                        expiration=date(2025, 12, 6),
                        option_type="put",
                    )
                    for strike in [128.0, 130.0, 133.0, 135.0, 138.0, 140.0]
                ]

        mock_client.get_option_chain.side_effect = get_option_chain_side_effect
        mock_client.submit_spread_order.return_value = OrderResult(
            success=True, order_id="order_123", status="accepted", error_message=None
        )
        MockAlpacaClient.return_value = mock_client

        # Initialize bot
        trading_bot.initialize()

        # Execute trading cycle
        summary = trading_bot.execute_trading_cycle()

        # Verify results
        assert isinstance(summary, ExecutionSummary)
        assert summary.total_symbols == 3
        assert summary.successful_trades == 3
        assert summary.failed_trades == 0
        assert len(summary.trade_results) == 3

        # Verify all trades were successful
        for result in summary.trade_results:
            assert result.success is True
            assert result.order_id is not None

    @patch("src.bot.trading_bot.AlpacaClient")
    def test_execute_trading_cycle_market_closed(self, MockAlpacaClient, trading_bot):
        """Test trading cycle when market is closed."""
        # Setup mocks
        mock_client = Mock()
        mock_client.authenticate.return_value = True
        mock_client.is_market_open.return_value = False  # Market closed
        mock_client.get_current_price.side_effect = [145.50, 180.25, 140.75]
        mock_client.get_option_chain.return_value = [
            OptionContract(
                symbol="TEST",
                strike=strike,
                expiration=date(2025, 12, 6),
                option_type="put",
            )
            for strike in [130.0, 135.0, 138.0, 140.0, 145.0, 150.0]
        ]
        mock_client.submit_spread_order.return_value = OrderResult(
            success=True, order_id="order_123", status="accepted", error_message=None
        )
        MockAlpacaClient.return_value = mock_client

        # Initialize bot
        trading_bot.initialize()

        # Execute trading cycle (should continue despite market closed warning)
        summary = trading_bot.execute_trading_cycle()

        # Verify execution continued
        assert isinstance(summary, ExecutionSummary)
        assert summary.total_symbols == 3

    @patch("src.bot.trading_bot.AlpacaClient")
    def test_execute_trading_cycle_partial_failures(self, MockAlpacaClient, trading_bot):
        """Test trading cycle with some failed trades."""
        # Setup mocks
        mock_client = Mock()
        mock_client.authenticate.return_value = True
        mock_client.is_market_open.return_value = True

        # First symbol succeeds, second fails (price unavailable), third succeeds
        def get_price_side_effect(symbol):
            if symbol == "AAPL":
                raise ValueError("Price data unavailable")
            return 145.50

        mock_client.get_current_price.side_effect = get_price_side_effect
        mock_client.get_option_chain.return_value = [
            OptionContract(
                symbol="TEST",
                strike=strike,
                expiration=date(2025, 12, 6),
                option_type="put",
            )
            for strike in [130.0, 135.0, 138.0, 140.0, 145.0, 150.0]
        ]
        mock_client.submit_spread_order.return_value = OrderResult(
            success=True, order_id="order_123", status="accepted", error_message=None
        )
        MockAlpacaClient.return_value = mock_client

        # Initialize bot
        trading_bot.initialize()

        # Execute trading cycle
        summary = trading_bot.execute_trading_cycle()

        # Verify results
        assert isinstance(summary, ExecutionSummary)
        assert summary.total_symbols == 3
        assert summary.successful_trades == 2
        assert summary.failed_trades == 1

        # Verify AAPL failed
        aapl_result = next(r for r in summary.trade_results if r.symbol == "AAPL")
        assert aapl_result.success is False
        assert (
            "Price data unavailable" in aapl_result.error_message
            or "Data error" in aapl_result.error_message
        )

    @patch("src.bot.trading_bot.AlpacaClient")
    def test_execute_trading_cycle_all_failures(self, MockAlpacaClient, trading_bot):
        """Test trading cycle where all trades fail."""
        # Setup mocks
        mock_client = Mock()
        mock_client.authenticate.return_value = True
        mock_client.is_market_open.return_value = True
        mock_client.get_current_price.side_effect = ValueError("Price data unavailable")
        MockAlpacaClient.return_value = mock_client

        # Initialize bot
        trading_bot.initialize()

        # Execute trading cycle
        summary = trading_bot.execute_trading_cycle()

        # Verify results
        assert isinstance(summary, ExecutionSummary)
        assert summary.total_symbols == 3
        assert summary.successful_trades == 0
        assert summary.failed_trades == 3

    @patch("src.bot.trading_bot.AlpacaClient")
    def test_process_symbol_success(self, MockAlpacaClient, trading_bot):
        """Test processing a single symbol successfully."""
        # Setup mocks
        mock_client = Mock()
        mock_client.authenticate.return_value = True
        mock_client.get_current_price.return_value = 145.50
        mock_client.get_option_chain.return_value = [
            OptionContract(
                symbol="TEST",
                strike=strike,
                expiration=date(2025, 12, 6),
                option_type="put",
            )
            for strike in [130.0, 135.0, 138.0, 140.0, 145.0, 150.0]
        ]
        mock_client.submit_spread_order.return_value = OrderResult(
            success=True, order_id="order_123", status="accepted", error_message=None
        )
        MockAlpacaClient.return_value = mock_client

        # Initialize bot
        trading_bot.initialize()

        # Process single symbol
        result = trading_bot.process_symbol("NVDA")

        # Verify result
        assert isinstance(result, TradeResult)
        assert result.symbol == "NVDA"
        assert result.success is True
        assert result.order_id == "order_123"
        assert result.short_strike > 0
        assert result.long_strike > 0
        assert result.short_strike > result.long_strike

    @patch("src.bot.trading_bot.AlpacaClient")
    def test_process_symbol_price_unavailable(self, MockAlpacaClient, trading_bot):
        """Test processing symbol when price is unavailable."""
        # Setup mocks
        mock_client = Mock()
        mock_client.authenticate.return_value = True
        mock_client.get_current_price.side_effect = ValueError("Price data unavailable")
        MockAlpacaClient.return_value = mock_client

        # Initialize bot
        trading_bot.initialize()

        # Process single symbol
        result = trading_bot.process_symbol("NVDA")

        # Verify result
        assert isinstance(result, TradeResult)
        assert result.symbol == "NVDA"
        assert result.success is False
        assert (
            "Price data unavailable" in result.error_message or "Data error" in result.error_message
        )

    @patch("src.bot.trading_bot.AlpacaClient")
    def test_process_symbol_option_chain_unavailable(self, MockAlpacaClient, trading_bot):
        """Test processing symbol when option chain is unavailable."""
        # Setup mocks
        mock_client = Mock()
        mock_client.authenticate.return_value = True
        mock_client.get_current_price.return_value = 145.50
        mock_client.get_option_chain.side_effect = ValueError("Option chain unavailable")
        MockAlpacaClient.return_value = mock_client

        # Initialize bot
        trading_bot.initialize()

        # Process single symbol
        result = trading_bot.process_symbol("NVDA")

        # Verify result
        assert isinstance(result, TradeResult)
        assert result.symbol == "NVDA"
        assert result.success is False
        assert "Option chain unavailable" in result.error_message

    @patch("src.bot.trading_bot.AlpacaClient")
    def test_log_execution_summary(self, MockAlpacaClient, trading_bot):
        """Test execution summary logging."""
        # Setup mocks
        mock_client = Mock()
        mock_client.authenticate.return_value = True
        MockAlpacaClient.return_value = mock_client

        # Initialize bot
        trading_bot.initialize()

        # Create test summary
        trade_results = [
            TradeResult(
                symbol="NVDA",
                success=True,
                order_id="order_1",
                short_strike=138.0,
                long_strike=133.0,
                expiration=date(2025, 12, 6),
                quantity=1,
                filled_price=0.50,
                error_message=None,
                timestamp=datetime.now(),
            ),
            TradeResult(
                symbol="AAPL",
                success=False,
                order_id=None,
                short_strike=170.0,
                long_strike=165.0,
                expiration=date(2025, 12, 6),
                quantity=1,
                filled_price=None,
                error_message="Insufficient buying power",
                timestamp=datetime.now(),
            ),
        ]

        summary = ExecutionSummary(
            execution_date=datetime.now(),
            total_symbols=2,
            successful_trades=1,
            failed_trades=1,
            trade_results=trade_results,
        )

        # Log summary (should not raise exception)
        trading_bot._log_execution_summary(summary)

        # Verify logger was called
        assert trading_bot.logger is not None

    @patch("src.bot.trading_bot.AlpacaClient")
    def test_shutdown(self, MockAlpacaClient, trading_bot):
        """Test graceful shutdown."""
        # Setup mocks
        mock_client = Mock()
        mock_client.authenticate.return_value = True
        mock_client._api = Mock()
        MockAlpacaClient.return_value = mock_client

        # Initialize bot
        trading_bot.initialize()
        assert trading_bot._initialized is True

        # Shutdown
        trading_bot.shutdown()

        # Verify cleanup
        assert trading_bot._initialized is False
        assert trading_bot.alpaca_client._api is None

    @patch("src.bot.trading_bot.AlpacaClient")
    def test_shutdown_without_initialization(self, MockAlpacaClient, trading_bot):
        """Test shutdown when bot was never initialized."""
        # Shutdown without initialization (should not raise exception)
        trading_bot.shutdown()

        # Should complete without error
        assert trading_bot._initialized is False
