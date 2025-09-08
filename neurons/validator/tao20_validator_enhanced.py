#!/usr/bin/env python3
"""
Enhanced TAO20 Validator Implementation - NAV Attestor

This validator implements the complete TAO20 validation and consensus mechanism
as specified in the implementation plan. It monitors miner activity, validates NAV
calculations, implements stake-based consensus, and distributes rewards through
a multi-tiered mechanism.

Key Features:
- Real-time on-chain event monitoring
- Volume-based miner ranking and scoring
- Multi-tiered reward allocation with top miner bonuses
- Stake-based validator consensus with slashing
- NAV attestation and validation
- Transparent, un-gameable scoring system
"""

import asyncio
import logging
import time
import hashlib
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from decimal import Decimal
import json
import os
import sys

import bittensor as bt
from web3 import Web3
from web3.logs import STRICT, IGNORE, DISCARD, WARN
import torch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class MinerVolumeStats:
    """Comprehensive miner volume statistics"""
    miner_address: str
    hotkey_ss58: str
    
    # Volume tracking
    total_volume: int = 0
    mint_volume: int = 0  # 1.10x weight
    redeem_volume: int = 0  # 1.00x weight
    epoch_volume: int = 0
    
    # Activity tracking
    total_transactions: int = 0
    mint_transactions: int = 0
    redeem_transactions: int = 0
    last_activity_timestamp: int = 0
    
    # Performance metrics
    weighted_score: float = 0.0
    rank: int = 0
    reward_weight: float = 0.0
    
    # Historical data
    volume_history: List[int] = field(default_factory=list)
    activity_timestamps: List[int] = field(default_factory=list)


@dataclass
class NAVAttestation:
    """NAV attestation record"""
    transaction_hash: str
    block_number: int
    miner_address: str
    operation_type: str  # 'mint' or 'redeem'
    amount: int
    nav_at_time: Decimal
    timestamp: int
    validator_signature: str
    is_valid: bool


@dataclass
class EpochData:
    """Epoch performance data"""
    epoch_number: int
    start_timestamp: int
    end_timestamp: int
    total_volume: int
    miner_volumes: Dict[str, int]
    miner_rankings: List[Tuple[str, float]]
    consensus_weights: torch.Tensor


@dataclass
class ValidatorStake:
    """Validator stake information"""
    validator_hotkey: str
    stake_amount: int
    last_weight_submission: int
    deviation_count: int = 0
    slash_history: List[Dict] = field(default_factory=list)
    is_active: bool = True


