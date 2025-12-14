# Position Management Module

This module provides infrastructure for querying and managing trading positions, specifically designed to support the tiered covered calls strategy.

## Components

### Data Models (`models.py`)

- **DetailedPosition**: Base class for representing detailed position information
- **OptionPosition**: Extends DetailedPosition for option-specific data (strike, expiration, etc.)
- **PositionSummary**: Aggregated view of all positions for a symbol
- **CoveredCallOrder**: Specification for covered call orders

### Position Service (`position_service.py`)

- **PositionService**: Main service class for position querying and management
  - `get_long_positions(symbol)`: Retrieves comprehensive position summary for a symbol
  - `calculate_available_shares(positions)`: Calculates shares available for covered calls
  - `get_existing_short_calls(symbol)`: Identifies existing covered call positions

## Usage Example

```python
from src.positions import PositionService, PositionSummary
from src.brokers.broker_factory import BrokerFactory

# Initialize broker client and position service
broker_client = BrokerFactory.create_client("tradier", config)
position_service = PositionService(broker_client, logger)

# Get position summary for a symbol
summary = position_service.get_long_positions("AAPL")
print(f"Total shares: {summary.total_shares}")
print(f"Available for covered calls: {summary.available_shares}")
print(f"Current price: ${summary.current_price:.2f}")
```

## Future Enhancements

- Option position querying (requires broker client extensions)
- Real-time position updates
- Position change notifications
- Advanced position analytics