#!/usr/bin/env python3
"""
TAO20 Index Miner - Authorized Participant
Handles basket assembly and delivery to vault for in-kind minting
"""

import asyncio
import logging
import os
import re
import signal
import time
import hashlib
from typing import Dict, List, Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod

import bittensor as bt
import aiohttp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class BasketSpecification:
    """Basket specification for creation unit"""
    epoch_id: int
    creation_unit_size: int              # base units (integer)
    assets: Dict[int, int]               # netuid -> qty (base units, integer)
    tolerance_bps: int
    valid_from: int
    valid_until: int
    weights_hash: str

@dataclass
class DeliveryResult:
    """Result of basket delivery attempt"""
    success: bool
    creation_id: Optional[str] = None
    delivered_assets: Optional[Dict[int, int]] = None  # integer quantities
    error_message: Optional[str] = None
    transaction_hashes: Optional[List[str]] = None
    deadline_ts: Optional[int] = None
    send_latency_seconds: Optional[float] = None
    receipt_latency_seconds: Optional[float] = None
    attempt_id: Optional[str] = None  # Added for correlation

class AcquisitionStrategy(ABC):
    """Abstract base class for asset acquisition strategies"""
    
    @abstractmethod
    async def can_acquire(self, netuid: int, amount: int) -> bool:  # integer amounts
        """Check if we can acquire the required amount"""
        pass
    
    @abstractmethod
    async def acquire(self, netuid: int, amount: int) -> bool:  # integer amounts
        """Acquire the required amount"""
        pass

class StakeStrategy(AcquisitionStrategy):
    """Staking-based acquisition strategy"""
    
    def __init__(self, source_ss58: str):
        self.source_ss58 = source_ss58
    
    async def can_acquire(self, netuid: int, amount: int) -> bool:
        """Check if we have sufficient TAO to stake"""
        try:
            # TODO: Check actual TAO balance
            logger.debug(f"Checking if can stake sufficient TAO for {amount} subnet {netuid} tokens")
            return True  # Mock - always can stake
        except Exception as e:
            logger.error(f"Error checking stake availability: {e}")
            return False
    
    async def acquire(self, netuid: int, amount: int) -> bool:
        """Stake TAO to acquire subnet tokens"""
        try:
            logger.info(f"Staking TAO to acquire {amount} subnet {netuid} tokens from {self.source_ss58}")
            
            # TODO: Implement actual staking
            # 1. Build stake extrinsic
            # 2. Sign with hotkey
            # 3. Submit to network
            # 4. Wait for finality
            
            await asyncio.sleep(1)  # Mock processing time
            return True
            
        except Exception as e:
            logger.error(f"Error staking to subnet {netuid}: {e}")
            return False

class OTCStrategy(AcquisitionStrategy):
    """Over-the-counter acquisition strategy"""
    
    def __init__(self, otc_partner_ss58: str):
        self.otc_partner_ss58 = otc_partner_ss58
    
    async def can_acquire(self, netuid: int, amount: int) -> bool:
        """Check if OTC partner can provide the tokens"""
        try:
            logger.debug(f"Checking OTC availability for {amount} of subnet {netuid}")
            return True  # Mock - always available
        except Exception as e:
            logger.error(f"Error checking OTC availability: {e}")
            return False
    
    async def acquire(self, netuid: int, amount: int) -> bool:
        """Acquire tokens via OTC"""
        try:
            logger.info(f"Acquiring {amount} of subnet {netuid} via OTC from {self.otc_partner_ss58}")
            
            # TODO: Implement OTC transfer
            # 1. Negotiate price with OTC partner
            # 2. Execute transfer
            # 3. Verify receipt
            
            await asyncio.sleep(1)  # Mock processing time
            return True
            
        except Exception as e:
            logger.error(f"Error acquiring via OTC: {e}")
            return False

