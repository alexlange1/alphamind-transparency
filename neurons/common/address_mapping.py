#!/usr/bin/env python3
"""
Bittensor to EVM Address Mapping System

This module provides secure mapping between Bittensor hotkeys (SS58 format) 
and Ethereum-compatible addresses for the TAO20 oracle system.
"""

import hashlib
import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
import bittensor as bt
from eth_account import Account
from eth_utils import to_checksum_address
import base58

logger = logging.getLogger(__name__)


@dataclass
class AddressMapping:
    """Address mapping between Bittensor and EVM"""
    hotkey_ss58: str
    hotkey_hex: str  
    evm_address: str
    private_key: Optional[str] = None  # Only for miners


class BittensorEVMMapper:
    """
    Maps Bittensor hotkeys to EVM addresses deterministically
    
    This creates a deterministic mapping so that the same Bittensor hotkey
    always maps to the same EVM address, enabling consistent tracking
    across the oracle system.
    """
    
    def __init__(self, wallet: bt.wallet):
        self.wallet = wallet
        self.mapping_cache: Dict[str, AddressMapping] = {}
        
    def get_evm_address_from_hotkey(self, hotkey_ss58: str) -> str:
        """
        Convert Bittensor hotkey (SS58) to EVM address deterministically
        
        Args:
            hotkey_ss58: Bittensor hotkey in SS58 format
            
        Returns:
            str: Ethereum-compatible address (checksummed)
        """
        if hotkey_ss58 in self.mapping_cache:
            return self.mapping_cache[hotkey_ss58].evm_address
            
        # Convert SS58 to hex
        try:
            # Decode SS58 to get the raw public key bytes
            decoded = base58.b58decode(hotkey_ss58)
            
            # Remove the network prefix and checksum (first byte and last 2 bytes)
            # SS58 format: [network_prefix][32_byte_pubkey][2_byte_checksum]
            if len(decoded) != 35:  # 1 + 32 + 2 bytes
                raise ValueError(f"Invalid SS58 address length: {len(decoded)}")
                
            pubkey_bytes = decoded[1:33]  # Extract the 32-byte public key
            pubkey_hex = pubkey_bytes.hex()
            
            # Create deterministic EVM address from Bittensor public key
            # Use Keccak256 hash of the public key (Ethereum standard)
            from Crypto.Hash import keccak
            
            # Take last 20 bytes of Keccak256 hash for Ethereum address
            hash_obj = keccak.new(digest_bits=256)
            hash_obj.update(pubkey_bytes)
            address_bytes = hash_obj.digest()[-20:]
            
            evm_address = to_checksum_address('0x' + address_bytes.hex())
            
            # Cache the mapping
            mapping = AddressMapping(
                hotkey_ss58=hotkey_ss58,
                hotkey_hex=pubkey_hex,
                evm_address=evm_address
            )
            self.mapping_cache[hotkey_ss58] = mapping
            
            logger.debug(f"Mapped {hotkey_ss58[:10]}... -> {evm_address}")
            return evm_address
            
        except Exception as e:
            logger.error(f"Failed to convert hotkey to EVM address: {e}")
            raise ValueError(f"Invalid Bittensor hotkey format: {hotkey_ss58}")
    
    def get_own_evm_address(self) -> str:
        """Get EVM address for this wallet's hotkey"""
        return self.get_evm_address_from_hotkey(self.wallet.hotkey.ss58_address)
    
    def create_evm_account_for_mining(self) -> Tuple[str, str]:
        """
        Create a new EVM account for mining operations
        
        For miners, we need actual EVM private keys to sign transactions.
        This creates a new account and returns both address and private key.
        
        Returns:
            Tuple[str, str]: (evm_address, private_key_hex)
        """
        # Create deterministic private key from Bittensor hotkey
        hotkey_ss58 = self.wallet.hotkey.ss58_address
        
        # Use hotkey as seed for deterministic key generation
        seed = hashlib.sha256(hotkey_ss58.encode()).digest()
        
        # Create EVM account from seed
        account = Account.from_key(seed)
        
        # Cache the mapping with private key
        mapping = AddressMapping(
            hotkey_ss58=hotkey_ss58,
            hotkey_hex=self.wallet.hotkey.public_key.hex(),
            evm_address=account.address,
            private_key=account.key.hex()
        )
        self.mapping_cache[hotkey_ss58] = mapping
        
        logger.info(f"Created EVM mining account: {account.address}")
        return account.address, account.key.hex()
    
    def get_mapping_for_hotkey(self, hotkey_ss58: str) -> AddressMapping:
        """Get complete mapping information for a hotkey"""
        evm_address = self.get_evm_address_from_hotkey(hotkey_ss58)
        return self.mapping_cache[hotkey_ss58]
    
    def get_all_known_mappings(self) -> Dict[str, AddressMapping]:
        """Get all cached address mappings"""
        return self.mapping_cache.copy()
    
    def verify_mapping(self, hotkey_ss58: str, evm_address: str) -> bool:
        """Verify that a hotkey correctly maps to an EVM address"""
        try:
            expected_address = self.get_evm_address_from_hotkey(hotkey_ss58)
            return expected_address.lower() == evm_address.lower()
        except Exception:
            return False


