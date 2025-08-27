// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "forge-std/Script.sol";
import {ValidatorSet} from "../src/ValidatorSet.sol";
import {TAO20Index} from "../src/TAO20Index.sol";

contract MinimalDeployScript is Script {
    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        vm.startBroadcast(deployerPrivateKey);

        console.log("Deploying minimal contracts for testing...");
        console.log("Deployer:", vm.addr(deployerPrivateKey));

        // Deploy ValidatorSet
        ValidatorSet validatorSet = new ValidatorSet(vm.addr(deployerPrivateKey));
        console.log("ValidatorSet deployed at:", address(validatorSet));

        // Deploy TAO20Index (simpler contract for testing)
        TAO20Index tao20Index = new TAO20Index();
        console.log("TAO20Index deployed at:", address(tao20Index));

        // Set up basic weights for testing (20 subnets with equal weights)
        uint256[] memory netuids = new uint256[](20);
        uint256[] memory weights = new uint256[](20);
        for (uint256 i = 0; i < 20; i++) {
            netuids[i] = i + 1;
            weights[i] = 1e18 / 20; // Equal weight (5% each)
        }
        
        validatorSet.setValidator(vm.addr(deployerPrivateKey), true);
        
        // Mark first seen for all netuids (100 days ago)
        for (uint256 i = 0; i < 20; i++) {
            validatorSet.recordFirstSeen(netuids[i], block.timestamp - 100 days);
        }
        
        uint16[] memory weightsBps = new uint16[](20);
        for (uint256 i = 0; i < 20; i++) {
            weightsBps[i] = 500; // 5% each in basis points
        }
        
        bytes32 hash = keccak256(abi.encode(1, netuids, weightsBps));
        validatorSet.publishWeightSet(1, netuids, weightsBps, hash);
        
        // Update TAO20Index with the same weights
        tao20Index.updateWeights(netuids, weights);
        
        console.log("Initial weightset published for epoch 1");
        
        vm.stopBroadcast();
        
        console.log("\n=== Minimal Deployment Summary ===");
        console.log("ValidatorSet:", address(validatorSet));
        console.log("TAO20Index:", address(tao20Index));
        console.log("=====================================");
    }
}
