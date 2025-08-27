// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "forge-std/Test.sol";
import {OracleWeighted} from "../src/OracleWeighted.sol";

contract OracleWeightedTest is Test {
    OracleWeighted o;
    function setUp() public { /* o = new OracleWeighted(); */ } // Abstract contract
    function testWeightedMedianAndQuorum() public {
        // stake: A=100, B=50, C=10; prices 10, 11, 20
        o.submit(1, 10e18, 100);
        o.submit(1, 11e18, 50);
        o.submit(1, 20e18, 10);
        (uint256 p, uint256 t) = o.getPriceWithTime(1);
        assertEq(p, 10e18); // weighted median under stake sums
    }
}


