"""
Tests for Epoch Manager System

Tests the epoch management, creation file publishing, and validation functionality.
"""

import pytest
import asyncio
import time
import json
from unittest.mock import Mock, patch
from typing import Dict

from subnet.creation.epoch_manager import EpochManager, CreationFile, AssetSpecification
from subnet.creation.creation_file import CreationFileValidator, CreationFileSerializer
from subnet.creation.weights_calculator import WeightsCalculator, WeightUpdateManager

class TestEpochManager:
    """Test cases for EpochManager"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.epoch_manager = EpochManager()
        self.epoch_manager.epoch_start_time = int(time.time())  # Set fixed start time for tests
    
    def test_epoch_calculation(self):
        """Test epoch ID calculation"""
        # Test current epoch calculation
        current_epoch = self.epoch_manager.get_current_epoch_id()
        assert isinstance(current_epoch, int)
        assert current_epoch >= 1
        
        # Test epoch start time
        epoch_start = self.epoch_manager.get_epoch_start(current_epoch)
        assert isinstance(epoch_start, int)
        assert epoch_start > 0
        
        # Test epoch end time
        epoch_end = self.epoch_manager.get_epoch_end(current_epoch)
        assert isinstance(epoch_end, int)
        assert epoch_end > epoch_start
        assert epoch_end - epoch_start == 1209600  # 14 days
    
    def test_epoch_active_status(self):
        """Test epoch active status checking"""
        current_epoch = self.epoch_manager.get_current_epoch_id()
        
        # Current epoch should be active
        assert self.epoch_manager.is_epoch_active(current_epoch) == True
        
        # Future epoch should not be active
        future_epoch = current_epoch + 10
        assert self.epoch_manager.is_epoch_active(future_epoch) == False
        
        # Past epoch should not be active
        past_epoch = current_epoch - 10
        assert self.epoch_manager.is_epoch_active(past_epoch) == False
    
    def test_weights_hash_calculation(self):
        """Test weights hash calculation"""
        weights = {1: 0.05, 2: 0.05, 3: 0.05, 4: 0.05, 5: 0.05,
                   6: 0.05, 7: 0.05, 8: 0.05, 9: 0.05, 10: 0.05,
                   11: 0.05, 12: 0.05, 13: 0.05, 14: 0.05, 15: 0.05,
                   16: 0.05, 17: 0.05, 18: 0.05, 19: 0.05, 20: 0.05}
        
        hash1 = self.epoch_manager.calculate_weights_hash(weights)
        hash2 = self.epoch_manager.calculate_weights_hash(weights)
        
        # Same weights should produce same hash
        assert hash1 == hash2
        assert hash1.startswith('0x')
        assert len(hash1) == 66  # 0x + 64 hex chars
    
    def test_asset_specification_calculation(self):
        """Test asset specification calculation"""
        weights = {1: 0.05, 2: 0.05, 3: 0.05, 4: 0.05, 5: 0.05,
                   6: 0.05, 7: 0.05, 8: 0.05, 9: 0.05, 10: 0.05,
                   11: 0.05, 12: 0.05, 13: 0.05, 14: 0.05, 15: 0.05,
                   16: 0.05, 17: 0.05, 18: 0.05, 19: 0.05, 20: 0.05}
        
        assets = self.epoch_manager.calculate_asset_specifications(weights)
        
        assert len(assets) == 20
        for asset in assets:
            assert isinstance(asset, AssetSpecification)
            assert asset.netuid in weights
            assert asset.weight_bps == int(weights[asset.netuid] * 10000)
            assert asset.asset_id.startswith('0x')
    
    @pytest.mark.asyncio
    async def test_creation_file_publishing(self):
        """Test creation file publishing"""
        weights = {1: 0.05, 2: 0.05, 3: 0.05, 4: 0.05, 5: 0.05,
                   6: 0.05, 7: 0.05, 8: 0.05, 9: 0.05, 10: 0.05,
                   11: 0.05, 12: 0.05, 13: 0.05, 14: 0.05, 15: 0.05,
                   16: 0.05, 17: 0.05, 18: 0.05, 19: 0.05, 20: 0.05}
        
        epoch_id = 1
        creation_file = await self.epoch_manager.publish_creation_file(
            epoch_id=epoch_id,
            weights=weights,
            published_by="test_system"
        )
        
        assert isinstance(creation_file, CreationFile)
        assert creation_file.epoch_id == epoch_id
        assert creation_file.published_by == "test_system"
        assert len(creation_file.assets) == 20
        assert creation_file.weights_hash.startswith('0x')
    
    @pytest.mark.asyncio
    async def test_creation_file_publishing_validation(self):
        """Test creation file publishing with invalid weights"""
        # Test with wrong number of subnets
        invalid_weights = {1: 0.5, 2: 0.5}  # Only 2 subnets
        
        with pytest.raises(ValueError, match="Must have exactly 20 subnets"):
            await self.epoch_manager.publish_creation_file(
                epoch_id=1,
                weights=invalid_weights,
                published_by="test_system"
            )
        
        # Test with weights not summing to 1.0
        invalid_weights = {1: 0.5, 2: 0.5, 3: 0.5, 4: 0.5, 5: 0.5,
                          6: 0.5, 7: 0.5, 8: 0.5, 9: 0.5, 10: 0.5,
                          11: 0.5, 12: 0.5, 13: 0.5, 14: 0.5, 15: 0.5,
                          16: 0.5, 17: 0.5, 18: 0.5, 19: 0.5, 20: 0.5}  # Sum = 10.0
        
        with pytest.raises(ValueError, match="Weights must sum to 1.0"):
            await self.epoch_manager.publish_creation_file(
                epoch_id=1,
                weights=invalid_weights,
                published_by="test_system"
            )
    
    def test_creation_file_retrieval(self):
        """Test creation file retrieval"""
        # Initially no creation files
        assert self.epoch_manager.get_creation_file(1) is None
        assert self.epoch_manager.get_current_creation_file() is None
        
        # After publishing, should be retrievable
        weights = {1: 0.05, 2: 0.05, 3: 0.05, 4: 0.05, 5: 0.05,
                   6: 0.05, 7: 0.05, 8: 0.05, 9: 0.05, 10: 0.05,
                   11: 0.05, 12: 0.05, 13: 0.05, 14: 0.05, 15: 0.05,
                   16: 0.05, 17: 0.05, 18: 0.05, 19: 0.05, 20: 0.05}
        
        asyncio.run(self.epoch_manager.publish_creation_file(
            epoch_id=1,
            weights=weights,
            published_by="test_system"
        ))
        
        creation_file = self.epoch_manager.get_creation_file(1)
        assert creation_file is not None
        assert creation_file.epoch_id == 1
    
    def test_expired_epochs_cleanup(self):
        """Test expired epochs cleanup"""
        # Create some test creation files
        weights = {1: 0.05, 2: 0.05, 3: 0.05, 4: 0.05, 5: 0.05,
                   6: 0.05, 7: 0.05, 8: 0.05, 9: 0.05, 10: 0.05,
                   11: 0.05, 12: 0.05, 13: 0.05, 14: 0.05, 15: 0.05,
                   16: 0.05, 17: 0.05, 18: 0.05, 19: 0.05, 20: 0.05}
        
        # Publish creation files for different epochs
        asyncio.run(self.epoch_manager.publish_creation_file(
            epoch_id=1,
            weights=weights,
            published_by="test_system"
        ))
        
        asyncio.run(self.epoch_manager.publish_creation_file(
            epoch_id=2,
            weights=weights,
            published_by="test_system"
        ))
        
        # Initially should have 2 creation files
        assert len(self.epoch_manager.creation_files) == 2
        
        # Mock time to make epochs expired
        with patch('time.time') as mock_time:
            mock_time.return_value = int(time.time()) + 1209600 * 3  # 3 epochs later
            
            expired_epochs = self.epoch_manager.get_expired_epochs()
            assert len(expired_epochs) >= 2
            
            cleaned_count = self.epoch_manager.cleanup_expired_epochs()
            assert cleaned_count >= 2
            
            # Should have fewer creation files after cleanup
            assert len(self.epoch_manager.creation_files) < 2

class TestCreationFileValidator:
    """Test cases for CreationFileValidator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = CreationFileValidator()
        self.epoch_manager = EpochManager()
    
    def test_valid_creation_file(self):
        """Test validation of valid creation file"""
        # Create a valid creation file
        weights = {1: 0.05, 2: 0.05, 3: 0.05, 4: 0.05, 5: 0.05,
                   6: 0.05, 7: 0.05, 8: 0.05, 9: 0.05, 10: 0.05,
                   11: 0.05, 12: 0.05, 13: 0.05, 14: 0.05, 15: 0.05,
                   16: 0.05, 17: 0.05, 18: 0.05, 19: 0.05, 20: 0.05}
        
        creation_file = asyncio.run(self.epoch_manager.publish_creation_file(
            epoch_id=1,
            weights=weights,
            published_by="test_system"
        ))
        
        errors = self.validator.validate_creation_file(creation_file)
        assert len(errors) == 0
    
    def test_invalid_creation_file_missing_fields(self):
        """Test validation of creation file with missing fields"""
        # Create creation file with missing fields
        creation_file = CreationFile(
            epoch_id=1,
            weights_hash="0x1234567890abcdef",
            valid_from=1000,
            valid_until=2000,
            creation_unit_size=1000,
            cash_component_bps=50,
            tolerance_bps=5,
            min_creation_size=1000,
            assets=[],
            published_at=1500,
            published_by="test"
        )
        
        errors = self.validator.validate_creation_file(creation_file)
        assert len(errors) > 0
        assert any("Must have exactly 20 assets" in error for error in errors)
    
    def test_invalid_weights_consistency(self):
        """Test validation of weights consistency"""
        # Create creation file with invalid weights
        assets = []
        for i in range(20):
            asset = AssetSpecification(
                netuid=i+1,
                asset_id=f"0x{i+1:064x}",
                qty_per_creation_unit=1000000000,
                weight_bps=1000  # 10% each = 200% total
            )
            assets.append(asset)
        
        creation_file = CreationFile(
            epoch_id=1,
            weights_hash="0x1234567890abcdef",
            valid_from=1000,
            valid_until=2000,
            creation_unit_size=1000,
            cash_component_bps=50,
            tolerance_bps=5,
            min_creation_size=1000,
            assets=assets,
            published_at=1500,
            published_by="test"
        )
        
        errors = self.validator.validate_creation_file(creation_file)
        assert len(errors) > 0
        assert any("Total weight must be 10000 basis points" in error for error in errors)

