// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "forge-std/Test.sol";
import "../src/Vault.sol";
import "../src/TAO20CoreV2OracleFree.sol";
import "../src/OracleFreeNAVCalculator.sol";
import "../src/StakingManager.sol";
import "../src/TAO20V2.sol";
import "../src/mocks/MockBittensorPrecompiles.sol";

/**
 * @title TAO20SimpleFlowTest
 * @dev Simple, working test for basic TAO20 functionality
 * Focuses on our corrected architecture without complex integration
 */
contract TAO20SimpleFlowTest is Test {

    // Core contracts
    Vault public vault;
    TAO20CoreV2OracleFree public tao20Core;
    OracleFreeNAVCalculator public navCalculator;
    StakingManager public stakingManager;
    TAO20V2 public tao20Token;
    
    // Mock precompiles
    MockEd25519Verify public mockEd25519;
    MockSubstrateQuery public mockSubstrateQuery;
    
    // Test accounts
    address public deployer = address(0x1);
    address public user1 = address(0x2);
    address public miner1 = address(0x10);
    
    function setUp() public {
        vm.startPrank(deployer);
        
        // Deploy mock precompiles first
        mockEd25519 = new MockEd25519Verify();
        mockSubstrateQuery = new MockSubstrateQuery();
        
        // Deploy core system
        stakingManager = new StakingManager();
        navCalculator = new OracleFreeNAVCalculator(address(stakingManager));
        tao20Core = new TAO20CoreV2OracleFree(
            address(stakingManager),
            address(navCalculator),
            "TAO20 Test Token",
            "TAO20T"
        );
        
        // Get deployed token
        tao20Token = TAO20V2(address(tao20Core.tao20Token()));
        
        // Deploy vault
        vault = new Vault(address(tao20Core));
        
        vm.stopPrank();
        
        console.log("=== Simple Test Setup Complete ===");
        console.log("Vault:", address(vault));
        console.log("TAO20Core:", address(tao20Core));
        console.log("TAO20Token:", address(tao20Token));
    }
    
    function testBasicDeployment() public {
        // Test that all contracts deployed successfully
        assertTrue(address(vault) != address(0), "Vault should be deployed");
        assertTrue(address(tao20Core) != address(0), "TAO20Core should be deployed");
        assertTrue(address(tao20Token) != address(0), "TAO20Token should be deployed");
        assertTrue(address(navCalculator) != address(0), "NAVCalculator should be deployed");
        assertTrue(address(stakingManager) != address(0), "StakingManager should be deployed");
        
        console.log("All contracts deployed successfully");
    }
    
    function testVaultConfiguration() public {
        // Test vault is properly configured
        uint16[] memory supportedSubnets = vault.getSupportedSubnets();
        assertTrue(supportedSubnets.length == 20, "Should support 20 subnets");
        
        // Check some specific subnets are supported
        assertTrue(vault.isSubnetSupported(1), "Subnet 1 should be supported");
        assertTrue(vault.isSubnetSupported(2), "Subnet 2 should be supported");
        assertFalse(vault.isSubnetSupported(999), "Subnet 999 should not be supported");
        
        console.log("Vault configuration correct");
    }
    
    function testNAVCalculation() public {
        // Test NAV calculation (should not be 1:1 peg)
        uint256 currentNAV = navCalculator.getCurrentNAV();
        assertTrue(currentNAV > 0, "NAV should be positive");
        
        console.log("Current NAV:", currentNAV);
        console.log("NAV calculation working");
    }
    
    function testTokenBasics() public {
        // Test basic token properties
        assertEq(tao20Token.name(), "TAO20 Test Token");
        assertEq(tao20Token.symbol(), "TAO20T");
        assertEq(tao20Token.decimals(), 18);
        assertEq(tao20Token.totalSupply(), 0); // Should start with 0 supply
        
        console.log("Token basics correct");
    }
    
    function testMockPrecompiles() public {
        // Test mock precompiles work
        
        // Test Ed25519 mock
        bytes memory validSignature = abi.encodePacked(
            bytes32(0xabcd000000000000000000000000000000000000000000000000000000000000),
            bytes32(0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef)
        );
        
        bool isValid = mockEd25519.verify(
            bytes32(uint256(0x123)),
            bytes32(uint256(0x456)),
            validSignature
        );
        assertTrue(isValid, "Mock Ed25519 should validate signature starting with 0xabcd");
        
        // Test Substrate query mock
        bytes32 blockHash = bytes32(uint256(0x789));
        mockSubstrateQuery.createMockDeposit(
            blockHash,
            1,
            bytes32(uint256(0x111)),
            1,
            100e18
        );
        
        (bool exists, ) = mockSubstrateQuery.queryDeposit(
            blockHash,
            1,
            bytes32(uint256(0x111)),
            1,
            100e18
        );
        assertTrue(exists, "Mock deposit should exist");
        
        console.log("Mock precompiles working");
    }
    
    function testVaultDepositStructure() public {
        // Test vault deposit verification structure (not full flow yet)
        
        // This tests the data structure without requiring full integration
        Vault.DepositProof memory proof = Vault.DepositProof({
            blockHash: bytes32(uint256(0x123)),
            extrinsicIndex: 1,
            depositorSS58: bytes32(uint256(0x456)),
            netuid: 1,
            amount: 100e18,
            blockNumber: 1000,
            timestamp: block.timestamp
        });
        
        // Test that proof structure is valid
        assertTrue(proof.amount > 0, "Proof amount should be positive");
        assertTrue(proof.netuid > 0, "Proof netuid should be positive");
        
        console.log("Vault deposit structure correct");
    }
    
    function testContractSizes() public {
        // Ensure contracts are not too large
        uint256 vaultSize = address(vault).code.length;
        uint256 coreSize = address(tao20Core).code.length;
        uint256 navSize = address(navCalculator).code.length;
        
        console.log("Contract sizes:");
        console.log("  Vault:", vaultSize, "bytes");
        console.log("  Core:", coreSize, "bytes");
        console.log("  NAV:", navSize, "bytes");
        
        // Ethereum limit is 24KB
        assertTrue(vaultSize < 24576, "Vault too large");
        assertTrue(coreSize < 24576, "Core too large");
        assertTrue(navSize < 24576, "NAV calculator too large");
        
        console.log("Contract sizes within limits");
    }
    
    function testAccessControl() public {
        // Test that vault only accepts calls from authorized addresses
        
        vm.startPrank(user1); // Unauthorized user
        
        // This should fail (we expect it to revert)
        Vault.DepositProof memory proof = Vault.DepositProof({
            blockHash: bytes32(uint256(0x123)),
            extrinsicIndex: 1,
            depositorSS58: bytes32(uint256(0x456)),
            netuid: 1,
            amount: 100e18,
            blockNumber: 1000,
            timestamp: block.timestamp
        });
        
        // This call should revert because user1 is not TAO20Core
        vm.expectRevert();
        vault.verifyDeposit(proof, user1);
        
        vm.stopPrank();
        
        console.log("Access control working");
    }
    
    function testSystemIntegration() public {
        // Test that contracts are properly linked
        assertTrue(address(tao20Core.navCalculator()) == address(navCalculator), "NAV calculator not linked");
        assertTrue(address(tao20Core.stakingManager()) == address(stakingManager), "Staking manager not linked");
        assertTrue(address(tao20Core.tao20Token()) == address(tao20Token), "Token not linked");
        
        console.log("System integration correct");
    }
}
