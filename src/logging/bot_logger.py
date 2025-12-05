"""Bot logger implementation with structured logging and credential masking."""

import logging
import re
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional

from src.config.models import LoggingConfig


class BotLogger:
    """Logger for the trading bot with structured logging and credential protection."""

    # Patterns to detect and mask sensitive information
    SENSITIVE_PATTERNS = [
        (
            re.compile(r'(api[_-]?key["\']?\s*[:=]\s*["\']?)([^"\'}\s]+)', re.IGNORECASE),
            r"\1***MASKED***",
        ),
        (
            re.compile(r'(api[_-]?secret["\']?\s*[:=]\s*["\']?)([^"\'}\s]+)', re.IGNORECASE),
            r"\1***MASKED***",
        ),
        (
            re.compile(r'(password["\']?\s*[:=]\s*["\']?)([^"\'}\s]+)', re.IGNORECASE),
            r"\1***MASKED***",
        ),
        (
            re.compile(r'(token["\']?\s*[:=]\s*["\']?)([^"\'}\s]+)', re.IGNORECASE),
            r"\1***MASKED***",
        ),
        (
            re.compile(r"(bearer\s+)([a-zA-Z0-9_\-\.]+)", re.IGNORECASE),
            r"\1***MASKED***",
        ),
    ]

    def __init__(self, config: LoggingConfig):
        """Initialize the bot logger.

        Args:
            config: Logging configuration
        """
        self.config = config
        self.logger = logging.getLogger("TradingBot")
        self.logger.setLevel(getattr(logging, config.level.upper()))

        # Remove existing handlers to avoid duplicates
        self.logger.handlers.clear()

        # Create formatters
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

        # Configure file handler with rotation
        log_path = Path(config.file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            config.file_path, maxBytes=10 * 1024 * 1024, backupCount=5  # 10 MB
        )
        file_handler.setLevel(getattr(logging, config.level.upper()))
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        # Configure console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, config.level.upper()))
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

    def _mask_sensitive_data(self, message: str) -> str:
        """Mask sensitive information in log messages.

        Args:
            message: Original log message

        Returns:
            Message with sensitive data masked
        """
        masked_message = message
        for pattern, replacement in self.SENSITIVE_PATTERNS:
            masked_message = pattern.sub(replacement, masked_message)
        return masked_message

    def _format_context(self, context: Optional[Dict[str, Any]]) -> str:
        """Format context dictionary for logging.

        Args:
            context: Context dictionary

        Returns:
            Formatted context string
        """
        if not context:
            return ""

        context_parts = []
        for key, value in context.items():
            # Mask sensitive keys
            if any(
                sensitive in key.lower() for sensitive in ["key", "secret", "password", "token"]
            ):
                value = "***MASKED***"
            context_parts.append(f"{key}={value}")

        return " | " + " | ".join(context_parts) if context_parts else ""

    def log_info(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Log an info message.

        Args:
            message: Log message
            context: Optional context dictionary for structured data
        """
        masked_message = self._mask_sensitive_data(message)
        context_str = self._format_context(context)
        self.logger.info(f"{masked_message}{context_str}")

    def log_warning(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Log a warning message.

        Args:
            message: Log message
            context: Optional context dictionary for structured data
        """
        masked_message = self._mask_sensitive_data(message)
        context_str = self._format_context(context)
        self.logger.warning(f"{masked_message}{context_str}")

    def log_error(
        self,
        message: str,
        error: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Log an error message.

        Args:
            message: Log message
            error: Optional exception object
            context: Optional context dictionary for structured data
        """
        masked_message = self._mask_sensitive_data(message)
        context_str = self._format_context(context)

        if error:
            error_info = f" | Error: {type(error).__name__}: {str(error)}"
            self.logger.error(f"{masked_message}{context_str}{error_info}", exc_info=True)
        else:
            self.logger.error(f"{masked_message}{context_str}")

    def log_debug(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Log a debug message.

        Args:
            message: Log message
            context: Optional context dictionary for structured data
        """
        masked_message = self._mask_sensitive_data(message)
        context_str = self._format_context(context)
        self.logger.debug(f"{masked_message}{context_str}")

    def log_critical(
        self,
        message: str,
        error: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Log a critical error message.

        Critical errors are severe issues that may prevent the bot from functioning.

        Args:
            message: Log message
            error: Optional exception object
            context: Optional context dictionary for structured data
        """
        masked_message = self._mask_sensitive_data(message)
        context_str = self._format_context(context)

        if error:
            error_info = f" | Error: {type(error).__name__}: {str(error)}"
            self.logger.critical(f"{masked_message}{context_str}{error_info}", exc_info=True)
        else:
            self.logger.critical(f"{masked_message}{context_str}")

    def log_trade(self, trade_result: Dict[str, Any]):
        """Log trade execution details.

        Args:
            trade_result: Dictionary containing trade result information with keys:
                - symbol: Trading symbol
                - success: Whether trade was successful
                - order_id: Order ID (if successful)
                - short_strike: Short strike price
                - long_strike: Long strike price
                - expiration: Expiration date
                - quantity: Number of contracts
                - filled_price: Filled price (if successful)
                - error_message: Error message (if failed)
                - timestamp: Execution timestamp
        """
        symbol = trade_result.get("symbol", "UNKNOWN")
        success = trade_result.get("success", False)

        if success:
            message = (
                f"Order submitted: {symbol} | "
                f"Status=FILLED | "
                f"Contracts={trade_result.get('quantity', 0)} | "
                f"Short Strike=${trade_result.get('short_strike', 0):.2f} | "
                f"Long Strike=${trade_result.get('long_strike', 0):.2f} | "
                f"Expiration={trade_result.get('expiration', 'N/A')}"
            )

            if trade_result.get("filled_price"):
                message += f" | Filled Price=${trade_result.get('filled_price'):.2f}"
            if trade_result.get("order_id"):
                message += f" | Order ID={trade_result.get('order_id')}"

            self.log_info(message)
        else:
            error_msg = trade_result.get("error_message", "Unknown error")
            message = (
                f"Order failed: {symbol} | "
                f"Error={error_msg} | "
                f"Short Strike=${trade_result.get('short_strike', 0):.2f} | "
                f"Long Strike=${trade_result.get('long_strike', 0):.2f}"
            )
            self.log_error(message)

    def log_execution_summary(self, summary: Dict[str, Any]):
        """Log execution cycle summary.

        Args:
            summary: Dictionary containing execution summary with keys:
                - execution_date: Execution timestamp
                - total_symbols: Total number of symbols processed
                - successful_trades: Number of successful trades
                - failed_trades: Number of failed trades
                - trade_results: List of trade result dictionaries
        """
        execution_date = summary.get("execution_date", datetime.now())
        total = summary.get("total_symbols", 0)
        successful = summary.get("successful_trades", 0)
        failed = summary.get("failed_trades", 0)

        message = (
            f"Execution complete | "
            f"Date={execution_date} | "
            f"Total={total} | "
            f"Success={successful} | "
            f"Failed={failed}"
        )

        self.log_info(message)

        # Log individual trade results if available
        trade_results = summary.get("trade_results", [])
        if trade_results:
            self.log_info(f"Trade details for {len(trade_results)} symbols:")
            for trade in trade_results:
                symbol = trade.get("symbol", "UNKNOWN")
                success = trade.get("success", False)
                status = "SUCCESS" if success else "FAILED"
                self.log_info(f"  - {symbol}: {status}")
