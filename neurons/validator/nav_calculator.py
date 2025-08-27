"""
NAV Calculation Engine

This module implements the Net Asset Value (NAV) calculation system for TAO20.
It calculates NAV at specific blocks, integrates with Bittensor pricing functions,
and provides validation and historical tracking.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import json
import hashlib

logger = logging.getLogger(__name__)


class NAVCalculationStatus(Enum):
    """Status of NAV calculation"""
    PENDING = "pending"
    CALCULATING = "calculating"
    COMPLETED = "completed"
    FAILED = "failed"
    INVALID = "invalid"


@dataclass
class NAVCalculation:
    """Represents a NAV calculation result"""
    epoch_id: int
    block_number: int
    timestamp: int
    nav_per_share: int  # In wei (1e18 precision)
    total_value: int  # Total value of underlying assets in wei
    total_shares: int  # Total TAO20 shares outstanding
    asset_prices: Dict[int, int] = field(default_factory=dict)  # netuid -> price in wei
    asset_holdings: Dict[int, int] = field(default_factory=dict)  # netuid -> quantity
    calculation_hash: str = ""
    status: NAVCalculationStatus = NAVCalculationStatus.PENDING
    error_message: str = ""
    calculation_time_ms: int = 0


@dataclass
class PricingInput:
    """Input data for pricing calculation"""
    netuid: int
    block_number: int
    timestamp: int
    market_data: Dict = field(default_factory=dict)


class NAVCalculator:
    """
    NAV Calculator for TAO20 index
    
    Calculates Net Asset Value at specific blocks using Bittensor pricing functions
    and provides validation and historical tracking.
    """
    
    def __init__(
        self,
        min_validators_for_price: int = 3,
        price_freshness_seconds: int = 300,  # 5 minutes
        nav_precision: int = 18,  # 1e18 precision
        max_price_deviation_bps: int = 500  # 5% max deviation
    ):
        self.min_validators_for_price = min_validators_for_price
        self.price_freshness_seconds = price_freshness_seconds
        self.nav_precision = nav_precision
        self.max_price_deviation_bps = max_price_deviation_bps
        
        # Storage for calculations
        self.nav_history: Dict[str, NAVCalculation] = {}
        self.price_history: Dict[int, Dict[int, int]] = {}  # block -> netuid -> price
        
        # Mock pricing data (replace with real Bittensor integration)
        self.mock_prices: Dict[int, int] = {
            1: 1000000000000000000,  # 1 TAO
            2: 950000000000000000,   # 0.95 TAO
            3: 1050000000000000000,  # 1.05 TAO
            # ... add more mock prices for all 20 subnets
        }
        
        logger.info(f"NAVCalculator initialized with precision {nav_precision}")

    async def calculate_nav_at_block(
        self,
        epoch_id: int,
        block_number: int,
        asset_holdings: Dict[int, int],
        total_shares: int
    ) -> NAVCalculation:
        """
        Calculate NAV at a specific block number
        
        Args:
            epoch_id: Current epoch ID
            block_number: Block number for NAV calculation
            asset_holdings: Current holdings of each subnet token
            total_shares: Total TAO20 shares outstanding
            
        Returns:
            NAVCalculation with the calculated NAV
        """
        start_time = time.time()
        calculation_id = f"nav_{epoch_id}_{block_number}_{int(start_time)}"
        
        logger.info(f"Calculating NAV for epoch {epoch_id} at block {block_number}")
        
        nav_calc = NAVCalculation(
            epoch_id=epoch_id,
            block_number=block_number,
            timestamp=int(start_time),
            total_shares=total_shares,
            status=NAVCalculationStatus.CALCULATING
        )
        
        try:
            # Get asset prices at the specific block
            asset_prices = await self._get_asset_prices_at_block(block_number)
            nav_calc.asset_prices = asset_prices
            
            # Calculate total value of underlying assets
            total_value = 0
            for netuid, quantity in asset_holdings.items():
                if netuid in asset_prices:
                    price = asset_prices[netuid]
                    asset_value = (quantity * price) // (10 ** self.nav_precision)
                    total_value += asset_value
                    nav_calc.asset_holdings[netuid] = quantity
                else:
                    logger.warning(f"No price available for subnet {netuid}")
            
            nav_calc.total_value = total_value
            
            # Calculate NAV per share
            if total_shares > 0:
                nav_per_share = (total_value * (10 ** self.nav_precision)) // total_shares
            else:
                nav_per_share = 0
                
            nav_calc.nav_per_share = nav_per_share
            
            # Generate calculation hash for verification
            nav_calc.calculation_hash = self._generate_calculation_hash(nav_calc)
            
            # Validate the calculation
            if await self._validate_nav_calculation(nav_calc):
                nav_calc.status = NAVCalculationStatus.COMPLETED
                logger.info(f"NAV calculation completed: {nav_per_share / (10 ** self.nav_precision):.6f} TAO")
            else:
                nav_calc.status = NAVCalculationStatus.INVALID
                nav_calc.error_message = "NAV calculation validation failed"
                logger.error("NAV calculation validation failed")
                
        except Exception as e:
            nav_calc.status = NAVCalculationStatus.FAILED
            nav_calc.error_message = str(e)
            logger.error(f"NAV calculation failed: {e}")
        
        # Record calculation time
        nav_calc.calculation_time_ms = int((time.time() - start_time) * 1000)
        
        # Store in history
        self.nav_history[calculation_id] = nav_calc
        
        return nav_calc

    async def _get_asset_prices_at_block(self, block_number: int) -> Dict[int, int]:
        """
        Get asset prices at a specific block number
        
        Args:
            block_number: Block number for price retrieval
            
        Returns:
            Dictionary mapping netuid to price in wei
        """
        # TODO: Replace with real Bittensor pricing integration
        # This would typically call the official Bittensor pricing functions
        # or use validator consensus pricing
        
        logger.info(f"Getting asset prices at block {block_number}")
        
        # For now, use mock prices with some block-based variation
        prices = {}
        for netuid, base_price in self.mock_prices.items():
            # Add some block-based variation to simulate real pricing
            variation = (block_number % 1000) / 10000  # Small variation
            price = int(base_price * (1 + variation))
            prices[netuid] = price
            
        return prices

    def _generate_calculation_hash(self, nav_calc: NAVCalculation) -> str:
        """
        Generate a hash for NAV calculation verification
        
        Args:
            nav_calc: NAV calculation to hash
            
        Returns:
            Hash string for verification
        """
        # Create a deterministic string representation
        data = {
            "epoch_id": nav_calc.epoch_id,
            "block_number": nav_calc.block_number,
            "asset_prices": dict(sorted(nav_calc.asset_prices.items())),
            "asset_holdings": dict(sorted(nav_calc.asset_holdings.items())),
            "total_shares": nav_calc.total_shares,
            "nav_per_share": nav_calc.nav_per_share,
            "total_value": nav_calc.total_value
        }
        
        data_str = json.dumps(data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(data_str.encode()).hexdigest()

    async def _validate_nav_calculation(self, nav_calc: NAVCalculation) -> bool:
        """
        Validate NAV calculation for reasonableness
        
        Args:
            nav_calc: NAV calculation to validate
            
        Returns:
            True if validation passes, False otherwise
        """
        try:
            # Check for reasonable NAV per share
            if nav_calc.nav_per_share < 0:
                logger.error("NAV per share is negative")
                return False
                
            # Check for reasonable total value
            if nav_calc.total_value < 0:
                logger.error("Total value is negative")
                return False
                
            # Check for reasonable total shares
            if nav_calc.total_shares < 0:
                logger.error("Total shares is negative")
                return False
                
            # Check price consistency
            for netuid, price in nav_calc.asset_prices.items():
                if price <= 0:
                    logger.error(f"Invalid price for subnet {netuid}: {price}")
                    return False
                    
                # Check for extreme price deviations
                if netuid in self.mock_prices:
                    base_price = self.mock_prices[netuid]
                    deviation = abs(price - base_price) / base_price
                    if deviation > (self.max_price_deviation_bps / 10000):
                        logger.warning(f"Large price deviation for subnet {netuid}: {deviation:.2%}")
                        
            # Verify calculation hash
            expected_hash = self._generate_calculation_hash(nav_calc)
            if nav_calc.calculation_hash != expected_hash:
                logger.error("Calculation hash mismatch")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"NAV validation error: {e}")
            return False

    async def get_nav_history(
        self,
        epoch_id: Optional[int] = None,
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
        limit: int = 100
    ) -> List[NAVCalculation]:
        """
        Get NAV calculation history with optional filtering
        
        Args:
            epoch_id: Filter by epoch ID
            start_block: Filter by start block number
            end_block: Filter by end block number
            limit: Maximum number of results
            
        Returns:
            List of NAV calculations matching criteria
        """
        results = []
        
        for calc in self.nav_history.values():
            if epoch_id is not None and calc.epoch_id != epoch_id:
                continue
            if start_block is not None and calc.block_number < start_block:
                continue
            if end_block is not None and calc.block_number > end_block:
                continue
                
            results.append(calc)
            
        # Sort by timestamp (newest first)
        results.sort(key=lambda x: x.timestamp, reverse=True)
        
        return results[:limit]

    async def get_latest_nav(self, epoch_id: Optional[int] = None) -> Optional[NAVCalculation]:
        """
        Get the latest NAV calculation
        
        Args:
            epoch_id: Optional epoch ID filter
            
        Returns:
            Latest NAV calculation or None
        """
        history = await self.get_nav_history(epoch_id=epoch_id, limit=1)
        return history[0] if history else None

    async def verify_nav_calculation(
        self,
        epoch_id: int,
        block_number: int,
        expected_nav: int,
        asset_holdings: Dict[int, int],
        total_shares: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify a NAV calculation against expected values
        
        Args:
            epoch_id: Epoch ID
            block_number: Block number
            expected_nav: Expected NAV per share
            asset_holdings: Asset holdings at the time
            total_shares: Total shares at the time
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Calculate NAV at the specified block
            nav_calc = await self.calculate_nav_at_block(
                epoch_id=epoch_id,
                block_number=block_number,
                asset_holdings=asset_holdings,
                total_shares=total_shares
            )
            
            if nav_calc.status != NAVCalculationStatus.COMPLETED:
                return False, f"NAV calculation failed: {nav_calc.error_message}"
                
            # Check if NAV matches expected value within tolerance
            tolerance = (expected_nav * self.max_price_deviation_bps) // 10000
            if abs(nav_calc.nav_per_share - expected_nav) > tolerance:
                return False, f"NAV mismatch: calculated {nav_calc.nav_per_share}, expected {expected_nav}"
                
            return True, None
            
        except Exception as e:
            return False, f"Verification error: {e}"

    def get_calculation_statistics(self) -> Dict:
        """
        Get statistics about NAV calculations
        
        Returns:
            Dictionary with calculation statistics
        """
        if not self.nav_history:
            return {
                "total_calculations": 0,
                "successful_calculations": 0,
                "failed_calculations": 0,
                "average_calculation_time_ms": 0
            }
            
        total = len(self.nav_history)
        successful = sum(1 for calc in self.nav_history.values() 
                        if calc.status == NAVCalculationStatus.COMPLETED)
        failed = sum(1 for calc in self.nav_history.values() 
                    if calc.status in [NAVCalculationStatus.FAILED, NAVCalculationStatus.INVALID])
        
        avg_time = sum(calc.calculation_time_ms for calc in self.nav_history.values()) / total
        
        return {
            "total_calculations": total,
            "successful_calculations": successful,
            "failed_calculations": failed,
            "average_calculation_time_ms": int(avg_time)
        }

    async def cleanup_old_calculations(self, max_age_hours: int = 24) -> int:
        """
        Clean up old NAV calculations to save memory
        
        Args:
            max_age_hours: Maximum age in hours to keep
            
        Returns:
            Number of calculations removed
        """
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        to_remove = []
        for calc_id, calc in self.nav_history.items():
            if (current_time - calc.timestamp) > max_age_seconds:
                to_remove.append(calc_id)
                
        for calc_id in to_remove:
            del self.nav_history[calc_id]
            
        logger.info(f"Cleaned up {len(to_remove)} old NAV calculations")
        return len(to_remove)


class NAVValidator:
    """
    Validator for NAV calculations
    
    Provides additional validation and consensus mechanisms for NAV calculations.
    """
    
    def __init__(self, nav_calculator: NAVCalculator):
        self.nav_calculator = nav_calculator
        self.validator_consensus: Dict[str, Dict] = {}  # calculation_id -> validator_votes
        
    async def validate_nav_with_consensus(
        self,
        calculation_id: str,
        nav_calculation: NAVCalculation,
        validator_signatures: List[str]
    ) -> bool:
        """
        Validate NAV calculation with multiple validator consensus
        
        Args:
            calculation_id: Unique calculation ID
            nav_calculation: NAV calculation to validate
            validator_signatures: List of validator signatures
            
        Returns:
            True if consensus validation passes
        """
        # TODO: Implement multi-validator consensus validation
        # This would verify signatures and check for consensus threshold
        
        logger.info(f"Validating NAV calculation {calculation_id} with {len(validator_signatures)} signatures")
        
        # For now, just verify the calculation internally
        return await self.nav_calculator._validate_nav_calculation(nav_calculation)

    def record_validator_vote(
        self,
        calculation_id: str,
        validator_id: str,
        is_valid: bool,
        signature: str
    ) -> None:
        """
        Record a validator's vote on a NAV calculation
        
        Args:
            calculation_id: Calculation ID
            validator_id: Validator identifier
            is_valid: Whether the validator considers the calculation valid
            signature: Validator's signature
        """
        if calculation_id not in self.validator_consensus:
            self.validator_consensus[calculation_id] = {}
            
        self.validator_consensus[calculation_id][validator_id] = {
            "is_valid": is_valid,
            "signature": signature,
            "timestamp": int(time.time())
        }
        
        logger.info(f"Recorded validator vote: {validator_id} -> {is_valid} for {calculation_id}")

    def get_consensus_status(self, calculation_id: str) -> Dict:
        """
        Get consensus status for a calculation
        
        Args:
            calculation_id: Calculation ID
            
        Returns:
            Dictionary with consensus status
        """
        if calculation_id not in self.validator_consensus:
            return {
                "total_votes": 0,
                "valid_votes": 0,
                "invalid_votes": 0,
                "consensus_reached": False
            }
            
        votes = self.validator_consensus[calculation_id]
        total_votes = len(votes)
        valid_votes = sum(1 for vote in votes.values() if vote["is_valid"])
        invalid_votes = total_votes - valid_votes
        
        # Consensus threshold: 2/3 of validators must agree
        consensus_threshold = (total_votes * 2) // 3
        consensus_reached = valid_votes >= consensus_threshold
        
        return {
            "total_votes": total_votes,
            "valid_votes": valid_votes,
            "invalid_votes": invalid_votes,
            "consensus_reached": consensus_reached,
            "consensus_threshold": consensus_threshold
        }

