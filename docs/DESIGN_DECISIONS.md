# TAO20 Design Decisions - Creation Unit Model

## 🎯 **Executive Summary**

TAO20 implements an **ETF-style creation/redemption system** with bi-weekly epoch-based weight updates and atomic basket delivery. This approach solves all core design challenges while maintaining professional standards and security.

## 🏗️ **Core Design Decisions**

### **1. ETF Creation Unit Model**
**Decision**: Use ETF-style creation/redemption instead of direct DEX integration

**Rationale**:
- ✅ **No DEX Dependency**: Uses existing Bittensor substrate infrastructure
- ✅ **Professional Standards**: Battle-tested model used by major ETFs
- ✅ **Price Risk Management**: Miners bear price risk appropriately
- ✅ **Atomic Execution**: All-or-nothing basket delivery prevents partial failures
- ✅ **Clear Epoch Boundaries**: Frozen weights prevent confusion during transitions

**Implementation**:
```python
# Creation File (Epoch Specification)
{
  "epoch_id": 1,
  "weights_hash": "0x1234...",
  "valid_from": 1640995200,
  "valid_until": 1642204800,
  "creation_unit_size": 1000,
  "cash_component_bps": 50,
  "tolerance_bps": 5,
  "min_creation_size": 1000,
  "assets": [
    {
      "netuid": 1,
      "asset_id": "0x1234...",
      "qty_per_creation_unit": 1000000000,
      "weight_bps": 500
    }
    // ... 19 more assets
  ]
}
```

### **2. All-or-Nothing Basket Delivery**
**Decision**: Require complete basket delivery with tight tolerances

**Rationale**:
- ✅ **Prevents Cherry-Picking**: Miners can't deliver only profitable assets
- ✅ **Maintains Index Integrity**: Ensures TAO20 tracks the intended composition
- ✅ **Atomic Execution**: Either all assets delivered or none
- ✅ **Tight Tolerances**: ±5 bps prevents significant deviations

**Implementation**:
```python
def validate_all_or_nothing(self, required: Dict[int, int], delivered: Dict[int, int]) -> bool:
    # All required assets must be present
    for netuid in required:
        if netuid not in delivered:
            return False
    
    # No extra assets allowed
    for netuid in delivered:
        if netuid not in required:
            return False
    
    # Quantities within tight tolerance (±5 bps)
    for netuid, required_qty in required.items():
        delivered_qty = delivered[netuid]
        tolerance = required_qty * 5 / 10000  # 5 bps
        
        if abs(delivered_qty - required_qty) > tolerance:
            return False
    
    return True
```

### **3. NAV Calculation at Receipt Block**
**Decision**: Calculate NAV at the block where basket delivery is finalized

**Rationale**:
- ✅ **Price Risk on Miners**: Miners bear price movement risk (as they should)
- ✅ **Fair Valuation**: NAV reflects actual delivery timing
- ✅ **No Protocol Risk**: Protocol doesn't bear price movement risk
- ✅ **Clear Accountability**: Miners responsible for timing and execution

**Implementation**:
```python
async def calculate_nav_at_block(self, block_number: int, basket_totals: Dict[int, int]) -> float:
    total_value = 0
    total_shares = 0
    
    for netuid, amount in basket_totals.items():
        # Get price at specific block using official pricing
        price = await self.get_official_price_at_block(netuid, block_number)
        value = amount * price
        total_value += value
        total_shares += amount
    
    return total_value / total_shares if total_shares > 0 else 0
```

### **4. Multi-Validator Attestation**
**Decision**: Require multiple validator attestations for minting

**Rationale**:
- ✅ **Security**: Prevents single point of failure
- ✅ **Consensus**: Multiple validators must agree on NAV calculation
- ✅ **Transparency**: All attestations recorded on-chain
- ✅ **Auditability**: Complete audit trail of minting decisions

**Implementation**:
```solidity
function submitAttestation(Attestation calldata attestation) external {
    require(validators[msg.sender], "Not authorized validator");
    require(!attestations[attestation.requestId][attestation.validatorHotkey], "Already attested");
    
    // Verify signature and epoch consistency
    require(verifyAttestationSignature(attestation), "Invalid signature");
    require(attestation.epochId == currentEpochId, "Wrong epoch");
    
    // Record attestation
    attestations[attestation.requestId][attestation.validatorHotkey] = true;
    attestationCount[attestation.requestId]++;
    
    // Execute mint if enough attestations
    if (attestationCount[attestation.requestId] >= requiredAttestations) {
        executeMint(attestation);
    }
}
```

### **5. Epoch-Frozen Composition**
**Decision**: Freeze weights for entire epoch (2 weeks)

**Rationale**:
- ✅ **Predictability**: Miners know exact requirements for 2 weeks
- ✅ **No Mid-Epoch Changes**: Prevents confusion and rebalancing issues
- ✅ **Clear Boundaries**: Unfinished creations expire at epoch end
- ✅ **Stability**: Reduces operational complexity

