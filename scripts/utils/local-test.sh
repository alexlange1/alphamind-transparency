#!/bin/bash

# TAO20 Local Testing Script
# This script provides a complete local testing environment for TAO20

set -e

echo "🚀 TAO20 Local Testing Environment"
echo "================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if Foundry is installed
if ! command -v forge &> /dev/null; then
    echo -e "${RED}❌ Foundry not found. Please install Foundry first:"
    echo -e "   curl -L https://foundry.paradigm.xyz | bash"
    echo -e "   foundryup${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Foundry found${NC}"

# Change to contracts directory
cd contracts

echo -e "\n${BLUE}📋 Step 1: Running Unit Tests${NC}"
echo "Running comprehensive test suite..."
forge test

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Unit tests completed successfully${NC}"
else
    echo -e "${YELLOW}⚠️  Some tests failed, but continuing with deployment tests...${NC}"
fi

echo -e "\n${BLUE}🔧 Step 2: Starting Local Blockchain${NC}"
echo "Starting Anvil local blockchain in background..."

# Kill any existing anvil processes
pkill -f anvil || true

# Start Anvil in background with a fixed private key for consistency
anvil --host 0.0.0.0 --port 8545 --accounts 10 --balance 10000 &
ANVIL_PID=$!

# Wait for Anvil to start
sleep 3

echo -e "${GREEN}✅ Anvil started (PID: $ANVIL_PID)${NC}"
echo "Local blockchain running at http://localhost:8545"

# Export environment variables for deployment
export PRIVATE_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
export RPC_URL=http://localhost:8545

echo -e "\n${BLUE}🚀 Step 3: Deploying Contracts${NC}"
echo "Deploying TAO20 system to local blockchain..."

# Deploy contracts
DEPLOYMENT_OUTPUT=$(forge script script/Deploy.s.sol:DeployScript --rpc-url $RPC_URL --broadcast --private-key $PRIVATE_KEY 2>&1)

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Contracts deployed successfully${NC}"
    
    # Extract contract addresses from deployment output
    VAULT_ADDRESS=$(echo "$DEPLOYMENT_OUTPUT" | grep "Vault:" | tail -1 | awk '{print $2}')
    ORACLE_ADDRESS=$(echo "$DEPLOYMENT_OUTPUT" | grep "OracleAggregator:" | tail -1 | awk '{print $2}')
    
    export VAULT_ADDRESS
    export ORACLE_ADDRESS
    
    echo -e "\n${BLUE}📊 Step 4: Testing Contract Interactions${NC}"
    echo "Testing minting, oracle updates, and fee accrual..."
    
    # Run interaction script
    forge script script/Interact.s.sol:InteractScript --rpc-url $RPC_URL --broadcast --private-key $PRIVATE_KEY
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Contract interactions completed successfully${NC}"
        
        echo -e "\n${GREEN}🎉 LOCAL TESTING COMPLETE! ${NC}"
        echo -e "${BLUE}Your TAO20 system is running locally and ready for testing.${NC}"
        echo ""
        echo "🔗 Local Blockchain: http://localhost:8545"
        echo "📋 Contract Addresses:"
        echo "   Vault: $VAULT_ADDRESS"
        echo "   Oracle: $ORACLE_ADDRESS"
        echo ""
        echo "🛠️  Next steps:"
        echo "   1. Use a wallet (MetaMask) with RPC http://localhost:8545"
        echo "   2. Import private key: 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
        echo "   3. Interact with contracts using the addresses above"
        echo "   4. Run 'forge test' anytime to verify functionality"
        echo ""
        echo "💡 To stop the local blockchain: kill $ANVIL_PID"
        
    else
        echo -e "${RED}❌ Contract interaction failed${NC}"
    fi
else
    echo -e "${RED}❌ Contract deployment failed${NC}"
    kill $ANVIL_PID
    exit 1
fi

# Keep the script running to maintain blockchain
echo -e "\n${YELLOW}🔄 Local blockchain will continue running..."
echo -e "Press Ctrl+C to stop the blockchain and exit${NC}"

# Trap Ctrl+C to cleanup
trap "echo -e '\n${YELLOW}🛑 Stopping local blockchain...${NC}'; kill $ANVIL_PID; exit 0" INT

# Wait for user to stop
wait $ANVIL_PID
