"""Unit tests for Scheduler."""

import pytest
import json
import tempfile
import os
from datetime import datetime, time as dt_time
from unittest.mock import Mock, patch, MagicMock, call
import schedule

from src.scheduler.scheduler import Scheduler
from src.config.models import Config, AlpacaCredentials, LoggingConfig
from src.bot.trading_bot import TradingBot, ExecutionSummary


class TestScheduler:
    """Test cases for Scheduler."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock Config object."""
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
    def temp_config_file(self):
        """Create a temporary config file for testing."""
        config_data = {
            "symbols": ["NVDA", "AAPL"],
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
            "logging": {"level": "INFO", "file_path": "logs/test_scheduler.log"},
        }

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            json.dump(config_data, f)
            temp_path = f.name

        yield temp_path

        if os.path.exists(temp_path):
            os.unlink(temp_path)

    @pytest.fixture
    def mock_trading_bot(self, temp_config_file):
        """Create a mock TradingBot."""
        bot = TradingBot(config_path=temp_config_file)
        bot.logger = Mock()
        bot._initialized = True
        return bot

    @pytest.fixture
    def scheduler(self, mock_config, mock_trading_bot):
        """Create a Scheduler instance."""
        return Scheduler(config=mock_config, trading_bot=mock_trading_bot)

    def test_initialization(self, mock_config, mock_trading_bot):
        """Test Scheduler initialization."""
        scheduler = Scheduler(config=mock_config, trading_bot=mock_trading_bot)

        assert scheduler.config == mock_config
        assert scheduler.trading_bot == mock_trading_bot
        assert scheduler._running is False
        assert scheduler._scheduled_time is None

    def test_calculate_execution_time_default_offset(self, mock_config, mock_trading_bot):
        """Test execution time calculation with default 30-minute offset."""
        scheduler = Scheduler(config=mock_config, trading_bot=mock_trading_bot)

        # Market opens at 9:30 AM, offset is 30 minutes
        # Expected execution time: 10:00 AM
        execution_time = scheduler._calculate_execution_time()

        assert isinstance(execution_time, dt_time)
        assert execution_time.hour == 10
        assert execution_time.minute == 0

    def test_calculate_execution_time_custom_offset(self, mock_config, mock_trading_bot):
        """Test execution time calculation with custom offset."""
        # Set custom offset of 60 minutes
        mock_config.execution_time_offset_minutes = 60
        scheduler = Scheduler(config=mock_config, trading_bot=mock_trading_bot)

        # Market opens at 9:30 AM, offset is 60 minutes
        # Expected execution time: 10:30 AM
        execution_time = scheduler._calculate_execution_time()

        assert isinstance(execution_time, dt_time)
        assert execution_time.hour == 10
        assert execution_time.minute == 30

    def test_calculate_execution_time_zero_offset(self, mock_config, mock_trading_bot):
        """Test execution time calculation with zero offset."""
        # Set offset to 0 minutes
        mock_config.execution_time_offset_minutes = 0
        scheduler = Scheduler(config=mock_config, trading_bot=mock_trading_bot)

        # Market opens at 9:30 AM, offset is 0 minutes
        # Expected execution time: 9:30 AM
        execution_time = scheduler._calculate_execution_time()

        assert isinstance(execution_time, dt_time)
        assert execution_time.hour == 9
        assert execution_time.minute == 30

    def test_calculate_execution_time_large_offset(self, mock_config, mock_trading_bot):
        """Test execution time calculation with large offset crossing hour boundary."""
        # Set offset to 150 minutes (2.5 hours)
        mock_config.execution_time_offset_minutes = 150
        scheduler = Scheduler(config=mock_config, trading_bot=mock_trading_bot)

        # Market opens at 9:30 AM, offset is 150 minutes
        # Expected execution time: 12:00 PM
        execution_time = scheduler._calculate_execution_time()

        assert isinstance(execution_time, dt_time)
        assert execution_time.hour == 12
        assert execution_time.minute == 0

    @patch("src.scheduler.scheduler.schedule")
    def test_schedule_execution(self, mock_schedule, scheduler):
        """Test scheduling execution on configured day and time."""
        # Setup mock schedule
        mock_job = Mock()
        mock_job.at.return_value = mock_job
        mock_job.do.return_value = None
        mock_schedule.every.return_value.tuesday = mock_job

        # Schedule execution
        scheduler.schedule_execution()

        # Verify schedule was set up correctly
        assert scheduler._scheduled_time is not None
        assert scheduler._scheduled_time.hour == 10  # 9:30 + 30 minutes
        assert scheduler._scheduled_time.minute == 0

        # Verify schedule.every().tuesday.at().do() was called
        mock_schedule.every.assert_called_once()
        mock_job.at.assert_called_once_with("10:00")
        mock_job.do.assert_called_once()

    @patch("src.scheduler.scheduler.schedule")
    def test_schedule_execution_different_day(self, mock_schedule, mock_config, mock_trading_bot):
        """Test scheduling execution on different day of week."""
        # Change execution day to Friday
        mock_config.execution_day = "Friday"
        scheduler = Scheduler(config=mock_config, trading_bot=mock_trading_bot)

        # Setup mock schedule
        mock_job = Mock()
        mock_job.at.return_value = mock_job
        mock_job.do.return_value = None
        mock_schedule.every.return_value.friday = mock_job

        # Schedule execution
        scheduler.schedule_execution()

        # Verify schedule was set up for Friday
        mock_schedule.every.assert_called_once()
        mock_job.at.assert_called_once_with("10:00")
        mock_job.do.assert_called_once()

    def test_execute_trading_cycle_success(self, scheduler, mock_trading_bot):
        """Test successful execution of trading cycle."""
        # Setup mock execution summary
        mock_summary = ExecutionSummary(
            execution_date=datetime.now(),
            total_symbols=2,
            successful_trades=2,
            failed_trades=0,
            trade_results=[],
        )
        mock_trading_bot.execute_trading_cycle = Mock(return_value=mock_summary)

        # Execute trading cycle
        scheduler._execute_trading_cycle()

        # Verify trading bot was called
        mock_trading_bot.execute_trading_cycle.assert_called_once()

        # Verify logging
        assert mock_trading_bot.logger.log_info.call_count >= 2

    def test_execute_trading_cycle_with_error(self, scheduler, mock_trading_bot):
        """Test execution of trading cycle with error."""
        # Setup mock to raise exception
        mock_trading_bot.execute_trading_cycle = Mock(side_effect=Exception("Test error"))

        # Execute trading cycle (should not raise exception)
        scheduler._execute_trading_cycle()

        # Verify error was logged
        mock_trading_bot.logger.log_error.assert_called_once()
        error_call = mock_trading_bot.logger.log_error.call_args
        assert "Error during scheduled trading cycle execution" in error_call[0][0]

    @patch("src.scheduler.scheduler.time.sleep")
    @patch("src.scheduler.scheduler.schedule")
    def test_run_loop(self, mock_schedule, mock_sleep, scheduler):
        """Test scheduler run loop."""
        # Setup mock to stop after 3 iterations
        call_count = [0]

        def side_effect(*args):
            call_count[0] += 1
            if call_count[0] >= 3:
                scheduler._running = False

        mock_sleep.side_effect = side_effect
        mock_schedule.run_pending = Mock()

        # Run scheduler
        scheduler.run()

        # Verify schedule.run_pending was called multiple times
        assert mock_schedule.run_pending.call_count >= 3

        # Verify sleep was called with 60 seconds
        for call_args in mock_sleep.call_args_list:
            assert call_args[0][0] == 60

    @patch("src.scheduler.scheduler.time.sleep")
    @patch("src.scheduler.scheduler.schedule")
    def test_run_loop_with_error_recovery(self, mock_schedule, mock_sleep, scheduler):
        """Test scheduler run loop handles errors and continues."""
        # Setup mock to raise exception once, then stop
        call_count = [0]

        def run_pending_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Test error")
            elif call_count[0] >= 2:
                scheduler._running = False

        mock_schedule.run_pending.side_effect = run_pending_side_effect
        mock_sleep.return_value = None

        # Run scheduler
        scheduler.run()

        # Verify error was logged but execution continued
        assert mock_schedule.run_pending.call_count >= 2
        scheduler.trading_bot.logger.log_error.assert_called()

    @patch("src.scheduler.scheduler.time.sleep")
    @patch("src.scheduler.scheduler.schedule")
    def test_stop(self, mock_schedule, mock_sleep, scheduler):
        """Test stopping the scheduler."""

        # Setup mock to call stop after 1 iteration
        def side_effect(*args):
            scheduler.stop()

        mock_sleep.side_effect = side_effect
        mock_schedule.run_pending = Mock()
        mock_schedule.clear = Mock()

        # Run scheduler
        scheduler.run()

        # Verify scheduler stopped
        assert scheduler._running is False

        # Verify schedule was cleared
        mock_schedule.clear.assert_called_once()

    @patch("src.scheduler.scheduler.schedule")
    def test_stop_clears_schedule(self, mock_schedule, scheduler):
        """Test that stop() clears all scheduled jobs."""
        mock_schedule.clear = Mock()

        # Stop scheduler
        scheduler.stop()

        # Verify schedule.clear() was called
        mock_schedule.clear.assert_called_once()
        assert scheduler._running is False
