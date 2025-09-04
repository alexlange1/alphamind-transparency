// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

interface IWeightsetRegistry {
    function getCurrentWeights() external view returns (uint256[] memory netuids, uint16[] memory weights);
    function getWeightsHash(uint256 epochId) external view returns (bytes32);
    function currentEpochId() external view returns (uint256);
}