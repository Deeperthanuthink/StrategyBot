# Requirements Document

## Introduction

This feature enables automated selling of covered calls across multiple expiration dates with incrementally higher strike prices. The system will query existing long positions for a specified symbol and systematically sell covered calls in three groups across the next three available expiration dates, using progressively higher out-of-the-money strike prices.

## Glossary

- **System**: The options trading bot application
- **User**: The trader using the system
- **Long_Position**: Stock shares or long option contracts owned by the user
- **Covered_Call**: A call option sold against owned stock shares (100 shares per contract)
- **Strike_Price**: The price at which the option can be exercised
- **Expiration_Date**: The date when the option contract expires
- **OTM_Strike**: Out-of-the-money strike price (above current stock price)
- **Position_Query**: Request to retrieve current holdings for a symbol
- **Tiered_Strategy**: Selling options across multiple expirations with different strikes
- **ITM_Call**: In-the-money call option where strike price is below current stock price
- **Roll_Transaction**: Closing an existing option position and opening a new one with different terms
- **Credit_Roll**: A roll transaction that results in a net credit to the trader
- **Expiring_Option**: An option contract that expires on the current trading day
- **Cost_Basis**: The original purchase price of the underlying stock shares
- **Effective_Cost_Basis**: The adjusted cost basis after accounting for option premiums collected
- **Strategy_Impact**: The effect of the covered call strategy on the overall position cost basis

## Requirements

### Requirement 1

**User Story:** As a trader, I want to query my long positions for a specific stock symbol, so that I can see all my holdings before executing a tiered covered call strategy.

#### Acceptance Criteria

1. WHEN the User requests position information for a symbol, THE System SHALL retrieve all long stock positions for that symbol
2. WHEN the User requests position information for a symbol, THE System SHALL retrieve all long option positions for that symbol
3. WHEN position data is retrieved, THE System SHALL display the total number of shares available for covered call writing
4. WHEN position data is retrieved, THE System SHALL display the current market price of the underlying stock
5. IF no long positions exist for the symbol, THEN THE System SHALL display an appropriate message and prevent strategy execution

### Requirement 2

**User Story:** As a trader, I want to automatically sell covered calls across three different expiration dates, so that I can generate income while managing time decay risk across multiple timeframes.

#### Acceptance Criteria

1. WHEN executing the tiered strategy, THE System SHALL identify the next three available expiration dates for the symbol
2. WHEN expiration dates are identified, THE System SHALL divide available shares into three equal groups for each expiration
3. WHEN shares cannot be divided equally, THE System SHALL allocate remaining shares to the nearest expiration group
4. WHEN executing orders, THE System SHALL submit covered call orders for each expiration group simultaneously
5. IF any expiration date has insufficient option liquidity, THEN THE System SHALL skip that expiration and use the next available date

### Requirement 3

**User Story:** As a trader, I want strike prices to be incrementally higher across the three expiration groups, so that I can capture more premium on longer-dated options while maintaining upside potential.

#### Acceptance Criteria

1. WHEN calculating strike prices, THE System SHALL find the first out-of-the-money strike above the current stock price for the nearest expiration
2. WHEN calculating strike prices for the second expiration, THE System SHALL use the next higher available strike price
3. WHEN calculating strike prices for the third expiration, THE System SHALL use the next higher available strike price after the second expiration strike
4. WHEN strike prices are selected, THE System SHALL ensure all strikes are above the current market price
5. IF insufficient strike prices are available above market price, THEN THE System SHALL use the highest available strikes and notify the User

### Requirement 4

**User Story:** As a trader, I want to see a detailed preview of the tiered covered call strategy before execution, so that I can review and confirm the planned trades.

#### Acceptance Criteria

1. WHEN the strategy is calculated, THE System SHALL display the current stock price and total shares owned
2. WHEN the strategy is calculated, THE System SHALL show the three expiration dates and corresponding strike prices
3. WHEN the strategy is calculated, THE System SHALL display the number of contracts for each expiration group
4. WHEN the strategy is calculated, THE System SHALL show the expected premium collection for each group
5. WHEN the preview is displayed, THE System SHALL require explicit User confirmation before executing trades

### Requirement 5

**User Story:** As a trader, I want the system to validate that I have sufficient shares for covered call writing, so that I don't accidentally create naked call positions.

#### Acceptance Criteria

1. WHEN calculating covered calls, THE System SHALL verify that total shares owned is at least 100 shares per contract
2. WHEN validating positions, THE System SHALL account for existing short call positions that may reduce available shares
3. WHEN insufficient shares are detected, THE System SHALL reduce the number of contracts to match available shares
4. WHEN contract quantities are adjusted, THE System SHALL notify the User of the changes
5. IF total shares are less than 100, THEN THE System SHALL prevent strategy execution and display an error message

### Requirement 6

**User Story:** As a trader, I want the system to automatically identify and roll in-the-money covered calls that are expiring today, so that I can maintain my covered call positions and avoid assignment.

#### Acceptance Criteria

1. WHEN the System runs near market close, THE System SHALL identify all short call positions expiring on the current day
2. WHEN expiring calls are identified, THE System SHALL determine which calls are in-the-money based on current stock price
3. WHEN in-the-money calls are found, THE System SHALL find the next available expiration date for rolling
4. WHEN selecting roll targets, THE System SHALL choose strikes nearest to the existing call strike price
5. WHEN calculating roll transactions, THE System SHALL ensure the roll results in a net credit to the trader

### Requirement 7

**User Story:** As a trader, I want to preview and confirm covered call roll transactions before execution, so that I can review the terms and ensure they meet my criteria.

#### Acceptance Criteria

1. WHEN roll opportunities are identified, THE System SHALL display the current expiring positions
2. WHEN displaying roll options, THE System SHALL show the proposed new expiration date and strike price
3. WHEN showing roll details, THE System SHALL calculate and display the net credit for each roll transaction
4. WHEN presenting roll opportunities, THE System SHALL show the total premium to be collected
5. WHEN roll preview is complete, THE System SHALL require explicit User confirmation before executing trades

### Requirement 8

**User Story:** As a trader, I want the system to execute covered call rolls as simultaneous buy-to-close and sell-to-open orders, so that I can ensure proper execution and avoid timing risks.

#### Acceptance Criteria

1. WHEN executing rolls, THE System SHALL submit buy-to-close orders for expiring in-the-money calls
2. WHEN closing positions, THE System SHALL simultaneously submit sell-to-open orders for new call positions
3. WHEN orders are submitted, THE System SHALL use appropriate order types to ensure fills
4. WHEN tracking execution, THE System SHALL monitor both legs of each roll transaction
5. IF any roll leg fails to execute, THEN THE System SHALL attempt to cancel the corresponding leg and report the failure

### Requirement 9

**User Story:** As a trader, I want to track the cost basis impact of my covered call strategy, so that I can understand how the strategy affects my overall position profitability.

#### Acceptance Criteria

1. WHEN displaying position information, THE System SHALL show the original cost basis of the underlying stock shares
2. WHEN calculating strategy impact, THE System SHALL compute the effective cost basis after accounting for option premiums collected
3. WHEN showing strategy results, THE System SHALL display the total premium collected and its impact on cost basis reduction
4. WHEN rolling positions, THE System SHALL track the cumulative premium collected from all roll transactions
5. WHEN presenting final results, THE System SHALL show both the original cost basis and the effective cost basis after strategy execution