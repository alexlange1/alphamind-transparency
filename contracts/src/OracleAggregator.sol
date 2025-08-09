// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import {IOracle} from "./IOracle.sol";

contract OracleAggregator is IOracle {
    struct Sample { uint256 price; uint256 ts; }
    mapping(uint256 => Sample[]) private _samplesByNet; // netuid => sliding window samples
    uint256 public maxSamples = 64;
    uint256 public maxAgeSec = 30 minutes;

    function setMaxSamples(uint256 n) external { require(n > 1 && n <= 256, "range"); maxSamples = n; }
    function setMaxAgeSec(uint256 s) external { require(s >= 60, "min"); maxAgeSec = s; }

    function submit(uint256 netuid, uint256 priceTau18) external {
        _samplesByNet[netuid].push(Sample({price: priceTau18, ts: block.timestamp}));
        if (_samplesByNet[netuid].length > maxSamples) {
            // pop front by shifting window (cheap enough for tests; production would use ring buffer)
            for (uint256 i = 1; i < _samplesByNet[netuid].length; i++) _samplesByNet[netuid][i-1] = _samplesByNet[netuid][i];
            _samplesByNet[netuid].pop();
        }
    }

    function _median(uint256[] memory arr) internal pure returns (uint256) {
        if (arr.length == 0) return 0;
        // insertion sort small arrays
        for (uint256 i = 1; i < arr.length; i++) {
            uint256 key = arr[i]; uint256 j = i;
            while (j > 0 && arr[j-1] > key) { arr[j] = arr[j-1]; j--; }
            arr[j] = key;
        }
        uint256 mid = arr.length / 2;
        if (arr.length % 2 == 1) return arr[mid];
        return (arr[mid-1] + arr[mid]) / 2;
    }

    function getPrice(uint256 netuid) external view returns (uint256 priceTau18) {
        (uint256 p,) = getPriceWithTime(netuid);
        return p;
    }

    function getPriceWithTime(uint256 netuid) public view returns (uint256 priceTau18, uint256 blockTime) {
        Sample[] memory s = _samplesByNet[netuid];
        if (s.length == 0) return (0, 0);
        // Filter by maxAge
        uint256 cutoff = block.timestamp - maxAgeSec;
        uint256 count;
        for (uint256 i = s.length; i > 0; i--) {
            if (s[i-1].ts >= cutoff) count++;
            else break;
        }
        if (count == 0) return (0, s[s.length-1].ts);
        uint256[] memory arr = new uint256[](count);
        uint256 idx;
        for (uint256 i = s.length; i > 0 && idx < count; i--) {
            if (s[i-1].ts >= cutoff) { arr[idx++] = s[i-1].price; blockTime = s[i-1].ts; }
            else break;
        }
        priceTau18 = _median(arr);
    }

    function getTwap(uint256 netuid, uint256 windowSec) external view returns (uint256) {
        Sample[] memory s = _samplesByNet[netuid];
        if (s.length == 0) return 0;
        uint256 cutoff = block.timestamp - windowSec;
        uint256 sum; uint256 cnt;
        for (uint256 i = s.length; i > 0; i--) {
            if (s[i-1].ts >= cutoff) { sum += s[i-1].price; cnt++; }
            else break;
        }
        return cnt == 0 ? 0 : sum / cnt;
    }
}


