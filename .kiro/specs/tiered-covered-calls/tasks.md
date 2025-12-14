# Implementation Plan - Tiered Covered Calls Feature

- [x] 1. Create position querying infrastructure
  - Create `src/positions/` directory and position service module
  - Implement `PositionSummary` and `DetailedPosition` data models
  - Add methods to query long stock and option positions for a symbol
  - Implement logic to calculate available shares (accounting for existing short calls)
  - _Requirements: 1.1, 1.2, 1.3, 5.2_

- [x] 1.1 Implement PositionService class
  - Write `PositionService` class with broker client integration
  - Add `get_long_positions()` method to retrieve all positions for a symbol
  - Implement `calculate_available_shares()` to determine shares available for covered calls
  - Add `get_existing_short_calls()` to identify existing covered call positions
  - _Requirements: 1.1, 1.2, 5.2_

- [x] 1.2 Create position data models
  - Define `PositionSummary` dataclass with symbol, shares, and price information
  - Create `DetailedPosition` dataclass for individual position details
  - Implement `OptionPosition` dataclass extending DetailedPosition for options
  - Add `CoveredCallOrder` dataclass for order specifications
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 2. Extend broker client interfaces for enhanced position querying
  - Add abstract method `get_detailed_positions()` to `BaseBrokerClient`
  - Add abstract method `get_option_chain_multiple_expirations()` for batch option data
  - Add abstract method `submit_multiple_covered_call_orders()` for batch order submission
  - _Requirements: 1.1, 1.2, 2.4_

- [x] 2.1 Implement enhanced position methods in TradierClient
  - Implement `get_detailed_positions()` using Tradier positions API
  - Add `get_option_chain_multiple_expirations()` for multiple expiration dates
  - Implement `submit_multiple_covered_call_orders()` with batch order logic
  - Add error handling for API failures and partial responses
  - _Requirements: 1.1, 1.2, 2.4_

- [x] 2.2 Implement enhanced position methods in AlpacaClient
  - Implement `get_detailed_positions()` using Alpaca positions API
  - Add `get_option_chain_multiple_expirations()` for multiple expiration dates
  - Implement `submit_multiple_covered_call_orders()` with batch order logic
  - Add error handling for API failures and partial responses
  - _Requirements: 1.1, 1.2, 2.4_

- [x] 3. Create tiered covered call strategy calculator
  - Create `src/strategy/tiered_covered_call_strategy.py` module
  - Implement `TieredCoveredCallCalculator` class with strategy planning logic
  - Add methods for expiration date selection and strike price calculation
  - Implement share division algorithm for equal distribution across groups
  - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.2, 3.3_

- [x] 3.1 Implement expiration date selection logic
  - Add `find_next_three_expirations()` method to identify available expiration dates
  - Filter expirations based on minimum and maximum days to expiration
  - Handle cases where fewer than 3 expirations are available
  - Sort expirations chronologically for proper ordering
  - _Requirements: 2.1, 2.5_

- [x] 3.2 Implement incremental strike price calculation
  - Add `calculate_incremental_strikes()` method for progressive strike selection
  - Find first out-of-the-money strike above current price for nearest expiration
  - Select next higher available strikes for second and third expirations
  - Validate all strikes are above current market price
  - Handle insufficient available strikes scenario
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 3.3 Implement share division and contract calculation
  - Add `divide_shares_into_groups()` method for equal share distribution
  - Calculate number of contracts per expiration (shares ÷ 100)
  - Handle remainder shares by allocating to nearest expiration group
  - Validate total contracts don't exceed available shares
  - _Requirements: 2.2, 2.3, 5.1, 5.3_

- [x] 4. Add configuration support for tiered covered calls strategy
  - Add "tcc" strategy configuration to `config/config.json`
  - Define configuration parameters for minimum shares, contract limits, and thresholds
  - Update `ConfigManager` to parse tiered covered call settings
  - Add validation for configuration parameters
  - _Requirements: 5.1, 5.4_

- [x] 4.1 Update configuration models
  - Add tiered covered call fields to `TradingConfig` dataclass
  - Include min_shares_required, max_contracts_per_expiration, and date range settings
  - Add strike_increment_minimum and premium_threshold_per_contract parameters
  - Update config validation to check tiered covered call parameters
  - _Requirements: 5.1, 5.4_

