# TAO20 Oracle Architecture Implementation Plan

## Overview

This document outlines the implementation plan for the TAO20 subnet's oracle-free architecture, designed to eliminate external dependencies while providing transparent, on-chain NAV calculations and miner incentivization through volume-based consensus.

## Architecture Principles

### Core Design Goals
- **Eliminate External Oracles**: Fully on-chain, no off-chain price feeders
- **Transparent Launch**: 1:1 TAO peg for maximum trust and auditability  
- **Miner Volume Incentives**: Validators rank miners by transaction volume
- **Real-Time NAV**: On-demand calculation for every mint/redeem
- **Future-Ready**: Architecture supports emission-weighted NAV evolution

### Participant Roles
- **Miners**: Generate transaction volume by calling mint/redeem functions
- **Validators**: Monitor miner activity and produce consensus rankings
- **Users**: Mint/redeem TAO20 tokens using the oracle-free pricing

## Phase 1: Oracle-Free Launch Implementation

### 1.1 Enhanced NAV Calculator

**File**: `contracts/src/OracleFreeNAVCalculator.sol`

```solidity
// Core NAV calculation logic
contract OracleFreeNAVCalculator {
    // Bittensor Metagraph precompile at 0x...802
    IMetagraphPrecompile constant METAGRAPH = IMetagraphPrecompile(0x0000000000000000000000000000000000000802);
    
    // Phase 1: Simple 1:1 peg
    function getCurrentNAV() external view returns (uint256) {
        return 1e18; // 1.0 TAO per TAO20
    }
    
    // Phase 2: Emission-weighted (future)
    function getEmissionWeightedNAV(uint256 totalSupply) external view returns (uint256) {
        // Implementation for emission-based NAV calculation
        // Uses METAGRAPH.getEmission() for real-time data
    }
}
```

**Key Features**:
- Initial 1:1 peg for launch simplicity
- Precompile integration ready for Phase 2
- Per-transaction calculation (no stale prices)
- Deterministic and auditable

### 1.2 Enhanced TAO20CoreV2 Integration

**Modifications to**: `contracts/src/TAO20CoreV2.sol`

```solidity
contract TAO20CoreV2Enhanced {
    OracleFreeNAVCalculator public immutable navCalculator;
    
    // Miner volume tracking
    mapping(address => uint256) public minerVolumeStaked;
    mapping(address => uint256) public minerVolumeRedeemed;
    mapping(address => uint256) public minerTransactionCount;
    
    function mintTAO20(MintRequest calldata request, bytes calldata signature) external {
        // Existing verification logic...
        
        // Get real-time NAV (1:1 initially)
        uint256 currentNAV = navCalculator.getCurrentNAV();
        
        // Calculate TAO20 to mint
        uint256 tao20Amount = (request.deposit.amount * 1e18) / currentNAV;
        
        // Track miner activity
        _trackMinerActivity(msg.sender, request.deposit.amount, true);
        
        // Mint tokens
        tao20Token.mint(request.recipient, tao20Amount);
        
        emit TAO20Minted(request.recipient, tao20Amount, request.deposit.amount, currentNAV);
        emit MinerActivityTracked(msg.sender, request.deposit.amount, true);
    }
    
    function redeemTAO20(uint256 amount) external {
        // Get real-time NAV
        uint256 currentNAV = navCalculator.getCurrentNAV();
        
        // Calculate redemption value
        uint256 redemptionValue = (amount * currentNAV) / 1e18;
        
        // Track miner activity
        _trackMinerActivity(msg.sender, redemptionValue, false);
        
        // Execute redemption...
        
        emit MinerActivityTracked(msg.sender, redemptionValue, false);
    }
}
```

### 1.3 Miner Volume Tracking System

**New Events**:
```solidity
event MinerActivityTracked(
    address indexed miner,
    uint256 amount,
    bool isMint,
    uint256 timestamp,
    uint256 cumulativeVolume
);

event NAVUpdated(
    uint256 newNAV,
    uint256 timestamp,
    uint256 totalSupply,
    uint256 totalValue
);
```

**Tracking Functions**:
```solidity
function _trackMinerActivity(address miner, uint256 amount, bool isMint) internal {
    if (isMint) {
        minerVolumeStaked[miner] += amount;
    } else {
        minerVolumeRedeemed[miner] += amount;
    }
    
    minerTransactionCount[miner]++;
    
    uint256 totalVolume = minerVolumeStaked[miner] + minerVolumeRedeemed[miner];
    
    emit MinerActivityTracked(miner, amount, isMint, block.timestamp, totalVolume);
}

// Public view functions for validators
function getMinerStats(address miner) external view returns (
    uint256 volumeStaked,
    uint256 volumeRedeemed,
    uint256 totalVolume,
    uint256 transactionCount
) {
    volumeStaked = minerVolumeStaked[miner];
    volumeRedeemed = minerVolumeRedeemed[miner];
    totalVolume = volumeStaked + volumeRedeemed;
    transactionCount = minerTransactionCount[miner];
}
```

### 1.4 Validator Integration

**File**: `neurons/validator/oracle_validator.py`

