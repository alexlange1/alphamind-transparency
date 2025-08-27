#!/usr/bin/env python3
"""
Simple test script for Epoch Manager System
"""

import asyncio
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from subnet.creation.epoch_manager import EpochManager
from subnet.creation.creation_file import CreationFileValidator, CreationFileSerializer
from subnet.creation.weights_calculator import WeightsCalculator

async def test_epoch_manager():
    """Test the epoch manager functionality"""
    print("🧪 Testing Epoch Manager System...")
    
    # Initialize epoch manager
    epoch_manager = EpochManager()
    print(f"✅ EpochManager initialized")
    
    # Test epoch calculation
    current_epoch = epoch_manager.get_current_epoch_id()
    print(f"✅ Current epoch: {current_epoch}")
    
    # Test weights calculation
    weights = {1: 0.05, 2: 0.05, 3: 0.05, 4: 0.05, 5: 0.05,
               6: 0.05, 7: 0.05, 8: 0.05, 9: 0.05, 10: 0.05,
               11: 0.05, 12: 0.05, 13: 0.05, 14: 0.05, 15: 0.05,
               16: 0.05, 17: 0.05, 18: 0.05, 19: 0.05, 20: 0.05}
    
    print(f"✅ Weights prepared: {len(weights)} subnets")
    
    # Test creation file publishing
    creation_file = await epoch_manager.publish_creation_file(
        epoch_id=current_epoch,
        weights=weights,
        published_by="test_system"
    )
    
    print(f"✅ Creation file published for epoch {creation_file.epoch_id}")
    print(f"   - Assets: {len(creation_file.assets)}")
    print(f"   - Weights hash: {creation_file.weights_hash[:16]}...")
    print(f"   - Valid from: {creation_file.valid_from}")
    print(f"   - Valid until: {creation_file.valid_until}")
    
    # Test creation file validation
    validator = CreationFileValidator()
    errors = validator.validate_creation_file(creation_file)
    
    if errors:
        print(f"❌ Validation errors: {errors}")
        return False
    else:
        print(f"✅ Creation file validation passed")
    
    # Test serialization
    serializer = CreationFileSerializer()
    json_str = serializer.to_json(creation_file)
    print(f"✅ Serialization successful ({len(json_str)} characters)")
    
    # Test deserialization
    deserialized_file = serializer.from_json(json_str)
    print(f"✅ Deserialization successful")
    print(f"   - Epoch ID: {deserialized_file.epoch_id}")
    print(f"   - Assets: {len(deserialized_file.assets)}")
    
    # Test weights calculator
    calculator = WeightsCalculator()
    stats = calculator.get_weight_statistics(weights)
    print(f"✅ Weight statistics calculated:")
    print(f"   - Total subnets: {stats['total_subnets']}")
    print(f"   - Total weight: {stats['total_weight']:.6f}")
    print(f"   - Min weight: {stats['min_weight']:.6f}")
    print(f"   - Max weight: {stats['max_weight']:.6f}")
    print(f"   - Avg weight: {stats['avg_weight']:.6f}")
    
    print("\n🎉 All tests passed! Epoch Manager System is working correctly.")
    return True

async def test_error_handling():
    """Test error handling"""
    print("\n🧪 Testing Error Handling...")
    
    epoch_manager = EpochManager()
    
    # Test invalid weights (wrong number of subnets)
    invalid_weights = {1: 0.5, 2: 0.5}  # Only 2 subnets
    
    try:
        await epoch_manager.publish_creation_file(
            epoch_id=1,
            weights=invalid_weights,
            published_by="test_system"
        )
        print("❌ Should have raised ValueError for wrong number of subnets")
        return False
    except ValueError as e:
        print(f"✅ Correctly caught error: {e}")
    
    # Test invalid weights (wrong total)
    invalid_weights = {1: 0.5, 2: 0.5, 3: 0.5, 4: 0.5, 5: 0.5,
                      6: 0.5, 7: 0.5, 8: 0.5, 9: 0.5, 10: 0.5,
                      11: 0.5, 12: 0.5, 13: 0.5, 14: 0.5, 15: 0.5,
                      16: 0.5, 17: 0.5, 18: 0.5, 19: 0.5, 20: 0.5}  # Sum = 10.0
    
    try:
        await epoch_manager.publish_creation_file(
            epoch_id=1,
            weights=invalid_weights,
            published_by="test_system"
        )
        print("❌ Should have raised ValueError for wrong total weight")
        return False
    except ValueError as e:
        print(f"✅ Correctly caught error: {e}")
    
    print("🎉 Error handling tests passed!")
    return True

async def main():
    """Main test function"""
    print("🚀 Starting TAO20 Creation Unit System Tests\n")
    
    # Test basic functionality
    success1 = await test_epoch_manager()
    
    # Test error handling
    success2 = await test_error_handling()
    
    if success1 and success2:
        print("\n🎉 All tests passed! Ready to proceed with implementation.")
        return True
    else:
        print("\n❌ Some tests failed. Please fix issues before proceeding.")
        return False

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
