// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

/**
 * @title IBittensorPrecompiles
 * @dev Complete interface definitions for all Bittensor precompiles
 * 
 * PRECOMPILE ADDRESSES:
 * - Ed25519Verify: 0x0000000000000000000000000000000000000402
 * - BalanceTransfer: 0x0000000000000000000000000000000000000800  
 * - MetagraphPrecompile: 0x0000000000000000000000000000000000000802
 * - SubnetPrecompile: 0x0000000000000000000000000000000000000803
 * - StakingPrecompileV2: 0x0000000000000000000000000000000000000805
 * - BatchPrecompile: 0x0000000000000000000000000000000000000804
 */

// ===================== ED25519 SIGNATURE VERIFICATION =====================

interface IEd25519Verify {
    /**
     * @dev Verify Ed25519 signature
     * @param message Message hash (32 bytes)
     * @param publicKey Ed25519 public key (32 bytes) 
     * @param r First half of signature (32 bytes)
     * @param s Second half of signature (32 bytes)
     * @return bool True if signature is valid
     */
    function verify(bytes32 message, bytes32 publicKey, bytes32 r, bytes32 s) external pure returns (bool);
}

// ===================== BALANCE TRANSFER =====================

interface IBalanceTransfer {
    /**
     * @dev Transfer TAO from EVM account to SS58 address
     * @param dest Destination SS58 public key (32 bytes)
     * @param amount Amount in TAO base units (1 TAO = 1e9 RAO)
     * @return bool True if transfer succeeded
     */
    function transferToSubstrate(bytes32 dest, uint256 amount) external returns (bool);
    
    /**
     * @dev Get TAO balance of an address
     * @param account Account address
     * @return uint256 Balance in TAO base units
     */
    function balanceOf(address account) external view returns (uint256);
}

// ===================== STAKING PRECOMPILE V2 =====================

interface IStakingPrecompileV2 {
    /**
     * @dev Add stake to a hotkey
     * @param hotkey Validator hotkey (32 bytes)
     * @param amountRao Amount in RAO (1 TAO = 1e9 RAO)
     * @return bool True if staking succeeded
     */
    function addStake(bytes32 hotkey, uint256 amountRao) external returns (bool);
    
    /**
     * @dev Remove stake from a hotkey
     * @param hotkey Validator hotkey (32 bytes)
     * @param amountRao Amount in RAO to unstake
     * @return bool True if unstaking succeeded
     */
    function removeStake(bytes32 hotkey, uint256 amountRao) external returns (bool);
    
    /**
     * @dev Get total stake for a hotkey
     * @param hotkey Validator hotkey (32 bytes)
     * @return uint256 Total stake in RAO
     */
    function getStake(bytes32 hotkey) external view returns (uint256);
    
    /**
     * @dev Get staking rewards for a hotkey
     * @param hotkey Validator hotkey (32 bytes)
     * @return uint256 Accumulated rewards in RAO
     */
    function getStakingRewards(bytes32 hotkey) external view returns (uint256);
    
    /**
     * @dev Get staking information for coldkey-hotkey pair
     * @param coldkey Coldkey public key (32 bytes)
     * @param hotkey Hotkey public key (32 bytes)
     * @return uint256 Staked amount in RAO
     */
    function getStakeForColdkeyHotkey(bytes32 coldkey, bytes32 hotkey) external view returns (uint256);
}

// ===================== METAGRAPH PRECOMPILE =====================

interface IMetagraphPrecompile {
    /**
     * @dev Get subnet information
     * @param netuid Subnet ID
     * @return bool True if subnet exists
     */
    function subnetExists(uint16 netuid) external view returns (bool);
    
    /**
     * @dev Get number of neurons in subnet
     * @param netuid Subnet ID  
     * @return uint256 Number of neurons
     */
    function getSubnetN(uint16 netuid) external view returns (uint256);
    
    /**
     * @dev Get neuron information
     * @param netuid Subnet ID
     * @param uid Neuron UID
     * @return hotkey Neuron hotkey
     * @return coldkey Neuron coldkey
     * @return stake Total stake in RAO
     * @return emission Emission rate
     * @return incentive Incentive score
     * @return consensus Consensus score
     * @return trust Trust score
     * @return validator_trust Validator trust score
     * @return dividends Dividend score
     * @return last_update Last update block
     */
    function getNeuron(uint16 netuid, uint16 uid) external view returns (
        bytes32 hotkey,
        bytes32 coldkey,
        uint256 stake,
        uint256 emission,
        uint256 incentive,
        uint256 consensus,
        uint256 trust,
        uint256 validator_trust,
        uint256 dividends,
        uint256 last_update
    );
    
    /**
     * @dev Get subnet emissions
     * @param netuid Subnet ID
     * @return uint256 Total emissions in RAO
     */
    function getEmission(uint16 netuid) external view returns (uint256);
}

// ===================== SUBNET PRECOMPILE =====================

interface ISubnetPrecompile {
    /**
     * @dev Register a new subnet
     * @param name Subnet name
     * @return uint16 New subnet ID
     */
    function registerSubnet(string calldata name) external returns (uint16);
    
    /**
     * @dev Get subnet owner
     * @param netuid Subnet ID
     * @return bytes32 Owner coldkey
     */
    function getSubnetOwner(uint16 netuid) external view returns (bytes32);
    
    /**
     * @dev Check if subnet is active
     * @param netuid Subnet ID
     * @return bool True if active
     */
    function isSubnetActive(uint16 netuid) external view returns (bool);
}

