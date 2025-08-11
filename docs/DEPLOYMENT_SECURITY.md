# TAO20 Secure Deployment Guide

## Prerequisites

### Security Requirements
- [ ] External security audit completed and issues resolved
- [ ] All security tests passing (13/13 core tests)
- [ ] Stress tests show acceptable performance under load
- [ ] Emergency response team trained and ready
- [ ] Monitoring infrastructure deployed

### Infrastructure Requirements
- [ ] Multi-signature wallet setup for contract administration
- [ ] Secure environment variables management
- [ ] Rate limiting and DDoS protection at infrastructure level
- [ ] SSL/TLS certificates configured
- [ ] Backup and disaster recovery procedures tested

## Deployment Steps

### 1. Smart Contract Deployment

**Deploy in this order:**

```bash
# 1. Deploy Timelock with 24-hour delay
forge script --rpc-url $RPC_URL --private-key $DEPLOYER_KEY \
  script/DeployTimelock.s.sol --broadcast

# 2. Deploy ValidatorSet with admin
forge script --rpc-url $RPC_URL --private-key $DEPLOYER_KEY \
  script/DeployValidatorSet.s.sol --broadcast

# 3. Deploy Vault with ValidatorSet address
forge script --rpc-url $RPC_URL --private-key $DEPLOYER_KEY \
  script/DeployVault.s.sol --broadcast

# 4. Configure Vault with Timelock
forge script --rpc-url $RPC_URL --private-key $DEPLOYER_KEY \
  script/ConfigureVault.s.sol --broadcast
```

**Security Configuration:**
```solidity
// Set conservative initial parameters
vault.setTxFeeBps(20);        // 0.2%
vault.setMgmtAprBps(100);     // 1.0%
vault.setTimelock(timelock);   // Enable timelock governance
vault.setPaused(true);        // Start paused for final checks
```

### 2. Environment Configuration

**Required Security Environment Variables:**

```bash
# Authentication & Authorization
export AM_API_TOKEN=$(openssl rand -hex 32)
export AM_ADMIN_TOKEN=$(openssl rand -hex 32)

# Signature Security
export AM_REQUIRE_SIGNING=1
export AM_REQUIRE_HOTKEY=1
export AM_REJECT_HMAC=1

# Rate Limiting (Production Settings)
export AM_MINT_RATE_LIMIT=5           # Conservative limit
export AM_MINT_WINDOW_SEC=300         # 5 minutes
export AM_GENERAL_RATE_LIMIT=50       # API calls per minute
export AM_GENERAL_WINDOW_SEC=60

# Oracle Security
export AM_PRICE_QUORUM=0.40           # Require 40% stake coverage
export AM_PRICE_STALE_SEC=300         # 5 minute max age
export AM_PRICE_BAND_PCT=0.15         # 15% deviation limit
export AM_PRICE_DEVIATION_ALERT=0.10  # Alert at 10%

# Consensus Security  
export AM_EMISSIONS_QUORUM=0.40       # Require 40% stake coverage
export AM_EMISSIONS_BAND_PCT=0.30     # 30% deviation limit
export AM_EMISSIONS_MAD_K=3.0         # 3-sigma outlier detection

# Slashing Parameters
export AM_SLASH_SOFT_THRESH_BPS=500   # 5% soft threshold
export AM_SLASH_HARD_THRESH_BPS=1000  # 10% hard threshold
export AM_STRIKES_SUSPEND=3           # Suspend after 3 strikes
export AM_MAX_SCORE_PENALTY=0.50      # Max 50% penalty per violation

# System Security
export AM_MAX_SLIPPAGE_BPS=100        # 1% max slippage
export AM_EMERGENCY_COOLDOWN=3600     # 1 hour emergency cooldown

# Monitoring
export AM_MONITORING_ENABLED=1
export AM_ALERT_WEBHOOK_URL="https://monitoring.alphamind.xyz/webhook"
export AM_LOG_LEVEL=INFO
```

### 3. Validator Network Setup

**Initialize Validator Set:**
```bash
# Register initial validators (use secure key management)
python3 -m subnet.validator.setup \
  --validator-keys validator1.key,validator2.key,validator3.key \
  --min-validators 3 \
  --registry-address $REGISTRY_ADDRESS
```

**Validator Security Checklist:**
- [ ] Validators running on separate infrastructure
- [ ] Secure key storage (HSM or secure enclaves)
- [ ] Network isolation and firewalls configured
- [ ] Monitoring and alerting active
- [ ] Backup validators ready for failover

### 4. Security Validation

**Pre-Launch Security Tests:**

```bash
# Run comprehensive security test suite
python3 -m pytest tests/test_security_core.py -v
python3 -m pytest tests/test_consensus.py -v 
python3 -m pytest tests/test_security_fixes.py -v

# Run stress tests
PYTHONPATH=$PWD python3 tests/stress_test.py

# Test emergency procedures
python3 scripts/test_emergency_stop.py

# Validate smart contract security
slither contracts/src/
mythril analyze contracts/src/Vault.sol
```

**Manual Security Validation:**
1. Verify timelock delays are correctly set
2. Test emergency stop functionality
3. Confirm rate limiting works as expected
4. Validate input sanitization
5. Test oracle manipulation resistance
6. Verify slashing mechanisms activate correctly

### 5. Monitoring Setup

**Deploy Monitoring Infrastructure:**

