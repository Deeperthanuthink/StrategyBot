"""Put Credit Spread (PCS) strategy module."""

from typing import Dict, Any
from screener.strategies.base import StrategyModule
from screener.core.models import StockData, StrategyAnalysis
from screener.analysis.engine import (
    identify_support_levels,
    estimate_pop_for_pcs,
    estimate_pcs_premium,
    generate_price_chart_data,
    generate_iv_history_chart_data,
)
import pandas as pd


# Default filters for PCS strategy based on requirements 3.1-3.9
PCS_DEFAULT_FILTERS = {
    "min_market_cap": 2_000_000_000,  # $2B - Requirement 3.1
    "min_volume": 1_000_000,  # 1M shares - Requirement 3.2
    "price_min": 20,  # $20 - Requirement 3.3
    "price_max": 200,  # $200 - Requirement 3.3
    "rsi_min": 40,  # RSI 40 - Requirement 3.4
    "rsi_max": 70,  # RSI 70 - Requirement 3.4
    "above_sma20": True,  # Requirement 3.5
    "above_sma50": True,  # Requirement 3.5
    "weekly_perf_min": -5,  # -5% - Requirement 3.6
    "weekly_perf_max": 10,  # +10% - Requirement 3.6
    "beta_min": 0.5,  # Requirement 3.8
    "beta_max": 1.5,  # Requirement 3.8
    "optionable": True,  # Requirement 3.7
    "shortable": True,  # Requirement 3.7
    "earnings_buffer_days": 14,  # 2 weeks - Requirement 3.9
}


# Finviz filter mapping for PCS criteria
FINVIZ_FILTER_MAP = {
    "min_market_cap": "cap_midover",  # $2B+
    "min_volume": "sh_avgvol_o1000",  # Over 1M
    "price_min": "sh_price_o20",  # Over $20
    "price_max": "sh_price_u200",  # Under $200
    "rsi_min": "ta_rsi_os40",  # RSI oversold 40
    "rsi_max": "ta_rsi_ob70",  # RSI overbought 70
    "above_sma20": "ta_sma20_pa",  # Price above SMA20
    "above_sma50": "ta_sma50_pa",  # Price above SMA50
    "optionable": "sh_opt_option",  # Optionable
    "shortable": "sh_short_yes",  # Shortable
}


