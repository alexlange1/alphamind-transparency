// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

/**
 * @title AddressUtils
 * @dev Utility library for address conversions between EVM and Substrate formats
 * 
 * KEY CONCEPTS:
 * - EVM Address (H160): 20-byte Ethereum-style address (0x1234...)
 * - Substrate Address (SS58): 32-byte public key with SS58 encoding (5ABC...)
 * - Vault Address: Contract's corresponding Substrate address for asset custody
 * 
 * CONVERSION RULES:
 * - EVM to Substrate: hash("evm:" + H160) -> Blake2b -> SS58 (network ID 42)
 * - Asset addresses: 0xFFffFFff + assetId for subnet token ERC-20 interfaces
 */

library AddressUtils {
    
    // ===================== CONSTANTS =====================
    
    /// @dev Bittensor network ID for SS58 encoding
    uint8 public constant BITTENSOR_NETWORK_ID = 42;
    
    /// @dev Prefix for EVM to Substrate address derivation
    bytes4 public constant EVM_PREFIX = "evm:";
    
    /// @dev Asset precompile address prefix (0xFFffFFff...)
    bytes4 public constant ASSET_PREFIX = 0xFFffFFff;
    
    /// @dev TAO token address (native token)
    address public constant TAO_ADDRESS = 0x0000000000000000000000000000000000000001;
    
    // ===================== ERRORS =====================
    
    error InvalidAddress();
    error InvalidAssetId();
    error ConversionFailed();
    
    // ===================== EVM TO SUBSTRATE CONVERSION =====================
    
    /**
     * @dev Convert EVM address to Substrate public key
     * @param evmAddress EVM address (20 bytes)
     * @return bytes32 Substrate public key (32 bytes)
     * 
     * PROCESS:
     * 1. Concatenate "evm:" prefix with EVM address bytes
     * 2. Hash with Blake2b (simulated with keccak256 for EVM compatibility)
     * 3. Return 32-byte public key
     * 
     * NOTE: In production, this would use actual Blake2b hashing
     * For EVM compatibility, we use keccak256 as approximation
     */
    function evmToSubstrate(address evmAddress) internal pure returns (bytes32) {
        if (evmAddress == address(0)) revert InvalidAddress();
        
        // Simulate Blake2b with keccak256 for EVM compatibility
        // In actual Bittensor implementation, this would be Blake2b
        bytes memory data = abi.encodePacked(EVM_PREFIX, evmAddress);
        return keccak256(data);
    }
    
    /**
     * @dev Get contract's vault address (Substrate mirror)
     * @param contractAddress Contract's EVM address
     * @return bytes32 Vault's Substrate public key
     */
    function getVaultAddress(address contractAddress) internal pure returns (bytes32) {
        return evmToSubstrate(contractAddress);
    }
    
    /**
     * @dev Get current contract's vault address
     * @return bytes32 This contract's Substrate public key
     */
    function getMyVaultAddress() internal view returns (bytes32) {
        return evmToSubstrate(address(this));
    }
    
    // ===================== ASSET ADDRESS GENERATION =====================
    
    /**
     * @dev Generate ERC-20 address for subnet token
     * @param netuid Subnet ID
     * @return address ERC-20 interface address for subnet token
     * 
     * PATTERN: 0xFFffFFff + netuid (padded to 20 bytes)
     * Example: Subnet 1 -> 0xFFffFFff00000000000000000000000000000001
     */
    function getSubnetTokenAddress(uint16 netuid) internal pure returns (address) {
        if (netuid == 0) revert InvalidAssetId();
        
        // Pack asset prefix with subnet ID
        bytes20 addressBytes = bytes20(abi.encodePacked(ASSET_PREFIX, bytes16(uint128(netuid))));
        return address(addressBytes);
    }
    
    /**
     * @dev Get TAO token ERC-20 interface address
     * @return address TAO token address
     */
    function getTAOAddress() internal pure returns (address) {
        return TAO_ADDRESS;
    }
    
    /**
     * @dev Check if address is a subnet token address
     * @param tokenAddress Address to check
     * @return bool True if it's a subnet token address
     * @return uint16 Subnet ID (0 if not subnet token)
     */
    function isSubnetToken(address tokenAddress) internal pure returns (bool, uint16) {
        bytes20 addressBytes = bytes20(tokenAddress);
        bytes4 prefix = bytes4(addressBytes);
        
        if (prefix != ASSET_PREFIX) {
            return (false, 0);
        }
        
        // Extract subnet ID from last 2 bytes
        bytes2 netuidBytes = bytes2(addressBytes << 144); // Shift to get last 2 bytes
        uint16 netuid = uint16(netuidBytes);
        
        return (true, netuid);
    }
    
    // ===================== SS58 UTILITIES =====================
    
    /**
     * @dev Validate Substrate public key format
     * @param pubkey Public key to validate
     * @return bool True if valid format
     */
    function isValidSubstrateKey(bytes32 pubkey) internal pure returns (bool) {
        return pubkey != bytes32(0);
    }
    
    /**
     * @dev Convert bytes32 to SS58 string (simplified)
     * @param pubkey Substrate public key
     * @return string SS58-encoded address (simplified representation)
     * 
     * NOTE: This is a simplified representation for logging/events
     * Actual SS58 encoding involves Base58 encoding with checksum
     */
    function toSS58String(bytes32 pubkey) internal pure returns (string memory) {
        if (!isValidSubstrateKey(pubkey)) revert InvalidAddress();
        
        // Convert to hex string with "5" prefix (simplified SS58 representation)
        return string(abi.encodePacked("5", _toHexString(pubkey)));
    }
    
    /**
     * @dev Convert bytes32 to hex string
     */
    function _toHexString(bytes32 data) private pure returns (string memory) {
        bytes memory alphabet = "0123456789abcdef";
        bytes memory str = new bytes(64);
        
        for (uint i = 0; i < 32; i++) {
            str[i*2] = alphabet[uint8(data[i] >> 4)];
            str[1+i*2] = alphabet[uint8(data[i] & 0x0f)];
        }
        
        return string(str);
    }
    
    // ===================== VALIDATION UTILITIES =====================
    
    /**
     * @dev Validate deposit parameters
     * @param userSS58 User's Substrate public key
     * @param netuid Subnet ID
     * @param amount Deposit amount
     * @return bool True if valid
     */
    function validateDepositParams(
        bytes32 userSS58,
        uint16 netuid,
        uint256 amount
    ) internal pure returns (bool) {
        return isValidSubstrateKey(userSS58) && 
               netuid > 0 && 
               amount > 0;
    }
    
    /**
     * @dev Calculate deposit ID for uniqueness tracking
     * @param blockHash Substrate block hash
     * @param extrinsicIndex Transaction index
     * @param userSS58 User's public key
     * @param netuid Subnet ID
     * @param amount Deposit amount
     * @param timestamp Block timestamp
     * @return bytes32 Unique deposit identifier
     */
    function calculateDepositId(
        bytes32 blockHash,
        uint32 extrinsicIndex,
        bytes32 userSS58,
        uint16 netuid,
        uint256 amount,
        uint256 timestamp
    ) internal pure returns (bytes32) {
        return keccak256(abi.encode(
            blockHash,
            extrinsicIndex,
            userSS58,
            netuid,
            amount,
            timestamp
        ));
    }
    
    // ===================== AMOUNT CONVERSION =====================
    
    /**
     * @dev Convert TAO to RAO (1 TAO = 1e9 RAO)
     * @param taoAmount Amount in TAO
     * @return uint256 Amount in RAO
     */
    function taoToRao(uint256 taoAmount) internal pure returns (uint256) {
        return taoAmount * 1e9;
    }
    
    /**
     * @dev Convert RAO to TAO (1 TAO = 1e9 RAO)
     * @param raoAmount Amount in RAO
     * @return uint256 Amount in TAO
     */
    function raoToTao(uint256 raoAmount) internal pure returns (uint256) {
        return raoAmount / 1e9;
    }
    
    /**
     * @dev Safe conversion with overflow check
     * @param amount Amount to convert
     * @param multiplier Conversion multiplier
     * @return uint256 Converted amount
     */
    function safeConvert(uint256 amount, uint256 multiplier) internal pure returns (uint256) {
        if (amount == 0) return 0;
        
        // Check for overflow
        if (amount > type(uint256).max / multiplier) {
            revert ConversionFailed();
        }
        
        return amount * multiplier;
    }
    
    // ===================== BATCH OPERATIONS =====================
    
    /**
     * @dev Convert multiple subnet IDs to token addresses
     * @param netuids Array of subnet IDs
     * @return addresses Array of token addresses
     */
    function getSubnetTokenAddresses(uint16[] memory netuids) 
        internal 
        pure 
        returns (address[] memory addresses) 
    {
        addresses = new address[](netuids.length);
        
        for (uint i = 0; i < netuids.length; i++) {
            addresses[i] = getSubnetTokenAddress(netuids[i]);
        }
    }
    
    /**
     * @dev Validate multiple Substrate keys
     * @param pubkeys Array of public keys
     * @return bool True if all are valid
     */
    function validateSubstrateKeys(bytes32[] memory pubkeys) internal pure returns (bool) {
        for (uint i = 0; i < pubkeys.length; i++) {
            if (!isValidSubstrateKey(pubkeys[i])) {
                return false;
            }
        }
        return true;
    }
}
