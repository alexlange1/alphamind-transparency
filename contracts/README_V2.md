# TAO20 V2 - Trustless Index Architecture

## Overview

TAO20 V2 is a complete redesign of the TAO20 index system, implementing a fully trustless and decentralized architecture. This version removes centralized control mechanisms in favor of cryptographic proofs and economic incentives.

## Key Improvements

### 🔒 Trustless Design
- **No validator attestations** required for minting/redeeming
- **Direct Ed25519 verification** of Substrate deposits
- **No emergency controls** or admin privileges
- **Immutable contracts** with no upgrade mechanisms

### 🚀 Simplified Architecture
- **No supply caps** - supply floats based on actual deposits
- **No blacklisting** - protocol remains neutral
- **No circuit breakers** - trust economic mechanisms
- **Streamlined codebase** with essential functionality only

### 💰 Enhanced Yield Management
- **Automatic staking** of all deposits
- **Yield compounding** increases token value
- **Anti-dilution mechanism** protects existing holders
- **Transparent reward distribution**

## Architecture Components

### 1. TAO20CoreV2.sol
**Main controller contract handling minting and redeeming**

**Key Features:**
- Direct Ed25519 signature verification via precompile
- On-chain Substrate deposit verification
- Automatic staking integration
- Yield-adjusted NAV calculations
- Replay protection with nonces

**Minting Process:**
1. User deposits SUBNET TOKENS (Alpha tokens) to Substrate vault
2. User creates mint request with Ed25519 signature
3. Contract verifies signature proves deposit ownership
4. Contract verifies subnet token deposit exists on Substrate
5. Subnet tokens are automatically staked for yield
6. TAO20 tokens are minted based on current NAV and subnet token value

**Redeeming Process:**
1. User burns TAO20 tokens
2. Contract calculates redemption value using current NAV
3. Contract unstakes subnet tokens proportionally across all subnets
4. Unstaked subnet tokens are transferred to user

### 2. TAO20V2.sol
**Simplified ERC20 token without restrictions**

**Key Features:**
- No supply cap - unlimited minting based on deposits
- No blacklisting mechanism
- No emergency controls
- Single authorized minter (TAO20Core)
- Standard ERC20 functionality with reentrancy protection

### 3. NAVOracle.sol
**Decentralized oracle for NAV calculation**

**Key Features:**
- Validator consensus for NAV submissions
- Stake-weighted median calculation
- Outlier rejection mechanism
- EIP-712 structured signatures
- Staleness protection

**Validator Role:**
- Submit NAV calculations based on staking yields
- Provide consensus on index composition updates
- No involvement in minting/redeeming process

### 4. StakingManager.sol
**Automatic staking and yield management**

**Key Features:**
- Default validator strategy (one per subnet)
- Automatic staking of deposits via precompiles
- Yield compounding every 24 hours
- Proportional unstaking for redemptions
- Transparent reward tracking

## Precompile Integration

### Ed25519 Verify (0x402)
- Verifies user ownership of Substrate deposits
- Cryptographic proof without trusted intermediaries
- Prevents unauthorized minting

### Staking V2 (0x805)
- Handles automatic staking/unstaking
- Direct integration with Bittensor network
- Enables yield generation

### Substrate Query (0x803)
- Verifies deposit existence on Substrate chain
- Provides block timestamp verification
- Ensures deposit authenticity

## Security Model

### Cryptographic Security
- **Ed25519 signatures** prove deposit ownership
- **Nonce-based replay protection** prevents double-spending
- **Message hashing** ensures data integrity

### Economic Security
- **Asset backing** - every token backed by staked TAO
- **Yield integration** - staking rewards increase value
- **Market mechanisms** - supply/demand equilibrium

### Operational Security
- **Immutable contracts** - no admin controls
- **Transparent operations** - all actions on-chain
- **Decentralized validation** - multiple independent validators

## Deployment

### Prerequisites
- Foundry installed
- Private key in environment
- Access to BEVM testnet/mainnet

### Deploy Script
```bash
forge script script/DeployV2.s.sol --rpc-url $RPC_URL --broadcast --verify
```

### Post-Deployment Setup
1. Register real validator addresses in NAVOracle
2. Set actual validator hotkeys in StakingManager
3. Configure proper subnet composition
4. Test minting/redeeming functionality

## Usage Examples

### Minting TAO20 Tokens
```solidity
// User creates mint request
TAO20CoreV2.MintRequest memory request = TAO20CoreV2.MintRequest({
    recipient: userAddress,
    deposit: SubstrateDeposit({
        blockHash: depositBlockHash,
        extrinsicIndex: depositExtrinsicIndex,
        userSS58: userSubstrateKey,
        netuid: subnetId,
        amount: depositAmount,
        timestamp: blockTimestamp
    }),
    nonce: userNonce,
    deadline: block.timestamp + 1 hours
});

// User signs the request
bytes memory signature = signMintRequest(request, userPrivateKey);

// Execute mint
tao20Core.mintTAO20(request, signature);
```

### Redeeming TAO20 Tokens
```solidity
// Simply call redeem with amount
tao20Core.redeemTAO20(amountToRedeem);
```

### Validator NAV Submission
```solidity
// Validator calculates NAV and submits
uint256 calculatedNAV = calculateNAV();
bytes memory signature = signNAVSubmission(calculatedNAV, block.timestamp);
navOracle.submitNAV(calculatedNAV, block.timestamp, signature);
```

## Testing

### Unit Tests
```bash
forge test --match-contract TAO20CoreV2Test
forge test --match-contract TAO20V2Test
forge test --match-contract NAVOracleTest
forge test --match-contract StakingManagerTest
```

### Integration Tests
```bash
forge test --match-contract IntegrationTest
```

### Gas Analysis
```bash
forge test --gas-report
```

## Monitoring

### Key Metrics
- Total Value Locked (TVL)
- Current NAV
- Staking yields per subnet
- Validator participation rates
- Minting/redeeming volumes

### Events to Monitor
- `TAO20Minted` - New tokens minted
- `TAO20Redeemed` - Tokens redeemed
- `NAVUpdated` - Oracle consensus reached
- `YieldCompounded` - Rewards compounded

## Security Considerations

### Potential Risks
1. **Precompile Failures** - Mitigated by try/catch blocks
2. **Oracle Manipulation** - Mitigated by stake-weighted consensus
3. **Validator Collusion** - Mitigated by multiple validators and outlier rejection
4. **Smart Contract Bugs** - Mitigated by extensive testing and audits

### Best Practices
- Always verify signatures before processing
- Use nonces to prevent replay attacks
- Implement proper error handling
- Monitor for unusual activity patterns

## Future Enhancements

### Phase 2 Features
- Multi-validator staking strategy
- Dynamic validator selection
- Advanced yield optimization
- Cross-chain compatibility

### Governance (Optional)
- Community-driven parameter updates
- Validator set management
- Emergency response procedures

## Support

For questions or issues:
- Review the code documentation
- Check the test files for examples
- Submit issues on the repository
- Contact the development team

---

**⚠️ Disclaimer**: This is experimental software. Use at your own risk. Always verify contract addresses and audit code before using in production.
