// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

interface IWeightsetRegistry {
    function byEpoch(uint256 epoch) external view returns (
        uint256 epochOut,
        bytes32 tupleHash,
        string memory cid,
        string memory signer,
        address publisher,
        uint256 blockNumber,
        uint256 timestamp
    );
}


