"""Core screening engine that orchestrates the stock screening workflow."""

import pandas as pd
from typing import Dict, Any, Optional
from screener.core.models import ScreenerResults, StockData
from screener.strategies.base import StrategyModule
from screener.strategies.discovery import discover_strategies, get_strategy
from datetime import datetime


class ScreeningEngine:
    """
    Core screening engine that orchestrates the stock screening workflow.
    
    This class coordinates between the Finviz client, strategy modules,
    and analysis engine to perform complete stock screening operations.
    """
    
    def __init__(self, finviz_client=None):
        """
        Initialize the screening engine.
        
        Args:
            finviz_client: Optional FinvizClient instance for data retrieval
        """
        self.finviz_client = finviz_client
        self._strategies_cache = None
    
    def get_available_strategies(self) -> list[str]:
        """
        Get list of all available strategy names.
        
        Uses the strategy discovery mechanism to find all registered strategies.
        Results are cached for performance.
        
        Returns:
            List of strategy names (e.g., ["Put Credit Spread", "Covered Call"])
        """
        if self._strategies_cache is None:
            strategies = discover_strategies()
            self._strategies_cache = list(strategies.keys())
        
        return self._strategies_cache
    
    def load_strategy(self, strategy_name: str) -> StrategyModule:
        """
        Load a specific strategy module by name.
        
        Args:
            strategy_name: Name of the strategy to load
            
        Returns:
            StrategyModule instance
            
        Raises:
            KeyError: If strategy with given name is not found
        """
        return get_strategy(strategy_name)
    
    def screen_stocks(
        self,
        strategy_name: str,
        filters: Optional[Dict[str, Any]] = None,
        stocks_df: Optional[pd.DataFrame] = None
    ) -> ScreenerResults:
        """
        Orchestrate the complete stock screening workflow.
        
        This method:
        1. Loads the specified strategy
        2. Retrieves stock data (from Finviz or provided DataFrame)
        3. Applies filters to the data
        4. Scores each stock using the strategy
        5. Ranks results by score
        6. Returns structured results
        
        Args:
            strategy_name: Name of the strategy to use for screening
            filters: Optional dictionary of filter parameters. If None, uses strategy defaults.
            stocks_df: Optional DataFrame of stocks to screen. If None, retrieves from Finviz.
            
        Returns:
            ScreenerResults object containing filtered and ranked stocks
            
        Raises:
            KeyError: If strategy not found
            ValueError: If no data source is available (no finviz_client and no stocks_df)
        """
        # Load the strategy
        strategy = self.load_strategy(strategy_name)
        
        # Use strategy defaults if no filters provided
        if filters is None:
            filters = strategy.default_filters
        
        # Get stock data
        if stocks_df is None:
            if self.finviz_client is None:
                raise ValueError(
                    "No stock data provided and no Finviz client configured. "
                    "Either provide stocks_df or configure finviz_client."
                )
            
            # Retrieve from Finviz
            finviz_filters = strategy.get_finviz_filters(filters)
            stocks_df = self.finviz_client.screen(finviz_filters)
        
        # Apply filters to the DataFrame
        filtered_df = self.apply_filters(stocks_df, filters, strategy)
        
        # Score each stock
        if len(filtered_df) > 0:
            # Convert DataFrame rows to StockData objects and score them
            scores = []
            for _, row in filtered_df.iterrows():
                try:
                    stock_data = self._row_to_stock_data(row)
                    score = strategy.score_stock(stock_data)
                    scores.append(score)
                except Exception as e:
                    # If scoring fails, assign a low score
                    print(f"Warning: Failed to score {row.get('ticker', 'unknown')}: {e}")
                    scores.append(0.0)
            
            filtered_df['strategy_score'] = scores
        else:
            filtered_df['strategy_score'] = []
        
        # Rank results
        ranked_df = self.rank_results(filtered_df)
        
        # Create results object
        results = ScreenerResults(
            timestamp=datetime.now(),
            strategy=strategy_name,
            filters=filters,
            stocks=ranked_df,
            metadata={
                'num_results': len(ranked_df),
                'strategy_module': strategy.name
            }
        )
        
        return results
    
    def apply_filters(
        self,
        stocks_df: pd.DataFrame,
        filters: Dict[str, Any],
        strategy: StrategyModule
    ) -> pd.DataFrame:
        """
        Apply filter criteria to a DataFrame of stocks.
        
        This method handles both standard filters and conditional filters
        (e.g., earnings date filtering).
        
        Args:
            stocks_df: DataFrame containing stock data
            filters: Dictionary of filter parameters
            strategy: Strategy module (for strategy-specific filtering logic)
            
        Returns:
            Filtered DataFrame
        """
        if len(stocks_df) == 0:
            return stocks_df
        
        filtered = stocks_df.copy()
        
        # Apply numeric range filters
        numeric_filters = {
            'min_market_cap': ('market_cap', 'ge'),
            'min_volume': ('avg_volume', 'ge'),
            'price_min': ('price', 'ge'),
            'price_max': ('price', 'le'),
            'rsi_min': ('rsi', 'ge'),
            'rsi_max': ('rsi', 'le'),
            'beta_min': ('beta', 'ge'),
            'beta_max': ('beta', 'le'),
            'weekly_perf_min': ('perf_week', 'ge'),
            'weekly_perf_max': ('perf_week', 'le'),
        }
        
        for filter_key, (column, operator) in numeric_filters.items():
            if filter_key in filters and column in filtered.columns:
                value = filters[filter_key]
                if operator == 'ge':
                    filtered = filtered[filtered[column] >= value]
                elif operator == 'le':
                    filtered = filtered[filtered[column] <= value]
        
        # Apply boolean filters
        if 'above_sma20' in filters and filters['above_sma20']:
            if 'price' in filtered.columns and 'sma20' in filtered.columns:
                filtered = filtered[filtered['price'] > filtered['sma20']]
        
        if 'above_sma50' in filters and filters['above_sma50']:
            if 'price' in filtered.columns and 'sma50' in filtered.columns:
                filtered = filtered[filtered['price'] > filtered['sma50']]
        
        if 'optionable' in filters and filters['optionable']:
            if 'optionable' in filtered.columns:
                filtered = filtered[filtered['optionable'] == True]
        
        if 'shortable' in filters and filters['shortable']:
            if 'shortable' in filtered.columns:
                filtered = filtered[filtered['shortable'] == True]
        
        # Apply conditional filter: earnings date
        if 'earnings_buffer_days' in filters:
            buffer_days = filters['earnings_buffer_days']
            if 'earnings_days_away' in filtered.columns:
                filtered = filtered[filtered['earnings_days_away'] > buffer_days]
        
        return filtered
    
    def rank_results(self, stocks_df: pd.DataFrame) -> pd.DataFrame:
        """
        Rank stocks by strategy score in descending order.
        
        Args:
            stocks_df: DataFrame with 'strategy_score' column
            
        Returns:
            DataFrame sorted by strategy_score (highest first)
        """
        if len(stocks_df) == 0:
            return stocks_df
        
        if 'strategy_score' not in stocks_df.columns:
            # If no scores, return as-is
            return stocks_df
        
        # Sort by strategy_score descending (highest scores first)
        ranked = stocks_df.sort_values('strategy_score', ascending=False)
        
        # Reset index for clean output
        ranked = ranked.reset_index(drop=True)
        
        return ranked
    
    def _row_to_stock_data(self, row: pd.Series) -> StockData:
        """
        Convert a DataFrame row to a StockData object.
        
        Args:
            row: Pandas Series representing a stock
            
        Returns:
            StockData object
        """
        return StockData(
            ticker=row.get('ticker', ''),
            company_name=row.get('company_name', ''),
            price=float(row.get('price', 0)),
            volume=int(row.get('volume', 0)),
            avg_volume=int(row.get('avg_volume', 0)),
            market_cap=float(row.get('market_cap', 0)),
            rsi=float(row.get('rsi', 50)),
            sma20=float(row.get('sma20', 0)),
            sma50=float(row.get('sma50', 0)),
            sma200=float(row.get('sma200', 0)),
            beta=float(row.get('beta', 1.0)),
            implied_volatility=float(row.get('implied_volatility', 0)),
            iv_rank=float(row.get('iv_rank', 50)),
            option_volume=int(row.get('option_volume', 0)),
            sector=row.get('sector', ''),
            industry=row.get('industry', ''),
            earnings_date=row.get('earnings_date'),
            earnings_days_away=int(row.get('earnings_days_away', 999)),
            perf_week=float(row.get('perf_week', 0)),
            perf_month=float(row.get('perf_month', 0)),
            perf_quarter=float(row.get('perf_quarter', 0)),
        )
