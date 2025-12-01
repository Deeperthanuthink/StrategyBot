"""
Collar Strategy Implementation

A collar strategy protects stock holdings by:
1. Buying a protective put (downside protection)
2. Selling a covered call (generates income to offset put cost)

This creates a "collar" around your stock position, limiting both gains and losses.
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class CollarParameters:
    """Parameters for a collar strategy.
    
    A collar consists of:
    - Long stock position (100 shares per collar)
    - Long put (protective put below current price)
    - Short call (covered call above current price)
    """
    symbol: str
    current_price: float
    shares_owned: int  # Should be multiple of 100
    
    # Put parameters (downside protection)
    put_strike: float  # Strike price for protective put
    put_expiration: date
    
    # Call parameters (income generation)
    call_strike: float  # Strike price for covered call
    call_expiration: date
    
    # Number of collars (1 collar = 100 shares + 1 put + 1 call)
    num_collars: int
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate collar parameters.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Must own at least 100 shares per collar
        if self.shares_owned < self.num_collars * 100:
            return False, f"Need {self.num_collars * 100} shares but only own {self.shares_owned}"
        
        # Put strike should be below current price (out-of-the-money)
        if self.put_strike >= self.current_price:
            return False, f"Put strike ${self.put_strike} must be below current price ${self.current_price}"
        
        # Call strike should be above current price (out-of-the-money)
        if self.call_strike <= self.current_price:
            return False, f"Call strike ${self.call_strike} must be above current price ${self.current_price}"
        
        # Put strike should be below call strike
        if self.put_strike >= self.call_strike:
            return False, f"Put strike ${self.put_strike} must be below call strike ${self.call_strike}"
        
        # Expirations should be in the future
        if self.put_expiration < date.today():
            return False, "Put expiration must be in the future"
        if self.call_expiration < date.today():
            return False, "Call expiration must be in the future"
        
        return True, None
    
    def get_max_profit(self) -> float:
        """Calculate maximum profit potential.
        
        Max profit occurs if stock rises to call strike.
        Profit = (Call Strike - Current Price) * Shares
        Plus any net credit from options
        """
        return (self.call_strike - self.current_price) * self.shares_owned
    
    def get_max_loss(self) -> float:
        """Calculate maximum loss potential.
        
        Max loss occurs if stock drops to put strike.
        Loss = (Current Price - Put Strike) * Shares
        Minus any net credit from options
        """
        return (self.current_price - self.put_strike) * self.shares_owned
    
    def get_protection_range(self) -> tuple[float, float]:
        """Get the price range where position is protected.
        
        Returns:
            Tuple of (floor_price, ceiling_price)
        """
        return (self.put_strike, self.call_strike)


class CollarCalculator:
    """Calculator for collar strategy parameters."""
    
    def __init__(self, put_offset_percent: float = 5.0, call_offset_percent: float = 5.0,
                 put_offset_dollars: float = 0.0, call_offset_dollars: float = 0.0):
        """Initialize collar calculator.
        
        Args:
            put_offset_percent: How far below current price to place put (default 5%)
            call_offset_percent: How far above current price to place call (default 5%)
            put_offset_dollars: Fixed dollar amount below price for put (takes precedence)
            call_offset_dollars: Fixed dollar amount above price for call (takes precedence)
        """
        self.put_offset_percent = put_offset_percent
        self.call_offset_percent = call_offset_percent
        self.put_offset_dollars = put_offset_dollars
        self.call_offset_dollars = call_offset_dollars
    
    def calculate_put_strike(self, current_price: float) -> float:
        """Calculate protective put strike price.
        
        Put is placed below current price for downside protection.
        Dollar offset takes precedence over percentage.
        
        Args:
            current_price: Current stock price
            
        Returns:
            Put strike price
        """
        if self.put_offset_dollars > 0:
            return current_price - self.put_offset_dollars
        return current_price * (1 - self.put_offset_percent / 100)
    
    def calculate_call_strike(self, current_price: float) -> float:
        """Calculate covered call strike price.
        
        Call is placed above current price to generate income.
        Dollar offset takes precedence over percentage.
        
        Args:
            current_price: Current stock price
            
        Returns:
            Call strike price
        """
        if self.call_offset_dollars > 0:
            return current_price + self.call_offset_dollars
        return current_price * (1 + self.call_offset_percent / 100)
    
    def calculate_num_collars(self, shares_owned: int) -> int:
        """Calculate how many collars can be created.
        
        Each collar requires 100 shares.
        
        Args:
            shares_owned: Number of shares owned
            
        Returns:
            Number of collars that can be created
        """
        return shares_owned // 100
    
    def find_nearest_strike_below(self, target: float, available_strikes: list) -> float:
        """Find nearest available strike at or below target.
        
        Args:
            target: Target strike price
            available_strikes: List of available strikes
            
        Returns:
            Nearest strike at or below target
        """
        strikes_below = [s for s in available_strikes if s <= target]
        if not strikes_below:
            raise ValueError(f"No strikes available at or below ${target}")
        return max(strikes_below)
    
    def find_nearest_strike_above(self, target: float, available_strikes: list) -> float:
        """Find nearest available strike at or above target.
        
        Args:
            target: Target strike price
            available_strikes: List of available strikes
            
        Returns:
            Nearest strike at or above target
        """
        strikes_above = [s for s in available_strikes if s >= target]
        if not strikes_above:
            raise ValueError(f"No strikes available at or above ${target}")
        return min(strikes_above)
    
    def validate_collar_parameters(self, params: CollarParameters) -> bool:
        """Validate collar parameters.
        
        Args:
            params: CollarParameters to validate
            
        Returns:
            True if valid
            
        Raises:
            ValueError: If validation fails
        """
        is_valid, error = params.validate()
        if not is_valid:
            raise ValueError(f"Collar validation error: {error}")
        return True



@dataclass
class CoveredCallParameters:
    """Parameters for a covered call strategy.
    
    A covered call consists of:
    - Long stock position (100 shares per contract)
    - Short call (sold above current price for income)
    """
    symbol: str
    current_price: float
    shares_owned: int  # Should be multiple of 100
    
    # Call parameters
    call_strike: float  # Strike price for covered call
    call_expiration: date
    
    # Number of contracts (1 contract = 100 shares)
    num_contracts: int
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate covered call parameters.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Must own at least 100 shares per contract
        if self.shares_owned < self.num_contracts * 100:
            return False, f"Need {self.num_contracts * 100} shares but only own {self.shares_owned}"
        
        # Call strike should be above current price (out-of-the-money)
        if self.call_strike <= self.current_price:
            return False, f"Call strike ${self.call_strike} must be above current price ${self.current_price}"
        
        # Expiration should be in the future
        if self.call_expiration < date.today():
            return False, "Call expiration must be in the future"
        
        return True, None
    
    def get_max_profit(self) -> float:
        """Calculate maximum profit potential.
        
        Max profit = (Call Strike - Current Price) * Shares + Premium received
        """
        return (self.call_strike - self.current_price) * (self.num_contracts * 100)
    
    def get_breakeven(self, premium_received: float) -> float:
        """Calculate breakeven price.
        
        Breakeven = Current Price - Premium per share
        """
        premium_per_share = premium_received / (self.num_contracts * 100)
        return self.current_price - premium_per_share


class CoveredCallCalculator:
    """Calculator for covered call strategy parameters."""
    
    def __init__(self, call_offset_percent: float = 5.0, call_offset_dollars: float = 0.0,
                 expiration_days: int = 10):
        """Initialize covered call calculator.
        
        Args:
            call_offset_percent: How far above current price to place call (default 5%)
            call_offset_dollars: Fixed dollar amount above price (takes precedence)
            expiration_days: Target days until expiration (default 10)
        """
        self.call_offset_percent = call_offset_percent
        self.call_offset_dollars = call_offset_dollars
        self.expiration_days = expiration_days
    
    def calculate_call_strike(self, current_price: float) -> float:
        """Calculate covered call strike price.
        
        Call is placed above current price to generate income.
        Dollar offset takes precedence over percentage.
        
        Args:
            current_price: Current stock price
            
        Returns:
            Call strike price
        """
        if self.call_offset_dollars > 0:
            return current_price + self.call_offset_dollars
        return current_price * (1 + self.call_offset_percent / 100)
    
    def calculate_expiration(self, from_date: date = None) -> date:
        """Calculate expiration date (nearest Friday around target days).
        
        Args:
            from_date: Starting date (default: today)
            
        Returns:
            Expiration date (Friday)
        """
        from datetime import timedelta
        
        if from_date is None:
            from_date = date.today()
        
        # Target date
        target = from_date + timedelta(days=self.expiration_days)
        
        # Find nearest Friday
        days_until_friday = (4 - target.weekday()) % 7
        if days_until_friday == 0 and target.weekday() != 4:
            days_until_friday = 7
        
        # If target is already Friday, use it
        if target.weekday() == 4:
            return target
        
        # Otherwise find the closest Friday
        friday_after = target + timedelta(days=days_until_friday)
        friday_before = friday_after - timedelta(days=7)
        
        # Return the Friday closest to target
        if friday_before >= from_date + timedelta(days=1):  # At least 1 day out
            if abs((friday_before - target).days) <= abs((friday_after - target).days):
                return friday_before
        return friday_after
    
    def calculate_num_contracts(self, shares_owned: int) -> int:
        """Calculate how many contracts can be sold.
        
        Each contract requires 100 shares.
        
        Args:
            shares_owned: Number of shares owned
            
        Returns:
            Number of contracts that can be sold
        """
        return shares_owned // 100
    
    def find_nearest_strike_above(self, target: float, available_strikes: list) -> float:
        """Find nearest available strike at or above target.
        
        Args:
            target: Target strike price
            available_strikes: List of available strikes
            
        Returns:
            Nearest strike at or above target
        """
        strikes_above = [s for s in available_strikes if s >= target]
        if not strikes_above:
            raise ValueError(f"No strikes available at or above ${target}")
        return min(strikes_above)
    
    def validate_parameters(self, params: CoveredCallParameters) -> bool:
        """Validate covered call parameters.
        
        Args:
            params: CoveredCallParameters to validate
            
        Returns:
            True if valid
            
        Raises:
            ValueError: If validation fails
        """
        is_valid, error = params.validate()
        if not is_valid:
            raise ValueError(f"Covered call validation error: {error}")
        return True



@dataclass
class CashSecuredPutParameters:
    """Parameters for a cash-secured put strategy.
    
    A cash-secured put:
    - Sell put option below current price
    - Keep cash reserved to buy shares if assigned
    - Collect premium as income
    """
    symbol: str
    current_price: float
    put_strike: float
    put_expiration: date
    num_contracts: int
    cash_required: float  # Strike * 100 * num_contracts
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate cash-secured put parameters."""
        if self.put_strike >= self.current_price:
            return False, f"Put strike ${self.put_strike} should be below current price ${self.current_price}"
        if self.put_expiration < date.today():
            return False, "Put expiration must be in the future"
        if self.num_contracts <= 0:
            return False, "Number of contracts must be positive"
        return True, None


