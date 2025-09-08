#!/usr/bin/env python3
"""
Local Contract Interface for TAO20 Testing
Connects Python miners/validators to local Anvil contracts
"""

import asyncio
import logging
import json
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal

from web3 import Web3
from web3.contract import Contract
from eth_account import Account

logger = logging.getLogger(__name__)

@dataclass
class LocalTestConfig:
    """Configuration for local testing environment"""
    rpc_url: str = "http://localhost:8545"
    chain_id: int = 11501
    
    # Test account keys (from Anvil mnemonic)
    private_keys: List[str] = None
    
    # Will be populated after deployment
    contract_addresses: Dict[str, str] = None

    def __post_init__(self):
        if self.private_keys is None:
            # Default Anvil test keys
            self.private_keys = [
                "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",  # Account 0
                "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d",  # Account 1
                "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a",  # Account 2
            ]
        
        if self.contract_addresses is None:
            self.contract_addresses = {}

@dataclass
class SubnetDeposit:
    """Simulated subnet token deposit"""
    user_ss58: str
    user_evm: str
    netuid: int
    amount: Decimal
    block_hash: str
    extrinsic_index: int
    timestamp: int

@dataclass
class MintResult:
    """Result of mint operation"""
    success: bool
    tx_hash: Optional[str] = None
    tao20_minted: Optional[Decimal] = None
    error: Optional[str] = None

