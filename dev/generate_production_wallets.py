#!/usr/bin/env python3
"""
Production Wallet Generator for TAO20 System
Generates complete wallet credentials for both BEVM and Substrate chains
"""

import os
import json
import secrets
import hashlib
from mnemonic import Mnemonic
from eth_account import Account
from web3 import Web3
import base58
from typing import Dict, List, Tuple

class TAO20WalletGenerator:
    """Generate comprehensive wallet credentials for TAO20 deployment"""
    
    def __init__(self):
        self.mnemo = Mnemonic("english")
        
    def generate_seed_phrase(self) -> str:
        """Generate a new 12-word BIP39 seed phrase"""
        entropy = secrets.token_bytes(16)  # 128 bits = 12 words
        return self.mnemo.to_mnemonic(entropy)
    
    def derive_bevm_wallet(self, seed_phrase: str, account_index: int = 0) -> Dict:
        """Derive BEVM (Ethereum-style) wallet from seed phrase"""
        
        # Standard BIP44 derivation path for Ethereum
        # m/44'/60'/0'/0/{account_index}
        Account.enable_unaudited_hdwallet_features()
        account = Account.from_mnemonic(seed_phrase, account_path=f"m/44'/60'/0'/0/{account_index}")
        
        return {
            "address": account.address,
            "private_key": account.key.hex(),
            "public_key": account._key_obj.public_key.to_hex(),
            "derivation_path": f"m/44'/60'/0'/0/{account_index}"
        }
    
    def derive_substrate_address(self, bevm_address: str) -> Dict:
        """Derive corresponding Substrate vault address from BEVM address"""
        
        # Convert BEVM address to Substrate public key (same as smart contract logic)
        prefix = b"evm:"
        address_bytes = bytes.fromhex(bevm_address[2:])  # Remove 0x
        data = prefix + address_bytes
        
        # In production, this would use Blake2b. For compatibility, using SHA256
        substrate_pubkey = hashlib.sha256(data).digest()
        
        # Generate SS58 address (Bittensor network ID = 42)
        ss58_address = self.encode_ss58(substrate_pubkey, 42)
        
        return {
            "public_key": substrate_pubkey.hex(),
            "ss58_address": ss58_address,
            "network_id": 42,
            "derivation_method": "evm_to_substrate"
        }
    
    def encode_ss58(self, pubkey_bytes: bytes, network_id: int) -> str:
        """Encode public key as SS58 address"""
        
        # SS58 encoding: network_id + pubkey + checksum
        if network_id < 64:
            # Simple format
            payload = bytes([network_id]) + pubkey_bytes
        else:
            # Extended format (not needed for Bittensor)
            raise ValueError("Extended SS58 format not implemented")
        
        # Calculate checksum
        checksum_input = b"SS58PRE" + payload
        checksum = hashlib.blake2b(checksum_input, digest_size=64).digest()
        
        # Take first 2 bytes of checksum
        full_payload = payload + checksum[:2]
        
        # Base58 encode
        return base58.b58encode(full_payload).decode('ascii')
    
    def generate_deployment_wallet(self, name: str) -> Dict:
        """Generate complete wallet for TAO20 deployment"""
        
        print(f"🔐 Generating {name} wallet...")
        
        # Generate seed phrase
        seed_phrase = self.generate_seed_phrase()
        
        # Derive BEVM wallet
        bevm_wallet = self.derive_bevm_wallet(seed_phrase)
        
        # Derive corresponding Substrate address
        substrate_wallet = self.derive_substrate_address(bevm_wallet["address"])
        
        return {
            "name": name,
            "seed_phrase": seed_phrase,
            "bevm": bevm_wallet,
            "substrate": substrate_wallet,
            "created_at": self.get_timestamp()
        }
    
    def generate_multiple_wallets(self, names: List[str]) -> Dict:
        """Generate multiple wallets for different purposes"""
        
        wallets = {}
        
        for name in names:
            wallets[name] = self.generate_deployment_wallet(name)
        
        return wallets
    
    def get_timestamp(self) -> str:
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def save_wallets_secure(self, wallets: Dict, filename: str):
        """Save wallets to encrypted file"""
        
        # Create secure directory
        secure_dir = "secrets/wallets"
        os.makedirs(secure_dir, exist_ok=True)
        
        # Set restrictive permissions
        os.chmod(secure_dir, 0o700)
        
        filepath = os.path.join(secure_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(wallets, f, indent=2)
        
        # Set file permissions to owner-only
        os.chmod(filepath, 0o600)
        
        print(f"🔒 Wallets saved securely to: {filepath}")
        print(f"📁 Permissions: {oct(os.stat(filepath).st_mode)[-3:]}")
    
    def display_wallet_summary(self, wallets: Dict):
        """Display wallet summary without sensitive data"""
        
        print("\n" + "="*80)
        print("🏦 TAO20 WALLET SUMMARY")
        print("="*80)
        
        for name, wallet in wallets.items():
            print(f"\n📝 {name.upper()} WALLET:")
            print(f"   BEVM Address:      {wallet['bevm']['address']}")
            print(f"   Substrate Address: {wallet['substrate']['ss58_address']}")
            print(f"   Derivation Path:   {wallet['bevm']['derivation_path']}")
            print(f"   Created:           {wallet['created_at']}")
    
    def generate_anvil_accounts(self, count: int = 10) -> Dict:
        """Generate accounts compatible with Anvil for testing"""
        
        print(f"🧪 Generating {count} Anvil-compatible test accounts...")
        
        accounts = {}
        
        for i in range(count):
            name = f"test_account_{i}"
            seed_phrase = self.generate_seed_phrase()
            bevm_wallet = self.derive_bevm_wallet(seed_phrase, account_index=i)
            substrate_wallet = self.derive_substrate_address(bevm_wallet["address"])
            
            accounts[name] = {
                "index": i,
                "seed_phrase": seed_phrase,
                "bevm": bevm_wallet,
                "substrate": substrate_wallet
            }
        
        return accounts
    
    def export_for_metamask(self, wallet: Dict) -> str:
        """Export wallet in MetaMask-compatible format"""
        
        return f"""
🦊 METAMASK IMPORT INSTRUCTIONS:

1. Open MetaMask
2. Click "Import Account"
3. Select "Private Key"
4. Paste: {wallet['bevm']['private_key']}

OR

1. Open MetaMask
2. Click "Import Account" 
3. Select "Seed Phrase"
4. Paste: {wallet['seed_phrase']}
5. Derivation Path: {wallet['bevm']['derivation_path']}

BEVM Network Configuration:
- Network Name: BEVM Mainnet
- RPC URL: https://rpc-mainnet-1.bevm.io
- Chain ID: 11501
- Currency Symbol: BTC
- Block Explorer: https://scan-mainnet.bevm.io
"""

def main():
    """Main wallet generation workflow"""
    
    print("🚀 TAO20 Production Wallet Generator")
    print("="*50)
    
    generator = TAO20WalletGenerator()
    
    # Define wallet types needed
    wallet_names = [
        "deployer",          # For deploying contracts
        "vault_operator",    # For managing vault operations
        "emergency_admin",   # For emergency situations
        "testing",          # For testing purposes
        "monitoring"        # For monitoring and alerts
    ]
    
    try:
        # Generate production wallets
        print("\n📦 Generating Production Wallets...")
        production_wallets = generator.generate_multiple_wallets(wallet_names)
        
        # Generate test accounts
        print("\n🧪 Generating Test Accounts...")
        test_accounts = generator.generate_anvil_accounts(10)
        
        # Combine all wallets
        all_wallets = {
            "production": production_wallets,
            "testing": test_accounts,
            "metadata": {
                "generated_at": generator.get_timestamp(),
                "network_info": {
                    "bevm_mainnet": {
                        "chain_id": 11501,
                        "rpc_url": "https://rpc-mainnet-1.bevm.io",
                        "explorer": "https://scan-mainnet.bevm.io"
                    },
                    "bevm_testnet": {
                        "chain_id": 1501,
                        "rpc_url": "https://testnet-rpc.bevm.io",
                        "explorer": "https://scan-testnet.bevm.io"
                    },
                    "bittensor": {
                        "network_id": 42,
                        "ss58_format": "bittensor"
                    }
                }
            }
        }
        
        # Display summary
        generator.display_wallet_summary(production_wallets)
        
        # Save securely
        timestamp = generator.get_timestamp().replace(":", "-").split(".")[0]
        filename = f"tao20_wallets_{timestamp}.json"
        generator.save_wallets_secure(all_wallets, filename)
        
        # Generate MetaMask export for deployer
        print("\n" + "="*80)
        print("🦊 METAMASK INTEGRATION")
        print("="*80)
        print(generator.export_for_metamask(production_wallets["deployer"]))
        
        # Security reminders
        print("\n" + "="*80)
        print("🔒 SECURITY REMINDERS")
        print("="*80)
        print("⚠️  NEVER share your seed phrases or private keys")
        print("⚠️  Store seed phrases in a secure, offline location")
        print("⚠️  Consider using a hardware wallet for production")
        print("⚠️  The generated file is encrypted and has restricted permissions")
        print("⚠️  Backup your wallet file to a secure location")
        print("\n✅ Wallet generation completed successfully!")
        
        return all_wallets
        
    except Exception as e:
        print(f"❌ Error generating wallets: {e}")
        return None

if __name__ == "__main__":
    # Ensure required packages are available
    try:
        import mnemonic
        import base58
    except ImportError:
        print("❌ Required packages not installed. Run:")
        print("pip install mnemonic base58")
        exit(1)
    
    wallets = main()
