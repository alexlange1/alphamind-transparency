#!/usr/bin/env python3
"""
Integration tests for TAO20 miner and validator
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
from dataclasses import dataclass

# Import the modules to test
from neurons.miner.miner import TAO20Miner, BasketSpecification, DeliveryResult, StakeStrategy, OTCStrategy
from neurons.validator.validator import TAO20Validator, CreationReceipt, TransferRecord, AttestationResult


@pytest.fixture
def mock_miner():
    """Create a mock TAO20 miner for testing"""
    with patch('subnet.miner.tao20_miner.bt.subtensor'), \
         patch('subnet.miner.tao20_miner.bt.wallet') as mock_wallet:
        
        # Mock the wallet
        mock_wallet_instance = Mock()
        mock_wallet_instance.hotkey.ss58_address = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
        mock_wallet.return_value = mock_wallet_instance
        
        # Create miner instance
        miner = TAO20Miner(
            wallet_path="test_wallet",
            source_ss58="5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",  # Renamed from vault_ss58
            miner_id="test_miner",
            tao20_api_url="http://localhost:8000",
            creation_file_dir="./test_creation_files",
            evm_addr="0x742d35Cc6634C0532925a3b8D4C9db96C4b4d8b6"  # Added EVM address
        )
        
        # Mock the EpochManager after it's created
        mock_epoch_manager_instance = Mock()
        
        # Mock creation file data
        mock_creation_file = Mock()
        mock_creation_file.epoch_id = 1
        mock_creation_file.creation_unit_size = 1000  # integer
        mock_creation_file.tolerance_bps = 50
        mock_creation_file.valid_from = 1000
        mock_creation_file.valid_until = 2000
        mock_creation_file.weights_hash = "abc123"
        
        # Mock assets
        mock_asset1 = Mock()
        mock_asset1.netuid = 1
        mock_asset1.qty_per_creation_unit = 100  # integer
        
        mock_asset2 = Mock()
        mock_asset2.netuid = 2
        mock_asset2.qty_per_creation_unit = 200  # integer
        
        mock_creation_file.assets = [mock_asset1, mock_asset2]
        
        # Configure mock methods
        mock_epoch_manager_instance.get_current_epoch_id.return_value = 1
        mock_epoch_manager_instance.get_creation_file.return_value = mock_creation_file
        mock_epoch_manager_instance.is_epoch_active.return_value = True
        
        # Assign the mock epoch manager
        miner.epoch_manager = mock_epoch_manager_instance
        
        return miner


@pytest.fixture
def mock_validator():
    """Create a mock TAO20 validator for testing"""
    with patch('subnet.validator.tao20_validator.bt.subtensor'), \
         patch('subnet.validator.tao20_validator.bt.wallet') as mock_wallet:
        
        # Mock the wallet
        mock_wallet_instance = Mock()
        mock_wallet_instance.hotkey.ss58_address = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
        mock_wallet.return_value = mock_wallet_instance
        
        validator = TAO20Validator(
            wallet_path="test_wallet",
            source_ss58="5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",  # Updated parameter name
            validator_id="test_validator",
            tao20_api_url="http://localhost:8000"
        )
        
        # Mock the EpochManager
        mock_epoch_manager = Mock()
        mock_creation_file = Mock()
        mock_creation_file.epoch_id = 1
        mock_creation_file.creation_unit_size = 1000
        mock_creation_file.assets = {1: 100, 2: 200}  # netuid -> qty
        mock_creation_file.tolerance_bps = 50
        mock_creation_file.valid_from = 1000
        mock_creation_file.valid_until = 2000
        mock_creation_file.weights_hash = "abc123"
        
        mock_epoch_manager.get_creation_file.return_value = mock_creation_file
        validator.epoch_manager = mock_epoch_manager
        
        # Mock the BasketValidator
        mock_basket_validator = Mock()
        mock_validation_result = Mock()
        mock_validation_result.is_valid = True
        mock_validation_result.error_message = None
        mock_basket_validator.validate_all_or_nothing.return_value = mock_validation_result
        validator.basket_validator = mock_basket_validator
        
        # Mock the NAVCalculator
        mock_nav_calculator = Mock()
        mock_nav_calculation = Mock()
        mock_nav_calculation.status.value = "completed"
        mock_nav_calculation.nav_per_share = 1000000000000000000  # 1 TAO in wei
        mock_nav_calculator.calculate_nav_at_block.return_value = mock_nav_calculation
        validator.nav_calculator = mock_nav_calculator
        
        return validator


class TestTAO20Miner:
    """Test TAO20 miner functionality"""
    
    @pytest.mark.asyncio
    async def test_get_current_basket_specification(self, mock_miner):
        """Test getting current basket specification"""
        basket_spec = await mock_miner.get_current_basket_specification(unit_count=2)
        
        assert basket_spec is not None
        assert basket_spec.epoch_id == 1
        assert basket_spec.creation_unit_size == 1000  # integer
        assert basket_spec.assets == {1: 200, 2: 400}  # integer quantities: 100*2, 200*2
        assert basket_spec.tolerance_bps == 50
        assert basket_spec.weights_hash == "abc123"
    
    @pytest.mark.asyncio
    async def test_check_creation_opportunity(self, mock_miner):
        """Test checking creation opportunity"""
        # Mock asset availability
        with patch.object(mock_miner, '_check_asset_availability', return_value=True):
            opportunity = await mock_miner.check_creation_opportunity(unit_count=1)
            
            assert opportunity is not None
            assert opportunity["type"] == "creation"
            assert opportunity["unit_count"] == 1
            assert opportunity["creation_unit_size"] == 1000  # integer
    
    @pytest.mark.asyncio
    async def test_check_creation_opportunity_no_assets(self, mock_miner):
        """Test creation opportunity when assets unavailable"""
        # Mock asset availability as False
        with patch.object(mock_miner, '_check_asset_availability', return_value=False):
            opportunity = await mock_miner.check_creation_opportunity(unit_count=1)
            
            assert opportunity is None
    
    @pytest.mark.asyncio
    async def test_assemble_basket(self, mock_miner):
        """Test basket assembly"""
        basket_spec = BasketSpecification(
            epoch_id=1,
            creation_unit_size=1000,  # integer
            assets={1: 100, 2: 200},  # integer quantities
            tolerance_bps=50,
            valid_from=1000,
            valid_until=2000,
            weights_hash="abc123"
        )
        
        # Mock balance checking and acquisition
        with patch.object(mock_miner, '_get_subnet_balance', return_value=500), \
             patch.object(mock_miner.acquisition_strategy, 'acquire', return_value=True):
            
            assembled_assets = await mock_miner._assemble_basket(basket_spec)
            
            assert assembled_assets is not None
            assert assembled_assets == {1: 100, 2: 200}  # Exact required amounts (integers)
    
    @pytest.mark.asyncio
    async def test_assemble_basket_insufficient_balance(self, mock_miner):
        """Test basket assembly with insufficient balance"""
        basket_spec = BasketSpecification(
            epoch_id=1,
            creation_unit_size=1000,  # integer
            assets={1: 100, 2: 200},  # integer quantities
            tolerance_bps=50,
            valid_from=1000,
            valid_until=2000,
            weights_hash="abc123"
        )
        
        # Mock insufficient balance and failed acquisition
        with patch.object(mock_miner, '_get_subnet_balance', return_value=50), \
             patch.object(mock_miner.acquisition_strategy, 'acquire', return_value=False):
            
            assembled_assets = await mock_miner._assemble_basket(basket_spec)
            
            assert assembled_assets is None
    
    @pytest.mark.asyncio
    async def test_validate_basket_delivery(self, mock_miner):
        """Test basket validation"""
        basket_spec = BasketSpecification(
            epoch_id=1,
            creation_unit_size=1000,  # integer
            assets={1: 100, 2: 200},  # integer quantities
            tolerance_bps=50,
            valid_from=1000,
            valid_until=2000,
            weights_hash="abc123"
        )
        
        assets = {1: 100, 2: 200}  # Exact match (integers)
        
        # Mock basket validator
        with patch('subnet.creation.basket_validator.BasketValidator') as mock_validator_class:
            mock_validator = Mock()
            mock_validator.validate_all_or_nothing.return_value = Mock(is_valid=True, errors=[])
            mock_validator_class.return_value = mock_validator
            
            result = await mock_miner._validate_basket_delivery(assets, basket_spec)
            
            assert result.is_valid is True
            mock_validator.validate_all_or_nothing.assert_called_once_with(
                basket_spec.assets, assets
            )
    
    @pytest.mark.asyncio
    async def test_deliver_to_vault_success(self, mock_miner):
        """Test successful vault delivery"""
        basket_spec = BasketSpecification(
            epoch_id=1,
            creation_unit_size=1000,  # integer
            assets={1: 100, 2: 200},  # integer quantities
            tolerance_bps=50,
            valid_from=1000,
            valid_until=2000,
            weights_hash="abc123"
        )
        
        assets = {1: 100, 2: 200}  # integer quantities
        
        # Mock all the delivery steps with future deadline
        future_deadline = int(time.time()) + 3600  # 1 hour from now
        
        with patch.object(mock_miner, '_load_vault_config', return_value={1: "vault1", 2: "vault2"}), \
             patch.object(mock_miner, '_send_transfer_to_vault', return_value={"tx_hash": "tx_hash", "block_hash": "block_hash", "extrinsic_index": 0}), \
             patch.object(mock_miner, '_register_creation', return_value={"creation_id": "creation123", "deadline_ts": future_deadline}), \
             patch.object(mock_miner, '_update_creation_transfers', return_value=True), \
             patch.object(mock_miner, '_wait_for_receipt_validation', return_value="receipt_valid"), \
             patch.object(mock_miner, '_validate_basket_delivery', return_value=Mock(is_valid=True, errors=[])), \
             patch.object(mock_miner, '_new_attempt_id', return_value="attempt123"), \
             patch.object(mock_miner, '_wait_for_finality', return_value=True):
            
            result = await mock_miner._deliver_to_vault(assets, basket_spec, 1)
            
            assert result.success is True
            assert result.creation_id == "creation123"
            assert result.delivered_assets == assets
        assert result.transaction_hashes == ["tx_hash", "tx_hash"]
        assert result.deadline_ts == future_deadline
        assert result.attempt_id == "attempt123"
    
    @pytest.mark.asyncio
    async def test_deliver_to_vault_insufficient_time(self, mock_miner):
        """Test vault delivery with insufficient time before deadline"""
        basket_spec = BasketSpecification(
            epoch_id=1,
            creation_unit_size=1000,  # integer
            assets={1: 100, 2: 200},  # integer quantities
            tolerance_bps=50,
            valid_from=1000,
            valid_until=2000,
            weights_hash="abc123"
        )
        
        assets = {1: 100, 2: 200}  # integer quantities
        
        # Mock registration with very short deadline
        with patch.object(mock_miner, '_load_vault_config', return_value={1: "vault1", 2: "vault2"}), \
             patch.object(mock_miner, '_send_transfer_to_vault', return_value="tx_hash"), \
             patch.object(mock_miner, '_register_creation', return_value={"creation_id": "creation123", "deadline_ts": int(time.time()) + 10}), \
             patch.object(mock_miner, '_validate_basket_delivery', return_value=Mock(is_valid=True, errors=[])):
            
            result = await mock_miner._deliver_to_vault(assets, basket_spec, 1)
            
            assert result.success is False
            assert "Insufficient time before deadline" in result.error_message
    
    @pytest.mark.asyncio
    async def test_deliver_to_vault_expired(self, mock_miner):
        """Test vault delivery that expires"""
        basket_spec = BasketSpecification(
            epoch_id=1,
            creation_unit_size=1000,  # integer
            assets={1: 100, 2: 200},  # integer quantities
            tolerance_bps=50,
            valid_from=1000,
            valid_until=2000,
            weights_hash="abc123"
        )
        
        assets = {1: 100, 2: 200}  # integer quantities
        
        # Mock expired status with future deadline (so deadline check passes)
        future_deadline = int(time.time()) + 3600  # 1 hour from now
        
        with patch.object(mock_miner, '_load_vault_config', return_value={1: "vault1", 2: "vault2"}), \
             patch.object(mock_miner, '_send_transfer_to_vault', return_value={"tx_hash": "tx_hash", "block_hash": "block_hash", "extrinsic_index": 0}), \
             patch.object(mock_miner, '_register_creation', return_value={"creation_id": "creation123", "deadline_ts": future_deadline}), \
             patch.object(mock_miner, '_update_creation_transfers', return_value=True), \
             patch.object(mock_miner, '_wait_for_receipt_validation', return_value="expired"), \
             patch.object(mock_miner, '_validate_basket_delivery', return_value=Mock(is_valid=True, errors=[])), \
             patch.object(mock_miner, '_new_attempt_id', return_value="attempt123"):
            
            result = await mock_miner._deliver_to_vault(assets, basket_spec, 1)
            
            assert result.success is False
            assert result.error_message == "Creation expired"
            assert result.deadline_ts == future_deadline
    
    @pytest.mark.asyncio
    async def test_get_metrics(self, mock_miner):
        """Test metrics retrieval"""
        # Set some metrics
        mock_miner.metrics['creations_attempted'] = 5
        mock_miner.metrics['creations_receipt_valid'] = 3
        mock_miner.metrics['creations_expired'] = 1
        mock_miner.metrics['creations_failed'] = 1
        
        metrics = mock_miner.get_metrics()
        
        assert metrics['creations_attempted'] == 5
        assert metrics['creations_receipt_valid'] == 3
        assert metrics['creations_expired'] == 1
        assert metrics['creations_failed'] == 1


class TestAcquisitionStrategies:
    """Test acquisition strategies"""
    
    @pytest.mark.asyncio
    async def test_stake_strategy(self):
        """Test staking strategy"""
        strategy = StakeStrategy("5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY")
        
        # Test can_acquire
        can_acquire = await strategy.can_acquire(1, 100)  # integer amount
        assert can_acquire is True
        
        # Test acquire
        acquired = await strategy.acquire(1, 100)  # integer amount
        assert acquired is True
    
    @pytest.mark.asyncio
    async def test_otc_strategy(self):
        """Test OTC strategy"""
        strategy = OTCStrategy("5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty")
        
        # Test can_acquire
        can_acquire = await strategy.can_acquire(1, 100)  # integer amount
        assert can_acquire is True
        
        # Test acquire
        acquired = await strategy.acquire(1, 100)  # integer amount
        assert acquired is True


class TestTAO20Validator:
    """Test TAO20 validator functionality"""
    
    @pytest.mark.asyncio
    async def test_validate_basket_success(self, mock_validator):
        """Test successful basket validation"""
        # Create a valid creation receipt with 20 transfers (simplified for testing)
        transfers = []
        for i in range(1, 21):  # 20 transfers
            transfers.append(TransferRecord(
                netuid=i, 
                amount=100 * i, 
                vault_ss58=f"vault{i}", 
                tx_hash=f"tx{i}", 
                block_hash=f"block{i}", 
                extrinsic_index=i-1
            ))
        
        creation = CreationReceipt(
            creation_id="creation123",
            source_ss58="5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
            epoch_id=1,
            weights_hash="abc123",
            unit_count=1,
            transfers=transfers,
            deadline_ts=int(time.time()) + 3600,
            registered_at=int(time.time())
        )
        
        # Mock successful validation
        with patch.object(mock_validator, '_get_basket_specification') as mock_get_spec:
            mock_spec = Mock()
            mock_spec.epoch_id = 1
            mock_spec.weights_hash = "abc123"
            # Create assets dict for all 20 subnets
            mock_spec.assets = {i: 100 * i for i in range(1, 21)}
            mock_get_spec.return_value = mock_spec
            
            result = await mock_validator._validate_basket(creation)
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_basket_wrong_transfer_count(self, mock_validator):
        """Test basket validation with wrong number of transfers"""
        # Create creation with only 1 transfer (should be 20)
        transfers = [
            TransferRecord(netuid=1, amount=100, vault_ss58="vault1", tx_hash="tx1", block_hash="block1", extrinsic_index=0)
        ]
        
        creation = CreationReceipt(
            creation_id="creation123",
            source_ss58="5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
            epoch_id=1,
            weights_hash="abc123",
            unit_count=1,
            transfers=transfers,
            deadline_ts=int(time.time()) + 3600,
            registered_at=int(time.time())
        )
        
        result = await mock_validator._validate_basket(creation)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_basket_expired(self, mock_validator):
        """Test basket validation with expired creation"""
        transfers = [
            TransferRecord(netuid=1, amount=100, vault_ss58="vault1", tx_hash="tx1", block_hash="block1", extrinsic_index=0),
            TransferRecord(netuid=2, amount=200, vault_ss58="vault2", tx_hash="tx2", block_hash="block2", extrinsic_index=1)
        ]
        
        creation = CreationReceipt(
            creation_id="creation123",
            source_ss58="5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
            epoch_id=1,
            weights_hash="abc123",
            unit_count=1,
            transfers=transfers,
            deadline_ts=int(time.time()) - 3600,  # Expired
            registered_at=int(time.time()) - 7200
        )
        
        result = await mock_validator._validate_basket(creation)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_calculate_nav_at_receipt(self, mock_validator):
        """Test NAV calculation at receipt time"""
        transfers = [
            TransferRecord(netuid=1, amount=100, vault_ss58="vault1", tx_hash="tx1", block_hash="block1", extrinsic_index=0),
            TransferRecord(netuid=2, amount=200, vault_ss58="vault2", tx_hash="tx2", block_hash="block2", extrinsic_index=1)
        ]
        
        creation = CreationReceipt(
            creation_id="creation123",
            source_ss58="5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
            epoch_id=1,
            weights_hash="abc123",
            unit_count=1,
            transfers=transfers,
            deadline_ts=int(time.time()) + 3600,
            registered_at=int(time.time())
        )
        
        # Mock successful NAV calculation
        with patch.object(mock_validator.nav_calculator, 'calculate_nav_at_block', new_callable=AsyncMock) as mock_calc:
            mock_result = Mock()
            mock_result.status.value = "completed"
            mock_result.nav_per_share = 1000000000000000000  # 1 TAO in wei
            mock_calc.return_value = mock_result
            
            # Mock the epoch_manager.get_creation_file call
            with patch.object(mock_validator.epoch_manager, 'get_creation_file') as mock_get_file:
                mock_creation_file = Mock()
                mock_creation_file.assets = {1: 100, 2: 200}
                mock_get_file.return_value = mock_creation_file
                
                nav = await mock_validator._calculate_nav_at_receipt(creation)
                
                assert nav == 1000000000000000000
    
    @pytest.mark.asyncio
    async def test_provide_attestation_success(self, mock_validator):
        """Test successful attestation provision"""
        transfers = [
            TransferRecord(netuid=1, amount=100, vault_ss58="vault1", tx_hash="tx1", block_hash="block1", extrinsic_index=0),
            TransferRecord(netuid=2, amount=200, vault_ss58="vault2", tx_hash="tx2", block_hash="block2", extrinsic_index=1)
        ]
        
        creation = CreationReceipt(
            creation_id="creation123",
            source_ss58="5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
            epoch_id=1,
            weights_hash="abc123",
            unit_count=1,
            transfers=transfers,
            deadline_ts=int(time.time()) + 3600,
            registered_at=int(time.time())
        )
        
        nav = 1000000000000000000  # 1 TAO in wei
        
        # Mock successful attestation
        with patch.object(mock_validator, '_sign_attestation', return_value="signature123"), \
             patch.object(mock_validator, '_submit_attestation', return_value=True):
            
            result = await mock_validator._provide_attestation(creation, nav)
            
            assert result.success is True
            assert result.creation_id == "creation123"
            assert result.nav_at_receipt == nav
            assert result.attestation_signature == "signature123"
    
    @pytest.mark.asyncio
    async def test_provide_attestation_interval_not_met(self, mock_validator):
        """Test attestation with interval not met"""
        transfers = [
            TransferRecord(netuid=1, amount=100, vault_ss58="vault1", tx_hash="tx1", block_hash="block1", extrinsic_index=0),
            TransferRecord(netuid=2, amount=200, vault_ss58="vault2", tx_hash="tx2", block_hash="block2", extrinsic_index=1)
        ]
        
        creation = CreationReceipt(
            creation_id="creation123",
            source_ss58="5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
            epoch_id=1,
            weights_hash="abc123",
            unit_count=1,
            transfers=transfers,
            deadline_ts=int(time.time()) + 3600,
            registered_at=int(time.time())
        )
        
        nav = 1000000000000000000  # 1 TAO in wei
        
        # Set last attestation time to recent
        mock_validator.last_attestation_time = time.time() - 30  # 30 seconds ago
        
        result = await mock_validator._provide_attestation(creation, nav)
        
        assert result.success is False
        assert "Attestation interval not met" in result.error_message
    
    def test_get_metrics(self, mock_validator):
        """Test metrics retrieval"""
        # Set some metrics
        mock_validator.metrics['creations_monitored'] = 10
        mock_validator.metrics['creations_attested'] = 8
        mock_validator.metrics['creations_rejected'] = 2
        mock_validator.metrics['avg_processing_time_seconds'] = [1.5, 2.0, 1.8]
        
        metrics = mock_validator.get_metrics()
        
        assert metrics['creations_monitored'] == 10
        assert metrics['creations_attested'] == 8
        assert metrics['creations_rejected'] == 2
        assert abs(metrics['avg_processing_time'] - 1.77) < 0.01  # Allow small floating point differences


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
