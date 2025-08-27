# Immediate Action Plan (Next 2-4 Weeks) - Creation Unit Model

## 🎯 **Week 1-2: Creation Unit System Implementation**

### **Day 1-3: Creation File & Epoch Management**

#### Task 1.1: Implement Creation File System
```python
# File: subnet/creation/epoch_manager.py
# Priority: HIGH
# Estimated time: 2 days

class EpochManager:
    def __init__(self):
        self.epoch_duration = 1209600  # 14 days
        self.current_epoch = None
        self.creation_files = {}
    
    async def publish_creation_file(self, epoch_id: int, weights: Dict[int, float]):
        """Publish creation file for new epoch"""
        
        creation_file = {
            "epoch_id": epoch_id,
            "weights_hash": self.calculate_weights_hash(weights),
            "valid_from": self.get_epoch_start(epoch_id),
            "valid_until": self.get_epoch_end(epoch_id),
            "creation_unit_size": 1000,
            "cash_component_bps": 50,
            "tolerance_bps": 5,
            "min_creation_size": 1000,
            "assets": self.calculate_asset_specifications(weights)
        }
        
        self.creation_files[epoch_id] = creation_file
        await self.publish_to_subnet(creation_file)
        
        return creation_file
    
    def calculate_asset_specifications(self, weights: Dict[int, float]) -> List[Dict]:
        """Calculate asset specifications for creation file"""
        assets = []
        
        for netuid, weight in weights.items():
            # Calculate quantity per creation unit based on weight
            qty_per_unit = self.calculate_qty_per_unit(netuid, weight)
            
            asset_spec = {
                "netuid": netuid,
                "asset_id": self.get_asset_id(netuid),
                "qty_per_creation_unit": qty_per_unit,
                "weight_bps": int(weight * 10000)
            }
            assets.append(asset_spec)
        
        return assets
```

#### Task 1.2: Implement Creation Request Management
```python
# File: subnet/creation/request_manager.py
# Priority: HIGH
# Estimated time: 1 day

class CreationRequestManager:
    def __init__(self):
        self.creation_requests = {}
        self.epoch_manager = EpochManager()
    
    async def submit_creation_request(self, miner_hotkey: str, creation_size: int) -> str:
        """Submit a creation request"""
        
        # Validate creation size
        current_epoch = self.epoch_manager.get_current_epoch()
        if creation_size < current_epoch.min_creation_size:
            raise ValueError(f"Creation size {creation_size} below minimum {current_epoch.min_creation_size}")
        
        # Generate request ID
        request_id = self.generate_request_id(miner_hotkey, creation_size)
        
        # Create request
        request = {
            "request_id": request_id,
            "epoch_id": current_epoch.epoch_id,
            "creation_size": creation_size,
            "miner_hotkey": miner_hotkey,
            "submitted_at": int(time.time()),
            "expires_at": int(time.time()) + 3600,  # 1 hour window
            "status": "pending",
            "basket_totals": None,
            "receipt_block": None,
            "nav_per_share": None,
            "shares_out": None,
            "fees": None,
            "cash_component": None
        }
        
        self.creation_requests[request_id] = request
        return request_id
    
    def get_required_basket(self, creation_size: int) -> Dict[int, int]:
        """Get required basket quantities for creation size"""
        current_epoch = self.epoch_manager.get_current_epoch()
        basket = {}
        
        for asset in current_epoch.assets:
            required_qty = asset["qty_per_creation_unit"] * creation_size
            basket[asset["netuid"]] = required_qty
        
        return basket
```

### **Day 4-7: Basket Delivery & Validation**

