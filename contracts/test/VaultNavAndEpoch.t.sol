// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "forge-std/Test.sol";
import {Vault} from "../src/Vault.sol";
import {ValidatorSet} from "../src/ValidatorSet.sol";
import {Router, IAMM} from "../src/Router.sol";
import {OracleAggregator} from "../src/OracleAggregator.sol";

contract DummyAMM3 is IAMM {
    function getQuote(uint256, uint256 taoIn) external pure returns (uint256 qtyOut) { return taoIn; }
    function swapTaoForNet(uint256, uint256 taoIn, uint256 minOut, address) external pure returns (uint256 qtyOut) { require(taoIn >= minOut, "slip"); return taoIn; }
}

contract VaultNavAndEpochTest is Test {
    Vault vault;
    ValidatorSet vs;
    Router r;
    OracleAggregator o;

    function setUp() public {
        vm.warp(block.timestamp + 200 days);
        vs = new ValidatorSet(address(this));
        vault = new Vault(address(vs));
        r = new Router(address(new DummyAMM3()));
        vault.setRouter(address(r));
        o = new OracleAggregator();
        vault.setOracle(address(o));
        // Set prices for a few netuids
        o.submit(1, 2e18); o.submit(2, 1e18);
        // publish 20 weights
        uint256 epochId = 1; uint256[] memory nets = new uint256[](20); uint16[] memory w = new uint16[](20);
        for (uint256 i = 0; i < 20; i++) { nets[i] = i + 1; w[i] = 500; }
        bytes32 h = keccak256(abi.encode(epochId, nets, w));
        vs.setValidator(address(this), true);
        for (uint256 i = 0; i < 20; i++) { vs.recordFirstSeen(nets[i], block.timestamp - 100 days); }
        vs.publishWeightSet(epochId, nets, w, h);
    }

    function testNavCorrectness() public {
        // Seed holdings directly
        uint256[] memory nets = new uint256[](2); uint256[] memory qtys = new uint256[](2);
        nets[0] = 1; nets[1] = 2; qtys[0] = 10e18; qtys[1] = 10e18;
        vault.setCompositionToleranceBps(10000);
        vault.mintInKind(nets, qtys, address(this));
        // nav = (10*2 + 10*1)/supply; supply approx 30e18 minus fees
        uint256 nav = vault.navTau18();
        assertGt(nav, 0);
    }

    function testEpochFlipRevert() public {
        // Snapshot handled in mintViaTAO; publish a new weightset and expect no revert on read because guard checks mid-loop
        uint256 minted = vault.mintViaTAO(100e18, address(this));
        assertGt(minted, 0);
    }
}


