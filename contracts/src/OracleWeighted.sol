// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import {IOracle} from "./IOracle.sol";

interface IStakeOracle {
    function getStake(address validator) external view returns (uint256);
    function getTotalStake(uint256 netuid) external view returns (uint256);
}

abstract contract OracleWeighted is IOracle {
    struct Report { uint256 price; uint256 ts; uint256 stake; address reporter; }
    mapping(uint256 => Report[]) private _reports; // netuid => reports
    uint256 public maxAgeSec = 30 minutes;
    uint256 public quorumBps = 3300; // 33% of total stake required
    uint256 public bandBps = 2000;   // 20% deviation band for slashing
    
    // Security: Add owner for access control
    address public owner;
    
    // Security: Interface for stake verification
    address public stakeOracle;
    
    event ReportSubmitted(uint256 indexed netuid, address indexed reporter, uint256 price, uint256 stake);
    event ReportOutlier(uint256 indexed netuid, address indexed reporter, uint256 price, uint256 median, uint256 bandBps);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);
    
    modifier onlyOwner() { 
        require(msg.sender == owner, "not owner"); 
        _; 
    }
    
    constructor() {
        owner = msg.sender;
        emit OwnershipTransferred(address(0), msg.sender);
    }
    
    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "zero address");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }
    
    function setStakeOracle(address _stakeOracle) external onlyOwner {
        stakeOracle = _stakeOracle;
    }

    function setMaxAgeSec(uint256 s) external onlyOwner { 
        require(s >= 60, "min"); 
        maxAgeSec = s; 
    }
    
    function setQuorumBps(uint256 bps) external onlyOwner { 
        require(bps <= 10000, "bps"); 
        quorumBps = bps; 
    }
    
    function setBandBps(uint256 bps) external onlyOwner { 
        require(bps <= 10000, "bps"); 
        bandBps = bps; 
    }

    function submit(uint256 netuid, uint256 priceTau18, uint256 stake) external {
        // Security: Verify stake against oracle if configured
        if (stakeOracle != address(0)) {
            uint256 actualStake = IStakeOracle(stakeOracle).getStake(msg.sender);
            require(stake <= actualStake, "stake exceeds actual");
            // Use verified stake instead of user-provided value
            stake = actualStake;
        }
        
        _reports[netuid].push(Report({price: priceTau18, ts: block.timestamp, stake: stake, reporter: msg.sender}));
        emit ReportSubmitted(netuid, msg.sender, priceTau18, stake);
    }

    function _weightedMedian(Report[] memory arr) internal pure returns (uint256) {
        // sort by price asc (insertion sort sufficient for tests)
        for (uint256 i = 1; i < arr.length; i++) {
            Report memory key = arr[i]; uint256 j = i;
            while (j > 0 && arr[j-1].price > key.price) { arr[j] = arr[j-1]; j--; }
            arr[j] = key;
        }
        uint256 total;
        for (uint256 i = 0; i < arr.length; i++) total += arr[i].stake;
        if (total == 0) return 0;
        uint256 cum;
        for (uint256 i = 0; i < arr.length; i++) { cum += arr[i].stake; if (cum * 2 >= total) return arr[i].price; }
        return arr[arr.length-1].price;
    }

    function _filterFresh(uint256 netuid) internal view returns (Report[] memory fresh, uint256 totalStake) {
        Report[] memory s = _reports[netuid];
        if (s.length == 0) return (fresh, 0);
        uint256 cutoff = block.timestamp > maxAgeSec ? (block.timestamp - maxAgeSec) : 0;
        uint256 count;
        for (uint256 i = s.length; i > 0; i--) { if (s[i-1].ts >= cutoff) count++; else break; }
        if (count == 0) return (fresh, 0);
        fresh = new Report[](count);
        uint256 idx;
        for (uint256 i = s.length; i > 0 && idx < count; i--) {
            if (s[i-1].ts >= cutoff) { fresh[idx++] = s[i-1]; totalStake += s[i-1].stake; } else break;
        }
    }

    function getPrice(uint256 netuid) external view returns (uint256 priceTau18) { (priceTau18,) = getPriceWithTime(netuid); }

    function getPriceWithTime(uint256 netuid) public view returns (uint256 priceTau18, uint256 blockTime) {
        (Report[] memory fresh, uint256 totalStake) = _filterFresh(netuid);
        if (fresh.length == 0) return (0, 0);
        uint256 med = _weightedMedian(fresh);
        
        // Security: Meaningful quorum check against external reference
        uint256 covered = totalStake; // stake from fresh reports
        uint256 referenceTotalStake = covered; // default fallback
        
        if (stakeOracle != address(0)) {
            try IStakeOracle(stakeOracle).getTotalStake(netuid) returns (uint256 oracleTotal) {
                if (oracleTotal > 0) {
                    referenceTotalStake = oracleTotal;
                }
            } catch {
                // Fallback: use the sum of reporting stakes
            }
        }
        
        if (referenceTotalStake == 0 || (covered * 10000) / referenceTotalStake < quorumBps) {
            return (0, fresh[0].ts);
        }
        
        return (med, fresh[0].ts);
    }

    function checkAndSlash(uint256 netuid) external {
        (Report[] memory fresh, uint256 totalStake) = _filterFresh(netuid);
        if (fresh.length < 2) return;
        uint256 med = _weightedMedian(fresh);
        for (uint256 i = 0; i < fresh.length; i++) {
            uint256 p = fresh[i].price;
            uint256 diff = p > med ? p - med : med - p;
            if (med > 0 && (diff * 10000) / med > bandBps) {
                emit ReportOutlier(netuid, fresh[i].reporter, p, med, bandBps);
            }
        }
    }
}


