// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

interface IValidatorSet {
    event WeightSetPublished(uint256 indexed epochId, uint256[] netuids, uint16[] weightsBps, bytes32 hash);
    function publishWeightSet(uint256 epochId, uint256[] calldata netuids, uint16[] calldata weightsBps, bytes32 hash) external;
    function currentEpochId() external view returns (uint256);
    function getWeights(uint256 epochId) external view returns (uint256[] memory netuids, uint16[] memory weightsBps);
}


