#!/usr/bin/env python3
"""
Simple TAO20 Miner
Only handles mint and redeem requests - no complex strategies
"""

import asyncio
import logging
import os
import time
from typing import Dict, Optional
from dataclasses import dataclass
from decimal import Decimal

import bittensor as bt
from web3 import Web3
from eth_account import Account
from local_contract_interface import LocalTAO20Interface, LocalTestConfig, SubnetDeposit

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class MinerConfig:
    """Simple miner configuration"""
    wallet_name: str
    wallet_hotkey: str
    wallet_path: str = "~/.bittensor/wallets"
    
    # Contract configuration
    rpc_url: str = "https://rpc-canary-1.bevm.io/"
    tao20_contract_address: str = ""
    evm_private_key: str = ""
    
    # Miner settings
    netuid: int = 20
    check_interval: int = 30  # Check for requests every 30 seconds

@dataclass
class MintRequest:
    """User mint request"""
    user_ss58: str           # User's Bittensor address
    user_evm: str           # User's EVM address  
    subnet_amounts: Dict[int, Decimal]  # netuid -> amount
    vault_tx_hash: str      # Transaction hash of deposit to vault
    timestamp: int          # Request timestamp

@dataclass
class RedeemRequest:
    """User redeem request"""
    user_evm: str           # User's EVM address
    tao20_amount: Decimal   # Amount of TAO20 to redeem
    target_composition: Dict[int, Decimal]  # Desired subnet token amounts
    timestamp: int