- [x] 5. Create interactive interface for tiered covered calls
  - Add "tcc" option to strategy selection menu in `interactive.py`
  - Implement symbol selection specifically for tiered covered calls
  - Create position summary display showing current holdings
  - Add strategy preview with detailed breakdown of planned trades
  - _Requirements: 4.1, 4.2, 4.3, 4.5_

- [x] 5.1 Implement position summary display
  - Add `display_position_summary()` function to show current holdings
  - Display total shares, available shares, and current stock price
  - Show existing short call positions that reduce available shares
  - Format display with clean tables and clear information hierarchy
  - _Requirements: 1.3, 1.4, 4.1_

- [x] 5.2 Implement strategy preview interface
  - Add `display_tiered_strategy_preview()` function for trade preview
  - Show three expiration groups with dates, strikes, and contract quantities
  - Display estimated premium collection for each group and total
  - Include risk information and position impact summary
  - _Requirements: 4.2, 4.3, 4.4_

- [x] 5.3 Add confirmation and execution flow
  - Implement `confirm_tiered_execution()` function for user confirmation
  - Add detailed confirmation prompt with strategy summary
  - Create execution progress display with real-time order status
  - Implement results display showing successful and failed orders
  - _Requirements: 4.5, 2.4_

- [x] 6. Integrate tiered covered calls into main trading bot
  - Add tiered covered call strategy to `TradingBot` class
  - Implement `process_tiered_covered_calls()` method for automated execution
  - Add strategy initialization and configuration loading
  - Integrate with existing logging and error handling systems
  - _Requirements: 2.4, 5.4, 5.5_

- [x] 6.1 Add strategy routing and execution
  - Update strategy selection logic in `TradingBot.execute_trading_cycle()`
  - Add "tcc" case to strategy routing with proper method call
  - Implement error handling and logging for tiered strategy execution
  - Update strategy names dictionary to include "Tiered Covered Calls"
  - _Requirements: 2.4, 5.4_

- [x] 7. Add comprehensive error handling and validation
  - Implement position validation to prevent naked call creation
  - Add order quantity validation against available shares
  - Create error recovery for partial order failures
  - Add logging for all position queries and order submissions
  - _Requirements: 5.1, 5.3, 5.4, 5.5_

- [x] 7.1 Implement position validation logic
  - Add validation to ensure sufficient shares for all planned contracts
  - Check for existing short calls that reduce available shares
  - Validate minimum share requirements before strategy execution
  - Add warnings for adjusted contract quantities due to insufficient shares
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 8. Create comprehensive test suite
  - Write unit tests for PositionService with mock broker responses
  - Create tests for TieredCoveredCallCalculator with various scenarios
  - Add integration tests for end-to-end strategy execution
  - Test error handling with edge cases and API failures
  - _Requirements: All requirements validation_

- [x] 8.1 Write unit tests for position querying
  - Test position summary calculation with various holding combinations
  - Mock broker API responses for different position scenarios
  - Test available shares calculation with existing short calls
  - Validate error handling for API failures and empty responses
  - _Requirements: 1.1, 1.2, 1.3, 1.5_

- [x] 8.2 Write unit tests for strategy calculation
  - Test expiration date selection with various market calendars
  - Validate strike price calculation with different price levels
  - Test share division with various quantities and remainder handling
  - Verify strategy validation with insufficient shares scenarios
  - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 9. Implement covered call rolling functionality
  - Create `src/strategy/covered_call_roller.py` module
  - Implement `CoveredCallRoller` class for automated rolling of expiring ITM calls
  - Add methods to identify expiring positions and calculate roll opportunities
  - Implement roll execution with simultaneous buy-to-close and sell-to-open orders
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 9.1 Implement expiring position identification
  - Add `identify_expiring_itm_calls()` method to find calls expiring today
  - Filter positions to only include in-the-money calls based on current stock price
  - Support both single symbol and portfolio-wide scanning
  - Add validation to ensure positions are actually short calls (not long)
  - _Requirements: 6.1, 6.2_

- [x] 9.2 Implement roll opportunity calculation
  - Add `calculate_roll_opportunities()` method to find suitable roll targets
  - Implement `find_best_roll_target()` to select optimal expiration and strike
  - Add logic to find strikes nearest to existing call strike price
  - Implement `estimate_roll_credit()` to calculate expected net credit
  - Ensure all roll opportunities res00ult in net credits to the trader
  - _Requirements: 6.3, 6.4, 6.5_