class WheelCalculator:
    """Calculator for the Wheel strategy.
    
    The Wheel Strategy:
    1. If you DON'T own shares → Sell cash-secured puts
       - Collect premium
       - If assigned, you buy shares at strike price
    
    2. If you DO own 100+ shares → Sell covered calls
       - Collect premium
       - If assigned, shares get called away (sold)
    
    Then repeat! The "wheel" keeps turning.
    """
    
    def __init__(self, put_offset_percent: float = 5.0, call_offset_percent: float = 5.0,
                 put_offset_dollars: float = 0.0, call_offset_dollars: float = 0.0,
                 expiration_days: int = 30):
        """Initialize wheel calculator.
        
        Args:
            put_offset_percent: How far below price for puts (default 5%)
            call_offset_percent: How far above price for calls (default 5%)
            put_offset_dollars: Fixed dollar offset for puts (takes precedence)
            call_offset_dollars: Fixed dollar offset for calls (takes precedence)
            expiration_days: Target days until expiration (default 30)
        """
        self.put_offset_percent = put_offset_percent
        self.call_offset_percent = call_offset_percent
        self.put_offset_dollars = put_offset_dollars
        self.call_offset_dollars = call_offset_dollars
        self.expiration_days = expiration_days
    
    def determine_phase(self, shares_owned: int) -> str:
        """Determine which phase of the wheel we're in.
        
        Args:
            shares_owned: Number of shares currently owned
            
        Returns:
            'csp' for cash-secured put phase, 'cc' for covered call phase
        """
        if shares_owned >= 100:
            return 'cc'  # Covered call phase
        return 'csp'  # Cash-secured put phase
    
    def calculate_put_strike(self, current_price: float) -> float:
        """Calculate cash-secured put strike price."""
        if self.put_offset_dollars > 0:
            return current_price - self.put_offset_dollars
        return current_price * (1 - self.put_offset_percent / 100)
    
    def calculate_call_strike(self, current_price: float) -> float:
        """Calculate covered call strike price."""
        if self.call_offset_dollars > 0:
            return current_price + self.call_offset_dollars
        return current_price * (1 + self.call_offset_percent / 100)
    
    def calculate_expiration(self, from_date: date = None) -> date:
        """Calculate expiration date (nearest Friday around target days)."""
        from datetime import timedelta
        
        if from_date is None:
            from_date = date.today()
        
        target = from_date + timedelta(days=self.expiration_days)
        
        # Find nearest Friday
        days_until_friday = (4 - target.weekday()) % 7
        if target.weekday() == 4:
            return target
        
        friday_after = target + timedelta(days=days_until_friday)
        friday_before = friday_after - timedelta(days=7)
        
        if friday_before >= from_date + timedelta(days=1):
            if abs((friday_before - target).days) <= abs((friday_after - target).days):
                return friday_before
        return friday_after
    
    def calculate_num_contracts(self, shares_owned: int) -> int:
        """Calculate contracts for covered call phase."""
        return shares_owned // 100
    
    def calculate_cash_required(self, put_strike: float, num_contracts: int) -> float:
        """Calculate cash needed to secure puts."""
        return put_strike * 100 * num_contracts
    
    def find_nearest_strike_below(self, target: float, available_strikes: list) -> float:
        """Find nearest strike at or below target."""
        strikes_below = [s for s in available_strikes if s <= target]
        if not strikes_below:
            raise ValueError(f"No strikes available at or below ${target}")
        return max(strikes_below)
    
    def find_nearest_strike_above(self, target: float, available_strikes: list) -> float:
        """Find nearest strike at or above target."""
        strikes_above = [s for s in available_strikes if s >= target]
        if not strikes_above:
            raise ValueError(f"No strikes available at or above ${target}")
        return min(strikes_above)



