// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "forge-std/Test.sol";
import {OracleAggregator} from "../src/OracleAggregator.sol";

contract OracleAggregatorTest is Test {
    OracleAggregator o;
    function setUp() public { o = new OracleAggregator(); }
    function testMedianAndStaleness() public {
        o.submit(1, 10e18); o.submit(1, 11e18); o.submit(1, 9e18);
        (uint256 p, uint256 t) = o.getPriceWithTime(1);
        assertEq(p, 10e18);
        vm.warp(block.timestamp + 3600);
        (uint256 p2, uint256 t2) = o.getPriceWithTime(1);
        assertEq(p2, 0); // stale
    }
}


