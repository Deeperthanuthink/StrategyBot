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
            return (
                False,
                f"Need {self.num_collars * 100} shares but only own {self.shares_owned}",
            )

        # Put strike should be below current price (out-of-the-money)
        if self.put_strike >= self.current_price:
            return (
                False,
                f"Put strike ${self.put_strike} must be below current price ${self.current_price}",
            )

        # Call strike should be above current price (out-of-the-money)
        if self.call_strike <= self.current_price:
            return (
                False,
                f"Call strike ${self.call_strike} must be above current price ${self.current_price}",
            )

        # Put strike should be below call strike
        if self.put_strike >= self.call_strike:
            return (
                False,
                f"Put strike ${self.put_strike} must be below call strike ${self.call_strike}",
            )

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

    def __init__(
        self,
        put_offset_percent: float = 5.0,
        call_offset_percent: float = 5.0,
        put_offset_dollars: float = 0.0,
        call_offset_dollars: float = 0.0,
    ):
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
            return (
                False,
                f"Need {self.num_contracts * 100} shares but only own {self.shares_owned}",
            )

        # Call strike should be above current price (out-of-the-money)
        if self.call_strike <= self.current_price:
            return (
                False,
                f"Call strike ${self.call_strike} must be above current price ${self.current_price}",
            )

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

    def __init__(
        self,
        call_offset_percent: float = 5.0,
        call_offset_dollars: float = 0.0,
        expiration_days: int = 10,
    ):
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
            return (
                False,
                f"Put strike ${self.put_strike} should be below current price ${self.current_price}",
            )
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

    def __init__(
        self,
        put_offset_percent: float = 5.0,
        call_offset_percent: float = 5.0,
        put_offset_dollars: float = 0.0,
        call_offset_dollars: float = 0.0,
        expiration_days: int = 30,
    ):
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
            return "cc"  # Covered call phase
        return "csp"  # Cash-secured put phase

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

    def __init__(
        self,
        call_offset_percent: float = 5.0,
        call_offset_dollars: float = 0.0,
        coverage_ratio: float = 0.667,
        num_legs: int = 5,
    ):
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
        # Total contracts to cover (e.g., 2/3 of holdings)
        # First convert shares to contracts, then apply coverage ratio
        total_contracts_available = shares_owned // 100
        total_contracts = int(total_contracts_available * self.coverage_ratio)

        if total_contracts < self.num_legs:
            # Not enough for full ladder, return 1 per leg up to total
            return 1 if total_contracts > 0 else 0

        # Divide evenly across legs (20% each for 5 legs)
        return total_contracts // self.num_legs

    def calculate_total_contracts(self, shares_owned: int) -> int:
        """Calculate total contracts across all legs.
        
        Args:
            shares_owned: Total shares owned
            
        Returns:
            Total number of contracts (each contract = 100 shares)
        """
        # First convert shares to contracts (100 shares = 1 contract)
        total_contracts_available = shares_owned // 100
        
        # Apply coverage ratio (e.g., 2/3 of holdings)
        # But ensure at least 1 contract if we have 100+ shares
        covered_contracts = int(total_contracts_available * self.coverage_ratio)
        
        # If we have shares but coverage ratio rounds to 0, use at least 1 contract
        if covered_contracts == 0 and total_contracts_available >= 1:
            return 1
            
        return covered_contracts

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

    def calculate_ladder(
        self, shares_owned: int, current_price: float, from_date: date = None
    ) -> list:
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
                ladder.append({"leg": i + 1, "expiration": exp, "contracts": leg_contracts})
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
    long_expiration: date  # Longer-term (4 days)
    num_contracts: int


class DoubleCalendarCalculator:
    """Calculator for Double Calendar spread strategy.

    A double calendar profits from time decay when the underlying
    stays between the put and call strikes.

    Structure:
    - Sell short-term put (2 days) + Buy long-term put (4 days) at lower strike
    - Sell short-term call (2 days) + Buy long-term call (4 days) at higher strike
    """

    def __init__(
        self,
        put_offset_percent: float = 2.0,
        call_offset_percent: float = 2.0,
        short_days: int = 2,
        long_days: int = 4,
    ):
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

    def calculate_max_profit(
        self, lower: float, middle: float, upper: float, debit_paid: float
    ) -> float:
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

    def calculate_breakevens(
        self, lower: float, middle: float, upper: float, debit_paid: float
    ) -> tuple:
        """Calculate breakeven prices.

        Returns:
            Tuple of (lower_breakeven, upper_breakeven)
        """
        debit_per_share = debit_paid / 100
        lower_be = lower + debit_per_share
        upper_be = upper - debit_per_share
        return (lower_be, upper_be)


