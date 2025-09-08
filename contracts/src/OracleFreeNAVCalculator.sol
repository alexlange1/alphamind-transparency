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

    // ===================== PHASE 1: SIMPLE NAV CALCULATION =====================
    
    /**
     * @dev Get current NAV - Phase 1 implementation (1:1 peg)
     * @return uint256 Current NAV in 18 decimals
     * 
     * PHASE 1 LOGIC:
     * - Always returns 1.0 (1e18)
     * - Maximum simplicity and trust
     * - Easy to audit and verify
     * - No complex calculations
     */
    function getCurrentNAV() external view returns (uint256) {
        if (!emissionWeightingActive) {
            return INITIAL_NAV; // 1:1 peg in Phase 1
        }
        
        // Phase 2: Use cached NAV (updated frequently)
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
            return INITIAL_NAV; // No updates needed in Phase 1
        }
        
        if (block.timestamp < lastNAVUpdate + NAV_UPDATE_FREQUENCY) {
            return cachedNAV; // Too frequent, return cached value
        }
        
        return _calculateEmissionWeightedNAV(totalSupply);
    }
}
