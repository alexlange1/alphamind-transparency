#!/bin/bash
"""
Oracle-Free TAO20 System Deployment Script
Deploys contracts to local testnet for integration testing
"""

set -e

echo "🚀 Deploying Oracle-Free TAO20 System..."

# Check if forge is available
if ! command -v forge &> /dev/null; then
    echo "❌ Forge not found. Please install Foundry first."
    exit 1
fi

# Create deployment directory
mkdir -p deployments

# Start local test network if not running
echo "📡 Starting local test network..."
if ! pgrep -f "anvil" > /dev/null; then
    echo "Starting Anvil local testnet..."
    anvil --port 8545 --chain-id 31337 --accounts 10 --balance 1000 > anvil.log 2>&1 &
    sleep 3
fi

# Deploy contracts
echo "📝 Deploying contracts..."

# Deploy StakingManager first
echo "Deploying StakingManager..."
STAKING_MANAGER=$(forge create src/StakingManager.sol:StakingManager \
    --rpc-url http://localhost:8545 \
    --private-key 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 \
    --json | jq -r '.deployedTo')

echo "StakingManager deployed to: $STAKING_MANAGER"

# Deploy OracleFreeNAVCalculator
echo "Deploying OracleFreeNAVCalculator..."
NAV_CALCULATOR=$(forge create src/OracleFreeNAVCalculator.sol:OracleFreeNAVCalculator \
    --rpc-url http://localhost:8545 \
    --private-key 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 \
    --constructor-args $STAKING_MANAGER \
    --json | jq -r '.deployedTo')

echo "OracleFreeNAVCalculator deployed to: $NAV_CALCULATOR"

# Deploy TAO20CoreV2OracleFree
echo "Deploying TAO20CoreV2OracleFree..."
CORE_CONTRACT=$(forge create src/TAO20CoreV2OracleFree.sol:TAO20CoreV2OracleFree \
    --rpc-url http://localhost:8545 \
    --private-key 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 \
    --constructor-args $STAKING_MANAGER $NAV_CALCULATOR "TAO20 Oracle-Free Index" "TAO20" \
    --json | jq -r '.deployedTo')

echo "TAO20CoreV2OracleFree deployed to: $CORE_CONTRACT"

# Get the TAO20 token address
echo "Getting TAO20 token address..."
TAO20_TOKEN=$(cast call $CORE_CONTRACT "tao20Token()" --rpc-url http://localhost:8545 | xargs printf "%s")

echo "TAO20V2 token address: $TAO20_TOKEN"

# Save deployment info
cat > deployments/oracle_free_local.json << EOF
{
  "network": "local",
  "chain_id": 31337,
  "rpc_url": "http://localhost:8545",
  "deployment_timestamp": $(date +%s),
  "contracts": {
    "StakingManager": "$STAKING_MANAGER",
    "OracleFreeNAVCalculator": "$NAV_CALCULATOR", 
    "TAO20CoreV2OracleFree": "$CORE_CONTRACT",
    "TAO20V2": "$TAO20_TOKEN"
  },
  "test_accounts": {
    "deployer": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
    "tester1": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
    "tester2": "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC"
  },
  "private_keys": {
    "deployer": "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
    "tester1": "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d",
    "tester2": "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"
  }
}
EOF

echo "✅ Deployment completed!"
echo ""
echo "📋 Deployment Summary:"
echo "  StakingManager:           $STAKING_MANAGER"
echo "  OracleFreeNAVCalculator:  $NAV_CALCULATOR"
echo "  TAO20CoreV2OracleFree:    $CORE_CONTRACT"  
echo "  TAO20V2 Token:            $TAO20_TOKEN"
echo ""
echo "💡 To test the integration:"
echo "  export TAO20_CONTRACT_ADDRESS=$CORE_CONTRACT"
echo "  export BEVM_RPC_URL=http://localhost:8545"
echo "  export TEST_PRIVATE_KEY=0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
echo "  cd ../neurons && python test_oracle_free_integration.py"
echo ""
echo "📁 Deployment info saved to: deployments/oracle_free_local.json"
