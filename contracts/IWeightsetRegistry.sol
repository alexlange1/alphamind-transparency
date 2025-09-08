// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

interface IWeightsetRegistry {
    function getCurrentWeights() external view returns (uint256[] memory netuids, uint16[] memory weights);
    function getWeightsHash(uint256 epochId) external view returns (bytes32);
    function currentEpochId() external view returns (uint256);
    function byEpoch(uint256 epochId) external view returns (uint256 epoch, bytes32 hash, uint256 startTs, uint256 endTs, uint256 totalStake, uint256 totalWeight, uint256 totalReward);
}