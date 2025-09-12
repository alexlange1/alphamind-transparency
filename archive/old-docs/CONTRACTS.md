# Smart Contracts

## Overview

The Alphamind smart contracts are built on BEVM (Bitcoin EVM) and handle the core functionality of the TAO20 index token system, including minting, redemption, and index management.

## Contract Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   TAO20 Token   │    │  Minter Logic   │    │   Vault Proxy   │
│   (ERC20)       │◄──►│   (Router)      │◄──►│   (Substrate)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Fee Manager    │    │  Param Registry │    │  Timelock       │
│  (Treasury)     │    │  (Governance)   │    │  (Security)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Core Contracts

### TAO20 Token (`TAO20.sol`)

The main index token implementing ERC20 standard with additional functionality for index management.

**Key Features:**
- Standard ERC20 functionality
- Index composition tracking
- Rebalancing logic
- Emergency pause controls

**Key Functions:**
```solidity
function mintInKind(
    uint256 amount,
    bytes32 minerHotkey,
    bytes calldata signature,
    bytes calldata message
) external;

function redeemInKind(
    uint256 amount,
    bytes32 minerHotkey,
    bytes calldata signature,
    bytes calldata message
) external;

function getIndexComposition() external view returns (uint256[] memory, uint256[] memory);
```

### Router (`Router.sol`)

Handles the routing of minting and redemption operations with slippage protection and validation.

**Key Features:**
- Slippage protection
- Input validation
- Gas optimization
- Error handling

**Key Functions:**
```solidity
function mintWithSlippage(
    uint256 amount,
    uint256 minAmountOut,
    bytes32 minerHotkey,
    bytes calldata signature,
    bytes calldata message
) external;

function redeemWithSlippage(
    uint256 amount,
    uint256 minAmountOut,
    bytes32 minerHotkey,
    bytes calldata signature,
    bytes calldata message
) external;
```

### Fee Manager (`FeeManager.sol`)

Manages fee collection and distribution for the protocol.

**Fee Structure:**
- **Minting Fee**: 0.1% of minted amount
- **Redemption Fee**: 0.1% of redeemed amount
- **Performance Fee**: 10% of profits (quarterly)

**Key Functions:**
```solidity
function collectMintFee(uint256 amount) external returns (uint256);
function collectRedeemFee(uint256 amount) external returns (uint256);
function distributeFees() external;
```

### Validator Set (`ValidatorSet.sol`)

Manages the set of validators that attest to minting and redemption operations.

**Key Features:**
- Validator registration/deregistration
- Stake management
- Slashing conditions
- Consensus threshold

**Key Functions:**
```solidity
function registerValidator(bytes32 hotkey, uint256 stake) external;
function deregisterValidator(bytes32 hotkey) external;
function slashValidator(bytes32 hotkey, uint256 amount) external;
```

## Security Features

### Access Control

- **Owner**: Can pause/unpause, upgrade contracts, manage parameters
- **Validator**: Can attest to operations, manage validator set
- **Miner**: Can initiate minting/redemption operations
- **Public**: Can view index composition, NAV, etc.

### Emergency Controls

```solidity
function pause() external onlyOwner;
function unpause() external onlyOwner;
function emergencyWithdraw() external onlyOwner;
```

### Timelock

All governance actions are subject to a 24-hour timelock:

```solidity
function queueTransaction(
    address target,
    uint256 value,
    string calldata signature,
    bytes calldata data,
    uint256 eta
) external;
```

## Precompiles Integration

### Ed25519 Verification

Used for Bittensor hotkey signature verification:

```solidity
function verifyEd25519(
    bytes32 publicKey,
    bytes32 message,
    bytes calldata signature
) internal view returns (bool) {
    return Ed25519Verify.verify(publicKey, message, signature);
}
```

### Staking V2

Used for managing validator stakes:

```solidity
function stake(bytes32 hotkey, uint256 amount) internal {
    StakingV2.stake(hotkey, amount);
}
```

## Gas Optimization

### Batch Operations

Multiple operations can be batched to reduce gas costs:

```solidity
function batchMint(
    uint256[] calldata amounts,
    bytes32[] calldata minerHotkeys,
    bytes[] calldata signatures,
    bytes[] calldata messages
) external;
```

### Storage Optimization

- Use packed structs for small data
- Optimize storage layout
- Use events for off-chain data

## Testing

### Test Coverage

- **Unit Tests**: 95%+ coverage
- **Integration Tests**: Full contract interaction testing
- **Fuzzing**: Property-based testing with Foundry
- **Formal Verification**: Key properties verified with Certora

### Test Commands

```bash
# Run all tests
forge test

# Run with coverage
forge coverage

# Run specific test
forge test --match-test testMintInKind

# Run fuzzing
forge test --fuzz-runs 10000
```

## Deployment

### Network Addresses

| Network | TAO20 Token | Router | Fee Manager | Validator Set |
|---------|-------------|--------|-------------|---------------|
| BEVM Mainnet | `0x...` | `0x...` | `0x...` | `0x...` |
| BEVM Testnet | `0x...` | `0x...` | `0x...` | `0x...` |

### Deployment Scripts

```bash
# Deploy to testnet
forge script script/Deploy.s.sol --rpc-url $TESTNET_RPC --broadcast

# Deploy to mainnet
forge script script/Deploy.s.sol --rpc-url $MAINNET_RPC --broadcast
```

## Audit Status

- **Internal Review**: ✅ Complete
- **External Audit**: 🔄 In Progress (Trail of Bits)
- **Bug Bounty**: 🔄 Active on Immunefi

## Upgradeability

Contracts use OpenZeppelin's upgradeable pattern:

```solidity
contract TAO20 is Initializable, ERC20Upgradeable, OwnableUpgradeable {
    function initialize(
        string memory name,
        string memory symbol,
        address initialOwner
    ) public initializer {
        __ERC20_init(name, symbol);
        __Ownable_init(initialOwner);
    }
}
```

## Monitoring

### Events

Key events for monitoring:

```solidity
event Minted(address indexed miner, uint256 amount, uint256 tao20Amount);
event Redeemed(address indexed miner, uint256 tao20Amount, uint256[] subnetAmounts);
event IndexRebalanced(uint256[] subnets, uint256[] weights);
event ValidatorRegistered(bytes32 indexed hotkey, uint256 stake);
event ValidatorSlashed(bytes32 indexed hotkey, uint256 amount);
```

### Metrics

- Total Value Locked (TVL)
- Daily Volume
- Fee Revenue
- Validator Count
- Index Performance
