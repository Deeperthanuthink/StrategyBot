"""Order validation and error handling for covered call strategies."""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple
from datetime import date
import logging

from ..positions.models import CoveredCallOrder, PositionSummary
from ..positions.validation import PositionValidator, ValidationResult
from ..brokers.base_client import OrderResult
from ..logging.bot_logger import BotLogger


@dataclass
class OrderValidationResult:
    """Result of order validation before submission."""
    is_valid: bool
    validated_orders: List[CoveredCallOrder]
    rejected_orders: List[CoveredCallOrder]
    warnings: List[str]
    errors: List[str]
    total_contracts: int
    total_shares_needed: int


@dataclass
class BatchOrderResult:
    """Result of batch order execution with error recovery."""
    successful_orders: List[Tuple[CoveredCallOrder, OrderResult]]
    failed_orders: List[Tuple[CoveredCallOrder, OrderResult]]
    partial_success: bool
    total_premium_collected: float
    execution_summary: Dict[str, Any]


class OrderValidator:
    """Validator for order execution with comprehensive error handling."""
    
    def __init__(self, logger: Optional[BotLogger] = None):
        """Initialize the order validator.
        
        Args:
            logger: Optional logger for tracking validation operations
        """
        self.logger = logger
        self.position_validator = PositionValidator(logger)
    
    def validate_orders_before_submission(
        self,
        orders: List[CoveredCallOrder],
        position_summary: PositionSummary,
        max_contracts_per_expiration: int = 10
    ) -> OrderValidationResult:
        """Validate orders before submission to prevent errors.
        
        Args:
            orders: List of orders to validate
            position_summary: Current position summary
            max_contracts_per_expiration: Maximum contracts allowed per expiration
            
        Returns:
            OrderValidationResult with validation details
        """
        symbol = position_summary.symbol
        validated_orders = []
        rejected_orders = []
        warnings = []
        errors = []
        
        if self.logger:
            self.logger.log_info(
                f"Validating {len(orders)} orders before submission for {symbol}",
                {
                    "symbol": symbol,
                    "order_count": len(orders),
                    "available_shares": position_summary.available_shares
                }
            )
        
        try:
            # 1. Validate individual order parameters
            for order in orders:
                order_warnings, order_errors = self._validate_single_order(
                    order, max_contracts_per_expiration
                )
                
                if order_errors:
                    rejected_orders.append(order)
                    errors.extend(order_errors)
                    if self.logger:
                        self.logger.log_error(
                            f"Order rejected for {symbol}: {'; '.join(order_errors)}",
                            context={
                                "symbol": symbol,
                                "strike": order.strike,
                                "expiration": order.expiration.isoformat(),
                                "quantity": order.quantity
                            }
                        )
                else:
                    validated_orders.append(order)
                    if order_warnings:
                        warnings.extend(order_warnings)
            
            # 2. Validate total position requirements
            if validated_orders:
                total_contracts = sum(order.quantity for order in validated_orders)
                position_validation = self.position_validator.validate_sufficient_shares(
                    position_summary, total_contracts, 100
                )
                
                if not position_validation.is_valid:
                    # Move all orders to rejected if position validation fails
                    rejected_orders.extend(validated_orders)
                    validated_orders = []
                    errors.append(position_validation.error_message)
                    
                    if self.logger:
                        self.logger.log_error(
                            f"Position validation failed for {symbol}: {position_validation.error_message}",
                            context={"symbol": symbol, "total_contracts": total_contracts}
                        )
                
                elif position_validation.warning_message:
                    warnings.append(position_validation.warning_message)
                    
                    # Adjust contracts if needed
                    if position_validation.adjusted_contracts is not None:
                        validated_orders = self._adjust_order_quantities(
                            validated_orders, position_validation.adjusted_contracts
                        )
            
            # 3. Check for conflicts with existing positions
            if validated_orders:
                conflict_validation = self.position_validator.validate_existing_short_calls(
                    position_summary, validated_orders
                )
                
                if conflict_validation.warning_message:
                    warnings.append(conflict_validation.warning_message)
            
            total_contracts = sum(order.quantity for order in validated_orders)
            total_shares_needed = total_contracts * 100
            
            result = OrderValidationResult(
                is_valid=len(validated_orders) > 0,
                validated_orders=validated_orders,
                rejected_orders=rejected_orders,
                warnings=warnings,
                errors=errors,
                total_contracts=total_contracts,
                total_shares_needed=total_shares_needed
            )
            
            if self.logger:
                self.logger.log_info(
                    f"Order validation completed for {symbol}",
                    {
                        "symbol": symbol,
                        "validated_orders": len(validated_orders),
                        "rejected_orders": len(rejected_orders),
                        "warnings": len(warnings),
                        "errors": len(errors),
                        "total_contracts": total_contracts
                    }
                )
            
            return result
            
        except Exception as e:
            error_msg = f"Error during order validation for {symbol}: {str(e)}"
            if self.logger:
                self.logger.log_error(error_msg, e, {"symbol": symbol})
            
            return OrderValidationResult(
                is_valid=False,
                validated_orders=[],
                rejected_orders=orders,
                warnings=[],
                errors=[error_msg],
                total_contracts=0,
                total_shares_needed=0
            )
    
    def _validate_single_order(
        self,
        order: CoveredCallOrder,
        max_contracts_per_expiration: int
    ) -> Tuple[List[str], List[str]]:
        """Validate a single order's parameters.
        
        Args:
            order: Order to validate
            max_contracts_per_expiration: Maximum contracts allowed
            
        Returns:
            Tuple of (warnings, errors)
        """
        warnings = []
        errors = []
        
        # Validate strike price
        if order.strike <= 0:
            errors.append(f"Invalid strike price: {order.strike}")
        
        # Validate quantity
        if order.quantity <= 0:
            errors.append(f"Invalid quantity: {order.quantity}")
        elif order.quantity > max_contracts_per_expiration:
            warnings.append(f"Quantity {order.quantity} exceeds maximum {max_contracts_per_expiration} per expiration")
        
        # Validate expiration date
        if order.expiration <= date.today():
            errors.append(f"Expiration date {order.expiration} is not in the future")
        
        # Validate underlying shares
        expected_shares = order.quantity * 100
        if order.underlying_shares < expected_shares:
            errors.append(f"Insufficient underlying shares: {order.underlying_shares} for {order.quantity} contracts")
        
        return warnings, errors
    
    def _adjust_order_quantities(
        self,
        orders: List[CoveredCallOrder],
        max_total_contracts: int
    ) -> List[CoveredCallOrder]:
        """Adjust order quantities proportionally to fit within limits.
        
        Args:
            orders: Original orders
            max_total_contracts: Maximum total contracts allowed
            
        Returns:
            List of adjusted orders
        """
        if not orders:
            return orders
        
        total_requested = sum(order.quantity for order in orders)
        if total_requested <= max_total_contracts:
            return orders
        
        # Proportionally reduce quantities
        adjusted_orders = []
        allocated_contracts = 0
        
        for i, order in enumerate(orders):
            if i == len(orders) - 1:
                # Last order gets remaining contracts
                adjusted_quantity = max_total_contracts - allocated_contracts
            else:
                proportion = order.quantity / total_requested
                adjusted_quantity = max(1, int(max_total_contracts * proportion))
            
            if adjusted_quantity > 0:
                adjusted_order = CoveredCallOrder(
                    symbol=order.symbol,
                    strike=order.strike,
                    expiration=order.expiration,
                    quantity=adjusted_quantity,
                    underlying_shares=adjusted_quantity * 100
                )
                adjusted_orders.append(adjusted_order)
                allocated_contracts += adjusted_quantity
        
        return adjusted_orders
    
    def handle_partial_order_failures(
        self,
        orders: List[CoveredCallOrder],
        results: List[OrderResult]
    ) -> BatchOrderResult:
        """Handle partial failures in batch order execution.
        
        Args:
            orders: Original orders submitted
            results: Results from broker execution
            
        Returns:
            BatchOrderResult with error recovery details
        """
        successful_orders = []
        failed_orders = []
        total_premium_collected = 0.0
        
        if self.logger:
            self.logger.log_info(
                f"Processing batch order results: {len(orders)} orders, {len(results)} results"
            )
        
        for order, result in zip(orders, results):
            if result.success:
                successful_orders.append((order, result))
                # Estimate premium collected (would need real data in production)
                estimated_premium = order.quantity * 1.0  # Placeholder
                total_premium_collected += estimated_premium
                
                if self.logger:
                    self.logger.log_info(
                        f"Order successful for {order.symbol}",
                        {
                            "symbol": order.symbol,
                            "strike": order.strike,
                            "expiration": order.expiration.isoformat(),
                            "quantity": order.quantity,
                            "order_id": result.order_id
                        }
                    )
            else:
                failed_orders.append((order, result))
                
                if self.logger:
                    self.logger.log_error(
                        f"Order failed for {order.symbol}: {result.error_message}",
                        context={
                            "symbol": order.symbol,
                            "strike": order.strike,
                            "expiration": order.expiration.isoformat(),
                            "quantity": order.quantity,
                            "error": result.error_message
                        }
                    )
        
        partial_success = len(successful_orders) > 0 and len(failed_orders) > 0
        
        execution_summary = {
            "total_orders": len(orders),
            "successful_orders": len(successful_orders),
            "failed_orders": len(failed_orders),
            "success_rate": len(successful_orders) / len(orders) if orders else 0,
            "total_premium_collected": total_premium_collected,
            "partial_success": partial_success
        }
        
        if self.logger:
            self.logger.log_info(
                f"Batch order execution completed",
                execution_summary
            )
        
        return BatchOrderResult(
            successful_orders=successful_orders,
            failed_orders=failed_orders,
            partial_success=partial_success,
            total_premium_collected=total_premium_collected,
            execution_summary=execution_summary
        )
    
    def log_order_submission_details(
        self,
        orders: List[CoveredCallOrder],
        symbol: str
    ) -> None:
        """Log comprehensive details about order submission.
        
        Args:
            orders: Orders being submitted
            symbol: Stock symbol
        """
        if not self.logger:
            return
        
        total_contracts = sum(order.quantity for order in orders)
        total_shares = total_contracts * 100
        
        # Group orders by expiration
        by_expiration = {}
        for order in orders:
            exp_str = order.expiration.isoformat()
            if exp_str not in by_expiration:
                by_expiration[exp_str] = []
            by_expiration[exp_str].append(order)
        
        self.logger.log_info(
            f"Submitting {len(orders)} covered call orders for {symbol}",
            {
                "symbol": symbol,
                "total_orders": len(orders),
                "total_contracts": total_contracts,
                "total_shares_covered": total_shares,
                "expirations": len(by_expiration),
                "order_details": [
                    {
                        "expiration": order.expiration.isoformat(),
                        "strike": order.strike,
                        "quantity": order.quantity,
                        "shares": order.underlying_shares
                    } for order in orders
                ]
            }
        )
        
        # Log by expiration group
        for exp_str, exp_orders in by_expiration.items():
            exp_contracts = sum(order.quantity for order in exp_orders)
            exp_strikes = [order.strike for order in exp_orders]
            
            self.logger.log_info(
                f"Expiration group {exp_str} for {symbol}",
                {
                    "symbol": symbol,
                    "expiration": exp_str,
                    "contracts": exp_contracts,
                    "strikes": exp_strikes,
                    "orders_in_group": len(exp_orders)
                }
            )