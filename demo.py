#!/usr/bin/env python3
"""
Demo Mode for Options Trading Bot

This script demonstrates what the bot would do during a trading cycle,
even when the market is closed. It simulates the entire workflow with
realistic data without making actual API calls or submitting orders.
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import List, Dict
import random

from src.config.config_manager import ConfigManager
from src.config.models import Config
from src.logging.bot_logger import BotLogger


class DemoSimulator:
    """Simulates trading bot execution with demo data."""

    def __init__(self, config: Config, logger: BotLogger):
        """Initialize the demo simulator.

        Args:
            config: Configuration object
            logger: Logger instance
        """
        self.config = config
        self.logger = logger

        # Demo stock prices (realistic values)
        self.demo_prices = {
            "AAPL": 185.50,
            "MSFT": 420.75,
            "GOOGL": 142.30,
            "NVDA": 875.25,
            "AMZN": 178.90,
            "TSLA": 245.60,
            "META": 485.20,
            "SPY": 485.75,
            "QQQ": 425.30,
            "AMD": 165.40,
        }

    def run_demo(self):
        """Run a complete demo of the trading cycle."""
        self.logger.log_info("=" * 70)
        self.logger.log_info("DEMO MODE - Simulating Trading Cycle")
        self.logger.log_info("=" * 70)
        self.logger.log_info("")

        # Step 1: Show configuration
        self._show_configuration()

        # Step 2: Simulate market check
        self._simulate_market_check()

        # Step 3: Process each symbol
        self.logger.log_info("")
        self.logger.log_info("=" * 70)
        self.logger.log_info("PROCESSING SYMBOLS")
        self.logger.log_info("=" * 70)

        results = []
        for symbol in self.config.symbols:
            result = self._process_symbol_demo(symbol)
            results.append(result)

        # Step 4: Show execution summary
        self._show_summary(results)

    def _show_configuration(self):
        """Display current configuration."""
        self.logger.log_info("CONFIGURATION:")
        self.logger.log_info(f"  Symbols: {', '.join(self.config.symbols)}")
        self.logger.log_info(f"  Strike Offset: {self.config.strike_offset_percent}% below market")
        self.logger.log_info(f"  Spread Width: ${self.config.spread_width}")
        self.logger.log_info(f"  Contract Quantity: {self.config.contract_quantity}")
        self.logger.log_info(f"  Execution Day: {self.config.execution_day}")
        self.logger.log_info(
            f"  Execution Time: Market open + {self.config.execution_time_offset_minutes} minutes"
        )
        self.logger.log_info(f"  Expiration: {self.config.expiration_offset_weeks} week(s) out")
        self.logger.log_info(f"  API Endpoint: {self.config.alpaca_credentials.base_url}")
        self.logger.log_info("")

    def _simulate_market_check(self):
        """Simulate market status check."""
        self.logger.log_info("MARKET STATUS CHECK:")

        now = datetime.now()
        is_weekend = now.weekday() >= 5
        is_market_hours = 9 <= now.hour < 16

        if is_weekend:
            self.logger.log_warning("  Market is CLOSED (Weekend)")
            next_open = self._get_next_market_open()
            self.logger.log_info(
                f"  Next market open: {next_open.strftime('%A, %B %d at 9:30 AM ET')}"
            )
        elif not is_market_hours:
            self.logger.log_warning("  Market is CLOSED (Outside trading hours)")
            self.logger.log_info("  Market hours: 9:30 AM - 4:00 PM ET, Monday-Friday")
        else:
            self.logger.log_info("  Market is OPEN")

        self.logger.log_info(
            "  [DEMO MODE: Proceeding with simulation regardless of market status]"
        )

    def _get_next_market_open(self) -> datetime:
        """Calculate next market open time."""
        now = datetime.now()
        days_ahead = 0

        # Find next weekday
        while True:
            days_ahead += 1
            next_day = now + timedelta(days=days_ahead)
            if next_day.weekday() < 5:  # Monday = 0, Friday = 4
                return next_day.replace(hour=9, minute=30, second=0, microsecond=0)

    def _process_symbol_demo(self, symbol: str) -> Dict:
        """Simulate processing a single symbol.

        Args:
            symbol: Stock symbol to process

        Returns:
            Dictionary with simulation results
        """
        self.logger.log_info("")
        self.logger.log_info(f"{'─' * 70}")
        self.logger.log_info(f"Processing: {symbol}")
        self.logger.log_info(f"{'─' * 70}")

        # Get or generate demo price
        if symbol in self.demo_prices:
            current_price = self.demo_prices[symbol]
        else:
            # Generate random price for unknown symbols
            current_price = random.uniform(50, 500)
            self.logger.log_warning(f"  Using generated price for {symbol} (not in demo database)")

        self.logger.log_info(f"  Current Price: ${current_price:.2f}")

        # Calculate strikes
        short_strike = current_price * (1 - self.config.strike_offset_percent / 100)
        long_strike = short_strike - self.config.spread_width

        # Round to nearest 0.50 (typical option strike increments)
        short_strike = round(short_strike * 2) / 2
        long_strike = round(long_strike * 2) / 2

        self.logger.log_info(f"  Calculated Short Strike: ${short_strike:.2f}")
        self.logger.log_info(f"  Calculated Long Strike: ${long_strike:.2f}")
        self.logger.log_info(f"  Spread Width: ${short_strike - long_strike:.2f}")

        # Calculate expiration
        today = date.today()
        target_date = today + timedelta(weeks=self.config.expiration_offset_weeks)
        days_until_friday = (4 - target_date.weekday()) % 7
        if target_date.weekday() == 4:
            expiration = target_date
        else:
            expiration = target_date + timedelta(days=days_until_friday)

        self.logger.log_info(f"  Expiration Date: {expiration.strftime('%Y-%m-%d (%A)')}")
        self.logger.log_info(f"  Days to Expiration: {(expiration - today).days}")

        # Simulate option chain lookup
        self.logger.log_info("")
        self.logger.log_info("  Simulating option chain lookup...")

        # Generate realistic available strikes around our calculated strikes
        available_strikes = self._generate_available_strikes(current_price)
        self.logger.log_info(f"  Found {len(available_strikes)} available strikes")

        # Find nearest available strikes
        actual_short_strike = min(available_strikes, key=lambda x: abs(x - short_strike))
        actual_long_strike = min(available_strikes, key=lambda x: abs(x - long_strike))

        if actual_short_strike != short_strike or actual_long_strike != long_strike:
            self.logger.log_info("  Adjusted to nearest available strikes:")
            self.logger.log_info(
                f"    Short Strike: ${short_strike:.2f} → ${actual_short_strike:.2f}"
            )
            self.logger.log_info(f"    Long Strike: ${long_strike:.2f} → ${actual_long_strike:.2f}")
            short_strike = actual_short_strike
            long_strike = actual_long_strike
        else:
            self.logger.log_info("  ✓ Calculated strikes are available in option chain")

        # Calculate estimated premium (credit received)
        spread_width = short_strike - long_strike
        # Typical credit is 20-40% of spread width for 5% OTM spreads
        estimated_credit = spread_width * random.uniform(0.20, 0.40)
        estimated_credit = round(estimated_credit * 100) / 100  # Round to cents

        self.logger.log_info("")
        self.logger.log_info("  TRADE DETAILS:")
        self.logger.log_info(f"    Strategy: Put Credit Spread")
        self.logger.log_info(f"    Sell Put: ${short_strike:.2f} (higher strike)")
        self.logger.log_info(f"    Buy Put: ${long_strike:.2f} (lower strike)")
        self.logger.log_info(f"    Spread Width: ${spread_width:.2f}")
        self.logger.log_info(f"    Contracts: {self.config.contract_quantity}")
        self.logger.log_info(f"    Estimated Credit: ${estimated_credit:.2f} per spread")
        self.logger.log_info(
            f"    Total Credit: ${estimated_credit * self.config.contract_quantity:.2f}"
        )
        self.logger.log_info(
            f"    Max Risk: ${spread_width * 100 * self.config.contract_quantity:.2f}"
        )
        self.logger.log_info(
            f"    Max Profit: ${estimated_credit * 100 * self.config.contract_quantity:.2f}"
        )

        # Calculate probability of profit (rough estimate)
        otm_percent = ((current_price - short_strike) / current_price) * 100
        prob_profit = min(95, 50 + otm_percent * 5)  # Rough approximation
        self.logger.log_info(f"    Short Strike OTM: {otm_percent:.1f}%")
        self.logger.log_info(f"    Est. Probability of Profit: ~{prob_profit:.0f}%")

        # Simulate order submission
        self.logger.log_info("")
        self.logger.log_info("  Simulating order submission...")

        # Randomly simulate success/failure (95% success rate in demo)
        success = random.random() < 0.95

        if success:
            order_id = f"DEMO-{symbol}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            self.logger.log_info(f"  ✓ Order submitted successfully")
            self.logger.log_info(f"    Order ID: {order_id}")
            self.logger.log_info(f"    Status: FILLED (simulated)")
            self.logger.log_info(f"    Fill Price: ${estimated_credit:.2f}")

            return {
                "symbol": symbol,
                "success": True,
                "current_price": current_price,
                "short_strike": short_strike,
                "long_strike": long_strike,
                "expiration": expiration,
                "credit": estimated_credit,
                "contracts": self.config.contract_quantity,
                "order_id": order_id,
            }
        else:
            error_messages = [
                "Insufficient buying power",
                "Strike price not available",
                "Market volatility too high",
                "Spread too narrow",
            ]
            error = random.choice(error_messages)
            self.logger.log_error(f"  ✗ Order failed: {error}")

            return {
                "symbol": symbol,
                "success": False,
                "current_price": current_price,
                "short_strike": short_strike,
                "long_strike": long_strike,
                "expiration": expiration,
                "error": error,
            }

    def _generate_available_strikes(self, current_price: float) -> List[float]:
        """Generate realistic available option strikes.

        Args:
            current_price: Current stock price

        Returns:
            List of available strike prices
        """
        strikes = []

        # Determine strike increment based on price
        if current_price < 50:
            increment = 1.0
        elif current_price < 100:
            increment = 2.5
        elif current_price < 200:
            increment = 5.0
        else:
            increment = 10.0

        # Generate strikes from 50% below to 20% above current price
        start_strike = current_price * 0.5
        end_strike = current_price * 1.2

        strike = round(start_strike / increment) * increment
        while strike <= end_strike:
            strikes.append(strike)
            strike += increment

        return strikes

    def _show_summary(self, results: List[Dict]):
        """Display execution summary.

        Args:
            results: List of trade results
        """
        self.logger.log_info("")
        self.logger.log_info("=" * 70)
        self.logger.log_info("EXECUTION SUMMARY")
        self.logger.log_info("=" * 70)

        successful = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]

        self.logger.log_info(f"  Total Symbols: {len(results)}")
        self.logger.log_info(f"  Successful: {len(successful)}")
        self.logger.log_info(f"  Failed: {len(failed)}")
        self.logger.log_info(f"  Success Rate: {len(successful)/len(results)*100:.1f}%")

        if successful:
            total_credit = sum(r["credit"] * r["contracts"] * 100 for r in successful)
            self.logger.log_info(f"  Total Credit Received: ${total_credit:.2f}")

        self.logger.log_info("")
        self.logger.log_info("DETAILED RESULTS:")

        for result in results:
            symbol = result["symbol"]
            if result["success"]:
                credit = result["credit"] * result["contracts"] * 100
                self.logger.log_info(
                    f"  ✓ {symbol}: ${result['short_strike']:.2f}/${result['long_strike']:.2f} "
                    f"spread for ${credit:.2f} credit"
                )
            else:
                self.logger.log_error(f"  ✗ {symbol}: Failed - {result['error']}")

        self.logger.log_info("")
        self.logger.log_info("=" * 70)
        self.logger.log_info("DEMO COMPLETE")
        self.logger.log_info("=" * 70)
        self.logger.log_info("")
        self.logger.log_info("NOTE: This was a simulation. No actual orders were placed.")
        self.logger.log_info(
            "To run with real data when market is open, use: python main.py --once"
        )
        self.logger.log_info("To test without placing orders, use: python main.py --dry-run --once")


def main():
    """Main entry point for demo mode."""
    parser = argparse.ArgumentParser(
        description="Demo Mode - Simulate trading bot execution with demo data"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config/config.json",
        help="Path to configuration file (default: config/config.json)",
    )

    args = parser.parse_args()

    # Verify config file exists
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Configuration file not found at {args.config}")
        print(f"Please create a configuration file or use --config to specify a different path")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("OPTIONS TRADING BOT - DEMO MODE")
    print("=" * 70)
    print("\nThis demo simulates what the bot would do during a trading cycle.")
    print("It uses simulated data and does not make actual API calls or place orders.")
    print()

    try:
        # Load configuration
        config_manager = ConfigManager()

        # Set dummy environment variables for demo mode if not set
        import os

        if not os.environ.get("ALPACA_API_KEY"):
            os.environ["ALPACA_API_KEY"] = "DEMO_KEY_NOT_REAL"
        if not os.environ.get("ALPACA_API_SECRET"):
            os.environ["ALPACA_API_SECRET"] = "DEMO_SECRET_NOT_REAL"

        config = config_manager.load_config(str(config_path))

        # Initialize logger
        logger = BotLogger(config.logging_config)
        logger.log_info("Demo mode initialized with simulated credentials")

        # Run demo
        simulator = DemoSimulator(config, logger)
        simulator.run_demo()

    except FileNotFoundError as e:
        print(f"ERROR: Configuration file not found: {str(e)}")
        sys.exit(1)
    except ValueError as e:
        print(f"ERROR: Configuration validation error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Unexpected error: {str(e)}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
