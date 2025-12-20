# Requirements Document

## Introduction

The tiered covered call strategy currently searches for option expiration dates by iterating through calendar dates and checking if options exist. This approach has a critical flaw: it includes dates that don't have real tradable options (like December 30, 2025), forcing the system to fall back to synthetic strikes. This creates unreliable strategy recommendations since synthetic options cannot be traded.

This feature will improve the expiration date selection logic to only use dates that have real, tradable options available from the Tradier API, eliminating the need for synthetic strike fallbacks in the strategy calculation.

## Glossary

- **Expiration_Finder**: The component responsible for discovering valid option expiration dates
- **Tradier_API**: The external broker API that provides real market option data
- **Option_Chain**: A collection of option contracts for a specific symbol and expiration date
- **Synthetic_Strike**: A generated option contract used as a fallback when real market data is unavailable
- **Strategy_Calculator**: The component that calculates tiered covered call recommendations
- **Valid_Expiration**: An expiration date that has real tradable call options available in the market

## Requirements

### Requirement 1

**User Story:** As a trader, I want the strategy to only recommend expirations with real tradable options, so that I can execute the recommended trades without manual adjustments

#### Acceptance Criteria

1. WHEN the Expiration_Finder searches for expiration dates, THE Expiration_Finder SHALL retrieve only dates that contain at least one call option from the Tradier_API
2. WHEN the Expiration_Finder validates an expiration date, THE Expiration_Finder SHALL verify that the Option_Chain contains call options with non-null bid and ask prices
3. IF an expiration date returns no call options from the Tradier_API, THEN THE Expiration_Finder SHALL exclude that date from the results
4. THE Strategy_Calculator SHALL NOT generate Synthetic_Strikes for any expiration date included in the strategy recommendation

### Requirement 2

**User Story:** As a trader, I want the system to use Tradier's expiration endpoint to find valid dates, so that the search is efficient and accurate

#### Acceptance Criteria

1. THE Expiration_Finder SHALL query the Tradier_API expiration endpoint to retrieve available expiration dates for a symbol
2. WHEN the Tradier_API returns expiration dates, THE Expiration_Finder SHALL filter dates to only include those within the configured min and max days range
3. THE Expiration_Finder SHALL sort the filtered expiration dates in chronological order
4. WHEN fewer than three Valid_Expirations are found, THE Expiration_Finder SHALL return all available Valid_Expirations without error
5. THE Expiration_Finder SHALL limit results to a maximum of three expiration dates

### Requirement 3

**User Story:** As a developer, I want clear logging when expiration dates are filtered out, so that I can troubleshoot issues with option availability

#### Acceptance Criteria

1. WHEN the Expiration_Finder queries the Tradier_API expiration endpoint, THE Expiration_Finder SHALL log the total number of expiration dates returned
2. WHEN the Expiration_Finder filters expiration dates by date range, THE Expiration_Finder SHALL log the number of dates excluded and the reason
3. WHEN the Expiration_Finder validates an expiration date, THE Expiration_Finder SHALL log whether the date has call options available
4. IF an expiration date is excluded due to missing call options, THEN THE Expiration_Finder SHALL log the date and the reason for exclusion
5. WHEN the Expiration_Finder completes the search, THE Expiration_Finder SHALL log the final list of Valid_Expirations selected

### Requirement 4

**User Story:** As a trader, I want the system to handle cases where no valid expirations exist, so that I receive clear feedback instead of synthetic data

#### Acceptance Criteria

1. IF the Tradier_API returns no expiration dates for a symbol, THEN THE Expiration_Finder SHALL raise an error with a message indicating no expirations are available
2. IF all expiration dates are outside the configured date range, THEN THE Expiration_Finder SHALL raise an error with a message indicating the date range constraint
3. IF no expiration dates have call options available, THEN THE Expiration_Finder SHALL raise an error with a message indicating insufficient option liquidity
4. THE error messages SHALL include the symbol, date range searched, and number of dates examined
5. THE Strategy_Calculator SHALL propagate expiration finding errors to the caller without attempting synthetic strike generation

### Requirement 5

**User Story:** As a trader, I want the system to verify option liquidity before including an expiration, so that I only see expirations with tradable options

#### Acceptance Criteria

1. WHEN the Expiration_Finder validates an expiration date, THE Expiration_Finder SHALL retrieve the Option_Chain for that date
2. THE Expiration_Finder SHALL count the number of call options in the Option_Chain
3. IF the Option_Chain contains zero call options, THEN THE Expiration_Finder SHALL exclude that expiration date
4. THE Expiration_Finder SHALL log the call option count for each validated expiration date
5. WHEN an expiration date has at least one call option, THE Expiration_Finder SHALL include that date in the Valid_Expirations list
