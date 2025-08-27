#!/usr/bin/env python3
"""
Test Bittensor network connection and available networks
"""

import bittensor as bt
import sys

def test_networks():
    """Test connection to different Bittensor networks"""
    
    networks = ["finney", "test", "local"]
    
    print("🔗 Testing Bittensor Network Connections")
    print("=" * 50)
    
    for network in networks:
        try:
            print(f"\n📡 Testing {network} network...")
            subtensor = bt.subtensor(network=network)
            
            # Test basic connectivity
            block_number = subtensor.get_current_block()
            print(f"   ✅ Connected to {network}")
            print(f"   📊 Current block: {block_number}")
            
            # Get network info
            try:
                difficulty = subtensor.difficulty()
                print(f"   🔥 Network difficulty: {difficulty}")
            except:
                print(f"   ⚠️  Could not get difficulty for {network}")
            
            # List some subnets
            try:
                subnets = subtensor.get_subnets()
                print(f"   🌐 Total subnets: {len(subnets)}")
                if subnets:
                    print(f"   📋 First few subnets: {subnets[:5]}")
            except Exception as e:
                print(f"   ⚠️  Could not get subnets: {e}")
                
        except Exception as e:
            print(f"   ❌ Failed to connect to {network}: {e}")
    
    return True

def test_wallet_creation():
    """Test wallet creation and operations"""
    
    print("\n\n🔑 Testing Wallet Operations")
    print("=" * 50)
    
    try:
        # Create a test wallet
        print("\n📝 Creating test wallet...")
        wallet_name = "testnet_wallet"
        hotkey_name = "testnet_hotkey"
        
        # Note: This will create actual wallet files, so be careful
        print(f"   Wallet name: {wallet_name}")
        print(f"   Hotkey name: {hotkey_name}")
        
        # For safety, we'll just check if we can instantiate a wallet object
        # without actually creating files
        wallet = bt.wallet()
        print(f"   ✅ Wallet object created")
        print(f"   🔑 Default wallet path: {wallet.path}")
        
        # Check default addresses (these will be random if no wallet exists)
        try:
            coldkey_address = wallet.coldkey.ss58_address if wallet.coldkey else "Not available"
            hotkey_address = wallet.hotkey.ss58_address if wallet.hotkey else "Not available"
            print(f"   🏠 Coldkey address: {coldkey_address}")
            print(f"   🔥 Hotkey address: {hotkey_address}")
        except Exception as e:
            print(f"   ⚠️  No existing wallet found: {e}")
            
    except Exception as e:
        print(f"   ❌ Wallet test failed: {e}")

def check_subnet_info():
    """Check specific subnet information"""
    
    print("\n\n🌐 Checking Subnet Information")
    print("=" * 50)
    
    try:
        subtensor = bt.subtensor(network="finney")
        
        # Check if our target subnet exists
        target_netuid = 21  # TAO20 subnet
        
        print(f"\n🎯 Checking subnet {target_netuid}...")
        
        try:
            subnet_info = subtensor.get_subnet_info(target_netuid)
            print(f"   ✅ Subnet {target_netuid} exists")
            print(f"   📊 Registration cost: {subnet_info.burn if hasattr(subnet_info, 'burn') else 'Unknown'}")
            print(f"   👥 Max neurons: {subnet_info.max_n if hasattr(subnet_info, 'max_n') else 'Unknown'}")
        except Exception as e:
            print(f"   ⚠️  Subnet {target_netuid} info: {e}")
            
            # Try to list available subnets
            try:
                subnets = subtensor.get_subnets()
                print(f"   📋 Available subnets: {subnets}")
            except Exception as e2:
                print(f"   ❌ Could not list subnets: {e2}")
                
    except Exception as e:
        print(f"   ❌ Subnet check failed: {e}")

if __name__ == "__main__":
    print("🚀 Bittensor Connection Test")
    print("=" * 60)
    
    try:
        test_networks()
        test_wallet_creation()
        check_subnet_info()
        
        print("\n\n✅ Connection test completed!")
        print("Check the output above for network status.")
        
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        sys.exit(1)
