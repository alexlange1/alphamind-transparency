#!/bin/bash

# Alphamind Deployment Script
# Deploys smart contracts and subnet components

set -e

echo "🚀 Deploying Alphamind ($TAO20)..."

# Check prerequisites
command -v forge >/dev/null 2>&1 || { echo "❌ Foundry not found. Please install Foundry first."; exit 1; }
command -v node >/dev/null 2>&1 || { echo "❌ Node.js not found. Please install Node.js first."; exit 1; }

# Deploy smart contracts
echo "📦 Deploying smart contracts..."
cd contracts
forge build
forge script script/Deploy.s.sol --rpc-url $BEVM_RPC_URL --broadcast --verify

# Deploy subnet
echo "🌐 Deploying subnet components..."
cd ../subnet
python -m pip install -r requirements.txt
python cli.py deploy --network mainnet

echo "✅ Deployment complete!"
echo "📊 Contract addresses:"
echo "   TAO20 Token: $TAO20_ADDRESS"
echo "   Minter: $MINTER_ADDRESS"
echo "   Vault: $VAULT_ADDRESS"
