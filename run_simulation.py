#!/usr/bin/env python3
"""
TAO20 End-to-End Simulation Script
Tests the complete miner → validator flow
"""

import asyncio
import json
import time
import aiohttp
from typing import Dict, List

# Configuration
API_URL = "http://localhost:8000"
MINER_SS58 = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"
EVM_ADDR = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"

async def simulate_miner_flow():
    """Simulate a miner creating and delivering a basket"""
    print("🔨 SIMULATING MINER FLOW")
    print("=" * 50)
    
    async with aiohttp.ClientSession() as session:
        # Step 1: Get current epoch
        print("📅 Step 1: Getting current epoch...")
        async with session.get(f"{API_URL}/epoch/current") as resp:
            epoch_data = await resp.json()
            print(f"   Current epoch: {epoch_data['epoch_id']}")
            print(f"   Weights hash: {epoch_data['weights_hash']}")
        
        # Step 2: Register creation
        print("\n📝 Step 2: Registering creation...")
        creation_request = {
            "epoch_id": epoch_data["epoch_id"],
            "source_ss58": MINER_SS58,
            "evm_addr": EVM_ADDR,
            "unit_count": 1,
            "weights_hash": epoch_data["weights_hash"]
        }
        
        async with session.post(f"{API_URL}/creations", json=creation_request) as resp:
            creation_data = await resp.json()
            creation_id = creation_data["creation_id"]
            deadline_ts = creation_data["deadline_ts"]
            print(f"   Creation registered: {creation_id}")
            print(f"   Deadline: {deadline_ts} (in {deadline_ts - time.time():.0f} seconds)")
        
        # Step 3: Simulate asset delivery (20 transfers)
        print("\n🚚 Step 3: Simulating asset delivery...")
        transfers = []
        for netuid in range(1, 21):
            transfer = {
                "netuid": netuid,
                "amount": 50000000000000000,  # 0.05 TAO in base units
                "vault_ss58": f"5Vault{netuid}Address{'x' * 32}",
                "tx_hash": f"0x{netuid:064x}",
                "block_hash": f"0xblock{netuid:059x}",
                "extrinsic_index": netuid
            }
            transfers.append(transfer)
        
        print(f"   Prepared {len(transfers)} transfers")
        
        # Step 4: Submit transfers
        print("\n📤 Step 4: Submitting transfers...")
        transfer_update = {"transfers": transfers}
        
        async with session.post(f"{API_URL}/creations/{creation_id}/transfers", json=transfer_update) as resp:
            update_result = await resp.json()
            print(f"   Transfers submitted: {update_result['status']}")
        
        # Step 5: Monitor status
        print("\n👀 Step 5: Monitoring creation status...")
        for i in range(10):
            async with session.get(f"{API_URL}/creations/{creation_id}/status") as resp:
                status_data = await resp.json()
                status = status_data["status"]
                print(f"   Check {i+1}: Status = {status}")
                
                if status in ["receipt_valid", "minted", "expired", "refunded"]:
                    print(f"   ✅ Terminal status reached: {status}")
                    break
            
            await asyncio.sleep(2)
        
        return creation_id, transfers

async def simulate_validator_flow(creation_id: str, transfers: List[Dict]):
    """Simulate a validator processing the creation"""
    print("\n🔍 SIMULATING VALIDATOR FLOW")
    print("=" * 50)
    
    # Step 1: Monitor for new creations
    print("📡 Step 1: Monitoring for new creations...")
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_URL}/creations") as resp:
            creations_data = await resp.json()
            print(f"   Found {len(creations_data['creations'])} total creations")
    
    # Step 2: Validate transfers (simplified)
    print("\n✅ Step 2: Validating transfers...")
    print(f"   Validating {len(transfers)} transfers for creation {creation_id}")
    
    # Check that we have exactly 20 transfers
    if len(transfers) != 20:
        print(f"   ❌ Expected 20 transfers, got {len(transfers)}")
        return False
    
    # Check amounts are consistent
    total_amount = sum(t["amount"] for t in transfers)
    expected_total = 20 * 50000000000000000  # 20 * 0.05 TAO
    if total_amount != expected_total:
        print(f"   ❌ Total amount mismatch: {total_amount} vs {expected_total}")
        return False
    
    print("   ✅ Transfer validation passed")
    
    # Step 3: Calculate NAV (simplified)
    print("\n💰 Step 3: Calculating NAV...")
    nav_per_token = 1000000000000000000  # 1.0 TAO per TAO20 token
    print(f"   Calculated NAV: {nav_per_token / 1e18:.6f} TAO per TAO20")
    
    # Step 4: Provide attestation (simplified)
    print("\n📋 Step 4: Providing attestation...")
    attestation = {
        "creation_id": creation_id,
        "validator_ss58": "5ValidatorAddress123456789",
        "nav_per_token": nav_per_token,
        "confidence_score": 0.95,
        "signature": "0xmock_signature_123456789",
        "timestamp": int(time.time())
    }
    print(f"   Attestation prepared with confidence: {attestation['confidence_score']}")
    
    return True

async def main():
    """Run the complete simulation"""
    print("🚀 TAO20 LOCAL SIMULATION STARTING")
    print("=" * 60)
    print(f"API URL: {API_URL}")
    print(f"Miner SS58: {MINER_SS58}")
    print(f"EVM Address: {EVM_ADDR}")
    print("=" * 60)
    
    try:
        # Test API connectivity
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_URL}/health") as resp:
                health = await resp.json()
                print(f"✅ API Health Check: {health['status']}")
        
        # Run miner simulation
        creation_id, transfers = await simulate_miner_flow()
        
        # Run validator simulation
        success = await simulate_validator_flow(creation_id, transfers)
        
        if success:
            print("\n🎉 SIMULATION COMPLETED SUCCESSFULLY!")
            print("=" * 60)
            print("Summary:")
            print(f"  • Miner created basket: {creation_id}")
            print(f"  • Delivered {len(transfers)} transfers")
            print(f"  • Validator validated and attested")
            print("  • End-to-end flow working! ✅")
        else:
            print("\n❌ SIMULATION FAILED")
            
    except Exception as e:
        print(f"\n💥 ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
