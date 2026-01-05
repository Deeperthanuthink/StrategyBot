"""Unit tests for Finviz error handling.

Tests invalid credentials error messages and rate limit handling.
Validates: Requirements 2.5, 2.6, 8.1, 8.5
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import time

from screener.finviz import (
    FinvizClient,
    FinvizCredentials,
    FinvizAuthenticationError,
    FinvizRateLimitError,
)


def test_invalid_credentials_error_message():
    """
    Test that invalid credentials produce a clear error message.
    
    Validates: Requirements 2.5, 8.1
    """
    # Test with missing environment variables
    with patch.dict('os.environ', {}, clear=True):
        with pytest.raises(FinvizAuthenticationError) as exc_info:
            FinvizClient()
        
        error_msg = str(exc_info.value).lower()
        assert "credentials not found" in error_msg
        assert "finviz_email" in error_msg
        assert "finviz_password" in error_msg


def test_authentication_failure_error_message():
    """
    Test that authentication failures produce clear error messages.
    
    Validates: Requirements 2.5, 8.1
    """
    credentials = FinvizCredentials(email="invalid@example.com", password="wrongpass")
    client = FinvizClient(credentials=credentials)
    
    # Mock the Overview class to raise an authentication error
    with patch('screener.finviz.client.Overview') as mock_overview:
        mock_overview.side_effect = Exception("Authentication failed: Invalid credentials")
        
        with pytest.raises(FinvizAuthenticationError) as exc_info:
            client.authenticate()
        
        error_msg = str(exc_info.value).lower()
        assert "failed to authenticate" in error_msg or "authentication" in error_msg


def test_rate_limit_error_with_retry():
    """
    Test that rate limit errors trigger retry logic with exponential backoff.
    
    Validates: Requirements 2.6, 8.5
    """
    credentials = FinvizCredentials(email="test@example.com", password="testpass")
    client = FinvizClient(credentials=credentials, max_retries=3, retry_delay=0.1)
    client._authenticated = True
    
    # Mock the Overview class to raise rate limit errors
    with patch('screener.finviz.client.Overview') as mock_overview:
        mock_instance = MagicMock()
        mock_overview.return_value = mock_instance
        
        # First two calls raise rate limit error, third succeeds
        mock_instance.screener_view.side_effect = [
            Exception("Rate limit exceeded"),
            Exception("Too many requests"),
            pd.DataFrame({'Ticker': ['AAPL'], 'Price': [150.0]})
        ]
        
        start_time = time.time()
        result = client.screen({})
        elapsed_time = time.time() - start_time
        
        # Should have retried twice with exponential backoff (0.1s + 0.2s = 0.3s minimum)
        assert elapsed_time >= 0.3
        assert len(result) == 1
        assert result['Ticker'].iloc[0] == 'AAPL'


def test_rate_limit_error_max_retries_exceeded():
    """
    Test that rate limit errors raise FinvizRateLimitError after max retries.
    
    Validates: Requirements 2.6, 8.5
    """
    credentials = FinvizCredentials(email="test@example.com", password="testpass")
    client = FinvizClient(credentials=credentials, max_retries=2, retry_delay=0.1)
    client._authenticated = True
    
    # Mock the Overview class to always raise rate limit errors
    with patch('screener.finviz.client.Overview') as mock_overview:
        mock_instance = MagicMock()
        mock_overview.return_value = mock_instance
        mock_instance.screener_view.side_effect = Exception("Rate limit exceeded")
        
        with pytest.raises(FinvizRateLimitError) as exc_info:
            client.screen({})
        
        error_msg = str(exc_info.value).lower()
        assert "rate limit" in error_msg
        assert "2 attempts" in error_msg or "retries" in error_msg
        
        # Should have retry_after attribute
        assert exc_info.value.retry_after is not None
        assert exc_info.value.retry_after > 0


def test_rate_limit_error_includes_retry_after():
    """
    Test that rate limit errors include retry_after information.
    
    Validates: Requirements 8.5
    """
    credentials = FinvizCredentials(email="test@example.com", password="testpass")
    client = FinvizClient(credentials=credentials, max_retries=1, retry_delay=0.1)
    client._authenticated = True
    
    with patch('screener.finviz.client.Overview') as mock_overview:
        mock_instance = MagicMock()
        mock_overview.return_value = mock_instance
        mock_instance.screener_view.side_effect = Exception("429 Too Many Requests")
        
        with pytest.raises(FinvizRateLimitError) as exc_info:
            client.screen({})
        
        # Should suggest a retry_after time
        assert exc_info.value.retry_after == 60  # Default suggestion


def test_exponential_backoff_timing():
    """
    Test that exponential backoff increases delay correctly.
    
    Validates: Requirements 2.6
    """
    credentials = FinvizCredentials(email="test@example.com", password="testpass")
    client = FinvizClient(credentials=credentials, max_retries=3, retry_delay=0.1)
    client._authenticated = True
    
    with patch('screener.finviz.client.Overview') as mock_overview:
        mock_instance = MagicMock()
        mock_overview.return_value = mock_instance
        
        # Fail twice, then succeed
        mock_instance.screener_view.side_effect = [
            Exception("Network error"),
            Exception("Network error"),
            pd.DataFrame({'Ticker': ['AAPL']})
        ]
        
        start_time = time.time()
        result = client.screen({})
        elapsed_time = time.time() - start_time
        
        # First retry: 0.1s, second retry: 0.2s = 0.3s total minimum
        assert elapsed_time >= 0.3
        assert len(result) == 1


def test_authentication_error_during_screen():
    """
    Test that authentication errors during screening are properly caught.
    
    Validates: Requirements 2.5, 8.1
    """
    credentials = FinvizCredentials(email="test@example.com", password="testpass")
    client = FinvizClient(credentials=credentials)
    client._authenticated = True
    
    with patch('screener.finviz.client.Overview') as mock_overview:
        mock_instance = MagicMock()
        mock_overview.return_value = mock_instance
        mock_instance.screener_view.side_effect = Exception("Authentication failed: Session expired")
        
        with pytest.raises(FinvizAuthenticationError) as exc_info:
            client.screen({})
        
        error_msg = str(exc_info.value).lower()
        assert "authentication" in error_msg


def test_generic_error_with_retry():
    """
    Test that generic errors also trigger retry logic.
    
    Validates: Requirements 2.6
    """
    credentials = FinvizCredentials(email="test@example.com", password="testpass")
    client = FinvizClient(credentials=credentials, max_retries=2, retry_delay=0.1)
    client._authenticated = True
    
    with patch('screener.finviz.client.Overview') as mock_overview:
        mock_instance = MagicMock()
        mock_overview.return_value = mock_instance
        
        # Fail once, then succeed
        mock_instance.screener_view.side_effect = [
            Exception("Network timeout"),
            pd.DataFrame({'Ticker': ['AAPL']})
        ]
        
        result = client.screen({})
        
        # Should have succeeded after retry
        assert len(result) == 1
        assert result['Ticker'].iloc[0] == 'AAPL'


def test_screen_without_authentication_raises_error():
    """
    Test that screening without authentication raises appropriate error.
    
    Validates: Requirements 2.5, 8.1
    """
    credentials = FinvizCredentials(email="test@example.com", password="testpass")
    client = FinvizClient(credentials=credentials)
    
    # Don't authenticate
    with pytest.raises(FinvizAuthenticationError) as exc_info:
        client.screen({})
    
    error_msg = str(exc_info.value).lower()
    assert "not authenticated" in error_msg
    assert "authenticate()" in error_msg.lower()


def test_max_retries_configuration():
    """
    Test that max_retries configuration is respected.
    
    Validates: Requirements 2.6
    """
    credentials = FinvizCredentials(email="test@example.com", password="testpass")
    
    # Test with different max_retries values
    client1 = FinvizClient(credentials=credentials, max_retries=1)
    assert client1.max_retries == 1
    
    client2 = FinvizClient(credentials=credentials, max_retries=5)
    assert client2.max_retries == 5
    
    client3 = FinvizClient(credentials=credentials)
    assert client3.max_retries == 3  # Default


def test_retry_delay_configuration():
    """
    Test that retry_delay configuration is respected.
    
    Validates: Requirements 2.6
    """
    credentials = FinvizCredentials(email="test@example.com", password="testpass")
    
    # Test with different retry_delay values
    client1 = FinvizClient(credentials=credentials, retry_delay=0.5)
    assert client1.retry_delay == 0.5
    
    client2 = FinvizClient(credentials=credentials, retry_delay=2.0)
    assert client2.retry_delay == 2.0
    
    client3 = FinvizClient(credentials=credentials)
    assert client3.retry_delay == 1.0  # Default