```python
class OracleValidator:
    def __init__(self):
        self.contract_address = "0x..." # TAO20CoreV2 address
        self.metagraph_precompile = "0x0000000000000000000000000000000000000802"
        
    async def track_miner_activity(self):
        """Monitor MinerActivityTracked events"""
        # Subscribe to contract events
        events = await self.get_contract_events("MinerActivityTracked")
        
        # Update miner volume tracking
        for event in events:
            miner_address = event['miner']
            volume = event['amount']
            self.update_miner_score(miner_address, volume)
    
    def calculate_miner_rankings(self):
        """Rank miners by total volume"""
        # Get all miner stats from contract
        miner_stats = {}
        for miner in self.known_miners:
            stats = self.contract.getMinerStats(miner)
            miner_stats[miner] = stats['totalVolume']
        
        # Sort by volume (descending)
        ranked_miners = sorted(miner_stats.items(), key=lambda x: x[1], reverse=True)
        
        # Convert to Bittensor weights
        weights = self.volume_to_weights(ranked_miners)
        return weights
    
    def volume_to_weights(self, ranked_miners):
        """Convert volume rankings to Bittensor weight format"""
        total_volume = sum(volume for _, volume in ranked_miners)
        if total_volume == 0:
            return {}
        
        weights = {}
        for miner, volume in ranked_miners:
            # Proportional weight based on volume
            weight = volume / total_volume
            weights[miner] = weight
        
        return weights
```

## Phase 2: Emission-Weighted NAV Evolution

### 2.1 Enhanced NAV Calculation

```solidity
function getEmissionWeightedNAV(uint256 totalSupply) external view returns (uint256) {
    if (totalSupply == 0) return 1e18; // Initial NAV = 1.0
    
    // Get total emissions from all tracked subnets
    uint256 totalEmissions = 0;
    uint256 totalStaked = stakingManager.getTotalStaked();
    
    // Query emissions via Metagraph precompile
    uint16[] memory netuids = stakingManager.getCurrentNetuids();
    for (uint i = 0; i < netuids.length; i++) {
        uint256 subnetEmissions = METAGRAPH.getEmission(netuids[i]);
        totalEmissions += subnetEmissions;
    }
    
    // Convert RAO to TAO
    uint256 totalEmissionsTAO = totalEmissions / 1e9;
    
    // NAV = (initial_value + accumulated_emissions) / total_supply
    uint256 totalValue = totalStaked + totalEmissionsTAO;
    return totalValue * 1e18 / totalSupply;
}
```

### 2.2 Automatic Yield Compounding

```solidity
function compoundYield() external {
    // Get pending rewards from all subnets
    uint256 totalRewards = 0;
    uint16[] memory netuids = stakingManager.getCurrentNetuids();
    
    for (uint i = 0; i < netuids.length; i++) {
        bytes32 validator = stakingManager.getDefaultValidator(netuids[i]);
        uint256 rewards = STAKING.getStakingRewards(validator);
        totalRewards += rewards / 1e9; // Convert to TAO
    }
    
    // Update NAV with compounded rewards
    if (totalRewards > 0) {
        // Rewards increase the underlying value, raising NAV
        emit YieldCompounded(totalRewards, block.timestamp);
    }
}
```

## Implementation Timeline

### Week 1-2: Core Infrastructure
- [ ] Implement `OracleFreeNAVCalculator` contract
- [ ] Enhance `TAO20CoreV2` with volume tracking
- [ ] Add miner activity events and functions
- [ ] Test 1:1 NAV calculation accuracy

### Week 3-4: Validator Integration
- [ ] Implement `oracle_validator.py` with event monitoring
- [ ] Create miner ranking algorithm
- [ ] Test validator consensus mechanism
- [ ] Integrate with Bittensor weight system

### Week 5-6: Launch Preparation
- [ ] Deploy contracts to testnet
- [ ] Run end-to-end testing with miners/validators
- [ ] Security audit of oracle-free calculations
- [ ] Performance testing under load

### Week 7-8: Phase 2 Development
- [ ] Implement emission-weighted NAV calculation
- [ ] Add automatic yield compounding
- [ ] Test with real Bittensor emission data
- [ ] Prepare governance mechanism for NAV formula updates

## Security Considerations

### Oracle-Free Security
- **No External Dependencies**: System cannot be manipulated by external oracles
- **Deterministic Calculations**: Same inputs always produce same outputs
- **Transparent Logic**: All calculations visible on-chain
- **Immutable Initial Formula**: 1:1 peg cannot be changed arbitrarily

### Validator Consensus Security
- **On-Chain Data Source**: Miner activity tracked via contract events
- **Consensus Verification**: All validators see identical data
- **Anti-Gaming**: Volume-based rewards encourage real usage
- **Transparent Rankings**: Anyone can verify miner scores

### Smart Contract Security
- **ReentrancyGuard**: Prevent reentrancy attacks
- **SafeMath**: Prevent overflow/underflow
- **Access Control**: Proper authorization for sensitive functions
- **Emergency Pause**: Ability to halt operations if needed

## Monitoring & Analytics

### Real-Time Metrics
- Current NAV value
- Total transaction volume per miner
- Validator consensus scores
- System utilization rates

### Dashboard Components
- Live NAV calculation display
- Miner leaderboard by volume
- Validator agreement metrics
- Historical NAV evolution

## Future Enhancements

### Advanced NAV Models
- Multi-subnet emission weighting
- Time-decay volume calculations
- Dynamic rebalancing mechanisms
- Cross-chain integration

### Governance Evolution
- Community NAV formula proposals
- Decentralized parameter updates
- Validator set management
- Emergency response protocols

## Conclusion

This implementation plan provides a clear path from the current oracle-dependent system to a fully oracle-free, transparent, and incentive-aligned TAO20 subnet. The phased approach ensures a stable launch while building toward more sophisticated emission-based valuation models.

The architecture achieves the core goals of:
- ✅ Eliminating external oracle risk
- ✅ Providing transparent, auditable pricing
- ✅ Incentivizing miners through volume-based rewards
- ✅ Creating a foundation for future emission-weighted NAV

Phase 1 focuses on trust and simplicity with the 1:1 peg, while Phase 2 introduces the sophistication needed for true yield-bearing index tokens backed by Bittensor emissions.
