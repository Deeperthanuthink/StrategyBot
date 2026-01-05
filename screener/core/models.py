"""Core data models for the stock screener system."""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional
import pandas as pd


@dataclass
class StockData:
    """Represents comprehensive stock data including technical indicators and options data."""
    
    # Basic identification
    ticker: str
    company_name: str
    price: float
    volume: int
    avg_volume: int
    market_cap: float
    
    # Technical indicators
    rsi: float
    sma20: float
    sma50: float
    sma200: float
    beta: float
    
    # Options data
    implied_volatility: float
    iv_rank: float
    option_volume: int
    
    # Fundamental data
    sector: str
    industry: str
    earnings_date: Optional[date]
    earnings_days_away: int
    
    # Performance metrics
    perf_week: float
    perf_month: float
    perf_quarter: float
    
    def validate(self) -> list[str]:
        """
        Validate that all required fields are present and within reasonable ranges.
        
        Returns:
            List of validation error messages. Empty list if valid.
        """
        errors = []
        
        # Required string fields
        if not self.ticker or not self.ticker.strip():
            errors.append("ticker is required and cannot be empty")
        if not self.company_name or not self.company_name.strip():
            errors.append("company_name is required and cannot be empty")
        
        # Price validations
        if self.price <= 0:
            errors.append(f"price must be positive, got {self.price}")
        
        # Volume validations
        if self.volume < 0:
            errors.append(f"volume cannot be negative, got {self.volume}")
        if self.avg_volume < 0:
            errors.append(f"avg_volume cannot be negative, got {self.avg_volume}")
        
        # Market cap validation
        if self.market_cap <= 0:
            errors.append(f"market_cap must be positive, got {self.market_cap}")
        
        # Technical indicator validations
        if not (0 <= self.rsi <= 100):
            errors.append(f"rsi must be between 0 and 100, got {self.rsi}")
        
        if self.sma20 < 0:
            errors.append(f"sma20 cannot be negative, got {self.sma20}")
        if self.sma50 < 0:
            errors.append(f"sma50 cannot be negative, got {self.sma50}")
        if self.sma200 < 0:
            errors.append(f"sma200 cannot be negative, got {self.sma200}")
        
        if self.beta < 0:
            errors.append(f"beta cannot be negative, got {self.beta}")
        
        # Options data validations
        if not (0 <= self.implied_volatility <= 10):  # IV typically 0-1000% but 10 is extreme
            errors.append(f"implied_volatility must be between 0 and 10, got {self.implied_volatility}")
        
        if not (0 <= self.iv_rank <= 100):
            errors.append(f"iv_rank must be between 0 and 100, got {self.iv_rank}")
        
        if self.option_volume < 0:
            errors.append(f"option_volume cannot be negative, got {self.option_volume}")
        
        # Fundamental data validations
        if not self.sector or not self.sector.strip():
            errors.append("sector is required and cannot be empty")
        if not self.industry or not self.industry.strip():
            errors.append("industry is required and cannot be empty")
        
        if self.earnings_days_away < 0:
            errors.append(f"earnings_days_away cannot be negative, got {self.earnings_days_away}")
        
        return errors
    
    def is_valid(self) -> bool:
        """Check if the stock data is valid."""
        return len(self.validate()) == 0


@dataclass
class StrategyAnalysis:
    """Represents strategy-specific analysis results for a stock."""
    
    ticker: str
    strategy_score: float  # 0-100
    
    # PCS-specific fields
    support_levels: list[float]
    recommended_strikes: dict  # {"short": 95, "long": 90}
    estimated_premium: float
    probability_of_profit: float
    max_risk: float
    return_on_risk: float
    
    # Visualizations
    price_chart_data: dict
    iv_history_data: dict
    
    # Recommendations
    trade_recommendation: str  # "Strong Buy", "Buy", "Hold", "Avoid"
    risk_assessment: str
    notes: list[str] = field(default_factory=list)


@dataclass
class ScreenerResults:
    """Represents the results of a screening operation."""
    
    timestamp: datetime
    strategy: str
    filters: dict
    stocks: pd.DataFrame
    metadata: dict = field(default_factory=dict)


@dataclass
class ScreeningSession:
    """Represents a historical screening session for tracking purposes."""
    
    id: str
    timestamp: datetime
    strategy: str
    num_results: int
    filters_summary: str
