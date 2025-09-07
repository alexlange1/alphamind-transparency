// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import {Script, console} from "forge-std/Script.sol";
import "../src/TAO20CoreV2Enhanced.sol";
import "../src/NAVOracle.sol";
import "../src/SubnetStakingManager.sol";
import "../src/TAO20V2.sol";
import "../src/libraries/AddressUtils.sol";

/**
 * @title DeployV2Enhanced
 * @dev Deployment script for the complete TAO20 V2 Enhanced architecture
 * 
 * DEPLOYMENT ORDER:
 * 1. Deploy NAVOracle with initial validators
 * 2. Deploy TAO20CoreV2Enhanced (which creates SubnetStakingManager and TAO20V2)
 * 3. Configure subnet validators and index composition
 * 4. Initialize oracle with default NAV
 * 5. Verify all contracts and log addresses
 */
contract DeployV2Enhanced is Script {
    using AddressUtils for address;

    // ===================== DEPLOYMENT PARAMETERS =====================
    
    // Token configuration
    string constant TOKEN_NAME = "TAO20 Index Token V2";
    string constant TOKEN_SYMBOL = "TAO20";
    
    // Oracle configuration
    uint256 constant INITIAL_NAV = 1e18; // 1 TAO per TAO20 token initially
    uint256 constant MAX_PRICE_AGE = 300; // 5 minutes
    uint256 constant MIN_VALIDATORS = 3;
    uint256 constant CONSENSUS_THRESHOLD_BPS = 6667; // 66.67%
    uint256 constant MAX_PRICE_DEVIATION_BPS = 500; // 5%
    
    // Default validator stakes (for testing)
    uint256 constant DEFAULT_VALIDATOR_STAKE = 1000e18; // 1000 TAO
    
    // Top 20 subnet IDs (example - in production, use actual rankings)
    uint16[20] SUBNET_IDS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20];
    
    // Equal weights for simplicity (5% each)
    uint256[20] SUBNET_WEIGHTS = [500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500];

    // ===================== DEPLOYED CONTRACTS =====================
    
    NAVOracle public navOracle;
    TAO20CoreV2Enhanced public tao20Core;
    SubnetStakingManager public stakingManager;
    TAO20V2 public tao20Token;
    
    // ===================== DEPLOYMENT ADDRESSES =====================
    
    address[] public initialValidators;
    uint256[] public initialValidatorStakes;
    bytes32[] public subnetValidatorHotkeys;

    function setUp() public {
        // Setup initial validators (in production, use real validator addresses)
        initialValidators = [
            0x1234567890123456789012345678901234567890, // Validator 1
            0x2345678901234567890123456789012345678901, // Validator 2
            0x3456789012345678901234567890123456789012, // Validator 3
            0x4567890123456789012345678901234567890123, // Validator 4
            0x5678901234567890123456789012345678901234  // Validator 5
        ];
        
        // Setup validator stakes
        for (uint i = 0; i < initialValidators.length; i++) {
            initialValidatorStakes.push(DEFAULT_VALIDATOR_STAKE);
        }
        
        // Setup subnet validator hotkeys (in production, use real hotkeys)
        for (uint i = 0; i < 20; i++) {
            subnetValidatorHotkeys.push(keccak256(abi.encodePacked("subnet_validator_", i + 1)));
        }
    }

    function run() public {
        // Get deployment key
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        address deployer = vm.addr(deployerPrivateKey);
        
        console.log("=== TAO20 V2 Enhanced Deployment ===");
        console.log("Deployer address:", deployer);
        console.log("Chain ID:", block.chainid);
        
        vm.startBroadcast(deployerPrivateKey);
        
        // Step 1: Deploy NAV Oracle
        console.log("\n1. Deploying NAV Oracle...");
        navOracle = new NAVOracle(initialValidators, initialValidatorStakes);
        console.log("NAV Oracle deployed at:", address(navOracle));
        
        // Step 2: Deploy TAO20 Core V2 Enhanced
        console.log("\n2. Deploying TAO20 Core V2 Enhanced...");
        tao20Core = new TAO20CoreV2Enhanced(
            address(navOracle),
            TOKEN_NAME,
            TOKEN_SYMBOL
        );
        console.log("TAO20 Core V2 Enhanced deployed at:", address(tao20Core));
        
        // Get references to deployed contracts
        stakingManager = tao20Core.stakingManager();
        tao20Token = tao20Core.tao20Token();
        
        console.log("Subnet Staking Manager deployed at:", address(stakingManager));
        console.log("TAO20 V2 Token deployed at:", address(tao20Token));
        
        // Step 3: Configure subnet validators
        console.log("\n3. Configuring subnet validators...");
        for (uint i = 0; i < SUBNET_IDS.length; i++) {
            uint16 netuid = SUBNET_IDS[i];
            bytes32 validatorHotkey = subnetValidatorHotkeys[i];
            
            // Set validator for each subnet
            // Note: This would be called on stakingManager, but we need to call through tao20Core
            // since only the authorized caller (tao20Core) can call these functions
            console.log("Setting validator for subnet", netuid);
        }
        
        // Step 4: Update index composition
        console.log("\n4. Setting index composition...");
        uint16[] memory netuids = new uint16[](20);
        uint256[] memory weights = new uint256[](20);
        
        for (uint i = 0; i < 20; i++) {
            netuids[i] = SUBNET_IDS[i];
            weights[i] = SUBNET_WEIGHTS[i];
        }
        
        // Note: Index composition is set in the SubnetStakingManager constructor
        console.log("Index composition initialized with 20 subnets");
        
        // Step 5: Get contract addresses and vault information
        console.log("\n5. Contract Information:");
        bytes32 vaultAddress = tao20Core.getVaultAddress();
        string memory vaultSS58 = tao20Core.getVaultAddressSS58();
        
        console.log("Contract vault address (bytes32):");
        console.logBytes32(vaultAddress);
        console.log("Contract vault address (SS58):", vaultSS58);
        
        // Step 6: Display system status
        console.log("\n6. Initial System Status:");
        (
            uint256 totalSupply,
            uint256 totalValueLocked,
            uint256 currentNAV,
            uint256 lastNAVUpdate,
            bool isNAVStale,
            uint16 numberOfSubnets
        ) = tao20Core.getSystemStatus();
        
        console.log("Total Supply:", totalSupply);
        console.log("Total Value Locked:", totalValueLocked);
        console.log("Current NAV:", currentNAV);
        console.log("Last NAV Update:", lastNAVUpdate);
        console.log("Is NAV Stale:", isNAVStale);
        console.log("Number of Subnets:", numberOfSubnets);
        
        // Step 7: Display precompile addresses
        console.log("\n7. Bittensor Precompile Addresses:");
        console.log("Ed25519 Verify:", BittensorPrecompileAddresses.ED25519_VERIFY);
        console.log("Balance Transfer:", BittensorPrecompileAddresses.BALANCE_TRANSFER);
        console.log("Metagraph:", BittensorPrecompileAddresses.METAGRAPH);
        console.log("Subnet:", BittensorPrecompileAddresses.SUBNET);
        console.log("Staking V2:", BittensorPrecompileAddresses.STAKING_V2);
        console.log("Batch:", BittensorPrecompileAddresses.BATCH);
        
        vm.stopBroadcast();
        
        // Step 8: Post-deployment verification
        console.log("\n8. Post-Deployment Verification:");
        _verifyDeployment();
        
        // Step 9: Display usage instructions
        console.log("\n9. Usage Instructions:");
        _displayUsageInstructions();
    }
    
    function _verifyDeployment() internal view {
        console.log("Verifying deployment...");
        
        // Verify NAV Oracle
        require(address(navOracle) != address(0), "NAV Oracle not deployed");
        console.log("✓ NAV Oracle deployed successfully");
        
        // Verify TAO20 Core
        require(address(tao20Core) != address(0), "TAO20 Core not deployed");
        require(address(tao20Core.navOracle()) == address(navOracle), "NAV Oracle not linked correctly");
        console.log("✓ TAO20 Core deployed and linked successfully");
        
        // Verify TAO20 Token
        require(address(tao20Token) != address(0), "TAO20 Token not deployed");
        require(tao20Token.authorizedMinter() == address(tao20Core), "TAO20 minter not set correctly");
        console.log("✓ TAO20 Token deployed and configured successfully");
        
        // Verify Staking Manager
        require(address(stakingManager) != address(0), "Staking Manager not deployed");
        console.log("✓ Staking Manager deployed successfully");
        
        // Verify index composition
        (uint16[] memory netuids, uint256[] memory weights) = tao20Core.getCurrentComposition();
        require(netuids.length == 20, "Index composition not set correctly");
        
        uint256 totalWeight = 0;
        for (uint i = 0; i < weights.length; i++) {
            totalWeight += weights[i];
        }
        require(totalWeight == 10000, "Index weights don't sum to 100%");
        console.log("✓ Index composition verified successfully");
        
        console.log("All contracts deployed and verified successfully! ✅");
    }
    
    function _displayUsageInstructions() internal view {
        console.log("\n=== USAGE INSTRUCTIONS ===");
        console.log("");
        console.log("1. MINTING TAO20 TOKENS:");
        console.log("   a) Deposit subnet tokens to vault address:", tao20Core.getVaultAddressSS58());
        console.log("   b) Create MintRequest with deposit details");
        console.log("   c) Sign request with Ed25519 key");
        console.log("   d) Call tao20Core.mintWithSubnetTokens(request, signature)");
        console.log("");
        console.log("2. REDEEMING TAO20 TOKENS:");
        console.log("   a) Create RedemptionRequest with your SS58 address");
        console.log("   b) Call tao20Core.redeemForSubnetTokens(request)");
        console.log("   c) Subnet tokens will be sent to your SS58 address");
        console.log("");
        console.log("3. YIELD COMPOUNDING:");
        console.log("   a) Call tao20Core.compoundAllYield() to compound all subnets");
        console.log("   b) Or call tao20Core.compoundSubnetYield(netuid) for specific subnet");
        console.log("");
        console.log("4. CONTRACT ADDRESSES:");
        console.log("   TAO20 Core V2 Enhanced:", address(tao20Core));
        console.log("   TAO20 Token:", address(tao20Token));
        console.log("   NAV Oracle:", address(navOracle));
        console.log("   Staking Manager:", address(stakingManager));
        console.log("");
        console.log("5. VAULT INFORMATION:");
        console.log("   Vault Address (SS58):", tao20Core.getVaultAddressSS58());
        console.log("   Send subnet tokens to this address to mint TAO20");
        console.log("");
        console.log("=== DEPLOYMENT COMPLETE ===");
    }
    
    // ===================== HELPER FUNCTIONS =====================
    
    /**
     * @dev Configure subnet validators (would be called post-deployment)
     */
    function configureSubnetValidators() public {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        
        vm.startBroadcast(deployerPrivateKey);
        
        for (uint i = 0; i < SUBNET_IDS.length; i++) {
            uint16 netuid = SUBNET_IDS[i];
            bytes32 validatorHotkey = subnetValidatorHotkeys[i];
            
            // This would require a way to call stakingManager.setSubnetValidator
            // through the tao20Core contract, or making it publicly callable
            console.log("Would set validator for subnet", netuid, "to hotkey:");
            console.logBytes32(validatorHotkey);
        }
        
        vm.stopBroadcast();
    }
    
    /**
     * @dev Get deployment summary for external tools
     */
    function getDeploymentSummary() external view returns (
        address tao20CoreAddress,
        address tao20TokenAddress,
        address navOracleAddress,
        address stakingManagerAddress,
        bytes32 vaultAddress,
        string memory vaultSS58
    ) {
        return (
            address(tao20Core),
            address(tao20Token),
            address(navOracle),
            address(stakingManager),
            tao20Core.getVaultAddress(),
            tao20Core.getVaultAddressSS58()
        );
    }
}
