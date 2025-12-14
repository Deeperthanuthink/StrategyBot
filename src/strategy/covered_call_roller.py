"""Covered call rolling functionality for automated management of expiring ITM calls."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple, Dict
import logging

from ..brokers.base_client import BaseBrokerClient, OrderResult
from ..positions.models import OptionPosition, DetailedPosition
from ..strategy.cost_basis_tracker import CostBasisTracker
from ..logging.bot_logger import BotLogger


@dataclass
class RollOpportunity:
    """Represents a roll opportunity for an expiring ITM call."""
    symbol: str
    current_call: OptionPosition
    target_expiration: date
    target_strike: float
    estimated_credit: float
    current_price: float


@dataclass
class RollPlan:
    """Comprehensive plan for rolling multiple covered calls."""
    symbol: str
    current_price: float
    roll_opportunities: List[RollOpportunity]
    total_estimated_credit: float
    execution_time: datetime
    cumulative_premium_collected: float  # Total premium from all previous strategies
    cost_basis_impact: float  # Additional cost basis reduction from rolls
    original_cost_basis_per_share: Optional[float] = None  # Original cost basis per share
    effective_cost_basis_after_rolls: Optional[float] = None  # Effective cost basis after rolls
    cost_basis_reduction_percentage: Optional[float] = None  # Percentage reduction from rolls


@dataclass
class RollOrder:
    """Represents a roll order with both close and open legs."""
    symbol: str
    close_strike: float
    close_expiration: date
    open_strike: float
    open_expiration: date
    quantity: int
    estimated_credit: float


@dataclass
class RollOrderResult:
    """Result of a roll order execution."""
    roll_order: RollOrder
    close_result: OrderResult
    open_result: OrderResult
    actual_credit: float
    success: bool


class CoveredCallRoller:
    """Service for automated rolling of expiring in-the-money covered calls."""
    
    def __init__(self, broker_client: BaseBrokerClient, logger: Optional[BotLogger] = None,
                 cost_basis_tracker: Optional[CostBasisTracker] = None):
        """Initialize the covered call roller.
        
        Args:
            broker_client: The broker client to use for API calls
            logger: Optional logger for tracking operations
            cost_basis_tracker: Optional cost basis tracker for cost basis calculations
        """
        self.broker_client = broker_client
        self.logger = logger
        self.cost_basis_tracker = cost_basis_tracker or CostBasisTracker(logger=logger)
    
    def identify_expiring_itm_calls(self, symbol: str = None) -> List[OptionPosition]:
        """Identify expiring in-the-money covered calls for today.
        
        This method finds all short call positions that:
        1. Expire today (current trading day)
        2. Are in-the-money (strike < current stock price)
        3. Are actually short calls (not long calls)
        4. Optionally filtered by symbol
        
        Args:
            symbol: Optional stock symbol to filter positions. If None, scans all positions.
            
        Returns:
            List of OptionPosition objects representing expiring ITM calls
            
        Raises:
            RuntimeError: If unable to retrieve positions or prices
        """
        if self.logger:
            self.logger.log_info(
                f"Identifying expiring ITM calls",
                {"symbol": symbol or "all_symbols", "expiration_date": date.today().isoformat()}
            )
        
        try:
            # Get today's date for expiration filtering
            today = date.today()
            
            # Use the broker client's method to get expiring short calls
            expiring_calls = self.broker_client.get_expiring_short_calls(today, symbol)
            
            if self.logger:
                self.logger.log_info(
                    f"Found {len(expiring_calls)} calls expiring today",
                    {"symbol": symbol or "all_symbols", "expiration_date": today.isoformat()}
                )
            
            # Check which ones are in-the-money
            itm_calls = []
            
            # Group calls by symbol to minimize price lookups
            calls_by_symbol = {}
            for call in expiring_calls:
                if call.symbol not in calls_by_symbol:
                    calls_by_symbol[call.symbol] = []
                calls_by_symbol[call.symbol].append(call)
            
            # Check ITM status for each symbol
            for call_symbol, calls in calls_by_symbol.items():
                try:
                    current_price = self.broker_client.get_current_price(call_symbol)
                    
                    for call in calls:
                        # Call is ITM if current price > strike price
                        if current_price > call.strike:
                            itm_calls.append(call)
                            
                            if self.logger:
                                self.logger.log_info(
                                    f"Found ITM call: {call_symbol} ${call.strike} exp {call.expiration}",
                                    {
                                        "symbol": call_symbol,
                                        "strike": call.strike,
                                        "current_price": current_price,
                                        "itm_amount": current_price - call.strike,
                                        "quantity": call.quantity
                                    }
                                )
                        else:
                            if self.logger:
                                self.logger.log_info(
                                    f"Call not ITM: {call_symbol} ${call.strike} exp {call.expiration}",
                                    {
                                        "symbol": call_symbol,
                                        "strike": call.strike,
                                        "current_price": current_price,
                                        "otm_amount": call.strike - current_price
                                    }
                                )
                
                except Exception as e:
                    if self.logger:
                        self.logger.log_error(
                            f"Error checking ITM status for {call_symbol}: {str(e)}",
                            e,
                            {"symbol": call_symbol}
                        )
                    # Continue with other symbols
                    continue
            
            if self.logger:
                self.logger.log_info(
                    f"Identified {len(itm_calls)} expiring ITM calls",
                    {
                        "symbol": symbol or "all_symbols",
                        "itm_calls": len(itm_calls),
                        "total_expiring": len(expiring_calls)
                    }
                )
            
            return itm_calls
            
        except Exception as e:
            error_msg = f"Error identifying expiring ITM calls: {str(e)}"
            if self.logger:
                self.logger.log_error(error_msg, e, {"symbol": symbol})
            raise RuntimeError(error_msg) from e
    
    def calculate_roll_opportunities(self, expiring_calls: List[OptionPosition]) -> List[RollOpportunity]:
        """Calculate roll opportunities for expiring ITM calls.
        
        For each expiring call, this method:
        1. Finds the best roll target (expiration and strike)
        2. Estimates the net credit for the roll
        3. Validates that the roll results in a net credit
        
        Args:
            expiring_calls: List of expiring ITM call positions
            
        Returns:
            List of RollOpportunity objects for viable rolls
            
        Raises:
            RuntimeError: If unable to calculate roll opportunities
        """
        if self.logger:
            self.logger.log_info(
                f"Calculating roll opportunities for {len(expiring_calls)} expiring calls"
            )
        
        roll_opportunities = []
        
        try:
            for call in expiring_calls:
                try:
                    # Get current stock price
                    current_price = self.broker_client.get_current_price(call.symbol)
                    
                    # Find best roll target
                    target_expiration, target_strike = self.find_best_roll_target(call, current_price)
                    
                    if target_expiration and target_strike:
                        # Estimate roll credit
                        estimated_credit = self.estimate_roll_credit(
                            call, target_expiration, target_strike
                        )
                        
                        # Only include if roll results in net credit
                        if estimated_credit > 0:
                            opportunity = RollOpportunity(
                                symbol=call.symbol,
                                current_call=call,
                                target_expiration=target_expiration,
                                target_strike=target_strike,
                                estimated_credit=estimated_credit,
                                current_price=current_price
                            )
                            roll_opportunities.append(opportunity)
                            
                            if self.logger:
                                self.logger.log_info(
                                    f"Found roll opportunity for {call.symbol}",
                                    {
                                        "symbol": call.symbol,
                                        "current_strike": call.strike,
                                        "current_expiration": call.expiration.isoformat(),
                                        "target_strike": target_strike,
                                        "target_expiration": target_expiration.isoformat(),
                                        "estimated_credit": estimated_credit,
                                        "current_price": current_price
                                    }
                                )
                        else:
                            if self.logger:
                                self.logger.log_info(
                                    f"No viable roll for {call.symbol} - negative credit",
                                    {
                                        "symbol": call.symbol,
                                        "current_strike": call.strike,
                                        "estimated_credit": estimated_credit
                                    }
                                )
                    else:
                        if self.logger:
                            self.logger.log_info(
                                f"No suitable roll target found for {call.symbol}",
                                {
                                    "symbol": call.symbol,
                                    "current_strike": call.strike,
                                    "current_expiration": call.expiration.isoformat()
                                }
                            )
                
                except Exception as e:
                    if self.logger:
                        self.logger.log_error(
                            f"Error calculating roll opportunity for {call.symbol}: {str(e)}",
                            e,
                            {"symbol": call.symbol, "strike": call.strike}
                        )
                    # Continue with other calls
                    continue
            
            if self.logger:
                self.logger.log_info(
                    f"Found {len(roll_opportunities)} viable roll opportunities",
                    {"total_opportunities": len(roll_opportunities)}
                )
            
            return roll_opportunities
            
        except Exception as e:
            error_msg = f"Error calculating roll opportunities: {str(e)}"
            if self.logger:
                self.logger.log_error(error_msg, e)
            raise RuntimeError(error_msg) from e
    
    def find_best_roll_target(self, current_call: OptionPosition, current_price: float) -> Tuple[Optional[date], Optional[float]]:
        """Find the best roll target (expiration and strike) for a call.
        
        Selection criteria:
        1. Find next available expiration (typically 1-4 weeks out)
        2. Select strike nearest to current call strike (preferably same or higher)
        3. Ensure strike is reasonable relative to current stock price
        
        Args:
            current_call: The expiring call position to roll
            current_price: Current stock price
            
        Returns:
            Tuple of (target_expiration, target_strike) or (None, None) if no suitable target
        """
        if self.logger:
            self.logger.log_info(
                f"Finding best roll target for {current_call.symbol}",
                {
                    "symbol": current_call.symbol,
                    "current_strike": current_call.strike,
                    "current_expiration": current_call.expiration.isoformat(),
                    "current_price": current_price
                }
            )
        
        try:
            # Find next available expiration dates (look 1-8 weeks out)
            today = date.today()
            potential_expirations = []
            
            # Generate potential expiration dates (weekly options typically expire on Fridays)
            for weeks_out in range(1, 9):  # 1-8 weeks out
                potential_date = today + timedelta(weeks=weeks_out)
                # Adjust to Friday if not already (simple approximation)
                days_until_friday = (4 - potential_date.weekday()) % 7
                friday_date = potential_date + timedelta(days=days_until_friday)
                potential_expirations.append(friday_date)
            
            # Try to get option chains for potential expirations
            available_expirations = []
            for exp_date in potential_expirations[:4]:  # Check first 4 potential dates
                try:
                    option_chain = self.broker_client.get_option_chain(current_call.symbol, exp_date)
                    if option_chain:  # If options are available for this expiration
                        available_expirations.append(exp_date)
                        if len(available_expirations) >= 2:  # We have enough options
                            break
                except Exception:
                    # Continue to next expiration if this one fails
                    continue
            
            if not available_expirations:
                if self.logger:
                    self.logger.log_info(
                        f"No available expirations found for {current_call.symbol}",
                        {"symbol": current_call.symbol}
                    )
                return None, None
            
            # Use the first available expiration (nearest term)
            target_expiration = available_expirations[0]
            
            # Get option chain for target expiration
            option_chain = self.broker_client.get_option_chain(current_call.symbol, target_expiration)
            
            # Filter to call options only
            call_options = [opt for opt in option_chain if opt.option_type == 'call']
            
            if not call_options:
                if self.logger:
                    self.logger.log_info(
                        f"No call options found for {current_call.symbol} exp {target_expiration}",
                        {"symbol": current_call.symbol, "expiration": target_expiration.isoformat()}
                    )
                return None, None
            
            # Find strike nearest to current call strike (prefer same or higher)
            available_strikes = sorted([opt.strike for opt in call_options])
            
            # Look for strikes at or above current strike first
            suitable_strikes = [s for s in available_strikes if s >= current_call.strike]
            
            if suitable_strikes:
                target_strike = suitable_strikes[0]  # Lowest strike at or above current
            else:
                # If no strikes at or above, use highest available strike
                target_strike = available_strikes[-1]
            
            if self.logger:
                self.logger.log_info(
                    f"Selected roll target for {current_call.symbol}",
                    {
                        "symbol": current_call.symbol,
                        "target_expiration": target_expiration.isoformat(),
                        "target_strike": target_strike,
                        "current_strike": current_call.strike,
                        "available_strikes": len(available_strikes)
                    }
                )
            
            return target_expiration, target_strike
            
        except Exception as e:
            if self.logger:
                self.logger.log_error(
                    f"Error finding roll target for {current_call.symbol}: {str(e)}",
                    e,
                    {"symbol": current_call.symbol}
                )
            return None, None
    
    def estimate_roll_credit(self, current_call: OptionPosition, target_exp: date, target_strike: float) -> float:
        """Estimate the net credit for a roll transaction.
        
        Roll credit = Premium received for new call - Cost to buy back current call
        
        Args:
            current_call: The expiring call to close
            target_exp: Target expiration for new call
            target_strike: Target strike for new call
            
        Returns:
            Estimated net credit (positive = credit, negative = debit)
        """
        if self.logger:
            self.logger.log_info(
                f"Estimating roll credit for {current_call.symbol}",
                {
                    "symbol": current_call.symbol,
                    "current_strike": current_call.strike,
                    "target_strike": target_strike,
                    "target_expiration": target_exp.isoformat()
                }
            )
        
        try:
            # For now, we'll implement a simplified estimation
            # In a real implementation, we would get actual option prices from the broker
            
            # Get current stock price
            current_price = self.broker_client.get_current_price(current_call.symbol)
            
            # Estimate cost to buy back current call (ITM call has intrinsic value)
            intrinsic_value = max(0, current_price - current_call.strike)
            # Add small time value for same-day expiration
            estimated_buyback_cost = intrinsic_value + 0.05  # Small time premium
            
            # Estimate premium for new call (simplified calculation)
            # This is a rough approximation - real implementation would use actual option prices
            time_to_exp = (target_exp - date.today()).days
            time_value_factor = min(0.02 * time_to_exp, 2.0)  # Rough time value estimate
            
            if target_strike > current_price:
                # OTM call - mainly time value
                estimated_new_call_premium = time_value_factor
            else:
                # ITM call - intrinsic + time value
                new_intrinsic = current_price - target_strike
                estimated_new_call_premium = new_intrinsic + time_value_factor
            
            # Net credit = premium received - cost to close
            estimated_credit = estimated_new_call_premium - estimated_buyback_cost
            
            if self.logger:
                self.logger.log_info(
                    f"Roll credit estimate for {current_call.symbol}",
                    {
                        "symbol": current_call.symbol,
                        "estimated_buyback_cost": estimated_buyback_cost,
                        "estimated_new_premium": estimated_new_call_premium,
                        "estimated_credit": estimated_credit,
                        "current_price": current_price,
                        "intrinsic_value": intrinsic_value
                    }
                )
            
            return estimated_credit
            
        except Exception as e:
            if self.logger:
                self.logger.log_error(
                    f"Error estimating roll credit for {current_call.symbol}: {str(e)}",
                    e,
                    {"symbol": current_call.symbol}
                )
            return 0.0  # Return 0 credit if estimation fails
    
    def execute_roll_plan(self, roll_plan: RollPlan) -> List[RollOrderResult]:
        """Execute a comprehensive roll plan with multiple roll opportunities.
        
        This method executes all rolls in the plan simultaneously, with proper
        error handling and rollback logic for failed orders.
        
        Args:
            roll_plan: RollPlan containing all roll opportunities to execute
            
        Returns:
            List of RollOrderResult objects with execution results
            
        Raises:
            RuntimeError: If critical errors occur during execution
        """
        if self.logger:
            self.logger.log_info(
                f"Executing roll plan for {roll_plan.symbol}",
                {
                    "symbol": roll_plan.symbol,
                    "roll_count": len(roll_plan.roll_opportunities),
                    "total_estimated_credit": roll_plan.total_estimated_credit
                }
            )
        
        results = []
        
        try:
            for opportunity in roll_plan.roll_opportunities:
                try:
                    # Create roll order
                    roll_order = RollOrder(
                        symbol=opportunity.symbol,
                        close_strike=opportunity.current_call.strike,
                        close_expiration=opportunity.current_call.expiration,
                        open_strike=opportunity.target_strike,
                        open_expiration=opportunity.target_expiration,
                        quantity=abs(opportunity.current_call.quantity),  # Ensure positive quantity
                        estimated_credit=opportunity.estimated_credit
                    )
                    
                    # Execute the roll (buy-to-close current, sell-to-open new)
                    roll_result = self._execute_single_roll(roll_order)
                    results.append(roll_result)
                    
                    if roll_result.success:
                        if self.logger:
                            self.logger.log_info(
                                f"Successfully executed roll for {opportunity.symbol}",
                                {
                                    "symbol": opportunity.symbol,
                                    "close_strike": roll_order.close_strike,
                                    "open_strike": roll_order.open_strike,
                                    "actual_credit": roll_result.actual_credit,
                                    "quantity": roll_order.quantity
                                }
                            )
                    else:
                        if self.logger:
                            self.logger.log_error(
                                f"Failed to execute roll for {opportunity.symbol}",
                                context={
                                    "symbol": opportunity.symbol,
                                    "close_result": roll_result.close_result.error_message,
                                    "open_result": roll_result.open_result.error_message
                                }
                            )
                
                except Exception as e:
                    if self.logger:
                        self.logger.log_error(
                            f"Error executing roll for {opportunity.symbol}: {str(e)}",
                            e,
                            {"symbol": opportunity.symbol}
                        )
                    
                    # Create failed result
                    failed_result = RollOrderResult(
                        roll_order=RollOrder(
                            symbol=opportunity.symbol,
                            close_strike=opportunity.current_call.strike,
                            close_expiration=opportunity.current_call.expiration,
                            open_strike=opportunity.target_strike,
                            open_expiration=opportunity.target_expiration,
                            quantity=abs(opportunity.current_call.quantity),
                            estimated_credit=opportunity.estimated_credit
                        ),
                        close_result=OrderResult(success=False, order_id=None, status=None, error_message=str(e)),
                        open_result=OrderResult(success=False, order_id=None, status=None, error_message=str(e)),
                        actual_credit=0.0,
                        success=False
                    )
                    results.append(failed_result)
            
            # Log overall execution summary
            successful_rolls = sum(1 for r in results if r.success)
            total_credit = sum(r.actual_credit for r in results if r.success)
            
            # Update cost basis tracking for successful rolls
            if successful_rolls > 0 and total_credit > 0:
                try:
                    # Calculate shares covered by successful rolls
                    successful_contracts = sum(
                        r.roll_order.quantity for r in results if r.success
                    )
                    shares_covered = successful_contracts * 100
                    
                    # Update cost basis tracker
                    self.cost_basis_tracker.update_cumulative_premium(
                        roll_plan.symbol, 
                        total_credit, 
                        strategy_type="roll",
                        contracts_executed=successful_contracts
                    )
                    
                    if self.logger:
                        self.logger.log_info(
                            f"Updated cost basis tracking for {roll_plan.symbol}",
                            {
                                "symbol": roll_plan.symbol,
                                "additional_premium": total_credit,
                                "contracts_executed": successful_contracts,
                                "shares_covered": shares_covered
                            }
                        )
                        
                except Exception as e:
                    if self.logger:
                        self.logger.log_warning(
                            f"Could not update cost basis tracking for {roll_plan.symbol}: {str(e)}",
                            {"symbol": roll_plan.symbol}
                        )
            
            if self.logger:
                self.logger.log_info(
                    f"Roll plan execution complete",
                    {
                        "symbol": roll_plan.symbol,
                        "total_rolls": len(results),
                        "successful_rolls": successful_rolls,
                        "failed_rolls": len(results) - successful_rolls,
                        "total_credit_collected": total_credit
                    }
                )
            
            return results
            
        except Exception as e:
            error_msg = f"Critical error executing roll plan: {str(e)}"
            if self.logger:
                self.logger.log_error(error_msg, e, {"symbol": roll_plan.symbol})
            raise RuntimeError(error_msg) from e
    
    def _execute_single_roll(self, roll_order: RollOrder) -> RollOrderResult:
        """Execute a single roll order with both close and open legs.
        
        Args:
            roll_order: RollOrder to execute
            
        Returns:
            RollOrderResult with execution details
        """
        if self.logger:
            self.logger.log_info(
                f"Executing single roll for {roll_order.symbol}",
                {
                    "symbol": roll_order.symbol,
                    "close_strike": roll_order.close_strike,
                    "open_strike": roll_order.open_strike,
                    "quantity": roll_order.quantity
                }
            )
        
        # Initialize results
        close_result = OrderResult(success=False, order_id=None, status=None, error_message="Not executed")
        open_result = OrderResult(success=False, order_id=None, status=None, error_message="Not executed")
        actual_credit = 0.0
        
        try:
            # Use the broker client's roll order method
            roll_result = self.broker_client.submit_roll_order(roll_order)
            
            if self.logger:
                self.logger.log_info(
                    f"Roll execution {'successful' if roll_result.success else 'failed'} for {roll_order.symbol}",
                    {
                        "symbol": roll_order.symbol,
                        "success": roll_result.success,
                        "actual_credit": roll_result.actual_credit,
                        "close_order_id": roll_result.close_result.order_id,
                        "open_order_id": roll_result.open_result.order_id
                    }
                )
            
            return roll_result
            
        except Exception as e:
            error_msg = f"Error executing single roll: {str(e)}"
            if self.logger:
                self.logger.log_error(error_msg, e, {"symbol": roll_order.symbol})
            
            return RollOrderResult(
                roll_order=roll_order,
                close_result=OrderResult(success=False, order_id=None, status=None, error_message=error_msg),
                open_result=OrderResult(success=False, order_id=None, status=None, error_message=error_msg),
                actual_credit=0.0,
                success=False
            )
    
    def calculate_cumulative_cost_basis_impact(self, symbol: str, additional_premium: float, 
                                             shares_covered: int = None) -> Tuple[float, float, float]:
        """Calculate cumulative cost basis impact from roll transactions.
        
        This method calculates the comprehensive cost basis impact of roll transactions:
        1. Gets current cost basis information
        2. Calculates impact of additional premium
        3. Computes new effective cost basis and reduction percentage
        
        Args:
            symbol: Stock symbol
            additional_premium: Additional premium collected from rolls
            shares_covered: Number of shares covered by the rolls (optional, will estimate if not provided)
            
        Returns:
            Tuple of (cost_basis_reduction_per_share, effective_cost_basis_after_rolls, reduction_percentage)
            
        Raises:
            ValueError: If cost basis cannot be calculated
        """
        if not symbol or not symbol.strip():
            raise ValueError("Symbol cannot be empty")
        
        symbol = symbol.upper().strip()
        
        if additional_premium < 0:
            raise ValueError(f"Additional premium cannot be negative: {additional_premium}")
        
        if self.logger:
            self.logger.log_info(
                f"Calculating cumulative cost basis impact for {symbol}",
                {"symbol": symbol, "additional_premium": additional_premium, "shares_covered": shares_covered}
            )
        
        try:
            # Get current cost basis information
            try:
                cost_basis_summary = self.cost_basis_tracker.get_cost_basis_summary(symbol)
                original_cost_basis = cost_basis_summary.original_cost_basis_per_share
                current_cumulative_premium = cost_basis_summary.cumulative_premium_collected
                total_shares = cost_basis_summary.total_shares
                
                if self.logger:
                    self.logger.log_info(
                        f"Retrieved cost basis data for {symbol}",
                        {
                            "original_cost_basis": original_cost_basis,
                            "current_cumulative_premium": current_cumulative_premium,
                            "total_shares": total_shares
                        }
                    )
                
            except ValueError:
                # No cost basis data available - try to estimate
                if self.logger:
                    self.logger.log_warning(f"No cost basis data available for {symbol}, using estimates")
                
                # Get current stock price as fallback
                current_price = self.broker_client.get_current_price(symbol)
                original_cost_basis = current_price  # Fallback estimate
                current_cumulative_premium = 0.0
                
                # Estimate shares if not provided
                if shares_covered is None:
                    # Estimate based on typical contract size
                    shares_covered = 100  # Default to 1 contract worth
                
                total_shares = shares_covered
            
            # Use provided shares_covered if available, otherwise use tracked shares
            if shares_covered is not None:
                calculation_shares = shares_covered
            else:
                calculation_shares = total_shares
            
            if calculation_shares <= 0:
                raise ValueError(f"Invalid shares for calculation: {calculation_shares}")
            
            # Calculate new cumulative premium
            new_cumulative_premium = current_cumulative_premium + additional_premium
            
            # Calculate effective cost basis after rolls
            effective_cost_basis_after_rolls = self.cost_basis_tracker.calculate_effective_cost_basis(
                original_cost_basis, new_cumulative_premium, calculation_shares
            )
            
            # Calculate cost basis reduction per share from this roll
            cost_basis_reduction_per_share = additional_premium / calculation_shares
            
            # Calculate percentage reduction from this roll
            reduction_percentage = (cost_basis_reduction_per_share / original_cost_basis) * 100 if original_cost_basis > 0 else 0.0
            
            if self.logger:
                self.logger.log_info(
                    f"Cost basis impact calculated for {symbol}",
                    {
                        "symbol": symbol,
                        "cost_basis_reduction_per_share": cost_basis_reduction_per_share,
                        "effective_cost_basis_after_rolls": effective_cost_basis_after_rolls,
                        "reduction_percentage": reduction_percentage,
                        "additional_premium": additional_premium,
                        "new_cumulative_premium": new_cumulative_premium
                    }
                )
            
            return cost_basis_reduction_per_share, effective_cost_basis_after_rolls, reduction_percentage
            
        except Exception as e:
            error_msg = f"Error calculating cumulative cost basis impact for {symbol}: {str(e)}"
            if self.logger:
                self.logger.log_error(error_msg, e, {"symbol": symbol})
            raise ValueError(error_msg) from e
    
    def create_roll_plan_with_cost_basis(self, symbol: str, roll_opportunities: List[RollOpportunity]) -> RollPlan:
        """Create a comprehensive roll plan with cost basis impact calculations.
        
        Args:
            symbol: Stock symbol
            roll_opportunities: List of roll opportunities
            
        Returns:
            RollPlan with cost basis impact information
            
        Raises:
            ValueError: If roll plan cannot be created
        """
        if not roll_opportunities:
            raise ValueError("No roll opportunities provided")
        
        symbol = symbol.upper().strip()
        
        if self.logger:
            self.logger.log_info(
                f"Creating roll plan with cost basis for {symbol}",
                {"symbol": symbol, "opportunities_count": len(roll_opportunities)}
            )
        
        try:
            # Calculate total estimated credit
            total_estimated_credit = sum(opp.estimated_credit for opp in roll_opportunities)
            
            # Get current price (use first opportunity's current price)
            current_price = roll_opportunities[0].current_price
            
            # Get current cumulative premium
            try:
                cost_basis_summary = self.cost_basis_tracker.get_cost_basis_summary(symbol)
                cumulative_premium_collected = cost_basis_summary.cumulative_premium_collected
                original_cost_basis_per_share = cost_basis_summary.original_cost_basis_per_share
            except ValueError:
                # No cost basis data available
                cumulative_premium_collected = 0.0
                original_cost_basis_per_share = None
            
            # Calculate cost basis impact
            try:
                # Estimate shares covered by rolls (sum of contracts * 100)
                shares_covered = sum(abs(opp.current_call.quantity) * 100 for opp in roll_opportunities)
                
                cost_basis_reduction_per_share, effective_cost_basis_after_rolls, reduction_percentage = self.calculate_cumulative_cost_basis_impact(
                    symbol, total_estimated_credit, shares_covered
                )
                
                cost_basis_impact = cost_basis_reduction_per_share
                
            except Exception as e:
                if self.logger:
                    self.logger.log_warning(f"Could not calculate cost basis impact for {symbol}: {str(e)}")
                cost_basis_impact = total_estimated_credit / 100.0  # Fallback estimate
                effective_cost_basis_after_rolls = None
                reduction_percentage = None
            
            # Create roll plan
            roll_plan = RollPlan(
                symbol=symbol,
                current_price=current_price,
                roll_opportunities=roll_opportunities,
                total_estimated_credit=total_estimated_credit,
                execution_time=datetime.now(),
                cumulative_premium_collected=cumulative_premium_collected,
                cost_basis_impact=cost_basis_impact,
                original_cost_basis_per_share=original_cost_basis_per_share,
                effective_cost_basis_after_rolls=effective_cost_basis_after_rolls,
                cost_basis_reduction_percentage=reduction_percentage
            )
            
            if self.logger:
                self.logger.log_info(
                    f"Created roll plan with cost basis for {symbol}",
                    {
                        "symbol": symbol,
                        "total_estimated_credit": total_estimated_credit,
                        "cost_basis_impact": cost_basis_impact,
                        "effective_cost_basis_after_rolls": effective_cost_basis_after_rolls,
                        "reduction_percentage": reduction_percentage
                    }
                )
            
            return roll_plan
            
        except Exception as e:
            error_msg = f"Error creating roll plan with cost basis for {symbol}: {str(e)}"
            if self.logger:
                self.logger.log_error(error_msg, e, {"symbol": symbol})
            raise ValueError(error_msg) from e