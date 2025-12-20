# Design Document: Valid Expiration Filtering

## Overview

This design improves the tiered covered call strategy's expiration date selection by using Tradier's expiration endpoint to retrieve only valid, tradable option expiration dates. The current implementation iterates through calendar dates and checks for options, which includes dates without real options (like Dec 30, 2025), forcing synthetic strike generation.

The new approach will:
1. Query Tradier's `/v1/markets/options/expirations` endpoint to get actual available expiration dates
2. Filter these dates by the configured date range (min/max days to expiration)
3. Validate that each expiration has call options before including it in the strategy
4. Eliminate the need for synthetic strikes in strategy calculations

## Architecture

### Component Overview

```
TieredCoveredCallCalculator
    ↓ calls
find_next_three_expirations()
    ↓ calls
TradierClient.get_option_expirations()  [NEW METHOD]
    ↓ HTTP GET
Tradier API: /v1/markets/options/expirations
    ↓ returns
List[date] (actual expiration dates)
    ↓ filtered by
Date range validation (min_days, max_days)
    ↓ validated by
Option chain verification (has call options)
    ↓ returns
List[date] (3 valid expirations)
```

### Key Changes

1. **New Method in TradierClient**: `get_option_expirations(symbol: str) -> List[date]`
   - Queries Tradier's expiration endpoint
   - Returns list of actual expiration dates available for the symbol
   - No date parameter needed - returns all available expirations

2. **Refactored Method in TieredCoveredCallCalculator**: `find_next_three_expirations(symbol: str) -> List[date]`
   - Calls `get_option_expirations()` instead of iterating through dates
   - Filters by date range
   - Validates each expiration has call options
   - Returns up to 3 valid expirations

3. **Remove Synthetic Strike Fallback**: In strategy calculation flow
   - Strategy calculator will only work with validated expirations
   - No synthetic strikes generated during strategy planning
   - Synthetic strikes remain available for other use cases (market closed scenarios)

## Components and Interfaces

### 1. TradierClient.get_option_expirations()

**Purpose**: Query Tradier API for available option expiration dates

**Method Signature**:
```python
def get_option_expirations(self, symbol: str) -> List[date]:
    """Get available option expiration dates for a symbol.
    
    Args:
        symbol: Stock symbol (e.g., 'TLT')
        
    Returns:
        List of expiration dates sorted chronologically
        
    Raises:
        ValueError: If API request fails or no expirations available
    """
```

**API Endpoint**: `GET /v1/markets/options/expirations`
- Parameters: `symbol={symbol}`
- Headers: `Authorization: Bearer {api_token}`, `Accept: application/json`
- Response format:
```json
{
  "expirations": {
    "date": ["2025-12-26", "2025-12-29", "2026-01-02", ...]
  }
}
```

**Implementation Details**:
- Use `requests.get()` to call Tradier REST API
- Parse JSON response and extract `expirations.date` array
- Convert date strings to Python `date` objects
- Sort dates chronologically
- Log the number of expirations retrieved
- Handle API errors with appropriate error messages

**Error Handling**:
- HTTP 4xx/5xx: Raise `ValueError` with status code and message
- Empty response: Raise `ValueError` indicating no expirations available
- JSON parse error: Raise `ValueError` with parsing error details

### 2. TieredCoveredCallCalculator.find_next_three_expirations()

**Purpose**: Find up to 3 valid expiration dates with tradable call options

**Refactored Logic**:
```python
def find_next_three_expirations(self, symbol: str) -> List[date]:
    # 1. Get all available expirations from Tradier
    all_expirations = self.broker_client.get_option_expirations(symbol)
    
    # 2. Calculate date range
    today = date.today()
    min_date = today + timedelta(days=self.min_days_to_expiration)
    max_date = today + timedelta(days=self.max_days_to_expiration)
    
    # 3. Filter by date range
    filtered_expirations = [
        exp for exp in all_expirations 
        if min_date <= exp <= max_date
    ]
    
    # 4. Validate each expiration has call options
    validated_expirations = []
    for expiration in filtered_expirations[:5]:  # Check up to 5 to get 3 valid
        options = self.broker_client.get_option_chain(symbol, expiration)
        call_options = [opt for opt in options if opt.option_type.lower() == 'call']
        
        if call_options:
            validated_expirations.append(expiration)
            if len(validated_expirations) >= 3:
                break
    
    # 5. Return up to 3 validated expirations
    return validated_expirations[:3]
```

**Changes from Current Implementation**:
- **Remove**: Date iteration loop (`for days_out in days_to_try`)
- **Remove**: Weekend skipping logic (not needed with real expirations)
- **Remove**: Sample date generation
- **Add**: Call to `get_option_expirations()`
- **Add**: Date range filtering
- **Simplify**: Validation loop (only check expirations from API)

### 3. Strategy Calculator Integration

**Current Flow**:
```
calculate_strategy()
  → find_next_three_expirations()
    → get_option_chain() [may return synthetic strikes]
  → calculate_strikes()
    → get_option_chain() [may return synthetic strikes]
  → create_orders()
```

**New Flow**:
```
calculate_strategy()
  → find_next_three_expirations()
    → get_option_expirations() [real dates only]
    → get_option_chain() [validate real options]
  → calculate_strikes()
    → get_option_chain() [real options only]
  → create_orders()
```

**Key Difference**: `get_option_chain()` will still have synthetic strike fallback for other use cases, but the strategy calculator will only call it with validated expirations that are known to have real options.

## Data Models

### Existing Models (No Changes)

