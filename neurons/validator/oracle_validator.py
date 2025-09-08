#!/usr/bin/env python3
"""
TAO20 Oracle Validator Implementation

This validator monitors miner activity on the TAO20 oracle-free system and produces
consensus rankings based on transaction volume. It demonstrates the validator role
in the oracle architecture where validators track on-chain activity rather than
providing price data.

Key Features:
- Monitors TAO20 contract events for miner activity
- Ranks miners by transaction volume
- Produces Bittensor consensus weights
- Tracks epoch-based performance
- Provides transparent scoring mechanism
"""

import asyncio
import logging
import time
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict
import json
import os
import sys

import bittensor as bt
from web3 import Web3
from eth_account import Account

# Add the common module to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'common'))
from address_mapping import ValidatorAddressManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class MinerStats:
    """Miner statistics tracking"""
    address: str
    volume_staked: int
    volume_redeemed: int
    total_volume: int
    transaction_count: int
    last_activity: int
    current_epoch_volume: int
    score: float = 0.0


@dataclass
class EpochData:
    """Epoch tracking data"""
    epoch_number: int
    start_time: int
    end_time: int
    miner_volumes: Dict[str, int]
    total_volume: int


class OracleValidator:
    """
    TAO20 Oracle Validator
    
    Monitors miner activity and produces consensus rankings based on
    transaction volume in the oracle-free TAO20 system.
    """
    
    def __init__(
        self,
        wallet: bt.wallet,
        config: bt.config,
        subtensor: bt.subtensor,
        metagraph: bt.metagraph
    ):
        self.wallet = wallet
        self.config = config
        self.subtensor = subtensor
        self.metagraph = metagraph
        
        # Initialize address mapping
        self.address_manager = ValidatorAddressManager(wallet)
        self.validator_address = self.address_manager.get_validator_address()
        
        # Contract configuration
        self.contract_address = config.oracle.contract_address
        self.web3_provider = config.oracle.web3_provider
        
        # Web3 setup
        self.w3 = Web3(Web3.HTTPProvider(self.web3_provider))
        self.contract = self._load_contract()
        
        # UID to EVM address mapping
        self.uid_to_evm = self.address_manager.map_metagraph_to_evm(metagraph)
        self.evm_to_uid = {v: k for k, v in self.uid_to_evm.items()}
        
        # Validator state
        self.miner_stats: Dict[str, MinerStats] = {}
        self.epoch_history: List[EpochData] = []
        self.current_epoch: int = 0
        self.last_weight_update: int = 0
        
        # Configuration
        self.update_interval = config.oracle.get('update_interval', 60)  # 1 minute
        self.weight_update_interval = config.oracle.get('weight_update_interval', 300)  # 5 minutes
        self.volume_decay_factor = config.oracle.get('volume_decay_factor', 0.95)  # Volume decay per epoch
        
        logger.info(f"Oracle Validator initialized for contract: {self.contract_address}")
        logger.info(f"Validator EVM address: {self.validator_address}")
        logger.info(f"Mapped {len(self.uid_to_evm)} UIDs to EVM addresses")
    
    def _load_contract(self):
        """Load TAO20 contract ABI and create contract instance"""
        try:
            # Load ABI from the contracts/abi directory
            abi_path = os.path.join(
                os.path.dirname(__file__), '..', '..', 'contracts', 'abi', 
                'TAO20CoreV2OracleFree.json'
            )
            
            with open(abi_path, 'r') as f:
                contract_abi = json.load(f)
            
            return self.w3.eth.contract(
                address=self.contract_address,
                abi=contract_abi
            )
        except Exception as e:
            logger.error(f"Failed to load contract ABI: {e}")
            raise
    
    async def run(self):
        """Main validator loop"""
        logger.info("Starting Oracle Validator...")
        
        # Initialize from contract state
        await self._initialize_from_contract()
        
        # Main monitoring loop
        while True:
            try:
                # Monitor miner activity
                await self._monitor_miner_activity()
                
                # Update miner rankings
                self._update_miner_rankings()
                
                # Check for epoch changes
                await self._check_epoch_advancement()
                
                # Update Bittensor weights if needed
                if self._should_update_weights():
                    await self._update_bittensor_weights()
                
                # Wait for next update
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"Error in validator loop: {e}")
                await asyncio.sleep(10)  # Short delay on error
    
    async def _initialize_from_contract(self):
        """Initialize validator state from contract"""
        try:
            # Get current epoch info
            epoch_info = self.contract.functions.getEpochInfo().call()
            self.current_epoch = epoch_info[0]
            
            # Get active miners
            active_miners = self.contract.functions.getActiveMiners().call()
            
            # Initialize miner stats
            for miner_address in active_miners:
                stats = self.contract.functions.getMinerStats(miner_address).call()
                
                self.miner_stats[miner_address] = MinerStats(
                    address=miner_address,
                    volume_staked=stats[0],
                    volume_redeemed=stats[1],
                    total_volume=stats[2],
                    transaction_count=stats[3],
                    last_activity=stats[4],
                    current_epoch_volume=stats[5]
                )
            
            logger.info(f"Initialized with {len(self.miner_stats)} active miners")
            
        except Exception as e:
            logger.error(f"Failed to initialize from contract: {e}")
            raise
    
    async def _monitor_miner_activity(self):
        """Monitor contract events for miner activity"""
        try:
            # Get latest block
            latest_block = self.w3.eth.block_number
            
            # Query recent MinerActivityTracked events
            event_filter = self.contract.events.MinerActivityTracked.create_filter(
                fromBlock=latest_block - 10,  # Last 10 blocks
                toBlock='latest'
            )
            
            events = event_filter.get_all_entries()
            
            for event in events:
                await self._process_activity_event(event)
                
        except Exception as e:
            logger.error(f"Error monitoring miner activity: {e}")
    
    async def _process_activity_event(self, event):
        """Process a MinerActivityTracked event"""
        try:
            # Extract event data
            miner = event['args']['miner']
            amount = event['args']['amount']
            is_mint = event['args']['isMint']
            timestamp = event['args']['timestamp']
            cumulative_volume = event['args']['cumulativeVolume']
            epoch_volume = event['args']['epochVolume']
            
            # Update miner stats
            if miner not in self.miner_stats:
                # New miner - get full stats from contract
                stats = self.contract.functions.getMinerStats(miner).call()
                self.miner_stats[miner] = MinerStats(
                    address=miner,
                    volume_staked=stats[0],
                    volume_redeemed=stats[1],
                    total_volume=stats[2],
                    transaction_count=stats[3],
                    last_activity=stats[4],
                    current_epoch_volume=stats[5]
                )
            else:
                # Update existing miner
                miner_stats = self.miner_stats[miner]
                
                if is_mint:
                    miner_stats.volume_staked += amount
                else:
                    miner_stats.volume_redeemed += amount
                
                miner_stats.total_volume = cumulative_volume
                miner_stats.transaction_count += 1
                miner_stats.last_activity = timestamp
                miner_stats.current_epoch_volume = epoch_volume
            
            logger.debug(f"Updated miner {miner}: volume={cumulative_volume}, epoch_volume={epoch_volume}")
            
        except Exception as e:
            logger.error(f"Error processing activity event: {e}")
    
    def _update_miner_rankings(self):
        """Update miner rankings based on volume"""
        try:
            # Calculate scores for each miner
            total_volume = sum(stats.current_epoch_volume for stats in self.miner_stats.values())
            
            if total_volume == 0:
                # No activity - equal scores
                for stats in self.miner_stats.values():
                    stats.score = 0.0
                return
            
            # Volume-based scoring with recency weighting
            current_time = int(time.time())
            
            for miner_address, stats in self.miner_stats.items():
                # Base score from current epoch volume
                volume_score = stats.current_epoch_volume / total_volume
                
                # Recency bonus (activity within last hour gets bonus)
                recency_bonus = 1.0
                if current_time - stats.last_activity < 3600:  # 1 hour
                    recency_bonus = 1.2
                elif current_time - stats.last_activity < 7200:  # 2 hours
                    recency_bonus = 1.1
                
                # Transaction frequency bonus
                frequency_bonus = min(1.5, 1.0 + (stats.transaction_count / 100))
                
                # Final score
                stats.score = volume_score * recency_bonus * frequency_bonus
            
            # Normalize scores to sum to 1.0
            total_score = sum(stats.score for stats in self.miner_stats.values())
            if total_score > 0:
                for stats in self.miner_stats.values():
                    stats.score /= total_score
            
            logger.debug(f"Updated rankings for {len(self.miner_stats)} miners")
            
        except Exception as e:
            logger.error(f"Error updating miner rankings: {e}")
    
    async def _check_epoch_advancement(self):
        """Check if epoch has advanced on-chain"""
        try:
            epoch_info = self.contract.functions.getEpochInfo().call()
            new_epoch = epoch_info[0]
            
            if new_epoch > self.current_epoch:
                # Epoch advanced - archive current epoch data
                await self._archive_epoch_data(self.current_epoch)
                
                # Reset current epoch volumes
                for stats in self.miner_stats.values():
                    stats.current_epoch_volume = 0
                
                self.current_epoch = new_epoch
                logger.info(f"Advanced to epoch {new_epoch}")
                
        except Exception as e:
            logger.error(f"Error checking epoch advancement: {e}")
    
    async def _archive_epoch_data(self, epoch_number: int):
        """Archive epoch data for historical analysis"""
        try:
            miner_volumes = {
                miner: stats.current_epoch_volume
                for miner, stats in self.miner_stats.items()
            }
            
            total_volume = sum(miner_volumes.values())
            
            epoch_data = EpochData(
                epoch_number=epoch_number,
                start_time=int(time.time()) - 3600,  # Approximate
                end_time=int(time.time()),
                miner_volumes=miner_volumes,
                total_volume=total_volume
            )
            
            self.epoch_history.append(epoch_data)
            
            # Keep only last 24 epochs (24 hours of data)
            if len(self.epoch_history) > 24:
                self.epoch_history.pop(0)
                
            logger.info(f"Archived epoch {epoch_number} with {total_volume} total volume")
            
        except Exception as e:
            logger.error(f"Error archiving epoch data: {e}")
    
    def _should_update_weights(self) -> bool:
        """Check if weights should be updated"""
        current_time = int(time.time())
        return current_time - self.last_weight_update >= self.weight_update_interval
    
    async def _update_bittensor_weights(self):
        """Update Bittensor weights based on miner rankings"""
        try:
            import torch
            
            # Create weight vector
            weights = torch.zeros(self.metagraph.n.item())
            
            # Map miner EVM addresses to UIDs and set weights
            for miner_address, stats in self.miner_stats.items():
                if miner_address in self.evm_to_uid:
                    uid = self.evm_to_uid[miner_address]
                    if uid < len(weights):
                        weights[uid] = stats.score
            
            # Normalize weights
            if weights.sum() > 0:
                weights = weights / weights.sum()
            
            # Set weights on Bittensor
            success, message = self.subtensor.set_weights(
                wallet=self.wallet,
                netuid=self.config.netuid,
                uids=list(range(self.metagraph.n.item())),
                weights=weights,
                wait_for_finalization=False
            )
            
            if success:
                self.last_weight_update = int(time.time())
                logger.info(f"Successfully updated Bittensor weights")
                
                # Log top miners
                top_miners = sorted(
                    self.miner_stats.items(),
                    key=lambda x: x[1].score,
                    reverse=True
                )[:5]
                
                for i, (miner, stats) in enumerate(top_miners):
                    uid = self.evm_to_uid.get(miner, "Unknown")
                    logger.info(f"Top miner #{i+1}: UID={uid} {miner[:10]}... score={stats.score:.4f} volume={stats.current_epoch_volume}")
            else:
                logger.error(f"Failed to update weights: {message}")
                
        except Exception as e:
            logger.error(f"Error updating Bittensor weights: {e}")
    
    def get_miner_rankings(self) -> List[Tuple[str, float]]:
        """Get current miner rankings"""
        return sorted(
            [(miner, stats.score) for miner, stats in self.miner_stats.items()],
            key=lambda x: x[1],
            reverse=True
        )
    
    def get_system_stats(self) -> Dict:
        """Get system-wide statistics"""
        total_volume = sum(stats.total_volume for stats in self.miner_stats.values())
        total_transactions = sum(stats.transaction_count for stats in self.miner_stats.values())
        active_miners = len([s for s in self.miner_stats.values() if s.current_epoch_volume > 0])
        
        return {
            'total_volume': total_volume,
            'total_transactions': total_transactions,
            'active_miners': len(self.miner_stats),
            'active_this_epoch': active_miners,
            'current_epoch': self.current_epoch,
            'epochs_tracked': len(self.epoch_history)
        }


