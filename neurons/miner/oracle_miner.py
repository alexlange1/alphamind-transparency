#!/usr/bin/env python3
"""
TAO20 Oracle Miner Implementation

This miner generates transaction volume on the TAO20 oracle-free system by
executing mint and redeem operations. In the oracle architecture, miners are
rewarded based on the volume they generate, not on providing oracle data.

Key Features:
- Automated mint/redeem transaction generation
- Strategic volume optimization
- Real-time NAV monitoring
- Activity scheduling and pacing
- Performance tracking and reporting
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import json
import os
import sys

import bittensor as bt
from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_defunct

# Add the common module to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'common'))
from address_mapping import MinerAddressManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TransactionResult:
    """Result of a transaction attempt"""
    success: bool
    tx_hash: Optional[str]
    amount: int
    is_mint: bool
    timestamp: int
    gas_used: Optional[int]
    error: Optional[str] = None


@dataclass
class MinerPerformance:
    """Miner performance tracking"""
    total_volume: int = 0
    total_transactions: int = 0
    successful_transactions: int = 0
    failed_transactions: int = 0
    total_gas_used: int = 0
    epoch_volume: int = 0
    last_activity: int = 0
    current_rank: int = 0


class OracleMiner:
    """
    TAO20 Oracle Miner
    
    Generates transaction volume by executing mint and redeem operations
    on the oracle-free TAO20 system to earn rewards based on activity.
    """
    
    def __init__(
        self,
        wallet: bt.wallet,
        config: bt.config,
        subtensor: bt.subtensor,
        metagraph: bt.metagraph
    ):
        self.wallet = wallet
        self.config = config
        self.subtensor = subtensor
        self.metagraph = metagraph
        
        # Initialize address management
        self.address_manager = MinerAddressManager(wallet)
        self.miner_address = self.address_manager.get_mining_address()
        self.private_key = self.address_manager.get_private_key()
        
        # Contract configuration
        self.contract_address = config.oracle.contract_address
        self.web3_provider = config.oracle.web3_provider
        
        # Web3 setup
        self.w3 = Web3(Web3.HTTPProvider(self.web3_provider))
        self.contract = self._load_contract()
        
        # Miner configuration
        self.min_transaction_amount = config.oracle.get('min_transaction_amount', int(0.1 * 1e18))  # 0.1 TAO
        self.max_transaction_amount = config.oracle.get('max_transaction_amount', int(10 * 1e18))   # 10 TAO
        self.transaction_interval = config.oracle.get('transaction_interval', 120)  # 2 minutes
        self.volume_target_per_hour = config.oracle.get('volume_target_per_hour', int(100 * 1e18))  # 100 TAO/hour
        
        # Miner state
        self.performance = MinerPerformance()
        self.transaction_history: List[TransactionResult] = []
        
        # Strategy parameters
        self.mint_probability = 0.6  # 60% chance to mint vs redeem
        self.volume_burst_mode = False
        self.last_nav_check = 0
        
        logger.info(f"Oracle Miner initialized for contract: {self.contract_address}")
        logger.info(f"Miner EVM address: {self.miner_address}")
    
    def _load_contract(self):
        """Load TAO20 contract ABI and create contract instance"""
        try:
            # Load ABI from the contracts/abi directory
            abi_path = os.path.join(
                os.path.dirname(__file__), '..', '..', 'contracts', 'abi', 
                'TAO20CoreV2OracleFree.json'
            )
            
            with open(abi_path, 'r') as f:
                contract_abi = json.load(f)
            
            return self.w3.eth.contract(
                address=self.contract_address,
                abi=contract_abi
            )
        except Exception as e:
            logger.error(f"Failed to load contract ABI: {e}")
            raise
    
    async def run(self):
        """Main miner loop"""
        logger.info("Starting Oracle Miner...")
        
        # Initialize miner state
        await self._initialize_miner_state()
        
        # Main mining loop
        while True:
            try:
                # Check current performance
                await self._update_performance_metrics()
                
                # Decide on transaction strategy
                transaction_type, amount = self._decide_transaction_strategy()
                
                # Execute transaction
                if transaction_type == 'mint':
                    result = await self._execute_mint(amount)
                elif transaction_type == 'redeem':
                    result = await self._execute_redeem(amount)
                else:
                    # Wait period - no transaction
                    await asyncio.sleep(self.transaction_interval)
                    continue
                
                # Record transaction result
                self._record_transaction_result(result)
                
                # Log performance
                if self.performance.total_transactions % 10 == 0:
                    self._log_performance()
                
                # Wait for next transaction
                await asyncio.sleep(self.transaction_interval + random.randint(-30, 30))
                
            except Exception as e:
                logger.error(f"Error in miner loop: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _initialize_miner_state(self):
        """Initialize miner state from contract and wallet"""
        try:
            # Get miner stats from contract using EVM address
            try:
                stats = self.contract.functions.getMinerStats(self.miner_address).call()
                self.performance.total_volume = stats[2]  # total_volume
                self.performance.total_transactions = stats[3]  # transaction_count
                self.performance.last_activity = stats[4]  # last_activity
                self.performance.epoch_volume = stats[5]  # current_epoch_volume
                logger.info("Loaded existing miner stats from contract")
            except:
                # New miner - no existing stats
                logger.info("New miner - no existing stats found")
            
            # Get current balances
            current_balance = self._get_tao_balance()
            tao20_balance = self._get_tao20_balance()
            
            logger.info(f"Initialized miner: TAO={current_balance/1e18:.2f}, TAO20={tao20_balance/1e18:.2f}")
            
        except Exception as e:
            logger.error(f"Failed to initialize miner state: {e}")
            raise
    
    def _get_tao_balance(self) -> int:
        """Get current TAO balance from Bittensor precompile"""
        try:
            # Use Bittensor balance transfer precompile to check TAO balance
            from web3 import Web3
            
            # Balance transfer precompile address
            BALANCE_PRECOMPILE = "0x0000000000000000000000000000000000000800"
            
            # Create precompile contract instance
            balance_abi = [
                {
                    "type": "function",
                    "name": "balanceOf",
                    "inputs": [{"name": "account", "type": "address"}],
                    "outputs": [{"name": "", "type": "uint256"}],
                    "stateMutability": "view"
                }
            ]
            
            balance_contract = self.w3.eth.contract(
                address=BALANCE_PRECOMPILE,
                abi=balance_abi
            )
            
            # Get balance in TAO base units
            balance = balance_contract.functions.balanceOf(self.miner_address).call()
            return balance
            
        except Exception as e:
            logger.error(f"Error getting TAO balance: {e}")
            return 0
    
    def _get_tao20_balance(self) -> int:
        """Get current TAO20 balance"""
        try:
            # TAO20 is an ERC20 token, use standard balanceOf
            tao20_token_address = self.contract.functions.tao20Token().call()
            
            # Create ERC20 contract instance
            erc20_abi = [
                {
                    "type": "function",
                    "name": "balanceOf",
                    "inputs": [{"name": "account", "type": "address"}],
                    "outputs": [{"name": "", "type": "uint256"}],
                    "stateMutability": "view"
                }
            ]
            
            token_contract = self.w3.eth.contract(
                address=tao20_token_address,
                abi=erc20_abi
            )
            
            return token_contract.functions.balanceOf(self.miner_address).call()
            
        except Exception as e:
            logger.error(f"Error getting TAO20 balance: {e}")
            return 0
    
    async def _update_performance_metrics(self):
        """Update performance metrics and ranking"""
        try:
            # Get current NAV
            current_nav = self.contract.functions.getCurrentNAV().call()
            
            # Get system stats for ranking
            system_stats = self.contract.functions.getSystemStats().call()
            
            # Update balances
            self.current_balance = self._get_tao_balance()
            self.tao20_balance = self._get_tao20_balance()
            
            # Calculate success rate
            if self.performance.total_transactions > 0:
                success_rate = self.performance.successful_transactions / self.performance.total_transactions
            else:
                success_rate = 0.0
            
            # Log metrics periodically
            if int(time.time()) - self.last_nav_check > 300:  # Every 5 minutes
                logger.info(f"NAV: {current_nav/1e18:.4f}, Success Rate: {success_rate:.2%}")
                self.last_nav_check = int(time.time())
                
        except Exception as e:
            logger.error(f"Error updating performance metrics: {e}")
    
    def _decide_transaction_strategy(self) -> Tuple[str, int]:
        """Decide on next transaction type and amount"""
        try:
            # Check if we should pause (to avoid over-activity)
            if self._should_pause():
                return 'wait', 0
            
            # Get current balances
            current_balance = self._get_tao_balance()
            tao20_balance = self._get_tao20_balance()
            
            # Determine transaction type based on actual balances
            if tao20_balance == 0 and current_balance > self.min_transaction_amount:
                # Must mint first if we have TAO but no TAO20
                transaction_type = 'mint'
            elif current_balance < self.min_transaction_amount and tao20_balance > 0:
                # Must redeem if we're low on TAO but have TAO20
                transaction_type = 'redeem'
            elif current_balance > self.min_transaction_amount and tao20_balance > 0:
                # Can do either - choose based on strategy
                import random
                if random.random() < self.mint_probability:
                    transaction_type = 'mint'
                else:
                    transaction_type = 'redeem'
            else:
                # Can't do any transactions
                return 'wait', 0
            
            # Determine amount based on transaction type
            if transaction_type == 'mint':
                max_amount = min(self.max_transaction_amount, current_balance - int(0.01 * 1e18))  # Leave some for gas
                amount = min(max_amount, int((current_balance * 0.1)))  # Use 10% of balance
            else:  # redeem
                max_amount = min(self.max_transaction_amount, tao20_balance)
                amount = min(max_amount, int((tao20_balance * 0.1)))  # Use 10% of balance
            
            # Ensure minimum amount
            amount = max(amount, self.min_transaction_amount)
            
            return transaction_type, amount
            
        except Exception as e:
            logger.error(f"Error deciding transaction strategy: {e}")
            return 'wait', 0
    
    def _should_pause(self) -> bool:
        """Check if miner should pause activity"""
        current_time = int(time.time())
        
        # Pause if we've been very active recently
        recent_activity = len([
            tx for tx in self.transaction_history
            if current_time - tx.timestamp < 300  # Last 5 minutes
        ])
        
        if recent_activity > 10:  # More than 10 transactions in 5 minutes
            return True
        
        # Pause if success rate is too low
        if self.performance.total_transactions > 10:
            success_rate = self.performance.successful_transactions / self.performance.total_transactions
            if success_rate < 0.5:  # Less than 50% success
                return True
        
        return False
    
    async def _execute_mint(self, amount: int) -> TransactionResult:
        """Execute a real mint transaction"""
        try:
            start_time = int(time.time())
            
            logger.info(f"Executing mint: {amount/1e18:.4f} TAO")
            
            # Note: For minting, the user must first deposit TAO to the Substrate side
            # and then provide proof of that deposit. This is a simplified version
            # that assumes the deposit has already been made.
            
            # In a real implementation, you would:
            # 1. Make a TAO deposit on the Substrate side
            # 2. Get the deposit receipt (block hash, extrinsic index, etc.)
            # 3. Create proper Ed25519 signature proving ownership
            # 4. Call mintTAO20 with the deposit proof
            
            logger.warning("Mint operation requires prior TAO deposit on Substrate side")
            logger.warning("This is a placeholder - real implementation needs deposit proof")
            
            # For now, return a pending result indicating the process needs completion
            result = TransactionResult(
                success=False,
                tx_hash=None,
                amount=amount,
                is_mint=True,
                timestamp=start_time,
                gas_used=None,
                error="Mint requires Substrate deposit - not implemented in demo"
            )
            
            logger.info(f"Mint preparation completed for {amount/1e18:.4f} TAO")
            return result
            
        except Exception as e:
            logger.error(f"Error executing mint: {e}")
            return TransactionResult(
                success=False,
                tx_hash=None,
                amount=amount,
                is_mint=True,
                timestamp=int(time.time()),
                gas_used=None,
                error=str(e)
            )
    
    async def _execute_redeem(self, amount: int) -> TransactionResult:
        """Execute a real redeem transaction"""
        try:
            start_time = int(time.time())
            
            logger.info(f"Executing redeem: {amount/1e18:.4f} TAO20")
            
            # Get current gas price
            gas_price = self.w3.eth.gas_price
            
            # Build transaction
            transaction = self.contract.functions.redeemTAO20(amount).build_transaction({
                'from': self.miner_address,
                'gas': 300000,  # Estimated gas limit
                'gasPrice': gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.miner_address),
            })
            
            # Sign transaction
            signed_txn = self.address_manager.sign_transaction(transaction)
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Wait for transaction receipt
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            result = TransactionResult(
                success=receipt.status == 1,
                tx_hash=tx_hash.hex(),
                amount=amount,
                is_mint=False,
                timestamp=start_time,
                gas_used=receipt.gasUsed
            )
            
            if result.success:
                logger.info(f"Redeem successful: {amount/1e18:.4f} TAO20 -> TAO, tx: {tx_hash.hex()}")
            else:
                logger.error(f"Redeem failed: tx: {tx_hash.hex()}")
                
            return result
            
        except Exception as e:
            logger.error(f"Error executing redeem: {e}")
            return TransactionResult(
                success=False,
                tx_hash=None,
                amount=amount,
                is_mint=False,
                timestamp=int(time.time()),
                gas_used=None,
                error=str(e)
            )
    
    def _record_transaction_result(self, result: TransactionResult):
        """Record transaction result and update performance"""
        self.transaction_history.append(result)
        
        # Keep only last 100 transactions
        if len(self.transaction_history) > 100:
            self.transaction_history.pop(0)
        
        # Update performance metrics
        self.performance.total_transactions += 1
        self.performance.last_activity = result.timestamp
        
        if result.success:
            self.performance.successful_transactions += 1
            self.performance.total_volume += result.amount
            self.performance.epoch_volume += result.amount
            
            if result.gas_used:
                self.performance.total_gas_used += result.gas_used
        else:
            self.performance.failed_transactions += 1
    
    def _log_performance(self):
        """Log current performance metrics"""
        success_rate = 0.0
        if self.performance.total_transactions > 0:
            success_rate = self.performance.successful_transactions / self.performance.total_transactions
        
        avg_gas = 0
        if self.performance.successful_transactions > 0:
            avg_gas = self.performance.total_gas_used / self.performance.successful_transactions
        
        logger.info(f"Performance: Volume={self.performance.total_volume/1e18:.1f} TAO, "
                   f"Transactions={self.performance.total_transactions}, "
                   f"Success={success_rate:.1%}, "
                   f"Avg Gas={avg_gas:.0f}")
    
    def get_performance_summary(self) -> Dict:
        """Get performance summary"""
        success_rate = 0.0
        if self.performance.total_transactions > 0:
            success_rate = self.performance.successful_transactions / self.performance.total_transactions
        
        return {
            'total_volume_tao': self.performance.total_volume / 1e18,
            'epoch_volume_tao': self.performance.epoch_volume / 1e18,
            'total_transactions': self.performance.total_transactions,
            'success_rate': success_rate,
            'current_tao_balance': self.current_balance / 1e18,
            'current_tao20_balance': self.tao20_balance / 1e18,
            'last_activity': self.performance.last_activity,
            'avg_gas_used': self.performance.total_gas_used / max(1, self.performance.successful_transactions)
        }


# Configuration for miner
def get_config():
    """Get miner configuration"""
    parser = bt.cli.ArgumentParser()
    
    # Oracle-specific configuration
    parser.add_argument('--oracle.contract_address', type=str, required=True,
                       help='TAO20 contract address')
    parser.add_argument('--oracle.web3_provider', type=str, required=True,
                       help='Web3 RPC provider URL')
    parser.add_argument('--oracle.min_transaction_amount', type=int, default=int(0.1 * 1e18),
                       help='Minimum transaction amount in TAO base units')
    parser.add_argument('--oracle.max_transaction_amount', type=int, default=int(10 * 1e18),
                       help='Maximum transaction amount in TAO base units')
    parser.add_argument('--oracle.transaction_interval', type=int, default=120,
                       help='Base interval between transactions in seconds')
    parser.add_argument('--oracle.volume_target_per_hour', type=int, default=int(100 * 1e18),
                       help='Target volume per hour in TAO base units')
    
    # Add Bittensor config
    bt.subtensor.add_args(parser)
    bt.wallet.add_args(parser)
    bt.logging.add_args(parser)
    
    return bt.config(parser)


# Main execution
async def main():
    """Main miner execution"""
    config = get_config()
    bt.logging(config=config, logging_dir=config.full_path)
    
    # Initialize Bittensor components
    wallet = bt.wallet(config=config)
    subtensor = bt.subtensor(config=config)
    metagraph = subtensor.metagraph(config.netuid)
    
    # Initialize miner
    miner = OracleMiner(wallet, config, subtensor, metagraph)
    
    # Run miner
    await miner.run()


if __name__ == "__main__":
    asyncio.run(main())
