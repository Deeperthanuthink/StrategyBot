# Implementation Plan: Strategy Stock Screener

## Overview

This implementation plan breaks down the strategy stock screener feature into discrete coding tasks. The system will be built incrementally, starting with core infrastructure, then adding Finviz integration, implementing the PCS strategy, building the Marimo notebook interface, and finally adding data persistence and configuration management.

## Tasks

- [x] 1. Set up project structure and dependencies
  - Create `screener/` directory structure
  - Add required dependencies to requirements.txt: marimo, finvizfinance, hypothesis, pandas, numpy, scipy
  - Create base configuration files
  - _Requirements: 7.1_

- [x] 2. Implement core data models
  - [x] 2.1 Create StockData dataclass
    - Define all fields: ticker, price, volume, technical indicators, options data
    - Add validation methods for required fields
    - _Requirements: 2.3, 2.4_

  - [x] 2.2 Write property test for StockData validation
    - **Property 8: Data Parsing Validity**
    - **Validates: Requirements 2.4**

  - [x] 2.3 Create StrategyAnalysis dataclass
    - Define fields for analysis results: scores, support levels, recommendations
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [x] 2.4 Create ScreenerResults and configuration dataclasses
    - Define ScreenerResults with timestamp, strategy, filters, stocks
    - Define ScreeningSession for history tracking
    - _Requirements: 6.1, 6.5_


- [x] 3. Implement strategy plugin system
  - [x] 3.1 Create StrategyModule abstract base class
    - Define abstract methods: name, default_filters, get_finviz_filters, score_stock, analyze_stock
    - _Requirements: 5.1, 5.5_

  - [x] 3.2 Implement strategy discovery mechanism
    - Create function to scan strategies/ directory
    - Auto-register strategy modules
    - _Requirements: 5.2_

  - [x] 3.3 Write property test for strategy discovery
    - **Property 15: Strategy Plugin Discovery**
    - **Validates: Requirements 5.2**

  - [x] 3.4 Write property test for strategy interface validation
    - **Property 17: Strategy Interface Validation**
    - **Validates: Requirements 5.5**

- [x] 4. Implement Finviz integration layer
  - [x] 4.1 Create FinvizClient class
    - Implement authentication with credentials from environment
    - Add connection validation
    - _Requirements: 2.1_

  - [x] 4.2 Write property test for authentication
    - **Property 5: Authentication Success**
    - **Validates: Requirements 2.1**

  - [x] 4.3 Implement screener method with filter mapping
    - Create FINVIZ_FILTER_MAP dictionary
    - Translate internal filters to Finviz parameters
    - Call finvizfinance library to retrieve results
    - _Requirements: 2.2_

  - [x] 4.4 Implement data download and parsing
    - Download complete dataset from Finviz
    - Parse into StockData objects
    - Handle missing fields with safe defaults
    - _Requirements: 2.3, 2.4_

  - [x] 4.5 Write property test for filter application
    - **Property 6: Filter Application Correctness**
    - **Validates: Requirements 2.2**

  - [x] 4.6 Write property test for data completeness
    - **Property 7: Downloaded Data Completeness**
    - **Validates: Requirements 2.3**

  - [x] 4.7 Implement error handling for authentication and rate limits
    - Add retry logic with exponential backoff
    - Handle rate limit errors gracefully
    - _Requirements: 2.5, 2.6_

  - [x] 4.8 Write unit tests for error handling
    - Test invalid credentials error message
    - Test rate limit handling
    - _Requirements: 2.5, 2.6, 8.1, 8.5_


- [x] 5. Implement analysis engine
  - [x] 5.1 Implement IV rank calculation
    - Create calculate_iv_rank function using 52-week high/low
    - _Requirements: 4.1_

  - [x] 5.2 Implement support level identification
    - Identify MA-based supports (20, 50, 200 day)
    - Find swing lows in recent price history
    - Identify psychological levels (round numbers)
    - _Requirements: 4.2_

  - [x] 5.3 Implement probability of profit estimation
    - Use Black-Scholes delta approximation
    - Calculate POP for given strike and DTE
    - _Requirements: 4.3_

  - [x] 5.4 Implement premium estimation for PCS
    - Use Black-Scholes to price put options
    - Calculate credit spread value
    - Compute max risk and return on risk
    - _Requirements: 4.4_

  - [x] 5.5 Write property test for analysis completeness
    - **Property 12: Analysis Completeness**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4**

  - [x] 5.6 Implement visualization data generation
    - Create price chart data with support levels
    - Create IV history chart data
    - _Requirements: 4.5_

  - [x] 5.7 Write property test for visualization data
    - **Property 13: Visualization Data Generation**
    - **Validates: Requirements 4.5**

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.