@dataclass
class MarriedPutParameters:
    """Parameters for a married put strategy.

    A married put consists of:
    - Buy 100 shares of stock
    - Buy 1 put option for protection

    This provides downside protection while maintaining unlimited upside.
    """

    symbol: str
    current_price: float
    shares_to_buy: int  # Typically 100
    put_strike: float
    put_expiration: date
    num_contracts: int  # 1 put per 100 shares


class MarriedPutCalculator:
    """Calculator for Married Put strategy.

    A married put is a protective strategy where you:
    1. Buy shares of stock (bullish position)
    2. Buy a put option (insurance/protection)

    Benefits:
    - Unlimited upside potential
    - Limited downside (protected below put strike)
    - Good for volatile stocks you're bullish on

    Cost: Stock price + put premium
    Max Loss: (Stock Price - Put Strike) + Put Premium
    Max Gain: Unlimited
    """

    def __init__(
        self,
        put_offset_percent: float = 5.0,
        put_offset_dollars: float = 0.0,
        expiration_days: int = 30,
        shares_per_unit: int = 100,
    ):
        """Initialize married put calculator.

        Args:
            put_offset_percent: How far below price for put strike (default 5%)
            put_offset_dollars: Fixed dollar offset (takes precedence)
            expiration_days: Days until put expiration (default 30)
            shares_per_unit: Shares to buy per unit (default 100)
        """
        self.put_offset_percent = put_offset_percent
        self.put_offset_dollars = put_offset_dollars
        self.expiration_days = expiration_days
        self.shares_per_unit = shares_per_unit

    def calculate_put_strike(self, current_price: float) -> float:
        """Calculate protective put strike price."""
        if self.put_offset_dollars > 0:
            return current_price - self.put_offset_dollars
        return current_price * (1 - self.put_offset_percent / 100)

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

    def calculate_max_loss(
        self,
        stock_price: float,
        put_strike: float,
        put_premium: float,
        shares: int = 100,
    ) -> float:
        """Calculate maximum loss.

        Max loss = (Stock Price - Put Strike) * Shares + Put Premium
        """
        return ((stock_price - put_strike) * shares) + put_premium

    def calculate_breakeven(
        self, stock_price: float, put_premium: float, shares: int = 100
    ) -> float:
        """Calculate breakeven price.

        Breakeven = Stock Price + (Put Premium / Shares)
        """
        return stock_price + (put_premium / shares)

    def find_nearest_strike_below(self, target: float, available_strikes: list) -> float:
        """Find nearest strike at or below target."""
        strikes_below = [s for s in available_strikes if s <= target]
        if not strikes_below:
            raise ValueError(f"No strikes available at or below ${target}")
        return max(strikes_below)


@dataclass
class LongStraddleParameters:
    """Parameters for a long straddle strategy.

    A long straddle consists of:
    - Buy 1 ATM call option
    - Buy 1 ATM put option (same strike as call)

    Both options have the same strike (ATM) and expiration.
    Profits from significant price movement in either direction.
    """

    symbol: str
    current_price: float
    strike: float  # ATM strike for both call and put
    expiration: date
    num_contracts: int


