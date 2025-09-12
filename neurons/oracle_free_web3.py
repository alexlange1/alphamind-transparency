#!/usr/bin/env python3
"""
Oracle-Free TAO20 Web3 Integration
Real smart contract interactions for the oracle-free TAO20 system
"""

import json
import logging
import os
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from decimal import Decimal

from web3 import Web3
from web3.contract import Contract
from eth_account import Account

# Optional import for production
try:
    import bittensor as bt
except ImportError:
    bt = None

logger = logging.getLogger(__name__)

@dataclass
class SubstrateDeposit:
    """Substrate deposit information"""
    block_hash: str
    extrinsic_index: int
    user_ss58: str
    netuid: int
    amount: int
    timestamp: int

@dataclass
class MintRequest:
    """Mint request for TAO20 tokens"""
    recipient: str  # EVM address
    deposit: SubstrateDeposit
    nonce: int
    deadline: int

@dataclass
class TransactionResult:
    """Result of a blockchain transaction"""
    success: bool
    tx_hash: Optional[str] = None
    block_number: Optional[int] = None
    gas_used: Optional[int] = None
    error_message: Optional[str] = None
    events: Optional[List[Dict]] = None

class OracleFreeContractInterface:
    """
    Web3 interface for oracle-free TAO20 contracts
    
    Provides real blockchain interactions with:
    - TAO20CoreV2OracleFree (main contract)
    - OracleFreeNAVCalculator (NAV calculations)
    - StakingManager (staking operations)
    - TAO20V2 (token contract)
    """
    
    def __init__(
        self,
        rpc_url: str,
        core_contract_address: str,
        private_key: str,
        chain_id: int = 11501  # BEVM mainnet
    ):
        """
        Initialize Web3 interface
        
        Args:
            rpc_url: BEVM RPC endpoint
            core_contract_address: TAO20CoreV2OracleFree contract address
            private_key: Account private key for transactions
            chain_id: BEVM chain ID
        """
        self.rpc_url = rpc_url
        self.core_address = Web3.to_checksum_address(core_contract_address)
        self.chain_id = chain_id
        
        # Initialize Web3 connection
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not self.w3.is_connected():
            raise RuntimeError(f"Failed to connect to BEVM at {rpc_url}")
        
        # Initialize account
        self.account = Account.from_key(private_key)
        self.address = self.account.address
        
        # Load contract ABIs and create contract instances
        self._load_contract_abis()
        self._create_contract_instances()
        
        logger.info(f"Oracle-free Web3 interface initialized")
        logger.info(f"Core contract: {self.core_address}")
        logger.info(f"Account: {self.address}")
        logger.info(f"Chain ID: {self.chain_id}")
    
    def _load_contract_abis(self):
        """Load contract ABIs from files or define minimal ABIs"""
        
        # TAO20CoreV2OracleFree minimal ABI
        self.core_abi = [
            {
                "inputs": [
                    {"name": "request", "type": "tuple", "components": [
                        {"name": "recipient", "type": "address"},
                        {"name": "deposit", "type": "tuple", "components": [
                            {"name": "blockHash", "type": "bytes32"},
                            {"name": "extrinsicIndex", "type": "uint32"},
                            {"name": "userSS58", "type": "bytes32"},
                            {"name": "netuid", "type": "uint16"},
                            {"name": "amount", "type": "uint256"},
                            {"name": "timestamp", "type": "uint256"}
                        ]},
                        {"name": "nonce", "type": "uint256"},
                        {"name": "deadline", "type": "uint256"}
                    ]},
                    {"name": "signature", "type": "bytes"}
                ],
                "name": "mintTAO20",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [{"name": "amount", "type": "uint256"}],
                "name": "redeemTAO20",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "getCurrentNAV",
                "outputs": [{"name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "updateNAV",
                "outputs": [{"name": "", "type": "uint256"}],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "tao20Token",
                "outputs": [{"name": "", "type": "address"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "stakingManager",
                "outputs": [{"name": "", "type": "address"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "navCalculator",
                "outputs": [{"name": "", "type": "address"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [{"name": "miner", "type": "address"}],
                "name": "getMinerStats",
                "outputs": [{"name": "", "type": "tuple", "components": [
                    {"name": "volumeStaked", "type": "uint256"},
                    {"name": "volumeRedeemed", "type": "uint256"},
                    {"name": "totalVolume", "type": "uint256"},
                    {"name": "transactionCount", "type": "uint256"},
                    {"name": "lastActivity", "type": "uint256"},
                    {"name": "currentEpochVolume", "type": "uint256"}
                ]}],
                "stateMutability": "view",
                "type": "function"
            }
        ]
        
        # TAO20V2 token ABI
        self.token_abi = [
            {
                "inputs": [{"name": "account", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "totalSupply",
                "outputs": [{"name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "authorizedMinter",
                "outputs": [{"name": "", "type": "address"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]
        
        # OracleFreeNAVCalculator ABI
        self.nav_calculator_abi = [
            {
                "inputs": [],
                "name": "getCurrentNAV",
                "outputs": [{"name": "", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "getPhaseInfo",
                "outputs": [
                    {"name": "isPhase2Active", "type": "bool"},
                    {"name": "currentNAV", "type": "uint256"},
                    {"name": "lastUpdate", "type": "uint256"},
                    {"name": "nextUpdateDue", "type": "uint256"}
                ],
                "stateMutability": "view",
                "type": "function"
            }
        ]
        
        # Events
        self.core_events = [
            {
                "anonymous": False,
                "inputs": [
                    {"indexed": True, "name": "recipient", "type": "address"},
                    {"indexed": True, "name": "miner", "type": "address"},
                    {"indexed": False, "name": "tao20Amount", "type": "uint256"},
                    {"indexed": False, "name": "depositAmount", "type": "uint256"},
                    {"indexed": True, "name": "netuid", "type": "uint16"},
                    {"indexed": False, "name": "nav", "type": "uint256"},
                    {"indexed": False, "name": "depositId", "type": "bytes32"}
                ],
                "name": "TAO20Minted",
                "type": "event"
            },
            {
                "anonymous": False,
                "inputs": [
                    {"indexed": True, "name": "user", "type": "address"},
                    {"indexed": True, "name": "miner", "type": "address"},
                    {"indexed": False, "name": "tao20Amount", "type": "uint256"},
                    {"indexed": False, "name": "totalValue", "type": "uint256"},
                    {"indexed": False, "name": "nav", "type": "uint256"}
                ],
                "name": "TAO20Redeemed",
                "type": "event"
            }
        ]
    
    def _create_contract_instances(self):
        """Create Web3 contract instances"""
        try:
            # Core contract
            self.core_contract = self.w3.eth.contract(
                address=self.core_address,
                abi=self.core_abi + self.core_events
            )
            
            # Get other contract addresses from core contract
            self.token_address = self.core_contract.functions.tao20Token().call()
            self.staking_manager_address = self.core_contract.functions.stakingManager().call()
            self.nav_calculator_address = self.core_contract.functions.navCalculator().call()
            
            # Create contract instances
            self.token_contract = self.w3.eth.contract(
                address=self.token_address,
                abi=self.token_abi
            )
            
            self.nav_calculator_contract = self.w3.eth.contract(
                address=self.nav_calculator_address,
                abi=self.nav_calculator_abi
            )
            
            logger.info(f"Contract instances created:")
            logger.info(f"  Token: {self.token_address}")
            logger.info(f"  Staking Manager: {self.staking_manager_address}")
            logger.info(f"  NAV Calculator: {self.nav_calculator_address}")
            
        except Exception as e:
            logger.error(f"Failed to create contract instances: {e}")
            raise
    
    # ===================== NAV OPERATIONS =====================
    
    def get_current_nav(self) -> Decimal:
        """Get current NAV from the calculator"""
        try:
            nav_raw = self.nav_calculator_contract.functions.getCurrentNAV().call()
            # Convert from 18 decimals to Decimal
            return Decimal(nav_raw) / Decimal(10**18)
        except Exception as e:
            logger.error(f"Failed to get current NAV: {e}")
            raise
    
    def get_phase_info(self) -> Dict[str, Any]:
        """Get phase information"""
        try:
            result = self.nav_calculator_contract.functions.getPhaseInfo().call()
            return {
                "is_phase2_active": result[0],
                "current_nav": Decimal(result[1]) / Decimal(10**18),
                "last_update": result[2],
                "next_update_due": result[3]
            }
        except Exception as e:
            logger.error(f"Failed to get phase info: {e}")
            raise
    
    def update_nav(self) -> TransactionResult:
        """Update NAV (only works if authorized)"""
        try:
            # Build transaction
            function_call = self.core_contract.functions.updateNAV()
            
            # Execute transaction
            return self._execute_transaction(function_call, "updateNAV")
            
        except Exception as e:
            logger.error(f"Failed to update NAV: {e}")
            return TransactionResult(success=False, error_message=str(e))
    
    # ===================== TOKEN OPERATIONS =====================
    
    def get_tao20_balance(self, address: Optional[str] = None) -> Decimal:
        """Get TAO20 token balance"""
        try:
            addr = address or self.address
            balance_raw = self.token_contract.functions.balanceOf(addr).call()
            return Decimal(balance_raw) / Decimal(10**18)
        except Exception as e:
            logger.error(f"Failed to get TAO20 balance: {e}")
            raise
    
    def get_total_supply(self) -> Decimal:
        """Get total TAO20 token supply"""
        try:
            supply_raw = self.token_contract.functions.totalSupply().call()
            return Decimal(supply_raw) / Decimal(10**18)
        except Exception as e:
            logger.error(f"Failed to get total supply: {e}")
            raise
    
    # ===================== MINTING OPERATIONS =====================
    
    def mint_tao20(self, mint_request: MintRequest, signature: bytes) -> TransactionResult:
        """
        Mint TAO20 tokens using a substrate deposit proof
        
        Args:
            mint_request: The mint request with deposit details
            signature: Ed25519 signature proving ownership
            
        Returns:
            TransactionResult with transaction details
        """
        try:
            # Convert MintRequest to contract format
            request_tuple = (
                mint_request.recipient,
                (
                    mint_request.deposit.block_hash.encode() if isinstance(mint_request.deposit.block_hash, str) else mint_request.deposit.block_hash,
                    mint_request.deposit.extrinsic_index,
                    mint_request.deposit.user_ss58.encode() if isinstance(mint_request.deposit.user_ss58, str) else mint_request.deposit.user_ss58,
                    mint_request.deposit.netuid,
                    mint_request.deposit.amount,
                    mint_request.deposit.timestamp
                ),
                mint_request.nonce,
                mint_request.deadline
            )
            
            # Build transaction
            function_call = self.core_contract.functions.mintTAO20(request_tuple, signature)
            
            # Execute transaction
            return self._execute_transaction(function_call, "mintTAO20")
            
        except Exception as e:
            logger.error(f"Failed to mint TAO20: {e}")
            return TransactionResult(success=False, error_message=str(e))
    
    def redeem_tao20(self, amount: Decimal) -> TransactionResult:
        """
        Redeem TAO20 tokens for underlying assets
        
        Args:
            amount: Amount of TAO20 tokens to redeem
            
        Returns:
            TransactionResult with transaction details
        """
        try:
            # Convert amount to wei (18 decimals)
            amount_wei = int(amount * Decimal(10**18))
            
            # Build transaction
            function_call = self.core_contract.functions.redeemTAO20(amount_wei)
            
            # Execute transaction
            return self._execute_transaction(function_call, "redeemTAO20")
            
        except Exception as e:
            logger.error(f"Failed to redeem TAO20: {e}")
            return TransactionResult(success=False, error_message=str(e))
    
    # ===================== MINER OPERATIONS =====================
    
    def get_miner_stats(self, miner_address: Optional[str] = None) -> Dict[str, Any]:
        """Get miner statistics"""
        try:
            addr = miner_address or self.address
            stats = self.core_contract.functions.getMinerStats(addr).call()
            
            return {
                "volume_staked": Decimal(stats[0]) / Decimal(10**18),
                "volume_redeemed": Decimal(stats[1]) / Decimal(10**18),
                "total_volume": Decimal(stats[2]) / Decimal(10**18),
                "transaction_count": stats[3],
                "last_activity": stats[4],
                "current_epoch_volume": Decimal(stats[5]) / Decimal(10**18)
            }
        except Exception as e:
            logger.error(f"Failed to get miner stats: {e}")
            raise
    
    # ===================== TRANSACTION UTILITIES =====================
    
    def _execute_transaction(self, function_call, function_name: str) -> TransactionResult:
        """Execute a contract transaction"""
        try:
            # Estimate gas
            gas_estimate = function_call.estimate_gas({'from': self.address})
            gas_limit = int(gas_estimate * 1.2)  # Add 20% buffer
            
            # Get current gas price
            gas_price = self.w3.eth.gas_price
            
            # Build transaction
            transaction = function_call.build_transaction({
                'from': self.address,
                'gas': gas_limit,
                'gasPrice': gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.address),
                'chainId': self.chain_id
            })
            
            # Sign transaction
            signed_txn = self.account.sign_transaction(transaction)
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            tx_hash_hex = tx_hash.hex()
            
            logger.info(f"Transaction {function_name} sent: {tx_hash_hex}")
            
            # Wait for confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            # Parse events
            events = []
            try:
                # Try to parse logs as events
                for log in receipt.logs:
                    try:
                        event = self.core_contract.events.TAO20Minted().process_log(log)
                        events.append(event)
                    except:
                        try:
                            event = self.core_contract.events.TAO20Redeemed().process_log(log)
                            events.append(event)
                        except:
                            pass
            except Exception as e:
                logger.debug(f"Could not parse events: {e}")
            
            success = receipt.status == 1
            
            if success:
                logger.info(f"Transaction {function_name} successful: {tx_hash_hex}")
            else:
                logger.error(f"Transaction {function_name} failed: {tx_hash_hex}")
            
            return TransactionResult(
                success=success,
                tx_hash=tx_hash_hex,
                block_number=receipt.blockNumber,
                gas_used=receipt.gasUsed,
                events=events
            )
            
        except Exception as e:
            logger.error(f"Transaction {function_name} failed: {e}")
            return TransactionResult(success=False, error_message=str(e))
    
    def get_account_balance(self) -> Decimal:
        """Get native token balance (for gas fees)"""
        try:
            balance_wei = self.w3.eth.get_balance(self.address)
            return Decimal(balance_wei) / Decimal(10**18)
        except Exception as e:
            logger.error(f"Failed to get account balance: {e}")
            raise
    
    def is_connected(self) -> bool:
        """Check if Web3 connection is active"""
        try:
            return self.w3.is_connected()
        except:
            return False

# ===================== UTILITY FUNCTIONS =====================

def create_mint_request(
    recipient_address: str,
    substrate_deposit: SubstrateDeposit,
    nonce: int,
    deadline_seconds: int = 3600
) -> MintRequest:
    """Create a mint request"""
    return MintRequest(
        recipient=recipient_address,
        deposit=substrate_deposit,
        nonce=nonce,
        deadline=int(time.time()) + deadline_seconds
    )

def ss58_to_bytes32(ss58_address: str) -> bytes:
    """Convert SS58 address to bytes32 for contract calls"""
    try:
        # This is a simplified conversion - in production, use proper SS58 decoding
        if ss58_address.startswith('5'):
            # Decode SS58 address to bytes
            import base58
            decoded = base58.b58decode(ss58_address)
            return decoded[1:33]  # Extract the 32-byte public key
        else:
            # If it's already hex, convert directly
            return bytes.fromhex(ss58_address.replace('0x', ''))
    except Exception as e:
        logger.error(f"Failed to convert SS58 to bytes32: {e}")
        raise

# ===================== TESTING UTILITIES =====================

async def test_oracle_free_integration():
    """Test the oracle-free Web3 integration"""
    
    # Configuration (these would come from environment in production)
    test_config = {
        'rpc_url': 'http://localhost:8545',  # Local test network
        'core_contract_address': '0x1234567890123456789012345678901234567890',  # Placeholder
        'private_key': '0x' + '0' * 64,  # Placeholder private key
    }
    
    try:
        # Initialize interface
        interface = OracleFreeContractInterface(
            rpc_url=test_config['rpc_url'],
            core_contract_address=test_config['core_contract_address'],
            private_key=test_config['private_key']
        )
        
        # Test basic connectivity
        logger.info(f"Connected: {interface.is_connected()}")
        logger.info(f"Account balance: {interface.get_account_balance()}")
        
        # Test NAV operations
        nav = interface.get_current_nav()
        logger.info(f"Current NAV: {nav}")
        
        phase_info = interface.get_phase_info()
        logger.info(f"Phase info: {phase_info}")
        
        # Test token operations
        balance = interface.get_tao20_balance()
        logger.info(f"TAO20 balance: {balance}")
        
        supply = interface.get_total_supply()
        logger.info(f"Total supply: {supply}")
        
        # Test miner stats
        stats = interface.get_miner_stats()
        logger.info(f"Miner stats: {stats}")
        
        logger.info("Oracle-free integration test completed successfully!")
        
    except Exception as e:
        logger.error(f"Oracle-free integration test failed: {e}")
        raise

if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_oracle_free_integration())
