# TAO20 Security Guide

## Overview

This guide outlines the comprehensive security measures implemented in TAO20 and provides operational guidance for maintaining a secure deployment.

## Critical Security Features

### 1. Smart Contract Security

#### Access Controls
- **Timelock Contract**: All critical parameter changes require a 24-hour delay
- **Role Separation**: Owner, timelock, and emergency functions are separated
- **Emergency Stop**: Circuit breaker for immediate protocol halting

```solidity
// Example: Critical functions require timelock
function setTxFeeBps(uint256 bps) external onlyTimelock { 
    require(bps <= 100, "fee too high"); // Max 1%
    txFeeBps = bps; 
}
```

#### Reentrancy Protection
All mint and redeem functions use `nonReentrant` modifier to prevent reentrancy attacks.

#### Overflow Protection
- Safe math for all calculations
- Bounds checking on fees and parameters
- Validation of price data before use

### 2. Oracle Security

#### Price Manipulation Protection
- **TWAP Integration**: Uses 30-minute time-weighted average prices
- **Deviation Limits**: Spot vs TWAP deviation capped at 20%
- **Staleness Checks**: Prices older than 5 minutes are rejected
- **Quorum Requirements**: Minimum 33% stake coverage required

```python
# Price validation example
def validate_price_freshness(price_reports, max_age_minutes=5):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=max_age_minutes)
    return [r for r in price_reports if parse_time(r.ts) >= cutoff]
```

### 3. Consensus Security

#### Stake-Weighted Consensus
- Median-based consensus resistant to outliers
- Stake-weighted voting prevents Sybil attacks
- Progressive slashing for dishonest behavior

#### Slashing Mechanism
```python
# Progressive penalties
if deviation_bps >= hard_threshold:    # >10%
    penalty = 20%  # 20% score reduction + strike
elif deviation_bps >= soft_threshold:  # >5%
    penalty = 5%   # 5% score reduction
```

### 4. API Security

#### Rate Limiting
- **Mint Operations**: 10 requests per 5 minutes per IP
- **Aggregate Operations**: 30 requests per minute per IP
- **General Endpoints**: 100 requests per minute per IP

#### Input Validation
```python
# Comprehensive validation
validate_positive_amount(amount, "amount")
validate_weights(weights)
validate_prices(prices)
sanitize_file_path(path)
```

#### Authentication
- Bearer token authentication required
- Admin token for sensitive operations
- CORS protection configured

### 5. Monitoring & Alerting

#### Security Monitoring
```python
# Real-time security alerts
monitor.alert("price_manipulation", "high", 
    f"Large price deviation: {deviation}%")

monitor.check_consensus_quorum(quorum_pct, min_quorum=33.0)
monitor.check_emergency_conditions(nav_change_pct)
```

## Deployment Security Checklist

### Pre-Deployment

- [ ] External security audit completed
- [ ] All tests passing (including stress tests)
- [ ] Timelock contract deployed and configured
- [ ] Emergency procedures documented
- [ ] Monitoring systems configured

### Environment Variables

**Required Security Settings:**
```bash
# Authentication
export AM_API_TOKEN="your-secure-api-token"
export AM_ADMIN_TOKEN="your-secure-admin-token"

# Signature Verification
export AM_REQUIRE_SIGNING=1
export AM_REQUIRE_HOTKEY=1
export AM_REJECT_HMAC=1

# Rate Limiting
export AM_MINT_RATE_LIMIT=10
export AM_MINT_WINDOW_SEC=300
export AM_GENERAL_RATE_LIMIT=100

# Oracle Security
export AM_PRICE_QUORUM=0.33
export AM_PRICE_STALE_SEC=300
export AM_PRICE_BAND_PCT=0.2

# Consensus Security
export AM_EMISSIONS_QUORUM=0.33
export AM_EMISSIONS_BAND_PCT=0.5
export AM_EMISSIONS_MAD_K=5.0
```

### Smart Contract Deployment

1. **Deploy Timelock**: Set appropriate delay (24-48 hours)
2. **Deploy Vault**: Initialize with timelock as admin
3. **Configure Parameters**: Set safe initial values
4. **Transfer Ownership**: Move ownership to timelock

```solidity
// Example deployment sequence
Timelock timelock = new Timelock(admin, 1 days);
Vault vault = new Vault(validatorSet);
vault.setTimelock(address(timelock));
// Transfer ownership through timelock after deployment
```

## Operational Security

### Monitoring Dashboard

Key metrics to monitor:
- Active security alerts by severity
- Consensus quorum levels
- Price deviation indicators
- API rate limiting effectiveness
- Memory and performance metrics

### Emergency Procedures

#### Level 1: Suspicious Activity
1. Increase monitoring frequency
2. Review recent transactions
3. Check consensus data for anomalies

#### Level 2: Confirmed Attack
1. Trigger emergency stop if necessary
2. Pause affected assets
3. Notify stakeholders
4. Begin incident response

#### Level 3: Critical Vulnerability
1. Immediate protocol pause
2. Emergency validator meeting
3. Coordinate patch deployment
4. Public disclosure (after fix)

### Regular Security Tasks

**Daily:**
- Review security alerts
- Check system health metrics
- Verify backup integrity

**Weekly:**
- Review slashing logs
- Analyze consensus performance
- Update threat intelligence

**Monthly:**
- Security parameter review
- Incident response drill
- Dependency security audit

## Attack Vectors & Mitigations

### 1. Price Oracle Manipulation
**Attack**: Manipulate price feeds to exploit arbitrage
**Mitigation**: TWAP, deviation limits, quorum requirements, stake weighting

### 2. Consensus Attacks
**Attack**: Coordinate miners to bias emissions/prices
**Mitigation**: Stake-weighted medians, slashing, outlier detection

### 3. Front-Running
**Attack**: MEV attacks on mint/redeem transactions
**Mitigation**: Slippage protection, oracle-based validation, batch processing

### 4. Governance Attacks
**Attack**: Malicious parameter changes
**Mitigation**: Timelock delays, community oversight, emergency stops

### 5. Smart Contract Exploits
**Attack**: Reentrancy, overflow, logic bugs
**Mitigation**: Audited code, reentrancy guards, comprehensive testing

## Security Updates

### Upgrade Process
1. **Prepare**: Test upgrade thoroughly
2. **Announce**: Give community advance notice
3. **Queue**: Submit to timelock with delay
4. **Execute**: Deploy after timelock period
5. **Verify**: Confirm successful upgrade

### Emergency Patches
For critical vulnerabilities:
1. Emergency stop if needed
2. Expedited patch development
3. Community validation
4. Coordinated deployment

## Contact Information

**Security Issues**: security@alphamind.xyz
**Emergency Contact**: +1-XXX-XXX-XXXX
**Bug Bounty**: https://alphamind.xyz/security/bounty

## Security Resources

- [Smart Contract Audit Report](./audit-report.pdf)
- [Incident Response Playbook](./incident-response.md)
- [Monitoring Dashboard](https://monitoring.alphamind.xyz)
- [Security Updates](https://github.com/alphamind/tao20/security)

---

**Last Updated**: January 2025
**Version**: 1.0.0
