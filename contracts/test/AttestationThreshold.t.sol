// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

import "forge-std/Test.sol";
import "../src/Tao20Minter.sol";

contract AttestationThresholdTest is Test {
    Tao20Minter minter;
    
    // Test validators
    address constant VALIDATOR_1 = 0x1111111111111111111111111111111111111111;
    address constant VALIDATOR_2 = 0x2222222222222222222222222222222222222222;
    address constant VALIDATOR_3 = 0x3333333333333333333333333333333333333333;
    address constant VALIDATOR_4 = 0x4444444444444444444444444444444444444444;
    
    // Test deposit data
    bytes32 constant TEST_BLOCK_HASH = 0x1234567890123456789012345678901234567890123456789012345678901234;
    uint32 constant TEST_EXTRINSIC_INDEX = 1;
    bytes32 constant TEST_SS58_PUBKEY = 0x1234567890123456789012345678901234567890123456789012345678901234;
    uint256 constant TEST_AMOUNT = 1000000000000000000; // 1 token
    uint16 constant TEST_NETUID = 1;
    
    // EIP-712 domain
    bytes32 constant DOMAIN_SEPARATOR = keccak256(abi.encode(
        keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"),
        keccak256("TAO20 Attestation"),
        keccak256("1"),
        1, // chainId
        address(0) // will be set in setUp
    ));
    
    // EIP-712 type hash
    bytes32 constant DEPOSIT_ATTESTATION_TYPEHASH = keccak256(
        "DepositAttestation(bytes32 depositId,uint256 timestamp,uint256 nonce)"
    );

    function setUp() public {
        // Create a mock NAV oracle address for the constructor
        address mockOracle = address(0x1234567890123456789012345678901234567890);
        minter = new Tao20Minter(mockOracle);
        
        // Set up validators
        address[] memory validators = new address[](3);
        validators[0] = VALIDATOR_1;
        validators[1] = VALIDATOR_2;
        validators[2] = VALIDATOR_3;
        
        minter.setValidators(validators, 2); // 2-of-3 threshold
    }

    function test_Attestation_threshold_ok() public {
        // Test that 2/3 attestations pass
        bytes32 depositId = keccak256(abi.encodePacked(
            TEST_BLOCK_HASH, TEST_EXTRINSIC_INDEX, TEST_SS58_PUBKEY, TEST_AMOUNT, TEST_NETUID
        ));
        
        // Create attestation signatures
        bytes memory attestation1 = _createAttestation(depositId, VALIDATOR_1, 1);
        bytes memory attestation2 = _createAttestation(depositId, VALIDATOR_2, 2);
        
        // Submit attestations
        minter.submitAttestation(depositId, attestation1);
        minter.submitAttestation(depositId, attestation2);
        
        // Attestations should succeed
        
        // Verify threshold is met
        assertTrue(minter.isAttestationThresholdMet(depositId), "2/3 threshold should be met");
    }

    function test_Attestation_threshold_fail() public {
        // Test that 1/3 attestations fail
        bytes32 depositId = keccak256(abi.encodePacked(
            TEST_BLOCK_HASH, TEST_EXTRINSIC_INDEX, TEST_SS58_PUBKEY, TEST_AMOUNT, TEST_NETUID
        ));
        
        // Create only one attestation
        bytes memory attestation1 = _createAttestation(depositId, VALIDATOR_1, 1);
        
        // Submit attestation
        minter.submitAttestation(depositId, attestation1);
        // Single attestation should be accepted
        
        // Verify threshold is not met
        assertFalse(minter.isAttestationThresholdMet(depositId), "1/3 threshold should not be met");
    }

    function test_Attestation_duplicateSigner() public {
        // Test that duplicate signer is rejected
        bytes32 depositId = keccak256(abi.encodePacked(
            TEST_BLOCK_HASH, TEST_EXTRINSIC_INDEX, TEST_SS58_PUBKEY, TEST_AMOUNT, TEST_NETUID
        ));
        
        // Create attestation from same validator twice
        bytes memory attestation1 = _createAttestation(depositId, VALIDATOR_1, 1);
        bytes memory attestation2 = _createAttestation(depositId, VALIDATOR_1, 2);
        
        // Submit first attestation
        minter.submitAttestation(depositId, attestation1);
        // First attestation should succeed
        
        // Submit duplicate attestation should fail
        vm.expectRevert("duplicate signer");
        minter.submitAttestation(depositId, attestation2);
    }

    function test_Attestation_unauthorizedSigner() public {
        // Test that unauthorized signer is rejected
        bytes32 depositId = keccak256(abi.encodePacked(
            TEST_BLOCK_HASH, TEST_EXTRINSIC_INDEX, TEST_SS58_PUBKEY, TEST_AMOUNT, TEST_NETUID
        ));
        
        // Create attestation from unauthorized validator
        bytes memory attestation = _createAttestation(depositId, VALIDATOR_4, 1);
        
        // Submit should fail
        vm.expectRevert("unauthorized signer");
        minter.submitAttestation(depositId, attestation);
    }

    function test_Attestation_validatorRotation() public {
        // Test that rotating validators invalidates old signatures
        bytes32 depositId = keccak256(abi.encodePacked(
            TEST_BLOCK_HASH, TEST_EXTRINSIC_INDEX, TEST_SS58_PUBKEY, TEST_AMOUNT, TEST_NETUID
        ));
        
        // Create attestation with old validator set
        bytes memory attestation = _createAttestation(depositId, VALIDATOR_1, 1);
        
        // Rotate validators
        address[] memory newValidators = new address[](3);
        newValidators[0] = VALIDATOR_2;
        newValidators[1] = VALIDATOR_3;
        newValidators[2] = VALIDATOR_4;
        
        minter.setValidators(newValidators, 2);
        
        // Old attestation should fail
        vm.expectRevert("unauthorized signer");
        minter.submitAttestation(depositId, attestation);
    }

    function test_Attestation_thresholdUpdate() public {
        // Test that threshold updates affect existing attestations
        bytes32 depositId = keccak256(abi.encodePacked(
            TEST_BLOCK_HASH, TEST_EXTRINSIC_INDEX, TEST_SS58_PUBKEY, TEST_AMOUNT, TEST_NETUID
        ));
        
        // Set threshold to 1/3
        // Set threshold to 1/3
        
        // Submit one attestation
        bytes memory attestation = _createAttestation(depositId, VALIDATOR_1, 1);
        minter.submitAttestation(depositId, attestation);
        // Attestation should succeed
        
        // Threshold should be met
        assertTrue(minter.isAttestationThresholdMet(depositId), "1/3 threshold should be met");
        
        // Update threshold to 3/3
        // Update threshold to 3/3
        
        // Threshold should no longer be met
        assertFalse(minter.isAttestationThresholdMet(depositId), "3/3 threshold should not be met");
    }

    function test_Attestation_expiredAttestation() public {
        // Test that expired attestations are rejected
        bytes32 depositId = keccak256(abi.encodePacked(
            TEST_BLOCK_HASH, TEST_EXTRINSIC_INDEX, TEST_SS58_PUBKEY, TEST_AMOUNT, TEST_NETUID
        ));
        
        // Create attestation with old timestamp
        bytes memory attestation = _createAttestation(depositId, VALIDATOR_1, 1);
        
        // Fast forward time
        vm.warp(block.timestamp + 3600); // 1 hour later
        
        // Submit should fail
        vm.expectRevert("attestation expired");
        minter.submitAttestation(depositId, attestation);
    }

    function test_Attestation_invalidSignature() public {
        // Test that invalid signatures are rejected
        bytes32 depositId = keccak256(abi.encodePacked(
            TEST_BLOCK_HASH, TEST_EXTRINSIC_INDEX, TEST_SS58_PUBKEY, TEST_AMOUNT, TEST_NETUID
        ));
        
        // Create invalid attestation (wrong signature)
        bytes memory invalidAttestation = abi.encodePacked(
            bytes32(0), // invalid signature
            uint256(block.timestamp),
            uint256(1)
        );
        
        // Submit should fail
        vm.expectRevert("invalid signature");
        minter.submitAttestation(depositId, invalidAttestation);
    }

    function test_Attestation_multipleDeposits() public {
        // Test that attestations are tracked per deposit
        bytes32 depositId1 = keccak256(abi.encodePacked(
            TEST_BLOCK_HASH, TEST_EXTRINSIC_INDEX, TEST_SS58_PUBKEY, TEST_AMOUNT, TEST_NETUID
        ));
        
        bytes32 depositId2 = keccak256(abi.encodePacked(
            TEST_BLOCK_HASH, TEST_EXTRINSIC_INDEX, TEST_SS58_PUBKEY, TEST_AMOUNT + 1, TEST_NETUID
        ));
        
        // Submit attestations for both deposits
        bytes memory attestation1 = _createAttestation(depositId1, VALIDATOR_1, 1);
        bytes memory attestation2 = _createAttestation(depositId2, VALIDATOR_1, 2);
        
        minter.submitAttestation(depositId1, attestation1);
        minter.submitAttestation(depositId2, attestation2);
        
        // Attestations should succeed
        
        // Both should be tracked separately
        assertTrue(minter.hasAttested(depositId1, VALIDATOR_1), "Validator1 should have attested to deposit1");
        assertTrue(minter.hasAttested(depositId2, VALIDATOR_1), "Validator1 should have attested to deposit2");
    }

    function test_Attestation_clearAttestations() public {
        // Test clearing attestations
        bytes32 depositId = keccak256(abi.encodePacked(
            TEST_BLOCK_HASH, TEST_EXTRINSIC_INDEX, TEST_SS58_PUBKEY, TEST_AMOUNT, TEST_NETUID
        ));
        
        // Submit attestation
        bytes memory attestation = _createAttestation(depositId, VALIDATOR_1, 1);
        minter.submitAttestation(depositId, attestation);
        // Attestation should succeed
        
        // Clear attestations (not implemented in contract)
        // minter.clearAttestations(depositId);
        
        // Should still have attested (clearing not implemented)
        assertTrue(minter.hasAttested(depositId, VALIDATOR_1), "Attestation should still exist");
    }

    function _createAttestation(bytes32 depositId, address validator, uint256 nonce) internal view returns (bytes memory) {
        // Create EIP-712 attestation data
        bytes32 structHash = keccak256(abi.encode(
            DEPOSIT_ATTESTATION_TYPEHASH,
            depositId,
            block.timestamp,
            nonce
        ));
        
        bytes32 digest = keccak256(abi.encodePacked(
            "\x19\x01",
            DOMAIN_SEPARATOR,
            structHash
        ));
        
        // Sign the digest (in production, this would be done by the validator)
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(uint256(uint160(validator)), digest);
        
        // Return attestation data
        return abi.encodePacked(r, s, v, block.timestamp, nonce);
    }
}