- [x] 9.3 Implement roll execution logic
  - Add `execute_roll_plan()` method for simultaneous order execution
  - Implement buy-to-close orders for expiring calls
  - Implement sell-to-open orders for new call positions
  - Add order tracking and error handling for partial fills
  - Implement rollback logic if either leg of the roll fails
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 10. Extend broker clients for rolling functionality
  - Add `submit_roll_order()` method to `BaseBrokerClient` abstract class
  - Add `get_expiring_short_calls()` method for position filtering
  - Implement rolling methods in `TradierClient` and `AlpacaClient`
  - Add error handling and retry logic for roll order execution
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 10.1 Implement rolling methods in TradierClient
  - Implement `submit_roll_order()` using Tradier's combo order functionality
  - Add `get_expiring_short_calls()` using positions API with expiration filtering
  - Implement proper order types and pricing for roll execution
  - Add comprehensive error handling for Tradier-specific issues
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 10.2 Implement rolling methods in AlpacaClient
  - Implement `submit_roll_order()` using Alpaca's order management
  - Add `get_expiring_short_calls()` using Alpaca positions API
  - Handle Alpaca-specific order types and execution requirements
  - Add error handling for Alpaca API limitations and responses
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 11. Create rolling interface and preview functionality
  - Add rolling-specific functions to `interactive.py`
  - Implement `display_roll_opportunities()` for roll preview
  - Add `confirm_roll_execution()` for user confirmation
  - Create detailed roll summary with credits and position changes
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 11.1 Implement roll preview display
  - Create formatted display of expiring ITM calls
  - Show proposed roll targets with expiration dates and strikes
  - Display estimated credits for each roll opportunity
  - Add summary of total premium to be collected
  - Include risk warnings and position impact information
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [x] 11.2 Add roll confirmation workflow
  - Implement confirmation prompt with detailed roll summary
  - Allow users to select which rolls to execute (all or individual)
  - Add option to modify roll targets before execution
  - Implement execution progress tracking and results display
  - _Requirements: 7.5, 8.4_

- [x] 12. Integrate rolling into scheduled execution
  - Add rolling functionality to `TradingBot` class
  - Implement `process_covered_call_rolls()` method for automated execution
  - Add scheduling logic to run rolling checks at configured time
  - Integrate with existing logging and notification systems
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 12.1 Add scheduled rolling execution
  - Update `TradingBot.execute_trading_cycle()` to include roll checks
  - Add time-based triggering for roll execution (default 3:30 PM)
  - Implement portfolio-wide scanning for expiring ITM calls
  - Add configuration support for enabling/disabling automatic rolling
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 12.2 Add rolling configuration and validation
  - Update configuration models to include rolling parameters
  - Add validation for roll execution time and credit thresholds
  - Implement configuration loading for rolling-specific settings
  - Add logging and monitoring for rolling execution
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 13. Create comprehensive test suite for rolling functionality
  - Write unit tests for `CoveredCallRoller` with mock data
  - Create integration tests for end-to-end rolling execution
  - Test error handling with various failure scenarios
  - Add tests for TLT ticker as specified example
  - _Requirements: All rolling requirements validation_

- [x] 13.1 Write unit tests for rolling logic
  - Test identification of expiring ITM calls with various scenarios
  - Mock broker responses for position and option chain data
  - Test roll opportunity calculation with different market conditions
  - Validate credit calculation and strike selection logic
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 13.2 Write integration tests for rolling execution
  - Test end-to-end rolling with paper trading accounts
  - Validate roll order execution with both Tradier and Alpaca
  - Test error handling and rollback scenarios
  - Create specific test cases using TLT ticker positions
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 14. Implement cost basis tracking functionality
  - Create `src/strategy/cost_basis_tracker.py` module
  - Implement `CostBasisTracker` class for tracking strategy impact on cost basis
  - Add methods to calculate original cost basis and effective cost basis after premium collection
  - Implement persistent storage for cumulative premium tracking across strategy executions
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 14.1 Implement cost basis calculation logic
  - Add `get_cost_basis_summary()` method to retrieve comprehensive cost basis information
  - Implement `calculate_strategy_impact()` to determine cost basis reduction from premium collection
  - Add `calculate_effective_cost_basis()` to compute adjusted cost basis after strategy execution
  - Create logic to handle multiple strategy executions and cumulative premium tracking
  - _Requirements: 9.1, 9.2, 9.3, 9.5_

