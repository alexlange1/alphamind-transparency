// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

interface IOracle {
    // Returns price in TAO terms with 1e18 precision
    function getPrice(uint256 netuid) external view returns (uint256 priceTau18);
    function getPriceWithTime(uint256 netuid) external view returns (uint256 priceTau18, uint256 blockTime);
}


