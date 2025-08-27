#!/usr/bin/env python3
"""
TAO20 Minting API
Backend API for processing mint requests with signature verification
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import asdict
import json
import hashlib

import bittensor as bt
from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_defunct

from ..vault.substrate_vault_manager import SubstrateVaultManager
from ..miner.tao20_miner import TAO20Miner

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TAO20MintingAPI:
    """
    Backend API for processing TAO20 mint requests
    """
    
    def __init__(
        self,
        vault_coldkey: str,
        vault_hotkey: str,
        contract_address: str,
        rpc_url: str,
        miner_wallet_path: str,
        miner_hotkey_path: str,
        subtensor_network: str = "finney"
    ):
        self.vault_coldkey = vault_coldkey
        self.vault_hotkey = vault_hotkey
        self.contract_address = contract_address
        self.rpc_url = rpc_url
        self.subtensor_network = subtensor_network
        
        # Initialize components
        self.vault_manager = SubstrateVaultManager(
            vault_coldkey=vault_coldkey,
            vault_hotkey=vault_hotkey,
            subtensor_network=subtensor_network
        )
        
        self.miner = TAO20Miner(
            wallet_path=miner_wallet_path,
            hotkey_path=miner_hotkey_path,
            contract_address=contract_address,
            rpc_url=rpc_url,
            subnet_uid=21,  # TAO20 subnet
            miner_id="tao20_minting_api"
        )
        
        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        
        # Load contract ABI
        self.contract_abi = self._load_contract_abi()
        self.contract = self.w3.eth.contract(
            address=contract_address,
            abi=self.contract_abi
        )
    
    def _load_contract_abi(self) -> List[Dict]:
        """Load the TAO20 contract ABI"""
        return [
            {
                "inputs": [
                    {"name": "amount", "type": "uint256"},
                    {"name": "minerHotkey", "type": "bytes32"},
                    {"name": "signature", "type": "bytes"},
                    {"name": "message", "type": "bytes"}
                ],
                "name": "mintInKind",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [
                    {"name": "amount", "type": "uint256"},
                    {"name": "minerHotkey", "type": "bytes32"},
                    {"name": "signature", "type": "bytes"},
                    {"name": "message", "type": "bytes"}
                ],
                "name": "redeemInKind",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "getIndexComposition",
                "outputs": [
                    {"name": "subnets", "type": "uint256[]"},
                    {"name": "weights", "type": "uint256[]"}
                ],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [{"name": "minerHotkey", "type": "bytes32"}],
                "name": "getMinerVolume",
                "outputs": [{"name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]
    
    def verify_signature(
        self, 
        user_address: str, 
        deposit_info: Dict, 
        signature: str,
        message: str
    ) -> bool:
        """Verify user signature for deposit confirmation"""
        
        try:
            # Create the expected message
            expected_message = self._create_deposit_message(deposit_info)
            
            if message != expected_message:
                logger.warning(f"Message mismatch for user {user_address}")
                return False
            
            # Verify signature
            message_hash = encode_defunct(text=message)
            recovered_address = Account.recover_message(message_hash, signature=signature)
            
            # Convert addresses to checksum format for comparison
            user_address_checksum = Web3.to_checksum_address(user_address)
            recovered_address_checksum = Web3.to_checksum_address(recovered_address)
            
            if user_address_checksum != recovered_address_checksum:
                logger.warning(f"Signature verification failed for user {user_address}")
                return False
            
            logger.info(f"Signature verified for user {user_address}")
            return True
            
        except Exception as e:
            logger.error(f"Error verifying signature for user {user_address}: {e}")
            return False
    
    def _create_deposit_message(self, deposit_info: Dict) -> str:
        """Create the message that should be signed by the user"""
        
        return (
            f"I confirm I deposited {deposit_info['amount']} alpha tokens "
            f"from subnet {deposit_info['netuid']} to the TAO20 vault "
            f"at timestamp {deposit_info['timestamp']}. "
            f"Deposit ID: {deposit_info['deposit_id']}"
        )
    
    async def process_mint_request(
        self, 
        user_address: str, 
        deposit_info: Dict, 
        signature: str,
        message: str
    ) -> Dict:
        """Process a TAO20 mint request"""
        
        try:
            # 1. Verify signature
            if not self.verify_signature(user_address, deposit_info, signature, message):
                return {
                    'success': False,
                    'error': 'Invalid signature',
                    'deposit_id': deposit_info.get('deposit_id')
                }
            
            deposit_id = deposit_info['deposit_id']
            
            # 2. Verify deposit exists and is valid
            if not await self.vault_manager.verify_deposit(user_address, deposit_id):
                return {
                    'success': False,
                    'error': 'Deposit not found or insufficient',
                    'deposit_id': deposit_id
                }
            
            # 3. Calculate TAO20 amount based on NAV at deposit time
            tao20_amount = await self.vault_manager.calculate_tao20_amount(deposit_id)
            
            # 4. Execute mint on blockchain
            success, transaction_hash = await self._execute_mint(
                deposit_id, tao20_amount, user_address
            )
            
            if success:
                # 5. Mark deposit as processed
                await self.vault_manager.mark_deposit_minted(deposit_id, transaction_hash)
                
                return {
                    'success': True,
                    'deposit_id': deposit_id,
                    'tao20_amount': tao20_amount,
                    'transaction_hash': transaction_hash,
                    'nav_at_deposit': deposit_info['nav_at_deposit']
                }
            else:
                await self.vault_manager.mark_deposit_failed(
                    deposit_id, "Blockchain transaction failed"
                )
                
                return {
                    'success': False,
                    'error': 'Blockchain transaction failed',
                    'deposit_id': deposit_id
                }
                
        except Exception as e:
            logger.error(f"Error processing mint request for user {user_address}: {e}")
            
            deposit_id = deposit_info.get('deposit_id')
            if deposit_id:
                await self.vault_manager.mark_deposit_failed(deposit_id, str(e))
            
            return {
                'success': False,
                'error': str(e),
                'deposit_id': deposit_id
            }
    
    async def _execute_mint(
        self, 
        deposit_id: str, 
        tao20_amount: float, 
        user_address: str
    ) -> Tuple[bool, Optional[str]]:
        """Execute mint transaction on blockchain"""
        
        try:
            # Convert to wei
            amount_wei = int(tao20_amount * 1e18)
            
            # Get miner hotkey
            miner_hotkey = self.miner.hotkey.hotkey.public_key.hex()
            
            # Sign mint message
            signature, message = self.miner.sign_message(
                "MintTAO20",
                amount=amount_wei,
                caller_address=user_address,
                nonce=int(time.time())
            )
            
            # Build transaction
            transaction = self.contract.functions.mintInKind(
                amount_wei,
                miner_hotkey,
                signature,
                message
            ).build_transaction({
                'from': self.miner.account.address,
                'gas': 500000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.miner.account.address)
            })
            
            # Sign and send transaction
            signed_txn = self.miner.account.sign_transaction(transaction)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Wait for transaction receipt
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt.status == 1:
                logger.info(f"Mint transaction successful: {tx_hash.hex()}")
                return True, tx_hash.hex()
            else:
                logger.error(f"Mint transaction failed: {tx_hash.hex()}")
                return False, None
                
        except Exception as e:
            logger.error(f"Error executing mint transaction: {e}")
            return False, None
    
    async def process_batch_mints(self, mint_requests: List[Dict]) -> List[Dict]:
        """Process multiple mint requests in batch"""
        
        results = []
        
        for request in mint_requests:
            result = await self.process_mint_request(
                user_address=request['user_address'],
                deposit_info=request['deposit_info'],
                signature=request['signature'],
                message=request['message']
            )
            results.append(result)
        
        return results
    
    async def get_deposit_status(self, deposit_id: str) -> Optional[Dict]:
        """Get status of a specific deposit"""
        return self.vault_manager.get_deposit_status(deposit_id)
    
    async def get_user_deposits(self, user_address: str) -> List[Dict]:
        """Get all deposits for a specific user"""
        return self.vault_manager.get_user_deposits(user_address)
    
    async def get_vault_summary(self) -> Dict:
        """Get summary of vault state"""
        return self.vault_manager.get_vault_summary()
    
    async def track_new_deposit(
        self, 
        user_address: str, 
        netuid: int, 
        amount: float
    ) -> str:
        """Track a new deposit"""
        return await self.vault_manager.track_deposit(
            user_address=user_address,
            netuid=netuid,
            amount=amount
        )
    
    async def validate_deposit_batch(self, deposit_ids: List[str]) -> Tuple[List[str], List[str]]:
        """Validate a batch of deposits"""
        return await self.vault_manager.validate_deposit_batch(deposit_ids)
    
    async def cleanup_old_deposits(self, days_old: int = 30):
        """Clean up old completed deposits"""
        await self.vault_manager.cleanup_old_deposits(days_old)
