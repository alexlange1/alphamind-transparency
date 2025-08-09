// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

contract ParamRegistry {
    address public owner;
    uint256 public priceBandBps = 2000; // 20%
    uint256 public priceQuorumBps = 3300; // 33%
    uint256 public mgmtAprBps = 100; // 1%
    uint256 public txFeeBps = 20; // 0.2%

    event ParamChanged(bytes32 indexed key, uint256 value);

    modifier onlyOwner() { require(msg.sender == owner, "not owner"); _; }

    constructor() { owner = msg.sender; }

    function setPriceBandBps(uint256 v) external onlyOwner { priceBandBps = v; emit ParamChanged("priceBandBps", v); }
    function setPriceQuorumBps(uint256 v) external onlyOwner { priceQuorumBps = v; emit ParamChanged("priceQuorumBps", v); }
    function setMgmtAprBps(uint256 v) external onlyOwner { mgmtAprBps = v; emit ParamChanged("mgmtAprBps", v); }
    function setTxFeeBps(uint256 v) external onlyOwner { txFeeBps = v; emit ParamChanged("txFeeBps", v); }
}


