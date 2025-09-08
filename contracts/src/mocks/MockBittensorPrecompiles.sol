// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

/**
 * @title MockBittensorPrecompiles
 * @dev Mock implementation of Bittensor precompiles for local testing
 * 
 * TESTING PURPOSE:
 * ✅ Simulates Ed25519 signature verification
 * ✅ Mocks Substrate queries for deposits
 * ✅ Simulates cross-chain balance transfers
 * ✅ Provides realistic testing environment
 * 
 * DEPLOYED AT PRECOMPILE ADDRESSES:
 * - 0x402: Ed25519 Verify
 * - 0x800: Balance Transfer  
 * - 0x802: Metagraph
 * - 0x805: Staking V2
 * - 0x806: Substrate Query
 */

/**
 * @dev Mock Ed25519 signature verification (address 0x402)
 */
contract MockEd25519Verify {
    
    mapping(bytes32 => bool) public validSignatures;
    
    event SignatureVerified(bytes32 indexed message, bytes32 indexed pubkey, bool result);
    
    /**
     * @dev Verify Ed25519 signature (mock implementation)
     * @param message Message that was signed
     * @param pubkey Public key of signer
     * @param signature Combined r+s signature (64 bytes)
     * @return bool True if signature is valid
     */
    function verify(
        bytes32 message,
        bytes32 pubkey, 
        bytes calldata signature
    ) external returns (bool) {
        require(signature.length == 64, "Invalid signature length");
        
        // Mock verification logic
        // In real testing, you can pre-configure valid signatures
        bytes32 sigHash = keccak256(abi.encodePacked(message, pubkey, signature));
        bool isValid = validSignatures[sigHash] || _mockVerification(message, pubkey, signature);
        
        emit SignatureVerified(message, pubkey, isValid);
        return isValid;
    }
    
    function _mockVerification(
        bytes32 message,
        bytes32 pubkey,
        bytes calldata signature
    ) internal pure returns (bool) {
        // Simple mock: signature is valid if it starts with specific bytes
        // This allows testing with predictable signatures
        return signature[0] == 0xab && signature[1] == 0xcd;
    }
    
    // Test helper: pre-approve signatures for testing
    function setValidSignature(bytes32 message, bytes32 pubkey, bytes calldata signature) external {
        bytes32 sigHash = keccak256(abi.encodePacked(message, pubkey, signature));
        validSignatures[sigHash] = true;
    }
}

/**
 * @dev Mock Substrate Query precompile (address 0x806)
 */