class LongStraddleCalculator:
    """Calculator for Long Straddle strategy.

    A long straddle is a volatility strategy where you:
    1. Buy an ATM call option
    2. Buy an ATM put option (same strike)

    Benefits:
    - Profits from large price moves in either direction
    - Unlimited profit potential on upside
    - Large profit potential on downside (down to zero)
    - No directional bias needed

    Risks:
    - Loses money if price stays near strike
    - Time decay works against you (both options lose value)
    - Requires significant move to overcome premium paid

    Best used when:
    - Expecting high volatility (earnings, news events)
    - Unsure of direction but confident in big move
    - Implied volatility is relatively low

    Cost: Call Premium + Put Premium
    Max Loss: Total premium paid (if price = strike at expiration)
    Max Gain: Unlimited (upside) or Strike - Premium (downside)
    Breakevens: Strike ± Total Premium Paid
    """

    def __init__(self, expiration_days: int = 30, num_contracts: int = 1):
        """Initialize long straddle calculator.

        Args:
            expiration_days: Days until expiration (default 30)
            num_contracts: Number of straddles to buy (default 1)
        """
        self.expiration_days = expiration_days
        self.num_contracts = num_contracts

    def calculate_strike(self, current_price: float, available_strikes: list) -> float:
        """Calculate ATM strike price (closest to current price).

        Args:
            current_price: Current stock price
            available_strikes: List of available strikes

        Returns:
            ATM strike price
        """
        if not available_strikes:
            raise ValueError("No strikes available")
        return min(available_strikes, key=lambda x: abs(x - current_price))

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

    def calculate_max_loss(
        self, call_premium: float, put_premium: float, num_contracts: int = 1
    ) -> float:
        """Calculate maximum loss.

        Max loss = Total premium paid (call + put) * 100 * contracts
        Occurs when stock price equals strike at expiration.

        Args:
            call_premium: Premium paid for call option
            put_premium: Premium paid for put option
            num_contracts: Number of straddles

        Returns:
            Maximum loss in dollars
        """
        return (call_premium + put_premium) * 100 * num_contracts

    def calculate_breakevens(self, strike: float, call_premium: float, put_premium: float) -> tuple:
        """Calculate breakeven prices.

        Lower breakeven = Strike - Total Premium
        Upper breakeven = Strike + Total Premium

        Args:
            strike: ATM strike price
            call_premium: Premium paid for call
            put_premium: Premium paid for put

        Returns:
            Tuple of (lower_breakeven, upper_breakeven)
        """
        total_premium = call_premium + put_premium
        lower_be = strike - total_premium
        upper_be = strike + total_premium
        return (lower_be, upper_be)

    def calculate_profit_at_price(
        self,
        final_price: float,
        strike: float,
        call_premium: float,
        put_premium: float,
        num_contracts: int = 1,
    ) -> float:
        """Calculate profit/loss at a given final stock price.

        Args:
            final_price: Stock price at expiration
            strike: Strike price of both options
            call_premium: Premium paid for call
            put_premium: Premium paid for put
            num_contracts: Number of straddles

        Returns:
            Profit (positive) or loss (negative) in dollars
        """
        total_premium = (call_premium + put_premium) * 100 * num_contracts

        # Call value at expiration
        call_value = max(0, final_price - strike) * 100 * num_contracts

        # Put value at expiration
        put_value = max(0, strike - final_price) * 100 * num_contracts

        return call_value + put_value - total_premium


@dataclass
class IronButterflyParameters:
    """Parameters for an iron butterfly strategy.

    An iron butterfly consists of:
    - Sell 1 ATM call
    - Sell 1 ATM put
    - Buy 1 OTM call (upper wing)
    - Buy 1 OTM put (lower wing)

    All options have the same expiration.
    Profits when stock stays near the ATM strike.
    """

    symbol: str
    current_price: float
    middle_strike: float  # ATM strike for short call and put
    lower_strike: float  # OTM put (long)
    upper_strike: float  # OTM call (long)
    expiration: date
    num_contracts: int


