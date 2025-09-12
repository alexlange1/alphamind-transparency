// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import {IValidatorSet} from "./IValidatorSet.sol";
import {IWeightsetRegistry} from "./IWeightsetRegistry.sol";

contract ValidatorSet is IValidatorSet {
    address public admin;
    address public pendingAdmin; // For 2-step admin transfer
    IWeightsetRegistry public registry;
    mapping(address => bool) public isValidator;
    uint256 public override currentEpochId;
    
    uint256 public adminTransferDelay = 2 days; // Minimum delay for admin changes
    uint256 public pendingAdminTimestamp;

    mapping(uint256 => bytes32) public epochWeightHash;
    mapping(uint256 => uint256[]) private _epochNetuids;
    mapping(uint256 => uint16[]) private _epochWeightsBps;
    mapping(uint256 => uint256) public firstSeenTs; // netuid => unix ts
    mapping(uint256 => bool) public eligibilityOverride; // admin override

    event RegistryChanged(address indexed newRegistry);
    event ValidatorChanged(address indexed validator, bool isValidator);
    event FirstSeenChanged(uint256 indexed netuid, uint256 timestamp);
    event EligibilityOverrideChanged(uint256 indexed netuid, bool isEligible);
    event AdminTransferInitiated(address indexed currentAdmin, address indexed pendingAdmin);
    event AdminTransferCompleted(address indexed oldAdmin, address indexed newAdmin);

    modifier onlyAdmin() { require(msg.sender == admin, "not admin"); _; }
    modifier onlyValidator() { require(isValidator[msg.sender], "not validator"); _; }

    constructor(address _admin) { admin = _admin; }

    function setRegistry(address reg) external onlyAdmin { 
        registry = IWeightsetRegistry(reg); 
        emit RegistryChanged(reg);
    }

    function setValidator(address val, bool ok) external onlyAdmin { 
        isValidator[val] = ok; 
        emit ValidatorChanged(val, ok);
    }
    function recordFirstSeen(uint256 netuid, uint256 ts) external onlyAdmin { 
        if (firstSeenTs[netuid] == 0 || ts < firstSeenTs[netuid]) {
            firstSeenTs[netuid] = ts; 
            emit FirstSeenChanged(netuid, ts);
        }
    }
    function setEligibilityOverride(uint256 netuid, bool ok) external onlyAdmin { 
        eligibilityOverride[netuid] = ok; 
        emit EligibilityOverrideChanged(netuid, ok);
    }

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
        // If registry set, verify on-chain published hash matches
        if (address(registry) != address(0)) {
            (uint256 e, bytes32 h,,,,,) = registry.byEpoch(epochId);
            require(e == epochId && h == hash, "registry mismatch");
        }
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
    
    function getWeightsHash(uint256 epochId) external view returns (bytes32) {
        return epochWeightHash[epochId];
    }
    
    // ===================== ADMIN TRANSFER FUNCTIONS =====================
    
    function initiateAdminTransfer(address newAdmin) external onlyAdmin {
        require(newAdmin != address(0), "Invalid admin address");
        require(newAdmin != admin, "Same admin");
        
        pendingAdmin = newAdmin;
        pendingAdminTimestamp = block.timestamp;
        
        emit AdminTransferInitiated(admin, newAdmin);
    }
    
    function completeAdminTransfer() external {
        require(msg.sender == pendingAdmin, "Not pending admin");
        require(block.timestamp >= pendingAdminTimestamp + adminTransferDelay, "Transfer delay not met");
        
        address oldAdmin = admin;
        admin = pendingAdmin;
        pendingAdmin = address(0);
        pendingAdminTimestamp = 0;
        
        emit AdminTransferCompleted(oldAdmin, admin);
    }
    
    function cancelAdminTransfer() external onlyAdmin {
        pendingAdmin = address(0);
        pendingAdminTimestamp = 0;
    }
}


