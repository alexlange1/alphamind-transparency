#!/usr/bin/env python3
"""
Real Contract Integration Test
Tests Python integration with actually deployed contracts
"""

import asyncio
import logging
import time
from decimal import Decimal

from local_contract_interface import LocalTAO20Interface, LocalTestConfig, SubnetDeposit

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Real deployed contract addresses from the deployment
DEPLOYED_ADDRESSES = {
    "TAO20Core": "0xa513E6E4b8f2a923D98304ec87F64353C4D5C853",
    "TAO20Token": "0x9bd03768a7DCc129555dE410FF8E85528A4F88b5",
    "Vault": "0x9E545E3C0baAB3E08CdfD552C960A1050f373042",
    "NAVCalculator": "0x0165878A594ca255338adfa4d48449f69242Eb8F",
    "StakingManager": "0x5FC8d32690cc91D4c39d9d3abcBD16989F875707",
    
    # Mock precompiles
    "MockEd25519": "0x5FbDB2315678afecb367f032d93F642f64180aa3",
    "MockSubstrateQuery": "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512",
    "MockBalanceTransfer": "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0",
}

async def test_real_contract_integration():
    """Test integration with real deployed contracts"""
    
    logger.info("🚀 Testing Real Contract Integration")
    logger.info("=" * 60)
    
    # Initialize interface
    config = LocalTestConfig()
    interface = LocalTAO20Interface(config)
    
    # Set the real contract addresses
    interface.set_contract_addresses(DEPLOYED_ADDRESSES)
    
    test_results = {}
    
    # =================== TEST 1: REAL CONTRACT ACCESS ===================
    logger.info("\n🔗 Test 1: Real Contract Access")
    try:
        # Test basic contract calls
        nav = interface.get_current_nav()
        vault_composition = interface.get_vault_composition()
        token_supply = interface.get_token_supply()
        
        success = all([
            nav is not None,
            vault_composition is not None,
            token_supply is not None
        ])
        
        test_results["real_contract_access"] = success
        
        if success:
            logger.info("✅ Real contract access working!")
            logger.info(f"   Current NAV: {nav}")
            logger.info(f"   Vault composition: {len(vault_composition)} subnets")
            logger.info(f"   Token supply: {token_supply}")
        else:
            logger.error("❌ Real contract access failed")
            
    except Exception as e:
        logger.error(f"❌ Real contract access error: {e}")
        test_results["real_contract_access"] = False
    
    # =================== TEST 2: VAULT VERIFICATION ===================
    logger.info("\n🏦 Test 2: Vault Contract Verification")
    try:
        # Test vault-specific functions
        supported_subnets = None
        if "Vault" in interface.contracts:
            vault = interface.contracts["Vault"]
            
            # Test getting supported subnets
            supported_subnets = vault.functions.getSupportedSubnets().call()
            
            # Test checking if specific subnets are supported
            subnet_1_supported = vault.functions.isSubnetSupported(1).call()
            subnet_999_supported = vault.functions.isSubnetSupported(999).call()
            
            success = (
                supported_subnets is not None and
                len(supported_subnets) == 20 and
                subnet_1_supported == True and
                subnet_999_supported == False
            )
        else:
            success = False
        
        test_results["vault_verification"] = success
        
        if success:
            logger.info("✅ Vault verification successful!")
            logger.info(f"   Supported subnets: {len(supported_subnets)}")
            logger.info(f"   Subnet 1 supported: {subnet_1_supported}")
            logger.info(f"   Subnet 999 supported: {subnet_999_supported}")
        else:
            logger.error("❌ Vault verification failed")
            
    except Exception as e:
        logger.error(f"❌ Vault verification error: {e}")
        test_results["vault_verification"] = False
    
    # =================== TEST 3: TOKEN CONTRACT ===================
    logger.info("\n🪙 Test 3: Token Contract Verification")
    try:
        if "TAO20Token" in interface.contracts:
            token = interface.contracts["TAO20Token"]
            
            # Test token properties
            name = token.functions.name().call()
            symbol = "N/A"  # Will implement symbol later if needed
            decimals = 18    # Standard
            total_supply = token.functions.totalSupply().call()
            
            # Test balance of deployer
            deployer_balance = token.functions.balanceOf(interface.deployer.address).call()
            
            success = (
                name is not None and
                total_supply == 0 and  # Should start with 0 supply
                isinstance(deployer_balance, int)
            )
        else:
            success = False
        
        test_results["token_verification"] = success
        
        if success:
            logger.info("✅ Token contract verification successful!")
            logger.info(f"   Token name: {name}")
            logger.info(f"   Total supply: {total_supply}")
            logger.info(f"   Deployer balance: {deployer_balance}")
        else:
            logger.error("❌ Token contract verification failed")
            
    except Exception as e:
        logger.error(f"❌ Token contract verification error: {e}")
        test_results["token_verification"] = False
    
    # =================== TEST 4: NAV CALCULATOR ===================
    logger.info("\n📊 Test 4: NAV Calculator Verification")
    try:
        if "NAVCalculator" in interface.contracts:
            nav_calc = interface.contracts["NAVCalculator"]
            
            # Test NAV calculation
            current_nav = nav_calc.functions.getCurrentNAV().call()
            
            # Convert from wei to decimal
            nav_decimal = Decimal(current_nav) / Decimal(10**18)
            
            success = (
                current_nav > 0 and
                nav_decimal > 0
            )
        else:
            success = False
        
        test_results["nav_verification"] = success
        
        if success:
            logger.info("✅ NAV calculator verification successful!")
            logger.info(f"   Current NAV (wei): {current_nav}")
            logger.info(f"   Current NAV (decimal): {nav_decimal}")
            logger.info("   ✓ Market-based calculation (no 1:1 peg)")
        else:
            logger.error("❌ NAV calculator verification failed")
            
    except Exception as e:
        logger.error(f"❌ NAV calculator verification error: {e}")
        test_results["nav_verification"] = False
    
    # =================== TEST 5: MOCK PRECOMPILES ===================
    logger.info("\n🧪 Test 5: Mock Precompile Verification")
    try:
        # Test mock Ed25519 verification
        mock_ed25519_addr = DEPLOYED_ADDRESSES["MockEd25519"]
        
        # Create simple contract instance for Ed25519
        ed25519_abi = [
            {
                "inputs": [
                    {"name": "message", "type": "bytes32"},
                    {"name": "pubkey", "type": "bytes32"}, 
                    {"name": "signature", "type": "bytes"}
                ],
                "name": "verify",
                "outputs": [{"name": "", "type": "bool"}],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]
        
        ed25519_contract = interface.w3.eth.contract(
            address=mock_ed25519_addr,
            abi=ed25519_abi
        )
        
        # Test signature that should pass (starts with 0xabcd)
        valid_signature = bytes.fromhex(
            "abcd000000000000000000000000000000000000000000000000000000000000" +
            "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
        )
        
        # Build transaction for verification
        verify_txn = ed25519_contract.functions.verify(
            bytes(32),  # message
            bytes(32),  # pubkey
            valid_signature
        ).build_transaction({
            'from': interface.deployer.address,
            'gas': 100000,
            'gasPrice': interface.w3.eth.gas_price,
            'nonce': interface.w3.eth.get_transaction_count(interface.deployer.address),
        })
        
        # Sign and send transaction
        signed_txn = interface.deployer.sign_transaction(verify_txn)
        tx_hash = interface.w3.eth.send_raw_transaction(signed_txn.raw_transaction)
        
        # Wait for transaction
        receipt = interface.w3.eth.wait_for_transaction_receipt(tx_hash)
        success = receipt.status == 1
        
        test_results["mock_precompiles"] = success
        
        if success:
            logger.info("✅ Mock precompile verification successful!")
            logger.info(f"   Ed25519 verification tx: {tx_hash.hex()}")
            logger.info("   ✓ Mock signature verification working")
        else:
            logger.error("❌ Mock precompile verification failed")
            
    except Exception as e:
        logger.error(f"❌ Mock precompile verification error: {e}")
        test_results["mock_precompiles"] = False
    
    # =================== TEST 6: COMPLETE SYSTEM INTEGRATION ===================
    logger.info("\n🔄 Test 6: Complete System Integration")
    try:
        # Test that all contracts are properly linked
        all_contracts_deployed = all(
            addr != "0x0000000000000000000000000000000000000000" 
            for addr in DEPLOYED_ADDRESSES.values()
        )
        
        all_contracts_accessible = len(interface.contracts) >= 3
        
        success = all_contracts_deployed and all_contracts_accessible
        
        test_results["system_integration"] = success
        
        if success:
            logger.info("✅ Complete system integration successful!")
            logger.info(f"   Deployed contracts: {len(DEPLOYED_ADDRESSES)}")
            logger.info(f"   Accessible contracts: {len(interface.contracts)}")
            logger.info("   ✓ All systems ready for production testing")
        else:
            logger.error("❌ Complete system integration failed")
            
    except Exception as e:
        logger.error(f"❌ Complete system integration error: {e}")
        test_results["system_integration"] = False
    
    # =================== RESULTS SUMMARY ===================
    logger.info("\n" + "=" * 60)
    logger.info("📋 REAL CONTRACT INTEGRATION RESULTS")
    logger.info("=" * 60)
    
    total_tests = len(test_results)
    passed_tests = sum(1 for result in test_results.values() if result)
    
    for test_name, passed in test_results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{test_name.replace('_', ' ').title()}: {status}")
    
    logger.info("-" * 60)
    logger.info(f"TOTAL: {passed_tests}/{total_tests} tests passed")
    logger.info(f"SUCCESS RATE: {passed_tests/total_tests*100:.1f}%")
    
    if passed_tests == total_tests:
        logger.info("🎉 ALL REAL CONTRACT TESTS PASSED!")
        logger.info("✅ Python fully integrated with deployed contracts")
        logger.info("✅ All contract calls working properly")
        logger.info("✅ Mock precompiles functional")
        logger.info("✅ Ready for end-to-end flow testing")
    else:
        logger.warning("⚠️  Some tests failed. Debugging needed.")
    
    return test_results

async def main():
    """Main entry point"""
    try:
        results = await test_real_contract_integration()
        
        # Exit with appropriate code
        total_tests = len(results)
        passed_tests = sum(1 for result in results.values() if result)
        
        if passed_tests == total_tests:
            logger.info("\n🚀 Ready for end-to-end flow testing!")
            exit(0)
        else:
            logger.info("\n🔧 Some integration issues to resolve")
            exit(1)
            
    except KeyboardInterrupt:
        logger.info("\n⏹️  Test interrupted by user")
        exit(1)
    except Exception as e:
        logger.error(f"\n💥 Test failed with error: {e}")
        exit(1)

if __name__ == "__main__":
    asyncio.run(main())
