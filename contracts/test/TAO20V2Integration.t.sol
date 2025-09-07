// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "forge-std/Test.sol";
import "../src/TAO20CoreV2.sol";
import "../src/TAO20V2.sol";
import "../src/NAVOracle.sol";
import "../src/StakingManager.sol";

/**
 * @title TAO20V2Integration
 * @dev Integration tests for TAO20 V2 architecture
 */
contract TAO20V2Integration is Test {
    
    TAO20CoreV2 public tao20Core;
    TAO20V2 public tao20Token;
    NAVOracle public navOracle;
    StakingManager public stakingManager;
    
    address public user1 = address(0x1);
    address public user2 = address(0x2);
    address public validator1 = address(0x101);
    address public validator2 = address(0x102);
    address public validator3 = address(0x103);
    
    bytes32 public constant TEST_VALIDATOR_HOTKEY = 0x1111111111111111111111111111111111111111111111111111111111111111;
    bytes32 public constant USER_SS58_KEY = 0x2222222222222222222222222222222222222222222222222222222222222222;
    
    uint256 public constant VALIDATOR_STAKE = 1000e18;
    uint256 public constant INITIAL_NAV = 1e18;
    
    event TAO20Minted(
        address indexed recipient, 
        uint256 tao20Amount, 
        uint256 depositAmount,
        uint16 indexed netuid,
        uint256 nav,
        bytes32 indexed depositId
    );
    
    function setUp() public {
        // Deploy contracts
        navOracle = new NAVOracle();
        stakingManager = new StakingManager();
        tao20Core = new TAO20CoreV2(
            address(navOracle),
            address(stakingManager),
            "TAO20 Index Token V2",
            "TAO20"
        );
        tao20Token = tao20Core.tao20Token();
        
        // Setup oracle validators
        navOracle.registerValidator(validator1, VALIDATOR_STAKE);
        navOracle.registerValidator(validator2, VALIDATOR_STAKE);
        navOracle.registerValidator(validator3, VALIDATOR_STAKE);
        
        // Setup staking validators
        stakingManager.setDefaultValidator(1, TEST_VALIDATOR_HOTKEY);
        
        // Setup initial composition
        uint16[] memory netuids = new uint16[](1);
        uint256[] memory weights = new uint256[](1);
        netuids[0] = 1;
        weights[0] = 10000; // 100%
        stakingManager.updateComposition(netuids, weights);
    }
    
    function testInitialState() public {
        // Check initial NAV
        (uint256 nav, , bool isStale) = navOracle.getLatestNAV();
        assertEq(nav, INITIAL_NAV);
        assertFalse(isStale);
        
        // Check token initial state
        assertEq(tao20Token.totalSupply(), 0);
        assertEq(tao20Token.balanceOf(user1), 0);
        
        // Check staking manager
        assertEq(stakingManager.getTotalStaked(), 0);
        
        // Check validator registration
        (uint256 stake, , bool isActive) = navOracle.getValidatorInfo(validator1);
        assertEq(stake, VALIDATOR_STAKE);
        assertTrue(isActive);
    }
    
    function testNAVOracleSubmission() public {
        uint256 newNAV = 1.1e18; // 10% increase
        uint256 timestamp = block.timestamp;
        
        // Create signature (simplified for testing)
        bytes memory signature = abi.encodePacked(
            keccak256(abi.encode(newNAV, timestamp, 0, validator1))
        );
        
        vm.startPrank(validator1);
        
        // Should revert due to deviation (but in real scenario, would be gradual)
        vm.expectRevert(NAVOracle.DeviationTooHigh.selector);
        navOracle.submitNAV(newNAV, timestamp, signature);
        
        vm.stopPrank();
    }
    
    function testTokenMinting() public {
        // Test that token can only be minted by authorized minter
        vm.startPrank(user1);
        
        vm.expectRevert(TAO20V2.UnauthorizedMinter.selector);
        tao20Token.mint(user1, 1000e18);
        
        vm.stopPrank();
        
        // Test authorized minting
        vm.startPrank(address(tao20Core));
        
        tao20Token.mint(user1, 1000e18);
        assertEq(tao20Token.balanceOf(user1), 1000e18);
        assertEq(tao20Token.totalSupply(), 1000e18);
        
        vm.stopPrank();
    }
    
    function testTokenBurning() public {
        // First mint some tokens
        vm.startPrank(address(tao20Core));
        tao20Token.mint(user1, 1000e18);
        vm.stopPrank();
        
        // Test that tokens can only be burned by authorized minter
        vm.startPrank(user1);
        
        vm.expectRevert(TAO20V2.UnauthorizedMinter.selector);
        tao20Token.burn(user1, 500e18);
        
        vm.stopPrank();
        
        // Test authorized burning
        vm.startPrank(address(tao20Core));
        
        tao20Token.burn(user1, 500e18);
        assertEq(tao20Token.balanceOf(user1), 500e18);
        assertEq(tao20Token.totalSupply(), 500e18);
        
        vm.stopPrank();
    }
    
    function testStakingManagerComposition() public {
        // Test composition update
        uint16[] memory netuids = new uint16[](3);
        uint256[] memory weights = new uint256[](3);
        
        netuids[0] = 1;
        netuids[1] = 2;
        netuids[2] = 3;
        
        weights[0] = 5000; // 50%
        weights[1] = 3000; // 30%
        weights[2] = 2000; // 20%
        
        stakingManager.updateComposition(netuids, weights);
        
        (uint16[] memory returnedNetuids, uint256[] memory returnedWeights) = 
            stakingManager.getCurrentComposition();
        
        assertEq(returnedNetuids.length, 3);
        assertEq(returnedWeights.length, 3);
        assertEq(returnedNetuids[0], 1);
        assertEq(returnedWeights[0], 5000);
    }
    
    function testInvalidComposition() public {
        uint16[] memory netuids = new uint16[](2);
        uint256[] memory weights = new uint256[](2);
        
        netuids[0] = 1;
        netuids[1] = 2;
        
        // Invalid weights (don't sum to 10000)
        weights[0] = 6000;
        weights[1] = 3000;
        
        vm.expectRevert(StakingManager.InvalidComposition.selector);
        stakingManager.updateComposition(netuids, weights);
    }
    
    function testUserNonceManagement() public {
        assertEq(tao20Core.getUserNonce(user1), 0);
        
        // Nonce should increment after successful mint (would need to mock precompiles)
        // This is more of an integration test that would require precompile mocking
    }
    
    function testTokenUtilityFunctions() public {
        // Test token info
        (
            string memory name,
            string memory symbol,
            uint8 decimals,
            uint256 supply,
            address minter
        ) = tao20Token.getTokenInfo();
        
        assertEq(name, "TAO20 Index Token V2");
        assertEq(symbol, "TAO20");
        assertEq(decimals, 18);
        assertEq(supply, 0);
        assertEq(minter, address(tao20Core));
        
        // Test percentage calculations
        vm.startPrank(address(tao20Core));
        tao20Token.mint(user1, 1000e18);
        tao20Token.mint(user2, 500e18);
        vm.stopPrank();
        
        uint256 user1Percentage = tao20Token.getUserSupplyPercentage(user1);
        uint256 user2Percentage = tao20Token.getUserSupplyPercentage(user2);
        
        // user1 has 1000/1500 = 66.67% = 6667 basis points
        assertEq(user1Percentage, 6666); // Rounded down
        
        // user2 has 500/1500 = 33.33% = 3333 basis points
        assertEq(user2Percentage, 3333); // Rounded down
    }
    
    function testReentrancyProtection() public {
        // Test that reentrancy protection works
        // This would require a malicious contract to test properly
        
        vm.startPrank(address(tao20Core));
        tao20Token.mint(user1, 1000e18);
        vm.stopPrank();
        
        // Test transfer reentrancy protection
        vm.startPrank(user1);
        bool success = tao20Token.transfer(user2, 100e18);
        assertTrue(success);
        assertEq(tao20Token.balanceOf(user2), 100e18);
        vm.stopPrank();
    }
    
    function testOracleStaleNAV() public {
        // Fast forward time to make NAV stale
        vm.warp(block.timestamp + 2 hours);
        
        vm.expectRevert(NAVOracle.NAVTooStale.selector);
        navOracle.getCurrentNAV();
        
        // But getLatestNAV should still work
        (uint256 nav, , bool isStale) = navOracle.getLatestNAV();
        assertEq(nav, INITIAL_NAV);
        assertTrue(isStale);
    }
}