- `OptionContract`: Represents a single option contract
- `ExpirationGroup`: Groups contracts by expiration
- `TieredCoveredCallPlan`: Complete strategy plan

### API Response Model (Internal)

```python
# Tradier expirations response
{
  "expirations": {
    "date": List[str]  # ISO format dates: "YYYY-MM-DD"
  }
}
```

## Error Handling

### Error Scenarios and Responses

1. **No expirations from Tradier API**
   - Raise: `ValueError("No option expirations available for {symbol}")`
   - Log: Error level with symbol and API response

2. **All expirations outside date range**
   - Raise: `ValueError("No expirations found between {min_date} and {max_date} for {symbol}")`
   - Log: Warning level with date range and available expirations

3. **No expirations with call options**
   - Raise: `ValueError("No expirations with call options found for {symbol}")`
   - Log: Warning level with expirations checked and call option counts

4. **Tradier API error (4xx/5xx)**
   - Raise: `ValueError("Tradier API error: {status_code} - {message}")`
   - Log: Error level with full request/response details

5. **Fewer than 3 valid expirations**
   - No error raised
   - Return available expirations (1 or 2)
   - Log: Info level indicating fewer than 3 expirations found

### Logging Strategy

**Info Level**:
- Number of expirations retrieved from API
- Number of expirations after date filtering
- Each expiration validation result (has call options: yes/no)
- Final list of validated expirations

**Warning Level**:
- Expiration excluded due to no call options
- Fewer than 3 expirations available
- All expirations outside date range

**Error Level**:
- API request failures
- JSON parsing errors
- No expirations available from API

## Testing Strategy

### Unit Tests

1. **TradierClient.get_option_expirations()**
   - Test successful API response parsing
   - Test empty expiration list handling
   - Test API error handling (4xx, 5xx)
   - Test date string to date object conversion
   - Test chronological sorting

2. **TieredCoveredCallCalculator.find_next_three_expirations()**
   - Test date range filtering
   - Test call option validation
   - Test returning fewer than 3 expirations
   - Test error propagation from get_option_expirations()
   - Test logging at each step

### Integration Tests

1. **End-to-End Strategy Calculation**
   - Test with symbol that has valid expirations (e.g., TLT)
   - Verify no synthetic strikes in final strategy
   - Verify all expirations have real call options
   - Test with different date ranges (min_days, max_days)

2. **API Integration**
   - Test against Tradier sandbox API
   - Verify correct endpoint usage
   - Verify authentication headers
   - Test with various symbols (stocks, ETFs)

### Manual Testing

1. **Compare old vs new behavior**
   - Run strategy calculation with current implementation
   - Run strategy calculation with new implementation
   - Verify new implementation excludes invalid dates (like Dec 30)
   - Verify new implementation is faster (fewer API calls)

2. **Edge cases**
   - Symbol with no options available
   - Symbol with only 1-2 expirations in range
   - Very narrow date range (min_days = max_days)
   - Very wide date range (max_days = 365)

## Performance Considerations

### API Call Reduction

**Current Implementation**:
- Iterates through ~90 dates
- Makes 1 API call per date to check for options
- Total: ~90 API calls to find 3 expirations

**New Implementation**:
- 1 API call to get all expirations
- 3-5 API calls to validate expirations
- Total: 4-6 API calls to find 3 expirations

**Improvement**: ~95% reduction in API calls

### Response Time

- Tradier expirations endpoint is fast (~100-200ms)
- Reduced API calls = faster strategy calculation
- Expected improvement: 5-10 seconds faster for typical strategy calculation

### Rate Limiting

- Tradier sandbox: 120 requests/minute
- Current implementation: Can hit rate limit with multiple symbols
- New implementation: Much less likely to hit rate limit

## Migration Plan

### Phase 1: Add New Method (Non-Breaking)
- Add `get_option_expirations()` to TradierClient
- Add unit tests for new method
- No changes to existing code

### Phase 2: Refactor Strategy Calculator
- Update `find_next_three_expirations()` to use new method
- Keep synthetic strike fallback in `get_option_chain()` for other use cases
- Add integration tests

### Phase 3: Validation
- Run side-by-side comparison tests
- Verify no synthetic strikes in strategy calculations
- Monitor logs for any issues

### Phase 4: Cleanup (Optional)
- Consider removing synthetic strike fallback if no longer needed
- Update documentation
- Remove old date iteration code

## Alternative Approaches Considered

### Alternative 1: Keep Date Iteration, Add Validation
- Continue iterating through dates
- Add stricter validation to exclude dates without real options
- **Rejected**: Still makes too many API calls, slower performance

### Alternative 2: Use Lumibot's Option Chain Method
- Use Lumibot's built-in option chain retrieval
- **Rejected**: Lumibot doesn't expose expiration endpoint, would still need date iteration

### Alternative 3: Cache Expirations
- Cache expiration dates for each symbol
- Refresh cache periodically
- **Rejected**: Adds complexity, expirations change infrequently but need to be current

## Open Questions

1. **Should we add caching for expirations?**
   - Pro: Faster repeated calculations for same symbol
   - Con: Adds complexity, cache invalidation logic needed
   - Decision: Not in initial implementation, can add later if needed

2. **Should we remove synthetic strikes entirely?**
   - Pro: Simpler code, forces use of real data
   - Con: Breaks other use cases (market closed scenarios)
   - Decision: Keep synthetic strikes, but don't use in strategy calculation

3. **How many expirations should we validate?**
   - Current: Check up to 5 to get 3 valid
   - Alternative: Check all filtered expirations
   - Decision: Check up to 5 (balance between thoroughness and API calls)
