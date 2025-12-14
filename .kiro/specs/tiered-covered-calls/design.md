# Design Document - Tiered Covered Calls Feature

## Overview

The Tiered Covered Calls feature implements an automated strategy for selling covered calls across multiple expiration dates with incrementally higher strike prices, plus automated rolling of in-the-money covered calls that are expiring. This design leverages the existing options trading infrastructure while adding new components for position querying, multi-expiration planning, tiered execution, and automated rolling.

## Architecture

### High-Level Flow
```
Initial Strategy: User Input (Symbol) → Position Query → Strategy Calculation → Preview → Execution → Results
Daily Rolling: Scheduled Run → Identify Expiring ITM Calls → Calculate Roll Options → Preview → Execute Rolls
```

### Component Integration
- **Position Service**: New component for querying long positions and existing short calls
- **Tiered Strategy Calculator**: New component for multi-expiration planning
- **Covered Call Roller**: New component for automated rolling of expiring ITM calls
- **Existing Broker Clients**: Reuse for order execution
- **Interactive Interface**: Extended for new strategy option and roll previews
- **Scheduler**: Integration with existing scheduling for daily roll checks

## Components and Interfaces

### 1. Position Query Service

**File**: `src/positions/position_service.py`

```python
@dataclass
class PositionSummary:
    symbol: str
    total_shares: int
    available_shares: int  # Shares not already covered by short calls
    current_price: float
    average_cost_basis: float  # Original cost basis per share
    total_cost_basis: float  # Total cost basis for all shares
    long_options: List[OptionPosition]
    existing_short_calls: List[OptionPosition]

class PositionService:
    def get_long_positions(self, symbol: str) -> PositionSummary
    def calculate_available_shares(self, positions: List[Position]) -> int
    def get_existing_short_calls(self, symbol: str) -> List[OptionPosition]
    def calculate_cost_basis(self, symbol: str) -> Tuple[float, float]  # Returns (avg_cost_per_share, total_cost)
    def get_cumulative_premium_collected(self, symbol: str) -> float
```

### 2. Tiered Covered Call Calculator

**File**: `src/strategy/tiered_covered_call_strategy.py`

```python
@dataclass
class TieredCoveredCallPlan:
    symbol: str
    current_price: float
    total_shares: int
    expiration_groups: List[ExpirationGroup]
    total_contracts: int
    estimated_premium: float
    original_cost_basis: float  # Original cost basis per share
    effective_cost_basis: float  # Cost basis after premium collection
    cost_basis_reduction: float  # Total premium collected per share

@dataclass
class ExpirationGroup:
    expiration_date: date
    strike_price: float
    num_contracts: int
    shares_used: int
    estimated_premium_per_contract: float

class TieredCoveredCallCalculator:
    def calculate_strategy(self, position_summary: PositionSummary) -> TieredCoveredCallPlan
    def find_next_three_expirations(self, symbol: str) -> List[date]
    def calculate_incremental_strikes(self, current_price: float, available_strikes: List[float]) -> List[float]
    def divide_shares_into_groups(self, total_shares: int, num_groups: int) -> List[int]
    def calculate_cost_basis_impact(self, position_summary: PositionSummary, estimated_premium: float) -> Tuple[float, float]
```

### 3. Cost Basis Tracking Service

**File**: `src/strategy/cost_basis_tracker.py`

```python
@dataclass
class CostBasisSummary:
    symbol: str
    total_shares: int
    original_cost_basis_per_share: float
    total_original_cost: float
    cumulative_premium_collected: float
    effective_cost_basis_per_share: float
    total_cost_basis_reduction: float
    cost_basis_reduction_percentage: float

@dataclass
class StrategyImpact:
    strategy_type: str  # 'initial_covered_calls' or 'roll'
    execution_date: date
    premium_collected: float
    contracts_executed: int
    cost_basis_reduction_per_share: float

class CostBasisTracker:
    def get_cost_basis_summary(self, symbol: str) -> CostBasisSummary
    def calculate_strategy_impact(self, symbol: str, premium_collected: float, shares_covered: int) -> StrategyImpact
    def update_cumulative_premium(self, symbol: str, additional_premium: float) -> None
    def get_strategy_history(self, symbol: str) -> List[StrategyImpact]
    def calculate_effective_cost_basis(self, original_cost: float, premium_collected: float, shares: int) -> float
```