contract MockSubstrateQuery {
    
    struct MockDeposit {
        bytes32 blockHash;
        uint32 extrinsicIndex;
        bytes32 depositor;
        uint16 netuid;
        uint256 amount;
        uint256 timestamp;
        bool exists;
    }
    
    mapping(bytes32 => MockDeposit) public deposits;
    mapping(bytes32 => uint256) public accountBalances; // SS58 -> balance
    
    event DepositQueried(bytes32 indexed depositHash, bool exists);
    event DepositCreated(bytes32 indexed depositHash, bytes32 depositor, uint16 netuid, uint256 amount);
    
    /**
     * @dev Query deposit existence (mock implementation)
     * @param blockHash Block hash where deposit occurred
     * @param extrinsicIndex Transaction index in block
     * @param depositor Depositor SS58 address
     * @param netuid Subnet ID
     * @param amount Deposited amount
     * @return exists Whether deposit exists
     * @return deposit Deposit details
     */
    function queryDeposit(
        bytes32 blockHash,
        uint32 extrinsicIndex,
        bytes32 depositor,
        uint16 netuid,
        uint256 amount
    ) external returns (bool exists, MockDeposit memory deposit) {
        
        bytes32 depositHash = keccak256(abi.encodePacked(
            blockHash, extrinsicIndex, depositor, netuid, amount
        ));
        
        deposit = deposits[depositHash];
        exists = deposit.exists;
        
        emit DepositQueried(depositHash, exists);
        
        return (exists, deposit);
    }
    
    /**
     * @dev Get account balance (mock implementation)
     * @param account SS58 address
     * @param netuid Subnet ID (0 = TAO, others = subnet tokens)
     * @return balance Account balance
     */
    function getBalance(bytes32 account, uint16 netuid) external view returns (uint256 balance) {
        bytes32 balanceKey = keccak256(abi.encodePacked(account, netuid));
        return accountBalances[balanceKey];
    }
    
    // Test helpers: create mock deposits and balances
    function createMockDeposit(
        bytes32 blockHash,
        uint32 extrinsicIndex,
        bytes32 depositor,
        uint16 netuid,
        uint256 amount
    ) external {
        bytes32 depositHash = keccak256(abi.encodePacked(
            blockHash, extrinsicIndex, depositor, netuid, amount
        ));
        
        deposits[depositHash] = MockDeposit({
            blockHash: blockHash,
            extrinsicIndex: extrinsicIndex,
            depositor: depositor,
            netuid: netuid,
            amount: amount,
            timestamp: block.timestamp,
            exists: true
        });
        
        emit DepositCreated(depositHash, depositor, netuid, amount);
    }
    
    function setBalance(bytes32 account, uint16 netuid, uint256 balance) external {
        bytes32 balanceKey = keccak256(abi.encodePacked(account, netuid));
        accountBalances[balanceKey] = balance;
    }
}

/**
 * @dev Mock Balance Transfer precompile (address 0x800)
 */
contract MockBalanceTransfer {
    
    mapping(bytes32 => mapping(uint16 => uint256)) public balances; // account -> netuid -> balance
    
    event Transfer(bytes32 indexed from, bytes32 indexed to, uint16 indexed netuid, uint256 amount);
    event TransferFailed(bytes32 indexed from, bytes32 indexed to, uint16 indexed netuid, uint256 amount, string reason);
    
    /**
     * @dev Transfer tokens between Substrate accounts (mock)
     * @param to Recipient SS58 address
     * @param netuid Subnet ID (0 = TAO, others = subnet tokens)  
     * @param amount Amount to transfer
     * @return success Whether transfer succeeded
     */
    function transfer(
        bytes32 to,
        uint16 netuid,
        uint256 amount
    ) external returns (bool success) {
        
        // Mock sender (would be derived from transaction in real precompile)
        bytes32 sender = bytes32(uint256(uint160(msg.sender)));
        
        // Check balance
        if (balances[sender][netuid] < amount) {
            emit TransferFailed(sender, to, netuid, amount, "Insufficient balance");
            return false;
        }
        
        // Execute transfer
        balances[sender][netuid] -= amount;
        balances[to][netuid] += amount;
        
        emit Transfer(sender, to, netuid, amount);
        return true;
    }
    
    function getBalance(bytes32 account, uint16 netuid) external view returns (uint256) {
        return balances[account][netuid];
    }
    
    // Test helper: set balances for testing
    function setBalance(bytes32 account, uint16 netuid, uint256 balance) external {
        balances[account][netuid] = balance;
    }
}

/**
 * @dev Mock Staking V2 precompile (address 0x805)
 */
