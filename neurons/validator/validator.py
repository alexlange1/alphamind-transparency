#!/usr/bin/env python3
"""
TAO20 Index Validator
Monitors creation registrations, validates baskets, calculates NAV, and provides attestations
for in-kind minting in the creation unit model
"""

import asyncio
import logging
import os
import time
import hashlib
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from collections import defaultdict

import bittensor as bt
import aiohttp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TransferRecord:
    """Individual transfer record within a creation"""
    netuid: int
    amount: int  # Base units (integer)
    vault_ss58: str
    tx_hash: str
    block_hash: str
    extrinsic_index: int

@dataclass
class CreationReceipt:
    """Complete creation receipt with all transfers"""
    creation_id: str
    source_ss58: str
    epoch_id: int
    weights_hash: str
    unit_count: int
    transfers: List[TransferRecord]
    deadline_ts: int
    registered_at: int

@dataclass
class BasketSpecification:
    """Basket specification for validation"""
    epoch_id: int
    creation_unit_size: int  # Base units
    assets: Dict[int, int]  # netuid -> qty (base units)
    tolerance_bps: int
    valid_from: int
    valid_until: int
    weights_hash: str

@dataclass
class AttestationResult:
    """Result of attestation process"""
    success: bool
    creation_id: str
    nav_at_receipt: int  # Base units (integer)
    attestation_signature: Optional[str] = None
    error_message: Optional[str] = None

