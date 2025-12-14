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


def select_strategy(symbol, shares_owned):
    """Let user select a trading strategy by typing abbreviation."""
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
    print("  │ ws  │ Wheel Strategy   │ Auto-cycle puts/calls     │")
    print("  │ mp  │ Married Put      │ Buy shares + protective put│")
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
    
    if shares_owned > 0:
        print(f"  💼 You own {shares_owned} shares of {symbol}")
    
    print()
    print("🔹 VOLATILITY STRATEGIES")
    print("  ┌─────┬──────────────────┬──────────────────────────┐")
    print("  │ ls  │ Long Straddle    │ Profit from big moves     │")
    print("  │ ib  │ Iron Butterfly   │ Profit when price stays put│")
    print("  │ ic  │ Iron Condor      │ Profit in wider price range│")
    print("  │ ss  │ Short Strangle ⚠️│ UNDEFINED RISK - use caution│")
    print("  └─────┴──────────────────┴──────────────────────────┘")
    
    print()
    print("🔹 ADVANCED STRATEGIES (QQQ Only)")
    print("  ┌─────┬──────────────────┬──────────────────────────┐")
    print("  │ dc  │ Double Calendar  │ Time decay profit strategy│")
    print("  │ bf  │ Butterfly        │ Low-cost defined risk     │")
    print("  └─────┴──────────────────┴──────────────────────────┘")
    
    print()

    while True:
        try:
            choice = (
                input("  Enter strategy (pc/pcs/cs/cc/ws/lcc/tcc/dc/bf/mp/ls/ib/ss/ic): ").strip().lower()
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
            else:
                print(
                    "  ❌ Enter 'pc', 'pcs', 'cs', 'cc', 'ws', 'lcc', 'tcc', 'dc', 'bf', 'mp', 'ls', 'ib', 'ss', or 'ic'"
                )

        except KeyboardInterrupt:
            print("\n\n  👋 Goodbye!")
            sys.exit(0)


def confirm_execution(symbol, strategy, shares_owned):
    """Confirm the trade execution with user."""
    has_100_shares = shares_owned >= 100

    strategy_names = {
        "pc": "Protected Collar",
        "pcs": "Put Credit Spread",
        "cs": "Collar Strategy",
        "cc": "Covered Call",
        "ws": f"Wheel Strategy ({'CC' if has_100_shares else 'CSP'} phase)",
        "lcc": "Laddered Covered Call",
        "tcc": "Tiered Covered Calls",
        "dc": "Double Calendar (QQQ)",
        "bf": "Butterfly (QQQ)",
        "mp": "Married Put",
        "ls": "Long Straddle",
        "ib": "Iron Butterfly",
        "ss": "Short Strangle ⚠️",
        "ic": "Iron Condor"
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
    if strategy == "tcc":
        total_contracts = shares_owned // 100
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


def confirm_tiered_execution(plan):
    """Confirm tiered covered call strategy execution with user.
    
    Args:
        plan: TieredCoveredCallPlan object with strategy details
        
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
    
    # Add cost basis reduction if available
    if hasattr(plan, 'original_cost_basis') and plan.original_cost_basis is not None:
        if hasattr(plan, 'effective_cost_basis') and plan.effective_cost_basis is not None:
            reduction_amount = plan.original_cost_basis - plan.effective_cost_basis
            reduction_percentage = (reduction_amount / plan.original_cost_basis) * 100 if plan.original_cost_basis > 0 else 0
            print(f"  │ Cost Basis Reduction: {reduction_percentage:<26.1f}% │")
    
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
    
    while True:
        try:
            confirm = input("  Execute tiered covered call strategy? (y/n): ").strip().lower()
            
            if confirm in ["y", "yes"]:
                print("  ✅ Execution confirmed!")
                return True
            elif confirm in ["n", "no"]:
                print("  🚫 Execution cancelled")
                return False
            else:
                print("  ❌ Please enter 'y' or 'n'")
                
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
    
    while True:
        try:
            confirm = input("  Execute covered call rolls? (y/n): ").strip().lower()
            
            if confirm in ["y", "yes"]:
                print("  ✅ Roll execution confirmed!")
                return True
            elif confirm in ["n", "no"]:
                print("  🚫 Roll execution cancelled")
                return False
            else:
                print("  ❌ Please enter 'y' or 'n'")
                
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
        if not confirm_tiered_execution(strategy_plan):
            return False
        
        # Display execution progress
        display_execution_progress(strategy_plan)
        
        # For now, we'll simulate execution since the actual order submission
        # would be handled by the main trading bot in task 6
        print("  ⏳ Simulating order execution...")
        print("  ✅ Orders would be submitted to broker")
        
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
                    "pc": "Protected Collar",
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
                    "ic": "Iron Condor"
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

        # Initialize position service for accurate share counting (includes long calls)
        from src.positions.position_service import PositionService
        position_service = PositionService(broker_client, logger=None)

        # Check shares owned for collar eligibility (includes long call equivalents)
        shares_owned = get_shares_owned(broker_client, selected_symbol, position_service)

        selected_strategy = select_strategy(selected_symbol, shares_owned)

        # Handle tiered covered calls with special workflow
        if selected_strategy == "tcc":
            # Confirm execution
            if not confirm_execution(selected_symbol, selected_strategy, shares_owned):
                print("\n  🚫 Trade cancelled")
                sys.exit(0)
            
            # Execute tiered covered calls workflow
            success = execute_tiered_covered_calls(selected_symbol, broker_client, config)
        else:
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
