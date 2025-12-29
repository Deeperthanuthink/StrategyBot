"""Trading calendar utilities using Tradier Market Calendar API."""

from datetime import date, datetime, timedelta
from typing import Optional, Dict, Set
from dataclasses import dataclass
import requests
import os


@dataclass
class CachedCalendar:
    """Cached calendar data for a month."""
    month: int
    year: int
    trading_days: Set[date]
    holidays: Dict[date, str]
    fetched_at: datetime
    
    def is_stale(self, max_age_hours: int = 24) -> bool:
        """Check if cache is older than max_age_hours."""
        age = datetime.now() - self.fetched_at
        return age.total_seconds() > (max_age_hours * 3600)


# Fallback holidays - only used when API is unavailable
FALLBACK_HOLIDAYS = {
    # 2025
    date(2025, 1, 1),   # New Year's Day
    date(2025, 1, 20),  # MLK Day
    date(2025, 2, 17),  # Presidents' Day
    date(2025, 4, 18),  # Good Friday
    date(2025, 5, 26),  # Memorial Day
    date(2025, 6, 19),  # Juneteenth
    date(2025, 7, 4),   # Independence Day
    date(2025, 9, 1),   # Labor Day
    date(2025, 11, 27), # Thanksgiving
    date(2025, 12, 25), # Christmas
    # 2026
    date(2026, 1, 1),   # New Year's Day
    date(2026, 1, 19),  # MLK Day
    date(2026, 2, 16),  # Presidents' Day
    date(2026, 4, 3),   # Good Friday
    date(2026, 5, 25),  # Memorial Day
    date(2026, 6, 19),  # Juneteenth
    date(2026, 7, 3),   # Independence Day (observed)
    date(2026, 9, 7),   # Labor Day
    date(2026, 11, 26), # Thanksgiving
    date(2026, 12, 25), # Christmas
}


class TradingCalendar:
    """Utility for trading day calculations using Tradier Market Calendar API.
    
    Uses the Tradier /v1/markets/calendar endpoint to get accurate market
    open/close status for any date, including holidays.
    """
    
    def __init__(self, api_token: str, is_sandbox: bool = False):
        """Initialize with Tradier API credentials.
        
        Args:
            api_token: Tradier API access token
            is_sandbox: Whether to use sandbox API
        """
        self.api_token = api_token
        self.base_url = "https://sandbox.tradier.com" if is_sandbox else "https://api.tradier.com"
        self._cache: Dict[tuple, CachedCalendar] = {}
    
    def get_market_calendar(self, month: int, year: int) -> Optional[Dict]:
        """Fetch market calendar for a given month from Tradier API.
        
        Endpoint: GET /v1/markets/calendar
        Params: month, year
        
        Args:
            month: Month number (1-12)
            year: Year (e.g., 2025)
            
        Returns:
            Dict with calendar data including open/close status for each day,
            or None if API call fails
        """
        # Check cache first
        cache_key = (month, year)
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if not cached.is_stale():
                return {
                    'trading_days': cached.trading_days,
                    'holidays': cached.holidays
                }
        
        # Make API call
        url = f"{self.base_url}/v1/markets/calendar"
        headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Accept': 'application/json'
        }
        params = {'month': month, 'year': year}
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Parse response
            trading_days = set()
            holidays = {}
            
            calendar_data = data.get('calendar', {})
            days_data = calendar_data.get('days', {})
            day_list = days_data.get('day', [])
            
            # Handle single day response (not a list)
            if isinstance(day_list, dict):
                day_list = [day_list]
            
            for day_entry in day_list:
                day_date = datetime.strptime(day_entry['date'], '%Y-%m-%d').date()
                status = day_entry.get('status', 'closed')
                
                if status == 'open':
                    trading_days.add(day_date)
                else:
                    description = day_entry.get('description', 'Market Closed')
                    holidays[day_date] = description
            
            # Cache the result
            self._cache[cache_key] = CachedCalendar(
                month=month,
                year=year,
                trading_days=trading_days,
                holidays=holidays,
                fetched_at=datetime.now()
            )
            
            return {
                'trading_days': trading_days,
                'holidays': holidays
            }
            
        except Exception as e:
            # Log error but don't raise - fallback will be used
            print(f"Warning: Failed to fetch market calendar: {e}")
            return None
    
    def is_trading_day(self, check_date: date) -> bool:
        """Check if a date is a valid trading day using Tradier API.
        
        Queries the market calendar and checks the 'status' field.
        Falls back to weekend-only check if API unavailable.
        
        Args:
            check_date: Date to check
            
        Returns:
            True if the date is a trading day, False otherwise
        """
        # Check if weekend
        if check_date.weekday() >= 5:  # Saturday=5, Sunday=6
            return False
        
        # Try to get calendar data from API
        calendar_data = self.get_market_calendar(check_date.month, check_date.year)
        
        if calendar_data:
            # Use API data
            return check_date in calendar_data['trading_days']
        else:
            # Fallback: check static holidays
            return check_date not in FALLBACK_HOLIDAYS
    
    def get_next_trading_day(self, from_date: date) -> date:
        """Get the next valid trading day from a given date.
        
        Uses Tradier calendar to find the next day with status='open'.
        
        Args:
            from_date: Starting date
            
        Returns:
            Next valid trading day
        """
        current = from_date + timedelta(days=1)
        max_iterations = 10  # Prevent infinite loops
        
        for _ in range(max_iterations):
            if self.is_trading_day(current):
                return current
            current += timedelta(days=1)
        
        # If we couldn't find a trading day in 10 days, something is wrong
        # Return the date 10 days out as a fallback
        return from_date + timedelta(days=10)
    
    def get_0dte_expiration(self, execution_date: Optional[date] = None) -> date:
        """Get the appropriate 0DTE expiration date.
        
        If execution_date is a trading day, returns execution_date.
        Otherwise, returns the next trading day.
        
        Args:
            execution_date: Date to check (defaults to today)
            
        Returns:
            Appropriate expiration date for 0DTE options
        """
        if execution_date is None:
            execution_date = date.today()
        
        if self.is_trading_day(execution_date):
            return execution_date
        else:
            return self.get_next_trading_day(execution_date)


def get_trading_calendar(
    api_token: Optional[str] = None,
    is_sandbox: bool = False
) -> TradingCalendar:
    """Factory function to create TradingCalendar instance.
    
    If api_token not provided, attempts to read from environment.
    
    Args:
        api_token: Tradier API access token (optional)
        is_sandbox: Whether to use sandbox API
        
    Returns:
        TradingCalendar instance
        
    Raises:
        ValueError: If api_token not provided and not in environment
    """
    if api_token is None:
        api_token = os.getenv('TRADIER_API_TOKEN')
        if api_token is None:
            raise ValueError(
                "api_token must be provided or TRADIER_API_TOKEN "
                "environment variable must be set"
            )
    
    return TradingCalendar(api_token=api_token, is_sandbox=is_sandbox)
