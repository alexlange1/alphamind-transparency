// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "forge-std/Test.sol";
import {Vault} from "../src/Vault.sol";
import {ValidatorSet} from "../src/ValidatorSet.sol";
import {Router} from "../src/Router.sol";
import {IOracle} from "../src/IOracle.sol";

contract DummyAMM2 is IAMM {
    function getQuote(uint256, uint256 taoIn) external pure returns (uint256 qtyOut) { return taoIn; }
    function swapTaoForNet(uint256, uint256 taoIn, uint256 minOut, address) external pure returns (uint256 qtyOut) {
        require(taoIn >= minOut, "slip");
        return taoIn; // 1:1
    }
}

contract DummyOracle2 is IOracle {
    mapping(uint256 => uint256) public price;
    constructor() { price[1] = 1e18; price[2] = 1e18; }
    function set(uint256 n, uint256 p) external { price[n] = p; }
    function getPrice(uint256 n) external view returns (uint256) { return price[n]; }
    function getPriceWithTime(uint256 n) external view returns (uint256, uint256) { return (price[n], block.timestamp); }
}

contract FeeAndPauseTest is Test {
    Vault vault;
    ValidatorSet vs;
    Router r;
    DummyOracle2 o;

    function setUp() public {
        vs = new ValidatorSet(address(this));
        vault = new Vault(address(vs));
        r = new Router(address(new DummyAMM2()));
        vault.setRouter(address(r));
        o = new DummyOracle2();
        vault.setOracle(address(o));
        // publish 20 weights of 500 bps each for simplicity
        uint256 epochId = 1;
        uint256[] memory netuids = new uint256[](20);
        uint16[] memory weights = new uint16[](20);
        for (uint256 i = 0; i < 20; i++) { netuids[i] = i + 1; weights[i] = 500; }
        bytes32 h = keccak256(abi.encode(epochId, netuids, weights));
        vs.setValidator(address(this), true);
        vs.publishWeightSet(epochId, netuids, weights, h);
    }

    function testMgmtFeeDrip() public {
        // Mint some supply via in-kind so fee accrual has base
        vault.setCompositionToleranceBps(10000);
        uint256[] memory nets = new uint256[](2);
        uint256[] memory qtys = new uint256[](2);
        nets[0] = 1; nets[1] = 2; qtys[0] = 100e18; qtys[1] = 100e18;
        vault.mintInKind(nets, qtys, address(this));
        uint256 s0 = vault.token().totalSupply();
        // dt = 0 → 0 minted
        uint256 m0 = vault.accrueMgmtFee();
        assertEq(m0, 0);
        // dt > 0 → approx s0 * apr * dt / 365d
        vm.warp(block.timestamp + 10 days);
        uint256 m1 = vault.accrueMgmtFee();
        assertGt(m1, 0);
        // Another call same block → 0
        uint256 m2 = vault.accrueMgmtFee();
        assertEq(m2, 0);
    }

    function testPausableGlobalAndAsset() public {
        vault.setPaused(true);
        uint256[] memory nets = new uint256[](1);
        uint256[] memory qtys = new uint256[](1);
        nets[0] = 1; qtys[0] = 1e18;
        vm.expectRevert(); vault.mintInKind(nets, qtys, address(this));
        vault.setPaused(false);
        vault.setAssetPaused(1, true);
        vm.expectRevert(); vault.mintInKind(nets, qtys, address(this));
        // Other asset should pass
        nets[0] = 2; vm.expectRevert(false); vault.setCompositionToleranceBps(10000); uint256 minted = vault.mintInKind(nets, qtys, address(this));
        assertGt(minted, 0);
    }

    function testCompositionTolerance() public {
        vault.setCompositionToleranceBps(100); // 1%
        // Basket 1:1 across assets, target is uniform 500bps across 20, but only 2 assets provided → each 50% of deposit vs target 5% → outside tol
        uint256[] memory nets = new uint256[](2);
        uint256[] memory qtys = new uint256[](2);
        nets[0] = 1; nets[1] = 2; qtys[0] = 100e18; qtys[1] = 100e18;
        vm.expectRevert(); vault.mintInKind(nets, qtys, address(this));
        // Relax tolerance to allow
        vault.setCompositionToleranceBps(5000); // 50%
        uint256 minted = vault.mintInKind(nets, qtys, address(this));
        assertGt(minted, 0);
    }
}


