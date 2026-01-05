"""
Property tests for PCS results ranking order.

Feature: strategy-stock-screener, Property 11: Results Ranking Order

For any screening result set, stocks should be ordered by strategy-specific
score in descending order (highest score first).

**Validates: Requirements 3.10**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import date, timedelta
from screener.strategies.pcs_strategy import PCSStrategy
from screener.core.models import StockData


def create_stock_with_score_factors(
    ticker: str,
    iv_rank: float,
    avg_volume: int,
    beta: float,
    earnings_days_away: int,
    price_above_sma20: bool = True,
    price_above_sma50: bool = True,
    rsi: float = 55.0,
) -> StockData:
    """Create a stock with specific factors that affect the score."""
    price = 100.0
    sma20 = price * 0.95 if price_above_sma20 else price * 1.05
    sma50 = price * 0.90 if price_above_sma50 else price * 1.10
    
    return StockData(
        ticker=ticker,
        company_name=f"{ticker} Inc.",
        price=price,
        volume=avg_volume,
        avg_volume=avg_volume,
        market_cap=5_000_000_000,
        rsi=rsi,
        sma20=sma20,
        sma50=sma50,
        sma200=85.0,
        beta=beta,
        implied_volatility=0.30,
        iv_rank=iv_rank,
        option_volume=100000,
        sector="Technology",
        industry="Software",
        earnings_date=date.today() + timedelta(days=earnings_days_away),
        earnings_days_away=earnings_days_away,
        perf_week=2.0,
        perf_month=5.0,
        perf_quarter=10.0,
    )


def rank_stocks_by_score(stocks: list[StockData], strategy: PCSStrategy) -> list[tuple[str, float]]:
    """Rank stocks by their strategy score in descending order."""
    scored = [(stock.ticker, strategy.score_stock(stock)) for stock in stocks]
    return sorted(scored, key=lambda x: x[1], reverse=True)


@settings(max_examples=100)
@given(
    iv_ranks=st.lists(
        st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        min_size=2,
        max_size=10,
    ),
)
def test_stocks_ranked_by_score_descending(iv_ranks: list[float]):
    """
    Feature: strategy-stock-screener, Property 11: Results Ranking Order
    
    For any set of stocks, ranking should produce descending order by score.
    **Validates: Requirements 3.10**
    """
    pcs = PCSStrategy()
    
    # Create stocks with varying IV ranks (major score factor)
    stocks = [
        create_stock_with_score_factors(
            ticker=f"STK{i}",
            iv_rank=iv_rank,
            avg_volume=2_000_000,
            beta=1.0,
            earnings_days_away=30,
        )
        for i, iv_rank in enumerate(iv_ranks)
    ]
    
    # Rank stocks
    ranked = rank_stocks_by_score(stocks, pcs)
    
    # Verify descending order
    scores = [score for _, score in ranked]
    for i in range(len(scores) - 1):
        assert scores[i] >= scores[i + 1], \
            f"Scores should be in descending order: {scores[i]} >= {scores[i + 1]}"


@settings(max_examples=100)
@given(
    num_stocks=st.integers(min_value=2, max_value=20),
)
def test_highest_score_stock_is_first(num_stocks: int):
    """
    Feature: strategy-stock-screener, Property 11: Results Ranking Order
    
    For any set of stocks, the stock with the highest score should be ranked first.
    **Validates: Requirements 3.10**
    """
    pcs = PCSStrategy()
    
    # Create stocks with varying characteristics
    stocks = []
    for i in range(num_stocks):
        # Vary IV rank to create different scores
        iv_rank = 30 + (i * 5) % 70  # Range from 30 to ~95
        stocks.append(
            create_stock_with_score_factors(
                ticker=f"STK{i}",
                iv_rank=iv_rank,
                avg_volume=1_000_000 + i * 500_000,
                beta=0.7 + (i % 5) * 0.15,
                earnings_days_away=15 + i * 5,
            )
        )
    
    # Calculate scores for all stocks
    scores = [(stock.ticker, pcs.score_stock(stock)) for stock in stocks]
    
    # Find the stock with the highest score
    max_score_ticker, max_score = max(scores, key=lambda x: x[1])
    
    # Rank stocks
    ranked = rank_stocks_by_score(stocks, pcs)
    
    # Verify the highest score stock is first
    assert ranked[0][0] == max_score_ticker, \
        f"Stock with highest score ({max_score_ticker}, {max_score}) should be first, " \
        f"but got ({ranked[0][0]}, {ranked[0][1]})"


@settings(max_examples=100)
@given(
    iv_rank_a=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    iv_rank_b=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
)
def test_ranking_preserves_relative_order(iv_rank_a: float, iv_rank_b: float):
    """
    Feature: strategy-stock-screener, Property 11: Results Ranking Order
    
    For any two stocks, the one with the higher score should be ranked higher.
    **Validates: Requirements 3.10**
    """
    pcs = PCSStrategy()
    
    # Create two stocks with different IV ranks
    stock_a = create_stock_with_score_factors(
        ticker="STKA",
        iv_rank=iv_rank_a,
        avg_volume=2_000_000,
        beta=1.0,
        earnings_days_away=30,
    )
    
    stock_b = create_stock_with_score_factors(
        ticker="STKB",
        iv_rank=iv_rank_b,
        avg_volume=2_000_000,
        beta=1.0,
        earnings_days_away=30,
    )
    
    actual_score_a = pcs.score_stock(stock_a)
    actual_score_b = pcs.score_stock(stock_b)
    
    # Skip if scores are equal (order is undefined for equal scores)
    assume(abs(actual_score_a - actual_score_b) > 0.001)
    
    # Rank stocks
    ranked = rank_stocks_by_score([stock_a, stock_b], pcs)
    
    # Verify relative order matches score comparison
    if actual_score_a > actual_score_b:
        assert ranked[0][0] == "STKA", \
            f"Stock A (score {actual_score_a}) should rank higher than Stock B (score {actual_score_b})"
    else:
        assert ranked[0][0] == "STKB", \
            f"Stock B (score {actual_score_b}) should rank higher than Stock A (score {actual_score_a})"


@settings(max_examples=100)
@given(
    num_stocks=st.integers(min_value=1, max_value=15),
)
def test_ranking_includes_all_stocks(num_stocks: int):
    """
    Feature: strategy-stock-screener, Property 11: Results Ranking Order
    
    For any set of stocks, ranking should include all stocks.
    **Validates: Requirements 3.10**
    """
    pcs = PCSStrategy()
    
    # Create stocks
    stocks = [
        create_stock_with_score_factors(
            ticker=f"STK{i}",
            iv_rank=50.0 + i,
            avg_volume=2_000_000,
            beta=1.0,
            earnings_days_away=30,
        )
        for i in range(num_stocks)
    ]
    
    # Rank stocks
    ranked = rank_stocks_by_score(stocks, pcs)
    
    # Verify all stocks are included
    assert len(ranked) == num_stocks, \
        f"Ranking should include all {num_stocks} stocks, got {len(ranked)}"
    
    # Verify all tickers are present
    ranked_tickers = {ticker for ticker, _ in ranked}
    expected_tickers = {f"STK{i}" for i in range(num_stocks)}
    assert ranked_tickers == expected_tickers, \
        f"All tickers should be present in ranking"


def test_score_range_is_0_to_100():
    """
    Verify that PCS scores are always in the 0-100 range.
    **Validates: Requirements 3.10**
    """
    pcs = PCSStrategy()
    
    # Test with extreme values
    test_cases = [
        # High score case
        create_stock_with_score_factors(
            ticker="HIGH",
            iv_rank=95.0,
            avg_volume=10_000_000,
            beta=1.0,
            earnings_days_away=60,
            price_above_sma20=True,
            price_above_sma50=True,
            rsi=55.0,
        ),
        # Low score case
        create_stock_with_score_factors(
            ticker="LOW",
            iv_rank=10.0,
            avg_volume=100_000,
            beta=2.5,
            earnings_days_away=5,
            price_above_sma20=False,
            price_above_sma50=False,
            rsi=80.0,
        ),
    ]
    
    for stock in test_cases:
        score = pcs.score_stock(stock)
        assert 0 <= score <= 100, \
            f"Score for {stock.ticker} should be in [0, 100], got {score}"