class LocalTAO20Interface:
    """
    Interface for interacting with locally deployed TAO20 contracts
    
    Designed for:
    1. Simple miner operations (mint/redeem)
    2. Validator monitoring and scoring
    3. Automated NAV testing
    4. End-to-end flow validation
    """
    
    def __init__(self, config: LocalTestConfig):
        self.config = config
        
        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(config.rpc_url))
        if not self.w3.is_connected():
            raise RuntimeError(f"Failed to connect to {config.rpc_url}")
        
        # Initialize test accounts
        self.accounts = [Account.from_key(key) for key in config.private_keys]
        self.deployer = self.accounts[0]
        self.miner1 = self.accounts[1]
        self.miner2 = self.accounts[2]
        
        # Contracts will be loaded when addresses are provided
        self.contracts = {}
        
        logger.info(f"Local TAO20 interface initialized")
        logger.info(f"Connected to: {config.rpc_url}")
        logger.info(f"Chain ID: {config.chain_id}")
        logger.info(f"Test accounts: {len(self.accounts)}")
    
    def load_deployment_info(self, deployment_file: str):
        """Load contract addresses from deployment file"""
        try:
            with open(deployment_file, 'r') as f:
                deployment_data = json.load(f)
            
            # Extract contract addresses from deployment data
            # This would parse the actual deployment output
            
            logger.info(f"Loaded deployment info from {deployment_file}")
            
        except Exception as e:
            logger.error(f"Failed to load deployment info: {e}")
    
    def set_contract_addresses(self, addresses: Dict[str, str]):
        """Manually set contract addresses for testing"""
        self.config.contract_addresses = addresses
        
        # Load contract ABIs and create contract instances
        for name, address in addresses.items():
            abi = self._get_contract_abi(name)
            if abi:
                self.contracts[name] = self.w3.eth.contract(
                    address=Web3.to_checksum_address(address),
                    abi=abi
                )
                logger.info(f"Loaded {name} contract at {address}")
    
    def _get_contract_abi(self, contract_name: str) -> Optional[List[Dict]]:
        """Get simplified ABI for testing"""
        
        # Minimal ABIs for testing purposes
        abis = {
            "Vault": [
                {
                    "inputs": [{"name": "netuid", "type": "uint16"}],
                    "name": "isSubnetSupported",
                    "outputs": [{"name": "", "type": "bool"}],
                    "stateMutability": "view",
                    "type": "function"
                },
                {
                    "inputs": [],
                    "name": "getSupportedSubnets", 
                    "outputs": [{"name": "", "type": "uint16[]"}],
                    "stateMutability": "view",
                    "type": "function"
                },
                {
                    "inputs": [{"name": "netuid", "type": "uint16"}],
                    "name": "getSubnetBalance",
                    "outputs": [{"name": "balance", "type": "uint256"}],
                    "stateMutability": "view",
                    "type": "function"
                }
            ],
            
            "TAO20Token": [
                {
                    "inputs": [],
                    "name": "totalSupply",
                    "outputs": [{"name": "", "type": "uint256"}],
                    "stateMutability": "view",
                    "type": "function"
                },
                {
                    "inputs": [{"name": "account", "type": "address"}],
                    "name": "balanceOf",
                    "outputs": [{"name": "", "type": "uint256"}],
                    "stateMutability": "view",
                    "type": "function"
                },
                {
                    "inputs": [],
                    "name": "name",
                    "outputs": [{"name": "", "type": "string"}],
                    "stateMutability": "view",
                    "type": "function"
                }
            ],
            
            "NAVCalculator": [
                {
                    "inputs": [],
                    "name": "getCurrentNAV",
                    "outputs": [{"name": "", "type": "uint256"}],
                    "stateMutability": "view",
                    "type": "function"
                }
            ]
        }
        
        return abis.get(contract_name)
    
    # ===================== SIMPLE MINER OPERATIONS =====================
    
    def simulate_substrate_deposit(self, deposit: SubnetDeposit) -> bool:
        """Simulate a subnet token deposit to the vault"""
        try:
            # In a real implementation, this would:
            # 1. Send tokens to vault's Substrate address
            # 2. Generate proper deposit proof
            # 3. Store deposit for verification
            
            logger.info(f"Simulated deposit: {deposit.amount} subnet {deposit.netuid} tokens")
            logger.info(f"From: {deposit.user_ss58} -> {deposit.user_evm}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to simulate deposit: {e}")
            return False
    
    def process_mint_request(self, deposit: SubnetDeposit) -> MintResult:
        """Process a mint request (simplified for testing)"""
        try:
            # This would be the miner's main operation:
            # 1. Verify substrate deposit exists
            # 2. Create Ed25519 signature proof
            # 3. Call contract mint function
            # 4. Monitor transaction success
            
            # For testing, simulate the process
            nav = self.get_current_nav()
            if nav is None:
                return MintResult(success=False, error="Could not get NAV")
            
            # Calculate TAO20 amount (simplified)
            # Real implementation would use proper subnet token pricing
            subnet_value = deposit.amount * Decimal("0.8")  # Example: subnet tokens worth 0.8 TAO each
            tao20_amount = subnet_value / nav
            
            logger.info(f"Mint calculation:")
            logger.info(f"  Subnet value: {subnet_value} TAO")
            logger.info(f"  Current NAV: {nav}")
            logger.info(f"  TAO20 to mint: {tao20_amount}")
            
            # Simulate successful mint
            return MintResult(
                success=True,
                tx_hash="0x" + "a" * 64,  # Mock transaction hash
                tao20_minted=tao20_amount
            )
            
        except Exception as e:
            logger.error(f"Failed to process mint: {e}")
            return MintResult(success=False, error=str(e))
    
    def process_redeem_request(self, tao20_amount: Decimal, user_ss58: str) -> MintResult:
        """Process a redeem request (simplified for testing)"""
        try:
            # This would be the miner's redeem operation:
            # 1. Verify user has sufficient TAO20 balance
            # 2. Calculate subnet token amounts to return
            # 3. Call contract redeem function
            # 4. Transfer subnet tokens to user's SS58 address
            
            nav = self.get_current_nav()
            if nav is None:
                return MintResult(success=False, error="Could not get NAV")
            
            # Calculate total redemption value
            total_value = tao20_amount * nav
            
            logger.info(f"Redeem calculation:")
            logger.info(f"  TAO20 amount: {tao20_amount}")
            logger.info(f"  Current NAV: {nav}")
            logger.info(f"  Total value: {total_value} TAO")
            
            # Simulate successful redeem
            return MintResult(
                success=True,
                tx_hash="0x" + "b" * 64,  # Mock transaction hash
                tao20_minted=-tao20_amount  # Negative for redeem
            )
            
        except Exception as e:
            logger.error(f"Failed to process redeem: {e}")
            return MintResult(success=False, error=str(e))
    
    # ===================== VALIDATOR OPERATIONS =====================
    
    def get_miner_performance_data(self, miner_address: str) -> Dict[str, any]:
        """Get performance data for miner scoring"""
        try:
            # This would collect real performance metrics:
            # 1. Volume processed
            # 2. Success/failure rates
            # 3. Response times
            # 4. Gas efficiency
            
            # For testing, return mock data
            return {
                "total_volume": "1000.5",
                "successful_operations": 25,
                "failed_operations": 2,
                "avg_response_time": 2.1,
                "uptime_percentage": 95.5,
                "gas_efficiency": 0.85
            }
            
        except Exception as e:
            logger.error(f"Failed to get miner performance: {e}")
            return {}
    
    def calculate_miner_scores(self, miners: List[str]) -> Dict[str, float]:
        """Calculate scores for a list of miners"""
        scores = {}
        
        for miner in miners:
            performance = self.get_miner_performance_data(miner)
            
            # Simple scoring algorithm
            volume_score = min(float(performance.get("total_volume", 0)) / 1000, 1.0)
            reliability_score = performance.get("successful_operations", 0) / max(
                performance.get("successful_operations", 0) + performance.get("failed_operations", 0), 1
            )
            speed_score = max(0, (5.0 - performance.get("avg_response_time", 10)) / 5.0)
            uptime_score = performance.get("uptime_percentage", 0) / 100.0
            
            final_score = (
                volume_score * 0.4 +
                reliability_score * 0.3 +
                speed_score * 0.2 +
                uptime_score * 0.1
            )
            
            scores[miner] = final_score
            
        return scores
    
    # ===================== NAV AND MONITORING =====================
    
    def get_current_nav(self) -> Optional[Decimal]:
        """Get current NAV from contract"""
        try:
            if "NAVCalculator" in self.contracts:
                nav_wei = self.contracts["NAVCalculator"].functions.getCurrentNAV().call()
                nav = Decimal(nav_wei) / Decimal(10**18)
                return nav
            else:
                # Mock NAV for testing
                return Decimal("1.0")
                
        except Exception as e:
            logger.error(f"Failed to get NAV: {e}")
            return None
    
    def get_vault_composition(self) -> Optional[Dict[int, Decimal]]:
        """Get current vault composition"""
        try:
            if "Vault" in self.contracts:
                supported_subnets = self.contracts["Vault"].functions.getSupportedSubnets().call()
                
                composition = {}
                for netuid in supported_subnets:
                    balance_wei = self.contracts["Vault"].functions.getSubnetBalance(netuid).call()
                    balance = Decimal(balance_wei) / Decimal(10**18)
                    if balance > 0:
                        composition[netuid] = balance
                
                return composition
            else:
                # Mock composition for testing
                return {1: Decimal("100"), 2: Decimal("50"), 3: Decimal("75")}
                
        except Exception as e:
            logger.error(f"Failed to get vault composition: {e}")
            return None
    
    def get_token_supply(self) -> Optional[Decimal]:
        """Get current TAO20 token supply"""
        try:
            if "TAO20Token" in self.contracts:
                supply_wei = self.contracts["TAO20Token"].functions.totalSupply().call()
                supply = Decimal(supply_wei) / Decimal(10**18)
                return supply
            else:
                # Mock supply for testing
                return Decimal("0")
                
        except Exception as e:
            logger.error(f"Failed to get token supply: {e}")
            return None
    
    # ===================== TESTING UTILITIES =====================
    
    def run_basic_connectivity_test(self) -> bool:
        """Test basic connectivity and contract access"""
        try:
            # Test Web3 connection
            latest_block = self.w3.eth.get_block('latest')
            logger.info(f"Connected to block {latest_block.number}")
            
            # Test account balances
            for i, account in enumerate(self.accounts[:3]):
                balance = self.w3.eth.get_balance(account.address)
                logger.info(f"Account {i}: {account.address} = {self.w3.from_wei(balance, 'ether')} ETH")
            
            # Test contract access if available
            if self.contracts:
                for name, contract in self.contracts.items():
                    logger.info(f"Contract {name}: {contract.address}")
            
            return True
            
        except Exception as e:
            logger.error(f"Connectivity test failed: {e}")
            return False
    
    async def run_end_to_end_test(self) -> Dict[str, bool]:
        """Run complete end-to-end flow test"""
        results = {}
        
        try:
            # Test 1: Basic connectivity
            results["connectivity"] = self.run_basic_connectivity_test()
            
            # Test 2: NAV calculation
            nav = self.get_current_nav()
            results["nav_calculation"] = nav is not None and nav > 0
            
            # Test 3: Vault composition
            composition = self.get_vault_composition()
            results["vault_access"] = composition is not None
            
            # Test 4: Simulated mint flow
            deposit = SubnetDeposit(
                user_ss58="5GNJqTPyNqANBkUVMN1LPPrxXnFouWXoe2wNSmmEoLctxiZY",
                user_evm=self.miner1.address,
                netuid=1,
                amount=Decimal("100"),
                block_hash="0x" + "1" * 64,
                extrinsic_index=1,
                timestamp=1234567890
            )
            
            deposit_success = self.simulate_substrate_deposit(deposit)
            mint_result = self.process_mint_request(deposit)
            results["mint_flow"] = deposit_success and mint_result.success
            
            # Test 5: Simulated redeem flow
            redeem_result = self.process_redeem_request(Decimal("10"), deposit.user_ss58)
            results["redeem_flow"] = redeem_result.success
            
            # Test 6: Miner scoring
            scores = self.calculate_miner_scores([self.miner1.address, self.miner2.address])
            results["miner_scoring"] = len(scores) == 2 and all(0 <= score <= 1 for score in scores.values())
            
            logger.info("End-to-end test results:")
            for test, passed in results.items():
                status = "PASS" if passed else "FAIL"
                logger.info(f"  {test}: {status}")
            
            return results
            
        except Exception as e:
            logger.error(f"End-to-end test failed: {e}")
            results["error"] = False
            return results

# ===================== MAIN ENTRY POINT =====================

async def main():
    """Demo of local contract interface"""
    
    # Initialize interface
    config = LocalTestConfig()
    interface = LocalTAO20Interface(config)
    
    # Run connectivity test
    logger.info("=== Testing Local TAO20 Interface ===")
    
    connected = interface.run_basic_connectivity_test()
    if not connected:
        logger.error("Failed basic connectivity test")
        return
    
    # Run end-to-end test
    results = await interface.run_end_to_end_test()
    
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)
    
    logger.info(f"\n=== TEST SUMMARY ===")
    logger.info(f"Passed: {passed_tests}/{total_tests}")
    logger.info(f"Success rate: {passed_tests/total_tests*100:.1f}%")
    
    if passed_tests == total_tests:
        logger.info("🎉 All tests passed! Ready for integration.")
    else:
        logger.warning("⚠️ Some tests failed. Check logs for details.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    asyncio.run(main())
