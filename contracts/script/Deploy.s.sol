// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "forge-std/Script.sol";
import {TAO20Core} from "../src/TAO20Core.sol";
import {ValidatorSet} from "../src/ValidatorSet.sol";
import {StakingNAVOracle} from "../src/StakingNAVOracle.sol";

contract DeployScript is Script {
    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        vm.startBroadcast(deployerPrivateKey);

        console.log("Deploying TAO20 Clean Architecture...");
        console.log("Deployer:", vm.addr(deployerPrivateKey));

        // Deploy ValidatorSet
        ValidatorSet validatorSet = new ValidatorSet(vm.addr(deployerPrivateKey));
        console.log("ValidatorSet deployed at:", address(validatorSet));

        // Deploy StakingNAVOracle
        StakingNAVOracle navOracle = new StakingNAVOracle(address(validatorSet));
        console.log("StakingNAVOracle deployed at:", address(navOracle));

        // Deploy TAO20Core (main contract)
        TAO20Core tao20Core = new TAO20Core(
            address(validatorSet),
            "TAO20 Index Token",
            "TAO20"
        );
        console.log("TAO20Core deployed at:", address(tao20Core));
        console.log("TAO20 token deployed at:", address(tao20Core.tao20Token()));

        // Configure the system
        console.log("Configuring system...");

        // Set up validator
        validatorSet.setValidator(vm.addr(deployerPrivateKey), true);
        
        // Set up basic weights for testing (top 20 subnets with equal weights)
        uint256[] memory netuids = new uint256[](20);
        uint16[] memory weights = new uint16[](20);
        for (uint256 i = 0; i < 20; i++) {
            netuids[i] = i + 1;
            weights[i] = 500; // 5% each
        }
        
        // Mark first seen for all netuids (100 days ago for eligibility)
        for (uint256 i = 0; i < 20; i++) {
            validatorSet.recordFirstSeen(netuids[i], block.timestamp - 100 days);
        }
        
        // Publish initial weightset
        bytes32 hash = keccak256(abi.encode(1, netuids, weights));
        validatorSet.publishWeightSet(1, netuids, weights, hash);
        console.log("Initial weightset published for epoch 1");

        // Set up subnet vault hotkeys (placeholder for testing)
        for (uint256 i = 0; i < 20; i++) {
            bytes32 vaultHotkey = keccak256(abi.encodePacked("vault_hotkey_", i + 1));
            tao20Core.setSubnetVaultHotkey(uint16(i + 1), vaultHotkey);
        }
        console.log("Subnet vault hotkeys configured");

        // Set composition tolerance to 5%
        tao20Core.setCompositionTolerance(500);
        console.log("Composition tolerance set to 5%");

        vm.stopBroadcast();
        
        console.log("\n=== TAO20 CLEAN ARCHITECTURE DEPLOYMENT ===");
        console.log("ValidatorSet:", address(validatorSet));
        console.log("StakingNAVOracle:", address(navOracle));
        console.log("TAO20Core:", address(tao20Core));
        console.log("TAO20 Token:", address(tao20Core.tao20Token()));
        console.log("==========================================");
        
        console.log("\n=== CORE FEATURES ===");
        console.log("Anti-dilution staking mechanism");
        console.log("Ed25519 signature verification");
        console.log("Validator attestation system");
        console.log("Yield compounding");
        console.log("Composition tolerance");
        console.log("Emergency controls");
        console.log("====================");
    }
}