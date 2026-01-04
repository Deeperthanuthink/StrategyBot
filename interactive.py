#!/usr/bin/env python3
"""
Interactive Options Trading Bot

Select a single stock and strategy for immediate execution.
Suppresses noisy Lumibot output for cleaner interface.
"""

import sys
import os
import json
import tempfile
import logging
import warnings
from datetime import date
from src.utils.trading_calendar import TradingCalendar

# Suppress noisy output BEFORE importing anything else
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
warnings.filterwarnings("ignore")
logging.getLogger("lumibot").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)
logging.getLogger("apscheduler").setLevel(logging.CRITICAL)
logging.getLogger("alpaca").setLevel(logging.CRITICAL)
logging.getLogger("alpaca.trading.stream").setLevel(logging.CRITICAL)
logging.getLogger("websockets").setLevel(logging.CRITICAL)

# Suppress Alpaca websocket errors when using Tradier
# This prevents "failed to authenticate" errors from Alpaca's background processes
import threading
_original_excepthook = threading.excepthook

def _custom_excepthook(args):
    """Custom exception hook to suppress Alpaca websocket errors."""
    if args.exc_type == ValueError and "failed to authenticate" in str(args.exc_value):
        # Silently ignore Alpaca websocket authentication errors
        return
    if "alpaca" in str(args.exc_value).lower() and "websocket" in str(args.exc_value).lower():
        return
    # For all other exceptions, use the original handler
    _original_excepthook(args)

threading.excepthook = _custom_excepthook

from dotenv import load_dotenv

load_dotenv()


def suppress_output():
    """Suppress noisy library output."""
    # Suppress various loggers including Alpaca websocket noise
    for logger_name in [
        "lumibot",
        "urllib3",
        "apscheduler",
        "requests",
        "tradier",
        "alpaca",
        "alpaca.trading.stream",
        "websockets",
        "asyncio",
    ]:
        logging.getLogger(logger_name).setLevel(logging.CRITICAL)