#### Task 1.3: Implement Substrate Vault Integration
```python
# File: subnet/vault/substrate_vault.py
# Priority: HIGH
# Estimated time: 2 days

class SubstrateVaultManager:
    def __init__(self):
        self.vault_address = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
        self.finality_depth = 10
        self.request_manager = CreationRequestManager()
    
    async def deliver_basket(self, request_id: str, basket: Dict[int, int]) -> bool:
        """Deliver basket to substrate vault"""
        
        try:
            # Validate basket against requirements
            required_basket = self.request_manager.get_required_basket(
                self.request_manager.creation_requests[request_id]["creation_size"]
            )
            
            if not self.validate_basket(required_basket, basket):
                raise ValueError("Basket validation failed")
            
            # Transfer each asset to vault
            for netuid, amount in basket.items():
                success = await self.transfer_to_vault(netuid, amount)
                if not success:
                    await self.rollback_transfers()
                    return False
            
            # Wait for finality
            await self.wait_for_finality()
            
            # Record delivery
            await self.record_basket_delivery(request_id, basket)
            
            return True
            
        except Exception as e:
            logger.error(f"Basket delivery failed: {e}")
            await self.rollback_transfers()
            return False
    
    def validate_basket(self, required: Dict[int, int], delivered: Dict[int, int]) -> bool:
        """Validate delivered basket against required basket"""
        tolerance_bps = 5  # 0.05%
        
        # Check all required assets are present
        for netuid in required:
            if netuid not in delivered:
                return False
        
        # Check no extra assets
        for netuid in delivered:
            if netuid not in required:
                return False
        
        # Check quantities within tolerance
        for netuid, required_qty in required.items():
            delivered_qty = delivered[netuid]
            tolerance = required_qty * tolerance_bps / 10000
            
            if abs(delivered_qty - required_qty) > tolerance:
                return False
        
        return True
```

#### Task 1.4: Implement Basket Validation
```python
# File: subnet/creation/basket_validator.py
# Priority: MEDIUM
# Estimated time: 1 day

class BasketValidator:
    def __init__(self):
        self.tolerance_bps = 5  # 0.05%
    
    def validate_all_or_nothing(self, required: Dict[int, int], delivered: Dict[int, int]) -> bool:
        """Validate all-or-nothing basket delivery"""
        
        # All required assets must be present
        for netuid in required:
            if netuid not in delivered:
                return False
        
        # No extra assets allowed
        for netuid in delivered:
            if netuid not in required:
                return False
        
        # Quantities within tight tolerance
        for netuid, required_qty in required.items():
            delivered_qty = delivered[netuid]
            tolerance = required_qty * self.tolerance_bps / 10000
            
            if abs(delivered_qty - required_qty) > tolerance:
                return False
        
        return True
    
    def validate_epoch_consistency(self, request_epoch_id: int, current_epoch_id: int) -> bool:
        """Validate epoch consistency"""
        return request_epoch_id == current_epoch_id
```

## 🎯 **Week 3-4: Validator Attestation System**

### **Day 1-3: Validator Attestation Implementation**

#### Task 2.1: Implement NAV Calculation at Block
```python
# File: subnet/validator/nav_calculator.py
# Priority: HIGH
# Estimated time: 2 days

class NAVCalculator:
    def __init__(self):
        self.official_pricing = OfficialPricingFunction()
    
    async def calculate_nav_at_block(self, block_number: int, basket_totals: Dict[int, int]) -> float:
        """Calculate NAV at specific block using official pricing"""
        
        total_value = 0
        total_shares = 0
        
        for netuid, amount in basket_totals.items():
            # Get price at block using official pricing function
            price = await self.official_pricing.get_price_at_block(netuid, block_number)
            value = amount * price
            total_value += value
            total_shares += amount
        
        if total_shares == 0:
            return 0
        
        return total_value / total_shares
    
    async def calculate_shares_and_fees(self, creation_size: int, nav_per_share: float) -> Tuple[int, int, int]:
        """Calculate shares, fees, and cash component"""
        
        # Calculate gross shares
        gross_shares = creation_size * 1000  # 1000 shares per creation unit
        
        # Calculate fees
        fee_bps = 10  # 0.1% fee
        fees = int(gross_shares * fee_bps / 10000)
        
        # Calculate net shares
        net_shares = gross_shares - fees
        
        # Calculate cash component for rounding
        cash_component = self.calculate_cash_component(gross_shares, nav_per_share)
        
        return net_shares, fees, cash_component
```

