// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import {IValidatorSet} from "./IValidatorSet.sol";

contract ValidatorSet is IValidatorSet {
    address public admin;
    mapping(address => bool) public isValidator;
    uint256 public override currentEpochId;

    mapping(uint256 => bytes32) public epochWeightHash;
    mapping(uint256 => uint256[]) private _epochNetuids;
    mapping(uint256 => uint16[]) private _epochWeightsBps;
    mapping(uint256 => uint256) public firstSeenTs; // netuid => unix ts
    mapping(uint256 => bool) public eligibilityOverride; // admin override

    modifier onlyAdmin() { require(msg.sender == admin, "not admin"); _; }
    modifier onlyValidator() { require(isValidator[msg.sender], "not validator"); _; }

    constructor(address _admin) { admin = _admin; }

    function setValidator(address val, bool ok) external onlyAdmin { isValidator[val] = ok; }
    function recordFirstSeen(uint256 netuid, uint256 ts) external onlyAdmin { if (firstSeenTs[netuid] == 0 || ts < firstSeenTs[netuid]) firstSeenTs[netuid] = ts; }
    function setEligibilityOverride(uint256 netuid, bool ok) external onlyAdmin { eligibilityOverride[netuid] = ok; }

    function publishWeightSet(uint256 epochId, uint256[] calldata netuids, uint16[] calldata weightsBps, bytes32 hash) external override onlyValidator {
        require(netuids.length == weightsBps.length, "len mismatch");
        uint256 sum;
        for (uint256 i = 0; i < weightsBps.length; i++) sum += weightsBps[i];
        require(sum == 10_000, "sum != 10000");
        require(weightsBps.length == 20, "not top20");
        // Enforce >= 90d eligibility unless overridden
        for (uint256 i = 0; i < netuids.length; i++) {
            if (!eligibilityOverride[netuids[i]]) {
                require(firstSeenTs[netuids[i]] > 0 && block.timestamp - firstSeenTs[netuids[i]] >= 90 days, "ineligible");
            }
        }
        bytes32 calc = keccak256(abi.encode(epochId, netuids, weightsBps));
        require(calc == hash, "hash mismatch");
        epochWeightHash[epochId] = hash;
        // Persist arrays for retrieval
        _epochNetuids[epochId] = netuids;
        _epochWeightsBps[epochId] = weightsBps;
        if (epochId > currentEpochId) currentEpochId = epochId;
        emit WeightSetPublished(epochId, netuids, weightsBps, hash);
    }

    function getWeights(uint256 epochId) external view returns (uint256[] memory netuids, uint16[] memory weightsBps) {
        return (_epochNetuids[epochId], _epochWeightsBps[epochId]);
    }
}


