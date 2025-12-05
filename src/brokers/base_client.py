"""Base client interface for all brokers."""
from abc import ABC, abstractmethod
from datetime import datetime, date
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class OptionContract:
    """Represents an option contract."""
    symbol: str
    strike: float
    expiration: date
    option_type: str  # 'put' or 'call'


@dataclass
class SpreadOrder:
    """Represents a put credit spread order."""
    symbol: str
    short_strike: float
    long_strike: float
    expiration: date
    quantity: int
    order_type: str = "limit"
    time_in_force: str = "gtc"


@dataclass
class OrderResult:
    """Result of an order submission."""
    success: bool
    order_id: Optional[str]
    status: Optional[str]
    error_message: Optional[str]


@dataclass
class AccountInfo:
    """Account information."""
    account_number: str
    buying_power: float
    cash: float
    portfolio_value: float


@dataclass
class Position:
    """Represents a stock position."""
    symbol: str
    quantity: int
    avg_cost: float
    current_price: float
    market_value: float


class BaseBrokerClient(ABC):
    """Abstract base class for all broker clients."""
    
    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticate with the broker API.
        
        Returns:
            True if authentication successful, False otherwise
        """
        pass
    
    @abstractmethod
    def is_market_open(self) -> bool:
        """Check if the market is currently open.
        
        Returns:
            True if market is open, False otherwise
        """
        pass
    
    @abstractmethod
    def get_market_open_time(self) -> datetime:
        """Get the next market open time.
        
        Returns:
            Datetime of next market open
        """
        pass
    
    @abstractmethod
    def get_current_price(self, symbol: str) -> float:
        """Get the current market price for a symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Current price as float
        """
        pass
    
    @abstractmethod
    def get_option_chain(self, symbol: str, expiration: date) -> List[OptionContract]:
        """Get option chain for a symbol and expiration date.
        
        Args:
            symbol: Stock symbol
            expiration: Option expiration date
            
        Returns:
            List of OptionContract objects for put options
        """
        pass
    
    @abstractmethod
    def submit_spread_order(self, spread: SpreadOrder) -> OrderResult:
        """Submit a put credit spread order.
        
        Args:
            spread: SpreadOrder object with order details
            
        Returns:
            OrderResult with order ID and status
        """
        pass
    
    @abstractmethod
    def get_account_info(self) -> AccountInfo:
        """Get account information.
        
        Returns:
            AccountInfo object with account details
        """
        pass
    
    @abstractmethod
    def get_broker_name(self) -> str:
        """Get the name of the broker.
        
        Returns:
            Broker name string
        """
        pass
    
    @abstractmethod
    def get_positions(self) -> List['Position']:
        """Get all current stock positions.
        
        Returns:
            List of Position objects
        """
        pass
    
    @abstractmethod
    def get_position(self, symbol: str) -> Optional['Position']:
        """Get position for a specific symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Position object if found, None otherwise
        """
        pass
    
    @abstractmethod
    def submit_collar_order(self, symbol: str, put_strike: float, call_strike: float,
                           expiration: date, num_collars: int) -> OrderResult:
        """Submit a collar order (protective put + covered call).
        
        Args:
            symbol: Stock symbol
            put_strike: Strike price for protective put
            call_strike: Strike price for covered call
            expiration: Option expiration date
            num_collars: Number of collars (1 collar = 100 shares + 1 put + 1 call)
            
        Returns:
            OrderResult with order ID and status
        """
        pass
    
    @abstractmethod
    def submit_covered_call_order(self, symbol: str, call_strike: float,
                                  expiration: date, num_contracts: int) -> OrderResult:
        """Submit a covered call order (sell call against stock position).
        
        Args:
            symbol: Stock symbol
            call_strike: Strike price for covered call
            expiration: Option expiration date
            num_contracts: Number of contracts (1 contract = 100 shares)
            
        Returns:
            OrderResult with order ID and status
        """
        pass

    @abstractmethod
    def submit_cash_secured_put_order(self, symbol: str, put_strike: float,
                                      expiration: date, num_contracts: int) -> OrderResult:
        """Submit a cash-secured put order (sell put to potentially buy shares).
        
        Args:
            symbol: Stock symbol
            put_strike: Strike price for put
            expiration: Option expiration date
            num_contracts: Number of contracts to sell
            
        Returns:
            OrderResult with order ID and status
        """
        pass

    @abstractmethod
    def submit_double_calendar_order(self, symbol: str, put_strike: float, call_strike: float,
                                     short_expiration: date, long_expiration: date,
                                     num_contracts: int) -> OrderResult:
        """Submit a double calendar spread order.
        
        Args:
            symbol: Stock symbol
            put_strike: Strike for put calendar
            call_strike: Strike for call calendar
            short_expiration: Near-term expiration (sell)
            long_expiration: Longer-term expiration (buy)
            num_contracts: Number of contracts per leg
            
        Returns:
            OrderResult with order ID and status
        """
        pass

    @abstractmethod
    def submit_butterfly_order(self, symbol: str, lower_strike: float, middle_strike: float,
                               upper_strike: float, expiration: date, 
                               num_butterflies: int) -> OrderResult:
        """Submit a butterfly spread order.
        
        Args:
            symbol: Stock symbol
            lower_strike: Lower wing strike (buy 1 call)
            middle_strike: Body strike (sell 2 calls)
            upper_strike: Upper wing strike (buy 1 call)
            expiration: Option expiration date
            num_butterflies: Number of butterflies
            
        Returns:
            OrderResult with order ID and status
        """
        pass

    @abstractmethod
    def submit_married_put_order(self, symbol: str, shares: int, put_strike: float,
                                 expiration: date) -> OrderResult:
        """Submit a married put order (buy stock + buy protective put).
        
        Args:
            symbol: Stock symbol
            shares: Number of shares to buy (typically 100)
            put_strike: Strike price for protective put
            expiration: Option expiration date
            
        Returns:
            OrderResult with order ID and status
        """
        pass

    @abstractmethod
    def submit_long_straddle_order(self, symbol: str, strike: float,
                                   expiration: date, num_contracts: int) -> OrderResult:
        """Submit a long straddle order (buy ATM call + buy ATM put).
        
        Args:
            symbol: Stock symbol
            strike: ATM strike price for both call and put
            expiration: Option expiration date
            num_contracts: Number of straddles to buy
            
        Returns:
            OrderResult with order ID and status
        """
        pass

    @abstractmethod
    def submit_iron_butterfly_order(self, symbol: str, lower_strike: float,
                                    middle_strike: float, upper_strike: float,
                                    expiration: date, num_contracts: int) -> OrderResult:
        """Submit an iron butterfly order.
        
        Iron butterfly structure:
        - Sell 1 ATM call (middle strike)
        - Sell 1 ATM put (middle strike)
        - Buy 1 OTM call (upper strike - protection)
        - Buy 1 OTM put (lower strike - protection)
        
        Args:
            symbol: Stock symbol
            lower_strike: Lower wing strike (buy put)
            middle_strike: ATM strike (sell call + sell put)
            upper_strike: Upper wing strike (buy call)
            expiration: Option expiration date
            num_contracts: Number of iron butterflies
            
        Returns:
            OrderResult with order ID and status
        """
        pass

    @abstractmethod
    def submit_short_strangle_order(self, symbol: str, put_strike: float,
                                    call_strike: float, expiration: date,
                                    num_contracts: int) -> OrderResult:
        """Submit a short strangle order (sell OTM put + sell OTM call).
        
        WARNING: This strategy has UNDEFINED RISK on both sides!
        
        Args:
            symbol: Stock symbol
            put_strike: OTM put strike (below current price)
            call_strike: OTM call strike (above current price)
            expiration: Option expiration date
            num_contracts: Number of strangles to sell
            
        Returns:
            OrderResult with order ID and status
        """
        pass
