#!/usr/bin/env python3
"""
Enhanced Substrate Vault Manager for TAO20 Index
Records deposits with block hash and extrinsic index, handles attestation-based minting
"""

import asyncio
import logging
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple, Set
from pathlib import Path
import json
import hashlib
from enum import Enum

import bittensor as bt
from web3 import Web3

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DepositStatus(Enum):
    PENDING = "pending"
    RECORDED = "recorded"
    ATTESTED = "attested"
    MINTED = "minted"
    FAILED = "failed"

@dataclass
class DepositRecord:
    """Enhanced deposit record with blockchain metadata"""
    deposit_id: str
    user_ss58: str
    netuid: int
    amount: float
    block_hash: str
    extrinsic_index: int
    timestamp: float
    status: DepositStatus
    nav_at_deposit: float
    nonce: int
    expiry: int
    chain_id: str
    domain: str
    # Attestation tracking
    attestations: Set[str]  # Set of validator hotkeys that attested
    required_attestations: int
    # Minting info
    claimer_evm: Optional[str] = None
    signature: Optional[str] = None
    transaction_hash: Optional[str] = None
    tao20_amount: Optional[float] = None
    error_message: Optional[str] = None

@dataclass
class MintClaim:
    """Mint claim request"""
    deposit_id: str
    claimer_evm: str
    ss58_pubkey: str
    signature: str
    amount: float
    nonce: int
    expiry: int
    chain_id: str
    domain: str

