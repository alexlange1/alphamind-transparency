#!/usr/bin/env python3
"""
Production TAO20 Miner - Zero Mock Code
Only essential functionality, real implementations only
"""

import asyncio
import logging
import os
import time
from typing import Dict, List, Optional
from dataclasses import dataclass

import bittensor as bt
import aiohttp

logger = logging.getLogger(__name__)

@dataclass
class DeliverySpec:
    """What needs to be delivered"""
    netuid_amounts: Dict[int, int]  # netuid -> amount (base units)
    vault_address: str
    deadline: int

@dataclass
class DeliveryResult:
    """Result of delivery attempt"""
    success: bool
    tx_hashes: List[str]
    error_message: Optional[str] = None

class ProductionMiner:
    """
    Production TAO20 Miner
    
    ONLY does:
    1. Get delivery requirements from validator
    2. Validate own holdings against requirements  
    3. Transfer tokens to vault
    4. Return success/failure
    
    Does NOT:
    - Implement acquisition strategies (miners decide this themselves)
    - Mock any functionality
    - Have complex dependency chains
    """
    
    def __init__(
        self,
        wallet_path: str,
        miner_id: str,
        validator_url: str,
        bittensor_network: str = "finney"
    ):
        self.miner_id = miner_id
        self.validator_url = validator_url
        
        # Initialize Bittensor - fail fast if not working
        self.wallet = bt.wallet(path=wallet_path)
        self.subtensor = bt.subtensor(network=bittensor_network)
        self.hotkey_ss58 = self.wallet.hotkey.ss58_address
        
        # Simple metrics
        self.deliveries_attempted = 0
        self.deliveries_successful = 0
        
        logger.info(f"Production miner initialized: {miner_id}")
        logger.info(f"Hotkey: {self.hotkey_ss58}")
    
    async def get_delivery_requirements(self) -> Optional[DeliverySpec]:
        """Get current delivery requirements from validator"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.validator_url}/delivery_requirements") as response:
                    if response.status != 200:
                        logger.error(f"Failed to get requirements: HTTP {response.status}")
                        return None
                    
                    data = await response.json()
                    return DeliverySpec(
                        netuid_amounts=data['netuid_amounts'],
                        vault_address=data['vault_address'],
                        deadline=data['deadline']
                    )
        except Exception as e:
            logger.error(f"Error getting delivery requirements: {e}")
            return None
    
    def check_token_balance(self, netuid: int) -> int:
        """Check actual token balance for netuid"""
        try:
            # Real Bittensor balance check
            stake = self.subtensor.get_stake_for_coldkey_and_hotkey(
                coldkey_ss58=self.wallet.coldkey.ss58_address,
                hotkey_ss58=self.hotkey_ss58
            )
            
            # For subnet tokens, we need to check subnet-specific stakes
            subnet_stake = self.subtensor.get_stake_for_coldkey_and_hotkey_and_netuid(
                coldkey_ss58=self.wallet.coldkey.ss58_address,
                hotkey_ss58=self.hotkey_ss58,
                netuid=netuid
            )
            
            return int(subnet_stake.tao * 1e9)  # Convert to RAO (base units)
            
        except Exception as e:
            logger.error(f"Error checking balance for netuid {netuid}: {e}")
            return 0
    
    def can_fulfill_delivery(self, spec: DeliverySpec) -> bool:
        """Check if we can fulfill the delivery requirements"""
        for netuid, required_amount in spec.netuid_amounts.items():
            available = self.check_token_balance(netuid)
            if available < required_amount:
                logger.warning(f"Insufficient balance for netuid {netuid}: need {required_amount}, have {available}")
                return False
        return True
    
    async def transfer_to_vault(self, netuid: int, amount: int, vault_address: str) -> Optional[str]:
        """Transfer tokens to vault - real implementation"""
        try:
            # Build transfer call
            call = self.subtensor.substrate.compose_call(
                call_module='Balances',
                call_function='transfer',
                call_params={
                    'dest': vault_address,
                    'value': amount
                }
            )
            
            # Sign and submit
            extrinsic = self.subtensor.substrate.create_signed_extrinsic(
                call=call,
                keypair=self.wallet.hotkey
            )
            
            receipt = self.subtensor.substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
            
            if receipt.is_success:
                return receipt.extrinsic_hash
            else:
                logger.error(f"Transfer failed: {receipt.error_message}")
                return None
                
        except Exception as e:
            logger.error(f"Error transferring {amount} to {vault_address}: {e}")
            return None
    
    async def execute_delivery(self, spec: DeliverySpec) -> DeliveryResult:
        """Execute the delivery to vault"""
        self.deliveries_attempted += 1
        
        # Check if we can fulfill
        if not self.can_fulfill_delivery(spec):
            return DeliveryResult(
                success=False,
                tx_hashes=[],
                error_message="Insufficient token balances"
            )
        
        # Check deadline
        if time.time() > spec.deadline:
            return DeliveryResult(
                success=False,
                tx_hashes=[],
                error_message="Delivery deadline passed"
            )
        
        # Execute transfers
        tx_hashes = []
        for netuid, amount in spec.netuid_amounts.items():
            tx_hash = await self.transfer_to_vault(netuid, amount, spec.vault_address)
            if tx_hash:
                tx_hashes.append(tx_hash)
            else:
                return DeliveryResult(
                    success=False,
                    tx_hashes=tx_hashes,
                    error_message=f"Transfer failed for netuid {netuid}"
                )
        
        self.deliveries_successful += 1
        logger.info(f"Delivery successful: {len(tx_hashes)} transfers completed")
        
        return DeliveryResult(
            success=True,
            tx_hashes=tx_hashes
        )
    
    async def run_delivery_loop(self, check_interval: int = 300):
        """Main loop - check for delivery opportunities"""
        logger.info(f"Starting delivery loop (interval: {check_interval}s)")
        
        while True:
            try:
                # Get current requirements
                spec = await self.get_delivery_requirements()
                if not spec:
                    logger.debug("No delivery requirements available")
                    await asyncio.sleep(check_interval)
                    continue
                
                # Check if we want to participate
                if self.can_fulfill_delivery(spec):
                    logger.info("Delivery opportunity found - executing")
                    result = await self.execute_delivery(spec)
                    
                    if result.success:
                        logger.info("Delivery completed successfully")
                    else:
                        logger.error(f"Delivery failed: {result.error_message}")
                else:
                    logger.debug("Cannot fulfill current delivery requirements")
                
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                logger.error(f"Error in delivery loop: {e}")
                await asyncio.sleep(60)  # Wait before retrying
    
    def get_stats(self) -> Dict:
        """Get miner statistics"""
        return {
            'miner_id': self.miner_id,
            'hotkey_ss58': self.hotkey_ss58,
            'deliveries_attempted': self.deliveries_attempted,
            'deliveries_successful': self.deliveries_successful,
            'success_rate': self.deliveries_successful / max(self.deliveries_attempted, 1)
        }

# Example usage
async def main():
    miner = ProductionMiner(
        wallet_path=os.environ.get("WALLET_PATH", "~/.bittensor/wallets/default"),
        miner_id=os.environ.get("MINER_ID", "prod_miner_1"),
        validator_url=os.environ.get("VALIDATOR_URL", "http://localhost:8000")
    )
    
    await miner.run_delivery_loop()

if __name__ == "__main__":
    asyncio.run(main())
