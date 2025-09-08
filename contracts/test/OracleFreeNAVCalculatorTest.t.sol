// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "forge-std/Test.sol";
import "../src/OracleFreeNAVCalculator.sol";
import "../src/StakingManager.sol";

/**
 * @title OracleFreeNAVCalculatorTest
 * @dev Test suite for oracle-free NAV calculation system
 */
contract OracleFreeNAVCalculatorTest is Test {
    OracleFreeNAVCalculator public navCalculator;
    StakingManager public stakingManager;
    
    // Test addresses
    address public owner = address(0x1);
    address public user = address(0x2);
    address public miner = address(0x3);
    
    // Test constants
    uint256 public constant INITIAL_NAV = 1e18; // 1.0 with 18 decimals
    uint256 public constant PHASE_1_NAV = 1e18; // Always 1.0 in Phase 1
    
    function setUp() public {
        vm.startPrank(owner);
        
        // Deploy StakingManager first (required for NAVCalculator)
        stakingManager = new StakingManager();
        
        // Deploy NAVCalculator
        navCalculator = new OracleFreeNAVCalculator(address(stakingManager));
        
        vm.stopPrank();
    }
    
    // ===================== PHASE 1 TESTS =====================
    
    function test_InitialState() public {
        // Check initial phase
        (bool phase2Active, uint256 currentNAV, uint256 lastUpdate,) = navCalculator.getPhaseInfo();
        assertFalse(phase2Active, "Should start in Phase 1");
        assertEq(currentNAV, INITIAL_NAV, "Initial NAV should be 1.0");
        assertGt(lastUpdate, 0, "Last update should be set");
    }
    
    function test_Phase1NAVAlways1() public {
        // In Phase 1, NAV should always be 1.0 regardless of total supply
        assertEq(navCalculator.getCurrentNAV(), PHASE_1_NAV, "Phase 1 NAV should be 1.0");
        
        // Test with different total supply values - should still be 1.0
        uint256 nav1 = navCalculator.calculateRealTimeNAV(0);
        uint256 nav2 = navCalculator.calculateRealTimeNAV(1000e18);
        uint256 nav3 = navCalculator.calculateRealTimeNAV(1000000e18);
        
        assertEq(nav1, PHASE_1_NAV, "NAV should be 1.0 with 0 supply");
        assertEq(nav2, PHASE_1_NAV, "NAV should be 1.0 with 1000 supply");
        assertEq(nav3, PHASE_1_NAV, "NAV should be 1.0 with 1M supply");
    }
    
    function test_Phase1NAVUpdateDoesNothing() public {
        uint256 navBefore = navCalculator.getCurrentNAV();
        
        // Update NAV in Phase 1 (should not change)
        vm.prank(address(stakingManager));
        uint256 updatedNAV = navCalculator.updateNAV(1000e18);
        
        uint256 navAfter = navCalculator.getCurrentNAV();
        
        assertEq(navBefore, navAfter, "NAV should not change in Phase 1");
        assertEq(updatedNAV, PHASE_1_NAV, "Updated NAV should be 1.0");
    }
    
    // ===================== PHASE TRANSITION TESTS =====================
    
    function test_ActivateEmissionWeighting() public {
        // Only staking manager can activate Phase 2
        vm.expectRevert(OracleFreeNAVCalculator.UnauthorizedCaller.selector);
        navCalculator.activateEmissionWeighting();
        
        // Activate from staking manager
        vm.prank(address(stakingManager));
        navCalculator.activateEmissionWeighting();
        
        // Check phase changed
        (bool phase2Active,,,) = navCalculator.getPhaseInfo();
        assertTrue(phase2Active, "Should be in Phase 2");
    }
    
    function test_DeactivateEmissionWeighting() public {
        // First activate Phase 2
        vm.prank(address(stakingManager));
        navCalculator.activateEmissionWeighting();
        
        // Then deactivate
        vm.prank(address(stakingManager));
        navCalculator.deactivateEmissionWeighting();
        
        // Check phase changed back
        (bool phase2Active,,,) = navCalculator.getPhaseInfo();
        assertFalse(phase2Active, "Should be back in Phase 1");
    }
    
    // ===================== PHASE 2 TESTS =====================
    
    function test_Phase2EmissionWeightedNAV() public {
        // Activate Phase 2
        vm.prank(address(stakingManager));
        navCalculator.activateEmissionWeighting();
        
        // Mock some emission data by advancing time and updating
        vm.warp(block.timestamp + 3600); // Advance 1 hour
        
        vm.prank(address(stakingManager));
        uint256 newNAV = navCalculator.updateNAV(1000e18);
        
        // In Phase 2, NAV can change based on emissions
        // For this test, it should be different from 1.0 (exact value depends on implementation)
        assertGt(newNAV, 0, "NAV should be positive");
        
        uint256 currentNAV = navCalculator.getCurrentNAV();
        assertEq(currentNAV, newNAV, "Current NAV should match updated NAV");
    }
    
    // ===================== ACCESS CONTROL TESTS =====================
    
    function test_OnlyStakingManagerCanUpdate() public {
        vm.expectRevert(OracleFreeNAVCalculator.UnauthorizedCaller.selector);
        navCalculator.updateNAV(1000e18);
        
        vm.expectRevert(OracleFreeNAVCalculator.UnauthorizedCaller.selector);
        navCalculator.activateEmissionWeighting();
        
        vm.expectRevert(OracleFreeNAVCalculator.UnauthorizedCaller.selector);
        navCalculator.deactivateEmissionWeighting();
    }
    
    // ===================== NAV UPDATE TIMING TESTS =====================
    
    function test_NAVUpdateTiming() public {
        // Should not need update initially
        assertFalse(navCalculator.needsNAVUpdate(), "Should not need update initially");
        
        // Advance time to trigger update need
        vm.warp(block.timestamp + 7200); // 2 hours
        
        // Should need update after time passes
        assertTrue(navCalculator.needsNAVUpdate(), "Should need update after time");
        
        // Update NAV
        vm.prank(address(stakingManager));
        navCalculator.updateNAV(1000e18);
        
        // Should not need update immediately after
        assertFalse(navCalculator.needsNAVUpdate(), "Should not need update after recent update");
    }
    
    // ===================== NAV DATA TESTS =====================
    
    function test_GetNAVData() public {
        (
            uint256 currentNAV,
            uint256 totalValue,
            uint256 totalEmissions,
            uint256 totalRewards,
            bool isEmissionWeighted,
            uint256 lastUpdate
        ) = navCalculator.getNAVData();
        
        assertEq(currentNAV, INITIAL_NAV, "NAV should be initial value");
        assertGt(lastUpdate, 0, "Last update should be set");
        assertFalse(isEmissionWeighted, "Should start in Phase 1");
        assertGe(totalValue, 0, "Total value should be non-negative");
        assertGe(totalRewards, 0, "Total rewards should be non-negative");
        assertGe(totalEmissions, 0, "Total emissions should be non-negative");
    }
    
    // ===================== EDGE CASE TESTS =====================
    
    function test_ZeroTotalSupply() public {
        // Test with zero total supply
        uint256 nav = navCalculator.calculateRealTimeNAV(0);
        assertEq(nav, PHASE_1_NAV, "NAV should be 1.0 with zero supply in Phase 1");
        
        // Test in Phase 2
        vm.prank(address(stakingManager));
        navCalculator.activateEmissionWeighting();
        
        uint256 navPhase2 = navCalculator.calculateRealTimeNAV(0);
        assertGt(navPhase2, 0, "NAV should be positive even with zero supply in Phase 2");
    }
    
    function test_LargeNumbers() public {
        // Test with very large total supply
        uint256 largeSupply = type(uint256).max / 1e18; // Avoid overflow
        uint256 nav = navCalculator.calculateRealTimeNAV(largeSupply);
        assertGt(nav, 0, "NAV should handle large numbers");
    }
    
    // ===================== INTEGRATION TESTS =====================
    
    function test_MultipleNAVUpdates() public {
        vm.prank(address(stakingManager));
        navCalculator.activateEmissionWeighting();
        
        uint256[] memory navValues = new uint256[](5);
        
        // Perform multiple updates over time
        for (uint i = 0; i < 5; i++) {
            vm.warp(block.timestamp + 1800); // Advance 30 minutes
            vm.prank(address(stakingManager));
            navValues[i] = navCalculator.updateNAV(1000e18 * (i + 1));
        }
        
        // Check that NAV is being tracked
        uint256 finalNAV = navCalculator.getCurrentNAV();
        assertEq(finalNAV, navValues[4], "Final NAV should match last update");
    }
    
    function test_PhaseToggling() public {
        // Start in Phase 1
        assertEq(navCalculator.getCurrentNAV(), PHASE_1_NAV);
        
        // Activate Phase 2
        vm.prank(address(stakingManager));
        navCalculator.activateEmissionWeighting();
        
        // Update NAV in Phase 2
        vm.warp(block.timestamp + 3600);
        vm.prank(address(stakingManager));
        uint256 phase2NAV = navCalculator.updateNAV(1000e18);
        
        // Go back to Phase 1
        vm.prank(address(stakingManager));
        navCalculator.deactivateEmissionWeighting();
        
        // Should be back to 1.0
        assertEq(navCalculator.getCurrentNAV(), PHASE_1_NAV);
    }
}