contract MockStakingV2 {
    
    mapping(bytes32 => uint256) public stakes; // hotkey -> stake amount
    mapping(bytes32 => uint256) public rewards; // hotkey -> accumulated rewards
    
    event StakeAdded(bytes32 indexed hotkey, uint256 amount);
    event StakeRemoved(bytes32 indexed hotkey, uint256 amount);
    event RewardsDistributed(bytes32 indexed hotkey, uint256 amount);
    
    /**
     * @dev Add stake to hotkey (mock implementation)
     * @param hotkey Validator hotkey
     * @param amount Amount to stake (in RAO)
     * @return success Whether staking succeeded
     */
    function addStake(bytes32 hotkey, uint256 amount) external returns (bool success) {
        stakes[hotkey] += amount;
        
        // Mock reward generation (1% per stake action)
        uint256 rewardAmount = amount / 100;
        rewards[hotkey] += rewardAmount;
        
        emit StakeAdded(hotkey, amount);
        emit RewardsDistributed(hotkey, rewardAmount);
        
        return true;
    }
    
    /**
     * @dev Remove stake from hotkey (mock implementation)
     * @param hotkey Validator hotkey
     * @param amount Amount to unstake (in RAO)
     * @return success Whether unstaking succeeded
     */
    function removeStake(bytes32 hotkey, uint256 amount) external returns (bool success) {
        if (stakes[hotkey] < amount) {
            return false;
        }
        
        stakes[hotkey] -= amount;
        emit StakeRemoved(hotkey, amount);
        
        return true;
    }
    
    function getStake(bytes32 hotkey) external view returns (uint256) {
        return stakes[hotkey];
    }
    
    function getRewards(bytes32 hotkey) external view returns (uint256) {
        return rewards[hotkey];
    }
}

/**
 * @dev Mock Metagraph precompile (address 0x802)  
 */
contract MockMetagraph {
    
    struct Neuron {
        bytes32 hotkey;
        bytes32 coldkey;
        uint256 stake;
        uint256 emission;
        bool active;
    }
    
    mapping(uint16 => mapping(uint256 => Neuron)) public neurons; // netuid -> uid -> neuron
    mapping(uint16 => uint256) public neuronCounts; // netuid -> count
    
    event NeuronRegistered(uint16 indexed netuid, uint256 indexed uid, bytes32 hotkey);
    
    /**
     * @dev Get neuron info (mock implementation)
     * @param netuid Subnet ID
     * @param uid Neuron UID
     * @return neuron Neuron details
     */
    function getNeuron(uint16 netuid, uint256 uid) external view returns (Neuron memory neuron) {
        return neurons[netuid][uid];
    }
    
    /**
     * @dev Get subnet size (mock implementation)
     * @param netuid Subnet ID
     * @return count Number of neurons
     */
    function getSubnetSize(uint16 netuid) external view returns (uint256 count) {
        return neuronCounts[netuid];
    }
    
    // Test helper: register mock neurons
    function registerNeuron(
        uint16 netuid,
        uint256 uid,
        bytes32 hotkey,
        bytes32 coldkey,
        uint256 stake,
        uint256 emission
    ) external {
        neurons[netuid][uid] = Neuron({
            hotkey: hotkey,
            coldkey: coldkey,
            stake: stake,
            emission: emission,
            active: true
        });
        
        if (uid >= neuronCounts[netuid]) {
            neuronCounts[netuid] = uid + 1;
        }
        
        emit NeuronRegistered(netuid, uid, hotkey);
    }
}

/**
 * @dev Precompile Deployer - deploys mocks at correct addresses
 */
contract PrecompileDeployer {
    
    event PrecompileDeployed(address indexed addr, string name);
    
    function deployAllPrecompiles() external {
        // Note: In a real environment, these would be deployed at fixed addresses
        // For local testing, we can deploy and track them
        
        MockEd25519Verify ed25519 = new MockEd25519Verify();
        MockSubstrateQuery query = new MockSubstrateQuery();
        MockBalanceTransfer transfer = new MockBalanceTransfer();
        MockStakingV2 staking = new MockStakingV2();
        MockMetagraph metagraph = new MockMetagraph();
        
        emit PrecompileDeployed(address(ed25519), "Ed25519Verify");
        emit PrecompileDeployed(address(query), "SubstrateQuery");
        emit PrecompileDeployed(address(transfer), "BalanceTransfer");
        emit PrecompileDeployed(address(staking), "StakingV2");
        emit PrecompileDeployed(address(metagraph), "Metagraph");
    }
}
