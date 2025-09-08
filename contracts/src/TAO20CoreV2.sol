// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/math/Math.sol";
import "./TAO20V2.sol";
import "./StakingNAVOracle.sol";
import "./StakingManager.sol";

// ===================== INTERFACES =====================

interface IEd25519Verify {
    function verify(bytes32 message, bytes32 pubkey, bytes32 r, bytes32 s) external pure returns (bool);
}

interface ISubstrateQuery {
    function verifyDeposit(bytes32 blockHash, uint32 extrinsicIndex, bytes32 userSS58, uint16 netuid, uint256 amount) external view returns (bool);
    function getBlockTimestamp(bytes32 blockHash) external view returns (uint256);
}

/**
 * @title TAO20CoreV2
 * @dev Trustless TAO20 index implementation with direct verification
 * 
 * KEY FEATURES:
 * ✅ No validator attestations required for minting/redeeming
 * ✅ Direct Ed25519 signature verification
 * ✅ On-chain Substrate deposit verification
 * ✅ Automatic staking integration
 * ✅ Yield-adjusted NAV from oracle
 * ✅ No artificial limits or emergency controls
 * ✅ Fully decentralized and trustless
 */
contract TAO20CoreV2 is ReentrancyGuard {
    using Math for uint256;

    // ===================== PRECOMPILES =====================
    
    /// @dev Ed25519 signature verification precompile
    IEd25519Verify constant ED25519 = IEd25519Verify(0x0000000000000000000000000000000000000402);
    
    /// @dev Substrate query precompile for deposit verification
    ISubstrateQuery constant SUBSTRATE = ISubstrateQuery(0x0000000000000000000000000000000000000803);

    // ===================== CORE CONTRACTS =====================
    
    TAO20V2 public immutable tao20Token;
    StakingNAVOracle public immutable navOracle;
    StakingManager public immutable stakingManager;
    
    // ===================== STATE VARIABLES =====================
    
    /// @dev Processed deposit IDs to prevent replay attacks
    mapping(bytes32 => bool) public processedDeposits;
    
    /// @dev User nonces for replay protection
    mapping(address => uint256) public userNonces;
    
    /// @dev Chain ID for signature verification
    uint256 public immutable CHAIN_ID;
    
    /// @dev Contract address for signature verification
    address public immutable CONTRACT_ADDRESS;

    // ===================== STRUCTS =====================
    
    struct SubstrateDeposit {
        bytes32 blockHash;        // Bittensor block hash
        uint32 extrinsicIndex;    // Transaction index in block
        bytes32 userSS58;         // User's Bittensor public key
        uint16 netuid;            // Subnet ID
        uint256 amount;           // Amount deposited (in TAO base units)
        uint256 timestamp;        // Block timestamp
    }

    struct MintRequest {
        address recipient;        // Who receives TAO20 tokens
        SubstrateDeposit deposit; // Substrate deposit details
        uint256 nonce;            // User nonce for replay protection
        uint256 deadline;         // Request expiration timestamp
    }

    // ===================== EVENTS =====================
    
    event TAO20Minted(
        address indexed recipient, 
        uint256 tao20Amount, 
        uint256 depositAmount,
        uint16 indexed netuid,
        uint256 nav,
        bytes32 indexed depositId
    );
    
    event TAO20Redeemed(
        address indexed user, 
        uint256 tao20Amount, 
        uint256 totalValue,
        uint256 nav
    );

    // ===================== ERRORS =====================
    
    error InvalidSignature();
    error RequestExpired();
    error InvalidNonce();
    error DepositAlreadyProcessed();
    error DepositNotFound();
    error InvalidDeposit();
    error ZeroAmount();
    error InsufficientBalance();

    // ===================== CONSTRUCTOR =====================
    
    constructor(
        address _navOracle,
        address _stakingManager,
        string memory _tokenName,
        string memory _tokenSymbol
    ) {
        navOracle = StakingNAVOracle(_navOracle);
        stakingManager = StakingManager(_stakingManager);
        tao20Token = new TAO20V2(_tokenName, _tokenSymbol);
        
        CHAIN_ID = block.chainid;
        CONTRACT_ADDRESS = address(this);
    }

    // ===================== CORE FUNCTIONS =====================

    /**
     * @dev Mint TAO20 tokens with trustless verification
     * @param request Mint request with SUBNET TOKEN deposit details
     * @param signature Ed25519 signature proving deposit ownership
     * 
     * PROCESS:
     * 1. User deposits subnet tokens (Alpha tokens) to Substrate vault
     * 2. User proves ownership with Ed25519 signature
     * 3. Contract verifies deposit of subnet tokens exists
     * 4. Subnet tokens are automatically staked for yield
     * 5. TAO20 tokens minted based on subnet token value
     */
    function mintTAO20(
        MintRequest calldata request,
        bytes calldata signature
    ) external nonReentrant {
        // Basic validation
        if (block.timestamp > request.deadline) revert RequestExpired();
        if (request.nonce != userNonces[msg.sender]) revert InvalidNonce();
        if (request.deposit.amount == 0) revert ZeroAmount();
        
        // Generate unique deposit ID
        bytes32 depositId = _getDepositId(request.deposit);
        if (processedDeposits[depositId]) revert DepositAlreadyProcessed();
        
        // Verify Ed25519 signature proves ownership of deposit
        bytes32 messageHash = _hashMintRequest(request);
        if (!_verifyEd25519Signature(messageHash, signature, request.deposit.userSS58)) {
            revert InvalidSignature();
        }
        
        // Verify deposit exists on Substrate chain
        if (!SUBSTRATE.verifyDeposit(
            request.deposit.blockHash,
            request.deposit.extrinsicIndex,
            request.deposit.userSS58,
            request.deposit.netuid,
            request.deposit.amount
        )) {
            revert DepositNotFound();
        }
        
        // Verify block timestamp matches
        uint256 blockTimestamp = SUBSTRATE.getBlockTimestamp(request.deposit.blockHash);
        if (blockTimestamp != request.deposit.timestamp) revert InvalidDeposit();
        
        // Mark deposit as processed and increment nonce
        processedDeposits[depositId] = true;
        userNonces[msg.sender]++;
        
        // Stake the deposited amount automatically
        stakingManager.stakeForSubnet(request.deposit.netuid, request.deposit.amount);
        
        // Get current NAV from oracle
        uint256 totalStaked = stakingManager.getTotalStaked();
        uint256 totalYield = stakingManager.getTotalYield();
        uint256 totalSupply = tao20Token.totalSupply();
        uint256 currentNAV = navOracle.getCurrentNAV(totalStaked, totalYield, totalSupply);
        
        // Calculate TAO20 tokens to mint (18 decimals)
        // TAO20_amount = deposit_amount * 1e18 / NAV
        uint256 tao20Amount = (request.deposit.amount * 1e18) / currentNAV;
        
        // Mint tokens to recipient
        tao20Token.mint(request.recipient, tao20Amount);
        
        emit TAO20Minted(
            request.recipient,
            tao20Amount,
            request.deposit.amount,
            request.deposit.netuid,
            currentNAV,
            depositId
        );
    }

    /**
     * @dev Redeem TAO20 tokens for underlying staked assets
     * @param amount Amount of TAO20 tokens to redeem
     */
    function redeemTAO20(uint256 amount) external nonReentrant {
        if (amount == 0) revert ZeroAmount();
        if (tao20Token.balanceOf(msg.sender) < amount) revert InsufficientBalance();
        
        // Get current NAV from oracle
        uint256 totalStaked = stakingManager.getTotalStaked();
        uint256 totalYield = stakingManager.getTotalYield();
        uint256 totalSupply = tao20Token.totalSupply();
        uint256 currentNAV = navOracle.getCurrentNAV(totalStaked, totalYield, totalSupply);
        
        // Calculate total value to redeem
        // total_value = TAO20_amount * NAV / 1e18
        uint256 totalValue = (amount * currentNAV) / 1e18;
        
        // Burn TAO20 tokens first
        tao20Token.burn(msg.sender, amount);
        
        // Get current index composition from staking manager
        (uint16[] memory netuids, uint256[] memory weights) = stakingManager.getCurrentComposition();
        
        // Unstake proportionally and transfer to user
        for (uint i = 0; i < netuids.length; i++) {
            uint256 subnetValue = (totalValue * weights[i]) / 10000; // weights in basis points
            
            if (subnetValue > 0) {
                stakingManager.unstakeAndTransfer(netuids[i], subnetValue, msg.sender);
            }
        }
        
        emit TAO20Redeemed(msg.sender, amount, totalValue, currentNAV);
    }

    // ===================== INTERNAL FUNCTIONS =====================

    /**
     * @dev Generate unique deposit ID
     */
    function _getDepositId(SubstrateDeposit memory deposit) internal pure returns (bytes32) {
        return keccak256(abi.encode(
            deposit.blockHash,
            deposit.extrinsicIndex,
            deposit.userSS58,
            deposit.netuid,
            deposit.amount,
            deposit.timestamp
        ));
    }

    /**
     * @dev Hash mint request for signature verification
     */
    function _hashMintRequest(MintRequest calldata request) internal view returns (bytes32) {
        return keccak256(abi.encode(
            "TAO20_MINT_REQUEST",
            CHAIN_ID,
            CONTRACT_ADDRESS,
            request.recipient,
            request.deposit.blockHash,
            request.deposit.extrinsicIndex,
            request.deposit.userSS58,
            request.deposit.netuid,
            request.deposit.amount,
            request.deposit.timestamp,
            request.nonce,
            request.deadline
        ));
    }

    /**
     * @dev Verify Ed25519 signature with enhanced safety
     */
    function _verifyEd25519Signature(
        bytes32 messageHash,
        bytes calldata signature,
        bytes32 pubkey
    ) internal pure returns (bool) {
        if (signature.length != 64) return false;
        if (pubkey == bytes32(0)) return false;
        if (messageHash == bytes32(0)) return false;
        
        bytes32 r = bytes32(signature[0:32]);
        bytes32 s = bytes32(signature[32:64]);
        
        try ED25519.verify(messageHash, pubkey, r, s) returns (bool result) {
            return result;
        } catch {
            return false;
        }
    }

    // ===================== VIEW FUNCTIONS =====================

    /**
     * @dev Get current NAV from oracle
     */
    function getCurrentNAV() external view returns (uint256) {
        uint256 totalStaked = stakingManager.getTotalStaked();
        uint256 totalYield = stakingManager.getTotalYield();
        uint256 totalSupply = tao20Token.totalSupply();
        return navOracle.getCurrentNAV(totalStaked, totalYield, totalSupply);
    }

    /**
     * @dev Get total value locked in the system
     */
    function getTotalValueLocked() external view returns (uint256) {
        return stakingManager.getTotalStaked();
    }

    /**
     * @dev Get user's next nonce
     */
    function getUserNonce(address user) external view returns (uint256) {
        return userNonces[user];
    }

    /**
     * @dev Check if deposit has been processed
     */
    function isDepositProcessed(bytes32 depositId) external view returns (bool) {
        return processedDeposits[depositId];
    }

    /**
     * @dev Get current index composition
     */
    function getCurrentComposition() external view returns (uint16[] memory netuids, uint256[] memory weights) {
        return stakingManager.getCurrentComposition();
    }
}
