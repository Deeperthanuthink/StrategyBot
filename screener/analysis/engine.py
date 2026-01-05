"""Analysis engine for strategy-specific calculations and metrics."""

import numpy as np
import pandas as pd
from scipy.stats import norm
from typing import Optional


def calculate_iv_rank(current_iv: float, iv_history: pd.Series) -> float:
    """
    Calculate Implied Volatility Rank.
    
    IV Rank = (Current IV - 52-week Low IV) / (52-week High IV - 52-week Low IV) * 100
    
    Args:
        current_iv: Current implied volatility value
        iv_history: Series of historical IV values (typically 52 weeks)
    
    Returns:
        IV Rank as a percentage (0-100)
    """
    if len(iv_history) == 0:
        return 50.0  # Default to middle if no history
    
    iv_low = iv_history.min()
    iv_high = iv_history.max()
    
    # If IV has been constant, return 50 (middle)
    if iv_high == iv_low:
        return 50.0
    
    # Calculate rank
    iv_rank = ((current_iv - iv_low) / (iv_high - iv_low)) * 100
    
    # Clamp to [0, 100] range
    return max(0.0, min(100.0, iv_rank))


def identify_support_levels(price_history: pd.DataFrame) -> list[float]:
    """
    Identify key support levels using multiple methods.
    
    Methods used:
    1. Moving averages (20, 50, 200 day)
    2. Recent swing lows (local minima)
    3. Psychological levels (round numbers)
    
    Args:
        price_history: DataFrame with columns: 'close', 'low', 'high', 'sma20', 'sma50', 'sma200'
    
    Returns:
        List of support levels sorted in descending order (highest to lowest)
    """
    supports = []
    
    if len(price_history) == 0:
        return supports
    
    # 1. MA-based supports
    if 'sma20' in price_history.columns and not pd.isna(price_history['sma20'].iloc[-1]):
        supports.append(float(price_history['sma20'].iloc[-1]))
    
    if 'sma50' in price_history.columns and not pd.isna(price_history['sma50'].iloc[-1]):
        supports.append(float(price_history['sma50'].iloc[-1]))
    
    if 'sma200' in price_history.columns and not pd.isna(price_history['sma200'].iloc[-1]):
        supports.append(float(price_history['sma200'].iloc[-1]))
    
    # 2. Swing lows (local minima in last 60 days)
    if 'low' in price_history.columns and len(price_history) > 10:
        recent = price_history.tail(min(60, len(price_history)))
        
        # Find local minima with a window of 5 days on each side
        for i in range(5, len(recent) - 5):
            window_low = recent['low'].iloc[i-5:i+6].min()
            if recent['low'].iloc[i] == window_low:
                supports.append(float(recent['low'].iloc[i]))
    
    # 3. Psychological levels (round numbers)
    if 'close' in price_history.columns:
        current_price = float(price_history['close'].iloc[-1])
        
        # Find round numbers within 10% of current price
        # Use increments of 5 for prices under 100, 10 for prices over 100
        increment = 5 if current_price < 100 else 10
        
        for level in range(0, int(current_price * 1.2) + increment, increment):
            if level > 0:
                distance_pct = abs(current_price - level) / current_price
                if distance_pct < 0.1:  # Within 10% of current price
                    supports.append(float(level))
    
    # Remove duplicates and sort in descending order
    unique_supports = sorted(set(supports), reverse=True)
    
    return unique_supports


def estimate_pop_for_pcs(
    current_price: float,
    short_strike: float,
    days_to_expiration: int,
    implied_volatility: float,
    risk_free_rate: float = 0.05
) -> float:
    """
    Estimate probability of profit for a put credit spread using delta approximation.
    
    For PCS, POP ≈ 1 - |delta of short put|
    Uses simplified Black-Scholes delta calculation.
    
    Args:
        current_price: Current stock price
        short_strike: Strike price of the short put
        days_to_expiration: Days until expiration
        implied_volatility: Implied volatility (as decimal, e.g., 0.30 for 30%)
        risk_free_rate: Risk-free interest rate (default 0.05 for 5%)
    
    Returns:
        Probability of profit as a percentage (0-100)
    """
    if days_to_expiration <= 0:
        # If expired, check if we're above the strike
        return 100.0 if current_price > short_strike else 0.0
    
    if implied_volatility <= 0:
        # If no volatility, use simple comparison
        return 100.0 if current_price > short_strike else 0.0
    
    # Time in years
    T = days_to_expiration / 365.0
    
    # Calculate d1 for Black-Scholes
    d1 = (np.log(current_price / short_strike) + 
          (risk_free_rate + 0.5 * implied_volatility**2) * T) / \
         (implied_volatility * np.sqrt(T))
    
    # Delta for put option: N(d1) - 1
    put_delta = norm.cdf(d1) - 1
    
    # POP is approximately 1 - |delta|
    pop = 1 - abs(put_delta)
    
    # Return as percentage, clamped to [0, 100]
    return max(0.0, min(100.0, pop * 100))


