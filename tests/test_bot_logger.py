"""Unit tests for BotLogger."""

import os
import tempfile
from datetime import datetime
from pathlib import Path
import pytest
from src.logging import BotLogger
from src.config.models import LoggingConfig


class TestBotLogger:
    """Test cases for BotLogger."""

    def test_log_file_creation_and_writing(self):
        """Test that log file is created and messages are written."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = os.path.join(temp_dir, "test.log")
            config = LoggingConfig(level="INFO", file_path=log_path)

            logger = BotLogger(config)
            logger.log_info("Test message")

            # Verify file was created
            assert os.path.exists(log_path)

            # Verify message was written
            with open(log_path, "r") as f:
                content = f.read()
                assert "Test message" in content
                assert "[INFO]" in content

    def test_console_output(self, caplog):
        """Test that messages are written to console."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = os.path.join(temp_dir, "test.log")
            config = LoggingConfig(level="INFO", file_path=log_path)

            logger = BotLogger(config)
            logger.log_info("Console test message")

            # Verify message was logged
            assert "Console test message" in caplog.text
            assert "INFO" in caplog.text

    def test_credential_masking_in_messages(self):
        """Test that API credentials are masked in log messages."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = os.path.join(temp_dir, "test.log")
            config = LoggingConfig(level="INFO", file_path=log_path)

            logger = BotLogger(config)

            # Test various credential patterns
            logger.log_info("api_key=AKIAIOSFODNN7EXAMPLE")
            logger.log_info("api_secret: my_secret_key_123")
            logger.log_info('password="super_secret_pass"')
            logger.log_info("token: bearer_token_xyz")
            logger.log_info("Bearer abc123def456")

            # Read log file
            with open(log_path, "r") as f:
                content = f.read()

                # Verify credentials are masked
                assert "AKIAIOSFODNN7EXAMPLE" not in content
                assert "my_secret_key_123" not in content
                assert "super_secret_pass" not in content
                assert "bearer_token_xyz" not in content
                assert "abc123def456" not in content

                # Verify masking markers are present
                assert "***MASKED***" in content

    def test_credential_masking_in_context(self):
        """Test that credentials in context dictionary are masked."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = os.path.join(temp_dir, "test.log")
            config = LoggingConfig(level="INFO", file_path=log_path)

            logger = BotLogger(config)

            # Test context with sensitive keys
            context = {
                "api_key": "secret_key_123",
                "api_secret": "secret_value",
                "password": "my_password",
                "token": "auth_token",
                "symbol": "NVDA",
            }

            logger.log_info("Test with context", context=context)

            # Read log file
            with open(log_path, "r") as f:
                content = f.read()

                # Verify sensitive values are masked
                assert "secret_key_123" not in content
                assert "secret_value" not in content
                assert "my_password" not in content
                assert "auth_token" not in content

                # Verify masking markers are present
                assert "***MASKED***" in content

                # Verify non-sensitive data is not masked
                assert "NVDA" in content

    def test_log_levels(self):
        """Test different log levels."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = os.path.join(temp_dir, "test.log")
            config = LoggingConfig(level="DEBUG", file_path=log_path)

            logger = BotLogger(config)

            logger.log_debug("Debug message")
            logger.log_info("Info message")
            logger.log_warning("Warning message")
            logger.log_error("Error message")

            # Read log file
            with open(log_path, "r") as f:
                content = f.read()

                assert "[DEBUG]" in content
                assert "Debug message" in content
                assert "[INFO]" in content
                assert "Info message" in content
                assert "[WARNING]" in content
                assert "Warning message" in content
                assert "[ERROR]" in content
                assert "Error message" in content

    def test_log_error_with_exception(self):
        """Test logging errors with exception objects."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = os.path.join(temp_dir, "test.log")
            config = LoggingConfig(level="INFO", file_path=log_path)

            logger = BotLogger(config)

            try:
                raise ValueError("Test exception")
            except ValueError as e:
                logger.log_error("An error occurred", error=e)

            # Read log file
            with open(log_path, "r") as f:
                content = f.read()

                assert "An error occurred" in content
                assert "ValueError" in content
                assert "Test exception" in content

    def test_context_formatting(self):
        """Test that context dictionary is properly formatted."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = os.path.join(temp_dir, "test.log")
            config = LoggingConfig(level="INFO", file_path=log_path)

            logger = BotLogger(config)

            context = {"symbol": "NVDA", "price": 145.50, "quantity": 2}

            logger.log_info("Trade executed", context=context)

            # Read log file
            with open(log_path, "r") as f:
                content = f.read()

                assert "symbol=NVDA" in content
                assert "price=145.5" in content
                assert "quantity=2" in content

    def test_log_trade_success(self):
        """Test logging successful trade execution."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = os.path.join(temp_dir, "test.log")
            config = LoggingConfig(level="INFO", file_path=log_path)

            logger = BotLogger(config)

            trade_result = {
                "symbol": "NVDA",
                "success": True,
                "order_id": "12345",
                "short_strike": 138.00,
                "long_strike": 133.00,
                "expiration": "2025-12-06",
                "quantity": 2,
                "filled_price": 0.45,
                "timestamp": datetime.now(),
            }

            logger.log_trade(trade_result)

            # Read log file
            with open(log_path, "r") as f:
                content = f.read()

                assert "Order submitted: NVDA" in content
                assert "Status=FILLED" in content
                assert "Contracts=2" in content
                assert "Short Strike=$138.00" in content
                assert "Long Strike=$133.00" in content
                assert "Expiration=2025-12-06" in content
                assert "Filled Price=$0.45" in content
                assert "Order ID=12345" in content

    def test_log_trade_failure(self):
        """Test logging failed trade execution."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = os.path.join(temp_dir, "test.log")
            config = LoggingConfig(level="INFO", file_path=log_path)

            logger = BotLogger(config)

            trade_result = {
                "symbol": "GOOGL",
                "success": False,
                "short_strike": 140.00,
                "long_strike": 135.00,
                "error_message": "Insufficient buying power",
                "timestamp": datetime.now(),
            }

            logger.log_trade(trade_result)

            # Read log file
            with open(log_path, "r") as f:
                content = f.read()

                assert "Order failed: GOOGL" in content
                assert "Error=Insufficient buying power" in content
                assert "Short Strike=$140.00" in content
                assert "Long Strike=$135.00" in content

    def test_log_execution_summary(self):
        """Test logging execution cycle summary."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = os.path.join(temp_dir, "test.log")
            config = LoggingConfig(level="INFO", file_path=log_path)

            logger = BotLogger(config)

            summary = {
                "execution_date": datetime(2025, 11, 25, 10, 0, 0),
                "total_symbols": 4,
                "successful_trades": 3,
                "failed_trades": 1,
                "trade_results": [
                    {"symbol": "NVDA", "success": True},
                    {"symbol": "GOOGL", "success": True},
                    {"symbol": "AAPL", "success": True},
                    {"symbol": "MSFT", "success": False},
                ],
            }

            logger.log_execution_summary(summary)

            # Read log file
            with open(log_path, "r") as f:
                content = f.read()

                assert "Execution complete" in content
                assert "Total=4" in content
                assert "Success=3" in content
                assert "Failed=1" in content
                assert "Trade details for 4 symbols" in content
                assert "NVDA: SUCCESS" in content
                assert "GOOGL: SUCCESS" in content
                assert "AAPL: SUCCESS" in content
                assert "MSFT: FAILED" in content

    def test_log_rotation_configuration(self):
        """Test that log rotation is properly configured."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = os.path.join(temp_dir, "test.log")
            config = LoggingConfig(level="INFO", file_path=log_path)

            logger = BotLogger(config)

            # Verify logger has rotating file handler
            handlers = logger.logger.handlers
            assert len(handlers) == 2  # File and console handlers

            # Find the rotating file handler
            from logging.handlers import RotatingFileHandler

            rotating_handler = None
            for handler in handlers:
                if isinstance(handler, RotatingFileHandler):
                    rotating_handler = handler
                    break

            assert rotating_handler is not None
            assert rotating_handler.maxBytes == 10 * 1024 * 1024  # 10 MB
            assert rotating_handler.backupCount == 5

    def test_log_directory_creation(self):
        """Test that log directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = os.path.join(temp_dir, "nested", "dir", "test.log")
            config = LoggingConfig(level="INFO", file_path=log_path)

            # Directory should not exist yet
            assert not os.path.exists(os.path.dirname(log_path))

            logger = BotLogger(config)
            logger.log_info("Test message")

            # Directory and file should now exist
            assert os.path.exists(os.path.dirname(log_path))
            assert os.path.exists(log_path)
