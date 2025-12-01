"""Strategy calculator for options trading."""
from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional
from src.config.models import Config


@dataclass
class SpreadParameters:
    """Parameters for a put credit spread."""
    symbol: str
    short_strike: float
    long_strike: float
    expiration: date
    current_price: float
    spread_width: float
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate spread parameters.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if self.short_strike <= 0:
            return False, "Short strike must be positive"
        if self.long_strike <= 0:
            return False, "Long strike must be positive"
        if self.short_strike <= self.long_strike:
            return False, "Short strike must be greater than long strike for put credit spread"
        if self.spread_width <= 0:
            return False, "Spread width must be positive"
        if abs((self.short_strike - self.long_strike) - self.spread_width) > 0.01:
            return False, "Actual spread width doesn't match configured spread width"
        if self.expiration < date.today():
            return False, "Expiration date cannot be in the past"
        return True, None


class StrategyCalculator:
    """Calculator for options trading strategy parameters."""
    
    def __init__(self, config: Config):
        """Initialize the StrategyCalculator.
        
        Args:
            config: Configuration object with strategy parameters
        """
        self._config = config
    
    def calculate_short_strike(self, current_price: float, offset_percent: float = 0.0, 
                                offset_dollars: float = 0.0) -> float:
        """Calculate the short put strike price.
        
        The short strike is calculated either as a fixed dollar amount below
        the current price (if offset_dollars > 0) or as a percentage below.
        
        Args:
            current_price: Current market price of the underlying
            offset_percent: Percentage below market price (e.g., 5.0 for 5%)
            offset_dollars: Fixed dollar amount below market price (takes precedence)
            
        Returns:
            Short strike price
            
        Raises:
            ValueError: If inputs are invalid
        """
        if current_price <= 0:
            raise ValueError("Current price must be positive")
        
        # Dollar offset takes precedence
        if offset_dollars > 0:
            short_strike = current_price - offset_dollars
        else:
            if offset_percent <= 0 or offset_percent > 100:
                raise ValueError("Offset percent must be between 0 and 100")
            short_strike = current_price * (1 - offset_percent / 100)
        
        return short_strike
    
    def calculate_long_strike(self, short_strike: float, spread_width: float) -> float:
        """Calculate the long put strike price.
        
        The long strike is calculated by subtracting the spread width from the short strike.
        
        Args:
            short_strike: Short put strike price
            spread_width: Dollar width of the spread
            
        Returns:
            Long strike price
            
        Raises:
            ValueError: If inputs are invalid
        """
        if short_strike <= 0:
            raise ValueError("Short strike must be positive")
        if spread_width <= 0:
            raise ValueError("Spread width must be positive")
        if spread_width >= short_strike:
            raise ValueError("Spread width cannot be greater than or equal to short strike")
        
        long_strike = short_strike - spread_width
        return long_strike
    
    def calculate_expiration_date(self, execution_date: date, offset_weeks: int) -> date:
        """Calculate the expiration date for the options.
        
        The expiration date is the Friday of the week that is offset_weeks after
        the execution date.
        
        Args:
            execution_date: Date when the trade is executed
            offset_weeks: Number of weeks to offset from execution date
            
        Returns:
            Expiration date (Friday)
            
        Raises:
            ValueError: If inputs are invalid
        """
        if offset_weeks <= 0:
            raise ValueError("Offset weeks must be positive")
        
        # Calculate target date by adding weeks
        target_date = execution_date + timedelta(weeks=offset_weeks)
        
        # Find the Friday of that week
        # weekday() returns 0=Monday, 4=Friday
        days_until_friday = (4 - target_date.weekday()) % 7
        
        # If target_date is already Friday, use it; otherwise find next Friday
        if target_date.weekday() == 4:
            expiration = target_date
        else:
            expiration = target_date + timedelta(days=days_until_friday)
        
        return expiration
    
    def find_nearest_strike(self, target_strike: float, available_strikes: List[float]) -> float:
        """Find the nearest available strike to the target strike.
        
        Args:
            target_strike: Target strike price
            available_strikes: List of available strike prices
            
        Returns:
            Nearest available strike price
            
        Raises:
            ValueError: If no strikes are available or inputs are invalid
        """
        if not available_strikes:
            raise ValueError("No available strikes provided")
        if target_strike <= 0:
            raise ValueError("Target strike must be positive")
        
        # Find the strike with minimum distance to target
        nearest_strike = min(available_strikes, key=lambda x: abs(x - target_strike))
        return nearest_strike
    
    def find_nearest_strike_below(self, target_strike: float, available_strikes: List[float]) -> float:
        """Find the nearest available strike at or below the target strike.
        
        For put credit spreads, we want strikes below the current price.
        This method finds the highest available strike that is at or below the target.
        
        Args:
            target_strike: Target strike price
            available_strikes: List of available strike prices (sorted)
            
        Returns:
            Nearest available strike at or below target
            
        Raises:
            ValueError: If no strikes are available below target or inputs are invalid
        """
        if not available_strikes:
            raise ValueError("No available strikes provided")
        if target_strike <= 0:
            raise ValueError("Target strike must be positive")
        
        # Filter strikes that are at or below target
        strikes_below = [strike for strike in available_strikes if strike <= target_strike]
        
        if not strikes_below:
            raise ValueError(f"No available strikes at or below target strike ${target_strike:.2f}")
        
        # Return the highest strike that's still below target (closest to target)
        nearest_below = max(strikes_below)
        return nearest_below
    
    def validate_spread_parameters(self, spread: SpreadParameters) -> bool:
        """Validate spread parameters.
        
        Args:
            spread: SpreadParameters object to validate
            
        Returns:
            True if valid
            
        Raises:
            ValueError: If validation fails with error message
        """
        is_valid, error_message = spread.validate()
        if not is_valid:
            raise ValueError(f"Spread validation error: {error_message}")
        return True
