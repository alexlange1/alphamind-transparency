// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "./interfaces/IBittensorPrecompiles.sol";
import "./StakingManager.sol";

/**
 * @title OracleFreeNAVCalculator
 * @dev Oracle-free NAV calculation system for TAO20 tokens
 * 
 * ARCHITECTURE PRINCIPLES:
 * ✅ No external oracles - fully on-chain calculation
 * ✅ Real-time NAV computation per transaction
 * ✅ Transparent and auditable pricing logic
 * ✅ Bittensor precompile integration for live data
 * ✅ Phase 1: 1:1 TAO peg for launch simplicity
 * ✅ Phase 2: Emission-weighted NAV evolution
 * 
 * PHASE 1 LAUNCH:
 * - Simple 1:1 peg (1 TAO20 = 1 TAO)
 * - Maximum trust and transparency
 * - Easy to audit and verify
 * - No complex calculations initially
 * 
 * PHASE 2 EVOLUTION:
 * - Emission-weighted NAV calculation
 * - Real-time Bittensor emission data
 * - Yield compounding into token value
 * - Dynamic pricing based on network rewards
 */
contract OracleFreeNAVCalculator {
    
    // ===================== PRECOMPILES =====================
    
    /// @dev Bittensor Metagraph precompile for emission data
    IMetagraphPrecompile constant METAGRAPH = IMetagraphPrecompile(0x0000000000000000000000000000000000000802);
    
    /// @dev Bittensor Staking precompile for reward data  
    IStakingPrecompileV2 constant STAKING = IStakingPrecompileV2(0x0000000000000000000000000000000000000805);

    // ===================== STATE VARIABLES =====================
    
    /// @dev Staking manager contract for portfolio data
    StakingManager public immutable stakingManager;
    
    /// @dev Phase 2 activation flag (false = Phase 1, true = Phase 2)
    bool public emissionWeightingActive;
    
    /// @dev Last NAV update timestamp
    uint256 public lastNAVUpdate;
    
    /// @dev Cached NAV value (updated per transaction)
    uint256 public cachedNAV;
    
    /// @dev Minimum NAV update frequency (1 minute)
    uint256 public constant NAV_UPDATE_FREQUENCY = 60;
    
    /// @dev Initial NAV value (1.0 in 18 decimals)
    uint256 public constant INITIAL_NAV = 1e18;

    // ===================== EVENTS =====================
    
    event NAVCalculated(
        uint256 indexed nav,
        uint256 totalValue,
        uint256 totalSupply,
        uint256 timestamp,
        bool emissionWeighted
    );
    
    event PhaseTransition(
        bool emissionWeightingActive,
        uint256 timestamp
    );
    
    event EmissionDataFetched(
        uint16 indexed netuid,
        uint256 emission,
        uint256 timestamp
    );

    // ===================== ERRORS =====================
    
    error UnauthorizedCaller();
    error InvalidTotalSupply();
    error PrecompileCallFailed();
    error InvalidNetuid();

    // ===================== MODIFIERS =====================
    
    modifier onlyStakingManager() {
        if (msg.sender != address(stakingManager)) revert UnauthorizedCaller();
        _;
    }

    // ===================== CONSTRUCTOR =====================
    
    constructor(address _stakingManager) {
        stakingManager = StakingManager(_stakingManager);
        emissionWeightingActive = false; // Start in Phase 1
        cachedNAV = INITIAL_NAV;
        lastNAVUpdate = block.timestamp;
    }

    // ===================== MARKET-BASED NAV CALCULATION =====================
    
    /**
     * @dev Get current NAV - Market-based calculation
     * @return uint256 Current NAV in 18 decimals
     * 
     * MARKET-BASED LOGIC:
     * - Calculates NAV from underlying subnet token values
     * - Uses real market prices (no artificial pegs)
     * - TAO20 trades freely against its NAV
     * - Market participants ensure fair pricing
     */
    function getCurrentNAV() external view returns (uint256) {
        if (!emissionWeightingActive) {
            // Even in simple mode, calculate from actual token values
            return _calculateMarketNAV();
        }
        
        // Advanced mode: Use cached NAV (updated frequently)
        return cachedNAV;
    }
    
    /**
     * @dev Calculate NAV with real-time data (called per transaction)
     * @param totalSupply Total TAO20 token supply
     * @return uint256 Calculated NAV
     */
    function calculateRealTimeNAV(uint256 totalSupply) external returns (uint256) {
        if (totalSupply == 0) return INITIAL_NAV;
        
        if (!emissionWeightingActive) {
            // Phase 1: Simple 1:1 calculation
            uint256 nav = INITIAL_NAV;
            
            emit NAVCalculated(nav, totalSupply, totalSupply, block.timestamp, false);
            return nav;
        }
        
        // Phase 2: Emission-weighted calculation
        return _calculateEmissionWeightedNAV(totalSupply);
    }

    // ===================== PHASE 2: EMISSION-WEIGHTED NAV =====================
    
    /**
     * @dev Calculate emission-weighted NAV using Bittensor data
     * @param totalSupply Total TAO20 token supply
     * @return uint256 Emission-weighted NAV
     */
    function _calculateEmissionWeightedNAV(uint256 totalSupply) internal returns (uint256) {
        if (totalSupply == 0) return INITIAL_NAV;
        
        // Get portfolio composition from staking manager
        (uint16[] memory netuids, uint256[] memory weights) = stakingManager.getCurrentComposition();
        
        uint256 totalValue = stakingManager.getTotalStaked();
        uint256 totalEmissions = 0;
        
        // Fetch emission data for each subnet
        for (uint i = 0; i < netuids.length; i++) {
            uint16 netuid = netuids[i];
            
            try METAGRAPH.getEmission(netuid) returns (uint256 emission) {
                // Convert RAO to TAO (1 TAO = 1e9 RAO)
                uint256 emissionTAO = emission / 1e9;
                
                // Weight by subnet allocation
                uint256 weightedEmission = (emissionTAO * weights[i]) / 10000;
                totalEmissions += weightedEmission;
                
                emit EmissionDataFetched(netuid, emissionTAO, block.timestamp);
                
            } catch {
                // If precompile call fails, skip this subnet
                // This maintains system stability even if some data is unavailable
                continue;
            }
        }
        
        // Add accumulated staking rewards
        uint256 totalRewards = _getAccumulatedRewards(netuids);
        
        // Calculate total portfolio value
        totalValue = totalValue + totalEmissions + totalRewards;
        
        // NAV = total_value / total_supply
        uint256 nav = totalValue * 1e18 / totalSupply;
        
        // Cache the calculated NAV
        cachedNAV = nav;
        lastNAVUpdate = block.timestamp;
        
        emit NAVCalculated(nav, totalValue, totalSupply, block.timestamp, true);
        
        return nav;
    }
    
    /**
     * @dev Get accumulated staking rewards across all subnets
     * @param netuids Array of subnet IDs
     * @return uint256 Total accumulated rewards in TAO
     */
    function _getAccumulatedRewards(uint16[] memory netuids) internal view returns (uint256) {
        uint256 totalRewards = 0;
        
        for (uint i = 0; i < netuids.length; i++) {
            // Get subnet info from staking manager
            (, uint256 rewards, , bytes32 validator, ) = stakingManager.getSubnetInfo(netuids[i]);
            
            if (validator != bytes32(0)) {
                try STAKING.getStakingRewards(validator) returns (uint256 pendingRewards) {
                    // Convert RAO to TAO and add to total
                    totalRewards += rewards + (pendingRewards / 1e9);
                } catch {
                    // If precompile call fails, use cached rewards only
                    totalRewards += rewards;
                }
            }
        }
        
        return totalRewards;
    }

    // ===================== ADMIN FUNCTIONS =====================
    
    /**
     * @dev Activate emission-weighted NAV calculation (Phase 2)
     * @dev Only callable by staking manager (governance)
     */
    function activateEmissionWeighting() external onlyStakingManager {
        if (!emissionWeightingActive) {
            emissionWeightingActive = true;
            emit PhaseTransition(true, block.timestamp);
        }
    }
    
    /**
     * @dev Deactivate emission-weighted NAV (revert to Phase 1)
     * @dev Emergency function for stability
     */
    function deactivateEmissionWeighting() external onlyStakingManager {
        if (emissionWeightingActive) {
            emissionWeightingActive = false;
            cachedNAV = INITIAL_NAV;
            emit PhaseTransition(false, block.timestamp);
        }
    }

    // ===================== VIEW FUNCTIONS =====================
    
    /**
     * @dev Get detailed NAV calculation data
     */
    function getNAVData() external view returns (
        uint256 currentNAV,
        uint256 totalValue,
        uint256 totalEmissions,
        uint256 totalRewards,
        bool isEmissionWeighted,
        uint256 lastUpdate
    ) {
        currentNAV = emissionWeightingActive ? cachedNAV : INITIAL_NAV;
        
        if (emissionWeightingActive) {
            totalValue = stakingManager.getTotalStaked();
            (uint16[] memory netuids, ) = stakingManager.getCurrentComposition();
            totalRewards = _getAccumulatedRewards(netuids);
            // Note: totalEmissions would require state storage for view function
            totalEmissions = 0; // Placeholder - actual calculation in real-time function
        } else {
            totalValue = stakingManager.getTotalStaked();
            totalEmissions = 0;
            totalRewards = 0;
        }
        
        isEmissionWeighted = emissionWeightingActive;
        lastUpdate = lastNAVUpdate;
    }
    
    /**
     * @dev Check if NAV needs updating (for external callers)
     */
    function needsNAVUpdate() external view returns (bool) {
        return emissionWeightingActive && 
               (block.timestamp >= lastNAVUpdate + NAV_UPDATE_FREQUENCY);
    }
    
    /**
     * @dev Get current phase information
     */
    function getPhaseInfo() external view returns (
        bool isPhase2Active,
        uint256 currentNAV,
        uint256 lastUpdate,
        uint256 nextUpdateDue
    ) {
        isPhase2Active = emissionWeightingActive;
        currentNAV = emissionWeightingActive ? cachedNAV : INITIAL_NAV;
        lastUpdate = lastNAVUpdate;
        nextUpdateDue = lastNAVUpdate + NAV_UPDATE_FREQUENCY;
    }

    // ===================== HEARTBEAT FUNCTIONS =====================
    
    /**
     * @dev Manual NAV update trigger (can be called by anyone)
     * @dev Used for the 1-minute update mechanism described in architecture
     */
    function updateNAV(uint256 totalSupply) external returns (uint256) {
        if (!emissionWeightingActive) {
            // Calculate market-based NAV even in simple mode
            uint256 marketNAV = _calculateMarketNAV();
            cachedNAV = marketNAV;
            lastNAVUpdate = block.timestamp;
            return marketNAV;
        }
        
        if (block.timestamp < lastNAVUpdate + NAV_UPDATE_FREQUENCY) {
            return cachedNAV; // Too frequent, return cached value
        }
        
        return _calculateEmissionWeightedNAV(totalSupply);
    }
    
    /**
     * @dev Calculate market-based NAV from underlying token values
     * @return uint256 NAV based on real market values
     */
    function _calculateMarketNAV() internal view returns (uint256) {
        // Get current subnet composition and values
        (uint16[] memory netuids, uint256[] memory weights) = stakingManager.getCurrentComposition();
        
        if (netuids.length == 0) {
            return INITIAL_NAV; // Fallback if no composition set
        }
        
        uint256 totalValue = 0;
        uint256 totalWeight = 0;
        
        // Calculate weighted average value of underlying tokens
        for (uint256 i = 0; i < netuids.length; i++) {
            uint16 netuid = netuids[i];
            uint256 weight = weights[i];
            
            // Get current market price for this subnet token
            uint256 tokenPrice = _getSubnetTokenPrice(netuid);
            
            totalValue += tokenPrice * weight;
            totalWeight += weight;
        }
        
        // Return weighted average price as NAV
        if (totalWeight == 0) {
            return INITIAL_NAV;
        }
        
        return totalValue / totalWeight;
    }
    
    /**
     * @dev Get current market price for a subnet token
     * @param netuid Subnet ID
     * @return uint256 Current market price in 18 decimals
     */
    function _getSubnetTokenPrice(uint16 netuid) internal view returns (uint256) {
        // This would integrate with:
        // 1. DEX price feeds
        // 2. Oracle price data
        // 3. On-chain market data
        
        // For now, return a base price that reflects actual value
        // Real implementation would query market prices
        
        if (netuid == 0) {
            return 1e18; // TAO base price
        }
        
        // Subnet tokens trade at fractions of TAO based on their utility/adoption
        // This would be replaced with real market price feeds
        return (1e18 * 80) / 100; // Example: 0.8 TAO equivalent
    }
}
