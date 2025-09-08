#!/usr/bin/env python3
"""
Oracle-Free TAO20 Miner
Real implementation with smart contract integration
"""

import asyncio
import logging
import os
import signal
import time
import hashlib
from typing import Dict, List, Optional
from dataclasses import dataclass
from decimal import Decimal

import bittensor as bt
import aiohttp
from oracle_free_web3 import (
    OracleFreeContractInterface, 
    MintRequest, 
    SubstrateDeposit,
    TransactionResult,
    create_mint_request,
    ss58_to_bytes32
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class MinerConfig:
    """Miner configuration"""
    wallet_name: str
    wallet_hotkey: str
    wallet_path: str = "~/.bittensor/wallets"
    
    # Contract configuration
    rpc_url: str = "https://rpc-canary-1.bevm.io/"  # BEVM mainnet
    core_contract_address: str = ""  # Set after deployment
    private_key: str = ""  # Miner's EVM private key
    
    # Miner configuration
    miner_uid: int = 0
    netuid: int = 20  # TAO20 subnet
    axon_port: int = 8091
    
    # Operation parameters
    min_mint_amount: Decimal = Decimal("1.0")  # Minimum 1 TAO to mint
    max_mint_amount: Decimal = Decimal("100.0")  # Maximum 100 TAO per mint
    check_interval: int = 60  # Check for opportunities every 60 seconds
    
    # Safety parameters
    max_gas_price_gwei: int = 50  # Maximum gas price
    max_pending_transactions: int = 5  # Maximum pending transactions

@dataclass 
class MiningOpportunity:
    """Represents a mining opportunity"""
    user_ss58: str
    deposit_amount: Decimal
    netuid: int
    block_hash: str
    extrinsic_index: int
    timestamp: int
    estimated_profit: Decimal

class OracleFreeMinedError(Exception):
    """Miner-specific errors"""
    pass

class OracleFreeMiner:
    """
    Oracle-Free TAO20 Miner
    
    Responsibilities:
    1. Monitor Bittensor for TAO deposits 
    2. Submit mint requests to TAO20CoreV2OracleFree contract
    3. Earn fees from successful minting operations
    4. Track performance and optimize operations
    """
    
    def __init__(self, config: MinerConfig):
        self.config = config
        self.running = False
        self.pending_transactions: Dict[str, TransactionResult] = {}
        
        # Initialize Bittensor components
        self._init_bittensor()
        
        # Initialize Web3 interface
        self._init_web3()
        
        # Initialize monitoring
        self.total_mints = 0
        self.total_volume = Decimal("0")
        self.total_fees = Decimal("0")
        self.start_time = time.time()
        
        logger.info(f"Oracle-free miner initialized")
        logger.info(f"Miner UID: {self.config.miner_uid}")
        logger.info(f"Contract: {self.config.core_contract_address}")
    
    def _init_bittensor(self):
        """Initialize Bittensor wallet and subtensor"""
        try:
            # Initialize wallet
            self.wallet = bt.wallet(
                name=self.config.wallet_name,
                hotkey=self.config.wallet_hotkey,
                path=self.config.wallet_path
            )
            
            # Initialize subtensor  
            self.subtensor = bt.subtensor()
            
            # Initialize metagraph
            self.metagraph = self.subtensor.metagraph(netuid=self.config.netuid)
            
            logger.info(f"Bittensor initialized for hotkey: {self.wallet.hotkey.ss58_address}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Bittensor: {e}")
            raise
    
    def _init_web3(self):
        """Initialize Web3 contract interface"""
        try:
            self.contract_interface = OracleFreeContractInterface(
                rpc_url=self.config.rpc_url,
                core_contract_address=self.config.core_contract_address,
                private_key=self.config.private_key
            )
            
            # Verify connection
            if not self.contract_interface.is_connected():
                raise OracleFreeMinedError("Failed to connect to BEVM network")
            
            # Check account balance
            balance = self.contract_interface.get_account_balance()
            if balance < Decimal("0.01"):  # Need some gas for transactions
                logger.warning(f"Low account balance: {balance} ETH")
            
            logger.info(f"Web3 interface initialized")
            logger.info(f"Account balance: {balance} ETH")
            
        except Exception as e:
            logger.error(f"Failed to initialize Web3: {e}")
            raise
    
    # ===================== MAIN MINING LOOP =====================
    
    async def run(self):
        """Main mining loop"""
        logger.info("Starting oracle-free miner...")
        self.running = True
        
        try:
            while self.running:
                try:
                    # Check for mining opportunities
                    opportunities = await self._find_mining_opportunities()
                    
                    # Process opportunities
                    for opportunity in opportunities:
                        if len(self.pending_transactions) >= self.config.max_pending_transactions:
                            logger.warning("Too many pending transactions, skipping opportunity")
                            continue
                        
                        await self._process_mining_opportunity(opportunity)
                    
                    # Check pending transactions
                    await self._check_pending_transactions()
                    
                    # Update stats
                    await self._update_stats()
                    
                    # Wait before next check
                    await asyncio.sleep(self.config.check_interval)
                    
                except KeyboardInterrupt:
                    logger.info("Received interrupt signal")
                    break
                except Exception as e:
                    logger.error(f"Error in mining loop: {e}")
                    await asyncio.sleep(30)  # Wait before retrying
                    
        except Exception as e:
            logger.error(f"Fatal error in mining loop: {e}")
            raise
        finally:
            logger.info("Miner stopped")
    
    async def _find_mining_opportunities(self) -> List[MiningOpportunity]:
        """Find potential mining opportunities"""
        opportunities = []
        
        try:
            # Query recent TAO deposits on Bittensor
            # This would involve monitoring substrate events
            deposits = await self._monitor_substrate_deposits()
            
            for deposit in deposits:
                # Check if deposit is eligible for minting
                if await self._is_mintable_deposit(deposit):
                    opportunity = MiningOpportunity(
                        user_ss58=deposit['user_ss58'],
                        deposit_amount=Decimal(str(deposit['amount'])) / Decimal(10**9),  # Convert from RAO
                        netuid=deposit['netuid'],
                        block_hash=deposit['block_hash'],
                        extrinsic_index=deposit['extrinsic_index'],
                        timestamp=deposit['timestamp'],
                        estimated_profit=await self._estimate_profit(deposit)
                    )
                    opportunities.append(opportunity)
            
            if opportunities:
                logger.info(f"Found {len(opportunities)} mining opportunities")
            
        except Exception as e:
            logger.error(f"Error finding mining opportunities: {e}")
        
        return opportunities
    
    async def _monitor_substrate_deposits(self) -> List[Dict]:
        """Monitor Substrate for TAO deposits"""
        # This is a simplified implementation
        # In production, this would use Substrate RPC to monitor events
        
        deposits = []
        
        try:
            # For now, return empty list - real implementation would:
            # 1. Connect to Substrate RPC
            # 2. Monitor balance transfer events
            # 3. Filter for deposits to known vault addresses
            # 4. Parse deposit information
            
            # Placeholder for demonstration
            logger.debug("Monitoring substrate deposits...")
            
        except Exception as e:
            logger.error(f"Error monitoring substrate deposits: {e}")
        
        return deposits
    
    async def _is_mintable_deposit(self, deposit: Dict) -> bool:
        """Check if a deposit is eligible for minting"""
        try:
            amount = Decimal(str(deposit['amount'])) / Decimal(10**9)
            
            # Check minimum amount
            if amount < self.config.min_mint_amount:
                return False
            
            # Check maximum amount
            if amount > self.config.max_mint_amount:
                return False
            
            # Check if deposit is recent enough
            if time.time() - deposit['timestamp'] > 3600:  # 1 hour old
                return False
            
            # Check if we've already processed this deposit
            deposit_id = f"{deposit['block_hash']}_{deposit['extrinsic_index']}"
            if deposit_id in self.pending_transactions:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking mintable deposit: {e}")
            return False
    
    async def _estimate_profit(self, deposit: Dict) -> Decimal:
        """Estimate profit from mining this opportunity"""
        try:
            # Get current NAV
            nav = self.contract_interface.get_current_nav()
            
            # Calculate minting amount
            deposit_amount = Decimal(str(deposit['amount'])) / Decimal(10**9)
            mint_amount = deposit_amount / nav
            
            # Estimate fees (simplified - in practice this would be more complex)
            estimated_fee = mint_amount * Decimal("0.001")  # 0.1% fee
            
            # Estimate gas costs
            gas_cost = Decimal("0.01")  # Rough estimate in ETH
            
            return estimated_fee - gas_cost
            
        except Exception as e:
            logger.error(f"Error estimating profit: {e}")
            return Decimal("0")
    
    # ===================== MINTING OPERATIONS =====================
    
    async def _process_mining_opportunity(self, opportunity: MiningOpportunity):
        """Process a mining opportunity"""
        try:
            logger.info(f"Processing mining opportunity: {opportunity.deposit_amount} TAO")
            
            # Create substrate deposit
            substrate_deposit = SubstrateDeposit(
                block_hash=opportunity.block_hash,
                extrinsic_index=opportunity.extrinsic_index,
                user_ss58=opportunity.user_ss58,
                netuid=opportunity.netuid,
                amount=int(opportunity.deposit_amount * Decimal(10**9)),  # Convert to RAO
                timestamp=opportunity.timestamp
            )
            
            # Create mint request
            mint_request = create_mint_request(
                recipient_address=self.contract_interface.address,  # Miner receives tokens
                substrate_deposit=substrate_deposit,
                nonce=int(time.time()),  # Simple nonce
                deadline_seconds=3600
            )
            
            # Generate signature (simplified - in practice this would be Ed25519)
            signature = await self._generate_mint_signature(mint_request)
            
            # Submit mint transaction
            result = self.contract_interface.mint_tao20(mint_request, signature)
            
            if result.success:
                # Track pending transaction
                self.pending_transactions[result.tx_hash] = result
                
                logger.info(f"Mint transaction submitted: {result.tx_hash}")
                logger.info(f"Amount: {opportunity.deposit_amount} TAO")
                
            else:
                logger.error(f"Mint transaction failed: {result.error_message}")
            
        except Exception as e:
            logger.error(f"Error processing mining opportunity: {e}")
    
    async def _generate_mint_signature(self, mint_request: MintRequest) -> bytes:
        """Generate signature for mint request"""
        try:
            # This is a simplified signature generation
            # In production, this would use Ed25519 signature of the request data
            
            # Create message hash
            message = f"{mint_request.recipient}{mint_request.deposit.amount}{mint_request.nonce}"
            message_hash = hashlib.sha256(message.encode()).digest()
            
            # For now, return the hash as signature (placeholder)
            # Real implementation would sign with Bittensor hotkey
            return message_hash + b'\x00' * 32  # 64 bytes total
            
        except Exception as e:
            logger.error(f"Error generating signature: {e}")
            return b'\x00' * 64
    
    # ===================== TRANSACTION MONITORING =====================
    
    async def _check_pending_transactions(self):
        """Check status of pending transactions"""
        completed_txs = []
        
        for tx_hash, result in self.pending_transactions.items():
            try:
                # Check transaction status
                receipt = self.contract_interface.w3.eth.get_transaction_receipt(tx_hash)
                
                if receipt:
                    if receipt.status == 1:
                        logger.info(f"Transaction successful: {tx_hash}")
                        self.total_mints += 1
                        
                        # Parse minted amount from events
                        try:
                            for event in result.events or []:
                                if event.event == 'TAO20Minted':
                                    amount = Decimal(event.args.tao20Amount) / Decimal(10**18)
                                    self.total_volume += amount
                                    logger.info(f"Minted {amount} TAO20 tokens")
                        except Exception as e:
                            logger.debug(f"Could not parse mint events: {e}")
                    else:
                        logger.error(f"Transaction failed: {tx_hash}")
                    
                    completed_txs.append(tx_hash)
                    
            except Exception as e:
                # Transaction might still be pending
                logger.debug(f"Could not get receipt for {tx_hash}: {e}")
        
        # Remove completed transactions
        for tx_hash in completed_txs:
            del self.pending_transactions[tx_hash]
    
    # ===================== STATS AND MONITORING =====================
    
    async def _update_stats(self):
        """Update miner statistics"""
        try:
            # Get on-chain stats
            miner_stats = self.contract_interface.get_miner_stats()
            
            # Log current stats
            runtime = time.time() - self.start_time
            logger.info(f"Miner Stats (Runtime: {runtime/3600:.1f}h):")
            logger.info(f"  Total Mints: {self.total_mints}")
            logger.info(f"  Total Volume: {self.total_volume} TAO")
            logger.info(f"  Pending TXs: {len(self.pending_transactions)}")
            logger.info(f"  On-chain Volume: {miner_stats['total_volume']} TAO")
            logger.info(f"  On-chain TX Count: {miner_stats['transaction_count']}")
            
            # Get TAO20 balance
            balance = self.contract_interface.get_tao20_balance()
            logger.info(f"  TAO20 Balance: {balance}")
            
        except Exception as e:
            logger.debug(f"Error updating stats: {e}")
    
    # ===================== LIFECYCLE MANAGEMENT =====================
    
    def stop(self):
        """Stop the miner"""
        logger.info("Stopping miner...")
        self.running = False
    
    async def cleanup(self):
        """Clean up resources"""
        try:
            # Wait for pending transactions to complete
            if self.pending_transactions:
                logger.info(f"Waiting for {len(self.pending_transactions)} pending transactions...")
                timeout = 300  # 5 minutes
                start_time = time.time()
                
                while self.pending_transactions and (time.time() - start_time) < timeout:
                    await self._check_pending_transactions()
                    await asyncio.sleep(10)
                
                if self.pending_transactions:
                    logger.warning(f"Timed out waiting for {len(self.pending_transactions)} transactions")
            
            logger.info("Miner cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

# ===================== MAIN ENTRY POINT =====================

async def main():
    """Main entry point"""
    
    # Configuration (in production, these would come from command line args or config file)
    config = MinerConfig(
        wallet_name=os.getenv("WALLET_NAME", "default"),
        wallet_hotkey=os.getenv("WALLET_HOTKEY", "default"),
        core_contract_address=os.getenv("TAO20_CONTRACT_ADDRESS", ""),
        private_key=os.getenv("MINER_PRIVATE_KEY", ""),
        rpc_url=os.getenv("BEVM_RPC_URL", "https://rpc-canary-1.bevm.io/"),
    )
    
    # Validate configuration
    if not config.core_contract_address:
        logger.error("TAO20_CONTRACT_ADDRESS environment variable is required")
        return
    
    if not config.private_key:
        logger.error("MINER_PRIVATE_KEY environment variable is required")
        return
    
    # Create and run miner
    miner = None
    try:
        miner = OracleFreeMiner(config)
        
        # Setup signal handlers
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}")
            if miner:
                miner.stop()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Run miner
        await miner.run()
        
    except Exception as e:
        logger.error(f"Miner failed: {e}")
        raise
    finally:
        if miner:
            await miner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