**Implementation**:
```python
class EpochManager:
    def __init__(self):
        self.epoch_duration = 1209600  # 14 days
    
    def is_valid_epoch(self, epoch_id: int) -> bool:
        current_epoch = self.get_current_epoch()
        return epoch_id == current_epoch
    
    def expire_old_requests(self):
        """Expire requests from previous epochs"""
        current_epoch = self.get_current_epoch()
        
        for request_id, request in self.creation_requests.items():
            if request.epoch_id < current_epoch and request.status == 'pending':
                request.status = 'expired'
                await self.return_tokens(request)
```

### **6. Auto-Staking of Underlying Tokens**
**Decision**: Automatically stake received subnet tokens

**Rationale**:
- ✅ **Ecosystem Alignment**: Aligns with Bittensor staking model
- ✅ **Revenue Generation**: Staking rewards flow into NAV
- ✅ **Network Security**: Contributes to subnet security
- ✅ **Passive Income**: Generates yield for TAO20 holders

**Implementation**:
```solidity
function autoStakeUnderlying(uint256[] memory basketTotals) internal {
    for (uint256 i = 0; i < basketTotals.length; i++) {
        uint256 netuid = activeSubnets[i];
        uint256 amount = basketTotals[i];
        
        if (amount > 0) {
            // Convert to RAO (1 TAO = 1e9 RAO)
            uint256 raoAmount = amount * 1e9;
            
            // Get hotkey for this subnet
            bytes32 hotkey = bytes32(uint256(netuid));
            
            // Stake via precompile
            (bool ok,) = address(STAKE).call(
                abi.encodeWithSignature("addStake(bytes32,uint256)", hotkey, raoAmount)
            );
            require(ok, "STAKE_FAIL");
        }
    }
}
```

## 🔄 **Mint Flow Architecture**

### **Phase 1: Creation Request**
1. Miner submits creation request with size
2. System validates minimum size requirements
3. System provides exact basket specifications

### **Phase 2: Basket Delivery**
1. Miner acquires all required subnet tokens
2. Miner delivers complete basket to substrate vault
3. System validates all-or-nothing delivery
4. System records receipt block for NAV calculation

### **Phase 3: Validator Attestation**
1. Validators verify basket delivery
2. Validators calculate NAV at receipt block
3. Validators sign attestations with NAV and shares calculation
4. Multiple validators must attest (consensus)

### **Phase 4: BEVM Minting**
1. Contract verifies sufficient attestations
2. Contract mints TAO20 shares to miner
3. Contract auto-stakes underlying tokens
4. Contract records fees and events

## 🔄 **Redeem Flow Architecture**

### **In-Kind Redemption (Default)**
1. Holder burns TAO20 shares
2. System calculates proportional basket
3. System transfers underlying tokens from vault
4. System unstakes proportional amounts

### **Cash Redemption (Future)**
- Disabled until DEX exists
- Protocol would sell underlying tokens
- More complex implementation

## 🛡️ **Critical Guardrails**

### **1. Minimum Creation Size**
- Prevents spam and ensures rounding is negligible
- Default: 1,000 creation units

### **2. Tight Tolerances**
- ±5 bps per asset prevents significant deviations
- All-or-nothing enforcement

### **3. Epoch Boundaries**
- Clear start/end times for each epoch
- Unfinished creations expire automatically

### **4. Validator Consensus**
- Multiple validators must attest
- Prevents single point of failure

### **5. Price Protection**
- NAV calculated at receipt block
- Miners bear price movement risk

## 📊 **Benefits of This Design**

### **For Miners**:
- ✅ Clear requirements (exact basket specifications)
- ✅ Predictable process (2-week epochs)
- ✅ Professional arbitrage opportunities
- ✅ Volume-based emissions with minting bonus

### **For Validators**:
- ✅ Clear role (attestation and volume tracking)
- ✅ Simple scoring (volume-based with minting bonus)
- ✅ Automated emissions distribution
- ✅ No complex consensus logic

### **For Protocol**:
- ✅ Professional ETF standards
- ✅ Robust security model
- ✅ Scalable architecture
- ✅ Ecosystem alignment (auto-staking)

### **For Users**:
- ✅ Transparent index tracking
- ✅ Professional creation/redemption
- ✅ Clear fee structure
- ✅ Yield generation through staking

## 🎯 **Implementation Timeline**

### **Week 1-2**: Creation Unit System
- Creation file and epoch management
- Basket delivery and validation
- All-or-nothing enforcement

### **Week 3-4**: Validator Attestation
- NAV calculation at block
- Multi-validator consensus
- BEVM contract integration

### **Week 5-6**: Miner Integration
- Creation unit miner implementation
- End-to-end testing
- Production readiness

This design provides a robust, professional, and scalable solution that addresses all core challenges while maintaining simplicity and security.
