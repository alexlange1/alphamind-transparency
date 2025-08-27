#!/usr/bin/env python3
"""
Set up a Bittensor testnet wallet for TAO20 testing
"""

import bittensor as bt
import os
import sys

def create_testnet_wallet():
    """Create a testnet wallet with coldkey and hotkey"""
    
    print("🔑 Setting up Bittensor Testnet Wallet")
    print("=" * 50)
    
    wallet_name = "testnet"
    hotkey_name = "testnet_hotkey"
    
    try:
        # Create wallet object
        wallet = bt.wallet(name=wallet_name, hotkey=hotkey_name)
        print(f"📁 Wallet path: {wallet.path}")
        
        # Check if wallet already exists
        if wallet.coldkey_file.exists_on_device() and wallet.hotkey_file.exists_on_device():
            print("✅ Testnet wallet already exists")
            print(f"🏠 Coldkey address: {wallet.coldkey.ss58_address}")
            print(f"🔥 Hotkey address: {wallet.hotkey.ss58_address}")
            return wallet
        
        # Create new wallet if it doesn't exist
        print("📝 Creating new testnet wallet...")
        
        # Create coldkey
        if not wallet.coldkey_file.exists_on_device():
            print("🏠 Creating coldkey...")
            wallet.create_coldkey_from_uri("//Alice", use_password=False)
            print(f"   ✅ Coldkey created: {wallet.coldkey.ss58_address}")
        
        # Create hotkey  
        if not wallet.hotkey_file.exists_on_device():
            print("🔥 Creating hotkey...")
            wallet.create_hotkey_from_uri("//Alice//stash", use_password=False)
            print(f"   ✅ Hotkey created: {wallet.hotkey.ss58_address}")
        
        print("✅ Testnet wallet setup completed!")
        return wallet
        
    except Exception as e:
        print(f"❌ Failed to create testnet wallet: {e}")
        return None

def check_testnet_balance(wallet):
    """Check wallet balance on test network"""
    
    print("\n💰 Checking Testnet Balance")
    print("=" * 50)
    
    try:
        subtensor = bt.subtensor(network="test")
        
        # Check coldkey balance
        coldkey_balance = subtensor.get_balance(wallet.coldkey.ss58_address)
        print(f"🏠 Coldkey balance: {coldkey_balance} TAO")
        
        # Check hotkey balance
        hotkey_balance = subtensor.get_balance(wallet.hotkey.ss58_address)
        print(f"🔥 Hotkey balance: {hotkey_balance} TAO")
        
        return coldkey_balance, hotkey_balance
        
    except Exception as e:
        print(f"❌ Failed to check balance: {e}")
        return None, None

def get_testnet_faucet_info():
    """Provide information about getting testnet TAO"""
    
    print("\n🚰 Testnet Faucet Information")
    print("=" * 50)
    print("""
For testnet TAO, you typically need to:

1. Join the Bittensor Discord server
2. Go to the #testnet-faucet channel
3. Request testnet TAO using your wallet address
4. Wait for the faucet bot to send you test TAO

Alternatively, you can:
- Check the Bittensor documentation for current faucet endpoints
- Look for community-run faucets
- Use the official Bittensor testnet tools

Your testnet addresses:
""")

def check_subnet_registration(wallet):
    """Check if wallet is registered on target subnet"""
    
    print("\n🌐 Checking Subnet Registration")
    print("=" * 50)
    
    try:
        subtensor = bt.subtensor(network="test")
        target_netuid = 21
        
        # Check if hotkey is registered
        is_registered = subtensor.is_hotkey_registered(
            netuid=target_netuid,
            hotkey_ss58=wallet.hotkey.ss58_address
        )
        
        print(f"🎯 Subnet {target_netuid} registration status: {'✅ Registered' if is_registered else '❌ Not registered'}")
        
        if not is_registered:
            # Get registration cost
            try:
                burn_cost = subtensor.burn(netuid=target_netuid)
                print(f"💸 Registration cost: {burn_cost} TAO")
                print(f"ℹ️  Use: btcli subnet register --netuid {target_netuid} --wallet.name testnet --wallet.hotkey testnet_hotkey")
            except Exception as e:
                print(f"⚠️  Could not get registration cost: {e}")
        
        return is_registered
        
    except Exception as e:
        print(f"❌ Failed to check registration: {e}")
        return False

def main():
    """Main setup function"""
    
    print("🚀 TAO20 Testnet Wallet Setup")
    print("=" * 60)
    
    # Create wallet
    wallet = create_testnet_wallet()
    if not wallet:
        print("❌ Failed to create wallet")
        sys.exit(1)
    
    # Show addresses for faucet requests
    print(f"\n📋 Your Testnet Addresses:")
    print(f"   Coldkey:  {wallet.coldkey.ss58_address}")
    print(f"   Hotkey:   {wallet.hotkey.ss58_address}")
    
    # Check balances
    coldkey_bal, hotkey_bal = check_testnet_balance(wallet)
    
    # Check registration status
    is_registered = check_subnet_registration(wallet)
    
    # Provide next steps
    print(f"\n📋 Next Steps:")
    if coldkey_bal and coldkey_bal.tao < 1:
        print("1. 🚰 Get testnet TAO from faucet (need at least 1 TAO)")
        get_testnet_faucet_info()
    
    if not is_registered:
        print("2. 🌐 Register on subnet 21 once you have testnet TAO")
    
    print("3. 🚀 Update testnet.env with your addresses")
    print("4. 🔧 Deploy contracts to testnet")
    
    # Update testnet.env file
    try:
        with open("testnet.env", "r") as f:
            content = f.read()
        
        # Replace placeholder addresses
        content = content.replace(
            "TAO20_SOURCE_SS58=5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
            f"TAO20_SOURCE_SS58={wallet.hotkey.ss58_address}"
        )
        
        with open("testnet.env", "w") as f:
            f.write(content)
        
        print(f"✅ Updated testnet.env with your hotkey address")
        
    except Exception as e:
        print(f"⚠️  Could not update testnet.env: {e}")

if __name__ == "__main__":
    main()