- [x] 7. Implement PCS strategy module
  - [x] 7.1 Create PCSStrategy class implementing StrategyModule
    - Define PCS_DEFAULT_FILTERS with all criteria
    - Implement get_finviz_filters method
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9_

  - [x] 7.2 Implement PCS scoring algorithm
    - Score based on IV rank (30 points)
    - Score based on technical strength (25 points)
    - Score based on liquidity (20 points)
    - Score based on stability (25 points)
    - _Requirements: 3.10_

  - [x] 7.3 Implement PCS analyze_stock method
    - Call analysis engine functions
    - Generate recommendations based on scores
    - Create StrategyAnalysis object
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [x] 7.4 Write property test for PCS filter enforcement
    - **Property 9: PCS Filter Criteria Enforcement**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8**

  - [x] 7.5 Write property test for earnings date filtering
    - **Property 10: Earnings Date Filtering**
    - **Validates: Requirements 3.9**

  - [x] 7.6 Write property test for results ranking
    - **Property 11: Results Ranking Order**
    - **Validates: Requirements 3.10**

- [x] 8. Implement core screening engine
  - [x] 8.1 Create ScreeningEngine class
    - Implement screen_stocks method to orchestrate workflow
    - Implement get_available_strategies using discovery
    - Implement load_strategy method
    - _Requirements: 5.2, 5.3_

  - [x] 8.2 Implement filter application logic
    - Apply filters to stock DataFrame
    - Handle conditional filters (earnings date)
    - _Requirements: 3.9_

  - [x] 8.3 Implement results ranking
    - Sort stocks by strategy score descending
    - _Requirements: 3.10_

  - [x] 8.4 Write property test for strategy loading
    - **Property 16: Strategy Loading Correctness**
    - **Validates: Requirements 5.3**


- [x] 9. Implement storage layer
  - [x] 9.1 Create StorageManager class
    - Implement save_results with timestamp
    - Implement load_results by ID
    - Create data/screener_results/ directory structure
    - _Requirements: 6.1, 6.2_

  - [x] 9.2 Write property test for results persistence
    - **Property 18: Results Persistence**
    - **Validates: Requirements 6.1**

  - [x] 9.3 Write property test for historical retrieval
    - **Property 19: Historical Results Retrieval**
    - **Validates: Requirements 6.2**

  - [x] 9.4 Implement export methods
    - Implement export_to_csv with all columns
    - Implement export_to_json with structured data
    - _Requirements: 6.3, 6.4_

  - [x] 9.5 Write property test for JSON export round-trip
    - **Property 20: Export Round-Trip Consistency**
    - **Validates: Requirements 6.4**

  - [x] 9.6 Write property test for CSV export completeness
    - **Property 21: CSV Export Completeness**
    - **Validates: Requirements 6.3**

  - [x] 9.7 Implement history log maintenance
    - Add entries to screener_history.json
    - Implement get_history method
    - _Requirements: 6.5_

  - [x] 9.8 Write property test for history logging
    - **Property 22: History Log Maintenance**
    - **Validates: Requirements 6.5**

  - [x] 9.9 Implement error handling for storage operations
    - Handle write failures with retry
    - Handle read failures with fallback
    - _Requirements: 6.6_

  - [x] 9.10 Write unit tests for storage error handling
    - Test write failure recovery
    - Test read failure fallback
    - _Requirements: 6.6_


- [x] 10. Implement configuration management
  - [x] 10.1 Create ConfigManager class
    - Implement load_config from JSON file
    - Implement get/set methods with dot notation
    - Implement save method
    - _Requirements: 7.1_

  - [x] 10.2 Write unit test for default config loading
    - Test that defaults are loaded on startup
    - _Requirements: 7.1_

  - [x] 10.3 Implement preset management
    - Implement save_preset method
    - Implement load_preset method
    - Implement list_presets method
    - Store presets in user_presets.json
    - _Requirements: 7.2, 7.3, 7.4_

  - [x] 10.4 Write property test for preset round-trip
    - **Property 23: Preset Round-Trip Consistency**
    - **Validates: Requirements 7.2, 7.3**

  - [x] 10.5 Write property test for multiple presets per strategy
    - **Property 24: Multiple Presets Per Strategy**
    - **Validates: Requirements 7.4**

  - [x] 10.6 Implement parameter validation
    - Validate numeric parameters are within ranges
    - Return clear error messages for invalid values
    - _Requirements: 7.6, 8.3_

  - [x] 10.7 Write property test for parameter validation
    - **Property 25: Parameter Range Validation**
    - **Validates: Requirements 7.6, 8.3**

  - [x] 10.8 Implement config error handling
    - Use safe defaults for invalid config
    - Log warnings for malformed files
    - _Requirements: 7.5_

  - [x] 10.9 Write unit tests for config error handling
    - Test invalid JSON handling
    - Test missing config file handling
    - _Requirements: 7.5_

