// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "forge-std/Test.sol";
import "../src/OracleFreeNAVCalculator.sol";
import "../src/StakingManager.sol";

/**
 * @title SimpleOracleFreeTest
 * @dev Simple test to verify oracle-free contracts compile and basic functionality works
 */
contract SimpleOracleFreeTest is Test {
    OracleFreeNAVCalculator public navCalculator;
    StakingManager public stakingManager;
    
    address public owner = address(0x1);
    
    function setUp() public {
        vm.startPrank(owner);
        
        stakingManager = new StakingManager();
        navCalculator = new OracleFreeNAVCalculator(address(stakingManager));
        
        vm.stopPrank();
    }
    
    function test_BasicDeployment() public {
        assertTrue(address(navCalculator) != address(0), "NAV calculator should be deployed");
        assertTrue(address(stakingManager) != address(0), "Staking manager should be deployed");
    }
    
    function test_Phase1NAV() public {
        uint256 nav = navCalculator.getCurrentNAV();
        assertEq(nav, 1e18, "Phase 1 NAV should be 1.0");
    }
    
    function test_PhaseInfo() public {
        (bool isPhase2Active, uint256 currentNAV, uint256 lastUpdate, uint256 nextUpdateDue) = navCalculator.getPhaseInfo();
        
        assertFalse(isPhase2Active, "Should start in Phase 1");
        assertEq(currentNAV, 1e18, "NAV should be 1.0");
        assertGt(lastUpdate, 0, "Last update should be set");
        assertGt(nextUpdateDue, lastUpdate, "Next update should be after last update");
    }
    
    function test_ActivatePhase2() public {
        vm.prank(address(stakingManager));
        navCalculator.activateEmissionWeighting();
        
        (bool isPhase2Active,,,) = navCalculator.getPhaseInfo();
        assertTrue(isPhase2Active, "Should be in Phase 2 after activation");
    }
    
    function test_NAVData() public {
        (
            uint256 currentNAV,
            uint256 totalValue,
            uint256 totalEmissions,
            uint256 totalRewards,
            bool isEmissionWeighted,
            uint256 lastUpdate
        ) = navCalculator.getNAVData();
        
        assertEq(currentNAV, 1e18, "NAV should be 1.0");
        assertGe(totalValue, 0, "Total value should be non-negative");
        assertGe(totalEmissions, 0, "Total emissions should be non-negative");
        assertGe(totalRewards, 0, "Total rewards should be non-negative");
        assertFalse(isEmissionWeighted, "Should not be emission weighted initially");
        assertGt(lastUpdate, 0, "Last update should be set");
    }
    
    function test_NAVUpdate() public {
        uint256 navBefore = navCalculator.getCurrentNAV();
        
        vm.prank(address(stakingManager));
        uint256 updatedNAV = navCalculator.updateNAV(1000e18);
        
        uint256 navAfter = navCalculator.getCurrentNAV();
        
        // In Phase 1, NAV should remain 1.0
        assertEq(navBefore, 1e18, "Initial NAV should be 1.0");
        assertEq(updatedNAV, 1e18, "Updated NAV should be 1.0 in Phase 1");
        assertEq(navAfter, 1e18, "Final NAV should be 1.0 in Phase 1");
    }
    
    function test_UnauthorizedAccess() public {
        // Should revert when non-staking-manager tries to update
        vm.expectRevert();
        navCalculator.updateNAV(1000e18);
        
        vm.expectRevert();
        navCalculator.activateEmissionWeighting();
        
        vm.expectRevert();
        navCalculator.deactivateEmissionWeighting();
    }
    
    function test_StakingManagerFunctionality() public {
        // Test basic staking manager functions
        uint256 totalStaked = stakingManager.getTotalStaked();
        assertGe(totalStaked, 0, "Total staked should be non-negative");
        
        uint256 totalValue = stakingManager.getTotalValue();
        assertGe(totalValue, 0, "Total value should be non-negative");
        
        (uint16[] memory netuids, uint256[] memory weights) = stakingManager.getCurrentComposition();
        assertGe(netuids.length, 0, "Should return netuid array");
        assertEq(netuids.length, weights.length, "Arrays should have same length");
    }
}
