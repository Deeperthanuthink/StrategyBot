"""Factory for creating broker clients."""

from typing import Optional
from src.logging.bot_logger import BotLogger
from .base_client import BaseBrokerClient
from .alpaca_client import AlpacaClient
from .tradier_client import TradierClient


class BrokerFactory:
    """Factory for creating broker clients based on configuration."""

    @staticmethod
    def create_broker(
        broker_type: str, credentials: dict, logger: Optional[BotLogger] = None
    ) -> BaseBrokerClient:
        """Create a broker client based on type.

        Args:
            broker_type: Type of broker ("alpaca" or "tradier")
            credentials: Dictionary with broker-specific credentials
            logger: Optional logger instance

        Returns:
            BaseBrokerClient instance

        Raises:
            ValueError: If broker_type is not supported
        """
        broker_type = broker_type.lower()

        if broker_type == "alpaca":
            return AlpacaClient(
                api_key=credentials.get("api_key"),
                api_secret=credentials.get("api_secret"),
                paper=credentials.get("paper", True),
                logger=logger,
            )
        elif broker_type == "tradier":
            return TradierClient(
                api_token=credentials.get("api_token"),
                account_id=credentials.get("account_id"),
                base_url=credentials.get("base_url", "https://sandbox.tradier.com"),
                logger=logger,
            )
        else:
            raise ValueError(f"Unsupported broker type: {broker_type}. Supported: alpaca, tradier")

    @staticmethod
    def get_supported_brokers() -> list:
        """Get list of supported broker types.

        Returns:
            List of supported broker names
        """
        return ["alpaca", "tradier"]
