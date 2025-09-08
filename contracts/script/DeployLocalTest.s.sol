// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "forge-std/Script.sol";
import "../src/Vault.sol";
import "../src/TAO20CoreV2OracleFree.sol";
import "../src/OracleFreeNAVCalculator.sol";
import "../src/StakingManager.sol";
import "../src/TAO20V2.sol";
import "../src/mocks/MockBittensorPrecompiles.sol";

/**
 * @title DeployLocalTest
 * @dev Deploy complete TAO20 system for local testing
 * 
 * DEPLOYMENT ORDER:
 * 1. Mock Bittensor precompiles
 * 2. Core infrastructure contracts
 * 3. TAO20 system contracts
 * 4. Configuration and initialization
 */
contract DeployLocalTest is Script {
    
    // Deployment addresses will be stored here
    address public stakingManager;
    address public navCalculator;
    address public tao20Core;
    address public vault;
    address public tao20Token;
    
    // Mock precompiles
    address public mockEd25519;
    address public mockSubstrateQuery;
    address public mockBalanceTransfer;
    address public mockStaking;
    address public mockMetagraph;
    
    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        vm.startBroadcast(deployerPrivateKey);
        
        console.log("=== Deploying TAO20 Local Test Environment ===");
        console.log("Deployer:", vm.addr(deployerPrivateKey));
        
        // Step 1: Deploy mock precompiles
        deployMockPrecompiles();
        
        // Step 2: Deploy core contracts
        deployCoreContracts();
        
        // Step 3: Initialize system
        initializeSystem();
        
        // Step 4: Deploy vault
        deployVault();
        
        // Step 5: Final configuration
        finalizeSetup();
        
        vm.stopBroadcast();
        
        // Output deployment info
        logDeploymentInfo();
    }
    
    function deployMockPrecompiles() internal {
        console.log("\n--- Deploying Mock Precompiles ---");
        
        mockEd25519 = address(new MockEd25519Verify());
        mockSubstrateQuery = address(new MockSubstrateQuery());
        mockBalanceTransfer = address(new MockBalanceTransfer());
        mockStaking = address(new MockStakingV2());
        mockMetagraph = address(new MockMetagraph());
        
        console.log("MockEd25519Verify:", mockEd25519);
        console.log("MockSubstrateQuery:", mockSubstrateQuery);
        console.log("MockBalanceTransfer:", mockBalanceTransfer);
        console.log("MockStakingV2:", mockStaking);
        console.log("MockMetagraph:", mockMetagraph);
    }
    
    function deployCoreContracts() internal {
        console.log("\n--- Deploying Core Contracts ---");
        
        // Deploy staking manager first
        stakingManager = address(new StakingManager());
        console.log("StakingManager:", stakingManager);
        
        // Deploy NAV calculator
        navCalculator = address(new OracleFreeNAVCalculator(stakingManager));
        console.log("OracleFreeNAVCalculator:", navCalculator);
        
        // Deploy TAO20 core (this will also deploy the token)
        tao20Core = address(new TAO20CoreV2OracleFree(
            stakingManager,
            navCalculator,
            "TAO20 Index Token",
            "TAO20"
        ));
        console.log("TAO20CoreV2OracleFree:", tao20Core);
        
        // Get the deployed token address
        tao20Token = address(TAO20CoreV2OracleFree(tao20Core).tao20Token());
        console.log("TAO20V2 Token:", tao20Token);
    }
    
    function initializeSystem() internal {
        console.log("\n--- Initializing System ---");
        
        // Setup mock data for testing
        setupMockData();
        
        console.log("System initialization complete");
    }
    
    function deployVault() internal {
        console.log("\n--- Deploying Vault ---");
        
        vault = address(new Vault(tao20Core));
        console.log("Vault:", vault);
    }
    
    function setupMockData() internal {
        console.log("Setting up mock test data...");
        
        // Setup mock neurons in popular subnets
        MockMetagraph metagraph = MockMetagraph(mockMetagraph);
        
        // Register neurons for top subnets
        metagraph.registerNeuron(1, 0, bytes32(uint256(0x1001)), bytes32(uint256(0x2001)), 1000e18, 100e18);
        metagraph.registerNeuron(2, 0, bytes32(uint256(0x1002)), bytes32(uint256(0x2002)), 800e18, 80e18);
        metagraph.registerNeuron(3, 0, bytes32(uint256(0x1003)), bytes32(uint256(0x2003)), 600e18, 60e18);
        metagraph.registerNeuron(4, 0, bytes32(uint256(0x1004)), bytes32(uint256(0x2004)), 500e18, 50e18);
        metagraph.registerNeuron(5, 0, bytes32(uint256(0x1005)), bytes32(uint256(0x2005)), 400e18, 40e18);
        
        // Setup initial balances
        MockSubstrateQuery query = MockSubstrateQuery(mockSubstrateQuery);
        MockBalanceTransfer transfer = MockBalanceTransfer(mockBalanceTransfer);
        
        // Give test users some subnet tokens
        bytes32 testUser1 = bytes32(uint256(0x1111111111111111111111111111111111111111111111111111111111111111));
        bytes32 testUser2 = bytes32(uint256(0x2222222222222222222222222222222222222222222222222222222222222222));
        
        for (uint16 netuid = 1; netuid <= 5; netuid++) {
            uint256 balance = 1000e18 - (netuid * 100e18); // Decreasing balances
            query.setBalance(testUser1, netuid, balance);
            query.setBalance(testUser2, netuid, balance / 2);
            
            transfer.setBalance(testUser1, netuid, balance);
            transfer.setBalance(testUser2, netuid, balance / 2);
        }
        
        console.log("Mock data setup complete");
    }
    
    function finalizeSetup() internal {
        console.log("\n--- Finalizing Setup ---");
        
        // Any final configuration steps would go here
        // For example, setting up initial weightings, etc.
        
        console.log("Setup finalization complete");
    }
    
    function logDeploymentInfo() internal view {
        console.log("\n=== DEPLOYMENT COMPLETE ===");
        console.log("");
        console.log("CORE CONTRACTS:");
        console.log("   TAO20Core:      ", tao20Core);
        console.log("   TAO20Token:     ", tao20Token);
        console.log("   Vault:          ", vault);
        console.log("   NAVCalculator:  ", navCalculator);
        console.log("   StakingManager: ", stakingManager);
        console.log("");
        console.log("MOCK PRECOMPILES:");
        console.log("   Ed25519Verify:    ", mockEd25519);
        console.log("   SubstrateQuery:   ", mockSubstrateQuery);
        console.log("   BalanceTransfer:  ", mockBalanceTransfer);
        console.log("   StakingV2:        ", mockStaking);
        console.log("   Metagraph:        ", mockMetagraph);
        console.log("");
        console.log("CHAIN INFO:");
        console.log("   Chain ID:       ", block.chainid);
        console.log("   Block Number:   ", block.number);
        console.log("   Timestamp:      ", block.timestamp);
        console.log("");
        console.log("Ready for testing!");
        console.log("");
        console.log("NEXT STEPS:");
        console.log("   1. Run: forge test --match-contract MintRedeemFlowTest");
        console.log("   2. Start Python integration tests");
        console.log("   3. Test complete mint/redeem flows");
    }
}
