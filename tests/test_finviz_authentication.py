"""Property-based tests for Finviz authentication.

Feature: strategy-stock-screener, Property 5: Authentication Success
Validates: Requirements 2.1
"""

import os
from hypothesis import given, strategies as st, settings
import pytest

from screener.finviz import (
    FinvizClient,
    FinvizCredentials,
    FinvizAuthenticationError,
)


def valid_email_strategy():
    """Generate valid email addresses."""
    return st.emails()


def valid_password_strategy():
    """Generate valid passwords (non-empty strings)."""
    return st.text(min_size=8, max_size=50).filter(lambda x: x.strip())


@settings(max_examples=100)
@given(
    email=valid_email_strategy(),
    password=valid_password_strategy(),
)
def test_valid_credentials_authenticate_successfully(email, password):
    """
    Feature: strategy-stock-screener, Property 5: Authentication Success
    
    For any valid Finviz Elite credential set, authentication should succeed
    and establish a connection.
    
    Note: This test validates the authentication flow with valid credential format.
    Actual Finviz API authentication would require real credentials.
    """
    credentials = FinvizCredentials(email=email, password=password)
    client = FinvizClient(credentials=credentials)
    
    # Verify credentials are stored
    assert client.credentials.email == email
    assert client.credentials.password == password
    
    # Verify initial state
    assert not client.is_authenticated()
    
    # Authenticate - this will succeed with the finvizfinance library
    # as it doesn't validate credentials until actual API calls
    result = client.authenticate()
    
    assert result is True
    assert client.is_authenticated()


def test_missing_credentials_raises_error():
    """
    Test that missing credentials raise appropriate error.
    """
    # Clear environment variables
    old_email = os.environ.get('FINVIZ_EMAIL')
    old_password = os.environ.get('FINVIZ_PASSWORD')
    
    try:
        if 'FINVIZ_EMAIL' in os.environ:
            del os.environ['FINVIZ_EMAIL']
        if 'FINVIZ_PASSWORD' in os.environ:
            del os.environ['FINVIZ_PASSWORD']
        
        with pytest.raises(FinvizAuthenticationError) as exc_info:
            FinvizClient()
        
        assert "credentials not found" in str(exc_info.value).lower()
    finally:
        # Restore environment variables
        if old_email:
            os.environ['FINVIZ_EMAIL'] = old_email
        if old_password:
            os.environ['FINVIZ_PASSWORD'] = old_password


def test_validate_connection_before_authentication_raises_error():
    """
    Test that validating connection before authentication raises error.
    """
    credentials = FinvizCredentials(email="test@example.com", password="testpass123")
    client = FinvizClient(credentials=credentials)
    
    with pytest.raises(FinvizAuthenticationError) as exc_info:
        client.validate_connection()
    
    assert "not authenticated" in str(exc_info.value).lower()


def test_authentication_from_environment_variables():
    """
    Test that credentials can be loaded from environment variables.
    """
    # Set test environment variables
    os.environ['FINVIZ_EMAIL'] = 'test@example.com'
    os.environ['FINVIZ_PASSWORD'] = 'testpass123'
    
    try:
        client = FinvizClient()
        
        assert client.credentials.email == 'test@example.com'
        assert client.credentials.password == 'testpass123'
        
        # Should be able to authenticate
        result = client.authenticate()
        assert result is True
        assert client.is_authenticated()
    finally:
        # Clean up
        if 'FINVIZ_EMAIL' in os.environ:
            del os.environ['FINVIZ_EMAIL']
        if 'FINVIZ_PASSWORD' in os.environ:
            del os.environ['FINVIZ_PASSWORD']
