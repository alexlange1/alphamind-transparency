// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

interface IAMM {
    function getQuote(uint256 netuid, uint256 taoIn) external view returns (uint256 qtyOut);
    function swapTaoForNet(uint256 netuid, uint256 taoIn, uint256 minOut, address to) external returns (uint256 qtyOut);
}

interface IBuybackAMM {
    function getQuoteAlpha(uint256 taoIn) external view returns (uint256 alphaOut);
    function swapTaoForAlpha(uint256 taoIn, uint256 minOut, address to) external returns (uint256 alphaOut);
}

contract Router {
    address public owner;
    IAMM public amm;
    IBuybackAMM public buybackAmm;
    uint256 public slippageBps = 100; // 1%

    event SlippageUpdated(uint256 bps);

    modifier onlyOwner() { require(msg.sender == owner, "not owner"); _; }

    constructor(address _amm) { owner = msg.sender; amm = IAMM(_amm); }

    function setSlippageBps(uint256 bps) external onlyOwner { slippageBps = bps; emit SlippageUpdated(bps); }
    function setBuybackAmm(address a) external onlyOwner { buybackAmm = IBuybackAMM(a); }

    function routeMint(uint256 netuid, uint256 taoIn, address to) external returns (uint256 qtyOut) {
        uint256 quote = amm.getQuote(netuid, taoIn);
        uint256 minOut = quote - ((quote * slippageBps) / 10000);
        qtyOut = amm.swapTaoForNet(netuid, taoIn, minOut, to);
    }

    function buyAlpha(uint256 taoIn, address to) external returns (uint256 alphaOut) {
        require(address(buybackAmm) != address(0), "no buyback amm");
        uint256 quote = buybackAmm.getQuoteAlpha(taoIn);
        uint256 minOut = quote - ((quote * slippageBps) / 10000);
        alphaOut = buybackAmm.swapTaoForAlpha(taoIn, minOut, to);
    }
}


