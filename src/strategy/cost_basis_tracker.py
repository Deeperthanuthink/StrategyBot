"""Cost basis tracking functionality for covered call strategies."""

import json
import os
from dataclasses import dataclass, asdict
from datetime import date, datetime
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path

from ..logging.bot_logger import BotLogger
from ..logging.logger_adapter import LoggerAdapter


@dataclass
class CostBasisSummary:
    """Comprehensive cost basis summary for a symbol."""
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
    """Impact of a strategy execution on cost basis."""
    strategy_type: str  # 'initial_covered_calls' or 'roll'
    execution_date: date
    premium_collected: float
    contracts_executed: int
    cost_basis_reduction_per_share: float
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['execution_date'] = self.execution_date.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'StrategyImpact':
        """Create from dictionary for JSON deserialization."""
        data = data.copy()
        data['execution_date'] = date.fromisoformat(data['execution_date'])
        return cls(**data)


@dataclass
class CostBasisData:
    """Internal data structure for cost basis persistence."""
    symbol: str
    original_cost_basis_per_share: float
    total_shares: int
    cumulative_premium_collected: float
    strategy_history: List[StrategyImpact]
    last_updated: datetime
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'symbol': self.symbol,
            'original_cost_basis_per_share': self.original_cost_basis_per_share,
            'total_shares': self.total_shares,
            'cumulative_premium_collected': self.cumulative_premium_collected,
            'strategy_history': [impact.to_dict() for impact in self.strategy_history],
            'last_updated': self.last_updated.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CostBasisData':
        """Create from dictionary for JSON deserialization."""
        return cls(
            symbol=data['symbol'],
            original_cost_basis_per_share=data['original_cost_basis_per_share'],
            total_shares=data['total_shares'],
            cumulative_premium_collected=data['cumulative_premium_collected'],
            strategy_history=[StrategyImpact.from_dict(impact) for impact in data['strategy_history']],
            last_updated=datetime.fromisoformat(data['last_updated'])
        )


