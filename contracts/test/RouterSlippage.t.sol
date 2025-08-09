// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "forge-std/Test.sol";
import {Router, IAMM, IBuybackAMM} from "../src/Router.sol";

contract BadAMM is IAMM, IBuybackAMM {
    function getQuote(uint256, uint256 taoIn) external pure returns (uint256 qtyOut) { return taoIn; }
    function swapTaoForNet(uint256, uint256 taoIn, uint256 minOut, address) external pure returns (uint256 qtyOut) {
        uint256 out = taoIn / 2; // heavy slippage
        require(out >= minOut, "slippage");
        return out;
    }
    function getQuoteAlpha(uint256 taoIn) external pure returns (uint256 alphaOut) { return taoIn; }
    function swapTaoForAlpha(uint256 taoIn, uint256 minOut, address) external pure returns (uint256 alphaOut) {
        uint256 out = taoIn / 2;
        require(out >= minOut, "slippage");
        return out;
    }
}

contract RouterSlippageTest is Test {
    Router r;
    BadAMM amm;
    function setUp() public { amm = new BadAMM(); r = new Router(address(amm)); r.setBuybackAmm(address(amm)); }
    function testBuybackSlippageGuard() public {
        r.setSlippageBps(100); // 1%
        vm.expectRevert(); r.buyAlpha(100e18, address(this));
    }
}


