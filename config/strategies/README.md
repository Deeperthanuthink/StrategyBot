# Strategy Configuration Files

This directory contains configuration files for each trading strategy supported by the stock screener.

## Purpose

Strategy configuration files allow you to:
- Define default screening filters per strategy
- Configure scoring weights for ranking stocks
- Set strategy-specific analysis parameters
- Customize strategies without modifying code

## File Format

Each strategy config file follows this structure:

```json
{
  "name": "Strategy Display Name",
  "description": "Brief description of the strategy",
  "default_filters": {
    // Screening criteria
    "min_market_cap": 2000000000,
    "min_volume": 1000000,
    // ... other filters
  },
  "scoring_weights": {
    // How to weight different factors when scoring stocks
    "iv_rank": 30,
    "technical_strength": 25,
    // ... other weights (should sum to 100)
  },
  "analysis_settings": {
    // Strategy-specific analysis parameters
    "default_dte": 45,
    // ... other settings
  }
}
```

## Available Strategies

### Put Credit Spread (PCS)
**File:** `pcs_config.json`

Screens for stocks suitable for selling put credit spreads. Focuses on:
- Large cap stocks with high liquidity
- Bullish technical indicators
- Elevated implied volatility
- No near-term earnings

### Covered Call
**File:** `covered_call_config.json`

Screens for stocks suitable for covered call strategies. Focuses on:
- Dividend-paying stocks
- Stable price action
- Moderate volatility for premium collection

### Iron Condor
**File:** `iron_condor_config.json`

Screens for stocks suitable for iron condor strategies. Focuses on:
- Range-bound stocks
- High liquidity for tight spreads
- Elevated IV for premium collection
- Low beta for stability

### Collar
**File:** `collar_config.json`

Screens for stocks suitable for collar strategies. Focuses on:
- Downside protection efficiency
- Cost-effective hedging
- Balanced risk/reward profiles

## Usage

### Loading Strategy Configs

```python
from screener.config import ConfigManager

config = ConfigManager()

# Load a specific strategy config
pcs_config = config.load_strategy_config("PCS")

# Get default filters
defaults = config.get_strategy_defaults("PCS")

# Get scoring weights
weights = config.get_strategy_scoring_weights("PCS")

# Get analysis settings
settings = config.get_strategy_analysis_settings("PCS")

# List all available strategies
strategies = config.list_available_strategies()
```

## Customization

You can customize strategy configs by:

1. **Editing existing configs**: Modify the JSON files directly
2. **Creating new strategies**: Add a new `{strategy_name}_config.json` file
3. **Using presets**: Save custom filter combinations as presets (stored separately in `user_presets.json`)

## File Naming Convention

Strategy config files must follow this naming pattern:
- `{strategy_name}_config.json` (e.g., `pcs_config.json`)
- Strategy name should be lowercase with underscores
- The system will automatically convert to uppercase when listing strategies

## Validation

Filter parameters in strategy configs are validated against acceptable ranges:
- `min_market_cap`, `max_market_cap`: 0 to 10 trillion
- `min_volume`, `max_volume`: 0 to 10 billion
- `price_min`, `price_max`: 0 to 10,000
- `rsi_min`, `rsi_max`: 0 to 100
- `beta_min`, `beta_max`: 0 to 10
- `iv_rank_min`, `iv_rank_max`: 0 to 100
- `weekly_perf_min`, `weekly_perf_max`: -100 to 100
- `earnings_buffer_days`: 0 to 365

## Notes

- Strategy configs are cached after first load for performance
- Invalid JSON files will be logged as errors and return None
- Missing strategy configs will return empty dictionaries for defaults/weights/settings
- The system gracefully handles missing or malformed config files