// ===================== BATCH PRECOMPILE =====================

interface IBatchPrecompile {
    /**
     * @dev Execute multiple calls in one transaction
     * @param targets Array of target addresses
     * @param calldatas Array of call data
     * @return results Array of return data
     */
    function batchAll(
        address[] calldata targets,
        bytes[] calldata calldatas
    ) external returns (bytes[] memory results);
}

// ===================== SUBSTRATE QUERY PRECOMPILE =====================

interface ISubstrateQuery {
    /**
     * @dev Verify a deposit exists on Substrate chain
     * @param blockHash Bittensor block hash
     * @param extrinsicIndex Transaction index in block
     * @param userSS58 User's Substrate public key
     * @param netuid Subnet ID (for subnet token deposits)
     * @param amount Amount deposited
     * @return bool True if deposit exists
     */
    function verifyDeposit(
        bytes32 blockHash,
        uint32 extrinsicIndex,
        bytes32 userSS58,
        uint16 netuid,
        uint256 amount
    ) external view returns (bool);
    
    /**
     * @dev Get block timestamp
     * @param blockHash Block hash
     * @return uint256 Block timestamp
     */
    function getBlockTimestamp(bytes32 blockHash) external view returns (uint256);
    
    /**
     * @dev Get account balance for a specific asset
     * @param account Account public key
     * @param assetId Asset ID (0 for TAO, subnet ID for subnet tokens)
     * @return uint256 Balance in asset base units
     */
    function getAssetBalance(bytes32 account, uint16 assetId) external view returns (uint256);
}

// ===================== ASSET TRANSFER PRECOMPILE =====================

interface IAssetTransfer {
    /**
     * @dev Transfer subnet tokens from EVM to SS58 address
     * @param assetId Asset ID (subnet ID for subnet tokens)
     * @param dest Destination SS58 public key (32 bytes)
     * @param amount Amount in asset base units
     * @return bool True if transfer succeeded
     */
    function transferAssetToSubstrate(uint16 assetId, bytes32 dest, uint256 amount) external returns (bool);
    
    /**
     * @dev Get asset balance in EVM context
     * @param assetId Asset ID
     * @param account EVM account address
     * @return uint256 Balance in asset base units
     */
    function getAssetBalance(uint16 assetId, address account) external view returns (uint256);
    
    /**
     * @dev Transfer asset between EVM addresses
     * @param assetId Asset ID
     * @param from From address
     * @param to To address  
     * @param amount Amount to transfer
     * @return bool True if transfer succeeded
     */
    function transferAsset(uint16 assetId, address from, address to, uint256 amount) external returns (bool);
}

// ===================== PRECOMPILE ADDRESSES =====================

library BittensorPrecompileAddresses {
    address public constant ED25519_VERIFY = 0x0000000000000000000000000000000000000402;
    address public constant BALANCE_TRANSFER = 0x0000000000000000000000000000000000000800;
    address public constant METAGRAPH = 0x0000000000000000000000000000000000000802;
    address public constant SUBNET = 0x0000000000000000000000000000000000000803;
    address public constant STAKING_V2 = 0x0000000000000000000000000000000000000805;
    address public constant BATCH = 0x0000000000000000000000000000000000000804;
    
    // Additional precompiles that may exist
    address public constant SUBSTRATE_QUERY = 0x0000000000000000000000000000000000000806;
    address public constant ASSET_TRANSFER = 0x0000000000000000000000000000000000000807;
}

// ===================== HELPER FUNCTIONS =====================

library BittensorPrecompiles {
    /**
     * @dev Get Ed25519 verify precompile
     */
    function ed25519Verify() internal pure returns (IEd25519Verify) {
        return IEd25519Verify(BittensorPrecompileAddresses.ED25519_VERIFY);
    }
    
    /**
     * @dev Get balance transfer precompile
     */
    function balanceTransfer() internal pure returns (IBalanceTransfer) {
        return IBalanceTransfer(BittensorPrecompileAddresses.BALANCE_TRANSFER);
    }
    
    /**
     * @dev Get staking precompile
     */
    function staking() internal pure returns (IStakingPrecompileV2) {
        return IStakingPrecompileV2(BittensorPrecompileAddresses.STAKING_V2);
    }
    
    /**
     * @dev Get metagraph precompile
     */
    function metagraph() internal pure returns (IMetagraphPrecompile) {
        return IMetagraphPrecompile(BittensorPrecompileAddresses.METAGRAPH);
    }
    
    /**
     * @dev Get subnet precompile
     */
    function subnet() internal pure returns (ISubnetPrecompile) {
        return ISubnetPrecompile(BittensorPrecompileAddresses.SUBNET);
    }
    
    /**
     * @dev Get batch precompile
     */
    function batch() internal pure returns (IBatchPrecompile) {
        return IBatchPrecompile(BittensorPrecompileAddresses.BATCH);
    }
    
    /**
     * @dev Get substrate query precompile
     */
    function substrateQuery() internal pure returns (ISubstrateQuery) {
        return ISubstrateQuery(BittensorPrecompileAddresses.SUBSTRATE_QUERY);
    }
    
    /**
     * @dev Get asset transfer precompile
     */
    function assetTransfer() internal pure returns (IAssetTransfer) {
        return IAssetTransfer(BittensorPrecompileAddresses.ASSET_TRANSFER);
    }
}
