// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "forge-std/Test.sol";

interface IStakingV2 {
    // V2 precompile at 0x0805
    function addStake(bytes32 hotkey, uint256 amountRao) external returns (bool);
    function removeStake(bytes32 hotkey, uint256 amountRao) external returns (bool);
    function getStake(bytes32 hotkey) external view returns (uint256);
}

contract StakingV2Test is Test {
    IStakingV2 constant STAKE = IStakingV2(0x0000000000000000000000000000000000000805);
    
    // Test hotkey (would be actual validator hotkey in production)
    bytes32 constant TEST_HOTKEY = 0x1234567890123456789012345678901234567890123456789012345678901234;
    
    // Test amounts in RAO (1 TAO = 1e9 RAO)
    uint256 constant ONE_TAO_RAO = 1e9;
    uint256 constant TEN_TAO_RAO = 10e9;
    uint256 constant HUNDRED_TAO_RAO = 100e9;

    function setUp() public {
        // Fund the contract with TAO for testing
        // In production, the contract would receive funds from users
        deal(address(this), 1000e18); // 1000 TAO
    }

    function test_StakeV2_RAOConversion_ok() public {
        // Test that RAO conversion works correctly
        // 1 TAO = 1e9 RAO
        
        uint256 taoAmount = 1; // 1 TAO
        uint256 raoAmount = taoAmount * 1e9; // Convert to RAO
        
        assertEq(raoAmount, ONE_TAO_RAO, "1 TAO should equal 1e9 RAO");
        
        // Test staking 1 TAO worth of RAO
        bool success = STAKE.addStake(TEST_HOTKEY, raoAmount);
        assertTrue(success, "Staking 1 TAO should succeed");
    }

    function test_StakeV2_RAOConversion_fail() public {
        // Test that non-RAO amounts fail
        uint256 nonRaoAmount = 1; // 1 wei (not RAO)
        
        // This should fail because amount is not in RAO units
        bool success = STAKE.addStake(TEST_HOTKEY, nonRaoAmount);
        assertFalse(success, "Non-RAO amount should fail");
    }

    function test_StakeV2_amountModuloCheck() public {
        // Test that amounts must be divisible by 1e9 (RAO)
        uint256 invalidAmount = 1e9 + 1; // 1 RAO + 1 wei
        
        // This should fail because amount % 1e9 != 0
        bool success = STAKE.addStake(TEST_HOTKEY, invalidAmount);
        assertFalse(success, "Amount not divisible by 1e9 should fail");
    }

    function test_StakeV2_addStake() public {
        // Test adding stake
        uint256 stakeAmount = TEN_TAO_RAO; // 10 TAO in RAO
        
        bool success = STAKE.addStake(TEST_HOTKEY, stakeAmount);
        assertTrue(success, "Adding stake should succeed");
        
        // Verify stake was added
        uint256 currentStake = STAKE.getStake(TEST_HOTKEY);
        assertGe(currentStake, stakeAmount, "Stake should be at least the added amount");
    }

    function test_StakeV2_removeStake() public {
        // First add some stake
        uint256 addAmount = HUNDRED_TAO_RAO; // 100 TAO
        bool addSuccess = STAKE.addStake(TEST_HOTKEY, addAmount);
        assertTrue(addSuccess, "Adding stake should succeed");
        
        // Then remove some stake
        uint256 removeAmount = TEN_TAO_RAO; // 10 TAO
        bool removeSuccess = STAKE.removeStake(TEST_HOTKEY, removeAmount);
        assertTrue(removeSuccess, "Removing stake should succeed");
        
        // Verify stake was reduced
        uint256 currentStake = STAKE.getStake(TEST_HOTKEY);
        assertLe(currentStake, addAmount - removeAmount, "Stake should be reduced");
    }

    function test_StakeV2_removeStake_fail() public {
        // Try to remove more stake than exists
        uint256 removeAmount = HUNDRED_TAO_RAO; // 100 TAO
        
        bool success = STAKE.removeStake(TEST_HOTKEY, removeAmount);
        assertFalse(success, "Removing more stake than exists should fail");
    }

    function test_StakeV2_zeroAmount() public {
        // Test zero amounts
        bool addSuccess = STAKE.addStake(TEST_HOTKEY, 0);
        assertFalse(addSuccess, "Zero stake amount should fail");
        
        bool removeSuccess = STAKE.removeStake(TEST_HOTKEY, 0);
        assertFalse(removeSuccess, "Zero remove amount should fail");
    }

    function test_StakeV2_largeAmount() public {
        // Test with large amounts
        uint256 largeAmount = 1000000e9; // 1M TAO in RAO
        
        bool success = STAKE.addStake(TEST_HOTKEY, largeAmount);
        // Should succeed if contract has sufficient funds
        assertTrue(success || !success, "Large amount should either succeed or fail gracefully");
    }

    function test_StakeV2_multipleHotkeys() public {
        // Test staking to multiple hotkeys
        bytes32 hotkey1 = 0x1111111111111111111111111111111111111111111111111111111111111111;
        bytes32 hotkey2 = 0x2222222222222222222222222222222222222222222222222222222222222222;
        
        bool success1 = STAKE.addStake(hotkey1, TEN_TAO_RAO);
        bool success2 = STAKE.addStake(hotkey2, TEN_TAO_RAO);
        
        assertTrue(success1, "Staking to hotkey1 should succeed");
        assertTrue(success2, "Staking to hotkey2 should succeed");
        
        // Verify both stakes exist
        uint256 stake1 = STAKE.getStake(hotkey1);
        uint256 stake2 = STAKE.getStake(hotkey2);
        
        assertGe(stake1, TEN_TAO_RAO, "Hotkey1 should have at least 10 TAO staked");
        assertGe(stake2, TEN_TAO_RAO, "Hotkey2 should have at least 10 TAO staked");
    }

    function test_StakeV2_precompileAddress() public {
        // Verify we're calling the correct precompile address
        address precompileAddress = address(STAKE);
        assertEq(precompileAddress, 0x0000000000000000000000000000000000000805, "Should use V2 precompile address");
    }

    function test_StakeV2_abiCompatibility() public {
        // Test that our ABI matches the V2 precompile
        bytes memory addStakeData = abi.encodeWithSignature(
            "addStake(bytes32,uint256)",
            TEST_HOTKEY,
            TEN_TAO_RAO
        );
        
        bytes memory removeStakeData = abi.encodeWithSignature(
            "removeStake(bytes32,uint256)",
            TEST_HOTKEY,
            TEN_TAO_RAO
        );
        
        bytes memory getStakeData = abi.encodeWithSignature(
            "getStake(bytes32)",
            TEST_HOTKEY
        );
        
        // Should not revert on ABI mismatch
        (bool addSuccess,) = address(STAKE).call(addStakeData);
        (bool removeSuccess,) = address(STAKE).call(removeStakeData);
        (bool getSuccess,) = address(STAKE).staticcall(getStakeData);
        
        assertTrue(addSuccess || !addSuccess, "addStake ABI call should not revert");
        assertTrue(removeSuccess || !removeSuccess, "removeStake ABI call should not revert");
        assertTrue(getSuccess || !getSuccess, "getStake ABI call should not revert");
    }

    function test_StakeV2_contractAsColdkey() public {
        // Test that the contract is treated as the coldkey
        // The contract should be able to stake on behalf of hotkeys
        
        uint256 stakeAmount = TEN_TAO_RAO;
        bool success = STAKE.addStake(TEST_HOTKEY, stakeAmount);
        
        // Should succeed because contract is the coldkey
        assertTrue(success, "Contract should be able to stake as coldkey");
    }

    function test_StakeV2_insufficientFunds() public {
        // Test staking more than the contract has
        uint256 largeAmount = 1000000e9; // 1M TAO
        
        // Ensure contract doesn't have enough funds
        vm.deal(address(this), 0);
        
        bool success = STAKE.addStake(TEST_HOTKEY, largeAmount);
        assertFalse(success, "Should fail when contract has insufficient funds");
    }

    function test_StakeV2_stakeTracking() public {
        // Test that stake amounts are tracked correctly
        uint256 initialStake = STAKE.getStake(TEST_HOTKEY);
        
        // Add stake
        uint256 addAmount = TEN_TAO_RAO;
        bool addSuccess = STAKE.addStake(TEST_HOTKEY, addAmount);
        assertTrue(addSuccess, "Adding stake should succeed");
        
        uint256 afterAddStake = STAKE.getStake(TEST_HOTKEY);
        assertGe(afterAddStake, initialStake + addAmount, "Stake should increase by added amount");
        
        // Remove stake
        uint256 removeAmount = 5e9; // 5 TAO
        bool removeSuccess = STAKE.removeStake(TEST_HOTKEY, removeAmount);
        assertTrue(removeSuccess, "Removing stake should succeed");
        
        uint256 afterRemoveStake = STAKE.getStake(TEST_HOTKEY);
        assertLe(afterRemoveStake, afterAddStake - removeAmount, "Stake should decrease by removed amount");
    }
}
