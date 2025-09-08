// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

/**
 * @title IStakingManager
 * @dev Interface for the Staking Manager
 */
interface IStakingManager {
    
    // ===================== EVENTS =====================
    
    event SubnetStaked(uint16 indexed netuid, uint256 amount, bytes32 validator);
    event SubnetUnstaked(uint16 indexed netuid, uint256 amount, bytes32 validator);
    event YieldCompounded(uint16 indexed netuid, uint256 rewardAmount);
    event DefaultValidatorSet(uint16 indexed netuid, bytes32 validator);
    event CompositionUpdated(uint16[] netuids, uint256[] weights);
    event RewardsTransferred(address indexed recipient, uint256 amount);
    
    // ===================== ERRORS =====================
    
    error UnauthorizedCaller();
    error InvalidNetuid();
    error InvalidValidator();
    error InsufficientStake();
    error StakingFailed();
    error UnstakingFailed();
    error InvalidComposition();
    error TransferFailed();
    error AmountTooSmall();
    
    // ===================== FUNCTIONS =====================
    
    /**
     * @dev Stake TAO for a specific subnet using default validator
     */
    function stakeForSubnet(uint16 netuid, uint256 amount) external;
    
    /**
     * @dev Unstake and transfer TAO to recipient
     */
    function unstakeAndTransfer(uint16 netuid, uint256 amount, address recipient) external;
    
    /**
     * @dev Compound staking rewards for all subnets
     */
    function compoundAllYield() external;
    
    /**
     * @dev Compound staking rewards for specific subnet
     */
    function compoundSubnetYield(uint16 netuid) external;
    
    /**
     * @dev Set default validator for a subnet
     */
    function setDefaultValidator(uint16 netuid, bytes32 validator) external;
    
    /**
     * @dev Update index composition
     */
    function updateComposition(uint16[] calldata netuids, uint256[] calldata weights) external;
    
    /**
     * @dev Get current composition
     */
    function getCurrentComposition() external view returns (uint16[] memory netuids, uint256[] memory weights);
    
    /**
     * @dev Get subnet staking information
     */
    function getSubnetInfo(uint16 netuid) external view returns (
        uint256 staked,
        uint256 rewards,
        uint256 lastUpdate,
        bytes32 validator,
        uint256 weight
    );
    
    /**
     * @dev Get total staked amount
     */
    function getTotalStaked() external view returns (uint256);
    
    /**
     * @dev Get total value including rewards
     */
    function getTotalValue() external view returns (uint256);
    
    /**
     * @dev Get yield-adjusted NAV calculation data
     */
    function getNAVData() external view returns (
        uint256 totalValue,
        uint256 totalSupply,
        uint256 nav
    );
    
    /**
     * @dev Check if subnet needs yield compounding
     */
    function needsYieldCompound(uint16 netuid) external view returns (bool);
    
    /**
     * @dev Get all subnets that need yield compounding
     */
    function getSubnetsNeedingCompound() external view returns (uint16[] memory);
}
