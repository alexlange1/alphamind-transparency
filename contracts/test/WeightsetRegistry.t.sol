// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import {WeightsetRegistry} from "../src/WeightsetRegistry.sol";

contract WeightsetRegistryTest is Test {
    WeightsetRegistry reg;

    function setUp() public {
        reg = new WeightsetRegistry();
    }

    function testPublishOnce() public {
        uint256 epoch = 1;
        bytes32 sh = bytes32(uint256(0x1234));
        string memory cid = "bafybeihash";
        string memory signer = "5F3sa2TJ...";
        bool ok = reg.publish(epoch, sh, cid, signer);
        assertTrue(ok, "publish ok");
        (uint256 e, bytes32 h, , , , , ) = reg.byEpoch(epoch);
        assertEq(e, epoch);
        assertEq(h, sh);
    }

    function testPublishRevertsIfAlready() public {
        uint256 epoch = 2;
        bytes32 sh = bytes32(uint256(0x55));
        reg.publish(epoch, sh, "cid", "signer");
        vm.expectRevert("already_published");
        reg.publish(epoch, sh, "cid2", "signer2");
    }
}


