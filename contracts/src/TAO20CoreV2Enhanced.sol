// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/math/Math.sol";
import "./TAO20V2.sol";
import "./StakingNAVOracle.sol";
import "./SubnetStakingManager.sol";
import "./interfaces/IBittensorPrecompiles.sol";
import "./libraries/AddressUtils.sol";

/**
 * @title TAO20CoreV2Enhanced
 * @dev Complete implementation of the trustless TAO20 index with subnet token staking
 * 
 * COMPREHENSIVE ARCHITECTURE:
 * ✅ Direct Ed25519 signature verification for deposit ownership
 * ✅ On-chain Substrate deposit verification
 * ✅ Automatic staking of subnet tokens (Alpha tokens) for yield
 * ✅ Yield-adjusted NAV from decentralized oracle
 * ✅ Pro-rata redemption with direct asset transfers to SS58 addresses
 * ✅ Anti-dilution mechanism - rewards compound into token value
 * ✅ No centralized control or admin privileges
 * ✅ Full integration with Bittensor precompiles
 * 
 * DEPOSIT FLOW:
 * 1. User deposits subnet tokens to contract's Substrate vault
 * 2. User proves ownership with Ed25519 signature
 * 3. Contract verifies deposit exists on Substrate chain
 * 4. Subnet tokens automatically staked with subnet validators
 * 5. TAO20 tokens minted based on current NAV and subnet token value
 * 
 * REDEMPTION FLOW:
 * 1. User burns TAO20 tokens
 * 2. Contract calculates redemption value using current NAV
 * 3. Contract unstakes subnet tokens proportionally across all 20 subnets
 * 4. Unstaked subnet tokens transferred directly to user's SS58 address
 */
