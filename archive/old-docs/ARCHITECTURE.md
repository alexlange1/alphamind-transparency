# Alphamind Architecture

## System Overview

Alphamind ($TAO20) is a decentralized index token that tracks the top 20 Bittensor subnets. The system consists of four main components:

1. **Smart Contracts** (BEVM)
2. **Bittensor Subnet** (Miner-Validator Network)
3. **Frontend Interface** (User Experience)
4. **Backend API** (Deposit Verification)

## Smart Contract Architecture

### Core Contracts

#### Tao20Minter.sol
The main contract that handles:
- **Minting**: Users deposit subnet tokens, receive TAO20
- **Redemption**: Users burn TAO20, receive underlying tokens
- **Attestation**: Multi-validator consensus for deposit verification
- **DEX Integration**: Uniswap V3 swaps for liquidity
- **Auto-Staking**: Automatic staking of underlying tokens

#### Key Features
- **Execution NAV**: Fair pricing based on actual DEX execution
- **Delayed Queue**: MEV protection through batched execution
- **Slippage Protection**: Configurable per-pool slippage limits
- **Emergency Controls**: Pause functionality and governance

### Precompile Integration

#### Ed25519 Verify (0x402)
Used for:
- User ownership verification
- Deposit signature validation
- Replay protection

#### Staking V2 (0x805)
Used for:
- Automatic staking of underlying tokens
- Stake verification and management
- RAO conversion (1 TAO = 1e9 RAO)

## Bittensor Subnet Architecture

### Validators
- **Consensus**: Aggregate miner reports using stake-weighted median
- **Attestation**: Sign deposit confirmations for minting
- **API Service**: Provide public endpoints for index data
- **Scoring**: Evaluate miner performance and apply penalties

### Miners
- **Data Collection**: Monitor Bittensor network for subnet data
- **Report Generation**: Submit signed reports with cryptographic verification
- **Competition**: Earn rewards based on data accuracy and timeliness

## Security Model

### Multi-Layer Security

1. **Attestation-Based Consensus**: M-of-N validator signatures required
2. **Precompile Verification**: On-chain signature and stake verification
3. **Slippage Protection**: Per-hop slippage limits and pool whitelisting
4. **Emergency Controls**: Pause functionality and timelock governance
5. **Reentrancy Protection**: All external calls protected

### Access Controls

- **Owner**: Can update configuration parameters
- **Timelock**: 24-hour delay for critical changes
- **Emergency**: Immediate pause functionality
- **Keepers**: Authorized batch execution

## Data Flow

### Minting Flow
1. User sends subnet tokens to vault
2. Indexer records deposit after finality
3. User signs structured message with ed25519
4. Validators attest deposit (M-of-N threshold)
5. Contract verifies signature via precompile
6. Mint claim queued for batch execution
7. Keeper executes DEX swaps and mints TAO20

### Redemption Flow
1. User calls `redeem()` with TAO20 shares
2. Redemption queued for batch execution
3. Keeper executes DEX swaps to acquire underlying
4. Shares burned and underlying tokens transferred
5. Auto-staking buffer maintained

## Technical Specifications

### Gas Optimization
- **Batch Processing**: Multiple operations in single transaction
- **Efficient Storage**: Packed structs and optimized mappings
- **Minimal External Calls**: Reduced gas costs through batching

### Scalability
- **Configurable Batch Sizes**: Adjustable based on network conditions
- **Queue Management**: Efficient processing of mint/redeem requests
- **Pool Rotation**: Support for multiple DEX pools

## Monitoring & Observability

### Metrics
- **Queue Depth**: Number of pending mint/redeem requests
- **Batch Latency**: Time from queue to execution
- **Slippage**: Actual vs expected execution prices
- **Attestation Latency**: Time for validator consensus
- **Staking Success Rate**: Percentage of successful auto-stakes

### Events
- `ClaimQueued`: Mint request queued
- `BatchExecuted`: Batch processing completed
- `RedeemQueued`: Redemption request queued
- `RedeemExecuted`: Redemption processing completed
- `AttestationSubmitted`: Validator attestation received
- `StakeUpdated`: Auto-staking operation completed

## Deployment Architecture

### Networks
- **BEVM Mainnet**: Production smart contracts
- **BEVM Testnet**: Testing and validation
- **Bittensor Mainnet**: Subnet operations
- **Bittensor Testnet**: Development and testing

### Infrastructure
- **Validators**: High-availability API servers
- **Miners**: Lightweight data collection nodes
- **Keepers**: Automated batch execution
- **Frontend**: User interface and wallet integration
