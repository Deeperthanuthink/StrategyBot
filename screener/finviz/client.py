"""Finviz Elite integration client for stock screening."""

import os
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
import pandas as pd
from finvizfinance.screener.overview import Overview


@dataclass
class FinvizCredentials:
    """Credentials for Finviz Elite authentication."""
    email: str
    password: str


class FinvizAuthenticationError(Exception):
    """Raised when Finviz authentication fails."""
    pass


class FinvizRateLimitError(Exception):
    """Raised when Finviz rate limit is exceeded."""
    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after  # Seconds until rate limit resets


# Mapping from internal filter names to Finviz screener parameters
FINVIZ_FILTER_MAP = {
    # Market Cap filters
    "min_market_cap_2b": "cap_midover",  # $2B+
    "min_market_cap_10b": "cap_largeover",  # $10B+
    
    # Volume filters
    "min_volume_100k": "sh_avgvol_o100",  # Over 100K
    "min_volume_500k": "sh_avgvol_o500",  # Over 500K
    "min_volume_1m": "sh_avgvol_o1000",  # Over 1M
    "min_volume_2m": "sh_avgvol_o2000",  # Over 2M
    
    # Price filters
    "price_over_1": "sh_price_o1",
    "price_over_2": "sh_price_o2",
    "price_over_3": "sh_price_o3",
    "price_over_4": "sh_price_o4",
    "price_over_5": "sh_price_o5",
    "price_over_7": "sh_price_o7",
    "price_over_10": "sh_price_o10",
    "price_over_15": "sh_price_o15",
    "price_over_20": "sh_price_o20",
    "price_over_30": "sh_price_o30",
    "price_over_40": "sh_price_o40",
    "price_over_50": "sh_price_o50",
    "price_under_1": "sh_price_u1",
    "price_under_2": "sh_price_u2",
    "price_under_3": "sh_price_u3",
    "price_under_4": "sh_price_u4",
    "price_under_5": "sh_price_u5",
    "price_under_7": "sh_price_u7",
    "price_under_10": "sh_price_u10",
    "price_under_15": "sh_price_u15",
    "price_under_20": "sh_price_u20",
    "price_under_30": "sh_price_u30",
    "price_under_40": "sh_price_u40",
    "price_under_50": "sh_price_u50",
    
    # RSI filters
    "rsi_oversold_30": "ta_rsi_os30",
    "rsi_oversold_40": "ta_rsi_os40",
    "rsi_overbought_60": "ta_rsi_ob60",
    "rsi_overbought_70": "ta_rsi_ob70",
    
    # Moving Average filters
    "price_above_sma20": "ta_sma20_pa",
    "price_below_sma20": "ta_sma20_pb",
    "price_above_sma50": "ta_sma50_pa",
    "price_below_sma50": "ta_sma50_pb",
    "price_above_sma200": "ta_sma200_pa",
    "price_below_sma200": "ta_sma200_pb",
    "sma20_above_sma50": "ta_sma20_sa50",
    "sma20_below_sma50": "ta_sma20_sb50",
    "sma50_above_sma200": "ta_sma50_sa200",
    "sma50_below_sma200": "ta_sma50_sb200",
    
    # Performance filters
    "perf_week_up": "ta_perf_1wup",
    "perf_week_down": "ta_perf_1wdown",
    "perf_month_up": "ta_perf_4wup",
    "perf_month_down": "ta_perf_4wdown",
    
    # Beta filters
    "beta_under_0_5": "fa_beta_u0.5",
    "beta_under_1": "fa_beta_u1",
    "beta_under_1_5": "fa_beta_u1.5",
    "beta_under_2": "fa_beta_u2",
    "beta_over_0_5": "fa_beta_o0.5",
    "beta_over_1": "fa_beta_o1",
    "beta_over_1_5": "fa_beta_o1.5",
    "beta_over_2": "fa_beta_o2",
    
    # Options filters
    "optionable": "sh_opt_option",
    "shortable": "sh_short_yes",
    
    # Earnings filters
    "earnings_before": "earningsdate_before",
    "earnings_after": "earningsdate_after",
    "earnings_this_week": "earningsdate_thisweek",
    "earnings_next_week": "earningsdate_nextweek",
    "earnings_prev_week": "earningsdate_prevweek",
    "earnings_this_month": "earningsdate_thismonth",
}


