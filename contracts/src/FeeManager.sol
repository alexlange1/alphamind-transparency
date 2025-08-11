// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

contract FeeManager {
    address public owner;
    uint256 public txFeesAccruedTao;
    uint256 public mgmtFeesAccruedTao;
    address public alphaToken;
    address public router;
    uint256 public buybackRateBps = 100; // 1% of accrued per call
    uint256 public alphaAccumulated; // tracking only for tests/accounting
    
    // Security: Track authorized fee recorders
    mapping(address => bool) public authorizedRecorders;

    event TxFeeRecorded(uint256 amountTao);
    event MgmtFeeRecorded(uint256 amountTao);
    event BuybackExecuted(uint256 taoSpent, uint256 alphaBought);
    event RecorderAuthorized(address recorder, bool authorized);

    modifier onlyOwner() { require(msg.sender == owner, "not owner"); _; }
    modifier onlyAuthorized() { require(authorizedRecorders[msg.sender] || msg.sender == owner, "not authorized"); _; }

    constructor() { owner = msg.sender; }

    function setAlpha(address a) external onlyOwner { alphaToken = a; }
    function setRouter(address r) external onlyOwner { router = r; }
    function setBuybackRateBps(uint256 bps) external onlyOwner { buybackRateBps = bps; }
    
    // Security: Only authorized recorders can record fees
    function authorizeRecorder(address recorder, bool authorized) external onlyOwner {
        authorizedRecorders[recorder] = authorized;
        emit RecorderAuthorized(recorder, authorized);
    }

    function recordTxFee(uint256 amt) external onlyAuthorized { 
        txFeesAccruedTao += amt; 
        emit TxFeeRecorded(amt); 
    }
    
    function recordMgmtFee(uint256 amt) external onlyAuthorized { 
        mgmtFeesAccruedTao += amt; 
        emit MgmtFeeRecorded(amt); 
    }

    function buyback() external {
        require(router != address(0) && alphaToken != address(0), "cfg");
        uint256 pool = txFeesAccruedTao + mgmtFeesAccruedTao;
        if (pool == 0) return;
        uint256 spend = (pool * buybackRateBps) / 10000;
        // In production, pull TAO from vault/treasury. Here we just decrement and simulate swap via Router
        if (spend > txFeesAccruedTao) {
            uint256 rem = spend - txFeesAccruedTao;
            txFeesAccruedTao = 0;
            mgmtFeesAccruedTao = mgmtFeesAccruedTao > rem ? mgmtFeesAccruedTao - rem : 0;
        } else {
            txFeesAccruedTao -= spend;
        }
        // simulate swap
        try RouterLike(router).buyAlpha(spend, owner) returns (uint256 alphaOut) {
            alphaAccumulated += alphaOut;
            emit BuybackExecuted(spend, alphaOut);
        } catch {
            emit BuybackExecuted(spend, 0);
        }
    }

    function scheduleBuybacks(uint256[] calldata atTimestamps) external onlyOwner {
        // Placeholder: off-chain keepers call buyback when ts reached; keeping for interface completeness
    }
}

interface RouterLike {
    function buyAlpha(uint256 taoIn, address to) external returns (uint256 alphaOut);
}


