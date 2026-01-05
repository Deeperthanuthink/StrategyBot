"""Strategy discovery and registration mechanism."""

import importlib
import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Dict, Type
from screener.strategies.base import StrategyModule


def discover_strategies(strategies_dir: str = None) -> Dict[str, StrategyModule]:
    """
    Automatically discover and register strategy modules.
    
    Scans the strategies directory for Python files matching the pattern
    '*_strategy.py' and attempts to import and instantiate strategy classes
    that inherit from StrategyModule.
    
    Args:
        strategies_dir: Optional path to strategies directory. 
                       If None, uses the default screener/strategies directory.
    
    Returns:
        Dictionary mapping strategy names to instantiated StrategyModule objects
        
    Example:
        >>> strategies = discover_strategies()
        >>> print(strategies.keys())
        dict_keys(['Put Credit Spread', 'Covered Call', ...])
    """
    strategies = {}
    
    # Determine the strategies directory
    if strategies_dir is None:
        # Default to the strategies directory relative to this file
        strategies_path = Path(__file__).parent
        use_standard_import = True
    else:
        strategies_path = Path(strategies_dir)
        use_standard_import = False
    
    # Scan for strategy files
    for file_path in strategies_path.glob("*_strategy.py"):
        try:
            if use_standard_import:
                # Use standard import for modules in the package
                module_name = f"screener.strategies.{file_path.stem}"
                module = importlib.import_module(module_name)
            else:
                # Use dynamic import for arbitrary directories (e.g., testing)
                module_name = file_path.stem
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
            
            # Look for classes that inherit from StrategyModule
            for name, obj in inspect.getmembers(module, inspect.isclass):
                # Check if it's a StrategyModule subclass (but not StrategyModule itself)
                if (issubclass(obj, StrategyModule) and 
                    obj is not StrategyModule and
                    obj.__module__ == module_name):
                    
                    # Instantiate the strategy
                    strategy_instance = obj()
                    
                    # Register by strategy name
                    strategies[strategy_instance.name] = strategy_instance
                    
        except Exception as e:
            # Log the error but continue discovering other strategies
            print(f"Warning: Failed to load strategy from {file_path}: {e}")
            continue
    
    return strategies


def get_strategy(strategy_name: str, strategies_dir: str = None) -> StrategyModule:
    """
    Get a specific strategy by name.
    
    Args:
        strategy_name: Name of the strategy to retrieve
        strategies_dir: Optional path to strategies directory
        
    Returns:
        StrategyModule instance
        
    Raises:
        KeyError: If strategy with given name is not found
    """
    strategies = discover_strategies(strategies_dir)
    
    if strategy_name not in strategies:
        available = ", ".join(strategies.keys())
        raise KeyError(
            f"Strategy '{strategy_name}' not found. "
            f"Available strategies: {available}"
        )
    
    return strategies[strategy_name]


def list_available_strategies(strategies_dir: str = None) -> list[str]:
    """
    List all available strategy names.
    
    Args:
        strategies_dir: Optional path to strategies directory
        
    Returns:
        List of strategy names
    """
    strategies = discover_strategies(strategies_dir)
    return list(strategies.keys())