```yaml
# monitoring/docker-compose.yml
version: '3.8'
services:
  prometheus:
    image: prom/prometheus
    ports: ["9090:9090"]
    volumes: ["./prometheus.yml:/etc/prometheus/prometheus.yml"]
    
  grafana:
    image: grafana/grafana
    ports: ["3000:3000"]
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=$GRAFANA_PASSWORD
    volumes: ["./grafana:/var/lib/grafana"]
    
  alertmanager:
    image: prom/alertmanager
    ports: ["9093:9093"]
    volumes: ["./alertmanager.yml:/etc/alertmanager/alertmanager.yml"]
```

**Critical Alerts Configuration:**
```yaml
# alertmanager.yml
rules:
- alert: HighSecurityAlerts
  expr: tao20_security_alerts{severity="critical"} > 0
  for: 0m
  labels: {severity: critical}
  annotations:
    summary: "Critical security alert detected"
    
- alert: LowConsensusQuorum  
  expr: tao20_consensus_quorum < 0.33
  for: 5m
  labels: {severity: high}
  annotations:
    summary: "Consensus quorum below threshold"
    
- alert: HighPriceDeviation
  expr: tao20_price_deviation > 0.20
  for: 1m
  labels: {severity: high}
  annotations:
    summary: "Price deviation exceeds safety limits"
```

### 6. Launch Sequence

**Staged Deployment:**

**Phase 1: Restricted Launch (Week 1)**
```bash
# Enable protocol with conservative limits
vault.setPaused(false)
vault.setTxFeeBps(30)           # Higher initial fee (0.3%)
vault.setCompositionTolerance(200)  # 2% tolerance

# Monitor closely:
# - Transaction volume < 1000 TAO per day
# - Number of unique users < 100
# - All security metrics green
```

**Phase 2: Gradual Scale (Week 2-4)**
```bash
# Increase limits gradually
vault.setTxFeeBps(20)           # Reduce to 0.2%
vault.setCompositionTolerance(100)  # Reduce to 1%

# Monitor:
# - Transaction volume < 10,000 TAO per day
# - Number of unique users < 1000
# - Stress test system under real load
```

**Phase 3: Full Production (Month 2+)**
```bash
# Normal operating parameters
# - All security systems proven
# - Emergency procedures tested
# - Community governance transition begins
```

## Security Monitoring

### Real-time Dashboards

**Critical Metrics to Monitor:**
- Security alert counts by severity
- Consensus quorum percentages
- Price deviation indicators  
- API rate limiting effectiveness
- Smart contract function call patterns
- Emergency stop trigger conditions

**Performance Metrics:**
- Transaction throughput
- Response times
- Memory usage patterns
- Network connectivity
- Database performance

### Alert Escalation

**Level 1: Automated Response**
- Rate limiting activation
- Temporary asset pausing
- Validator notifications

**Level 2: Human Response (< 15 minutes)**
- Security team notification
- Incident investigation
- Stakeholder communication

**Level 3: Emergency Response (< 5 minutes)**  
- Emergency stop activation
- All operations halted
- Immediate team assembly
- Public communication

## Emergency Procedures

### Emergency Stop Process

1. **Detection**: Automated monitoring or manual identification
2. **Assessment**: Rapid threat evaluation (< 2 minutes)
3. **Decision**: Go/no-go decision by authorized personnel
4. **Execution**: Emergency stop activation
5. **Communication**: Immediate public notification
6. **Investigation**: Full incident analysis
7. **Recovery**: Coordinated protocol resume

### Emergency Contact Protocol

**Immediate Response Team:**
- Security Lead: security@alphamind.xyz
- Technical Lead: tech@alphamind.xyz  
- Operations Lead: ops@alphamind.xyz

**Escalation Chain:**
1. On-call engineer (24/7)
2. Team leads (< 15 min)
3. Executive team (< 30 min)
4. Community notification (< 1 hour)

## Post-Deployment Security

### Regular Security Tasks

**Daily:**
- Review security alert dashboard
- Check system health metrics
- Validate backup integrity
- Monitor consensus performance

**Weekly:**
- Analyze slashing logs
- Review rate limiting effectiveness
- Update threat intelligence
- Test emergency procedures

**Monthly:**
- Security parameter review
- Dependency security audit
- Incident response drill
- Community security update

**Quarterly:**
- External security assessment
- Code audit refresh
- Emergency procedure updates
- Governance security review

### Security Updates

**Normal Updates (via Timelock):**
1. Propose changes with 48-hour notice
2. Community review period
3. Submit to timelock (24-hour delay)
4. Execute after delay period

**Emergency Updates:**
1. Emergency stop if needed
2. Critical patch development
3. Expedited community review
4. Coordinated emergency deployment

## Governance Security

### Timelock Management

**Parameter Change Process:**
1. Technical analysis and impact assessment
2. Community proposal and discussion
3. Technical review and testing
4. Timelock submission with appropriate delay
5. Final review before execution
6. Monitoring post-implementation

**Emergency Override Conditions:**
- Critical vulnerability discovered
- Active exploit in progress
- System integrity compromised
- Community safety at risk

### Decentralization Timeline

**Month 1-3: Bootstrap Phase**
- Core team maintains full control
- Focus on security and stability
- Community feedback integration

**Month 4-6: Transition Phase**
- Introduce community governance
- Transfer non-critical functions
- Test governance processes

**Month 7+: Decentralized Phase**
- Community-controlled governance
- Core team advisory role only
- Full decentralization achieved

---

**Security Contact**: security@alphamind.xyz  
**Last Updated**: January 2025  
**Version**: 1.0.0