- [x] 10.10 Implement strategy-specific configuration files
  - Create config/strategies/ directory structure
  - Create strategy config files for PCS, Covered Call, Iron Condor, Collar
  - Extend ConfigManager to load strategy configs
  - Add methods: load_strategy_config, get_strategy_defaults, get_strategy_scoring_weights, get_strategy_analysis_settings, list_available_strategies
  - Write unit tests for strategy config loading
  - Create documentation for strategy config system
  - _Enhancement: Allows strategies to be configured via JSON files instead of hardcoded in modules_

- [x] 11. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.


- [x] 12. Implement Marimo notebook interface
  - [x] 12.1 Create main notebook file (screener.py)
    - Set up Marimo app structure
    - Import all required modules
    - _Requirements: 1.1_

  - [x] 12.2 Write unit test for notebook initialization
    - Test that UI elements are present on launch
    - _Requirements: 1.1_

  - [x] 12.3 Create strategy selector UI component
    - Use mo.ui.dropdown with available strategies
    - Make reactive to selection changes
    - _Requirements: 1.1, 5.3_

  - [x] 12.4 Create filter panel UI component
    - Use mo.ui.dictionary for filter inputs
    - Load default filters from selected strategy
    - Make reactive to strategy changes
    - _Requirements: 1.1, 1.2_

  - [x] 12.5 Write property test for reactive updates
    - **Property 1: Reactive UI Updates**
    - **Validates: Requirements 1.2**

  - [x] 12.6 Create results table UI component
    - Display stocks with symbols, metrics, scores
    - Make sortable by columns
    - Make filterable
    - _Requirements: 1.3_

  - [x] 12.7 Write property test for results display completeness
    - **Property 2: Results Display Completeness**
    - **Validates: Requirements 1.3**

  - [x] 12.8 Create stock detail view UI component
    - Display detailed analysis on stock selection
    - Show support levels, POP, premium estimates
    - Include price and IV charts
    - _Requirements: 1.4, 4.5_

  - [x] 12.9 Write property test for detail view trigger
    - **Property 3: Stock Detail View Trigger**
    - **Validates: Requirements 1.4**

  - [x] 12.10 Implement preference persistence
    - Save filter preferences to config
    - Load preferences on startup
    - _Requirements: 1.5_

  - [x] 12.11 Write property test for preference persistence
    - **Property 4: Preference Persistence Round-Trip**
    - **Validates: Requirements 1.5**

  - [x] 12.11 Create export controls UI component
    - Add buttons for CSV and JSON export
    - Wire to StorageManager export methods
    - _Requirements: 6.3, 6.4_


- [ ] 13. Implement additional strategy modules
  - [ ] 13.1 Create CoveredCallStrategy class
    - Define covered call specific filters
    - Implement scoring for covered calls
    - Implement analysis for covered calls
    - _Requirements: 5.4_

  - [ ] 13.2 Create IronCondorStrategy class
    - Define iron condor specific filters
    - Implement scoring for iron condors
    - Implement analysis for iron condors
    - _Requirements: 5.4_

  - [ ] 13.3 Create CollarStrategy class
    - Define collar specific filters
    - Implement scoring for collars
    - Implement analysis for collars
    - _Requirements: 5.4_

  - [ ] 13.4 Write unit test for minimum required strategies
    - Test that PCS, Covered Call, Iron Condor, and Collar are available
    - _Requirements: 5.4_

- [ ] 14. Integration and wiring
  - [ ] 14.1 Wire all components together in main notebook
    - Connect ScreeningEngine to Finviz client
    - Connect UI components to screening engine
    - Connect storage manager for persistence
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [ ] 14.2 Add comparative analysis functionality
    - Implement comparative metrics calculation
    - Display rankings across multiple stocks
    - _Requirements: 4.6_

  - [ ] 14.3 Write property test for comparative metrics
    - **Property 14: Comparative Metrics Availability**
    - **Validates: Requirements 4.6**

  - [ ] 14.4 Implement empty results handling
    - Detect when no stocks match criteria
    - Suggest specific filters to relax
    - _Requirements: 8.4_

  - [ ] 14.5 Write unit test for empty results suggestions
    - Test that suggestions are provided when results are empty
    - _Requirements: 8.4_

  - [ ] 14.6 Add environment variable configuration
    - Load Finviz credentials from .env
    - Load other config from environment
    - _Requirements: 2.1_

- [ ] 15. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- All tasks are required for comprehensive implementation
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- The implementation uses Python with marimo, finvizfinance, hypothesis, pandas, numpy, and scipy
