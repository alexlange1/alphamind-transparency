#!/usr/bin/env python3
"""
Bittensor Precompile Integration for TAO20 Subnet
Based on official documentation: https://docs.learnbittensor.org/evm-tutorials/
"""

import hashlib
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from web3 import Web3
from eth_account.messages import encode_defunct


# Precompile addresses from Bittensor documentation
ED25519_VERIFY_PRECOMPILE = "0x0000000000000000000000000000000000000402"
STAKING_PRECOMPILE = "0x0000000000000000000000000000000000000805"
METAGRAPH_PRECOMPILE = "0x0000000000000000000000000000000000000806"


@dataclass
class ValidatorInfo:
    """Validator information from metagraph"""
    hotkey: str
    coldkey: str
    stake: int  # In RAO (1 TAO = 1e9 RAO)
    rank: int
    trust: float
    consensus: float
    incentive: float
    dividends: float
    emission: int
    last_update: int


@dataclass
class MinerInfo:
    """Miner information from metagraph"""
    hotkey: str
    coldkey: str
    stake: int  # In RAO
    rank: int
    trust: float
    consensus: float
    incentive: float
    dividends: float
    emission: int
    last_update: int


class BittensorPrecompiles:
    """
    Wrapper for Bittensor precompile interactions
    Provides easy access to ED25519 verification, staking, and metagraph data
    """
    
    def __init__(self, web3: Web3, netuid: int):
        self.web3 = web3
        self.netuid = netuid
    
    def verify_ed25519_signature(
        self,
        message: bytes,
        signature: bytes,
        public_key: bytes
    ) -> bool:
        """
        Verify ED25519 signature using precompile
        
        Args:
            message: Original message that was signed
            signature: 64-byte ED25519 signature
            public_key: 32-byte ED25519 public key
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # Prepare input data for precompile
            # Format: message (32 bytes) + signature (64 bytes) + public_key (32 bytes)
            message_hash = hashlib.sha256(message).digest()
            input_data = message_hash + signature + public_key
            
            # Call precompile
            result = self.web3.eth.call({
                'to': ED25519_VERIFY_PRECOMPILE,
                'data': input_data.hex()
            })
            
            # Precompile returns 1 for valid, 0 for invalid
            return int(result.hex(), 16) == 1
            
        except Exception as e:
            print(f"ED25519 verification failed: {e}")
            return False
    
    def get_stake_info(self, hotkey: str) -> Optional[Dict]:
        """
        Get staking information for a hotkey
        
        Args:
            hotkey: SS58 address of the hotkey
            
        Returns:
            Dictionary with staking information or None if failed
        """
        try:
            # Convert SS58 to bytes32 for precompile
            hotkey_bytes = self._ss58_to_bytes32(hotkey)
            
            # Prepare input: netuid (32 bytes) + hotkey (32 bytes)
            input_data = self.netuid.to_bytes(32, 'big') + hotkey_bytes
            
            # Call staking precompile
            result = self.web3.eth.call({
                'to': STAKING_PRECOMPILE,
                'data': input_data.hex()
            })
            
            # Parse result (format depends on precompile implementation)
            # This is a placeholder - actual format should be verified
            if result and len(result) >= 32:
                stake_amount = int.from_bytes(result[:32], 'big')
                return {
                    'hotkey': hotkey,
                    'stake_amount': stake_amount,
                    'netuid': self.netuid
                }
            
            return None
            
        except Exception as e:
            print(f"Failed to get stake info: {e}")
            return None
    
    def get_metagraph_info(self) -> Optional[Dict]:
        """
        Get complete metagraph information for the subnet
        
        Returns:
            Dictionary with validators and miners info or None if failed
        """
        try:
            # Prepare input: netuid (32 bytes)
            input_data = self.netuid.to_bytes(32, 'big')
            
            # Call metagraph precompile
            result = self.web3.eth.call({
                'to': METAGRAPH_PRECOMPILE,
                'data': input_data.hex()
            })
            
            if not result:
                return None
            
            # Parse metagraph data
            # This is a placeholder - actual parsing should match precompile format
            validators, miners = self._parse_metagraph_data(result)
            
            return {
                'netuid': self.netuid,
                'validators': validators,
                'miners': miners,
                'total_stake': sum(v.stake for v in validators),
                'validator_count': len(validators),
                'miner_count': len(miners)
            }
            
        except Exception as e:
            print(f"Failed to get metagraph info: {e}")
            return None
    
    def get_validator_set(self) -> List[ValidatorInfo]:
        """Get list of active validators with their information"""
        metagraph = self.get_metagraph_info()
        if metagraph:
            return metagraph.get('validators', [])
        return []
    
    def get_miner_set(self) -> List[MinerInfo]:
        """Get list of active miners with their information"""
        metagraph = self.get_metagraph_info()
        if metagraph:
            return metagraph.get('miners', [])
        return []
    
    def get_top_validators_by_stake(self, limit: int = 10) -> List[ValidatorInfo]:
        """Get top validators sorted by stake amount"""
        validators = self.get_validator_set()
        return sorted(validators, key=lambda v: v.stake, reverse=True)[:limit]
    
    def get_validator_consensus_weights(self) -> Dict[str, float]:
        """Get consensus weights for all validators"""
        validators = self.get_validator_set()
        return {v.hotkey: v.consensus for v in validators}
    
    def verify_miner_signature(
        self,
        miner_hotkey: str,
        message: str,
        signature: str
    ) -> bool:
        """
        Verify that a message was signed by a specific miner
        
        Args:
            miner_hotkey: SS58 address of the miner's hotkey
            message: Original message that was signed
            signature: Hex-encoded signature
            
        Returns:
            True if signature is valid and from the specified miner
        """
        try:
            # Convert inputs to proper format
            message_bytes = message.encode('utf-8')
            signature_bytes = bytes.fromhex(signature.replace('0x', ''))
            public_key_bytes = self._ss58_to_public_key(miner_hotkey)
            
            # Verify using precompile
            return self.verify_ed25519_signature(
                message_bytes,
                signature_bytes,
                public_key_bytes
            )
            
        except Exception as e:
            print(f"Miner signature verification failed: {e}")
            return False
    
    def _ss58_to_bytes32(self, ss58_address: str) -> bytes:
        """Convert SS58 address to bytes32 format for precompiles"""
        # This is a placeholder - actual implementation should use proper SS58 decoding
        # For now, use a simple hash
        return hashlib.sha256(ss58_address.encode()).digest()
    
    def _ss58_to_public_key(self, ss58_address: str) -> bytes:
        """Convert SS58 address to public key bytes"""
        # This is a placeholder - actual implementation should extract public key
        # For now, use a simple hash (first 32 bytes)
        return hashlib.sha256(ss58_address.encode()).digest()[:32]
    
    def _parse_metagraph_data(self, data: bytes) -> Tuple[List[ValidatorInfo], List[MinerInfo]]:
        """
        Parse raw metagraph data from precompile
        
        This is a placeholder implementation - actual format should be verified
        against the precompile specification
        """
        validators = []
        miners = []
        
        # Placeholder parsing logic
        # Actual implementation should match precompile data format
        offset = 0
        
        # Read validator count
        if len(data) >= offset + 4:
            validator_count = int.from_bytes(data[offset:offset+4], 'big')
            offset += 4
            
            # Parse validators
            for i in range(validator_count):
                if len(data) >= offset + 128:  # Assuming 128 bytes per validator
                    validator = self._parse_validator_data(data[offset:offset+128])
                    if validator:
                        validators.append(validator)
                    offset += 128
        
        # Read miner count
        if len(data) >= offset + 4:
            miner_count = int.from_bytes(data[offset:offset+4], 'big')
            offset += 4
            
            # Parse miners
            for i in range(miner_count):
                if len(data) >= offset + 128:  # Assuming 128 bytes per miner
                    miner = self._parse_miner_data(data[offset:offset+128])
                    if miner:
                        miners.append(miner)
                    offset += 128
        
        return validators, miners
    
    def _parse_validator_data(self, data: bytes) -> Optional[ValidatorInfo]:
        """Parse individual validator data"""
        try:
            # Placeholder parsing - actual format should be verified
            hotkey = data[:32].hex()
            coldkey = data[32:64].hex()
            stake = int.from_bytes(data[64:72], 'big')
            rank = int.from_bytes(data[72:76], 'big')
            trust = int.from_bytes(data[76:80], 'big') / 1e9  # Assuming fixed point
            consensus = int.from_bytes(data[80:84], 'big') / 1e9
            incentive = int.from_bytes(data[84:88], 'big') / 1e9
            dividends = int.from_bytes(data[88:92], 'big') / 1e9
            emission = int.from_bytes(data[92:100], 'big')
            last_update = int.from_bytes(data[100:108], 'big')
            
            return ValidatorInfo(
                hotkey=hotkey,
                coldkey=coldkey,
                stake=stake,
                rank=rank,
                trust=trust,
                consensus=consensus,
                incentive=incentive,
                dividends=dividends,
                emission=emission,
                last_update=last_update
            )
        except Exception:
            return None
    
    def _parse_miner_data(self, data: bytes) -> Optional[MinerInfo]:
        """Parse individual miner data"""
        try:
            # Placeholder parsing - actual format should be verified
            hotkey = data[:32].hex()
            coldkey = data[32:64].hex()
            stake = int.from_bytes(data[64:72], 'big')
            rank = int.from_bytes(data[72:76], 'big')
            trust = int.from_bytes(data[76:80], 'big') / 1e9
            consensus = int.from_bytes(data[80:84], 'big') / 1e9
            incentive = int.from_bytes(data[84:88], 'big') / 1e9
            dividends = int.from_bytes(data[88:92], 'big') / 1e9
            emission = int.from_bytes(data[92:100], 'big')
            last_update = int.from_bytes(data[100:108], 'big')
            
            return MinerInfo(
                hotkey=hotkey,
                coldkey=coldkey,
                stake=stake,
                rank=rank,
                trust=trust,
                consensus=consensus,
                incentive=incentive,
                dividends=dividends,
                emission=emission,
                last_update=last_update
            )
        except Exception:
            return None
