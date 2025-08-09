// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "forge-std/Test.sol";
import {Router} from "../src/Router.sol";

contract DummyAMM is IAMM {
    function getQuote(uint256, uint256 taoIn) external pure returns (uint256 qtyOut) { return taoIn * 2; }
    function swapTaoForNet(uint256, uint256 taoIn, uint256 minOut, address) external pure returns (uint256 qtyOut) {
        uint256 out = taoIn * 2;
        require(out >= minOut, "slippage");
        return out;
    }
}

contract RouterTest is Test {
    Router r;
    DummyAMM amm;
    function setUp() public { amm = new DummyAMM(); r = new Router(address(amm)); }
    function testQuoteAndSwap() public { uint256 out = r.routeMint(1, 100e18, address(this)); assertEq(out, 200e18); }
}


