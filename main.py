#!/usr/bin/env python3
"""
Options Trading Bot - Main Entry Point

This script serves as the main entry point for the automated options trading bot.
It initializes the bot with configuration and starts the scheduler for automated execution.
"""

import sys
import signal
import argparse
from pathlib import Path
from dotenv import load_dotenv

from src.bot.trading_bot import TradingBot
from src.scheduler.scheduler import Scheduler

# Load environment variables from .env file
load_dotenv()


def main():
    """Main entry point for the trading bot."""
    parser = argparse.ArgumentParser(
        description="Automated Options Trading Bot for Put Credit Spreads"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config/config.json",
        help="Path to configuration file (default: config/config.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run mode (no actual orders will be submitted)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Execute trading cycle once and exit (without scheduler)",
    )
    parser.add_argument("--version", action="version", version="Options Trading Bot v1.0.0")

    args = parser.parse_args()

    # Verify config file exists
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Configuration file not found at {args.config}")
        print(f"Please create a configuration file or use --config to specify a different path")
        sys.exit(1)

    print(f"Options Trading Bot starting...")
    print(f"Configuration: {args.config}")
    if args.dry_run:
        print("DRY-RUN MODE: No actual orders will be submitted")

    # Initialize TradingBot with configuration
    trading_bot = TradingBot(config_path=str(config_path), dry_run=args.dry_run)

    print("Initializing trading bot...")
    if not trading_bot.initialize():
        print("ERROR: Failed to initialize trading bot")
        sys.exit(1)

    print("Trading bot initialized successfully")

    # Handle --once option or run_immediately config: run single execution without scheduler
    if args.once or trading_bot.config.run_immediately:
        if trading_bot.config.run_immediately:
            print("\nRUN IMMEDIATELY mode enabled in config - ignoring schedule")
        print("\nRunning single trading cycle...")
        try:
            summary = trading_bot.execute_trading_cycle()
            print(
                f"\nExecution complete: {summary.successful_trades}/{summary.total_symbols} successful"
            )
            trading_bot.shutdown()
            sys.exit(0)
        except Exception as e:
            print(f"\nERROR: Trading cycle failed: {str(e)}")
            trading_bot.shutdown()
            sys.exit(1)

    # Initialize Scheduler for continuous operation
    scheduler = Scheduler(config=trading_bot.config, trading_bot=trading_bot)
    scheduler.schedule_execution()

    print(f"Scheduler configured for {trading_bot.config.execution_day} execution")
    print("Press Ctrl+C to stop the bot\n")

    # Set up signal handler for graceful shutdown
    def signal_handler(sig, frame):
        """Handle keyboard interrupt for graceful shutdown."""
        print("\n\nShutdown signal received...")
        scheduler.stop()
        trading_bot.shutdown()
        print("Trading bot stopped successfully")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start Scheduler
    try:
        scheduler.run()
    except KeyboardInterrupt:
        print("\n\nShutdown signal received...")
        scheduler.stop()
        trading_bot.shutdown()
        print("Trading bot stopped successfully")
        sys.exit(0)
    except Exception as e:
        print(f"\nERROR: Unexpected error in main loop: {str(e)}")
        scheduler.stop()
        trading_bot.shutdown()
        sys.exit(1)


if __name__ == "__main__":
    main()
