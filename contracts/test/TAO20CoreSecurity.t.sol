// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "forge-std/Test.sol";
import {TAO20Core} from "../src/TAO20Core.sol";

// Mock ValidatorSet for testing
contract MockValidatorSet {
    mapping(address => bool) public isValidator;
    
    function setValidator(address validator, bool status) external {
        isValidator[validator] = status;
    }
    
    function currentEpochId() external pure returns (uint256) {
        return 1;
    }
    
    function getWeights(uint256) external pure returns (uint256[] memory netuids, uint16[] memory weights) {
        netuids = new uint256[](2);
        weights = new uint16[](2);
        netuids[0] = 1;
        netuids[1] = 2;
        weights[0] = 5000;
        weights[1] = 5000;
    }
}

contract TAO20CoreSecurityTest is Test {
    TAO20Core public tao20Core;
    MockValidatorSet public mockValidatorSet;
    
    address owner = address(0x1);
    address validator = address(0x2);
    address user = address(0x3);
    address attacker = address(0x4);
    
    function setUp() public {
        vm.startPrank(owner);
        
        // Deploy Mock ValidatorSet
        mockValidatorSet = new MockValidatorSet();
        
        // Deploy TAO20Core
        tao20Core = new TAO20Core(
            address(mockValidatorSet),
            "TAO20 Index Token",
            "TAO20"
        );
        
        // Set up validator
        mockValidatorSet.setValidator(validator, true);
        
        vm.stopPrank();
    }
    
    function testEmptyDepositsArrayReverts() public {
        TAO20Core.SubstrateDeposit[] memory emptyDeposits = new TAO20Core.SubstrateDeposit[](0);
        
        TAO20Core.MintRequest memory request = TAO20Core.MintRequest({
            recipient: user,
            deposits: emptyDeposits,
            merkleProofs: new bytes32[](0),
            nonce: 0,
            deadline: block.timestamp + 1 hours
        });
        
        bytes memory signature = "dummy_signature_64_bytes_long_dummy_signature_64_bytes_long";
        
        vm.prank(user);
        vm.expectRevert("Empty deposits array");
        tao20Core.mintTAO20(request, signature);
    }
    
    function testMixedUserDepositsRevert() public {
        // Create deposits from two different users
        TAO20Core.SubstrateDeposit[] memory mixedDeposits = new TAO20Core.SubstrateDeposit[](2);
        
        // First deposit from user
        mixedDeposits[0] = TAO20Core.SubstrateDeposit({
            blockHash: keccak256("block1"),
            extrinsicIndex: 1,
            userSS58: keccak256("user_ss58_key"),
            netuid: 1,
            amount: 1000e18,
            stakingEpoch: block.timestamp,
            merkleRoot: keccak256("merkle1")
        });
        
        // Second deposit from attacker (different userSS58)
        mixedDeposits[1] = TAO20Core.SubstrateDeposit({
            blockHash: keccak256("block2"),
            extrinsicIndex: 2,
            userSS58: keccak256("attacker_ss58_key"), // Different user!
            netuid: 2,
            amount: 1000e18,
            stakingEpoch: block.timestamp,
            merkleRoot: keccak256("merkle2")
        });
        
        TAO20Core.MintRequest memory request = TAO20Core.MintRequest({
            recipient: attacker,
            deposits: mixedDeposits,
            merkleProofs: new bytes32[](2),
            nonce: 0,
            deadline: block.timestamp + 1 hours
        });
        
        bytes memory signature = "dummy_signature_64_bytes_long_dummy_signature_64_bytes_long";
        
        vm.prank(attacker);
        vm.expectRevert("All deposits must belong to same user");
        tao20Core.mintTAO20(request, signature);
    }
    
    function testSameUserDepositsPassValidation() public {
        // Create deposits from the same user
        TAO20Core.SubstrateDeposit[] memory sameUserDeposits = new TAO20Core.SubstrateDeposit[](2);
        
        bytes32 userSS58 = keccak256("user_ss58_key");
        
        sameUserDeposits[0] = TAO20Core.SubstrateDeposit({
            blockHash: keccak256("block1"),
            extrinsicIndex: 1,
            userSS58: userSS58,
            netuid: 1,
            amount: 1000e18,
            stakingEpoch: block.timestamp,
            merkleRoot: keccak256("merkle1")
        });
        
        sameUserDeposits[1] = TAO20Core.SubstrateDeposit({
            blockHash: keccak256("block2"),
            extrinsicIndex: 2,
            userSS58: userSS58, // Same user
            netuid: 2,
            amount: 1000e18,
            stakingEpoch: block.timestamp,
            merkleRoot: keccak256("merkle2")
        });
        
        TAO20Core.MintRequest memory request = TAO20Core.MintRequest({
            recipient: user,
            deposits: sameUserDeposits,
            merkleProofs: new bytes32[](2),
            nonce: 0,
            deadline: block.timestamp + 1 hours
        });
        
        // This should now fail with signature verification, but not with the mixed user check
        bytes memory signature = "dummy_signature_64_bytes_long_dummy_signature_64_bytes_long";
        
        vm.prank(user);
        vm.expectRevert("Invalid signature length");
        tao20Core.mintTAO20(request, signature);
    }
}
