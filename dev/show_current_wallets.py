#!/usr/bin/env python3
"""
Display Current TAO20 Wallet Information
Shows both generated wallets and current Anvil accounts
"""

import json
import os
from web3 import Web3
from eth_account import Account
import hashlib

class WalletDisplay:
    """Display wallet information for TAO20 system"""
    
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider('http://localhost:8545'))
    
    def derive_substrate_address(self, bevm_address: str) -> str:
        """Derive Substrate address from BEVM address"""
        prefix = b"evm:"
        address_bytes = bytes.fromhex(bevm_address[2:])
        data = prefix + address_bytes
        substrate_pubkey = hashlib.sha256(data).digest()
        return f"5{substrate_pubkey.hex()[:40]}..." # Simplified display
    
    def show_anvil_accounts(self):
        """Show current Anvil accounts with derived Substrate addresses"""
        
        print("🔧 CURRENT ANVIL ACCOUNTS")
        print("="*80)
        print("These are the accounts currently running in your Anvil instance:")
        print()
        
        # Anvil default accounts (well-known for development)
        anvil_accounts = [
            {
                "index": 0,
                "address": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
                "private_key": "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
                "balance": "10000 ETH"
            },
            {
                "index": 1, 
                "address": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
                "private_key": "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d",
                "balance": "10000 ETH"
            },
            {
                "index": 2,
                "address": "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC", 
                "private_key": "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a",
                "balance": "10000 ETH"
            }
        ]
        
        for account in anvil_accounts:
            substrate_addr = self.derive_substrate_address(account["address"])
            
            print(f"📝 Account {account['index']}:")
            print(f"   BEVM Address:      {account['address']}")
            print(f"   Private Key:       {account['private_key']}")
            print(f"   Substrate Vault:   {substrate_addr}")
            print(f"   Balance:           {account['balance']}")
            print()
        
        print("💡 TIP: Use Account 0 for deploying contracts (it's already funded)")
    
    def show_deployed_contracts(self):
        """Show currently deployed contract addresses"""
        
        print("\n🏗️ DEPLOYED CONTRACTS")
        print("="*80)
        
        contracts = {
            "TAO20Core": "0xa513E6E4b8f2a923D98304ec87F64353C4D5C853",
            "TAO20Token": "0x9bd03768a7DCc129555dE410FF8E85528A4F88b5", 
            "Vault": "0x9E545E3C0baAB3E08CdfD552C960A1050f373042",
            "NAVCalculator": "0x0165878A594ca255338adfa4d48449f69242Eb8F",
            "StakingManager": "0x5FC8d32690cc91D4c39d9d3abcBD16989F875707"
        }
        
        for name, address in contracts.items():
            substrate_vault = self.derive_substrate_address(address)
            
            print(f"📄 {name}:")
            print(f"   BEVM Address:      {address}")
            print(f"   Substrate Vault:   {substrate_vault}")
            print()
    
    def show_production_wallets(self):
        """Show generated production wallets"""
        
        # Find the most recent wallet file
        wallet_dir = "secrets/wallets"
        if not os.path.exists(wallet_dir):
            print("⚠️  No production wallets found. Run generate_production_wallets.py first.")
            return
        
        wallet_files = [f for f in os.listdir(wallet_dir) if f.startswith("tao20_wallets_")]
        if not wallet_files:
            print("⚠️  No production wallets found.")
            return
        
        latest_file = sorted(wallet_files)[-1]
        filepath = os.path.join(wallet_dir, latest_file)
        
        print("\n🏦 PRODUCTION WALLETS")
        print("="*80)
        print(f"📁 Source: {filepath}")
        print()
        
        with open(filepath, 'r') as f:
            wallets = json.load(f)
        
        for name, wallet in wallets["production"].items():
            print(f"📝 {name.upper()}:")
            print(f"   Seed Phrase:       {wallet['seed_phrase']}")
            print(f"   BEVM Address:      {wallet['bevm']['address']}")
            print(f"   Private Key:       {wallet['bevm']['private_key']}")
            print(f"   Substrate Address: {wallet['substrate']['ss58_address']}")
            print()
    
    def show_usage_examples(self):
        """Show usage examples"""
        
        print("\n💡 USAGE EXAMPLES")
        print("="*80)
        
        print("🚀 Deploy with Anvil Account 0:")
        print("   forge script script/DeployLocalTest.s.sol \\")
        print("     --rpc-url http://localhost:8545 \\")
        print("     --private-key 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 \\")
        print("     --broadcast")
        print()
        
        print("🦊 Import to MetaMask:")
        print("   1. Network: BEVM Local")
        print("   2. RPC URL: http://localhost:8545") 
        print("   3. Chain ID: 11501")
        print("   4. Private Key: 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80")
        print()
        
        print("🔗 Substrate Vault for Contract 0x9E54...:")
        print("   Users deposit Alpha tokens to: 5Gik2qiEzGM...")
        print("   Contract monitors this address for deposits")
        print()
        
        print("🐍 Python Integration:")
        print("   python test_real_contracts.py  # Test with deployed contracts")
        print("   python test_local_integration.py  # Full integration test")

def main():
    """Main display function"""
    
    print("🔍 TAO20 CURRENT WALLET STATUS")
    print("="*80)
    print("This shows all wallet information for your TAO20 deployment")
    print()
    
    display = WalletDisplay()
    
    # Show current Anvil accounts
    display.show_anvil_accounts()
    
    # Show deployed contracts
    display.show_deployed_contracts()
    
    # Show production wallets
    display.show_production_wallets()
    
    # Show usage examples
    display.show_usage_examples()
    
    print("\n✅ Complete wallet information displayed!")
    print("🔒 Remember: Keep private keys and seed phrases secure!")

if __name__ == "__main__":
    main()