class TAO20ConsensusValidator:
    """
    Enhanced TAO20 Validator - NAV Attestor and Consensus Engine
    
    Implements the complete validation, consensus, and reward distribution
    system for the TAO20 network with stake-based honesty enforcement.
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
        
        # Validator identification
        self.validator_hotkey = wallet.hotkey.ss58_address
        self.validator_uid = self._get_validator_uid()
        
        # Contract and network configuration
        self.contract_address = config.validator.contract_address
        self.web3_provider = config.validator.web3_provider
        self.nav_oracle_address = config.validator.get('nav_oracle_address')
        
        # Web3 setup
        self.w3 = Web3(Web3.HTTPProvider(self.web3_provider))
        self.tao20_contract = self._load_tao20_contract()
        self.nav_oracle_contract = self._load_nav_oracle_contract()
        
        # Validation parameters
        self.stake_requirement = int(config.validator.get('stake_requirement', 1000 * 1e9))  # 1000 TAO in RAO
        self.deviation_threshold = Decimal(config.validator.get('deviation_threshold', '0.05'))  # 5%
        self.slash_percentage = Decimal(config.validator.get('slash_percentage', '0.1'))  # 10%
        
        # Reward system parameters
        self.top_miner_count = config.validator.get('top_miner_count', 10)
        self.base_reward_pool = Decimal(config.validator.get('base_reward_pool', '0.8'))  # 80% base
        self.bonus_reward_pool = Decimal(config.validator.get('bonus_reward_pool', '0.2'))  # 20% bonus
        
        # Validator state
        self.miner_stats: Dict[str, MinerVolumeStats] = {}
        self.nav_attestations: List[NAVAttestation] = []
        self.epoch_history: List[EpochData] = []
        self.validator_stakes: Dict[str, ValidatorStake] = {}
        
        # Current state
        self.current_epoch = 0
        self.last_block_processed = 0
        self.last_weight_update = 0
        self.current_nav = Decimal('1.0')
        
        # Event monitoring
        self.event_filters = {}
        self.processing_queue = asyncio.Queue()
        
        # Consensus tracking
        self.validator_weight_submissions: Dict[str, torch.Tensor] = {}
        self.consensus_weights = None
        
        logger.info(f"TAO20 Consensus Validator initialized")
        logger.info(f"Validator UID: {self.validator_uid}")
        logger.info(f"Validator hotkey: {self.validator_hotkey}")
        logger.info(f"Contract: {self.contract_address}")
        logger.info(f"Stake requirement: {self.stake_requirement/1e9:.0f} TAO")
    
    def _get_validator_uid(self) -> Optional[int]:
        """Get validator UID from metagraph"""
        try:
            for uid, hotkey in enumerate(self.metagraph.hotkeys):
                if hotkey == self.validator_hotkey:
                    return uid
            return None
        except Exception as e:
            logger.error(f"Error getting validator UID: {e}")
            return None
    
    def _load_tao20_contract(self):
        """Load TAO20 contract interface"""
        try:
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
            logger.error(f"Failed to load TAO20 contract: {e}")
            raise
    
    def _load_nav_oracle_contract(self):
        """Load NAV Oracle contract interface"""
        try:
            if not self.nav_oracle_address:
                return None
                
            abi_path = os.path.join(
                os.path.dirname(__file__), '..', '..', 'contracts', 'abi',
                'OracleFreeNAVCalculator.json'
            )
            
            with open(abi_path, 'r') as f:
                contract_abi = json.load(f)
            
            return self.w3.eth.contract(
                address=self.nav_oracle_address,
                abi=contract_abi
            )
        except Exception as e:
            logger.error(f"Failed to load NAV Oracle contract: {e}")
            return None
    
    async def run(self):
        """Main validator consensus loop"""
        logger.info("Starting TAO20 Consensus Validator...")
        
        # Initialize validator state
        await self._initialize_validator_state()
        
        # Verify stake requirement
        if not await self._verify_stake_requirement():
            logger.error("Insufficient stake to operate as validator")
            return
        
        # Start background tasks
        asyncio.create_task(self._event_monitoring_loop())
        asyncio.create_task(self._nav_attestation_loop())
        asyncio.create_task(self._consensus_loop())
        asyncio.create_task(self._epoch_management_loop())
        asyncio.create_task(self._performance_reporting_loop())
        
        # Main consensus loop
        while True:
            try:
                # Process queued events
                await self._process_event_queue()
                
                # Update miner rankings
                self._update_miner_rankings()
                
                # Check for consensus updates
                if self._should_update_weights():
                    await self._update_bittensor_weights()
                
                # Check for epoch transitions
                await self._check_epoch_transition()
                
                # Monitor validator consensus
                await self._monitor_validator_consensus()
                
                await asyncio.sleep(10)  # Main loop interval
                
            except Exception as e:
                logger.error(f"Error in consensus loop: {e}")
                await asyncio.sleep(30)
    
    async def _initialize_validator_state(self):
        """Initialize validator state from blockchain"""
        try:
            # Get current block
            self.last_block_processed = self.w3.eth.block_number
            
            # Get current epoch
            try:
                epoch_info = self.tao20_contract.functions.getEpochInfo().call()
                self.current_epoch = epoch_info[0]
            except:
                self.current_epoch = 0
            
            # Initialize miner stats from contract
            await self._load_miner_stats_from_contract()
            
            # Initialize validator stakes
            await self._load_validator_stakes()
            
            # Setup event filters
            await self._setup_event_filters()
            
            logger.info(f"Initialized validator state: epoch={self.current_epoch}, "
                       f"miners={len(self.miner_stats)}, block={self.last_block_processed}")
            
        except Exception as e:
            logger.error(f"Failed to initialize validator state: {e}")
            raise
    
    async def _verify_stake_requirement(self) -> bool:
        """Verify validator meets stake requirement"""
        try:
            # Get validator stake from Bittensor
            if self.validator_uid is not None:
                stake = self.metagraph.S[self.validator_uid]
                stake_rao = int(stake * 1e9)  # Convert TAO to RAO
                
                if stake_rao >= self.stake_requirement:
                    logger.info(f"Stake requirement met: {stake_rao/1e9:.2f} TAO")
                    return True
                else:
                    logger.error(f"Insufficient stake: {stake_rao/1e9:.2f} TAO "
                               f"(required: {self.stake_requirement/1e9:.2f} TAO)")
                    return False
            else:
                logger.error("Validator UID not found in metagraph")
                return False
                
        except Exception as e:
            logger.error(f"Error verifying stake requirement: {e}")
            return False
    
    async def _load_miner_stats_from_contract(self):
        """Load existing miner stats from contract"""
        try:
            # Get active miners from contract
            try:
                active_miners = self.tao20_contract.functions.getActiveMiners().call()
            except:
                active_miners = []
            
            for miner_address in active_miners:
                try:
                    stats = self.tao20_contract.functions.getMinerStats(miner_address).call()
                    
                    # Map EVM address to hotkey (simplified mapping)
                    hotkey_ss58 = self._map_evm_to_hotkey(miner_address)
                    
                    miner_stats = MinerVolumeStats(
                        miner_address=miner_address,
                        hotkey_ss58=hotkey_ss58,
                        total_volume=stats[2] if len(stats) > 2 else 0,
                        total_transactions=stats[3] if len(stats) > 3 else 0,
                        last_activity_timestamp=stats[4] if len(stats) > 4 else 0,
                        epoch_volume=stats[5] if len(stats) > 5 else 0
                    )
                    
                    self.miner_stats[miner_address] = miner_stats
                    
                except Exception as e:
                    logger.warning(f"Error loading stats for miner {miner_address}: {e}")
            
            logger.info(f"Loaded stats for {len(self.miner_stats)} miners")
            
        except Exception as e:
            logger.error(f"Error loading miner stats: {e}")
    
    def _map_evm_to_hotkey(self, evm_address: str) -> str:
        """Map EVM address to Bittensor hotkey (simplified)"""
        # In real implementation, would maintain proper mapping
        # For now, use a deterministic but simplified approach
        return f"5{evm_address[2:48]}"  # Simplified SS58 format
    
    async def _load_validator_stakes(self):
        """Load validator stake information"""
        try:
            # Load stakes for all validators in metagraph
            for uid, hotkey in enumerate(self.metagraph.hotkeys):
                stake_amount = int(self.metagraph.S[uid] * 1e9)  # Convert to RAO
                
                self.validator_stakes[hotkey] = ValidatorStake(
                    validator_hotkey=hotkey,
                    stake_amount=stake_amount,
                    last_weight_submission=0,
                    is_active=stake_amount >= self.stake_requirement
                )
            
            active_validators = sum(1 for stake in self.validator_stakes.values() if stake.is_active)
            logger.info(f"Loaded {len(self.validator_stakes)} validator stakes "
                       f"({active_validators} active)")
            
        except Exception as e:
            logger.error(f"Error loading validator stakes: {e}")
    
    async def _setup_event_filters(self):
        """Setup Web3 event filters for monitoring"""
        try:
            # Filter for MinerActivityTracked events
            self.event_filters['miner_activity'] = self.tao20_contract.events.MinerActivityTracked.create_filter(
                fromBlock=self.last_block_processed,
                toBlock='latest'
            )
            
            # Filter for NAV update events
            if self.nav_oracle_contract:
                self.event_filters['nav_updated'] = self.nav_oracle_contract.events.NAVCalculated.create_filter(
                    fromBlock=self.last_block_processed,
                    toBlock='latest'
                )
            
            logger.info("Event filters setup completed")
            
        except Exception as e:
            logger.error(f"Error setting up event filters: {e}")
    
    async def _event_monitoring_loop(self):
        """Background event monitoring loop"""
        while True:
            try:
                # Process miner activity events
                if 'miner_activity' in self.event_filters:
                    events = self.event_filters['miner_activity'].get_new_entries()
                    for event in events:
                        await self.processing_queue.put(('miner_activity', event))
                
                # Process NAV update events
                if 'nav_updated' in self.event_filters:
                    events = self.event_filters['nav_updated'].get_new_entries()
                    for event in events:
                        await self.processing_queue.put(('nav_updated', event))
                
                # Update last processed block
                current_block = self.w3.eth.block_number
                if current_block > self.last_block_processed:
                    self.last_block_processed = current_block
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in event monitoring: {e}")
                await asyncio.sleep(30)
    
    async def _process_event_queue(self):
        """Process queued blockchain events"""
        try:
            while not self.processing_queue.empty():
                event_type, event_data = await self.processing_queue.get()
                
                if event_type == 'miner_activity':
                    await self._process_miner_activity_event(event_data)
                elif event_type == 'nav_updated':
                    await self._process_nav_update_event(event_data)
                
        except Exception as e:
            logger.error(f"Error processing event queue: {e}")
    
    async def _process_miner_activity_event(self, event):
        """Process miner activity event"""
        try:
            # Extract event data
            args = event['args']
            miner_address = args['miner']
            amount = args['amount']
            is_mint = args['isMint']
            timestamp = args['timestamp']
            cumulative_volume = args.get('cumulativeVolume', amount)
            epoch_volume = args.get('epochVolume', amount)
            
            # Get or create miner stats
            if miner_address not in self.miner_stats:
                hotkey_ss58 = self._map_evm_to_hotkey(miner_address)
                self.miner_stats[miner_address] = MinerVolumeStats(
                    miner_address=miner_address,
                    hotkey_ss58=hotkey_ss58
                )
            
            miner_stats = self.miner_stats[miner_address]
            
            # Update volume statistics
            miner_stats.total_volume = cumulative_volume
            miner_stats.epoch_volume = epoch_volume
            miner_stats.total_transactions += 1
            miner_stats.last_activity_timestamp = timestamp
            
            if is_mint:
                miner_stats.mint_volume += amount
                miner_stats.mint_transactions += 1
            else:
                miner_stats.redeem_volume += amount
                miner_stats.redeem_transactions += 1
            
            # Add to activity history
            miner_stats.activity_timestamps.append(timestamp)
            if len(miner_stats.activity_timestamps) > 100:  # Keep last 100
                miner_stats.activity_timestamps.pop(0)
            
            # Create NAV attestation
            await self._create_nav_attestation(event, miner_address, amount, is_mint)
            
            logger.debug(f"Processed activity: miner={miner_address[:10]}... "
                        f"type={'mint' if is_mint else 'redeem'} amount={amount/1e18:.2f}")
            
        except Exception as e:
            logger.error(f"Error processing miner activity event: {e}")
    
    async def _create_nav_attestation(self, event, miner_address: str, amount: int, is_mint: bool):
        """Create NAV attestation for the transaction"""
        try:
            # Get current NAV
            nav = await self._get_current_nav()
            if not nav:
                logger.warning("Cannot create NAV attestation - no NAV available")
                return
            
            # Create attestation
            attestation_data = f"{event['transactionHash'].hex()}:{miner_address}:{amount}:{nav}:{int(time.time())}"
            signature = self._sign_attestation(attestation_data)
            
            attestation = NAVAttestation(
                transaction_hash=event['transactionHash'].hex(),
                block_number=event['blockNumber'],
                miner_address=miner_address,
                operation_type='mint' if is_mint else 'redeem',
                amount=amount,
                nav_at_time=nav,
                timestamp=int(time.time()),
                validator_signature=signature,
                is_valid=True
            )
            
            self.nav_attestations.append(attestation)
            
            # Keep only recent attestations
            if len(self.nav_attestations) > 1000:
                self.nav_attestations = self.nav_attestations[-1000:]
            
            logger.debug(f"Created NAV attestation: {attestation.transaction_hash[:10]}... NAV={nav:.6f}")
            
        except Exception as e:
            logger.error(f"Error creating NAV attestation: {e}")
    
    def _sign_attestation(self, data: str) -> str:
        """Sign attestation data with validator key"""
        # In real implementation, would use proper Bittensor signing
        # For now, create a deterministic signature
        signature_input = f"{self.validator_hotkey}:{data}"
        return hashlib.sha256(signature_input.encode()).hexdigest()
    
    async def _process_nav_update_event(self, event):
        """Process NAV update event"""
        try:
            args = event['args']
            new_nav = Decimal(args['nav']) / Decimal(1e18)
            timestamp = args.get('timestamp', int(time.time()))
            
            self.current_nav = new_nav
            
            logger.debug(f"NAV updated: {new_nav:.6f} at timestamp {timestamp}")
            
        except Exception as e:
            logger.error(f"Error processing NAV update event: {e}")
    
    async def _get_current_nav(self) -> Optional[Decimal]:
        """Get current NAV from contract"""
        try:
            nav_wei = self.tao20_contract.functions.getCurrentNAV().call()
            return Decimal(nav_wei) / Decimal(1e18)
        except Exception as e:
            logger.error(f"Error getting current NAV: {e}")
            return None
    
    def _update_miner_rankings(self):
        """Update miner rankings based on volume with multi-tier scoring"""
        try:
            if not self.miner_stats:
                return
            
            # Calculate weighted scores
            for miner_address, stats in self.miner_stats.items():
                # Base score with mint bonus (1.10x for mint, 1.00x for redeem)
                weighted_score = (
                    Decimal('1.10') * Decimal(stats.mint_volume) +
                    Decimal('1.00') * Decimal(stats.redeem_volume)
                )
                
                stats.weighted_score = float(weighted_score)
            
            # Sort miners by weighted score
            sorted_miners = sorted(
                self.miner_stats.items(),
                key=lambda x: x[1].weighted_score,
                reverse=True
            )
            
            # Assign ranks
            for rank, (miner_address, stats) in enumerate(sorted_miners, 1):
                stats.rank = rank
            
            # Calculate reward weights using multi-tier system
            self._calculate_multi_tier_rewards(sorted_miners)
            
            logger.debug(f"Updated rankings for {len(self.miner_stats)} miners")
            
        except Exception as e:
            logger.error(f"Error updating miner rankings: {e}")
    
    def _calculate_multi_tier_rewards(self, sorted_miners: List[Tuple[str, MinerVolumeStats]]):
        """Calculate multi-tiered reward allocation"""
        try:
            if not sorted_miners:
                return
            
            total_weighted_score = sum(stats.weighted_score for _, stats in sorted_miners)
            if total_weighted_score == 0:
                return
            
            # Phase 1: Base proportional rewards
            for miner_address, stats in sorted_miners:
                base_weight = stats.weighted_score / total_weighted_score
                stats.reward_weight = base_weight * float(self.base_reward_pool)
            
            # Phase 2: Top miner bonuses
            top_miners = sorted_miners[:self.top_miner_count]
            if top_miners:
                # Define bonus percentages for top ranks
                bonus_percentages = [
                    0.50, 0.30, 0.20, 0.15, 0.12,  # Ranks 1-5
                    0.10, 0.08, 0.06, 0.04, 0.02   # Ranks 6-10
                ]
                
                # Calculate bonus pool distribution
                total_bonus_factor = sum(bonus_percentages[:len(top_miners)])
                
                for i, (miner_address, stats) in enumerate(top_miners):
                    if i < len(bonus_percentages):
                        bonus_factor = bonus_percentages[i] / total_bonus_factor
                        bonus_weight = bonus_factor * float(self.bonus_reward_pool)
                        stats.reward_weight += bonus_weight
            
            # Normalize final weights to sum to 1.0
            total_reward_weight = sum(stats.reward_weight for _, stats in sorted_miners)
            if total_reward_weight > 0:
                for _, stats in sorted_miners:
                    stats.reward_weight /= total_reward_weight
            
            # Log top performers
            if len(sorted_miners) >= 3:
                logger.info("Top 3 miners:")
                for i, (miner_address, stats) in enumerate(sorted_miners[:3]):
                    logger.info(f"  #{i+1}: {miner_address[:10]}... "
                              f"score={stats.weighted_score/1e18:.2f} "
                              f"weight={stats.reward_weight:.4f}")
            
        except Exception as e:
            logger.error(f"Error calculating multi-tier rewards: {e}")
    
    def _should_update_weights(self) -> bool:
        """Check if weights should be updated"""
        current_time = int(time.time())
        update_interval = self.config.validator.get('weight_update_interval', 300)  # 5 minutes
        return current_time - self.last_weight_update >= update_interval
    
    async def _update_bittensor_weights(self):
        """Update Bittensor weights based on miner rankings"""
        try:
            if not self.miner_stats:
                logger.warning("No miner stats available for weight update")
                return
            
            # Create weight tensor
            weights = torch.zeros(self.metagraph.n.item())
            
            # Map miner addresses to UIDs and set weights
            for miner_address, stats in self.miner_stats.items():
                # Find corresponding UID (simplified mapping)
                uid = self._find_miner_uid(stats.hotkey_ss58)
                if uid is not None and uid < len(weights):
                    weights[uid] = stats.reward_weight
            
            # Normalize weights
            if weights.sum() > 0:
                weights = weights / weights.sum()
            
            # Store our weight submission for consensus monitoring
            self.validator_weight_submissions[self.validator_hotkey] = weights.clone()
            
            # Submit weights to Bittensor
            success, message = await self._submit_weights_to_bittensor(weights)
            
            if success:
                self.last_weight_update = int(time.time())
                logger.info(f"Successfully updated Bittensor weights")
                
                # Log weight distribution
                non_zero_weights = (weights > 0).sum().item()
                logger.info(f"Distributed weights to {non_zero_weights} miners")
                
            else:
                logger.error(f"Failed to update weights: {message}")
                
        except Exception as e:
            logger.error(f"Error updating Bittensor weights: {e}")
    
    def _find_miner_uid(self, hotkey_ss58: str) -> Optional[int]:
        """Find miner UID from hotkey"""
        try:
            for uid, hotkey in enumerate(self.metagraph.hotkeys):
                if hotkey == hotkey_ss58:
                    return uid
            return None
        except Exception as e:
            logger.error(f"Error finding miner UID: {e}")
            return None
    
    async def _submit_weights_to_bittensor(self, weights: torch.Tensor) -> Tuple[bool, str]:
        """Submit weights to Bittensor network"""
        try:
            # Create UIDs tensor
            uids = torch.arange(len(weights))
            
            # Submit weights
            success, message = self.subtensor.set_weights(
                wallet=self.wallet,
                netuid=self.config.netuid,
                uids=uids,
                weights=weights,
                wait_for_finalization=False,
                version_key=0
            )
            
            return success, message
            
        except Exception as e:
            logger.error(f"Error submitting weights to Bittensor: {e}")
            return False, str(e)
    
    async def _monitor_validator_consensus(self):
        """Monitor validator consensus and detect deviations"""
        try:
            if len(self.validator_weight_submissions) < 2:
                return  # Need at least 2 validators for consensus
            
            # Calculate consensus weights (median approach)
            all_weights = list(self.validator_weight_submissions.values())
            consensus_weights = torch.median(torch.stack(all_weights), dim=0)[0]
            
            # Check for deviations
            for validator_hotkey, submitted_weights in self.validator_weight_submissions.items():
                deviation = self._calculate_weight_deviation(submitted_weights, consensus_weights)
                
                if deviation > self.deviation_threshold:
                    await self._handle_validator_deviation(validator_hotkey, deviation)
            
            self.consensus_weights = consensus_weights
            
        except Exception as e:
            logger.error(f"Error monitoring validator consensus: {e}")
    
    def _calculate_weight_deviation(self, weights1: torch.Tensor, weights2: torch.Tensor) -> Decimal:
        """Calculate deviation between two weight vectors"""
        try:
            # Calculate L1 distance (Manhattan distance)
            diff = torch.abs(weights1 - weights2)
            deviation = diff.sum().item()
            return Decimal(str(deviation))
        except Exception as e:
            logger.error(f"Error calculating weight deviation: {e}")
            return Decimal('0')
    
    async def _handle_validator_deviation(self, validator_hotkey: str, deviation: Decimal):
        """Handle validator deviation (potential dishonesty)"""
        try:
            if validator_hotkey not in self.validator_stakes:
                return
            
            stake_info = self.validator_stakes[validator_hotkey]
            stake_info.deviation_count += 1
            
            logger.warning(f"Validator deviation detected: {validator_hotkey[:10]}... "
                         f"deviation={deviation:.4f} count={stake_info.deviation_count}")
            
            # Apply slashing if deviation is severe or repeated
            if deviation > self.deviation_threshold * 2 or stake_info.deviation_count >= 3:
                slash_amount = int(stake_info.stake_amount * self.slash_percentage)
                await self._apply_validator_slash(validator_hotkey, slash_amount, f"Deviation: {deviation}")
            
        except Exception as e:
            logger.error(f"Error handling validator deviation: {e}")
    
    async def _apply_validator_slash(self, validator_hotkey: str, slash_amount: int, reason: str):
        """Apply slashing to validator stake"""
        try:
            if validator_hotkey not in self.validator_stakes:
                return
            
            stake_info = self.validator_stakes[validator_hotkey]
            
            # Record slash
            slash_record = {
                'timestamp': int(time.time()),
                'amount': slash_amount,
                'reason': reason,
                'remaining_stake': stake_info.stake_amount - slash_amount
            }
            
            stake_info.slash_history.append(slash_record)
            stake_info.stake_amount = max(0, stake_info.stake_amount - slash_amount)
            
            # Deactivate if stake falls below requirement
            if stake_info.stake_amount < self.stake_requirement:
                stake_info.is_active = False
            
            logger.warning(f"Applied slash to validator {validator_hotkey[:10]}...: "
                         f"{slash_amount/1e9:.2f} TAO ({reason})")
            
            # In real implementation, would execute on-chain slash
            # For now, just log and track internally
            
        except Exception as e:
            logger.error(f"Error applying validator slash: {e}")
    
    async def _nav_attestation_loop(self):
        """Background NAV attestation monitoring"""
        while True:
            try:
                # Update current NAV
                nav = await self._get_current_nav()
                if nav:
                    self.current_nav = nav
                
                await asyncio.sleep(30)  # Update every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in NAV attestation loop: {e}")
                await asyncio.sleep(60)
    
    async def _consensus_loop(self):
        """Background consensus monitoring loop"""
        while True:
            try:
                await self._monitor_validator_consensus()
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in consensus loop: {e}")
                await asyncio.sleep(120)
    
    async def _epoch_management_loop(self):
        """Background epoch management"""
        while True:
            try:
                await self._check_epoch_transition()
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                logger.error(f"Error in epoch management: {e}")
                await asyncio.sleep(600)
    
    async def _check_epoch_transition(self):
        """Check for epoch transition"""
        try:
            # Get current epoch from contract
            try:
                epoch_info = self.tao20_contract.functions.getEpochInfo().call()
                contract_epoch = epoch_info[0]
            except:
                return
            
            if contract_epoch > self.current_epoch:
                # Epoch transition detected
                await self._handle_epoch_transition(self.current_epoch, contract_epoch)
                self.current_epoch = contract_epoch
                
        except Exception as e:
            logger.error(f"Error checking epoch transition: {e}")
    
    async def _handle_epoch_transition(self, old_epoch: int, new_epoch: int):
        """Handle epoch transition"""
        try:
            logger.info(f"Epoch transition: {old_epoch} -> {new_epoch}")
            
            # Archive current epoch data
            if self.miner_stats:
                epoch_data = EpochData(
                    epoch_number=old_epoch,
                    start_timestamp=int(time.time()) - 3600,  # Approximate
                    end_timestamp=int(time.time()),
                    total_volume=sum(stats.epoch_volume for stats in self.miner_stats.values()),
                    miner_volumes={addr: stats.epoch_volume for addr, stats in self.miner_stats.items()},
                    miner_rankings=[(addr, stats.weighted_score) for addr, stats in 
                                  sorted(self.miner_stats.items(), key=lambda x: x[1].weighted_score, reverse=True)],
                    consensus_weights=self.consensus_weights.clone() if self.consensus_weights is not None else torch.tensor([])
                )
                
                self.epoch_history.append(epoch_data)
                
                # Keep only recent epochs
                if len(self.epoch_history) > 100:
                    self.epoch_history = self.epoch_history[-100:]
            
            # Reset epoch volumes
            for stats in self.miner_stats.values():
                stats.epoch_volume = 0
            
            # Reset validator weight submissions for new epoch
            self.validator_weight_submissions.clear()
            
            logger.info(f"Epoch {old_epoch} archived, reset for epoch {new_epoch}")
            
        except Exception as e:
            logger.error(f"Error handling epoch transition: {e}")
    
    async def _performance_reporting_loop(self):
        """Background performance reporting"""
        while True:
            try:
                await asyncio.sleep(600)  # Report every 10 minutes
                self._log_performance_report()
            except Exception as e:
                logger.error(f"Error in performance reporting: {e}")
                await asyncio.sleep(600)
    
    def _log_performance_report(self):
        """Log comprehensive performance report"""
        try:
            total_volume = sum(stats.total_volume for stats in self.miner_stats.values())
            epoch_volume = sum(stats.epoch_volume for stats in self.miner_stats.values())
            total_transactions = sum(stats.total_transactions for stats in self.miner_stats.values())
            active_miners = len([s for s in self.miner_stats.values() if s.last_activity_timestamp > int(time.time()) - 3600])
            
            logger.info("=== Validator Performance Report ===")
            logger.info(f"Current Epoch: {self.current_epoch}")
            logger.info(f"Active Miners: {active_miners}/{len(self.miner_stats)}")
            logger.info(f"Total Volume: {total_volume/1e18:.2f} TAO")
            logger.info(f"Epoch Volume: {epoch_volume/1e18:.2f} TAO")
            logger.info(f"Total Transactions: {total_transactions}")
            logger.info(f"Current NAV: {self.current_nav:.6f}")
            logger.info(f"NAV Attestations: {len(self.nav_attestations)}")
            logger.info(f"Validator Consensus: {len(self.validator_weight_submissions)} submissions")
            logger.info(f"Last Weight Update: {int(time.time()) - self.last_weight_update}s ago")
            
            # Top 5 miners
            if self.miner_stats:
                sorted_miners = sorted(
                    self.miner_stats.items(),
                    key=lambda x: x[1].weighted_score,
                    reverse=True
                )[:5]
                
                logger.info("Top 5 Miners:")
                for i, (addr, stats) in enumerate(sorted_miners, 1):
                    logger.info(f"  #{i}: {addr[:10]}... "
                              f"score={stats.weighted_score/1e18:.2f} "
                              f"weight={stats.reward_weight:.4f} "
                              f"vol={stats.epoch_volume/1e18:.1f}")
            
        except Exception as e:
            logger.error(f"Error logging performance report: {e}")
    
    def get_system_stats(self) -> Dict:
        """Get comprehensive system statistics"""
        try:
            total_volume = sum(stats.total_volume for stats in self.miner_stats.values())
            epoch_volume = sum(stats.epoch_volume for stats in self.miner_stats.values())
            total_transactions = sum(stats.total_transactions for stats in self.miner_stats.values())
            active_miners = len([s for s in self.miner_stats.values() 
                               if s.last_activity_timestamp > int(time.time()) - 3600])
            
            return {
                'validator_uid': self.validator_uid,
                'validator_hotkey': self.validator_hotkey,
                'current_epoch': self.current_epoch,
                'total_miners': len(self.miner_stats),
                'active_miners': active_miners,
                'total_volume_tao': float(total_volume / 1e18),
                'epoch_volume_tao': float(epoch_volume / 1e18),
                'total_transactions': total_transactions,
                'current_nav': float(self.current_nav),
                'nav_attestations': len(self.nav_attestations),
                'validator_submissions': len(self.validator_weight_submissions),
                'last_weight_update': self.last_weight_update,
                'epochs_tracked': len(self.epoch_history),
                'active_validators': sum(1 for stake in self.validator_stakes.values() if stake.is_active),
                'total_validators': len(self.validator_stakes)
            }
            
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return {}


def get_config():
    """Get validator configuration"""
    parser = bt.cli.ArgumentParser()
    
    # Validator-specific configuration
    parser.add_argument('--validator.contract_address', type=str, required=True,
                       help='TAO20 contract address')
    parser.add_argument('--validator.web3_provider', type=str, required=True,
                       help='Web3 RPC provider URL')
    parser.add_argument('--validator.nav_oracle_address', type=str,
                       help='NAV Oracle contract address')
    
    # Consensus parameters
    parser.add_argument('--validator.stake_requirement', type=int, default=int(1000 * 1e9),
                       help='Minimum stake requirement in RAO')
    parser.add_argument('--validator.deviation_threshold', type=float, default=0.05,
                       help='Maximum allowed weight deviation (5%)')
    parser.add_argument('--validator.slash_percentage', type=float, default=0.1,
                       help='Slash percentage for misbehavior (10%)')
    
    # Reward system parameters
    parser.add_argument('--validator.top_miner_count', type=int, default=10,
                       help='Number of top miners to receive bonuses')
    parser.add_argument('--validator.base_reward_pool', type=float, default=0.8,
                       help='Base reward pool percentage (80%)')
    parser.add_argument('--validator.bonus_reward_pool', type=float, default=0.2,
                       help='Bonus reward pool percentage (20%)')
    parser.add_argument('--validator.weight_update_interval', type=int, default=300,
                       help='Weight update interval in seconds')
    
    # Add Bittensor config
    bt.subtensor.add_args(parser)
    bt.wallet.add_args(parser)
    bt.logging.add_args(parser)
    
    return bt.config(parser)


async def main():
    """Main validator execution"""
    config = get_config()
    bt.logging(config=config, logging_dir=config.full_path)
    
    # Initialize Bittensor components
    wallet = bt.wallet(config=config)
    subtensor = bt.subtensor(config=config)
    metagraph = subtensor.metagraph(config.netuid)
    
    # Initialize validator
    validator = TAO20ConsensusValidator(wallet, config, subtensor, metagraph)
    
    # Run validator
    await validator.run()


if __name__ == "__main__":
    asyncio.run(main())