class IronButterflyCalculator:
    """Calculator for Iron Butterfly strategy.

    An iron butterfly is a neutral, limited-risk strategy that profits
    when the underlying stays near the middle strike at expiration.

    Structure:
    - Sell 1 ATM call (middle strike)
    - Sell 1 ATM put (middle strike)
    - Buy 1 OTM call (upper wing - protection)
    - Buy 1 OTM put (lower wing - protection)

    Benefits:
    - Defined risk (max loss = wing width - credit received)
    - Collects premium from selling ATM straddle
    - Wings provide protection against large moves
    - High probability of profit if stock stays near strike

    Risks:
    - Max profit only if stock exactly at middle strike
    - Loses money on big moves (but loss is capped)

    Best used when:
    - Expecting low volatility / range-bound market
    - Stock likely to stay near current price
    - Want defined risk with premium collection

    Max Profit: Net credit received (if stock = middle strike at expiration)
    Max Loss: Wing width - Net credit (if stock beyond wings)
    Breakevens: Middle strike ± Net credit received
    """

    def __init__(self, wing_width: float = 5.0, expiration_days: int = 30, num_contracts: int = 1):
        """Initialize iron butterfly calculator.

        Args:
            wing_width: Distance from ATM to wing strikes (default $5)
            expiration_days: Days until expiration (default 30)
            num_contracts: Number of iron butterflies (default 1)
        """
        self.wing_width = wing_width
        self.expiration_days = expiration_days
        self.num_contracts = num_contracts

    def calculate_strikes(self, current_price: float, available_strikes: list) -> tuple:
        """Calculate iron butterfly strikes.

        Args:
            current_price: Current stock price
            available_strikes: List of available strikes

        Returns:
            Tuple of (lower_strike, middle_strike, upper_strike)
        """
        if not available_strikes:
            raise ValueError("No strikes available")

        # Find middle strike (ATM - closest to current price)
        middle_strike = min(available_strikes, key=lambda x: abs(x - current_price))

        # Calculate target wing strikes
        target_lower = middle_strike - self.wing_width
        target_upper = middle_strike + self.wing_width

        # Find actual available strikes for wings
        lower_strike = self._find_nearest_strike(target_lower, available_strikes)
        upper_strike = self._find_nearest_strike(target_upper, available_strikes)

        # Ensure wings are outside middle
        if lower_strike >= middle_strike:
            strikes_below = [s for s in available_strikes if s < middle_strike]
            if strikes_below:
                lower_strike = max(strikes_below)
            else:
                raise ValueError("No strikes available below middle strike")

        if upper_strike <= middle_strike:
            strikes_above = [s for s in available_strikes if s > middle_strike]
            if strikes_above:
                upper_strike = min(strikes_above)
            else:
                raise ValueError("No strikes available above middle strike")

        return (lower_strike, middle_strike, upper_strike)

    def _find_nearest_strike(self, target: float, available_strikes: list) -> float:
        """Find nearest available strike to target."""
        return min(available_strikes, key=lambda x: abs(x - target))

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

    def calculate_max_profit(self, net_credit: float, num_contracts: int = 1) -> float:
        """Calculate maximum profit.

        Max profit = Net credit received * 100 * contracts
        Occurs when stock price equals middle strike at expiration.

        Args:
            net_credit: Net credit received per contract
            num_contracts: Number of iron butterflies

        Returns:
            Maximum profit in dollars
        """
        return net_credit * 100 * num_contracts

    def calculate_max_loss(
        self, net_credit: float, wing_width: float, num_contracts: int = 1
    ) -> float:
        """Calculate maximum loss.

        Max loss = (Wing width - Net credit) * 100 * contracts
        Occurs when stock price is beyond either wing at expiration.

        Args:
            net_credit: Net credit received per contract
            wing_width: Distance between middle and wing strikes
            num_contracts: Number of iron butterflies

        Returns:
            Maximum loss in dollars
        """
        return (wing_width - net_credit) * 100 * num_contracts

    def calculate_breakevens(self, middle_strike: float, net_credit: float) -> tuple:
        """Calculate breakeven prices.

        Lower breakeven = Middle strike - Net credit
        Upper breakeven = Middle strike + Net credit

        Args:
            middle_strike: ATM strike price
            net_credit: Net credit received per contract

        Returns:
            Tuple of (lower_breakeven, upper_breakeven)
        """
        lower_be = middle_strike - net_credit
        upper_be = middle_strike + net_credit
        return (lower_be, upper_be)


@dataclass
class ShortStrangleParameters:
    """Parameters for a short strangle strategy.

    A short strangle consists of:
    - Sell 1 OTM call (above current price)
    - Sell 1 OTM put (below current price)

    Collects premium, profits when stock stays between strikes.
    WARNING: Undefined risk on both sides!
    """

    symbol: str
    current_price: float
    put_strike: float  # OTM put (below price)
    call_strike: float  # OTM call (above price)
    expiration: date
    num_contracts: int


