"""Data models for position tracking and covered call orders."""

from dataclasses import dataclass
from datetime import date
from typing import List, Optional


@dataclass
class DetailedPosition:
    """Represents a detailed position in a security."""
    symbol: str
    quantity: int
    market_value: float
    average_cost: float
    unrealized_pnl: float
    position_type: str  # 'stock', 'long_call', 'long_put', 'short_call', 'short_put'


@dataclass
class OptionPosition(DetailedPosition):
    """Represents a detailed option position extending DetailedPosition."""
    strike: float
    expiration: date
    option_type: str  # 'call' or 'put'
    
    def __post_init__(self):
        """Validate option-specific fields after initialization."""
        if self.option_type not in ['call', 'put']:
            raise ValueError(f"Invalid option_type: {self.option_type}. Must be 'call' or 'put'")
        if self.strike <= 0:
            raise ValueError(f"Invalid strike price: {self.strike}. Must be positive")


@dataclass
class PositionSummary:
    """Summary of positions for a specific symbol."""
    symbol: str
    total_shares: int
    available_shares: int  # Shares not already covered by short calls
    current_price: float
    long_options: List[OptionPosition]
    existing_short_calls: List[OptionPosition]
    average_cost_basis: Optional[float] = None  # Original cost basis per share
    total_cost_basis: Optional[float] = None  # Total cost basis for all shares
    cumulative_premium_collected: Optional[float] = None  # Total premium from previous strategies
    effective_cost_basis_per_share: Optional[float] = None  # Cost basis after premium collection
    
    def __post_init__(self):
        """Validate position summary after initialization."""
        if self.total_shares < 0:
            raise ValueError(f"Invalid total_shares: {self.total_shares}. Cannot be negative")
        if self.available_shares < 0:
            raise ValueError(f"Invalid available_shares: {self.available_shares}. Cannot be negative")
        if self.available_shares > self.total_shares:
            raise ValueError(f"Available shares ({self.available_shares}) cannot exceed total shares ({self.total_shares})")
        if self.current_price <= 0:
            raise ValueError(f"Invalid current_price: {self.current_price}. Must be positive")
        
        # Validate cost basis fields if provided
        if self.average_cost_basis is not None and self.average_cost_basis <= 0:
            raise ValueError(f"Invalid average_cost_basis: {self.average_cost_basis}. Must be positive")
        if self.total_cost_basis is not None and self.total_cost_basis < 0:
            raise ValueError(f"Invalid total_cost_basis: {self.total_cost_basis}. Cannot be negative")
        if self.cumulative_premium_collected is not None and self.cumulative_premium_collected < 0:
            raise ValueError(f"Invalid cumulative_premium_collected: {self.cumulative_premium_collected}. Cannot be negative")
        if self.effective_cost_basis_per_share is not None and self.effective_cost_basis_per_share < 0:
            raise ValueError(f"Invalid effective_cost_basis_per_share: {self.effective_cost_basis_per_share}. Cannot be negative")


@dataclass
class CoveredCallOrder:
    """Represents a covered call order specification."""
    symbol: str
    strike: float
    expiration: date
    quantity: int
    underlying_shares: int
    
    def __post_init__(self):
        """Validate covered call order after initialization."""
        if self.strike <= 0:
            raise ValueError(f"Invalid strike price: {self.strike}. Must be positive")
        if self.quantity <= 0:
            raise ValueError(f"Invalid quantity: {self.quantity}. Must be positive")
        if self.underlying_shares < self.quantity * 100:
            raise ValueError(f"Insufficient underlying shares: {self.underlying_shares} for {self.quantity} contracts")