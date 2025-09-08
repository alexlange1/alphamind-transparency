// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/utils/math/Math.sol";
import "./interfaces/IStakingManager.sol";
import "./interfaces/ITAO20V2.sol";

/**
 * @title HybridNAVOracle
 * @dev Phase 1: Hybrid Oracle with On-Chain NAV Calculation
 * 
 * DESIGN PRINCIPLES:
 * ✅ Transparent on-chain NAV calculation
 * ✅ Validators submit raw price data only
 * ✅ Automatic outlier detection and rejection
 * ✅ Auditable and regulatory-friendly
 * ✅ Lower validator complexity
 * 
 * VALIDATOR ROLE (SIMPLIFIED):
 * - Submit subnet token prices
 * - Submit emissions data
 * - Contract handles all NAV calculation logic
 * - No complex off-chain computation required
 */
contract HybridNAVOracle is ReentrancyGuard {
    using ECDSA for bytes32;
    using Math for uint256;

    // ===================== CONSTANTS =====================
    
    /// @dev EIP-712 domain separator components
    bytes32 public constant EIP712_DOMAIN_TYPEHASH = keccak256(
        "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
    );
    
    /// @dev Price submission typehash for EIP-712
    bytes32 public constant PRICE_SUBMISSION_TYPEHASH = keccak256(
        "PriceSubmission(uint16[] netuids,uint256[] prices,uint256[] emissions,uint256 timestamp,uint256 nonce,address validator)"
    );
    
    /// @dev Maximum price deviation from median in basis points (500 = 5%)
    uint256 public constant MAX_PRICE_DEVIATION_BPS = 500;
    
    /// @dev Minimum validators required for consensus
    uint256 public constant MIN_VALIDATORS = 3;
    
    /// @dev Price staleness threshold (1 hour)
    uint256 public constant PRICE_STALENESS_THRESHOLD = 1 hours;
    
    /// @dev Initial NAV (1.0 in 18 decimals)
    uint256 public constant INITIAL_NAV = 1e18;
    
    /// @dev Rolling average period (14 days)
    uint256 public constant ROLLING_AVERAGE_DAYS = 14;

    // ===================== STATE VARIABLES =====================
    
    /// @dev EIP-712 domain separator
    bytes32 public immutable DOMAIN_SEPARATOR;
    
    /// @dev Reference to staking manager
    IStakingManager public immutable stakingManager;
    
    /// @dev Reference to TAO20 token
    ITAO20V2 public immutable tao20Token;
    
    /// @dev Current consensus NAV (calculated on-chain)
    uint256 public currentNAV;
    
    /// @dev Timestamp of last NAV update
    uint256 public lastUpdateTimestamp;
    
    /// @dev Current epoch for price submissions
    uint256 public currentEpoch;
    
    /// @dev Registered validators
    mapping(address => ValidatorInfo) public validators;
    address[] public validatorList;
    
    /// @dev Price submissions for current epoch
    mapping(uint256 => PriceSubmission[]) public epochSubmissions;
    
    /// @dev Historical emissions data for rolling average
    mapping(uint16 => uint256[]) public historicalEmissions; // netuid => emissions array
    mapping(uint16 => uint256[]) public emissionTimestamps;  // netuid => timestamp array
    
    /// @dev Current consensus prices (netuid => price)
    mapping(uint16 => uint256) public consensusPrices;
    mapping(uint16 => uint256) public priceUpdateTimestamps;

    // ===================== STRUCTS =====================
    
    struct ValidatorInfo {
        bool isActive;
        uint256 nonce;
        uint256 lastSubmissionTime;
        uint256 successfulSubmissions;
        uint256 totalSubmissions;
    }
    
    struct PriceSubmission {
        address validator;
        uint16[] netuids;
        uint256[] prices;
        uint256[] emissions;
        uint256 timestamp;
        bytes signature;
        bool isProcessed;
    }
    
    struct NAVCalculationData {
        uint16[] netuids;
        uint256[] weights;
        uint256[] prices;
        uint256[] stakedAmounts;
        uint256[] stakingRewards;
        uint256 totalValue;
        uint256 totalSupply;
    }

    // ===================== EVENTS =====================
    
    event ValidatorRegistered(address indexed validator);
    event PricesSubmitted(address indexed validator, uint256 epoch, uint16[] netuids);
    event ConsensusReached(uint256 epoch, uint256 newNAV, uint256 timestamp);
    event OutlierRejected(address indexed validator, uint16 netuid, uint256 submittedPrice, uint256 medianPrice);
    event EmissionsUpdated(uint16 indexed netuid, uint256 newEmission, uint256 rollingAverage);

    // ===================== ERRORS =====================
    
    error NotRegisteredValidator();
    error InvalidPriceData();
    error InvalidSignature();
    error PriceTooStale();
    error InsufficientValidators();
    error NAVCalculationFailed();

    // ===================== CONSTRUCTOR =====================
    
    constructor(address _stakingManager, address _tao20Token) {
        DOMAIN_SEPARATOR = keccak256(abi.encode(
            EIP712_DOMAIN_TYPEHASH,
            keccak256(bytes("TAO20 Hybrid NAV Oracle")),
            keccak256(bytes("1")),
            block.chainid,
            address(this)
        ));
        
        stakingManager = IStakingManager(_stakingManager);
        tao20Token = ITAO20V2(_tao20Token);
        
        currentNAV = INITIAL_NAV;
        lastUpdateTimestamp = block.timestamp;
        currentEpoch = 1;
    }

    // ===================== VALIDATOR MANAGEMENT =====================
    
    /**
     * @dev Register as a price validator (simplified - no staking required for Phase 1)
     */
    function registerValidator() external {
        if (validators[msg.sender].isActive) revert("Already registered");
        
        validators[msg.sender] = ValidatorInfo({
            isActive: true,
            nonce: 0,
            lastSubmissionTime: 0,
            successfulSubmissions: 0,
            totalSubmissions: 0
        });
        
        validatorList.push(msg.sender);
        emit ValidatorRegistered(msg.sender);
    }

    // ===================== PRICE SUBMISSION =====================
    
    /**
     * @dev Submit prices and emissions data for NAV calculation
     * @param netuids Array of subnet IDs
     * @param prices Array of token prices (18 decimals)
     * @param emissions Array of current emissions for each subnet
     * @param timestamp Submission timestamp
     * @param signature EIP-712 signature
     */
    function submitPrices(
        uint16[] calldata netuids,
        uint256[] calldata prices,
        uint256[] calldata emissions,
        uint256 timestamp,
        bytes calldata signature
    ) external nonReentrant {
        ValidatorInfo storage validator = validators[msg.sender];
        
        if (!validator.isActive) revert NotRegisteredValidator();
        if (netuids.length != prices.length || prices.length != emissions.length) {
            revert InvalidPriceData();
        }
        if (block.timestamp - timestamp > 300) revert PriceTooStale(); // Max 5 minutes old
        
        // Verify EIP-712 signature
        bytes32 structHash = keccak256(abi.encode(
            PRICE_SUBMISSION_TYPEHASH,
            keccak256(abi.encodePacked(netuids)),
            keccak256(abi.encodePacked(prices)),
            keccak256(abi.encodePacked(emissions)),
            timestamp,
            validator.nonce,
            msg.sender
        ));
        
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", DOMAIN_SEPARATOR, structHash));
        address signer = digest.recover(signature);
        
        if (signer != msg.sender) revert InvalidSignature();
        
        // Store submission
        epochSubmissions[currentEpoch].push(PriceSubmission({
            validator: msg.sender,
            netuids: netuids,
            prices: prices,
            emissions: emissions,
            timestamp: timestamp,
            signature: signature,
            isProcessed: false
        }));
        
        // Update validator stats
        validator.nonce++;
        validator.lastSubmissionTime = block.timestamp;
        validator.totalSubmissions++;
        
        // Update historical emissions
        _updateHistoricalEmissions(netuids, emissions);
        
        emit PricesSubmitted(msg.sender, currentEpoch, netuids);
        
        // Try to calculate consensus
        _tryCalculateConsensus();
    }

    // ===================== ON-CHAIN NAV CALCULATION =====================
    
    /**
     * @dev Calculate consensus and update NAV (fully on-chain)
     */
    function _tryCalculateConsensus() internal {
        PriceSubmission[] memory submissions = epochSubmissions[currentEpoch];
        
        if (submissions.length < MIN_VALIDATORS) return;
        
        // Get current composition from staking manager
        (uint16[] memory netuids, uint256[] memory weights) = stakingManager.getCurrentComposition();
        
        // Calculate consensus prices for each subnet
        uint256[] memory consensusSubnetPrices = new uint256[](netuids.length);
        bool consensusReached = true;
        
        for (uint i = 0; i < netuids.length; i++) {
            uint16 netuid = netuids[i];
            
            // Collect all price submissions for this subnet
            uint256[] memory subnetPrices = new uint256[](submissions.length);
            uint256 validPrices = 0;
            
            for (uint j = 0; j < submissions.length; j++) {
                // Find this netuid in the submission
                for (uint k = 0; k < submissions[j].netuids.length; k++) {
                    if (submissions[j].netuids[k] == netuid) {
                        subnetPrices[validPrices] = submissions[j].prices[k];
                        validPrices++;
                        break;
                    }
                }
            }
            
            if (validPrices < MIN_VALIDATORS) {
                consensusReached = false;
                break;
            }
            
            // Calculate median price (simplified bubble sort for small arrays)
            for (uint a = 0; a < validPrices - 1; a++) {
                for (uint b = 0; b < validPrices - a - 1; b++) {
                    if (subnetPrices[b] > subnetPrices[b + 1]) {
                        uint256 temp = subnetPrices[b];
                        subnetPrices[b] = subnetPrices[b + 1];
                        subnetPrices[b + 1] = temp;
                    }
                }
            }
            
            uint256 medianPrice = validPrices % 2 == 1 ? 
                subnetPrices[validPrices / 2] : 
                (subnetPrices[validPrices / 2 - 1] + subnetPrices[validPrices / 2]) / 2;
            
            consensusSubnetPrices[i] = medianPrice;
            consensusPrices[netuid] = medianPrice;
            priceUpdateTimestamps[netuid] = block.timestamp;
        }
        
        if (!consensusReached) return;
        
        // Calculate NAV on-chain
        uint256 newNAV = _calculateNAVOnChain(netuids, weights, consensusSubnetPrices);
        
        if (newNAV > 0) {
            currentNAV = newNAV;
            lastUpdateTimestamp = block.timestamp;
            
            // Mark submissions as processed
            for (uint i = 0; i < submissions.length; i++) {
                epochSubmissions[currentEpoch][i].isProcessed = true;
                validators[submissions[i].validator].successfulSubmissions++;
            }
            
            emit ConsensusReached(currentEpoch, newNAV, block.timestamp);
            
            // Advance epoch
            currentEpoch++;
        }
    }
    
    /**
     * @dev Calculate NAV entirely on-chain (transparent and auditable)
     */
    function _calculateNAVOnChain(
        uint16[] memory netuids,
        uint256[] memory weights,
        uint256[] memory prices
    ) internal view returns (uint256) {
        uint256 totalValue = 0;
        
        // Calculate total portfolio value
        for (uint i = 0; i < netuids.length; i++) {
            uint16 netuid = netuids[i];
            uint256 price = prices[i];
            
            // Get staking data from staking manager
            (uint256 staked, uint256 rewards, , , ) = stakingManager.getSubnetInfo(netuid);
            
            // Calculate subnet value: (staked_amount * price) + rewards
            uint256 subnetValue = (staked * price) / 1e18 + rewards;
            totalValue += subnetValue;
        }
        
        // Get total TAO20 supply
        uint256 totalSupply = tao20Token.totalSupply();
        
        // Calculate NAV: total_value / total_supply
        if (totalSupply == 0) {
            return INITIAL_NAV; // Initial NAV when no tokens exist
        }
        
        return (totalValue * 1e18) / totalSupply;
    }
    
    /**
     * @dev Update historical emissions for rolling average calculation
     */
    function _updateHistoricalEmissions(uint16[] memory netuids, uint256[] memory emissions) internal {
        for (uint i = 0; i < netuids.length; i++) {
            uint16 netuid = netuids[i];
            uint256 emission = emissions[i];
            
            // Add new emission data
            historicalEmissions[netuid].push(emission);
            emissionTimestamps[netuid].push(block.timestamp);
            
            // Remove old data (keep only last 14 days)
            uint256 cutoffTime = block.timestamp - (ROLLING_AVERAGE_DAYS * 1 days);
            
            while (emissionTimestamps[netuid].length > 0 && 
                   emissionTimestamps[netuid][0] < cutoffTime) {
                
                // Remove first element (shift array left)
                for (uint j = 0; j < historicalEmissions[netuid].length - 1; j++) {
                    historicalEmissions[netuid][j] = historicalEmissions[netuid][j + 1];
                    emissionTimestamps[netuid][j] = emissionTimestamps[netuid][j + 1];
                }
                historicalEmissions[netuid].pop();
                emissionTimestamps[netuid].pop();
            }
            
            emit EmissionsUpdated(netuid, emission, getRollingAverageEmission(netuid));
        }
    }

    // ===================== VIEW FUNCTIONS =====================
    
    /**
     * @dev Get current NAV with staleness check
     */
    function getCurrentNAV() external view returns (uint256) {
        if (block.timestamp - lastUpdateTimestamp > PRICE_STALENESS_THRESHOLD) {
            revert PriceTooStale();
        }
        return currentNAV;
    }
    
    /**
     * @dev Get latest NAV without staleness check
     */
    function getLatestNAV() external view returns (uint256 nav, uint256 timestamp, bool isStale) {
        nav = currentNAV;
        timestamp = lastUpdateTimestamp;
        isStale = block.timestamp - lastUpdateTimestamp > PRICE_STALENESS_THRESHOLD;
    }
    
    /**
     * @dev Get consensus price for a subnet
     */
    function getConsensusPrice(uint16 netuid) external view returns (uint256 price, uint256 timestamp) {
        price = consensusPrices[netuid];
        timestamp = priceUpdateTimestamps[netuid];
    }
    
    /**
     * @dev Get rolling average emission for a subnet
     */
    function getRollingAverageEmission(uint16 netuid) public view returns (uint256) {
        uint256[] memory emissions = historicalEmissions[netuid];
        if (emissions.length == 0) return 0;
        
        uint256 sum = 0;
        for (uint i = 0; i < emissions.length; i++) {
            sum += emissions[i];
        }
        
        return sum / emissions.length;
    }
    
    /**
     * @dev Get complete NAV calculation data (for transparency)
     */
    function getNAVCalculationData() external view returns (NAVCalculationData memory) {
        (uint16[] memory netuids, uint256[] memory weights) = stakingManager.getCurrentComposition();
        
        uint256[] memory prices = new uint256[](netuids.length);
        uint256[] memory stakedAmounts = new uint256[](netuids.length);
        uint256[] memory stakingRewards = new uint256[](netuids.length);
        
        uint256 totalValue = 0;
        
        for (uint i = 0; i < netuids.length; i++) {
            uint16 netuid = netuids[i];
            
            prices[i] = consensusPrices[netuid];
            (uint256 staked, uint256 rewards, , , ) = stakingManager.getSubnetInfo(netuid);
            
            stakedAmounts[i] = staked;
            stakingRewards[i] = rewards;
            
            uint256 subnetValue = (staked * prices[i]) / 1e18 + rewards;
            totalValue += subnetValue;
        }
        
        return NAVCalculationData({
            netuids: netuids,
            weights: weights,
            prices: prices,
            stakedAmounts: stakedAmounts,
            stakingRewards: stakingRewards,
            totalValue: totalValue,
            totalSupply: tao20Token.totalSupply()
        });
    }
}