#### Task 2.2: Implement Validator Attestation
```python
# File: subnet/validator/attestation_manager.py
# Priority: HIGH
# Estimated time: 1 day

class AttestationManager:
    def __init__(self):
        self.required_attestations = 3
        self.attestation_window = 300  # 5 minutes
        self.nav_calculator = NAVCalculator()
    
    async def attest_creation(self, request_id: str, validator_hotkey: str):
        """Attest to a creation request"""
        
        request = self.get_creation_request(request_id)
        
        # Verify basket delivery
        if not await self.verify_basket_delivery(request):
            raise ValueError("Basket delivery verification failed")
        
        # Calculate NAV at receipt block
        nav_per_share = await self.nav_calculator.calculate_nav_at_block(
            request["receipt_block"], 
            request["basket_totals"]
        )
        
        # Calculate shares and fees
        shares_out, fees, cash_component = await self.nav_calculator.calculate_shares_and_fees(
            request["creation_size"], 
            nav_per_share
        )
        
        # Create attestation
        attestation = {
            "request_id": request_id,
            "validator_hotkey": validator_hotkey,
            "epoch_id": request["epoch_id"],
            "basket_totals": request["basket_totals"],
            "nav_per_share": nav_per_share,
            "shares_out": shares_out,
            "fees": fees,
            "cash_component": cash_component,
            "receipt_block": request["receipt_block"],
            "attested_at": int(time.time()),
            "signature": None  # Will be signed
        }
        
        # Sign attestation
        attestation["signature"] = await self.sign_attestation(attestation)
        
        # Submit to BEVM contract
        await self.submit_attestation(attestation)
        
        return attestation
```

### **Day 4-7: BEVM Contract Integration**

#### Task 2.3: Implement BEVM Contract
```solidity
// File: contracts/src/TAO20CreationUnit.sol
// Priority: HIGH
// Estimated time: 2 days

contract TAO20CreationUnit {
    struct Attestation {
        bytes32 requestId;
        bytes32 validatorHotkey;
        uint256 epochId;
        uint256[] basketTotals;
        uint256 navPerShare;
        uint256 sharesOut;
        uint256 fees;
        uint256 cashComponent;
        uint256 receiptBlock;
        uint256 attestedAt;
        bytes signature;
    }
    
    mapping(bytes32 => mapping(bytes32 => bool)) public attestations;
    mapping(bytes32 => uint256) public attestationCount;
    mapping(bytes32 => bool) public mintedRequests;
    mapping(address => bool) public validators;
    
    uint256 public requiredAttestations = 3;
    uint256 public currentEpochId;
    
    event AttestationSubmitted(bytes32 indexed requestId, bytes32 indexed validatorHotkey);
    event CreationMinted(bytes32 indexed requestId, address indexed miner, uint256 sharesOut, uint256 navPerShare);
    
    function submitAttestation(Attestation calldata attestation) external {
        require(validators[msg.sender], "Not authorized validator");
        require(!attestations[attestation.requestId][attestation.validatorHotkey], "Already attested");
        
        // Verify signature
        require(verifyAttestationSignature(attestation), "Invalid signature");
        
        // Verify epoch consistency
        require(attestation.epochId == currentEpochId, "Wrong epoch");
        
        // Record attestation
        attestations[attestation.requestId][attestation.validatorHotkey] = true;
        attestationCount[attestation.requestId]++;
        
        emit AttestationSubmitted(attestation.requestId, attestation.validatorHotkey);
        
        // Check if we have enough attestations
        if (attestationCount[attestation.requestId] >= requiredAttestations) {
            executeMint(attestation);
        }
    }
    
    function executeMint(Attestation memory attestation) internal {
        require(!mintedRequests[attestation.requestId], "Already minted");
        
        // Mint TAO20 shares
        _mint(attestation.miner, attestation.sharesOut);
        
        // Record fees
        feeManager.recordFees(attestation.fees);
        
        // Auto-stake underlying tokens
        autoStakeUnderlying(attestation.basketTotals);
        
        mintedRequests[attestation.requestId] = true;
        
        emit CreationMinted(
            attestation.requestId,
            attestation.miner,
            attestation.sharesOut,
            attestation.navPerShare
        );
    }
}
```

## 🎯 **Week 5-6: Miner Implementation & Integration**

### **Day 1-3: Creation Unit Miner**

