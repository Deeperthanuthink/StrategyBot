"""Position validation logic for covered call strategies."""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import date
import logging

from .models import PositionSummary, CoveredCallOrder, OptionPosition
from ..logging.bot_logger import BotLogger


@dataclass
class ValidationResult:
    """Result of position validation."""
    is_valid: bool
    error_message: Optional[str] = None
    warning_message: Optional[str] = None
    adjusted_contracts: Optional[int] = None
    validation_details: Optional[Dict[str, Any]] = None


@dataclass
class PositionValidationSummary:
    """Summary of position validation results."""
    symbol: str
    total_shares: int
    available_shares: int
    existing_short_calls: int
    max_contracts_allowed: int
    requested_contracts: int
    validation_passed: bool
    adjustments_made: bool
    warnings: List[str]
    errors: List[str]


class PositionValidator:
    """Validator for position-related operations to prevent naked call creation."""
    
    def __init__(self, logger: Optional[BotLogger] = None):
        """Initialize the position validator.
        
        Args:
            logger: Optional logger for tracking validation operations
        """
        self.logger = logger
    
    def validate_sufficient_shares(
        self, 
        position_summary: PositionSummary, 
        requested_contracts: int,
        min_shares_required: int = 100
    ) -> ValidationResult:
        """Validate that sufficient shares exist for covered call writing.
        
        This method ensures that the user has enough shares to cover all
        requested covered call contracts without creating naked positions.
        
        Args:
            position_summary: Current position summary for the symbol
            requested_contracts: Number of contracts requested
            min_shares_required: Minimum shares required per contract (default: 100)
            
        Returns:
            ValidationResult with validation outcome and details
        """
        symbol = position_summary.symbol
        total_shares = position_summary.total_shares
        available_shares = position_summary.available_shares
        
        # Log validation start
        if self.logger:
            self.logger.log_info(
                f"Validating share sufficiency for {symbol}",
                {
                    "symbol": symbol,
                    "total_shares": total_shares,
                    "available_shares": available_shares,
                    "requested_contracts": requested_contracts,
                    "shares_needed": requested_contracts * min_shares_required
                }
            )
        
        # Calculate shares needed
        shares_needed = requested_contracts * min_shares_required
        
        # Check if we have any shares at all
        if total_shares <= 0:
            error_msg = f"No shares found for {symbol}. Cannot write covered calls without underlying shares."
            if self.logger:
                self.logger.log_error(error_msg, context={"symbol": symbol, "total_shares": total_shares})
            
            return ValidationResult(
                is_valid=False,
                error_message=error_msg,
                validation_details={
                    "total_shares": total_shares,
                    "available_shares": available_shares,
                    "shares_needed": shares_needed,
                    "deficit": shares_needed
                }
            )
        
        # Check minimum share requirement
        if total_shares < min_shares_required:
            error_msg = f"Insufficient shares for {symbol}: {total_shares} shares available, need at least {min_shares_required} for covered calls."
            if self.logger:
                self.logger.log_error(error_msg, context={"symbol": symbol, "total_shares": total_shares})
            
            return ValidationResult(
                is_valid=False,
                error_message=error_msg,
                validation_details={
                    "total_shares": total_shares,
                    "available_shares": available_shares,
                    "min_required": min_shares_required,
                    "deficit": min_shares_required - total_shares
                }
            )
        
        # Check if available shares can cover requested contracts
        if available_shares < shares_needed:
            # Calculate maximum contracts we can actually write
            max_contracts = available_shares // min_shares_required
            
            if max_contracts == 0:
                error_msg = f"No available shares for {symbol}: {available_shares} available shares, all {total_shares} shares already covered by existing short calls."
                if self.logger:
                    self.logger.log_error(error_msg, context={"symbol": symbol, "available_shares": available_shares})
                
                return ValidationResult(
                    is_valid=False,
                    error_message=error_msg,
                    validation_details={
                        "total_shares": total_shares,
                        "available_shares": available_shares,
                        "shares_needed": shares_needed,
                        "max_contracts": max_contracts,
                        "shares_covered_by_calls": total_shares - available_shares
                    }
                )
            else:
                # We can write some contracts, but not as many as requested
                warning_msg = f"Insufficient available shares for {symbol}: requested {requested_contracts} contracts ({shares_needed} shares), but only {available_shares} shares available. Adjusting to {max_contracts} contracts."
                
                if self.logger:
                    self.logger.log_warning(
                        warning_msg,
                        {
                            "symbol": symbol,
                            "requested_contracts": requested_contracts,
                            "adjusted_contracts": max_contracts,
                            "available_shares": available_shares,
                            "shares_needed": shares_needed
                        }
                    )
                
                return ValidationResult(
                    is_valid=True,
                    warning_message=warning_msg,
                    adjusted_contracts=max_contracts,
                    validation_details={
                        "total_shares": total_shares,
                        "available_shares": available_shares,
                        "shares_needed": shares_needed,
                        "max_contracts": max_contracts,
                        "adjustment_reason": "insufficient_available_shares"
                    }
                )
        
        # Validation passed - sufficient shares available
        if self.logger:
            self.logger.log_info(
                f"Share validation passed for {symbol}",
                {
                    "symbol": symbol,
                    "requested_contracts": requested_contracts,
                    "available_shares": available_shares,
                    "shares_needed": shares_needed,
                    "excess_shares": available_shares - shares_needed
                }
            )
        
        return ValidationResult(
            is_valid=True,
            validation_details={
                "total_shares": total_shares,
                "available_shares": available_shares,
                "shares_needed": shares_needed,
                "excess_shares": available_shares - shares_needed
            }
        )
    
    def validate_existing_short_calls(
        self, 
        position_summary: PositionSummary,
        new_orders: List[CoveredCallOrder]
    ) -> ValidationResult:
        """Validate that new covered call orders don't conflict with existing short calls.
        
        This method checks for potential conflicts with existing short call positions
        and ensures we don't over-allocate shares.
        
        Args:
            position_summary: Current position summary for the symbol
            new_orders: List of new covered call orders to validate
            
        Returns:
            ValidationResult with validation outcome and details
        """
        symbol = position_summary.symbol
        existing_short_calls = position_summary.existing_short_calls
        total_shares = position_summary.total_shares
        
        # Calculate shares already covered by existing short calls
        shares_covered_by_existing = sum(
            abs(call.quantity) * 100 for call in existing_short_calls 
            if call.position_type == 'short_call'
        )
        
        # Calculate shares needed for new orders
        shares_needed_for_new = sum(order.quantity * 100 for order in new_orders)
        
        # Total shares that would be covered after new orders
        total_shares_to_be_covered = shares_covered_by_existing + shares_needed_for_new
        
        if self.logger:
            self.logger.log_info(
                f"Validating short call conflicts for {symbol}",
                {
                    "symbol": symbol,
                    "total_shares": total_shares,
                    "existing_short_calls": len(existing_short_calls),
                    "shares_covered_by_existing": shares_covered_by_existing,
                    "shares_needed_for_new": shares_needed_for_new,
                    "total_shares_to_be_covered": total_shares_to_be_covered
                }
            )
        
        # Check for over-allocation
        if total_shares_to_be_covered > total_shares:
            error_msg = f"Cannot write {len(new_orders)} new covered calls for {symbol}: would require {total_shares_to_be_covered} shares but only {total_shares} shares owned. {shares_covered_by_existing} shares already covered by existing short calls."
            
            if self.logger:
                self.logger.log_error(
                    error_msg,
                    context={
                        "symbol": symbol,
                        "total_shares": total_shares,
                        "total_shares_to_be_covered": total_shares_to_be_covered,
                        "over_allocation": total_shares_to_be_covered - total_shares
                    }
                )
            
            return ValidationResult(
                is_valid=False,
                error_message=error_msg,
                validation_details={
                    "total_shares": total_shares,
                    "shares_covered_by_existing": shares_covered_by_existing,
                    "shares_needed_for_new": shares_needed_for_new,
                    "total_shares_to_be_covered": total_shares_to_be_covered,
                    "over_allocation": total_shares_to_be_covered - total_shares,
                    "existing_short_calls": [
                        {
                            "strike": call.strike,
                            "expiration": call.expiration.isoformat(),
                            "quantity": call.quantity
                        } for call in existing_short_calls if call.position_type == 'short_call'
                    ]
                }
            )
        
        # Check for duplicate strikes/expirations (potential conflicts)
        existing_positions = {
            (call.strike, call.expiration): abs(call.quantity) 
            for call in existing_short_calls if call.position_type == 'short_call'
        }
        
        conflicts = []
        for order in new_orders:
            key = (order.strike, order.expiration)
            if key in existing_positions:
                conflicts.append({
                    "strike": order.strike,
                    "expiration": order.expiration.isoformat(),
                    "existing_quantity": existing_positions[key],
                    "new_quantity": order.quantity
                })
        
        if conflicts:
            warning_msg = f"Potential conflicts detected for {symbol}: {len(conflicts)} new orders have same strike/expiration as existing short calls."
            
            if self.logger:
                self.logger.log_warning(
                    warning_msg,
                    {
                        "symbol": symbol,
                        "conflicts": conflicts
                    }
                )
            
            return ValidationResult(
                is_valid=True,
                warning_message=warning_msg,
                validation_details={
                    "total_shares": total_shares,
                    "shares_covered_by_existing": shares_covered_by_existing,
                    "shares_needed_for_new": shares_needed_for_new,
                    "conflicts": conflicts
                }
            )
        
        # Validation passed
        if self.logger:
            self.logger.log_info(
                f"Short call validation passed for {symbol}",
                {
                    "symbol": symbol,
                    "new_orders": len(new_orders),
                    "no_conflicts": True
                }
            )
        
        return ValidationResult(
            is_valid=True,
            validation_details={
                "total_shares": total_shares,
                "shares_covered_by_existing": shares_covered_by_existing,
                "shares_needed_for_new": shares_needed_for_new,
                "total_shares_to_be_covered": total_shares_to_be_covered
            }
        )
    
    def validate_minimum_requirements(
        self,
        position_summary: PositionSummary,
        min_shares_required: int = 300,
        min_contracts_per_expiration: int = 1,
        max_contracts_per_expiration: int = 10
    ) -> ValidationResult:
        """Validate minimum requirements for strategy execution.
        
        Args:
            position_summary: Current position summary
            min_shares_required: Minimum total shares required for strategy
            min_contracts_per_expiration: Minimum contracts per expiration
            max_contracts_per_expiration: Maximum contracts per expiration
            
        Returns:
            ValidationResult with validation outcome
        """
        symbol = position_summary.symbol
        total_shares = position_summary.total_shares
        available_shares = position_summary.available_shares
        
        if self.logger:
            self.logger.log_info(
                f"Validating minimum requirements for {symbol}",
                {
                    "symbol": symbol,
                    "total_shares": total_shares,
                    "available_shares": available_shares,
                    "min_shares_required": min_shares_required
                }
            )
        
        # Check minimum shares requirement
        if total_shares < min_shares_required:
            error_msg = f"Insufficient shares for tiered strategy: {symbol} has {total_shares} shares, need at least {min_shares_required} for tiered covered calls."
            
            if self.logger:
                self.logger.log_error(error_msg, context={"symbol": symbol, "total_shares": total_shares})
            
            return ValidationResult(
                is_valid=False,
                error_message=error_msg,
                validation_details={
                    "total_shares": total_shares,
                    "min_shares_required": min_shares_required,
                    "deficit": min_shares_required - total_shares
                }
            )
        
        # Check available shares for strategy
        if available_shares < min_shares_required:
            error_msg = f"Insufficient available shares for tiered strategy: {symbol} has {available_shares} available shares, need at least {min_shares_required}. {total_shares - available_shares} shares already covered by existing calls."
            
            if self.logger:
                self.logger.log_error(error_msg, context={"symbol": symbol, "available_shares": available_shares})
            
            return ValidationResult(
                is_valid=False,
                error_message=error_msg,
                validation_details={
                    "total_shares": total_shares,
                    "available_shares": available_shares,
                    "min_shares_required": min_shares_required,
                    "shares_covered_by_calls": total_shares - available_shares
                }
            )
        
        # Validation passed
        max_possible_contracts = available_shares // 100
        
        if self.logger:
            self.logger.log_info(
                f"Minimum requirements validation passed for {symbol}",
                {
                    "symbol": symbol,
                    "total_shares": total_shares,
                    "available_shares": available_shares,
                    "max_possible_contracts": max_possible_contracts
                }
            )
        
        return ValidationResult(
            is_valid=True,
            validation_details={
                "total_shares": total_shares,
                "available_shares": available_shares,
                "max_possible_contracts": max_possible_contracts,
                "meets_minimum_requirements": True
            }
        )
    
    def create_validation_summary(
        self,
        position_summary: PositionSummary,
        requested_contracts: int,
        validation_results: List[ValidationResult]
    ) -> PositionValidationSummary:
        """Create a comprehensive validation summary.
        
        Args:
            position_summary: Position summary that was validated
            requested_contracts: Number of contracts originally requested
            validation_results: List of validation results from different checks
            
        Returns:
            PositionValidationSummary with comprehensive validation details
        """
        symbol = position_summary.symbol
        total_shares = position_summary.total_shares
        available_shares = position_summary.available_shares
        
        # Count existing short calls
        existing_short_calls = len([
            call for call in position_summary.existing_short_calls 
            if call.position_type == 'short_call'
        ])
        
        # Calculate max contracts allowed
        max_contracts_allowed = available_shares // 100
        
        # Collect warnings and errors
        warnings = []
        errors = []
        adjustments_made = False
        validation_passed = True
        
        for result in validation_results:
            if not result.is_valid:
                validation_passed = False
                if result.error_message:
                    errors.append(result.error_message)
            
            if result.warning_message:
                warnings.append(result.warning_message)
            
            if result.adjusted_contracts is not None:
                adjustments_made = True
        
        return PositionValidationSummary(
            symbol=symbol,
            total_shares=total_shares,
            available_shares=available_shares,
            existing_short_calls=existing_short_calls,
            max_contracts_allowed=max_contracts_allowed,
            requested_contracts=requested_contracts,
            validation_passed=validation_passed,
            adjustments_made=adjustments_made,
            warnings=warnings,
            errors=errors
        )