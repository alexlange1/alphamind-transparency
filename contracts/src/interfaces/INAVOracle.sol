// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

/**
 * @title INAVOracle
 * @dev Interface for the NAV Oracle
 */
interface INAVOracle {
    
    // ===================== STRUCTS =====================
    
    struct NAVSubmission {
        address validator;
        uint256 nav;
        uint256 timestamp;
        uint256 stake;
        bytes signature;
    }
    
    struct ConsensusResult {
        uint256 nav;
        uint256 timestamp;
        uint256 participatingStake;
        uint256 totalValidators;
    }
    
    // ===================== EVENTS =====================
    
    event ValidatorRegistered(address indexed validator, uint256 stake);
    event ValidatorStakeUpdated(address indexed validator, uint256 oldStake, uint256 newStake);
    event ValidatorRemoved(address indexed validator);
    event NAVSubmitted(address indexed validator, uint256 nav, uint256 timestamp, uint256 epoch);
    event NAVUpdated(uint256 oldNAV, uint256 newNAV, uint256 timestamp, uint256 epoch);
    event EpochAdvanced(uint256 oldEpoch, uint256 newEpoch);
    
    // ===================== ERRORS =====================
    
    error InvalidValidator();
    error InsufficientStake();
    error InvalidNAV();
    error InvalidSignature();
    error InvalidNonce();
    error DeviationTooHigh();
    error InsufficientValidators();
    error NAVTooStale();
    error EpochNotReady();
    error ZeroStake();
    
    // ===================== FUNCTIONS =====================
    
    /**
     * @dev Register a new validator with stake
     */
    function registerValidator(address validator, uint256 stake) external;
    
    /**
     * @dev Update validator stake
     */
    function updateValidatorStake(address validator, uint256 newStake) external;
    
    /**
     * @dev Submit NAV calculation with signature
     */
    function submitNAV(uint256 nav, uint256 timestamp, bytes calldata signature) external;
    
    /**
     * @dev Get current NAV with staleness check
     */
    function getCurrentNAV() external view returns (uint256);
    
    /**
     * @dev Get NAV without staleness check
     */
    function getLatestNAV() external view returns (uint256 nav, uint256 timestamp, bool isStale);
    
    /**
     * @dev Get validator information
     */
    function getValidatorInfo(address validator) external view returns (
        uint256 stake,
        uint256 nonce,
        bool isActive
    );
    
    /**
     * @dev Get current epoch submissions
     */
    function getEpochSubmissions(uint256 epoch) external view returns (NAVSubmission[] memory);
    
    /**
     * @dev Get oracle status
     */
    function getOracleStatus() external view returns (
        uint256 nav,
        uint256 lastUpdate,
        uint256 epoch,
        uint256 validatorCount,
        uint256 totalStakeAmount,
        bool isStale
    );
}
