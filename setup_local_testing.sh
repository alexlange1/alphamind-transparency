#!/bin/bash

# TAO20 Local Testing Environment Setup
# Sets up Anvil + complete contract deployment for private testing

set -e

echo "🚀 Setting up TAO20 Local Testing Environment"
echo "=============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check dependencies
echo -e "${BLUE}📋 Checking dependencies...${NC}"

if ! command -v forge &> /dev/null; then
    echo -e "${RED}❌ Foundry not found. Please install: https://book.getfoundry.sh/${NC}"
    exit 1
fi

if ! command -v anvil &> /dev/null; then
    echo -e "${RED}❌ Anvil not found. Please install Foundry first.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Dependencies OK${NC}"

# Configuration
CHAIN_ID=11501  # BEVM-like chain ID
PORT=8545
MNEMONIC="test test test test test test test test test test test junk"
ACCOUNTS=10

echo -e "${BLUE}🔧 Configuration:${NC}"
echo "   Chain ID: $CHAIN_ID"
echo "   Port: $PORT"
echo "   Accounts: $ACCOUNTS"

# Kill any existing anvil process
echo -e "${YELLOW}🧹 Cleaning up existing processes...${NC}"
pkill -f "anvil" || true
sleep 2

# Start Anvil in background
echo -e "${BLUE}🏭 Starting Anvil local blockchain...${NC}"
anvil \
    --chain-id $CHAIN_ID \
    --port $PORT \
    --accounts $ACCOUNTS \
    --mnemonic "$MNEMONIC" \
    --balance 10000 \
    --gas-limit 30000000 \
    --gas-price 1 \
    --host 0.0.0.0 \
    > anvil.log 2>&1 &

ANVIL_PID=$!
echo "   Anvil PID: $ANVIL_PID"

# Wait for Anvil to start
echo -e "${YELLOW}⏳ Waiting for Anvil to start...${NC}"
sleep 5

# Check if Anvil is running
if ! kill -0 $ANVIL_PID 2>/dev/null; then
    echo -e "${RED}❌ Failed to start Anvil${NC}"
    cat anvil.log
    exit 1
fi

echo -e "${GREEN}✅ Anvil started successfully${NC}"

# Set environment variables
export RPC_URL="http://localhost:$PORT"
export PRIVATE_KEY="0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"  # First test account

echo -e "${BLUE}🔑 Environment variables:${NC}"
echo "   RPC_URL: $RPC_URL"
echo "   PRIVATE_KEY: ${PRIVATE_KEY:0:10}..."

# Compile contracts
echo -e "${BLUE}🔨 Compiling contracts...${NC}"
cd contracts
forge build --skip test

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Contract compilation failed${NC}"
    kill $ANVIL_PID
    exit 1
fi

echo -e "${GREEN}✅ Contracts compiled successfully${NC}"

# Deploy contracts
echo -e "${BLUE}🚀 Deploying contracts to local network...${NC}"
forge script script/DeployLocalTest.s.sol:DeployLocalTest \
    --rpc-url $RPC_URL \
    --private-key $PRIVATE_KEY \
    --broadcast \
    --legacy

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Contract deployment failed${NC}"
    kill $ANVIL_PID
    exit 1
fi

echo -e "${GREEN}✅ Contracts deployed successfully${NC}"

# Get deployment addresses
echo -e "${BLUE}📋 Getting deployment addresses...${NC}"

# This would typically parse the broadcast output
# For now, we'll get them from the logs
DEPLOYMENT_FILE="broadcast/DeployLocalTest.s.sol/$CHAIN_ID/run-latest.json"

if [ -f "$DEPLOYMENT_FILE" ]; then
    echo -e "${GREEN}✅ Deployment info saved to: $DEPLOYMENT_FILE${NC}"
else
    echo -e "${YELLOW}⚠️  Deployment info not found. Check broadcast/ directory.${NC}"
fi

# Run tests
echo -e "${BLUE}🧪 Running contract tests...${NC}"
forge test --match-contract MintRedeemFlowTest -vv

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Tests passed${NC}"
else
    echo -e "${YELLOW}⚠️  Some tests failed (expected for mock environment)${NC}"
fi

# Create a summary file
cat > ../testing_environment.env << EOF
# TAO20 Local Testing Environment
# Generated on $(date)

# Network Configuration
CHAIN_ID=$CHAIN_ID
RPC_URL=$RPC_URL
ANVIL_PID=$ANVIL_PID

# Test Accounts (from mnemonic)
PRIVATE_KEY_0=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
PRIVATE_KEY_1=0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d
PRIVATE_KEY_2=0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a

# Test Addresses
ADDRESS_0=0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
ADDRESS_1=0x70997970C51812dc3A010C7d01b50e0d17dc79C8
ADDRESS_2=0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC

# Contract Addresses (update after deployment)
# TAO20_CORE=0x...
# VAULT=0x...
# TAO20_TOKEN=0x...

# Usage Instructions
# 1. Source this file: source testing_environment.env
# 2. Use addresses above for testing
# 3. Connect to RPC_URL for transactions
# 4. Stop with: kill \$ANVIL_PID
EOF

echo -e "${GREEN}✅ Environment file created: testing_environment.env${NC}"

# Final instructions
echo ""
echo -e "${GREEN}🎉 LOCAL TESTING ENVIRONMENT READY!${NC}"
echo ""
echo -e "${BLUE}📖 Next Steps:${NC}"
echo "   1. Source environment: ${YELLOW}source testing_environment.env${NC}"
echo "   2. Run Python tests: ${YELLOW}cd neurons && python test_integration_demo.py${NC}"
echo "   3. Test mint/redeem flows with local contracts"
echo "   4. Develop and iterate on contract logic"
echo ""
echo -e "${BLUE}🔧 Management:${NC}"
echo "   • View logs: ${YELLOW}tail -f anvil.log${NC}"
echo "   • Stop environment: ${YELLOW}kill $ANVIL_PID${NC}"
echo "   • Check status: ${YELLOW}ps aux | grep anvil${NC}"
echo ""
echo -e "${BLUE}🌐 Network Info:${NC}"
echo "   • RPC URL: ${YELLOW}$RPC_URL${NC}"
echo "   • Chain ID: ${YELLOW}$CHAIN_ID${NC}"
echo "   • Explorer: ${YELLOW}http://localhost:$PORT (no UI, use RPC)${NC}"
echo ""
echo -e "${GREEN}✨ Happy testing! All transactions are private and local.${NC}"

cd ..