### 4. Covered Call Rolling Service

**File**: `src/strategy/covered_call_roller.py`

```python
@dataclass
class RollOpportunity:
    symbol: str
    current_call: OptionPosition
    target_expiration: date
    target_strike: float
    estimated_credit: float
    current_price: float

@dataclass
class RollPlan:
    symbol: str
    current_price: float
    roll_opportunities: List[RollOpportunity]
    total_estimated_credit: float
    execution_time: datetime
    cumulative_premium_collected: float  # Total premium from all previous strategies
    cost_basis_impact: float  # Additional cost basis reduction from rolls

class CoveredCallRoller:
    def identify_expiring_itm_calls(self, symbol: str = None) -> List[OptionPosition]
    def calculate_roll_opportunities(self, expiring_calls: List[OptionPosition]) -> List[RollOpportunity]
    def find_best_roll_target(self, current_call: OptionPosition, current_price: float) -> Tuple[date, float]
    def estimate_roll_credit(self, current_call: OptionPosition, target_exp: date, target_strike: float) -> float
    def execute_roll_plan(self, roll_plan: RollPlan) -> List[OrderResult]
    def calculate_cumulative_cost_basis_impact(self, symbol: str, additional_premium: float) -> float
```

### 5. Extended Broker Interface

**File**: `src/brokers/base_client.py` (extension)

```python
# Add to existing BaseBrokerClient
@abstractmethod
def submit_multiple_covered_call_orders(self, orders: List[CoveredCallOrder]) -> List[OrderResult]

@abstractmethod  
def get_detailed_positions(self, symbol: str = None) -> List[DetailedPosition]

@abstractmethod
def get_option_chain_multiple_expirations(self, symbol: str, expirations: List[date]) -> Dict[date, List[OptionContract]]

@abstractmethod
def submit_roll_order(self, close_order: OptionOrder, open_order: OptionOrder) -> RollOrderResult

@abstractmethod
def get_expiring_short_calls(self, expiration_date: date, symbol: str = None) -> List[OptionPosition]
```

### 6. Interactive Interface Extension

**File**: `interactive.py` (extension)

```python
def select_tiered_covered_call_symbol() -> str
def display_position_summary(summary: PositionSummary) -> None
def display_tiered_strategy_preview(plan: TieredCoveredCallPlan) -> None
def confirm_tiered_execution(plan: TieredCoveredCallPlan) -> bool
def display_roll_opportunities(roll_plan: RollPlan) -> None
def confirm_roll_execution(roll_plan: RollPlan) -> bool
def display_cost_basis_summary(cost_basis_summary: CostBasisSummary) -> None
def display_strategy_impact(strategy_impact: StrategyImpact) -> None
```

## Data Models

### Enhanced Position Models

**File**: `src/models/position_models.py`

```python
@dataclass
class DetailedPosition:
    symbol: str
    quantity: int
    market_value: float
    average_cost: float
    unrealized_pnl: float
    position_type: str  # 'stock', 'long_call', 'long_put', 'short_call', 'short_put'

@dataclass
class OptionPosition(DetailedPosition):
    strike: float
    expiration: date
    option_type: str  # 'call' or 'put'
    
@dataclass
class CoveredCallOrder:
    symbol: str
    strike: float
    expiration: date
    quantity: int
    underlying_shares: int

@dataclass
class RollOrder:
    symbol: str
    close_strike: float
    close_expiration: date
    open_strike: float
    open_expiration: date
    quantity: int
    estimated_credit: float

@dataclass
class RollOrderResult:
    roll_order: RollOrder
    close_result: OrderResult
    open_result: OrderResult
    actual_credit: float
    success: bool

@dataclass
class StrategyExecutionResult:
    symbol: str
    execution_date: date
    strategy_type: str  # 'tiered_covered_calls' or 'roll'
    orders_executed: List[OrderResult]
    total_premium_collected: float
    contracts_executed: int
    cost_basis_impact: StrategyImpact
    success: bool
```