def clear_screen():
    """Clear terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")


def calculate_ema_from_bars(symbol: str, api_token: str, is_sandbox: bool, period: int = 20, lookback_minutes: int = 100) -> float:
    """Calculate EMA from 1-minute bars using Tradier timesales API.
    
    Args:
        symbol: Stock symbol
        api_token: Tradier API token
        is_sandbox: Whether using sandbox API
        period: EMA period (default 20)
        lookback_minutes: How many minutes of data to fetch (default 100)
        
    Returns:
        Current EMA value, or None if calculation fails
    """
    import requests
    from datetime import datetime, timedelta
    
    try:
        base_url = "https://sandbox.tradier.com" if is_sandbox else "https://api.tradier.com"
        
        # Get timesales data (1-minute intervals)
        # Tradier timesales endpoint: /v1/markets/timesales
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=lookback_minutes)
        
        response = requests.get(
            f"{base_url}/v1/markets/timesales",
            params={
                "symbol": symbol,
                "interval": "1min",
                "start": start_time.strftime("%Y-%m-%d %H:%M"),
                "end": end_time.strftime("%Y-%m-%d %H:%M"),
            },
            headers={
                "Authorization": f"Bearer {api_token}",
                "Accept": "application/json"
            },
            timeout=10
        )
        
        if response.status_code != 200:
            print(f"  ⚠️  Failed to fetch bar data: {response.status_code}")
            return None
            
        data = response.json()
        series = data.get("series", {})
        
        if not series:
            print(f"  ⚠️  No timesales data available")
            return None
            
        bars = series.get("data", [])
        
        if not bars or len(bars) < period:
            print(f"  ⚠️  Insufficient bar data (need {period}, got {len(bars)})")
            return None
        
        # Extract closing prices
        prices = [float(bar.get("close", bar.get("price", 0))) for bar in bars]
        prices = [p for p in prices if p > 0]  # Filter out invalid prices
        
        if len(prices) < period:
            print(f"  ⚠️  Insufficient valid prices (need {period}, got {len(prices)})")
            return None
        
        # Calculate EMA
        # EMA = Price(t) * k + EMA(y) * (1 - k)
        # where k = 2 / (N + 1)
        k = 2 / (period + 1)
        
        # Start with SMA for first EMA value
        ema = sum(prices[:period]) / period
        
        # Calculate EMA for remaining prices
        for price in prices[period:]:
            ema = price * k + ema * (1 - k)
        
        return ema
        
    except Exception as e:
        print(f"  ⚠️  Error calculating EMA: {str(e)}")
        return None


def display_banner():
    """Display the interactive bot banner."""
    print()
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 15 + "🤖 OPTIONS TRADING BOT" + " " * 21 + "║")
    print("╚" + "═" * 58 + "╝")
    print()


def select_trading_mode():
    """Let user select between paper trading and live trading.
    
    Returns:
        str: 'paper' or 'live'
    """
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 15 + "⚠️  TRADING MODE SELECTION" + " " * 17 + "║")
    print("╚" + "═" * 58 + "╝")
    print()
    print("  Please select your trading mode:")
    print()
    print("  ┌" + "─" * 54 + "┐")
    print("  │  📝 PAPER TRADING                                   │")
    print("  │      • Uses sandbox/paper trading account           │")
    print("  │      • No real money at risk                        │")
    print("  │      • Safe for testing strategies                  │")
    print("  │      • Type 'PAPER' to select                       │")
    print("  ├" + "─" * 54 + "┤")
    print("  │  💰 LIVE TRADING                                    │")
    print("  │      • Uses real brokerage account                  │")
    print("  │      • REAL MONEY AT RISK!                          │")
    print("  │      • Only use if you understand the risks         │")
    print("  │      • Type 'LIVE' to select                        │")
    print("  └" + "─" * 54 + "┘")
    print()
    
    while True:
        try:
            choice = input("  Enter trading mode (PAPER/LIVE): ").strip().upper()
            
            if choice == "PAPER":
                print()
                print("  ✅ Paper Trading Mode selected")
                print("     Using sandbox/paper trading credentials")
                return "paper"
            elif choice == "LIVE":
                print()
                print("  ⚠️  WARNING: You are about to use LIVE TRADING!")
                print("  ⚠️  Real money will be at risk!")
                print()
                confirm = input("  Type 'I UNDERSTAND' to confirm live trading: ").strip()
                
                if confirm == "I UNDERSTAND":
                    print()
                    print("  🔴 LIVE TRADING MODE ACTIVATED")
                    print("     Using production trading credentials")
                    return "live"
                else:
                    print("  ❌ Live trading not confirmed. Please try again.")
                    continue
            else:
                print("  ❌ Please type 'PAPER' or 'LIVE' (full word required)")
                
        except KeyboardInterrupt:
            print("\n\n  👋 Goodbye!")
            sys.exit(0)


def set_trading_mode_env(mode: str):
    """Set environment variables based on trading mode.
    
    Args:
        mode: 'paper' or 'live'
    """
    if mode == "paper":
        # Set paper trading credentials
        # Tradier
        paper_tradier_token = os.environ.get("TRADIER_PAPER_API_TOKEN", "")
        paper_tradier_account = os.environ.get("TRADIER_PAPER_ACCOUNT_ID", "")
        if paper_tradier_token:
            os.environ["TRADIER_API_TOKEN"] = paper_tradier_token
        if paper_tradier_account:
            os.environ["TRADIER_ACCOUNT_ID"] = paper_tradier_account
        os.environ["TRADIER_BASE_URL"] = "https://sandbox.tradier.com"
        
        # Alpaca
        paper_alpaca_key = os.environ.get("ALPACA_PAPER_API_KEY", "")
        paper_alpaca_secret = os.environ.get("ALPACA_PAPER_API_SECRET", "")
        if paper_alpaca_key:
            os.environ["ALPACA_API_KEY"] = paper_alpaca_key
        if paper_alpaca_secret:
            os.environ["ALPACA_API_SECRET"] = paper_alpaca_secret
            
    elif mode == "live":
        # Set live trading credentials
        # Tradier
        live_tradier_token = os.environ.get("TRADIER_LIVE_API_TOKEN", "")
        live_tradier_account = os.environ.get("TRADIER_LIVE_ACCOUNT_ID", "")
        if live_tradier_token:
            os.environ["TRADIER_API_TOKEN"] = live_tradier_token
        if live_tradier_account:
            os.environ["TRADIER_ACCOUNT_ID"] = live_tradier_account
        os.environ["TRADIER_BASE_URL"] = "https://api.tradier.com"
        
        # Alpaca
        live_alpaca_key = os.environ.get("ALPACA_LIVE_API_KEY", "")
        live_alpaca_secret = os.environ.get("ALPACA_LIVE_API_SECRET", "")
        if live_alpaca_key:
            os.environ["ALPACA_API_KEY"] = live_alpaca_key
        if live_alpaca_secret:
            os.environ["ALPACA_API_SECRET"] = live_alpaca_secret


def display_positions(positions):
    """Display current stock positions."""
    if not positions:
        print("  📭 No stock positions found")
        return

    print("  ┌" + "─" * 40 + "┐")
    print("  │ Symbol     Shares      Value         │")
    print("  ├" + "─" * 40 + "┤")
    for pos in positions:
        value_str = f"${pos.market_value:,.2f}" if pos.market_value else "N/A"
        print(f"  │ {pos.symbol:<10} {pos.quantity:<11} {value_str:<13} │")
    print("  └" + "─" * 40 + "┘")


def select_stock(suggested_symbols):
    """Let user select a stock by typing any symbol."""
    print("📈 SELECT A STOCK:")
    print()
    
    # Display suggested symbols in a clean grid format
    if suggested_symbols:
        print("  📋 Suggested symbols:")
        print("  ┌" + "─" * 42 + "┐")
        
        # Display symbols in rows of 4
        for i in range(0, len(suggested_symbols), 4):
            row_symbols = suggested_symbols[i:i+4]
            row_text = "  │ " + " │ ".join(f"{sym:^8}" for sym in row_symbols)
            # Pad the row if it's not complete
            while len(row_symbols) < 4:
                row_text += " │        "
                row_symbols.append("")
            row_text += " │"
            print(row_text)
        
        print("  └" + "─" * 42 + "┘")
        print()
    
    print("  💡 You can also enter any valid stock symbol")
    print()

    while True:
        try:
            choice = input("  Enter stock symbol: ").strip().upper()

            if not choice:
                print("  ❌ Please enter a symbol")
                continue

            # Basic validation: 1-5 uppercase letters
            if not choice.isalpha() or len(choice) > 5:
                print("  ❌ Invalid symbol format (use 1-5 letters like AAPL)")
                continue

            print(f"  ✅ Selected: {choice}")
            return choice

        except KeyboardInterrupt:
            print("\n\n  👋 Goodbye!")
            sys.exit(0)


def select_strategy(symbol, shares_owned, broker_client=None):
    """Let user select a trading strategy by typing abbreviation.
    
    Args:
        symbol: Stock symbol
        shares_owned: Number of shares owned (including long call equivalents)
        broker_client: Optional broker client to get detailed position info
    """
    print()
    print("─" * 70)
    print("📊 TRADING STRATEGIES")
    print("─" * 70)
    
    # Check if stock-based strategies are available
    has_100_shares = shares_owned >= 100
    has_300_shares = shares_owned >= 300  # Minimum for tiered covered calls
    
    print()
    print("🔹 BASIC STRATEGIES")
    print("  ┌─────┬──────────────────┬──────────────────────────┐")
    print("  │ pcs │ Put Credit Spread│ Sell put spread for credit│")
    print("  │ lps │ Laddered Put Spr │ 5 weekly put spreads      │")
    print("  │ tpd │ Put Diagonal     │ Sell puts against long puts│")
    print("  │ ws  │ Wheel Strategy   │ Auto-cycle puts/calls     │")
    print("  │ mp  │ Married Put      │ Buy shares + protective put│")
    print("  └─────┴──────────────────┴──────────────────────────┘")
    
    print()
    print("🔹 MANAGEMENT STRATEGIES")
    print("  ┌─────┬──────────────────┬──────────────────────────┐")
    print("  │ritmo│ Roll ITM Options │ Roll expiring ITM options │")
    print("  └─────┴──────────────────┴──────────────────────────┘")

    print()
    print("🔹 STOCK-BASED STRATEGIES" + (" (Available)" if has_100_shares else " (Need 100+ shares)"))
    status_pc = "✅" if has_100_shares else "❌"
    status_cs = "✅" if has_100_shares else "❌"
    status_cc = "✅" if has_100_shares else "❌"
    status_lcc = "✅" if has_100_shares else "❌"
    status_tcc = "✅" if has_300_shares else "❌"
    
    print("  ┌─────┬──────────────────┬──────────────────────────┐")
    print(f"  │ pc  │ Protected Collar {status_pc}│ Protective put + covered call│")
    print(f"  │ cs  │ Collar Strategy {status_cs} │ Legacy Collar Strategy       │")
    print(f"  │ cc  │ Covered Call {status_cc}   │ Sell call on owned shares    │")
    print(f"  │ lcc │ Laddered CC {status_lcc}    │ Multiple weekly covered calls│")
    print(f"  │ tcc │ Tiered CC {status_tcc}      │ 3-tier multi-expiration calls│")
    print("  └─────┴──────────────────┴──────────────────────────┘")
    
    if shares_owned > 0 or broker_client:
        position_info = []
        actual_stock_shares = 0
        
        # Get actual stock shares (not including long call equivalents)
        if broker_client:
            try:
                position = broker_client.get_position(symbol)
                if position:
                    actual_stock_shares = position.quantity
            except Exception:
                actual_stock_shares = shares_owned  # Fallback to total if we can't get position
        else:
            actual_stock_shares = shares_owned
        
        if actual_stock_shares > 0:
            position_info.append(f"{actual_stock_shares} shares")
        
        # Get long calls and puts if broker_client is available
        if broker_client:
            try:
                detailed_positions = broker_client.get_detailed_positions(symbol)
                long_calls = [pos for pos in detailed_positions 
                            if hasattr(pos, 'position_type') and pos.position_type == 'long_call' and pos.quantity > 0]
                long_puts = [pos for pos in detailed_positions 
                            if hasattr(pos, 'position_type') and pos.position_type == 'long_put' and pos.quantity > 0]
                
                if long_calls:
                    total_long_calls = sum(abs(pos.quantity) for pos in long_calls)
                    position_info.append(f"{total_long_calls} long call(s)")
                if long_puts:
                    total_long_puts = sum(abs(pos.quantity) for pos in long_puts)
                    position_info.append(f"{total_long_puts} long put(s)")
            except Exception:
                pass  # Silently fail if we can't get detailed positions
        
        if position_info:
            print(f"  💼 You own {', '.join(position_info)} of {symbol}")
    
    print()
    print("🔹 VOLATILITY STRATEGIES")
    print("  ┌─────┬──────────────────┬──────────────────────────┐")
    print("  │ ls  │ Long Straddle    │ Profit from big moves     │")
    print("  │ ib  │ Iron Butterfly   │ Profit when price stays put│")
    print("  │ ic  │ Iron Condor      │ Profit in wider price range│")
    print("  │ ss  │ Short Strangle ⚠️│ UNDEFINED RISK - use caution│")
    print("  └─────┴──────────────────┴──────────────────────────┘")
    
    print()
    print("🔹 LIZARD STRATEGIES (Premium Collection)")
    print("  ┌─────┬──────────────────┬──────────────────────────┐")
    print("  │ jl  │ Jade Lizard      │ No upside risk if done right│")
    print("  │ bl  │ Big Lizard ⚠️    │ Short straddle + call hedge │")
    print("  └─────┴──────────────────┴──────────────────────────┘")
    
    print()
    print("🔹 0DTE STRATEGIES (SPX/SPY/QQQ)")
    print("  ┌─────┬──────────────────┬──────────────────────────┐")
    print("  │metf │ METF Strategy    │ EMA-based 0DTE spreads    │")
    print("  └─────┴──────────────────┴──────────────────────────┘")
    print("     Supports: SPX (30pt), SPY (3pt), QQQ (4pt) spreads")
    
    print()
    print("🔹 ADVANCED STRATEGIES (QQQ Only)")
    print("  ┌─────┬──────────────────┬──────────────────────────┐")
    print("  │ dc  │ Double Calendar  │ Time decay profit strategy│")
    print("  │ bf  │ Butterfly        │ Low-cost defined risk     │")
    print("  │ bwb │ Broken Wing BF   │ Asymmetric butterfly      │")
    print("  └─────┴──────────────────┴──────────────────────────┘")
    
    print()

    while True:
        try:
            choice = (
                input("  Enter strategy (pc/pcs/lps/tpd/cs/cc/ws/lcc/tcc/dc/bf/bwb/mp/ls/ib/ss/ic/jl/bl/metf): ").strip().lower()
            )

            if choice == "pc":
                if not has_100_shares:
                    print(f"  ❌ Protected Collar requires 100+ shares. You have {shares_owned}.")
                    continue
                print("  ✅ Selected: Protected Collar")
                return "pc"
            elif choice == "pcs":
                print("  ✅ Selected: Put Credit Spread")
                return "pcs"
            elif choice == "lps":
                print("  ✅ Selected: Laddered Put Spread")
                print("     📝 5 weekly put credit spreads with staggered expirations")
                return "lps"
            elif choice == "tpd":
                print("  ✅ Selected: Tiered Put Diagonal")
                print("     📝 Sell puts at 3 expirations against your long puts")
                return "tpd"
            elif choice == "cs":
                if not has_100_shares:
                    print(f"  ❌ Collar requires 100+ shares. You have {shares_owned}.")
                    continue
                print("  ✅ Selected: Collar Strategy")
                return "cs"
            elif choice == "cc":
                if not has_100_shares:
                    print(f"  ❌ Covered Call requires 100+ shares. You have {shares_owned}.")
                    continue
                print("  ✅ Selected: Covered Call")
                return "cc"
            elif choice == "ws":
                if has_100_shares:
                    print("  ✅ Selected: Wheel Strategy (Covered Call phase)")
                else:
                    print("  ✅ Selected: Wheel Strategy (Cash-Secured Put phase)")
                return "ws"
            elif choice == "lcc":
                if not has_100_shares:
                    print(f"  ❌ Laddered CC requires 100+ shares. You have {shares_owned}.")
                    continue
                print("  ✅ Selected: Laddered Covered Call")
                return "lcc"
            elif choice == "tcc":
                if not has_300_shares:
                    print(f"  ❌ Tiered Covered Calls requires 300+ shares. You have {shares_owned}.")
                    continue
                print("  ✅ Selected: Tiered Covered Calls")
                return "tcc"
            elif choice == "dc":
                print("  ✅ Selected: Double Calendar on QQQ")
                return "dc"
            elif choice == "bf":
                print("  ✅ Selected: Butterfly on QQQ")
                return "bf"
            elif choice == "mp":
                print("  ✅ Selected: Married Put")
                return "mp"
            elif choice == "ls":
                print("  ✅ Selected: Long Straddle")
                return "ls"
            elif choice == "ib":
                print("  ✅ Selected: Iron Butterfly")
                return "ib"
            elif choice == "ss":
                print("  ⚠️ WARNING: Short Strangle has UNDEFINED RISK!")
                print("  ✅ Selected: Short Strangle")
                return "ss"
            elif choice == "ic":
                print("  ✅ Selected: Iron Condor")
                return "ic"
            elif choice == "jl":
                print("  ✅ Selected: Jade Lizard")
                print("     📝 Neutral-to-bullish: Sell OTM put + sell OTM call + buy further OTM call")
                print("     💡 No upside risk if call spread width ≤ put premium")
                return "jl"
            elif choice == "bl":
                print("  ⚠️ WARNING: Big Lizard has UNDEFINED DOWNSIDE RISK!")
                print("  ✅ Selected: Big Lizard")
                print("     📝 Aggressive: Sell ATM straddle + buy OTM call for upside protection")
                return "bl"
            elif choice == "bwb":
                print("  ✅ Selected: Broken Wing Butterfly on QQQ")
                print("     📝 Asymmetric butterfly: Can be done for credit, risk only on one side")
                return "bwb"
            elif choice == "metf":
                print("  ✅ Selected: METF Strategy (0DTE Credit Spreads)")
                print()
                print("     📊 Supported Symbols:")
                print("        • SPX/SPXW: 25-35 pt spreads, $1.25-$2.50 credit")
                print("        • SPY: 2-5 pt spreads, $0.15-$0.35 credit")
                print("        • QQQ: 3-6 pt spreads, $0.15-$0.40 credit")
                print()
                print("     ⏰ Entry times: 12:30, 1:00, 1:30, 2:00, 2:30, 2:45 PM EST")
                print("     📈 20 EMA > 40 EMA → Put Credit Spread (bullish)")
                print("     📉 20 EMA < 40 EMA → Call Credit Spread (bearish)")
                return "metf"
            elif choice == "ritmo":
                print("  ✅ Selected: Roll In The Money Options (RITMO)")
                print("     📝 Automatically rolls expiring ITM options to next expiration")
                print("     💡 Keeps same strike, extends time for recovery")
                return "ritmo"
            else:
                print(
                    "  ❌ Enter 'pc', 'pcs', 'cs', 'cc', 'ws', 'lcc', 'tcc', 'dc', 'bf', 'bwb', 'mp', 'ls', 'ib', 'ss', 'ic', 'jl', 'bl', 'metf', or 'ritmo'"
                )

        except KeyboardInterrupt:
            print("\n\n  👋 Goodbye!")
            sys.exit(0)


def confirm_execution(symbol, strategy, shares_owned, shares_for_legs=None):
    """Confirm the trade execution with user.
    
    Args:
        symbol: Stock symbol
        strategy: Strategy code
        shares_owned: Actual shares owned (for display and calculations)
        shares_for_legs: Total equivalent shares for determining number of legs (optional, defaults to shares_owned)
    """
    has_100_shares = shares_owned >= 100
    
    # If shares_for_legs not provided, use shares_owned
    if shares_for_legs is None:
        shares_for_legs = shares_owned

    strategy_names = {
        "pc": "Protected Collar",
        "pcs": "Put Credit Spread",
        "lps": "Laddered Put Spread",
        "tpd": "Tiered Put Diagonal",
        "cs": "Collar Strategy",
        "cc": "Covered Call",
        "ws": f"Wheel Strategy ({'CC' if has_100_shares else 'CSP'} phase)",
        "lcc": "Laddered Covered Call",
        "tcc": "Tiered Covered Calls",
        "dc": "Double Calendar (QQQ)",
        "bf": "Butterfly (QQQ)",
        "bwb": "Broken Wing Butterfly (QQQ)",
        "mp": "Married Put",
        "ls": "Long Straddle",
        "ib": "Iron Butterfly",
        "ss": "Short Strangle ⚠️",
        "ic": "Iron Condor",
        "jl": "Jade Lizard",
        "bl": "Big Lizard ⚠️",
        "metf": "METF Strategy (SPX 0DTE)",
        "ritmo": "Roll In The Money Options"
    }
    strategy_name = strategy_names.get(strategy, strategy)

    print()
    print("─" * 60)
    print("🎯 TRADE SUMMARY:")
    print()
    print(f"  Stock:      {symbol}")
    print(f"  Strategy:   {strategy_name}")
    if strategy in ["pc", "cs", "cc"]:
        contracts = shares_owned // 100
        print(f"  Shares:     {shares_owned} ({contracts} contract(s))")
    if strategy == "cc":
        print(f"  Strike:     ~5% above current price")
        print(f"  Expiry:     ~10 days out")
    if strategy == "lps":
        print(f"  Structure:  5 weekly put credit spreads")
        print(f"  Legs:       Week 1, 2, 3, 4, 5 expirations")
        print(f"  Strikes:    Below current price (same for all weeks)")
        print(f"  Spread:     $5 wide (configurable)")
        print(f"  💡 Benefit: Consistent weekly income, no shares needed")
    if strategy == "tpd":
        print(f"  Structure:  Tiered put diagonals (3 expirations)")
        print(f"  Requirement: Must own long puts on this symbol")
        print(f"  Tiers:      1 week, 2 weeks, 3 weeks out")
        print(f"  Distribution: Quantity split across tiers")
        print(f"  💡 Benefit: Maximize premium from protective puts")
    if strategy == "ws":
        if has_100_shares:
            contracts = shares_owned // 100
            print(f"  Action:     Sell {contracts} covered call(s)")
            print(f"  Strike:     ~5% above current price")
        else:
            print(f"  Action:     Sell 1 cash-secured put")
            print(f"  Strike:     ~5% below current price")
        print(f"  Expiry:     ~15 days out")
    if strategy == "lcc":
        # Calculate dynamic number of legs based on total equivalent shares (including long calls)
        # 500+ shares = 5 legs, 400-499 = 4 legs, 300-399 = 3 legs, 200-299 = 2 legs, 100-199 = 1 leg
        if shares_for_legs >= 500:
            num_legs = 5
        elif shares_for_legs >= 400:
            num_legs = 4
        elif shares_for_legs >= 300:
            num_legs = 3
        elif shares_for_legs >= 200:
            num_legs = 2
        else:
            num_legs = 1
        
        total_contracts = int((shares_owned * 0.667) // 100)
        percentage_per_leg = 100 // num_legs if num_legs > 0 else 100
        
        print(f"  Shares:     {shares_owned} (actual stock shares)")
        if shares_for_legs != shares_owned:
            print(f"  Equivalent: {shares_for_legs} shares (including long calls)")
        print(f"  Coverage:   2/3 of holdings ({total_contracts} contracts)")
        print(f"  Legs:       {num_legs} next available expirations (~{percentage_per_leg}% each)")
        print(f"  Strike:     ~5% above current price")
    if strategy == "tcc":
        total_contracts = shares_owned // 100
        print(f"  Shares:     {shares_owned} (actual stock shares)")
        print(f"  Coverage:   Up to {total_contracts} contracts across 3 expirations")
        print(f"  Structure:  3 groups with incremental strike prices")
        print(f"  Strikes:    Progressive OTM strikes (higher for longer expirations)")
        print(f"  Timeline:   Next 3 available expiration dates")
    if strategy == "dc":
        print(f"  Symbol:     QQQ (overrides selection)")
        print(f"  Structure:  Put calendar + Call calendar")
        print(f"  Short leg:  2 days out")
        print(f"  Long leg:   4 days out")
        print(f"  Strikes:    ~2% below/above current price")
    if strategy == "bf":
        print(f"  Symbol:     QQQ (overrides selection)")
        print(f"  Structure:  Buy 1 / Sell 2 / Buy 1 calls")
        print(f"  Wing width: $5 between strikes")
        print(f"  Expiry:     ~7 days out")
        print(f"  Max profit: At middle strike")
    if strategy == "mp":
        print(f"  Action:     Buy 100 shares + Buy 1 put")
        print(f"  Put strike: ~5% below current price")
        print(f"  Expiry:     ~30 days out")
        print(f"  Protection: Limited loss below put strike")
    if strategy == "ls":
        print(f"  Action:     Buy 1 ATM call + Buy 1 ATM put")
        print(f"  Strike:     At-the-money (closest to current price)")
        print(f"  Expiry:     ~30 days out")
        print(f"  Profit:     Big move up OR down")
    if strategy == "ib":
        print(f"  Action:     Sell ATM straddle + Buy OTM wings")
        print(f"  Middle:     At-the-money (sell call + put)")
        print(f"  Wings:      $5 above/below middle (buy protection)")
        print(f"  Expiry:     ~30 days out")
        print(f"  Profit:     Stock stays near middle strike")
    if strategy == "ss":
        print(f"  ⚠️ WARNING: UNDEFINED RISK STRATEGY!")
        print(f"  Action:     Sell OTM put + Sell OTM call")
        print(f"  Put:        ~5% below current price")
        print(f"  Call:       ~5% above current price")
        print(f"  Expiry:     ~30 days out")
        print(f"  Profit:     Stock stays between strikes")
    if strategy == "ic":
        print(f"  Action:     Sell put spread + Sell call spread")
        print(f"  Put spread: ~3% below price ($5 wide)")
        print(f"  Call spread: ~3% above price ($5 wide)")
        print(f"  Expiry:     ~30 days out")
        print(f"  Profit:     Stock stays between short strikes")
    if strategy == "jl":
        print(f"  Action:     Sell OTM put + Sell OTM call + Buy further OTM call")
        print(f"  Put:        ~5% below current price (sell)")
        print(f"  Short Call: ~5% above current price (sell)")
        print(f"  Long Call:  ~10% above current price (buy protection)")
        print(f"  Expiry:     ~30 days out")
        print(f"  Profit:     Stock stays between put and short call")
        print(f"  💡 Key:     No upside risk if call spread width ≤ put premium")
    if strategy == "bl":
        print(f"  ⚠️ WARNING: UNDEFINED DOWNSIDE RISK!")
        print(f"  Action:     Sell ATM straddle + Buy OTM call")
        print(f"  Straddle:   At-the-money (sell put + call)")
        print(f"  Long Call:  ~10% above current price (buy protection)")
        print(f"  Expiry:     ~30 days out")
        print(f"  Profit:     Stock stays near straddle strike")
        print(f"  Risk:       Unlimited on downside, limited on upside")
    if strategy == "bwb":
        print(f"  Symbol:     QQQ (overrides selection)")
        print(f"  Action:     Buy 1 lower / Sell 2 middle / Buy 1 upper call")
        print(f"  Structure:  Asymmetric butterfly (unequal wing widths)")
        print(f"  Lower wing: $5 wide (narrow)")
        print(f"  Upper wing: $10 wide (broken/wide)")
        print(f"  Expiry:     ~30 days out")
        print(f"  💡 Key:     Can be done for credit, risk only on wide side")
    if strategy == "metf":
        print(f"  Symbol:     {symbol} (0DTE options)")
        print(f"  Strategy:   EMA Trend Following Credit Spreads")
        print(f"  ⏰ Entry:    12:30, 1:00, 1:30, 2:00, 2:30, 2:45 PM EST")
        print(f"  📊 Signal:  1-min 20 EMA vs 40 EMA crossover")
        print(f"     • 20 EMA > 40 EMA → Put Credit Spread (bullish)")
        print(f"     • 20 EMA < 40 EMA → Call Credit Spread (bearish)")
        # Show symbol-specific parameters
        if symbol.upper() in ["SPX", "SPXW"]:
            print(f"  Width:      25, 30, or 35 points")
            print(f"  Credit:     $1.25 - $2.50 target per spread")
        elif symbol.upper() == "SPY":
            print(f"  Width:      2, 3, 4, or 5 points")
            print(f"  Credit:     $0.15 - $0.35 target per spread")
        elif symbol.upper() == "QQQ":
            print(f"  Width:      3, 4, 5, or 6 points")
            print(f"  Credit:     $0.15 - $0.40 target per spread")
        print(f"  Stop:       1x credit received (100% of premium)")
        print(f"  Hold:       Till expiration")
        print(f"  ⚠️ Avoid:   FOMC days and FOMC Minutes days")
    if strategy == "ritmo":
        print(f"  Action:     Roll expiring ITM options to next expiration")
        print(f"  Target:     Options expiring TODAY that are in-the-money")
        print(f"  New Expiry: Next available expiration date")
        print(f"  Strike:     Keep same strike price")
        print(f"  💡 Benefit: Extend time for recovery, collect additional credit")
        print(f"  ⚠️ Note:    Only rolls if net credit meets minimum threshold")
    print()

    while True:
        try:
            confirm = input("  Execute this trade? (y/n): ").strip().lower()

            if confirm in ["y", "yes"]:
                return True
            elif confirm in ["n", "no"]:
                return False
            else:
                print("  ❌ Please enter 'y' or 'n'")

        except KeyboardInterrupt:
            print("\n\n  👋 Goodbye!")
            sys.exit(0)


def get_shares_owned(broker_client, symbol, position_service=None):
    """Check how many shares of a symbol the user owns.
    
    This includes both stock shares and equivalent shares from long call options.
    Each long call contract represents 100 shares.
    
    Args:
        broker_client: Broker client instance
        symbol: Stock symbol
        position_service: Optional PositionService instance for detailed position info
        
    Returns:
        Total shares including stock and long call equivalents
    """
    try:
        # If position service is available, use it to get total shares including long calls
        if position_service:
            try:
                summary = position_service.get_long_positions(symbol)
                return summary.total_shares
            except Exception:
                # Fall back to basic position check if position service fails
                pass
        
        # Fallback: just get stock position
        position = broker_client.get_position(symbol)
        if position:
            return position.quantity
        return 0
    except Exception:
        return 0


def display_position_summary(summary):
    """Display current holdings for tiered covered calls.
    
    Args:
        summary: PositionSummary object with current position information
    """
    print()
    print("─" * 60)
    print("📊 POSITION SUMMARY")
    print("─" * 60)
    print()
    
    # Main position information
    print("🔹 STOCK POSITION")
    print("  ┌" + "─" * 50 + "┐")
    print(f"  │ Symbol:          {summary.symbol:<30} │")
    print(f"  │ Current Price:   ${summary.current_price:<29.2f} │")
    print(f"  │ Total Shares:    {summary.total_shares:<30} │")
    print(f"  │ Available Shares: {summary.available_shares:<29} │")
    
    # Calculate market value
    market_value = summary.total_shares * summary.current_price
    available_value = summary.available_shares * summary.current_price
    
    print(f"  │ Market Value:    ${market_value:<29,.2f} │")
    print(f"  │ Available Value: ${available_value:<29,.2f} │")
    print("  └" + "─" * 50 + "┘")
    
    # Cost basis information
    if summary.average_cost_basis is not None:
        print()
        print("🔹 COST BASIS INFORMATION")
        print("  ┌" + "─" * 50 + "┐")
        print(f"  │ Original Cost/Share: ${summary.average_cost_basis:<25.2f} │")
        
        if summary.total_cost_basis is not None:
            print(f"  │ Total Original Cost: ${summary.total_cost_basis:<25,.2f} │")
        
        if summary.cumulative_premium_collected is not None:
            print(f"  │ Premium Collected:   ${summary.cumulative_premium_collected:<25.2f} │")
        
        if summary.effective_cost_basis_per_share is not None:
            print(f"  │ Effective Cost/Share: ${summary.effective_cost_basis_per_share:<24.2f} │")
            
            # Calculate cost basis reduction percentage
            if summary.average_cost_basis > 0:
                reduction_amount = summary.average_cost_basis - summary.effective_cost_basis_per_share
                reduction_percentage = (reduction_amount / summary.average_cost_basis) * 100
                print(f"  │ Cost Basis Reduction: ${reduction_amount:<7.2f} ({reduction_percentage:<5.1f}%)     │")
        
        print("  └" + "─" * 50 + "┘")
    
    # Show existing short calls if any
    if summary.existing_short_calls:
        print()
        print("🔹 EXISTING SHORT CALLS")
        print("  ┌" + "─" * 58 + "┐")
        print("  │ Expiration   Strike    Contracts  Shares Covered │")
        print("  ├" + "─" * 58 + "┤")
        
        total_covered_shares = 0
        for call in summary.existing_short_calls:
            contracts = abs(call.quantity)  # Make positive for display
            shares_covered = contracts * 100
            total_covered_shares += shares_covered
            
            print(f"  │ {call.expiration.strftime('%Y-%m-%d')}   ${call.strike:<7.2f}  {contracts:<9}  {shares_covered:<13} │")
        
        print("  ├" + "─" * 58 + "┤")
        print(f"  │ TOTAL COVERED SHARES:                    {total_covered_shares:<13} │")
        print("  └" + "─" * 58 + "┘")
    else:
        print()
        print("🔹 EXISTING SHORT CALLS")
        print("  📭 No existing short call positions")
    
    # Show long options if any
    if summary.long_options:
        print()
        print("🔹 LONG OPTIONS")
        print("  ┌" + "─" * 58 + "┐")
        print("  │ Type   Expiration   Strike    Contracts  Value    │")
        print("  ├" + "─" * 58 + "┤")
        
        for option in summary.long_options:
            option_type = option.option_type.upper()
            contracts = option.quantity
            value = option.market_value
            
            print(f"  │ {option_type:<6} {option.expiration.strftime('%Y-%m-%d')}   ${option.strike:<7.2f}  {contracts:<9}  ${value:<7.2f} │")
        
        print("  └" + "─" * 58 + "┘")
    
    # Availability check
    print()
    if summary.available_shares >= 300:
        contracts_possible = summary.available_shares // 100
        print(f"  ✅ Ready for Tiered Covered Calls ({contracts_possible} contracts possible)")
    elif summary.available_shares >= 100:
        print(f"  ⚠️  Only {summary.available_shares} shares available (need 300+ for optimal tiered strategy)")
    else:
        print(f"  ❌ Insufficient shares for covered calls (need 100+ shares, have {summary.available_shares})")
    
    print()


def display_tiered_strategy_preview(plan):
    """Display detailed preview of tiered covered call strategy.
    
    Args:
        plan: TieredCoveredCallPlan object with strategy details
    """
    print()
    print("─" * 70)
    print("🎯 TIERED COVERED CALL STRATEGY PREVIEW")
    print("─" * 70)
    print()
    
    # Strategy overview
    print("🔹 STRATEGY OVERVIEW")
    print("  ┌" + "─" * 60 + "┐")
    print(f"  │ Symbol:           {plan.symbol:<40} │")
    print(f"  │ Current Price:    ${plan.current_price:<39.2f} │")
    print(f"  │ Total Shares:     {plan.total_shares:<40} │")
    print(f"  │ Total Contracts:  {plan.total_contracts:<40} │")
    print(f"  │ Est. Premium:     ${plan.estimated_premium:<39.2f} │")
    print("  └" + "─" * 60 + "┘")
    
    # Cost basis impact (if available)
    if hasattr(plan, 'original_cost_basis') and plan.original_cost_basis is not None:
        print()
        print("🔹 COST BASIS IMPACT")
        print("  ┌" + "─" * 60 + "┐")
        print(f"  │ Original Cost/Share:  ${plan.original_cost_basis:<35.2f} │")
        
        if hasattr(plan, 'effective_cost_basis') and plan.effective_cost_basis is not None:
            print(f"  │ Effective Cost/Share: ${plan.effective_cost_basis:<35.2f} │")
            
            # Calculate reduction
            reduction_amount = plan.original_cost_basis - plan.effective_cost_basis
            reduction_percentage = (reduction_amount / plan.original_cost_basis) * 100 if plan.original_cost_basis > 0 else 0
            
            print(f"  │ Cost Basis Reduction: ${reduction_amount:<7.2f} ({reduction_percentage:<5.1f}%)         │")
        
        if hasattr(plan, 'cost_basis_reduction') and plan.cost_basis_reduction is not None:
            # Calculate shares covered for this strategy
            shares_covered = sum(group.shares_used for group in plan.expiration_groups)
            premium_per_share = plan.estimated_premium / shares_covered if shares_covered > 0 else 0
            
            print(f"  │ Premium per Share:    ${premium_per_share:<35.2f} │")
            print(f"  │ Total Premium Impact: ${plan.estimated_premium:<35.2f} │")
        
        print("  └" + "─" * 60 + "┘")
    
    # Expiration groups breakdown
    print()
    print("🔹 EXPIRATION GROUPS")
    print("  ┌" + "─" * 68 + "┐")
    print("  │ Group  Expiration   Strike    Contracts  Premium/Contract  Total │")
    print("  ├" + "─" * 68 + "┤")
    
    total_premium = 0.0
    for i, group in enumerate(plan.expiration_groups, 1):
        group_premium = group.estimated_premium_per_contract * group.num_contracts
        total_premium += group_premium
        
        print(f"  │ {i:<6} {group.expiration_date.strftime('%Y-%m-%d')}   ${group.strike_price:<7.2f}  {group.num_contracts:<9}  ${group.estimated_premium_per_contract:<15.2f}  ${group_premium:<5.2f} │")
    
    print("  ├" + "─" * 68 + "┤")
    print(f"  │ TOTAL ESTIMATED PREMIUM:                                    ${total_premium:<5.2f} │")
    print("  └" + "─" * 68 + "┘")
    
    # Risk and position impact
    print()
    print("🔹 RISK & POSITION IMPACT")
    print("  ┌" + "─" * 60 + "┐")
    
    # Calculate key metrics
    shares_covered = sum(group.shares_used for group in plan.expiration_groups)
    coverage_percentage = (shares_covered / plan.total_shares) * 100 if plan.total_shares > 0 else 0
    premium_per_share = total_premium / shares_covered if shares_covered > 0 else 0
    
    # Calculate potential upside to highest strike
    highest_strike = max(group.strike_price for group in plan.expiration_groups)
    upside_potential = ((highest_strike - plan.current_price) / plan.current_price) * 100
    
    print(f"  │ Shares Covered:   {shares_covered} ({coverage_percentage:.1f}% of holdings)     │")
    print(f"  │ Premium/Share:    ${premium_per_share:<39.2f} │")
    print(f"  │ Highest Strike:   ${highest_strike:<39.2f} │")
    print(f"  │ Upside Potential: {upside_potential:<39.1f}% │")
    print("  │                                                          │")
    print("  │ ⚠️  RISKS:                                               │")
    print("  │ • Shares may be called away if stock rises above strikes│")
    print("  │ • Limited upside beyond highest strike price            │")
    print("  │ • Premium received reduces cost basis but caps gains    │")
    print("  └" + "─" * 60 + "┘")
    
    # Timeline breakdown
    print()
    print("🔹 EXPIRATION TIMELINE")
    print("  ┌" + "─" * 50 + "┐")
    
    for i, group in enumerate(plan.expiration_groups, 1):
        days_to_expiration = (group.expiration_date - date.today()).days
        print(f"  │ Group {i}: {days_to_expiration:>2} days to expiration ({group.expiration_date.strftime('%m/%d')})     │")
    
    print("  └" + "─" * 50 + "┘")
    
    print()


def confirm_tiered_execution(plan, broker_client=None):
    """Confirm tiered covered call strategy execution with user.
    
    Args:
        plan: TieredCoveredCallPlan object with strategy details
        broker_client: Optional broker client for buying power info
        
    Returns:
        bool: True if user confirms execution, False otherwise
    """
    print()
    print("─" * 60)
    print("🎯 EXECUTION CONFIRMATION")
    print("─" * 60)
    print()
    
    # Summary of what will be executed
    print("🔹 EXECUTION SUMMARY")
    print("  ┌" + "─" * 50 + "┐")
    print(f"  │ Symbol:          {plan.symbol:<30} │")
    print(f"  │ Strategy:        Tiered Covered Calls      │")
    print(f"  │ Total Contracts: {plan.total_contracts:<30} │")
    print(f"  │ Est. Premium:    ${plan.estimated_premium:<29.2f} │")
    
    # Collateral for covered calls is $0 (shares are collateral)
    print(f"  │ Collateral:      $0.00 (shares are collateral) │")
    
    # Add cost basis reduction if available
    if hasattr(plan, 'original_cost_basis') and plan.original_cost_basis is not None:
        if hasattr(plan, 'effective_cost_basis') and plan.effective_cost_basis is not None:
            reduction_amount = plan.original_cost_basis - plan.effective_cost_basis
            reduction_percentage = (reduction_amount / plan.original_cost_basis) * 100 if plan.original_cost_basis > 0 else 0
            print(f"  │ Cost Basis Reduction: {reduction_percentage:<26.1f}% │")
    
    # Get and show buying power impact if broker client available
    if broker_client:
        try:
            account_info = broker_client.get_account()
            # Try different attribute names for buying power
            buying_power = None
            if hasattr(account_info, 'buying_power'):
                buying_power = account_info.buying_power
            elif hasattr(account_info, 'option_buying_power'):
                buying_power = account_info.option_buying_power
            elif hasattr(account_info, 'cash_available'):
                buying_power = account_info.cash_available
            
            if buying_power is not None:
                current_bp = float(buying_power)
                # Covered calls increase buying power (credit received, no collateral)
                bp_impact = -plan.estimated_premium  # Negative because it increases BP
                remaining_bp = current_bp - bp_impact
                
                print(f"  │ Current Buying Power: ${current_bp:<25,.2f} │")
                print(f"  │ BP Impact:       +${abs(bp_impact):<29,.2f} │")
                print(f"  │ Remaining BP:    ${remaining_bp:<29,.2f} │")
            else:
                print(f"  │ ℹ️  Buying power not available in account info    │")
        except Exception as e:
            # Show error if we can't get account info
            print(f"  │ ⚠️  Could not fetch buying power: {str(e)[:30]:<20}│")
    else:
        print(f"  │ ℹ️  Buying power info unavailable (no broker client) │")
    
    print("  └" + "─" * 50 + "┘")
    
    print()
    print("🔹 ORDERS TO BE PLACED")
    for i, group in enumerate(plan.expiration_groups, 1):
        print(f"  {i}. Sell {group.num_contracts} call(s) - ${group.strike_price:.2f} strike, {group.expiration_date.strftime('%m/%d/%Y')} expiration")
    
    print()
    print("⚠️  IMPORTANT REMINDERS:")
    print("  • This will create covered call obligations on your shares")
    print("  • Shares may be called away if stock price exceeds strike prices")
    print("  • Orders will be submitted immediately upon confirmation")
    print("  • Check your broker platform for real-time order status")
    
    print()
    print("  ⚠️  WARNING: These orders will be submitted to your broker!")
    print("  ⚠️  Real money will be at risk. Review carefully.")
    print()
    
    while True:
        try:
            confirm = input("  🔐 Type 'CONFIRM' to execute or 'cancel' to abort: ").strip()
            
            if confirm.upper() == "CONFIRM":
                print()
                print("  ✅ Execution confirmed!")
                return True
            elif confirm.lower() in ["cancel", "no", "n", "abort"]:
                print()
                print("  🚫 Execution cancelled")
                return False
            else:
                print("  ❌ Please type 'CONFIRM' to proceed or 'cancel' to abort")
                
        except KeyboardInterrupt:
            print("\n\n  👋 Goodbye!")
            sys.exit(0)


def display_execution_progress(plan):
    """Display execution progress for tiered covered call orders.
    
    Args:
        plan: TieredCoveredCallPlan object with strategy details
    """
    print()
    print("─" * 60)
    print("🚀 EXECUTING TIERED COVERED CALL STRATEGY")
    print("─" * 60)
    print()
    
    print(f"  ⏳ Submitting {plan.total_contracts} covered call orders for {plan.symbol}...")
    print()
    
    for i, group in enumerate(plan.expiration_groups, 1):
        print(f"  📤 Group {i}: {group.num_contracts} contracts @ ${group.strike_price:.2f} ({group.expiration_date.strftime('%m/%d')})")
    
    print()
    print("  ⏳ Processing orders...")


def display_execution_results(results, plan, strategy_impact=None):
    """Display results of tiered covered call execution.
    
    Args:
        results: List of order results or execution summary
        plan: TieredCoveredCallPlan object with strategy details
        strategy_impact: Optional StrategyImpact object with cost basis impact
    """
    print()
    print("─" * 60)
    print("📊 EXECUTION RESULTS")
    print("─" * 60)
    print()
    
    # Order status
    print("🔹 ORDER STATUS")
    print("  ┌" + "─" * 50 + "┐")
    print(f"  │ Symbol:           {plan.symbol:<30} │")
    print(f"  │ Strategy:         Tiered Covered Calls     │")
    print(f"  │ Orders Submitted: {plan.total_contracts:<30} │")
    print(f"  │ Premium Collected: ${plan.estimated_premium:<28.2f} │")
    print("  └" + "─" * 50 + "┘")
    
    # Cost basis impact (if available)
    if strategy_impact:
        print()
        print("🔹 COST BASIS IMPACT")
        print("  ┌" + "─" * 50 + "┐")
        print(f"  │ Premium Collected:    ${strategy_impact.premium_collected:<25.2f} │")
        print(f"  │ Contracts Executed:   {strategy_impact.contracts_executed:<25} │")
        print(f"  │ Reduction per Share:  ${strategy_impact.cost_basis_reduction_per_share:<25.2f} │")
        
        # Calculate total shares affected
        shares_affected = strategy_impact.contracts_executed * 100
        total_reduction = strategy_impact.cost_basis_reduction_per_share * shares_affected
        
        print(f"  │ Total Shares Affected: {shares_affected:<24} │")
        print(f"  │ Total Cost Reduction: ${total_reduction:<25.2f} │")
        print("  └" + "─" * 50 + "┘")
        
        print()
        print("💰 Your effective cost basis has been reduced!")
        print(f"   Each covered share now costs ${strategy_impact.cost_basis_reduction_per_share:.2f} less")
    
    elif hasattr(plan, 'original_cost_basis') and plan.original_cost_basis is not None:
        # Show estimated cost basis impact even without strategy_impact object
        shares_covered = sum(group.shares_used for group in plan.expiration_groups)
        premium_per_share = plan.estimated_premium / shares_covered if shares_covered > 0 else 0
        
        print()
        print("🔹 ESTIMATED COST BASIS IMPACT")
        print("  ┌" + "─" * 50 + "┐")
        print(f"  │ Premium per Share:    ${premium_per_share:<25.2f} │")
        print(f"  │ Shares Covered:       {shares_covered:<25} │")
        print(f"  │ Total Premium Impact: ${plan.estimated_premium:<25.2f} │")
        print("  └" + "─" * 50 + "┘")
    
    print()
    print("✅ Tiered covered call strategy execution completed!")
    print()
    print("📱 Check your broker dashboard for:")
    print("  • Order fill confirmations")
    print("  • Updated position details")
    print("  • Actual premium collected amounts")
    print()
    print("📋 Strategy details logged to trading_bot.log")
    print()


def select_tiered_covered_call_symbol():
    """Let user select a symbol specifically for tiered covered calls."""
    print()
    print("─" * 60)
    print("📈 SELECT SYMBOL FOR TIERED COVERED CALLS")
    print("─" * 60)
    print()
    
    print("💡 Tiered Covered Calls work best with:")
    print("  • Stocks you plan to hold long-term")
    print("  • Symbols with good option liquidity")
    print("  • Positions of 300+ shares for optimal diversification")
    print()
    
    while True:
        try:
            symbol = input("  Enter stock symbol: ").strip().upper()
            
            if not symbol:
                print("  ❌ Please enter a symbol")
                continue
                
            # Basic validation: 1-5 uppercase letters
            if not symbol.isalpha() or len(symbol) > 5:
                print("  ❌ Invalid symbol format (use 1-5 letters like AAPL)")
                continue
                
            print(f"  ✅ Selected: {symbol}")
            return symbol
            
        except KeyboardInterrupt:
            print("\n\n  👋 Goodbye!")
            sys.exit(0)


def display_roll_opportunities(roll_plan):
    """Display roll opportunities for expiring ITM calls.
    
    Args:
        roll_plan: RollPlan object with roll opportunities and details
    """
    print()
    print("─" * 70)
    print("🔄 COVERED CALL ROLL OPPORTUNITIES")
    print("─" * 70)
    print()
    
    # Roll overview
    print("🔹 ROLL OVERVIEW")
    print("  ┌" + "─" * 60 + "┐")
    print(f"  │ Symbol:              {roll_plan.symbol:<35} │")
    print(f"  │ Current Price:       ${roll_plan.current_price:<34.2f} │")
    print(f"  │ Expiring ITM Calls:  {len(roll_plan.roll_opportunities):<35} │")
    print(f"  │ Total Est. Credit:   ${roll_plan.total_estimated_credit:<34.2f} │")
    print("  └" + "─" * 60 + "┘")
    
    if not roll_plan.roll_opportunities:
        print()
        print("📭 No roll opportunities found")
        print("   • All expiring calls are out-of-the-money, or")
        print("   • No suitable roll targets available, or") 
        print("   • Roll transactions would result in net debits")
        return
    
    # Individual roll opportunities
    print()
    print("🔹 ROLL DETAILS")
    print("  ┌" + "─" * 78 + "┐")
    print("  │ Current Call         →  New Call             Credit   ITM Amount │")
    print("  │ Strike   Exp         →  Strike   Exp         Est.     (Current) │")
    print("  ├" + "─" * 78 + "┤")
    
    total_estimated_credit = 0.0
    for i, opportunity in enumerate(roll_plan.roll_opportunities, 1):
        current_call = opportunity.current_call
        itm_amount = opportunity.current_price - current_call.strike
        
        # Format current call info
        current_info = f"${current_call.strike:>6.2f}  {current_call.expiration.strftime('%m/%d')}"
        
        # Format new call info  
        new_info = f"${opportunity.target_strike:>6.2f}  {opportunity.target_expiration.strftime('%m/%d')}"
        
        # Format credit and ITM amount
        credit_str = f"${opportunity.estimated_credit:>5.2f}"
        itm_str = f"${itm_amount:>6.2f}"
        
        print(f"  │ {current_info:<16} →  {new_info:<16} {credit_str:<8} {itm_str:<10} │")
        total_estimated_credit += opportunity.estimated_credit
    
    print("  ├" + "─" * 78 + "┤")
    print(f"  │ TOTAL ESTIMATED CREDIT:                                ${total_estimated_credit:>6.2f}        │")
    print("  └" + "─" * 78 + "┘")
    
    # Risk and impact information
    print()
    print("🔹 ROLL IMPACT & RISKS")
    print("  ┌" + "─" * 60 + "┐")
    
    # Calculate key metrics
    total_contracts = sum(abs(opp.current_call.quantity) for opp in roll_plan.roll_opportunities)
    shares_affected = total_contracts * 100
    credit_per_share = total_estimated_credit / shares_affected if shares_affected > 0 else 0
    
    # Calculate average days extension
    today = date.today()
    avg_extension = 0
    if roll_plan.roll_opportunities:
        total_extension = sum(
            (opp.target_expiration - today).days 
            for opp in roll_plan.roll_opportunities
        )
        avg_extension = total_extension / len(roll_plan.roll_opportunities)
    
    print(f"  │ Contracts to Roll:   {total_contracts:<35} │")
    print(f"  │ Shares Affected:     {shares_affected:<35} │")
    print(f"  │ Credit per Share:    ${credit_per_share:<34.2f} │")
    print(f"  │ Avg. Time Extension: {avg_extension:<31.0f} days │")
    print("  │                                                          │")
    print("  │ ⚠️  ROLL RISKS:                                          │")
    print("  │ • Extends obligation period for covered calls           │")
    print("  │ • May roll to higher strikes (more upside potential)    │")
    print("  │ • Roll credits reduce effective cost basis              │")
    print("  │ • Assignment risk continues with new positions          │")
    print("  └" + "─" * 60 + "┘")
    
    # Execution timing
    print()
    print("🔹 EXECUTION TIMING")
    print("  ┌" + "─" * 50 + "┐")
    print(f"  │ Execution Time: {roll_plan.execution_time.strftime('%I:%M %p')}                    │")
    print("  │ ⏰ Rolls should be executed before market close    │")
    print("  │ 📈 ITM calls may be assigned if not rolled        │")
    print("  └" + "─" * 50 + "┘")
    
    print()


def confirm_roll_execution(roll_plan):
    """Confirm covered call roll execution with user.
    
    Args:
        roll_plan: RollPlan object with roll opportunities
        
    Returns:
        bool: True if user confirms execution, False otherwise
    """
    print()
    print("─" * 60)
    print("🎯 ROLL EXECUTION CONFIRMATION")
    print("─" * 60)
    print()
    
    if not roll_plan.roll_opportunities:
        print("  📭 No roll opportunities to execute")
        return False
    
    # Summary of what will be executed
    print("🔹 EXECUTION SUMMARY")
    print("  ┌" + "─" * 50 + "┐")
    print(f"  │ Symbol:           {roll_plan.symbol:<30} │")
    print(f"  │ Strategy:         Covered Call Rolls       │")
    print(f"  │ Rolls to Execute: {len(roll_plan.roll_opportunities):<30} │")
    print(f"  │ Est. Credit:      ${roll_plan.total_estimated_credit:<29.2f} │")
    print("  └" + "─" * 50 + "┘")
    
    print()
    print("🔹 ROLL TRANSACTIONS TO BE EXECUTED")
    for i, opportunity in enumerate(roll_plan.roll_opportunities, 1):
        current_call = opportunity.current_call
        contracts = abs(current_call.quantity)
        
        print(f"  {i}. Roll {contracts} contract(s):")
        print(f"     Close: ${current_call.strike:.2f} call exp {current_call.expiration.strftime('%m/%d/%Y')}")
        print(f"     Open:  ${opportunity.target_strike:.2f} call exp {opportunity.target_expiration.strftime('%m/%d/%Y')}")
        print(f"     Est. Credit: ${opportunity.estimated_credit:.2f}")
        print()
    
    print("⚠️  IMPORTANT REMINDERS:")
    print("  • Rolls will close expiring ITM calls and open new positions")
    print("  • New calls will have extended expiration dates")
    print("  • Credits collected will reduce your effective cost basis")
    print("  • Orders will be submitted as combo orders (both legs together)")
    print("  • Check your broker platform for real-time execution status")
    
    print()
    print("  ⚠️  WARNING: These orders will be submitted to your broker!")
    print("  ⚠️  Real money will be at risk. Review carefully.")
    print()
    
    while True:
        try:
            confirm = input("  🔐 Type 'CONFIRM' to execute or 'cancel' to abort: ").strip()
            
            if confirm.upper() == "CONFIRM":
                print()
                print("  ✅ Roll execution confirmed!")
                return True
            elif confirm.lower() in ["cancel", "no", "n", "abort"]:
                print()
                print("  🚫 Roll execution cancelled")
                return False
            else:
                print("  ❌ Please type 'CONFIRM' to proceed or 'cancel' to abort")
                
        except KeyboardInterrupt:
            print("\n\n  👋 Goodbye!")
            sys.exit(0)


def display_roll_execution_progress(roll_plan):
    """Display execution progress for covered call rolls.
    
    Args:
        roll_plan: RollPlan object with roll opportunities
    """
    print()
    print("─" * 60)
    print("🔄 EXECUTING COVERED CALL ROLLS")
    print("─" * 60)
    print()
    
    print(f"  ⏳ Processing {len(roll_plan.roll_opportunities)} roll transactions for {roll_plan.symbol}...")
    print()
    
    for i, opportunity in enumerate(roll_plan.roll_opportunities, 1):
        current_call = opportunity.current_call
        contracts = abs(current_call.quantity)
        
        print(f"  📤 Roll {i}: {contracts} contract(s)")
        print(f"      ${current_call.strike:.2f} → ${opportunity.target_strike:.2f}")
        print(f"      {current_call.expiration.strftime('%m/%d')} → {opportunity.target_expiration.strftime('%m/%d')}")
    
    print()
    print("  ⏳ Submitting combo orders...")


def display_roll_execution_results(results, roll_plan, strategy_impact=None):
    """Display results of covered call roll execution.
    
    Args:
        results: List of RollOrderResult objects
        roll_plan: RollPlan object with original roll opportunities
        strategy_impact: Optional StrategyImpact object with cost basis impact
    """
    print()
    print("─" * 60)
    print("📊 ROLL EXECUTION RESULTS")
    print("─" * 60)
    print()
    
    # Calculate summary statistics
    successful_rolls = sum(1 for r in results if r.success)
    failed_rolls = len(results) - successful_rolls
    total_credit_collected = sum(r.actual_credit for r in results if r.success)
    
    # Overall status
    print("🔹 EXECUTION SUMMARY")
    print("  ┌" + "─" * 50 + "┐")
    print(f"  │ Symbol:            {roll_plan.symbol:<30} │")
    print(f"  │ Strategy:          Covered Call Rolls       │")
    print(f"  │ Total Rolls:       {len(results):<30} │")
    print(f"  │ Successful:        {successful_rolls:<30} │")
    print(f"  │ Failed:            {failed_rolls:<30} │")
    print(f"  │ Credit Collected:  ${total_credit_collected:<29.2f} │")
    print("  └" + "─" * 50 + "┘")
    
    # Cost basis impact from rolls
    if strategy_impact:
        print()
        print("🔹 COST BASIS IMPACT")
        print("  ┌" + "─" * 50 + "┐")
        print(f"  │ Roll Premium:         ${strategy_impact.premium_collected:<25.2f} │")
        print(f"  │ Contracts Rolled:     {strategy_impact.contracts_executed:<25} │")
        print(f"  │ Reduction per Share:  ${strategy_impact.cost_basis_reduction_per_share:<25.2f} │")
        
        # Show cumulative impact if available
        if hasattr(roll_plan, 'cumulative_premium_collected') and roll_plan.cumulative_premium_collected is not None:
            print(f"  │ Cumulative Premium:   ${roll_plan.cumulative_premium_collected:<25.2f} │")
        
        if hasattr(roll_plan, 'cost_basis_impact') and roll_plan.cost_basis_impact is not None:
            print(f"  │ Total Cost Reduction: ${roll_plan.cost_basis_impact:<25.2f} │")
        
        print("  └" + "─" * 50 + "┘")
        
        print()
        print("💰 Roll credits further reduce your cost basis!")
        print(f"   Additional ${strategy_impact.cost_basis_reduction_per_share:.2f} reduction per share")
    
    elif total_credit_collected > 0:
        # Show estimated cost basis impact even without strategy_impact object
        total_contracts = sum(abs(opp.current_call.quantity) for opp in roll_plan.roll_opportunities if any(r.success for r in results))
        shares_affected = total_contracts * 100
        credit_per_share = total_credit_collected / shares_affected if shares_affected > 0 else 0
        
        print()
        print("🔹 ESTIMATED COST BASIS IMPACT")
        print("  ┌" + "─" * 50 + "┐")
        print(f"  │ Credit per Share:     ${credit_per_share:<25.2f} │")
        print(f"  │ Shares Affected:      {shares_affected:<25} │")
        print(f"  │ Total Credit Impact:  ${total_credit_collected:<25.2f} │")
        print("  └" + "─" * 50 + "┘")
    
    # Individual roll results
    if results:
        print()
        print("🔹 INDIVIDUAL ROLL RESULTS")
        print("  ┌" + "─" * 68 + "┐")
        print("  │ Roll   Status    Close Order    Open Order     Credit    │")
        print("  ├" + "─" * 68 + "┤")
        
        for i, result in enumerate(results, 1):
            status = "✅ Success" if result.success else "❌ Failed"
            close_id = result.close_result.order_id[:8] if result.close_result.order_id else "N/A"
            open_id = result.open_result.order_id[:8] if result.open_result.order_id else "N/A"
            credit = f"${result.actual_credit:.2f}" if result.success else "$0.00"
            
            print(f"  │ {i:<6} {status:<9} {close_id:<12} {open_id:<12} {credit:<8} │")
        
        print("  └" + "─" * 68 + "┘")
    
    # Show any error messages for failed rolls
    failed_results = [r for r in results if not r.success]
    if failed_results:
        print()
        print("🔹 FAILED ROLL DETAILS")
        for i, result in enumerate(failed_results, 1):
            print(f"  ❌ Failed Roll {i}:")
            if result.close_result.error_message:
                print(f"     Close Error: {result.close_result.error_message[:50]}...")
            if result.open_result.error_message:
                print(f"     Open Error: {result.open_result.error_message[:50]}...")
            print()
    
    # Final status message
    print()
    if successful_rolls == len(results):
        print("✅ All covered call rolls executed successfully!")
    elif successful_rolls > 0:
        print(f"⚠️  Partial success: {successful_rolls}/{len(results)} rolls completed")
    else:
        print("❌ All roll executions failed")
    
    print()
    print("📱 Check your broker dashboard for:")
    print("  • Final order confirmations")
    print("  • Updated position details")
    print("  • Actual premium credits received")
    print()
    print("📋 Roll execution details logged to trading_bot.log")
    print()


def select_rolls_to_execute(roll_plan):
    """Allow user to select which rolls to execute (all or individual).
    
    Args:
        roll_plan: RollPlan object with roll opportunities
        
    Returns:
        List of selected RollOpportunity objects, or None if cancelled
    """
    if not roll_plan.roll_opportunities:
        return []
    
    print()
    print("─" * 60)
    print("🎯 SELECT ROLLS TO EXECUTE")
    print("─" * 60)
    print()
    
    print("🔹 AVAILABLE ROLL OPTIONS")
    print("  1. Execute all rolls")
    print("  2. Select individual rolls")
    print("  3. Cancel (no rolls)")
    print()
    
    while True:
        try:
            choice = input("  Select option (1/2/3): ").strip()
            
            if choice == "1":
                print("  ✅ Selected: Execute all rolls")
                return roll_plan.roll_opportunities
            elif choice == "2":
                return _select_individual_rolls(roll_plan)
            elif choice == "3":
                print("  🚫 Roll execution cancelled")
                return None
            else:
                print("  ❌ Please enter 1, 2, or 3")
                
        except KeyboardInterrupt:
            print("\n\n  👋 Goodbye!")
            sys.exit(0)


def _select_individual_rolls(roll_plan):
    """Allow user to select individual rolls to execute.
    
    Args:
        roll_plan: RollPlan object with roll opportunities
        
    Returns:
        List of selected RollOpportunity objects
    """
    print()
    print("🔹 INDIVIDUAL ROLL SELECTION")
    print("  ┌" + "─" * 70 + "┐")
    print("  │ #  Current Call      →  New Call         Credit   Select │")
    print("  ├" + "─" * 70 + "┤")
    
    for i, opportunity in enumerate(roll_plan.roll_opportunities, 1):
        current_call = opportunity.current_call
        current_info = f"${current_call.strike:.2f} {current_call.expiration.strftime('%m/%d')}"
        new_info = f"${opportunity.target_strike:.2f} {opportunity.target_expiration.strftime('%m/%d')}"
        credit_str = f"${opportunity.estimated_credit:.2f}"
        
        print(f"  │ {i:<2} {current_info:<15} →  {new_info:<12} {credit_str:<8} [ ]    │")
    
    print("  └" + "─" * 70 + "┘")
    print()
    print("💡 Enter roll numbers to execute (e.g., '1,3,4' or '1-3' or 'all'):")
    print("   Or enter 'none' to cancel")
    
    while True:
        try:
            selection = input("  Select rolls: ").strip().lower()
            
            if selection in ["none", "cancel", ""]:
                print("  🚫 No rolls selected")
                return []
            
            if selection == "all":
                print(f"  ✅ Selected all {len(roll_plan.roll_opportunities)} rolls")
                return roll_plan.roll_opportunities
            
            # Parse selection
            selected_indices = _parse_roll_selection(selection, len(roll_plan.roll_opportunities))
            
            if selected_indices is None:
                print("  ❌ Invalid selection format. Use numbers like '1,3,4' or '1-3'")
                continue
            
            if not selected_indices:
                print("  ❌ No valid roll numbers selected")
                continue
            
            # Get selected opportunities
            selected_opportunities = [
                roll_plan.roll_opportunities[i-1] for i in selected_indices
            ]
            
            print(f"  ✅ Selected {len(selected_opportunities)} roll(s): {', '.join(map(str, selected_indices))}")
            return selected_opportunities
            
        except KeyboardInterrupt:
            print("\n\n  👋 Goodbye!")
            sys.exit(0)


def _parse_roll_selection(selection, max_rolls):
    """Parse user's roll selection input.
    
    Args:
        selection: User input string (e.g., '1,3,4' or '1-3')
        max_rolls: Maximum number of available rolls
        
    Returns:
        List of selected roll indices (1-based), or None if invalid
    """
    try:
        selected = set()
        
        # Split by commas
        parts = [part.strip() for part in selection.split(',')]
        
        for part in parts:
            if '-' in part:
                # Handle range (e.g., '1-3')
                try:
                    start, end = part.split('-', 1)
                    start_num = int(start.strip())
                    end_num = int(end.strip())
                    
                    if start_num < 1 or end_num > max_rolls or start_num > end_num:
                        return None
                    
                    selected.update(range(start_num, end_num + 1))
                except ValueError:
                    return None
            else:
                # Handle single number
                try:
                    num = int(part)
                    if num < 1 or num > max_rolls:
                        return None
                    selected.add(num)
                except ValueError:
                    return None
        
        return sorted(list(selected))
        
    except Exception:
        return None


def modify_roll_targets(selected_opportunities, broker_client):
    """Allow user to modify roll targets before execution.
    
    Args:
        selected_opportunities: List of selected RollOpportunity objects
        broker_client: Broker client for getting option data
        
    Returns:
        List of modified RollOpportunity objects, or None if cancelled
    """
    print()
    print("─" * 60)
    print("🔧 MODIFY ROLL TARGETS (OPTIONAL)")
    print("─" * 60)
    print()
    
    print("🔹 MODIFICATION OPTIONS")
    print("  1. Use current targets (no changes)")
    print("  2. Modify individual roll targets")
    print("  3. Cancel roll execution")
    print()
    
    while True:
        try:
            choice = input("  Select option (1/2/3): ").strip()
            
            if choice == "1":
                print("  ✅ Using current roll targets")
                return selected_opportunities
            elif choice == "2":
                return _modify_individual_targets(selected_opportunities, broker_client)
            elif choice == "3":
                print("  🚫 Roll execution cancelled")
                return None
            else:
                print("  ❌ Please enter 1, 2, or 3")
                
        except KeyboardInterrupt:
            print("\n\n  👋 Goodbye!")
            sys.exit(0)


def _modify_individual_targets(selected_opportunities, broker_client):
    """Allow modification of individual roll targets.
    
    Args:
        selected_opportunities: List of RollOpportunity objects
        broker_client: Broker client for option data
        
    Returns:
        List of modified RollOpportunity objects
    """
    print()
    print("🔹 INDIVIDUAL TARGET MODIFICATION")
    print("   (Press Enter to keep current target)")
    print()
    
    modified_opportunities = []
    
    for i, opportunity in enumerate(selected_opportunities, 1):
        print(f"📋 Roll {i}: {opportunity.symbol}")
        print(f"   Current: ${opportunity.current_call.strike:.2f} exp {opportunity.current_call.expiration.strftime('%m/%d/%Y')}")
        print(f"   Target:  ${opportunity.target_strike:.2f} exp {opportunity.target_expiration.strftime('%m/%d/%Y')}")
        print(f"   Credit:  ${opportunity.estimated_credit:.2f}")
        print()
        
        # For now, we'll keep the current targets since modifying them would require
        # complex option chain lookups and validation. This is a placeholder for
        # future enhancement.
        print("   💡 Target modification not yet implemented - using current targets")
        modified_opportunities.append(opportunity)
        print()
    
    print("✅ Target review complete")
    return modified_opportunities


def display_cost_basis_summary(cost_basis_summary):
    """Display comprehensive cost basis information for a symbol.
    
    Args:
        cost_basis_summary: CostBasisSummary object with cost basis details
    """
    print()
    print("─" * 70)
    print("💰 COST BASIS SUMMARY")
    print("─" * 70)
    print()
    
    # Main cost basis information
    print("🔹 COST BASIS OVERVIEW")
    print("  ┌" + "─" * 60 + "┐")
    print(f"  │ Symbol:                   {cost_basis_summary.symbol:<30} │")
    print(f"  │ Total Shares:             {cost_basis_summary.total_shares:<30} │")
    print(f"  │ Original Cost per Share:  ${cost_basis_summary.original_cost_basis_per_share:<29.2f} │")
    print(f"  │ Total Original Cost:      ${cost_basis_summary.total_original_cost:<29,.2f} │")
    print("  └" + "─" * 60 + "┘")
    
    # Premium and reduction information
    print()
    print("🔹 STRATEGY IMPACT")
    print("  ┌" + "─" * 60 + "┐")
    print(f"  │ Cumulative Premium:       ${cost_basis_summary.cumulative_premium_collected:<29.2f} │")
    print(f"  │ Effective Cost per Share: ${cost_basis_summary.effective_cost_basis_per_share:<29.2f} │")
    print(f"  │ Total Cost Reduction:     ${cost_basis_summary.total_cost_basis_reduction:<29.2f} │")
    print(f"  │ Reduction Percentage:     {cost_basis_summary.cost_basis_reduction_percentage:<29.1f}% │")
    print("  └" + "─" * 60 + "┘")
    
    # Visual representation of cost basis reduction
    print()
    print("🔹 COST BASIS BREAKDOWN")
    print("  ┌" + "─" * 60 + "┐")
    
    # Calculate values for visual representation
    original_cost = cost_basis_summary.original_cost_basis_per_share
    effective_cost = cost_basis_summary.effective_cost_basis_per_share
    premium_per_share = cost_basis_summary.cumulative_premium_collected / cost_basis_summary.total_shares if cost_basis_summary.total_shares > 0 else 0
    
    print(f"  │ Original Cost:    ${original_cost:>8.2f} ████████████████████████ │")
    print(f"  │ Premium Collected: ${premium_per_share:>7.2f} ████████                 │")
    print(f"  │ Effective Cost:   ${effective_cost:>8.2f} ████████████████         │")
    print("  └" + "─" * 60 + "┘")
    
    # Summary message
    print()
    if cost_basis_summary.cost_basis_reduction_percentage > 0:
        print(f"  ✅ Your cost basis has been reduced by {cost_basis_summary.cost_basis_reduction_percentage:.1f}%")
        print(f"     through covered call premium collection!")
    else:
        print("  📊 No cost basis reduction yet - start executing strategies to see impact")
    
    print()


def display_strategy_impact(strategy_impact):
    """Display cost basis reduction from a specific strategy execution.
    
    Args:
        strategy_impact: StrategyImpact object with strategy execution details
    """
    print()
    print("─" * 60)
    print("📈 STRATEGY IMPACT")
    print("─" * 60)
    print()
    
    # Strategy execution details
    print("🔹 EXECUTION DETAILS")
    print("  ┌" + "─" * 50 + "┐")
    print(f"  │ Strategy Type:       {strategy_impact.strategy_type:<25} │")
    print(f"  │ Execution Date:      {strategy_impact.execution_date.strftime('%Y-%m-%d'):<25} │")
    print(f"  │ Contracts Executed:  {strategy_impact.contracts_executed:<25} │")
    print(f"  │ Premium Collected:   ${strategy_impact.premium_collected:<24.2f} │")
    print("  └" + "─" * 50 + "┘")
    
    # Cost basis impact
    print()
    print("🔹 COST BASIS IMPACT")
    print("  ┌" + "─" * 50 + "┐")
    print(f"  │ Reduction per Share: ${strategy_impact.cost_basis_reduction_per_share:<24.2f} │")
    
    # Calculate total shares affected (assuming 100 shares per contract)
    shares_affected = strategy_impact.contracts_executed * 100
    total_reduction = strategy_impact.cost_basis_reduction_per_share * shares_affected
    
    print(f"  │ Shares Affected:     {shares_affected:<25} │")
    print(f"  │ Total Reduction:     ${total_reduction:<24.2f} │")
    print("  └" + "─" * 50 + "┘")
    
    # Strategy type specific information
    print()
    print("🔹 STRATEGY NOTES")
    if strategy_impact.strategy_type == "initial_covered_calls":
        print("  📝 Initial covered call strategy execution")
        print("     • Sold covered calls against existing stock position")
        print("     • Premium collected reduces effective cost basis")
        print("     • Creates obligation to sell shares if called away")
    elif strategy_impact.strategy_type == "roll":
        print("  📝 Covered call roll transaction")
        print("     • Closed expiring ITM calls and opened new positions")
        print("     • Additional premium collected further reduces cost basis")
        print("     • Extended obligation period with new expiration dates")
    else:
        print(f"  📝 {strategy_impact.strategy_type.replace('_', ' ').title()} strategy")
        print("     • Premium collected reduces effective cost basis")
    
    print()


def display_cost_basis_history(symbol, strategy_history):
    """Display historical strategy impact on cost basis.
    
    Args:
        symbol: Stock symbol
        strategy_history: List of StrategyImpact objects sorted by execution date
    """
    print()
    print("─" * 80)
    print(f"📊 COST BASIS HISTORY - {symbol}")
    print("─" * 80)
    print()
    
    if not strategy_history:
        print("  📭 No strategy execution history found")
        print("     Execute some covered call strategies to see historical impact")
        return
    
    # Historical execution table
    print("🔹 STRATEGY EXECUTION HISTORY")
    print("  ┌" + "─" * 76 + "┐")
    print("  │ Date       Strategy Type        Contracts  Premium   Reduction/Share │")
    print("  ├" + "─" * 76 + "┤")
    
    total_premium = 0.0
    total_contracts = 0
    
    for impact in strategy_history:
        strategy_display = impact.strategy_type.replace('_', ' ').title()[:18]  # Truncate if too long
        date_str = impact.execution_date.strftime('%Y-%m-%d')
        
        print(f"  │ {date_str}  {strategy_display:<18} {impact.contracts_executed:<9}  ${impact.premium_collected:<7.2f}  ${impact.cost_basis_reduction_per_share:<13.2f} │")
        
        total_premium += impact.premium_collected
        total_contracts += impact.contracts_executed
    
    print("  ├" + "─" * 76 + "┤")
    print(f"  │ TOTALS                         {total_contracts:<9}  ${total_premium:<7.2f}                  │")
    print("  └" + "─" * 76 + "┘")
    
    # Summary statistics
    print()
    print("🔹 HISTORICAL SUMMARY")
    print("  ┌" + "─" * 50 + "┐")
    print(f"  │ Total Executions:    {len(strategy_history):<25} │")
    print(f"  │ Total Contracts:     {total_contracts:<25} │")
    print(f"  │ Total Premium:       ${total_premium:<24.2f} │")
    
    # Calculate average premium per execution and per contract
    avg_premium_per_execution = total_premium / len(strategy_history) if strategy_history else 0
    avg_premium_per_contract = total_premium / total_contracts if total_contracts > 0 else 0
    
    print(f"  │ Avg Premium/Execution: ${avg_premium_per_execution:<22.2f} │")
    print(f"  │ Avg Premium/Contract: ${avg_premium_per_contract:<23.2f} │")
    print("  └" + "─" * 50 + "┘")
    
    # Timeline analysis
    if len(strategy_history) > 1:
        first_date = strategy_history[0].execution_date
        last_date = strategy_history[-1].execution_date
        days_span = (last_date - first_date).days
        
        print()
        print("🔹 TIMELINE ANALYSIS")
        print("  ┌" + "─" * 50 + "┐")
        print(f"  │ First Execution:     {first_date.strftime('%Y-%m-%d'):<25} │")
        print(f"  │ Latest Execution:    {last_date.strftime('%Y-%m-%d'):<25} │")
        print(f"  │ Time Span:           {days_span:<22} days │")
        
        if days_span > 0:
            executions_per_month = (len(strategy_history) / days_span) * 30
            print(f"  │ Avg Frequency:       {executions_per_month:<22.1f}/month │")
        
        print("  └" + "─" * 50 + "┘")
    
    print()


def display_final_strategy_report(symbol, strategy_type, execution_results, cost_basis_summary=None, strategy_impact=None):
    """Display comprehensive final report for strategy execution.
    
    Args:
        symbol: Stock symbol
        strategy_type: Type of strategy executed
        execution_results: Results from strategy execution
        cost_basis_summary: Optional CostBasisSummary object
        strategy_impact: Optional StrategyImpact object from this execution
    """
    print()
    print("═" * 70)
    print("📋 FINAL STRATEGY EXECUTION REPORT")
    print("═" * 70)
    print()
    
    # Strategy execution summary
    print("🔹 EXECUTION SUMMARY")
    print("  ┌" + "─" * 60 + "┐")
    print(f"  │ Symbol:           {symbol:<40} │")
    print(f"  │ Strategy:         {strategy_type:<40} │")
    print(f"  │ Execution Date:   {date.today().strftime('%Y-%m-%d'):<40} │")
    
    if strategy_impact:
        print(f"  │ Contracts:        {strategy_impact.contracts_executed:<40} │")
        print(f"  │ Premium Collected: ${strategy_impact.premium_collected:<39.2f} │")
    
    print("  └" + "─" * 60 + "┘")
    
    # Cost basis impact from this execution
    if strategy_impact:
        print()
        print("🔹 THIS EXECUTION'S IMPACT")
        print("  ┌" + "─" * 60 + "┐")
        print(f"  │ Premium Collected:        ${strategy_impact.premium_collected:<29.2f} │")
        print(f"  │ Cost Basis Reduction/Share: ${strategy_impact.cost_basis_reduction_per_share:<27.2f} │")
        
        # Calculate total impact
        shares_affected = strategy_impact.contracts_executed * 100
        total_reduction = strategy_impact.cost_basis_reduction_per_share * shares_affected
        
        print(f"  │ Shares Affected:          {shares_affected:<29} │")
        print(f"  │ Total Cost Basis Reduction: ${total_reduction:<27.2f} │")
        print("  └" + "─" * 60 + "┘")
    
    # Overall cost basis summary
    if cost_basis_summary:
        print()
        print("🔹 UPDATED COST BASIS SUMMARY")
        print("  ┌" + "─" * 60 + "┐")
        print(f"  │ Original Cost per Share:  ${cost_basis_summary.original_cost_basis_per_share:<29.2f} │")
        print(f"  │ Effective Cost per Share: ${cost_basis_summary.effective_cost_basis_per_share:<29.2f} │")
        print(f"  │ Total Premium Collected:  ${cost_basis_summary.cumulative_premium_collected:<29.2f} │")
        print(f"  │ Cost Basis Reduction:     {cost_basis_summary.cost_basis_reduction_percentage:<29.1f}% │")
        print("  └" + "─" * 60 + "┘")
        
        # Visual progress bar for cost basis reduction
        print()
        print("🔹 COST BASIS REDUCTION PROGRESS")
        reduction_pct = min(cost_basis_summary.cost_basis_reduction_percentage, 100)  # Cap at 100%
        filled_blocks = int(reduction_pct / 5)  # Each block represents 5%
        empty_blocks = 20 - filled_blocks
        
        progress_bar = "█" * filled_blocks + "░" * empty_blocks
        print(f"  0%  {progress_bar}  100%")
        print(f"      {reduction_pct:.1f}% cost basis reduction achieved")
    
    # Next steps and recommendations
    print()
    print("🔹 NEXT STEPS")
    print("  ✅ Strategy execution completed successfully")
    print("  📱 Check your broker dashboard for order confirmations")
    print("  📊 Monitor positions for assignment risk and roll opportunities")
    
    if cost_basis_summary and cost_basis_summary.cost_basis_reduction_percentage > 0:
        print(f"  💰 Your effective cost basis is now ${cost_basis_summary.effective_cost_basis_per_share:.2f} per share")
        print("  🎯 Continue executing strategies to further reduce cost basis")
    
    print()
    print("📋 All details have been logged to trading_bot.log")
    print("═" * 70)
    print()


def execute_tiered_covered_calls(symbol, broker_client, config):
    """Execute the complete tiered covered calls workflow.
    
    Args:
        symbol: Stock symbol to trade
        broker_client: Initialized broker client
        config: Trading configuration
        
    Returns:
        bool: True if execution was successful, False otherwise
    """
    try:
        # Import required modules
        from src.positions.position_service import PositionService
        from src.strategy.tiered_covered_call_strategy import TieredCoveredCallCalculator
        from src.logging.bot_logger import BotLogger
        from src.config.models import LoggingConfig
        from datetime import date
        
        # Create logger
        logging_config = LoggingConfig(level="INFO", file_path="logs/trading_bot.log")
        logger = BotLogger(logging_config)
        
        # Initialize services
        position_service = PositionService(broker_client, logger)
        calculator = TieredCoveredCallCalculator(broker_client, logger=logger)
        
        print()
        print("═" * 60)
        print("🔍 ANALYZING POSITIONS...")
        print("═" * 60)
        
        # Get position summary
        try:
            position_summary = position_service.get_long_positions(symbol)
        except Exception as e:
            print(f"  ❌ Error retrieving positions: {str(e)}")
            return False
        
        # Display position summary
        display_position_summary(position_summary)
        
        # Check if we have sufficient shares
        if position_summary.available_shares < 100:
            print("  ❌ Insufficient shares for covered calls")
            return False
        
        if position_summary.available_shares < 300:
            print("  ⚠️  Warning: Less than 300 shares available. Strategy will be less diversified.")
            proceed = input("  Continue anyway? (y/n): ").strip().lower()
            if proceed not in ["y", "yes"]:
                print("  🚫 Strategy cancelled")
                return False
        
        print()
        print("═" * 60)
        print("🧮 CALCULATING STRATEGY...")
        print("═" * 60)
        
        # Calculate strategy
        try:
            strategy_plan = calculator.calculate_strategy(position_summary)
        except Exception as e:
            print(f"  ❌ Error calculating strategy: {str(e)}")
            print("  💡 This might be due to:")
            print("     • Insufficient option liquidity")
            print("     • Market hours (options data unavailable)")
            print("     • Network connectivity issues")
            return False
        
        # Display strategy preview
        display_tiered_strategy_preview(strategy_plan)
        
        # Get user confirmation
        if not confirm_tiered_execution(strategy_plan, broker_client):
            return False
        
        # Display execution progress
        display_execution_progress(strategy_plan)
        
        # Actually submit the orders to the broker
        print("  ⏳ Submitting orders to broker...")
        
        try:
            # Import the TradingBot to use its order submission
            from src.bot.trading_bot import TradingBot
            
            # Create a temporary config for the trading bot
            import tempfile
            import json
            
            # Read the current config
            with open('config/config.json', 'r') as f:
                config_data = json.load(f)
            
            # Set strategy to tcc
            config_data['strategy'] = 'tcc'
            config_data['symbols'] = [symbol]
            config_data['run_immediately'] = True
            
            # Write to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
                json.dump(config_data, tmp)
                tmp_path = tmp.name
            
            # Initialize trading bot for real execution (not dry run)
            trading_bot = TradingBot(config_path=tmp_path, dry_run=False)
            if not trading_bot.initialize():
                print("  ❌ Failed to initialize trading bot for execution")
                return False
            
            # Submit the orders using the trading bot's method
            result = trading_bot.process_tiered_covered_calls(symbol)
            
            # Clean up temp file
            import os
            os.unlink(tmp_path)
            
            if result.success:
                print("  ✅ Orders submitted successfully!")
                print(f"  💰 Premium collected: ${result.premium_collected:.2f}")
            else:
                print("  ❌ Order submission failed")
                if result.error_message:
                    print(f"     Error: {result.error_message}")
                return False
                
        except Exception as e:
            print(f"  ❌ Error submitting orders: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

        
        # Display results
        display_execution_results([], strategy_plan)
        
        return True
        
    except Exception as e:
        print(f"  ❌ Unexpected error: {str(e)}")
        return False


def initialize_broker():
    """Initialize broker client to check positions."""
    suppress_output()

    from src.config.config_manager import ConfigManager
    from src.brokers.broker_factory import BrokerFactory
    from src.logging.bot_logger import BotLogger
    from src.config.models import LoggingConfig

    config_manager = ConfigManager()
    config = config_manager.load_config("config/config.json")

    # Create a quiet logger
    logging_config = LoggingConfig(level="ERROR", file_path="logs/trading_bot.log")
    logger = BotLogger(logging_config)

    broker_type = config.broker_type
    if broker_type.lower() == "alpaca":
        credentials = {
            "api_key": config.alpaca_credentials.api_key,
            "api_secret": config.alpaca_credentials.api_secret,
            "paper": config.alpaca_credentials.paper,
        }
    else:
        credentials = {
            "api_token": config.tradier_credentials.api_token,
            "account_id": config.tradier_credentials.account_id,
            "base_url": config.tradier_credentials.base_url,
        }

    broker_client = BrokerFactory.create_broker(
        broker_type=broker_type, credentials=credentials, logger=logger
    )
    broker_client.authenticate()

    return config, broker_client


def get_option_premium(trading_bot, symbol, strike, expiration, option_type):
    """Get real-time option premium from broker.
    
    Args:
        trading_bot: TradingBot instance
        symbol: Stock symbol
        strike: Strike price
        expiration: Expiration date
        option_type: 'call' or 'put'
        
    Returns:
        float: Mid price of the option, or 0.50 as fallback
    """
    try:
        # Format expiration date
        expiration_str = expiration.strftime("%y%m%d")
        
        # Construct option symbol using OCC format
        strike_str = f"{int(strike * 1000):08d}"
        option_symbol = f"{symbol}{expiration_str}{option_type[0].upper()}{strike_str}"
        
        # Get quote
        quotes = trading_bot.broker_client.get_option_quotes([option_symbol])
        if quotes and option_symbol in quotes:
            return quotes[option_symbol].get("mid", 0.50)
    except Exception:
        pass
    
    return 0.50  # Fallback default


def calculate_planned_orders(trading_bot, symbol, strategy, shares_owned=None):
    """Calculate planned orders for verification display.
    
    This function calculates what orders would be placed without actually
    submitting them, allowing the user to review before execution.
    
    Args:
        trading_bot: Initialized TradingBot instance
        symbol: Stock symbol
        strategy: Strategy code
        shares_owned: Number of shares owned (for strategies that need it like LCC)
        
    Returns:
        List of order dictionaries with details for display
    """
    from datetime import date, timedelta
    
    planned_orders = []
    
    try:
        # Get current price
        current_price = trading_bot.broker_client.get_current_price(symbol)
        
        if strategy == "pcs":
            # Put Credit Spread
            short_strike_target = trading_bot.strategy_calculator.calculate_short_strike(
                current_price=current_price,
                offset_percent=trading_bot.config.strike_offset_percent,
                offset_dollars=trading_bot.config.strike_offset_dollars,
            )
            long_strike_target = trading_bot.strategy_calculator.calculate_long_strike(
                short_strike=short_strike_target,
                spread_width=trading_bot.config.spread_width
            )
            target_expiration = trading_bot.strategy_calculator.calculate_expiration_date(
                execution_date=date.today(),
                offset_weeks=trading_bot.config.expiration_offset_weeks,
            )
            
            # Find nearest available expiration
            expiration = trading_bot.broker_client.get_nearest_expiration(symbol, target_expiration)
            
            # Get option chain and find actual available strikes
            option_chain = trading_bot.broker_client.get_option_chain(symbol, expiration)
            put_options = [contract for contract in option_chain if contract.option_type == "put"]
            available_strikes = sorted(set([contract.strike for contract in put_options]))
            
            # Find nearest available strikes
            short_strike = trading_bot.strategy_calculator.find_nearest_strike_below(
                target_strike=short_strike_target,
                available_strikes=available_strikes
            )
            long_strike = trading_bot.strategy_calculator.find_nearest_strike_below(
                target_strike=long_strike_target,
                available_strikes=available_strikes
            )
            
            # Get the actual option contracts for pricing
            short_put = next((opt for opt in put_options if opt.strike == short_strike), None)
            long_put = next((opt for opt in put_options if opt.strike == long_strike), None)
            
            # Get real-time quotes for accurate pricing
            estimated_credit = 0.50  # Default fallback
            if short_put and long_put:
                quotes = trading_bot.broker_client.get_option_quotes([short_put.symbol, long_put.symbol])
                if quotes:
                    short_price = quotes.get(short_put.symbol, {}).get("mid", 0)
                    long_price = quotes.get(long_put.symbol, {}).get("mid", 0)
                    if short_price > 0 and long_price > 0:
                        estimated_credit = short_price - long_price
            
            planned_orders.append({
                'type': 'spread',
                'action': 'SELL',
                'spread_type': 'credit',
                'short_strike': short_strike,
                'long_strike': long_strike,
                'expiration': expiration.strftime('%m/%d/%Y'),
                'quantity': trading_bot.config.contract_quantity,
                'option_type': 'PUT',
                'estimated_price': estimated_credit
            })
            
        elif strategy == "lps":
            # Laddered Put Spread - 5 weekly put credit spreads
            # Calculate target strikes (use more conservative offset for safety)
            # Use 5-10% below current price instead of the default 20%
            conservative_offset = min(trading_bot.config.strike_offset_percent, 10.0)
            
            short_strike_target = trading_bot.strategy_calculator.calculate_short_strike(
                current_price=current_price,
                offset_percent=conservative_offset,
                offset_dollars=0,  # Use percentage only
            )
            long_strike_target = trading_bot.strategy_calculator.calculate_long_strike(
                short_strike=short_strike_target,
                spread_width=trading_bot.config.spread_width
            )
            
            # Create 5 weekly spreads
            num_legs = 5  # 5 weekly expirations
            for i in range(num_legs):
                try:
                    # Calculate expiration for each week
                    target_expiration = date.today() + timedelta(weeks=i+1)
                    
                    # Find nearest available expiration
                    expiration = trading_bot.broker_client.get_nearest_expiration(symbol, target_expiration)
                    
                    # Get option chain for this expiration
                    option_chain = trading_bot.broker_client.get_option_chain(symbol, expiration)
                    put_options = [contract for contract in option_chain if contract.option_type == "put"]
                    available_strikes = sorted(set([contract.strike for contract in put_options]))
                    
                    if not available_strikes:
                        continue  # Skip this week if no strikes available
                    
                    # Find nearest available strikes with fallback
                    try:
                        short_strike = trading_bot.strategy_calculator.find_nearest_strike_below(
                            target_strike=short_strike_target,
                            available_strikes=available_strikes
                        )
                    except ValueError:
                        # If target is too low, use the lowest available strike
                        short_strike = min(available_strikes)
                    
                    try:
                        long_strike = trading_bot.strategy_calculator.find_nearest_strike_below(
                            target_strike=long_strike_target,
                            available_strikes=available_strikes
                        )
                    except ValueError:
                        # If target is too low, use strike below short strike
                        strikes_below_short = [s for s in available_strikes if s < short_strike]
                        if strikes_below_short:
                            long_strike = max(strikes_below_short)
                        else:
                            continue  # Skip if can't form a valid spread
                    
                    # Ensure valid spread (short > long)
                    if short_strike <= long_strike:
                        continue
                    
                    # Get quotes for pricing
                    short_put = next((opt for opt in put_options if opt.strike == short_strike), None)
                    long_put = next((opt for opt in put_options if opt.strike == long_strike), None)
                    
                    estimated_credit = 0.50  # Default fallback
                    if short_put and long_put:
                        quotes = trading_bot.broker_client.get_option_quotes([short_put.symbol, long_put.symbol])
                        if quotes:
                            short_price = quotes.get(short_put.symbol, {}).get("mid", 0)
                            long_price = quotes.get(long_put.symbol, {}).get("mid", 0)
                            if short_price > 0 and long_price > 0:
                                estimated_credit = short_price - long_price
                    
                    planned_orders.append({
                        'type': 'spread',
                        'action': 'SELL',
                        'spread_type': 'credit',
                        'short_strike': short_strike,
                        'long_strike': long_strike,
                        'expiration': expiration.strftime('%m/%d/%Y'),
                        'quantity': 1,  # 1 spread per week
                        'option_type': f'PUT (Week {i+1})',
                        'estimated_price': estimated_credit
                    })
                except Exception as e:
                    # Skip this week if any error occurs
                    print(f"  ⚠️  Skipping week {i+1}: {str(e)}")
                    continue
            
        elif strategy == "tpd":
            # Tiered Put Diagonal - Sell short-term puts at multiple expirations against existing long puts
            # Similar to Tiered Covered Calls but for puts
            try:
                detailed_positions = trading_bot.broker_client.get_detailed_positions(symbol)
                
                # Filter for long puts (position_type will be 'long_put')
                long_puts = [pos for pos in detailed_positions 
                            if hasattr(pos, 'position_type') and pos.position_type == 'long_put' and pos.quantity > 0]
                
                if not long_puts:
                    print(f"  ❌ No long puts found for {symbol}")
                    print(f"     Tiered Put Diagonal requires existing long put positions")
                    print(f"     Please buy protective puts first, then use this strategy")
                    return None
                
                print(f"  ✅ Found {len(long_puts)} long put position(s)")
                
                # For each long put, create tiered short puts at 3 different expirations
                for long_put in long_puts:
                    long_put_strike = long_put.strike if hasattr(long_put, 'strike') else 0
                    long_put_qty = abs(long_put.quantity)
                    
                    if long_put_strike == 0:
                        continue
                    
                    # Get next 3 available expirations starting from 1 week out
                    try:
                        available_expirations = trading_bot.broker_client.get_option_expirations(symbol)
                        # Use same logic as TCC: filter by min/max days and validate put options exist
                        today = date.today()
                        min_date = today + timedelta(days=7)  # Start 1 week out
                        max_date = today + timedelta(days=60)  # Max 60 days out
                        long_exp = long_put.expiration if hasattr(long_put, 'expiration') else None
                        
                        # Filter by date range and before long put expiration
                        if long_exp:
                            filtered_expirations = [exp for exp in available_expirations 
                                                   if min_date <= exp <= max_date and exp < long_exp]
                        else:
                            filtered_expirations = [exp for exp in available_expirations 
                                                   if min_date <= exp <= max_date]
                        
                        if not filtered_expirations:
                            print(f"  ⚠️  No valid expirations found for long put ${long_put_strike:.2f}")
                            continue
                        
                        # Validate that each expiration has put options available (like TCC validates calls)
                        validated_expirations = []
                        for expiration in filtered_expirations[:5]:  # Check up to 5 to get 3 valid
                            try:
                                options = trading_bot.broker_client.get_option_chain(symbol, expiration)
                                put_options = [opt for opt in options if opt.option_type and opt.option_type.lower() == 'put']
                                
                                if put_options:
                                    validated_expirations.append(expiration)
                                    if len(validated_expirations) >= 3:
                                        break
                            except Exception:
                                continue
                        
                        if not validated_expirations:
                            print(f"  ⚠️  No expirations with put options found for long put ${long_put_strike:.2f}")
                            continue
                        
                        # Take up to 3 validated expirations
                        tier_expirations = validated_expirations[:3]
                        
                    except Exception as e:
                        print(f"  ⚠️  Could not get expirations: {str(e)}")
                        continue
                    
                    tier_quantities = []
                    
                    # Distribute quantity across tiers
                    if long_put_qty == 3:
                        # If exactly 3 contracts, sell 1 per tier
                        tier_quantities = [1, 1, 1]
                    elif long_put_qty > 3:
                        # If more than 3, distribute evenly
                        base_qty = long_put_qty // 3
                        remainder = long_put_qty % 3
                        tier_quantities = [base_qty, base_qty, base_qty]
                        # Distribute remainder to first tiers
                        for i in range(remainder):
                            tier_quantities[i] += 1
                    else:
                        # If less than 3 contracts, distribute 1 per tier starting from Tier 1
                        tier_quantities = [0, 0, 0]
                        for i in range(long_put_qty):
                            tier_quantities[i] = 1
                    
                    # Create orders for each tier
                    for tier_idx, (expiration, qty) in enumerate(zip(tier_expirations, tier_quantities), 1):
                        if qty == 0:
                            continue
                        
                        try:
                            # Make sure short expiration is before long expiration
                            # For diagonal spreads, short leg should expire before long leg
                            if hasattr(long_put, 'expiration'):
                                long_exp = long_put.expiration
                                print(f"  📅 Tier {tier_idx}: Short exp {expiration.strftime('%m/%d/%Y')}, Long exp {long_exp.strftime('%m/%d/%Y')}")
                                
                                if expiration >= long_exp:
                                    print(f"  ⚠️  Skipping tier {tier_idx} - short expiration must be before long expiration")
                                    continue
                            
                            # Get option chain
                            option_chain = trading_bot.broker_client.get_option_chain(symbol, expiration)
                            put_options = [contract for contract in option_chain if contract.option_type == "put"]
                            available_strikes = sorted(set([contract.strike for contract in put_options]))
                            
                            if not available_strikes:
                                continue
                            
                            # Find strike near the money (slightly below current price)
                            # Use configurable percentage below current price for better premium
                            target_percent_below = trading_bot.config.tpd_target_percent_below / 100.0
                            target_strike = current_price * (1 - target_percent_below)
                            
                            # Select the nearest available strike to our target
                            short_strike = min(available_strikes, key=lambda x: abs(x - target_strike))
                            
                            # Get quote for pricing
                            short_put = next((opt for opt in put_options if opt.strike == short_strike), None)
                            
                            estimated_credit = 0.50  # Default
                            if short_put:
                                quotes = trading_bot.broker_client.get_option_quotes([short_put.symbol])
                                if quotes and short_put.symbol in quotes:
                                    estimated_credit = quotes[short_put.symbol].get("mid", 0.50)
                            
                            planned_orders.append({
                                'type': 'option',
                                'action': 'SELL',
                                'strike': short_strike,
                                'expiration': expiration.strftime('%m/%d/%Y'),
                                'quantity': qty,
                                'option_type': f'PUT Tier {tier_idx} (vs ${long_put_strike:.2f})',
                                'estimated_price': estimated_credit
                            })
                        except Exception as tier_error:
                            print(f"  ⚠️  Skipping tier {tier_idx}: {str(tier_error)}")
                            continue
                    
                if not planned_orders:
                    print(f"  ❌ Could not create any diagonal spreads")
                    print(f"     No valid short expirations found")
                    return None
                    
            except Exception as e:
                print(f"  ❌ Error checking positions: {str(e)}")
                import traceback
                traceback.print_exc()
                return None
            
        elif strategy == "cc":
            # Covered Call
            call_strike_target = current_price * (1 + trading_bot.config.covered_call_offset_percent / 100)
            if trading_bot.config.covered_call_offset_dollars:
                call_strike_target = current_price + trading_bot.config.covered_call_offset_dollars
            
            target_expiration = date.today() + timedelta(days=trading_bot.config.covered_call_expiration_days)
            
            # Find nearest available expiration
            expiration = trading_bot.broker_client.get_nearest_expiration(symbol, target_expiration)
            
            # Get option chain and find actual available strikes
            option_chain = trading_bot.broker_client.get_option_chain(symbol, expiration)
            call_options = [contract for contract in option_chain if contract.option_type == "call"]
            available_strikes = sorted(set([contract.strike for contract in call_options]))
            
            # Find nearest available strike above target
            call_strike = trading_bot.strategy_calculator.find_nearest_strike_above(
                target_strike=call_strike_target,
                available_strikes=available_strikes
            )
            
            # Get real-time premium
            estimated_credit = get_option_premium(trading_bot, symbol, call_strike, expiration, 'call')
            
            planned_orders.append({
                'type': 'option',
                'action': 'SELL',
                'strike': call_strike,
                'expiration': expiration.strftime('%m/%d/%Y'),
                'quantity': 1,
                'option_type': 'CALL',
                'estimated_price': estimated_credit
            })
            
        elif strategy in ["pc", "cs"]:
            # Protected Collar / Collar Strategy
            put_strike_target = current_price * (1 - trading_bot.config.collar_put_offset_percent / 100)
            call_strike_target = current_price * (1 + trading_bot.config.collar_call_offset_percent / 100)
            
            target_expiration = date.today() + timedelta(weeks=trading_bot.config.expiration_offset_weeks)
            
            # Find nearest available expiration
            expiration = trading_bot.broker_client.get_nearest_expiration(symbol, target_expiration)
            
            # Get option chain and find actual available strikes
            option_chain = trading_bot.broker_client.get_option_chain(symbol, expiration)
            put_options = [contract for contract in option_chain if contract.option_type == "put"]
            call_options = [contract for contract in option_chain if contract.option_type == "call"]
            put_strikes = sorted(set([contract.strike for contract in put_options]))
            call_strikes = sorted(set([contract.strike for contract in call_options]))
            
            # Find nearest available strikes
            put_strike = trading_bot.strategy_calculator.find_nearest_strike_below(
                target_strike=put_strike_target,
                available_strikes=put_strikes
            )
            call_strike = trading_bot.strategy_calculator.find_nearest_strike_above(
                target_strike=call_strike_target,
                available_strikes=call_strikes
            )
            
            # Get real-time premiums
            put_debit = get_option_premium(trading_bot, symbol, put_strike, expiration, 'put')
            call_credit = get_option_premium(trading_bot, symbol, call_strike, expiration, 'call')
            
            planned_orders.append({
                'type': 'option',
                'action': 'BUY',
                'strike': put_strike,
                'expiration': expiration.strftime('%m/%d/%Y'),
                'quantity': 1,
                'option_type': 'PUT',
                'estimated_price': put_debit
            })
            planned_orders.append({
                'type': 'option',
                'action': 'SELL',
                'strike': call_strike,
                'expiration': expiration.strftime('%m/%d/%Y'),
                'quantity': 1,
                'option_type': 'CALL',
                'estimated_price': call_credit
            })
            
        elif strategy == "ws":
            # Wheel Strategy
            # Check if we have shares (covered call) or not (cash-secured put)
            position = trading_bot.broker_client.get_position(symbol)
            has_shares = position and position.quantity >= 100
            
            if has_shares:
                # Covered call phase
                call_strike = current_price * (1 + trading_bot.config.wheel_call_offset_percent / 100)
                call_strike = round(call_strike)
                expiration = date.today() + timedelta(days=trading_bot.config.wheel_expiration_days)
                
                # Get real-time premium
                estimated_credit = get_option_premium(trading_bot, symbol, call_strike, expiration, 'call')
                
                planned_orders.append({
                    'type': 'option',
                    'action': 'SELL',
                    'strike': call_strike,
                    'expiration': expiration.strftime('%m/%d/%Y'),
                    'quantity': position.quantity // 100,
                    'option_type': 'CALL',
                    'estimated_price': estimated_credit
                })
            else:
                # Cash-secured put phase
                put_strike = current_price * (1 - trading_bot.config.wheel_put_offset_percent / 100)
                put_strike = round(put_strike)
                expiration = date.today() + timedelta(days=trading_bot.config.wheel_expiration_days)
                
                # Get real-time premium
                estimated_credit = get_option_premium(trading_bot, symbol, put_strike, expiration, 'put')
                
                planned_orders.append({
                    'type': 'option',
                    'action': 'SELL',
                    'strike': put_strike,
                    'expiration': expiration.strftime('%m/%d/%Y'),
                    'quantity': 1,
                    'option_type': 'PUT',
                    'estimated_price': estimated_credit
                })
                
        elif strategy == "mp":
            # Married Put
            put_strike = current_price * (1 - trading_bot.config.mp_put_offset_percent / 100)
            put_strike = round(put_strike)
            expiration = date.today() + timedelta(days=trading_bot.config.mp_expiration_days)
            
            # Get real-time premium for put
            put_debit = get_option_premium(trading_bot, symbol, put_strike, expiration, 'put')
            
            planned_orders.append({
                'type': 'stock',
                'action': 'BUY',
                'strike': current_price,
                'expiration': 'N/A',
                'quantity': 100,
                'option_type': 'SHARES',
                'estimated_price': current_price
            })
            planned_orders.append({
                'type': 'option',
                'action': 'BUY',
                'strike': put_strike,
                'expiration': expiration.strftime('%m/%d/%Y'),
                'quantity': 1,
                'option_type': 'PUT',
                'estimated_price': put_debit
            })
            
        elif strategy == "ls":
            # Long Straddle
            atm_strike = round(current_price)
            expiration = date.today() + timedelta(days=trading_bot.config.ls_expiration_days)
            
            # Get real-time premiums
            call_debit = get_option_premium(trading_bot, symbol, atm_strike, expiration, 'call')
            put_debit = get_option_premium(trading_bot, symbol, atm_strike, expiration, 'put')
            
            planned_orders.append({
                'type': 'option',
                'action': 'BUY',
                'strike': atm_strike,
                'expiration': expiration.strftime('%m/%d/%Y'),
                'quantity': trading_bot.config.ls_num_contracts,
                'option_type': 'CALL',
                'estimated_price': call_debit
            })
            planned_orders.append({
                'type': 'option',
                'action': 'BUY',
                'strike': atm_strike,
                'expiration': expiration.strftime('%m/%d/%Y'),
                'quantity': trading_bot.config.ls_num_contracts,
                'option_type': 'PUT',
                'estimated_price': put_debit
            })
            
        elif strategy == "ib":
            # Iron Butterfly
            atm_strike = round(current_price)
            wing_width = trading_bot.config.ib_wing_width
            expiration = date.today() + timedelta(days=trading_bot.config.ib_expiration_days)
            
            # Fetch premiums for all legs
            long_put_premium = get_option_premium(trading_bot, symbol, atm_strike - wing_width, expiration, 'put')
            short_put_premium = get_option_premium(trading_bot, symbol, atm_strike, expiration, 'put')
            short_call_premium = get_option_premium(trading_bot, symbol, atm_strike, expiration, 'call')
            long_call_premium = get_option_premium(trading_bot, symbol, atm_strike + wing_width, expiration, 'call')
            
            planned_orders.append({
                'type': 'option',
                'action': 'BUY',
                'strike': atm_strike - wing_width,
                'expiration': expiration.strftime('%m/%d/%Y'),
                'quantity': trading_bot.config.ib_num_contracts,
                'option_type': 'PUT',
                'estimated_price': long_put_premium
            })
            planned_orders.append({
                'type': 'option',
                'action': 'SELL',
                'strike': atm_strike,
                'expiration': expiration.strftime('%m/%d/%Y'),
                'quantity': trading_bot.config.ib_num_contracts,
                'option_type': 'PUT',
                'estimated_price': short_put_premium
            })
            planned_orders.append({
                'type': 'option',
                'action': 'SELL',
                'strike': atm_strike,
                'expiration': expiration.strftime('%m/%d/%Y'),
                'quantity': trading_bot.config.ib_num_contracts,
                'option_type': 'CALL',
                'estimated_price': short_call_premium
            })
            planned_orders.append({
                'type': 'option',
                'action': 'BUY',
                'strike': atm_strike + wing_width,
                'expiration': expiration.strftime('%m/%d/%Y'),
                'quantity': trading_bot.config.ib_num_contracts,
                'option_type': 'CALL',
                'estimated_price': long_call_premium
            })
            
        elif strategy == "ic":
            # Iron Condor
            put_short = current_price * (1 - trading_bot.config.ic_put_spread_offset_percent / 100)
            call_short = current_price * (1 + trading_bot.config.ic_call_spread_offset_percent / 100)
            put_short = round(put_short)
            call_short = round(call_short)
            spread_width = trading_bot.config.ic_spread_width
            expiration = date.today() + timedelta(days=trading_bot.config.ic_expiration_days)
            
            # Fetch premiums for put spread
            put_short_premium = get_option_premium(trading_bot, symbol, put_short, expiration, 'put')
            put_long_premium = get_option_premium(trading_bot, symbol, put_short - spread_width, expiration, 'put')
            put_spread_credit = put_short_premium - put_long_premium
            
            # Fetch premiums for call spread
            call_short_premium = get_option_premium(trading_bot, symbol, call_short, expiration, 'call')
            call_long_premium = get_option_premium(trading_bot, symbol, call_short + spread_width, expiration, 'call')
            call_spread_credit = call_short_premium - call_long_premium
            
            planned_orders.append({
                'type': 'spread',
                'action': 'SELL',
                'spread_type': 'credit',
                'short_strike': put_short,
                'long_strike': put_short - spread_width,
                'expiration': expiration.strftime('%m/%d/%Y'),
                'quantity': trading_bot.config.ic_num_contracts,
                'option_type': 'PUT SPREAD',
                'estimated_price': put_spread_credit
            })
            planned_orders.append({
                'type': 'spread',
                'action': 'SELL',
                'spread_type': 'credit',
                'short_strike': call_short,
                'long_strike': call_short + spread_width,
                'expiration': expiration.strftime('%m/%d/%Y'),
                'quantity': trading_bot.config.ic_num_contracts,
                'option_type': 'CALL SPREAD',
                'estimated_price': call_spread_credit
            })
            
        elif strategy == "ss":
            # Short Strangle
            put_strike = current_price * (1 - trading_bot.config.ss_put_offset_percent / 100)
            call_strike = current_price * (1 + trading_bot.config.ss_call_offset_percent / 100)
            put_strike = round(put_strike)
            call_strike = round(call_strike)
            expiration = date.today() + timedelta(days=trading_bot.config.ss_expiration_days)
            
            # Fetch premiums
            put_premium = get_option_premium(trading_bot, symbol, put_strike, expiration, 'put')
            call_premium = get_option_premium(trading_bot, symbol, call_strike, expiration, 'call')
            
            planned_orders.append({
                'type': 'option',
                'action': 'SELL',
                'strike': put_strike,
                'expiration': expiration.strftime('%m/%d/%Y'),
                'quantity': trading_bot.config.ss_num_contracts,
                'option_type': 'PUT',
                'estimated_price': put_premium
            })
            planned_orders.append({
                'type': 'option',
                'action': 'SELL',
                'strike': call_strike,
                'expiration': expiration.strftime('%m/%d/%Y'),
                'quantity': trading_bot.config.ss_num_contracts,
                'option_type': 'CALL',
                'estimated_price': call_premium
            })
            
        elif strategy == "jl":
            # Jade Lizard
            put_strike = current_price * 0.95  # ~5% OTM put
            call_short = current_price * 1.05  # ~5% OTM short call
            call_long = current_price * 1.10   # ~10% OTM long call
            put_strike = round(put_strike)
            call_short = round(call_short)
            call_long = round(call_long)
            expiration = date.today() + timedelta(days=30)
            
            # Fetch premiums
            put_premium = get_option_premium(trading_bot, symbol, put_strike, expiration, 'put')
            call_short_premium = get_option_premium(trading_bot, symbol, call_short, expiration, 'call')
            call_long_premium = get_option_premium(trading_bot, symbol, call_long, expiration, 'call')
            
            planned_orders.append({
                'type': 'option',
                'action': 'SELL',
                'strike': put_strike,
                'expiration': expiration.strftime('%m/%d/%Y'),
                'quantity': 1,
                'option_type': 'PUT',
                'estimated_price': put_premium
            })
            planned_orders.append({
                'type': 'option',
                'action': 'SELL',
                'strike': call_short,
                'expiration': expiration.strftime('%m/%d/%Y'),
                'quantity': 1,
                'option_type': 'CALL',
                'estimated_price': call_short_premium
            })
            planned_orders.append({
                'type': 'option',
                'action': 'BUY',
                'strike': call_long,
                'expiration': expiration.strftime('%m/%d/%Y'),
                'quantity': 1,
                'option_type': 'CALL',
                'estimated_price': call_long_premium
            })
            
        elif strategy == "bl":
            # Big Lizard
            atm_strike = round(current_price)
            call_long = current_price * 1.10  # ~10% OTM long call
            call_long = round(call_long)
            expiration = date.today() + timedelta(days=30)
            
            # Fetch premiums
            put_premium = get_option_premium(trading_bot, symbol, atm_strike, expiration, 'put')
            call_short_premium = get_option_premium(trading_bot, symbol, atm_strike, expiration, 'call')
            call_long_premium = get_option_premium(trading_bot, symbol, call_long, expiration, 'call')
            
            planned_orders.append({
                'type': 'option',
                'action': 'SELL',
                'strike': atm_strike,
                'expiration': expiration.strftime('%m/%d/%Y'),
                'quantity': 1,
                'option_type': 'PUT',
                'estimated_price': put_premium
            })
            planned_orders.append({
                'type': 'option',
                'action': 'SELL',
                'strike': atm_strike,
                'expiration': expiration.strftime('%m/%d/%Y'),
                'quantity': 1,
                'option_type': 'CALL',
                'estimated_price': call_short_premium
            })
            planned_orders.append({
                'type': 'option',
                'action': 'BUY',
                'strike': call_long,
                'expiration': expiration.strftime('%m/%d/%Y'),
                'quantity': 1,
                'option_type': 'CALL',
                'estimated_price': call_long_premium
            })
            
        elif strategy == "dc":
            # Double Calendar
            put_strike = current_price * (1 - trading_bot.config.dc_put_offset_percent / 100)
            call_strike = current_price * (1 + trading_bot.config.dc_call_offset_percent / 100)
            put_strike = round(put_strike)
            call_strike = round(call_strike)
            short_exp = date.today() + timedelta(days=trading_bot.config.dc_short_days)
            long_exp = date.today() + timedelta(days=trading_bot.config.dc_long_days)
            
            # Fetch premiums for put calendar
            put_short_premium = get_option_premium(trading_bot, symbol, put_strike, short_exp, 'put')
            put_long_premium = get_option_premium(trading_bot, symbol, put_strike, long_exp, 'put')
            
            # Fetch premiums for call calendar
            call_short_premium = get_option_premium(trading_bot, symbol, call_strike, short_exp, 'call')
            call_long_premium = get_option_premium(trading_bot, symbol, call_strike, long_exp, 'call')
            
            # Put calendar
            planned_orders.append({
                'type': 'option',
                'action': 'SELL',
                'strike': put_strike,
                'expiration': short_exp.strftime('%m/%d/%Y'),
                'quantity': 1,
                'option_type': 'PUT (short exp)',
                'estimated_price': put_short_premium
            })
            planned_orders.append({
                'type': 'option',
                'action': 'BUY',
                'strike': put_strike,
                'expiration': long_exp.strftime('%m/%d/%Y'),
                'quantity': 1,
                'option_type': 'PUT (long exp)',
                'estimated_price': put_long_premium
            })
            # Call calendar
            planned_orders.append({
                'type': 'option',
                'action': 'SELL',
                'strike': call_strike,
                'expiration': short_exp.strftime('%m/%d/%Y'),
                'quantity': 1,
                'option_type': 'CALL (short exp)',
                'estimated_price': call_short_premium
            })
            planned_orders.append({
                'type': 'option',
                'action': 'BUY',
                'strike': call_strike,
                'expiration': long_exp.strftime('%m/%d/%Y'),
                'quantity': 1,
                'option_type': 'CALL (long exp)',
                'estimated_price': call_long_premium
            })
            
        elif strategy == "bf":
            # Butterfly
            atm_strike = round(current_price)
            wing_width = trading_bot.config.bf_wing_width
            expiration = date.today() + timedelta(days=trading_bot.config.bf_expiration_days)
            
            # Fetch premiums
            lower_wing_premium = get_option_premium(trading_bot, symbol, atm_strike - wing_width, expiration, 'call')
            atm_premium = get_option_premium(trading_bot, symbol, atm_strike, expiration, 'call')
            upper_wing_premium = get_option_premium(trading_bot, symbol, atm_strike + wing_width, expiration, 'call')
            
            planned_orders.append({
                'type': 'option',
                'action': 'BUY',
                'strike': atm_strike - wing_width,
                'expiration': expiration.strftime('%m/%d/%Y'),
                'quantity': 1,
                'option_type': 'CALL',
                'estimated_price': lower_wing_premium
            })
            planned_orders.append({
                'type': 'option',
                'action': 'SELL',
                'strike': atm_strike,
                'expiration': expiration.strftime('%m/%d/%Y'),
                'quantity': 2,
                'option_type': 'CALL',
                'estimated_price': atm_premium
            })
            planned_orders.append({
                'type': 'option',
                'action': 'BUY',
                'strike': atm_strike + wing_width,
                'expiration': expiration.strftime('%m/%d/%Y'),
                'quantity': 1,
                'option_type': 'CALL',
                'estimated_price': upper_wing_premium
            })
            
        elif strategy == "bwb":
            # Broken Wing Butterfly
            atm_strike = round(current_price)
            lower_wing = 5
            upper_wing = 10
            expiration = date.today() + timedelta(days=30)
            
            # Fetch premiums
            lower_wing_premium = get_option_premium(trading_bot, symbol, atm_strike - lower_wing, expiration, 'call')
            atm_premium = get_option_premium(trading_bot, symbol, atm_strike, expiration, 'call')
            upper_wing_premium = get_option_premium(trading_bot, symbol, atm_strike + upper_wing, expiration, 'call')
            
            planned_orders.append({
                'type': 'option',
                'action': 'BUY',
                'strike': atm_strike - lower_wing,
                'expiration': expiration.strftime('%m/%d/%Y'),
                'quantity': 1,
                'option_type': 'CALL',
                'estimated_price': lower_wing_premium
            })
            planned_orders.append({
                'type': 'option',
                'action': 'SELL',
                'strike': atm_strike,
                'expiration': expiration.strftime('%m/%d/%Y'),
                'quantity': 2,
                'option_type': 'CALL',
                'estimated_price': atm_premium
            })
            planned_orders.append({
                'type': 'option',
                'action': 'BUY',
                'strike': atm_strike + upper_wing,
                'expiration': expiration.strftime('%m/%d/%Y'),
                'quantity': 1,
                'option_type': 'CALL',
                'estimated_price': upper_wing_premium
            })
            
        elif strategy == "metf":
            # METF Strategy - 0DTE Credit Spreads
            # This uses the SAME logic as TradingBot.process_metf_symbol()
            from src.strategy.metf_strategy import (
                METFStrategy,
                SYMBOL_CONFIGS,
                TrendDirection,
                SpreadType,
            )

            # Get symbol config
            symbol_upper = symbol.upper()
            if symbol_upper not in SYMBOL_CONFIGS:
                print(f"  ❌ Symbol {symbol_upper} not supported for METF.")
                print(f"     Supported symbols: {list(SYMBOL_CONFIGS.keys())}")
                return None
                
            config = SYMBOL_CONFIGS[symbol_upper]
            spread_width = config.default_spread_width
            otm_offset = config.otm_offset

            # Check if today is a trading day using TradingCalendar
            # Create calendar using credentials from trading_bot.config
            calendar = TradingCalendar(
                api_token=trading_bot.config.tradier_credentials.api_token,
                is_sandbox="sandbox" in trading_bot.config.tradier_credentials.base_url.lower()
            )
            
            is_trading_day = calendar.is_trading_day(date.today())
            
            # Check if market is currently open (during trading hours)
            is_market_open = False
            try:
                is_market_open = trading_bot.broker_client.is_market_open()
            except Exception:
                pass

            # METF requires real-time EMA data from 1-minute charts
            # Since we don't have historical bar data API, we need user input for direction
            if not is_trading_day:
                print()
                print(
                    "  ⚠️  METF Strategy requires real-time EMA data from 1-minute charts."
                )
                print("  📊 Today is NOT a trading day - EMA signals unavailable.")
                print()
                print("  Please select the spread direction manually:")
                print("    [P] PUT Credit Spread  - Use if you expect price to stay UP")
                print(
                    "    [C] CALL Credit Spread - Use if you expect price to stay DOWN"
                )
                print()

                while True:
                    direction = input("  Enter direction (P/C): ").strip().upper()
                    if direction in ["P", "PUT"]:
                        trend = TrendDirection.BULLISH
                        spread_type_name = "PUT"
                        signal_reason = "Manual selection: PUT Credit Spread (non-trading day)"
                        # Set dummy EMA values for display
                        ema_20 = current_price * 1.001
                        ema_40 = current_price * 0.999
                        break
                    elif direction in ["C", "CALL"]:
                        trend = TrendDirection.BEARISH
                        spread_type_name = "CALL"
                        signal_reason = "Manual selection: CALL Credit Spread (non-trading day)"
                        # Set dummy EMA values for display
                        ema_20 = current_price * 0.999
                        ema_40 = current_price * 1.001
                        break
                    else:
                        print("  ❌ Please enter 'P' for PUT or 'C' for CALL")
            else:
                # Today is a trading day - calculate EMAs automatically
                print()
                print("  📊 METF Strategy - Calculating EMA signals...")
                print()
                
                # Calculate 20 EMA and 40 EMA from 1-minute bars
                ema_20 = calculate_ema_from_bars(
                    symbol_upper,
                    trading_bot.config.tradier_credentials.api_token,
                    "sandbox" in trading_bot.config.tradier_credentials.base_url.lower(),
                    period=20,
                    lookback_minutes=100
                )
                
                ema_40 = calculate_ema_from_bars(
                    symbol_upper,
                    trading_bot.config.tradier_credentials.api_token,
                    "sandbox" in trading_bot.config.tradier_credentials.base_url.lower(),
                    period=40,
                    lookback_minutes=150
                )
                
                # Check if EMA calculation was successful
                if ema_20 is None or ema_40 is None:
                    print("  ⚠️  Unable to calculate EMAs automatically.")
                    print("  📊 Falling back to manual selection...")
                    print()
                    print("  Please select the spread direction manually:")
                    print("    [P] PUT Credit Spread  - Use if you expect price to stay UP")
                    print("    [C] CALL Credit Spread - Use if you expect price to stay DOWN")
                    print()

                    while True:
                        direction = input("  Enter direction (P/C): ").strip().upper()
                        if direction in ["P", "PUT"]:
                            trend = TrendDirection.BULLISH
                            spread_type_name = "PUT"
                            signal_reason = "Manual selection: PUT Credit Spread (EMA calculation failed)"
                            # Set dummy EMA values for display
                            ema_20 = current_price * 1.001
                            ema_40 = current_price * 0.999
                            break
                        elif direction in ["C", "CALL"]:
                            trend = TrendDirection.BEARISH
                            spread_type_name = "CALL"
                            signal_reason = "Manual selection: CALL Credit Spread (EMA calculation failed)"
                            # Set dummy EMA values for display
                            ema_20 = current_price * 0.999
                            ema_40 = current_price * 1.001
                            break
                        else:
                            print("  ❌ Please enter 'P' for PUT or 'C' for CALL")
                else:
                    # EMAs calculated successfully - determine trend automatically
                    print(f"  ✅ 20 EMA: ${ema_20:.2f}")
                    print(f"  ✅ 40 EMA: ${ema_40:.2f}")
                    print()
                    
                    if ema_20 > ema_40:
                        trend = TrendDirection.BULLISH
                        spread_type_name = "PUT"
                        signal_reason = f"Automatic: 20 EMA (${ema_20:.2f}) > 40 EMA (${ema_40:.2f}) → BULLISH → PUT Credit Spread"
                        print(f"  📈 BULLISH Signal: 20 EMA > 40 EMA")
                        print(f"  ✅ Executing PUT Credit Spread")
                    else:
                        trend = TrendDirection.BEARISH
                        spread_type_name = "CALL"
                        signal_reason = f"Automatic: 20 EMA (${ema_20:.2f}) < 40 EMA (${ema_40:.2f}) → BEARISH → CALL Credit Spread"
                        print(f"  📉 BEARISH Signal: 20 EMA < 40 EMA")
                        print(f"  ✅ Executing CALL Credit Spread")
                    print()

            # Calculate initial strikes based on trend (same as trading bot)
            if trend == TrendDirection.BULLISH:
                short_strike = round(current_price - otm_offset)
                long_strike = short_strike - spread_width
            else:
                short_strike = round(current_price + otm_offset)
                long_strike = short_strike + spread_width

            # Use TradingCalendar to get 0DTE expiration (already created above)
            
            expiration = calendar.get_0dte_expiration()
            
            # Display user-friendly message when expiration is adjusted
            if expiration != date.today():
                print(f"  ⚠️  Running on non-trading day ({date.today().strftime('%A')})")
                print(f"  📅 Using next trading day: {expiration.strftime('%A, %m/%d/%Y')}")
                print()

            # Get available strikes from option chain (same as trading bot)
            try:
                option_chain = trading_bot.broker_client.get_option_chain(symbol_upper, expiration)
                available_strikes = sorted(list(set([c.strike for c in option_chain])))

                if available_strikes:
                    # Find nearest available strikes (same logic as trading bot)
                    short_strike = min(available_strikes, key=lambda x: abs(x - short_strike))
                    
                    if trend == TrendDirection.BULLISH:
                        # For PUT spread, long strike should be below short
                        valid_longs = [s for s in available_strikes if s < short_strike]
                        if valid_longs:
                            target_long = short_strike - spread_width
                            long_strike = min(valid_longs, key=lambda x: abs(x - target_long))
                    else:
                        # For CALL spread, long strike should be above short
                        valid_longs = [s for s in available_strikes if s > short_strike]
                        if valid_longs:
                            target_long = short_strike + spread_width
                            long_strike = min(valid_longs, key=lambda x: abs(x - target_long))
                            
                    print(f"  ✅ Adjusted to available strikes: Short ${short_strike}, Long ${long_strike}")
            except Exception as e:
                print(f"  ⚠️  Could not get option chain, using calculated strikes: {str(e)}")

            # Format expiration display with note if adjusted
            expiration_display = expiration.strftime("%m/%d/%Y") + " (0DTE)"
            if expiration != date.today():
                expiration_display += f" - Adjusted from {date.today().strftime('%m/%d/%Y')}"

            planned_orders.append(
                {
                    "type": "spread",
                    "action": "SELL",
                    "spread_type": "credit",
                    "short_strike": short_strike,
                    "long_strike": long_strike,
                    "expiration": expiration_display,
                    "quantity": 1,
                    "option_type": spread_type_name,
                    "estimated_price": (config.min_credit + config.max_credit) / 2,
                    # METF-specific fields for justification
                    "metf_signal": {
                        "trend": trend.value,
                        "ema_20": ema_20,
                        "ema_40": ema_40,
                        "reason": signal_reason,
                        "spread_type": f"{spread_type_name} Credit Spread",
                        "market_open": is_market_open,
                    },
                    # Store trend for execution
                    "metf_trend": trend,
                }
            )
            
        elif strategy == "ritmo":
            # Roll In The Money Options
            # Find all options expiring today that are in the money
            try:
                detailed_positions = trading_bot.broker_client.get_detailed_positions(symbol)
                
                # Filter for options expiring today
                today = date.today()
                expiring_today = []
                
                for pos in detailed_positions:
                    if not hasattr(pos, 'expiration') or not hasattr(pos, 'option_type'):
                        continue
                    
                    # Check if expiring today
                    if pos.expiration == today and pos.quantity != 0:
                        expiring_today.append(pos)
                
                if not expiring_today:
                    print(f"  ℹ️  No options expiring today for {symbol}")
                    return None
                
                print(f"  ✅ Found {len(expiring_today)} option position(s) expiring today")
                
                # Check which ones are in the money
                itm_positions = []
                for pos in expiring_today:
                    strike = pos.strike if hasattr(pos, 'strike') else 0
                    option_type = pos.option_type.lower() if hasattr(pos, 'option_type') else ''
                    
                    is_itm = False
                    if 'call' in option_type:
                        # Call is ITM if current price > strike
                        is_itm = current_price > strike
                    elif 'put' in option_type:
                        # Put is ITM if current price < strike
                        is_itm = current_price < strike
                    
                    if is_itm:
                        itm_positions.append(pos)
                        print(f"  💰 ITM: {option_type.upper()} ${strike:.2f} (current: ${current_price:.2f})")
                
                if not itm_positions:
                    print(f"  ℹ️  No in-the-money options expiring today")
                    print(f"     All expiring options are out of the money")
                    return None
                
                print(f"  ✅ Found {len(itm_positions)} ITM option(s) to roll")
                
                # For each ITM position, create roll orders
                for pos in itm_positions:
                    strike = pos.strike
                    quantity = abs(pos.quantity)
                    option_type = pos.option_type.lower() if hasattr(pos, 'option_type') else ''
                    position_type = pos.position_type if hasattr(pos, 'position_type') else 'unknown'
                    
                    # Determine if this is a long or short position
                    is_long = 'long' in position_type.lower() or pos.quantity > 0
                    
                    # Get next available expiration
                    try:
                        available_expirations = trading_bot.broker_client.get_option_expirations(symbol)
                        future_expirations = [exp for exp in available_expirations if exp > today]
                        
                        if not future_expirations:
                            print(f"  ⚠️  No future expirations available for {symbol}")
                            continue
                        
                        # Use the next available expiration
                        next_expiration = future_expirations[0]
                        
                        # Check if it's within max days limit (if configured)
                        days_to_next = (next_expiration - today).days
                        max_days = getattr(trading_bot.config, 'ritmo_max_days_to_next_expiration', 30)
                        
                        if days_to_next > max_days:
                            print(f"  ⚠️  Next expiration is {days_to_next} days out (max: {max_days})")
                            continue
                        
                        # Get premium for the new option
                        opt_type = 'call' if 'call' in option_type else 'put'
                        new_premium = get_option_premium(trading_bot, symbol, strike, next_expiration, opt_type)
                        
                        # Get premium for closing current position (should be near intrinsic value)
                        current_premium = get_option_premium(trading_bot, symbol, strike, today, opt_type)
                        
                        # Debug output
                        print(f"  📊 Premium Analysis for {opt_type.upper()} ${strike:.2f}:")
                        print(f"     Current (expiring today): ${current_premium:.2f}")
                        print(f"     New ({next_expiration.strftime('%m/%d/%Y')}): ${new_premium:.2f}")
                        
                        # Calculate net credit/debit for the roll
                        if is_long:
                            # Rolling a long position: sell current, buy new
                            # Net debit = new premium - current premium
                            net_credit = current_premium - new_premium
                            roll_action = "SELL TO CLOSE → BUY TO OPEN"
                            print(f"     Net for LONG roll: ${net_credit:.2f} (sell current ${current_premium:.2f}, buy new ${new_premium:.2f})")
                            
                            # For long positions, we allow small debits (user is extending protection)
                            # Check if debit is reasonable (not more than max allowed debit)
                            max_debit = getattr(trading_bot.config, 'ritmo_max_debit_to_roll', 0.50)
                            
                            if net_credit < 0 and abs(net_credit) > max_debit:
                                print(f"  ⚠️  Roll debit ${abs(net_credit):.2f} exceeds maximum ${max_debit:.2f}")
                                print(f"     Skipping {opt_type.upper()} ${strike:.2f}")
                                print(f"  💡 Tip: Increase 'ritmo_max_debit_to_roll' in config to allow this roll")
                                continue
                            
                            # For long positions, we proceed even with small debits
                            print(f"  ✅ Roll approved for LONG position (debit ${abs(net_credit):.2f} is acceptable)")
                            
                        else:
                            # Rolling a short position: buy to close current, sell new
                            # Net credit = new premium - current premium
                            net_credit = new_premium - current_premium
                            roll_action = "BUY TO CLOSE → SELL TO OPEN"
                            print(f"     Net for SHORT roll: ${net_credit:.2f} (buy to close ${current_premium:.2f}, sell new ${new_premium:.2f})")
                            
                            # For short positions, we require a minimum credit
                            min_credit = getattr(trading_bot.config, 'ritmo_min_credit_to_roll', 0.01)
                            
                            if net_credit < min_credit:
                                print(f"  ⚠️  Roll credit ${net_credit:.2f} below minimum ${min_credit:.2f}")
                                print(f"     Skipping {opt_type.upper()} ${strike:.2f}")
                                print(f"  💡 Tip: Lower 'min_credit_to_roll' in config to allow this roll")
                                continue
                        
                        # Add roll order
                        planned_orders.append({
                            'type': 'roll',
                            'action': roll_action,
                            'strike': strike,
                            'current_expiration': today.strftime('%m/%d/%Y'),
                            'new_expiration': next_expiration.strftime('%m/%d/%Y'),
                            'quantity': quantity,
                            'option_type': opt_type.upper(),
                            'estimated_price': net_credit,
                            'is_long': is_long,
                            'position_type': position_type
                        })
                        
                    except Exception as roll_error:
                        print(f"  ⚠️  Could not create roll for {option_type.upper()} ${strike:.2f}: {str(roll_error)}")
                        continue
                
                if not planned_orders:
                    print(f"  ℹ️  No valid rolls found")
                    print(f"     Check minimum credit requirements or expiration limits")
                    return None
                    
            except Exception as e:
                print(f"  ❌ Error checking positions: {str(e)}")
                import traceback
                traceback.print_exc()
                return None
        
        elif strategy == "lcc":
            # Laddered Covered Call
            call_strike = current_price * (1 + trading_bot.config.laddered_call_offset_percent / 100)
            call_strike = round(call_strike)
            
            # Calculate dynamic number of legs based on shares owned
            # 500+ shares = 5 legs, 400-499 = 4 legs, 300-399 = 3 legs, 200-299 = 2 legs, 100-199 = 1 leg
            if shares_owned is None:
                # Fallback to config if shares not provided
                dynamic_num_legs = trading_bot.config.laddered_num_legs
            elif shares_owned >= 500:
                dynamic_num_legs = 5
            elif shares_owned >= 400:
                dynamic_num_legs = 4
            elif shares_owned >= 300:
                dynamic_num_legs = 3
            elif shares_owned >= 200:
                dynamic_num_legs = 2
            else:
                dynamic_num_legs = 1
            
            # Get available expirations from broker
            try:
                available_expirations = trading_bot.broker_client.get_option_expirations(symbol)
                # Filter to future dates only
                today = date.today()
                future_expirations = [exp for exp in available_expirations if exp > today]
                
                if not future_expirations:
                    print(f"  ⚠️  No future expirations available for {symbol}")
                    return None
                
                # Take the next N available expirations based on shares owned
                num_legs = min(dynamic_num_legs, len(future_expirations))
                selected_expirations = future_expirations[:num_legs]
                
                for i, exp_date in enumerate(selected_expirations):
                    # Fetch premium for this leg
                    call_premium = get_option_premium(trading_bot, symbol, call_strike, exp_date, 'call')
                    
                    planned_orders.append({
                        'type': 'option',
                        'action': 'SELL',
                        'strike': call_strike,
                        'expiration': exp_date.strftime('%m/%d/%Y'),
                        'quantity': 1,
                        'option_type': f'CALL (Exp {i+1})',
                        'estimated_price': call_premium
                    })
            except Exception as e:
                print(f"  ⚠️  Could not get option expirations: {str(e)}")
                # Fallback to weekly calculation
                for i in range(dynamic_num_legs):
                    exp_date = date.today() + timedelta(weeks=i+1)
                    call_premium = get_option_premium(trading_bot, symbol, call_strike, exp_date, 'call')
                    
                    planned_orders.append({
                        'type': 'option',
                        'action': 'SELL',
                        'strike': call_strike,
                        'expiration': exp_date.strftime('%m/%d/%Y'),
                        'quantity': 1,
                        'option_type': f'CALL (Week {i+1})',
                        'estimated_price': call_premium
                    })
        
        else:
            # Generic fallback
            planned_orders.append({
                'type': 'option',
                'action': 'UNKNOWN',
                'strike': current_price,
                'expiration': 'TBD',
                'quantity': 1,
                'option_type': 'OPTION',
                'estimated_price': 0
            })
            
    except Exception as e:
        print(f"  ⚠️  Warning: Could not calculate all order details: {str(e)}")
        # Return partial orders if any were calculated
        if not planned_orders:
            return None
    
    return planned_orders


def calculate_collateral_requirement(order, symbol, current_price=None):
    """Calculate collateral requirement for an option order.
    
    Collateral requirements by strategy:
    - Covered Call: $0 (shares are collateral)
    - Cash-Secured Put: Strike × 100 × Quantity
    - Credit Spreads (PCS, IC): Spread width × 100 × Quantity
    - Debit Spreads: $0 (just premium paid)
    - Long Options (MP, LS): $0 (just premium paid)
    - Short Straddle/Strangle: Strike × 100 × Quantity (for puts) + margin for calls
    - Iron Butterfly: Max(put spread width, call spread width) × 100 × Quantity
    - Butterflies/Calendars: $0 or minimal (net debit strategies)
    
    Args:
        order: Order dictionary with order details
        symbol: Stock symbol
        current_price: Current stock price (optional, for margin calculations)
        
    Returns:
        float: Collateral requirement in dollars
    """
    order_type = order.get('type', 'Unknown')
    action = order.get('action', '').upper()
    quantity = order.get('quantity', 1)
    
    # No collateral needed for buying options (just the premium paid)
    if action in ['BUY', 'BTO', 'BUY TO OPEN']:
        return 0.0
    
    # Single leg options
    if order_type == 'option' and action in ['SELL', 'STO', 'SELL TO OPEN']:
        option_type = order.get('option_type', '').upper()
        strike = order.get('strike', 0)
        
        if 'CALL' in option_type:
            # Covered call - assumes you own the shares (no additional collateral)
            # For naked calls (not covered), would need: 20% of stock value + premium - OTM amount
            # But we assume covered calls in this system
            return 0.0
        elif 'PUT' in option_type:
            # Cash-secured put - need cash to buy shares at strike
            return strike * 100 * quantity
    
    # Spreads
    if order_type == 'spread':
        spread_type = order.get('spread_type', '').lower()
        short_strike = order.get('short_strike', 0)
        long_strike = order.get('long_strike', 0)
        
        if spread_type == 'credit':
            # Credit spread collateral = width of spread
            # This applies to: PCS, Call Credit Spreads, Iron Condor legs
            width = abs(short_strike - long_strike)
            return width * 100 * quantity
        else:
            # Debit spread - no collateral, just the debit paid
            # This applies to: Debit spreads, Calendars, Diagonals
            return 0.0
    
    # Stock purchase (for Married Put strategy)
    if order_type == 'stock':
        stock_quantity = order.get('quantity', 0)
        price = order.get('price', current_price or 0)
        return price * stock_quantity
    
    # Default: no collateral calculated
    return 0.0


def verify_planned_orders(symbol, strategy, planned_orders, broker_client=None):
    """Display planned orders and get final verification before execution.
    
    This provides an additional layer of protection by showing exactly what
    orders will be placed before submitting them to the broker.
    
    Args:
        symbol: Stock symbol
        strategy: Strategy code (e.g., 'pcs', 'cc', 'metf')
        planned_orders: List of order details to display
        broker_client: Optional broker client to check for pending orders
        
    Returns:
        bool: True if user confirms, False otherwise
    """
    strategy_names = {
        "pc": "Protected Collar",
        "pcs": "Put Credit Spread",
        "lps": "Laddered Put Spread",
        "tpd": "Tiered Put Diagonal",
        "cs": "Collar Strategy",
        "cc": "Covered Call",
        "ws": "Wheel Strategy",
        "lcc": "Laddered Covered Call",
        "tcc": "Tiered Covered Calls",
        "dc": "Double Calendar",
        "bf": "Butterfly",
        "bwb": "Broken Wing Butterfly",
        "mp": "Married Put",
        "ls": "Long Straddle",
        "ib": "Iron Butterfly",
        "ss": "Short Strangle",
        "ic": "Iron Condor",
        "jl": "Jade Lizard",
        "bl": "Big Lizard",
        "metf": "METF Strategy",
        "ritmo": "Roll In The Money Options"
    }
    strategy_name = strategy_names.get(strategy, strategy.upper())
    
    print()
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 20 + "⚠️  FINAL ORDER VERIFICATION" + " " * 20 + "║")
    print("╚" + "═" * 68 + "╝")
    print()
    
    print(f"  � Strate:gy: {strategy_name}")
    print(f"  📈 Symbol:   {symbol}")
    print()
    
    # Check for pending orders
    if broker_client:
        try:
            pending_orders = broker_client.get_pending_orders(symbol)
            if pending_orders:
                print("  ┌" + "─" * 66 + "┐")
                print("  │" + " " * 18 + "⚠️  PENDING ORDERS DETECTED" + " " * 20 + "│")
                print("  ├" + "─" * 66 + "┤")
                print(f"  │ Found {len(pending_orders)} pending order(s) for {symbol}" + " " * (66 - len(f" Found {len(pending_orders)} pending order(s) for {symbol}")) + "│")
                print("  │" + " " * 66 + "│")
                
                for i, order in enumerate(pending_orders[:5], 1):  # Show max 5
                    order_symbol = order.get("symbol", "")
                    side = order.get("side", "")
                    qty = order.get("quantity", 0)
                    status = order.get("status", "")
                    order_class = order.get("class", "")
                    
                    order_desc = f"{i}. {side.upper()} {qty}x {order_symbol} ({order_class}) - {status}"
                    padding = 66 - len(f" {order_desc}")
                    print(f"  │ {order_desc}" + " " * max(0, padding) + "│")
                
                if len(pending_orders) > 5:
                    print(f"  │ ... and {len(pending_orders) - 5} more" + " " * (66 - len(f" ... and {len(pending_orders) - 5} more")) + "│")
                
                print("  │" + " " * 66 + "│")
                print("  │ ⚠️  WARNING: Placing new orders may conflict with pending orders  │")
                print("  │    Consider waiting for pending orders to fill or cancel them    │")
                print("  └" + "─" * 66 + "┘")
                print()
        except Exception as e:
            # Silently continue if we can't check pending orders
            pass
    
    # Display METF signal justification if present
    if strategy == "metf" and planned_orders:
        metf_signal = planned_orders[0].get('metf_signal')
        if metf_signal:
            print("  ┌" + "─" * 66 + "┐")
            print("  │" + " " * 18 + "📊 METF SIGNAL ANALYSIS" + " " * 25 + "│")
            print("  ├" + "─" * 66 + "┤")
            
            trend = metf_signal.get('trend', 'unknown').upper()
            ema_20 = metf_signal.get('ema_20', 0)
            ema_40 = metf_signal.get('ema_40', 0)
            reason = metf_signal.get('reason', '')
            spread_type = metf_signal.get('spread_type', '')
            
            # Trend indicator
            if trend == "BULLISH":
                trend_icon = "📈"
                trend_color = "BULLISH"
            elif trend == "BEARISH":
                trend_icon = "📉"
                trend_color = "BEARISH"
            else:
                trend_icon = "➡️"
                trend_color = "NEUTRAL"
            
            # Check if this was a manual selection
            market_open = metf_signal.get('market_open', False)
            is_manual = 'Manual selection' in reason or 'User confirmed' in reason
            
            print(f"  │ {trend_icon} Trend Direction: {trend_color:<47} │")
            print(f"  │                                                                    │")
            
            if is_manual and not market_open:
                print(f"  │ ⚠️  Market Status: CLOSED                                          │")
                print(f"  │    EMA data unavailable - direction manually selected            │")
                print(f"  │                                                                    │")
            elif is_manual:
                print(f"  │ ℹ️  Direction: User-confirmed based on external chart analysis    │")
                print(f"  │                                                                    │")
            
            print(f"  │ 📐 EMA Analysis (1-minute chart):                                  │")
            print(f"  │    • 20 EMA: ${ema_20:<54.2f} │")
            print(f"  │    • 40 EMA: ${ema_40:<54.2f} │")
            print(f"  │                                                                    │")
            
            # Signal explanation
            if trend == "BULLISH":
                print(f"  │ ✅ Signal: 20 EMA > 40 EMA                                         │")
                print(f"  │    → Market showing BULLISH momentum                              │")
                print(f"  │    → Selling PUT Credit Spread (profit if price stays up)        │")
            elif trend == "BEARISH":
                print(f"  │ ✅ Signal: 20 EMA < 40 EMA                                         │")
                print(f"  │    → Market showing BEARISH momentum                              │")
                print(f"  │    → Selling CALL Credit Spread (profit if price stays down)     │")
            else:
                print(f"  │ ⚠️  Signal: EMAs are close (neutral/unclear trend)                │")
                print(f"  │    → Consider waiting for clearer signal                         │")
            
            print(f"  │                                                                    │")
            print(f"  │ 🎯 Selected Strategy: {spread_type:<43} │")
            print("  └" + "─" * 66 + "┘")
            print()
    
    if not planned_orders:
        print("  ❌ No orders to display")
        return False
    
    print("  ┌" + "─" * 66 + "┐")
    print("  │" + " " * 20 + "ORDERS TO BE SUBMITTED" + " " * 24 + "│")
    print("  ├" + "─" * 66 + "┤")
    
    total_debit = 0.0
    total_credit = 0.0
    
    for i, order in enumerate(planned_orders, 1):
        order_type = order.get('type', 'Unknown')
        
        # Handle error orders
        if order_type == 'error':
            print(f"  │ ❌ {order.get('message', 'Unknown error')}" + " " * max(0, 66 - len(f" ❌ {order.get('message', 'Unknown error')}")) + "│")
            if i < len(planned_orders):
                print("  │" + " " * 66 + "│")
            continue
        
        action = order.get('action', 'Unknown')
        strike = order.get('strike', 0)
        expiration = order.get('expiration', 'N/A')
        quantity = order.get('quantity', 1)
        option_type = order.get('option_type', '')
        est_price = order.get('estimated_price', 0)
        
        # Format the order line
        if order_type == 'roll':
            # Special handling for roll orders
            current_exp = order.get('current_expiration', 'N/A')
            new_exp = order.get('new_expiration', 'N/A')
            is_long = order.get('is_long', False)
            
            print(f"  │ {i}. ROLL {quantity}x {symbol} ${strike:.2f} {option_type.upper()}" + " " * max(0, 35 - len(f"{i}. ROLL {quantity}x {symbol} ${strike:.2f} {option_type.upper()}")) + "│")
            print(f"  │    From: {current_exp} → To: {new_exp}" + " " * (66 - len(f"    From: {current_exp} → To: {new_exp}")) + "│")
            print(f"  │    Position: {'LONG' if is_long else 'SHORT'}" + " " * (66 - len(f"    Position: {'LONG' if is_long else 'SHORT'}")) + "│")
            if est_price > 0:
                total_credit += est_price * quantity * 100
                print(f"  │    Est. Net Credit: ${est_price:.2f} (${est_price * quantity * 100:.2f} total)" + " " * (66 - len(f"    Est. Net Credit: ${est_price:.2f} (${est_price * quantity * 100:.2f} total)")) + "│")
            elif est_price < 0:
                total_debit += abs(est_price) * quantity * 100
                print(f"  │    Est. Net Debit: ${abs(est_price):.2f} (${abs(est_price) * quantity * 100:.2f} total)" + " " * (66 - len(f"    Est. Net Debit: ${abs(est_price):.2f} (${abs(est_price) * quantity * 100:.2f} total)")) + "│")
            else:
                print(f"  │    Est. Net: $0.00 (even roll)" + " " * (66 - len(f"    Est. Net: $0.00 (even roll)")) + "│")
        elif order_type == 'spread':
            short_strike = order.get('short_strike', 0)
            long_strike = order.get('long_strike', 0)
            spread_type = order.get('spread_type', 'credit')
            
            print(f"  │ {i}. {action} {quantity}x {symbol} {option_type} {spread_type.upper()} SPREAD" + " " * max(0, 35 - len(f"{i}. {action} {quantity}x {symbol} {option_type} {spread_type.upper()} SPREAD")) + "│")
            print(f"  │    Short: ${short_strike:<8.2f} | Long: ${long_strike:<8.2f} | Exp: {expiration:<10}" + " " * 5 + "│")
            if est_price > 0:
                if spread_type == 'credit':
                    total_credit += est_price * quantity * 100
                    print(f"  │    Est. Credit: ${est_price:.2f} per spread (${est_price * quantity * 100:.2f} total)" + " " * (66 - len(f"    Est. Credit: ${est_price:.2f} per spread (${est_price * quantity * 100:.2f} total)")) + "│")
                else:
                    total_debit += est_price * quantity * 100
                    print(f"  │    Est. Debit: ${est_price:.2f} per spread (${est_price * quantity * 100:.2f} total)" + " " * (66 - len(f"    Est. Debit: ${est_price:.2f} per spread (${est_price * quantity * 100:.2f} total)")) + "│")
        else:
            # Single leg option
            action_str = f"{action} {quantity}x {symbol} ${strike:.2f} {option_type.upper()}"
            padding = 66 - len(f" {i}. {action_str}")
            print(f"  │ {i}. {action_str}" + " " * max(0, padding) + "│")
            print(f"  │    Expiration: {expiration}" + " " * (66 - len(f"    Expiration: {expiration}")) + "│")
            if est_price > 0:
                if action.upper() in ['SELL', 'STO', 'SELL TO OPEN']:
                    total_credit += est_price * quantity * 100
                    print(f"  │    Est. Credit: ${est_price:.2f} (${est_price * quantity * 100:.2f} total)" + " " * (66 - len(f"    Est. Credit: ${est_price:.2f} (${est_price * quantity * 100:.2f} total)")) + "│")
                else:
                    total_debit += est_price * quantity * 100
                    print(f"  │    Est. Debit: ${est_price:.2f} (${est_price * quantity * 100:.2f} total)" + " " * (66 - len(f"    Est. Debit: ${est_price:.2f} (${est_price * quantity * 100:.2f} total)")) + "│")
        
        if i < len(planned_orders):
            print("  │" + " " * 66 + "│")
    
    print("  ├" + "─" * 66 + "┤")
    
    # Calculate total collateral requirement
    total_collateral = sum(calculate_collateral_requirement(order, symbol) for order in planned_orders)
    
    # Summary
    if total_credit > 0 or total_debit > 0:
        net = total_credit - total_debit
        if net >= 0:
            print(f"  │ 💰 NET ESTIMATED CREDIT: ${net:,.2f}" + " " * (66 - len(f" 💰 NET ESTIMATED CREDIT: ${net:,.2f}")) + "│")
        else:
            print(f"  │ 💸 NET ESTIMATED DEBIT: ${abs(net):,.2f}" + " " * (66 - len(f" 💸 NET ESTIMATED DEBIT: ${abs(net):,.2f}")) + "│")
    
    # Show collateral requirement
    if total_collateral > 0:
        print(f"  │ 🔒 COLLATERAL REQUIRED: ${total_collateral:,.2f}" + " " * (66 - len(f" 🔒 COLLATERAL REQUIRED: ${total_collateral:,.2f}")) + "│")
    
    # Get and show buying power impact if broker client available
    if broker_client:
        try:
            account_info = broker_client.get_account()
            if hasattr(account_info, 'buying_power'):
                current_bp = float(account_info.buying_power)
                # Buying power impact = collateral required - credit received + debit paid
                bp_impact = total_collateral - total_credit + total_debit
                remaining_bp = current_bp - bp_impact
                
                print(f"  │ 💵 CURRENT BUYING POWER: ${current_bp:,.2f}" + " " * (66 - len(f" 💵 CURRENT BUYING POWER: ${current_bp:,.2f}")) + "│")
                print(f"  │ 📉 BUYING POWER IMPACT: -${bp_impact:,.2f}" + " " * (66 - len(f" 📉 BUYING POWER IMPACT: -${bp_impact:,.2f}")) + "│")
                print(f"  │ 💳 REMAINING BUYING POWER: ${remaining_bp:,.2f}" + " " * (66 - len(f" 💳 REMAINING BUYING POWER: ${remaining_bp:,.2f}")) + "│")
                
                # Warning if insufficient buying power
                if remaining_bp < 0:
                    print(f"  │ ⚠️  WARNING: INSUFFICIENT BUYING POWER!" + " " * 31 + "│")
        except Exception:
            # Silently fail if we can't get account info
            pass
    
    print("  └" + "─" * 66 + "┘")
    
    print()
    print("  ⚠️  WARNING: These orders will be submitted to your broker!")
    print("  ⚠️  Real money will be at risk. Review carefully.")
    print()
    
    while True:
        try:
            confirm = input("  🔐 Type 'CONFIRM' to execute or 'cancel' to abort: ").strip()
            
            if confirm.upper() == "CONFIRM":
                print()
                print("  ✅ Orders confirmed for execution!")
                return True
            elif confirm.lower() in ["cancel", "no", "n", "abort"]:
                print()
                print("  🚫 Order execution cancelled")
                return False
            else:
                print("  ❌ Please type 'CONFIRM' to proceed or 'cancel' to abort")
                
        except KeyboardInterrupt:
            print("\n\n  👋 Goodbye!")
            sys.exit(0)


def execute_trade(symbol, strategy, shares_owned=None, shares_for_legs=None):
    """Execute the selected trade.
    
    Args:
        symbol: Stock symbol
        strategy: Strategy code
        shares_owned: Number of shares owned (for display and contract calculations)
        shares_for_legs: Number of shares to use for determining number of legs (for LCC)
    """
    suppress_output()
    
    # If shares_for_legs not provided, use shares_owned
    if shares_for_legs is None:
        shares_for_legs = shares_owned

    try:
        print()
        print("═" * 60)
        print("🚀 PREPARING TRADE...")
        print("═" * 60)
        print()

        from src.bot.trading_bot import TradingBot

        # Load original config
        with open("config/config.json", "r") as f:
            config_data = json.load(f)

        # Override for single stock and strategy
        # For double calendar and butterfly, always use QQQ
        if strategy in ["dc", "bf"]:
            config_data["symbols"] = ["QQQ"]
            actual_symbol = "QQQ"
        else:
            config_data["symbols"] = [symbol]
            actual_symbol = symbol
        config_data["strategy"] = strategy
        config_data["run_immediately"] = True

        # Write to temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump(config_data, tmp)
            tmp_path = tmp.name

        try:
            # Initialize trading bot with temp config (dry run first to calculate orders)
            trading_bot = TradingBot(config_path=tmp_path, dry_run=True)

            print("  ⏳ Initializing...")
            if not trading_bot.initialize():
                print("  ❌ Failed to initialize trading bot")
                return False

            # Calculate planned orders for verification
            print("  ⏳ Calculating order parameters...")
            planned_orders = calculate_planned_orders(trading_bot, actual_symbol, strategy, shares_for_legs)
            
            if not planned_orders:
                print("  ❌ Could not calculate order parameters")
                print("  💡 This might be due to:")
                print("     • Market hours (options data unavailable)")
                print("     • Insufficient option liquidity")
                print("     • Network connectivity issues")
                return False
            
            # Show verification prompt with planned orders
            if not verify_planned_orders(actual_symbol, strategy, planned_orders, trading_bot.broker_client):
                return False
            
            # Now execute for real
            print()
            print("═" * 60)
            print("🚀 EXECUTING TRADE...")
            print("═" * 60)
            print()
            
            # Re-initialize without dry run
            trading_bot_real = TradingBot(config_path=tmp_path, dry_run=False)
            if not trading_bot_real.initialize():
                print("  ❌ Failed to initialize trading bot for execution")
                return False

            print("  ⏳ Submitting order...")
            # Execute the trade
            summary = trading_bot_real.execute_trading_cycle()

            # Display results
            print()
            print("═" * 60)
            print("📊 RESULTS")
            print("═" * 60)
            print()

            if summary.successful_trades > 0:
                strategy_names = {
                    "pc": "Protected Collar",
                    "pcs": "Put Credit Spread",
                    "lps": "Laddered Put Spread",
                    "tpd": "Tiered Put Diagonal",
                    "cs": "Collar",
                    "cc": "Covered Call",
                    "ws": "Wheel",
                    "lcc": "Laddered CC",
                    "dc": "Double Calendar",
                    "bf": "Butterfly",
                    "mp": "Married Put",
                    "ls": "Long Straddle",
                    "ib": "Iron Butterfly",
                    "ss": "Short Strangle",
                    "ic": "Iron Condor",
                    "jl": "Jade Lizard",
                    "bl": "Big Lizard",
                    "bwb": "Broken Wing Butterfly",
                    "metf": "METF Strategy"
                }
                strategy_name = strategy_names.get(strategy, strategy)
                print(f"  ✅ SUCCESS!")
                print(f"     Stock:    {actual_symbol}")
                print(f"     Strategy: {strategy_name}")
                print()
                print("  📱 Check your broker dashboard for order details")
            else:
                print(f"  ❌ FAILED: Trade failed for {actual_symbol}")
                print()
                print("  📋 Check logs/trading_bot.log for details")

                # Show error if available
                if summary.trade_results:
                    for result in summary.trade_results:
                        if result.error_message:
                            print(f"  ⚠️  Error: {result.error_message[:50]}...")

            return summary.successful_trades > 0

        finally:
            # Clean up temp file
            os.unlink(tmp_path)

    except Exception as e:
        print(f"\n  ❌ ERROR: {str(e)}")
        print("  📋 Check logs/trading_bot.log for details")
        return False


def main():
    """Main interactive function."""
    try:
        suppress_output()
        display_banner()
        
        # First, select trading mode (paper or live)
        trading_mode = select_trading_mode()
        set_trading_mode_env(trading_mode)
        print()

        print("  ⏳ Connecting to broker...")
        config, broker_client = initialize_broker()
        
        # Show trading mode indicator
        if trading_mode == "live":
            print("  🔴 Connected to LIVE trading account!")
        else:
            print("  ✅ Connected to paper trading account")
        print()

        if not config.symbols:
            print("  ❌ No symbols configured in config.json")
            sys.exit(1)

        # Show current positions
        print("─" * 60)
        print("📊 YOUR CURRENT POSITIONS:")
        print()
        positions = broker_client.get_positions()
        display_positions(positions)
        print()

        # Interactive selection
        print("─" * 60)
        selected_symbol = select_stock(config.symbols)

        # Initialize position service for accurate share counting (includes long calls)
        from src.positions.position_service import PositionService
        position_service = PositionService(broker_client, logger=None)

        # Check shares owned for collar eligibility (includes long call equivalents)
        shares_owned = get_shares_owned(broker_client, selected_symbol, position_service)

        selected_strategy = select_strategy(selected_symbol, shares_owned, broker_client)

        # For LCC and TCC strategies, get actual stock shares (not including long call equivalents)
        if selected_strategy in ["lcc", "tcc"]:
            # Get actual stock position only
            position = broker_client.get_position(selected_symbol)
            actual_stock_shares = position.quantity if position else 0
            # For LCC: use total shares (including long calls) for leg calculation
            # For TCC: use actual stock shares only
            if selected_strategy == "lcc":
                confirmation_shares = actual_stock_shares
                shares_for_legs = shares_owned  # Use total including long calls for leg count
            else:
                confirmation_shares = actual_stock_shares
                shares_for_legs = actual_stock_shares
        else:
            # For other strategies, use total shares including long call equivalents
            confirmation_shares = shares_owned
            shares_for_legs = shares_owned

        # Handle tiered covered calls with special workflow
        if selected_strategy == "tcc":
            # Confirm execution
            if not confirm_execution(selected_symbol, selected_strategy, confirmation_shares, shares_for_legs):
                print("\n  🚫 Trade cancelled")
                sys.exit(0)
            
            # Execute tiered covered calls workflow
            success = execute_tiered_covered_calls(selected_symbol, broker_client, config)
        else:
            # Confirm execution
            if not confirm_execution(selected_symbol, selected_strategy, confirmation_shares, shares_for_legs):
                print("\n  🚫 Trade cancelled")
                sys.exit(0)

            # Execute the trade (pass shares_for_legs for dynamic leg calculation)
            success = execute_trade(selected_symbol, selected_strategy, confirmation_shares, shares_for_legs)

        print()
        if success:
            print("  🎉 Trade execution completed!")
        else:
            print("  ⚠️  Trade execution failed")
        print()

    except KeyboardInterrupt:
        print("\n\n  👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n  ❌ Unexpected error: {str(e)}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
