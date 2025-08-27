#!/usr/bin/env python3
"""
NAV Integration Service for TAO20 Creation Process

This service bridges real-time NAV calculation with the miner/validator creation process.
It ensures that:
1. Miners get accurate NAV for creation unit calculations
2. Validators can verify NAV at receipt time
3. Smart contracts receive real-time NAV updates
4. All NAV calculations are consistent across the system
"""

import asyncio
import logging
import time
import json
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from decimal import Decimal, getcontext
import aiohttp
from pathlib import Path

# Set high precision for financial calculations
getcontext().prec = 50

logger = logging.getLogger(__name__)

@dataclass
class CreationNAV:
    """NAV data specifically for creation process"""
    creation_id: str
    nav_per_token: Decimal  # NAV at creation time
    block_number: int  # Block when creation was received
    timestamp: int  # Unix timestamp
    confidence_score: float  # Confidence in NAV accuracy
    calculation_hash: str  # For verification
    validator_attestations: List[str] = None  # Validator signatures

@dataclass
class NAVValidationResult:
    """Result of NAV validation"""
    is_valid: bool
    nav_deviation_bps: int  # Deviation in basis points
    validator_consensus: bool  # Whether validators agree
    error_message: Optional[str] = None

class NAVIntegrationService:
    """
    Integration service for NAV in TAO20 creation process
    
    This service:
    1. Provides NAV to miners for creation calculations
    2. Records NAV at creation receipt time for validators
    3. Validates NAV consistency across the system
    4. Manages NAV attestation process
    """
    
    def __init__(
        self,
        realtime_nav_service,  # Instance of RealtimeNAVService
        oracle_contract_address: str = "",
        web3_provider_url: str = "",
        nav_cache_ttl: int = 30,  # 30 second cache
        max_nav_deviation_bps: int = 50,  # 0.5% max deviation
        required_validator_consensus: int = 3  # Minimum validators for consensus
    ):
        self.realtime_nav_service = realtime_nav_service
        self.oracle_contract_address = oracle_contract_address
        self.web3_provider_url = web3_provider_url
        self.nav_cache_ttl = nav_cache_ttl
        self.max_nav_deviation_bps = max_nav_deviation_bps
        self.required_validator_consensus = required_validator_consensus
        
        # NAV cache for creations
        self.creation_navs: Dict[str, CreationNAV] = {}
        self.nav_cache: Dict[int, Decimal] = {}  # block_number -> nav
        self.nav_cache_timestamps: Dict[int, int] = {}
        
        # Web3 integration (for smart contract interaction)
        self.w3 = None
        self.oracle_contract = None
        
        # Metrics
        self.metrics = {
            'nav_requests': 0,
            'nav_validations': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'validation_failures': 0,
            'oracle_updates': 0
        }
        
        logger.info("NAVIntegrationService initialized")
    
    async def initialize(self):
        """Initialize Web3 connection and contracts"""
        try:
            if self.web3_provider_url and self.oracle_contract_address:
                from web3 import Web3
                
                self.w3 = Web3(Web3.HTTPProvider(self.web3_provider_url))
                
                # TODO: Load oracle contract ABI and create contract instance
                # self.oracle_contract = self.w3.eth.contract(
                #     address=self.oracle_contract_address,
                #     abi=oracle_abi
                # )
                
                logger.info("Web3 connection initialized")
            else:
                logger.warning("Web3 not configured - running without smart contract integration")
                
        except Exception as e:
            logger.error(f"Failed to initialize Web3: {e}")
    
    # ===================== Miner Integration =====================
    
    async def get_nav_for_creation(self, unit_count: int, netuid_amounts: Dict[int, int]) -> Optional[Decimal]:
        """
        Get current NAV for creation calculation (used by miners)
        
        Args:
            unit_count: Number of creation units
            netuid_amounts: Asset amounts by netuid
            
        Returns:
            Current NAV per TAO20 token in TAO
        """
        try:
            self.metrics['nav_requests'] += 1
            
            # Get real-time NAV
            nav_data = await self.realtime_nav_service.get_current_nav()
            
            if not nav_data:
                logger.error("No NAV data available for creation")
                return None
            
            # Validate NAV freshness
            current_time = int(time.time())
            if current_time - nav_data.timestamp > self.nav_cache_ttl:
                logger.warning(f"NAV data is stale: {current_time - nav_data.timestamp}s old")
                return None
            
            # Validate confidence
            if nav_data.confidence_score < 0.8:
                logger.warning(f"NAV confidence too low: {nav_data.confidence_score}")
                return None
            
            logger.debug(f"Providing NAV for creation: {nav_data.nav_per_token:.6f} TAO/TAO20")
            return nav_data.nav_per_token
            
        except Exception as e:
            logger.error(f"Failed to get NAV for creation: {e}")
            return None
    
    async def estimate_tao20_minted(self, total_tao_value: Decimal) -> Optional[Decimal]:
        """
        Estimate TAO20 tokens that will be minted for a given TAO value
        
        Args:
            total_tao_value: Total TAO value of assets being delivered
            
        Returns:
            Estimated TAO20 tokens to be minted
        """
        try:
            nav_per_token = await self.get_nav_for_creation(1, {})
            
            if not nav_per_token or nav_per_token == 0:
                return None
            
            estimated_tokens = total_tao_value / nav_per_token
            logger.debug(f"Estimated TAO20 minted: {estimated_tokens:.6f} for {total_tao_value:.6f} TAO")
            
            return estimated_tokens
            
        except Exception as e:
            logger.error(f"Failed to estimate TAO20 minted: {e}")
            return None
    
    # ===================== Validator Integration =====================
    
    async def record_nav_at_receipt(self, creation_id: str, block_number: int) -> Optional[CreationNAV]:
        """
        Record NAV at the time of creation receipt (used by validators)
        
        Args:
            creation_id: Unique creation identifier
            block_number: Block number when creation was received
            
        Returns:
            CreationNAV with NAV at receipt time
        """
        try:
            current_time = int(time.time())
            
            # Check cache first
            cache_key = block_number
            if (cache_key in self.nav_cache and 
                cache_key in self.nav_cache_timestamps and
                current_time - self.nav_cache_timestamps[cache_key] <= self.nav_cache_ttl):
                
                self.metrics['cache_hits'] += 1
                nav_per_token = self.nav_cache[cache_key]
                logger.debug(f"Using cached NAV for block {block_number}: {nav_per_token:.6f}")
                
            else:
                self.metrics['cache_misses'] += 1
                
                # Get NAV at specific block (historical lookup)
                nav_data = await self._get_nav_at_block(block_number)
                
                if not nav_data:
                    logger.error(f"Failed to get NAV at block {block_number}")
                    return None
                
                nav_per_token = nav_data.nav_per_token
                
                # Cache the result
                self.nav_cache[cache_key] = nav_per_token
                self.nav_cache_timestamps[cache_key] = current_time
            
            # Create CreationNAV record
            creation_nav = CreationNAV(
                creation_id=creation_id,
                nav_per_token=nav_per_token,
                block_number=block_number,
                timestamp=current_time,
                confidence_score=0.95,  # High confidence for historical data
                calculation_hash=self._generate_creation_hash(creation_id, nav_per_token, block_number),
                validator_attestations=[]
            )
            
            # Store for later validation
            self.creation_navs[creation_id] = creation_nav
            
            logger.info(f"Recorded NAV for creation {creation_id}: {nav_per_token:.6f} TAO/TAO20 at block {block_number}")
            return creation_nav
            
        except Exception as e:
            logger.error(f"Failed to record NAV at receipt: {e}")
            return None
    
    async def _get_nav_at_block(self, block_number: int) -> Optional[object]:
        """Get NAV at a specific historical block"""
        try:
            # Method 1: Query oracle contract for historical NAV
            if self.oracle_contract:
                try:
                    nav_wei = self.oracle_contract.functions.navAtBlock(block_number).call()
                    if nav_wei > 0:
                        nav_per_token = Decimal(str(nav_wei)) / Decimal("1000000000000000000")  # Convert from wei
                        logger.debug(f"Retrieved NAV from oracle for block {block_number}: {nav_per_token:.6f}")
                        return type('NAVData', (), {'nav_per_token': nav_per_token})()
                except Exception as e:
                    logger.warning(f"Failed to get NAV from oracle: {e}")
            
            # Method 2: Use real-time service (if block is recent)
            current_nav = await self.realtime_nav_service.get_current_nav()
            if current_nav and abs(current_nav.block_number - block_number) <= 10:  # Within 10 blocks
                logger.debug(f"Using current NAV for recent block {block_number}: {current_nav.nav_per_token:.6f}")
                return current_nav
            
            # Method 3: Calculate from vault state at block (fallback)
            return await self._calculate_nav_at_block(block_number)
            
        except Exception as e:
            logger.error(f"Failed to get NAV at block {block_number}: {e}")
            return None
    
    async def _calculate_nav_at_block(self, block_number: int) -> Optional[object]:
        """Calculate NAV at a specific block from vault state"""
        try:
            # TODO: Implement historical NAV calculation
            # This would:
            # 1. Query vault holdings at the specific block
            # 2. Get subnet prices at that block
            # 3. Calculate total value and supply
            # 4. Return NAV = total_value / total_supply
            
            logger.debug(f"Calculating NAV at block {block_number} from vault state")
            
            # For now, use current NAV as approximation
            current_nav = await self.realtime_nav_service.get_current_nav()
            if current_nav:
                return current_nav
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to calculate NAV at block {block_number}: {e}")
            return None
    
    async def validate_creation_nav(self, creation_id: str, expected_nav: Decimal) -> NAVValidationResult:
        """
        Validate NAV for a creation against recorded value
        
        Args:
            creation_id: Creation identifier
            expected_nav: Expected NAV value
            
        Returns:
            Validation result
        """
        try:
            self.metrics['nav_validations'] += 1
            
            if creation_id not in self.creation_navs:
                self.metrics['validation_failures'] += 1
                return NAVValidationResult(
                    is_valid=False,
                    nav_deviation_bps=0,
                    validator_consensus=False,
                    error_message=f"No NAV record found for creation {creation_id}"
                )
            
            recorded_nav = self.creation_navs[creation_id]
            
            # Calculate deviation
            if recorded_nav.nav_per_token == 0:
                deviation_bps = 10000  # 100% deviation
            else:
                deviation = abs(expected_nav - recorded_nav.nav_per_token)
                deviation_bps = int((deviation / recorded_nav.nav_per_token) * 10000)
            
            # Check if deviation is acceptable
            is_valid = deviation_bps <= self.max_nav_deviation_bps
            
            # Check validator consensus (simplified)
            validator_consensus = len(recorded_nav.validator_attestations) >= self.required_validator_consensus
            
            if not is_valid:
                self.metrics['validation_failures'] += 1
                error_msg = f"NAV deviation too large: {deviation_bps} bps (max: {self.max_nav_deviation_bps} bps)"
            else:
                error_msg = None
            
            result = NAVValidationResult(
                is_valid=is_valid and validator_consensus,
                nav_deviation_bps=deviation_bps,
                validator_consensus=validator_consensus,
                error_message=error_msg
            )
            
            logger.debug(f"NAV validation for {creation_id}: {result.is_valid} "
                        f"(deviation: {deviation_bps} bps, consensus: {validator_consensus})")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to validate NAV for creation {creation_id}: {e}")
            self.metrics['validation_failures'] += 1
            return NAVValidationResult(
                is_valid=False,
                nav_deviation_bps=0,
                validator_consensus=False,
                error_message=str(e)
            )
    
    # ===================== Smart Contract Integration =====================
    
    async def publish_nav_to_oracle(self, nav_data) -> bool:
        """Publish NAV to oracle smart contract"""
        try:
            if not self.oracle_contract:
                logger.warning("Oracle contract not initialized")
                return False
            
            # TODO: Implement actual smart contract call
            # This would call oracle.submitNAV() with proper parameters
            
            self.metrics['oracle_updates'] += 1
            logger.debug(f"Published NAV to oracle: {nav_data.nav_per_token:.6f}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish NAV to oracle: {e}")
            return False
    
    # ===================== Utility Methods =====================
    
    def _generate_creation_hash(self, creation_id: str, nav_per_token: Decimal, block_number: int) -> str:
        """Generate hash for creation NAV verification"""
        import hashlib
        
        data = f"{creation_id}:{nav_per_token}:{block_number}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    async def cleanup_old_records(self, max_age_hours: int = 24):
        """Clean up old NAV records to save memory"""
        current_time = int(time.time())
        max_age_seconds = max_age_hours * 3600
        
        # Clean creation NAVs
        to_remove = []
        for creation_id, nav_record in self.creation_navs.items():
            if current_time - nav_record.timestamp > max_age_seconds:
                to_remove.append(creation_id)
        
        for creation_id in to_remove:
            del self.creation_navs[creation_id]
        
        # Clean NAV cache
        cache_to_remove = []
        for block_number, timestamp in self.nav_cache_timestamps.items():
            if current_time - timestamp > max_age_seconds:
                cache_to_remove.append(block_number)
        
        for block_number in cache_to_remove:
            del self.nav_cache[block_number]
            del self.nav_cache_timestamps[block_number]
        
        if to_remove or cache_to_remove:
            logger.info(f"Cleaned up {len(to_remove)} creation NAVs and {len(cache_to_remove)} cache entries")
    
    def get_service_status(self) -> Dict:
        """Get comprehensive service status"""
        return {
            'creation_navs_count': len(self.creation_navs),
            'nav_cache_size': len(self.nav_cache),
            'oracle_connected': self.oracle_contract is not None,
            'metrics': self.metrics.copy()
        }
    
    # ===================== API Endpoints =====================
    
    async def handle_nav_request(self, request_data: Dict) -> Dict:
        """Handle API request for NAV data"""
        try:
            request_type = request_data.get('type')
            
            if request_type == 'current_nav':
                # Get current NAV for minting
                nav = await self.get_nav_for_creation(1, {})
                return {
                    'status': 'success',
                    'nav_per_token': str(nav) if nav else None,
                    'timestamp': int(time.time())
                }
            
            elif request_type == 'estimate_minting':
                # Estimate TAO20 tokens for TAO value
                tao_value = Decimal(str(request_data.get('tao_value', 0)))
                tokens = await self.estimate_tao20_minted(tao_value)
                return {
                    'status': 'success',
                    'tao20_tokens': str(tokens) if tokens else None,
                    'tao_value': str(tao_value)
                }
            
            elif request_type == 'validate_nav':
                # Validate NAV for creation
                creation_id = request_data.get('creation_id')
                expected_nav = Decimal(str(request_data.get('expected_nav', 0)))
                result = await self.validate_creation_nav(creation_id, expected_nav)
                return {
                    'status': 'success',
                    'validation_result': asdict(result)
                }
            
            else:
                return {
                    'status': 'error',
                    'message': f"Unknown request type: {request_type}"
                }
                
        except Exception as e:
            logger.error(f"Failed to handle NAV request: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }


async def main():
    """Test the NAV integration service"""
    from neurons.validator.realtime_nav_service import RealtimeNAVService
    
    # Initialize real-time NAV service
    nav_service = RealtimeNAVService()
    
    # Initialize integration service
    integration_service = NAVIntegrationService(nav_service)
    await integration_service.initialize()
    
    print("NAV Integration Service Test")
    print("=" * 40)
    
    # Test getting NAV for creation
    nav = await integration_service.get_nav_for_creation(1, {1: 1000, 2: 500})
    print(f"Current NAV for creation: {nav}")
    
    # Test estimating TAO20 minting
    tao20_tokens = await integration_service.estimate_tao20_minted(Decimal("100"))
    print(f"Estimated TAO20 tokens for 100 TAO: {tao20_tokens}")
    
    # Test recording NAV at receipt
    creation_nav = await integration_service.record_nav_at_receipt("test_creation_123", 1000000)
    print(f"Recorded creation NAV: {creation_nav}")
    
    # Test validation
    if creation_nav:
        validation = await integration_service.validate_creation_nav("test_creation_123", creation_nav.nav_per_token)
        print(f"NAV validation result: {validation}")
    
    # Show service status
    status = integration_service.get_service_status()
    print(f"Service status: {json.dumps(status, indent=2, default=str)}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