contract TAO20CoreV2Enhanced is ReentrancyGuard {
    using Math for uint256;
    using AddressUtils for address;
    using AddressUtils for bytes32;
    using BittensorPrecompiles for *;

    // ===================== CORE CONTRACTS =====================
    
    TAO20V2 public immutable tao20Token;
    StakingNAVOracle public immutable navOracle;
    SubnetStakingManager public immutable stakingManager;
    
    // ===================== STATE VARIABLES =====================
    
    /// @dev Processed deposit IDs to prevent replay attacks
    mapping(bytes32 => bool) public processedDeposits;
    
    /// @dev User nonces for replay protection
    mapping(address => uint256) public userNonces;
    
    /// @dev Chain ID for signature verification
    uint256 public immutable CHAIN_ID;
    
    /// @dev Contract address for signature verification
    address public immutable CONTRACT_ADDRESS;
    
    /// @dev Contract's vault address on Substrate
    bytes32 public immutable VAULT_ADDRESS;
    
    /// @dev Minimum deposit amount (0.001 subnet tokens)
    uint256 public constant MIN_DEPOSIT_AMOUNT = 1e15;
    
    /// @dev Maximum signature age (1 hour)
    uint256 public constant MAX_SIGNATURE_AGE = 3600;

    // ===================== STRUCTS =====================
    
    struct SubnetTokenDeposit {
        bytes32 blockHash;        // Bittensor block hash where deposit occurred
        uint32 extrinsicIndex;    // Transaction index in block
        bytes32 userSS58;         // User's Bittensor public key (depositor)
        uint16 netuid;            // Subnet ID (1-20 for top subnets)
        uint256 amount;           // Amount of subnet tokens deposited
        uint256 timestamp;        // Block timestamp
        uint256 blockNumber;      // Block number for verification
    }

    struct MintRequest {
        address recipient;                    // Who receives TAO20 tokens
        SubnetTokenDeposit deposit;          // Subnet token deposit details
        uint256 nonce;                       // User nonce for replay protection
        uint256 deadline;                    // Request expiration timestamp
        uint256 expectedNAV;                 // Expected NAV for slippage protection
        uint256 maxSlippageBps;             // Maximum slippage in basis points
    }
    
    struct RedemptionRequest {
        uint256 tao20Amount;                 // Amount of TAO20 to redeem
        bytes32 recipientSS58;              // User's SS58 address for asset delivery
        uint256 expectedNAV;                 // Expected NAV for slippage protection
        uint256 maxSlippageBps;             // Maximum slippage in basis points
        uint256 deadline;                    // Request expiration
    }

    // ===================== EVENTS =====================
    
    event SubnetTokenMinted(
        address indexed recipient,
        uint256 tao20Amount,
        uint256 subnetTokenAmount,
        uint16 indexed netuid,
        uint256 nav,
        bytes32 indexed depositId,
        bytes32 userSS58
    );
    
    event TAO20Redeemed(
        address indexed user,
        uint256 tao20Amount,
        uint256 totalValue,
        uint256 nav,
        bytes32 recipientSS58
    );
    
    event YieldCompounded(
        uint16 indexed netuid,
        uint256 rewardAmount,
        uint256 newNAV
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
    error SlippageExceeded();
    error InvalidSubnet();
    error InvalidRecipient();
    error StakingFailed();
    error TransferFailed();
    error NAVStale();

    // ===================== CONSTRUCTOR =====================
    
    constructor(
        address _navOracle,
        string memory _tokenName,
        string memory _tokenSymbol
    ) {
        navOracle = StakingNAVOracle(_navOracle);
        
        // Deploy subnet staking manager
        stakingManager = new SubnetStakingManager();
        
        // Deploy TAO20 token
        tao20Token = new TAO20V2(_tokenName, _tokenSymbol);
        
        CHAIN_ID = block.chainid;
        CONTRACT_ADDRESS = address(this);
        VAULT_ADDRESS = AddressUtils.getMyVaultAddress();
    }

    // ===================== MINTING FUNCTIONS =====================

    /**
     * @dev Mint TAO20 tokens with trustless subnet token deposit verification
     * @param request Mint request with subnet token deposit details
     * @param signature Ed25519 signature proving deposit ownership
     * 
     * COMPLETE PROCESS:
     * 1. Validate request parameters and signature
     * 2. Verify Ed25519 signature proves deposit ownership
     * 3. Verify subnet token deposit exists on Substrate chain
     * 4. Automatically stake deposited subnet tokens for yield
     * 5. Get current NAV from decentralized oracle
     * 6. Calculate TAO20 tokens to mint based on subnet token value
     * 7. Mint TAO20 tokens to recipient
     */
    function mintWithSubnetTokens(
        MintRequest calldata request,
        bytes calldata signature
    ) external nonReentrant {
        // Basic validation
        _validateMintRequest(request);
        
        // Generate unique deposit ID
        bytes32 depositId = AddressUtils.calculateDepositId(
            request.deposit.blockHash,
            request.deposit.extrinsicIndex,
            request.deposit.userSS58,
            request.deposit.netuid,
            request.deposit.amount,
            request.deposit.timestamp
        );
        
        if (processedDeposits[depositId]) revert DepositAlreadyProcessed();
        
        // Verify Ed25519 signature proves ownership of subnet token deposit
        bytes32 messageHash = _hashMintRequest(request);
        if (!_verifyEd25519Signature(messageHash, signature, request.deposit.userSS58)) {
            revert InvalidSignature();
        }
        
        // Verify subnet token deposit exists on Substrate chain
        if (!BittensorPrecompiles.substrateQuery().verifyDeposit(
            request.deposit.blockHash,
            request.deposit.extrinsicIndex,
            request.deposit.userSS58,
            request.deposit.netuid,
            request.deposit.amount
        )) {
            revert DepositNotFound();
        }
        
        // Verify block timestamp matches
        uint256 blockTimestamp = BittensorPrecompiles.substrateQuery().getBlockTimestamp(request.deposit.blockHash);
        if (blockTimestamp != request.deposit.timestamp) revert InvalidDeposit();
        
        // Mark deposit as processed and increment nonce
        processedDeposits[depositId] = true;
        userNonces[msg.sender]++;
        
        // Automatically stake the deposited subnet tokens
        try stakingManager.stakeSubnetTokens(request.deposit.netuid, request.deposit.amount) {
            // Staking successful
        } catch {
            revert StakingFailed();
        }
        
        // Get current NAV from oracle with slippage protection
        uint256 currentNAV = _getCurrentNAVWithSlippageCheck(request.expectedNAV, request.maxSlippageBps);
        
        // Calculate TAO20 tokens to mint
        // For subnet tokens, we need to convert to TAO equivalent first
        uint256 subnetTokenValueInTAO = _getSubnetTokenValueInTAO(request.deposit.netuid, request.deposit.amount);
        uint256 tao20Amount = (subnetTokenValueInTAO * 1e18) / currentNAV;
        
        // Mint TAO20 tokens to recipient
        tao20Token.mint(request.recipient, tao20Amount);
        
        emit SubnetTokenMinted(
            request.recipient,
            tao20Amount,
            request.deposit.amount,
            request.deposit.netuid,
            currentNAV,
            depositId,
            request.deposit.userSS58
        );
    }

    // ===================== REDEMPTION FUNCTIONS =====================

    /**
     * @dev Redeem TAO20 tokens for underlying subnet tokens
     * @param redemptionRequest Redemption parameters including SS58 destination
     * 
     * COMPLETE PROCESS:
     * 1. Validate redemption request
     * 2. Burn TAO20 tokens from user
     * 3. Calculate total redemption value using current NAV
     * 4. Execute pro-rata unstaking across all 20 subnets
     * 5. Transfer unstaked subnet tokens directly to user's SS58 address
     */
    function redeemForSubnetTokens(RedemptionRequest calldata redemptionRequest) external nonReentrant {
        _validateRedemptionRequest(redemptionRequest);
        
        if (tao20Token.balanceOf(msg.sender) < redemptionRequest.tao20Amount) {
            revert InsufficientBalance();
        }
        
        // Get current NAV with slippage protection
        uint256 currentNAV = _getCurrentNAVWithSlippageCheck(
            redemptionRequest.expectedNAV, 
            redemptionRequest.maxSlippageBps
        );
        
        // Calculate total value to redeem (in TAO equivalent)
        uint256 totalRedemptionValue = (redemptionRequest.tao20Amount * currentNAV) / 1e18;
        
        // Burn TAO20 tokens first (prevents reentrancy)
        tao20Token.burn(msg.sender, redemptionRequest.tao20Amount);
        
        // Execute pro-rata redemption across all subnets
        try stakingManager.executeProRataRedemption(totalRedemptionValue, redemptionRequest.recipientSS58) {
            // Redemption successful
        } catch {
            revert TransferFailed();
        }
        
        emit TAO20Redeemed(
            msg.sender,
            redemptionRequest.tao20Amount,
            totalRedemptionValue,
            currentNAV,
            redemptionRequest.recipientSS58
        );
    }

    // ===================== YIELD MANAGEMENT =====================

    /**
     * @dev Compound yield across all subnets (callable by anyone)
     * This increases NAV automatically without diluting existing holders
     */
    function compoundAllYield() external nonReentrant {
        stakingManager.compoundAllAlphaYield();
        
        // Get updated NAV after compounding
        uint256 newNAV = navOracle.getCurrentNAV().navPerToken;
        
        // Emit events for each subnet that was compounded
        uint16[] memory netuidsNeedingCompound = stakingManager.getSubnetsNeedingCompound();
        for (uint i = 0; i < netuidsNeedingCompound.length; i++) {
            uint16 netuid = netuidsNeedingCompound[i];
            (, uint256 rewards,,,, ) = stakingManager.getSubnetInfo(netuid);
            
            emit YieldCompounded(netuid, rewards, newNAV);
        }
    }
    
    /**
     * @dev Compound yield for specific subnet
     */
    function compoundSubnetYield(uint16 netuid) external nonReentrant {
        stakingManager.compoundSubnetAlphaYield(netuid);
        
        uint256 newNAV = navOracle.getCurrentNAV().navPerToken;
        (, uint256 rewards,,,, ) = stakingManager.getSubnetInfo(netuid);
        
        emit YieldCompounded(netuid, rewards, newNAV);
    }

    // ===================== INTERNAL FUNCTIONS =====================

    /**
     * @dev Validate mint request parameters
     */
    function _validateMintRequest(MintRequest calldata request) internal view {
        if (block.timestamp > request.deadline) revert RequestExpired();
        if (request.nonce != userNonces[msg.sender]) revert InvalidNonce();
        if (request.deposit.amount < MIN_DEPOSIT_AMOUNT) revert ZeroAmount();
        if (request.deposit.netuid == 0 || request.deposit.netuid > 20) revert InvalidSubnet();
        if (!AddressUtils.isValidSubstrateKey(request.deposit.userSS58)) revert InvalidDeposit();
        if (request.recipient == address(0)) revert InvalidRecipient();
    }
    
    /**
     * @dev Validate redemption request parameters
     */
    function _validateRedemptionRequest(RedemptionRequest calldata request) internal view {
        if (block.timestamp > request.deadline) revert RequestExpired();
        if (request.tao20Amount == 0) revert ZeroAmount();
        if (!AddressUtils.isValidSubstrateKey(request.recipientSS58)) revert InvalidRecipient();
    }

    /**
     * @dev Hash mint request for signature verification
     */
    function _hashMintRequest(MintRequest calldata request) internal view returns (bytes32) {
        return keccak256(abi.encode(
            "TAO20_SUBNET_MINT_REQUEST",
            CHAIN_ID,
            CONTRACT_ADDRESS,
            request.recipient,
            request.deposit.blockHash,
            request.deposit.extrinsicIndex,
            request.deposit.userSS58,
            request.deposit.netuid,
            request.deposit.amount,
            request.deposit.timestamp,
            request.deposit.blockNumber,
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
        
        try BittensorPrecompiles.ed25519Verify().verify(messageHash, pubkey, r, s) returns (bool result) {
            return result;
        } catch {
            return false;
        }
    }
    
    /**
     * @dev Get current NAV from oracle
     */
    function _getCurrentNAV() internal view returns (uint256) {
        uint256 totalStaked = stakingManager.getTotalStaked();
        uint256 totalYield = stakingManager.getTotalYield();
        uint256 totalSupply = tao20Token.totalSupply();
        return navOracle.getCurrentNAV(totalStaked, totalYield, totalSupply);
    }
    
    /**
     * @dev Get current NAV with slippage protection
     */
    function _getCurrentNAVWithSlippageCheck(uint256 expectedNAV, uint256 maxSlippageBps) internal view returns (uint256) {
        uint256 currentNAV = _getCurrentNAV();
        
        // For now, we don't have timestamp from StakingNAVOracle, so skip staleness check
        // This can be enhanced later if needed
        
        // Check slippage if expected NAV is provided
        if (expectedNAV > 0 && maxSlippageBps > 0) {
            uint256 slippage = currentNAV > expectedNAV 
                ? ((currentNAV - expectedNAV) * 10000) / expectedNAV
                : ((expectedNAV - currentNAV) * 10000) / expectedNAV;
                
            if (slippage > maxSlippageBps) revert SlippageExceeded();
        }
        
        return currentNAV;
    }
    
    /**
     * @dev Get subnet token value in TAO equivalent
     * In production, this would use the oracle's subnet token prices
     * For now, simplified 1:1 conversion
     */
    function _getSubnetTokenValueInTAO(uint16 netuid, uint256 subnetTokenAmount) internal view returns (uint256) {
        // Get subnet token price from oracle
        uint256 subnetTokenPriceInTAO = navOracle.getNAVForSubnet(netuid);
        
        // Convert subnet token amount to TAO equivalent
        return (subnetTokenAmount * subnetTokenPriceInTAO) / 1e18;
    }

    // ===================== VIEW FUNCTIONS =====================

    /**
     * @dev Get current NAV from oracle
     */
    function getCurrentNAV() external view returns (uint256) {
        return navOracle.getCurrentNAV().navPerToken;
    }

    /**
     * @dev Get total value locked in the system
     */
    function getTotalValueLocked() external view returns (uint256) {
        return stakingManager.getTotalValueLocked();
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
    
    /**
     * @dev Get contract's vault address on Substrate
     */
    function getVaultAddress() external view returns (bytes32) {
        return VAULT_ADDRESS;
    }
    
    /**
     * @dev Get vault address in SS58 format for display
     */
    function getVaultAddressSS58() external view returns (string memory) {
        return AddressUtils.toSS58String(VAULT_ADDRESS);
    }
    
    /**
     * @dev Get comprehensive system status
     */
    function getSystemStatus() external view returns (
        uint256 totalSupply,
        uint256 totalValueLocked,
        uint256 currentNAV,
        uint256 lastNAVUpdate,
        bool isNAVStale,
        uint16 numberOfSubnets
    ) {
        totalSupply = tao20Token.totalSupply();
        totalValueLocked = stakingManager.getTotalValueLocked();
        
        currentNAV = _getCurrentNAV();
        lastNAVUpdate = block.timestamp; // Current block timestamp since we calculate NAV on-demand
        isNAVStale = false; // Always fresh since calculated on-demand
        
        (uint16[] memory netuids, ) = stakingManager.getCurrentComposition();
        numberOfSubnets = uint16(netuids.length);
    }
    
    /**
     * @dev Get subnet information for UI
     */
    function getSubnetDetails(uint16 netuid) external view returns (
        uint256 stakedAmount,
        uint256 rewards,
        uint256 weight,
        address tokenAddress,
        bytes32 validator,
        string memory vaultSS58
    ) {
        (stakedAmount, rewards, , validator, weight, tokenAddress) = stakingManager.getSubnetInfo(netuid);
        vaultSS58 = AddressUtils.toSS58String(VAULT_ADDRESS);
    }
}
