"""Unit tests for TradierClient.get_option_expirations() method."""

import unittest
from unittest.mock import Mock, patch
from datetime import date
from src.tradier.tradier_client import TradierClient
from src.logging.bot_logger import BotLogger


class TestTradierClientGetOptionExpirations(unittest.TestCase):
    """Test cases for TradierClient.get_option_expirations() method."""

    def setUp(self):
        """Set up test fixtures."""
        self.api_token = "test_token"
        self.account_id = "test_account"
        self.base_url = "https://sandbox.tradier.com"
        self.logger = Mock(spec=BotLogger)
        self.client = TradierClient(
            api_token=self.api_token,
            account_id=self.account_id,
            base_url=self.base_url,
            logger=self.logger
        )

    @patch('requests.Session.get')
    def test_successful_api_response_parsing(self, mock_get):
        """Test successful API response parsing with mock response."""
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "expirations": {
                "date": ["2025-12-26", "2025-12-29", "2026-01-02", "2026-01-09"]
            }
        }
        mock_get.return_value = mock_response

        # Act
        result = self.client.get_option_expirations("TLT")

        # Assert
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0], date(2025, 12, 26))
        self.assertEqual(result[1], date(2025, 12, 29))
        self.assertEqual(result[2], date(2026, 1, 2))
        self.assertEqual(result[3], date(2026, 1, 9))
        self.logger.log_info.assert_called_once()

    @patch('requests.Session.get')
    def test_empty_expiration_list_handling(self, mock_get):
        """Test empty expiration list handling."""
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "expirations": {
                "date": []
            }
        }
        mock_get.return_value = mock_response

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            self.client.get_option_expirations("INVALID")
        
        self.assertIn("No option expirations available", str(context.exception))
        self.logger.log_error.assert_called()

    @patch('requests.Session.get')
    def test_api_error_404_handling(self, mock_get):
        """Test API error handling for 404 status code."""
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Symbol not found"
        mock_get.return_value = mock_response

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            self.client.get_option_expirations("INVALID")
        
        self.assertIn("404", str(context.exception))
        self.logger.log_error.assert_called()

    @patch('requests.Session.get')
    def test_api_error_500_handling(self, mock_get):
        """Test API error handling for 500 status code."""
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        mock_get.return_value = mock_response

        # Act & Assert
        with self.assertRaises(ValueError) as context:
            self.client.get_option_expirations("TLT")
        
        self.assertIn("500", str(context.exception))
        self.logger.log_error.assert_called()

    @patch('requests.Session.get')
    def test_date_string_to_date_object_conversion(self, mock_get):
        """Test date string to date object conversion."""
        # Arrange
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "expirations": {
                "date": ["2025-12-26", "2026-01-02"]
            }
        }
        mock_get.return_value = mock_response

        # Act
        result = self.client.get_option_expirations("TLT")

        # Assert
        self.assertIsInstance(result[0], date)
        self.assertIsInstance(result[1], date)
        self.assertEqual(result[0].year, 2025)
        self.assertEqual(result[0].month, 12)
        self.assertEqual(result[0].day, 26)

    @patch('requests.Session.get')
    def test_chronological_sorting_of_dates(self, mock_get):
        """Test chronological sorting of dates."""
        # Arrange - dates intentionally out of order
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "expirations": {
                "date": ["2026-01-09", "2025-12-26", "2026-01-02", "2025-12-29"]
            }
        }
        mock_get.return_value = mock_response

        # Act
        result = self.client.get_option_expirations("TLT")

        # Assert
        self.assertEqual(result[0], date(2025, 12, 26))
        self.assertEqual(result[1], date(2025, 12, 29))
        self.assertEqual(result[2], date(2026, 1, 2))
        self.assertEqual(result[3], date(2026, 1, 9))
        # Verify sorted
        for i in range(len(result) - 1):
            self.assertLess(result[i], result[i + 1])


if __name__ == '__main__':
    unittest.main()