class ShortStrangleCalculator:
    """Calculator for Short Strangle strategy.

    A short strangle is a neutral, premium-collection strategy where you:
    1. Sell an OTM put (below current price)
    2. Sell an OTM call (above current price)

    Benefits:
    - Collects premium from both options
    - Wider profit range than short straddle
    - Profits from time decay
    - High probability of profit

    Risks:
    - UNDEFINED RISK on both sides
    - Large losses if stock moves significantly
    - Requires margin
    - Can lose more than premium collected

    Best used when:
    - Expecting low volatility / range-bound market
    - High implied volatility (collect more premium)
    - Confident stock will stay in range

    Max Profit: Net credit received (if stock between strikes at expiration)
    Max Loss: UNLIMITED on upside, substantial on downside (to zero)
    Breakevens: Put strike - Credit, Call strike + Credit
    """

    def __init__(
        self,
        put_offset_percent: float = 5.0,
        call_offset_percent: float = 5.0,
        expiration_days: int = 30,
        num_contracts: int = 1,
    ):
        """Initialize short strangle calculator.

        Args:
            put_offset_percent: How far below price for put (default 5%)
            call_offset_percent: How far above price for call (default 5%)
            expiration_days: Days until expiration (default 30)
            num_contracts: Number of strangles to sell (default 1)
        """
        self.put_offset_percent = put_offset_percent
        self.call_offset_percent = call_offset_percent
        self.expiration_days = expiration_days
        self.num_contracts = num_contracts

    def calculate_put_strike(self, current_price: float) -> float:
        """Calculate OTM put strike (below current price)."""
        return current_price * (1 - self.put_offset_percent / 100)

    def calculate_call_strike(self, current_price: float) -> float:
        """Calculate OTM call strike (above current price)."""
        return current_price * (1 + self.call_offset_percent / 100)

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

    def calculate_max_profit(self, net_credit: float, num_contracts: int = 1) -> float:
        """Calculate maximum profit.

        Max profit = Net credit received * 100 * contracts
        Occurs when stock price is between put and call strikes at expiration.
        """
        return net_credit * 100 * num_contracts

    def calculate_breakevens(
        self, put_strike: float, call_strike: float, net_credit: float
    ) -> tuple:
        """Calculate breakeven prices.

        Lower breakeven = Put strike - Net credit
        Upper breakeven = Call strike + Net credit
        """
        lower_be = put_strike - net_credit
        upper_be = call_strike + net_credit
        return (lower_be, upper_be)

    def calculate_profit_range(self, put_strike: float, call_strike: float) -> float:
        """Calculate the width of the profit range."""
        return call_strike - put_strike


@dataclass
class IronCondorParameters:
    """Parameters for an iron condor strategy.
    
    An iron condor consists of:
    - Sell OTM put spread (lower strikes)
    - Sell OTM call spread (upper strikes)
    
    All options have the same expiration.
    Profits when stock stays between the short strikes.
    """
    symbol: str
    current_price: float
    put_short_strike: float   # OTM put (sell)
    put_long_strike: float    # Further OTM put (buy)
    call_short_strike: float  # OTM call (sell)
    call_long_strike: float   # Further OTM call (buy)
    expiration: date
    num_contracts: int