# Configuration for validator
def get_config():
    """Get validator configuration"""
    parser = bt.cli.ArgumentParser()
    
    # Oracle-specific configuration
    parser.add_argument('--oracle.contract_address', type=str, required=True,
                       help='TAO20 contract address')
    parser.add_argument('--oracle.web3_provider', type=str, required=True,
                       help='Web3 RPC provider URL')
    parser.add_argument('--oracle.update_interval', type=int, default=60,
                       help='Update interval in seconds')
    parser.add_argument('--oracle.weight_update_interval', type=int, default=300,
                       help='Weight update interval in seconds')
    parser.add_argument('--oracle.volume_decay_factor', type=float, default=0.95,
                       help='Volume decay factor per epoch')
    
    # Add Bittensor config
    bt.subtensor.add_args(parser)
    bt.wallet.add_args(parser)
    bt.logging.add_args(parser)
    
    return bt.config(parser)


# Main execution
async def main():
    """Main validator execution"""
    config = get_config()
    bt.logging(config=config, logging_dir=config.full_path)
    
    # Initialize Bittensor components
    wallet = bt.wallet(config=config)
    subtensor = bt.subtensor(config=config)
    metagraph = subtensor.metagraph(config.netuid)
    
    # Initialize validator
    validator = OracleValidator(wallet, config, subtensor, metagraph)
    
    # Run validator
    await validator.run()


if __name__ == "__main__":
    import torch
    asyncio.run(main())