def estimate_pcs_premium(
    current_price: float,
    short_strike: float,
    long_strike: float,
    days_to_expiration: int,
    implied_volatility: float,
    risk_free_rate: float = 0.05
) -> dict:
    """
    Estimate premium for a put credit spread using Black-Scholes.
    
    Args:
        current_price: Current stock price
        short_strike: Strike price of the short put (higher strike)
        long_strike: Strike price of the long put (lower strike)
        days_to_expiration: Days until expiration
        implied_volatility: Implied volatility (as decimal, e.g., 0.30 for 30%)
        risk_free_rate: Risk-free interest rate (default 0.05 for 5%)
    
    Returns:
        Dictionary with:
            - credit: Net credit received for the spread
            - max_risk: Maximum risk (width - credit)
            - return_on_risk: Return on risk as percentage
    """
    if days_to_expiration <= 0 or implied_volatility <= 0:
        return {
            "credit": 0.0,
            "max_risk": short_strike - long_strike,
            "return_on_risk": 0.0
        }
    
    # Time in years
    T = days_to_expiration / 365.0
    
    def black_scholes_put(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate Black-Scholes put option price."""
        if T <= 0 or sigma <= 0:
            return max(K - S, 0)
        
        d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        
        put_price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        return max(put_price, 0)
    
    # Calculate option values
    short_put_value = black_scholes_put(current_price, short_strike, T, risk_free_rate, implied_volatility)
    long_put_value = black_scholes_put(current_price, long_strike, T, risk_free_rate, implied_volatility)
    
    # Credit is what we receive (short - long)
    credit = short_put_value - long_put_value
    
    # Max risk is the width of the spread minus the credit
    spread_width = short_strike - long_strike
    max_risk = spread_width - credit
    
    # Return on risk
    return_on_risk = (credit / max_risk * 100) if max_risk > 0 else 0.0
    
    return {
        "credit": float(credit),
        "max_risk": float(max_risk),
        "return_on_risk": float(return_on_risk)
    }


def generate_price_chart_data(
    price_history: pd.DataFrame,
    support_levels: list[float]
) -> dict:
    """
    Generate price chart data with support levels for visualization.
    
    Args:
        price_history: DataFrame with columns: 'close', 'low', 'high', and optionally 'sma20', 'sma50', 'sma200'
        support_levels: List of identified support levels
    
    Returns:
        Dictionary with chart data including:
            - dates: List of date strings
            - prices: List of closing prices
            - lows: List of low prices
            - highs: List of high prices
            - sma20: List of 20-day SMA values (if available)
            - sma50: List of 50-day SMA values (if available)
            - sma200: List of 200-day SMA values (if available)
            - support_levels: List of support level values
    """
    if len(price_history) == 0:
        return {
            "dates": [],
            "prices": [],
            "lows": [],
            "highs": [],
            "support_levels": support_levels
        }
    
    chart_data = {
        "dates": price_history.index.astype(str).tolist() if hasattr(price_history.index, 'astype') else list(range(len(price_history))),
        "prices": price_history['close'].tolist() if 'close' in price_history.columns else [],
        "lows": price_history['low'].tolist() if 'low' in price_history.columns else [],
        "highs": price_history['high'].tolist() if 'high' in price_history.columns else [],
        "support_levels": support_levels
    }
    
    # Add moving averages if available
    if 'sma20' in price_history.columns:
        chart_data['sma20'] = price_history['sma20'].tolist()
    
    if 'sma50' in price_history.columns:
        chart_data['sma50'] = price_history['sma50'].tolist()
    
    if 'sma200' in price_history.columns:
        chart_data['sma200'] = price_history['sma200'].tolist()
    
    return chart_data


def generate_iv_history_chart_data(iv_history: pd.Series, current_iv: float) -> dict:
    """
    Generate IV history chart data for visualization.
    
    Args:
        iv_history: Series of historical IV values
        current_iv: Current implied volatility value
    
    Returns:
        Dictionary with chart data including:
            - dates: List of date strings
            - iv_values: List of IV values
            - current_iv: Current IV value
            - iv_low: 52-week low IV
            - iv_high: 52-week high IV
            - iv_mean: Mean IV over the period
    """
    if len(iv_history) == 0:
        return {
            "dates": [],
            "iv_values": [],
            "current_iv": current_iv,
            "iv_low": current_iv,
            "iv_high": current_iv,
            "iv_mean": current_iv
        }
    
    return {
        "dates": iv_history.index.astype(str).tolist() if hasattr(iv_history.index, 'astype') else list(range(len(iv_history))),
        "iv_values": iv_history.tolist(),
        "current_iv": float(current_iv),
        "iv_low": float(iv_history.min()),
        "iv_high": float(iv_history.max()),
        "iv_mean": float(iv_history.mean())
    }