class CostBasisTracker:
    """Service for tracking cost basis impact of covered call strategies."""
    
    def __init__(self, data_directory: str = "data", logger: Optional[Any] = None):
        """Initialize the cost basis tracker.
        
        Args:
            data_directory: Directory to store cost basis data files
            logger: Optional logger for tracking operations (BotLogger or any compatible logger)
        """
        self.data_directory = Path(data_directory)
        
        # Wrap logger with adapter if it doesn't have the expected interface
        if logger is not None:
            if hasattr(logger, 'log_info') and hasattr(logger, 'log_error') and hasattr(logger, 'log_warning'):
                # Logger already has the expected interface (BotLogger)
                self.logger = logger
            else:
                # Wrap with adapter to provide compatible interface
                self.logger = LoggerAdapter(logger)
        else:
            self.logger = None
        
        # Ensure data directory exists
        self.data_directory.mkdir(exist_ok=True)
        
        # File path for cost basis data
        self.data_file = self.data_directory / "cost_basis_data.json"
        
        # In-memory cache of cost basis data
        self._data_cache: Dict[str, CostBasisData] = {}
        self._load_data()
    
    def _load_data(self) -> None:
        """Load cost basis data from persistent storage."""
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                
                self._data_cache = {}
                for symbol, symbol_data in data.items():
                    self._data_cache[symbol] = CostBasisData.from_dict(symbol_data)
                
                if self.logger:
                    self.logger.log_info(
                        f"Loaded cost basis data for {len(self._data_cache)} symbols",
                        {"symbols": list(self._data_cache.keys())}
                    )
                    
            except Exception as e:
                if self.logger:
                    self.logger.log_error(f"Error loading cost basis data: {str(e)}", e)
                self._data_cache = {}
        else:
            self._data_cache = {}
            if self.logger:
                self.logger.log_info("No existing cost basis data file found, starting fresh")
    
    def _save_data(self) -> None:
        """Save cost basis data to persistent storage."""
        try:
            data = {}
            for symbol, cost_data in self._data_cache.items():
                data[symbol] = cost_data.to_dict()
            
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            if self.logger:
                self.logger.log_info(
                    f"Saved cost basis data for {len(self._data_cache)} symbols",
                    {"data_file": str(self.data_file)}
                )
                
        except Exception as e:
            if self.logger:
                self.logger.log_error(f"Error saving cost basis data: {str(e)}", e)
            raise RuntimeError(f"Failed to save cost basis data: {str(e)}") from e
    
    def get_cost_basis_summary(self, symbol: str) -> CostBasisSummary:
        """Retrieve comprehensive cost basis information for a symbol.
        
        Args:
            symbol: Stock symbol to get cost basis summary for
            
        Returns:
            CostBasisSummary with current cost basis information
            
        Raises:
            ValueError: If symbol data is not found or invalid
        """
        symbol = symbol.upper().strip()
        
        if self.logger:
            self.logger.log_info(f"Getting cost basis summary for {symbol}")
        
        if symbol not in self._data_cache:
            if self.logger:
                self.logger.log_info(f"No cost basis data found for {symbol}")
            raise ValueError(f"No cost basis data found for {symbol}. Initialize with calculate_strategy_impact first.")
        
        try:
            data = self._data_cache[symbol]
            
            # Calculate effective cost basis
            effective_cost_basis_per_share = self.calculate_effective_cost_basis(
                data.original_cost_basis_per_share,
                data.cumulative_premium_collected,
                data.total_shares
            )
            
            # Calculate total cost basis reduction
            total_cost_basis_reduction = data.cumulative_premium_collected
            
            # Calculate reduction percentage
            if data.total_shares > 0 and data.original_cost_basis_per_share > 0:
                cost_basis_reduction_percentage = (
                    (data.cumulative_premium_collected / data.total_shares) / 
                    data.original_cost_basis_per_share * 100
                )
            else:
                cost_basis_reduction_percentage = 0.0
            
            summary = CostBasisSummary(
                symbol=symbol,
                total_shares=data.total_shares,
                original_cost_basis_per_share=data.original_cost_basis_per_share,
                total_original_cost=data.original_cost_basis_per_share * data.total_shares,
                cumulative_premium_collected=data.cumulative_premium_collected,
                effective_cost_basis_per_share=effective_cost_basis_per_share,
                total_cost_basis_reduction=total_cost_basis_reduction,
                cost_basis_reduction_percentage=cost_basis_reduction_percentage
            )
            
            if self.logger:
                self.logger.log_info(
                    f"Cost basis summary for {symbol}",
                    {
                        "symbol": symbol,
                        "original_cost_basis": data.original_cost_basis_per_share,
                        "effective_cost_basis": effective_cost_basis_per_share,
                        "cumulative_premium": data.cumulative_premium_collected,
                        "reduction_percentage": cost_basis_reduction_percentage
                    }
                )
            
            return summary
            
        except Exception as e:
            error_msg = f"Error getting cost basis summary for {symbol}: {str(e)}"
            if self.logger:
                self.logger.log_error(error_msg, e, {"symbol": symbol})
            raise ValueError(error_msg) from e
    
    def calculate_strategy_impact(self, symbol: str, premium_collected: float, 
                                shares_covered: int, strategy_type: str = "initial_covered_calls",
                                original_cost_basis_per_share: Optional[float] = None) -> StrategyImpact:
        """Calculate and record the impact of a strategy execution on cost basis.
        
        Args:
            symbol: Stock symbol
            premium_collected: Total premium collected from the strategy
            shares_covered: Number of shares covered by the strategy
            strategy_type: Type of strategy ('initial_covered_calls' or 'roll')
            original_cost_basis_per_share: Original cost basis per share (required for new symbols)
            
        Returns:
            StrategyImpact object with calculated impact
            
        Raises:
            ValueError: If required parameters are missing or invalid
        """
        symbol = symbol.upper().strip()
        
        if premium_collected < 0:
            raise ValueError(f"Premium collected cannot be negative: {premium_collected}")
        
        if shares_covered <= 0:
            raise ValueError(f"Shares covered must be positive: {shares_covered}")
        
        if strategy_type not in ["initial_covered_calls", "roll"]:
            raise ValueError(f"Invalid strategy type: {strategy_type}")
        
        if self.logger:
            self.logger.log_info(
                f"Calculating strategy impact for {symbol}",
                {
                    "symbol": symbol,
                    "premium_collected": premium_collected,
                    "shares_covered": shares_covered,
                    "strategy_type": strategy_type
                }
            )
        
        try:
            # Initialize data for new symbols
            if symbol not in self._data_cache:
                if original_cost_basis_per_share is None:
                    raise ValueError(f"Original cost basis per share required for new symbol {symbol}")
                
                if original_cost_basis_per_share <= 0:
                    raise ValueError(f"Original cost basis per share must be positive: {original_cost_basis_per_share}")
                
                self._data_cache[symbol] = CostBasisData(
                    symbol=symbol,
                    original_cost_basis_per_share=original_cost_basis_per_share,
                    total_shares=shares_covered,
                    cumulative_premium_collected=0.0,
                    strategy_history=[],
                    last_updated=datetime.now()
                )
                
                if self.logger:
                    self.logger.log_info(
                        f"Initialized cost basis tracking for {symbol}",
                        {
                            "symbol": symbol,
                            "original_cost_basis": original_cost_basis_per_share,
                            "total_shares": shares_covered
                        }
                    )
            
            # Calculate cost basis reduction per share
            cost_basis_reduction_per_share = premium_collected / shares_covered if shares_covered > 0 else 0.0
            
            # Create strategy impact record
            impact = StrategyImpact(
                strategy_type=strategy_type,
                execution_date=date.today(),
                premium_collected=premium_collected,
                contracts_executed=shares_covered // 100,  # Assuming 100 shares per contract
                cost_basis_reduction_per_share=cost_basis_reduction_per_share
            )
            
            # Update cumulative data
            data = self._data_cache[symbol]
            data.cumulative_premium_collected += premium_collected
            data.strategy_history.append(impact)
            data.last_updated = datetime.now()
            
            # Update total shares if this is a new strategy execution
            if strategy_type == "initial_covered_calls":
                data.total_shares = max(data.total_shares, shares_covered)
            
            # Save updated data
            self._save_data()
            
            if self.logger:
                self.logger.log_info(
                    f"Strategy impact calculated for {symbol}",
                    {
                        "symbol": symbol,
                        "strategy_type": strategy_type,
                        "premium_collected": premium_collected,
                        "cost_basis_reduction_per_share": cost_basis_reduction_per_share,
                        "cumulative_premium": data.cumulative_premium_collected
                    }
                )
            
            return impact
            
        except Exception as e:
            error_msg = f"Error calculating strategy impact for {symbol}: {str(e)}"
            if self.logger:
                self.logger.log_error(error_msg, e, {"symbol": symbol})
            raise ValueError(error_msg) from e
    
    def calculate_effective_cost_basis(self, original_cost: float, premium_collected: float, shares: int) -> float:
        """Calculate effective cost basis after accounting for premium collection.
        
        Args:
            original_cost: Original cost basis per share
            premium_collected: Total premium collected
            shares: Number of shares
            
        Returns:
            Effective cost basis per share
            
        Raises:
            ValueError: If parameters are invalid
        """
        if original_cost <= 0:
            raise ValueError(f"Original cost must be positive: {original_cost}")
        
        if premium_collected < 0:
            raise ValueError(f"Premium collected cannot be negative: {premium_collected}")
        
        if shares <= 0:
            raise ValueError(f"Shares must be positive: {shares}")
        
        # Effective cost basis = original cost - (premium collected / shares)
        premium_per_share = premium_collected / shares
        effective_cost_basis = original_cost - premium_per_share
        
        # Ensure effective cost basis doesn't go negative
        return max(0.0, effective_cost_basis)
    
    def update_cumulative_premium(self, symbol: str, additional_premium: float, 
                                strategy_type: str = "roll", contracts_executed: int = 0) -> None:
        """Update cumulative premium collected for a symbol.
        
        This method updates the cumulative premium and creates a corresponding strategy impact record
        to maintain data integrity.
        
        Args:
            symbol: Stock symbol
            additional_premium: Additional premium to add to cumulative total
            strategy_type: Type of strategy that generated the premium (default: "roll")
            contracts_executed: Number of contracts executed (default: 0 for unknown)
            
        Raises:
            ValueError: If symbol not found or premium is negative
        """
        symbol = symbol.upper().strip()
        
        if additional_premium < 0:
            raise ValueError(f"Additional premium cannot be negative: {additional_premium}")
        
        if symbol not in self._data_cache:
            raise ValueError(f"No cost basis data found for {symbol}. Initialize with calculate_strategy_impact first.")
        
        if self.logger:
            self.logger.log_info(
                f"Updating cumulative premium for {symbol}",
                {"symbol": symbol, "additional_premium": additional_premium, "strategy_type": strategy_type}
            )
        
        try:
            data = self._data_cache[symbol]
            
            # Calculate cost basis reduction per share
            cost_basis_reduction_per_share = additional_premium / data.total_shares if data.total_shares > 0 else 0.0
            
            # Create strategy impact record to maintain data integrity
            impact = StrategyImpact(
                strategy_type=strategy_type,
                execution_date=date.today(),
                premium_collected=additional_premium,
                contracts_executed=contracts_executed,
                cost_basis_reduction_per_share=cost_basis_reduction_per_share
            )
            
            # Update cumulative data
            data.cumulative_premium_collected += additional_premium
            data.strategy_history.append(impact)
            data.last_updated = datetime.now()
            
            self._save_data()
            
            if self.logger:
                self.logger.log_info(
                    f"Updated cumulative premium for {symbol}",
                    {
                        "symbol": symbol,
                        "additional_premium": additional_premium,
                        "new_cumulative_premium": data.cumulative_premium_collected,
                        "strategy_type": strategy_type
                    }
                )
                
        except Exception as e:
            error_msg = f"Error updating cumulative premium for {symbol}: {str(e)}"
            if self.logger:
                self.logger.log_error(error_msg, e, {"symbol": symbol})
            raise ValueError(error_msg) from e
    
    def get_strategy_history(self, symbol: str) -> List[StrategyImpact]:
        """Retrieve historical strategy executions and their impact.
        
        Args:
            symbol: Stock symbol to get history for
            
        Returns:
            List of StrategyImpact objects sorted by execution date
            
        Raises:
            ValueError: If symbol not found
        """
        symbol = symbol.upper().strip()
        
        if symbol not in self._data_cache:
            if self.logger:
                self.logger.log_info(f"No strategy history found for {symbol}")
            return []
        
        try:
            data = self._data_cache[symbol]
            
            # Return copy of history sorted by execution date
            history = sorted(data.strategy_history, key=lambda x: x.execution_date)
            
            if self.logger:
                self.logger.log_info(
                    f"Retrieved strategy history for {symbol}",
                    {
                        "symbol": symbol,
                        "history_count": len(history),
                        "date_range": f"{history[0].execution_date} to {history[-1].execution_date}" if history else "empty"
                    }
                )
            
            return history
            
        except Exception as e:
            error_msg = f"Error getting strategy history for {symbol}: {str(e)}"
            if self.logger:
                self.logger.log_error(error_msg, e, {"symbol": symbol})
            raise ValueError(error_msg) from e
    
    def get_all_tracked_symbols(self) -> List[str]:
        """Get list of all symbols being tracked.
        
        Returns:
            List of symbol strings
        """
        return list(self._data_cache.keys())
    
    def remove_symbol_data(self, symbol: str) -> bool:
        """Remove all cost basis data for a symbol.
        
        Args:
            symbol: Stock symbol to remove
            
        Returns:
            True if data was removed, False if symbol was not found
        """
        symbol = symbol.upper().strip()
        
        if symbol in self._data_cache:
            del self._data_cache[symbol]
            self._save_data()
            
            if self.logger:
                self.logger.log_info(f"Removed cost basis data for {symbol}")
            
            return True
        else:
            if self.logger:
                self.logger.log_info(f"No cost basis data found to remove for {symbol}")
            return False
    
    def validate_data_integrity(self, symbol: str) -> Tuple[bool, List[str]]:
        """Validate data integrity for a symbol's cost basis tracking.
        
        This method ensures that:
        1. Cumulative premium matches sum of strategy history
        2. All strategy impacts have valid dates and amounts
        3. Cost basis calculations are consistent
        
        Args:
            symbol: Stock symbol to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        symbol = symbol.upper().strip()
        errors = []
        
        if symbol not in self._data_cache:
            errors.append(f"No data found for symbol {symbol}")
            return False, errors
        
        try:
            data = self._data_cache[symbol]
            
            # Validate basic data
            if data.original_cost_basis_per_share <= 0:
                errors.append(f"Invalid original cost basis: {data.original_cost_basis_per_share}")
            
            if data.total_shares <= 0:
                errors.append(f"Invalid total shares: {data.total_shares}")
            
            if data.cumulative_premium_collected < 0:
                errors.append(f"Invalid cumulative premium: {data.cumulative_premium_collected}")
            
            # Validate strategy history consistency
            calculated_premium = sum(impact.premium_collected for impact in data.strategy_history)
            if abs(calculated_premium - data.cumulative_premium_collected) > 0.01:  # Allow small floating point differences
                errors.append(
                    f"Premium mismatch: cumulative={data.cumulative_premium_collected}, "
                    f"calculated from history={calculated_premium}"
                )
            
            # Validate individual strategy impacts
            for i, impact in enumerate(data.strategy_history):
                if impact.premium_collected < 0:
                    errors.append(f"Strategy {i}: negative premium {impact.premium_collected}")
                
                if impact.contracts_executed < 0:
                    errors.append(f"Strategy {i}: negative contracts {impact.contracts_executed}")
                
                if impact.cost_basis_reduction_per_share < 0:
                    errors.append(f"Strategy {i}: negative cost basis reduction {impact.cost_basis_reduction_per_share}")
                
                if impact.execution_date > date.today():
                    errors.append(f"Strategy {i}: future execution date {impact.execution_date}")
            
            # Validate cost basis calculations
            try:
                effective_cost_basis = self.calculate_effective_cost_basis(
                    data.original_cost_basis_per_share,
                    data.cumulative_premium_collected,
                    data.total_shares
                )
                
                if effective_cost_basis < 0:
                    errors.append(f"Negative effective cost basis: {effective_cost_basis}")
                    
            except Exception as e:
                errors.append(f"Error calculating effective cost basis: {str(e)}")
            
            is_valid = len(errors) == 0
            
            if self.logger:
                if is_valid:
                    self.logger.log_info(f"Data integrity validation passed for {symbol}")
                else:
                    self.logger.log_warning(
                        f"Data integrity validation failed for {symbol}",
                        {"symbol": symbol, "errors": errors}
                    )
            
            return is_valid, errors
            
        except Exception as e:
            error_msg = f"Error validating data integrity for {symbol}: {str(e)}"
            if self.logger:
                self.logger.log_error(error_msg, e, {"symbol": symbol})
            errors.append(error_msg)
            return False, errors
    
    def backup_data(self, backup_path: Optional[str] = None) -> str:
        """Create a backup of all cost basis data.
        
        Args:
            backup_path: Optional custom backup file path
            
        Returns:
            Path to the backup file
            
        Raises:
            RuntimeError: If backup creation fails
        """
        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = str(self.data_directory / f"cost_basis_backup_{timestamp}.json")
        
        try:
            # Create backup data
            backup_data = {
                'backup_timestamp': datetime.now().isoformat(),
                'symbols': {}
            }
            
            for symbol, data in self._data_cache.items():
                backup_data['symbols'][symbol] = data.to_dict()
            
            # Write backup file
            with open(backup_path, 'w') as f:
                json.dump(backup_data, f, indent=2)
            
            if self.logger:
                self.logger.log_info(
                    f"Created cost basis data backup",
                    {"backup_path": backup_path, "symbols_count": len(self._data_cache)}
                )
            
            return backup_path
            
        except Exception as e:
            error_msg = f"Error creating backup: {str(e)}"
            if self.logger:
                self.logger.log_error(error_msg, e)
            raise RuntimeError(error_msg) from e
    
    def restore_from_backup(self, backup_path: str, merge: bool = False) -> None:
        """Restore cost basis data from a backup file.
        
        Args:
            backup_path: Path to the backup file
            merge: If True, merge with existing data. If False, replace all data.
            
        Raises:
            RuntimeError: If restore operation fails
        """
        if not os.path.exists(backup_path):
            raise RuntimeError(f"Backup file not found: {backup_path}")
        
        try:
            with open(backup_path, 'r') as f:
                backup_data = json.load(f)
            
            if 'symbols' not in backup_data:
                raise RuntimeError("Invalid backup file format: missing 'symbols' key")
            
            if not merge:
                self._data_cache = {}
            
            # Restore symbol data
            restored_count = 0
            for symbol, symbol_data in backup_data['symbols'].items():
                self._data_cache[symbol] = CostBasisData.from_dict(symbol_data)
                restored_count += 1
            
            # Save restored data
            self._save_data()
            
            if self.logger:
                self.logger.log_info(
                    f"Restored cost basis data from backup",
                    {
                        "backup_path": backup_path,
                        "restored_symbols": restored_count,
                        "merge_mode": merge,
                        "backup_timestamp": backup_data.get('backup_timestamp', 'unknown')
                    }
                )
                
        except Exception as e:
            error_msg = f"Error restoring from backup: {str(e)}"
            if self.logger:
                self.logger.log_error(error_msg, e)
            raise RuntimeError(error_msg) from e