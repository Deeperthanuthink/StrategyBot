# Strategy Stock Screener

A modular stock screening system with Marimo notebook interface and Finviz Elite integration for options trading strategies.

## Directory Structure

```
screener/
├── __init__.py              # Package initialization
├── strategies/              # Strategy plugin modules
│   └── __init__.py
├── analysis/                # Analysis engine for calculations
│   └── __init__.py
├── storage/                 # Data persistence layer
│   └── __init__.py
├── config/                  # Configuration management
│   └── __init__.py
├── finviz/                  # Finviz Elite integration
│   └── __init__.py
└── core/                    # Core screening engine
    └── __init__.py
```

## Configuration

Configuration is stored in `config/screener_config.json`. See the design document for details.

## Data Storage

Screening results are stored in `data/screener_results/` with the following structure:
- Individual screening results: `YYYY-MM-DD_strategy_HHMMSS.json`
- CSV exports: `YYYY-MM-DD_strategy_HHMMSS.csv`
- History log: `data/screener_history.json`
- User presets: `data/user_presets.json`

## Usage

The main entry point is the Marimo notebook `screener.py` (to be created in task 12).

## Requirements

See `requirements.txt` for all dependencies. Key dependencies:
- marimo: Interactive notebook interface
- finvizfinance: Finviz Elite integration
- hypothesis: Property-based testing
- pandas, numpy, scipy: Data analysis and calculations
