// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "forge-std/Script.sol";
import {TAO20Core} from "../src/TAO20Core.sol";
import {ValidatorSet} from "../src/ValidatorSet.sol";
import {StakingNAVOracle} from "../src/StakingNAVOracle.sol";

contract InteractScript is Script {
    
    TAO20Core public tao20Core;
    ValidatorSet public validatorSet;
    StakingNAVOracle public navOracle;
    
    function setUp() external {
        // Load deployed contract addresses from environment or hardcode for testing
        tao20Core = TAO20Core(vm.envAddress("TAO20_CORE_ADDRESS"));
        validatorSet = ValidatorSet(vm.envAddress("VALIDATOR_SET_ADDRESS"));
        navOracle = StakingNAVOracle(vm.envAddress("NAV_ORACLE_ADDRESS"));
    }
    
    function run() external {
        uint256 privateKey = vm.envUint("PRIVATE_KEY");
        vm.startBroadcast(privateKey);

        console.log("=== TAO20 INTERACTION SCRIPT ===");
        console.log("TAO20Core:", address(tao20Core));
        console.log("ValidatorSet:", address(validatorSet));
        console.log("NAVOracle:", address(navOracle));

        // Example: Check current NAV
        uint256 totalValue = tao20Core.getTotalValue();
        uint256 totalSupply = tao20Core.tao20Token().totalSupply();
        uint256 nav = tao20Core.getYieldAdjustedNAV();
        
        console.log("Total Value:", totalValue);
        console.log("Total Supply:", totalSupply);
        console.log("Current NAV:", nav);

        // Example: Check subnet staking info
        for (uint16 i = 1; i <= 5; i++) {
            (uint256 staked, uint256 yield, uint256 lastUpdate, bytes32 vaultHotkey) = 
                tao20Core.getSubnetStakingInfo(i);
            
            console.log("Subnet", i);
            console.log("- Staked:", staked);
            console.log("- Yield:", yield);
            console.log("- LastUpdate:", lastUpdate);
        }

        // Example: Compound yield (anyone can call)
        console.log("Compounding yield...");
        tao20Core.compoundYield();
        console.log("Yield compounded successfully");

        vm.stopBroadcast();
        console.log("==============================");
    }
    
    function testMinting() external {
        uint256 privateKey = vm.envUint("PRIVATE_KEY");
        vm.startBroadcast(privateKey);
        
        console.log("=== TESTING MINTING FLOW ===");
        
        // This would be called after user deposits to Bittensor substrate
        // and validators have attested the deposits
        
        // Example mint request structure (for reference)
        /*
        TAO20Core.SubstrateDeposit[] memory deposits = new TAO20Core.SubstrateDeposit[](2);
        deposits[0] = TAO20Core.SubstrateDeposit({
            blockHash: keccak256("block1"),
            extrinsicIndex: 1,
            userSS58: keccak256("user_ss58_key"),
            netuid: 1,
            amount: 1000e18,
            stakingEpoch: block.timestamp,
            merkleRoot: keccak256("merkle_root")
        });
        
        TAO20Core.MintRequest memory request = TAO20Core.MintRequest({
            recipient: vm.addr(privateKey),
            deposits: deposits,
            merkleProofs: new bytes32[](2),
            nonce: 0,
            deadline: block.timestamp + 1 hours
        });
        
        // User would sign this with their Ed25519 key
        bytes memory signature = ""; // Ed25519 signature
        
        tao20Core.mintTAO20(request, signature);
        */
        
        console.log("Note: Minting requires real Bittensor deposits and Ed25519 signatures");
        console.log("========================");
        
        vm.stopBroadcast();
    }
}