@dataclass
class LadderedCallParameters:
    """Parameters for a single leg of a laddered covered call."""
    symbol: str
    call_strike: float
    expiration: date
    num_contracts: int
    leg_number: int  # 1-5


class LadderedCoveredCallCalculator:
    """Calculator for Laddered Covered Call strategy.
    
    Sells covered calls on 2/3 of holdings, spread across 5 expirations:
    - Each leg = 20% of the 2/3 (so ~13.3% of total holdings per leg)
    - 5 different expiration dates (weekly intervals)
    - Diversifies expiration risk and captures different premiums
    
    Example: If you own 1500 shares
    - 2/3 = 1000 shares = 10 contracts total
    - 20% per leg = 2 contracts per expiration
    - Leg 1: 2 contracts expiring week 1
    - Leg 2: 2 contracts expiring week 2
    - Leg 3: 2 contracts expiring week 3
    - Leg 4: 2 contracts expiring week 4
    - Leg 5: 2 contracts expiring week 5
    """
    
    def __init__(self, call_offset_percent: float = 5.0, call_offset_dollars: float = 0.0,
                 coverage_ratio: float = 0.667, num_legs: int = 5):
        """Initialize laddered covered call calculator.
        
        Args:
            call_offset_percent: How far above price for calls (default 5%)
            call_offset_dollars: Fixed dollar offset (takes precedence)
            coverage_ratio: Fraction of holdings to cover (default 2/3 = 0.667)
            num_legs: Number of expiration legs (default 5)
        """
        self.call_offset_percent = call_offset_percent
        self.call_offset_dollars = call_offset_dollars
        self.coverage_ratio = coverage_ratio
        self.num_legs = num_legs
    
    def calculate_call_strike(self, current_price: float) -> float:
        """Calculate call strike price."""
        if self.call_offset_dollars > 0:
            return current_price + self.call_offset_dollars
        return current_price * (1 + self.call_offset_percent / 100)
    
    def calculate_contracts_per_leg(self, shares_owned: int) -> int:
        """Calculate contracts per leg.
        
        Args:
            shares_owned: Total shares owned
            
        Returns:
            Number of contracts per leg (minimum 1 if eligible)
        """
        # Total contracts to cover (2/3 of holdings)
        total_contracts = int((shares_owned * self.coverage_ratio) // 100)
        
        if total_contracts < self.num_legs:
            # Not enough for full ladder, return 1 per leg up to total
            return 1 if total_contracts > 0 else 0
        
        # Divide evenly across legs (20% each)
        return total_contracts // self.num_legs
    
    def calculate_total_contracts(self, shares_owned: int) -> int:
        """Calculate total contracts across all legs."""
        return int((shares_owned * self.coverage_ratio) // 100)
    
    def calculate_expirations(self, from_date: date = None) -> list:
        """Calculate 5 weekly expiration dates (Fridays).
        
        Args:
            from_date: Starting date (default: today)
            
        Returns:
            List of 5 Friday expiration dates
        """
        from datetime import timedelta
        
        if from_date is None:
            from_date = date.today()
        
        expirations = []
        
        # Find first Friday
        days_until_friday = (4 - from_date.weekday()) % 7
        if days_until_friday == 0:
            days_until_friday = 7  # Next Friday if today is Friday
        
        first_friday = from_date + timedelta(days=days_until_friday)
        
        # Generate 5 consecutive Fridays
        for i in range(self.num_legs):
            exp_date = first_friday + timedelta(weeks=i)
            expirations.append(exp_date)
        
        return expirations
    
    def calculate_ladder(self, shares_owned: int, current_price: float, 
                         from_date: date = None) -> list:
        """Calculate full ladder parameters.
        
        Args:
            shares_owned: Total shares owned
            current_price: Current stock price
            from_date: Starting date
            
        Returns:
            List of (expiration, num_contracts) tuples for each leg
        """
        contracts_per_leg = self.calculate_contracts_per_leg(shares_owned)
        expirations = self.calculate_expirations(from_date)
        
        ladder = []
        remaining_contracts = self.calculate_total_contracts(shares_owned)
        
        for i, exp in enumerate(expirations):
            # Last leg gets any remainder
            if i == len(expirations) - 1:
                leg_contracts = remaining_contracts
            else:
                leg_contracts = min(contracts_per_leg, remaining_contracts)
            
            if leg_contracts > 0:
                ladder.append({
                    'leg': i + 1,
                    'expiration': exp,
                    'contracts': leg_contracts
                })
                remaining_contracts -= leg_contracts
        
        return ladder
    
    def find_nearest_strike_above(self, target: float, available_strikes: list) -> float:
        """Find nearest strike at or above target."""
        strikes_above = [s for s in available_strikes if s >= target]
        if not strikes_above:
            raise ValueError(f"No strikes available at or above ${target}")
        return min(strikes_above)



@dataclass
class DoubleCalendarParameters:
    """Parameters for a double calendar spread.
    
    A double calendar consists of:
    - Put calendar: Sell short-term put, buy longer-term put (lower strike)
    - Call calendar: Sell short-term call, buy longer-term call (higher strike)
    """
    symbol: str
    current_price: float
    put_strike: float
    call_strike: float
    short_expiration: date  # Near-term (2 days)
    long_expiration: date   # Longer-term (4 days)
    num_contracts: int


class DoubleCalendarCalculator:
    """Calculator for Double Calendar spread strategy.
    
    A double calendar profits from time decay when the underlying
    stays between the put and call strikes.
    
    Structure:
    - Sell short-term put (2 days) + Buy long-term put (4 days) at lower strike
    - Sell short-term call (2 days) + Buy long-term call (4 days) at higher strike
    """
    
    def __init__(self, put_offset_percent: float = 2.0, call_offset_percent: float = 2.0,
                 short_days: int = 2, long_days: int = 4):
        """Initialize double calendar calculator.
        
        Args:
            put_offset_percent: How far below price for put strike (default 2%)
            call_offset_percent: How far above price for call strike (default 2%)
            short_days: Days until short leg expiration (default 2)
            long_days: Days until long leg expiration (default 4)
        """
        self.put_offset_percent = put_offset_percent
        self.call_offset_percent = call_offset_percent
        self.short_days = short_days
        self.long_days = long_days
    
    def calculate_put_strike(self, current_price: float) -> float:
        """Calculate put strike (below current price)."""
        return current_price * (1 - self.put_offset_percent / 100)
    
    def calculate_call_strike(self, current_price: float) -> float:
        """Calculate call strike (above current price)."""
        return current_price * (1 + self.call_offset_percent / 100)
    
    def calculate_short_expiration(self, from_date: date = None) -> date:
        """Calculate short leg expiration (2 days out)."""
        from datetime import timedelta
        if from_date is None:
            from_date = date.today()
        
        target = from_date + timedelta(days=self.short_days)
        # Skip weekends
        while target.weekday() >= 5:
            target += timedelta(days=1)
        return target
    
    def calculate_long_expiration(self, from_date: date = None) -> date:
        """Calculate long leg expiration (4 days out)."""
        from datetime import timedelta
        if from_date is None:
            from_date = date.today()
        
        target = from_date + timedelta(days=self.long_days)
        # Skip weekends
        while target.weekday() >= 5:
            target += timedelta(days=1)
        return target
    
    def find_nearest_strike(self, target: float, available_strikes: list) -> float:
        """Find nearest available strike to target."""
        if not available_strikes:
            raise ValueError("No strikes available")
        return min(available_strikes, key=lambda x: abs(x - target))
    
    def find_nearest_strike_below(self, target: float, available_strikes: list) -> float:
        """Find nearest strike at or below target."""
        strikes_below = [s for s in available_strikes if s <= target]
        if not strikes_below:
            raise ValueError(f"No strikes available at or below ${target}")
        return max(strikes_below)
    
    def find_nearest_strike_above(self, target: float, available_strikes: list) -> float:
        """Find nearest strike at or above target."""
        strikes_above = [s for s in available_strikes if s >= target]
        if not strikes_above:
            raise ValueError(f"No strikes available at or above ${target}")
        return min(strikes_above)



@dataclass
class ButterflyParameters:
    """Parameters for a butterfly spread.
    
    A long call butterfly consists of:
    - Buy 1 lower strike call
    - Sell 2 middle strike calls (ATM - target price)
    - Buy 1 higher strike call
    
    All same expiration. Max profit at middle strike.
    """
    symbol: str
    current_price: float
    lower_strike: float
    middle_strike: float
    upper_strike: float
    expiration: date
    num_butterflies: int
    wing_width: float  # Distance between strikes


class ButterflyCalculator:
    """Calculator for Butterfly spread strategy.
    
    A butterfly is a neutral strategy that profits when the underlying
    stays near the middle strike at expiration.
    
    Structure (Long Call Butterfly):
    - Buy 1 lower strike call
    - Sell 2 middle strike calls (ATM)
    - Buy 1 upper strike call
    
    Max profit: At middle strike
    Max loss: Net debit paid
    Best for: Range-bound markets, low volatility expectations
    """
    
    def __init__(self, wing_width: float = 5.0, expiration_days: int = 7):
        """Initialize butterfly calculator.
        
        Args:
            wing_width: Distance between strikes in dollars (default $5)
            expiration_days: Days until expiration (default 7)
        """
        self.wing_width = wing_width
        self.expiration_days = expiration_days
    
    def calculate_strikes(self, current_price: float, available_strikes: list) -> tuple:
        """Calculate butterfly strikes centered on current price.
        
        Args:
            current_price: Current stock price
            available_strikes: List of available strikes
            
        Returns:
            Tuple of (lower_strike, middle_strike, upper_strike)
        """
        # Find middle strike (ATM - closest to current price)
        middle_strike = min(available_strikes, key=lambda x: abs(x - current_price))
        
        # Calculate target lower and upper strikes
        target_lower = middle_strike - self.wing_width
        target_upper = middle_strike + self.wing_width
        
        # Find actual available strikes
        lower_strike = self.find_nearest_strike(target_lower, available_strikes)
        upper_strike = self.find_nearest_strike(target_upper, available_strikes)
        
        # Ensure symmetry - adjust if needed
        actual_lower_width = middle_strike - lower_strike
        actual_upper_width = upper_strike - middle_strike
        
        # If asymmetric, try to fix
        if abs(actual_lower_width - actual_upper_width) > 1:
            # Use the smaller width for both
            min_width = min(actual_lower_width, actual_upper_width)
            lower_strike = self.find_nearest_strike(middle_strike - min_width, available_strikes)
            upper_strike = self.find_nearest_strike(middle_strike + min_width, available_strikes)
        
        return (lower_strike, middle_strike, upper_strike)
    
    def calculate_expiration(self, from_date: date = None) -> date:
        """Calculate expiration date (nearest Friday around target days)."""
        from datetime import timedelta
        
        if from_date is None:
            from_date = date.today()
        
        target = from_date + timedelta(days=self.expiration_days)
        
        # Find nearest Friday
        days_until_friday = (4 - target.weekday()) % 7
        if target.weekday() == 4:
            return target
        
        friday_after = target + timedelta(days=days_until_friday)
        friday_before = friday_after - timedelta(days=7)
        
        if friday_before >= from_date + timedelta(days=1):
            if abs((friday_before - target).days) <= abs((friday_after - target).days):
                return friday_before
        return friday_after
    
    def find_nearest_strike(self, target: float, available_strikes: list) -> float:
        """Find nearest available strike to target."""
        if not available_strikes:
            raise ValueError("No strikes available")
        return min(available_strikes, key=lambda x: abs(x - target))
    
    def calculate_max_profit(self, lower: float, middle: float, upper: float, 
                            debit_paid: float) -> float:
        """Calculate maximum profit potential.
        
        Max profit = wing width - debit paid (per butterfly)
        Occurs when stock is exactly at middle strike at expiration.
        """
        wing_width = middle - lower
        return (wing_width * 100) - debit_paid
    
    def calculate_max_loss(self, debit_paid: float) -> float:
        """Calculate maximum loss.
        
        Max loss = debit paid (per butterfly)
        Occurs when stock is below lower strike or above upper strike.
        """
        return debit_paid
    
    def calculate_breakevens(self, lower: float, middle: float, upper: float,
                            debit_paid: float) -> tuple:
        """Calculate breakeven prices.
        
        Returns:
            Tuple of (lower_breakeven, upper_breakeven)
        """
        debit_per_share = debit_paid / 100
        lower_be = lower + debit_per_share
        upper_be = upper - debit_per_share
        return (lower_be, upper_be)
