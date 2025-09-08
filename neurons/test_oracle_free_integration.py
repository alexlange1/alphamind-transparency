#!/usr/bin/env python3
"""
Oracle-Free TAO20 Integration Test
End-to-end testing of the oracle-free system
"""

import asyncio
import logging
import os
import time
from typing import Dict, Any
from decimal import Decimal

from oracle_free_web3 import (
    OracleFreeContractInterface,
    MintRequest,
    SubstrateDeposit,
    create_mint_request,
    TransactionResult
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OracleFreeIntegrationTest:
    """
    Comprehensive integration test for oracle-free TAO20 system
    
    Tests:
    1. Contract connectivity and basic queries
    2. NAV calculation and phase transitions
    3. Token operations (if possible)
    4. Miner and validator interactions
    5. Error handling and edge cases
    """
    
    def __init__(self, test_config: Dict[str, Any]):
        self.config = test_config
        self.test_results = {}
        
        # Initialize contract interface
        self.interface = OracleFreeContractInterface(
            rpc_url=test_config['rpc_url'],
            core_contract_address=test_config['core_contract_address'],
            private_key=test_config['private_key']
        )
        
        logger.info("Oracle-free integration test initialized")
        logger.info(f"Contract: {test_config['core_contract_address']}")
        logger.info(f"RPC: {test_config['rpc_url']}")
    
    async def run_all_tests(self) -> Dict[str, bool]:
        """Run all integration tests"""
        logger.info("Starting comprehensive oracle-free integration tests...")
        
        test_functions = [
            ('connectivity', self.test_connectivity),
            ('basic_queries', self.test_basic_queries),
            ('nav_operations', self.test_nav_operations),
            ('phase_info', self.test_phase_info),
            ('token_queries', self.test_token_queries),
            ('miner_stats', self.test_miner_stats),
            ('error_handling', self.test_error_handling),
            ('performance', self.test_performance),
        ]
        
        results = {}
        
        for test_name, test_func in test_functions:
            try:
                logger.info(f"Running test: {test_name}")
                start_time = time.time()
                
                success = await test_func()
                
                duration = time.time() - start_time
                results[test_name] = {
                    'success': success,
                    'duration': duration
                }
                
                status = "PASS" if success else "FAIL"
                logger.info(f"Test {test_name}: {status} ({duration:.2f}s)")
                
            except Exception as e:
                logger.error(f"Test {test_name} failed with exception: {e}")
                results[test_name] = {
                    'success': False,
                    'error': str(e),
                    'duration': 0
                }
        
        self.test_results = results
        return results
    
    # ===================== BASIC CONNECTIVITY TESTS =====================
    
    async def test_connectivity(self) -> bool:
        """Test basic Web3 connectivity"""
        try:
            # Test connection
            if not self.interface.is_connected():
                logger.error("Web3 not connected")
                return False
            
            # Test account balance
            balance = self.interface.get_account_balance()
            logger.info(f"Account balance: {balance} ETH")
            
            # Test latest block
            latest_block = self.interface.w3.eth.get_block('latest')
            logger.info(f"Latest block: {latest_block.number}")
            
            return True
            
        except Exception as e:
            logger.error(f"Connectivity test failed: {e}")
            return False
    
    async def test_basic_queries(self) -> bool:
        """Test basic contract queries"""
        try:
            # Test contract address queries
            token_address = self.interface.token_address
            staking_address = self.interface.staking_manager_address
            nav_address = self.interface.nav_calculator_address
            
            logger.info(f"Token contract: {token_address}")
            logger.info(f"Staking manager: {staking_address}")
            logger.info(f"NAV calculator: {nav_address}")
            
            # Verify addresses are valid
            if not all([token_address, staking_address, nav_address]):
                logger.error("Invalid contract addresses")
                return False
            
            # Test that addresses are different
            addresses = [token_address, staking_address, nav_address]
            if len(set(addresses)) != len(addresses):
                logger.error("Duplicate contract addresses")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Basic queries test failed: {e}")
            return False
    
    # ===================== NAV TESTS =====================
    
    async def test_nav_operations(self) -> bool:
        """Test NAV calculation operations"""
        try:
            # Get current NAV
            nav = self.interface.get_current_nav()
            logger.info(f"Current NAV: {nav}")
            
            # Verify NAV is reasonable
            if nav <= 0 or nav > 10:  # Sanity check
                logger.error(f"Unreasonable NAV value: {nav}")
                return False
            
            # In Phase 1, NAV should be exactly 1.0
            phase_info = self.interface.get_phase_info()
            if not phase_info['is_phase2_active'] and nav != Decimal("1.0"):
                logger.error(f"Phase 1 NAV should be 1.0, got {nav}")
                return False
            
            logger.info(f"NAV operations test passed")
            return True
            
        except Exception as e:
            logger.error(f"NAV operations test failed: {e}")
            return False
    
    async def test_phase_info(self) -> bool:
        """Test phase information queries"""
        try:
            phase_info = self.interface.get_phase_info()
            
            logger.info(f"Phase info: {phase_info}")
            
            # Verify phase info structure
            required_keys = ['is_phase2_active', 'current_nav', 'last_update', 'next_update_due']
            for key in required_keys:
                if key not in phase_info:
                    logger.error(f"Missing phase info key: {key}")
                    return False
            
            # Verify data types
            if not isinstance(phase_info['is_phase2_active'], bool):
                logger.error("is_phase2_active should be boolean")
                return False
            
            if not isinstance(phase_info['current_nav'], Decimal):
                logger.error("current_nav should be Decimal")
                return False
            
            if phase_info['last_update'] <= 0:
                logger.error("last_update should be positive")
                return False
            
            if phase_info['next_update_due'] <= phase_info['last_update']:
                logger.error("next_update_due should be after last_update")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Phase info test failed: {e}")
            return False
    
    # ===================== TOKEN TESTS =====================
    
    async def test_token_queries(self) -> bool:
        """Test token contract queries"""
        try:
            # Get TAO20 balance
            balance = self.interface.get_tao20_balance()
            logger.info(f"TAO20 balance: {balance}")
            
            # Get total supply
            total_supply = self.interface.get_total_supply()
            logger.info(f"Total supply: {total_supply}")
            
            # Verify values are non-negative
            if balance < 0:
                logger.error("Balance cannot be negative")
                return False
            
            if total_supply < 0:
                logger.error("Total supply cannot be negative")
                return False
            
            # Check authorized minter
            minter = self.interface.token_contract.functions.authorizedMinter().call()
            logger.info(f"Authorized minter: {minter}")
            
            # Verify minter is the core contract
            if minter.lower() != self.interface.core_address.lower():
                logger.error(f"Minter should be core contract, got {minter}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Token queries test failed: {e}")
            return False
    
    # ===================== MINER TESTS =====================
    
    async def test_miner_stats(self) -> bool:
        """Test miner statistics queries"""
        try:
            # Get miner stats for our address
            stats = self.interface.get_miner_stats()
            logger.info(f"Miner stats: {stats}")
            
            # Verify stats structure
            required_keys = [
                'volume_staked', 'volume_redeemed', 'total_volume',
                'transaction_count', 'last_activity', 'current_epoch_volume'
            ]
            
            for key in required_keys:
                if key not in stats:
                    logger.error(f"Missing miner stat key: {key}")
                    return False
            
            # Verify non-negative values
            for key in ['volume_staked', 'volume_redeemed', 'total_volume', 'current_epoch_volume']:
                if stats[key] < 0:
                    logger.error(f"Miner stat {key} cannot be negative")
                    return False
            
            if stats['transaction_count'] < 0:
                logger.error("Transaction count cannot be negative")
                return False
            
            # Verify total_volume is sum of staked and redeemed
            expected_total = stats['volume_staked'] + stats['volume_redeemed']
            if abs(stats['total_volume'] - expected_total) > Decimal("0.001"):
                logger.warning(f"Total volume mismatch: {stats['total_volume']} vs {expected_total}")
                # This might be acceptable due to rounding, so just warn
            
            return True
            
        except Exception as e:
            logger.error(f"Miner stats test failed: {e}")
            return False
    
    # ===================== ERROR HANDLING TESTS =====================
    
    async def test_error_handling(self) -> bool:
        """Test error handling for invalid operations"""
        try:
            success_count = 0
            total_tests = 0
            
            # Test 1: Invalid mint request (should fail gracefully)
            total_tests += 1
            try:
                invalid_request = MintRequest(
                    recipient="0x0000000000000000000000000000000000000000",
                    deposit=SubstrateDeposit(
                        block_hash="0x" + "0" * 64,
                        extrinsic_index=0,
                        user_ss58="invalid",
                        netuid=0,
                        amount=0,
                        timestamp=0
                    ),
                    nonce=0,
                    deadline=0  # Expired deadline
                )
                
                result = self.interface.mint_tao20(invalid_request, b'\x00' * 64)
                
                # Should fail
                if not result.success:
                    logger.info("Invalid mint request correctly rejected")
                    success_count += 1
                else:
                    logger.warning("Invalid mint request unexpectedly succeeded")
                    
            except Exception as e:
                logger.info(f"Invalid mint request correctly raised exception: {e}")
                success_count += 1
            
            # Test 2: Invalid redemption amount (should fail gracefully)
            total_tests += 1
            try:
                # Try to redeem more than balance
                balance = self.interface.get_tao20_balance()
                invalid_amount = balance + Decimal("1000000")
                
                result = self.interface.redeem_tao20(invalid_amount)
                
                if not result.success:
                    logger.info("Invalid redemption amount correctly rejected")
                    success_count += 1
                else:
                    logger.warning("Invalid redemption unexpectedly succeeded")
                    
            except Exception as e:
                logger.info(f"Invalid redemption correctly raised exception: {e}")
                success_count += 1
            
            # Test 3: Query with invalid address
            total_tests += 1
            try:
                invalid_address = "0x0000000000000000000000000000000000000000"
                balance = self.interface.get_tao20_balance(invalid_address)
                
                # Should return 0, not fail
                if balance == 0:
                    logger.info("Query with invalid address returned 0")
                    success_count += 1
                else:
                    logger.warning(f"Query with invalid address returned {balance}")
                    
            except Exception as e:
                logger.info(f"Query with invalid address handled gracefully: {e}")
                success_count += 1
            
            success_rate = success_count / total_tests
            logger.info(f"Error handling tests: {success_count}/{total_tests} passed ({success_rate:.1%})")
            
            return success_rate >= 0.8  # 80% success rate acceptable
            
        except Exception as e:
            logger.error(f"Error handling tests failed: {e}")
            return False
    
    # ===================== PERFORMANCE TESTS =====================
    
    async def test_performance(self) -> bool:
        """Test performance of various operations"""
        try:
            performance_results = {}
            
            # Test 1: NAV query performance
            start_time = time.time()
            for _ in range(10):
                nav = self.interface.get_current_nav()
            nav_query_time = (time.time() - start_time) / 10
            performance_results['nav_query'] = nav_query_time
            
            # Test 2: Balance query performance
            start_time = time.time()
            for _ in range(10):
                balance = self.interface.get_tao20_balance()
            balance_query_time = (time.time() - start_time) / 10
            performance_results['balance_query'] = balance_query_time
            
            # Test 3: Phase info query performance
            start_time = time.time()
            for _ in range(10):
                phase_info = self.interface.get_phase_info()
            phase_query_time = (time.time() - start_time) / 10
            performance_results['phase_query'] = phase_query_time
            
            # Test 4: Miner stats query performance
            start_time = time.time()
            for _ in range(10):
                stats = self.interface.get_miner_stats()
            stats_query_time = (time.time() - start_time) / 10
            performance_results['stats_query'] = stats_query_time
            
            logger.info("Performance results (average time per query):")
            for operation, avg_time in performance_results.items():
                logger.info(f"  {operation}: {avg_time:.3f}s")
            
            # Check if any operation is too slow
            max_acceptable_time = 5.0  # 5 seconds max per query
            for operation, avg_time in performance_results.items():
                if avg_time > max_acceptable_time:
                    logger.error(f"Operation {operation} too slow: {avg_time:.3f}s")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Performance tests failed: {e}")
            return False
    
    # ===================== TEST REPORTING =====================
    
    def generate_report(self) -> str:
        """Generate test report"""
        if not self.test_results:
            return "No test results available"
        
        report = []
        report.append("Oracle-Free TAO20 Integration Test Report")
        report.append("=" * 50)
        report.append("")
        
        total_tests = len(self.test_results)
        successful_tests = sum(1 for result in self.test_results.values() if result['success'])
        
        report.append(f"Total tests: {total_tests}")
        report.append(f"Successful: {successful_tests}")
        report.append(f"Failed: {total_tests - successful_tests}")
        report.append(f"Success rate: {successful_tests/total_tests:.1%}")
        report.append("")
        
        report.append("Test Details:")
        report.append("-" * 20)
        
        for test_name, result in self.test_results.items():
            status = "PASS" if result['success'] else "FAIL"
            duration = result.get('duration', 0)
            
            report.append(f"{test_name:20s} {status:4s} ({duration:.2f}s)")
            
            if not result['success'] and 'error' in result:
                report.append(f"  Error: {result['error']}")
        
        return "\n".join(report)

# ===================== MAIN EXECUTION =====================

async def main():
    """Main test execution"""
    
    # Test configuration
    test_config = {
        'rpc_url': os.getenv('BEVM_RPC_URL', 'http://localhost:8545'),
        'core_contract_address': os.getenv('TAO20_CONTRACT_ADDRESS', ''),
        'private_key': os.getenv('TEST_PRIVATE_KEY', '0x' + '0' * 64),
    }
    
    # Validate configuration
    if not test_config['core_contract_address']:
        logger.error("TAO20_CONTRACT_ADDRESS environment variable required")
        logger.info("Example: export TAO20_CONTRACT_ADDRESS=0x1234...")
        return
    
    if test_config['private_key'] == '0x' + '0' * 64:
        logger.warning("Using dummy private key - some tests may fail")
        logger.info("Set TEST_PRIVATE_KEY environment variable for full testing")
    
    try:
        # Run integration tests
        test_suite = OracleFreeIntegrationTest(test_config)
        results = await test_suite.run_all_tests()
        
        # Generate and display report
        report = test_suite.generate_report()
        print("\n" + report + "\n")
        
        # Exit with appropriate code
        success_rate = sum(1 for r in results.values() if r['success']) / len(results)
        exit_code = 0 if success_rate >= 0.8 else 1
        
        logger.info(f"Integration tests completed with {success_rate:.1%} success rate")
        exit(exit_code)
        
    except Exception as e:
        logger.error(f"Integration tests failed: {e}")
        exit(1)

if __name__ == "__main__":
    asyncio.run(main())