class PCSStrategy(StrategyModule):
    """
    Put Credit Spread (PCS) strategy implementation.
    
    This strategy screens for stocks suitable for selling put credit spreads,
    which profit when the stock stays above the short strike price.
    
    Key criteria:
    - Large cap stocks ($2B+ market cap) for liquidity
    - High volume (1M+ shares) for options liquidity
    - Price range $20-$200 for manageable position sizes
    - RSI 40-70 (not oversold or overbought)
    - Price above key moving averages (bullish trend)
    - Moderate beta (0.5-1.5) for stability
    - No earnings within 2 weeks (avoid event risk)
    """
    
    @property
    def name(self) -> str:
        """Strategy display name."""
        return "Put Credit Spread"
    
    @property
    def default_filters(self) -> Dict[str, Any]:
        """Default screening parameters for PCS strategy."""
        return PCS_DEFAULT_FILTERS.copy()
    
    def get_finviz_filters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert PCS strategy parameters to Finviz filter format.
        
        Args:
            params: Strategy-specific parameters
            
        Returns:
            Dictionary mapping Finviz filter keys to values
        """
        finviz_filters = {}
        
        for param_key, param_value in params.items():
            # Skip non-boolean False values and None
            if param_value is None:
                continue
            if isinstance(param_value, bool) and not param_value:
                continue
                
            # Map to Finviz filter if mapping exists
            if param_key in FINVIZ_FILTER_MAP:
                finviz_filters[FINVIZ_FILTER_MAP[param_key]] = param_value
            else:
                # Pass through unmapped filters
                finviz_filters[param_key] = param_value
        
        return finviz_filters

    
    def score_stock(self, stock_data: StockData) -> float:
        """
        Calculate PCS-specific score for a stock.
        
        Scoring breakdown (100 points total):
        - IV Rank (30 points): Higher IV = more premium
        - Technical strength (25 points): Price above MAs, RSI in sweet spot
        - Liquidity (20 points): Higher volume = better fills
        - Stability (25 points): Moderate beta, no near-term earnings
        
        Args:
            stock_data: Complete stock data
            
        Returns:
            Score from 0-100
        """
        score = 0.0
        
        # IV Rank scoring (30 points max)
        # Higher IV rank means more premium available
        if stock_data.iv_rank > 50:
            # Scale from 0-30 based on IV rank above 50
            iv_score = 30 * ((stock_data.iv_rank - 50) / 50)
            score += min(30.0, iv_score)
        elif stock_data.iv_rank > 30:
            # Partial credit for IV rank 30-50
            score += 15 * ((stock_data.iv_rank - 30) / 20)
        
        # Technical strength scoring (25 points max)
        # Price above SMA20 (10 points)
        if stock_data.price > stock_data.sma20:
            score += 10.0
        
        # Price above SMA50 (10 points)
        if stock_data.price > stock_data.sma50:
            score += 10.0
        
        # RSI in sweet spot 45-65 (5 points)
        if 45 <= stock_data.rsi <= 65:
            score += 5.0
        elif 40 <= stock_data.rsi <= 70:
            # Partial credit for being in acceptable range
            score += 2.5
        
        # Liquidity scoring (20 points max)
        # Scale based on average volume relative to 5M shares
        volume_ratio = stock_data.avg_volume / 5_000_000
        volume_score = min(20.0, 20.0 * volume_ratio)
        score += volume_score
        
        # Stability scoring (25 points max)
        # Beta in ideal range 0.7-1.3 (15 points)
        if 0.7 <= stock_data.beta <= 1.3:
            score += 15.0
        elif 0.5 <= stock_data.beta <= 1.5:
            # Partial credit for acceptable beta range
            score += 7.5
        
        # Earnings buffer (10 points)
        if stock_data.earnings_days_away > 14:
            score += 10.0
        elif stock_data.earnings_days_away > 7:
            # Partial credit for 7-14 days
            score += 5.0
        
        # Ensure score is clamped to [0, 100]
        return max(0.0, min(100.0, score))

    
    def analyze_stock(self, stock_data: StockData) -> StrategyAnalysis:
        """
        Perform detailed PCS analysis on a stock.
        
        Calculates:
        - Support levels for strike selection
        - Recommended strikes (short and long puts)
        - Probability of profit
        - Premium estimates
        - Trade recommendation
        
        Args:
            stock_data: Complete stock data
            
        Returns:
            StrategyAnalysis with detailed PCS analysis
        """
        # Calculate strategy score
        strategy_score = self.score_stock(stock_data)
        
        # Generate price history DataFrame for support level calculation
        # In production, this would come from historical data
        # For now, create a synthetic DataFrame based on available data
        price_history = self._create_price_history_df(stock_data)
        
        # Identify support levels
        support_levels = identify_support_levels(price_history)
        
        # Determine recommended strikes
        # Short strike: typically at or below nearest support level
        # Long strike: $5 below short strike for standard spread
        recommended_strikes = self._calculate_recommended_strikes(
            stock_data.price, 
            support_levels
        )
        
        # Calculate probability of profit
        # Default to 45 DTE (days to expiration) for standard PCS
        default_dte = 45
        pop = estimate_pop_for_pcs(
            current_price=stock_data.price,
            short_strike=recommended_strikes["short"],
            days_to_expiration=default_dte,
            implied_volatility=stock_data.implied_volatility
        )
        
        # Estimate premium
        premium_data = estimate_pcs_premium(
            current_price=stock_data.price,
            short_strike=recommended_strikes["short"],
            long_strike=recommended_strikes["long"],
            days_to_expiration=default_dte,
            implied_volatility=stock_data.implied_volatility
        )
        
        # Generate visualization data
        price_chart_data = generate_price_chart_data(price_history, support_levels)
        
        # Generate IV history data (synthetic for now)
        iv_history = self._create_iv_history(stock_data)
        iv_history_data = generate_iv_history_chart_data(iv_history, stock_data.implied_volatility)
        
        # Determine trade recommendation
        trade_recommendation = self._get_trade_recommendation(strategy_score, pop)
        
        # Risk assessment
        risk_assessment = self._assess_risk(stock_data, pop, premium_data)
        
        # Generate notes
        notes = self._generate_notes(stock_data, support_levels, pop, premium_data)
        
        return StrategyAnalysis(
            ticker=stock_data.ticker,
            strategy_score=strategy_score,
            support_levels=support_levels,
            recommended_strikes=recommended_strikes,
            estimated_premium=premium_data["credit"],
            probability_of_profit=pop,
            max_risk=premium_data["max_risk"],
            return_on_risk=premium_data["return_on_risk"],
            price_chart_data=price_chart_data,
            iv_history_data=iv_history_data,
            trade_recommendation=trade_recommendation,
            risk_assessment=risk_assessment,
            notes=notes
        )
    
    def _create_price_history_df(self, stock_data: StockData) -> pd.DataFrame:
        """Create a synthetic price history DataFrame from stock data."""
        # Create a simple DataFrame with current values
        # In production, this would be replaced with actual historical data
        import numpy as np
        
        # Generate 60 days of synthetic price history
        days = 60
        dates = pd.date_range(end=pd.Timestamp.now(), periods=days, freq='D')
        
        # Create price series with some variation around current price
        np.random.seed(hash(stock_data.ticker) % 2**32)
        price_variation = np.random.normal(0, stock_data.price * 0.02, days)
        prices = stock_data.price + np.cumsum(price_variation) - np.cumsum(price_variation)[-1]
        prices[-1] = stock_data.price  # Ensure last price matches current
        
        # Create high/low with typical daily range
        daily_range = stock_data.price * 0.015  # 1.5% typical daily range
        highs = prices + np.abs(np.random.normal(0, daily_range, days))
        lows = prices - np.abs(np.random.normal(0, daily_range, days))
        
        df = pd.DataFrame({
            'close': prices,
            'high': highs,
            'low': lows,
            'sma20': stock_data.sma20,
            'sma50': stock_data.sma50,
            'sma200': stock_data.sma200
        }, index=dates)
        
        return df
    
    def _create_iv_history(self, stock_data: StockData) -> pd.Series:
        """Create a synthetic IV history Series from stock data."""
        import numpy as np
        
        # Generate 252 days (1 year) of synthetic IV history
        days = 252
        dates = pd.date_range(end=pd.Timestamp.now(), periods=days, freq='D')
        
        # Create IV series that results in the current IV rank
        np.random.seed(hash(stock_data.ticker) % 2**32)
        
        # Calculate what the min/max IV should be based on IV rank
        current_iv = stock_data.implied_volatility
        iv_rank = stock_data.iv_rank / 100  # Convert to 0-1 scale
        
        # Estimate historical IV range
        if iv_rank > 0.5:
            iv_min = current_iv * (1 - iv_rank)
            iv_max = current_iv + (current_iv - iv_min) * (1 - iv_rank) / iv_rank
        else:
            iv_max = current_iv / iv_rank if iv_rank > 0 else current_iv * 2
            iv_min = current_iv - (iv_max - current_iv) * iv_rank / (1 - iv_rank) if iv_rank < 1 else current_iv * 0.5
        
        # Generate IV values within the range
        iv_values = np.random.uniform(iv_min, iv_max, days)
        iv_values[-1] = current_iv  # Ensure last value matches current
        
        return pd.Series(iv_values, index=dates)
    
    def _calculate_recommended_strikes(
        self, 
        current_price: float, 
        support_levels: list[float]
    ) -> dict:
        """Calculate recommended short and long strikes for PCS."""
        # Find the nearest support level below current price
        supports_below = [s for s in support_levels if s < current_price]
        
        if supports_below:
            # Use the highest support below current price
            short_strike = max(supports_below)
        else:
            # Default to 5% below current price if no support found
            short_strike = round(current_price * 0.95, 0)
        
        # Round to nearest $1 for cleaner strikes
        short_strike = round(short_strike)
        
        # Long strike is typically $5 below short strike
        # Adjust spread width based on price level
        if current_price < 50:
            spread_width = 2.5
        elif current_price < 100:
            spread_width = 5
        else:
            spread_width = 10
        
        long_strike = short_strike - spread_width
        
        return {
            "short": float(short_strike),
            "long": float(long_strike)
        }
    
    def _get_trade_recommendation(self, score: float, pop: float) -> str:
        """Determine trade recommendation based on score and POP."""
        if score >= 80 and pop >= 70:
            return "Strong Buy"
        elif score >= 65 and pop >= 60:
            return "Buy"
        elif score >= 50 and pop >= 50:
            return "Hold"
        else:
            return "Avoid"
    
    def _assess_risk(
        self, 
        stock_data: StockData, 
        pop: float, 
        premium_data: dict
    ) -> str:
        """Assess overall risk level for the trade."""
        risk_factors = []
        
        # Check earnings proximity
        if stock_data.earnings_days_away <= 7:
            risk_factors.append("Earnings within 1 week")
        elif stock_data.earnings_days_away <= 14:
            risk_factors.append("Earnings within 2 weeks")
        
        # Check beta
        if stock_data.beta > 1.5:
            risk_factors.append("High beta (volatile)")
        elif stock_data.beta < 0.5:
            risk_factors.append("Low beta (may lack movement)")
        
        # Check IV rank
        if stock_data.iv_rank < 30:
            risk_factors.append("Low IV rank (limited premium)")
        
        # Check POP
        if pop < 50:
            risk_factors.append("Low probability of profit")
        
        # Check return on risk
        if premium_data["return_on_risk"] < 10:
            risk_factors.append("Low return on risk")
        
        if len(risk_factors) == 0:
            return "Low Risk"
        elif len(risk_factors) <= 2:
            return f"Moderate Risk: {', '.join(risk_factors)}"
        else:
            return f"High Risk: {', '.join(risk_factors)}"
    
    def _generate_notes(
        self, 
        stock_data: StockData, 
        support_levels: list[float],
        pop: float,
        premium_data: dict
    ) -> list[str]:
        """Generate analysis notes for the trade."""
        notes = []
        
        # IV rank note
        if stock_data.iv_rank >= 70:
            notes.append(f"High IV rank ({stock_data.iv_rank:.1f}%) - excellent premium opportunity")
        elif stock_data.iv_rank >= 50:
            notes.append(f"Elevated IV rank ({stock_data.iv_rank:.1f}%) - good premium available")
        else:
            notes.append(f"IV rank at {stock_data.iv_rank:.1f}% - consider waiting for higher IV")
        
        # Technical note
        if stock_data.price > stock_data.sma20 > stock_data.sma50:
            notes.append("Strong uptrend - price above both SMA20 and SMA50")
        elif stock_data.price > stock_data.sma20:
            notes.append("Short-term bullish - price above SMA20")
        
        # Support level note
        if support_levels:
            nearest_support = max([s for s in support_levels if s < stock_data.price], default=None)
            if nearest_support:
                distance_pct = (stock_data.price - nearest_support) / stock_data.price * 100
                notes.append(f"Nearest support at ${nearest_support:.2f} ({distance_pct:.1f}% below)")
        
        # POP note
        notes.append(f"Estimated probability of profit: {pop:.1f}%")
        
        # Premium note
        if premium_data["credit"] > 0:
            notes.append(f"Estimated credit: ${premium_data['credit']:.2f} per spread")
            notes.append(f"Return on risk: {premium_data['return_on_risk']:.1f}%")
        
        return notes
