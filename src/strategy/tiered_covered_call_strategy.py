"""Tiered covered call strategy calculator for multi-expiration covered call execution."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple
from src.positions.models import PositionSummary, CoveredCallOrder
from src.positions.validation import PositionValidator, ValidationResult, PositionValidationSummary
from src.brokers.base_client import BaseBrokerClient, OptionContract
from src.strategy.cost_basis_tracker import CostBasisTracker
from src.logging.bot_logger import BotLogger


@dataclass
class ExpirationGroup:
    """Represents a group of covered calls for a specific expiration."""
    expiration_date: date
    strike_price: float
    num_contracts: int
    shares_used: int
    estimated_premium_per_contract: float


@dataclass
class TieredCoveredCallPlan:
    """Complete plan for tiered covered call strategy execution."""
    symbol: str
    current_price: float
    total_shares: int
    expiration_groups: List[ExpirationGroup]
    total_contracts: int
    estimated_premium: float
    original_cost_basis: Optional[float] = None  # Original cost basis per share
    effective_cost_basis: Optional[float] = None  # Cost basis after premium collection
    cost_basis_reduction: Optional[float] = None  # Total premium collected per share
    cost_basis_reduction_percentage: Optional[float] = None  # Percentage reduction in cost basis


class TieredCoveredCallCalculator:
    """Calculator for tiered covered call strategy planning and execution."""
    
    def __init__(self, broker_client: BaseBrokerClient, min_days_to_expiration: int = 7, 
                 max_days_to_expiration: int = 60, logger: Optional[BotLogger] = None,
                 cost_basis_tracker: Optional[CostBasisTracker] = None):
        """Initialize the calculator with broker client and configuration.
        
        Args:
            broker_client: Broker client for market data and order execution
            min_days_to_expiration: Minimum days to expiration for option selection
            max_days_to_expiration: Maximum days to expiration for option selection
            logger: Optional logger for tracking operations
            cost_basis_tracker: Optional cost basis tracker for cost basis calculations
        """
        self.broker_client = broker_client
        self.min_days_to_expiration = min_days_to_expiration
        self.max_days_to_expiration = max_days_to_expiration
        self.logger = logger
        self.validator = PositionValidator(logger)
        self.cost_basis_tracker = cost_basis_tracker or CostBasisTracker(logger=logger)
    
    def find_next_three_expirations(self, symbol: str) -> List[date]:
        """Find the next three available expiration dates for the symbol.
        
        This method retrieves available expiration dates from the Tradier API,
        filters them by the configured date range, and validates that each
        expiration has call options available.
        
        Args:
            symbol: Stock symbol to find expirations for
            
        Returns:
            List of up to 3 expiration dates sorted chronologically
            
        Raises:
            ValueError: If no valid expirations are found
        """
        today = date.today()
        min_date = today + timedelta(days=self.min_days_to_expiration)
        max_date = today + timedelta(days=self.max_days_to_expiration)
        
        # Get all available expirations from Tradier API
        if self.logger:
            self.logger.log_info(
                f"Retrieving option expirations from API for {symbol}",
                {"symbol": symbol, "min_date": str(min_date), "max_date": str(max_date)}
            )
        
        try:
            all_expirations = self.broker_client.get_option_expirations(symbol)
        except Exception as e:
            error_msg = f"Failed to retrieve option expirations for {symbol}: {str(e)}"
            if self.logger:
                self.logger.log_error(
                    error_msg,
                    e,
                    {"symbol": symbol, "min_date": str(min_date), "max_date": str(max_date)}
                )
            raise ValueError(error_msg) from e
        
        if not all_expirations:
            error_msg = f"No option expirations available for {symbol}"
            if self.logger:
                self.logger.log_error(
                    error_msg,
                    context={"symbol": symbol, "min_date": str(min_date), "max_date": str(max_date)}
                )
            raise ValueError(error_msg)
        
        if self.logger:
            self.logger.log_info(
                f"Retrieved {len(all_expirations)} expirations from API for {symbol}",
                {
                    "symbol": symbol,
                    "total_count": len(all_expirations),
                    "first_expiration": all_expirations[0].isoformat() if all_expirations else None,
                    "last_expiration": all_expirations[-1].isoformat() if all_expirations else None
                }
            )
        
        # Filter by date range
        filtered_expirations = [
            exp for exp in all_expirations
            if min_date <= exp <= max_date
        ]
        
        if self.logger:
            self.logger.log_info(
                f"Filtered expirations by date range for {symbol}",
                {
                    "symbol": symbol,
                    "before_filtering": len(all_expirations),
                    "after_filtering": len(filtered_expirations),
                    "excluded_count": len(all_expirations) - len(filtered_expirations)
                }
            )
        
        if not filtered_expirations:
            error_msg = (
                f"No expirations found between {min_date} and {max_date} for {symbol}. "
                f"Found {len(all_expirations)} total expirations but none within date range."
            )
            if self.logger:
                self.logger.log_error(
                    error_msg,
                    context={
                        "symbol": symbol,
                        "min_date": str(min_date),
                        "max_date": str(max_date),
                        "total_expirations": len(all_expirations),
                        "date_range_days": (max_date - min_date).days
                    }
                )
            raise ValueError(error_msg)
        
        # Validate that each expiration has call options available
        validated_expirations = []
        for expiration in filtered_expirations[:5]:  # Check up to 5 to get 3 valid
            try:
                options = self.broker_client.get_option_chain(symbol, expiration)
                
                # Filter for call options only
                call_options = [opt for opt in options if opt.option_type and opt.option_type.lower() == 'call']
                
                if self.logger:
                    self.logger.log_info(
                        f"Validating expiration {expiration} for {symbol}: found {len(call_options)} call options",
                        {
                            "symbol": symbol,
                            "expiration": str(expiration),
                            "total_options": len(options),
                            "call_options": len(call_options)
                        }
                    )
                
                if call_options:
                    validated_expirations.append(expiration)
                    if len(validated_expirations) >= 3:
                        break
                else:
                    if self.logger:
                        self.logger.log_warning(
                            f"Expiration {expiration} excluded for {symbol}: no call options available",
                            {
                                "symbol": symbol,
                                "expiration": str(expiration),
                                "total_options": len(options)
                            }
                        )
            except Exception as e:
                if self.logger:
                    self.logger.log_warning(
                        f"Could not validate expiration {expiration} for {symbol}: {str(e)}",
                        {"symbol": symbol, "expiration": str(expiration)}
                    )
                continue
        
        if not validated_expirations:
            error_msg = (
                f"No expirations with call options found for {symbol} between {min_date} and {max_date}. "
                f"Checked {len(filtered_expirations)} expirations but none had call options available."
            )
            if self.logger:
                self.logger.log_error(
                    error_msg,
                    context={
                        "symbol": symbol,
                        "min_date": str(min_date),
                        "max_date": str(max_date),
                        "expirations_checked": len(filtered_expirations),
                        "filtered_expirations": [str(exp) for exp in filtered_expirations[:5]]
                    }
                )
            raise ValueError(error_msg)
        
        if self.logger:
            if len(validated_expirations) < 3:
                self.logger.log_warning(
                    f"Found fewer than 3 valid expirations for {symbol}",
                    {
                        "symbol": symbol,
                        "count": len(validated_expirations),
                        "expirations": [str(exp) for exp in validated_expirations]
                    }
                )
            
            self.logger.log_info(
                f"Final validated expirations for {symbol}",
                {
                    "symbol": symbol,
                    "count": len(validated_expirations),
                    "expirations": [str(exp) for exp in validated_expirations]
                }
            )
        
        # Return up to 3 validated expirations
        return validated_expirations[:3] 
   
    def calculate_incremental_strikes(self, symbol: str, current_price: float, 
                                    expirations: List[date]) -> List[float]:
        """Calculate incremental strike prices for multiple expirations.
        
        This method finds progressively higher out-of-the-money strike prices
        for each expiration, starting with the first OTM strike above current price
        for the nearest expiration.
        
        Args:
            symbol: Stock symbol
            current_price: Current market price of the underlying stock
            expirations: List of expiration dates (should be sorted chronologically)
            
        Returns:
            List of strike prices corresponding to each expiration
            
        Raises:
            ValueError: If insufficient strikes are available or current_price is invalid
        """
        if current_price <= 0:
            raise ValueError(f"Invalid current price: {current_price}. Must be positive")
        
        if not expirations:
            raise ValueError("No expiration dates provided")
        
        # Get option chains for all expirations
        option_chains = {}
        for expiration in expirations:
            try:
                options = self.broker_client.get_option_chain(symbol, expiration)
                # Filter for call options only
                call_options = [opt for opt in options if opt.option_type.lower() == 'call']
                option_chains[expiration] = call_options
            except Exception as e:
                raise ValueError(f"Failed to get option chain for {symbol} expiration {expiration}: {str(e)}")
        
        # Extract available strikes for each expiration
        strikes_by_expiration = {}
        for expiration, options in option_chains.items():
            # First try to get OTM strikes (above current price)
            otm_strikes = sorted([opt.strike for opt in options if opt.strike > current_price])
            
            if otm_strikes:
                strikes_by_expiration[expiration] = otm_strikes
            else:
                # If no OTM strikes, try ATM or slightly ITM strikes
                # Get all available strikes and use the highest ones
                all_strikes = sorted([opt.strike for opt in options])
                
                if not all_strikes:
                    raise ValueError(f"No call strikes available for {symbol} expiration {expiration}")
                
                # Use strikes at or near current price (within 2% below)
                near_money_strikes = [s for s in all_strikes if s >= current_price * 0.98]
                
                if near_money_strikes:
                    strikes_by_expiration[expiration] = sorted(near_money_strikes)
                    if self.logger:
                        self.logger.log_warning(
                            f"No OTM strikes available for {expiration}, using ATM/near-money strikes",
                            {"current_price": current_price, "highest_strike": max(all_strikes)}
                        )
                else:
                    # Last resort: use the highest available strikes
                    strikes_by_expiration[expiration] = sorted(all_strikes[-3:]) if len(all_strikes) >= 3 else all_strikes
                    if self.logger:
                        self.logger.log_warning(
                            f"Using highest available strikes for {expiration} (all below current price)",
                            {"current_price": current_price, "highest_strike": max(all_strikes)}
                        )
        
        # Calculate incremental strikes
        selected_strikes = []
        
        for i, expiration in enumerate(expirations):
            available_strikes = strikes_by_expiration[expiration]
            
            if i == 0:
                # For nearest expiration, use first OTM strike above current price
                selected_strike = available_strikes[0]
            else:
                # For subsequent expirations, find next higher strike than previous
                previous_strike = selected_strikes[i-1]
                
                # Find strikes higher than the previous strike
                higher_strikes = [strike for strike in available_strikes if strike > previous_strike]
                
                if not higher_strikes:
                    # If no higher strikes available, use the highest available strike
                    selected_strike = max(available_strikes)
                    # Log warning that we couldn't get incremental strikes
                else:
                    selected_strike = higher_strikes[0]
            
            selected_strikes.append(selected_strike)
        
        # Validate strikes are reasonable (allow ATM strikes within 2% of current price)
        for i, strike in enumerate(selected_strikes):
            if strike < current_price * 0.98:
                if self.logger:
                    self.logger.log_warning(
                        f"Strike ${strike:.2f} for expiration {expirations[i]} is below current price ${current_price:.2f}",
                        {"strike": strike, "current_price": current_price, "expiration": expirations[i]}
                    )
        
        return selected_strikes
    
    def validate_and_adjust_contracts(
        self,
        position_summary: PositionSummary,
        requested_contracts_per_group: List[int]
    ) -> Tuple[List[int], List[str]]:
        """Validate and adjust contract quantities to prevent naked calls.
        
        Args:
            position_summary: Current position summary
            requested_contracts_per_group: Requested contracts for each expiration group
            
        Returns:
            Tuple of (adjusted_contracts, warnings)
        """
        symbol = position_summary.symbol
        available_shares = position_summary.available_shares
        total_requested_contracts = sum(requested_contracts_per_group)
        shares_needed = total_requested_contracts * 100
        
        warnings = []
        
        if self.logger:
            self.logger.log_info(
                f"Validating contract quantities for {symbol}",
                {
                    "symbol": symbol,
                    "available_shares": available_shares,
                    "total_requested_contracts": total_requested_contracts,
                    "shares_needed": shares_needed
                }
            )
        
        # Check if we have enough shares
        if shares_needed <= available_shares:
            # No adjustment needed
            if self.logger:
                self.logger.log_info(f"Contract validation passed for {symbol} - no adjustments needed")
            return requested_contracts_per_group, warnings
        
        # Need to adjust - calculate maximum possible contracts
        max_total_contracts = available_shares // 100
        
        if max_total_contracts == 0:
            warning_msg = f"No contracts possible for {symbol}: only {available_shares} shares available"
            warnings.append(warning_msg)
            if self.logger:
                self.logger.log_warning(warning_msg, {"symbol": symbol})
            return [0] * len(requested_contracts_per_group), warnings
        
        # Proportionally reduce contracts
        reduction_factor = max_total_contracts / total_requested_contracts
        adjusted_contracts = []
        allocated_contracts = 0
        
        for i, requested in enumerate(requested_contracts_per_group):
            if i == len(requested_contracts_per_group) - 1:
                # Last group gets remaining contracts
                adjusted = max_total_contracts - allocated_contracts
            else:
                adjusted = max(0, int(requested * reduction_factor))
            
            adjusted_contracts.append(adjusted)
            allocated_contracts += adjusted
        
        # Ensure we don't exceed maximum
        while sum(adjusted_contracts) > max_total_contracts:
            for i in range(len(adjusted_contracts) - 1, -1, -1):
                if adjusted_contracts[i] > 0:
                    adjusted_contracts[i] -= 1
                    break
        
        warning_msg = f"Adjusted contract quantities for {symbol}: requested {total_requested_contracts} contracts ({shares_needed} shares), adjusted to {sum(adjusted_contracts)} contracts ({sum(adjusted_contracts) * 100} shares) due to insufficient available shares"
        warnings.append(warning_msg)
        
        if self.logger:
            self.logger.log_warning(
                warning_msg,
                {
                    "symbol": symbol,
                    "original_contracts": requested_contracts_per_group,
                    "adjusted_contracts": adjusted_contracts,
                    "reduction_factor": reduction_factor
                }
            )
        
        return adjusted_contracts, warnings

    def divide_shares_into_groups(self, total_shares: int, num_groups: int = 3) -> List[int]:
        """Divide available shares into equal groups for multiple expirations.
        
        This method divides the total available shares into equal groups,
        allocating any remainder shares to the nearest expiration group.
        
        Args:
            total_shares: Total number of shares available for covered calls
            num_groups: Number of groups to divide shares into (default: 3)
            
        Returns:
            List of share quantities for each group
            
        Raises:
            ValueError: If total_shares is insufficient or invalid parameters
        """
        if total_shares < 0:
            raise ValueError(f"Invalid total_shares: {total_shares}. Cannot be negative")
        
        if num_groups <= 0:
            raise ValueError(f"Invalid num_groups: {num_groups}. Must be positive")
        
        if total_shares < 100:
            raise ValueError(f"Insufficient shares: {total_shares}. Need at least 100 shares for covered calls")
        
        # First, round down total shares to nearest multiple of 100 (full contracts only)
        usable_shares = (total_shares // 100) * 100
        
        # Try equal division first
        if usable_shares % num_groups == 0:
            shares_per_group = usable_shares // num_groups
            # Check if each group gets a multiple of 100
            if shares_per_group % 100 == 0:
                return [shares_per_group] * num_groups
        
        # If equal division doesn't work, use remainder allocation
        shares_per_group = usable_shares // num_groups
        
        # Round down each group to nearest 100 for full contracts
        shares_per_group = (shares_per_group // 100) * 100
        
        if shares_per_group == 0:
            # If we can't allocate 100 shares per group, allocate all usable shares to first group
            return [usable_shares] + [0] * (num_groups - 1)
        
        # Allocate base shares to each group
        share_groups = [shares_per_group] * num_groups
        
        # Calculate remaining shares after equal allocation
        allocated_shares = shares_per_group * num_groups
        remaining_shares = usable_shares - allocated_shares
        
        # Distribute remaining full contracts (multiples of 100) to first group
        additional_contracts = remaining_shares // 100
        if additional_contracts > 0:
            share_groups[0] += additional_contracts * 100
        
        return share_groups
    
    def validate_no_synthetic_strikes(self, symbol: str, expiration_groups: List[ExpirationGroup]) -> bool:
        """Validate that all strikes in the strategy plan are from real option chains.
        
        This method verifies that no synthetic strikes are present in the strategy plan
        by checking that each strike exists in the actual option chain for its expiration.
        
        Args:
            symbol: Stock symbol
            expiration_groups: List of expiration groups to validate
            
        Returns:
            True if all strikes are real (not synthetic)
            
        Raises:
            ValueError: If any synthetic strikes are detected
        """
        if self.logger:
            self.logger.log_info(
                f"Validating no synthetic strikes in strategy plan for {symbol}",
                {"symbol": symbol, "groups_count": len(expiration_groups)}
            )
        
        for group in expiration_groups:
            try:
                # Get real option chain for this expiration
                options = self.broker_client.get_option_chain(symbol, group.expiration_date)
                
                # Extract real strikes from call options
                call_options = [opt for opt in options if opt.option_type and opt.option_type.lower() == 'call']
                real_strikes = [opt.strike for opt in call_options]
                
                # Check if the group's strike is in the real strikes
                if group.strike_price not in real_strikes:
                    error_msg = (
                        f"Synthetic strike detected: {group.strike_price} for expiration "
                        f"{group.expiration_date} is not in real option chain. "
                        f"Real strikes: {real_strikes}"
                    )
                    if self.logger:
                        self.logger.log_error(
                            error_msg,
                            context={
                                "symbol": symbol,
                                "expiration": str(group.expiration_date),
                                "synthetic_strike": group.strike_price,
                                "real_strikes": real_strikes
                            }
                        )
                    raise ValueError(error_msg)
                
                if self.logger:
                    self.logger.log_info(
                        f"Strike {group.strike_price} validated for expiration {group.expiration_date}",
                        {
                            "symbol": symbol,
                            "expiration": str(group.expiration_date),
                            "strike": group.strike_price,
                            "real_strikes_count": len(real_strikes)
                        }
                    )
                    
            except ValueError:
                # Re-raise validation errors
                raise
            except Exception as e:
                error_msg = f"Error validating strikes for {symbol} expiration {group.expiration_date}: {str(e)}"
                if self.logger:
                    self.logger.log_error(error_msg, e, {"symbol": symbol})
                raise ValueError(error_msg) from e
        
        if self.logger:
            self.logger.log_info(
                f"All strikes validated as real (no synthetic strikes) for {symbol}",
                {"symbol": symbol, "validated_groups": len(expiration_groups)}
            )
        
        return True
    
    def calculate_cost_basis_impact(self, position_summary: PositionSummary, estimated_premium: float) -> Tuple[float, float, float, float]:
        """Calculate cost basis impact of the tiered covered call strategy.
        
        This method calculates how the strategy will affect the cost basis of the position:
        1. Determines original cost basis per share
        2. Calculates effective cost basis after premium collection
        3. Computes cost basis reduction per share and percentage
        
        Args:
            position_summary: Current position summary with cost basis information
            estimated_premium: Total estimated premium to be collected from strategy
            
        Returns:
            Tuple of (original_cost_basis, effective_cost_basis, cost_basis_reduction_per_share, reduction_percentage)
            
        Raises:
            ValueError: If cost basis cannot be calculated
        """
        symbol = position_summary.symbol
        total_shares = position_summary.total_shares
        
        if self.logger:
            self.logger.log_info(
                f"Calculating cost basis impact for {symbol}",
                {
                    "symbol": symbol,
                    "total_shares": total_shares,
                    "estimated_premium": estimated_premium
                }
            )
        
        try:
            # Get original cost basis from position summary or cost basis tracker
            original_cost_basis = position_summary.average_cost_basis
            
            if original_cost_basis is None:
                # Try to get from cost basis tracker
                try:
                    cost_basis_summary = self.cost_basis_tracker.get_cost_basis_summary(symbol)
                    original_cost_basis = cost_basis_summary.original_cost_basis_per_share
                except ValueError:
                    # No cost basis data available - use current price as fallback
                    original_cost_basis = position_summary.current_price
                    if self.logger:
                        self.logger.log_warning(
                            f"No cost basis data available for {symbol}, using current price as estimate",
                            {"current_price": original_cost_basis}
                        )
            
            if original_cost_basis <= 0:
                raise ValueError(f"Invalid original cost basis: {original_cost_basis}")
            
            if total_shares <= 0:
                raise ValueError(f"Invalid total shares: {total_shares}")
            
            # Get existing cumulative premium
            existing_premium = position_summary.cumulative_premium_collected or 0.0
            
            # Calculate total premium after this strategy
            total_premium_after_strategy = existing_premium + estimated_premium
            
            # Calculate effective cost basis after strategy
            effective_cost_basis = self.cost_basis_tracker.calculate_effective_cost_basis(
                original_cost_basis, total_premium_after_strategy, total_shares
            )
            
            # Calculate cost basis reduction per share from this strategy
            cost_basis_reduction_per_share = estimated_premium / total_shares
            
            # Calculate percentage reduction from this strategy
            reduction_percentage = (cost_basis_reduction_per_share / original_cost_basis) * 100
            
            if self.logger:
                self.logger.log_info(
                    f"Cost basis impact calculated for {symbol}",
                    {
                        "symbol": symbol,
                        "original_cost_basis": original_cost_basis,
                        "effective_cost_basis": effective_cost_basis,
                        "cost_basis_reduction_per_share": cost_basis_reduction_per_share,
                        "reduction_percentage": reduction_percentage,
                        "existing_premium": existing_premium,
                        "new_premium": estimated_premium,
                        "total_premium": total_premium_after_strategy
                    }
                )
            
            return original_cost_basis, effective_cost_basis, cost_basis_reduction_per_share, reduction_percentage
            
        except Exception as e:
            error_msg = f"Error calculating cost basis impact for {symbol}: {str(e)}"
            if self.logger:
                self.logger.log_error(error_msg, e, {"symbol": symbol})
            raise ValueError(error_msg) from e
    
    def calculate_strategy(self, position_summary: PositionSummary) -> TieredCoveredCallPlan:
        """Calculate complete tiered covered call strategy plan with comprehensive validation.
        
        This method orchestrates the entire strategy calculation process,
        combining expiration selection, strike calculation, and share division
        with comprehensive validation to prevent naked call creation.
        
        Args:
            position_summary: Summary of current positions for the symbol
            
        Returns:
            Complete TieredCoveredCallPlan with all strategy details
            
        Raises:
            ValueError: If strategy cannot be calculated due to insufficient data or shares
        """
        symbol = position_summary.symbol
        current_price = position_summary.current_price
        available_shares = position_summary.available_shares
        total_shares = position_summary.total_shares
        
        if self.logger:
            self.logger.log_info(
                f"Starting tiered covered call strategy calculation for {symbol}",
                {
                    "symbol": symbol,
                    "current_price": current_price,
                    "total_shares": total_shares,
                    "available_shares": available_shares,
                    "existing_short_calls": len(position_summary.existing_short_calls)
                }
            )
        
        # Comprehensive validation before strategy calculation
        try:
            # 1. Validate minimum requirements for tiered strategy
            min_req_validation = self.validator.validate_minimum_requirements(
                position_summary, min_shares_required=300
            )
            
            if not min_req_validation.is_valid:
                error_msg = f"Strategy validation failed for {symbol}: {min_req_validation.error_message}"
                if self.logger:
                    self.logger.log_error(error_msg, context={"symbol": symbol})
                raise ValueError(error_msg)
            
            # 2. Validate sufficient shares for basic covered calls
            basic_validation = self.validator.validate_sufficient_shares(
                position_summary, 1, 100  # At least 1 contract possible
            )
            
            if not basic_validation.is_valid:
                error_msg = f"Insufficient shares for any covered calls: {basic_validation.error_message}"
                if self.logger:
                    self.logger.log_error(error_msg, context={"symbol": symbol})
                raise ValueError(error_msg)
            
            if self.logger:
                self.logger.log_info(
                    f"Position validation passed for {symbol}",
                    {
                        "symbol": symbol,
                        "available_shares": available_shares,
                        "validation_passed": True
                    }
                )
            
        except Exception as validation_error:
            error_msg = f"Position validation failed for {symbol}: {str(validation_error)}"
            if self.logger:
                self.logger.log_error(error_msg, validation_error, {"symbol": symbol})
            raise ValueError(error_msg) from validation_error
        
        try:
            # Find available expiration dates
            if self.logger:
                self.logger.log_info(f"Finding expiration dates for {symbol}")
            
            expirations = self.find_next_three_expirations(symbol)
            
            if self.logger:
                self.logger.log_info(
                    f"Found {len(expirations)} expiration dates for {symbol}",
                    {
                        "symbol": symbol,
                        "expirations": [exp.isoformat() for exp in expirations]
                    }
                )
            
            # Calculate incremental strike prices
            if self.logger:
                self.logger.log_info(f"Calculating strike prices for {symbol}")
            
            strikes = self.calculate_incremental_strikes(symbol, current_price, expirations)
            
            if self.logger:
                self.logger.log_info(
                    f"Calculated strike prices for {symbol}",
                    {
                        "symbol": symbol,
                        "current_price": current_price,
                        "strikes": strikes
                    }
                )
            
            # Divide shares into groups with validation
            if self.logger:
                self.logger.log_info(f"Dividing {available_shares} shares into {len(expirations)} groups for {symbol}")
            
            share_groups = self.divide_shares_into_groups(available_shares, len(expirations))
            
            if self.logger:
                self.logger.log_info(
                    f"Share division completed for {symbol}",
                    {
                        "symbol": symbol,
                        "available_shares": available_shares,
                        "share_groups": share_groups,
                        "total_allocated": sum(share_groups)
                    }
                )
            
            # Create and validate expiration groups
            expiration_groups = []
            total_contracts = 0
            estimated_total_premium = 0.0
            orders_for_validation = []
            
            for i, (expiration, strike, shares) in enumerate(zip(expirations, strikes, share_groups)):
                if shares >= 100:  # Only create groups with at least 100 shares
                    num_contracts = shares // 100
                    
                    # Create order for validation
                    order = CoveredCallOrder(
                        symbol=symbol,
                        strike=strike,
                        expiration=expiration,
                        quantity=num_contracts,
                        underlying_shares=shares
                    )
                    orders_for_validation.append(order)
                    
                    # Estimate premium (placeholder - would need real market data)
                    days_to_expiration = (expiration - date.today()).days
                    estimated_premium = max(0.50, (strike - current_price) * 0.1 + days_to_expiration * 0.02)
                    
                    group = ExpirationGroup(
                        expiration_date=expiration,
                        strike_price=strike,
                        num_contracts=num_contracts,
                        shares_used=shares,
                        estimated_premium_per_contract=estimated_premium
                    )
                    
                    expiration_groups.append(group)
                    total_contracts += num_contracts
                    estimated_total_premium += estimated_premium * num_contracts
                    
                    if self.logger:
                        self.logger.log_info(
                            f"Created expiration group {i+1} for {symbol}",
                            {
                                "symbol": symbol,
                                "expiration": expiration.isoformat(),
                                "strike": strike,
                                "contracts": num_contracts,
                                "shares": shares,
                                "estimated_premium": estimated_premium
                            }
                        )
            
            if not expiration_groups:
                error_msg = f"No valid expiration groups could be created with available shares for {symbol}"
                if self.logger:
                    self.logger.log_error(error_msg, context={"symbol": symbol, "available_shares": available_shares})
                raise ValueError(error_msg)
            
            # Final validation of all orders together
            if self.logger:
                self.logger.log_info(f"Performing final validation of {len(orders_for_validation)} orders for {symbol}")
            
            final_validation = self.validator.validate_existing_short_calls(
                position_summary, orders_for_validation
            )
            
            if not final_validation.is_valid:
                error_msg = f"Final order validation failed for {symbol}: {final_validation.error_message}"
                if self.logger:
                    self.logger.log_error(error_msg, context={"symbol": symbol})
                raise ValueError(error_msg)
            
            if final_validation.warning_message and self.logger:
                self.logger.log_warning(
                    f"Strategy validation warning for {symbol}: {final_validation.warning_message}",
                    {"symbol": symbol}
                )
            
            # Validate no synthetic strikes are present in the strategy plan
            try:
                self.validate_no_synthetic_strikes(symbol, expiration_groups)
            except ValueError as validation_error:
                error_msg = f"Synthetic strike validation failed for {symbol}: {str(validation_error)}"
                if self.logger:
                    self.logger.log_error(error_msg, validation_error, {"symbol": symbol})
                raise ValueError(error_msg) from validation_error
            
            # Calculate cost basis impact
            try:
                original_cost_basis, effective_cost_basis, cost_basis_reduction_per_share, reduction_percentage = self.calculate_cost_basis_impact(
                    position_summary, estimated_total_premium
                )
                
                if self.logger:
                    self.logger.log_info(
                        f"Cost basis impact for {symbol}",
                        {
                            "original_cost_basis": original_cost_basis,
                            "effective_cost_basis": effective_cost_basis,
                            "cost_basis_reduction_per_share": cost_basis_reduction_per_share,
                            "reduction_percentage": reduction_percentage
                        }
                    )
                
            except Exception as e:
                if self.logger:
                    self.logger.log_warning(f"Could not calculate cost basis impact for {symbol}: {str(e)}")
                original_cost_basis = None
                effective_cost_basis = None
                cost_basis_reduction_per_share = None
                reduction_percentage = None
            
            # Create final plan
            plan = TieredCoveredCallPlan(
                symbol=symbol,
                current_price=current_price,
                total_shares=available_shares,
                expiration_groups=expiration_groups,
                total_contracts=total_contracts,
                estimated_premium=estimated_total_premium,
                original_cost_basis=original_cost_basis,
                effective_cost_basis=effective_cost_basis,
                cost_basis_reduction=cost_basis_reduction_per_share,
                cost_basis_reduction_percentage=reduction_percentage
            )
            
            if self.logger:
                self.logger.log_info(
                    f"Tiered covered call strategy calculation completed for {symbol}",
                    {
                        "symbol": symbol,
                        "total_contracts": total_contracts,
                        "expiration_groups": len(expiration_groups),
                        "estimated_premium": estimated_total_premium,
                        "shares_allocated": sum(group.shares_used for group in expiration_groups)
                    }
                )
            
            return plan
            
        except Exception as e:
            error_msg = f"Error calculating tiered covered call strategy for {symbol}: {str(e)}"
            if self.logger:
                self.logger.log_error(error_msg, e, {"symbol": symbol})
            raise ValueError(error_msg) from e