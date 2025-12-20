# Implementation Plan

- [x] 1. Add get_option_expirations() method to TradierClient
  - Create new method that queries Tradier's `/v1/markets/options/expirations` endpoint
  - Parse JSON response and extract expiration dates from `expirations.date` array
  - Convert date strings (YYYY-MM-DD format) to Python date objects
  - Sort dates chronologically before returning
  - Add error handling for API failures (4xx/5xx status codes)
  - Add error handling for empty expiration lists
  - Add logging for number of expirations retrieved and any errors
  - _Requirements: 2.1, 2.2, 3.1, 4.1_

- [x] 1.1 Write unit tests for get_option_expirations()
  - Test successful API response parsing with mock response
  - Test empty expiration list handling
  - Test API error handling (404, 500 status codes)
  - Test date string to date object conversion
  - Test chronological sorting of dates
  - _Requirements: 2.1, 2.2_

- [x] 2. Refactor find_next_three_expirations() in TieredCoveredCallCalculator
  - Replace date iteration loop with call to broker_client.get_option_expirations()
  - Remove weekend skipping logic (_skip_weekend method calls)
  - Remove sample date generation loop (days_to_try iteration)
  - Add date range filtering to keep only expirations between min_date and max_date
  - Keep existing validation loop that checks for call options
  - Update validation loop to check up to 5 expirations (instead of iterating all dates)
  - Update logging to show expirations from API, filtered count, and validation results
  - _Requirements: 2.2, 2.3, 2.4, 2.5, 3.2, 3.3, 3.4, 3.5_

- [x] 2.1 Write unit tests for refactored find_next_three_expirations()
  - Test date range filtering with various min/max days configurations
  - Test call option validation logic
  - Test returning fewer than 3 expirations when available
  - Test error propagation from get_option_expirations()
  - Test logging at each step (API call, filtering, validation)
  - _Requirements: 2.2, 2.3, 2.4, 2.5_

- [x] 3. Update error handling in strategy calculator
  - Ensure find_next_three_expirations() raises ValueError with clear message when no expirations available
  - Ensure error message includes symbol and date range when all expirations outside range
  - Ensure error message includes symbol when no expirations have call options
  - Update calculate_strategy() to propagate expiration finding errors without attempting synthetic strikes
  - Add logging for all error scenarios at appropriate levels (warning/error)
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 3.4_

- [x] 3.1 Write integration tests for strategy calculation
  - Test end-to-end strategy calculation with symbol that has valid expirations
  - Verify no synthetic strikes appear in final strategy plan
  - Verify all expirations in plan have real call options
  - Test with different date ranges (narrow and wide)
  - Test error handling when no valid expirations found
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 4. Update logging throughout expiration finding flow
  - Add info-level log when get_option_expirations() is called with total count retrieved
  - Add info-level log after date filtering with count before and after
  - Add info-level log for each expiration validation showing call option count
  - Add warning-level log when expiration excluded due to no call options
  - Add warning-level log when fewer than 3 expirations available
  - Add info-level log with final list of validated expirations
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 5. Verify synthetic strikes are not used in strategy calculations
  - Review get_option_chain() to ensure synthetic strike fallback remains for other use cases
  - Verify that find_next_three_expirations() only returns expirations with real options
  - Test that calculate_strategy() never receives expirations that would trigger synthetic strikes
  - Add assertion or validation check that strategy plan contains no synthetic options
  - _Requirements: 1.4, 5.1, 5.2, 5.3_
