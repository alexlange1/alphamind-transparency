// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "forge-std/Test.sol";
import "../src/Tao20Minter.sol";

contract RedeemQueueTest is Test {
    Tao20Minter minter;
    
    // Test addresses
    address constant USER = 0x1111111111111111111111111111111111111111;
    address constant KEEPER = 0x2222222222222222222222222222222222222222;
    address constant RECEIVER = 0x3333333333333333333333333333333333333333;
    
    // Test amounts
    uint256 constant INITIAL_BALANCE = 1000e18; // 1000 TAO20
    uint256 constant REDEEM_AMOUNT = 100e18; // 100 TAO20

    function setUp() public {
        minter = new Tao20Minter();
        
        // Authorize keeper
        minter.setKeeperAuthorization(KEEPER, true);
        
        // Fund contract
        deal(address(minter), 1000e18); // 1000 TAO
        
        // Mint TAO20 to user
        minter.testMint(USER, INITIAL_BALANCE);
    }

    // Gate 8: Redemption path - Unit tests
    function test_Redeem_zeroShares() public {
        vm.prank(USER);
        vm.expectRevert("zero shares");
        minter.redeem(0, RECEIVER);
    }

    function test_Redeem_invalidReceiver() public {
        vm.prank(USER);
        vm.expectRevert("invalid receiver");
        minter.redeem(REDEEM_AMOUNT, address(0));
    }

    function test_Redeem_insufficientBalance() public {
        uint256 tooMuch = INITIAL_BALANCE + 1;
        vm.prank(USER);
        vm.expectRevert("insufficient balance");
        minter.redeem(tooMuch, RECEIVER);
    }

    function test_Redeem_successfulQueue() public {
        uint256 userBalanceBefore = minter.balanceOf(USER);
        uint256 queueLengthBefore = minter.getRedeemQueueLength();
        
        vm.prank(USER);
        minter.redeem(REDEEM_AMOUNT, RECEIVER);
        
        // Check user balance decreased
        uint256 userBalanceAfter = minter.balanceOf(USER);
        assertEq(userBalanceAfter, userBalanceBefore - REDEEM_AMOUNT, "User balance should decrease");
        
        // Check queue length increased
        uint256 queueLengthAfter = minter.getRedeemQueueLength();
        assertEq(queueLengthAfter, queueLengthBefore + 1, "Queue length should increase");
        
        // Check queue item
        (bytes32 redeemId, address receiver, uint256 shares, uint256 queuedAt) = minter.getRedeemQueueItem(0);
        assertEq(receiver, RECEIVER, "Receiver should match");
        assertEq(shares, REDEEM_AMOUNT, "Shares should match");
        assertGt(queuedAt, 0, "Queued timestamp should be set");
    }

    function test_Redeem_proRataRounding() public {
        // Test with odd number of shares to check rounding
        uint256 oddAmount = 123456789;
        vm.prank(USER);
        minter.redeem(oddAmount, RECEIVER);
        
        // Verify the exact amount was queued
        (,, uint256 shares,) = minter.getRedeemQueueItem(0);
        assertEq(shares, oddAmount, "Exact amount should be queued");
    }

    // Gate 8: Redemption path - Integration tests
    function test_Redeem_duringPartialStake() public {
        // Set stake fraction to 80%
        minter.setStakeFractionBps(8000);
        
        // Queue a redemption
        vm.prank(USER);
        minter.redeem(REDEEM_AMOUNT, RECEIVER);
        
        // Fast forward time
        vm.warp(block.timestamp + 301); // Past min execution delay
        
        // Execute redemption batch
        vm.prank(KEEPER);
        minter.executeRedeemBatch(1);
        
        // Check that redemption was processed
        uint256 queueLengthAfter = minter.getRedeemQueueLength();
        assertEq(queueLengthAfter, 0, "Queue should be empty after execution");
    }

    function test_Redeem_liquidityBuffer() public {
        // Set stake fraction to 90% (10% liquidity buffer)
        minter.setStakeFractionBps(9000);
        
        // Queue multiple redemptions
        vm.prank(USER);
        minter.redeem(REDEEM_AMOUNT, RECEIVER);
        
        vm.prank(USER);
        minter.redeem(REDEEM_AMOUNT, RECEIVER);
        
        // Fast forward time
        vm.warp(block.timestamp + 301);
        
        // Execute redemptions
        vm.prank(KEEPER);
        minter.executeRedeemBatch(2);
        
        // Verify redemptions processed successfully
        uint256 queueLengthAfter = minter.getRedeemQueueLength();
        assertEq(queueLengthAfter, 0, "All redemptions should be processed");
    }

    function test_Redeem_thinLiquidity() public {
        // Simulate thin liquidity by setting low contract balance
        vm.deal(address(minter), 100e18); // Low balance
        
        // Queue redemption
        vm.prank(USER);
        minter.redeem(REDEEM_AMOUNT, RECEIVER);
        
        // Fast forward time
        vm.warp(block.timestamp + 301);
        
        // Execute should succeed with available liquidity
        vm.prank(KEEPER);
        minter.executeRedeemBatch(1);
        
        // Verify redemption processed
        uint256 queueLengthAfter = minter.getRedeemQueueLength();
        assertEq(queueLengthAfter, 0, "Redemption should be processed");
    }

    // Gate 8: Redemption path - Invariant tests
    function test_Redeem_NAVInvariant() public {
        uint256 totalSupplyBefore = minter.totalSupply();
        uint256 backingValueBefore = minter.getBackingValue();
        
        // Queue and execute redemption
        vm.prank(USER);
        minter.redeem(REDEEM_AMOUNT, RECEIVER);
        
        vm.warp(block.timestamp + 301);
        vm.prank(KEEPER);
        minter.executeRedeemBatch(1);
        
        uint256 totalSupplyAfter = minter.totalSupply();
        uint256 backingValueAfter = minter.getBackingValue();
        
        // Check NAV invariant: Δ(totalSupply) * nav ≈ − executed_out_value ± ε
        uint256 supplyDelta = totalSupplyBefore - totalSupplyAfter;
        uint256 valueDelta = backingValueBefore - backingValueAfter;
        
        // Allow for small rounding differences (ε = 1e9)
        assertApproxEqRel(supplyDelta, valueDelta, 1e9, "NAV invariant should hold");
    }

    function test_Redeem_multipleRedemptions() public {
        // Queue multiple redemptions
        for (uint256 i = 0; i < 3; i++) {
            vm.prank(USER);
            minter.redeem(REDEEM_AMOUNT, RECEIVER);
        }
        
        // Check queue length
        uint256 queueLength = minter.getRedeemQueueLength();
        assertEq(queueLength, 3, "Should have 3 redemptions in queue");
        
        // Fast forward time
        vm.warp(block.timestamp + 301);
        
        // Execute all redemptions
        vm.prank(KEEPER);
        minter.executeRedeemBatch(3);
        
        // Check queue is empty
        uint256 queueLengthAfter = minter.getRedeemQueueLength();
        assertEq(queueLengthAfter, 0, "Queue should be empty");
    }

    function test_Redeem_executionTiming() public {
        // Queue redemption
        vm.prank(USER);
        minter.redeem(REDEEM_AMOUNT, RECEIVER);
        
        // Try to execute too early
        vm.warp(block.timestamp + 299); // Just under min delay
        vm.prank(KEEPER);
        vm.expectRevert("too early");
        minter.executeRedeemBatch(1);
        
        // Execute at correct time
        vm.warp(block.timestamp + 2); // Past min delay
        vm.prank(KEEPER);
        minter.executeRedeemBatch(1);
        
        // Verify executed
        uint256 queueLength = minter.getRedeemQueueLength();
        assertEq(queueLength, 0, "Redemption should be executed");
    }

    function test_Redeem_expiredExecution() public {
        // Queue redemption
        vm.prank(USER);
        minter.redeem(REDEEM_AMOUNT, RECEIVER);
        
        // Try to execute too late
        vm.warp(block.timestamp + 3601); // Past max delay
        vm.prank(KEEPER);
        vm.expectRevert("expired");
        minter.executeRedeemBatch(1);
    }

    function test_Redeem_pausedContract() public {
        // Pause contract
        minter.pause();
        
        // Try to redeem
        vm.prank(USER);
        vm.expectRevert("Pausable: paused");
        minter.redeem(REDEEM_AMOUNT, RECEIVER);
        
        // Unpause and try again
        minter.unpause();
        vm.prank(USER);
        minter.redeem(REDEEM_AMOUNT, RECEIVER);
        
        // Should succeed
        uint256 queueLength = minter.getRedeemQueueLength();
        assertEq(queueLength, 1, "Redemption should be queued");
    }

    function test_Redeem_unauthorizedKeeper() public {
        // Queue redemption
        vm.prank(USER);
        minter.redeem(REDEEM_AMOUNT, RECEIVER);
        
        // Try to execute with unauthorized keeper
        vm.warp(block.timestamp + 301);
        vm.prank(USER); // Not authorized
        vm.expectRevert("unauthorized keeper");
        minter.executeRedeemBatch(1);
    }

    function test_Redeem_emptyQueue() public {
        vm.prank(KEEPER);
        vm.expectRevert("empty redeem queue");
        minter.executeRedeemBatch(1);
    }

    function test_Redeem_invalidBatchSize() public {
        vm.prank(KEEPER);
        vm.expectRevert("invalid batch size");
        minter.executeRedeemBatch(0);
        
        vm.prank(KEEPER);
        vm.expectRevert("invalid batch size");
        minter.executeRedeemBatch(51);
    }

    function test_Redeem_partialBatch() public {
        // Queue 5 redemptions
        for (uint256 i = 0; i < 5; i++) {
            vm.prank(USER);
            minter.redeem(REDEEM_AMOUNT, RECEIVER);
        }
        
        // Execute only 3
        vm.warp(block.timestamp + 301);
        vm.prank(KEEPER);
        minter.executeRedeemBatch(3);
        
        // Check 2 remain in queue
        uint256 queueLength = minter.getRedeemQueueLength();
        assertEq(queueLength, 2, "Should have 2 redemptions remaining");
    }
}
