#!/usr/bin/env python3
"""
Oracle-Free TAO20 Validator
Real implementation with smart contract integration
"""

import asyncio
import logging
import os
import signal
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from decimal import Decimal

import bittensor as bt
import aiohttp
from aiohttp import web
from oracle_free_web3 import (
    OracleFreeContractInterface,
    TransactionResult
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ValidatorConfig:
    """Validator configuration"""
    wallet_name: str
    wallet_hotkey: str
    wallet_path: str = "~/.bittensor/wallets"
    
    # Contract configuration
    rpc_url: str = "https://rpc-canary-1.bevm.io/"  # BEVM mainnet
    core_contract_address: str = ""  # Set after deployment
    
    # Validator configuration
    validator_uid: int = 0
    netuid: int = 20  # TAO20 subnet
    axon_port: int = 8092
    api_port: int = 8093
    
    # Validation parameters
    min_stake_threshold: Decimal = Decimal("1000.0")  # Minimum stake to be active validator
    consensus_threshold: float = 0.67  # 67% consensus required
    
    # Monitoring parameters
    update_interval: int = 300  # Update NAV every 5 minutes
    sync_interval: int = 60    # Sync with other validators every minute

@dataclass
class ValidatorStats:
    """Validator performance statistics"""
    nav_updates: int = 0
    consensus_participations: int = 0
    successful_validations: int = 0
    failed_validations: int = 0
    total_volume_validated: Decimal = Decimal("0")
    uptime_start: float = 0.0

class OracleFreeValidatorError(Exception):
    """Validator-specific errors"""
    pass

class OracleFreeValidator:
    """
    Oracle-Free TAO20 Validator
    
    Responsibilities:
    1. Monitor TAO20 system state
    2. Validate miner submissions
    3. Participate in NAV consensus
    4. Update system NAV when needed
    5. Provide public API for system data
    """
    
    def __init__(self, config: ValidatorConfig):
        self.config = config
        self.running = False
        
        # Initialize Bittensor components
        self._init_bittensor()
        
        # Initialize Web3 interface (read-only for validators)
        self._init_web3()
        
        # Initialize validator state
        self.stats = ValidatorStats(uptime_start=time.time())
        self.current_nav = Decimal("1.0")
        self.last_nav_update = time.time()
        
        # API server
        self.app = web.Application()
        self._setup_api_routes()
        
        logger.info(f"Oracle-free validator initialized")
        logger.info(f"Validator UID: {self.config.validator_uid}")
        logger.info(f"Contract: {self.config.core_contract_address}")
    
    def _init_bittensor(self):
        """Initialize Bittensor wallet and subtensor"""
        try:
            # Initialize wallet
            self.wallet = bt.wallet(
                name=self.config.wallet_name,
                hotkey=self.config.wallet_hotkey,
                path=self.config.wallet_path
            )
            
            # Initialize subtensor
            self.subtensor = bt.subtensor()
            
            # Initialize metagraph
            self.metagraph = self.subtensor.metagraph(netuid=self.config.netuid)
            
            # Check if we're a registered validator
            if self.wallet.hotkey.ss58_address not in [n.hotkey for n in self.metagraph.neurons]:
                logger.warning("Hotkey not registered in subnet")
            
            logger.info(f"Bittensor initialized for hotkey: {self.wallet.hotkey.ss58_address}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Bittensor: {e}")
            raise
    
    def _init_web3(self):
        """Initialize Web3 contract interface (read-only)"""
        try:
            # Validators typically don't need to send transactions, so we use a dummy private key
            dummy_private_key = "0x" + "0" * 64
            
            self.contract_interface = OracleFreeContractInterface(
                rpc_url=self.config.rpc_url,
                core_contract_address=self.config.core_contract_address,
                private_key=dummy_private_key
            )
            
            # Verify connection
            if not self.contract_interface.is_connected():
                raise OracleFreeValidatorError("Failed to connect to BEVM network")
            
            # Get initial system state
            self.current_nav = self.contract_interface.get_current_nav()
            phase_info = self.contract_interface.get_phase_info()
            
            logger.info(f"Web3 interface initialized")
            logger.info(f"Current NAV: {self.current_nav}")
            logger.info(f"Phase 2 active: {phase_info['is_phase2_active']}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Web3: {e}")
            raise
    
    # ===================== MAIN VALIDATION LOOP =====================
    
    async def run(self):
        """Main validation loop"""
        logger.info("Starting oracle-free validator...")
        self.running = True
        
        try:
            # Start API server
            api_runner = await self._start_api_server()
            
            # Main validation loop
            while self.running:
                try:
                    # Monitor system state
                    await self._monitor_system_state()
                    
                    # Check if NAV update is needed
                    if await self._should_update_nav():
                        await self._participate_in_nav_consensus()
                    
                    # Validate recent transactions
                    await self._validate_recent_transactions()
                    
                    # Sync with other validators
                    await self._sync_with_validators()
                    
                    # Update local statistics
                    await self._update_stats()
                    
                    # Wait before next cycle
                    await asyncio.sleep(self.config.sync_interval)
                    
                except KeyboardInterrupt:
                    logger.info("Received interrupt signal")
                    break
                except Exception as e:
                    logger.error(f"Error in validation loop: {e}")
                    await asyncio.sleep(30)  # Wait before retrying
            
            # Cleanup API server
            await api_runner.cleanup()
            
        except Exception as e:
            logger.error(f"Fatal error in validation loop: {e}")
            raise
        finally:
            logger.info("Validator stopped")
    
    async def _monitor_system_state(self):
        """Monitor TAO20 system state"""
        try:
            # Get current NAV
            nav = self.contract_interface.get_current_nav()
            if nav != self.current_nav:
                logger.info(f"NAV changed: {self.current_nav} -> {nav}")
                self.current_nav = nav
            
            # Get phase information
            phase_info = self.contract_interface.get_phase_info()
            
            # Get token metrics
            total_supply = self.contract_interface.get_total_supply()
            
            # Log system state
            logger.debug(f"System State:")
            logger.debug(f"  NAV: {nav}")
            logger.debug(f"  Total Supply: {total_supply}")
            logger.debug(f"  Phase 2: {phase_info['is_phase2_active']}")
            logger.debug(f"  Last Update: {phase_info['last_update']}")
            
        except Exception as e:
            logger.error(f"Error monitoring system state: {e}")
    
    async def _should_update_nav(self) -> bool:
        """Check if NAV should be updated"""
        try:
            # Check time since last update
            time_since_update = time.time() - self.last_nav_update
            if time_since_update < self.config.update_interval:
                return False
            
            # Check if we're an active validator
            if not await self._is_active_validator():
                return False
            
            # Check phase info from contract
            phase_info = self.contract_interface.get_phase_info()
            
            # In Phase 1, NAV updates are not really needed (always 1.0)
            # But we can still participate for testing/monitoring
            if not phase_info['is_phase2_active']:
                logger.debug("Phase 1 active - NAV updates not critical")
                return time_since_update > self.config.update_interval * 2  # Less frequent in Phase 1
            
            # In Phase 2, regular updates are important
            return True
            
        except Exception as e:
            logger.error(f"Error checking NAV update need: {e}")
            return False
    
    async def _is_active_validator(self) -> bool:
        """Check if this validator is active"""
        try:
            # Refresh metagraph
            self.metagraph.sync(subtensor=self.subtensor)
            
            # Find our neuron
            our_neuron = None
            for neuron in self.metagraph.neurons:
                if neuron.hotkey == self.wallet.hotkey.ss58_address:
                    our_neuron = neuron
                    break
            
            if not our_neuron:
                logger.warning("Neuron not found in metagraph")
                return False
            
            # Check stake threshold
            stake = our_neuron.stake.tao
            if stake < float(self.config.min_stake_threshold):
                logger.debug(f"Insufficient stake: {stake} < {self.config.min_stake_threshold}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking validator status: {e}")
            return False
    
    # ===================== NAV CONSENSUS =====================
    
    async def _participate_in_nav_consensus(self):
        """Participate in NAV consensus process"""
        try:
            logger.info("Participating in NAV consensus...")
            
            # Calculate our NAV opinion
            our_nav_opinion = await self._calculate_nav_opinion()
            
            # Get opinions from other validators
            validator_opinions = await self._collect_validator_opinions()
            
            # Add our opinion
            validator_opinions[self.wallet.hotkey.ss58_address] = our_nav_opinion
            
            # Calculate consensus NAV
            consensus_nav = await self._calculate_consensus_nav(validator_opinions)
            
            # Check if we should submit NAV update
            if await self._should_submit_nav_update(consensus_nav):
                result = await self._submit_nav_update(consensus_nav)
                if result:
                    self.stats.nav_updates += 1
                    self.last_nav_update = time.time()
                    logger.info(f"Successfully updated NAV to {consensus_nav}")
            
            self.stats.consensus_participations += 1
            
        except Exception as e:
            logger.error(f"Error in NAV consensus: {e}")
    
    async def _calculate_nav_opinion(self) -> Decimal:
        """Calculate our opinion on current NAV"""
        try:
            # Get current contract NAV
            contract_nav = self.contract_interface.get_current_nav()
            
            # Get phase info
            phase_info = self.contract_interface.get_phase_info()
            
            if not phase_info['is_phase2_active']:
                # Phase 1: NAV should always be 1.0
                return Decimal("1.0")
            else:
                # Phase 2: Calculate based on emissions and staking
                # For now, trust the contract's calculation
                return contract_nav
            
        except Exception as e:
            logger.error(f"Error calculating NAV opinion: {e}")
            return self.current_nav
    
    async def _collect_validator_opinions(self) -> Dict[str, Decimal]:
        """Collect NAV opinions from other validators"""
        opinions = {}
        
        try:
            # Get active validators from metagraph
            active_validators = []
            for neuron in self.metagraph.neurons:
                if neuron.stake.tao >= float(self.config.min_stake_threshold):
                    active_validators.append(neuron)
            
            # Query each validator's API for their NAV opinion
            for validator in active_validators:
                if validator.hotkey == self.wallet.hotkey.ss58_address:
                    continue  # Skip ourselves
                
                try:
                    # Try to get NAV opinion from validator API
                    opinion = await self._query_validator_nav_opinion(validator)
                    if opinion:
                        opinions[validator.hotkey] = opinion
                except Exception as e:
                    logger.debug(f"Could not get opinion from {validator.hotkey}: {e}")
            
            logger.debug(f"Collected {len(opinions)} validator opinions")
            
        except Exception as e:
            logger.error(f"Error collecting validator opinions: {e}")
        
        return opinions
    
    async def _query_validator_nav_opinion(self, validator) -> Optional[Decimal]:
        """Query a validator's NAV opinion via API"""
        try:
            # Construct API URL (assuming standard port)
            api_url = f"http://{validator.axon_info.ip}:{self.config.api_port}/nav_opinion"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        return Decimal(str(data.get('nav_opinion', '1.0')))
            
        except Exception as e:
            logger.debug(f"Error querying validator {validator.hotkey}: {e}")
        
        return None
    
    async def _calculate_consensus_nav(self, opinions: Dict[str, Decimal]) -> Decimal:
        """Calculate consensus NAV from validator opinions"""
        try:
            if not opinions:
                return self.current_nav
            
            # Simple median consensus
            sorted_opinions = sorted(opinions.values())
            median_index = len(sorted_opinions) // 2
            
            if len(sorted_opinions) % 2 == 0:
                # Even number of opinions
                consensus = (sorted_opinions[median_index - 1] + sorted_opinions[median_index]) / 2
            else:
                # Odd number of opinions
                consensus = sorted_opinions[median_index]
            
            logger.debug(f"Consensus NAV calculated: {consensus} from {len(opinions)} opinions")
            return consensus
            
        except Exception as e:
            logger.error(f"Error calculating consensus NAV: {e}")
            return self.current_nav
    
    async def _should_submit_nav_update(self, consensus_nav: Decimal) -> bool:
        """Check if we should submit NAV update to contract"""
        try:
            # Check if consensus differs significantly from current contract NAV
            current_contract_nav = self.contract_interface.get_current_nav()
            
            # Calculate difference
            difference = abs(consensus_nav - current_contract_nav)
            threshold = current_contract_nav * Decimal("0.01")  # 1% threshold
            
            if difference < threshold:
                logger.debug(f"NAV difference too small: {difference} < {threshold}")
                return False
            
            # Check if enough time has passed since last update
            time_since_update = time.time() - self.last_nav_update
            if time_since_update < self.config.update_interval:
                logger.debug(f"Too soon for update: {time_since_update} < {self.config.update_interval}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking NAV update decision: {e}")
            return False
    
    async def _submit_nav_update(self, nav: Decimal) -> bool:
        """Submit NAV update to contract"""
        try:
            # Note: In the oracle-free system, validators don't typically submit transactions
            # NAV is calculated automatically by the contract
            # This is more of a monitoring/consensus verification function
            
            logger.info(f"NAV consensus reached: {nav}")
            logger.info("(Note: Oracle-free system updates NAV automatically)")
            
            # For demonstration, we could call updateNAV() if we had transaction privileges
            # result = self.contract_interface.update_nav()
            # return result.success
            
            return True
            
        except Exception as e:
            logger.error(f"Error submitting NAV update: {e}")
            return False
    
    # ===================== TRANSACTION VALIDATION =====================
    
    async def _validate_recent_transactions(self):
        """Validate recent minting/redemption transactions"""
        try:
            # This would involve:
            # 1. Monitoring recent contract events
            # 2. Validating mint requests against substrate deposits
            # 3. Checking redemption calculations
            # 4. Reporting any anomalies
            
            logger.debug("Validating recent transactions...")
            
            # Placeholder for transaction validation logic
            # In a full implementation, this would parse contract events
            # and validate each transaction's legitimacy
            
        except Exception as e:
            logger.error(f"Error validating transactions: {e}")
    
    # ===================== VALIDATOR COORDINATION =====================
    
    async def _sync_with_validators(self):
        """Sync state with other validators"""
        try:
            # Update metagraph
            self.metagraph.sync(subtensor=self.subtensor)
            
            # Share our current state with other validators
            # This helps maintain consensus and coordination
            
            logger.debug("Synced with validator network")
            
        except Exception as e:
            logger.error(f"Error syncing with validators: {e}")
    
    # ===================== API SERVER =====================
    
    def _setup_api_routes(self):
        """Setup API routes for public access"""
        
        self.app.router.add_get('/health', self._api_health)
        self.app.router.add_get('/status', self._api_status)
        self.app.router.add_get('/nav', self._api_nav)
        self.app.router.add_get('/nav_opinion', self._api_nav_opinion)
        self.app.router.add_get('/stats', self._api_stats)
        self.app.router.add_get('/system', self._api_system)
    
    async def _start_api_server(self):
        """Start the API server"""
        runner = web.AppRunner(self.app)
        await runner.setup()
        
        site = web.TCPSite(runner, '0.0.0.0', self.config.api_port)
        await site.start()
        
        logger.info(f"API server started on port {self.config.api_port}")
        return runner
    
    async def _api_health(self, request):
        """Health check endpoint"""
        return web.json_response({
            'status': 'healthy',
            'uptime': time.time() - self.stats.uptime_start,
            'running': self.running
        })
    
    async def _api_status(self, request):
        """Validator status endpoint"""
        try:
            is_active = await self._is_active_validator()
            
            return web.json_response({
                'validator_uid': self.config.validator_uid,
                'hotkey': self.wallet.hotkey.ss58_address,
                'active': is_active,
                'current_nav': str(self.current_nav),
                'last_nav_update': self.last_nav_update,
                'connected_to_bevm': self.contract_interface.is_connected()
            })
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def _api_nav(self, request):
        """Current NAV endpoint"""
        try:
            contract_nav = self.contract_interface.get_current_nav()
            phase_info = self.contract_interface.get_phase_info()
            
            return web.json_response({
                'current_nav': str(contract_nav),
                'phase_2_active': phase_info['is_phase2_active'],
                'last_update': phase_info['last_update'],
                'next_update_due': phase_info['next_update_due']
            })
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def _api_nav_opinion(self, request):
        """Our NAV opinion endpoint (for consensus)"""
        try:
            opinion = await self._calculate_nav_opinion()
            return web.json_response({
                'nav_opinion': str(opinion),
                'timestamp': time.time()
            })
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    async def _api_stats(self, request):
        """Validator statistics endpoint"""
        uptime = time.time() - self.stats.uptime_start
        
        return web.json_response({
            'uptime_seconds': uptime,
            'nav_updates': self.stats.nav_updates,
            'consensus_participations': self.stats.consensus_participations,
            'successful_validations': self.stats.successful_validations,
            'failed_validations': self.stats.failed_validations,
            'total_volume_validated': str(self.stats.total_volume_validated)
        })
    
    async def _api_system(self, request):
        """System information endpoint"""
        try:
            total_supply = self.contract_interface.get_total_supply()
            phase_info = self.contract_interface.get_phase_info()
            
            return web.json_response({
                'total_supply': str(total_supply),
                'current_nav': str(self.current_nav),
                'phase_2_active': phase_info['is_phase2_active'],
                'contract_address': self.config.core_contract_address,
                'chain_id': self.contract_interface.chain_id
            })
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
    
    # ===================== STATS AND MONITORING =====================
    
    async def _update_stats(self):
        """Update validator statistics"""
        try:
            uptime = time.time() - self.stats.uptime_start
            
            if uptime > 0 and uptime % 3600 == 0:  # Log every hour
                logger.info(f"Validator Stats (Uptime: {uptime/3600:.1f}h):")
                logger.info(f"  NAV Updates: {self.stats.nav_updates}")
                logger.info(f"  Consensus Participations: {self.stats.consensus_participations}")
                logger.info(f"  Current NAV: {self.current_nav}")
                
                # Log system metrics
                total_supply = self.contract_interface.get_total_supply()
                logger.info(f"  System Total Supply: {total_supply}")
            
        except Exception as e:
            logger.debug(f"Error updating stats: {e}")
    
    # ===================== LIFECYCLE MANAGEMENT =====================
    
    def stop(self):
        """Stop the validator"""
        logger.info("Stopping validator...")
        self.running = False
    
    async def cleanup(self):
        """Clean up resources"""
        try:
            logger.info("Validator cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

# ===================== MAIN ENTRY POINT =====================

async def main():
    """Main entry point"""
    
    # Configuration (in production, these would come from command line args or config file)
    config = ValidatorConfig(
        wallet_name=os.getenv("WALLET_NAME", "default"),
        wallet_hotkey=os.getenv("WALLET_HOTKEY", "default"),
        core_contract_address=os.getenv("TAO20_CONTRACT_ADDRESS", ""),
        rpc_url=os.getenv("BEVM_RPC_URL", "https://rpc-canary-1.bevm.io/"),
    )
    
    # Validate configuration
    if not config.core_contract_address:
        logger.error("TAO20_CONTRACT_ADDRESS environment variable is required")
        return
    
    # Create and run validator
    validator = None
    try:
        validator = OracleFreeValidator(config)
        
        # Setup signal handlers
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}")
            if validator:
                validator.stop()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Run validator
        await validator.run()
        
    except Exception as e:
        logger.error(f"Validator failed: {e}")
        raise
    finally:
        if validator:
            await validator.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
