// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

interface IOracle {
    // Returns price in TAO terms with 1e18 precision
    function getPrice(uint256 netuid) external view returns (uint256 priceTau18);
    function getPriceWithTime(uint256 netuid) external view returns (uint256 priceTau18, uint256 blockTime);
    // Fee-aware TWAP quote for a swap amount (abstracted; implementation can resolve tokenIn/out by netuid)
    function getQuoteTWAP(uint256 netuid, uint256 amountInTau, uint256 windowSecs) external view returns (uint256 amountOutTokens);
}


