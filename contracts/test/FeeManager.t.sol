// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "forge-std/Test.sol";
import {FeeManager} from "../src/FeeManager.sol";
import {Router, IBuybackAMM} from "../src/Router.sol";

contract BBAMM is IBuybackAMM {
    function getQuoteAlpha(uint256 taoIn) external pure returns (uint256) { return taoIn; }
    function swapTaoForAlpha(uint256 taoIn, uint256 minOut, address) external pure returns (uint256) {
        require(taoIn >= minOut, "slip");
        return taoIn;
    }
}

contract FeeManagerTest is Test {
    FeeManager fm;
    Router r;
    function setUp() public {
        fm = new FeeManager();
        r = new Router(address(0));
        r.setBuybackAmm(address(new BBAMM()));
        fm.setRouter(address(r));
        fm.setAlpha(address(0xA1));
    }

    function testBuybackAccounting() public {
        vm.prank(address(this));
        fm.recordTxFee(100e18);
        fm.recordMgmtFee(50e18);
        fm.setBuybackRateBps(1000); // 10%
        fm.buyback();
        // alphaAccumulated should be approx 10% of pool (150e18 * 10% = 15e18)
        assertEq(fm.alphaAccumulated(), 15e18);
    }
}


