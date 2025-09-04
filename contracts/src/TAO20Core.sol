// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "@openzeppelin/contracts/utils/math/Math.sol";
import "./TAO20.sol";
import "./IValidatorSet.sol";
import "./ValidatorSet.sol";

// ===================== INTERFACES =====================

interface IEd25519Verify {
    function verify(bytes32 message, bytes32 pubkey, bytes32 r, bytes32 s) external pure returns (bool);
}

interface IStakingV2 {
    function addStake(bytes32 hotkey, uint256 amountRao) external returns (bool);
    function removeStake(bytes32 hotkey, uint256 amountRao) external returns (bool);
    function getStake(bytes32 hotkey) external view returns (uint256);
    function getStakingRewards(bytes32 hotkey) external view returns (uint256);
}

/**
 * @title TAO20Core
 * @dev Clean implementation of TAO20 index with anti-dilution staking mechanism
 * 
 * CORE ARCHITECTURE:
 * 1. Users deposit subnet tokens to Bittensor Substrate vault (auto-staked)
 * 2. Users prove ownership with Ed25519 signatures on BEVM
 * 3. Validators attest deposits with cryptographic proofs
 * 4. System mints TAO20 tokens with yield-adjusted NAV
 * 5. Staking rewards compound into token value (anti-dilution)
 */
