"""Unit tests for TradingCalendar."""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from src.utils.trading_calendar import TradingCalendar, FALLBACK_HOLIDAYS


class TestTradingCalendar:
    """Test cases for TradingCalendar utility."""

    @pytest.fixture
    def calendar(self):
        """Create a TradingCalendar instance for testing."""
        return TradingCalendar(api_token="test_token", is_sandbox=True)

    def test_is_trading_day_saturday(self, calendar):
        """Test that Saturday returns False for is_trading_day."""
        # Saturday, December 28, 2024
        saturday = date(2024, 12, 28)
        assert saturday.weekday() == 5  # Verify it's Saturday
        assert calendar.is_trading_day(saturday) is False

    def test_is_trading_day_sunday(self, calendar):
        """Test that Sunday returns False for is_trading_day."""
        # Sunday, December 29, 2024
        sunday = date(2024, 12, 29)
        assert sunday.weekday() == 6  # Verify it's Sunday
        assert calendar.is_trading_day(sunday) is False

    @patch('src.utils.trading_calendar.requests.get')
    def test_is_trading_day_weekday_open(self, mock_get, calendar):
        """Test that weekday returns True when API indicates market is open."""
        # Monday, December 30, 2024
        monday = date(2024, 12, 30)
        assert monday.weekday() == 0  # Verify it's Monday
        
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            'calendar': {
                'month': 12,
                'year': 2024,
                'days': {
                    'day': [
                        {
                            'date': '2024-12-30',
                            'status': 'open',
                            'open': {'start': '09:30', 'end': '16:00'}
                        }
                    ]
                }
            }
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        assert calendar.is_trading_day(monday) is True

    @patch('src.utils.trading_calendar.requests.get')
    def test_is_trading_day_holiday(self, mock_get, calendar):
        """Test that holiday returns False when API indicates market is closed."""
        # Christmas Day 2025
        christmas = date(2025, 12, 25)
        
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            'calendar': {
                'month': 12,
                'year': 2025,
                'days': {
                    'day': [
                        {
                            'date': '2025-12-25',
                            'status': 'closed',
                            'description': 'Christmas Day'
                        }
                    ]
                }
            }
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        assert calendar.is_trading_day(christmas) is False

    @patch('src.utils.trading_calendar.requests.get')
    def test_get_next_trading_day_from_saturday(self, mock_get, calendar):
        """Test that next trading day from Saturday returns Monday."""
        # Saturday, December 28, 2024
        saturday = date(2024, 12, 28)
        expected_monday = date(2024, 12, 30)
        
        # Mock API response for Monday
        mock_response = Mock()
        mock_response.json.return_value = {
            'calendar': {
                'month': 12,
                'year': 2024,
                'days': {
                    'day': [
                        {
                            'date': '2024-12-30',
                            'status': 'open',
                            'open': {'start': '09:30', 'end': '16:00'}
                        }
                    ]
                }
            }
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = calendar.get_next_trading_day(saturday)
        assert result == expected_monday

    @patch('src.utils.trading_calendar.requests.get')
    def test_get_next_trading_day_from_sunday(self, mock_get, calendar):
        """Test that next trading day from Sunday returns Monday."""
        # Sunday, December 29, 2024
        sunday = date(2024, 12, 29)
        expected_monday = date(2024, 12, 30)
        
        # Mock API response for Monday
        mock_response = Mock()
        mock_response.json.return_value = {
            'calendar': {
                'month': 12,
                'year': 2024,
                'days': {
                    'day': [
                        {
                            'date': '2024-12-30',
                            'status': 'open',
                            'open': {'start': '09:30', 'end': '16:00'}
                        }
                    ]
                }
            }
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = calendar.get_next_trading_day(sunday)
        assert result == expected_monday

    @patch('src.utils.trading_calendar.requests.get')
    def test_get_next_trading_day_holiday_monday(self, mock_get, calendar):
        """Test that next trading day handles holiday Monday correctly."""
        # Friday before MLK Day 2025 (Monday, January 20, 2025 is a holiday)
        friday = date(2025, 1, 17)
        expected_tuesday = date(2025, 1, 21)
        
        # Mock API responses for both months
        def mock_get_side_effect(url, **kwargs):
            mock_response = Mock()
            params = kwargs.get('params', {})
            month = params.get('month')
            
            if month == 1:
                mock_response.json.return_value = {
                    'calendar': {
                        'month': 1,
                        'year': 2025,
                        'days': {
                            'day': [
                                {
                                    'date': '2025-01-20',
                                    'status': 'closed',
                                    'description': 'Martin Luther King Jr. Day'
                                },
                                {
                                    'date': '2025-01-21',
                                    'status': 'open',
                                    'open': {'start': '09:30', 'end': '16:00'}
                                }
                            ]
                        }
                    }
                }
            mock_response.raise_for_status = Mock()
            return mock_response
        
        mock_get.side_effect = mock_get_side_effect
        
        result = calendar.get_next_trading_day(friday)
        assert result == expected_tuesday

    @patch('src.utils.trading_calendar.requests.get')
    def test_get_0dte_expiration_trading_day(self, mock_get, calendar):
        """Test that get_0dte_expiration returns today on trading day."""
        # Monday, December 30, 2024
        monday = date(2024, 12, 30)
        
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            'calendar': {
                'month': 12,
                'year': 2024,
                'days': {
                    'day': [
                        {
                            'date': '2024-12-30',
                            'status': 'open',
                            'open': {'start': '09:30', 'end': '16:00'}
                        }
                    ]
                }
            }
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = calendar.get_0dte_expiration(monday)
        assert result == monday

    @patch('src.utils.trading_calendar.requests.get')
    def test_get_0dte_expiration_weekend(self, mock_get, calendar):
        """Test that get_0dte_expiration returns next trading day on weekend."""
        # Saturday, December 28, 2024
        saturday = date(2024, 12, 28)
        expected_monday = date(2024, 12, 30)
        
        # Mock API response for Monday
        mock_response = Mock()
        mock_response.json.return_value = {
            'calendar': {
                'month': 12,
                'year': 2024,
                'days': {
                    'day': [
                        {
                            'date': '2024-12-30',
                            'status': 'open',
                            'open': {'start': '09:30', 'end': '16:00'}
                        }
                    ]
                }
            }
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = calendar.get_0dte_expiration(saturday)
        assert result == expected_monday

    @patch('src.utils.trading_calendar.requests.get')
    def test_fallback_when_api_unavailable(self, mock_get, calendar):
        """Test fallback behavior when API is unavailable."""
        # Mock API failure
        mock_get.side_effect = Exception("API unavailable")
        
        # Test with a known fallback holiday (Christmas 2025)
        christmas = date(2025, 12, 25)
        assert calendar.is_trading_day(christmas) is False
        
        # Test with a regular weekday not in fallback holidays
        regular_day = date(2025, 3, 15)  # Saturday
        assert calendar.is_trading_day(regular_day) is False  # Weekend check still works
        
        # Test with a weekday not in fallback holidays
        weekday = date(2025, 3, 17)  # Monday
        assert calendar.is_trading_day(weekday) is True  # Should be True (not in fallback)
