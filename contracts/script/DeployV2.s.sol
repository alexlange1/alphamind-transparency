// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "forge-std/Script.sol";
import "../src/TAO20CoreV2.sol";
import "../src/TAO20V2.sol";
import "../src/NAVOracle.sol";
import "../src/StakingManager.sol";

/**
 * @title DeployV2
 * @dev Deployment script for TAO20 V2 architecture
 */
contract DeployV2 is Script {
    
    // ===================== CONFIGURATION =====================
    
    string constant TOKEN_NAME = "TAO20 Index Token V2";
    string constant TOKEN_SYMBOL = "TAO20";
    
    // Default validators for initial setup (placeholder hotkeys)
    bytes32 constant DEFAULT_VALIDATOR_1 = 0x1111111111111111111111111111111111111111111111111111111111111111;
    bytes32 constant DEFAULT_VALIDATOR_2 = 0x2222222222222222222222222222222222222222222222222222222222222222;
    bytes32 constant DEFAULT_VALIDATOR_3 = 0x3333333333333333333333333333333333333333333333333333333333333333;
    
    // Initial subnet composition (top 3 for testing)
    uint16[] initialNetuids = [1, 2, 3];
    uint256[] initialWeights = [5000, 3000, 2000]; // 50%, 30%, 20%
    
    // Oracle validators (placeholder addresses)
    address constant ORACLE_VALIDATOR_1 = 0x1000000000000000000000000000000000000001;
    address constant ORACLE_VALIDATOR_2 = 0x2000000000000000000000000000000000000002;
    address constant ORACLE_VALIDATOR_3 = 0x3000000000000000000000000000000000000003;
    
    uint256 constant VALIDATOR_STAKE = 1000e18; // 1000 TAO stake per validator

    // ===================== DEPLOYMENT =====================
    
    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        
        vm.startBroadcast(deployerPrivateKey);
        
        console.log("=== Deploying TAO20 V2 Architecture ===");
        console.log("Deployer:", vm.addr(deployerPrivateKey));
        console.log("Chain ID:", block.chainid);
        console.log("");
        
        // 1. Deploy NAV Oracle
        console.log("1. Deploying NAV Oracle...");
        NAVOracle navOracle = new NAVOracle();
        console.log("NAV Oracle deployed at:", address(navOracle));
        
        // 2. Deploy Staking Manager
        console.log("2. Deploying Staking Manager...");
        StakingManager stakingManager = new StakingManager();
        console.log("Staking Manager deployed at:", address(stakingManager));
        
        // 3. Deploy TAO20 Core (which will deploy the token)
        console.log("3. Deploying TAO20 Core...");
        TAO20CoreV2 tao20Core = new TAO20CoreV2(
            address(navOracle),
            address(stakingManager),
            TOKEN_NAME,
            TOKEN_SYMBOL
        );
        console.log("TAO20 Core deployed at:", address(tao20Core));
        
        // 4. Get TAO20 token address
        address tao20Token = address(tao20Core.tao20Token());
        console.log("TAO20 Token deployed at:", tao20Token);
        
        // 5. Setup Oracle Validators
        console.log("4. Setting up Oracle Validators...");
        navOracle.registerValidator(ORACLE_VALIDATOR_1, VALIDATOR_STAKE);
        navOracle.registerValidator(ORACLE_VALIDATOR_2, VALIDATOR_STAKE);
        navOracle.registerValidator(ORACLE_VALIDATOR_3, VALIDATOR_STAKE);
        console.log("Oracle validators registered");
        
        // 6. Setup Staking Validators
        console.log("5. Setting up Staking Validators...");
        stakingManager.setDefaultValidator(1, DEFAULT_VALIDATOR_1);
        stakingManager.setDefaultValidator(2, DEFAULT_VALIDATOR_2);
        stakingManager.setDefaultValidator(3, DEFAULT_VALIDATOR_3);
        console.log("Default validators set");
        
        // 7. Setup Initial Composition
        console.log("6. Setting up Initial Composition...");
        stakingManager.updateComposition(initialNetuids, initialWeights);
        console.log("Initial composition set");
        
        vm.stopBroadcast();
        
        // ===================== DEPLOYMENT SUMMARY =====================
        
        console.log("");
        console.log("=== Deployment Summary ===");
        console.log("NAV Oracle:      ", address(navOracle));
        console.log("Staking Manager: ", address(stakingManager));
        console.log("TAO20 Core:      ", address(tao20Core));
        console.log("TAO20 Token:     ", tao20Token);
        console.log("");
        
        console.log("=== Configuration ===");
        console.log("Token Name:      ", TOKEN_NAME);
        console.log("Token Symbol:    ", TOKEN_SYMBOL);
        console.log("Oracle Validators:", 3);
        console.log("Initial Subnets: ", initialNetuids.length);
        console.log("");
        
        console.log("=== Next Steps ===");
        console.log("1. Verify contracts on block explorer");
        console.log("2. Setup real validator hotkeys");
        console.log("3. Update oracle validators with real addresses");
        console.log("4. Configure proper subnet composition");
        console.log("5. Test minting and redeeming functionality");
        
        // ===================== SAVE DEPLOYMENT INFO =====================
        
        string memory deploymentInfo = string(abi.encodePacked(
            "{\n",
            '  "chainId": ', vm.toString(block.chainid), ",\n",
            '  "navOracle": "', vm.toString(address(navOracle)), '",\n',
            '  "stakingManager": "', vm.toString(address(stakingManager)), '",\n',
            '  "tao20Core": "', vm.toString(address(tao20Core)), '",\n',
            '  "tao20Token": "', vm.toString(tao20Token), '",\n',
            '  "tokenName": "', TOKEN_NAME, '",\n',
            '  "tokenSymbol": "', TOKEN_SYMBOL, '",\n',
            '  "deployedAt": ', vm.toString(block.timestamp), "\n",
            "}"
        ));
        
        vm.writeFile("./deployment-v2.json", deploymentInfo);
        console.log("Deployment info saved to deployment-v2.json");
    }
    
    // ===================== HELPER FUNCTIONS =====================
    
    /**
     * @dev Verify deployment was successful
     */
    function verifyDeployment(
        address navOracle,
        address stakingManager,
        address tao20Core,
        address tao20Token
    ) external view {
        console.log("=== Verifying Deployment ===");
        
        // Check NAV Oracle
        (uint256 nav, , , , , bool isStale) = NAVOracle(navOracle).getOracleStatus();
        console.log("NAV Oracle - Current NAV:", nav);
        console.log("NAV Oracle - Is Stale:", isStale);
        
        // Check Staking Manager
        uint256 totalStaked = StakingManager(stakingManager).getTotalStaked();
        console.log("Staking Manager - Total Staked:", totalStaked);
        
        // Check TAO20 Core
        uint256 currentNAV = TAO20CoreV2(tao20Core).getCurrentNAV();
        console.log("TAO20 Core - Current NAV:", currentNAV);
        
        // Check TAO20 Token
        (string memory name, string memory symbol, , uint256 supply, ) = 
            TAO20V2(tao20Token).getTokenInfo();
        console.log("TAO20 Token - Name:", name);
        console.log("TAO20 Token - Symbol:", symbol);
        console.log("TAO20 Token - Supply:", supply);
        
        console.log("Deployment verification complete");
    }
}
