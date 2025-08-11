// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "forge-std/Test.sol";
import {ValidatorSet} from "../src/ValidatorSet.sol";
import {WeightsetRegistry} from "../src/WeightsetRegistry.sol";

contract ValidatorSetTest is Test {
    ValidatorSet vs;
    address admin = address(0xA11CE);
    address validator = address(0xB0B);

    function setUp() public {
        vm.warp(block.timestamp + 200 days);
        vm.prank(admin);
        vs = new ValidatorSet(admin);
        vm.prank(admin);
        vs.setValidator(validator, true);
    }

    function _arr(uint256 n) internal pure returns (uint256[] memory, uint16[] memory) {
        uint256[] memory u = new uint256[](20);
        uint16[] memory w = new uint16[](20);
        for (uint256 i = 0; i < 20; i++) { u[i] = i+1; w[i] = uint16(10000/20); }
        return (u, w);
    }

    function testPublishHappyPath() public {
        (uint256[] memory u, uint16[] memory w) = _arr(20);
        // mark first seen 100 days ago
        for (uint256 i = 0; i < 20; i++) { vm.prank(admin); vs.recordFirstSeen(u[i], block.timestamp - 100 days); }
        bytes32 h = keccak256(abi.encode(1, u, w));
        vm.prank(validator);
        vs.publishWeightSet(1, u, w, h);
        (uint256[] memory u2, uint16[] memory w2) = vs.getWeights(1);
        assertEq(u2.length, 20);
        assertEq(w2.length, 20);
        assertEq(vs.currentEpochId(), 1);
    }

    function testRejectIneligible() public {
        (uint256[] memory u, uint16[] memory w) = _arr(20);
        // missing firstSeen for one uid should revert
        bytes32 h = keccak256(abi.encode(1, u, w));
        vm.prank(validator);
        vm.expectRevert("ineligible");
        vs.publishWeightSet(1, u, w, h);
    }

    function testRegistryVerification() public {
        // Set registry and require matching hash
        WeightsetRegistry reg = new WeightsetRegistry();
        vm.prank(admin);
        vs.setRegistry(address(reg));

        (uint256[] memory u, uint16[] memory w) = _arr(20);
        for (uint256 i = 0; i < 20; i++) { vm.prank(admin); vs.recordFirstSeen(u[i], block.timestamp - 100 days); }
        bytes32 h = keccak256(abi.encode(3, u, w));

        // without on-chain publish, should revert registry mismatch
        vm.prank(validator);
        vm.expectRevert("registry mismatch");
        vs.publishWeightSet(3, u, w, h);

        // publish to registry, then succeed
        reg.publish(3, h, "cid", "signer");
        vm.prank(validator);
        vs.publishWeightSet(3, u, w, h);
        assertEq(vs.currentEpochId(), 3);
    }
}

contract ValidatorSetTest2 is Test {
    ValidatorSet vs;
    address admin = address(0xA11CE);
    address v1 = address(0xBEEF);

    function setUp() public {
        vm.warp(block.timestamp + 200 days);
        vs = new ValidatorSet(admin);
        vm.prank(admin);
        vs.setValidator(v1, true);
    }

    function testPublishWeightSet() public {
        uint256 epochId = 1;
        uint256[] memory netuids = new uint256[](20);
        uint16[] memory weights = new uint16[](20);
        for (uint256 i = 0; i < 20; i++) { netuids[i] = i + 1; weights[i] = 500; }
        // mark first seen for eligibility
        for (uint256 i = 0; i < 20; i++) { vm.prank(admin); vs.recordFirstSeen(netuids[i], block.timestamp - 100 days); }
        bytes32 h = keccak256(abi.encode(epochId, netuids, weights));
        vm.prank(v1);
        vs.publishWeightSet(epochId, netuids, weights, h);
        assertEq(vs.currentEpochId(), 1);
    }

    function testRejectBadSum() public {
        uint256 epochId = 2;
        uint256[] memory netuids = new uint256[](20);
        uint16[] memory weights = new uint16[](20);
        for (uint256 i = 0; i < 20; i++) { netuids[i] = i + 1; weights[i] = 400; }
        bytes32 h = keccak256(abi.encode(epochId, netuids, weights));
        vm.prank(v1);
        vm.expectRevert();
        vs.publishWeightSet(epochId, netuids, weights, h);
    }
}


