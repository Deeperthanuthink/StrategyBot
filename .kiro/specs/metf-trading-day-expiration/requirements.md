# Requirements Document

## Introduction

This feature ensures that the METF (Market EMA Trend Following) 0DTE strategy uses the next valid trading day for expiration when the bot is run on weekends or market holidays. Currently, the METF strategy uses `date.today()` for 0DTE expiration, which causes issues when running on non-trading days since options cannot expire on weekends or holidays.

## Glossary

- **METF Strategy**: Market EMA Trend Following strategy that trades 0DTE (zero days to expiration) credit spreads based on EMA crossover signals
- **0DTE**: Zero Days To Expiration - options that expire on the same day they are traded
- **Trading Day**: A day when the US stock market is open for trading (excludes weekends and market holidays)
- **Market Holiday**: A day when the US stock market is closed (e.g., New Year's Day, Independence Day, Thanksgiving)
- **Expiration Date**: The date on which an options contract expires and becomes worthless or is exercised

## Requirements

### Requirement 1: Detect Non-Trading Days

**User Story:** As a trader, I want the METF strategy to detect when I'm running it on a weekend or holiday, so that it doesn't attempt to use an invalid expiration date.

#### Acceptance Criteria

1. WHEN the METF strategy is executed, THE System SHALL determine if the current date is a valid trading day by checking if it falls on a weekday (Monday through Friday).
2. WHEN the current date is a Saturday or Sunday, THE System SHALL identify the date as a non-trading day.
3. WHEN the current date is a known US market holiday, THE System SHALL identify the date as a non-trading day.

### Requirement 2: Calculate Next Trading Day

**User Story:** As a trader, I want the system to automatically calculate the next valid trading day when running on a non-trading day, so that my 0DTE orders use a valid expiration.

#### Acceptance Criteria

1. WHEN the current date is a Saturday, THE System SHALL calculate the next trading day as the following Monday (unless Monday is a holiday).
2. WHEN the current date is a Sunday, THE System SHALL calculate the next trading day as the following Monday (unless Monday is a holiday).
3. WHEN the current date is a market holiday, THE System SHALL calculate the next trading day as the first subsequent weekday that is not a holiday.
4. WHEN the calculated next trading day falls on a holiday, THE System SHALL continue to the next weekday until a valid trading day is found.

### Requirement 3: Use Next Trading Day for METF Expiration

**User Story:** As a trader, I want the METF strategy to use the next trading day as the expiration date when I run it on a non-trading day, so that my orders are valid.

#### Acceptance Criteria

1. WHEN the METF strategy is executed on a non-trading day, THE System SHALL use the next valid trading day as the expiration date for the 0DTE spread.
2. WHEN the METF strategy is executed on a valid trading day, THE System SHALL use the current date as the expiration date (existing behavior).
3. WHEN the expiration date is adjusted to the next trading day, THE System SHALL log a warning message indicating the adjustment and the reason.

### Requirement 4: Inform User of Expiration Adjustment

**User Story:** As a trader, I want to be clearly informed when the expiration date has been adjusted to the next trading day, so that I understand what date my options will expire.

#### Acceptance Criteria

1. WHEN the expiration date is adjusted in the trading bot, THE System SHALL log an informational message stating the original date and the adjusted expiration date.
2. WHEN the expiration date is adjusted in the interactive mode, THE System SHALL display a message to the user indicating that the expiration has been set to the next trading day.
3. WHEN displaying the planned order in interactive mode, THE System SHALL show the adjusted expiration date with a note indicating it was adjusted from a non-trading day.

### Requirement 5: US Market Holiday Calendar

**User Story:** As a trader, I want the system to recognize all standard US market holidays, so that the next trading day calculation is accurate.

#### Acceptance Criteria

1. THE System SHALL maintain a list of US market holidays for the current and next calendar year.
2. THE System SHALL recognize the following holidays: New Year's Day, Martin Luther King Jr. Day, Presidents' Day, Good Friday, Memorial Day, Juneteenth, Independence Day, Labor Day, Thanksgiving Day, and Christmas Day.
3. WHEN a holiday falls on a weekend, THE System SHALL recognize the observed date (Friday for Saturday holidays, Monday for Sunday holidays) as the non-trading day.