class EnhancedSubstrateVaultManager:
    """
    Enhanced vault manager with attestation-based minting
    """
    
    def __init__(
        self,
        vault_ss58: str,
        subtensor_network: str = "finney",
        state_file: str = "enhanced_vault_state.json",
        required_attestations: int = 2,
        total_validators: int = 3
    ):
        self.vault_ss58 = vault_ss58
        self.subtensor_network = subtensor_network
        self.state_file = Path(state_file)
        self.required_attestations = required_attestations
        self.total_validators = total_validators
        
        # Initialize Bittensor connection
        self.subtensor = bt.subtensor(network=subtensor_network)
        
        # State tracking
        self.deposits: Dict[str, DepositRecord] = {}
        self.deposit_counter = 0
        self.nonce_tracker: Dict[str, int] = {}  # Track nonces per user
        self.attestation_threshold = required_attestations / total_validators
        
        # Load existing state
        self.load_state()
    
    def load_state(self):
        """Load vault state from file"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                
                # Load deposits
                self.deposits = {}
                for deposit_id, deposit_data in data.get('deposits', {}).items():
                    # Convert status string back to enum
                    deposit_data['status'] = DepositStatus(deposit_data['status'])
                    # Convert attestations list back to set
                    deposit_data['attestations'] = set(deposit_data.get('attestations', []))
                    self.deposits[deposit_id] = DepositRecord(**deposit_data)
                
                # Load nonce tracker
                self.nonce_tracker = data.get('nonce_tracker', {})
                self.deposit_counter = data.get('deposit_counter', 0)
                
                logger.info(f"Loaded {len(self.deposits)} deposits from state file")
                
            except Exception as e:
                logger.error(f"Error loading state: {e}")
    
    def save_state(self):
        """Save vault state to file"""
        try:
            data = {
                'deposits': {
                    deposit_id: {
                        **asdict(deposit),
                        'status': deposit.status.value,  # Convert enum to string
                        'attestations': list(deposit.attestations)  # Convert set to list
                    }
                    for deposit_id, deposit in self.deposits.items()
                },
                'nonce_tracker': self.nonce_tracker,
                'deposit_counter': self.deposit_counter
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving state: {e}")
    
    def create_deposit_id(self, user_ss58: str, netuid: int, amount: float, block_hash: str, extrinsic_index: int) -> str:
        """Create a unique deposit ID based on blockchain data"""
        hash_input = f"{user_ss58}_{netuid}_{amount}_{block_hash}_{extrinsic_index}_{self.deposit_counter}"
        deposit_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
        
        deposit_id = f"deposit_{int(time.time())}_{deposit_hash}"
        return deposit_id
    
    def get_next_nonce(self, user_ss58: str) -> int:
        """Get next nonce for a user"""
        current_nonce = self.nonce_tracker.get(user_ss58, 0)
        self.nonce_tracker[user_ss58] = current_nonce + 1
        return current_nonce
    
    async def record_deposit(
        self, 
        user_ss58: str, 
        netuid: int, 
        amount: float,
        block_hash: str,
        extrinsic_index: int,
        nav_at_deposit: Optional[float] = None
    ) -> str:
        """Record a deposit with blockchain metadata after finality"""
        
        # Get current NAV if not provided
        if nav_at_deposit is None:
            nav_at_deposit = await self.get_current_nav()
        
        # Create deposit ID
        deposit_id = self.create_deposit_id(user_ss58, netuid, amount, block_hash, extrinsic_index)
        
        # Get next nonce for user
        nonce = self.get_next_nonce(user_ss58)
        
        # Create deposit record
        deposit_record = DepositRecord(
            deposit_id=deposit_id,
            user_ss58=user_ss58,
            netuid=netuid,
            amount=amount,
            block_hash=block_hash,
            extrinsic_index=extrinsic_index,
            timestamp=time.time(),
            status=DepositStatus.RECORDED,
            nav_at_deposit=nav_at_deposit,
            nonce=nonce,
            expiry=int(time.time()) + (24 * 3600),  # 24 hour expiry
            chain_id=self.subtensor_network,
            domain="alphamind.xyz",
            attestations=set(),
            required_attestations=self.required_attestations
        )
        
        # Store deposit
        self.deposits[deposit_id] = deposit_record
        
        # Save state
        self.save_state()
        
        logger.info(f"Recorded deposit {deposit_id}: {amount} alpha tokens from subnet {netuid}")
        logger.info(f"Block: {block_hash}, Extrinsic: {extrinsic_index}")
        
        return deposit_id
    
    def create_mint_claim_message(
        self, 
        deposit_id: str, 
        claimer_evm: str, 
        amount: float, 
        nonce: int, 
        expiry: int, 
        chain_id: str, 
        domain: str
    ) -> str:
        """Create the structured message for mint claim signature"""
        
        # Structured message format
        message = (
            f"mint-claim\n"
            f"deposit-id: {deposit_id}\n"
            f"claimer-evm: {claimer_evm}\n"
            f"amount: {amount}\n"
            f"nonce: {nonce}\n"
            f"expiry: {expiry}\n"
            f"chain-id: {chain_id}\n"
            f"domain: {domain}"
        )
        
        return message
    
    def verify_mint_claim_signature(
        self, 
        mint_claim: MintClaim, 
        signature: str, 
        ss58_pubkey: str
    ) -> bool:
        """Verify the mint claim signature"""
        
        try:
            # Create the expected message
            expected_message = self.create_mint_claim_message(
                mint_claim.deposit_id,
                mint_claim.claimer_evm,
                mint_claim.amount,
                mint_claim.nonce,
                mint_claim.expiry,
                mint_claim.chain_id,
                mint_claim.domain
            )
            
            # Verify signature using Bittensor's Ed25519 precompile
            # This would call the actual precompile in production
            # For now, we'll simulate the verification
            return self._simulate_signature_verification(expected_message, signature, ss58_pubkey)
            
        except Exception as e:
            logger.error(f"Error verifying mint claim signature: {e}")
            return False
    
    def _simulate_signature_verification(self, message: str, signature: str, ss58_pubkey: str) -> bool:
        """Simulate signature verification (replace with actual precompile call)"""
        # In production, this would call the Ed25519VerifyPrecompile
        # For now, we'll return True for testing
        logger.info(f"Simulating signature verification for message: {message[:50]}...")
        return True
    
    async def attest_deposit(self, deposit_id: str, validator_hotkey: str) -> bool:
        """Attest to a deposit (called by validators)"""
        
        if deposit_id not in self.deposits:
            logger.warning(f"Deposit {deposit_id} not found for attestation")
            return False
        
        deposit = self.deposits[deposit_id]
        
        # Check if already attested by this validator
        if validator_hotkey in deposit.attestations:
            logger.warning(f"Validator {validator_hotkey} already attested to deposit {deposit_id}")
            return False
        
        # Add attestation
        deposit.attestations.add(validator_hotkey)
        
        # Check if we have enough attestations
        if len(deposit.attestations) >= deposit.required_attestations:
            deposit.status = DepositStatus.ATTESTED
            logger.info(f"Deposit {deposit_id} attested by {len(deposit.attestations)} validators")
        
        self.save_state()
        return True
    
    async def process_mint_claim(
        self, 
        mint_claim: MintClaim, 
        signature: str
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Process a mint claim request"""
        
        try:
            # Verify deposit exists and is attested
            if mint_claim.deposit_id not in self.deposits:
                return False, None, "Deposit not found"
            
            deposit = self.deposits[mint_claim.deposit_id]
            
            if deposit.status != DepositStatus.ATTESTED:
                return False, None, f"Deposit not attested. Status: {deposit.status.value}"
            
            # Verify signature
            if not self.verify_mint_claim_signature(mint_claim, signature, mint_claim.ss58_pubkey):
                return False, None, "Invalid signature"
            
            # Check nonce
            if mint_claim.nonce != deposit.nonce:
                return False, None, "Invalid nonce"
            
            # Check expiry
            if time.time() > mint_claim.expiry:
                return False, None, "Claim expired"
            
            # Check amount matches
            if abs(mint_claim.amount - deposit.amount) > 0.001:  # Allow small floating point differences
                return False, None, "Amount mismatch"
            
            # Update deposit with claim info
            deposit.claimer_evm = mint_claim.claimer_evm
            deposit.signature = signature
            deposit.status = DepositStatus.MINTED
            
            # Calculate TAO20 amount
            deposit.tao20_amount = deposit.amount / deposit.nav_at_deposit
            
            self.save_state()
            
            logger.info(f"Mint claim processed for deposit {mint_claim.deposit_id}")
            return True, deposit.tao20_amount, None
            
        except Exception as e:
            logger.error(f"Error processing mint claim: {e}")
            return False, None, str(e)
    
    async def get_current_nav(self) -> float:
        """Get current NAV for TAO20 index"""
        try:
            # This would integrate with your existing NAV calculation
            # For now, return a placeholder
            return 1.0
            
        except Exception as e:
            logger.error(f"Error getting current NAV: {e}")
            return 1.0
    
    def get_deposit_status(self, deposit_id: str) -> Optional[Dict]:
        """Get status of a specific deposit"""
        
        if deposit_id not in self.deposits:
            return None
        
        deposit = self.deposits[deposit_id]
        deposit_dict = asdict(deposit)
        deposit_dict['status'] = deposit.status.value
        deposit_dict['attestations'] = list(deposit.attestations)
        return deposit_dict
    
    def get_user_deposits(self, user_ss58: str) -> List[Dict]:
        """Get all deposits for a specific user"""
        
        user_deposits = []
        for deposit in self.deposits.values():
            if deposit.user_ss58 == user_ss58:
                deposit_dict = asdict(deposit)
                deposit_dict['status'] = deposit.status.value
                deposit_dict['attestations'] = list(deposit.attestations)
                user_deposits.append(deposit_dict)
        
        return user_deposits
    
    def get_pending_attestations(self) -> List[Dict]:
        """Get deposits pending attestation"""
        
        pending = []
        for deposit in self.deposits.values():
            if deposit.status == DepositStatus.RECORDED:
                deposit_dict = asdict(deposit)
                deposit_dict['status'] = deposit.status.value
                deposit_dict['attestations'] = list(deposit.attestations)
                deposit_dict['attestation_progress'] = f"{len(deposit.attestations)}/{deposit.required_attestations}"
                pending.append(deposit_dict)
        
        return pending
    
    def get_attested_deposits(self) -> List[Dict]:
        """Get deposits that are attested and ready for minting"""
        
        attested = []
        for deposit in self.deposits.values():
            if deposit.status == DepositStatus.ATTESTED:
                deposit_dict = asdict(deposit)
                deposit_dict['status'] = deposit.status.value
                deposit_dict['attestations'] = list(deposit.attestations)
                attested.append(deposit_dict)
        
        return attested
    
    async def cleanup_expired_deposits(self, max_age_hours: int = 24):
        """Clean up expired deposits"""
        
        cutoff_time = time.time() - (max_age_hours * 3600)
        deposits_to_remove = []
        
        for deposit_id, deposit in self.deposits.items():
            if (deposit.timestamp < cutoff_time and 
                deposit.status in [DepositStatus.RECORDED, DepositStatus.FAILED]):
                deposits_to_remove.append(deposit_id)
        
        for deposit_id in deposits_to_remove:
            del self.deposits[deposit_id]
        
        if deposits_to_remove:
            self.save_state()
            logger.info(f"Cleaned up {len(deposits_to_remove)} expired deposits")
    
    async def monitor_deposits(self, interval: int = 60):
        """Monitor for new deposits and handle attestations"""
        
        logger.info("Starting deposit monitoring")
        
        while True:
            try:
                # Check for deposits that need attestation
                pending = self.get_pending_attestations()
                
                for deposit in pending:
                    logger.info(f"Deposit {deposit['deposit_id']} needs attestation: {deposit['attestation_progress']}")
                
                # Clean up expired deposits
                await self.cleanup_expired_deposits()
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"Error in deposit monitoring: {e}")
                await asyncio.sleep(interval)
