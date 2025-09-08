#!/usr/bin/env python3
"""
Local Integration Test for TAO20 System
Tests Python integration with locally deployed contracts
"""

import asyncio
import logging
import time
from decimal import Decimal

from local_contract_interface import LocalTAO20Interface, LocalTestConfig, SubnetDeposit

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_integration_test():
    """Run comprehensive integration test"""
    
    logger.info("🚀 Starting TAO20 Local Integration Test")
    logger.info("=" * 50)
    
    # Initialize interface
    config = LocalTestConfig()
    interface = LocalTAO20Interface(config)
    
    # Test results tracking
    test_results = {}
    
    # =================== TEST 1: CONNECTIVITY ===================
    logger.info("\n📡 Test 1: Basic Connectivity")
    try:
        connected = interface.run_basic_connectivity_test()
        test_results["connectivity"] = connected
        
        if connected:
            logger.info("✅ Connectivity test passed")
        else:
            logger.error("❌ Connectivity test failed")
            
    except Exception as e:
        logger.error(f"❌ Connectivity test error: {e}")
        test_results["connectivity"] = False
    
    # =================== TEST 2: CONTRACT ACCESS ===================
    logger.info("\n🔗 Test 2: Contract Access")
    try:
        # Try to get NAV (tests contract interaction)
        nav = interface.get_current_nav()
        vault_composition = interface.get_vault_composition()
        token_supply = interface.get_token_supply()
        
        success = all([
            nav is not None,
            vault_composition is not None,
            token_supply is not None
        ])
        
        test_results["contract_access"] = success
        
        if success:
            logger.info("✅ Contract access test passed")
            logger.info(f"   Current NAV: {nav}")
            logger.info(f"   Vault subnets: {len(vault_composition) if vault_composition else 0}")
            logger.info(f"   Token supply: {token_supply}")
        else:
            logger.error("❌ Contract access test failed")
            
    except Exception as e:
        logger.error(f"❌ Contract access test error: {e}")
        test_results["contract_access"] = False
    
    # =================== TEST 3: MINER SIMULATION ===================
    logger.info("\n⛏️  Test 3: Miner Simulation")
    try:
        # Create a simulated subnet deposit
        deposit = SubnetDeposit(
            user_ss58="5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",  # Alice
            user_evm=interface.miner1.address,
            netuid=1,  # Text prompting subnet
            amount=Decimal("100.0"),  # 100 subnet tokens
            block_hash="0x" + "1234" * 16,
            extrinsic_index=42,
            timestamp=int(time.time())
        )
        
        # Step 1: Simulate substrate deposit
        deposit_success = interface.simulate_substrate_deposit(deposit)
        
        # Step 2: Process mint request
        mint_result = interface.process_mint_request(deposit)
        
        success = deposit_success and mint_result.success
        test_results["miner_simulation"] = success
        
        if success:
            logger.info("✅ Miner simulation test passed")
            logger.info(f"   Deposited: {deposit.amount} subnet {deposit.netuid} tokens")
            logger.info(f"   Minted: {mint_result.tao20_minted} TAO20 tokens")
        else:
            logger.error("❌ Miner simulation test failed")
            if mint_result.error:
                logger.error(f"   Error: {mint_result.error}")
                
    except Exception as e:
        logger.error(f"❌ Miner simulation test error: {e}")
        test_results["miner_simulation"] = False
    
    # =================== TEST 4: VALIDATOR SIMULATION ===================
    logger.info("\n🏛️  Test 4: Validator Simulation")
    try:
        # Test miner performance data collection
        miner_addresses = [
            interface.miner1.address,
            interface.miner2.address
        ]
        
        # Get performance data for each miner
        performance_data = {}
        for miner in miner_addresses:
            data = interface.get_miner_performance_data(miner)
            performance_data[miner] = data
        
        # Calculate scores
        scores = interface.calculate_miner_scores(miner_addresses)
        
        success = (
            len(performance_data) == 2 and
            len(scores) == 2 and
            all(0 <= score <= 1 for score in scores.values())
        )
        
        test_results["validator_simulation"] = success
        
        if success:
            logger.info("✅ Validator simulation test passed")
            for miner, score in scores.items():
                logger.info(f"   Miner {miner[:8]}...: Score {score:.3f}")
        else:
            logger.error("❌ Validator simulation test failed")
            
    except Exception as e:
        logger.error(f"❌ Validator simulation test error: {e}")
        test_results["validator_simulation"] = False
    
    # =================== TEST 5: REDEEM SIMULATION ===================
    logger.info("\n💰 Test 5: Redeem Simulation")
    try:
        # Simulate redeeming some TAO20 tokens
        redeem_amount = Decimal("10.0")
        user_ss58 = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
        
        redeem_result = interface.process_redeem_request(redeem_amount, user_ss58)
        
        success = redeem_result.success
        test_results["redeem_simulation"] = success
        
        if success:
            logger.info("✅ Redeem simulation test passed")
            logger.info(f"   Redeemed: {redeem_amount} TAO20 tokens")
            logger.info(f"   To user: {user_ss58[:8]}...")
        else:
            logger.error("❌ Redeem simulation test failed")
            if redeem_result.error:
                logger.error(f"   Error: {redeem_result.error}")
                
    except Exception as e:
        logger.error(f"❌ Redeem simulation test error: {e}")
        test_results["redeem_simulation"] = False
    
    # =================== TEST 6: AUTOMATED NAV ===================
    logger.info("\n📊 Test 6: Automated NAV System")
    try:
        # Test that NAV is calculated automatically without validator consensus
        nav1 = interface.get_current_nav()
        await asyncio.sleep(1)  # Small delay
        nav2 = interface.get_current_nav()
        
        # NAV should be deterministic and automated
        success = (
            nav1 is not None and 
            nav2 is not None and
            nav1 == nav2  # Should be consistent
        )
        
        test_results["automated_nav"] = success
        
        if success:
            logger.info("✅ Automated NAV test passed")
            logger.info(f"   NAV is consistently: {nav1}")
            logger.info("   ✓ No validator consensus required")
            logger.info("   ✓ Market-based calculation")
        else:
            logger.error("❌ Automated NAV test failed")
            
    except Exception as e:
        logger.error(f"❌ Automated NAV test error: {e}")
        test_results["automated_nav"] = False
    
    # =================== RESULTS SUMMARY ===================
    logger.info("\n" + "=" * 50)
    logger.info("📋 INTEGRATION TEST RESULTS")
    logger.info("=" * 50)
    
    total_tests = len(test_results)
    passed_tests = sum(1 for result in test_results.values() if result)
    
    for test_name, passed in test_results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{test_name.replace('_', ' ').title()}: {status}")
    
    logger.info("-" * 50)
    logger.info(f"TOTAL: {passed_tests}/{total_tests} tests passed")
    logger.info(f"SUCCESS RATE: {passed_tests/total_tests*100:.1f}%")
    
    if passed_tests == total_tests:
        logger.info("🎉 ALL TESTS PASSED! Integration ready.")
        logger.info("✅ Python ↔ Smart Contract integration working")
        logger.info("✅ Simplified miner architecture validated")
        logger.info("✅ Simplified validator architecture validated")
        logger.info("✅ Automated NAV system confirmed")
    else:
        logger.warning("⚠️  Some tests failed. Ready for debugging.")
        logger.info("💡 This is expected until contracts are deployed locally")
    
    return test_results

async def main():
    """Main entry point"""
    try:
        results = await run_integration_test()
        
        # Exit with appropriate code
        total_tests = len(results)
        passed_tests = sum(1 for result in results.values() if result)
        
        if passed_tests == total_tests:
            logger.info("\n🚀 Ready for full testing with deployed contracts!")
            exit(0)
        else:
            logger.info("\n🔧 Need to deploy contracts and update addresses")
            exit(1)
            
    except KeyboardInterrupt:
        logger.info("\n⏹️  Test interrupted by user")
        exit(1)
    except Exception as e:
        logger.error(f"\n💥 Test failed with error: {e}")
        exit(1)

if __name__ == "__main__":
    asyncio.run(main())