class TAO20Miner:
    """
    TAO20 Index Miner as Authorized Participant
    Assembles baskets and delivers to vault for in-kind minting
    """
    
    def __init__(
        self,
        wallet_path: str,
        source_ss58: str,  # Renamed from vault_ss58
        miner_id: str,
        tao20_api_url: str,
        creation_file_dir: str = "./creation_files",
        min_creation_size: int = 1000,  # integer
        acquisition_strategy: Optional[AcquisitionStrategy] = None,
        evm_addr: Optional[str] = None,  # Explicit EVM address
        bittensor_network: Optional[str] = None,  # Configurable network
        strict_all_or_nothing: bool = True,  # SIMPLIFIED: All-or-nothing flag
        dry_run: bool = False  # Dry-run mode for testing
    ):
        self.wallet_path = wallet_path
        self.source_ss58 = source_ss58  # Renamed from vault_ss58
        self.miner_id = miner_id
        self.tao20_api_url = tao20_api_url
        self.creation_file_dir = creation_file_dir
        self.min_creation_size = min_creation_size
        self.strict_all_or_nothing = strict_all_or_nothing
        self.dry_run = dry_run
        
        # Initialize Bittensor wallet and hotkey with error handling
        try:
            self.bt_wallet = bt.wallet(path=wallet_path)
            wallet_ss58 = self.bt_wallet.hotkey.ss58_address
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Bittensor wallet at {wallet_path}: {e}")
        
        # Validate source_ss58 vs wallet hotkey
        if source_ss58 and source_ss58 != wallet_ss58:
            logger.warning(f"Provided source_ss58 ({source_ss58}) differs from wallet hotkey ({wallet_ss58}); using wallet hotkey.")
        self.source_ss58 = wallet_ss58  # Always use wallet hotkey as source of truth
        
        # EVM address validation - fail fast if missing or invalid
        self.evm_addr = evm_addr or os.environ.get("TAO20_EVM_ADDR")
        if not self.evm_addr or not re.fullmatch(r"0x[a-fA-F0-9]{40}", self.evm_addr):
            raise ValueError("TAO20_EVM_ADDR must be a 0x-prefixed, 40-byte hex address")
        
        # Initialize Bittensor connection with configurable network
        try:
            network = bittensor_network or os.environ.get("BITTENSOR_NETWORK", "finney")
            self.subtensor = bt.subtensor(network=network)
        except Exception as e:
            raise RuntimeError(f"Failed to connect to Bittensor network '{network}': {e}")
        
        # Initialize creation file system
        try:
            from creation.epoch_manager import EpochManager
        except ImportError:
            from ..creation.epoch_manager import EpochManager
        self.epoch_manager = EpochManager()
        
        # Set acquisition strategy (default to staking)
        self.acquisition_strategy = acquisition_strategy or StakeStrategy(self.source_ss58)
        
        # State tracking
        self.current_basket_spec: Optional[BasketSpecification] = None
        self.last_delivery_time = 0
        self.min_delivery_interval = 300  # 5 minutes between deliveries
        
        # Crash-safe idempotency: persist attempt metadata
        self._attempt_store_path = os.path.join(self.creation_file_dir, "pending_attempt.json")
        
        # Metrics with capped arrays
        self.metrics = {
            'creations_attempted': 0,
            'creations_receipt_valid': 0,
            'creations_expired': 0,
            'creations_failed': 0,
            'creation_send_latency_seconds': [],
            'receipt_latency_seconds': [],
            'api_rate_limit_retries': 0,
            'finality_wait_seconds': []  # Added for finality tracking
        }
        
        # Initialize advanced metrics
        try:
            from common.metrics import get_metrics
            self.metrics_collector = get_metrics()
        except ImportError:
            self.metrics_collector = None
        
        logger.info(f"TAO20 Miner initialized: {miner_id}")
        logger.info(f"Source SS58: {self.source_ss58}")
        logger.info(f"EVM Address: {self.evm_addr}")
        logger.info(f"Using acquisition strategy: {type(self.acquisition_strategy).__name__}")
        logger.info(f"Strict all-or-nothing: {self.strict_all_or_nothing}")
        logger.info(f"Dry-run mode: {self.dry_run}")
    
    def _new_attempt_id(self, basket_spec: BasketSpecification, unit_count: int) -> str:
        """Generate stable attempt_id for idempotency across retries"""
        seed = f"{basket_spec.epoch_id}:{self.source_ss58}:{unit_count}:{basket_spec.weights_hash}:{os.urandom(8)}"
        return hashlib.sha256(seed.encode()).hexdigest()[:16]
    
    def _estimate_delivery_time(self, assets: Dict[int, int]) -> int:
        """Estimate delivery time in seconds"""
        per_tx_secs = int(os.getenv("TAO20_ESTIMATED_TX_SECONDS", "15"))
        finality_buffer = int(os.getenv("TAO20_FINALITY_BUFFER_SECONDS", "30"))
        return len(assets) * per_tx_secs + finality_buffer
    
    def _add_metric_with_cap(self, metric_name: str, value: float, max_items: int = 500):
        """Add metric value with capped array size"""
        self.metrics[metric_name].append(value)
        if len(self.metrics[metric_name]) > max_items:
            del self.metrics[metric_name][0:len(self.metrics[metric_name])-max_items]
    
    def _persist_attempt(self, attempt_id: str, basket_spec: BasketSpecification, unit_count: int):
        """Persist attempt metadata for crash-safe idempotency"""
        import json
        import tempfile
        payload = {
            "attempt_id": attempt_id,
            "epoch_id": basket_spec.epoch_id,
            "weights_hash": basket_spec.weights_hash,
            "unit_count": unit_count,
            "ss58": self.source_ss58,
        }
        os.makedirs(self.creation_file_dir, exist_ok=True)
        tmp = self._attempt_store_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(payload, f)
        os.replace(tmp, self._attempt_store_path)

    def _load_attempt(self) -> Optional[dict]:
        """Load pending attempt metadata"""
        import json
        try:
            with open(self._attempt_store_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return None
        except Exception as e:
            logger.warning(f"Failed to read pending attempt: {e}")
            return None

    def _clear_attempt(self):
        """Clear pending attempt metadata"""
        try:
            os.remove(self._attempt_store_path)
        except FileNotFoundError:
            pass

    def metrics_snapshot(self) -> str:
        """Export one-liner metrics for log-based monitoring"""
        metrics = self.get_metrics()
        return (f"creations={metrics['creations_attempted']}, "
                f"success={metrics['creations_receipt_valid']}, "
                f"expired={metrics['creations_expired']}, "
                f"failed={metrics['creations_failed']}, "
                f"avg_send={metrics.get('avg_send_latency_seconds', 0):.2f}s, "
                f"avg_receipt={metrics.get('avg_receipt_latency_seconds', 0):.2f}s, "
                f"avg_finality={metrics.get('avg_finality_wait_seconds', 0):.2f}s")
    
    async def get_current_basket_specification(self, unit_count: int = 1) -> Optional[BasketSpecification]:
        """Get current basket specification from creation file system"""
        try:
            # Get current epoch
            current_epoch = self.epoch_manager.get_current_epoch_id()
            
            # Get creation file for current epoch
            creation_file = self.epoch_manager.get_creation_file(current_epoch)
            if not creation_file:
                logger.error(f"No creation file found for epoch {current_epoch}")
                return None
            
            # Check if epoch is still valid
            if not self.epoch_manager.is_epoch_active(current_epoch):
                logger.warning(f"Epoch {current_epoch} is not active")
                return None
            
            # Calculate required quantities for unit_count - ALL INTEGERS IN BASE UNITS
            assets = {}
            for asset in creation_file.assets:
                # Ensure qty_per_creation_unit is in base units (no decimals)
                # TODO: Add per-asset decimals map if needed
                # For now, ensure Creation File quantities are already base units
                if hasattr(asset, 'base_units') and not asset.base_units:
                    logger.error(f"Creation file quantities must be in base units for asset {asset.netuid}")
                    return None
                
                required_qty = int(asset.qty_per_creation_unit) * int(unit_count)  # Ensure integers
                assets[asset.netuid] = required_qty
            
            logger.debug(f"Basket specification for {unit_count} creation units:")
            for netuid, qty in assets.items():
                logger.debug(f"  Subnet {netuid}: {qty} tokens (base units)")
            
            return BasketSpecification(
                epoch_id=creation_file.epoch_id,
                creation_unit_size=int(creation_file.creation_unit_size),  # Ensure integer
                assets=assets,
                tolerance_bps=creation_file.tolerance_bps,
                valid_from=creation_file.valid_from,
                valid_until=creation_file.valid_until,
                weights_hash=creation_file.weights_hash
            )
            
        except Exception as e:
            logger.error(f"Failed to get basket specification: {e}")
            return None
    
    async def check_creation_opportunity(self, unit_count: int = 1) -> Optional[Dict]:
        """Check if there's an opportunity to create TAO20 via basket delivery"""
        try:
            # Get current basket specification
            basket_spec = await self.get_current_basket_specification(unit_count)
            if not basket_spec:
                return None
            
            # Check minimum creation size
            total_size = unit_count * basket_spec.creation_unit_size
            if total_size < self.min_creation_size:
                logger.debug(f"Creation size {total_size} below minimum {self.min_creation_size}")
                return None
            
            # Check if we have sufficient assets to deliver the basket
            can_deliver = await self._check_asset_availability(basket_spec)
            
            if can_deliver:
                return {
                    "type": "creation",
                    "basket_spec": basket_spec,
                    "unit_count": unit_count,
                    "creation_unit_size": basket_spec.creation_unit_size
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to check creation opportunity: {e}")
            return None
    
    async def _check_asset_availability(self, basket_spec: BasketSpecification) -> bool:
        """Check if we have sufficient assets to deliver the basket"""
        try:
            for netuid, required_qty in basket_spec.assets.items():
                current_balance = await self._get_subnet_balance(netuid)
                if current_balance < required_qty:
                    # Check if we can acquire the missing amount
                    can_acquire = await self.acquisition_strategy.can_acquire(netuid, required_qty - current_balance)
                    if not can_acquire:
                        logger.warning(f"Cannot acquire {required_qty - current_balance} of subnet {netuid} tokens")
                        return False
            return True
        except Exception as e:
            logger.error(f"Failed to check asset availability: {e}")
            return False
    
    async def _get_subnet_balance(self, netuid: int) -> int:  # Return integer
        """Get current balance of subnet tokens"""
        try:
            # TODO: Implement actual balance checking from Bittensor substrate
            # This would query the stake balance for the miner's hotkey on the subnet
            logger.debug(f"Getting balance for subnet {netuid}")
            return 1000  # Mock balance (integer)
        except Exception as e:
            logger.error(f"Error getting subnet balance: {e}")
            return 0
    
    async def assemble_and_deliver_basket(self, basket_spec: BasketSpecification, unit_count: int) -> DeliveryResult:
        """Assemble and deliver basket to vault"""
        try:
            current_time = time.time()
            if current_time - self.last_delivery_time < self.min_delivery_interval:
                return DeliveryResult(
                    success=False,
                    error_message="Delivery interval not met"
                )
            
            # Update metrics
            self.metrics['creations_attempted'] += 1
            
            # Assemble basket
            delivered_assets = await self._assemble_basket(basket_spec)
            if not delivered_assets:
                return DeliveryResult(
                    success=False,
                    error_message="Failed to assemble basket"
                )
            
            # Validate basket before delivery
            validation_result = await self._validate_basket_delivery(delivered_assets, basket_spec)
            if not validation_result.is_valid:
                return DeliveryResult(
                    success=False,
                    error_message=f"Basket validation failed: {validation_result.errors}"
                )
            
            # Deliver to vault
            delivery_result = await self._deliver_to_vault(delivered_assets, basket_spec, unit_count)
            
            if delivery_result.success:
                self.last_delivery_time = current_time
                logger.info(f"Successfully delivered basket: {delivery_result.creation_id}")
                return delivery_result
            else:
                return delivery_result
                
        except Exception as e:
            logger.error(f"Failed to assemble and deliver basket: {e}")
            return DeliveryResult(
                success=False,
                error_message=str(e)
            )
    
    async def _assemble_basket(self, basket_spec: BasketSpecification) -> Optional[Dict[int, int]]:  # Integer quantities
        """Assemble the basket of assets"""
        try:
            assembled_assets = {}
            
            for netuid, required_qty in basket_spec.assets.items():
                current_balance = await self._get_subnet_balance(netuid)
                
                if current_balance < required_qty:
                    # Acquire missing amount using strategy
                    acquired = await self.acquisition_strategy.acquire(netuid, required_qty - current_balance)
                    if not acquired:
                        logger.error(f"Failed to acquire {required_qty - current_balance} of subnet {netuid}")
                        return None
                    
                    # Update balance after acquisition
                    current_balance = await self._get_subnet_balance(netuid)
                
                # FIXED: Deliver exact required amount, not current balance
                assembled_assets[netuid] = required_qty  # Exact required amount
            
            return assembled_assets
            
        except Exception as e:
            logger.error(f"Failed to assemble basket: {e}")
            return None
    
    async def _validate_basket_delivery(self, assets: Dict[int, int], basket_spec: BasketSpecification) -> 'BasketValidationResult':
        """Validate basket delivery against specification"""
        try:
            from creation.basket_validator import BasketValidator
        except ImportError:
            from ..creation.basket_validator import BasketValidator
        
        # Add global tolerance check
        validator = BasketValidator(
            tolerance_bps=basket_spec.tolerance_bps, 
            global_tolerance_bps=30  # 0.3% global tolerance
        )
        return validator.validate_all_or_nothing(basket_spec.assets, assets)
    
    async def _wait_for_finality(self, block_hash: str, timeout_s: int = 180) -> bool:
        """Wait for block finality - TODO: Implement real Substrate RPC"""
        try:
            # TODO: Implement actual finality check
            # 1. Query finalized head via RPC
            # 2. Compare block_hash to finalized head
            # 3. Return True if finalized, False if timeout
            
            logger.debug(f"Waiting for finality of block {block_hash[:16]}...")
            await asyncio.sleep(2)  # Mock finality wait
            return True  # Mock - always finalized
            
        except Exception as e:
            logger.error(f"Error waiting for finality: {e}")
            return False
    
    async def _deliver_to_vault(self, assets: Dict[int, int], basket_spec: BasketSpecification, unit_count: int) -> DeliveryResult:
        """Deliver basket to vault - REGISTER FIRST, THEN SEND TRANSFERS - ALL OR NOTHING"""
        try:
            # Recheck minimum creation size (defensive)
            total_size = unit_count * basket_spec.creation_unit_size
            if total_size < self.min_creation_size:
                return DeliveryResult(
                    success=False,
                    error_message=f"Creation size {total_size} below minimum {self.min_creation_size}"
                )
            
            # Load and validate vault configuration
            vault_config = await self._load_vault_config()
            if not vault_config:
                return DeliveryResult(
                    success=False,
                    error_message="Failed to load vault configuration"
                )
            
            # FIXED: Permissive vault config check (subset, not equality)
            missing = set(assets.keys()) - set(vault_config.keys())
            if missing:
                return DeliveryResult(
                    success=False,
                    error_message=f"Vault config missing netuids: {sorted(missing)}"
                )
            
            # Crash-safe idempotency: reuse existing attempt or create new one
            pending = self._load_attempt()
            if pending and pending.get("epoch_id") == basket_spec.epoch_id \
               and pending.get("weights_hash") == basket_spec.weights_hash \
               and pending.get("unit_count") == unit_count \
               and pending.get("ss58") == self.source_ss58:
                attempt_id = pending["attempt_id"]
                logger.info(f"[{attempt_id}] Reusing pending attempt")
            else:
                attempt_id = self._new_attempt_id(basket_spec, unit_count)
                self._persist_attempt(attempt_id, basket_spec, unit_count)
            
            # Use single HTTP session for entire attempt with timeouts and headers
            timeout = aiohttp.ClientTimeout(total=30, connect=5, sock_read=20)
            headers = {"User-Agent": f"tao20-miner/{self.miner_id}", "Content-Type": "application/json"}
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                # 1) REGISTER FIRST - get creation_id and deadline
                creation = await self._register_creation(basket_spec, [], unit_count, attempt_id, session)
                if not creation:
                    return DeliveryResult(
                        success=False,
                        error_message="Failed to register creation"
                    )
                
                creation_id = creation.get("creation_id")
                deadline_ts = creation.get("deadline_ts")
                
                if not creation_id:
                    return DeliveryResult(
                        success=False,
                        error_message="No creation_id returned from server"
                    )
                
                # Log creation_id early for correlation
                logger.info(f"[{attempt_id}] Registered creation {creation_id} with deadline {deadline_ts}")
                
                # 2) PRE-FLIGHT CHECK - can we finish before deadline?
                estimated_secs = self._estimate_delivery_time(assets)
                if deadline_ts and time.time() + estimated_secs > deadline_ts:
                    return DeliveryResult(
                        success=False,
                        error_message="Insufficient time before deadline",
                        deadline_ts=deadline_ts,
                        attempt_id=attempt_id
                    )
                
                # 3) SEND TRANSFERS - all from same source_ss58 with deadline guards
                send_start_time = time.time()
                tx_hashes = []
                transfers = []
                
                per_tx_secs = int(os.getenv("TAO20_ESTIMATED_TX_SECONDS", "15"))
                buffer_secs = int(os.getenv("TAO20_FINALITY_BUFFER_SECONDS", "30"))
                
                # FIXED: Deterministic transfer order
                for i, netuid in enumerate(sorted(assets.keys())):
                    amount = assets[netuid]
                    
                    # FIXED: Guard deadline during transfer loop
                    remaining_secs = (len(assets) - i) * per_tx_secs + buffer_secs
                    if deadline_ts and time.time() + remaining_secs > deadline_ts:
                        logger.warning(f"[{attempt_id}] Deadline risk detected mid-loop, aborting creation {creation_id}")
                        return DeliveryResult(
                            success=False,
                            error_message="Insufficient time before deadline (mid-loop)",
                            deadline_ts=deadline_ts,
                            attempt_id=attempt_id
                        )
                    
                    vault_ss58 = vault_config.get(netuid)
                    if not vault_ss58:
                        return DeliveryResult(
                            success=False,
                            error_message=f"No vault configured for subnet {netuid}",
                            attempt_id=attempt_id
                        )
                    
                    # Send transfer to vault FROM THE SAME SS58 (enforced)
                    transfer_ref = await self._send_transfer_to_vault(netuid, amount, vault_ss58)
                    if not transfer_ref:
                        # FIXED: Use strict_all_or_nothing flag
                        if not self.strict_all_or_nothing and transfers:
                            # (optional) report partials for refund flows
                            logger.warning(f"[{attempt_id}] Transfer failed for subnet {netuid}, reporting partial transfers for refund")
                            await self._update_creation_transfers(creation_id, transfers, creation_id, session)
                        else:
                            logger.error(f"[{attempt_id}] Transfer failed for subnet {netuid}, aborting entire creation")
                        return DeliveryResult(
                            success=False,
                            error_message=f"Failed to send transfer for subnet {netuid}",
                            attempt_id=attempt_id
                        )
                    
                    # Wait for finality before proceeding
                    finality_start = time.time()
                    finalized = await self._wait_for_finality(transfer_ref["block_hash"])
                    finality_time = time.time() - finality_start
                    self._add_metric_with_cap('finality_wait_seconds', finality_time)
                    
                    if not finalized:
                        logger.error(f"[{attempt_id}] Transfer for subnet {netuid} did not finalize in time")
                        return DeliveryResult(
                            success=False,
                            error_message=f"Transfer for subnet {netuid} did not finalize",
                            attempt_id=attempt_id
                        )
                    
                    tx_hashes.append(transfer_ref["tx_hash"])
                    transfers.append({
                        "netuid": netuid,
                        "amount": int(amount),  # Ensure integer
                        "vault_ss58": vault_ss58,
                        "tx_hash": transfer_ref["tx_hash"],
                        "block_hash": transfer_ref["block_hash"],  # FIXED: Include block_hash
                        "extrinsic_index": transfer_ref["extrinsic_index"]  # FIXED: Include extrinsic_index
                    })
                
                send_latency = time.time() - send_start_time
                
                # 4) UPDATE SERVER WITH TRANSFER REFERENCES (idempotent)
                # FIXED: Use creation_id for transfer idempotency
                update_success = await self._update_creation_transfers(creation_id, transfers, creation_id, session)
                if not update_success:
                    return DeliveryResult(
                        success=False,
                        error_message="Failed to update creation with transfer references",
                        attempt_id=attempt_id
                    )
                
                # 5) POLL FOR STATUS
                receipt_start_time = time.time()
                receipt_status = await self._wait_for_receipt_validation(creation_id, session)
                receipt_latency = time.time() - receipt_start_time
                
                # Update metrics with capped arrays
                self._add_metric_with_cap('creation_send_latency_seconds', send_latency)
                self._add_metric_with_cap('receipt_latency_seconds', receipt_latency)
                
                # FIXED: Treat 'minted' as success
                if receipt_status in ("receipt_valid", "minted"):
                    self.metrics['creations_receipt_valid'] += 1
                    logger.info(f"[{attempt_id}] Creation {creation_id} successful with status: {receipt_status}")
                    self._clear_attempt()  # Clear pending attempt on success
                    return DeliveryResult(
                        success=True,
                        creation_id=creation_id,
                        delivered_assets=assets,
                        transaction_hashes=tx_hashes,
                        deadline_ts=deadline_ts,
                        send_latency_seconds=send_latency,
                        receipt_latency_seconds=receipt_latency,
                        attempt_id=attempt_id
                    )
                elif receipt_status == "expired":
                    self.metrics['creations_expired'] += 1
                    logger.warning(f"[{attempt_id}] Creation {creation_id} expired")
                    self._clear_attempt()  # Clear pending attempt on expiry
                    return DeliveryResult(
                        success=False,
                        error_message="Creation expired",
                        deadline_ts=deadline_ts,
                        send_latency_seconds=send_latency,
                        receipt_latency_seconds=receipt_latency,
                        attempt_id=attempt_id
                    )
                else:
                    self.metrics['creations_failed'] += 1
                    logger.error(f"[{attempt_id}] Creation {creation_id} failed with status: {receipt_status}")
                    self._clear_attempt()  # Clear pending attempt on failure
                    return DeliveryResult(
                        success=False,
                        error_message=f"Creation failed with status: {receipt_status}",
                        deadline_ts=deadline_ts,
                        send_latency_seconds=send_latency,
                        receipt_latency_seconds=receipt_latency,
                        attempt_id=attempt_id
                    )
                
        except Exception as e:
            logger.error(f"Failed to deliver to vault: {e}")
            return DeliveryResult(
                success=False,
                error_message=str(e)
            )
    
    async def _load_vault_config(self) -> Dict[int, str]:
        """Load and validate vault configuration mapping netuid to vault SS58 addresses"""
        try:
            config_path = os.path.join(self.creation_file_dir, "vaults.json")
            if os.path.exists(config_path):
                import json
                with open(config_path, 'r') as f:
                    raw = json.load(f)
                    # Fix: Convert string keys to integers
                    vault_config = {int(k): v for k, v in raw.items()}
            else:
                # Default vault configuration
                vault_config = {
                    1: "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",  # Alice
                    2: "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty",  # Bob
                    3: "5FLSigC9HGRKVhB9FiEo4Y3koPsNmBmLJbpXg2mp1hXcS59Y",  # Charlie
                    # Add more as needed
                }
            
            # Validate vault configuration
            if len(vault_config) != 20:
                logger.warning(f"Vault config has {len(vault_config)} entries, expected 20")
            
            # Check for duplicates
            vault_addresses = list(vault_config.values())
            if len(vault_addresses) != len(set(vault_addresses)):
                logger.warning("Duplicate vault addresses found in configuration")
            
            # Validate SS58 prefix (Bittensor addresses start with '5')
            for netuid, address in vault_config.items():
                if not address.startswith('5'):
                    logger.warning(f"Vault address for subnet {netuid} doesn't start with '5': {address}")
            
            return vault_config
            
        except Exception as e:
            logger.error(f"Error loading vault config: {e}")
            return {}
    
    async def _send_transfer_to_vault(self, netuid: int, amount: int, vault_ss58: str) -> Optional[Dict]:  # FIXED: Return dict with block_hash and extrinsic_index
        """Send transfer to vault for specific subnet FROM THE SAME SS58"""
        try:
            # TODO: Implement actual Substrate transfer
            # This would:
            # 1. Build transfer extrinsic FROM self.source_ss58 TO vault_ss58
            # 2. Sign with hotkey
            # 3. Submit to network
            # 4. Wait for inclusion
            # 5. Return transaction hash, block hash, and extrinsic index
            
            logger.debug(f"Sending {amount} tokens FROM {self.source_ss58} TO vault {vault_ss58} for subnet {netuid}")
            
            # Mock transfer with block_hash and extrinsic_index
            await asyncio.sleep(0.5)
            tx_hash = f"0x{os.urandom(32).hex()}"
            block_hash = f"0x{os.urandom(32).hex()}"  # TODO: real finalized block hash
            extrinsic_index = 0  # TODO: real index from inclusion
            
            return {
                "tx_hash": tx_hash,
                "block_hash": block_hash,
                "extrinsic_index": extrinsic_index
            }
            
        except Exception as e:
            logger.error(f"Error sending transfer: {e}")
            return None
    
    async def _register_creation(self, basket_spec: BasketSpecification, transfer_records: List[Dict], unit_count: int, attempt_id: str, session: aiohttp.ClientSession) -> Optional[Dict]:
        """Register creation with TAO20 API - with retry policy"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Use stable attempt_id for idempotency
                idempotency_key = f"create:{attempt_id}"
                
                creation_data = {
                    "epoch_id": basket_spec.epoch_id,
                    "weights_hash": basket_spec.weights_hash,
                    "ss58": self.source_ss58,  # ENFORCED: All transfers from same SS58
                    "evm_addr": self.evm_addr,  # Use explicit EVM address
                    "unit_count": unit_count,
                    "transfers": transfer_records,
                    "idempotency_key": idempotency_key,  # Prevent duplicate registrations
                    "network": os.environ.get("BITTENSOR_NETWORK", "finney")  # FIXED: Include network/chain_id
                }
                
                async with session.post(f"{self.tao20_api_url}/creations", json=creation_data) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result  # Return full response for deadline_ts
                    elif response.status in [429, 503]:  # Rate limit
                        self.metrics['api_rate_limit_retries'] += 1
                        delay = min(2 ** attempt, 60)  # Exponential backoff
                        logger.warning(f"[{attempt_id}] API rate limited (attempt {attempt + 1}/{max_retries}), backing off for {delay}s")
                        if attempt < max_retries - 1:  # Don't sleep on last attempt
                            await asyncio.sleep(delay)
                        continue
                    else:
                        # FIXED: More informative error logs
                        body = await response.text()
                        logger.error(f"[{attempt_id}] POST {self.tao20_api_url}/creations failed: {response.status} – {body[:500]}")
                        break
                        
            except Exception as e:
                logger.error(f"Error registering creation (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(min(2 ** attempt, 60))
                continue
        
        return None
    
    async def _update_creation_transfers(self, creation_id: str, transfers: List[Dict], idempotency_key: str, session: aiohttp.ClientSession) -> bool:
        """Update creation with transfer references - with retry policy"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                async with session.post(
                    f"{self.tao20_api_url}/creations/{creation_id}/transfers", 
                    json={"transfers": transfers, "idempotency_key": idempotency_key}
                ) as response:
                    if response.status == 200:
                        return True
                    elif response.status in [429, 503]:  # Rate limit
                        self.metrics['api_rate_limit_retries'] += 1
                        delay = min(2 ** attempt, 60)  # Exponential backoff
                        logger.warning(f"API rate limited (attempt {attempt + 1}/{max_retries}), backing off for {delay}s")
                        if attempt < max_retries - 1:  # Don't sleep on last attempt
                            await asyncio.sleep(delay)
                        continue
                    else:
                        # FIXED: More informative error logs
                        body = await response.text()
                        logger.error(f"POST {self.tao20_api_url}/creations/{creation_id}/transfers failed: {response.status} – {body[:500]}")
                        break
                        
            except Exception as e:
                logger.error(f"Error updating creation transfers (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(min(2 ** attempt, 60))
                continue
        
        return False
    
    async def _wait_for_receipt_validation(self, creation_id: str, session: aiohttp.ClientSession) -> str:
        """Wait for receipt validation status - SINGLE SESSION"""
        try:
            for attempt in range(60):  # 5 minutes with 5-second intervals
                try:
                    async with session.get(f"{self.tao20_api_url}/creations/{creation_id}/status") as response:
                        if response.status == 200:
                            result = await response.json()
                            status = result.get("status")
                            
                            if status in ["receipt_valid", "minted", "expired", "refunded"]:
                                return status
                        elif response.status in [429, 503]:  # Rate limit
                            self.metrics['api_rate_limit_retries'] += 1
                            delay = min(2 ** attempt, 60)  # Exponential backoff
                            logger.warning(f"API rate limited, backing off for {delay}s")
                            await asyncio.sleep(delay)
                            continue
                        else:
                            # FIXED: More informative error logs
                            body = await response.text()
                            logger.warning(f"GET {self.tao20_api_url}/creations/{creation_id}/status failed: {response.status} – {body[:500]}")
                    
                except Exception as e:
                    logger.error(f"Error checking status: {e}")
                
                await asyncio.sleep(5)  # Poll every 5 seconds
            
            return "timeout"
            
        except Exception as e:
            logger.error(f"Error waiting for receipt validation: {e}")
            return "error"
    
    async def run_creation_loop(self, interval: int = 60, stop_event: Optional[asyncio.Event] = None):
        """Main creation loop for basket assembly and delivery"""
        logger.info("Starting TAO20 creation loop")
        
        consecutive_failures = 0
        max_failures = 5
        
        while not (stop_event and stop_event.is_set()):
            try:
                # Check for creation opportunity (start with 1 unit)
                opportunity = await self.check_creation_opportunity(unit_count=1)
                
                if opportunity:
                    logger.info(f"Found creation opportunity: {opportunity}")
                    
                    basket_spec = opportunity["basket_spec"]
                    unit_count = opportunity["unit_count"]
                    result = await self.assemble_and_deliver_basket(basket_spec, unit_count)
                    
                    if result.success:
                        consecutive_failures = 0
                        logger.info(f"Successfully delivered basket: {result.creation_id}")
                        logger.debug(f"Delivered assets: {result.delivered_assets}")
                        if result.send_latency_seconds:
                            logger.info(f"Send latency: {result.send_latency_seconds:.2f}s")
                        if result.receipt_latency_seconds:
                            logger.info(f"Receipt latency: {result.receipt_latency_seconds:.2f}s")
                    else:
                        consecutive_failures += 1
                        logger.error(f"Failed to deliver basket: {result.error_message}")
                else:
                    consecutive_failures = 0
                
                # Exponential backoff on consecutive failures
                if consecutive_failures > 0:
                    backoff_interval = min(interval * (2 ** consecutive_failures), 3600)
                    logger.warning(f"Backing off for {backoff_interval} seconds due to {consecutive_failures} failures")
                    await asyncio.sleep(backoff_interval)
                else:
                    await asyncio.sleep(interval)
                
                # Check for max failures
                if consecutive_failures >= max_failures:
                    logger.error("Too many consecutive failures, stopping miner")
                    break
                
            except asyncio.CancelledError:
                logger.info("Creation loop cancelled")
                break
            except Exception as e:
                consecutive_failures += 1
                logger.error(f"Error in creation loop: {e}")
                await asyncio.sleep(interval)
    
    async def run_bittensor_miner(self):
        """Run the Bittensor miner protocol"""
        await self.run_creation_loop()
    
    def get_metrics(self) -> Dict:
        """Get current metrics"""
        metrics = self.metrics.copy()
        
        # Calculate average latencies
        if metrics['creation_send_latency_seconds']:
            metrics['avg_send_latency_seconds'] = sum(metrics['creation_send_latency_seconds']) / len(metrics['creation_send_latency_seconds'])
        else:
            metrics['avg_send_latency_seconds'] = 0
            
        if metrics['receipt_latency_seconds']:
            metrics['avg_receipt_latency_seconds'] = sum(metrics['receipt_latency_seconds']) / len(metrics['receipt_latency_seconds'])
        else:
            metrics['avg_receipt_latency_seconds'] = 0
        
        if metrics['finality_wait_seconds']:
            metrics['avg_finality_wait_seconds'] = sum(metrics['finality_wait_seconds']) / len(metrics['finality_wait_seconds'])
        else:
            metrics['avg_finality_wait_seconds'] = 0
        
        return metrics


async def main():
    """Main entry point"""
    # Example: Use OTC strategy instead of staking
    # otc_strategy = OTCStrategy("5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY")
    
    # Setup graceful shutdown
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in ("SIGINT", "SIGTERM"):
        try:
            loop.add_signal_handler(getattr(signal, sig), stop.set)
        except Exception:
            pass  # Windows/limited envs
    
    miner = TAO20Miner(
        wallet_path=os.environ.get("TAO20_WALLET_PATH", "~/.bittensor/wallets/default"),
        source_ss58=os.environ.get("TAO20_SOURCE_SS58"),  # Renamed from TAO20_VAULT_SS58
        miner_id=os.environ.get("TAO20_MINER_ID", "tao20_miner_1"),
        tao20_api_url=os.environ.get("TAO20_API_URL", "http://localhost:8000"),
        creation_file_dir=os.environ.get("TAO20_CREATION_FILE_DIR", "./creation_files"),
        evm_addr=os.environ.get("TAO20_EVM_ADDR"),  # Explicit EVM address
        bittensor_network=os.environ.get("BITTENSOR_NETWORK", "finney"),  # Configurable network
        strict_all_or_nothing=os.environ.get("TAO20_STRICT_ALL_OR_NOTHING", "true").lower() == "true",  # All-or-nothing flag
        dry_run=os.environ.get("TAO20_DRY_RUN", "false").lower() == "true"  # Dry-run mode
        # acquisition_strategy=otc_strategy  # Optional: override default staking strategy
    )
    
    await miner.run_creation_loop(stop_event=stop)


if __name__ == "__main__":
    asyncio.run(main())
