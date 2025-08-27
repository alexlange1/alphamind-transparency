#!/usr/bin/env python3
"""
Enhanced TAO20 Validator
Monitors deposits and provides attestations for the enhanced minting system
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Set
from dataclasses import asdict
import json

import bittensor as bt
from web3 import Web3

from ..vault.enhanced_vault_manager import EnhancedSubstrateVaultManager, MintClaim
from ..miner.tao20_miner import TAO20Miner

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnhancedTAO20Validator:
    """
    Enhanced validator that monitors deposits and provides attestations
    """
    
    def __init__(
        self,
        wallet_path: str,
        hotkey_path: str,
        contract_address: str,
        rpc_url: str,
        vault_ss58: str,
        subnet_uid: int = 21,
        validator_id: str = "enhanced_tao20_validator",
        required_attestations: int = 2,
        total_validators: int = 3
    ):
        self.wallet_path = wallet_path
        self.hotkey_path = hotkey_path
        self.contract_address = contract_address
        self.rpc_url = rpc_url
        self.vault_ss58 = vault_ss58
        self.subnet_uid = subnet_uid
        self.validator_id = validator_id
        self.required_attestations = required_attestations
        self.total_validators = total_validators
        
        # Initialize components
        self.wallet = bt.wallet(path=wallet_path)
        self.hotkey = bt.wallet(path=hotkey_path)
        
        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        
        # Load contract ABI
        self.contract_abi = self._load_contract_abi()
        self.contract = self.w3.eth.contract(
            address=contract_address,
            abi=self.contract_abi
        )
        
        # Initialize vault manager
        self.vault_manager = EnhancedSubstrateVaultManager(
            vault_ss58=vault_ss58,
            required_attestations=required_attestations,
            total_validators=total_validators
        )
        
        # State tracking
        self.attested_deposits: Set[str] = set()
        self.last_attestation_time = 0
        self.attestation_interval = 60  # seconds
        
        # Initialize Bittensor connection
        self.subtensor = bt.subtensor(network="finney")
        
        logger.info(f"Enhanced TAO20 Validator initialized: {validator_id}")
    
    def _load_contract_abi(self) -> List[Dict]:
        """Load the enhanced TAO20 contract ABI"""
        return [
            {
                "inputs": [
                    {"name": "depositId", "type": "string"},
                    {"name": "userEvm", "type": "address"},
                    {"name": "userSs58", "type": "bytes32"},
                    {"name": "netuid", "type": "uint256"},
                    {"name": "amount", "type": "uint256"},
                    {"name": "blockHash", "type": "bytes32"},
                    {"name": "extrinsicIndex", "type": "uint256"},
                    {"name": "navAtDeposit", "type": "uint256"}
                ],
                "name": "recordDeposit",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [
                    {"name": "depositId", "type": "string"},
                    {"name": "validatorHotkey", "type": "bytes32"}
                ],
                "name": "attestDeposit",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [
                    {"name": "depositId", "type": "string"},
                    {"name": "claimerEvm", "type": "address"},
                    {"name": "ss58Pubkey", "type": "bytes32"},
                    {"name": "amount", "type": "uint256"},
                    {"name": "nonce", "type": "uint256"},
                    {"name": "expiry", "type": "uint256"},
                    {"name": "chainId", "type": "string"},
                    {"name": "domain", "type": "string"},
                    {"name": "signature", "type": "bytes"}
                ],
                "name": "submitMintClaim",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [{"name": "depositId", "type": "string"}],
                "name": "getDepositAttestations",
                "outputs": [{"name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [
                    {"name": "depositId", "type": "string"},
                    {"name": "validatorHotkey", "type": "bytes32"}
                ],
                "name": "isAttestedByValidator",
                "outputs": [{"name": "", "type": "bool"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [{"name": "depositId", "type": "string"}],
                "name": "getDelayedMintStatus",
                "outputs": [
                    {"name": "claimerEvm", "type": "address"},
                    {"name": "tao20Amount", "type": "uint256"},
                    {"name": "executionNAV", "type": "uint256"},
                    {"name": "timestamp", "type": "uint256"},
                    {"name": "executed", "type": "bool"}
                ],
                "stateMutability": "view",
                "type": "function"
            }
        ]
    
    async def monitor_deposits(self, interval: int = 30):
        """Monitor for new deposits and record them"""
        
        logger.info("Starting deposit monitoring")
        
        while True:
            try:
                # Monitor for new deposits to the vault
                await self._check_for_new_deposits()
                
                # Provide attestations for recorded deposits
                await self._provide_attestations()
                
                # Monitor mint claims
                await self._monitor_mint_claims()
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"Error in deposit monitoring: {e}")
                await asyncio.sleep(interval)
    
    async def _check_for_new_deposits(self):
        """Check for new deposits to the vault"""
        
        try:
            # Get recent blocks and check for transfers to vault
            # This would integrate with Bittensor's blockchain monitoring
            # For now, we'll simulate finding new deposits
            
            # Simulate finding a new deposit
            # In production, this would:
            # 1. Monitor recent blocks for transfer events
            # 2. Filter for transfers to the vault SS58
            # 3. Extract deposit information
            
            pass
            
        except Exception as e:
            logger.error(f"Error checking for new deposits: {e}")
    
    async def _record_deposit_on_contract(
        self,
        deposit_id: str,
        user_evm: str,
        user_ss58: str,
        netuid: int,
        amount: float,
        block_hash: str,
        extrinsic_index: int,
        nav_at_deposit: float
    ):
        """Record a deposit on the smart contract"""
        
        try:
            # Convert parameters to contract format
            amount_wei = int(amount * 1e18)
            nav_wei = int(nav_at_deposit * 1e18)
            user_ss58_bytes = self._ss58_to_bytes32(user_ss58)
            block_hash_bytes = self._hex_to_bytes32(block_hash)
            
            # Build transaction
            transaction = self.contract.functions.recordDeposit(
                deposit_id,
                user_evm,
                user_ss58_bytes,
                netuid,
                amount_wei,
                block_hash_bytes,
                extrinsic_index,
                nav_wei
            ).build_transaction({
                'from': self.wallet.account.address,
                'gas': 500000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.wallet.account.address)
            })
            
            # Sign and send transaction
            signed_txn = self.wallet.account.sign_transaction(transaction)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Wait for transaction receipt
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt.status == 1:
                logger.info(f"Deposit recorded on contract: {deposit_id}")
                return True
            else:
                logger.error(f"Failed to record deposit on contract: {deposit_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error recording deposit on contract: {e}")
            return False
    
    async def _provide_attestations(self):
        """Provide attestations for deposits that need them"""
        
        try:
            # Check if enough time has passed since last attestation
            current_time = time.time()
            if current_time - self.last_attestation_time < self.attestation_interval:
                return
            
            # Get deposits pending attestation
            pending_deposits = self.vault_manager.get_pending_attestations()
            
            for deposit in pending_deposits:
                deposit_id = deposit['deposit_id']
                
                # Check if we already attested to this deposit
                if deposit_id in self.attested_deposits:
                    continue
                
                # Check if we should attest (simulate validator logic)
                if await self._should_attest_deposit(deposit):
                    await self._attest_deposit(deposit_id)
                    self.attested_deposits.add(deposit_id)
            
            self.last_attestation_time = current_time
            
        except Exception as e:
            logger.error(f"Error providing attestations: {e}")
    
    async def _should_attest_deposit(self, deposit: Dict) -> bool:
        """Determine if we should attest to a deposit"""
        
        try:
            # In production, this would include:
            # 1. Verify the deposit actually exists on-chain
            # 2. Check if the amount matches what was transferred
            # 3. Verify the block hash and extrinsic index
            # 4. Validate the NAV calculation
            
            # For now, we'll simulate the validation
            # Simulate 90% success rate for testing
            import random
            return random.random() < 0.9
            
        except Exception as e:
            logger.error(f"Error determining attestation: {e}")
            return False
    
    async def _attest_deposit(self, deposit_id: str):
        """Attest to a deposit on the smart contract"""
        
        try:
            # Get validator hotkey
            validator_hotkey = self.hotkey.hotkey.public_key.hex()
            validator_hotkey_bytes = self._hex_to_bytes32(validator_hotkey)
            
            # Build transaction
            transaction = self.contract.functions.attestDeposit(
                deposit_id,
                validator_hotkey_bytes
            ).build_transaction({
                'from': self.wallet.account.address,
                'gas': 200000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.wallet.account.address)
            })
            
            # Sign and send transaction
            signed_txn = self.wallet.account.sign_transaction(transaction)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Wait for transaction receipt
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt.status == 1:
                logger.info(f"Attestation submitted for deposit: {deposit_id}")
                
                # Update local vault manager
                await self.vault_manager.attest_deposit(deposit_id, validator_hotkey)
                
                return True
            else:
                logger.error(f"Failed to attest deposit: {deposit_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error attesting deposit: {e}")
            return False
    
    async def _monitor_mint_claims(self):
        """Monitor mint claims and their execution"""
        
        try:
            # Get attested deposits that are ready for minting
            attested_deposits = self.vault_manager.get_attested_deposits()
            
            for deposit in attested_deposits:
                deposit_id = deposit['deposit_id']
                
                # Check if mint claim has been submitted
                mint_status = await self._get_mint_claim_status(deposit_id)
                
                if mint_status and not mint_status['executed']:
                    logger.info(f"Mint claim pending for deposit: {deposit_id}")
                    
                    # Check if it's time to execute
                    if await self._should_execute_mint_claim(deposit_id):
                        await self._execute_mint_claim(deposit_id)
            
        except Exception as e:
            logger.error(f"Error monitoring mint claims: {e}")
    
    async def _get_mint_claim_status(self, deposit_id: str) -> Optional[Dict]:
        """Get mint claim status from contract"""
        
        try:
            result = self.contract.functions.getDelayedMintStatus(deposit_id).call()
            
            return {
                'claimer_evm': result[0],
                'tao20_amount': result[1],
                'execution_nav': result[2],
                'timestamp': result[3],
                'executed': result[4]
            }
            
        except Exception as e:
            logger.error(f"Error getting mint claim status: {e}")
            return None
    
    async def _should_execute_mint_claim(self, deposit_id: str) -> bool:
        """Determine if a mint claim should be executed"""
        
        try:
            # Check if we're an authorized keeper
            # In production, this would check the contract's keeper authorization
            
            # Check if enough time has passed
            mint_status = await self._get_mint_claim_status(deposit_id)
            if not mint_status:
                return False
            
            current_time = int(time.time())
            execution_time = mint_status['timestamp']
            
            # Execute if past the minimum delay
            return current_time >= execution_time
            
        except Exception as e:
            logger.error(f"Error checking mint claim execution: {e}")
            return False
    
    async def _execute_mint_claim(self, deposit_id: str):
        """Execute a mint claim (if authorized as keeper)"""
        
        try:
            # This would call the executeDelayedMint function on the contract
            # For now, we'll just log the execution
            
            logger.info(f"Would execute mint claim for deposit: {deposit_id}")
            
            # In production:
            # transaction = self.contract.functions.executeDelayedMint(deposit_id).build_transaction(...)
            # signed_txn = self.wallet.account.sign_transaction(transaction)
            # tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
        except Exception as e:
            logger.error(f"Error executing mint claim: {e}")
    
    async def get_attestation_stats(self) -> Dict:
        """Get attestation statistics"""
        
        try:
            total_deposits = len(self.vault_manager.deposits)
            pending_attestations = len(self.vault_manager.get_pending_attestations())
            attested_deposits = len(self.vault_manager.get_attested_deposits())
            
            return {
                'total_deposits': total_deposits,
                'pending_attestations': pending_attestations,
                'attested_deposits': attested_deposits,
                'attestations_provided': len(self.attested_deposits),
                'required_attestations': self.required_attestations,
                'total_validators': self.total_validators
            }
            
        except Exception as e:
            logger.error(f"Error getting attestation stats: {e}")
            return {}
    
    def _ss58_to_bytes32(self, ss58_address: str) -> bytes:
        """Convert SS58 address to bytes32"""
        # This would use proper SS58 decoding
        # For now, we'll use a simple hash
        import hashlib
        return hashlib.sha256(ss58_address.encode()).digest()
    
    def _hex_to_bytes32(self, hex_string: str) -> bytes:
        """Convert hex string to bytes32"""
        if hex_string.startswith('0x'):
            hex_string = hex_string[2:]
        return bytes.fromhex(hex_string.ljust(64, '0')[:64])
    
    async def run(self):
        """Main validator loop"""
        
        logger.info("Starting Enhanced TAO20 Validator")
        
        # Start deposit monitoring
        monitor_task = asyncio.create_task(self.monitor_deposits())
        
        # Start vault manager monitoring
        vault_task = asyncio.create_task(self.vault_manager.monitor_deposits())
        
        try:
            # Run both tasks
            await asyncio.gather(monitor_task, vault_task)
            
        except KeyboardInterrupt:
            logger.info("Shutting down Enhanced TAO20 Validator")
            
        except Exception as e:
            logger.error(f"Error in validator main loop: {e}")
            
        finally:
            # Cancel tasks
            monitor_task.cancel()
            vault_task.cancel()
            
            try:
                await asyncio.gather(monitor_task, vault_task, return_exceptions=True)
            except asyncio.CancelledError:
                pass


if __name__ == "__main__":
    # Example usage
    validator = EnhancedTAO20Validator(
        wallet_path="/path/to/wallet",
        hotkey_path="/path/to/hotkey",
        contract_address="0x1234567890123456789012345678901234567890",
        rpc_url="http://127.0.0.1:9944",
        vault_ss58="your_vault_ss58_here"
    )
    
    asyncio.run(validator.run())
