// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import {TAO20} from "./TAO20.sol";
import {IValidatorSet} from "./IValidatorSet.sol";
import {Router} from "./Router.sol";
import {FeeManager} from "./FeeManager.sol";
import {IOracle} from "./IOracle.sol";
import {OracleAggregator} from "./OracleAggregator.sol";

contract Vault {
    TAO20 public immutable token;
    IValidatorSet public validatorSet;
    FeeManager public feeManager;
    Router public router;
    uint256 public txFeeBps = 20; // 0.2%
    IOracle public oracle;
    uint256 public compTolBps; // composition tolerance in bps

    // Netuid -> quantity held (scaled 1e18)
    mapping(uint256 => uint256) public holdings;

    event MintInKind(address indexed account, uint256 minted, uint256[] netuids, uint256[] quantities);
    event RedeemInKind(address indexed account, uint256 burned, uint256[] netuids, uint256[] quantities);
    event FeesAccrued(uint256 mgmtFeeMinted, uint256 newSupply);
    event Paused(bool paused);
    event AssetPaused(uint256 netuid, bool paused);

    modifier onlyFeeManager() { require(msg.sender == address(feeManager), "not fee mgr"); _; }

    constructor(address _validatorSet) {
        token = new TAO20(address(this));
        validatorSet = IValidatorSet(_validatorSet);
        feeManager = new FeeManager();
    }

    bool public paused;
    mapping(uint256, bool) public assetPaused;
    uint256 public lastMgmtTs;
    uint256 public mgmtAprBps = 100; // 1% APR

    function setFeeManager(address fm) external onlyFeeManager { feeManager = FeeManager(fm); }
    function setRouter(address r) external onlyFeeManager { router = Router(r); }
    function setTxFeeBps(uint256 bps) external onlyFeeManager { txFeeBps = bps; }
    function setOracle(address o) external onlyFeeManager { oracle = IOracle(o); }
    function setMgmtAprBps(uint256 bps) external onlyFeeManager { mgmtAprBps = bps; }
    function setPaused(bool p) external onlyFeeManager { paused = p; emit Paused(p); }
    function setAssetPaused(uint256 n, bool p) external onlyFeeManager { assetPaused[n] = p; emit AssetPaused(n, p); }
    function setCompositionToleranceBps(uint256 bps) external onlyFeeManager { compTolBps = bps; }

    function mintInKind(uint256[] calldata netuids, uint256[] calldata quantities, address to) external returns (uint256 minted) {
        require(!paused, "paused");
        require(netuids.length == quantities.length, "len");
        // Compute total contributed value using oracle if available (qty * price)
        uint256 totalVal;
        for (uint256 i = 0; i < netuids.length; i++) {
            require(!assetPaused[netuids[i]], "asset paused");
            uint256 p = address(oracle) == address(0) ? 1e18 : oracle.getPrice(netuids[i]);
            totalVal += (quantities[i] * p) / 1e18;
        }
        // Enforce composition tolerance if weights available
        if (compTolBps > 0) {
            (uint256[] memory nets, uint16[] memory wBps) = validatorSet.getWeights(validatorSet.currentEpochId());
            require(nets.length == 20 && wBps.length == 20, "weights");
            // Map netuid->target bps
            for (uint256 i = 0; i < netuids.length; i++) {
                uint256 nid = netuids[i];
                // find in weights (O(20))
                uint16 target = 0;
                for (uint256 j = 0; j < nets.length; j++) if (nets[j] == nid) { target = wBps[j]; break; }
                // if asset not in index, reject
                require(target > 0, "asset not in index");
                uint256 p = address(oracle) == address(0) ? 1e18 : oracle.getPrice(nid);
                uint256 val = (quantities[i] * p) / 1e18;
                uint256 shareBps = totalVal == 0 ? 0 : (val * 10000) / totalVal;
                uint256 diff = shareBps > target ? shareBps - target : target - shareBps;
                require(diff <= compTolBps, "composition");
            }
        }
        // Update holdings and compute value for fee/mint baseline (use totalVal)
        for (uint256 i = 0; i < netuids.length; i++) { holdings[netuids[i]] += quantities[i]; }
        uint256 val = totalVal;
        // Apply tx fee
        uint256 fee = (val * txFeeBps) / 10000;
        feeManager.recordTxFee(fee);
        minted = val - fee; // placeholder: real impl would use prices & NAV
        token.mint(to, minted);
        emit MintInKind(to, minted, netuids, quantities);
    }

    function redeemInKind(uint256 amount, address to) external returns (uint256[] memory netuids, uint256[] memory quantities) {
        require(!paused, "paused");
        require(token.balanceOf(msg.sender) >= amount, "bal");
        token.burn(msg.sender, amount);
        // Pro-rata across all holdings
        // Iterate a bounded window for demo; production would track active set
        uint256 capacity = 0;
        for (uint256 i = 0; i < 1000; i++) if (holdings[i] > 0 && !assetPaused[i]) capacity++;
        netuids = new uint256[](capacity);
        quantities = new uint256[](capacity);
        uint256 idx;
        for (uint256 i = 0; i < 1000; i++) {
            uint256 h = holdings[i];
            if (h == 0 || assetPaused[i]) continue;
            // pro-rata quantity = amount / totalSupply * holdings[i]
            uint256 q = (amount * h) / token.totalSupply();
            holdings[i] = h - q;
            netuids[idx] = i;
            quantities[idx] = q;
            idx++;
        }
        emit RedeemInKind(to, amount, netuids, quantities);
    }

    function mintViaTAO(uint256 taoIn, address to) external returns (uint256 minted) {
        require(!paused, "paused");
        require(address(router) != address(0), "no router");
        // Snapshot epoch and fetch weights
        uint256 epochSnap = validatorSet.currentEpochId();
        (uint256[] memory nets, uint16[] memory wBps) = validatorSet.getWeights(epochSnap);
        require(nets.length == 20 && wBps.length == 20, "weights");
        uint256 fee = (taoIn * txFeeBps) / 10000;
        feeManager.recordTxFee(fee);
        uint256 netTao = taoIn - fee;
        // Route across basket
        for (uint256 i = 0; i < nets.length; i++) {
            require(!assetPaused[nets[i]], "asset paused");
            require(validatorSet.currentEpochId() == epochSnap, "epoch changed");
            uint256 alloc = (netTao * wBps[i]) / 10000;
            if (alloc == 0) continue;
            uint256 qty = router.routeMint(nets[i], alloc, address(this));
            // Additional oracle-based slippage guard: qty should be >= alloc / price * (1 - router.slippageBps)
            if (address(oracle) != address(0)) {
                (uint256 p, uint256 ts) = oracle.getPriceWithTime(nets[i]);
                // Quorum gating: price 0 means no quorum/fresh price
                require(p > 0, "oracle quorum");
                if (p > 0) {
                    uint256 expQty = (alloc * 1e18) / p;
                    // prefer TWAP if available and fresher
                    uint256 twap = OracleAggregator(address(oracle)).getTwap(nets[i], 30 minutes);
                    if (twap > 0) { expQty = (alloc * 1e18) / twap; }
                    uint256 minQty = expQty - ((expQty * Router(address(router)).slippageBps()) / 10000);
                    require(qty >= minQty, "oracle slippage");
                }
            }
            holdings[nets[i]] += qty;
            // Convert alloc TAO to TAO20 minted based on NAV proxy using oracle price
            // Simplification: 1 TAO of value mints 1 TAO20 unit
            minted += alloc;
        }
        token.mint(to, minted);
    }

    function navTau18() public view returns (uint256 nav) {
        uint256 tv = 0;
        for (uint256 i = 0; i < 1000; i++) {
            uint256 q = holdings[i];
            if (q == 0) continue;
            uint256 p = address(oracle) == address(0) ? 1e18 : oracle.getPrice(i);
            tv += (q * p) / 1e18;
        }
        uint256 s = token.totalSupply();
        if (s == 0) return 0;
        return tv / s;
    }

    function accrueMgmtFee() public returns (uint256 minted) {
        uint256 s = token.totalSupply();
        if (s == 0) { lastMgmtTs = block.timestamp; return 0; }
        uint256 last = lastMgmtTs == 0 ? block.timestamp : lastMgmtTs;
        uint256 dt = block.timestamp - last;
        if (dt == 0 || mgmtAprBps == 0) { lastMgmtTs = block.timestamp; return 0; }
        // APR per-second (linear approximation)
        uint256 feeBps = (mgmtAprBps * dt) / 365 days;
        if (feeBps == 0) { lastMgmtTs = block.timestamp; return 0; }
        minted = (s * feeBps) / 10000;
        token.mint(address(feeManager), minted);
        lastMgmtTs = block.timestamp;
        emit FeesAccrued(minted, token.totalSupply());
    }
}