contract TAO20Core is Ownable, ReentrancyGuard, Pausable {
    using Math for uint256;

    // ===================== PRECOMPILES =====================
    
    /// @dev Ed25519 signature verification precompile
    IEd25519Verify constant ED25519 = IEd25519Verify(0x0000000000000000000000000000000000000402);
    
    /// @dev Bittensor staking precompile  
    IStakingV2 constant STAKING = IStakingV2(0x0000000000000000000000000000000000000805);

    // ===================== CORE CONTRACTS =====================
    
    TAO20 public immutable tao20Token;
    IValidatorSet public validatorSet;
    
    // ===================== STAKING & YIELD TRACKING =====================
    
    /// @dev Total staked per subnet (in RAO)
    mapping(uint16 => uint256) public subnetStaked;
    
    /// @dev Accumulated staking rewards per subnet
    mapping(uint16 => uint256) public accumulatedYield;
    
    /// @dev Last yield update timestamp per subnet
    mapping(uint16 => uint256) public lastYieldUpdate;
    
    /// @dev Total yield per share (18 decimals)
    uint256 public yieldPerShare;
    
    /// @dev Subnet vault hotkeys for staking
    mapping(uint16 => bytes32) public subnetVaultHotkeys;

    // ===================== DEPOSIT VERIFICATION =====================
    
    /// @dev Processed deposit IDs to prevent replay
    mapping(bytes32 => bool) public processedDeposits;
    
    /// @dev Validator attestations per deposit
    mapping(bytes32 => mapping(address => bool)) public validatorAttestations;
    
    /// @dev Attestation count per deposit
    mapping(bytes32 => uint256) public attestationCount;
    
    /// @dev User nonces for replay protection
    mapping(address => uint256) public userNonces;

    // ===================== CONFIGURATION =====================
    
    /// @dev Minimum validator attestations required
    uint256 public attestationThreshold = 3;
    
    /// @dev Composition tolerance in basis points (500 = 5%)
    uint256 public compositionTolerance = 500;
    
    /// @dev Yield compound frequency (24 hours)
    uint256 public yieldCompoundPeriod = 24 hours;

    // ===================== STRUCTS =====================
    
    struct SubstrateDeposit {
        bytes32 blockHash;        // Bittensor block hash
        uint32 extrinsicIndex;    // Transaction index
        bytes32 userSS58;         // User's Bittensor public key
        uint16 netuid;            // Subnet ID
        uint256 amount;           // Amount deposited (in subnet tokens)
        uint256 stakingEpoch;     // When staking started
        bytes32 merkleRoot;       // Merkle root of deposit batch
    }

    struct MintRequest {
        address recipient;        // Who receives TAO20 tokens
        SubstrateDeposit[] deposits; // Array of substrate deposits
        bytes32[] merkleProofs;   // Merkle proofs for each deposit
        uint256 nonce;            // User nonce for replay protection
        uint256 deadline;         // Request expiration
    }

    // ===================== EVENTS =====================
    
    event DepositAttested(bytes32 indexed depositId, address indexed validator, uint256 attestationCount);
    event YieldCompounded(uint16 indexed netuid, uint256 yieldAmount, uint256 newYieldPerShare);
    event TAO20Minted(address indexed recipient, uint256 amount, uint256 yieldAdjustedNAV);
    event TAO20Redeemed(address indexed user, uint256 tao20Amount, uint256 subnetTokensReturned);
    event SubnetStaked(uint16 indexed netuid, uint256 amount, bytes32 vaultHotkey);


    // ===================== CONSTRUCTOR =====================
    
    constructor(
        address _validatorSet,
        string memory _tokenName,
        string memory _tokenSymbol
    ) Ownable(msg.sender) {
        validatorSet = IValidatorSet(_validatorSet);
        tao20Token = new TAO20(address(this), _tokenName, _tokenSymbol);
    }

    // ===================== CORE FUNCTIONS =====================

    /**
     * @dev Mint TAO20 tokens based on verified Substrate deposits
     * @param request Mint request with deposits and proofs
     * @param signature Ed25519 signature proving ownership
     */
    function mintTAO20(
        MintRequest calldata request,
        bytes calldata signature
    ) external nonReentrant whenNotPaused {
        require(block.timestamp <= request.deadline, "Request expired");
        require(request.nonce == userNonces[msg.sender], "Invalid nonce");
        require(request.deposits.length > 0, "Empty deposits array");
        
        // Verify all deposits belong to the same user and get the common userSS58
        bytes32 commonUserSS58 = request.deposits[0].userSS58;
        for (uint i = 0; i < request.deposits.length; i++) {
            require(request.deposits[i].userSS58 == commonUserSS58, "All deposits must belong to same user");
        }
        
        // Verify Ed25519 signature with the verified common user key
        bytes32 messageHash = _hashMintRequest(request);
        require(_verifyEd25519Signature(messageHash, signature, commonUserSS58), "Invalid signature");
        
        // Increment nonce
        userNonces[msg.sender]++;
        
        uint256 totalValue = 0;
        
        // Process each deposit
        for (uint i = 0; i < request.deposits.length; i++) {
            SubstrateDeposit memory deposit = request.deposits[i];
            bytes32 depositId = _getDepositId(deposit);
            
            // Verify deposit hasn't been processed
            require(!processedDeposits[depositId], "Deposit already processed");
            
            // Verify sufficient attestations
            require(attestationCount[depositId] >= attestationThreshold, "Insufficient attestations");
            
            // TODO: Implement merkle proof verification for production
            // For now, we trust the deposit structure
            require(deposit.merkleRoot != bytes32(0), "Invalid merkle root");
            
            // Mark as processed
            processedDeposits[depositId] = true;
            
            // Add to subnet staking
            _addToSubnetStaking(deposit.netuid, deposit.amount);
            
            // Calculate value with yield
            totalValue += _calculateDepositValue(deposit);
        }
        
        // Verify composition tolerance
        _verifyCompositionTolerance(request.deposits);
        
        // Calculate yield-adjusted NAV and mint tokens
        uint256 yieldAdjustedNAV = _getYieldAdjustedNAV();
        uint256 tao20Amount = totalValue * 1e18 / yieldAdjustedNAV;
        
        tao20Token.mint(request.recipient, tao20Amount);
        
        emit TAO20Minted(request.recipient, tao20Amount, yieldAdjustedNAV);
    }

    /**
     * @dev Redeem TAO20 tokens for underlying subnet tokens
     * @param amount Amount of TAO20 tokens to redeem
     */
    function redeemTAO20(uint256 amount) external nonReentrant whenNotPaused {
        require(amount > 0, "Zero amount");
        require(tao20Token.balanceOf(msg.sender) >= amount, "Insufficient balance");
        
        // Burn TAO20 tokens
        tao20Token.burn(msg.sender, amount);
        
        // Calculate redemption value with current yield
        uint256 yieldAdjustedNAV = _getYieldAdjustedNAV();
        uint256 redemptionValue = amount * yieldAdjustedNAV / 1e18;
        
        // Get current weightings
        (uint256[] memory netuids, uint16[] memory weights) = validatorSet.getWeights(validatorSet.currentEpochId());
        
        // Redeem proportionally and unstake
        for (uint i = 0; i < netuids.length; i++) {
            uint16 netuid = uint16(netuids[i]);
            uint256 subnetAmount = redemptionValue * weights[i] / 10000;
            
            if (subnetAmount > 0) {
                _removeFromSubnetStaking(netuid, subnetAmount);
            }
        }
        
        emit TAO20Redeemed(msg.sender, amount, redemptionValue);
    }

    // ===================== VALIDATOR FUNCTIONS =====================

    /**
     * @dev Validators attest to substrate deposits
     * @param depositId Unique deposit identifier
     * @param deposit Deposit details
     */
    function attestDeposit(
        bytes32 depositId,
        SubstrateDeposit calldata deposit
    ) external {
        require(ValidatorSet(address(validatorSet)).isValidator(msg.sender), "Not authorized validator");
        require(!validatorAttestations[depositId][msg.sender], "Already attested");
        
        // Verify deposit ID matches
        require(depositId == _getDepositId(deposit), "Invalid deposit ID");
        
        // Record attestation
        validatorAttestations[depositId][msg.sender] = true;
        attestationCount[depositId]++;
        
        emit DepositAttested(depositId, msg.sender, attestationCount[depositId]);
    }

    // ===================== YIELD MANAGEMENT =====================

    /**
     * @dev Compound staking rewards into NAV (anyone can call)
     */
    function compoundYield() external nonReentrant {
        (uint256[] memory netuids, ) = validatorSet.getWeights(validatorSet.currentEpochId());
        
        uint256 totalNewYield = 0;
        
        for (uint i = 0; i < netuids.length; i++) {
            uint16 netuid = uint16(netuids[i]);
            
            // Skip if too recent
            if (block.timestamp < lastYieldUpdate[netuid] + yieldCompoundPeriod) {
                continue;
            }
            
            bytes32 vaultHotkey = subnetVaultHotkeys[netuid];
            if (vaultHotkey == bytes32(0)) continue;
            
            // Get staking rewards
            uint256 newRewards = STAKING.getStakingRewards(vaultHotkey);
            
            if (newRewards > 0) {
                accumulatedYield[netuid] += newRewards;
                totalNewYield += newRewards;
                lastYieldUpdate[netuid] = block.timestamp;
                
                emit YieldCompounded(netuid, newRewards, yieldPerShare);
            }
        }
        
        // Update global yield per share
        if (totalNewYield > 0 && tao20Token.totalSupply() > 0) {
            yieldPerShare += (totalNewYield * 1e18) / tao20Token.totalSupply();
        }
    }

    // ===================== INTERNAL FUNCTIONS =====================

    function _addToSubnetStaking(uint16 netuid, uint256 amount) internal {
        bytes32 vaultHotkey = subnetVaultHotkeys[netuid];
        require(vaultHotkey != bytes32(0), "No vault hotkey for subnet");
        
        // Convert to RAO (1 TAO = 1e9 RAO)
        uint256 amountRao = amount * 1e9;
        
        // Add stake via precompile
        require(STAKING.addStake(vaultHotkey, amountRao), "Staking failed");
        
        subnetStaked[netuid] += amountRao;
        
        emit SubnetStaked(netuid, amountRao, vaultHotkey);
    }

    function _removeFromSubnetStaking(uint16 netuid, uint256 amount) internal {
        bytes32 vaultHotkey = subnetVaultHotkeys[netuid];
        require(vaultHotkey != bytes32(0), "No vault hotkey for subnet");
        
        uint256 amountRao = amount * 1e9;
        require(subnetStaked[netuid] >= amountRao, "Insufficient staked amount");
        
        // Remove stake via precompile
        require(STAKING.removeStake(vaultHotkey, amountRao), "Unstaking failed");
        
        subnetStaked[netuid] -= amountRao;
    }

    function _calculateDepositValue(SubstrateDeposit memory deposit) internal view returns (uint256) {
        // Base value of deposit
        uint256 baseValue = deposit.amount;
        
        // Add proportional share of accumulated yield
        uint256 subnetYield = accumulatedYield[deposit.netuid];
        uint256 totalStaked = subnetStaked[deposit.netuid];
        
        if (totalStaked > 0 && subnetYield > 0) {
            // Calculate yield share using proper scaling to avoid division by zero
            // yieldShare = (subnetYield * deposit.amount * 1e9) / totalStaked
            uint256 yieldShare = (subnetYield * deposit.amount * 1e9) / totalStaked;
            baseValue += yieldShare;
        }
        
        return baseValue;
    }

    function _getYieldAdjustedNAV() internal view returns (uint256) {
        uint256 totalSupply = tao20Token.totalSupply();
        if (totalSupply == 0) return 1e18; // Initial NAV = 1.0
        
        // Calculate total value including accumulated yield
        uint256 totalValue = 0;
        (uint256[] memory netuids, ) = validatorSet.getWeights(validatorSet.currentEpochId());
        
        for (uint i = 0; i < netuids.length; i++) {
            uint16 netuid = uint16(netuids[i]);
            uint256 stakedAmount = subnetStaked[netuid] / 1e9; // Convert from RAO
            uint256 yieldAmount = accumulatedYield[netuid];
            totalValue += stakedAmount + yieldAmount;
        }
        
        // Handle edge case: if total value is zero but supply > 0, return minimum NAV
        // This prevents division by zero in mintTAO20 function
        if (totalValue == 0) return 1; // Minimal NAV to prevent division by zero
        
        return totalValue * 1e18 / totalSupply;
    }

    function _verifyCompositionTolerance(SubstrateDeposit[] memory deposits) internal view {
        if (compositionTolerance == 0) return;
        
        (uint256[] memory targetNetuids, uint16[] memory targetWeights) = 
            validatorSet.getWeights(validatorSet.currentEpochId());
        
        // Calculate total deposit value
        uint256 totalValue = 0;
        for (uint i = 0; i < deposits.length; i++) {
            totalValue += deposits[i].amount;
        }
        
        // Verify each subnet is within tolerance
        for (uint i = 0; i < deposits.length; i++) {
            uint16 netuid = deposits[i].netuid;
            uint256 depositWeight = (deposits[i].amount * 10000) / totalValue;
            
            // Find target weight
            uint256 targetWeight = 0;
            for (uint j = 0; j < targetNetuids.length; j++) {
                if (uint16(targetNetuids[j]) == netuid) {
                    targetWeight = targetWeights[j];
                    break;
                }
            }
            
            require(targetWeight > 0, "Subnet not in current weightings");
            
            uint256 deviation = depositWeight > targetWeight ? 
                depositWeight - targetWeight : targetWeight - depositWeight;
            
            require(deviation <= compositionTolerance, "Composition tolerance exceeded");
        }
    }

    function _getDepositId(SubstrateDeposit memory deposit) internal pure returns (bytes32) {
        return keccak256(abi.encode(
            deposit.blockHash,
            deposit.extrinsicIndex,
            deposit.userSS58,
            deposit.netuid,
            deposit.amount,
            deposit.stakingEpoch
        ));
    }

    function _hashMintRequest(MintRequest calldata request) internal pure returns (bytes32) {
        return keccak256(abi.encode(
            request.recipient,
            request.deposits,
            request.nonce,
            request.deadline
        ));
    }

    function _verifyEd25519Signature(
        bytes32 messageHash,
        bytes calldata signature,
        bytes32 pubkey
    ) internal pure returns (bool) {
        require(signature.length == 64, "Invalid signature length");
        
        bytes32 r = bytes32(signature[0:32]);
        bytes32 s = bytes32(signature[32:64]);
        
        return ED25519.verify(messageHash, pubkey, r, s);
    }

    // ===================== ADMIN FUNCTIONS =====================

    function setValidatorSet(address _validatorSet) external onlyOwner {
        validatorSet = IValidatorSet(_validatorSet);
    }

    function setAttestationThreshold(uint256 _threshold) external onlyOwner {
        require(_threshold > 0, "Invalid threshold");
        attestationThreshold = _threshold;
    }

    function setCompositionTolerance(uint256 _tolerance) external onlyOwner {
        require(_tolerance <= 2000, "Tolerance too high"); // Max 20%
        compositionTolerance = _tolerance;
    }

    function setSubnetVaultHotkey(uint16 netuid, bytes32 hotkey) external onlyOwner {
        subnetVaultHotkeys[netuid] = hotkey;
    }

    function pause() external onlyOwner {
        _pause();
    }

    function unpause() external onlyOwner {
        _unpause();
    }

    // ===================== VIEW FUNCTIONS =====================

    function getYieldAdjustedNAV() external view returns (uint256) {
        return _getYieldAdjustedNAV();
    }

    function getSubnetStakingInfo(uint16 netuid) external view returns (
        uint256 staked,
        uint256 yield,
        uint256 lastUpdate,
        bytes32 vaultHotkey
    ) {
        return (
            subnetStaked[netuid],
            accumulatedYield[netuid],
            lastYieldUpdate[netuid],
            subnetVaultHotkeys[netuid]
        );
    }

    function getTotalValue() external view returns (uint256) {
        uint256 totalValue = 0;
        (uint256[] memory netuids, ) = validatorSet.getWeights(validatorSet.currentEpochId());
        
        for (uint i = 0; i < netuids.length; i++) {
            uint16 netuid = uint16(netuids[i]);
            totalValue += subnetStaked[netuid] / 1e9; // Convert from RAO
            totalValue += accumulatedYield[netuid];
        }
        
        return totalValue;
    }
}