class TAO20Validator:
    """
    TAO20 Index Validator that monitors creations and provides attestations
    for the in-kind creation unit model
    """
    
    def __init__(
        self,
        wallet_path: str,
        source_ss58: str,
        validator_id: str = "tao20_validator",
        tao20_api_url: str = "http://localhost:8000",
        bittensor_network: str = "finney",
        min_attestation_interval: int = 60,  # seconds
        max_creation_age: int = 3600,  # 1 hour
        nav_precision: int = 18  # 1e18 precision
    ):
        self.wallet_path = wallet_path
        self.source_ss58 = source_ss58
        self.validator_id = validator_id
        self.tao20_api_url = tao20_api_url
        self.min_attestation_interval = min_attestation_interval
        self.max_creation_age = max_creation_age
        self.nav_precision = nav_precision
        
        # Initialize Bittensor wallet and connection
        try:
            self.bt_wallet = bt.wallet(path=wallet_path)
            wallet_ss58 = self.bt_wallet.hotkey.ss58_address
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Bittensor wallet at {wallet_path}: {e}")
        
        # Validate source_ss58 vs wallet hotkey
        if source_ss58 and source_ss58 != wallet_ss58:
            logger.warning(f"Provided source_ss58 ({source_ss58}) differs from wallet hotkey ({wallet_ss58}); using wallet hotkey.")
        self.source_ss58 = wallet_ss58  # Always use wallet hotkey as source of truth
        
        try:
            self.subtensor = bt.subtensor(network=bittensor_network)
        except Exception as e:
            raise RuntimeError(f"Failed to connect to Bittensor network '{bittensor_network}': {e}")
        
        # Initialize creation file system
        try:
            from creation.epoch_manager import EpochManager
        except ImportError:
            from ..creation.epoch_manager import EpochManager
        self.epoch_manager = EpochManager()
        
        # Initialize basket validator
        try:
            from creation.basket_validator import BasketValidator
        except ImportError:
            from ..creation.basket_validator import BasketValidator
        self.basket_validator = BasketValidator()
        
        # Initialize NAV calculator
        try:
            from neurons.validator.nav_calculator import NAVCalculator
        except ImportError:
            from .nav_calculator import NAVCalculator
        self.nav_calculator = NAVCalculator()
        
        # Initialize incentive manager
        try:
            from neurons.validator.incentive_manager import IncentiveManager, VolumeType
        except ImportError:
            from .incentive_manager import IncentiveManager, VolumeType
        self.incentive_manager = IncentiveManager()
        self.VolumeType = VolumeType
        
        # Initialize precompile integration (if EVM address available)
        self.precompiles = None
        evm_rpc_url = os.environ.get("BEVM_RPC_URL")
        if evm_rpc_url:
            try:
                from web3 import Web3
                from common.precompiles import BittensorPrecompiles
                
                web3 = Web3(Web3.HTTPProvider(evm_rpc_url))
                self.precompiles = BittensorPrecompiles(web3, netuid=1)  # TODO: Make configurable
                logger.info("Precompile integration initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize precompiles: {e}")
        
        # Initialize metrics
        try:
            from common.metrics import get_metrics
            self.metrics_collector = get_metrics()
        except ImportError:
            self.metrics_collector = None
        
        # State tracking
        self.attested_creations: Set[str] = set()
        self.last_attestation_time = 0
        self.processing_creations: Set[str] = set()  # Prevent duplicate processing
        
        # Metrics
        self.metrics = {
            'creations_monitored': 0,
            'creations_attested': 0,
            'creations_rejected': 0,
            'validation_errors': 0,
            'nav_calculation_errors': 0,
            'attestation_errors': 0,
            'avg_processing_time_seconds': []
        }
        
        logger.info(f"TAO20 Validator initialized: {validator_id}")
        logger.info(f"Source SS58: {self.source_ss58}")
        logger.info(f"API URL: {self.tao20_api_url}")
    
    def _add_metric_with_cap(self, metric_name: str, value: float, max_items: int = 500):
        """Add metric value with capped array size"""
        if metric_name in self.metrics and isinstance(self.metrics[metric_name], list):
            self.metrics[metric_name].append(value)
            if len(self.metrics[metric_name]) > max_items:
                del self.metrics[metric_name][0:len(self.metrics[metric_name])-max_items]
    
    async def monitor_creations(self, interval: int = 30):
        """Monitor for new creation registrations"""
        logger.info("Starting creation monitoring")
        
        while True:
            try:
                # Get pending creations from API
                pending_creations = await self._get_pending_creations()
                
                for creation in pending_creations:
                    if (creation.creation_id not in self.attested_creations and 
                        creation.creation_id not in self.processing_creations):
                        
                        # Check if creation is too old
                        if time.time() - creation.registered_at > self.max_creation_age:
                            logger.warning(f"Creation {creation.creation_id} is too old, skipping")
                            continue
                        
                        # Process creation
                        self.processing_creations.add(creation.creation_id)
                        asyncio.create_task(self._process_creation(creation))
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"Error in creation monitoring: {e}")
                await asyncio.sleep(interval)
    
    async def _get_pending_creations(self) -> List[CreationReceipt]:
        """Get pending creations from API"""
        try:
            timeout = aiohttp.ClientTimeout(total=30, connect=5, sock_read=20)
            headers = {"User-Agent": f"tao20-validator/{self.validator_id}", "Content-Type": "application/json"}
            
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(f"{self.tao20_api_url}/creations/pending") as response:
                    if response.status == 200:
                        data = await response.json()
                        creations = []
                        
                        for creation_data in data.get("creations", []):
                            try:
                                transfers = []
                                for transfer_data in creation_data.get("transfers", []):
                                    transfer = TransferRecord(
                                        netuid=transfer_data["netuid"],
                                        amount=int(transfer_data["amount"]),  # Ensure integer
                                        vault_ss58=transfer_data["vault_ss58"],
                                        tx_hash=transfer_data["tx_hash"],
                                        block_hash=transfer_data["block_hash"],
                                        extrinsic_index=transfer_data["extrinsic_index"]
                                    )
                                    transfers.append(transfer)
                                
                                creation = CreationReceipt(
                                    creation_id=creation_data["creation_id"],
                                    source_ss58=creation_data["source_ss58"],
                                    epoch_id=creation_data["epoch_id"],
                                    weights_hash=creation_data["weights_hash"],
                                    unit_count=creation_data["unit_count"],
                                    transfers=transfers,
                                    deadline_ts=creation_data["deadline_ts"],
                                    registered_at=creation_data["registered_at"]
                                )
                                creations.append(creation)
                                
                            except KeyError as e:
                                logger.error(f"Missing field in creation data: {e}")
                                continue
                        
                        return creations
                    else:
                        logger.error(f"Failed to get pending creations: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Error getting pending creations: {e}")
            return []
    
    async def _process_creation(self, creation: CreationReceipt):
        """Process a creation through validation → NAV → attestation pipeline"""
        start_time = time.time()
        
        try:
            logger.info(f"Processing creation: {creation.creation_id}")
            self.metrics['creations_monitored'] += 1
            
            # Step 1: Validate basket
            if not await self._validate_basket(creation):
                logger.error(f"Basket validation failed for creation: {creation.creation_id}")
                self.metrics['validation_errors'] += 1
                self.metrics['creations_rejected'] += 1
                return
            
            # Step 2: Calculate NAV at receipt time
            nav = await self._calculate_nav_at_receipt(creation)
            if nav <= 0:
                logger.error(f"Invalid NAV for creation: {creation.creation_id}")
                self.metrics['nav_calculation_errors'] += 1
                self.metrics['creations_rejected'] += 1
                return
            
            # Step 3: Provide attestation
            attestation = await self._provide_attestation(creation, nav)
            
            if attestation.success:
                self.attested_creations.add(creation.creation_id)
                self.metrics['creations_attested'] += 1
                
                # Record volume for incentive calculation
                total_volume = sum(transfer.amount for transfer in creation.transfers)
                gas_cost = sum(transfer.amount * 0.001 for transfer in creation.transfers)  # Estimate gas cost
                
                self.incentive_manager.record_volume(
                    miner_ss58=creation.source_ss58,
                    volume_type=self.VolumeType.MINT,  # All creations are minting volume
                    volume_amount=total_volume,
                    creation_id=creation.creation_id,
                    nav_at_time=nav,
                    gas_cost=gas_cost
                )
                
                # Record validator attestation for reward calculation
                accuracy_score = 1.0  # Perfect accuracy for successful attestation
                stake_amount = 1000000000000000000000  # 1000 TAO default, should be fetched from chain
                
                self.incentive_manager.record_validator_attestation(
                    validator_ss58=self.source_ss58,
                    accuracy_score=accuracy_score,
                    stake_amount=stake_amount
                )
                
                logger.info(f"Attestation provided for creation: {creation.creation_id}, NAV: {nav}, Volume: {total_volume}")
            else:
                logger.error(f"Failed to provide attestation: {attestation.error_message}")
                self.metrics['attestation_errors'] += 1
                self.metrics['creations_rejected'] += 1
                
        except Exception as e:
            logger.error(f"Error processing creation {creation.creation_id}: {e}")
            self.metrics['validation_errors'] += 1
        finally:
            # Clean up processing state
            self.processing_creations.discard(creation.creation_id)
            
            # Record processing time
            processing_time = time.time() - start_time
            self._add_metric_with_cap('avg_processing_time_seconds', processing_time)
    
    async def _validate_basket(self, creation: CreationReceipt) -> bool:
        """Validate the complete basket delivery"""
        try:
            logger.info(f"Validating basket for creation: {creation.creation_id}")
            
            # 1. Check that we have exactly 20 transfers
            if len(creation.transfers) != 20:
                logger.error(f"Creation {creation.creation_id} has {len(creation.transfers)} transfers, expected 20")
                return False
            
            # 2. Get basket specification for the epoch
            basket_spec = await self._get_basket_specification(creation.epoch_id)
            if not basket_spec:
                logger.error(f"No basket specification found for epoch {creation.epoch_id}")
                return False
            
            # 3. Validate epoch and weights hash
            if basket_spec.epoch_id != creation.epoch_id:
                logger.error(f"Epoch mismatch: {basket_spec.epoch_id} vs {creation.epoch_id}")
                return False
            
            if basket_spec.weights_hash != creation.weights_hash:
                logger.error(f"Weights hash mismatch for creation {creation.creation_id}")
                return False
            
            # 4. Check deadline
            if time.time() > creation.deadline_ts:
                logger.error(f"Creation {creation.creation_id} has expired")
                return False
            
            # 5. Build delivered assets from transfers
            delivered_assets = {}
            for transfer in creation.transfers:
                if transfer.netuid in delivered_assets:
                    logger.error(f"Duplicate transfer for subnet {transfer.netuid} in creation {creation.creation_id}")
                    return False
                delivered_assets[transfer.netuid] = transfer.amount
            
            # 6. Calculate required assets for unit_count
            required_assets = {}
            for netuid, qty_per_unit in basket_spec.assets.items():
                required_assets[netuid] = qty_per_unit * creation.unit_count
            
            # 7. Validate using basket validator
            validation_result = self.basket_validator.validate_all_or_nothing(
                required_assets, 
                delivered_assets, 
                basket_spec.tolerance_bps
            )
            
            if not validation_result.is_valid:
                logger.error(f"Basket validation failed for creation {creation.creation_id}: {validation_result.error_message}")
                return False
            
            # 8. Verify all transfers are from the same source SS58
            # (This is already enforced by the API, but double-check)
            for transfer in creation.transfers:
                # Note: We can't verify the actual sender from transfer data alone
                # This would require on-chain verification
                pass
            
            # 9. Verify transfers are finalized (optional - could be done on-chain)
            # For now, assume transfers are finalized if they have block_hash and extrinsic_index
            
            logger.info(f"Basket validation successful for creation: {creation.creation_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error validating basket for creation {creation.creation_id}: {e}")
            return False
    
    async def _get_basket_specification(self, epoch_id: int) -> Optional[BasketSpecification]:
        """Get basket specification for an epoch"""
        try:
            # Get creation file for the epoch
            creation_file = self.epoch_manager.get_creation_file(epoch_id)
            if not creation_file:
                logger.error(f"No creation file found for epoch {epoch_id}")
                return None
            
            # Convert to BasketSpecification
            basket_spec = BasketSpecification(
                epoch_id=creation_file.epoch_id,
                creation_unit_size=creation_file.creation_unit_size,
                assets=creation_file.assets,
                tolerance_bps=creation_file.tolerance_bps,
                valid_from=creation_file.valid_from,
                valid_until=creation_file.valid_until,
                weights_hash=creation_file.weights_hash
            )
            
            return basket_spec
            
        except Exception as e:
            logger.error(f"Error getting basket specification for epoch {epoch_id}: {e}")
            return None
    
    async def _calculate_nav_at_receipt(self, creation: CreationReceipt) -> int:
        """Calculate NAV at the receipt block (base units)"""
        try:
            logger.info(f"Calculating NAV for creation: {creation.creation_id}")
            
            # Use the earliest block from all transfers as the receipt block
            # This ensures NAV is calculated at the time the creation was "received"
            receipt_block = None
            for transfer in creation.transfers:
                # TODO: Convert block_hash to block number
                # For now, use a mock approach
                if receipt_block is None:
                    receipt_block = 1000000  # Mock block number
            
            if receipt_block is None:
                logger.error(f"No valid receipt block found for creation {creation.creation_id}")
                return 0
            
            # Calculate NAV using the NAV calculator
            nav_calculation = await self.nav_calculator.calculate_nav_at_block(
                epoch_id=creation.epoch_id,
                block_number=receipt_block,
                asset_holdings=self.epoch_manager.get_creation_file(creation.epoch_id).assets,
                total_shares=1000000  # TODO: Get actual total shares
            )
            
            if nav_calculation.status.value == "completed":
                logger.info(f"NAV calculated for creation {creation.creation_id}: {nav_calculation.nav_per_share}")
                return nav_calculation.nav_per_share
            else:
                logger.error(f"NAV calculation failed for creation {creation.creation_id}: {nav_calculation.error_message}")
                return 0
                
        except Exception as e:
            logger.error(f"Error calculating NAV for creation {creation.creation_id}: {e}")
            return 0
    
    async def _provide_attestation(self, creation: CreationReceipt, nav: int) -> AttestationResult:
        """Provide attestation for creation"""
        try:
            current_time = time.time()
            if current_time - self.last_attestation_time < self.min_attestation_interval:
                return AttestationResult(
                    success=False,
                    creation_id=creation.creation_id,
                    nav_at_receipt=nav,
                    error_message="Attestation interval not met"
                )
            
            # Create attestation signature
            signature = await self._sign_attestation(creation, nav)
            
            if signature:
                # Submit attestation to API
                success = await self._submit_attestation(creation, nav, signature)
                
                if success:
                    self.last_attestation_time = current_time
                    
                    return AttestationResult(
                        success=True,
                        creation_id=creation.creation_id,
                        nav_at_receipt=nav,
                        attestation_signature=signature
                    )
                else:
                    return AttestationResult(
                        success=False,
                        creation_id=creation.creation_id,
                        nav_at_receipt=nav,
                        error_message="Failed to submit attestation"
                    )
            else:
                return AttestationResult(
                    success=False,
                    creation_id=creation.creation_id,
                    nav_at_receipt=nav,
                    error_message="Failed to sign attestation"
                )
                
        except Exception as e:
            logger.error(f"Error providing attestation for creation {creation.creation_id}: {e}")
            return AttestationResult(
                success=False,
                creation_id=creation.creation_id,
                nav_at_receipt=nav,
                error_message=str(e)
            )
    
    async def _sign_attestation(self, creation: CreationReceipt, nav: int) -> Optional[str]:
        """Sign attestation for creation"""
        try:
            # Create attestation message
            message = f"{creation.creation_id}:{creation.source_ss58}:{creation.epoch_id}:{creation.weights_hash}:{creation.unit_count}:{nav}:{creation.deadline_ts}"
            
            # Sign with hotkey
            signature = self.bt_wallet.hotkey.sign(message.encode('utf-8'))
            
            return signature.hex()
            
        except Exception as e:
            logger.error(f"Error signing attestation for creation {creation.creation_id}: {e}")
            return None
    
    async def _submit_attestation(self, creation: CreationReceipt, nav: int, signature: str) -> bool:
        """Submit attestation to API"""
        try:
            timeout = aiohttp.ClientTimeout(total=30, connect=5, sock_read=20)
            headers = {"User-Agent": f"tao20-validator/{self.validator_id}", "Content-Type": "application/json"}
            
            payload = {
                "creation_id": creation.creation_id,
                "validator_ss58": self.source_ss58,
                "nav_at_receipt": nav,
                "attestation_signature": signature,
                "timestamp": int(time.time())
            }
            
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.post(f"{self.tao20_api_url}/attestations", json=payload) as response:
                    if response.status == 200:
                        logger.info(f"Attestation submitted successfully for creation: {creation.creation_id}")
                        return True
                    else:
                        logger.error(f"Failed to submit attestation: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error submitting attestation for creation {creation.creation_id}: {e}")
            return False
    
    def get_metrics(self) -> Dict:
        """Get current metrics"""
        metrics = self.metrics.copy()
        
        # Calculate average processing time
        if metrics['avg_processing_time_seconds']:
            metrics['avg_processing_time'] = sum(metrics['avg_processing_time_seconds']) / len(metrics['avg_processing_time_seconds'])
        else:
            metrics['avg_processing_time'] = 0
        
        return metrics
    
    def metrics_snapshot(self) -> str:
        """Export one-liner metrics for log-based monitoring"""
        metrics = self.get_metrics()
        return (f"monitored={metrics['creations_monitored']}, "
                f"attested={metrics['creations_attested']}, "
                f"rejected={metrics['creations_rejected']}, "
                f"avg_processing={metrics.get('avg_processing_time', 0):.2f}s")
    
    def get_incentive_leaderboard(self) -> Dict:
        """Get current incentive leaderboard for miners"""
        return self.incentive_manager.get_leaderboard()
    
    def get_miner_incentive_stats(self, miner_ss58: str) -> Dict:
        """Get incentive statistics for a specific miner"""
        return self.incentive_manager.get_miner_stats(miner_ss58)
    
    def get_validator_incentive_stats(self) -> Dict:
        """Get incentive statistics for this validator"""
        validator_rewards = self.incentive_manager.calculate_validator_rewards()
        
        for reward in validator_rewards:
            if reward.validator_ss58 == self.source_ss58:
                return {
                    'validator_ss58': self.source_ss58,
                    'attestations_provided': reward.attestations_provided,
                    'accuracy_score': reward.accuracy_score,
                    'stake_amount': reward.stake_amount,
                    'base_reward': reward.base_reward,
                    'accuracy_bonus': reward.accuracy_bonus,
                    'stake_bonus': reward.stake_bonus,
                    'total_reward': reward.total_reward,
                    'epoch_progress': self.incentive_manager.get_epoch_progress()
                }
        
        return {
            'validator_ss58': self.source_ss58,
            'attestations_provided': 0,
            'accuracy_score': 0.0,
            'stake_amount': 0,
            'base_reward': 0,
            'accuracy_bonus': 0,
            'stake_bonus': 0,
            'total_reward': 0,
            'epoch_progress': self.incentive_manager.get_epoch_progress()
        }
    
    async def run_attestation_loop(self, interval: int = 60):
        """Main attestation loop"""
        logger.info("Starting TAO20 attestation loop")
        
        while True:
            try:
                # Monitor creations
                await self.monitor_creations(interval)
                
            except Exception as e:
                logger.error(f"Error in attestation loop: {e}")
                await asyncio.sleep(interval)
    
    async def run_bittensor_validator(self):
        """Run the Bittensor validator protocol"""
        await self.run_attestation_loop()


async def main():
    """Main entry point"""
    validator = TAO20Validator(
        wallet_path=os.environ.get("TAO20_WALLET_PATH", "~/.bittensor/wallets/default"),
        source_ss58=os.environ.get("TAO20_SOURCE_SS58"),
        validator_id=os.environ.get("TAO20_VALIDATOR_ID", "tao20_validator_1"),
        tao20_api_url=os.environ.get("TAO20_API_URL", "http://localhost:8000"),
        bittensor_network=os.environ.get("BITTENSOR_NETWORK", "finney"),
        min_attestation_interval=int(os.environ.get("TAO20_MIN_ATTESTATION_INTERVAL", "60")),
        max_creation_age=int(os.environ.get("TAO20_MAX_CREATION_AGE", "3600"))
    )
    
    await validator.run_bittensor_validator()


if __name__ == "__main__":
    asyncio.run(main())