#### Task 3.1: Implement Creation Unit Miner
```python
# File: subnet/miner/creation_miner.py
# Priority: HIGH
# Estimated time: 2 days

class TAO20CreationMiner:
    def __init__(self):
        self.min_creation_size = 1000
        self.max_creation_size = 10000
        self.creation_manager = CreationRequestManager()
        self.vault_manager = SubstrateVaultManager()
    
    async def arbitrage_loop(self):
        """Main arbitrage loop for creation units"""
        while True:
            try:
                # Check for arbitrage opportunity
                opportunity = await self.check_creation_opportunity()
                
                if opportunity and opportunity["premium"] > 0.01:  # 1% premium
                    # Calculate optimal creation size
                    creation_size = self.calculate_optimal_creation_size(opportunity)
                    
                    # Submit creation request
                    request_id = await self.creation_manager.submit_creation_request(
                        self.hotkey, creation_size
                    )
                    
                    # Prepare and deliver basket
                    basket = await self.prepare_basket(creation_size)
                    success = await self.vault_manager.deliver_basket(request_id, basket)
                    
                    if success:
                        logger.info(f"Creation request {request_id} delivered successfully")
                        # Volume will be tracked by validators for emissions
                
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Arbitrage error: {e}")
                await asyncio.sleep(60)
    
    async def prepare_basket(self, creation_size: int) -> Dict[int, int]:
        """Prepare basket for delivery"""
        required_basket = self.creation_manager.get_required_basket(creation_size)
        
        # Acquire tokens according to required basket
        acquired_basket = {}
        for netuid, required_qty in required_basket.items():
            acquired_qty = await self.acquire_subnet_token(netuid, required_qty)
            acquired_basket[netuid] = acquired_qty
        
        return acquired_basket
    
    def calculate_optimal_creation_size(self, opportunity: Dict) -> int:
        """Calculate optimal creation size based on opportunity"""
        premium = opportunity["premium"]
        available_capital = opportunity["available_capital"]
        
        # Scale creation size based on premium and capital
        base_size = self.min_creation_size
        premium_multiplier = min(premium * 100, 5)  # Max 5x multiplier
        
        optimal_size = int(base_size * premium_multiplier)
        optimal_size = min(optimal_size, self.max_creation_size)
        optimal_size = min(optimal_size, available_capital // 1000)  # Rough estimate
        
        return max(optimal_size, self.min_creation_size)
```

### **Day 4-7: Integration Testing**

#### Task 3.2: End-to-End Integration Testing
```python
# File: tests/test_creation_unit_flow.py
# Priority: HIGH
# Estimated time: 2 days

class TestCreationUnitFlow:
    def test_complete_creation_flow(self):
        """Test complete creation unit flow"""
        
        # 1. Submit creation request
        request_id = self.creation_manager.submit_creation_request(
            miner_hotkey="test_miner",
            creation_size=1000
        )
        
        # 2. Deliver basket to vault
        basket = self.prepare_test_basket(1000)
        success = self.vault_manager.deliver_basket(request_id, basket)
        assert success == True
        
        # 3. Validator attestation
        attestation = self.attestation_manager.attest_creation(
            request_id, "test_validator"
        )
        assert attestation is not None
        
        # 4. BEVM contract minting
        mint_result = self.contract.execute_mint(attestation)
        assert mint_result == True
        
        # 5. Verify volume tracking
        volume = self.volume_tracker.get_miner_volume("test_miner")
        assert volume > 0
    
    def test_basket_validation(self):
        """Test basket validation"""
        
        required = {1: 1000, 2: 800, 3: 600}
        delivered = {1: 1005, 2: 800, 3: 600}  # Within tolerance
        
        valid = self.basket_validator.validate_all_or_nothing(required, delivered)
        assert valid == True
        
        # Test invalid basket
        invalid_delivered = {1: 1000, 2: 800}  # Missing asset
        valid = self.basket_validator.validate_all_or_nothing(required, invalid_delivered)
        assert valid == False
```

## 📊 **Success Metrics**

### **Week 1-2 Success Criteria:**
- [ ] Creation file system working
- [ ] Epoch management functional
- [ ] Basket delivery to substrate vault working
- [ ] All-or-nothing validation implemented

### **Week 3-4 Success Criteria:**
- [ ] NAV calculation at block working
- [ ] Validator attestation system functional
- [ ] BEVM contract integration complete
- [ ] Multi-validator consensus working

### **Week 5-6 Success Criteria:**
- [ ] Creation unit miner working
- [ ] End-to-end flow functional
- [ ] Volume tracking for emissions working
- [ ] System ready for production

## 🎯 **Key Benefits of Creation Unit Model**

1. **Professional Standards**: ETF creation unit model is battle-tested
2. **Price Risk Management**: Miners bear price risk appropriately
3. **Clear Epoch Boundaries**: No confusion about weight changes
4. **Atomic Execution**: All-or-nothing basket delivery
5. **Validator Consensus**: Multi-validator attestation for security
6. **Auto-Staking**: Aligns with Bittensor ecosystem
7. **Scalable**: Can handle multiple miners efficiently

This creation unit approach provides a robust, production-ready solution that addresses all the core design challenges while maintaining simplicity and security.
