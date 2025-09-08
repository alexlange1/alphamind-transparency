#!/bin/bash
# 🕵️ TAO20 Stealth Testnet Deployment
# Deploys contracts to BEVM testnet WITHOUT source verification for maximum privacy

set -e

echo "🕵️ TAO20 Stealth Testnet Deployment"
echo "=================================="

# Load environment variables
if [ -f "deployment/testnet/config/stealth.env" ]; then
    source deployment/testnet/config/stealth.env
else
    echo "❌ Error: stealth.env not found"
    echo "Create deployment/testnet/config/stealth.env with:"
    echo "TESTNET_PRIVATE_KEY=your_private_key_here"
    echo "TESTNET_RPC_URL=https://testnet-rpc.bevm.io"
    exit 1
fi

# Verify required variables
if [ -z "$TESTNET_PRIVATE_KEY" ]; then
    echo "❌ Error: TESTNET_PRIVATE_KEY not set in stealth.env"
    exit 1
fi

if [ -z "$TESTNET_RPC_URL" ]; then
    echo "❌ Error: TESTNET_RPC_URL not set in stealth.env"
    exit 1
fi

# Get deployer address
DEPLOYER_ADDRESS=$(cast wallet address $TESTNET_PRIVATE_KEY)
echo "🔐 Deployer: $DEPLOYER_ADDRESS"

# Check balance
BALANCE=$(cast balance $DEPLOYER_ADDRESS --rpc-url $TESTNET_RPC_URL)
BALANCE_ETH=$(cast to-unit $BALANCE ether)
echo "💰 Balance: $BALANCE_ETH BTC"

if (( $(echo "$BALANCE_ETH < 0.01" | bc -l) )); then
    echo "⚠️  Warning: Low balance. You may need more testnet BTC."
    echo "💡 Get testnet BTC from BEVM faucet: https://scan-testnet.bevm.io/faucet"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Privacy settings
echo "🔒 Privacy Settings:"
echo "   - Source verification: DISABLED"
echo "   - Contract names: Obfuscated in bytecode"
echo "   - Function names: Hidden"
echo "   - Purpose: Unknown to public"

# Confirmation
echo ""
read -p "🚀 Ready to deploy to testnet stealthily? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled."
    exit 1
fi

# Navigate to contracts directory
cd core/contracts

# Deploy contracts WITHOUT verification (stealth mode)
echo ""
echo "🚀 Deploying contracts in stealth mode..."
echo "======================================="

forge script script/DeployLocalTest.s.sol \
    --rpc-url $TESTNET_RPC_URL \
    --private-key $TESTNET_PRIVATE_KEY \
    --broadcast \
    --legacy \
    --slow

# Note: NO --verify flag = source code remains private!

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Stealth deployment successful!"
    echo ""
    echo "🔒 Privacy Status:"
    echo "   ✅ Contracts deployed but source code is private"
    echo "   ✅ Only bytecode visible on block explorer"
    echo "   ✅ Function names appear as hashes (0xa9059cbb...)"
    echo "   ✅ Your innovation remains secret"
    echo ""
    echo "📄 Contract addresses saved to:"
    echo "   core/contracts/broadcast/DeployLocalTest.s.sol/1501/run-latest.json"
    echo ""
    echo "🎯 Next Steps:"
    echo "   1. Test all functions privately"
    echo "   2. Validate real BEVM integration"
    echo "   3. Verify cross-chain functionality"
    echo "   4. Debug any issues in private"
    echo ""
    echo "💡 To reveal source code later (when ready):"
    echo "   forge verify-contract <CONTRACT_ADDRESS> <CONTRACT_NAME> --rpc-url $TESTNET_RPC_URL"
    echo ""
    echo "🕵️ Stealth deployment complete - your secret is safe!"
else
    echo "❌ Deployment failed"
    exit 1
fi
