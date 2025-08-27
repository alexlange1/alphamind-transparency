#!/usr/bin/env python3
"""
Simple test script for Creation Request Manager
"""

import asyncio
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from subnet.creation.epoch_manager import EpochManager
from subnet.creation.request_manager import CreationRequestManager, RequestStatus

async def test_request_manager():
    """Test the request manager functionality"""
    print("🧪 Testing Creation Request Manager...")
    
    # Initialize managers
    epoch_manager = EpochManager()
    request_manager = CreationRequestManager(epoch_manager=epoch_manager)
    
    print(f"✅ Managers initialized")
    
    # Create a creation file first
    weights = {1: 0.05, 2: 0.05, 3: 0.05, 4: 0.05, 5: 0.05,
               6: 0.05, 7: 0.05, 8: 0.05, 9: 0.05, 10: 0.05,
               11: 0.05, 12: 0.05, 13: 0.05, 14: 0.05, 15: 0.05,
               16: 0.05, 17: 0.05, 18: 0.05, 19: 0.05, 20: 0.05}
    
    current_epoch = epoch_manager.get_current_epoch_id()
    creation_file = await epoch_manager.publish_creation_file(
        epoch_id=current_epoch,
        weights=weights,
        published_by="test_system"
    )
    
    print(f"✅ Creation file published for epoch {current_epoch}")
    
    # Test request submission
    miner_hotkey = "test_miner_123"
    creation_size = 1000
    
    request_id = await request_manager.submit_creation_request(
        miner_hotkey=miner_hotkey,
        creation_size=creation_size
    )
    
    print(f"✅ Creation request submitted: {request_id}")
    
    # Test request retrieval
    request = request_manager.get_creation_request(request_id)
    assert request is not None
    assert request.request_id == request_id
    assert request.miner_hotkey == miner_hotkey
    assert request.creation_size == creation_size
    assert request.status == RequestStatus.PENDING
    
    print(f"✅ Request retrieval successful")
    print(f"   - Status: {request.status.value}")
    print(f"   - Epoch: {request.epoch_id}")
    print(f"   - Expires at: {request.expires_at}")
    
    # Test basket calculation
    required_basket = request_manager.get_required_basket_for_request(request_id)
    assert len(required_basket) == 20
    
    print(f"✅ Basket calculation successful")
    print(f"   - Required assets: {len(required_basket)}")
    print(f"   - Sample quantities: {list(required_basket.items())[:3]}")
    
    # Test status updates
    basket_totals = {netuid: qty for netuid, qty in required_basket.items()}
    receipt_block = 12345
    
    success = request_manager.mark_request_delivered(
        request_id, basket_totals, receipt_block
    )
    assert success == True
    
    request = request_manager.get_creation_request(request_id)
    assert request.status == RequestStatus.DELIVERED
    assert request.basket_totals == basket_totals
    assert request.receipt_block == receipt_block
    
    print(f"✅ Status update to DELIVERED successful")
    
    # Test attestation
    nav_per_share = 1.0
    shares_out = 1000000
    fees = 1000
    cash_component = 50
    
    success = request_manager.mark_request_attested(
        request_id, nav_per_share, shares_out, fees, cash_component
    )
    assert success == True
    
    request = request_manager.get_creation_request(request_id)
    assert request.status == RequestStatus.ATTESTED
    assert request.nav_per_share == nav_per_share
    assert request.shares_out == shares_out
    assert request.fees == fees
    assert request.cash_component == cash_component
    
    print(f"✅ Status update to ATTESTED successful")
    
    # Test minting
    success = request_manager.mark_request_minted(request_id)
    assert success == True
    
    request = request_manager.get_creation_request(request_id)
    assert request.status == RequestStatus.MINTED
    
    print(f"✅ Status update to MINTED successful")
    
    # Test statistics
    stats = request_manager.get_request_statistics()
    assert stats['total_requests'] == 1
    assert stats['minted_requests'] == 1
    assert stats['success_rate'] == 1.0
    
    print(f"✅ Statistics calculation successful")
    print(f"   - Total requests: {stats['total_requests']}")
    print(f"   - Success rate: {stats['success_rate']:.2%}")
    
    # Test miner requests
    miner_requests = request_manager.get_miner_requests(miner_hotkey)
    assert len(miner_requests) == 1
    assert miner_requests[0].request_id == request_id
    
    print(f"✅ Miner request retrieval successful")
    
    print("\n🎉 All request manager tests passed!")
    return True

async def test_error_handling():
    """Test error handling"""
    print("\n🧪 Testing Error Handling...")
    
    epoch_manager = EpochManager()
    request_manager = CreationRequestManager(epoch_manager=epoch_manager)
    
    # Test invalid creation size
    try:
        await request_manager.submit_creation_request(
            miner_hotkey="test_miner",
            creation_size=500  # Below minimum
        )
        print("❌ Should have raised ValueError for small creation size")
        return False
    except ValueError as e:
        print(f"✅ Correctly caught error: {e}")
    
    # Test invalid creation size (too large)
    try:
        await request_manager.submit_creation_request(
            miner_hotkey="test_miner",
            creation_size=20000  # Above maximum
        )
        print("❌ Should have raised ValueError for large creation size")
        return False
    except ValueError as e:
        print(f"✅ Correctly caught error: {e}")
    
    # Test invalid miner hotkey
    try:
        await request_manager.submit_creation_request(
            miner_hotkey="",  # Empty hotkey
            creation_size=1000
        )
        print("❌ Should have raised ValueError for empty hotkey")
        return False
    except ValueError as e:
        print(f"✅ Correctly caught error: {e}")
    
    print("🎉 Error handling tests passed!")
    return True

async def main():
    """Main test function"""
    print("🚀 Starting Creation Request Manager Tests\n")
    
    # Test basic functionality
    success1 = await test_request_manager()
    
    # Test error handling
    success2 = await test_error_handling()
    
    if success1 and success2:
        print("\n🎉 All tests passed! Request Manager is working correctly.")
        return True
    else:
        print("\n❌ Some tests failed. Please fix issues before proceeding.")
        return False

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
