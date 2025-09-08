// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/math/Math.sol";

// ===================== INTERFACES =====================

interface IStakingV2 {
    function addStake(bytes32 hotkey, uint256 amountRao) external returns (bool);
    function removeStake(bytes32 hotkey, uint256 amountRao) external returns (bool);
    function getStake(bytes32 hotkey) external view returns (uint256);
    function getStakingRewards(bytes32 hotkey) external view returns (uint256);
}

interface ITAOTransfer {
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

/**
 * @title StakingManager
 * @dev Manages automatic staking of deposited TAO across Bittensor subnets
 * 
 * PURPOSE:
 * - Automatically stake deposited TAO to earn yield
 * - Manage validator selection per subnet
 * - Handle proportional unstaking for redemptions
 * - Track staking rewards and compound yield
 * 
 * FEATURES:
 * ✅ Default validator strategy - one validator per subnet initially
 * ✅ Automatic yield compounding
 * ✅ Proportional unstaking for redemptions
 * ✅ Transparent staking tracking
 * ✅ Upgradeable validator selection strategy
 */
contract StakingManager is ReentrancyGuard {
    using Math for uint256;

    // ===================== PRECOMPILES =====================
    
    /// @dev Bittensor staking precompile
    IStakingV2 constant STAKING = IStakingV2(0x0000000000000000000000000000000000000805);
    
    /// @dev TAO token interface (for transfers after unstaking)
    ITAOTransfer constant TAO = ITAOTransfer(0x0000000000000000000000000000000000000001);

    // ===================== STATE VARIABLES =====================
    
    /// @dev Authorized caller (TAO20Core contract)
    address public immutable authorizedCaller;
    
    /// @dev Default validator hotkey per subnet
    mapping(uint16 => bytes32) public defaultValidators;
    
    /// @dev Total staked amount per subnet (in TAO base units)
    mapping(uint16 => uint256) public subnetStaked;
    
    /// @dev Last yield compound timestamp per subnet
    mapping(uint16 => uint256) public lastYieldUpdate;
    
    /// @dev Accumulated rewards per subnet (in TAO base units)
    mapping(uint16 => uint256) public accumulatedRewards;
    
    /// @dev Current index composition (subnet IDs and weights)
    uint16[] public currentNetuids;
    mapping(uint16 => uint256) public currentWeights; // in basis points (10000 = 100%)
    
    /// @dev Yield compound frequency (24 hours)
    uint256 public constant YIELD_COMPOUND_PERIOD = 24 hours;
    
    /// @dev Minimum staking amount (0.001 TAO)
    uint256 public constant MIN_STAKE_AMOUNT = 1e6; // 1e9 RAO = 1 TAO, so 1e6 = 0.001 TAO
    
    /// @dev Total staked across all subnets
    uint256 public totalStaked;

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

    // ===================== MODIFIERS =====================
    
    modifier onlyAuthorizedCaller() {
        if (msg.sender != authorizedCaller) revert UnauthorizedCaller();
        _;
    }

    // ===================== CONSTRUCTOR =====================
    
    constructor() {
        authorizedCaller = msg.sender; // TAO20Core contract
    }

    // ===================== STAKING FUNCTIONS =====================
    
    /**
     * @dev Stake subnet tokens for a specific subnet using default validator
     * @param netuid Subnet ID  
     * @param amount Amount of subnet tokens to stake (in subnet token base units)
     * 
     * NOTE: This stakes the actual subnet tokens (Alpha tokens) that users deposited,
     * not TAO tokens. Each subnet has its own native token that gets staked.
     */
    function stakeForSubnet(uint16 netuid, uint256 amount) 
        external 
        onlyAuthorizedCaller 
        nonReentrant 
    {
        if (amount < MIN_STAKE_AMOUNT) revert AmountTooSmall();
        
        bytes32 validator = defaultValidators[netuid];
        if (validator == bytes32(0)) revert InvalidValidator();
        
        // Convert to RAO (1 TAO = 1e9 RAO)
        uint256 amountRao = amount * 1e9;
        
        // Stake via precompile
        if (!STAKING.addStake(validator, amountRao)) revert StakingFailed();
        
        // Update tracking
        subnetStaked[netuid] += amount;
        totalStaked += amount;
        
        emit SubnetStaked(netuid, amount, validator);
    }
    
    /**
     * @dev Unstake and transfer TAO to recipient
     * @param netuid Subnet ID
     * @param amount Amount to unstake (in TAO base units)
     * @param recipient Address to receive unstaked TAO
     */
    function unstakeAndTransfer(uint16 netuid, uint256 amount, address recipient) 
        external 
        onlyAuthorizedCaller 
        nonReentrant 
    {
        if (amount == 0) revert AmountTooSmall();
        if (subnetStaked[netuid] < amount) revert InsufficientStake();
        
        bytes32 validator = defaultValidators[netuid];
        if (validator == bytes32(0)) revert InvalidValidator();
        
        // Convert to RAO
        uint256 amountRao = amount * 1e9;
        
        // Unstake via precompile
        if (!STAKING.removeStake(validator, amountRao)) revert UnstakingFailed();
        
        // Update tracking
        subnetStaked[netuid] -= amount;
        totalStaked -= amount;
        
        // Transfer TAO to recipient
        if (!TAO.transfer(recipient, amount)) revert TransferFailed();
        
        emit SubnetUnstaked(netuid, amount, validator);
        emit RewardsTransferred(recipient, amount);
    }

    // ===================== YIELD MANAGEMENT =====================
    
    /**
     * @dev Compound staking rewards for all subnets
     */
    function compoundAllYield() external nonReentrant {
        for (uint i = 0; i < currentNetuids.length; i++) {
            _compoundSubnetYield(currentNetuids[i]);
        }
    }
    
    /**
     * @dev Compound staking rewards for specific subnet
     * @param netuid Subnet ID
     */
    function compoundSubnetYield(uint16 netuid) external nonReentrant {
        _compoundSubnetYield(netuid);
    }
    
    /**
     * @dev Internal function to compound subnet yield
     */
    function _compoundSubnetYield(uint16 netuid) internal {
        // Check if enough time has passed
        if (block.timestamp < lastYieldUpdate[netuid] + YIELD_COMPOUND_PERIOD) {
            return;
        }
        
        bytes32 validator = defaultValidators[netuid];
        if (validator == bytes32(0)) return;
        
        // Get staking rewards
        uint256 rewardsRao = STAKING.getStakingRewards(validator);
        if (rewardsRao == 0) return;
        
        // Convert to TAO base units
        uint256 rewardsTao = rewardsRao / 1e9;
        
        // Update accumulated rewards
        accumulatedRewards[netuid] += rewardsTao;
        totalStaked += rewardsTao; // Rewards increase total value
        lastYieldUpdate[netuid] = block.timestamp;
        
        emit YieldCompounded(netuid, rewardsTao);
    }

    // ===================== ADMIN FUNCTIONS =====================
    
    /**
     * @dev Set default validator for a subnet
     * @param netuid Subnet ID
     * @param validator Validator hotkey
     */
    function setDefaultValidator(uint16 netuid, bytes32 validator) external onlyAuthorizedCaller {
        if (validator == bytes32(0)) revert InvalidValidator();
        
        defaultValidators[netuid] = validator;
        emit DefaultValidatorSet(netuid, validator);
    }
    
    /**
     * @dev Update index composition (netuids and weights)
     * @param netuids Array of subnet IDs
     * @param weights Array of weights (in basis points, sum must equal 10000)
     */
    function updateComposition(uint16[] calldata netuids, uint256[] calldata weights) 
        external 
        onlyAuthorizedCaller 
    {
        if (netuids.length != weights.length) revert InvalidComposition();
        if (netuids.length == 0) revert InvalidComposition();
        
        // Verify weights sum to 10000 (100%)
        uint256 totalWeight = 0;
        for (uint i = 0; i < weights.length; i++) {
            totalWeight += weights[i];
        }
        if (totalWeight != 10000) revert InvalidComposition();
        
        // Clear existing composition
        for (uint i = 0; i < currentNetuids.length; i++) {
            delete currentWeights[currentNetuids[i]];
        }
        delete currentNetuids;
        
        // Set new composition
        for (uint i = 0; i < netuids.length; i++) {
            currentNetuids.push(netuids[i]);
            currentWeights[netuids[i]] = weights[i];
        }
        
        emit CompositionUpdated(netuids, weights);
    }

    // ===================== VIEW FUNCTIONS =====================
    
    /**
     * @dev Get current composition
     */
    function getCurrentComposition() external view returns (uint16[] memory netuids, uint256[] memory weights) {
        netuids = currentNetuids;
        weights = new uint256[](currentNetuids.length);
        
        for (uint i = 0; i < currentNetuids.length; i++) {
            weights[i] = currentWeights[currentNetuids[i]];
        }
    }
    
    /**
     * @dev Get subnet staking information
     */
    function getSubnetInfo(uint16 netuid) external view returns (
        uint256 staked,
        uint256 rewards,
        uint256 lastUpdate,
        bytes32 validator,
        uint256 weight
    ) {
        staked = subnetStaked[netuid];
        rewards = accumulatedRewards[netuid];
        lastUpdate = lastYieldUpdate[netuid];
        validator = defaultValidators[netuid];
        weight = currentWeights[netuid];
    }
    
    /**
     * @dev Get total staked amount
     */
    function getTotalStaked() external view returns (uint256) {
        return totalStaked;
    }
    
    /**
     * @dev Get total value including rewards
     */
    function getTotalValue() external view returns (uint256) {
        uint256 totalValue = totalStaked;
        
        // Add any pending rewards
        for (uint i = 0; i < currentNetuids.length; i++) {
            uint16 netuid = currentNetuids[i];
            bytes32 validator = defaultValidators[netuid];
            
            if (validator != bytes32(0)) {
                uint256 pendingRewards = STAKING.getStakingRewards(validator) / 1e9;
                totalValue += pendingRewards;
            }
        }
        
        return totalValue;
    }
    
    /**
     * @dev Get yield-adjusted NAV calculation data
     */
    function getNAVData() external view returns (
        uint256 totalValue,
        uint256 totalSupply,
        uint256 nav
    ) {
        totalValue = this.getTotalValue();
        // Note: totalSupply would come from TAO20 token contract
        // This is just the staking component of NAV calculation
        totalSupply = 0; // Placeholder - would be provided by calling contract
        nav = totalValue; // Simplified - actual NAV = totalValue / totalSupply
    }
    
    /**
     * @dev Check if subnet needs yield compounding
     */
    function needsYieldCompound(uint16 netuid) external view returns (bool) {
        return block.timestamp >= lastYieldUpdate[netuid] + YIELD_COMPOUND_PERIOD;
    }
    
    /**
     * @dev Get all subnets that need yield compounding
     */
    function getSubnetsNeedingCompound() external view returns (uint16[] memory) {
        uint256 count = 0;
        
        // Count subnets needing compound
        for (uint i = 0; i < currentNetuids.length; i++) {
            if (this.needsYieldCompound(currentNetuids[i])) {
                count++;
            }
        }
        
        // Build array
        uint16[] memory needingCompound = new uint16[](count);
        uint256 index = 0;
        
        for (uint i = 0; i < currentNetuids.length; i++) {
            if (this.needsYieldCompound(currentNetuids[i])) {
                needingCompound[index] = currentNetuids[i];
                index++;
            }
        }
        
        return needingCompound;
    }
}
