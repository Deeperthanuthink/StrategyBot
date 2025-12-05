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

# Suppress noisy output BEFORE importing anything else
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
warnings.filterwarnings("ignore")
logging.getLogger("lumibot").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)
logging.getLogger("apscheduler").setLevel(logging.CRITICAL)

from dotenv import load_dotenv

load_dotenv()


def suppress_output():
    """Suppress noisy library output."""
    # Suppress various loggers
    for logger_name in ["lumibot", "urllib3", "apscheduler", "requests", "tradier"]:
        logging.getLogger(logger_name).setLevel(logging.CRITICAL)


def clear_screen():
    """Clear terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")


def display_banner():
    """Display the interactive bot banner."""
    print()
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 15 + "🤖 OPTIONS TRADING BOT" + " " * 21 + "║")
    print("╚" + "═" * 58 + "╝")
    print()


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
    print(f"  Suggested: {', '.join(suggested_symbols)}")
    print("  (or type any valid stock symbol)")
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


def select_strategy(symbol, shares_owned):
    """Let user select a trading strategy by typing abbreviation."""
    print()
    print("─" * 60)
    print("📊 STRATEGIES:")
    print()
    print("  pcs - Put Credit Spread")
    print("        • Sell put spread for credit")
    print("        • Profit if stock stays above short strike")
    print()

    # Check if stock-based strategies are available
    has_100_shares = shares_owned >= 100

    if has_100_shares:
        print("  cs  - Collar Strategy")
        print("        • Protective put + covered call")
        print(f"        • ✅ You own {shares_owned} shares of {symbol}")
        print()
        print("  cc  - Covered Call")
        print("        • Sell call 5% above price, ~10 day expiry")
        print(f"        • ✅ You own {shares_owned} shares of {symbol}")
    else:
        print("  cs  - Collar Strategy (UNAVAILABLE)")
        print("        • Requires owning 100+ shares")
        if shares_owned > 0:
            print(f"        • ❌ You only own {shares_owned} shares of {symbol}")
        else:
            print(f"        • ❌ You don't own any shares of {symbol}")
        print()
        print("  cc  - Covered Call (UNAVAILABLE)")
        print("        • Requires owning 100+ shares")

    print()
    print("  ws  - Wheel Strategy")
    print("        • Auto-cycles between selling puts & calls")
    if has_100_shares:
        print(f"        • 🔄 Will sell COVERED CALL (you own {shares_owned} shares)")
    else:
        print(f"        • 🔄 Will sell CASH-SECURED PUT (you own {shares_owned} shares)")

    print()
    if has_100_shares:
        total_contracts = int((shares_owned * 0.667) // 100)
        contracts_per_leg = max(1, total_contracts // 5)
        print("  lcc - Laddered Covered Call")
        print("        • Sells calls on 2/3 of holdings")
        print("        • Spread across 5 weekly expirations (20% each)")
        print(f"        • ✅ ~{total_contracts} contracts across 5 legs")
    else:
        print("  lcc - Laddered Covered Call (UNAVAILABLE)")
        print("        • Requires owning 100+ shares")

    print()
    print("  dc  - Double Calendar (QQQ)")
    print("        • Sell 2-day options, buy 4-day options")
    print("        • Put calendar + Call calendar")
    print("        • Profits from time decay")

    print()
    print("  bf  - Butterfly (QQQ)")
    print("        • Buy 1 lower, Sell 2 middle, Buy 1 upper")
    print("        • Max profit at middle strike")
    print("        • Low cost, defined risk")

    print()
    print("  mp  - Married Put")
    print("        • Buy 100 shares + Buy 1 protective put")
    print("        • Unlimited upside, limited downside")
    print("        • Good for bullish outlook with protection")

    print()
    print("  ls  - Long Straddle")
    print("        • Buy 1 ATM call + Buy 1 ATM put")
    print("        • Profits from big moves in either direction")
    print("        • Best when expecting high volatility")

    print()
    print("  ib  - Iron Butterfly")
    print("        • Sell ATM call + Sell ATM put + Buy wings")
    print("        • Profits when stock stays near strike")
    print("        • Defined risk, collects premium")

    print()
    print("  ss  - Short Strangle ⚠️")
    print("        • Sell OTM call + Sell OTM put")
    print("        • Profits when stock stays in range")
    print("        • ⚠️ UNDEFINED RISK - use with caution!")

    print()

    while True:
        try:
            choice = (
                input("  Enter strategy (pcs/cs/cc/ws/lcc/dc/bf/mp/ls/ib/ss): ").strip().lower()
            )

            if choice == "pcs":
                print("  ✅ Selected: Put Credit Spread")
                return "pcs"
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
            else:
                print(
                    "  ❌ Enter 'pcs', 'cs', 'cc', 'ws', 'lcc', 'dc', 'bf', 'mp', 'ls', 'ib', or 'ss'"
                )

        except KeyboardInterrupt:
            print("\n\n  👋 Goodbye!")
            sys.exit(0)


def confirm_execution(symbol, strategy, shares_owned):
    """Confirm the trade execution with user."""
    has_100_shares = shares_owned >= 100

    strategy_names = {
        "pcs": "Put Credit Spread",
        "cs": "Collar Strategy",
        "cc": "Covered Call",
        "ws": f"Wheel Strategy ({'CC' if has_100_shares else 'CSP'} phase)",
        "lcc": "Laddered Covered Call",
        "dc": "Double Calendar (QQQ)",
        "bf": "Butterfly (QQQ)",
        "mp": "Married Put",
        "ls": "Long Straddle",
        "ib": "Iron Butterfly",
        "ss": "Short Strangle ⚠️",
    }
    strategy_name = strategy_names.get(strategy, strategy)

    print()
    print("─" * 60)
    print("🎯 TRADE SUMMARY:")
    print()
    print(f"  Stock:      {symbol}")
    print(f"  Strategy:   {strategy_name}")
    if strategy in ["cs", "cc"]:
        contracts = shares_owned // 100
        print(f"  Shares:     {shares_owned} ({contracts} contract(s))")
    if strategy == "cc":
        print(f"  Strike:     ~5% above current price")
        print(f"  Expiry:     ~10 days out")
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
        total_contracts = int((shares_owned * 0.667) // 100)
        print(f"  Coverage:   2/3 of holdings ({total_contracts} contracts)")
        print(f"  Legs:       5 weekly expirations (20% each)")
        print(f"  Strike:     ~5% above current price")
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


def get_shares_owned(broker_client, symbol):
    """Check how many shares of a symbol the user owns."""
    try:
        position = broker_client.get_position(symbol)
        if position:
            return position.quantity
        return 0
    except Exception:
        return 0


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


def execute_trade(symbol, strategy):
    """Execute the selected trade."""
    suppress_output()

    try:
        print()
        print("═" * 60)
        print("🚀 EXECUTING TRADE...")
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
        else:
            config_data["symbols"] = [symbol]
        config_data["strategy"] = strategy
        config_data["run_immediately"] = True

        # Write to temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump(config_data, tmp)
            tmp_path = tmp.name

        try:
            # Initialize trading bot with temp config
            trading_bot = TradingBot(config_path=tmp_path, dry_run=False)

            print("  ⏳ Initializing...")
            if not trading_bot.initialize():
                print("  ❌ Failed to initialize trading bot")
                return False

            print("  ⏳ Submitting order...")
            # Execute the trade
            summary = trading_bot.execute_trading_cycle()

            # Display results
            print()
            print("═" * 60)
            print("📊 RESULTS")
            print("═" * 60)
            print()

            if summary.successful_trades > 0:
                strategy_names = {
                    "pcs": "Put Credit Spread",
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
                }
                strategy_name = strategy_names.get(strategy, strategy)
                print(f"  ✅ SUCCESS!")
                print(f"     Stock:    {symbol}")
                print(f"     Strategy: {strategy_name}")
                print()
                print("  📱 Check your broker dashboard for order details")
            else:
                print(f"  ❌ FAILED: Trade failed for {symbol}")
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

        print("  ⏳ Connecting to broker...")
        config, broker_client = initialize_broker()
        print("  ✅ Connected!")
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

        # Check shares owned for collar eligibility
        shares_owned = get_shares_owned(broker_client, selected_symbol)

        selected_strategy = select_strategy(selected_symbol, shares_owned)

        # Confirm execution
        if not confirm_execution(selected_symbol, selected_strategy, shares_owned):
            print("\n  🚫 Trade cancelled")
            sys.exit(0)

        # Execute the trade
        success = execute_trade(selected_symbol, selected_strategy)

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
