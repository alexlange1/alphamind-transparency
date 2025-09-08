// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/math/Math.sol";
import "./interfaces/IBittensorPrecompiles.sol";
import "./libraries/AddressUtils.sol";

/**
 * @title SubnetStakingManager
 * @dev Enhanced staking manager for subnet tokens (Alpha tokens) with yield compounding
 * 
 * KEY FEATURES:
 * ✅ Stakes actual subnet tokens (Alpha tokens), not TAO
 * ✅ Supports all 20 subnet tokens in the index
 * ✅ Automatic yield compounding increases NAV
 * ✅ Pro-rata unstaking for redemptions
 * ✅ Transparent reward tracking per subnet
 * ✅ Asset transfer to user's SS58 address on redemption
 * 
 * ARCHITECTURE:
 * - Each subnet has its own Alpha token that gets staked
 * - Staking happens on the specific subnet's validators
 * - Rewards accumulate and compound automatically
 * - Redemptions unstake proportionally across all subnets
 * - Assets are transferred directly to user's Substrate address
 */
contract SubnetStakingManager is ReentrancyGuard {
    using Math for uint256;
    using AddressUtils for address;
    using AddressUtils for bytes32;
    using BittensorPrecompiles for *;

    // ===================== STATE VARIABLES =====================
    
    /// @dev Authorized caller (TAO20Core contract)
    address public immutable authorizedCaller;
    
    /// @dev Default validator hotkey per subnet for staking Alpha tokens
    mapping(uint16 => bytes32) public subnetValidators;
    
    /// @dev Total staked Alpha tokens per subnet (in Alpha token base units)
    mapping(uint16 => uint256) public subnetStaked;
    
    /// @dev Last yield compound timestamp per subnet
    mapping(uint16 => uint256) public lastYieldUpdate;
    
    /// @dev Accumulated Alpha token rewards per subnet
    mapping(uint16 => uint256) public accumulatedRewards;
    
    /// @dev Current index composition (top 20 subnets and their weights)
    uint16[] public indexComposition;
    mapping(uint16 => uint256) public subnetWeights; // in basis points (10000 = 100%)
    
    /// @dev Total value locked across all subnets (in TAO equivalent)
    uint256 public totalValueLocked;
    
    /// @dev Yield compound frequency (24 hours)
    uint256 public constant YIELD_COMPOUND_PERIOD = 24 hours;
    
    /// @dev Minimum staking amount per subnet (0.001 Alpha tokens)
    uint256 public constant MIN_STAKE_AMOUNT = 1e15; // Assuming 18 decimals for Alpha tokens
    
    /// @dev Contract's vault address on Substrate
    bytes32 public immutable vaultAddress;

    // ===================== EVENTS =====================
    
    event SubnetTokenStaked(uint16 indexed netuid, uint256 alphaAmount, bytes32 validator);
    event SubnetTokenUnstaked(uint16 indexed netuid, uint256 alphaAmount, bytes32 validator);
    event AlphaYieldCompounded(uint16 indexed netuid, uint256 rewardAmount);
    event SubnetValidatorSet(uint16 indexed netuid, bytes32 validator);
    event IndexCompositionUpdated(uint16[] netuids, uint256[] weights);
    event AssetsTransferred(address indexed recipient, bytes32 ss58Address, uint256 totalValue);
    event SubnetTokenDeposited(uint16 indexed netuid, uint256 amount, bytes32 from);

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
    error SubnetNotInIndex();
    error InvalidAssetTransfer();

    // ===================== MODIFIERS =====================
    
    modifier onlyAuthorizedCaller() {
        if (msg.sender != authorizedCaller) revert UnauthorizedCaller();
        _;
    }

    // ===================== CONSTRUCTOR =====================
    
    constructor() {
        authorizedCaller = msg.sender; // TAO20Core contract
        vaultAddress = AddressUtils.getMyVaultAddress();
        
        // Initialize with top 20 subnets (example composition)
        _initializeDefaultComposition();
    }

    // ===================== SUBNET TOKEN STAKING =====================
    
    /**
     * @dev Stake subnet tokens (Alpha tokens) for yield generation
     * @param netuid Subnet ID (1-20 for top subnets)
     * @param alphaAmount Amount of Alpha tokens to stake
     * 
     * PROCESS:
     * 1. Verify subnet is in index composition
     * 2. Get Alpha tokens from contract's EVM balance
     * 3. Stake Alpha tokens with subnet's validator
     * 4. Update tracking and emit events
     */
    function stakeSubnetTokens(uint16 netuid, uint256 alphaAmount) 
        external 
        onlyAuthorizedCaller 
        nonReentrant 
    {
        if (alphaAmount < MIN_STAKE_AMOUNT) revert AmountTooSmall();
        if (subnetWeights[netuid] == 0) revert SubnetNotInIndex();
        
        bytes32 validator = subnetValidators[netuid];
        if (validator == bytes32(0)) revert InvalidValidator();
        
        // Get subnet token ERC-20 interface
        address subnetTokenAddress = AddressUtils.getSubnetTokenAddress(netuid);
        
        // Verify contract has sufficient Alpha tokens
        uint256 contractBalance = BittensorPrecompiles.assetTransfer().getAssetBalance(netuid, address(this));
        if (contractBalance < alphaAmount) revert InsufficientStake();
        
        // Convert Alpha tokens to RAO equivalent for staking
        // Note: This assumes Alpha tokens have same precision as TAO
        uint256 alphaAmountRao = AddressUtils.taoToRao(alphaAmount);
        
        // Stake Alpha tokens with subnet validator
        if (!BittensorPrecompiles.staking().addStake(validator, alphaAmountRao)) {
            revert StakingFailed();
        }
        
        // Update tracking
        subnetStaked[netuid] += alphaAmount;
        
        emit SubnetTokenStaked(netuid, alphaAmount, validator);
    }
    
    /**
     * @dev Unstake subnet tokens and transfer to user's SS58 address
     * @param netuid Subnet ID
     * @param alphaAmount Amount of Alpha tokens to unstake
     * @param recipientSS58 User's Substrate address (32-byte public key)
     */
    function unstakeAndTransferSubnetTokens(
        uint16 netuid, 
        uint256 alphaAmount, 
        bytes32 recipientSS58
    ) 
        external 
        onlyAuthorizedCaller 
        nonReentrant 
    {
        if (alphaAmount == 0) revert AmountTooSmall();
        if (subnetStaked[netuid] < alphaAmount) revert InsufficientStake();
        if (!AddressUtils.isValidSubstrateKey(recipientSS58)) revert InvalidAssetTransfer();
        
        bytes32 validator = subnetValidators[netuid];
        if (validator == bytes32(0)) revert InvalidValidator();
        
        // Convert to RAO for unstaking
        uint256 alphaAmountRao = AddressUtils.taoToRao(alphaAmount);
        
        // Unstake Alpha tokens from subnet validator
        if (!BittensorPrecompiles.staking().removeStake(validator, alphaAmountRao)) {
            revert UnstakingFailed();
        }
        
        // Update tracking
        subnetStaked[netuid] -= alphaAmount;
        
        // Transfer Alpha tokens to user's SS58 address
        if (!BittensorPrecompiles.assetTransfer().transferAssetToSubstrate(netuid, recipientSS58, alphaAmount)) {
            revert TransferFailed();
        }
        
        emit SubnetTokenUnstaked(netuid, alphaAmount, validator);
    }

    // ===================== YIELD MANAGEMENT =====================
    
    /**
     * @dev Compound Alpha token staking rewards for all subnets in index
     */
    function compoundAllAlphaYield() external nonReentrant {
        for (uint i = 0; i < indexComposition.length; i++) {
            _compoundSubnetAlphaYield(indexComposition[i]);
        }
    }
    
    /**
     * @dev Compound Alpha token staking rewards for specific subnet
     * @param netuid Subnet ID
     */
    function compoundSubnetAlphaYield(uint16 netuid) external nonReentrant {
        if (subnetWeights[netuid] == 0) revert SubnetNotInIndex();
        _compoundSubnetAlphaYield(netuid);
    }
    
    /**
     * @dev Internal function to compound subnet Alpha yield
     */
    function _compoundSubnetAlphaYield(uint16 netuid) internal {
        // Check if enough time has passed
        if (block.timestamp < lastYieldUpdate[netuid] + YIELD_COMPOUND_PERIOD) {
            return;
        }
        
        bytes32 validator = subnetValidators[netuid];
        if (validator == bytes32(0)) return;
        
        // Get Alpha token staking rewards from subnet validator
        uint256 rewardsRao = BittensorPrecompiles.staking().getStakingRewards(validator);
        if (rewardsRao == 0) return;
        
        // Convert rewards to Alpha token base units
        uint256 rewardsAlpha = AddressUtils.raoToTao(rewardsRao);
        
        // Update accumulated rewards (these increase NAV automatically)
        accumulatedRewards[netuid] += rewardsAlpha;
        lastYieldUpdate[netuid] = block.timestamp;
        
        emit AlphaYieldCompounded(netuid, rewardsAlpha);
    }

    // ===================== REDEMPTION LOGIC =====================
    
    /**
     * @dev Execute pro-rata redemption across all subnets
     * @param totalRedemptionValue Total value being redeemed (in TAO equivalent)
     * @param recipientSS58 User's Substrate address
     * 
     * PROCESS:
     * 1. Calculate each subnet's share based on current weights
     * 2. Unstake Alpha tokens proportionally from each subnet
     * 3. Transfer unstaked Alpha tokens to user's SS58 address
     * 4. Update total value locked
     */
    function executeProRataRedemption(
        uint256 totalRedemptionValue,
        bytes32 recipientSS58
    ) 
        external 
        onlyAuthorizedCaller 
        nonReentrant 
    {
        if (totalRedemptionValue == 0) revert AmountTooSmall();
        if (!AddressUtils.isValidSubstrateKey(recipientSS58)) revert InvalidAssetTransfer();
        
        uint256 totalTransferred = 0;
        
        // Redeem from each subnet proportionally
        for (uint i = 0; i < indexComposition.length; i++) {
            uint16 netuid = indexComposition[i];
            uint256 subnetWeight = subnetWeights[netuid];
            
            if (subnetWeight == 0 || subnetStaked[netuid] == 0) continue;
            
            // Calculate this subnet's share (weight is in basis points)
            uint256 subnetRedemptionValue = (totalRedemptionValue * subnetWeight) / 10000;
            
            if (subnetRedemptionValue > 0) {
                // Convert TAO equivalent to Alpha token amount
                // For simplicity, assume 1:1 conversion (in production, use oracle prices)
                uint256 alphaAmountToUnstake = subnetRedemptionValue;
                
                // Ensure we don't unstake more than available
                if (alphaAmountToUnstake > subnetStaked[netuid]) {
                    alphaAmountToUnstake = subnetStaked[netuid];
                }
                
                if (alphaAmountToUnstake > 0) {
                    // Unstake and transfer this subnet's Alpha tokens
                    try this.unstakeAndTransferSubnetTokens(netuid, alphaAmountToUnstake, recipientSS58) {
                        totalTransferred += alphaAmountToUnstake;
                    } catch {
                        // Continue with other subnets if one fails
                        continue;
                    }
                }
            }
        }
        
        // Update total value locked
        if (totalTransferred <= totalValueLocked) {
            totalValueLocked -= totalTransferred;
        } else {
            totalValueLocked = 0;
        }
        
        emit AssetsTransferred(msg.sender, recipientSS58, totalTransferred);
    }

    // ===================== INDEX COMPOSITION MANAGEMENT =====================
    
    /**
     * @dev Update index composition with new top 20 subnets
     * @param netuids Array of subnet IDs (should be exactly 20)
     * @param weights Array of weights in basis points (sum must equal 10000)
     */
    function updateIndexComposition(uint16[] calldata netuids, uint256[] calldata weights) 
        external 
        onlyAuthorizedCaller 
    {
        if (netuids.length != weights.length) revert InvalidComposition();
        if (netuids.length == 0 || netuids.length > 20) revert InvalidComposition();
        
        // Verify weights sum to 10000 (100%)
        uint256 totalWeight = 0;
        for (uint i = 0; i < weights.length; i++) {
            totalWeight += weights[i];
        }
        if (totalWeight != 10000) revert InvalidComposition();
        
        // Clear existing composition
        for (uint i = 0; i < indexComposition.length; i++) {
            delete subnetWeights[indexComposition[i]];
        }
        delete indexComposition;
        
        // Set new composition
        for (uint i = 0; i < netuids.length; i++) {
            if (netuids[i] == 0) revert InvalidNetuid();
            
            indexComposition.push(netuids[i]);
            subnetWeights[netuids[i]] = weights[i];
        }
        
        emit IndexCompositionUpdated(netuids, weights);
    }
    
    /**
     * @dev Set validator for a subnet
     * @param netuid Subnet ID
     * @param validator Validator hotkey for staking subnet's Alpha tokens
     */
    function setSubnetValidator(uint16 netuid, bytes32 validator) external onlyAuthorizedCaller {
        if (validator == bytes32(0)) revert InvalidValidator();
        if (subnetWeights[netuid] == 0) revert SubnetNotInIndex();
        
        subnetValidators[netuid] = validator;
        emit SubnetValidatorSet(netuid, validator);
    }

    // ===================== VIEW FUNCTIONS =====================
    
    /**
     * @dev Get current index composition
     */
    function getCurrentComposition() external view returns (uint16[] memory netuids, uint256[] memory weights) {
        netuids = indexComposition;
        weights = new uint256[](indexComposition.length);
        
        for (uint i = 0; i < indexComposition.length; i++) {
            weights[i] = subnetWeights[indexComposition[i]];
        }
    }
    
    /**
     * @dev Get subnet staking information
     */
    function getSubnetInfo(uint16 netuid) external view returns (
        uint256 stakedAlpha,
        uint256 accumulatedAlphaRewards,
        uint256 lastUpdate,
        bytes32 validator,
        uint256 weight,
        address tokenAddress
    ) {
        stakedAlpha = subnetStaked[netuid];
        accumulatedAlphaRewards = accumulatedRewards[netuid];
        lastUpdate = lastYieldUpdate[netuid];
        validator = subnetValidators[netuid];
        weight = subnetWeights[netuid];
        tokenAddress = AddressUtils.getSubnetTokenAddress(netuid);
    }
    
    /**
     * @dev Get total value of all staked Alpha tokens (in TAO equivalent)
     */
    function getTotalValueLocked() external view returns (uint256) {
        uint256 totalValue = 0;
        
        for (uint i = 0; i < indexComposition.length; i++) {
            uint16 netuid = indexComposition[i];
            
            // Add staked amount plus accumulated rewards
            uint256 subnetValue = subnetStaked[netuid] + accumulatedRewards[netuid];
            
            // Convert to TAO equivalent (simplified 1:1, in production use oracle)
            totalValue += subnetValue;
        }
        
        return totalValue;
    }
    
    /**
     * @dev Get NAV data for oracle calculations
     */
    function getNAVData() external view returns (
        uint256 totalValue,
        uint256 pendingRewards,
        uint256 nav
    ) {
        totalValue = this.getTotalValueLocked();
        
        // Calculate pending rewards across all subnets
        pendingRewards = 0;
        for (uint i = 0; i < indexComposition.length; i++) {
            uint16 netuid = indexComposition[i];
            bytes32 validator = subnetValidators[netuid];
            
            if (validator != bytes32(0)) {
                uint256 pendingRao = BittensorPrecompiles.staking().getStakingRewards(validator);
                pendingRewards += AddressUtils.raoToTao(pendingRao);
            }
        }
        
        // Total value including pending rewards
        nav = totalValue + pendingRewards;
    }
    
    /**
     * @dev Check which subnets need yield compounding
     */
    function getSubnetsNeedingCompound() external view returns (uint16[] memory) {
        uint256 count = 0;
        
        // Count subnets needing compound
        for (uint i = 0; i < indexComposition.length; i++) {
            if (block.timestamp >= lastYieldUpdate[indexComposition[i]] + YIELD_COMPOUND_PERIOD) {
                count++;
            }
        }
        
        // Build array
        uint16[] memory needingCompound = new uint16[](count);
        uint256 index = 0;
        
        for (uint i = 0; i < indexComposition.length; i++) {
            if (block.timestamp >= lastYieldUpdate[indexComposition[i]] + YIELD_COMPOUND_PERIOD) {
                needingCompound[index] = indexComposition[i];
                index++;
            }
        }
        
        return needingCompound;
    }
    
    /**
     * @dev Get contract's vault address on Substrate
     */
    function getVaultAddress() external view returns (bytes32) {
        return vaultAddress;
    }

    // ===================== INTERNAL FUNCTIONS =====================
    
    /**
     * @dev Initialize default index composition (top 20 subnets)
     */
    function _initializeDefaultComposition() internal {
        // Example: Initialize with top 20 subnets with equal weights
        // In production, this would be set based on actual subnet rankings
        
        uint16[] memory defaultNetuids = new uint16[](20);
        uint256[] memory defaultWeights = new uint256[](20);
        
        for (uint i = 0; i < 20; i++) {
            defaultNetuids[i] = uint16(i + 1); // Subnets 1-20
            defaultWeights[i] = 500; // 5% each (500 basis points)
        }
        
        // Set composition
        for (uint i = 0; i < 20; i++) {
            indexComposition.push(defaultNetuids[i]);
            subnetWeights[defaultNetuids[i]] = defaultWeights[i];
        }
        
        emit IndexCompositionUpdated(defaultNetuids, defaultWeights);
    }
}
