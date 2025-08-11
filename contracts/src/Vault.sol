// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import {TAO20} from "./TAO20.sol";
import {IValidatorSet} from "./IValidatorSet.sol";
import {Router} from "./Router.sol";
import {FeeManager} from "./FeeManager.sol";
import {IOracle} from "./IOracle.sol";
import {OracleAggregator} from "./OracleAggregator.sol";
import {ReentrancyGuard} from "./ReentrancyGuard.sol";

contract Vault is ReentrancyGuard {
    TAO20 public immutable token;
    IValidatorSet public validatorSet;
    FeeManager public feeManager;
    Router public router;
    uint256 public txFeeBps = 20; // 0.2%
    IOracle public oracle;
    uint256 public compTolBps; // composition tolerance in bps

    // Netuid -> quantity held (scaled 1e18)
    mapping(uint256 => uint256) public holdings;
    uint256[] public activeNetuids;
    mapping(uint256 => uint256) public netuidIndex; // 0 is not a valid index

    event MintInKind(address indexed account, uint256 minted, uint256[] netuids, uint256[] quantities);
    event RedeemInKind(address indexed account, uint256 burned, uint256[] netuids, uint256[] quantities);
    event MintViaTAO(address indexed account, uint256 taoIn, uint256 minted, uint256 avgSlippageBps);
    event FeesAccrued(uint256 mgmtFeeMinted, uint256 newSupply);
    event Paused(bool paused);
    event AssetPaused(uint256 netuid, bool paused);

    address public owner;
    address public timelock;
    modifier onlyOwner() { require(msg.sender == owner, "not owner"); _; }
    modifier onlyTimelock() { require(msg.sender == timelock, "not timelock"); _; }
    modifier onlyOwnerOrTimelock() { require(msg.sender == owner || msg.sender == timelock, "not authorized"); _; }

    constructor(address _validatorSet) {
        token = new TAO20(address(this));
        validatorSet = IValidatorSet(_validatorSet);
        feeManager = new FeeManager();
        owner = msg.sender;
    }

    bool public paused;
    mapping(uint256 => bool) public assetPaused;
    uint256 public lastMgmtTs;
    uint256 public mgmtAprBps = 100; // 1% APR
    
    // Circuit breaker for emergency stops
    bool public emergencyStop;
    uint256 public lastEmergencyTs;
    uint256 public emergencyCooldown = 1 hours;

    function setTimelock(address _timelock) external onlyOwner { timelock = _timelock; }
    
    // Critical functions requiring timelock
    function setFeeManager(address fm) external onlyOwnerOrTimelock { feeManager = FeeManager(fm); }
    function setRouter(address r) external onlyOwnerOrTimelock { router = Router(r); }
    function setTxFeeBps(uint256 bps) external onlyOwnerOrTimelock { 
        require(bps <= 100, "fee too high"); // Max 1%
        txFeeBps = bps; 
    }
    function setOracle(address o) external onlyOwnerOrTimelock { oracle = IOracle(o); }
    function setMgmtAprBps(uint256 bps) external onlyOwnerOrTimelock { 
        require(bps <= 500, "mgmt fee too high"); // Max 5%
        mgmtAprBps = bps; 
    }
    function setPaused(bool p) external onlyOwner { paused = p; emit Paused(p); }
    function setAssetPaused(uint256 n, bool p) external onlyOwner { assetPaused[n] = p; emit AssetPaused(n, p); }
    function setCompositionToleranceBps(uint256 bps) external onlyOwner { compTolBps = bps; }
    
    function triggerEmergencyStop() external onlyOwner {
        require(!emergencyStop, "already stopped");
        emergencyStop = true;
        lastEmergencyTs = block.timestamp;
        emit Paused(true);
    }
    
    function resumeFromEmergency() external onlyOwner {
        require(emergencyStop, "not stopped");
        require(block.timestamp >= lastEmergencyTs + emergencyCooldown, "cooldown period");
        emergencyStop = false;
        emit Paused(false);
    }

    function mintInKind(uint256[] calldata netuids, uint256[] calldata quantities, address to) external nonReentrant returns (uint256 minted) {
        require(!paused && !emergencyStop, "paused");
        require(netuids.length == quantities.length, "Invalid input lengths");
        // Compute total contributed value using oracle if available (qty * price)
        uint256 totalVal;
        for (uint256 i = 0; i < netuids.length; i++) {
            require(!assetPaused[netuids[i]], "asset paused");
            uint256 p = address(oracle) == address(0) ? 1e18 : oracle.getPrice(netuids[i]);
            require(p > 0, "invalid price");
            
            // Safe math for value calculation
            uint256 value = (quantities[i] * p) / 1e18;
            require(totalVal + value >= totalVal, "overflow");
            totalVal += value;
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
        // Apply tx fee on contributed value
        uint256 fee = (totalVal * txFeeBps) / 10000;
        feeManager.recordTxFee(fee);
        // Calculate minted amount using NAV BEFORE updating holdings
        uint256 preNAV = navTau18();
        if (preNAV == 0) {
            // Bootstrap case: mint 1:1 with contributed net value
            minted = totalVal - fee;
        } else {
            // Standard case: mint based on NAV
            minted = ((totalVal - fee) * 1e18) / preNAV;
        }
        // Update holdings after mint calculation
        for (uint256 i = 0; i < netuids.length; i++) { 
            if (holdings[netuids[i]] == 0 && quantities[i] > 0) {
                addNetuid(netuids[i]);
            }
            holdings[netuids[i]] += quantities[i]; 
        }
        token.mint(to, minted);
        emit MintInKind(to, minted, netuids, quantities);
    }

    function redeemInKind(uint256 amount, address to) external nonReentrant returns (uint256[] memory netuids, uint256[] memory quantities) {
        require(!paused && !emergencyStop, "paused");
        require(to != address(0), "redeem to zero address");
        require(amount > 0, "zero amount");
        require(token.balanceOf(msg.sender) >= amount, "bal");
        // Capture total supply BEFORE burn to compute proportional shares
        uint256 supplyBefore = token.totalSupply();
        token.burn(msg.sender, amount);
        
        uint256 len = activeNetuids.length;
        netuids = new uint256[](len);
        quantities = new uint256[](len);
        
        for (uint256 i = 0; i < len; i++) {
            uint256 netuid = activeNetuids[i];
            uint256 h = holdings[netuid];
            if (h == 0 || assetPaused[netuid]) continue;
            
            uint256 q = (amount * h) / supplyBefore;
            holdings[netuid] = h - q;
            if (holdings[netuid] == 0) {
                removeNetuid(netuid);
            }
            netuids[i] = netuid;
            quantities[i] = q;
        }
        
        emit RedeemInKind(to, amount, netuids, quantities);
    }

    function mintViaTAO(uint256 taoIn, address to) external nonReentrant returns (uint256 minted) {
        require(!paused && !emergencyStop, "paused");
        require(to != address(0), "mint to zero address");
        require(taoIn > 0, "zero amount");
        require(address(router) != address(0), "no router");
        // Snapshot epoch and fetch weights
        uint256 epochSnap = validatorSet.currentEpochId();
        require(epochSnap > 0, "no epoch");
        (uint256[] memory nets, uint16[] memory wBps) = validatorSet.getWeights(epochSnap);
        require(nets.length == 20 && wBps.length == 20, "weights");
        // Validate fee calculation doesn't overflow
        require(taoIn <= type(uint256).max / txFeeBps, "fee overflow");
        uint256 fee = (taoIn * txFeeBps) / 10000;
        require(fee <= taoIn, "fee exceeds input");
        feeManager.recordTxFee(fee);
        uint256 netTao = taoIn - fee;
        require(netTao > 0, "insufficient after fees");
        // NAV per token BEFORE any asset acquisition
        uint256 preNAV = navTau18();
        
        // Aggregate slippage tracking for whitepaper compliance
        uint256 totalWeightedSlippage = 0;
        uint256 totalWeight = 0;
        
        uint256[] memory qtys = new uint256[](nets.length);
        uint256 acquiredValTau = 0;

        // Route across basket
        for (uint256 i = 0; i < nets.length; i++) {
            require(!assetPaused[nets[i]], "asset paused");
            require(validatorSet.currentEpochId() == epochSnap, "epoch changed");
            uint256 alloc = (netTao * wBps[i]) / 10000;
            if (alloc == 0) continue;
            
            // Get pre-trade price for slippage calculation (optional)
            uint256 priceForSlippage = 0;
            uint256 spotTs = 0;
            if (address(oracle) != address(0)) {
                (uint256 p, uint256 ts) = oracle.getPriceWithTime(nets[i]);
                if (p > 0) {
                    spotTs = ts;
                    // Optional staleness check if timestamp present
                    if (ts > 0) {
                        require(block.timestamp - ts <= 300, "price too stale"); // 5 minutes max
                    }
                    // Try TWAP via optional interface; ignore if not implemented
                    uint256 twap = 0;
                    {
                        (bool ok, bytes memory data) = address(oracle).staticcall(abi.encodeWithSignature("getTwap(uint256,uint256)", nets[i], 30 minutes));
                        if (ok && data.length >= 32) {
                            twap = abi.decode(data, (uint256));
                        }
                    }
                    if (twap > 0) {
                        // Additional sanity check: spot vs TWAP deviation
                        uint256 deviation = p > twap ? (p - twap) * 10000 / twap : (twap - p) * 10000 / twap;
                        require(deviation <= 2000, "price deviation too high"); // 20% max
                        priceForSlippage = twap;
                    } else {
                        priceForSlippage = p;
                    }
                }
            }
            
            uint256 qty = router.routeMint(nets[i], alloc, address(this));
            qtys[i] = qty;
            
            // Calculate individual trade slippage for aggregate tracking
            if (priceForSlippage > 0) {
                uint256 expectedQty = (alloc * 1e18) / priceForSlippage;
                uint256 individualSlippageBps = 0;
                
                if (qty < expectedQty) {
                    // Calculate slippage as (expected - actual) / expected * 10000
                    individualSlippageBps = ((expectedQty - qty) * 10000) / expectedQty;
                }
                
                // Add to weighted average calculation
                totalWeightedSlippage += individualSlippageBps * wBps[i];
                totalWeight += wBps[i];
                
                // Individual oracle-based validation
                uint256 routerSlippageBps = Router(address(router)).slippageBps();
                uint256 minQty = expectedQty - ((expectedQty * routerSlippageBps) / 10000);
                require(qty >= minQty, "oracle slippage");
            }

            // Accumulate realized acquired value using latest oracle spot price if available, else fallback to TAO alloc
            if (address(oracle) != address(0)) {
                uint256 spot = oracle.getPrice(nets[i]);
                if (spot > 0 && qty > 0) {
                    acquiredValTau += (qty * spot) / 1e18;
                } else {
                    acquiredValTau += alloc;
                }
            } else {
                // Fallback: assume alloc reflects value in TAO
                acquiredValTau += alloc;
            }
        }

        for(uint256 i = 0; i < nets.length; i++){
            if (holdings[nets[i]] == 0 && qtys[i] > 0) {
                addNetuid(nets[i]);
            }
            holdings[nets[i]] += qtys[i];
        }
        
        // Enforce aggregate 1% slippage limit as per whitepaper Section 3.1
        uint256 avgSlippageBps = 0;
        if (totalWeight > 0) {
            avgSlippageBps = totalWeightedSlippage / totalWeight;
            require(avgSlippageBps <= 100, "aggregate slippage exceeds 1%");
        }
        
        // Proper NAV-based minting calculation using realized acquired value and pre-mint NAV
        if (preNAV == 0) {
            // Bootstrap case: mint 1:1 with realized TAO value acquired
            minted = acquiredValTau;
        } else {
            minted = (acquiredValTau * 1e18) / preNAV;
        }
        token.mint(to, minted);
        
        emit MintViaTAO(to, taoIn, minted, avgSlippageBps);
    }

    function navTau18() public view returns (uint256 nav) {
        uint256 tv = 0;
        for (uint256 i = 0; i < activeNetuids.length; i++) {
            uint256 netuid = activeNetuids[i];
            uint256 q = holdings[netuid];
            if (q == 0) continue;
            uint256 p = address(oracle) == address(0) ? 1e18 : oracle.getPrice(netuid);
            tv += (q * p) / 1e18;
        }
        uint256 s = token.totalSupply();
        if (s == 0) return 0;
        return tv / s;
    }

    function accrueMgmtFee() public returns (uint256 minted) {
        uint256 s = token.totalSupply();
        if (s == 0) { 
            lastMgmtTs = block.timestamp; 
            return 0; 
        }
        
        uint256 last = lastMgmtTs == 0 ? block.timestamp : lastMgmtTs;
        uint256 dt = block.timestamp - last;
        
        // Minimum accrual period to prevent spam
        if (dt < 1 hours || mgmtAprBps == 0) { 
            return 0; 
        }
        
        // Compound interest calculation: (1 + r)^t - 1
        // For small rates, approximate: r * t
        uint256 annualRateBps = mgmtAprBps;
        uint256 periodRateBps = (annualRateBps * dt) / 365 days;
        
        // Cap to prevent overflow and unreasonable fees
        if (periodRateBps > 1000) { // Max 10% in one accrual
            periodRateBps = 1000;
        }
        
        if (periodRateBps == 0) { 
            lastMgmtTs = block.timestamp; 
            return 0; 
        }
        
        // Calculate new tokens to mint to fee manager
        // New supply = old supply * (1 + rate)
        // Tokens to mint = new supply - old supply
        uint256 newSupply = s + (s * periodRateBps) / 10000;
        minted = newSupply - s;
        
        if (minted > 0) {
            // Record TAO-equivalent value of management fee for accounting, using current NAV per token
            uint256 nav = navTau18();
            token.mint(address(feeManager), minted);
            if (nav > 0) {
                uint256 taoEquiv = (minted * nav) / 1e18;
                feeManager.recordMgmtFee(taoEquiv);
            }
            lastMgmtTs = block.timestamp;
            emit FeesAccrued(minted, token.totalSupply());
        }
    }

    function addNetuid(uint256 netuid) internal {
        require(netuidIndex[netuid] == 0, "Netuid already active");
        activeNetuids.push(netuid);
        netuidIndex[netuid] = activeNetuids.length;
    }

    function removeNetuid(uint256 netuid) internal {
        uint256 index = netuidIndex[netuid];
        require(index > 0, "Netuid not active");

        uint256 lastNetuid = activeNetuids[activeNetuids.length - 1];
        activeNetuids[index - 1] = lastNetuid;
        netuidIndex[lastNetuid] = index;

        activeNetuids.pop();
        netuidIndex[netuid] = 0;
    }
}