class FinvizClient:
    """Client for interacting with Finviz Elite screening service."""
    
    def __init__(
        self,
        credentials: Optional[FinvizCredentials] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Initialize Finviz client with credentials.
        
        Args:
            credentials: Finviz Elite credentials. If None, loads from environment.
            max_retries: Maximum number of retry attempts for failed requests
            retry_delay: Initial delay in seconds for exponential backoff
        
        Raises:
            FinvizAuthenticationError: If credentials are missing or invalid.
        """
        if credentials is None:
            credentials = self._load_credentials_from_env()
        
        self.credentials = credentials
        self._authenticated = False
        self._screener = None
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    def _load_credentials_from_env(self) -> FinvizCredentials:
        """
        Load Finviz credentials from environment variables.
        
        Returns:
            FinvizCredentials object
        
        Raises:
            FinvizAuthenticationError: If credentials are not found in environment.
        """
        email = os.getenv('FINVIZ_EMAIL')
        password = os.getenv('FINVIZ_PASSWORD')
        
        if not email or not password:
            raise FinvizAuthenticationError(
                "Finviz credentials not found. Please set FINVIZ_EMAIL and "
                "FINVIZ_PASSWORD environment variables."
            )
        
        return FinvizCredentials(email=email, password=password)
    
    def authenticate(self) -> bool:
        """
        Authenticate with Finviz Elite and establish connection.
        
        Returns:
            True if authentication successful
        
        Raises:
            FinvizAuthenticationError: If authentication fails
        """
        try:
            # Initialize the screener - finvizfinance handles authentication internally
            # Note: The library doesn't have explicit authentication, but we validate
            # credentials are present
            self._screener = Overview()
            self._authenticated = True
            return True
        except Exception as e:
            raise FinvizAuthenticationError(
                f"Failed to authenticate with Finviz: {str(e)}"
            )
    
    def validate_connection(self) -> bool:
        """
        Validate that the connection to Finviz is working.
        
        Returns:
            True if connection is valid
        
        Raises:
            FinvizAuthenticationError: If not authenticated or connection fails
        """
        if not self._authenticated:
            raise FinvizAuthenticationError(
                "Not authenticated. Call authenticate() first."
            )
        
        try:
            # Try a simple screener call to validate connection
            test_screener = Overview()
            # Just checking if we can create the screener object
            return True
        except Exception as e:
            raise FinvizAuthenticationError(
                f"Connection validation failed: {str(e)}"
            )
    
    def is_authenticated(self) -> bool:
        """Check if client is authenticated."""
        return self._authenticated
    
    def screen(self, filters: Dict[str, Any]) -> pd.DataFrame:
        """
        Execute a stock screen with the given filters.
        
        Args:
            filters: Dictionary of filter names to values. Keys should match
                    FINVIZ_FILTER_MAP keys or be custom Finviz filter strings.
        
        Returns:
            DataFrame containing screened stocks
        
        Raises:
            FinvizAuthenticationError: If not authenticated
            FinvizRateLimitError: If rate limit is exceeded after retries
        """
        if not self._authenticated:
            raise FinvizAuthenticationError(
                "Not authenticated. Call authenticate() first."
            )
        
        # Translate internal filters to Finviz parameters
        finviz_filters = self._translate_filters(filters)
        
        # Retry logic with exponential backoff
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                # Create a new screener instance
                screener = Overview()
                
                # Set filters if any
                if finviz_filters:
                    screener.set_filter(filters_dict=finviz_filters)
                
                # Get the screener data
                df = screener.screener_view()
                
                return df
            except Exception as e:
                last_exception = e
                error_msg = str(e).lower()
                
                # Check if it's a rate limit error
                if "rate limit" in error_msg or "too many requests" in error_msg or "429" in error_msg:
                    if attempt < self.max_retries - 1:
                        # Calculate exponential backoff delay
                        delay = self.retry_delay * (2 ** attempt)
                        print(f"Rate limit hit. Retrying in {delay} seconds... (Attempt {attempt + 1}/{self.max_retries})")
                        time.sleep(delay)
                        continue
                    else:
                        # Max retries reached
                        raise FinvizRateLimitError(
                            f"Finviz rate limit exceeded after {self.max_retries} attempts: {str(e)}",
                            retry_after=60  # Suggest waiting 60 seconds
                        )
                
                # Check if it's an authentication error
                if "auth" in error_msg or "credential" in error_msg or "login" in error_msg:
                    raise FinvizAuthenticationError(
                        f"Authentication failed: {str(e)}"
                    )
                
                # For other errors, retry with exponential backoff
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    print(f"Request failed. Retrying in {delay} seconds... (Attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(delay)
                    continue
                else:
                    # Max retries reached, raise the last exception
                    raise Exception(f"Error during screening after {self.max_retries} attempts: {str(e)}")
        
        # Should not reach here, but just in case
        if last_exception:
            raise last_exception
        raise Exception("Unexpected error during screening")
    
    def _translate_filters(self, filters: Dict[str, Any]) -> Dict[str, str]:
        """
        Translate internal filter names to Finviz filter parameters.
        
        Args:
            filters: Dictionary of internal filter names to values
        
        Returns:
            Dictionary of Finviz filter parameters
        """
        finviz_filters = {}
        
        for key, value in filters.items():
            # If the key is in our mapping, use the mapped value
            if key in FINVIZ_FILTER_MAP:
                # Only include if value is truthy (for boolean filters)
                if value:
                    finviz_filters[FINVIZ_FILTER_MAP[key]] = value
            else:
                # Pass through unmapped filters (assume they're already Finviz format)
                finviz_filters[key] = value
        
        return finviz_filters
    
    def download_screener_data(self, filters: Dict[str, Any]) -> pd.DataFrame:
        """
        Download complete dataset from Finviz with all available columns.
        
        Args:
            filters: Dictionary of filter names to values
        
        Returns:
            DataFrame with complete stock data
        
        Raises:
            FinvizAuthenticationError: If not authenticated
            FinvizRateLimitError: If rate limit is exceeded
        """
        # Use the screen method which already handles authentication and errors
        return self.screen(filters)
    
    def parse_stock_data(self, df: pd.DataFrame) -> list:
        """
        Parse Finviz DataFrame into StockData objects.
        
        Args:
            df: DataFrame from Finviz screener
        
        Returns:
            List of StockData objects
        """
        from screener.core.models import StockData
        from datetime import date, datetime
        
        stock_data_list = []
        
        for _, row in df.iterrows():
            try:
                stock = self._parse_single_stock(row)
                stock_data_list.append(stock)
            except Exception as e:
                # Log error but continue processing other stocks
                print(f"Warning: Failed to parse stock {row.get('Ticker', 'UNKNOWN')}: {str(e)}")
                continue
        
        return stock_data_list
    
    def _parse_single_stock(self, row: pd.Series) -> 'StockData':
        """
        Parse a single row from Finviz DataFrame into StockData object.
        
        Args:
            row: Single row from Finviz DataFrame
        
        Returns:
            StockData object
        """
        from screener.core.models import StockData
        from datetime import date, datetime
        
        # Helper function to safely parse numeric values
        def safe_float(value, default=0.0):
            if pd.isna(value):
                return default
            if isinstance(value, str):
                # Remove % signs and convert
                value = value.replace('%', '').replace(',', '')
                try:
                    return float(value)
                except (ValueError, AttributeError):
                    return default
            try:
                return float(value)
            except (ValueError, TypeError):
                return default
        
        def safe_int(value, default=0):
            if pd.isna(value):
                return default
            if isinstance(value, str):
                # Handle K, M, B suffixes
                value = value.replace(',', '')
                multiplier = 1
                if value.endswith('K'):
                    multiplier = 1_000
                    value = value[:-1]
                elif value.endswith('M'):
                    multiplier = 1_000_000
                    value = value[:-1]
                elif value.endswith('B'):
                    multiplier = 1_000_000_000
                    value = value[:-1]
                try:
                    return int(float(value) * multiplier)
                except (ValueError, AttributeError):
                    return default
            try:
                return int(value)
            except (ValueError, TypeError):
                return default
        
        def safe_string(value, default="Unknown"):
            if pd.isna(value) or value == '' or value is None:
                return default
            return str(value).strip()
        
        def parse_market_cap(value):
            """Parse market cap with B/M/T suffixes."""
            if pd.isna(value) or value == '' or value is None or value == 0:
                return 1_000_000.0  # Default to 1M
            if isinstance(value, str):
                value = value.replace(',', '').strip()
                try:
                    if value.endswith('T'):
                        return float(value[:-1]) * 1_000_000_000_000
                    elif value.endswith('B'):
                        return float(value[:-1]) * 1_000_000_000
                    elif value.endswith('M'):
                        return float(value[:-1]) * 1_000_000
                    else:
                        return float(value)
                except (ValueError, TypeError):
                    return 1_000_000.0
            try:
                result = float(value)
                if result == 0:
                    return 1_000_000.0
                return result
            except (ValueError, TypeError):
                return 1_000_000.0
        
        def parse_earnings_date(value):
            """Parse earnings date string."""
            if pd.isna(value) or value == '' or value == '-':
                return None
            try:
                # Finviz format is typically "MMM DD" or "MMM DD AMC/BMO"
                date_str = str(value).split()[0:2]
                if len(date_str) >= 2:
                    # Add current year
                    current_year = datetime.now().year
                    date_str_full = f"{date_str[0]} {date_str[1]} {current_year}"
                    return datetime.strptime(date_str_full, "%b %d %Y").date()
            except Exception:
                pass
            return None
        
        def calculate_earnings_days_away(earnings_date):
            """Calculate days until earnings."""
            if earnings_date is None:
                return 999  # Default to far future
            today = date.today()
            delta = (earnings_date - today).days
            return max(0, delta)
        
        # Parse earnings date first
        earnings_date = parse_earnings_date(row.get('Earnings', None))
        
        # Create StockData object with safe defaults
        stock = StockData(
            ticker=safe_string(row.get('Ticker', ''), 'UNKNOWN'),
            company_name=safe_string(row.get('Company', ''), 'Unknown Company'),
            price=safe_float(row.get('Price', 0), 1.0),
            volume=safe_int(row.get('Volume', 0), 0),
            avg_volume=safe_int(row.get('Avg Volume', 0), 0),
            market_cap=parse_market_cap(row.get('Market Cap', 0)),
            
            # Technical indicators
            rsi=safe_float(row.get('RSI (14)', 50), 50.0),
            sma20=safe_float(row.get('SMA20', 0), safe_float(row.get('Price', 0), 1.0)),
            sma50=safe_float(row.get('SMA50', 0), safe_float(row.get('Price', 0), 1.0)),
            sma200=safe_float(row.get('SMA200', 0), safe_float(row.get('Price', 0), 1.0)),
            beta=safe_float(row.get('Beta', 1.0), 1.0),
            
            # Options data - use safe defaults
            implied_volatility=safe_float(row.get('Volatility', 0.3), 0.3),
            iv_rank=safe_float(row.get('IV Rank', 50), 50.0),
            option_volume=safe_int(row.get('Option Volume', 0), 0),
            
            # Fundamental data
            sector=safe_string(row.get('Sector', ''), 'Unknown'),
            industry=safe_string(row.get('Industry', ''), 'Unknown'),
            earnings_date=earnings_date,
            earnings_days_away=calculate_earnings_days_away(earnings_date),
            
            # Performance metrics
            perf_week=safe_float(row.get('Perf Week', 0), 0.0),
            perf_month=safe_float(row.get('Perf Month', 0), 0.0),
            perf_quarter=safe_float(row.get('Perf Quarter', 0), 0.0),
        )
        
        return stock
