// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "forge-std/Script.sol";
import "../src/TAO20Index.sol";

contract DeployTAO20Script is Script {
    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        
        vm.startBroadcast(deployerPrivateKey);
        
        // Deploy TAO20 Index contract
        TAO20Index tao20Index = new TAO20Index();
        
        console.log("TAO20 Index deployed at:", address(tao20Index));
        
        // Initialize with top 20 subnets (placeholder weights)
        uint256[] memory subnets = new uint256[](20);
        uint256[] memory weights = new uint256[](20);
        
        // Initialize with equal weights for top 20 subnets
        for (uint256 i = 0; i < 20; i++) {
            subnets[i] = i + 1; // netuids 1-20
            weights[i] = 1e18 / 20; // Equal weight (5% each)
        }
        
        // Update weights
        tao20Index.updateWeights(subnets, weights);
        
        console.log("TAO20 Index initialized with top 20 subnets");
        
        vm.stopBroadcast();
    }
}
