"""Position service for querying and managing trading positions."""

from typing import List, Optional, Tuple
from datetime import date
import logging

from ..brokers.base_client import BaseBrokerClient, Position
from .models import DetailedPosition, OptionPosition, PositionSummary, CoveredCallOrder
from .validation import PositionValidator, ValidationResult, PositionValidationSummary
from ..strategy.cost_basis_tracker import CostBasisTracker
from ..logging.bot_logger import BotLogger


class PositionService:
    """Service for querying and managing trading positions."""
    
    def __init__(self, broker_client: BaseBrokerClient, logger: Optional[BotLogger] = None, 
                 cost_basis_tracker: Optional[CostBasisTracker] = None):
        """Initialize the position service.
        
        Args:
            broker_client: The broker client to use for API calls
            logger: Optional logger for tracking operations
            cost_basis_tracker: Optional cost basis tracker for cost basis calculations
        """
        self.broker_client = broker_client
        self.logger = logger
        self.validator = PositionValidator(logger)
        self.cost_basis_tracker = cost_basis_tracker or CostBasisTracker(logger=logger)
    
    def get_long_positions(self, symbol: str) -> PositionSummary:
        """Retrieve all positions for a symbol and create a position summary.
        
        Args:
            symbol: The stock symbol to query positions for
            
        Returns:
            PositionSummary with current holdings and available shares
            
        Raises:
            ValueError: If symbol is invalid or no positions found
        """
        if not symbol or not symbol.strip():
            raise ValueError("Symbol cannot be empty")
        
        symbol = symbol.upper().strip()
        
        try:
            # Get current stock price
            current_price = self.broker_client.get_current_price(symbol)
            
            # Get stock position
            stock_position = self.broker_client.get_position(symbol)
            stock_shares = stock_position.quantity if stock_position else 0
            
            # Get detailed positions to include option positions
            try:
                detailed_positions = self.broker_client.get_detailed_positions(symbol)
                
                # Separate long options and short calls
                long_options: List[OptionPosition] = []
                existing_short_calls: List[OptionPosition] = []
                
                for pos in detailed_positions:
                    if isinstance(pos, OptionPosition):
                        if pos.position_type == 'long_call' and pos.option_type == 'call':
                            long_options.append(pos)
                        elif pos.position_type == 'short_call' and pos.option_type == 'call':
                            existing_short_calls.append(pos)
                        elif pos.position_type in ['long_put', 'short_put']:
                            # Include puts in long_options list for tracking
                            long_options.append(pos)
                
            except Exception as e:
                # If detailed positions not available, fall back to empty lists
                if self.logger:
                    self.logger.log_warning(f"Could not retrieve detailed positions for {symbol}: {str(e)}")
                long_options: List[OptionPosition] = []
                existing_short_calls: List[OptionPosition] = []
            
            # Calculate equivalent shares from long call options
            # Each long call contract represents 100 shares
            long_call_equivalent_shares = sum(
                pos.quantity * 100 for pos in long_options 
                if pos.option_type == 'call' and pos.position_type == 'long_call'
            )
            
            # Total shares = stock shares + equivalent shares from long calls
            total_shares = stock_shares + long_call_equivalent_shares
            
            if self.logger:
                if long_call_equivalent_shares > 0:
                    self.logger.log_info(
                        f"Found {stock_shares} stock shares + {long_call_equivalent_shares} equivalent shares from long calls = {total_shares} total shares of {symbol} at ${current_price:.2f}"
                    )
                else:
                    self.logger.log_info(f"Found {total_shares} shares of {symbol} at ${current_price:.2f}")
            
            # Calculate available shares (total shares minus shares covered by existing short calls)
            shares_covered_by_calls = sum(
                abs(option.quantity) * 100 for option in existing_short_calls 
                if option.option_type == 'call' and option.position_type == 'short_call'
            )
            available_shares = max(0, total_shares - shares_covered_by_calls)
            
            if self.logger:
                self.logger.log_info(f"Available shares for {symbol}: {available_shares} (covered by calls: {shares_covered_by_calls})")
            
            # Get cost basis information
            try:
                avg_cost_basis, total_cost_basis = self._calculate_cost_basis_with_data(symbol, current_price, total_shares, stock_position)
                cumulative_premium = self.get_cumulative_premium_collected(symbol)
                
                # Calculate effective cost basis if we have the data
                effective_cost_basis_per_share = None
                if avg_cost_basis and total_shares > 0:
                    effective_cost_basis_per_share = self.cost_basis_tracker.calculate_effective_cost_basis(
                        avg_cost_basis, cumulative_premium, total_shares
                    )
                
                if self.logger:
                    self.logger.log_info(
                        f"Cost basis information for {symbol}",
                        {
                            "avg_cost_basis": avg_cost_basis,
                            "total_cost_basis": total_cost_basis,
                            "cumulative_premium": cumulative_premium,
                            "effective_cost_basis": effective_cost_basis_per_share
                        }
                    )
                
            except Exception as e:
                # Don't fail the entire position query if cost basis calculation fails
                if self.logger:
                    self.logger.log_warning(f"Could not calculate cost basis for {symbol}: {str(e)}")
                avg_cost_basis = None
                total_cost_basis = None
                cumulative_premium = None
                effective_cost_basis_per_share = None
            
            return PositionSummary(
                symbol=symbol,
                total_shares=total_shares,
                available_shares=available_shares,
                current_price=current_price,
                long_options=long_options,
                existing_short_calls=existing_short_calls,
                average_cost_basis=avg_cost_basis,
                total_cost_basis=total_cost_basis,
                cumulative_premium_collected=cumulative_premium,
                effective_cost_basis_per_share=effective_cost_basis_per_share
            )
            
        except Exception as e:
            error_msg = f"Error retrieving positions for {symbol}: {str(e)}"
            if self.logger:
                self.logger.log_error(error_msg, e)
            raise RuntimeError(error_msg) from e
    
    def calculate_available_shares(self, positions: List[Position]) -> int:
        """Calculate shares available for covered call writing.
        
        Args:
            positions: List of Position objects for a symbol
            
        Returns:
            Number of shares available for covered calls
        """
        total_stock_shares = 0
        
        # Sum up all stock positions (positive quantities only for long positions)
        for position in positions:
            if position.quantity > 0:  # Only count long positions
                total_stock_shares += position.quantity
        
        # TODO: In future tasks, subtract shares covered by existing short calls
        # For now, return total stock shares
        return total_stock_shares
    
    def get_existing_short_calls(self, symbol: str) -> List[OptionPosition]:
        """Identify existing covered call positions for a symbol.
        
        Args:
            symbol: The stock symbol to query for existing short calls
            
        Returns:
            List of OptionPosition objects representing existing short calls
        """
        # TODO: This will be implemented in future tasks when we extend broker clients
        # to support option position querying
        if self.logger:
            self.logger.log_info(f"Querying existing short calls for {symbol} (not yet implemented)")
        
        return []
    
    def calculate_cost_basis(self, symbol: str) -> Tuple[float, float]:
        """Retrieve original stock purchase cost basis.
        
        This method attempts to get cost basis information from multiple sources:
        1. Cost basis tracker (if available)
        2. Broker client position data
        3. Default estimation based on current price
        
        Args:
            symbol: Stock symbol to calculate cost basis for
            
        Returns:
            Tuple of (average_cost_per_share, total_cost_basis)
            
        Raises:
            ValueError: If unable to determine cost basis
        """
        if not symbol or not symbol.strip():
            raise ValueError("Symbol cannot be empty")
        
        symbol = symbol.upper().strip()
        
        if self.logger:
            self.logger.log_info(f"Calculating cost basis for {symbol}")
        
        try:
            # First try to get from cost basis tracker
            try:
                cost_basis_summary = self.cost_basis_tracker.get_cost_basis_summary(symbol)
                avg_cost = cost_basis_summary.original_cost_basis_per_share
                total_cost = cost_basis_summary.total_original_cost
                
                if self.logger:
                    self.logger.log_info(
                        f"Retrieved cost basis from tracker for {symbol}",
                        {"avg_cost": avg_cost, "total_cost": total_cost}
                    )
                
                return avg_cost, total_cost
                
            except ValueError:
                # Cost basis tracker doesn't have data for this symbol
                if self.logger:
                    self.logger.log_info(f"No cost basis data in tracker for {symbol}, trying broker")
            
            # Try to get from broker position data
            try:
                stock_position = self.broker_client.get_position(symbol)
                if stock_position and hasattr(stock_position, 'average_cost') and stock_position.average_cost > 0:
                    avg_cost = stock_position.average_cost
                    total_cost = avg_cost * stock_position.quantity
                    
                    if self.logger:
                        self.logger.log_info(
                            f"Retrieved cost basis from broker for {symbol}",
                            {"avg_cost": avg_cost, "total_cost": total_cost}
                        )
                    
                    return avg_cost, total_cost
                    
            except Exception as e:
                if self.logger:
                    self.logger.log_warning(f"Could not get cost basis from broker for {symbol}: {str(e)}")
            
            # Fallback: estimate based on current price (not ideal but prevents errors)
            current_price = self.broker_client.get_current_price(symbol)
            stock_position = self.broker_client.get_position(symbol)
            total_shares = stock_position.quantity if stock_position else 0
            
            if total_shares > 0:
                # Use current price as estimate (this is a fallback)
                avg_cost = current_price
                total_cost = avg_cost * total_shares
                
                if self.logger:
                    self.logger.log_warning(
                        f"Using current price as cost basis estimate for {symbol} - this may not be accurate",
                        {"estimated_avg_cost": avg_cost, "estimated_total_cost": total_cost}
                    )
                
                return avg_cost, total_cost
            else:
                raise ValueError(f"No position found for {symbol} to calculate cost basis")
                
        except Exception as e:
            error_msg = f"Error calculating cost basis for {symbol}: {str(e)}"
            if self.logger:
                self.logger.log_error(error_msg, e, {"symbol": symbol})
            raise ValueError(error_msg) from e
    
    def get_cumulative_premium_collected(self, symbol: str) -> float:
        """Get total premium collected from previous strategies.
        
        Args:
            symbol: Stock symbol to get cumulative premium for
            
        Returns:
            Total premium collected from all previous strategy executions
        """
        if not symbol or not symbol.strip():
            raise ValueError("Symbol cannot be empty")
        
        symbol = symbol.upper().strip()
        
        if self.logger:
            self.logger.log_info(f"Getting cumulative premium collected for {symbol}")
        
        try:
            cost_basis_summary = self.cost_basis_tracker.get_cost_basis_summary(symbol)
            cumulative_premium = cost_basis_summary.cumulative_premium_collected
            
            if self.logger:
                self.logger.log_info(
                    f"Retrieved cumulative premium for {symbol}",
                    {"cumulative_premium": cumulative_premium}
                )
            
            return cumulative_premium
            
        except ValueError:
            # No cost basis data available - return 0
            if self.logger:
                self.logger.log_info(f"No premium history found for {symbol}, returning 0")
            return 0.0
        except Exception as e:
            error_msg = f"Error getting cumulative premium for {symbol}: {str(e)}"
            if self.logger:
                self.logger.log_error(error_msg, e, {"symbol": symbol})
            # Return 0 instead of raising error to prevent breaking position queries
            return 0.0
    
    def _calculate_cost_basis_with_data(self, symbol: str, current_price: float, total_shares: int, stock_position) -> Tuple[float, float]:
        """Helper method to calculate cost basis without making additional API calls.
        
        This method is used internally by get_long_positions to avoid duplicate API calls.
        
        Args:
            symbol: Stock symbol
            current_price: Already retrieved current price
            total_shares: Already retrieved total shares
            stock_position: Already retrieved stock position
            
        Returns:
            Tuple of (average_cost_per_share, total_cost_basis)
        """
        try:
            # First try to get from cost basis tracker
            try:
                cost_basis_summary = self.cost_basis_tracker.get_cost_basis_summary(symbol)
                avg_cost = cost_basis_summary.original_cost_basis_per_share
                total_cost = cost_basis_summary.total_original_cost
                
                if self.logger:
                    self.logger.log_info(
                        f"Retrieved cost basis from tracker for {symbol}",
                        {"avg_cost": avg_cost, "total_cost": total_cost}
                    )
                
                return avg_cost, total_cost
                
            except ValueError:
                # Cost basis tracker doesn't have data for this symbol
                if self.logger:
                    self.logger.log_info(f"No cost basis data in tracker for {symbol}, trying broker")
            
            # Try to get from already retrieved broker position data
            if stock_position and hasattr(stock_position, 'average_cost') and stock_position.average_cost > 0:
                avg_cost = stock_position.average_cost
                total_cost = avg_cost * stock_position.quantity
                
                if self.logger:
                    self.logger.log_info(
                        f"Retrieved cost basis from broker for {symbol}",
                        {"avg_cost": avg_cost, "total_cost": total_cost}
                    )
                
                return avg_cost, total_cost
            
            # Fallback: use provided current price (not ideal but prevents errors)
            if total_shares > 0:
                avg_cost = current_price
                total_cost = avg_cost * total_shares
                
                if self.logger:
                    self.logger.log_warning(
                        f"Using current price as cost basis estimate for {symbol} - this may not be accurate",
                        {"estimated_avg_cost": avg_cost, "estimated_total_cost": total_cost}
                    )
                
                return avg_cost, total_cost
            else:
                raise ValueError(f"No position found for {symbol} to calculate cost basis")
                
        except Exception as e:
            error_msg = f"Error calculating cost basis for {symbol}: {str(e)}"
            if self.logger:
                self.logger.log_error(error_msg, e, {"symbol": symbol})
            raise ValueError(error_msg) from e
    
    def validate_cost_basis_accuracy(self, symbol: str, position_summary: PositionSummary) -> Tuple[bool, List[str]]:
        """Validate accuracy of cost basis calculations.
        
        This method performs validation checks to ensure cost basis data is accurate and consistent:
        1. Validates that effective cost basis is not negative
        2. Checks that cumulative premium is reasonable relative to position size
        3. Ensures cost basis reduction doesn't exceed original cost basis
        4. Validates data consistency between different sources
        
        Args:
            symbol: Stock symbol to validate
            position_summary: Position summary with cost basis information
            
        Returns:
            Tuple of (is_valid, list_of_warnings)
        """
        if not symbol or not symbol.strip():
            raise ValueError("Symbol cannot be empty")
        
        symbol = symbol.upper().strip()
        warnings = []
        is_valid = True
        
        if self.logger:
            self.logger.log_info(f"Validating cost basis accuracy for {symbol}")
        
        try:
            # Skip validation if cost basis data is not available
            if position_summary.average_cost_basis is None:
                if self.logger:
                    self.logger.log_info(f"No cost basis data available for {symbol}, skipping validation")
                return True, ["No cost basis data available for validation"]
            
            # Validate effective cost basis is not negative
            if (position_summary.effective_cost_basis_per_share is not None and 
                position_summary.effective_cost_basis_per_share < 0):
                warnings.append(f"Negative effective cost basis: ${position_summary.effective_cost_basis_per_share:.2f}")
                is_valid = False
            
            # Validate cumulative premium is reasonable
            if (position_summary.cumulative_premium_collected is not None and 
                position_summary.cumulative_premium_collected > 0 and
                position_summary.total_shares > 0):
                
                premium_per_share = position_summary.cumulative_premium_collected / position_summary.total_shares
                original_cost = position_summary.average_cost_basis
                
                # Warning if premium per share exceeds 50% of original cost basis
                if premium_per_share > (original_cost * 0.5):
                    warnings.append(
                        f"High premium collection: ${premium_per_share:.2f} per share "
                        f"({premium_per_share/original_cost*100:.1f}% of original cost basis)"
                    )
                
                # Error if premium per share exceeds original cost basis
                if premium_per_share > original_cost:
                    warnings.append(
                        f"Premium per share (${premium_per_share:.2f}) exceeds original cost basis "
                        f"(${original_cost:.2f}) - this may indicate data errors"
                    )
                    is_valid = False
            
            # Validate consistency between total cost basis and per-share calculations
            if (position_summary.total_cost_basis is not None and 
                position_summary.average_cost_basis is not None and
                position_summary.total_shares > 0):
                
                expected_total = position_summary.average_cost_basis * position_summary.total_shares
                actual_total = position_summary.total_cost_basis
                
                # Allow for small floating point differences
                if abs(expected_total - actual_total) > 0.01:
                    warnings.append(
                        f"Cost basis calculation inconsistency: expected total ${expected_total:.2f}, "
                        f"actual total ${actual_total:.2f}"
                    )
            
            # Validate effective cost basis calculation
            if (position_summary.effective_cost_basis_per_share is not None and
                position_summary.average_cost_basis is not None and
                position_summary.cumulative_premium_collected is not None and
                position_summary.total_shares > 0):
                
                expected_effective = self.cost_basis_tracker.calculate_effective_cost_basis(
                    position_summary.average_cost_basis,
                    position_summary.cumulative_premium_collected,
                    position_summary.total_shares
                )
                
                actual_effective = position_summary.effective_cost_basis_per_share
                
                # Allow for small floating point differences
                if abs(expected_effective - actual_effective) > 0.01:
                    warnings.append(
                        f"Effective cost basis calculation inconsistency: expected ${expected_effective:.2f}, "
                        f"actual ${actual_effective:.2f}"
                    )
            
            if self.logger:
                if is_valid:
                    self.logger.log_info(
                        f"Cost basis validation passed for {symbol}",
                        {"warnings_count": len(warnings)}
                    )
                else:
                    self.logger.log_warning(
                        f"Cost basis validation failed for {symbol}",
                        {"warnings": warnings}
                    )
            
            return is_valid, warnings
            
        except Exception as e:
            error_msg = f"Error validating cost basis accuracy for {symbol}: {str(e)}"
            if self.logger:
                self.logger.log_error(error_msg, e, {"symbol": symbol})
            return False, [error_msg]
    
    def validate_covered_call_orders(
        self,
        symbol: str,
        orders: List[CoveredCallOrder],
        min_shares_required: int = 300
    ) -> Tuple[bool, PositionValidationSummary]:
        """Validate covered call orders against current positions.
        
        This method performs comprehensive validation to ensure:
        1. Sufficient shares exist for all contracts
        2. No conflicts with existing short calls
        3. Minimum requirements are met
        4. No naked call positions would be created
        
        Args:
            symbol: Stock symbol to validate
            orders: List of covered call orders to validate
            min_shares_required: Minimum shares required for strategy execution
            
        Returns:
            Tuple of (validation_passed, validation_summary)
        """
        if self.logger:
            self.logger.log_info(
                f"Starting comprehensive validation for {symbol}",
                {
                    "symbol": symbol,
                    "order_count": len(orders),
                    "total_contracts": sum(order.quantity for order in orders),
                    "min_shares_required": min_shares_required
                }
            )
        
        # Calculate total contracts requested first (before try block)
        total_contracts = sum(order.quantity for order in orders)
        
        try:
            # Get current position summary
            position_summary = self.get_long_positions(symbol)
            
            # Perform all validation checks
            validation_results = []
            
            # 1. Validate sufficient shares
            share_validation = self.validator.validate_sufficient_shares(
                position_summary, total_contracts, 100
            )
            validation_results.append(share_validation)
            
            # 2. Validate existing short calls
            short_call_validation = self.validator.validate_existing_short_calls(
                position_summary, orders
            )
            validation_results.append(short_call_validation)
            
            # 3. Validate minimum requirements
            min_req_validation = self.validator.validate_minimum_requirements(
                position_summary, min_shares_required
            )
            validation_results.append(min_req_validation)
            
            # Create comprehensive summary
            validation_summary = self.validator.create_validation_summary(
                position_summary, total_contracts, validation_results
            )
            
            # Log validation results
            if self.logger:
                if validation_summary.validation_passed:
                    self.logger.log_info(
                        f"Validation passed for {symbol}",
                        {
                            "symbol": symbol,
                            "total_contracts": total_contracts,
                            "available_shares": validation_summary.available_shares,
                            "adjustments_made": validation_summary.adjustments_made,
                            "warnings": len(validation_summary.warnings)
                        }
                    )
                else:
                    self.logger.log_error(
                        f"Validation failed for {symbol}",
                        context={
                            "symbol": symbol,
                            "errors": validation_summary.errors,
                            "total_shares": validation_summary.total_shares,
                            "available_shares": validation_summary.available_shares
                        }
                    )
            
            return validation_summary.validation_passed, validation_summary
            
        except Exception as e:
            error_msg = f"Error during position validation for {symbol}: {str(e)}"
            if self.logger:
                self.logger.log_error(error_msg, e, {"symbol": symbol})
            
            # Return failed validation with error details
            validation_summary = PositionValidationSummary(
                symbol=symbol,
                total_shares=0,
                available_shares=0,
                existing_short_calls=0,
                max_contracts_allowed=0,
                requested_contracts=total_contracts,
                validation_passed=False,
                adjustments_made=False,
                warnings=[],
                errors=[error_msg]
            )
            
            return False, validation_summary
    
    def validate_single_covered_call(
        self,
        symbol: str,
        strike: float,
        expiration: date,
        quantity: int
    ) -> ValidationResult:
        """Validate a single covered call order.
        
        Args:
            symbol: Stock symbol
            strike: Strike price
            expiration: Expiration date
            quantity: Number of contracts
            
        Returns:
            ValidationResult with validation outcome
        """
        if self.logger:
            self.logger.log_info(
                f"Validating single covered call for {symbol}",
                {
                    "symbol": symbol,
                    "strike": strike,
                    "expiration": expiration.isoformat(),
                    "quantity": quantity
                }
            )
        
        try:
            # Create order object for validation
            order = CoveredCallOrder(
                symbol=symbol,
                strike=strike,
                expiration=expiration,
                quantity=quantity,
                underlying_shares=quantity * 100
            )
            
            # Get position summary
            position_summary = self.get_long_positions(symbol)
            
            # Validate sufficient shares
            result = self.validator.validate_sufficient_shares(
                position_summary, quantity, 100
            )
            
            if self.logger:
                if result.is_valid:
                    self.logger.log_info(
                        f"Single covered call validation passed for {symbol}",
                        {
                            "symbol": symbol,
                            "quantity": quantity,
                            "available_shares": position_summary.available_shares
                        }
                    )
                else:
                    self.logger.log_error(
                        f"Single covered call validation failed for {symbol}: {result.error_message}",
                        context={"symbol": symbol, "quantity": quantity}
                    )
            
            return result
            
        except Exception as e:
            error_msg = f"Error validating single covered call for {symbol}: {str(e)}"
            if self.logger:
                self.logger.log_error(error_msg, e, {"symbol": symbol})
            
            return ValidationResult(
                is_valid=False,
                error_message=error_msg
            )
    
    def get_position_validation_summary(self, symbol: str) -> PositionValidationSummary:
        """Get a validation summary for current positions without validating specific orders.
        
        Args:
            symbol: Stock symbol to get validation summary for
            
        Returns:
            PositionValidationSummary with current position status
        """
        if self.logger:
            self.logger.log_info(f"Getting position validation summary for {symbol}")
        
        try:
            position_summary = self.get_long_positions(symbol)
            
            # Count existing short calls
            existing_short_calls = len([
                call for call in position_summary.existing_short_calls 
                if call.position_type == 'short_call'
            ])
            
            # Calculate max contracts allowed
            max_contracts_allowed = position_summary.available_shares // 100
            
            validation_summary = PositionValidationSummary(
                symbol=symbol,
                total_shares=position_summary.total_shares,
                available_shares=position_summary.available_shares,
                existing_short_calls=existing_short_calls,
                max_contracts_allowed=max_contracts_allowed,
                requested_contracts=0,  # No specific request
                validation_passed=position_summary.available_shares >= 100,
                adjustments_made=False,
                warnings=[],
                errors=[] if position_summary.available_shares >= 100 else [
                    f"Insufficient shares: {position_summary.available_shares} available, need at least 100"
                ]
            )
            
            if self.logger:
                self.logger.log_info(
                    f"Position validation summary for {symbol}",
                    {
                        "symbol": symbol,
                        "total_shares": validation_summary.total_shares,
                        "available_shares": validation_summary.available_shares,
                        "max_contracts_allowed": validation_summary.max_contracts_allowed,
                        "existing_short_calls": validation_summary.existing_short_calls
                    }
                )
            
            return validation_summary
            
        except Exception as e:
            error_msg = f"Error getting position validation summary for {symbol}: {str(e)}"
            if self.logger:
                self.logger.log_error(error_msg, e, {"symbol": symbol})
            
            return PositionValidationSummary(
                symbol=symbol,
                total_shares=0,
                available_shares=0,
                existing_short_calls=0,
                max_contracts_allowed=0,
                requested_contracts=0,
                validation_passed=False,
                adjustments_made=False,
                warnings=[],
                errors=[error_msg]
            )