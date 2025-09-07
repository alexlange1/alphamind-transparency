# TAO20 Migration Plan: Phase 1 → Phase 2

## Overview

This document outlines the migration strategy from Phase 1 (Hybrid Oracle) to Phase 2 (Validator-Based with Slashing), following ChatGPT's excellent recommendation for a phased approach.

## Phase 1: Launch/MVP (Hybrid Oracle + On-Chain Verification)

### Duration: 6-12 months
### Goal: Establish trust and prove product-market fit

### Key Features:
- **✅ On-chain NAV calculation** - Fully transparent and auditable
- **✅ Simplified validator role** - Only submit raw price/emissions data  
- **✅ Regulatory friendly** - Easy to explain to auditors
- **✅ Lower technical risk** - Proven approach
- **✅ Gas efficient** - Biweekly calculations manageable

### Implementation:
```
HybridNAVOracle.sol
├── Validators submit: prices[] + emissions[]
├── Contract calculates: rolling averages, weights, NAV
├── Outlier detection: automatic rejection of bad data
└── Result: Transparent, auditable NAV on-chain
```

### Validator Requirements (Phase 1):
- **No staking required** (simplified onboarding)
- **Submit price data** for 20 subnet tokens
- **Submit emission data** from Bittensor
- **EIP-712 signatures** for authenticity
- **Simple registration** process

## Phase 2: Scaling/Maturity (Validator-Based with Slashing)

### Duration: After 6-12 months of successful Phase 1 operation
### Goal: Maximum decentralization and advanced features

### Key Features:
- **✅ Off-chain NAV calculation** - Validators compute full NAV
- **✅ Economic security** - Slashing for dishonest behavior
- **✅ Advanced logic** - Execution-adjusted pricing, MEV protection
- **✅ Bittensor-native** - Deep ecosystem understanding
- **✅ Scalable** - Handle complex scenarios

### Implementation:
```
NAVOracleWithSlashing.sol
├── Validators stake: 1000+ TAO minimum
├── Validators calculate: Full NAV with complex logic
├── Consensus mechanism: Stake-weighted median
├── Slashing conditions: Persistent deviation, invalid data
└── Result: Maximum security and decentralization
```

### Validator Requirements (Phase 2):
- **Minimum stake**: 1000 TAO
- **Full NAV calculation** using provided scripts
- **Economic incentives** - earn fees, lose stake for bad behavior
- **Advanced features** - handle slippage, execution costs, etc.

## Migration Timeline

### Months 1-3: Phase 1 Development & Testing
- [ ] Deploy HybridNAVOracle contract
- [ ] Launch with 3-5 trusted validators
- [ ] Monitor NAV accuracy and system stability
- [ ] Gather regulatory feedback
- [ ] Build user base and TVL

### Months 4-6: Phase 1 Optimization
- [ ] Expand to 10+ validators
- [ ] Optimize gas costs
- [ ] Add more price data sources
- [ ] Implement automated monitoring
- [ ] Prepare audit reports

### Months 7-9: Phase 2 Development
- [ ] Develop NAVOracleWithSlashing contract
- [ ] Create advanced validator scripts
- [ ] Design slashing parameters
- [ ] Extensive testing and simulations
- [ ] Security audits

### Months 10-12: Migration Preparation
- [ ] Validator recruitment and training
- [ ] Migration testing on testnet
- [ ] Community governance setup
- [ ] Final security reviews
- [ ] Migration announcement

### Month 13+: Phase 2 Launch
- [ ] Deploy Phase 2 contracts
- [ ] Migrate validator set
- [ ] Transfer control to new oracle
- [ ] Monitor transition period
- [ ] Sunset Phase 1 contracts

## Migration Mechanism

### Seamless Transition Strategy:
```solidity
contract TAO20CoreV2 {
    INAVOracle public currentOracle;  // Points to active oracle
    
    function migrateOracle(address newOracle) external onlyGovernance {
        // Validate new oracle
        require(INAVOracle(newOracle).getCurrentNAV() > 0, "Invalid oracle");
        
        // Update reference
        address oldOracle = address(currentOracle);
        currentOracle = INAVOracle(newOracle);
        
        emit OracleMigrated(oldOracle, newOracle);
    }
}
```

### Migration Checklist:
- [ ] New oracle deployed and tested
- [ ] Validators registered and staked
- [ ] NAV calculations validated against Phase 1
- [ ] Community approval via governance
- [ ] Migration executed during low-activity period
- [ ] Old oracle deprecated gracefully

## Risk Mitigation

### Phase 1 Risks:
- **Gas costs** - Mitigated by biweekly updates
- **Validator centralization** - Mitigated by easy onboarding
- **Price manipulation** - Mitigated by outlier detection

### Phase 2 Risks:
- **Validator collusion** - Mitigated by slashing and stake requirements
- **Complex bugs** - Mitigated by extensive testing and audits
- **Migration issues** - Mitigated by gradual transition

### Fallback Plans:
- **Phase 1 continuation** - If Phase 2 shows issues
- **Hybrid approach** - Combine both systems temporarily
- **External oracle** - Chainlink integration as backup

## Success Metrics

### Phase 1 Success Criteria:
- [ ] NAV accuracy within 0.5% of theoretical
- [ ] 99.9% uptime over 6 months
- [ ] Zero critical security incidents
- [ ] Positive regulatory feedback
- [ ] Growing TVL and user adoption

### Phase 2 Success Criteria:
- [ ] Successful validator onboarding (10+ validators)
- [ ] Effective slashing mechanism (deterrent effect)
- [ ] Advanced features working correctly
- [ ] Community governance functioning
- [ ] Continued growth and adoption

## Governance Integration

### Phase 1: Centralized (AlphaMind Team)
- Quick decision making for early iterations
- Direct communication with regulators
- Rapid bug fixes and improvements

### Phase 2: Decentralized (Community Governance)
- Token holder voting on parameters
- Validator set management by community
- Transparent upgrade processes

## Communication Strategy

### Stakeholder Updates:
- **Users**: Regular updates on system improvements
- **Validators**: Migration training and support
- **Regulators**: Transparency reports and compliance updates
- **Community**: Governance participation and feedback

### Key Messages:
- **Phase 1**: "Transparent, auditable, regulatory-friendly"
- **Phase 2**: "Maximum decentralization and security"
- **Migration**: "Seamless upgrade with no user disruption"

## Conclusion

This phased approach provides:
- **Low-risk launch** with proven technology
- **Regulatory clarity** from day one
- **Natural evolution** to full decentralization
- **Community building** time
- **Technical validation** before complex features

The migration from Phase 1 to Phase 2 represents TAO20's evolution from a trusted, transparent system to a fully decentralized, economically secured protocol that can handle the complexities of a mature DeFi product.

---

**Next Steps**: Begin Phase 1 development with HybridNAVOracle implementation and validator onboarding.