class MinerAddressManager(BittensorEVMMapper):
    """
    Extended address manager for miners that need to sign transactions
    """
    
    def __init__(self, wallet: bt.wallet):
        super().__init__(wallet)
        self.evm_account = None
        self.private_key = None
        self._initialize_mining_account()
    
    def _initialize_mining_account(self):
        """Initialize the EVM account for mining operations"""
        self.evm_address, self.private_key = self.create_evm_account_for_mining()
        self.evm_account = Account.from_key(self.private_key)
        
        logger.info(f"Miner EVM account initialized: {self.evm_address}")
    
    def get_mining_address(self) -> str:
        """Get the EVM address for mining operations"""
        return self.evm_address
    
    def get_private_key(self) -> str:
        """Get the private key for signing transactions"""
        return self.private_key
    
    def sign_transaction(self, transaction_dict: dict) -> dict:
        """
        Sign an EVM transaction with the miner's private key
        
        Args:
            transaction_dict: Web3 transaction dictionary
            
        Returns:
            dict: Signed transaction ready for broadcast
        """
        try:
            signed_txn = self.evm_account.sign_transaction(transaction_dict)
            return signed_txn
        except Exception as e:
            logger.error(f"Failed to sign transaction: {e}")
            raise


class ValidatorAddressManager(BittensorEVMMapper):
    """
    Extended address manager for validators that only need to read data
    """
    
    def __init__(self, wallet: bt.wallet):
        super().__init__(wallet)
        self.validator_address = self.get_own_evm_address()
        
        logger.info(f"Validator EVM address: {self.validator_address}")
    
    def get_validator_address(self) -> str:
        """Get the EVM address for this validator"""
        return self.validator_address
    
    def map_metagraph_to_evm(self, metagraph: bt.metagraph) -> Dict[int, str]:
        """
        Map all UIDs in metagraph to their corresponding EVM addresses
        
        Args:
            metagraph: Bittensor metagraph
            
        Returns:
            Dict[int, str]: Mapping from UID to EVM address
        """
        uid_to_evm = {}
        
        for uid in range(metagraph.n.item()):
            try:
                hotkey = metagraph.hotkeys[uid]
                evm_address = self.get_evm_address_from_hotkey(hotkey)
                uid_to_evm[uid] = evm_address
            except Exception as e:
                logger.warning(f"Failed to map UID {uid}: {e}")
                continue
                
        logger.info(f"Mapped {len(uid_to_evm)} UIDs to EVM addresses")
        return uid_to_evm


# Utility functions for common operations
def get_miner_address_manager(wallet: bt.wallet) -> MinerAddressManager:
    """Create a miner address manager"""
    return MinerAddressManager(wallet)


def get_validator_address_manager(wallet: bt.wallet) -> ValidatorAddressManager:
    """Create a validator address manager"""  
    return ValidatorAddressManager(wallet)


def verify_address_mapping(hotkey_ss58: str, evm_address: str, wallet: bt.wallet) -> bool:
    """Verify that a hotkey maps to the expected EVM address"""
    mapper = BittensorEVMMapper(wallet)
    return mapper.verify_mapping(hotkey_ss58, evm_address)