## Error Handling

### Position Query Errors
- **No positions found**: Display message, prevent execution
- **Broker API failure**: Retry with exponential backoff, fallback to manual input
- **Insufficient shares**: Adjust contract quantities, notify user

### Strategy Calculation Errors
- **No available expirations**: Use available expirations, warn user
- **Insufficient strikes**: Use highest available strikes, notify user
- **Uneven share division**: Allocate remainder to nearest expiration

### Execution Errors
- **Partial fills**: Track successful orders, report failures
- **Order rejection**: Log details, continue with remaining orders
- **Network failures**: Implement retry logic with user notification

## Testing Strategy

### Unit Tests
- Position query logic with mock broker responses
- Strike price calculation with various market conditions
- Share division algorithms with different quantities
- Error handling for edge cases

### Integration Tests
- End-to-end flow with paper trading accounts
- Multiple broker implementations (Tradier, Alpaca)
- Real option chain data validation
- Order execution verification

### Manual Testing Scenarios
- High-priced stocks (>$1000) with wide strike intervals
- Low-priced stocks (<$50) with narrow strike intervals
- Stocks with limited option liquidity
- Accounts with mixed position types

## Configuration

### New Configuration Options

**File**: `config/config.json` (extension)

```json
{
  "strategies": {
    "tcc": {
      "name": "Tiered Covered Calls",
      "min_shares_required": 300,
      "max_contracts_per_expiration": 10,
      "min_days_to_expiration": 7,
      "max_days_to_expiration": 60,
      "strike_increment_minimum": 2.50,
      "premium_threshold_per_contract": 0.50
    }
  }
}
```

### Strategy Parameters
- **min_shares_required**: Minimum shares needed to execute strategy (default: 300 for 3 groups)
- **max_contracts_per_expiration**: Safety limit per expiration (default: 10)
- **min/max_days_to_expiration**: Expiration date filtering
- **strike_increment_minimum**: Minimum difference between strikes
- **premium_threshold_per_contract**: Minimum premium to consider execution
- **roll_enabled**: Enable automatic rolling of expiring ITM calls (default: true)
- **roll_execution_time**: Time of day to check for roll opportunities (default: "15:30")
- **min_roll_credit**: Minimum credit required to execute a roll (default: 0.10)
- **max_roll_days_out**: Maximum days to expiration for roll targets (default: 45)

## Implementation Phases

### Phase 1: Core Position Querying
- Implement PositionService
- Add broker methods for detailed positions
- Create position summary display

### Phase 2: Strategy Calculation
- Implement TieredCoveredCallCalculator
- Add expiration and strike selection logic
- Create strategy preview interface

### Phase 3: Order Execution
- Implement multiple order submission
- Add execution tracking and reporting
- Integrate with existing logging system

### Phase 4: Interactive Integration
- Add "tcc" option to strategy menu
- Implement user flow for symbol selection and confirmation
- Add results display and error handling

## Security Considerations

- **Position Validation**: Always verify sufficient shares before order submission
- **Order Limits**: Implement maximum contract limits to prevent accidental large orders
- **Confirmation Required**: Require explicit user confirmation for all executions
- **Audit Trail**: Log all position queries and order submissions for compliance

## Performance Considerations

- **Batch API Calls**: Query multiple expirations in single API call where possible
- **Caching**: Cache option chain data for short periods to reduce API calls
- **Parallel Execution**: Submit orders for different expirations concurrently
- **Rate Limiting**: Respect broker API rate limits with appropriate delays