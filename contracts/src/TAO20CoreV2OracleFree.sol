// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/math/Math.sol";
import "./TAO20V2.sol";
import "./StakingManager.sol";
import "./OracleFreeNAVCalculator.sol";
import "./interfaces/IBittensorPrecompiles.sol";

/**
 * @title TAO20CoreV2OracleFree
 * @dev Oracle-free TAO20 implementation with miner volume tracking
 * 
 * ORACLE-FREE ARCHITECTURE:
 * ✅ No external price feeds or oracles
 * ✅ On-chain NAV calculation per transaction
 * ✅ Transparent and deterministic pricing
 * ✅ Real-time Bittensor precompile integration
 * 
 * MINER INCENTIVE SYSTEM:
 * ✅ Volume-based miner ranking
 * ✅ Transaction activity tracking
 * ✅ Validator consensus on miner rewards
 * ✅ Anti-gaming through on-chain verification
 * 
 * PHASE 1 LAUNCH:
 * - 1:1 TAO peg for maximum trust
 * - Simple, auditable calculations
 * - Focus on volume generation and tracking
 * 
 * PHASE 2 EVOLUTION:
 * - Emission-weighted NAV
 * - Yield compounding
 * - Advanced miner scoring
 */
contract TAO20CoreV2OracleFree is ReentrancyGuard {
    using Math for uint256;

    // ===================== PRECOMPILES =====================
    
    /// @dev Ed25519 signature verification precompile
    IEd25519Verify constant ED25519 = IEd25519Verify(0x0000000000000000000000000000000000000402);
    
    /// @dev Substrate query precompile for deposit verification
    ISubstrateQuery constant SUBSTRATE = ISubstrateQuery(0x0000000000000000000000000000000000000806);
    
    /// @dev Balance transfer precompile
    IBalanceTransfer constant BALANCE_TRANSFER = IBalanceTransfer(0x0000000000000000000000000000000000000800);

    // ===================== CORE CONTRACTS =====================
    
    TAO20V2 public immutable tao20Token;
    StakingManager public immutable stakingManager;
    OracleFreeNAVCalculator public immutable navCalculator;
    
    // ===================== MINER TRACKING STATE =====================
    
    /// @dev Total volume staked by each miner (in TAO base units)
    mapping(address => uint256) public minerVolumeStaked;
    
    /// @dev Total volume redeemed by each miner (in TAO base units)
    mapping(address => uint256) public minerVolumeRedeemed;
    
    /// @dev Total transaction count per miner
    mapping(address => uint256) public minerTransactionCount;
    
    /// @dev Last activity timestamp per miner
    mapping(address => uint256) public minerLastActivity;
    
    /// @dev Global miner activity tracking
    uint256 public totalSystemVolume;
    uint256 public totalTransactionCount;
    address[] public activeMinersList;
    mapping(address => bool) public isActiveMiner;
    
    /// @dev Epoch-based volume tracking for rewards
    mapping(uint256 => mapping(address => uint256)) public epochMinerVolume;
    uint256 public currentEpoch;
    uint256 public constant EPOCH_DURATION = 1 hours; // Hourly epochs for rewards
    uint256 public epochStartTime;

    // ===================== DEPOSIT TRACKING STATE =====================
    
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
        uint16 netuid;            // Subnet ID (0 for TAO, >0 for subnet tokens)
        uint256 amount;           // Amount deposited (in TAO base units)
        uint256 timestamp;        // Block timestamp
    }

    struct MintRequest {
        address recipient;        // Who receives TAO20 tokens
        SubstrateDeposit deposit; // Substrate deposit details
        uint256 nonce;            // User nonce for replay protection
        uint256 deadline;         // Request expiration timestamp
    }
    
    struct MinerStats {
        uint256 volumeStaked;
        uint256 volumeRedeemed;
        uint256 totalVolume;
        uint256 transactionCount;
        uint256 lastActivity;
        uint256 currentEpochVolume;
    }

    // ===================== EVENTS =====================
    
    event TAO20Minted(
        address indexed recipient,
        address indexed miner,
        uint256 tao20Amount,
        uint256 depositAmount,
        uint16 indexed netuid,
        uint256 nav,
        bytes32 depositId
    );
    
    event TAO20Redeemed(
        address indexed user,
        address indexed miner,
        uint256 tao20Amount,
        uint256 totalValue,
        uint256 nav
    );
    
    event MinerActivityTracked(
        address indexed miner,
        uint256 amount,
        bool isMint,
        uint256 timestamp,
        uint256 cumulativeVolume,
        uint256 epochVolume
    );
    
    event NAVUpdated(
        uint256 currentNAV,
        uint256 totalSupply,
        uint256 totalValue,
        uint256 timestamp
    );
    
    event EpochAdvanced(
        uint256 oldEpoch,
        uint256 newEpoch,
        uint256 timestamp
    );
    
    event NewMinerRegistered(
        address indexed miner,
        uint256 timestamp
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
    error UnauthorizedMiner();

    // ===================== CONSTRUCTOR =====================
    
    constructor(
        address _stakingManager,
        address _navCalculator,
        string memory _tokenName,
        string memory _tokenSymbol
    ) {
        stakingManager = StakingManager(_stakingManager);
        navCalculator = OracleFreeNAVCalculator(_navCalculator);
        tao20Token = new TAO20V2(_tokenName, _tokenSymbol);
        
        CHAIN_ID = block.chainid;
        CONTRACT_ADDRESS = address(this);
        
        // Initialize epoch tracking
        currentEpoch = 0;
        epochStartTime = block.timestamp;
    }

    // ===================== CORE MINTING FUNCTION =====================

    /**
     * @dev Mint TAO20 tokens with oracle-free NAV calculation
     * @param request Mint request with TAO deposit details
     * @param signature Ed25519 signature proving deposit ownership
     * 
     * ORACLE-FREE PROCESS:
     * 1. Verify deposit exists on Bittensor chain (via precompile)
     * 2. Calculate NAV in real-time using on-chain data
     * 3. Mint TAO20 tokens based on current NAV
     * 4. Track miner activity for validator consensus
     * 5. Emit events for validator monitoring
     */
    function mintTAO20(
        MintRequest calldata request,
        bytes calldata signature
    ) external nonReentrant {
        
        // ===== VALIDATION =====
        
        if (block.timestamp > request.deadline) revert RequestExpired();
        if (request.deposit.amount == 0) revert ZeroAmount();
        
        // Verify nonce
        if (request.nonce != userNonces[request.recipient]) revert InvalidNonce();
        userNonces[request.recipient]++;
        
        // Create deposit ID for replay protection
        bytes32 depositId = keccak256(abi.encode(
            request.deposit.blockHash,
            request.deposit.extrinsicIndex,
            request.deposit.userSS58,
            request.deposit.netuid,
            request.deposit.amount
        ));
        
        if (processedDeposits[depositId]) revert DepositAlreadyProcessed();
        
        // ===== SIGNATURE VERIFICATION =====
        
        bytes32 messageHash = keccak256(abi.encode(
            CHAIN_ID,
            CONTRACT_ADDRESS,
            request.recipient,
            request.deposit,
            request.nonce,
            request.deadline
        ));
        
        // Extract Ed25519 signature components
        bytes32 r = bytes32(signature[0:32]);
        bytes32 s = bytes32(signature[32:64]);
        
        if (!ED25519.verify(messageHash, request.deposit.userSS58, r, s)) {
            revert InvalidSignature();
        }
        
        // ===== DEPOSIT VERIFICATION =====
        
        bool depositExists = SUBSTRATE.verifyDeposit(
            request.deposit.blockHash,
            request.deposit.extrinsicIndex,
            request.deposit.userSS58,
            request.deposit.netuid,
            request.deposit.amount
        );
        
        if (!depositExists) revert DepositNotFound();
        
        // Mark deposit as processed
        processedDeposits[depositId] = true;
        
        // ===== ORACLE-FREE NAV CALCULATION =====
        
        uint256 currentSupply = tao20Token.totalSupply();
        uint256 currentNAV = navCalculator.calculateRealTimeNAV(currentSupply);
        
        // Calculate TAO20 tokens to mint (18 decimals)
        // TAO20_amount = deposit_amount * 1e18 / NAV
        uint256 tao20Amount = (request.deposit.amount * 1e18) / currentNAV;
        
        // ===== STAKING INTEGRATION =====
        
        // For TAO deposits (netuid == 0), stake automatically
        if (request.deposit.netuid == 0) {
            // Get current composition and stake proportionally
            (uint16[] memory netuids, uint256[] memory weights) = stakingManager.getCurrentComposition();
            
            for (uint i = 0; i < netuids.length; i++) {
                uint256 stakeAmount = (request.deposit.amount * weights[i]) / 10000;
                if (stakeAmount > 0) {
                    stakingManager.stakeForSubnet(netuids[i], stakeAmount);
                }
            }
        }
        
        // ===== MINER ACTIVITY TRACKING =====
        
        _trackMinerActivity(msg.sender, request.deposit.amount, true);
        
        // ===== TOKEN MINTING =====
        
        tao20Token.mint(request.recipient, tao20Amount);
        
        // ===== EVENTS =====
        
        emit TAO20Minted(
            request.recipient,
            msg.sender,
            tao20Amount,
            request.deposit.amount,
            request.deposit.netuid,
            currentNAV,
            depositId
        );
        
        emit NAVUpdated(currentNAV, currentSupply + tao20Amount, 0, block.timestamp);
    }

    // ===================== CORE REDEMPTION FUNCTION =====================

    /**
     * @dev Redeem TAO20 tokens for underlying assets with oracle-free pricing
     * @param amount Amount of TAO20 tokens to redeem
     */
    function redeemTAO20(uint256 amount) external nonReentrant {
        if (amount == 0) revert ZeroAmount();
        if (tao20Token.balanceOf(msg.sender) < amount) revert InsufficientBalance();
        
        // ===== ORACLE-FREE NAV CALCULATION =====
        
        uint256 currentSupply = tao20Token.totalSupply();
        uint256 currentNAV = navCalculator.calculateRealTimeNAV(currentSupply);
        
        // Calculate total value to redeem
        // total_value = TAO20_amount * NAV / 1e18
        uint256 totalValue = (amount * currentNAV) / 1e18;
        
        // ===== TOKEN BURNING =====
        
        tao20Token.burn(msg.sender, amount);
        
        // ===== PROPORTIONAL UNSTAKING =====
        
        (uint16[] memory netuids, uint256[] memory weights) = stakingManager.getCurrentComposition();
        
        for (uint i = 0; i < netuids.length; i++) {
            uint256 subnetValue = (totalValue * weights[i]) / 10000;
            
            if (subnetValue > 0) {
                stakingManager.unstakeAndTransfer(netuids[i], subnetValue, msg.sender);
            }
        }
        
        // ===== MINER ACTIVITY TRACKING =====
        
        _trackMinerActivity(msg.sender, totalValue, false);
        
        // ===== EVENTS =====
        
        emit TAO20Redeemed(msg.sender, msg.sender, amount, totalValue, currentNAV);
        emit NAVUpdated(currentNAV, currentSupply - amount, 0, block.timestamp);
    }

    // ===================== MINER TRACKING FUNCTIONS =====================
    
    /**
     * @dev Internal function to track miner activity
     * @param miner Miner address
     * @param amount Transaction amount
     * @param isMint True for mint, false for redeem
     */
    function _trackMinerActivity(address miner, uint256 amount, bool isMint) internal {
        // Check for epoch advancement
        _checkAndAdvanceEpoch();
        
        // Register new miner if needed
        if (!isActiveMiner[miner]) {
            activeMinersList.push(miner);
            isActiveMiner[miner] = true;
            emit NewMinerRegistered(miner, block.timestamp);
        }
        
        // Update miner stats
        if (isMint) {
            minerVolumeStaked[miner] += amount;
        } else {
            minerVolumeRedeemed[miner] += amount;
        }
        
        minerTransactionCount[miner]++;
        minerLastActivity[miner] = block.timestamp;
        
        // Update epoch volume
        epochMinerVolume[currentEpoch][miner] += amount;
        
        // Update global stats
        totalSystemVolume += amount;
        totalTransactionCount++;
        
        uint256 totalVolume = minerVolumeStaked[miner] + minerVolumeRedeemed[miner];
        uint256 epochVolume = epochMinerVolume[currentEpoch][miner];
        
        emit MinerActivityTracked(
            miner,
            amount,
            isMint,
            block.timestamp,
            totalVolume,
            epochVolume
        );
    }
    
    /**
     * @dev Check and advance epoch if needed
     */
    function _checkAndAdvanceEpoch() internal {
        if (block.timestamp >= epochStartTime + EPOCH_DURATION) {
            uint256 oldEpoch = currentEpoch;
            currentEpoch++;
            epochStartTime = block.timestamp;
            
            emit EpochAdvanced(oldEpoch, currentEpoch, block.timestamp);
        }
    }

    // ===================== VALIDATOR INTERFACE FUNCTIONS =====================
    
    /**
     * @dev Get comprehensive miner statistics
     * @param miner Miner address
     * @return MinerStats struct with all miner data
     */
    function getMinerStats(address miner) external view returns (MinerStats memory) {
        return MinerStats({
            volumeStaked: minerVolumeStaked[miner],
            volumeRedeemed: minerVolumeRedeemed[miner],
            totalVolume: minerVolumeStaked[miner] + minerVolumeRedeemed[miner],
            transactionCount: minerTransactionCount[miner],
            lastActivity: minerLastActivity[miner],
            currentEpochVolume: epochMinerVolume[currentEpoch][miner]
        });
    }
    
    /**
     * @dev Get epoch-specific miner volume
     * @param epoch Epoch number
     * @param miner Miner address
     * @return uint256 Volume for that epoch
     */
    function getEpochMinerVolume(uint256 epoch, address miner) external view returns (uint256) {
        return epochMinerVolume[epoch][miner];
    }
    
    /**
     * @dev Get all active miners (for validator iteration)
     * @return address[] Array of active miner addresses
     */
    function getActiveMiners() external view returns (address[] memory) {
        return activeMinersList;
    }
    
    /**
     * @dev Get current epoch information
     */
    function getEpochInfo() external view returns (
        uint256 epoch,
        uint256 startTime,
        uint256 endTime,
        uint256 remainingTime
    ) {
        epoch = currentEpoch;
        startTime = epochStartTime;
        endTime = epochStartTime + EPOCH_DURATION;
        remainingTime = block.timestamp >= endTime ? 0 : endTime - block.timestamp;
    }
    
    /**
     * @dev Get system-wide statistics
     */
    function getSystemStats() external view returns (
        uint256 totalVolume,
        uint256 totalTransactions,
        uint256 activeMinersCount,
        uint256 currentNAV,
        uint256 totalSupply
    ) {
        totalVolume = totalSystemVolume;
        totalTransactions = totalTransactionCount;
        activeMinersCount = activeMinersList.length;
        currentNAV = navCalculator.getCurrentNAV();
        totalSupply = tao20Token.totalSupply();
    }

    // ===================== HEARTBEAT FUNCTIONS =====================
    
    /**
     * @dev Manual NAV update (called by external heartbeat)
     * @dev Implements the 1-minute update mechanism from architecture
     */
    function updateNAV() external returns (uint256) {
        uint256 currentSupply = tao20Token.totalSupply();
        uint256 nav = navCalculator.updateNAV(currentSupply);
        
        emit NAVUpdated(nav, currentSupply, 0, block.timestamp);
        return nav;
    }
    
    /**
     * @dev Force epoch advancement (if needed)
     */
    function advanceEpoch() external {
        _checkAndAdvanceEpoch();
    }

    // ===================== VIEW FUNCTIONS =====================
    
    /**
     * @dev Get current NAV without state changes
     */
    function getCurrentNAV() external view returns (uint256) {
        return navCalculator.getCurrentNAV();
    }
    
    /**
     * @dev Check if NAV needs updating
     */
    function needsNAVUpdate() external view returns (bool) {
        return navCalculator.needsNAVUpdate();
    }
    
    /**
     * @dev Get detailed NAV calculation data
     */
    function getNAVDetails() external view returns (
        uint256 currentNAV,
        uint256 totalValue,
        uint256 totalEmissions,
        uint256 totalRewards,
        bool isEmissionWeighted,
        uint256 lastUpdate
    ) {
        return navCalculator.getNAVData();
    }
}