class IronCondorCalculator:
    """Calculator for Iron Condor strategy.
    
    An iron condor is a neutral, limited-risk strategy that profits
    when the underlying stays between the short strikes at expiration.
    
    Structure:
    - Sell OTM put (put short strike - below current price)
    - Buy further OTM put (put long strike - protection)
    - Sell OTM call (call short strike - above current price)
    - Buy further OTM call (call long strike - protection)
    
    Benefits:
    - Defined risk (max loss = spread width - credit received)
    - Collects premium from selling both spreads
    - Wider profit range than iron butterfly
    - High probability of profit
    
    Risks:
    - Limited profit potential
    - Loses money on big moves (but loss is capped)
    - Requires 4 legs (higher commissions)
    
    Best used when:
    - Expecting low volatility / range-bound market
    - Want defined risk with premium collection
    - Stock likely to stay in a range (not too close to current price)
    
    Max Profit: Net credit received (if stock between short strikes)
    Max Loss: Spread width - Net credit (if stock beyond long strikes)
    Breakevens: Put short strike - Credit, Call short strike + Credit
    """
    
    def __init__(self, put_spread_offset_percent: float = 3.0, 
                 call_spread_offset_percent: float = 3.0,
                 spread_width: float = 5.0, expiration_days: int = 30,
                 num_contracts: int = 1):
        """Initialize iron condor calculator.
        
        Args:
            put_spread_offset_percent: How far below price for put spread (default 3%)
            call_spread_offset_percent: How far above price for call spread (default 3%)
            spread_width: Width of each spread in dollars (default $5)
            expiration_days: Days until expiration (default 30)
            num_contracts: Number of iron condors (default 1)
        """
        self.put_spread_offset_percent = put_spread_offset_percent
        self.call_spread_offset_percent = call_spread_offset_percent
        self.spread_width = spread_width
        self.expiration_days = expiration_days
        self.num_contracts = num_contracts
    
    def calculate_strikes(self, current_price: float, available_strikes: list) -> tuple:
        """Calculate iron condor strikes.
        
        Args:
            current_price: Current stock price
            available_strikes: List of available strikes
            
        Returns:
            Tuple of (put_long, put_short, call_short, call_long)
        """
        if not available_strikes:
            raise ValueError("No strikes available")
        
        # Calculate target short strikes (closer to current price)
        put_short_target = current_price * (1 - self.put_spread_offset_percent / 100)
        call_short_target = current_price * (1 + self.call_spread_offset_percent / 100)
        
        # Find actual short strikes
        put_short_strike = self._find_nearest_strike_below(put_short_target, available_strikes)
        call_short_strike = self._find_nearest_strike_above(call_short_target, available_strikes)
        
        # Calculate long strikes (further from current price for protection)
        put_long_target = put_short_strike - self.spread_width
        call_long_target = call_short_strike + self.spread_width
        
        # Find actual long strikes
        put_long_strike = self._find_nearest_strike_below(put_long_target, available_strikes)
        call_long_strike = self._find_nearest_strike_above(call_long_target, available_strikes)
        
        # Ensure proper ordering
        if put_long_strike >= put_short_strike:
            raise ValueError("Put long strike must be below put short strike")
        if call_long_strike <= call_short_strike:
            raise ValueError("Call long strike must be above call short strike")
        
        return (put_long_strike, put_short_strike, call_short_strike, call_long_strike)
    
    def _find_nearest_strike_below(self, target: float, available_strikes: list) -> float:
        """Find nearest strike at or below target."""
        strikes_below = [s for s in available_strikes if s <= target]
        if not strikes_below:
            raise ValueError(f"No strikes available at or below ${target}")
        return max(strikes_below)
    
    def _find_nearest_strike_above(self, target: float, available_strikes: list) -> float:
        """Find nearest strike at or above target."""
        strikes_above = [s for s in available_strikes if s >= target]
        if not strikes_above:
            raise ValueError(f"No strikes available at or above ${target}")
        return min(strikes_above)
    
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
    
    def calculate_max_profit(self, net_credit: float, num_contracts: int = 1) -> float:
        """Calculate maximum profit.
        
        Max profit = Net credit received * 100 * contracts
        Occurs when stock price is between short strikes at expiration.
        """
        return net_credit * 100 * num_contracts
    
    def calculate_max_loss(self, net_credit: float, spread_width: float,
                          num_contracts: int = 1) -> float:
        """Calculate maximum loss.
        
        Max loss = (Spread width - Net credit) * 100 * contracts
        Occurs when stock price is beyond either long strike at expiration.
        """
        return (spread_width - net_credit) * 100 * num_contracts
    
    def calculate_breakevens(self, put_short_strike: float, call_short_strike: float,
                            net_credit: float) -> tuple:
        """Calculate breakeven prices.
        
        Lower breakeven = Put short strike - Net credit
        Upper breakeven = Call short strike + Net credit
        """
        lower_be = put_short_strike - net_credit
        upper_be = call_short_strike + net_credit
        return (lower_be, upper_be)
    
    def calculate_profit_range(self, put_short_strike: float, call_short_strike: float) -> float:
        """Calculate the width of the profit range."""
        return call_short_strike - put_short_strike