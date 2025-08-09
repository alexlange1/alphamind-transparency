// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "forge-std/Test.sol";
import {ValidatorSet} from "../src/ValidatorSet.sol";

contract ValidatorSetTest is Test {
    ValidatorSet vs;
    address admin = address(0xA11CE);
    address v1 = address(0xBEEF);

    function setUp() public {
        vs = new ValidatorSet(admin);
        vm.prank(admin);
        vs.setValidator(v1, true);
    }

    function testPublishWeightSet() public {
        uint256 epochId = 1;
        uint256[] memory netuids = new uint256[](20);
        uint16[] memory weights = new uint16[](20);
        for (uint256 i = 0; i < 20; i++) { netuids[i] = i + 1; weights[i] = 500; }
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