class SimpleTAO20Miner:
    """
    Simple TAO20 Miner
    
    Responsibilities:
    1. Process mint requests (verify vault deposits, mint TAO20)
    2. Process redeem requests (burn TAO20, release subnet tokens)
    3. Earn fees from successful operations
    
    NOT responsible for:
    - Finding opportunities
    - NAV calculations  
    - Consensus mechanisms
    - Complex strategies
    """
    
    def __init__(self, config: MinerConfig):
        self.config = config
        self.running = False
        
        # Initialize Bittensor
        self.wallet = bt.wallet(
            name=config.wallet_name,
            hotkey=config.wallet_hotkey,
            path=config.wallet_path
        )
        self.subtensor = bt.subtensor()
        
        # Initialize local contract interface
        local_config = LocalTestConfig(rpc_url=config.rpc_url)
        self.contract_interface = LocalTAO20Interface(local_config)
        
        # Use first test account as miner
        self.account = self.contract_interface.miner1
        
        # Performance tracking
        self.total_mints = 0
        self.total_redeems = 0
        self.total_fees_earned = Decimal("0")
        
        logger.info(f"Simple TAO20 Miner initialized")
        logger.info(f"Bittensor address: {self.wallet.hotkey.ss58_address}")
        logger.info(f"EVM address: {self.account.address}")
    
    def _init_contract(self):
        """Initialize TAO20 contract interface"""
        # Minimal ABI for mint/redeem operations
        minimal_abi = [
            {
                "inputs": [
                    {"name": "user", "type": "address"},
                    {"name": "amounts", "type": "uint256[]"},
                    {"name": "proof", "type": "bytes"}
                ],
                "name": "mintTAO20",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [
                    {"name": "amount", "type": "uint256"},
                    {"name": "targetAmounts", "type": "uint256[]"}
                ],
                "name": "redeemTAO20", 
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]
        
        return self.w3.eth.contract(
            address=self.config.tao20_contract_address,
            abi=minimal_abi
        )
    
    # ===================== MAIN MINER LOOP =====================
    
    async def run(self):
        """Main miner loop - simple and focused"""
        logger.info("Starting simple TAO20 miner...")
        self.running = True
        
        while self.running:
            try:
                # Check for pending mint requests
                mint_requests = await self._get_pending_mint_requests()
                for request in mint_requests:
                    await self._process_mint_request(request)
                
                # Check for pending redeem requests  
                redeem_requests = await self._get_pending_redeem_requests()
                for request in redeem_requests:
                    await self._process_redeem_request(request)
                
                # Wait before next check
                await asyncio.sleep(self.config.check_interval)
                
            except KeyboardInterrupt:
                logger.info("Miner interrupted")
                break
            except Exception as e:
                logger.error(f"Error in miner loop: {e}")
                await asyncio.sleep(60)  # Wait longer on error
        
        logger.info("Miner stopped")
    
    # ===================== MINT PROCESSING =====================
    
    async def _get_pending_mint_requests(self) -> list[MintRequest]:
        """Get pending mint requests from users"""
        try:
            # In practice, this would:
            # 1. Monitor a request queue (API, database, or on-chain events)
            # 2. Check for new substrate vault deposits
            # 3. Match deposits to mint requests
            
            # For now, return empty list (placeholder)
            # Real implementation would fetch from request system
            return []
            
        except Exception as e:
            logger.error(f"Error getting mint requests: {e}")
            return []
    
    async def _process_mint_request(self, request: MintRequest) -> bool:
        """Process a mint request"""
        try:
            logger.info(f"Processing mint request for {request.user_evm}")
            
            # Step 1: Verify vault deposit
            if not await self._verify_vault_deposit(request):
                logger.warning(f"Vault deposit verification failed for {request.user_evm}")
                return False
            
            # Step 2: Verify wallet ownership
            if not await self._verify_wallet_ownership(request):
                logger.warning(f"Wallet ownership verification failed for {request.user_evm}")
                return False
            
            # Step 3: Calculate TAO20 amount to mint
            tao20_amount = await self._calculate_mint_amount(request.subnet_amounts)
            
            # Step 4: Execute mint transaction
            success = await self._execute_mint(request.user_evm, tao20_amount, request)
            
            if success:
                self.total_mints += 1
                self.total_fees_earned += tao20_amount * Decimal("0.001")  # 0.1% fee
                logger.info(f"Successfully minted {tao20_amount} TAO20 for {request.user_evm}")
                return True
            else:
                logger.error(f"Failed to mint for {request.user_evm}")
                return False
                
        except Exception as e:
            logger.error(f"Error processing mint request: {e}")
            return False
    
    async def _verify_vault_deposit(self, request: MintRequest) -> bool:
        """Verify user deposited subnet tokens to vault"""
        try:
            # Check that the vault transaction exists and contains correct amounts
            # This would use Substrate RPC to verify the transaction
            
            logger.debug(f"Verifying vault deposit: {request.vault_tx_hash}")
            
            # Placeholder verification - real implementation would:
            # 1. Query Substrate RPC for transaction details
            # 2. Verify amounts match request.subnet_amounts
            # 3. Verify destination is correct vault address
            # 4. Verify transaction is confirmed
            
            return True  # Placeholder
            
        except Exception as e:
            logger.error(f"Error verifying vault deposit: {e}")
            return False
    
    async def _verify_wallet_ownership(self, request: MintRequest) -> bool:
        """Verify user owns both Bittensor and EVM wallets"""
        try:
            # Verify that the user can prove ownership of both wallets
            # This could involve signature verification
            
            logger.debug(f"Verifying wallet ownership for {request.user_ss58} -> {request.user_evm}")
            
            # Placeholder verification - real implementation would:
            # 1. Check if user signed a message with both keys
            # 2. Verify the signatures match expected addresses
            # 3. Ensure request is recent (anti-replay)
            
            return True  # Placeholder
            
        except Exception as e:
            logger.error(f"Error verifying wallet ownership: {e}")
            return False
    
    async def _calculate_mint_amount(self, subnet_amounts: Dict[int, Decimal]) -> Decimal:
        """Calculate TAO20 amount to mint based on subnet token deposits"""
        try:
            # Calculate based on current NAV and subnet token values
            # This is where the current weightings are applied
            
            total_value = Decimal("0")
            
            for netuid, amount in subnet_amounts.items():
                # Get current subnet token price (this would be from price oracle)
                token_price = await self._get_subnet_token_price(netuid)
                total_value += amount * token_price
            
            # Get current TAO20 NAV
            current_nav = await self._get_current_nav()
            
            # TAO20 amount = total_value / nav
            tao20_amount = total_value / current_nav
            
            logger.debug(f"Calculated mint amount: {tao20_amount} TAO20")
            return tao20_amount
            
        except Exception as e:
            logger.error(f"Error calculating mint amount: {e}")
            return Decimal("0")
    
    async def _execute_mint(self, user_address: str, amount: Decimal, request: MintRequest) -> bool:
        """Execute the mint transaction"""
        try:
            # Convert to wei
            amount_wei = int(amount * Decimal(10**18))
            
            # Create proof of deposit (simplified)
            proof = self._create_deposit_proof(request)
            
            # Build transaction
            function_call = self.tao20_contract.functions.mintTAO20(
                user_address,
                [int(amt * Decimal(10**18)) for amt in request.subnet_amounts.values()],
                proof
            )
            
            # Execute transaction
            tx_hash = await self._send_transaction(function_call)
            
            if tx_hash:
                logger.info(f"Mint transaction sent: {tx_hash.hex()}")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Error executing mint: {e}")
            return False
    
    # ===================== REDEEM PROCESSING =====================
    
    async def _get_pending_redeem_requests(self) -> list[RedeemRequest]:
        """Get pending redeem requests from users"""
        try:
            # In practice, this would monitor for TAO20 burn events
            # or check a request queue
            return []  # Placeholder
            
        except Exception as e:
            logger.error(f"Error getting redeem requests: {e}")
            return []
    
    async def _process_redeem_request(self, request: RedeemRequest) -> bool:
        """Process a redeem request"""
        try:
            logger.info(f"Processing redeem request for {request.user_evm}")
            
            # Step 1: Verify user has sufficient TAO20 balance
            if not await self._verify_tao20_balance(request):
                logger.warning(f"Insufficient TAO20 balance for {request.user_evm}")
                return False
            
            # Step 2: Calculate subnet tokens to release
            subnet_amounts = await self._calculate_redeem_amounts(request)
            
            # Step 3: Execute redeem transaction
            success = await self._execute_redeem(request.user_evm, request.tao20_amount, subnet_amounts)
            
            if success:
                self.total_redeems += 1
                self.total_fees_earned += request.tao20_amount * Decimal("0.001")  # 0.1% fee
                logger.info(f"Successfully redeemed {request.tao20_amount} TAO20 for {request.user_evm}")
                return True
            else:
                logger.error(f"Failed to redeem for {request.user_evm}")
                return False
                
        except Exception as e:
            logger.error(f"Error processing redeem request: {e}")
            return False
    
    async def _execute_redeem(self, user_address: str, tao20_amount: Decimal, subnet_amounts: Dict[int, Decimal]) -> bool:
        """Execute the redeem transaction"""
        try:
            # Convert amounts to wei
            tao20_wei = int(tao20_amount * Decimal(10**18))
            subnet_wei = [int(amt * Decimal(10**18)) for amt in subnet_amounts.values()]
            
            # Build transaction
            function_call = self.tao20_contract.functions.redeemTAO20(
                tao20_wei,
                subnet_wei
            )
            
            # Execute transaction
            tx_hash = await self._send_transaction(function_call)
            
            if tx_hash:
                logger.info(f"Redeem transaction sent: {tx_hash.hex()}")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Error executing redeem: {e}")
            return False
    
    # ===================== UTILITY FUNCTIONS =====================
    
    async def _get_subnet_token_price(self, netuid: int) -> Decimal:
        """Get current price of subnet token"""
        # This would fetch from price oracle or DEX
        # For now, return placeholder
        return Decimal("1.0")  # Placeholder
    
    async def _get_current_nav(self) -> Decimal:
        """Get current TAO20 NAV"""
        # This would be calculated automatically from subnet token values
        # No validator consensus needed
        return Decimal("1.0")  # Placeholder
    
    def _create_deposit_proof(self, request: MintRequest) -> bytes:
        """Create proof of substrate deposit"""
        # This would create cryptographic proof of the deposit
        # For now, return placeholder
        return b"proof_placeholder"
    
    async def _send_transaction(self, function_call) -> Optional[bytes]:
        """Send transaction to blockchain"""
        try:
            # Build transaction
            transaction = function_call.build_transaction({
                'from': self.account.address,
                'gas': 500000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
            })
            
            # Sign and send
            signed_txn = self.account.sign_transaction(transaction)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            return tx_hash
            
        except Exception as e:
            logger.error(f"Error sending transaction: {e}")
            return None
    
    async def _verify_tao20_balance(self, request: RedeemRequest) -> bool:
        """Verify user has sufficient TAO20 balance"""
        # Would check TAO20 contract balance
        return True  # Placeholder
    
    async def _calculate_redeem_amounts(self, request: RedeemRequest) -> Dict[int, Decimal]:
        """Calculate subnet token amounts to release"""
        # Calculate based on current weightings and user preference
        return request.target_composition  # Placeholder
    
    def get_stats(self) -> Dict[str, any]:
        """Get miner performance statistics"""
        return {
            "total_mints": self.total_mints,
            "total_redeems": self.total_redeems,
            "total_fees_earned": str(self.total_fees_earned),
            "uptime": time.time() - self.start_time if hasattr(self, 'start_time') else 0,
            "success_rate": "calculated_dynamically"  # Would track success/failure rates
        }
    
    def stop(self):
        """Stop the miner"""
        self.running = False
        logger.info("Miner stop requested")

# ===================== MAIN ENTRY POINT =====================

async def main():
    """Main entry point for simple miner"""
    
    config = MinerConfig(
        wallet_name=os.getenv("WALLET_NAME", "default"),
        wallet_hotkey=os.getenv("WALLET_HOTKEY", "default"),
        tao20_contract_address=os.getenv("TAO20_CONTRACT_ADDRESS", ""),
        evm_private_key=os.getenv("EVM_PRIVATE_KEY", ""),
    )
    
    if not config.tao20_contract_address:
        logger.error("TAO20_CONTRACT_ADDRESS environment variable required")
        return
    
    if not config.evm_private_key:
        logger.error("EVM_PRIVATE_KEY environment variable required") 
        return
    
    # Create and run miner
    miner = SimpleTAO20Miner(config)
    
    try:
        await miner.run()
    except KeyboardInterrupt:
        logger.info("Miner interrupted by user")
    finally:
        miner.stop()

if __name__ == "__main__":
    asyncio.run(main())