class TestCreationFileSerializer:
    """Test cases for CreationFileSerializer"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.serializer = CreationFileSerializer()
        self.epoch_manager = EpochManager()
    
    def test_serialization_deserialization(self):
        """Test creation file serialization and deserialization"""
        # Create a valid creation file
        weights = {1: 0.05, 2: 0.05, 3: 0.05, 4: 0.05, 5: 0.05,
                   6: 0.05, 7: 0.05, 8: 0.05, 9: 0.05, 10: 0.05,
                   11: 0.05, 12: 0.05, 13: 0.05, 14: 0.05, 15: 0.05,
                   16: 0.05, 17: 0.05, 18: 0.05, 19: 0.05, 20: 0.05}
        
        original_file = asyncio.run(self.epoch_manager.publish_creation_file(
            epoch_id=1,
            weights=weights,
            published_by="test_system"
        ))
        
        # Serialize to JSON
        json_str = self.serializer.to_json(original_file)
        assert isinstance(json_str, str)
        assert "epoch_id" in json_str
        assert "assets" in json_str
        
        # Deserialize from JSON
        deserialized_file = self.serializer.from_json(json_str)
        assert isinstance(deserialized_file, CreationFile)
        assert deserialized_file.epoch_id == original_file.epoch_id
        assert len(deserialized_file.assets) == len(original_file.assets)
    
    def test_file_save_load(self, tmp_path):
        """Test saving and loading creation file to/from file"""
        # Create a valid creation file
        weights = {1: 0.05, 2: 0.05, 3: 0.05, 4: 0.05, 5: 0.05,
                   6: 0.05, 7: 0.05, 8: 0.05, 9: 0.05, 10: 0.05,
                   11: 0.05, 12: 0.05, 13: 0.05, 14: 0.05, 15: 0.05,
                   16: 0.05, 17: 0.05, 18: 0.05, 19: 0.05, 20: 0.05}
        
        original_file = asyncio.run(self.epoch_manager.publish_creation_file(
            epoch_id=1,
            weights=weights,
            published_by="test_system"
        ))
        
        # Save to file
        filepath = tmp_path / "creation_file.json"
        self.serializer.save_to_file(original_file, str(filepath))
        assert filepath.exists()
        
        # Load from file
        loaded_file = self.serializer.load_from_file(str(filepath))
        assert isinstance(loaded_file, CreationFile)
        assert loaded_file.epoch_id == original_file.epoch_id
        assert len(loaded_file.assets) == len(original_file.assets)

class TestWeightsCalculator:
    """Test cases for WeightsCalculator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.calculator = WeightsCalculator()
    
    def test_equal_weight_distribution(self):
        """Test equal weight distribution creation"""
        weights = self.calculator.create_equal_weight_distribution(20)
        
        assert len(weights) == 20
        assert abs(sum(weights.values()) - 1.0) < 0.001
        assert all(weight == 0.05 for weight in weights.values())
    
    def test_weight_validation(self):
        """Test weight validation"""
        # Valid weights
        valid_weights = {1: 0.05, 2: 0.05, 3: 0.05, 4: 0.05, 5: 0.05,
                        6: 0.05, 7: 0.05, 8: 0.05, 9: 0.05, 10: 0.05,
                        11: 0.05, 12: 0.05, 13: 0.05, 14: 0.05, 15: 0.05,
                        16: 0.05, 17: 0.05, 18: 0.05, 19: 0.05, 20: 0.05}
        
        errors = self.calculator.validate_weights(valid_weights)
        assert len(errors) == 0
        
        # Invalid weights - wrong number of subnets
        invalid_weights = {1: 0.5, 2: 0.5}
        errors = self.calculator.validate_weights(invalid_weights)
        assert len(errors) > 0
        assert any("Must have exactly 20 subnets" in error for error in errors)
        
        # Invalid weights - wrong total
        invalid_weights = {1: 0.5, 2: 0.5, 3: 0.5, 4: 0.5, 5: 0.5,
                          6: 0.5, 7: 0.5, 8: 0.5, 9: 0.5, 10: 0.5,
                          11: 0.5, 12: 0.5, 13: 0.5, 14: 0.5, 15: 0.5,
                          16: 0.5, 17: 0.5, 18: 0.5, 19: 0.5, 20: 0.5}
        errors = self.calculator.validate_weights(invalid_weights)
        assert len(errors) > 0
        assert any("Total weight must be 1.0" in error for error in errors)
    
    def test_weight_statistics(self):
        """Test weight statistics calculation"""
        weights = {1: 0.05, 2: 0.05, 3: 0.05, 4: 0.05, 5: 0.05,
                   6: 0.05, 7: 0.05, 8: 0.05, 9: 0.05, 10: 0.05,
                   11: 0.05, 12: 0.05, 13: 0.05, 14: 0.05, 15: 0.05,
                   16: 0.05, 17: 0.05, 18: 0.05, 19: 0.05, 20: 0.05}
        
        stats = self.calculator.get_weight_statistics(weights)
        
        assert stats['total_subnets'] == 20
        assert abs(stats['total_weight'] - 1.0) < 0.001
        assert stats['min_weight'] == 0.05
        assert stats['max_weight'] == 0.05
        assert abs(stats['avg_weight'] - 0.05) < 0.001
        assert stats['weight_variance'] == 0.0

if __name__ == "__main__":
    pytest.main([__file__])
