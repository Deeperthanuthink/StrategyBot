"""Base abstract class for strategy modules."""

from abc import ABC, abstractmethod
from typing import Dict, Any
from screener.core.models import StockData, StrategyAnalysis


class StrategyModule(ABC):
    """
    Abstract base class for trading strategy modules.
    
    Each strategy module defines screening criteria, scoring logic,
    and analysis methods specific to a particular options trading strategy.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """
        Strategy display name.
        
        Returns:
            Human-readable name for the strategy (e.g., "Put Credit Spread")
        """
        pass
    
    @property
    @abstractmethod
    def default_filters(self) -> Dict[str, Any]:
        """
        Default screening parameters for this strategy.
        
        Returns:
            Dictionary of filter names to default values
        """
        pass
    
    @abstractmethod
    def get_finviz_filters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert strategy parameters to Finviz filter format.
        
        Args:
            params: Strategy-specific parameters
            
        Returns:
            Dictionary mapping Finviz filter keys to values
        """
        pass
    
    @abstractmethod
    def score_stock(self, stock_data: StockData) -> float:
        """
        Calculate strategy-specific score for a stock.
        
        Args:
            stock_data: Complete stock data including technical and fundamental metrics
            
        Returns:
            Score from 0-100, where higher scores indicate better candidates
        """
        pass
    
    @abstractmethod
    def analyze_stock(self, stock_data: StockData) -> StrategyAnalysis:
        """
        Perform detailed strategy-specific analysis on a stock.
        
        Args:
            stock_data: Complete stock data including technical and fundamental metrics
            
        Returns:
            StrategyAnalysis object with detailed analysis results
        """
        pass