- [x] 14.2 Implement cost basis persistence and history
  - Add `update_cumulative_premium()` method to track total premium collected over time
  - Implement `get_strategy_history()` to retrieve historical strategy executions and their impact
  - Create data storage mechanism for cost basis tracking (JSON file or database)
  - Add validation to ensure cost basis calculations remain accurate across multiple executions
  - _Requirements: 9.4, 9.5_

- [ ] 15. Integrate cost basis tracking into existing components
  - Update `PositionService` to include cost basis information in position summaries
  - Modify `TieredCoveredCallCalculator` to calculate and display cost basis impact
  - Update `CoveredCallRoller` to track cost basis impact of roll transactions
  - Integrate cost basis tracking into order execution results
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 15.1 Update position service for cost basis
  - Add `calculate_cost_basis()` method to retrieve original stock purchase cost basis
  - Implement `get_cumulative_premium_collected()` to get total premium from previous strategies
  - Update `PositionSummary` data model to include cost basis fields
  - Add cost basis validation to ensure accuracy of calculations
  - _Requirements: 9.1, 9.2_

- [x] 15.2 Update strategy calculators for cost basis impact
  - Modify `TieredCoveredCallCalculator.calculate_strategy()` to include cost basis calculations
  - Add `calculate_cost_basis_impact()` method to determine effective cost basis after strategy
  - Update `TieredCoveredCallPlan` to include original and effective cost basis information
  - Implement cost basis reduction percentage calculations for strategy preview
  - _Requirements: 9.2, 9.3, 9.5_

- [x] 15.3 Update rolling functionality for cost basis tracking
  - Add `calculate_cumulative_cost_basis_impact()` method to `CoveredCallRoller`
  - Update `RollPlan` to include cumulative premium and cost basis impact information
  - Modify roll execution to update cost basis tracking after successful rolls
  - Add cost basis impact to roll preview and confirmation displays
  - _Requirements: 9.4, 9.5_

- [x] 16. Create cost basis display and reporting functionality
  - Add cost basis display functions to `interactive.py`
  - Implement `display_cost_basis_summary()` for comprehensive cost basis information
  - Add `display_strategy_impact()` to show cost basis reduction from strategy execution
  - Create cost basis reporting in strategy preview and results displays
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 16.1 Implement cost basis preview displays
  - Update `display_position_summary()` to include original and effective cost basis
  - Modify `display_tiered_strategy_preview()` to show cost basis impact of planned strategy
  - Add cost basis reduction calculations to strategy confirmation prompts
  - Include cost basis percentage reduction in strategy summaries
  - _Requirements: 9.1, 9.2, 9.3, 9.5_

- [x] 16.2 Implement cost basis results and history displays
  - Add cost basis impact to strategy execution results display
  - Create `display_cost_basis_history()` to show historical strategy impact
  - Implement cost basis tracking in roll results and confirmations
  - Add cost basis summary to final strategy execution reports
  - _Requirements: 9.4, 9.5_

- [x] 17. Create comprehensive test suite for cost basis functionality
  - Write unit tests for `CostBasisTracker` with various scenarios
  - Create integration tests for cost basis tracking across multiple strategy executions
  - Test cost basis calculations with different premium amounts and share quantities
  - Add tests for cost basis persistence and historical tracking
  - _Requirements: All cost basis requirements validation_

- [x] 17.1 Write unit tests for cost basis calculations
  - Test cost basis summary generation with various position scenarios
  - Mock broker responses for cost basis and premium data
  - Test effective cost basis calculations with different premium amounts
  - Validate cost basis reduction percentage calculations
  - _Requirements: 9.1, 9.2, 9.3, 9.5_

- [x] 17.2 Write integration tests for cost basis tracking
  - Test end-to-end cost basis tracking with multiple strategy executions
  - Validate cost basis persistence across application restarts
  - Test cost basis tracking with both initial strategies and rolls
  - Create specific test cases using TLT ticker with known cost basis
  - _Requirements: 9.4, 9.5_