#!/usr/bin/env python3
"""
Substrate Vault Manager for TAO20 Index
Handles tracking of alpha token deposits and vault operations
"""

import asyncio
import logging
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json
import hashlib

import bittensor as bt
from web3 import Web3

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class DepositInfo:
    """Information about a user's deposit"""
    deposit_id: str
    user_address: str
    netuid: int
    amount: float
    timestamp: float
    nav_at_deposit: float
    status: str  # 'pending', 'confirmed', 'minted', 'failed'
    transaction_hash: Optional[str] = None
    tao20_amount: Optional[float] = None
    error_message: Optional[str] = None

@dataclass
class VaultState:
    """Current state of the vault"""
    total_deposits: Dict[int, float]  # netuid -> total amount
    total_tao20_minted: float
    last_nav_update: float
    current_nav: float
    fees_accrued: float

class SubstrateVaultManager:
    """
    Manages substrate vault operations for TAO20 Index
    """
    
    def __init__(
        self,
        vault_coldkey: str,
        vault_hotkey: str,
        subtensor_network: str = "finney",
        state_file: str = "vault_state.json"
    ):
        self.vault_coldkey = vault_coldkey
        self.vault_hotkey = vault_hotkey
        self.subtensor_network = subtensor_network
        self.state_file = Path(state_file)
        
        # Initialize Bittensor connection
        self.subtensor = bt.subtensor(network=subtensor_network)
        
        # State tracking
        self.deposits: Dict[str, DepositInfo] = {}
        self.deposit_counter = 0
        self.vault_state = VaultState(
            total_deposits={},
            total_tao20_minted=0.0,
            last_nav_update=0.0,
            current_nav=0.0,
            fees_accrued=0.0
        )
        
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
                    self.deposits[deposit_id] = DepositInfo(**deposit_data)
                
                # Load vault state
                vault_data = data.get('vault_state', {})
                self.vault_state = VaultState(**vault_data)
                
                # Set deposit counter
                self.deposit_counter = data.get('deposit_counter', 0)
                
                logger.info(f"Loaded {len(self.deposits)} deposits from state file")
                
            except Exception as e:
                logger.error(f"Error loading state: {e}")
    
    def save_state(self):
        """Save vault state to file"""
        try:
            data = {
                'deposits': {deposit_id: asdict(deposit) for deposit_id, deposit in self.deposits.items()},
                'vault_state': asdict(self.vault_state),
                'deposit_counter': self.deposit_counter
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving state: {e}")
    
    def create_deposit_id(self, user_address: str, netuid: int, amount: float) -> str:
        """Create a unique deposit ID"""
        timestamp = int(time.time())
        hash_input = f"{user_address}_{netuid}_{amount}_{timestamp}_{self.deposit_counter}"
        deposit_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
        
        deposit_id = f"deposit_{timestamp}_{deposit_hash}"
        return deposit_id
    
    async def track_deposit(
        self, 
        user_address: str, 
        netuid: int, 
        amount: float,
        nav_at_deposit: Optional[float] = None
    ) -> str:
        """Track when user deposits alpha tokens to vault"""
        
        # Get current NAV if not provided
        if nav_at_deposit is None:
            nav_at_deposit = await self.get_current_nav()
        
        # Create deposit ID
        deposit_id = self.create_deposit_id(user_address, netuid, amount)
        
        # Create deposit info
        deposit_info = DepositInfo(
            deposit_id=deposit_id,
            user_address=user_address,
            netuid=netuid,
            amount=amount,
            timestamp=time.time(),
            nav_at_deposit=nav_at_deposit,
            status='pending'
        )
        
        # Store deposit
        self.deposits[deposit_id] = deposit_info
        
        # Update vault state
        if netuid not in self.vault_state.total_deposits:
            self.vault_state.total_deposits[netuid] = 0.0
        self.vault_state.total_deposits[netuid] += amount
        
        # Save state
        self.save_state()
        
        logger.info(f"Tracked deposit {deposit_id}: {amount} alpha tokens from subnet {netuid}")
        
        return deposit_id
    
    async def verify_deposit(self, user_address: str, deposit_id: str) -> bool:
        """Verify user has actually deposited to vault"""
        
        if deposit_id not in self.deposits:
            logger.warning(f"Deposit {deposit_id} not found")
            return False
        
        deposit = self.deposits[deposit_id]
        
        if deposit.user_address != user_address:
            logger.warning(f"Deposit {deposit_id} belongs to different user")
            return False
        
        # Check if vault has the required stake
        try:
            vault_stake = await self.get_vault_stake(deposit.netuid)
            required_stake = deposit.amount
            
            if vault_stake >= required_stake:
                # Mark as confirmed
                deposit.status = 'confirmed'
                self.save_state()
                logger.info(f"Deposit {deposit_id} confirmed")
                return True
            else:
                logger.warning(f"Insufficient vault stake for deposit {deposit_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error verifying deposit {deposit_id}: {e}")
            return False
    
    async def get_vault_stake(self, netuid: int) -> float:
        """Get vault's stake in a specific subnet"""
        try:
            # Get vault's stake using Bittensor API
            stake = self.subtensor.get_stake_for_coldkey_and_subnet(
                coldkey_ss58=self.vault_coldkey,
                netuid=netuid
            )
            
            return float(stake.tao)
            
        except Exception as e:
            logger.error(f"Error getting vault stake for subnet {netuid}: {e}")
            return 0.0
    
    async def get_current_nav(self) -> float:
        """Get current NAV for TAO20 index"""
        try:
            # This would integrate with your existing NAV calculation
            # For now, return a placeholder
            return 1.0
            
        except Exception as e:
            logger.error(f"Error getting current NAV: {e}")
            return 1.0
    
    async def calculate_tao20_amount(self, deposit_id: str) -> float:
        """Calculate TAO20 amount for a deposit based on NAV at deposit time"""
        
        if deposit_id not in self.deposits:
            raise ValueError(f"Deposit {deposit_id} not found")
        
        deposit = self.deposits[deposit_id]
        
        # Calculate TAO20 amount based on NAV at deposit time
        tao20_amount = deposit.amount / deposit.nav_at_deposit
        
        # Update deposit info
        deposit.tao20_amount = tao20_amount
        self.save_state()
        
        return tao20_amount
    
    async def mark_deposit_minted(self, deposit_id: str, transaction_hash: str):
        """Mark a deposit as successfully minted"""
        
        if deposit_id not in self.deposits:
            raise ValueError(f"Deposit {deposit_id} not found")
        
        deposit = self.deposits[deposit_id]
        deposit.status = 'minted'
        deposit.transaction_hash = transaction_hash
        
        # Update vault state
        self.vault_state.total_tao20_minted += deposit.tao20_amount or 0.0
        
        self.save_state()
        
        logger.info(f"Deposit {deposit_id} marked as minted")
    
    async def mark_deposit_failed(self, deposit_id: str, error_message: str):
        """Mark a deposit as failed"""
        
        if deposit_id not in self.deposits:
            raise ValueError(f"Deposit {deposit_id} not found")
        
        deposit = self.deposits[deposit_id]
        deposit.status = 'failed'
        deposit.error_message = error_message
        
        self.save_state()
        
        logger.error(f"Deposit {deposit_id} marked as failed: {error_message}")
    
    def get_deposit_status(self, deposit_id: str) -> Optional[Dict]:
        """Get status of a specific deposit"""
        
        if deposit_id not in self.deposits:
            return None
        
        deposit = self.deposits[deposit_id]
        return asdict(deposit)
    
    def get_user_deposits(self, user_address: str) -> List[Dict]:
        """Get all deposits for a specific user"""
        
        user_deposits = []
        for deposit in self.deposits.values():
            if deposit.user_address == user_address:
                user_deposits.append(asdict(deposit))
        
        return user_deposits
    
    def get_vault_summary(self) -> Dict:
        """Get summary of vault state"""
        
        total_deposits_value = sum(self.vault_state.total_deposits.values())
        
        return {
            'total_deposits_value': total_deposits_value,
            'total_tao20_minted': self.vault_state.total_tao20_minted,
            'current_nav': self.vault_state.current_nav,
            'fees_accrued': self.vault_state.fees_accrued,
            'deposits_by_subnet': self.vault_state.total_deposits,
            'total_deposits_count': len(self.deposits)
        }
    
    async def cleanup_old_deposits(self, days_old: int = 30):
        """Clean up old completed deposits"""
        
        cutoff_time = time.time() - (days_old * 24 * 3600)
        deposits_to_remove = []
        
        for deposit_id, deposit in self.deposits.items():
            if (deposit.timestamp < cutoff_time and 
                deposit.status in ['minted', 'failed']):
                deposits_to_remove.append(deposit_id)
        
        for deposit_id in deposits_to_remove:
            del self.deposits[deposit_id]
        
        if deposits_to_remove:
            self.save_state()
            logger.info(f"Cleaned up {len(deposits_to_remove)} old deposits")
    
    async def validate_deposit_batch(self, deposit_ids: List[str]) -> Tuple[List[str], List[str]]:
        """Validate a batch of deposits"""
        
        valid_deposits = []
        invalid_deposits = []
        
        for deposit_id in deposit_ids:
            if deposit_id in self.deposits:
                deposit = self.deposits[deposit_id]
                if deposit.status == 'confirmed':
                    valid_deposits.append(deposit_id)
                else:
                    invalid_deposits.append(deposit_id)
            else:
                invalid_deposits.append(deposit_id)
        
        return valid_deposits, invalid_deposits
