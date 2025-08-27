#!/usr/bin/env python3
"""
Simple test script for Basket Validator
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from subnet.creation.basket_validator import BasketValidator, BasketValidatorFactory

def test_basket_validator():
    """Test the basket validator functionality"""
    print("🧪 Testing Basket Validator...")
    
    # Initialize validator
    validator = BasketValidator(tolerance_bps=5)
    print(f"✅ BasketValidator initialized with tolerance {validator.tolerance_bps} bps")
    
    # Test valid basket
    required = {1: 1000, 2: 2000, 3: 3000}
    delivered = {1: 1000, 2: 2000, 3: 3000}
    
    result = validator.validate_all_or_nothing(required, delivered)
    assert result.is_valid == True
    assert len(result.errors) == 0
    
    print(f"✅ Valid basket validation passed")
    
    # Test basket with small tolerance deviation (should pass)
    delivered_within_tolerance = {1: 1001, 2: 1999, 3: 3001}  # Within 1 tolerance
    result = validator.validate_all_or_nothing(required, delivered_within_tolerance)
    print(f"   - Result valid: {result.is_valid}")
    print(f"   - Errors: {result.errors}")
    print(f"   - Warnings: {result.warnings}")
    assert result.is_valid == True
    assert len(result.errors) == 0
    
    print(f"✅ Basket within tolerance validation passed")
    
    # Test basket with tolerance violation (should fail)
    delivered_outside_tolerance = {1: 1010, 2: 1990, 3: 3010}  # Outside 5 bps tolerance
    result = validator.validate_all_or_nothing(required, delivered_outside_tolerance)
    assert result.is_valid == False
    assert len(result.errors) > 0
    
    print(f"✅ Basket outside tolerance validation correctly failed")
    
    # Test missing assets
    delivered_missing = {1: 1000, 2: 2000}  # Missing subnet 3
    result = validator.validate_all_or_nothing(required, delivered_missing)
    assert result.is_valid == False
    assert len(result.missing_assets) == 1
    assert 3 in result.missing_assets
    
    print(f"✅ Missing assets validation correctly failed")
    
    # Test extra assets
    delivered_extra = {1: 1000, 2: 2000, 3: 3000, 4: 4000}  # Extra subnet 4
    result = validator.validate_all_or_nothing(required, delivered_extra)
    assert result.is_valid == False
    assert len(result.extra_assets) == 1
    assert 4 in result.extra_assets
    
    print(f"✅ Extra assets validation correctly failed")
    
    # Test quick validation methods
    assert validator.validate_basket_completeness(required, delivered) == True
    assert validator.validate_basket_accuracy(required, delivered) == True
    assert validator.validate_basket_completeness(required, delivered_missing) == False
    assert validator.validate_basket_accuracy(required, delivered_outside_tolerance) == False
    
    print(f"✅ Quick validation methods working correctly")
    
    # Test deviation calculation
    deviations = validator.calculate_basket_deviation(required, delivered_within_tolerance)
    assert 1 in deviations
    assert 2 in deviations
    assert 3 in deviations
    assert deviations[1] == 0.001  # 0.1% deviation
    
    print(f"✅ Deviation calculation working correctly")
    
    # Test tolerance calculation
    tolerance = validator.get_tolerance_for_asset(1000)
    assert tolerance == 1  # max(1, 1000 * 0.0005) = max(1, 0) = 1
    tolerance = validator.get_tolerance_for_asset(10000)
    assert tolerance == 5  # max(1, 10000 * 0.0005) = max(1, 5) = 5
    
    print(f"✅ Tolerance calculation working correctly")
    
    # Test correction suggestions
    corrections = validator.suggest_basket_corrections(required, delivered_missing)
    print(f"   - Corrections: {corrections}")
    assert 3 in corrections  # Only missing asset should be in corrections
    assert corrections[3] == 3000  # Full required quantity needed
    
    print(f"✅ Correction suggestions working correctly")
    
    # Test validation summary
    summary = validator.get_validation_summary(result)
    assert 'is_valid' in summary
    assert 'total_errors' in summary
    assert 'missing_assets_count' in summary
    assert 'extra_assets_count' in summary
    
    print(f"✅ Validation summary working correctly")
    
    print("\n🎉 All basket validator tests passed!")
    return True

def test_validator_factory():
    """Test the validator factory"""
    print("\n🧪 Testing Basket Validator Factory...")
    
    # Test strict validator
    strict_validator = BasketValidatorFactory.create_strict_validator()
    assert strict_validator.tolerance_bps == 1
    print(f"✅ Strict validator created with tolerance {strict_validator.tolerance_bps} bps")
    
    # Test standard validator
    standard_validator = BasketValidatorFactory.create_standard_validator()
    assert standard_validator.tolerance_bps == 5
    print(f"✅ Standard validator created with tolerance {standard_validator.tolerance_bps} bps")
    
    # Test relaxed validator
    relaxed_validator = BasketValidatorFactory.create_relaxed_validator()
    assert relaxed_validator.tolerance_bps == 10
    print(f"✅ Relaxed validator created with tolerance {relaxed_validator.tolerance_bps} bps")
    
    # Test custom validator
    custom_validator = BasketValidatorFactory.create_custom_validator(15)
    assert custom_validator.tolerance_bps == 15
    print(f"✅ Custom validator created with tolerance {custom_validator.tolerance_bps} bps")
    
    print("🎉 All validator factory tests passed!")
    return True

def test_edge_cases():
    """Test edge cases"""
    print("\n🧪 Testing Edge Cases...")
    
    validator = BasketValidator(tolerance_bps=5)
    
    # Test empty baskets
    result = validator.validate_all_or_nothing({}, {})
    assert result.is_valid == True
    print(f"✅ Empty basket validation passed")
    
    # Test zero quantities
    required = {1: 0, 2: 0}
    delivered = {1: 0, 2: 0}
    result = validator.validate_all_or_nothing(required, delivered)
    assert result.is_valid == True
    print(f"✅ Zero quantities validation passed")
    
    # Test very small quantities
    required = {1: 1, 2: 2}
    delivered = {1: 1, 2: 2}
    result = validator.validate_all_or_nothing(required, delivered)
    assert result.is_valid == True
    print(f"✅ Small quantities validation passed")
    
    # Test very large quantities
    required = {1: 1000000000, 2: 2000000000}
    delivered = {1: 1000000000, 2: 2000000000}
    result = validator.validate_all_or_nothing(required, delivered)
    assert result.is_valid == True
    print(f"✅ Large quantities validation passed")
    
    print("🎉 All edge case tests passed!")
    return True

def main():
    """Main test function"""
    print("🚀 Starting Basket Validator Tests\n")
    
    # Test basic functionality
    success1 = test_basket_validator()
    
    # Test validator factory
    success2 = test_validator_factory()
    
    # Test edge cases
    success3 = test_edge_cases()
    
    if success1 and success2 and success3:
        print("\n🎉 All tests passed! Basket Validator is working correctly.")
        return True
    else:
        print("\n❌ Some tests failed. Please fix issues before proceeding.")
        return False

if __name__ == "__main__":
    result = main()
    sys.exit(0 if result else 1)
