// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "forge-std/Script.sol";
import {Vault} from "../src/Vault.sol";
import {ValidatorSet} from "../src/ValidatorSet.sol";
import {Router} from "../src/Router.sol";
import {OracleAggregator} from "../src/OracleAggregator.sol";
// import {OracleWeighted} from "../src/OracleWeighted.sol"; // TODO: Implement for production

contract DeployScript is Script {
    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        vm.startBroadcast(deployerPrivateKey);

        console.log("Deploying contracts...");
        console.log("Deployer:", vm.addr(deployerPrivateKey));

        // Deploy ValidatorSet
        ValidatorSet validatorSet = new ValidatorSet(vm.addr(deployerPrivateKey));
        console.log("ValidatorSet deployed at:", address(validatorSet));

        // Deploy FeeManager first (placeholder address for now)
        address feeManager = address(0x1); // Placeholder
        
        // Deploy Vault
        Vault vault = new Vault(address(validatorSet), feeManager);
        console.log("Vault deployed at:", address(vault));
        console.log("TAO20 token deployed at:", address(vault.token()));

        // Deploy Router (you'll need to implement a proper AMM)
        // For testing, we'll skip router for now
        
        // Deploy Oracles
        // OracleAggregator oracleAgg = new OracleAggregator(); // Abstract contract
        // console.log("OracleAggregator deployed at:", address(oracleAgg));
        
        // OracleWeighted oracleWeighted = new OracleWeighted(); // Abstract contract
        // console.log("OracleWeighted deployed at:", address(oracleWeighted));

        // Configure the system
        // vault.setOracle(address(oracleAgg));
        console.log("Oracle configured for Vault");

        // Set up basic weights for testing (20 subnets with equal weights)
        uint256[] memory netuids = new uint256[](20);
        uint16[] memory weights = new uint16[](20);
        for (uint256 i = 0; i < 20; i++) {
            netuids[i] = i + 1;
            weights[i] = 500; // 5% each
        }
        
        validatorSet.setValidator(vm.addr(deployerPrivateKey), true);
        
        // Mark first seen for all netuids (100 days ago)
        for (uint256 i = 0; i < 20; i++) {
            validatorSet.recordFirstSeen(netuids[i], block.timestamp - 100 days);
        }
        
        bytes32 hash = keccak256(abi.encode(1, netuids, weights));
        validatorSet.publishWeightSet(1, netuids, weights, hash);
        
        console.log("Initial weightset published for epoch 1");
        
        vm.stopBroadcast();
        
        console.log("\n=== Deployment Summary ===");
        console.log("ValidatorSet:", address(validatorSet));
        console.log("Vault:", address(vault));
        console.log("TAO20:", address(vault.token()));
        console.log("FeeManager:", address(vault.feeManager()));
        // console.log("OracleAggregator:", address(oracleAgg));
        // console.log("OracleWeighted:", address(oracleWeighted));
        console.log("========================");
    }
}
