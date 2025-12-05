"""Scheduler for automated trading bot execution."""

import schedule
import time
from datetime import datetime, time as dt_time
from typing import Optional

from src.config.models import Config
from src.bot.trading_bot import TradingBot


class Scheduler:
    """Scheduler for automated execution of trading bot on a weekly schedule."""

    def __init__(self, config: Config, trading_bot: TradingBot):
        """Initialize the Scheduler.

        Args:
            config: Configuration object containing execution timing parameters
            trading_bot: TradingBot instance to execute on schedule
        """
        self.config = config
        self.trading_bot = trading_bot
        self._running = False
        self._scheduled_time: Optional[dt_time] = None

    def schedule_execution(self):
        """Set up trigger for trading bot execution.

        This method calculates the execution time based on market open time
        plus the configured offset minutes, and schedules the trading bot
        to run at that time on the configured execution day (or daily).
        """
        # Calculate execution time
        execution_time = self._calculate_execution_time()
        self._scheduled_time = execution_time

        # Get execution day from config
        execution_day = self.config.execution_day

        # Schedule the job
        if execution_day.lower() == "daily":
            # Schedule for every day
            schedule.every().day.at(execution_time.strftime("%H:%M")).do(
                self._execute_trading_cycle
            )
            schedule_type = "daily"
        else:
            # Schedule for specific day of week
            schedule_job = getattr(schedule.every(), execution_day.lower())
            schedule_job.at(execution_time.strftime("%H:%M")).do(self._execute_trading_cycle)
            schedule_type = f"weekly on {execution_day}"

        if self.trading_bot.logger:
            self.trading_bot.logger.log_info(
                f"Scheduled trading bot execution ({schedule_type})",
                {
                    "schedule": schedule_type,
                    "time": execution_time.strftime("%H:%M"),
                    "timezone": "US/Central",
                },
            )

    def _calculate_execution_time(self) -> dt_time:
        """Calculate execution time as market open + configured offset minutes.

        This method handles timezone conversion to US/Central for market hours.
        Market typically opens at 9:30 AM Eastern Time = 8:30 AM Central Time.

        Returns:
            Time object representing the execution time in US/Central timezone
        """
        # Market opens at 9:30 AM Eastern Time = 8:30 AM Central Time
        market_open_hour_ct = 8
        market_open_minute_ct = 30

        # Add configured offset minutes
        offset_minutes = self.config.execution_time_offset_minutes

        # Calculate total minutes from midnight
        total_minutes = (market_open_hour_ct * 60) + market_open_minute_ct + offset_minutes

        # Convert back to hours and minutes
        execution_hour = total_minutes // 60
        execution_minute = total_minutes % 60

        # Create time object (schedule library handles timezone internally)
        execution_time = dt_time(hour=execution_hour, minute=execution_minute)

        return execution_time

    def _execute_trading_cycle(self):
        """Execute the trading cycle with error handling.

        This method is called by the scheduler and wraps the trading bot
        execution with error handling and logging.
        """
        try:
            if self.trading_bot.logger:
                self.trading_bot.logger.log_info(
                    "Scheduler triggered trading cycle execution",
                    {
                        "scheduled_time": (
                            self._scheduled_time.strftime("%H:%M")
                            if self._scheduled_time
                            else "unknown"
                        )
                    },
                )

            # Execute the trading cycle
            summary = self.trading_bot.execute_trading_cycle()

            if self.trading_bot.logger:
                self.trading_bot.logger.log_info(
                    "Scheduled trading cycle completed",
                    {
                        "successful_trades": summary.successful_trades,
                        "failed_trades": summary.failed_trades,
                    },
                )

        except Exception as e:
            if self.trading_bot.logger:
                self.trading_bot.logger.log_error(
                    "Error during scheduled trading cycle execution",
                    e,
                    {
                        "scheduled_time": (
                            self._scheduled_time.strftime("%H:%M")
                            if self._scheduled_time
                            else "unknown"
                        )
                    },
                )
            else:
                print(f"ERROR during scheduled execution: {str(e)}")

    def run(self):
        """Run the scheduler with continuous execution loop.

        This method starts the scheduler and checks for pending jobs every minute.
        It handles scheduler errors with logging and continues running.
        The loop continues until stop() is called.
        """
        self._running = True

        if self.trading_bot.logger:
            self.trading_bot.logger.log_info(
                "Scheduler started",
                {
                    "execution_day": self.config.execution_day,
                    "execution_time": (
                        self._scheduled_time.strftime("%H:%M CT")
                        if self._scheduled_time
                        else "not scheduled"
                    ),
                    "timezone": "US/Central",
                },
            )

        while self._running:
            try:
                # Check for pending scheduled jobs
                schedule.run_pending()

                # Sleep for 1 minute before checking again
                time.sleep(60)

            except KeyboardInterrupt:
                # Allow graceful shutdown on Ctrl+C
                if self.trading_bot.logger:
                    self.trading_bot.logger.log_info("Scheduler interrupted by user")
                self.stop()
                break

            except Exception as e:
                # Log error but continue running
                if self.trading_bot.logger:
                    self.trading_bot.logger.log_error(
                        "Error in scheduler loop, attempting to continue",
                        e,
                        {"error": str(e)},
                    )
                else:
                    print(f"ERROR in scheduler loop: {str(e)}")

                # Sleep before retrying
                time.sleep(60)

        if self.trading_bot.logger:
            self.trading_bot.logger.log_info("Scheduler stopped")

    def stop(self):
        """Stop the scheduler gracefully.

        This method sets the running flag to False, which will cause
        the run() loop to exit on its next iteration.
        """
        if self.trading_bot.logger:
            self.trading_bot.logger.log_info("Stopping scheduler")

        self._running = False

        # Clear all scheduled jobs
        schedule.clear()
